
import unittest
import sys
import os
import textwrap

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.compiler.lexer.lexer import Lexer
from core.compiler.parser.parser import Parser
from core.compiler.semantic.semantic_analyzer import SemanticAnalyzer
from core.compiler.parser.symbol_table import ScopeManager, SymbolType
from core.compiler.semantic.types import FunctionType, INT_TYPE, VOID_TYPE, ANY_TYPE
from core.types.diagnostic_types import CompilerError

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
        import pkg.math
        """
        mod, parser = self.parse_code(code)
        
        # New parser logic: import pkg.math creates:
        # 1. 'pkg' (MODULE) in global scope
        # 2. 'math' (MODULE) in pkg.exported_scope
        
        pkg_sym = parser.scope_manager.resolve('pkg')
        self.assertIsNotNone(pkg_sym)
        self.assertEqual(pkg_sym.type, SymbolType.MODULE)
        
        math_sym = pkg_sym.exported_scope.resolve('math')
        self.assertIsNotNone(math_sym)
        self.assertEqual(math_sym.type, SymbolType.MODULE)

    def test_import_as_registers_alias(self):
        """Test 'import m as alias'."""
        code = """
        import pkg.math as m
        """
        mod, parser = self.parse_code(code)
        
        sym = parser.scope_manager.resolve('m')
        assert sym is not None
        if sym is None: self.fail()
        self.assertEqual(sym.type, SymbolType.MODULE)
        
        # Original name should NOT be defined
        self.assertIsNone(parser.scope_manager.resolve('pkg.math'))

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
        # 1. Create a dummy scope for module 'mock_math'
        math_scope = ScopeManager().global_scope
        sqrt_sym = math_scope.define('sqrt', SymbolType.FUNCTION)
        sqrt_sym.type_info = FunctionType([INT_TYPE], INT_TYPE)
        
        self.module_cache['mock_math'] = math_scope
        
        # 2. Parse code that imports mock_math
        code = """
        import mock_math
        int x = mock_math.sqrt(16)
        """
        # We need SemanticAnalyzer to verify type check
        mod, parser = self.parse_code(code, module_cache=self.module_cache)
        
        # Check if 'mock_math' symbol is linked
        math_sym = parser.scope_manager.resolve('mock_math')
        self.assertIsNotNone(math_sym)
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
        # Note: we need to pass module_cache to parser
        mod, parser = self.parse_code(code, module_cache=self.module_cache)
        
        # Check symbol in current scope
        sym = parser.scope_manager.resolve('VERSION')
        self.assertIsNotNone(sym)
        
        # Verify type info was copied from the cached module scope
        self.assertIsNotNone(sym.type_info)
        self.assertEqual(sym.type_info.name, 'int')

if __name__ == '__main__':
    unittest.main()
