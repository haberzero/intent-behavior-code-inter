"""
IBIRuntime 内核插件规范

IBCI 运行时内省与控制模块。提供：
- ``snapshot()`` —— 运行时快照（tasks/channels/slots/vms/vars/llm）
- ``subscribe()`` —— 订阅状态变更事件流（返回 stream Channel）
"""

def __ibcext_metadata__() -> dict:
    """插件元数据"""
    return {
        "name": "iruntime",
        "kind": "method_module",
        "version": "0.1.0",
        "description": "IBCI 运行时内省与事件流模块",
        "dependencies": [],
    }


def __ibcext_vtable__() -> dict:
    """插件虚表 - 定义暴露给 IBCI 的方法"""
    return {
        "functions": {
            "snapshot": {
                "params": [],
                "return_type": "dict",
                "description": "获取当前运行时快照（tasks/channels/slots/vms/vars/llm）"
            },
            "subscribe": {
                "params": [],
                "return_type": "chan",
                "description": "订阅运行时状态变更事件流，返回 mode=stream 的 Channel"
            },
            "configure": {
                "params": [{"name": "kwargs", "kind": "VAR_KEYWORD"}],
                "return_type": "dict",
                "description": "统一启停接口（parallel/stream/observability/debug），粒度全局→单调用→单实例"
            },
            "get_config": {
                "params": [],
                "return_type": "dict",
                "description": "读取当前生效配置"
            },
        }
    }
