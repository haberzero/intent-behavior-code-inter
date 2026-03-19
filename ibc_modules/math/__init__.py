import math
from core.extension import ibcext

class MathLib(ibcext.IbPlugin):
    """
    Math 2.1: 数学计算插件。
    """
    def __init__(self):
        super().__init__()
        self.pi = math.pi
        self._ibci_whitelist = ["pi"]

    @ibcext.method("sqrt")
    def sqrt(self, x: float) -> float:
        return math.sqrt(x)

    @ibcext.method("pow")
    def pow(self, x: float, y: float) -> float:
        return math.pow(x, y)

    @ibcext.method("sin")
    def sin(self, x: float) -> float:
        return math.sin(x)

    @ibcext.method("cos")
    def cos(self, x: float) -> float:
        return math.cos(x)

def create_implementation():
    return MathLib()
