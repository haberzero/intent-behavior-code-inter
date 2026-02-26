import math

class MathLib:
    pi = math.pi
    
    @staticmethod
    def sqrt(x: float) -> float:
        return math.sqrt(x)
        
    @staticmethod
    def pow(x: float, y: float) -> float:
        return math.pow(x, y)
        
    @staticmethod
    def sin(x: float) -> float:
        return math.sin(x)
        
    @staticmethod
    def cos(x: float) -> float:
        return math.cos(x)

implementation = MathLib()
