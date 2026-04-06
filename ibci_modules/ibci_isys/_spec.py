"""
Isys 内核插件规范

IBCI 内核运行时状态模块规范。
"""

def __ibcext_metadata__() -> dict:
    """插件元数据"""
    return {
        "name": "isys",
        "version": "1.0.0",
        "description": "IBCI 内核运行时状态模块 - 入口文件路径和运行时状态查询",
        "dependencies": [],
    }


def __ibcext_vtable__() -> dict:
    """插件虚表 - 定义暴露给 IBCI 的方法"""
    return {
        "functions": {
            "entry_path": {
                "param_types": [],
                "return_type": "str",
                "description": "获取入口文件的绝对路径"
            },
            "entry_dir": {
                "param_types": [],
                "return_type": "str",
                "description": "获取入口文件所在的目录"
            },
            "project_root": {
                "param_types": [],
                "return_type": "str",
                "description": "获取项目根目录"
            },
        }
    }
