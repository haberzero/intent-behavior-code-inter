from typing import Any, Optional, TYPE_CHECKING
from core.kernel.spec import IbSpec
if TYPE_CHECKING:
    from core.runtime.objects.kernel import IbObject

def _cast_string_to_native(val: str, target_desc: Any) -> Any:
    """将字符串转换为目标类型的原生 Python 值"""
    if not target_desc:
        return val

    axiom_name = target_desc.get_base_name() if hasattr(target_desc, "get_base_name") else None
    if axiom_name == "int":
        return int(val)
    if axiom_name == "float":
        return float(val)
    if axiom_name == "bool":
        return val.strip().lower() not in ("false", "0", "no", "none", "")
    return val

def _cast_numeric_to_native(val: Any, target_desc: Any) -> Any:
    """将数值转换为目标类型的原生 Python 值"""
    if not target_desc:
        return val
        
    # 使用公理名称判定，解决多引擎隔离下的 identity 失效问题
    axiom_name = target_desc.get_base_name()
    if axiom_name == "str":
        return str(val)
    if axiom_name == "int":
        return int(val)
    if axiom_name == "float":
        return float(val)
    if axiom_name == "bool":
        return bool(val)
    return val
