import unittest
from tests.interpreter.base import BaseInterpreterTest

class TestBasicOps(BaseInterpreterTest):
    """
    测试解释器的基础运算和控制流。
    """
    def test_arithmetic(self):
        """测试算术运算"""
        code = """
        print(1 + 2)
        print(10 - 4)
        print(3 * 4)
        print(10 / 2)
        print(10 % 3)
        """
        self.run_code(code)
        self.assert_outputs(["3", "6", "12", "5", "1"])

    def test_logic_and_comparison(self):
        """测试逻辑与比较运算"""
        code = """
        print(1 == 1)
        print(1 != 1)
        print(1 < 2)
        print(1 > 2)
        print(1 <= 1)
        print(1 >= 2)
        print(1 == 1 and 2 == 2)
        print(1 == 1 or 2 == 3)
        print(not (1 == 1))
        """
        self.run_code(code)
        self.assert_outputs(["1", "0", "1", "0", "1", "0", "1", "1", "0"])

    def test_bitwise_ops(self):
        """测试位运算"""
        code = """
        print(5 & 3)   # 101 & 011 = 001 (1)
        print(5 | 3)   # 101 | 011 = 111 (7)
        print(5 ^ 3)   # 101 ^ 011 = 110 (6)
        print(1 << 2)  # 1 -> 100 (4)
        print(8 >> 1)  # 1000 -> 100 (4)
        print(~0)      # ~0 = -1
        """
        self.run_code(code)
        self.assert_outputs(["1", "7", "6", "4", "4", "-1"])

    def test_control_flow_if(self):
        """测试 if-else 控制流"""
        code = """
        var x = 10
        if x > 5:
            print("x is big")
        else:
            print("x is small")
            
        if x < 5:
            print("unreachable")
        elif x == 10:
            print("x is ten")
        """
        self.run_code(code)
        self.assert_outputs(["x is big", "x is ten"])

    def test_control_flow_loops(self):
        """测试 while 和 for-in 循环"""
        code = """
        var i = 0
        while i < 3:
            print(i)
            i = i + 1
            
        for x in [10, 20]:
            print(x)
        """
        self.run_code(code)
        self.assert_outputs(["0", "1", "2", "10", "20"])

    def test_functions(self):
        """测试函数定义、调用及递归"""
        code = """
        func add(int a, int b) -> int:
            return a + b
            
        func fib(int n) -> int:
            if n <= 1:
                return n
            return fib(n-1) + fib(n-2)
            
        print(add(1, 2))
        print(fib(6))
        """
        self.run_code(code)
        self.assert_outputs(["3", "8"])

if __name__ == '__main__':
    unittest.main()
