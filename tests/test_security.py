
import unittest
import os
import sys
from unittest.mock import MagicMock

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.dependency.resolver import ModuleResolver, ModuleResolveError
from utils.dependency.dependency_scanner import DependencyScanner
from utils.diagnostics.issue_tracker import IssueTracker

class TestSecurity(unittest.TestCase):
    def setUp(self):
        # Use a temporary directory structure for testing
        self.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'test_data', 'security_project'))
        if not os.path.exists(self.root_dir):
            os.makedirs(self.root_dir)
            
        self.resolver = ModuleResolver(self.root_dir)
        self.scanner = DependencyScanner(self.root_dir, IssueTracker())

    def test_path_traversal_absolute(self):
        """Test preventing path traversal using absolute import simulation."""
        # Try to resolve a module that would map to outside root
        # e.g. "..\outside" -> invalid in module name usually, but if resolver allows ".."
        # Our resolver splits by ".", so ".." becomes empty string if not careful?
        # ModuleResolver handles leading dots for relative.
        
        # Test 1: Relative import attempting to go up too far
        context_file = os.path.join(self.root_dir, 'main.ibci')
        
        # module_name = "..outside" (level 2)
        # base_dir = parent of main.ibci (root_dir) -> parent of root_dir
        # Should raise ModuleResolveError
        
        with self.assertRaises(ModuleResolveError) as cm:
            self.resolver.resolve('..outside', context_file)
        
        self.assertIn("Security Error", str(cm.exception))

    def test_path_traversal_scanner(self):
        """Test DependencyScanner rejects files outside root."""
        # Create a dummy file outside root
        outside_dir = os.path.abspath(os.path.join(self.root_dir, '..'))
        outside_file = os.path.join(outside_dir, 'secret.ibci')
        
        # We don't actually need the file to exist for the security check to fail first
        # But scan_file checks security before existence
        
        result = self.scanner.scan_file(outside_file)
        self.assertIsNone(result)
        
        # Check diagnostics
        errors = [d for d in self.scanner.issue_tracker.diagnostics if "Security Error" in d.message]
        self.assertTrue(len(errors) > 0)

    def test_valid_nested_file(self):
        """Test valid nested file access is allowed."""
        nested_dir = os.path.join(self.root_dir, 'pkg')
        if not os.path.exists(nested_dir):
            os.makedirs(nested_dir)
        nested_file = os.path.join(nested_dir, 'mod.ibci')
        
        # Create file so scan_file succeeds reading
        with open(nested_file, 'w') as f:
            f.write("var x = 1")
            
        result = self.scanner.scan_file(nested_file)
        self.assertIsNotNone(result)
        self.assertEqual(result.file_path, nested_file)

if __name__ == '__main__':
    unittest.main()
