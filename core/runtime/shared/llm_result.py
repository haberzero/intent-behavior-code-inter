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

# MOCK 哨兵常量（产生方 ibci_ai 与消费方 llm_executor / enum axioms 统一引用，
# 替代散落的字符串字面量，避免"靠凑巧相等"的魔法哨兵）
MOCK_REPAIR_SENTINEL = "__MOCK_REPAIR__"
MOCK_AMBIGUOUS_SENTINEL = "MAYBE_YES_MAYBE_NO_this_is_ambiguous"


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

    由 ``LLMExecutorImpl.dispatch_eager()`` 创建，通过 ``resolve()`` 阻塞等待结果。

    字段说明：
    - node_uid: 对应的 IbBehaviorExpr 节点 UID（用于日志与 pending 查询）
    - future: ``concurrent.futures.Future``，持有后台线程的 ``LLMResult``

    使用模式::

        future = scheduler.dispatch_eager(node_uid, ec, intent_ctx)
        # … 其他工作 …
        result_obj = scheduler.resolve(node_uid)  # 阻塞等待
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
        """完成通知钩子（R2）：后台 Future 完成时设置 ``event``（可跨线程）。"""
        self.future.add_done_callback(lambda _future: event.set())

    def get(self, registry: Any) -> 'IbObject':
        """阻塞等待 Future 完成并返回 IbObject。若已完成则零开销。

        若后台线程抛出异常，该异常将在此处重新抛出。
        若 LLM 调用结果不确定（is_uncertain=True），返回
        ``IbLLMCallResult(is_certain=False)`` 不确定容器（与统一 llmexcept
        机制的返回值传递一致），由调用方（``vm_handle_IbName``）检测并处理。
        """
        result: LLMResult = self.future.result()
        if result is not None:
            if result.value is not None and not result.is_uncertain:
                return result.value
            if result.is_uncertain:
                # 延迟导入避免 shared 叶子模块与 objects 形成导入环
                from core.runtime.objects.kernel import IbLLMCallResult

                cls = registry.get_class("llm_call_result")
                if cls is None:
                    raise RuntimeError("Registry missing 'llm_call_result' class")
                return IbLLMCallResult(
                    ib_class=cls,
                    is_certain=False,
                    raw_response=result.raw_response or "",
                    retry_hint=result.retry_hint or "",
                )
        return registry.get_none()
