"""
Sys 系统能力插件规范

- __ibcext_vtable__() 返回纯字典（原生 IBC-Inter 元数据声明）
- 不导入任何内核代码，保持零侵入
"""
from typing import Dict, Any


def __ibcext_metadata__() -> Dict[str, Any]:
    """插件元数据"""
    return {
        "name": "sys",
        "version": "2.2.0",
        "description": "System capability plugin",
        "dependencies": [],
    }


def __ibcext_vtable__() -> Dict[str, Any]:
    """
    方法虚表 - 返回原生 IBC-Inter 元数据声明

    request_external_access: void -> void (请求外部访问权限)
    is_sandboxed: void -> bool (检查是否在沙箱中运行)
    """
    return {
        "functions": {
            "request_external_access": {
                "param_types": [],
                "return_type": "void"
            },
            "is_sandboxed": {
                "param_types": [],
                "return_type": "bool"
            },
            "script_dir": {
                "param_types": [],
                "return_type": "str"
            },
            "script_path": {
                "param_types": [],
                "return_type": "str"
            },
            "project_root": {
                "param_types": [],
                "return_type": "str"
            }
        }
    }
