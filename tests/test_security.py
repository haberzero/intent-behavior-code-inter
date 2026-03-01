import unittest
import os
import shutil
import sys
import textwrap

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.engine import IBCIEngine
from core.types.exception_types import InterpreterError
from core.compiler.parser.resolver.resolver import ModuleResolver, ModuleResolveError
from core.scheduler import Scheduler
from core.support.diagnostics.issue_tracker import IssueTracker

class TestSecurity(unittest.TestCase):
    """
    Consolidated tests for Security and Sandboxing.
    Covers path traversal prevention, workspace isolation, and restricted access.
    """

    def setUp(self):
        self.workspace = os.path.abspath("tmp_security_workspace")
        os.makedirs(self.workspace, exist_ok=True)
        
        self.outside_file = os.path.abspath("outside_workspace.txt")
        with open(self.outside_file, 'w') as f:
            f.write("sensitive data")
            
        self.engine = IBCIEngine(root_dir=self.workspace)

    def tearDown(self):
        if os.path.exists(self.workspace):
            shutil.rmtree(self.workspace)
        if os.path.exists(self.outside_file):
            os.remove(self.outside_file)

    def run_code(self, code):
        test_file = os.path.join(self.workspace, "test.ibci")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(code).strip() + "\n")
            
        output = []
        def output_callback(msg):
            output.append(msg)
            
        self.engine._prepare_interpreter(output_callback=output_callback)
        ast_cache = self.engine.scheduler.compile_project(test_file)
        self.engine.interpreter.interpret(ast_cache[test_file])
        return output

    # --- Static Analysis Security (Resolver/Scheduler) ---

    def test_resolver_path_traversal(self):
        """测试 ModuleResolver 拒绝向上越级访问根目录以外的路径"""
        resolver = ModuleResolver(self.workspace)
        context_file = os.path.join(self.workspace, 'main.ibci')
        
        # Attempt to go up past root via relative import
        with self.assertRaises(ModuleResolveError) as cm:
            resolver.resolve('..outside', context_file)
        self.assertIn("Security Error", str(cm.exception))

    def test_scheduler_root_enforcement(self):
        """测试 Scheduler 拒绝编译根目录以外的文件"""
        scheduler = Scheduler(self.workspace)
        outside_file = os.path.join(os.path.dirname(self.workspace), 'secret.ibci')
        
        with self.assertRaises(Exception):
            scheduler.compile_project(outside_file)
            
        errors = [d for d in scheduler.issue_tracker.diagnostics if "Security Error" in d.message]
        self.assertTrue(len(errors) > 0)

    # --- Runtime Sandbox Security ---

    def test_runtime_file_access_denied(self):
        """测试运行时文件模块拒绝访问工作区以外的文件"""
        code = f"""
        import file
        str path = '{self.outside_file.replace('\\', '/')}'
        str content = file.read(path)
        """
        with self.assertRaises(InterpreterError) as cm:
            self.run_code(code)
        self.assertIn("Security Error", str(cm.exception))
        self.assertIn("outside workspace", str(cm.exception))

    def test_runtime_request_external_access(self):
        """测试通过显式请求获取外部访问权限"""
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
        """测试工作区内部文件的正常访问"""
        internal_path = os.path.join(self.workspace, "safe.txt")
        with open(internal_path, 'w') as f:
            f.write("safe data")
            
        code = f"""
        import file
        str path = '{internal_path.replace('\\', '/')}'
        print(file.read(path))
        """
        output = self.run_code(code)
        self.assertEqual(output, ["safe data"])

if __name__ == '__main__':
    unittest.main()
