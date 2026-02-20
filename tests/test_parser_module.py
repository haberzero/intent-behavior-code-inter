
import unittest
import sys
import os
import textwrap

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.lexer.lexer import Lexer
from utils.parser.parser import Parser
from utils.semantic.analyzer import SemanticAnalyzer
from utils.parser.symbol_table import ScopeManager, SymbolType
from utils.semantic.types import FunctionType, INT_TYPE, VOID_TYPE, ANY_TYPE
from typedef.diagnostic_types import CompilerError

class TestParserModule(unittest.TestCase):
    """
    Test module-level features:
    - Import statement symbol registration
    - Cross-module symbol resolution
    - Module cache integration
    """

    def setUp(self):
        self.scope_manager = ScopeManager()
        self.module_cache = {}

    def parse_code(self, code, module_cache=None):
        dedented_code = textwrap.dedent(code).strip() + "\n"
        lexer = Lexer(dedented_code)
        tokens = lexer.tokenize()
        parser = Parser(tokens, module_cache=module_cache)
        return parser.parse(), parser

    def test_import_registers_module_symbol(self):
        """Test that 'import m' registers 'm' as a MODULE symbol."""
        code = """
        import utils.math
        """
        mod, parser = self.parse_code(code)
        
        # Check global scope
        sym = parser.scope_manager.resolve('utils.math') 
        # Actually parser registers alias. Default alias for 'import a.b' is 'utils.math'?
        # In parse_aliases, asname is None.
        # Parser logic: sym = define(asname or module_name)
        # So it defines 'utils.math'.
        
        assert sym is not None
        if sym is None: self.fail()
        self.assertEqual(sym.type, SymbolType.MODULE)
        self.assertEqual(sym.name, 'utils.math')

    def test_import_as_registers_alias(self):
        """Test 'import m as alias'."""
        code = """
        import utils.math as m
        """
        mod, parser = self.parse_code(code)
        
        sym = parser.scope_manager.resolve('m')
        assert sym is not None
        if sym is None: self.fail()
        self.assertEqual(sym.type, SymbolType.MODULE)
        
        # Original name should NOT be defined
        self.assertIsNone(parser.scope_manager.resolve('utils.math'))

    def test_from_import_registers_symbols(self):
        """Test 'from m import a' registers 'a'."""
        code = """
        from math import sqrt
        """
        # We simulate that 'math' module has 'sqrt'
        # But even without cache, parser should register 'sqrt' as VARIABLE (fallback)
        mod, parser = self.parse_code(code)
        
        sym = parser.scope_manager.resolve('sqrt')
        assert sym is not None
        if sym is None: self.fail()
        self.assertEqual(sym.type, SymbolType.VARIABLE)

    def test_cross_module_resolution(self):
        """Test resolving symbols from imported module via cache."""
        # 1. Create a dummy scope for module 'math'
        math_scope = ScopeManager().global_scope
        sqrt_sym = math_scope.define('sqrt', SymbolType.FUNCTION)
        sqrt_sym.type_info = FunctionType([INT_TYPE], INT_TYPE)
        
        self.module_cache['math'] = math_scope
        
        # 2. Parse code that imports math
        code = """
        import math
        int x = math.sqrt(16)
        """
        # We need SemanticAnalyzer to verify type check
        mod, parser = self.parse_code(code, module_cache=self.module_cache)
        
        # Check if 'math' symbol is linked
        math_sym = parser.scope_manager.resolve('math')
        assert math_sym is not None
        if math_sym is None: self.fail()
        self.assertEqual(math_sym.exported_scope, math_scope)
        
        # 3. Analyze
        analyzer = SemanticAnalyzer()
        # Analyzer needs to use the parser's scope which is attached to mod
        analyzer.analyze(mod)
        
        # If no error, type check passed.
        # This confirms 'math.sqrt' resolved to FunctionType([int], int)

    def test_from_import_with_cache(self):
        """Test 'from m import a' uses cache to get correct symbol type."""
        # Setup 'config' module with 'VERSION' variable
        config_scope = ScopeManager().global_scope
        ver_sym = config_scope.define('VERSION', SymbolType.VARIABLE)
        ver_sym.type_info = INT_TYPE
        
        self.module_cache['config'] = config_scope
        
        code = """
        from config import VERSION
        int v = VERSION
        """
        mod, parser = self.parse_code(code, module_cache=self.module_cache)
        
        # Check symbol in current scope
        sym = parser.scope_manager.resolve('VERSION')
        assert sym is not None
        if sym is None: self.fail()
        
        # Verify type info was copied from the cached module scope
        assert sym.type_info is not None
        if sym.type_info is None: self.fail()
        self.assertEqual(sym.type_info.name, 'int')

if __name__ == '__main__':
    unittest.main()
