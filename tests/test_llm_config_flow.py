import unittest
import sys
import os
import json

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.support.diagnostics.issue_tracker import IssueTracker
from core.engine import IBCIEngine

class TestLLMConfigFlow(unittest.TestCase):
    """
    测试全链路联动：JSON 配置读取 -> 解析 -> LLM 状态注入 -> AI 行为执行。
    """
    def setUp(self):
        self.test_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "tmp_llm_test"))
        os.makedirs(self.test_dir, exist_ok=True)
        self.output = []
        self.engine = IBCIEngine(root_dir=self.test_dir)

    def tearDown(self):
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def capture_output(self, msg):
        self.output.append(msg)

    def test_json_config_to_llm_flow(self):
        # 1. 准备 JSON 配置文件 (使用 TESTONLY 魔法字段)
        config_path = os.path.join(self.test_dir, "api_config.json")
        config_data = {
            "url": "TESTONLY",
            "key": "TESTONLY",
            "model": "TESTONLY"
        }
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f)

        # 2. 编写 IBCI 编排代码
        code = f"""
import file
import json
import ai

# 读取并解析配置
str path = '{config_path.replace('\\', '/')}'
str raw = file.read(path)
dict cfg = json.parse(raw)

# 动态注入 LLM 配置
ai.set_config(cfg["url"], cfg["key"], cfg["model"])

# 执行带意图的 LLM 函数
llm mock_call():
__sys__
你是一个模拟器
__user__
hello ibci
llmend

@ 请执行一次模拟调用
str ai_res = mock_call()
print(ai_res)
"""
        # 3. 执行
        test_file = os.path.join(self.test_dir, "test.ibci")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(code.strip())
            
        success = self.engine.run(test_file, output_callback=self.capture_output)
        self.assertTrue(success)
        
        # 4. 验证结果
        self.assertTrue(len(self.output) > 0)
        final_res = self.output[0]
        self.assertIn("[MOCK]", final_res)
        self.assertIn("hello ibci", final_res)
        self.assertIn("请执行一次模拟调用", final_res)

    def test_missing_config_error_handling(self):
        """验证未配置 LLM 时执行 AI 行为的报错引导逻辑"""
        code = """
import ai
# 故意不调用 ai.set_config
@~ 请帮我做些事情 ~
"""
        test_file = os.path.join(self.test_dir, "error_test.ibci")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write(code.strip())
            
        # 这里预期运行失败，且抛出特定的 InterpreterError
        from core.types.exception_types import InterpreterError
        # 由于 engine.run 内部捕获了异常并打印，我们需要验证其返回值或直接测试 interpreter
        # 为了精确测试报错内容，我们手动准备解释器
        self.engine._prepare_interpreter(output_callback=self.capture_output)
        
        ast_cache = self.engine.scheduler.compile_project(test_file)
        entry_ast = ast_cache[test_file]
        
        with self.assertRaises(InterpreterError) as cm:
            self.engine.interpreter.interpret(entry_ast)
        
        # 验证报错信息中包含引导性修复建议
        error_msg = str(cm.exception)
        self.assertIn("LLM 运行配置缺失", error_msg)
        self.assertIn("ai.set_config", error_msg)
        self.assertIn("建议修复方案", error_msg)

if __name__ == '__main__':
    unittest.main()
