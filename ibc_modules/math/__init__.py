import math
from core.extension import sdk as ibci

class MathLib(ibci.IbPlugin):
    """
    Math 2.1: 数学计算插件。
    """
    def __init__(self):
        super().__init__()
        self.pi = math.pi
        self._ibci_whitelist = ["pi"]
    
    @ibci.method("sqrt")
    def sqrt(self, x: float) -> float:
        return math.sqrt(x)
        
    @ibci.method("pow")
    def pow(self, x: float, y: float) -> float:
        return math.pow(x, y)
        
    @ibci.method("sin")
    def sin(self, x: float) -> float:
        return math.sin(x)
        
    @ibci.method("cos")
    def cos(self, x: float) -> float:
        return math.cos(x)

def create_implementation():
    return MathLib()
