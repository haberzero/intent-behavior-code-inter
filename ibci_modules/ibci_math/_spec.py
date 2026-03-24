"""
[IES 2.2] Math 数学计算插件规范

IES 2.2 协议实现（第一方组件）：
- __ibcext_vtable__() 返回纯字典（原生 IBC-Inter 元数据声明）
- 不导入任何内核代码，保持零侵入
"""
from typing import Dict, Any


def __ibcext_metadata__() -> Dict[str, Any]:
    """[IES 2.2] 插件元数据"""
    return {
        "name": "math",
        "version": "2.2.0",
        "description": "Mathematical computation plugin",
        "dependencies": [],
    }


def __ibcext_vtable__() -> Dict[str, Any]:
    """
    [IES 2.2] 方法虚表 - 返回原生 IBC-Inter 元数据声明

    sqrt: float -> float (平方根)
    pow: (float, float) -> float (幂运算)
    sin: float -> float (正弦)
    cos: float -> float (余弦)
    """
    return {
        "functions": {
            "sqrt": {
                "param_types": ["float"],
                "return_type": "float"
            },
            "pow": {
                "param_types": ["float", "float"],
                "return_type": "float"
            },
            "sin": {
                "param_types": ["float"],
                "return_type": "float"
            },
            "cos": {
                "param_types": ["float"],
                "return_type": "float"
            }
        },
        "variables": {
            "pi": "float"
        }
    }
