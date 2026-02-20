
import unittest
import os
import sys

# Add project root to sys.path so we can import modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.scheduler import Scheduler
from typedef.parser_types import Module
from typedef.scope_types import ScopeNode

class TestScheduler(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'test_data', 'multi_file_project'))
        self.entry_file = os.path.join(self.test_dir, 'main.ibci')
        
    def test_compile_project(self):
        scheduler = Scheduler(self.test_dir)
        ast_map = scheduler.compile_project(self.entry_file)
        
        # Check if we got ASTs for both files
        self.assertIn(self.entry_file, ast_map)
        math_file = os.path.join(self.test_dir, 'utils', 'math.ibci')
        self.assertIn(math_file, ast_map)
        
        # Check if main AST is valid
        main_ast = ast_map[self.entry_file]
        self.assertIsInstance(main_ast, Module)
        self.assertIsNotNone(main_ast.scope)
        
        # Check if utils.math was imported correctly
        # We can inspect the scope of main module to see if 'utils.math' is defined
        utils_math_sym = main_ast.scope.resolve('m')
        self.assertIsNotNone(utils_math_sym)
        self.assertEqual(utils_math_sym.type.name, 'MODULE')
        
        # Check if we can resolve 'add' function inside the imported module scope
        math_scope = utils_math_sym.exported_scope
        self.assertIsNotNone(math_scope)
        add_sym = math_scope.resolve('add')
        self.assertIsNotNone(add_sym)
        self.assertEqual(add_sym.type.name, 'FUNCTION')

if __name__ == '__main__':
    unittest.main()
