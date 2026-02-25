import unittest
import sys
import os
import json

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.lexer.lexer import Lexer
from utils.parser.parser import Parser
from utils.interpreter.interpreter import Interpreter
from utils.diagnostics.issue_tracker import IssueTracker
from utils.scheduler import Scheduler
from typedef.diagnostic_types import CompilerError

class TestInterpreterIntegration(unittest.TestCase):
    """
    集成测试：验证跨文件导入和标准库功能。
    """
    def setUp(self):
        self.test_dir = os.path.join(os.path.dirname(__file__), "tmp_test_project")
        os.makedirs(self.test_dir, exist_ok=True)
        self.output = []

    def tearDown(self):
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def capture_output(self, msg):
        self.output.append(msg)

    def create_file(self, name, content):
        path = os.path.join(self.test_dir, name)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return path

    def test_stdlib_json_math(self):
        code = """
import json
import math

str data = '{"key": "value", "count": 42}'
dict d = json.parse(data)
print(d["key"])

float root = math.sqrt(16.0)
print(root)
"""
        lexer = Lexer(code.strip() + "\n")
        tokens = lexer.tokenize()
        issue_tracker = IssueTracker()
        parser = Parser(tokens, issue_tracker)
        module = parser.parse()
        
        interpreter = Interpreter(issue_tracker, output_callback=self.capture_output)
        interpreter.interpret(module)
        
        self.assertEqual(self.output, ["value", "4.0"])

    def test_stdlib_file_time(self):
        test_file = os.path.join(self.test_dir, "hello.txt")
        code = f"""
import file
import time

str path = '{test_file.replace('\\', '/')}'
file.write(path, "hello from ibci")
str content = file.read(path)
print(content)

float t1 = time.now()
time.sleep(0.1)
float t2 = time.now()
print(t2 > t1)
"""
        lexer = Lexer(code.strip() + "\n")
        tokens = lexer.tokenize()
        issue_tracker = IssueTracker()
        parser = Parser(tokens, issue_tracker)
        module = parser.parse()
        
        interpreter = Interpreter(issue_tracker, output_callback=self.capture_output)
        interpreter.interpret(module)
        
        self.assertEqual(self.output[0], "hello from ibci")
        self.assertEqual(self.output[1], "True")

    def test_cross_file_import_basic(self):
        """验证 Scheduler 联动下的跨文件导入（目前仅验证 AST 获取）"""
        # 创建两个文件
        lib_path = self.create_file("lib.ibci", "int x = 100")
        main_path = self.create_file("main.ibci", "import lib\nprint('imported')")
        
        # 使用 Scheduler 编译
        scheduler = Scheduler(self.test_dir)
        ast_cache = scheduler.compile_project(main_path)
        
        # 使用 Interpreter 执行 main
        interpreter = Interpreter(scheduler.issue_tracker, output_callback=self.capture_output, scheduler=scheduler)
        interpreter.interpret(ast_cache[main_path])
        
        self.assertIn("imported", self.output)

    def test_cross_file_import_from(self):
        """验证 from ... import ... 的运行时逻辑"""
        self.create_file("math_lib.ibci", """
func add(int a, int b) -> int:
    return a + b

int constant = 42
""")
        main_path = self.create_file("main.ibci", """
from math_lib import add, constant
from math_lib import *

int res = add(10, constant)
print(res)
int res2 = add(1, 2)
print(res2)
""")
        
        scheduler = Scheduler(self.test_dir)
        ast_cache = scheduler.compile_project(main_path)
        
        interpreter = Interpreter(scheduler.issue_tracker, output_callback=self.capture_output, scheduler=scheduler)
        interpreter.interpret(ast_cache[main_path])
        
        self.assertEqual(self.output, ["52", "3"])

if __name__ == '__main__':
    unittest.main()
