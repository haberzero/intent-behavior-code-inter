import unittest
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.support.diagnostics.issue_tracker import IssueTracker
from core.types.exception_types import InterpreterError, SemanticError
from core.types.diagnostic_types import CompilerError
from core.engine import IBCIEngine

class TestTypePromotion(unittest.TestCase):
    def setUp(self):
        # 使用标准的引擎初始化，它会自动发现内置模块
        self.engine = IBCIEngine(auto_sniff=True)

    def run_code(self, code):
        # 创建一个临时文件来模拟运行
        test_file = "tmp_type_test.ibci"
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(code)
        
        try:
            success = self.engine.run(test_file)
            if not success:
                # 检查是否有静态错误
                if self.engine.scheduler.issue_tracker.has_errors:
                    raise CompilerError(self.engine.scheduler.issue_tracker.diagnostics)
                raise InterpreterError("Execution failed")
            return None, self.engine.interpreter
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

    def test_valid_numeric_promotion(self):
        # int + float -> float
        code = """
int a = 10
float b = 5.5
float c = a + b
"""
        _, interp = self.run_code(code)
        self.assertEqual(interp.context.get_variable("c"), 15.5)

    def test_invalid_string_numeric_addition(self):
        # int + str -> Error
        code = """
int a = 10
str b = "5"
var c = a + b
"""
        with self.assertRaises(CompilerError) as cm:
            self.run_code(code)
        msg = cm.exception.diagnostics[0].message
        self.assertIn("Binary operator '+' not supported for types 'int' and 'str'", msg)

    def test_valid_string_concatenation(self):
        code = """
str a = "hello "
str b = "world"
str c = a + b
"""
        _, interp = self.run_code(code)
        self.assertEqual(interp.context.get_variable("c"), "hello world")

    def test_invalid_string_subtraction(self):
        code = """
str a = "hello"
str b = "h"
var c = a - b
"""
        with self.assertRaises(CompilerError) as cm:
            self.run_code(code)
        msg = cm.exception.diagnostics[0].message
        self.assertIn("Binary operator '-' not supported for types 'str' and 'str'", msg)

    def test_numeric_comparison_promotion(self):
        code = """
int a = 10
float b = 5.5
bool c = a > b
"""
        _, interp = self.run_code(code)
        self.assertTrue(interp.context.get_variable("c"))

    def test_invalid_comparison(self):
        code = """
int a = 10
str b = "10"
bool c = a == b
"""
        with self.assertRaises(CompilerError) as cm:
            self.run_code(code)
        msg = cm.exception.diagnostics[0].message
        self.assertIn("Comparison operator '==' not supported for types 'int' and 'str'", msg)

    def test_runtime_invalid_addition(self):
        # Using 'var' to bypass semantic check
        code = """
var a = 10
var b = "5"
var c = a + b
"""
        # Note: In our current implementation, even 'var' is inferred statically if initialized.
        # To truly test runtime, we'd need a more complex scenario, but let's just ensure 
        # that either semantic or runtime catch it.
        with self.assertRaises((CompilerError, InterpreterError)):
            self.run_code(code)

    def test_behavior_expr_runtime_dot_access(self):
        code = """
import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
dict user = {"name": "Alice"}
str res = ~~Hello $user.name~~
"""
        _, interp = self.run_code(code)
        self.assertIn("Alice", interp.context.get_variable("res"))

if __name__ == '__main__':
    unittest.main()
