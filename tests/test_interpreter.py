import unittest
import sys
import os
import shutil
import textwrap

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.engine import IBCIEngine
from core.types.exception_types import InterpreterError
from core.types.diagnostic_types import CompilerError

class TestInterpreter(unittest.TestCase):
    """
    Consolidated tests for Interpreter.
    Covers basic execution, complex error handling, and system integration.
    """

    def setUp(self):
        self.output = []
        self.test_dir = os.path.join(os.path.dirname(__file__), "tmp_test_project")
        os.makedirs(self.test_dir, exist_ok=True)
        self.engine = IBCIEngine(root_dir=self.test_dir)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def capture_output(self, msg):
        self.output.append(msg)

    def run_code(self, code):
        test_file = os.path.join(self.test_dir, "test.ibci")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(code).strip() + "\n")
        
        success = self.engine.run(test_file, output_callback=self.capture_output)
        if not success:
            # Re-run manually to raise exceptions for tests that expect them
            self.engine._prepare_interpreter(output_callback=self.capture_output)
            ast_cache = self.engine.scheduler.compile_project(test_file)
            self.engine.interpreter.interpret(ast_cache[test_file])
            
        return success, self.engine.interpreter

    def create_file(self, name, content):
        path = os.path.join(self.test_dir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(textwrap.dedent(content))
        return path

    # --- Basic Execution ---

    def test_variable_and_scope(self):
        """Test variable assignment and scope shadowing."""
        code = """
        int a = 10
        int b = a + 5
        var c = b
        func test() -> int:
            int a = 20
            return a
        int res = test()
        """
        _, interp = self.run_code(code)
        self.assertEqual(interp.context.get_variable("a"), 10)
        self.assertEqual(interp.context.get_variable("b"), 15)
        self.assertEqual(interp.context.get_variable("c"), 15)
        self.assertEqual(interp.context.get_variable("res"), 20)

    def test_control_flow(self):
        """Test if-else, while, and for loops."""
        code = """
        int sum = 0
        for i in 5:
            sum = sum + i
        
        int count = 0
        while count < 3:
            count = count + 1
            
        int res = 0
        if sum > 5:
            res = 1
        else:
            res = -1
        """
        success, interp = self.run_code(code)
        self.assertTrue(success)
        self.assertEqual(interp.context.get_variable("sum"), 10)
        self.assertEqual(interp.context.get_variable("count"), 3)
        self.assertEqual(interp.context.get_variable("res"), 1)

    def test_recursion(self):
        """Test recursive function calls."""
        code = """
        func fib(int n) -> int:
            if n <= 1:
                return n
            return fib(n-1) + fib(n-2)
        int res = fib(6)
        """
        success, interp = self.run_code(code)
        self.assertTrue(success)
        self.assertEqual(interp.context.get_variable("res"), 8)

    # --- Error Handling & Protection ---

    def test_interpreter_errors(self):
        """Test division by zero and type mismatch errors."""
        # 1. Division by zero
        # We need to bypass semantic check for 1 / 0 if it's static. 
        # But if it's runtime, run_code will raise InterpreterError.
        code1 = "int x = 1 / 0"
        with self.assertRaises((InterpreterError, CompilerError)):
            self.run_code(code1)

        # 2. Type mismatch in explicit declaration
        code2 = 'int x = "s"'
        with self.assertRaises((InterpreterError, CompilerError)):
            self.run_code(code2)

    def test_builtin_protection(self):
        """Test protection of built-in functions."""
        with self.assertRaises((InterpreterError, CompilerError)):
            self.run_code("print = 10")

    def test_exception_handling(self):
        """Test try-except-finally blocks."""
        code = """
        int x = 0
        try:
            x = 1 / 0
        except:
            x = 2
        finally:
            x = x + 10
        """
        _, interp = self.run_code(code)
        self.assertEqual(interp.context.get_variable("x"), 12)

    # --- Integration & Stdlib ---

    def test_stdlib_json_math(self):
        """Test built-in json and math modules."""
        code = """
        import json
        import math
        str data = '{"key": 42}'
        dict d = json.parse(data)
        print(d["key"])
        float root = math.sqrt(16.0)
        """
        self.run_code(code)
        self.assertIn("42", self.output)

    def test_cross_file_import(self):
        """Test importing symbols from another file."""
        self.create_file("lib.ibci", "int val = 100")
        code = """
        import lib
        int res = lib.val
        """
        _, interp = self.run_code(code)
        self.assertEqual(interp.context.get_variable("res"), 100)

    def test_container_extensions(self):
        """Test list and dict native methods (append, sort, etc.)."""
        code = """
        list l = [2, 1]
        l.append(3)
        l.sort()
        """
        _, interp = self.run_code(code)
        self.assertEqual(interp.context.get_variable("l"), [1, 2, 3])

if __name__ == '__main__':
    unittest.main()
