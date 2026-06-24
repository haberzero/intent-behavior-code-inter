from typing import Dict, Any, TYPE_CHECKING

from core.base.diagnostics.debugger import CoreModule, DebugLevel, core_debugger

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
        name = getattr(spec, "name", None)
        base_name = spec.get_base_name() if hasattr(spec, "get_base_name") else name
        return base_name == "intent_context" or name == "intent_context"

    # 1) Prefer semantic side-table type info: it is produced after full Pass-4
    #    type resolution and is more stable than runtime node shape fallbacks.
    direct_spec = ec.get_side_table("node_to_type", param_uid)
    if _is_intent_context_spec(direct_spec):
        return True

    # 2) Compatibility fallback for IbTypeAnnotatedExpr-wrapped target binding
    if not isinstance(param_data, dict):
        return False
    if param_data.get("_type") == "IbTypeAnnotatedExpr":
        target_uid = param_data.get("target")
        target_spec = ec.get_side_table("node_to_type", target_uid)
        if _is_intent_context_spec(target_spec):
            return True
        annotation_uid = param_data.get("annotation")
        annotation_data = ec.get_node_data(annotation_uid) if annotation_uid else None
        if annotation_data:
            ann_type = annotation_data.get("_type")
            if ann_type == "IbName":
                return annotation_data.get("id") == "intent_context"
            if ann_type == "IbAttribute":
                return annotation_data.get("attr") == "intent_context"
    return False


def _should_activate_intent_context_arg(arg_value: Any, is_intent_ctx_param: bool) -> bool:
    if is_intent_ctx_param:
        return True
    return (
        isinstance(arg_value, IbObject)
        and hasattr(arg_value, "fields")
        and arg_value.fields.get("_ctx") is not None
    )
