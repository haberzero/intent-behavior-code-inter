from typing import Dict, Any, TYPE_CHECKING

from .base import IbObject

if TYPE_CHECKING:
    from core.runtime.interfaces import IExecutionContext


def _is_intent_context_param(ec: 'IExecutionContext', param_uid: str, param_data: Dict[str, Any]) -> bool:
    """
    Return True when a parameter node is annotated as `intent_context`.
    """
    def _is_intent_context_spec(spec: Any) -> bool:
        if spec is None:
            return False
        base_name = spec.get_base_name()
        name = getattr(spec, "name", None)
        return base_name == "intent_context" or name == "intent_context"

    # 语义侧表类型信息：Pass-4 类型解析后产生，是稳定的单一判别源。
    # 函数参数节点一律为 IbArg（解析器不再产生 IbTypeAnnotatedExpr 包装，
    # 见 symbol_resolution_pass 注释）——无节点形态嗅探兜底。
    direct_spec = ec.get_side_table("node_to_type", param_uid)
    return _is_intent_context_spec(direct_spec)


def _should_activate_intent_context_arg(arg_value: Any, is_intent_ctx_param: bool) -> bool:
    if is_intent_ctx_param:
        return True
    if not isinstance(arg_value, IbObject):
        return False
    # 惰性 import + isinstance 精确判别（base.py:176 先例，替代 hasattr 探测）——
    # 仅当 _ctx 槽持有真实 IbIntentContext 才激活意图上下文路径，任何恰有
    # 非 None _ctx 字段的普通对象不再误激活（与 use() 校验对齐）。
    from core.runtime.objects.intent_context import IbIntentContext
    other_ctx = arg_value.fields.get("_ctx")
    return isinstance(other_ctx, IbIntentContext)
