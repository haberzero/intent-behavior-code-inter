import unittest
from tests.interpreter.base import BaseInterpreterTest

class TestOOP(BaseInterpreterTest):
    """
    测试解释器的面向对象支持。
    """
    def test_basic_class_and_instantiation(self):
        """测试基础类定义和实例化"""
        code = """
        class Point:
            var x = 0
            var y = 0
            
            func set_x(int val) -> void:
                self.x = val
            
            func get_x() -> int:
                return self.x
        
        Point p = Point()
        p.set_x(10)
        print(p.get_x())
        print(p.y)
        """
        self.run_code(code)
        self.assert_outputs(["10", "0"])

    def test_inheritance_and_overriding(self):
        """测试类继承和方法重写"""
        code = """
        class Animal:
            func speak() -> str:
                return "silent"
        
        class Dog(Animal):
            func speak() -> str:
                return "woof"
        
        Animal a = Animal()
        Dog d = Dog()
        print(a.speak())
        print(d.speak())
        """
        self.run_code(code)
        self.assert_outputs(["silent", "woof"])

    def test_bound_method(self):
        """测试绑定方法 (Bound Method)"""
        code = """
        class Adder:
            var base = 10
            func add(int val) -> int:
                return self.base + val
        
        Adder a = Adder()
        # 提取方法引用 (Bound Method)
        var f = a.add
        print(f(5))
        """
        self.run_code(code)
        self.assert_outputs(["15"])

if __name__ == '__main__':
    unittest.main()
