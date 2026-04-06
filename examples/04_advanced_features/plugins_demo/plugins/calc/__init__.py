class Calculator:
    def add(self, a: int, b: int) -> int:
        return a + b

    def mul(self, a: int, b: int) -> int:
        return a * b

    def sub(self, a: int, b: int) -> int:
        return a - b

    def div(self, a: int, b: int) -> int:
        if b == 0: return 0
        return a // b

def create_implementation():
    return Calculator()
