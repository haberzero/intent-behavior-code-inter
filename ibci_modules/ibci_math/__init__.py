"""
Math 数学计算插件

纯 Python 实现，零侵入。
"""
import math


class MathLib:
    """
    Math 2.2: 数学计算插件。
    不继承任何核心类，完全独立。
    """
    def __init__(self):
        self.pi = math.pi

    def sqrt(self, x: float) -> float:
        return math.sqrt(x)

    def pow(self, x: float, y: float) -> float:
        return math.pow(x, y)

    def sin(self, x: float) -> float:
        return math.sin(x)

    def cos(self, x: float) -> float:
        return math.cos(x)


def create_implementation():
    return MathLib()
