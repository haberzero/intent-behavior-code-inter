
import unittest
import textwrap
from core.types import parser_types as ast
from core.runtime.interpreter.interpreter import Interpreter
from core.runtime.interpreter.runtime_context import RuntimeContextImpl
from core.support.diagnostics.issue_tracker import IssueTracker
from core.compiler.parser.parser import Parser
from core.compiler.lexer.lexer import Lexer
from core.runtime.interpreter.runtime_types import ClassInstance
from core.types.exception_types import InterpreterError

class TestRuntimeTypes(unittest.TestCase):
    def setUp(self):
        self.issue_tracker = IssueTracker()
        self.interpreter = Interpreter(self.issue_tracker)

    def parse_code(self, code: str) -> ast.Module:
        lexer = Lexer(code, self.issue_tracker)
        tokens = lexer.tokenize()
        parser = Parser(tokens, self.issue_tracker)
        try:
            return parser.parse()
        except Exception:
            for diag in self.issue_tracker.diagnostics:
                print(f"Error: {diag.message} at line {diag.location.line if diag.location else '?'}")
            raise

    def run_code(self, code: str):
        module = self.parse_code(code)
        return self.interpreter.execute_module(module)

    def test_class_instantiation_type(self):
        """测试类实例化的运行时类型信息"""
        code = "class MyClass:\n    pass\n\nc = MyClass()\n"
        self.run_code(code)
        
        c = self.interpreter.context.get_variable("c")
        self.assertIsInstance(c, ClassInstance)
        self.assertEqual(c.class_def.name, "MyClass")
        self.assertIsNotNone(c.runtime_type)
        self.assertEqual(c.runtime_type.class_name, "MyClass")

    def test_type_check_success(self):
        """测试正确的类型注解"""
        code = "class MyClass:\n    pass\n\nMyClass c = MyClass()\n"
        self.run_code(code)
        c = self.interpreter.context.get_variable("c")
        self.assertIsInstance(c, ClassInstance)

    def test_type_check_fail_primitive(self):
        """测试类类型注解拒绝基础类型"""
        code = "class MyClass:\n    pass\n\nMyClass c = 1\n"
        with self.assertRaises(InterpreterError) as cm:
            self.run_code(code)
        self.assertIn("Type mismatch", str(cm.exception))

    def test_type_check_fail_other_class(self):
        """测试类类型注解拒绝其他类"""
        code = "class A:\n    pass\nclass B:\n    pass\n\nA a = B()\n"
        with self.assertRaises(InterpreterError) as cm:
            self.run_code(code)
        self.assertIn("Type mismatch", str(cm.exception))

    def test_inheritance_check(self):
        """测试多态赋值"""
        code = "class Parent:\n    pass\nclass Child(Parent):\n    pass\n\nParent p = Child()\n"
        self.run_code(code)
        p = self.interpreter.context.get_variable("p")
        self.assertEqual(p.class_def.name, "Child")

if __name__ == "__main__":
    unittest.main()
