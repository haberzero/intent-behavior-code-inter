import math


class MathLib:
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
