"""
ISys 内核插件规范

IBCI 内核运行时状态与系统控制模块规范。
与 Python 标准库的 sys 模块类似，提供对解释器和运行时环境的查询与控制接口。
"""

def __ibcext_metadata__() -> dict:
    """插件元数据"""
    return {
        "name": "isys",
        "kind": "method_module",
        "version": "2.0.0",
        "description": "IBCI 内核运行时状态与系统控制模块（合并自 isys + sys）",
        "dependencies": [],
    }


def __ibcext_vtable__() -> dict:
    """插件虚表 - 定义暴露给 IBCI 的方法"""
    return {
        "functions": {
            # --- 路径信息 ---
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
                "description": "获取项目根目录（沙箱边界）"
            },
            # --- 沙箱控制 ---
            "is_sandboxed": {
                "param_types": [],
                "return_type": "bool",
                "description": "检查当前是否在沙箱模式下运行"
            },
            "request_external_access": {
                "param_types": [],
                "return_type": "void",
                "description": "请求启用外部访问权限（允许访问项目目录之外的文件）"
            },
        }
    }
