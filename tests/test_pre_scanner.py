import unittest
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.compiler.lexer.lexer import Lexer
from core.compiler.parser.core.token_stream import TokenStream
from core.compiler.parser.scanners.pre_scanner import PreScanner
from core.compiler.parser.symbol_table import ScopeManager, SymbolType
from core.support.diagnostics.issue_tracker import IssueTracker

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
        stream = TokenStream(tokens, IssueTracker())
        pre_scanner = PreScanner(stream, manager)
        pre_scanner.scan()
        
        # Check if functions are defined
        sym_func = manager.resolve("my_func")
        assert sym_func is not None
        self.assertEqual(sym_func.type, SymbolType.FUNCTION)
        
        sym_llm = manager.resolve("my_llm_func")
        assert sym_llm is not None
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
        stream = TokenStream(tokens, IssueTracker())
        pre_scanner = PreScanner(stream, manager)
        pre_scanner.scan()
        
        sym_x = manager.resolve("x")
        assert sym_x is not None
        self.assertEqual(sym_x.type, SymbolType.VARIABLE)
        
        sym_y = manager.resolve("y")
        assert sym_y is not None
        self.assertEqual(sym_y.type, SymbolType.VARIABLE)

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
        stream = TokenStream(tokens, IssueTracker())
        pre_scanner = PreScanner(stream, manager)
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
        stream = TokenStream(tokens, IssueTracker())
        pre_scanner = PreScanner(stream, manager)
        pre_scanner.scan()
        
        sym_numbers = manager.resolve("numbers")
        assert sym_numbers is not None
        self.assertEqual(sym_numbers.type, SymbolType.VARIABLE)

if __name__ == '__main__':
    unittest.main()
