"""
ibci_math/core.py

IBCI Math 插件实现。非侵入层插件，零内核依赖。
"""
import math


class MathLib:
    """数学运算工具，包装 Python math 标准库。"""

    def __init__(self):
        self.pi: float = math.pi

    def sqrt(self, x: float) -> float:
        return math.sqrt(x)

    def pow(self, x: float, y: float) -> float:
        return math.pow(x, y)

    def sin(self, x: float) -> float:
        return math.sin(x)

    def cos(self, x: float) -> float:
        return math.cos(x)


def create_implementation() -> MathLib:
    return MathLib()
