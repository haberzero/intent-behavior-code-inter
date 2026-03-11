from core.extension import sdk

class Calculator:
    @sdk.method("add")
    def add_numbers(self, a: int, b: int):
        return a + b

    @sdk.method("mul")
    def multiply_numbers(self, a: int, b: int):
        return a * b

implementation = Calculator()
