"""
Math 数学运算插件规范

非侵入式数学工具插件。包含基础运算、三角函数、对数/指数、随机数等。
"""


def __ibcext_metadata__() -> dict:
    return {
        "name": "math",
        "kind": "method_module",
        "version": "2.0.0",
        "description": "IBCI 数学运算工具（基础/三角/对数/随机）",
        "dependencies": [],
    }


def __ibcext_vtable__() -> dict:
    return {
        "functions": {
            # --- 基础运算 ---
            "sqrt":   {"params": [{"name": "x", "type": "float"}], "return_type": "float"},
            "pow":    {"params": [{"name": "x", "type": "float"}, {"name": "y", "type": "float"}], "return_type": "float"},
            "abs":    {"params": [{"name": "x", "type": "float"}], "return_type": "float"},
            "floor":  {"params": [{"name": "x", "type": "float"}], "return_type": "int"},
            "ceil":   {"params": [{"name": "x", "type": "float"}], "return_type": "int"},
            "round":  {"params": [{"name": "x", "type": "float"}, {"name": "ndigits", "type": "int"}], "return_type": "float"},
            "clamp":  {"params": [{"name": "x", "type": "float"}, {"name": "lo", "type": "float"}, {"name": "hi", "type": "float"}], "return_type": "float"},
            "min":    {"params": [{"name": "a", "type": "float"}, {"name": "b", "type": "float"}], "return_type": "float"},
            "max":    {"params": [{"name": "a", "type": "float"}, {"name": "b", "type": "float"}], "return_type": "float"},
            # --- 对数/指数 ---
            "exp":    {"params": [{"name": "x", "type": "float"}], "return_type": "float"},
            "log":    {"params": [{"name": "x", "type": "float"}], "return_type": "float"},
            "log2":   {"params": [{"name": "x", "type": "float"}], "return_type": "float"},
            "log10":  {"params": [{"name": "x", "type": "float"}], "return_type": "float"},
            # --- 三角函数 ---
            "sin":    {"params": [{"name": "x", "type": "float"}], "return_type": "float"},
            "cos":    {"params": [{"name": "x", "type": "float"}], "return_type": "float"},
            "tan":    {"params": [{"name": "x", "type": "float"}], "return_type": "float"},
            "asin":   {"params": [{"name": "x", "type": "float"}], "return_type": "float"},
            "acos":   {"params": [{"name": "x", "type": "float"}], "return_type": "float"},
            "atan":   {"params": [{"name": "x", "type": "float"}], "return_type": "float"},
            "atan2":  {"params": [{"name": "y", "type": "float"}, {"name": "x", "type": "float"}], "return_type": "float"},
            # --- 角度转换 ---
            "degrees": {"params": [{"name": "radians", "type": "float"}], "return_type": "float"},
            "radians": {"params": [{"name": "degrees", "type": "float"}], "return_type": "float"},
            # --- 随机数 ---
            "random":  {"params": [], "return_type": "float"},
            "randint": {"params": [{"name": "lo", "type": "int"}, {"name": "hi", "type": "int"}], "return_type": "int"},
        },
        "variables": {
            "pi":  "float",
            "e":   "float",
            "inf": "float",
        }
    }
