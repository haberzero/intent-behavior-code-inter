import unittest
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.lexer.lexer import Lexer
from utils.parser.pre_scanner import PreScanner
from utils.parser.symbol_table import ScopeManager, SymbolType

class TestPreScanner(unittest.TestCase):
    def test_function_registration(self):
        """Test scanning function definitions."""
        code = """
func my_func(int a):
    pass
    
llm my_llm_func(str s):
    pass
"""
        lexer = Lexer(code.strip())
        tokens = lexer.tokenize()
        
        manager = ScopeManager()
        pre_scanner = PreScanner(tokens, 0, manager)
        pre_scanner.scan()
        
        # Check if functions are defined
        sym_func = manager.resolve("my_func")
        self.assertIsNotNone(sym_func)
        self.assertEqual(sym_func.type, SymbolType.FUNCTION)
        
        sym_llm = manager.resolve("my_llm_func")
        self.assertIsNotNone(sym_llm)
        self.assertEqual(sym_llm.type, SymbolType.FUNCTION)

    def test_variable_registration(self):
        """Test variable registration in global scope."""
        code = """
var x = 10
int y = 20
"""
        lexer = Lexer(code.strip())
        tokens = lexer.tokenize()
        
        manager = ScopeManager()
        pre_scanner = PreScanner(tokens, 0, manager)
        pre_scanner.scan()
        
        self.assertIsNotNone(manager.resolve("x"))
        self.assertEqual(manager.resolve("x").type, SymbolType.VARIABLE)
        
        self.assertIsNotNone(manager.resolve("y"))
        self.assertEqual(manager.resolve("y").type, SymbolType.VARIABLE)

    def test_skip_nested_blocks(self):
        """Test that PreScanner skips nested function bodies but registers top-level items."""
        code = """
func outer():
    var inner_var = 1
    func inner_func():
        pass
"""
        lexer = Lexer(code.strip())
        tokens = lexer.tokenize()
        
        manager = ScopeManager()
        pre_scanner = PreScanner(tokens, 0, manager)
        pre_scanner.scan()
        
        # 'outer' should be registered
        self.assertIsNotNone(manager.resolve("outer"))
        
        # 'inner_var' and 'inner_func' should NOT be registered in global scope
        # because PreScanner registers 'outer' and skips its body block.
        self.assertIsNone(manager.resolve("inner_var"))
        self.assertIsNone(manager.resolve("inner_func"))

    def test_generics_declaration(self):
        """Test scanning generic variable declarations."""
        code = "list[int] numbers = []"
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        
        manager = ScopeManager()
        pre_scanner = PreScanner(tokens, 0, manager)
        pre_scanner.scan()
        
        self.assertIsNotNone(manager.resolve("numbers"))
        self.assertEqual(manager.resolve("numbers").type, SymbolType.VARIABLE)

if __name__ == '__main__':
    unittest.main()
