
import unittest
from core.types import parser_types as ast
from core.runtime.interpreter.interpreter import Interpreter
from core.runtime.interpreter.runtime_context import RuntimeContextImpl
from core.runtime.interpreter.interfaces import Scope
from core.support.diagnostics.issue_tracker import IssueTracker
from core.compiler.parser.parser import Parser
from core.compiler.lexer.lexer import Lexer

class TestInterpreterScope(unittest.TestCase):
    def setUp(self):
        self.issue_tracker = IssueTracker()
        self.interpreter = Interpreter(self.issue_tracker)

    def parse_code(self, code: str, filename: str) -> ast.Module:
        lexer = Lexer(code, self.issue_tracker)
        tokens = lexer.tokenize()
        parser = Parser(tokens, self.issue_tracker)
        return parser.parse()

    def test_scope_isolation(self):
        """测试不同 Scope 之间的变量隔离"""
        code1 = "x = 10"
        code2 = "y = x + 5"
        
        module1 = self.parse_code(code1, "module1.ibci")
        module2 = self.parse_code(code2, "module2.ibci")
        
        # Scope 1
        scope1 = RuntimeContextImpl().global_scope
        self.interpreter.execute_module(module1, scope=scope1)
        
        # Verify x is in scope1
        self.assertIsNotNone(scope1.get_symbol("x"))
        self.assertEqual(scope1.get_symbol("x").value, 10)
        
        # Scope 2
        scope2 = RuntimeContextImpl().global_scope
        
        # Execute module2 in scope2 should FAIL because x is not in scope2
        with self.assertRaises(Exception): # Expecting InterpreterError or similar
            self.interpreter.execute_module(module2, scope=scope2)
            
        # Execute module2 in scope1 should SUCCEED
        self.interpreter.execute_module(module2, scope=scope1)
        self.assertIsNotNone(scope1.get_symbol("y"))
        self.assertEqual(scope1.get_symbol("y").value, 15)

    def test_intrinsics_availability(self):
        """测试内置函数在不同 Scope 中的可用性"""
        code = "l = len([1, 2, 3])"
        module = self.parse_code(code, "test_intrinsics.ibci")
        
        scope = RuntimeContextImpl().global_scope
        
        # execute_module 会自动重新注册 intrinsics 到新 scope
        self.interpreter.execute_module(module, scope=scope)
        
        self.assertIsNotNone(scope.get_symbol("l"))
        self.assertEqual(scope.get_symbol("l").value, 3)
        
        # Verify 'len' is present in the scope
        self.assertIsNotNone(scope.get_symbol("len"))

    def test_context_restoration(self):
        """测试执行后 Context 是否恢复"""
        original_context = self.interpreter.context
        
        code = "x = 1"
        module = self.parse_code(code, "test_restore.ibci")
        
        new_scope = RuntimeContextImpl().global_scope
        self.interpreter.execute_module(module, scope=new_scope)
        
        # Context should be restored to the original one
        self.assertIs(self.interpreter.context, original_context)
        # Original context should NOT have x
        self.assertIsNone(original_context.global_scope.get_symbol("x"))

if __name__ == "__main__":
    unittest.main()
