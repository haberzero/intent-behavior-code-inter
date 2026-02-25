import unittest
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.lexer.lexer import Lexer
from utils.parser.parser import Parser
from utils.interpreter.interpreter import Interpreter
from utils.diagnostics.issue_tracker import IssueTracker
from typedef.exception_types import InterpreterError
from typedef.diagnostic_types import CompilerError

class TestInterpreterComplex(unittest.TestCase):
    """
    重构后的复杂单元测试，验证架构的稳健性、类型保护和控制流限制。
    """
    def setUp(self):
        self.output = []

    def capture_output(self, msg):
        self.output.append(msg)

    def run_code(self, code):
        lexer = Lexer(code.strip() + "\n")
        tokens = lexer.tokenize()
        issue_tracker = IssueTracker()
        parser = Parser(tokens, issue_tracker)
        module = parser.parse()
        interpreter = Interpreter(issue_tracker, output_callback=self.capture_output)
        return interpreter.interpret(module)

    def test_type_checking(self):
        # 1. 测试非法的显式类型赋值
        code = 'int x = "hello"'
        with self.assertRaises(InterpreterError) as cm:
            self.run_code(code)
        self.assertIn("Type mismatch", str(cm.exception))

        # 2. 测试 var 的灵活性
        code_var = """
var x = 10
x = "now i am string"
"""
        # 不应抛出异常
        self.run_code(code_var)

    def test_builtin_protection(self):
        # 1. 尝试对内置函数符号赋值
        code = "print = 10"
        with self.assertRaises(InterpreterError) as cm:
            self.run_code(code)
        self.assertIn("Cannot reassign built-in variable", str(cm.exception))

        # 2. 尝试重定义内置函数
        code_func = """
func print(str s) -> None:
    pass
"""
        with self.assertRaises(InterpreterError) as cm:
            self.run_code(code_func)
        self.assertIn("Cannot redefine built-in function", str(cm.exception))

    def test_division_by_zero(self):
        code = "int x = 10 / 0"
        with self.assertRaises(InterpreterError) as cm:
            self.run_code(code)
        self.assertIn("Division by zero", str(cm.exception))

    def test_type_error_in_binop(self):
        code = """
str s = "hello"
int i = 10
var res = s + i
"""
        with self.assertRaises(InterpreterError) as cm:
            self.run_code(code)
        self.assertIn("not supported for types", str(cm.exception))

    def test_recursion_limit(self):
        code = """
func f(int n) -> int:
    return f(n)

f(1)
"""
        lexer = Lexer(code.strip() + "\n")
        tokens = lexer.tokenize()
        issue_tracker = IssueTracker()
        parser = Parser(tokens, issue_tracker)
        module = parser.parse()

        interp = Interpreter(issue_tracker, output_callback=self.capture_output)
        interp.max_call_stack = 10

        with self.assertRaises(InterpreterError) as cm:
            interp.interpret(module)
        self.assertIn("RecursionError: Maximum recursion depth", str(cm.exception))

    def test_control_flow_outside_loop(self):
        # 测试在循环外使用 break
        code = "break"
        with self.assertRaises(InterpreterError) as cm:
            self.run_code(code)
        self.assertIn("Control flow statement used outside", str(cm.exception))

    def test_len_builtin(self):
        code = """
list l = [1, 2, 3]
int length = len(l)
print(length)
"""
        self.run_code(code)
        self.assertEqual(self.output, ["3"])

    def test_container_ext(self):
        """测试容器原生方法的扩展支持 (list.append, dict.keys 等)"""
        code = """
list l = [1, 2]
l.append(3)
l.sort()
dict d = {"a": 1, "b": 2}
list keys = (list)d.keys()
keys.sort()
print(len(l))
print(keys)
"""
        self.run_code(code)
        self.assertEqual(self.output[0], "3")
        self.assertIn("'a'", self.output[1])
        self.assertIn("'b'", self.output[1])

    def test_exception_handling(self):
        """测试基础错误捕获机制 (try-except-finally-raise)"""
        # 1. 基础 try-except-finally
        code1 = """
int x = 0
try:
    x = 1 / 0
except:
    x = 2
finally:
    x = x + 10
print(x)
"""
        self.output = []
        self.run_code(code1)
        self.assertEqual(self.output, ["12"])

        # 2. 具名异常捕获
        code2 = """
try:
    raise "Custom Error"
except str as e:
    print(e)
"""
        self.output = []
        self.run_code(code2)
        self.assertEqual(self.output, ["Custom Error"])

        # 3. try-else-finally 全流程
        code3 = """
str status = ""
try:
    status = "running"
except:
    status = "error"
else:
    status = "ok"
finally:
    status = status + "_done"
print(status)
"""
        self.output = []
        self.run_code(code3)
        self.assertEqual(self.output, ["ok_done"])

    def test_ai_module_ext(self):
        """测试 ai 模块的新增配置功能 (retry/timeout)"""
        code = """
import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
ai.set_retry(2)
ai.set_timeout(10.5)
str res = ~~hello~~
print("done")
"""
        self.output = []
        self.run_code(code)
        self.assertEqual(self.output, ["done"])

if __name__ == '__main__':
    unittest.main()
