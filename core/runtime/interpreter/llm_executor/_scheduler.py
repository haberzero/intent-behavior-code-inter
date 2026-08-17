"""``_SchedulerMixin`` —— LLMScheduler 能力。

提供 ``dispatch_eager`` / ``resolve_future_cps`` / ``close`` 接口与惰性线程池管理，
支持 behavior 表达式的并发 LLM 调用。依赖 :class:`LLMExecutorCore` 初始化的
LLMScheduler 共享状态 (``self._max_workers`` / ``self._thread_pool`` /
``self._pending_futures`` / ``self._pending_futures_lock``)，并调用
:class:`_BehaviorMixin` 提供的 :meth:`_prepare_behavior_call`（同步薄包装，
经 :meth:`_pump_cps` 驱动 CPS 权威版本）。
"""

from concurrent.futures import ThreadPoolExecutor as _ThreadPoolExecutor
from typing import Any, Optional

from core.runtime.interfaces import IExecutionContext

from core.runtime.shared.llm_result import LLMResult, LLMFuture


class _SchedulerMixin:
    # ---------------------------------------------------------------------------
    # LLMScheduler — dispatch_eager / resolve / 线程池管理
    # ---------------------------------------------------------------------------

    def _get_thread_pool(self) -> _ThreadPoolExecutor:
        """惰性初始化线程池（首次 dispatch_eager 调用时创建）。

        线程池已通过 :meth:`close` 关闭后，禁止再次获取（fail-fast）——
        否则会在不知情下静默重建新池，破坏"已关闭"资源生命周期不变量。
        """
        if self._closed:
            raise RuntimeError(
                "LLMExecutorImpl 线程池已关闭（close() 已调用），禁止再次 dispatch_eager/run_batch。"
            )
        if self._thread_pool is None:
            self._thread_pool = _ThreadPoolExecutor(max_workers=self._max_workers)
        return self._thread_pool

    def dispatch_eager(
        self,
        node_uid: str,
        execution_context: IExecutionContext,
        intent_ctx: Optional[Any] = None,
    ) -> LLMFuture:
        """同步薄包装：经 :meth:`_pump_cps` 驱动 CPS 权威版本。

        供无 CPS 帧上下文的宿主/外部调用使用（VM 主路径直接
        ``yield from`` :meth:`dispatch_eager_cps`）。
        """
        gen = self.dispatch_eager_cps(
            node_uid, execution_context, intent_ctx=intent_ctx
        )
        return self._pump_cps(gen, execution_context)

    def dispatch_eager_cps(
        self,
        node_uid: str,
        execution_context: IExecutionContext,
        intent_ctx: Optional[Any] = None,
    ):
        """CPS 版立即提交 LLM 调用到线程池，返回 ``LLMFuture``（生成器）。

        在 ``dispatch_eligible=True`` 且数据依赖已满足时，由 VM 调度器调用。
        与同步版同语义，但 prompt 段预求值（段插值 / 意图消解 / 输出约束 /
        retry_hint，经 :meth:`_prepare_behavior_call_cps`）以 ``yield from``
        嵌入当前 VM 帧栈——消除 ``vm.run`` 重入的"同步旁路"（段求值含
        Waitable 时不再阻塞调度线程，frame_stack_depth 正确）。调用方须
        ``yield from``；返回 :class:`LLMFuture`。
        """
        node_data = execution_context.get_node_data(node_uid)
        spec = yield from self._prepare_behavior_call_cps(
            node_uid, node_data, execution_context, captured_intents=intent_ctx
        )
        return self._submit_dispatch(spec, node_uid, execution_context)

    def _submit_dispatch(
        self,
        spec: Any,
        node_uid: str,
        execution_context: IExecutionContext,
    ) -> LLMFuture:
        """提交预求值结果到线程池并记录 dispatch 调用信息（同步部分）。

        拆分执行边界：预求值（CPS 权威 :meth:`dispatch_eager_cps`）完成后，
        后台线程仅执行 :meth:`_call_and_parse`（``_call_llm`` + 解析），
        不重入 VM、不访问 live context、不写主线程单写槽。
        """
        # 记录 dispatch 时刻的调用信息（LLMCallRequest 结构化快照）：调用已提交，
        # idbg.current_llm() 应立即可见"最近一次 LLM 调用"，而非等变量读取
        # 触发 resolve 后才可观测。resolve 点（_record_current_call_info 覆盖）
        # 再补全 response。只写单写槽不追加追踪（追踪保留已解析完整调用）。
        info = spec.request.as_dict()
        info["response"] = ""
        info["raw_response"] = ""
        self._record_dispatch_call_info(info)

        def _run() -> LLMResult:
            return self._call_and_parse(spec, node_uid, execution_context)

        future = self._get_thread_pool().submit(_run)
        llm_future = LLMFuture(node_uid=node_uid, future=future)
        with self._pending_futures_lock:
            self._pending_futures[node_uid] = llm_future
        hooks = self._test_hooks()
        if hooks is not None:
            hooks.on_dispatch(node_uid=node_uid)
        return llm_future

    def resolve_future_cps(self, future: LLMFuture):
        """CPS 版结果解析：yield future 给调度器挂起，恢复后处理结果（生成器）。

        服务 VM 调度器（``run_many`` / 单根可挂起）：当变量读取点持有 ``LLMFuture``
        时，以 ``yield future`` 挂起当前根，让出给其它根，LLM 就绪后由调度器
        ``send`` 回 ``LLMResult`` 恢复——而非 ``future.result()`` 阻塞等待当前线程。

        结果处理：``_pending_futures`` 清理、主线程单写槽 ``_current_call_info``
        记录、确定性结果转译（``_finalize_invoke_result``）。仅主线程（调度器
        单线程推进）调用；后台线程不触碰本方法。
        """
        result = yield future
        with self._pending_futures_lock:
            self._pending_futures.pop(future.node_uid, None)
        if result is not None and result.call_info is not None:
            # 经统一记录点（单写槽 + 调用追踪），不直接写槽。
            self._record_current_call_info(result.call_info)
        return self._finalize_invoke_result(result)

    def close(self) -> None:
        """关闭线程池（等待已提交任务完成）。

        应优先调用此方法显式释放资源，而非依赖 ``__del__``。
        关闭后再次调用 ``dispatch_eager()``/``run_batch`` 会抛 ``RuntimeError``
        （见 :meth:`_get_thread_pool`），不再静默重建线程池。
        幂等：重复调用安全。
        """
        if self._thread_pool is not None:
            self._thread_pool.shutdown(wait=True)
            self._thread_pool = None
        self._closed = True

    def __del__(self) -> None:
        """关闭线程池（非阻塞；允许已提交的任务完成）。"""
        if self._thread_pool is not None:
            try:
                self._thread_pool.shutdown(wait=False)
            except Exception:
                pass
