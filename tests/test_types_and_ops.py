import unittest
import sys
import os
import textwrap

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.engine import IBCIEngine
from core.types.diagnostic_types import CompilerError

class TestTypesAndOps(unittest.TestCase):
    """
    Consolidated tests for data types and operators.
    Covers bitwise operations, type promotion, and invalid operator usage.
    """

    def setUp(self):
        self.engine = IBCIEngine()

    def run_code(self, code):
        test_file = os.path.join(os.path.dirname(__file__), "tmp_types_ops_test.ibci")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(code).strip() + "\n")
        
        try:
            success = self.engine.run(test_file)
            if not success:
                if self.engine.scheduler.issue_tracker.has_errors:
                    raise CompilerError(self.engine.scheduler.issue_tracker.diagnostics)
            return self.engine.interpreter
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

    # --- Bitwise Operations ---

    def test_bitwise_operators(self):
        """Test bitwise AND, OR, XOR, shifts, and NOT."""
        code = """
        int a = 10  # 1010
        int b = 3   # 0011
        int r_and = a & b   # 0010 = 2
        int r_or = a | b    # 1011 = 11
        int r_xor = a ^ b   # 1001 = 9
        int r_lshift = a << 2 # 101000 = 40
        int r_rshift = a >> 1 # 0101 = 5
        int r_not = ~a      # -11
        """
        interp = self.run_code(code)
        self.assertEqual(interp.context.get_variable("r_and"), 2)
        self.assertEqual(interp.context.get_variable("r_or"), 11)
        self.assertEqual(interp.context.get_variable("r_xor"), 9)
        self.assertEqual(interp.context.get_variable("r_lshift"), 40)
        self.assertEqual(interp.context.get_variable("r_rshift"), 5)
        self.assertEqual(interp.context.get_variable("r_not"), -11)

    # --- Type Promotion & Compatibility ---

    def test_numeric_promotion(self):
        """Test promotion from int to float in arithmetic and comparison."""
        code = """
        int a = 10
        float b = 5.5
        float r_add = a + b   # 15.5
        bool r_gt = a > b     # True
        """
        interp = self.run_code(code)
        self.assertEqual(interp.context.get_variable("r_add"), 15.5)
        self.assertTrue(interp.context.get_variable("r_gt"))

    def test_string_operations(self):
        """Test string concatenation and invalid subtraction."""
        code = """
        str a = "hello "
        str b = "world"
        str c = a + b
        """
        interp = self.run_code(code)
        self.assertEqual(interp.context.get_variable("c"), "hello world")
        
        # Invalid subtraction
        with self.assertRaises(CompilerError):
            self.run_code('str res = "a" - "b"')

    def test_invalid_mixed_types(self):
        """Test invalid operations between incompatible types."""
        # int + str
        with self.assertRaises(CompilerError):
            self.run_code('int x = 10 + "s"')
            
        # float & int
        with self.assertRaises(CompilerError):
            self.run_code('float f = 1.5; int x = f & 1')

    # --- None & Callable ---

    def test_none_comparisons(self):
        """Test None comparisons with various types."""
        code = """
        var a = None
        bool r1 = (a == None)    # True
        bool r2 = (a != None)    # False
        bool r3 = (10 == None)   # False
        bool r4 = ("s" != None)  # True
        bool r5 = (None == 0)    # False
        """
        interp = self.run_code(code)
        self.assertTrue(interp.context.get_variable("r1"))
        self.assertFalse(interp.context.get_variable("r2"))
        self.assertFalse(interp.context.get_variable("r3"))
        self.assertTrue(interp.context.get_variable("r4"))
        self.assertFalse(interp.context.get_variable("r5"))

    def test_callable_type_assignment(self):
        """Test callable type declaration and assignment."""
        code = """
        func my_func(int x) -> int:
            return x + 1
        callable f = my_func
        int res = f(10)
        """
        interp = self.run_code(code)
        self.assertEqual(interp.context.get_variable("res"), 11)

if __name__ == '__main__':
    unittest.main()
