"""
Isolated Plugin 规范
"""


def __ibcext_metadata__() -> dict:
    """插件元数据"""
    return {
        "name": "isolated_plugin",
        "version": "1.0.0",
        "description": "子项目隔离环境中的插件",
        "dependencies": [],
    }


def __ibcext_vtable__() -> dict:
    """插件方法表"""
    return {
        "functions": {
            "get_isolation_info": {
                "param_types": [],
                "return_type": "dict"
            }
        }
    }
