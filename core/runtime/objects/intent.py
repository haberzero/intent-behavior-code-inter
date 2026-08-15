from typing import List, Optional, Any, Union, Dict, TYPE_CHECKING, Mapping
from core.runtime.interfaces import RuntimeContext
from core.runtime.objects.kernel import IbObject, IbClass
from core.runtime.objects.ib_type_mapping import register_ib_type
from core.runtime.observability.diagnostics import kernel_diagnostic
from core.base.diagnostics.codes import KDIAG_PROTOCOL_TO_PROMPT_FALLBACK
from core.kernel.intent_logic import IntentMode, IntentRole

if TYPE_CHECKING:
    from core.runtime.interpreter.llm_executor import LLMExecutorImpl


def _intent_segment_to_prompt(val: Any) -> str:
    """把意图段求值结果转提示词文本（``__to_prompt__`` 协议，回退 ``to_native``）。

    供 :meth:`IbIntent.resolve_content` 与 :meth:`IbIntent.resolve_content_cps`
    共用（单一权威，无双写）。实现委托给统一的 :class:`PromptRenderer`；
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
    表示运行时的意图对象。
    封装了意图的内容、模式以及来源信息。
    现在是真正的 IbObject 子类 (Everything is an Object)。
    """
    __slots__ = ('content', 'segments', 'mode', 'tag', 'source_uid', 'role', 'pop_top')
    
    def __init__(self, ib_class: IbClass, content: str = "", segments: List[Any] = None, 
                 mode: IntentMode = IntentMode.APPEND, tag: Optional[str] = None,
                 source_uid: Optional[str] = None, role: IntentRole = IntentRole.BLOCK,
                 pop_top: bool = False):
        super().__init__(ib_class)
        self.content = content
        self.segments = segments if segments is not None else []
        self.mode = mode
        self.tag = tag
        self.source_uid = source_uid
        self.role = role
        self.pop_top = pop_top

    @staticmethod
    def from_node_data(node_uid: str, node_data: Mapping[str, Any], ib_class: IbClass, role: IntentRole = IntentRole.BLOCK) -> 'IbIntent':
        """
        从 AST 节点数据构造运行时意图对象。
        """
        return IbIntent(
            ib_class=ib_class,
            content=node_data.get('content', ''),
            segments=node_data.get('segments', []),
            mode=IntentMode.from_str(node_data.get('mode', '+')),
            tag=node_data.get('tag'),
            role=role,
            source_uid=node_uid,
            pop_top=node_data.get('pop_top', False)
        )

    def resolve_content(self, context: RuntimeContext, execution_context: Any = None) -> str:
        """解析意图内容，对 node_ UID 片段通过 VMExecutor CPS 路径求值。"""
        if self.segments and execution_context:
            content_parts = []
            for segment in self.segments:
                if isinstance(segment, str) and segment.startswith("node_"):
                    vm = execution_context.vm_executor
                    if vm is None:
                        raise RuntimeError("IbIntent.resolve_content: vm_executor not available")
                    val = vm.run(segment)
                    content_parts.append(_intent_segment_to_prompt(val))
                else:
                    content_parts.append(str(segment))
            return "".join(content_parts).strip()
        
        return str(self.content).strip()

    def resolve_content_cps(self, context: RuntimeContext, execution_context: Any = None):
        """CPS 版 :meth:`resolve_content`；node_ UID 片段经 ``yield`` 交外层 VM 帧栈。

        ``resolve_content`` 在段含 node_ 时 ``vm.run(segment)`` 同步重入调度循环
        （任务内同步重入）；本版本 ``yield segment`` 由外层 ``_drive_loop_gen``
        作为子任务接管求值，消除重入。非 node_ 段与 ``__to_prompt__`` 解析共用
        ``_intent_segment_to_prompt``，无双写。返回消解后字符串。
        """
        if self.segments and execution_context:
            content_parts = []
            for segment in self.segments:
                if isinstance(segment, str) and segment.startswith("node_"):
                    val = yield segment
                    content_parts.append(_intent_segment_to_prompt(val))
                else:
                    content_parts.append(str(segment))
            return "".join(content_parts).strip()

        return str(self.content).strip()

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
        """返回意图内容字符串。"""
        return self.content or ""

    def get_tag(self) -> str:
        """返回意图标签；无标签时返回空字符串。"""
        return self.tag or ""

    def get_mode(self) -> str:
        """返回意图模式字符串：'+', '!', 或 '-'。"""
        return self.mode.value if self.mode else "+"

    def __repr__(self):
        tag_str = f" tag={self.tag}" if self.tag else ""
        return f"<Intent mode={self.mode.name}{tag_str} role={self.role.value} content='{self.content[:20]}...'>"
