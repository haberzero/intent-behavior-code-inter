import unittest
from tests.base import BaseIBCTest, MockAI
from core.domain.types import ModuleMetadata
from core.domain.issue import CompilerError, InterpreterError

class TestComprehensiveInterpreter(BaseIBCTest):
    """
    全面测试解释器的逻辑细节与边界情况。
    """

    def setUp(self):
        super().setUp()
        self.setup_mock_ai()

    def test_intent_stacking(self):
        code = """
        intent "A":
            intent "B":
                @ C
                str x = @~ T ~
        """
        self.run_code(code)
        sys_prompt = self.mock_ai.last_sys
        self.assertIn("A", sys_prompt)
        self.assertIn("B", sys_prompt)
        self.assertIn("C", sys_prompt)
        # 顺序验证
        self.assertTrue(sys_prompt.find("A") < sys_prompt.find("B") < sys_prompt.find("C"))

    def test_intent_override(self):
        code = """
        intent "A":
            intent ! "B":
                @ C
                str x = @~ T ~
        """
        self.run_code(code)
        sys_prompt = self.mock_ai.last_sys
        self.assertNotIn("A", sys_prompt)
        self.assertIn("B", sys_prompt)
        self.assertIn("C", sys_prompt)

    def test_intent_remove(self):
        code = """
        intent "A":
            intent "B":
                @- A
                str x = @~ T ~
        """
        self.run_code(code)
        sys_prompt = self.mock_ai.last_sys
        self.assertNotIn("A", sys_prompt)
        self.assertIn("B", sys_prompt)

    def test_builtin_ops_comprehensive(self):
        """全面验证内置类型的方法"""
        code = """
        list l = [3, 1, 2]
        l.append(4)
        print(l.len())
        l.sort()
        print(l[0])
        
        dict d = {"a": 1}
        print(d.get("a"))
        print(d.len())
        
        str s = "hello"
        print(s.len())
        int i = "123".cast_to(int)
        print(i + 1)
        
        int x = 10
        print(x.to_bool())
        list range_l = 3.to_list()
        print(range_l.len())
        """
        self.run_code(code)
        # l.len() -> 4
        # l[0] after sort -> 1
        # d.get("a") -> 1
        # d.len() -> 1
        # s.len() -> 5
        # "123".cast_to(int) + 1 -> 124
        # 10.to_bool() -> 1
        # 3.to_list().len() -> 3
        self.assert_outputs(["4", "1", "1", "1", "5", "124", "1", "3"])

    def test_oop_inheritance_and_bound_methods(self):
        """验证 OOP 继承、重写与绑定方法"""
        code = """
        class Base:
            func greet() -> str:
                return "base"
        
        class Derived(Base):
            func greet() -> str:
                return "derived"
            
        Base b = Base()
        Derived d = Derived()
        print(b.greet())
        print(d.greet())
        
        var f = d.greet
        print(f())
        """
        self.run_code(code)
        self.assert_outputs(["base", "derived", "derived"])

    def test_circular_reference_serialization(self):
        """验证循环引用的运行时序列化与恢复"""
        from core.runtime.serialization.runtime_serializer import RuntimeSerializer, RuntimeDeserializer
        
        code = """
        dict a = {}
        dict b = {}
        a["next"] = b
        b["next"] = a
        """
        self.run_code(code)
        
        ctx = self.engine.interpreter.context
        serializer = RuntimeSerializer(self.engine.registry)
        data = serializer.serialize_context(ctx)
        
        # 验证序列化数据中包含两个实例
        self.assertTrue(len(data["pools"]["instances"]) >= 2)
        
        # 反序列化
        deserializer = RuntimeDeserializer(self.engine.registry)
        new_ctx = deserializer.deserialize_context(data)
        
        # 验证循环引用依然存在
        a_val = new_ctx.get_variable("a")
        b_val = new_ctx.get_variable("b")
        self.assertIs(a_val.receive("__getitem__", [self.engine.registry.box("next")]), b_val)
        self.assertIs(b_val.receive("__getitem__", [self.engine.registry.box("next")]), a_val)

    def test_semantic_errors(self):
        """验证解释器/编译器对边界错误的上报"""
        # 1. 类型不匹配
        with self.assertRaises(CompilerError):
            with self.silent_mode():
                self.run_code('int x = "str"')
            
        # 2. 未定义变量
        with self.assertRaises(CompilerError):
            with self.silent_mode():
                self.run_code('print(unknown)')
            
        # 3. 参数不匹配
        with self.assertRaises(CompilerError):
            code = """
            func f(int a):
                pass
            f(1, 2)
            """
            with self.silent_mode():
                self.run_code(code)

    def test_chained_comparison(self):
        """验证链式比较 a < b < c"""
        code = """
        print(1 < 2 < 3)
        print(1 < 2 < 0)
        print(1 < 2 == 2)
        print(5 > 3 > 1)
        """
        self.run_code(code)
        # 1 < 2 < 3 -> True
        # 1 < 2 < 0 -> False
        # 1 < 2 == 2 -> True
        # 5 > 3 > 1 -> True
        self.assert_outputs(["1", "0", "1", "1"])

if __name__ == "__main__":
    unittest.main()
