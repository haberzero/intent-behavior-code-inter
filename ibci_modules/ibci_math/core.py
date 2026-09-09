"""
ibci_math/core.py

数学内核实现（模块级函数形态）。零内核依赖。

契约（成员面 + 签名）单一权威源 = 内核契约源（contracts/math.ibci，bind 表达）；
本模块 = 实现面。
"""
import builtins
import math as _math
import random as _random

# 常量（契约声明的 field 成员）
pi: float = _math.pi
e: float = _math.e
inf: float = _math.inf

__all__ = [
    "sqrt", "pow", "abs", "floor", "ceil", "round", "clamp", "min", "max",
    "exp", "log", "log2", "log10",
    "sin", "cos", "tan", "asin", "acos", "atan", "atan2",
    "degrees", "radians", "random", "randint",
    "pi", "e", "inf",
]


# --- 基础运算 ---

def sqrt(x: float) -> float:
    """平方根。"""
    return _math.sqrt(x)


def pow(x: float, y: float) -> float:
    """x 的 y 次方。"""
    return _math.pow(x, y)


def abs(x: float) -> float:
    """绝对值。"""
    return builtins.abs(x)


def floor(x: float) -> int:
    """向下取整。"""
    return _math.floor(x)


def ceil(x: float) -> int:
    """向上取整。"""
    return _math.ceil(x)


def round(x: float, ndigits: int) -> float:
    """四舍五入到指定小数位。"""
    return builtins.round(x, ndigits)


def clamp(x: float, lo: float, hi: float) -> float:
    """将 x 限制在 [lo, hi] 范围内。"""
    if x < lo:
        return lo
    if x > hi:
        return hi
    return x


def min(a: float, b: float) -> float:
    """返回两个值中较小的一个。"""
    return a if a < b else b


def max(a: float, b: float) -> float:
    """返回两个值中较大的一个。"""
    return a if a > b else b


# --- 对数/指数 ---

def exp(x: float) -> float:
    """e 的 x 次方。"""
    return _math.exp(x)


def log(x: float) -> float:
    """自然对数 ln(x)。"""
    return _math.log(x)


def log2(x: float) -> float:
    """以 2 为底的对数。"""
    return _math.log2(x)


def log10(x: float) -> float:
    """以 10 为底的对数。"""
    return _math.log10(x)


# --- 三角函数 ---

def sin(x: float) -> float:
    return _math.sin(x)


def cos(x: float) -> float:
    return _math.cos(x)


def tan(x: float) -> float:
    return _math.tan(x)


def asin(x: float) -> float:
    return _math.asin(x)


def acos(x: float) -> float:
    return _math.acos(x)


def atan(x: float) -> float:
    return _math.atan(x)


def atan2(y: float, x: float) -> float:
    """atan(y/x)，正确处理象限。"""
    return _math.atan2(y, x)


# --- 角度转换 ---

def degrees(radians: float) -> float:
    """弧度转角度。"""
    return _math.degrees(radians)


def radians(degrees: float) -> float:
    """角度转弧度。"""
    return _math.radians(degrees)


# --- 随机数 ---

def random() -> float:
    """返回 [0.0, 1.0) 的随机浮点数。"""
    return _random.random()


def randint(lo: int, hi: int) -> int:
    """返回 [lo, hi] 的随机整数（含两端）。"""
    return _random.randint(lo, hi)
