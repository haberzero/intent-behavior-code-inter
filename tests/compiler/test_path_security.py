import unittest
import os
import tempfile
import shutil
from core.engine import IBCIEngine
from core.domain.issue import CompilerError

class TestPathSecurity(unittest.TestCase):
    def setUp(self):
        self.test_root = os.path.abspath("test_root_security")
        if os.path.exists(self.test_root):
            shutil.rmtree(self.test_root)
        os.makedirs(self.test_root)
        self.engine = IBCIEngine(root_dir=self.test_root)

    def tearDown(self):
        if os.path.exists(self.test_root):
            shutil.rmtree(self.test_root)

    def test_run_string_allowed(self):
        """
        run_string uses a temp file outside the root.
        It should be explicitly allowed and work.
        """
        code = "int a = 10"
        # run_string internally calls allow_file on its temp file
        success = self.engine.run_string(code, prepare_interpreter=False)
        self.assertTrue(success)

    def test_outside_root_denied(self):
        """
        Trying to run a file outside the root without allow_file should fail.
        """
        with tempfile.NamedTemporaryFile(suffix=".ibci", delete=False) as f:
            f.write(b"int a = 10")
            temp_path = f.name
        
        try:
            # Should fail because it's outside self.test_root
            success = self.engine.run(temp_path, prepare_interpreter=False)
            self.assertFalse(success)
        except CompilerError:
            # Expected
            pass
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_outside_root_allowed(self):
        """
        Explicitly allowing a file outside the root should work.
        """
        with tempfile.NamedTemporaryFile(suffix=".ibci", delete=False) as f:
            f.write(b"int a = 10")
            temp_path = f.name
        
        try:
            # Manually allow it
            self.engine.scheduler.allow_file(temp_path)
            success = self.engine.run(temp_path, prepare_interpreter=False)
            self.assertTrue(success)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

if __name__ == "__main__":
    unittest.main()
