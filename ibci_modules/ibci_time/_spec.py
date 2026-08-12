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
            "now":          {"params": [], "return_type": "float", "description": "Unix 时间戳（秒）"},
            "now_ms":       {"params": [], "return_type": "int",   "description": "Unix 时间戳（毫秒）"},
            "utcnow":       {"params": [], "return_type": "str",   "description": "UTC 时间 ISO 字符串"},
            "localtime":    {"params": [], "return_type": "str",   "description": "本地时间格式化字符串"},
            # --- 格式化/解析 ---
            "format":       {"params": [{"name": "timestamp", "type": "float"}, {"name": "fmt", "type": "str"}], "return_type": "str", "description": "时间戳格式化（strftime 格式）"},
            "parse":        {"params": [{"name": "time_str", "type": "str"}, {"name": "fmt", "type": "str"}], "return_type": "float", "description": "时间字符串解析为时间戳"},
            "date_str":     {"params": [{"name": "timestamp", "type": "float"}], "return_type": "str", "description": "时间戳→'YYYY-MM-DD'"},
            "datetime_str": {"params": [{"name": "timestamp", "type": "float"}], "return_type": "str", "description": "时间戳→'YYYY-MM-DD HH:MM:SS'"},
            # --- 时间差 ---
            "add_seconds":  {"params": [{"name": "timestamp", "type": "float"}, {"name": "seconds", "type": "float"}], "return_type": "float", "description": "时间戳加秒"},
            "add_days":     {"params": [{"name": "timestamp", "type": "float"}, {"name": "days", "type": "int"}], "return_type": "float", "description": "时间戳加天"},
            "diff_seconds": {"params": [{"name": "ts1", "type": "float"}, {"name": "ts2", "type": "float"}], "return_type": "float", "description": "两时间戳差（秒）"},
            "diff_days":    {"params": [{"name": "ts1", "type": "float"}, {"name": "ts2", "type": "float"}], "return_type": "float", "description": "两时间戳差（天）"},
            # --- 休眠 ---
            "sleep":        {"params": [{"name": "seconds", "type": "float"}], "return_type": "void", "description": "休眠（秒）"},
            "sleep_ms":     {"params": [{"name": "milliseconds", "type": "int"}], "return_type": "void", "description": "休眠（毫秒）"},
        }
    }
