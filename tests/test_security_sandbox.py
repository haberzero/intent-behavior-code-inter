import unittest
import os
import shutil
from typedef.exception_types import InterpreterError
from app.engine import IBCIEngine

class TestSecuritySandbox(unittest.TestCase):
    def setUp(self):
        self.workspace = os.path.abspath("tmp_workspace")
        os.makedirs(self.workspace, exist_ok=True)
        self.outside_file = os.path.abspath("outside_workspace.txt")
        with open(self.outside_file, 'w') as f:
            f.write("sensitive data")

    def tearDown(self):
        if os.path.exists(self.workspace):
            shutil.rmtree(self.workspace)
        if os.path.exists(self.outside_file):
            os.remove(self.outside_file)

    def run_code(self, code, root_dir=None):
        if root_dir is None:
            root_dir = self.workspace
            
        engine = IBCIEngine(root_dir=root_dir)
        test_file = os.path.join(root_dir, "test_security.ibci")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(code.strip() + "\n")
            
        # 为了捕获输出或异常，我们手动准备解释器
        output = []
        def output_callback(msg):
            output.append(msg)
            
        try:
            engine._prepare_interpreter(output_callback=output_callback)
            ast_cache = engine.scheduler.compile_project(test_file)
            engine.interpreter.interpret(ast_cache[test_file])
            return output
        finally:
            if os.path.exists(test_file):
                os.remove(test_file)

    def test_path_traversal_denied(self):
        code = f"""
import file
str path = '{self.outside_file.replace('\\', '/')}'
str content = file.read(path)
"""
        with self.assertRaises(InterpreterError) as cm:
            self.run_code(code)
        self.assertIn("Security Error", str(cm.exception))
        self.assertIn("outside workspace", str(cm.exception))

    def test_path_traversal_allowed_after_request(self):
        code = f"""
import file
import sys
sys.request_external_access()
str path = '{self.outside_file.replace('\\', '/')}'
str content = file.read(path)
print(content)
"""
        output = self.run_code(code)
        self.assertEqual(output, ["sensitive data"])

    def test_internal_access_allowed(self):
        internal_file = os.path.join(self.workspace, "internal.txt")
        with open(internal_file, 'w') as f:
            f.write("safe data")
            
        code = f"""
import file
str path = '{internal_file.replace('\\', '/')}'
str content = file.read(path)
print(content)
"""
        output = self.run_code(code)
        self.assertEqual(output, ["safe data"])

if __name__ == '__main__':
    unittest.main()
