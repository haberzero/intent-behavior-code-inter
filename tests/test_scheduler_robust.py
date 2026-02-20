
import unittest
import os
import sys

# Add project root to sys.path so we can import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.scheduler import Scheduler
from typedef.parser_types import Module
from typedef.scope_types import ScopeNode, SymbolType

class TestSchedulerRobust(unittest.TestCase):
    """
    Robustness and regression tests for Scheduler and Cross-Module Compilation.
    Designed to verify complex scenarios like chained imports, aliases, and type propagation.
    """
    def setUp(self):
        self.test_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'test_data', 'robust_project'))
        if not os.path.exists(self.test_dir):
            os.makedirs(self.test_dir)
            
    def _create_file(self, rel_path: str, content: str):
        full_path = os.path.join(self.test_dir, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return full_path

    def test_chained_import_types(self):
        """
        Scenario: A imports B, B imports C.
        A uses C's type via B? No, A imports B.
        A uses B's function which uses C's type.
        Verify A sees B's return type correctly.
        """
        # C: defines struct-like or just a type (simulated by var with int type for now)
        self._create_file('c.ibci', """
var C_VAL = 42
""")
        
        # B: imports C, defines function returning C_VAL
        self._create_file('b.ibci', """
import c
func get_c_val() -> int:
    return c.C_VAL
""")
        
        # A: imports B, calls get_c_val
        self._create_file('a.ibci', """
import b
var res = b.get_c_val()
""")
        
        scheduler = Scheduler(self.test_dir)
        ast_map = scheduler.compile_project(os.path.join(self.test_dir, 'a.ibci'))
        
        a_ast = ast_map[os.path.join(self.test_dir, 'a.ibci')]
        # Check type of 'res' in A
        res_sym = a_ast.scope.resolve('res')
        self.assertIsNotNone(res_sym)
        self.assertIsNotNone(res_sym.type_info)
        self.assertEqual(res_sym.type_info.name, 'int')

    def test_import_alias_type_propagation(self):
        """
        Scenario: import x as y. Verify y has correct type info.
        """
        self._create_file('utils.ibci', """
func helper() -> str:
    return "help"
""")
        self._create_file('main.ibci', """
import utils as u
var s = u.helper()
""")
        
        scheduler = Scheduler(self.test_dir)
        ast_map = scheduler.compile_project(os.path.join(self.test_dir, 'main.ibci'))
        
        main_ast = ast_map[os.path.join(self.test_dir, 'main.ibci')]
        
        # Check 'u' symbol
        u_sym = main_ast.scope.resolve('u')
        self.assertEqual(u_sym.type, SymbolType.MODULE)
        self.assertIsNotNone(u_sym.exported_scope)
        
        # Check 's' symbol type (inferred from u.helper())
        s_sym = main_ast.scope.resolve('s')
        self.assertIsNotNone(s_sym.type_info)
        self.assertEqual(s_sym.type_info.name, 'str')

    def test_from_import_alias_propagation(self):
        """
        Scenario: from m import f as g. Verify g has f's type.
        """
        self._create_file('math_pkg.ibci', """
func add(int a, int b) -> int:
    return a + b
""")
        self._create_file('calc.ibci', """
from math_pkg import add as sum_func
var result = sum_func(1, 2)
""")
        
        scheduler = Scheduler(self.test_dir)
        ast_map = scheduler.compile_project(os.path.join(self.test_dir, 'calc.ibci'))
        
        calc_ast = ast_map[os.path.join(self.test_dir, 'calc.ibci')]
        
        # Check 'sum_func'
        sum_sym = calc_ast.scope.resolve('sum_func')
        self.assertIsNotNone(sum_sym)
        self.assertIsNotNone(sum_sym.type_info, "Alias should inherit type info")
        self.assertEqual(sum_sym.type_info.name, 'function')
        
        # Check 'result' type
        res_sym = calc_ast.scope.resolve('result')
        self.assertEqual(res_sym.type_info.name, 'int')

    def test_reexport_propagation(self):
        """
        Scenario:
        mod1: defines foo
        mod2: imports foo from mod1, and re-exports it?
        (IBC-Inter currently doesn't have explicit 'export', but symbols in scope are public)
        mod3: imports foo from mod2.
        
        Verify mod3 sees foo's type.
        """
        self._create_file('mod1.ibci', """
func foo() -> bool:
    return True
""")
        
        self._create_file('mod2.ibci', """
from mod1 import foo
# foo is now in mod2's scope
""")
        
        self._create_file('mod3.ibci', """
from mod2 import foo
var check = foo()
""")
        
        scheduler = Scheduler(self.test_dir)
        ast_map = scheduler.compile_project(os.path.join(self.test_dir, 'mod3.ibci'))
        
        mod3_ast = ast_map[os.path.join(self.test_dir, 'mod3.ibci')]
        
        # Check 'foo' in mod3
        foo_sym = mod3_ast.scope.resolve('foo')
        self.assertIsNotNone(foo_sym)
        
        # This tests the 'lazy resolution chain': mod3.foo -> mod2.foo -> mod1.foo
        # SemanticAnalyzer should follow the origin_symbol chain.
        self.assertIsNotNone(foo_sym.type_info, "Re-exported symbol should preserve type info")
        self.assertEqual(foo_sym.type_info.name, 'function')
        self.assertEqual(foo_sym.type_info.return_type.name, 'bool')

if __name__ == '__main__':
    unittest.main()
