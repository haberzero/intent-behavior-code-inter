from typing import Dict, Any


def __ibcext_metadata__() -> Dict[str, Any]:
    """插件元数据"""
    return {
        "name": "math",
        "version": "0.0.1",
        "description": "Mathematical computation plugin",
        "dependencies": [],
    }


def __ibcext_vtable__() -> Dict[str, Any]:
    """
    方法虚表 - 返回原生 IBC-Inter 元数据声明

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
