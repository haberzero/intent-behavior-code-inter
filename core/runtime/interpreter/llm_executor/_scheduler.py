"""``_SchedulerMixin`` —— LLMScheduler 能力。

提供 ``dispatch_eager`` / ``resolve`` / ``close`` 接口与惰性线程池管理，
支持 behavior 表达式的并发 LLM 调用。依赖 :class:`LLMExecutorCore` 初始化的
LLMScheduler 共享状态 (``self._max_workers`` / ``self._thread_pool`` /
``self._pending_futures`` / ``self._pending_futures_lock``)，并调用
:class:`_BehaviorMixin` 提供的 :meth:`execute_behavior_expression`。

分隔注释块 (``LLMScheduler — dispatch_eager / resolve / 线程池管理``) 原位于
``llm_executor.py`` 第 517-519 行。
"""

from concurrent.futures import ThreadPoolExecutor as _ThreadPoolExecutor
from typing import Any, Optional

from core.runtime.interfaces import IExecutionContext

from core.runtime.shared.llm_result import LLMResult, LLMFuture
from core.runtime.objects.kernel import IbObject


class _SchedulerMixin:
    # ---------------------------------------------------------------------------
    # LLMScheduler — dispatch_eager / resolve / 线程池管理
    # ---------------------------------------------------------------------------

    def _get_thread_pool(self) -> _ThreadPoolExecutor:
        """惰性初始化线程池（首次 dispatch_eager 调用时创建）。"""
        if self._thread_pool is None:
            self._thread_pool = _ThreadPoolExecutor(max_workers=self._max_workers)
        return self._thread_pool

    def dispatch_eager(
        self,
        node_uid: str,
        execution_context: IExecutionContext,
        intent_ctx: Optional[Any] = None,
    ) -> LLMFuture:
        """立即将 LLM 调用提交到线程池，返回 ``LLMFuture``（非阻塞）。

        在 ``dispatch_eligible=True`` 且数据依赖已满足时，由 VM 调度器调用。
        在 dispatch 时刻捕获 prompt 内容与意图上下文，后台线程中发起实际调用。

        参数：
            node_uid:          对应 ``IbBehaviorExpr`` 节点的 UID
            execution_context: 当前执行上下文（用于 prompt 求值；调用时刻只读）
            intent_ctx:        （可选）已 fork 的意图上下文快照；None 表示使用
                               当前 runtime_context 的活跃意图

        返回：
            ``LLMFuture``，可通过 ``resolve(node_uid)`` 阻塞等待结果。
        """
        def _run() -> LLMResult:
            return self.execute_behavior_expression(
                node_uid, execution_context, captured_intents=intent_ctx
            )

        future = self._get_thread_pool().submit(_run)
        llm_future = LLMFuture(node_uid=node_uid, future=future)
        with self._pending_futures_lock:
            self._pending_futures[node_uid] = llm_future
        return llm_future

    def resolve(self, node_uid: str) -> IbObject:
        """阻塞等待 ``node_uid`` 对应的 ``LLMFuture`` 完成，返回 ``IbObject``。

        在变量使用点检测到对应 ``LLMFuture`` 时由 VM 调度器调用。

        若 ``dispatch_eager`` 尚未被调用，或对应 Future 已被 resolve 消费，
        则抛出 ``RuntimeError``。
        """
        with self._pending_futures_lock:
            llm_future = self._pending_futures.pop(node_uid, None)
        if llm_future is None:
            raise RuntimeError(
                f"LLMExecutorImpl.resolve: 节点 {node_uid!r} 没有待解析的 Future。"
                f"请确认 dispatch_eager() 已在 resolve() 之前被调用，"
                f"且每个 Future 只被 resolve 一次。"
            )
        return llm_future.get(self.registry)

    def close(self) -> None:
        """关闭线程池（等待已提交任务完成）。

        应优先调用此方法显式释放资源，而非依赖 ``__del__``。
        关闭后不应再调用 ``dispatch_eager()``（会重新创建线程池）。
        """
        if self._thread_pool is not None:
            self._thread_pool.shutdown(wait=True)
            self._thread_pool = None

    def __del__(self) -> None:
        """关闭线程池（非阻塞；允许已提交的任务完成）。"""
        if self._thread_pool is not None:
            try:
                self._thread_pool.shutdown(wait=False)
            except Exception:
                pass
