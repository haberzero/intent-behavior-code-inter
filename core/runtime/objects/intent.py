from typing import List, Optional, Any, TYPE_CHECKING
from core.runtime.interfaces import RuntimeContext
from core.runtime.objects.kernel import IbObject, IbClass
from core.runtime.objects.ib_type_mapping import register_ib_type
from core.runtime.observability.diagnostics import kernel_diagnostic
from core.base.diagnostics.codes import KDIAG_PROTOCOL_TO_PROMPT_FALLBACK
from core.kernel.intent_logic import IntentMode, IntentRole

if TYPE_CHECKING:
    from core.runtime.interpreter.llm_executor import LLMExecutorImpl


def _intent_segment_to_prompt(val: Any) -> str:
    """把意图段值转提示词文本（``__to_prompt__`` 协议，回退 ``to_native``）。

    供 :meth:`IbIntent.render_text` 使用（单一权威渲染，无双写）。
    实现委托给统一的 :class:`PromptRenderer`；
    协议实现异常经 ``kernel_diagnostic`` 告警，不静默降级。
    """
    from core.runtime.shared.prompt_renderer import PromptRenderer
    try:
        return PromptRenderer.to_prompt_str(val)
    except Exception as e:
        kernel_diagnostic(
            code=KDIAG_PROTOCOL_TO_PROMPT_FALLBACK,
            detail={"context": "intent_resolution", "error": repr(e)},
            message=(
                f"__to_prompt__ failed in intent resolution, "
                f"falling back to to_native(): {e!r}"
            ),
        )
        if isinstance(val, IbObject):
            return str(val.to_native())
        return str(val)

@register_ib_type("Intent")
class IbIntent(IbObject):
    """
    表示运行时的意图对象（一等值模型）。

    意图段在注释/栈操作执行点被求值为**一等值列表**（``values``），不再保存
    退化字符串 ``content`` 或延迟段引用 ``segments``（G5 意图值栈）：
    - 渲染：``content``（协议属性）/ :meth:`render_text` 从各值经 ``__to_prompt__``
      拼接（可调用/行为值渲染为契约形态，复用 :func:`_intent_segment_to_prompt`）；
    - 匹配（``@-``）：操作数求值为值后经 :meth:`render_text` 与栈内意图渲染文本比较。
    封装了意图的值、模式以及来源信息。现在是真正的 IbObject 子类 (Everything is an Object)。
    """
    __slots__ = ('values', 'mode', 'tag', 'source_uid', 'role', 'pop_top')
    
    def __init__(self, ib_class: IbClass, values: List[Any] = None,
                 mode: IntentMode = IntentMode.APPEND, tag: Optional[str] = None,
                 source_uid: Optional[str] = None, role: IntentRole = IntentRole.BLOCK,
                 pop_top: bool = False):
        super().__init__(ib_class)
        self.values = values if values is not None else []
        self.mode = mode
        self.tag = tag
        self.source_uid = source_uid
        self.role = role
        self.pop_top = pop_top

    @property
    def content(self) -> str:
        """意图内容（协议属性）：从一等值列表渲染的文本。"""
        return self.render_text()

    def render_text(self) -> str:
        """把意图的一等值列表渲染为提示词文本（单一权威渲染）。

        每个值经 :func:`_intent_segment_to_prompt`（``__to_prompt__`` 协议 +
        兜底 ``to_native``）渲染后拼接去空白。
        """
        return "".join(_intent_segment_to_prompt(v) for v in self.values).strip()

    def resolve_content(self, context: RuntimeContext, execution_context: Any = None) -> str:
        """解析意图内容：值已 eager 求值，直接渲染（无 VM 求值需求）。"""
        return self.render_text()

    @property
    def is_override(self) -> bool:
        return self.mode == IntentMode.OVERRIDE

    @property
    def is_remove(self) -> bool:
        return self.mode == IntentMode.REMOVE
    
    @property
    def is_pop_top(self) -> bool:
        """判断是否为无参数的 @-（移除栈顶意图）"""
        return self.mode == IntentMode.REMOVE and self.pop_top
    
    # ------------------------------------------------------------------ #
    # Public vtable methods (IntentAxiom.get_method_specs)              #
    # ------------------------------------------------------------------ #

    def get_content(self) -> str:
        """返回意图内容字符串（渲染文本）。"""
        return self.render_text()

    def get_tag(self) -> str:
        """返回意图标签；无标签时返回空字符串。"""
        return self.tag or ""

    def get_mode(self) -> str:
        """返回意图模式字符串：'+', '!', 或 '-'。"""
        return self.mode.value if self.mode else "+"

    def __repr__(self):
        tag_str = f" tag={self.tag}" if self.tag else ""
        return f"<Intent mode={self.mode.name}{tag_str} role={self.role.value} content='{self.content[:20]}...'>"
