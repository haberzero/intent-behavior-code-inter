"""
Sys 系统能力插件规范

非侵入式系统能力插件。
"""

def __ibcext_metadata__() -> dict:
    """插件元数据"""
    return {
        "name": "ibci_sys",
        "version": "2.3.0",
        "description": "IBCI 系统能力插件（非侵入式）- 沙箱控制和权限管理",
        "dependencies": [],
    }


def __ibcext_vtable__() -> dict:
    """插件虚表 - 定义暴露给 IBCI 的方法"""
    return {
        "functions": {
            "request_external_access": {
                "param_types": [],
                "return_type": "void",
                "description": "请求启用外部访问权限（沙箱控制）"
            },
            "is_sandboxed": {
                "param_types": [],
                "return_type": "bool",
                "description": "检查当前是否在沙箱模式运行"
            },
        }
    }
