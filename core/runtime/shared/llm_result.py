"""LLM 执行结果的显式返回类型与异步 Future 包装。

此模块位于 ``core/runtime/shared/`` —— 运行时各子包（interpreter / vm / objects）
共享的叶子模块，用于打破 interpreter ↔ vm 和 objects ↔ interpreter 循环依赖。

``LLMResult`` 的 ``unwrap()`` 方法中有一个对 ``objects.primitives.IbNone`` 的延迟导入，
这是运行时唯一的跨包引用（非 top-level），不会形成导入循环。
"""

from dataclasses import dataclass, field
from typing import Optional, Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from core.runtime.objects.kernel import IbObject


@dataclass
class LLMResult:
    """
    LLM 执行结果的显式返回类型。

    替代传统的异常机制，提供清晰的成功/失败状态区分。

    字段说明:
    - success: 执行是否成功完成
    - is_uncertain: LLM 返回结果是否不确定/无法解析
    - value: 成功时的返回值
    - error_message: 错误信息（如果有）
    - raw_response: LLM 的原始回复
    - retry_hint: 重试提示（如果 is_uncertain=True）
    - call_info: 诊断信息（sys_prompt/user_prompt/response/intents），绑定到调用实例
    """
    success: bool = False
    is_uncertain: bool = False
    value: Optional['IbObject'] = None
    error_message: Optional[str] = None
    raw_response: str = ""
    retry_hint: Optional[str] = None
    call_info: Optional[Dict[str, Any]] = None

    @property
    def is_success(self) -> bool:
        """执行成功且结果确定"""
        return self.success and not self.is_uncertain

    @staticmethod
    def success_result(value: Optional['IbObject'] = None, raw_response: str = "") -> 'LLMResult':
        """创建成功结果"""
        return LLMResult(
            success=True,
            is_uncertain=False,
            value=value,
            raw_response=raw_response
        )

    @staticmethod
    def uncertain_result(raw_response: str, retry_hint: Optional[str] = None) -> 'LLMResult':
        """创建不确定结果"""
        return LLMResult(
            success=True,
            is_uncertain=True,
            value=None,
            raw_response=raw_response,
            retry_hint=retry_hint
        )

    @staticmethod
    def error_result(error_message: str) -> 'LLMResult':
        """创建错误结果"""
        return LLMResult(
            success=False,
            is_uncertain=False,
            error_message=error_message
        )


@dataclass
class LLMFuture:
    """LLM 异步调用的 Future 包装（LLMScheduler 并发 dispatch 基础设施）。

    由 ``LLMExecutorImpl.dispatch_eager()`` 创建；调度器经 ``resolve_future_cps``
    （CPS，``yield future`` 挂起）或本对象的 ``try_result``/``register_wake``
    （Waitable 契约）等待结果。

    字段说明：
    - node_uid: 对应的 IbBehaviorExpr 节点 UID（用于日志与 pending 查询）
    - future: ``concurrent.futures.Future``，持有后台线程的 ``LLMResult``
    """

    node_uid: str
    future: Any  # concurrent.futures.Future[LLMResult]

    @property
    def is_done(self) -> bool:
        """返回 True 当且仅当后台 LLM 调用已完成（无论成功与否）。"""
        return self.future.done()

    def try_result(self):
        """非阻塞取回 ``(ok, LLMResult)``（调度器专用；不阻塞）。

        ``ok=False`` 表示尚未完成（调度器重新轮询）；``ok=True`` 消费一次，
        返回原始 ``LLMResult``（任务侧再解析为 ``IbObject``）。
        """
        if self.future.done():
            return (True, self.future.result())
        return (False, None)

    def result(self) -> Any:
        """阻塞等待后台 Future 完成并返回原始 ``LLMResult``（不含解析）。

        供宿主/线程体作为 ``Waitable`` 消费：调度器 ``is_done`` 后取
        ``try_result()`` 得原始结果，由任务侧再解析为 ``IbObject``。
        """
        return self.future.result()

    def register_wake(self, event) -> None:
        """完成通知钩子：后台 Future 完成时设置 ``event``（可跨线程）。"""
        self.future.add_done_callback(lambda _future: event.set())


class LLMBatchFuture:
    """聚合多个 :class:`LLMFuture` 的 Waitable（run_batch 多 Future 聚合）。

    并发批量行为执行（``ai.run_batch``）把每个 item 的 LLM 调用提交为独立
    ``LLMFuture``，本对象把它们聚合为单一 Waitable：全部完成才就绪
    （``is_done``），就绪后经 ``try_result`` **一次保序**取回各 ``LLMResult``
    列表（按提交序）。调度器非阻塞轮询/通知式唤醒等待，消除了同步
    ``fut.result()`` 逐个阻塞主线程。

    与 :class:`LLMFuture` 同为结构性 ``Waitable``（is_done 属性 +
    try_result/result/register_wake）；worker 异常经 ``fut.result()`` 重抛，
    由调度器 ``try_result`` 捕获并 ``throw`` 进任务（错误粒度 = 整个批次）。
    """

    def __init__(self, futures: Any):
        self._futures: list = list(futures)

    @property
    def is_done(self) -> bool:
        return all(f.is_done for f in self._futures)

    def try_result(self):
        """非阻塞取回 ``(ok, [LLMResult...])``；未全部完成则 ``(False, None)``。"""
        if not self.is_done:
            return (False, None)
        return (True, [f.future.result() for f in self._futures])

    def result(self) -> Any:
        """阻塞取回 ``[LLMResult...]``（宿主/线程体专用，消费一次）。"""
        return [f.future.result() for f in self._futures]

    def register_wake(self, event) -> None:
        """任一子 Future 完成即设置 ``event``（调度器即时唤醒；全完成后会再置位）。"""
        for f in self._futures:
            f.future.add_done_callback(lambda _f: event.set())
