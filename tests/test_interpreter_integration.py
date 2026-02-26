import unittest
import sys
import os
import json
import shutil

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.engine import IBCIEngine

class TestInterpreterIntegration(unittest.TestCase):
    """
    集成测试：使用标准化 IBCIEngine 验证跨文件导入和标准库功能。
    """
    def setUp(self):
        self.test_dir = os.path.join(os.path.dirname(__file__), "tmp_test_project")
        os.makedirs(self.test_dir, exist_ok=True)
        self.output = []
        self.engine = IBCIEngine(root_dir=self.test_dir)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def capture_output(self, msg):
        self.output.append(msg)

    def create_file(self, name, content):
        path = os.path.join(self.test_dir, name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return path

    def test_stdlib_json_math(self):
        path = self.create_file("test.ibci", """
import json
import math

str data = '{"key": "value", "count": 42}'
dict d = json.parse(data)
print(d["key"])

float root = math.sqrt(16.0)
print(root)
""")
        success = self.engine.run(path, output_callback=self.capture_output)
        self.assertTrue(success)
        self.assertEqual(self.output, ["value", "4.0"])

    def test_stdlib_file_time(self):
        test_file = os.path.join(self.test_dir, "hello.txt")
        # Ensure path is escaped for IBCI string
        safe_path = test_file.replace('\\', '/')
        
        path = self.create_file("test.ibci", f"""
import file
import time

str path = '{safe_path}'
file.write(path, "hello from ibci")
str content = file.read(path)
print(content)

float t1 = time.now()
time.sleep(0.1)
float t2 = time.now()
print(t2 > t1)
""")
        success = self.engine.run(path, output_callback=self.capture_output)
        self.assertTrue(success)
        self.assertEqual(self.output[0], "hello from ibci")
        self.assertEqual(self.output[1], "True")

    def test_cross_file_import_basic(self):
        """验证标准化引擎下的跨文件导入"""
        self.create_file("lib.ibci", "int x = 100")
        main_path = self.create_file("main.ibci", "import lib\nprint('imported')")
        
        success = self.engine.run(main_path, output_callback=self.capture_output)
        self.assertTrue(success)
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
        success = self.engine.run(main_path, output_callback=self.capture_output)
        self.assertTrue(success)
        self.assertEqual(self.output, ["52", "3"])

    def test_engine_register_plugin(self):
        """验证 IBCIEngine 的插件注册与运行时调用流程"""
        class MyPlugin:
            def hello(self, name):
                return f"Hello, {name}!"
            def get_val(self):
                return 123
        
        # 注册插件
        self.engine.register_plugin("ext", MyPlugin())
        
        # 运行代码使用插件
        path = self.create_file("plugin_test.ibci", """
import ext
str msg = ext.hello("World")
print(msg)
int val = ext.get_val()
print(val)
""")
        self.output = []
        success = self.engine.run(path, output_callback=self.capture_output)
        self.assertTrue(success)
        self.assertEqual(self.output, ["Hello, World!", "123"])

if __name__ == '__main__':
    unittest.main()
