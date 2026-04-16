"""
Math 数学运算插件规范

非侵入式数学工具插件。包含基础运算、三角函数、对数/指数、随机数等。
"""


def __ibcext_metadata__() -> dict:
    return {
        "name": "math",
        "version": "2.0.0",
        "description": "IBCI 数学运算工具（基础/三角/对数/随机）",
        "dependencies": [],
    }


def __ibcext_vtable__() -> dict:
    return {
        "functions": {
            # --- 基础运算 ---
            "sqrt":   {"param_types": ["float"],           "return_type": "float"},
            "pow":    {"param_types": ["float", "float"],  "return_type": "float"},
            "abs":    {"param_types": ["float"],           "return_type": "float"},
            "floor":  {"param_types": ["float"],           "return_type": "int"},
            "ceil":   {"param_types": ["float"],           "return_type": "int"},
            "round":  {"param_types": ["float", "int"],    "return_type": "float"},
            "clamp":  {"param_types": ["float", "float", "float"], "return_type": "float"},
            "min":    {"param_types": ["float", "float"],  "return_type": "float"},
            "max":    {"param_types": ["float", "float"],  "return_type": "float"},
            # --- 对数/指数 ---
            "exp":    {"param_types": ["float"],           "return_type": "float"},
            "log":    {"param_types": ["float"],           "return_type": "float"},
            "log2":   {"param_types": ["float"],           "return_type": "float"},
            "log10":  {"param_types": ["float"],           "return_type": "float"},
            # --- 三角函数 ---
            "sin":    {"param_types": ["float"],           "return_type": "float"},
            "cos":    {"param_types": ["float"],           "return_type": "float"},
            "tan":    {"param_types": ["float"],           "return_type": "float"},
            "asin":   {"param_types": ["float"],           "return_type": "float"},
            "acos":   {"param_types": ["float"],           "return_type": "float"},
            "atan":   {"param_types": ["float"],           "return_type": "float"},
            "atan2":  {"param_types": ["float", "float"],  "return_type": "float"},
            # --- 角度转换 ---
            "degrees": {"param_types": ["float"],          "return_type": "float"},
            "radians": {"param_types": ["float"],          "return_type": "float"},
            # --- 随机数 ---
            "random":  {"param_types": [],                 "return_type": "float"},
            "randint": {"param_types": ["int", "int"],     "return_type": "int"},
        },
        "variables": {
            "pi":  "float",
            "e":   "float",
            "inf": "float",
        }
    }
