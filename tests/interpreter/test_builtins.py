import unittest
from tests.interpreter.base import BaseInterpreterTest

class TestBuiltins(BaseInterpreterTest):
    """
    测试解释器的内置类型及方法。
    """
    def test_list_ops(self):
        """测试列表操作"""
        code = """
        list l = [3, 1, 2]
        l.append(4)
        print(l.len())
        l.sort()
        print(l[0])
        print(l[1])
        print(l[2])
        print(l[3])
        """
        self.run_code(code)
        self.assert_outputs(["4", "1", "2", "3", "4"])

    def test_dict_ops(self):
        """测试字典操作"""
        code = """
        dict d = {"a": 1, "b": 2}
        print(d["a"])
        print(d.get("b"))
        d["c"] = 3
        print(d["c"])
        """
        self.run_code(code)
        self.assert_outputs(["1", "2", "3"])

    def test_string_ops(self):
        """测试字符串操作及内联优化"""
        code = """
        str s = "hello"
        print(s + " world")
        print(s + 123.cast_to(str))
        print("123".cast_to(int))
        
        # 边界：空字符串拼接
        str empty = ""
        print(empty + "append")
        
        # 边界：长度计算 (内联优化)
        print("abc".len())
        print("".len())
        """
        self.run_code(code)
        self.assert_outputs(["hello world", "hello123", "123", "append", "3", "0"])

    def test_type_cast_edge_cases(self):
        """测试类型强转的边界情况"""
        code = """
        # int -> float
        int x = 42
        float f = x.cast_to(float)
        print(f)
        
        # str -> bool
        print("true".cast_to(bool))
        print("false".cast_to(bool))
        print("".cast_to(bool))
        
        # 链式转换
        print(100.cast_to(str).cast_to(int))
        """
        self.run_code(code)
        self.assert_outputs(["42.0", "1", "0", "0", "100"])

    def test_int_ops(self):
        """测试整数辅助方法"""
        code = """
        int x = 10
        print(x.to_bool())
        print(0.to_bool())
        
        list l = 3.to_list()
        print(l.len())
        """
        self.run_code(code)
        self.assert_outputs(["1", "0", "3"])

    def test_none_ops(self):
        """测试 None 及其布尔转换"""
        code = """
        var n = None
        if n:
            print("none is true")
        else:
            print("none is false")
        """
        self.run_code(code)
        self.assert_outputs(["none is false"])

if __name__ == '__main__':
    unittest.main()
