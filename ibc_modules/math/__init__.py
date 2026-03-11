import math
from core.extension import sdk as ibci

class MathLib:
    def __init__(self):
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

implementation = MathLib()
