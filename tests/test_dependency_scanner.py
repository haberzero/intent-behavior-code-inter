
import unittest
import os
import tempfile
import shutil
from utils.dependency.dependency_scanner import DependencyScanner
from utils.dependency.graph import DependencyGraph
from typedef.dependency_types import CircularDependencyError, ModuleNotFoundError

class TestDependencyScanner(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.realpath(tempfile.mkdtemp())
        self.scanner = DependencyScanner(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def create_file(self, rel_path, content):
        # Normalize path separators for current OS
        rel_path = rel_path.replace('/', os.sep)
        path = os.path.join(self.test_dir, rel_path)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return path

    def test_simple_import(self):
        # A imports B
        path_b = self.create_file('B.ibci', '# Module B')
        path_a = self.create_file('A.ibci', 'import B')
        
        modules = self.scanner.scan_dependencies(path_a)
        
        self.assertIn(path_a, modules)
        self.assertIn(path_b, modules)
        
        mod_a = modules[path_a]
        self.assertEqual(len(mod_a.imports), 1)
        self.assertEqual(mod_a.imports[0].module_name, 'B')
        self.assertEqual(mod_a.imports[0].file_path, path_b)

    def test_circular_dependency(self):
        # A imports B, B imports A
        path_a = self.create_file('A.ibci', 'import B')
        path_b = self.create_file('B.ibci', 'import A')
        
        modules = self.scanner.scan_dependencies(path_a)
        graph = DependencyGraph(modules)
        
        with self.assertRaises(CircularDependencyError) as cm:
            graph.get_compilation_order()
            
        self.assertTrue("Circular dependency detected" in str(cm.exception))
        # Cycle should be A -> B -> A or similar
        self.assertTrue("A.ibci" in str(cm.exception))
        self.assertTrue("B.ibci" in str(cm.exception))

    def test_transitive_dependency(self):
        # A -> B -> C
        path_c = self.create_file('C.ibci', '# Module C')
        path_b = self.create_file('B.ibci', 'import C')
        path_a = self.create_file('A.ibci', 'import B')
        
        modules = self.scanner.scan_dependencies(path_a)
        graph = DependencyGraph(modules)
        order = graph.get_compilation_order()
        
        # Order should be [C, B, A]
        self.assertEqual(order, [path_c, path_b, path_a])

    def test_missing_module(self):
        path_a = self.create_file('A.ibci', 'import Missing')
        
        self.scanner.scan_dependencies(path_a)
        
        self.assertTrue(self.scanner.issue_tracker.has_errors())
        self.assertTrue(any("Module 'Missing' not found" in d.message for d in self.scanner.issue_tracker.diagnostics))

    def test_complex_import_patterns(self):
        # Test 'from ... import ...' and comments
        path_utils = self.create_file('utils/math.ibci', '# Math utils')
        path_main = self.create_file('main.ibci', """
        # This is a comment
        import utils.math
        from utils.math import sqrt
        """)
        
        modules = self.scanner.scan_dependencies(path_main)
        mod_main = modules[path_main]
        
        self.assertEqual(len(mod_main.imports), 2)
        self.assertEqual(mod_main.imports[0].module_name, 'utils.math')
        self.assertEqual(mod_main.imports[1].module_name, 'utils.math')
        
        # Check resolution
        self.assertEqual(mod_main.imports[0].file_path, path_utils)

    def test_self_import_cycle(self):
        # A imports A
        path_a = self.create_file('A.ibci', 'import A')
        
        modules = self.scanner.scan_dependencies(path_a)
        graph = DependencyGraph(modules)
        
        with self.assertRaises(CircularDependencyError):
            graph.get_compilation_order()

    def test_invalid_import_position(self):
        """Test that imports after non-import statements are flagged."""
        path_b = self.create_file('B.ibci', '# Module B')
        path_a = self.create_file('A.ibci', """
        import B
        
        # Some comment
        func foo() -> void:
            pass
            
        import B # Invalid import here
        """)
        
        self.scanner.scan_dependencies(path_a)
        
        self.assertTrue(self.scanner.issue_tracker.has_errors())
        # Should contain invalid position error
        self.assertTrue(any("Import statements must be at the top" in d.message for d in self.scanner.issue_tracker.diagnostics))
        
        # The first import should still be valid
        mod_a = self.scanner.modules[os.path.realpath(path_a)]
        self.assertEqual(len(mod_a.imports), 1)

if __name__ == '__main__':
    unittest.main()
