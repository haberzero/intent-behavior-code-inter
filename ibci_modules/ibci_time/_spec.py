"""
Time 时间工具插件规范

非侵入式时间工具插件。包含当前时间、格式化/解析、时间差计算、休眠等。
"""


def __ibcext_metadata__() -> dict:
    return {
        "name": "time",
        "kind": "method_module",
        "version": "2.0.0",
        "description": "IBCI 时间工具（当前时间/格式化/解析/时间差/休眠）",
        "dependencies": [],
    }


def __ibcext_vtable__() -> dict:
    return {
        "functions": {
            # --- 当前时间 ---
            "now":          {"param_types": [],             "return_type": "float", "description": "Unix 时间戳（秒）"},
            "now_ms":       {"param_types": [],             "return_type": "int",   "description": "Unix 时间戳（毫秒）"},
            "utcnow":       {"param_types": [],             "return_type": "str",   "description": "UTC 时间 ISO 字符串"},
            "localtime":    {"param_types": [],             "return_type": "str",   "description": "本地时间格式化字符串"},
            # --- 格式化/解析 ---
            "format":       {"param_types": ["float", "str"], "return_type": "str", "description": "时间戳格式化（strftime 格式）"},
            "parse":        {"param_types": ["str", "str"],   "return_type": "float", "description": "时间字符串解析为时间戳"},
            "date_str":     {"param_types": ["float"],         "return_type": "str", "description": "时间戳→'YYYY-MM-DD'"},
            "datetime_str": {"param_types": ["float"],         "return_type": "str", "description": "时间戳→'YYYY-MM-DD HH:MM:SS'"},
            # --- 时间差 ---
            "add_seconds":  {"param_types": ["float", "float"], "return_type": "float", "description": "时间戳加秒"},
            "add_days":     {"param_types": ["float", "int"],   "return_type": "float", "description": "时间戳加天"},
            "diff_seconds": {"param_types": ["float", "float"], "return_type": "float", "description": "两时间戳差（秒）"},
            "diff_days":    {"param_types": ["float", "float"], "return_type": "float", "description": "两时间戳差（天）"},
            # --- 休眠 ---
            "sleep":        {"param_types": ["float"],           "return_type": "void", "description": "休眠（秒）"},
            "sleep_ms":     {"param_types": ["int"],             "return_type": "void", "description": "休眠（毫秒）"},
        }
    }
