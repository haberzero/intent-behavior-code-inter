"""
Net 网络请求插件规范

非侵入式 HTTP 工具插件。
支持标准 HTTP 方法、JSON 解析、表单提交、会话级配置（超时、默认头、认证）。
"""


def __ibcext_metadata__() -> dict:
    return {
        "name": "net",
        "version": "2.0.0",
        "description": "IBCI HTTP 网络请求工具（含认证/会话配置）",
        "dependencies": [],
    }


def __ibcext_vtable__() -> dict:
    return {
        "functions": {
            # --- 会话级配置 ---
            "set_timeout": {
                "param_types": ["float"],
                "return_type": "void",
                "description": "设置全局请求超时时间（秒）"
            },
            "set_default_headers": {
                "param_types": ["dict"],
                "return_type": "void",
                "description": "设置全局默认请求头"
            },
            "set_bearer_token": {
                "param_types": ["str"],
                "return_type": "void",
                "description": "设置 Bearer Token 认证头"
            },
            "set_basic_auth": {
                "param_types": ["str", "str"],
                "return_type": "void",
                "description": "设置 Basic Auth 认证（用户名、密码）"
            },
            "clear_auth": {
                "param_types": [],
                "return_type": "void",
                "description": "清除认证头"
            },
            # --- HTTP 方法 ---
            "get": {
                "param_types": ["str"],
                "return_type": "str",
                "description": "发送 GET 请求，返回响应文本"
            },
            "get_json": {
                "param_types": ["str"],
                "return_type": "dict",
                "description": "发送 GET 请求，自动解析 JSON 响应"
            },
            "post": {
                "param_types": ["str", "dict"],
                "return_type": "str",
                "description": "发送 POST 请求（JSON body），返回响应文本"
            },
            "post_json": {
                "param_types": ["str", "dict"],
                "return_type": "dict",
                "description": "发送 POST 请求（JSON body），自动解析 JSON 响应"
            },
            "post_form": {
                "param_types": ["str", "dict"],
                "return_type": "str",
                "description": "发送 POST 表单请求（application/x-www-form-urlencoded）"
            },
            "put": {
                "param_types": ["str", "dict"],
                "return_type": "str",
                "description": "发送 PUT 请求（JSON body），返回响应文本"
            },
            "delete": {
                "param_types": ["str"],
                "return_type": "str",
                "description": "发送 DELETE 请求，返回响应文本"
            },
            "head": {
                "param_types": ["str"],
                "return_type": "dict",
                "description": "发送 HEAD 请求，返回响应头 dict"
            },
            "get_status_code": {
                "param_types": ["str"],
                "return_type": "int",
                "description": "发送 GET 请求，仅返回 HTTP 状态码"
            },
        }
    }
