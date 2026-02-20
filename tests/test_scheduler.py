
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
        # We can inspect the scope of main module to see if 'utils' is defined
        utils_sym = main_ast.scope.resolve('utils')
        self.assertIsNotNone(utils_sym)
        self.assertEqual(utils_sym.type.name, 'MODULE')
        
        # Check if 'math' is in 'utils' scope
        self.assertIsNotNone(utils_sym.exported_scope)
        math_sym = utils_sym.exported_scope.resolve('math')
        self.assertIsNotNone(math_sym)
        
        # Check if 'add' is in 'math' scope
        math_scope = math_sym.exported_scope
        self.assertIsNotNone(math_scope)
        add_sym = math_scope.resolve('add')
        self.assertIsNotNone(add_sym)
        self.assertEqual(add_sym.type.name, 'FUNCTION')

    def test_circular_dependency(self):
        # Create circular project dynamically or use test_data
        # We already created tests/test_data/circular_project
        test_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'test_data', 'circular_project'))
        entry_file = os.path.join(test_dir, 'a.ibci')
        
        scheduler = Scheduler(test_dir)
        
        # Should raise CircularDependencyError
        # But wait, Scheduler wraps it in CompilerError or re-raises?
        # In scheduler.py:
        # except Exception as e:
        #     self.issue_tracker.report(Severity.ERROR, "DEP_CYCLE", str(e))
        #     raise e
        
        from typedef.dependency_types import CircularDependencyError
        
        with self.assertRaises(CircularDependencyError):
            scheduler.compile_project(entry_file)

    def test_missing_file(self):
        test_dir = self.test_dir
        # Non-existent entry file
        entry_file = os.path.join(test_dir, 'non_existent.ibci')
        
        scheduler = Scheduler(test_dir)
        
        # DependencyScanner reports ERROR but doesn't raise exception immediately in scan_file
        # But scan_dependencies catches it?
        # DependencyScanner.scan_file returns None if file not found and reports error.
        # scan_dependencies continues?
        # Let's check Scheduler.
        
        # Scheduler calls scan_dependencies.
        # If scan_dependencies finishes with errors in issue_tracker, Scheduler raises CompilerError.
        
        from typedef.diagnostic_types import CompilerError
        
        with self.assertRaises(CompilerError):
            scheduler.compile_project(entry_file)

if __name__ == '__main__':
    unittest.main()
