from core.extension import ibcext

class Calculator:
    @ibcext.method("add")
    def add_numbers(self, a: int, b: int):
        return a + b

    @ibcext.method("mul")
    def multiply_numbers(self, a: int, b: int):
        return a * b

implementation = Calculator()
