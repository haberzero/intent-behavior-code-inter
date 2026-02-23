
import unittest
import os
import sys

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.parser.resolver.resolver import ModuleResolver, ModuleResolveError
from utils.scheduler import Scheduler
from utils.diagnostics.issue_tracker import IssueTracker
from typedef.diagnostic_types import Severity

class TestSecurity(unittest.TestCase):
    def setUp(self):
        # Use a temporary directory structure for testing
        self.root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'test_data', 'security_project'))
        if not os.path.exists(self.root_dir):
            os.makedirs(self.root_dir)
            
        self.resolver = ModuleResolver(self.root_dir)
        self.scheduler = Scheduler(self.root_dir)

    def test_path_traversal_absolute(self):
        """Test preventing path traversal using absolute import simulation."""
        # This tests ModuleResolver directly
        
        context_file = os.path.join(self.root_dir, 'main.ibci')
        
        # module_name = "..outside" (level 2 relative import)
        # Attempt to go up past root
        
        with self.assertRaises(ModuleResolveError) as cm:
            self.resolver.resolve('..outside', context_file)
        
        self.assertIn("Security Error", str(cm.exception))

    def test_path_traversal_scheduler(self):
        """Test Scheduler rejects files outside root."""
        # Create a dummy file path outside root (doesn't need to exist)
        outside_dir = os.path.abspath(os.path.join(self.root_dir, '..'))
        outside_file = os.path.join(outside_dir, 'secret.ibci')
        
        # Calling compile_project with outside file should fail
        # It raises CompilerError if dependency scanning fails
        
        try:
            self.scheduler.compile_project(outside_file)
        except Exception:
            pass # Expected to fail
            
        # Check diagnostics
        errors = [d for d in self.scheduler.issue_tracker.diagnostics if "Security Error" in d.message]
        self.assertTrue(len(errors) > 0, "Expected Security Error in diagnostics")

    def test_valid_nested_file(self):
        """Test valid nested file access is allowed."""
        nested_dir = os.path.join(self.root_dir, 'pkg')
        if not os.path.exists(nested_dir):
            os.makedirs(nested_dir)
        nested_file = os.path.join(nested_dir, 'mod.ibci')
        
        # Create file so it can be read
        with open(nested_file, 'w') as f:
            f.write("var x = 1")
            
        # Should succeed without security error
        try:
            self.scheduler.compile_project(nested_file)
        except Exception:
            # Might fail due to other reasons (parsing etc), but not security
            pass
            
        security_errors = [d for d in self.scheduler.issue_tracker.diagnostics if "Security Error" in d.message]
        self.assertEqual(len(security_errors), 0, f"Unexpected security errors: {security_errors}")

if __name__ == '__main__':
    unittest.main()
