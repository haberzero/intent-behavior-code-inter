from typing import Optional
from .symbols import StaticType, STATIC_ANY, STATIC_INT, STATIC_FLOAT, STATIC_STR, STATIC_BOOL, STATIC_VOID

def get_builtin_type(name: str) -> Optional[StaticType]:
    """获取静态内置类型"""
    mapping = {
        "var": STATIC_ANY,
        "Any": STATIC_ANY,
        "int": STATIC_INT,
        "float": STATIC_FLOAT,
        "str": STATIC_STR,
        "bool": STATIC_BOOL,
        "void": STATIC_VOID,
        "none": STATIC_VOID
    }
    return mapping.get(name)
