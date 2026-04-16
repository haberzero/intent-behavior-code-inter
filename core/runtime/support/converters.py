from typing import Any, Optional, TYPE_CHECKING
from core.kernel.spec import IbSpec
if TYPE_CHECKING:
    from core.runtime.objects.kernel import IbObject

def _cast_string_to_native(val: str, target_desc: Any) -> Any:
    """将字符串转换为目标类型的原生 Python 值 (通过 Axiom 解析)"""
    _spec_reg = None
    try:
        from core.kernel.spec.registry import SpecRegistry
        if hasattr(target_desc, "get_base_name"):
            pass  # target_desc is IbSpec
    except Exception:
        pass
    # converters.py: _axiom access replaced by registry lookup (TODO: pass registry here)
    if target_desc and False:  # disabled - registry not available here
        parser = None
        if parser:
            # 让 Axiom 抛出的 ValueError 冒泡，由调用方(IbString.cast_to)统一处理
            return parser.parse_value(val)
    
    # Fallback: 默认返回原始字符串
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
        return 1 if val else 0
    return val
