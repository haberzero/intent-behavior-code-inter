import unittest
import sys
import os
import json

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.engine import IBCIEngine

class TestLLMReturnTypes(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "tmp_llm_types_test"))
        os.makedirs(self.test_dir, exist_ok=True)
        self.output = []
        self.engine = IBCIEngine(root_dir=self.test_dir)

    def tearDown(self):
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def capture_output(self, msg):
        self.output.append(msg)

    def run_ibci(self, code):
        test_file = os.path.join(self.test_dir, "test.ibci")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(code.strip())
        return self.engine.run(test_file, output_callback=self.capture_output)

    def test_llm_return_int(self):
        code = """
import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")

llm get_score() -> int:
__sys__
__user__
MOCK:RESPONSE: 42
llmend

int score = get_score()
print(score + 8)
"""
        success = self.run_ibci(code)
        self.assertTrue(success)
        self.assertIn("50", self.output)

    def test_llm_return_float(self):
        code = """
import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")

llm get_pi() -> float:
__sys__
__user__
MOCK:RESPONSE: 3.14159
llmend

float pi = get_pi()
print(pi * 2)
"""
        success = self.run_ibci(code)
        self.assertTrue(success)
        # 3.14159 * 2 = 6.28318
        self.assertTrue(any("6.28318" in str(o) for o in self.output))

    def test_llm_return_list(self):
        code = """
import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")

llm get_items() -> list:
__sys__
__user__
MOCK:RESPONSE: ["apple", "banana", "cherry"]
llmend

list items = get_items()
print(items[1])
"""
        success = self.run_ibci(code)
        self.assertTrue(success)
        self.assertIn("banana", self.output)

    def test_llm_return_dict(self):
        code = """
import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")

llm get_user() -> dict:
__sys__
__user__
MOCK:RESPONSE: {"name": "Alice", "age": 30}
llmend

dict user = get_user()
print(user.name)
print(user.age + 5)
"""
        success = self.run_ibci(code)
        self.assertTrue(success)
        self.assertIn("Alice", self.output)
        self.assertIn("35", self.output)

    def test_llm_return_markdown_json(self):
        # 模拟 LLM 经常返回的带有 Markdown 标记的 JSON
        code = """
import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")

llm get_data() -> dict:
__sys__
__user__
MOCK:RESPONSE: ```json
{"status": "ok", "code": 200}
```
llmend

dict data = get_data()
print(data.status)
"""
        success = self.run_ibci(code)
        self.assertTrue(success)
        self.assertIn("ok", self.output)

    def test_custom_type_prompt(self):
        # 测试自定义提示词是否注入
        # 实际上很难直接在 MOCK 模式下验证注入了什么，但我们可以验证 set_return_type_prompt 能工作
        code = """
import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
ai.set_return_type_prompt("int", "PLEASE RETURN INTEGER ONLY!!!")
str p = ai.get_return_type_prompt("int")
print(p)
"""
        success = self.run_ibci(code)
        self.assertTrue(success)
        self.assertIn("PLEASE RETURN INTEGER ONLY!!!", self.output)

if __name__ == '__main__':
    unittest.main()
