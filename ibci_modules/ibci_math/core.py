"""
ibci_math/core.py

IBCI Math 数学运算插件实现。非侵入层插件，零内核依赖。
"""
import math
import random as _random


class MathLib:
    """数学运算工具，包装 Python math 标准库。"""

    def __init__(self):
        self.pi: float = math.pi
        self.e: float = math.e
        self.inf: float = math.inf

    # --- 基础运算 ---

    def sqrt(self, x: float) -> float:
        """平方根。"""
        return math.sqrt(x)

    def pow(self, x: float, y: float) -> float:
        """x 的 y 次方。"""
        return math.pow(x, y)

    def abs(self, x: float) -> float:
        """绝对值。"""
        return abs(x)

    def floor(self, x: float) -> int:
        """向下取整。"""
        return math.floor(x)

    def ceil(self, x: float) -> int:
        """向上取整。"""
        return math.ceil(x)

    def round(self, x: float, ndigits: int) -> float:
        """四舍五入到指定小数位。"""
        return builtins_round(x, ndigits)

    def clamp(self, x: float, lo: float, hi: float) -> float:
        """将 x 限制在 [lo, hi] 范围内。"""
        if x < lo:
            return lo
        if x > hi:
            return hi
        return x

    def min(self, a: float, b: float) -> float:
        """返回两个值中较小的一个。"""
        return a if a < b else b

    def max(self, a: float, b: float) -> float:
        """返回两个值中较大的一个。"""
        return a if a > b else b

    # --- 对数/指数 ---

    def exp(self, x: float) -> float:
        """e 的 x 次方。"""
        return math.exp(x)

    def log(self, x: float) -> float:
        """自然对数 ln(x)。"""
        return math.log(x)

    def log2(self, x: float) -> float:
        """以 2 为底的对数。"""
        return math.log2(x)

    def log10(self, x: float) -> float:
        """以 10 为底的对数。"""
        return math.log10(x)

    # --- 三角函数 ---

    def sin(self, x: float) -> float:
        return math.sin(x)

    def cos(self, x: float) -> float:
        return math.cos(x)

    def tan(self, x: float) -> float:
        return math.tan(x)

    def asin(self, x: float) -> float:
        return math.asin(x)

    def acos(self, x: float) -> float:
        return math.acos(x)

    def atan(self, x: float) -> float:
        return math.atan(x)

    def atan2(self, y: float, x: float) -> float:
        """atan(y/x)，正确处理象限。"""
        return math.atan2(y, x)

    # --- 角度转换 ---

    def degrees(self, radians: float) -> float:
        """弧度转角度。"""
        return math.degrees(radians)

    def radians(self, degrees: float) -> float:
        """角度转弧度。"""
        return math.radians(degrees)

    # --- 随机数 ---

    def random(self) -> float:
        """返回 [0.0, 1.0) 的随机浮点数。"""
        return _random.random()

    def randint(self, lo: int, hi: int) -> int:
        """返回 [lo, hi] 的随机整数（含两端）。"""
        return _random.randint(lo, hi)


# Python 内置 round 的别名，避免与方法名冲突
builtins_round = round


def create_implementation() -> MathLib:
    return MathLib()
