from typing import Any, Optional, TYPE_CHECKING
from core.domain.types.descriptors import (
    INT_DESCRIPTOR, STR_DESCRIPTOR, FLOAT_DESCRIPTOR, 
    BOOL_DESCRIPTOR
)

if TYPE_CHECKING:
    from core.runtime.objects.kernel import IbObject

def _cast_string_to_native(val: str, target_desc: Any) -> Any:
    """将字符串转换为目标类型的原生 Python 值 (通过 Axiom 解析)"""
    if target_desc and target_desc._axiom:
        parser = target_desc._axiom.get_parser_capability()
        if parser:
            try:
                return parser.parse_value(val)
            except (ValueError, TypeError):
                # 如果解析失败，回退到目标类型的默认原生值
                if target_desc is INT_DESCRIPTOR: return 0
                if target_desc is FLOAT_DESCRIPTOR: return 0.0
                if target_desc is BOOL_DESCRIPTOR: return False
    
    # Fallback: 默认返回原始字符串或基本转换
    return val

def _cast_numeric_to_native(val: Any, target_desc: Any) -> Any:
    """将数值转换为目标类型的原生 Python 值"""
    if target_desc is STR_DESCRIPTOR:
        return str(val)
    if target_desc is INT_DESCRIPTOR:
        return int(val)
    if target_desc is FLOAT_DESCRIPTOR:
        return float(val)
    if target_desc is BOOL_DESCRIPTOR:
        return 1 if val else 0
    return val
