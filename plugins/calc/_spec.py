"""
[IES 2.2] Calc 插件规范
"""
from typing import Dict, Any

def __ibcext_metadata__() -> Dict[str, Any]:
    return {
        "name": "calc",
        "version": "1.0.0",
        "description": "A simple calculator plugin",
        "dependencies": []
    }

def __ibcext_vtable__() -> Dict[str, Any]:
    return {
        "functions": {
            "add": {
                "param_types": ["int", "int"],
                "return_type": "int"
            },
            "mul": {
                "param_types": ["int", "int"],
                "return_type": "int"
            }
        }
    }
