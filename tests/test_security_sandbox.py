import unittest
import os
import shutil
from utils.lexer.lexer import Lexer
from utils.parser.parser import Parser
from utils.interpreter.interpreter import Interpreter
from utils.diagnostics.issue_tracker import IssueTracker
from typedef.exception_types import InterpreterError

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
            
        lexer = Lexer(code.strip() + "\n")
        tokens = lexer.tokenize()
        issue_tracker = IssueTracker()
        parser = Parser(tokens, issue_tracker)
        module = parser.parse()
        
        # We need a scheduler or just pass root_dir to Interpreter if we want to customize it
        # Actually our current Interpreter derives root_dir from scheduler or defaults to "."
        # For testing, let's create a mock scheduler or just rely on the default and change CWD?
        # Better to update Interpreter to accept root_dir or pass a mock scheduler.
        
        class MockScheduler:
            def __init__(self, rd): self.root_dir = rd
            
        interpreter = Interpreter(issue_tracker, scheduler=MockScheduler(root_dir))
        return interpreter.interpret(module)

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
        # We need to capture output to verify
        lexer = Lexer(code.strip() + "\n")
        tokens = lexer.tokenize()
        issue_tracker = IssueTracker()
        parser = Parser(tokens, issue_tracker)
        module = parser.parse()
        
        output = []
        class MockScheduler:
            def __init__(self, rd): self.root_dir = rd
            
        interpreter = Interpreter(issue_tracker, scheduler=MockScheduler(self.workspace), 
                                  output_callback=lambda m: output.append(m))
        interpreter.interpret(module)
        
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
        output = []
        lexer = Lexer(code.strip() + "\n")
        tokens = lexer.tokenize()
        issue_tracker = IssueTracker()
        parser = Parser(tokens, issue_tracker)
        module = parser.parse()
        
        class MockScheduler:
            def __init__(self, rd): self.root_dir = rd
            
        interpreter = Interpreter(issue_tracker, scheduler=MockScheduler(self.workspace), 
                                  output_callback=lambda m: output.append(m))
        interpreter.interpret(module)
        self.assertEqual(output, ["safe data"])

if __name__ == '__main__':
    unittest.main()
