from tests.base import BaseIBCTest, MockAI
from core.runtime.objects.kernel import IbObject
from core.compiler.serialization.serializer import FlatSerializer
import textwrap

class TestIntentInterpolation(BaseIBCTest):
    """
    测试意图插值系统 (@ $var)
    验证 LLMExecutor 是否能正确从栈中提取变量并构建 Prompt。
    """
    
    def test_basic_interpolation(self):
        """测试基础变量插值 @ $x"""
        code = """
        int x = 42
        str res = @~ 这是一次测试，数值是 $x ~
        """
        with self.capture_llm() as (captured, hook):
            self.run_code(code, pre_run_hook=hook)
            
        self.assertEqual(len(captured), 1)
        self.assertIn("数值是 42", captured[0]["user"])

    def test_complex_interpolation(self):
        """测试复杂路径插值 @ $u.name"""
        code = """
        class User:
            str name = "Alice"
        
        User u = User()
        str res = @~ 用户名是 $u.name ~
        """
        with self.capture_llm() as (captured, hook):
            self.run_code(code, pre_run_hook=hook)
            
        self.assertEqual(len(captured), 1)
        self.assertIn("用户名是 Alice", captured[0]["user"])

    def test_intent_stacking_in_calls(self):
        """测试函数调用过程中的意图栈叠加"""
        code = """
        func greet(str name):
            str res = @~ 你好 $name ~
            
        greet("Bob")
        """
        with self.capture_llm() as (captured, hook):
            self.run_code(code, pre_run_hook=hook)
            
        self.assertEqual(len(captured), 1)
        user_prompt = captured[0]["user"]
        self.assertIn("你好 Bob", user_prompt)
