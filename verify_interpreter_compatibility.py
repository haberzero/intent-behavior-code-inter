import sys
import os
import unittest

# Add project root to path
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from utils.lexer.lexer_v2 import LexerV2
from utils.parser.parser_v2 import ParserV2
from utils.interpreter.interpreter import Interpreter
from typedef import parser_types as ast

class TestInterpreterCompatibility(unittest.TestCase):
    """
    Verifies that the existing Interpreter works correctly with ASTs produced by Parser V2.
    """
    
    def run_code(self, code):
        print(f"\n--- Running Code ---\n{code.strip()}")
        lexer = LexerV2(code.strip() + "\n")
        tokens = lexer.tokenize()
        
        parser = ParserV2(tokens)
        module = parser.parse()
        
        if parser.errors:
            for err in parser.errors:
                print(f"[Parser Error] {err}")
            raise Exception("Parser errors occurred")
            
        interpreter = Interpreter()
        return interpreter.interpret(module), interpreter

    def test_basic_flow(self):
        code = """
int x = 10
int y = 20
int z = x + y
"""
        _, interp = self.run_code(code)
        self.assertEqual(interp.global_scope.get("z"), 30)
        print("Basic flow: OK")

    def test_generic_type_annotation(self):
        """
        Parser V2 produces Subscript nodes for generics.
        Interpreter needs to handle them in type checks.
        """
        code = """
func process(List[int] data) -> int:
    return len(data)

list l = [1, 2, 3]
int res = process(l)
"""
        _, interp = self.run_code(code)
        self.assertEqual(interp.global_scope.get("res"), 3)
        print("Generic type annotation: OK")

    def test_custom_type_declaration(self):
        """
        Parser V2 allows 'UserType x = ...'.
        Interpreter should handle this if 'UserType' is defined/mocked.
        Since we don't have class definitions yet, we can't fully test this 
        without mocking a type in the interpreter's scope first.
        But we can test that it doesn't crash if we treat it as 'var' or fail gracefully.
        Actually, Interpreter.visit_Assign calls _check_type_compatibility.
        If 'UserType' is not found, it raises InterpreterError.
        """
        # We'll skip runtime execution of unknown types for now, 
        # or we can manually inject a type.
        pass

    def test_constructor_call(self):
        """
        Parser V2 parses 'int(x)' as a Call.
        Interpreter needs to handle 'int' as a function/class.
        Existing interpreter has 'int' as a registered type (class).
        visit_Call handles callable objects. 'int' class is callable.
        """
        code = """
str s = "123"
int i = int(s)
"""
        # Note: 'int(s)' is a Call.
        # Interpreter.visit_Call -> visit(node.func) -> visit_Name('int') -> returns int class.
        # callable(int) is True.
        # int("123") returns 123.
        _, interp = self.run_code(code)
        self.assertEqual(interp.global_scope.get("i"), 123)
        print("Constructor call int(s): OK")

if __name__ == '__main__':
    unittest.main()
