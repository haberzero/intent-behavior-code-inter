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

class TestLLMConfigFlow(unittest.TestCase):
    """
    测试全链路联动：JSON 配置读取 -> 解析 -> LLM 状态注入 -> AI 行为执行。
    """
    def setUp(self):
        self.test_dir = os.path.join(os.path.dirname(__file__), "tmp_llm_test")
        os.makedirs(self.test_dir, exist_ok=True)
        self.output = []

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

# 执行带意图的行为描述
@ 请执行一次模拟调用
str ai_res = ~~ hello ibci ~~
print(ai_res)
"""
        # 3. 执行
        lexer = Lexer(code.strip() + "\n")
        tokens = lexer.tokenize()
        issue_tracker = IssueTracker()
        parser = Parser(tokens, issue_tracker)
        try:
            module = parser.parse()
        except Exception as e:
                if hasattr(e, 'diagnostics'):
                    for d in e.diagnostics:
                        if d.location:
                            print(f"[{d.severity.name}] {d.code}: {d.message} at {d.location.line}:{d.location.column}")
                        else:
                            print(f"[{d.severity.name}] {d.code}: {d.message}")
                raise e
        
        # 传入 output_callback 以捕获 print 输出
        interpreter = Interpreter(issue_tracker, output_callback=self.capture_output)
        interpreter.interpret(module)
        
        # 4. 验证结果
        # 验证是否成功触发了 LLMHandler 内部的 TESTONLY 虚拟块
        self.assertTrue(len(self.output) > 0)
        final_res = self.output[0]
        self.assertIn("[TESTONLY MODE]", final_res)
        self.assertIn("hello ibci", final_res)
        self.assertIn("请执行一次模拟调用", final_res)

    def test_missing_config_error_handling(self):
        """验证未配置 LLM 时执行 AI 行为的报错引导逻辑"""
        code = """
import ai
# 故意不调用 ai.set_config
~~ 请帮我做些事情 ~~
"""
        lexer = Lexer(code.strip() + "\n")
        tokens = lexer.tokenize()
        issue_tracker = IssueTracker()
        parser = Parser(tokens, issue_tracker)
        module = parser.parse()
        
        interpreter = Interpreter(issue_tracker, output_callback=self.capture_output)
        
        from typedef.exception_types import InterpreterError
        with self.assertRaises(InterpreterError) as cm:
            interpreter.interpret(module)
        
        # 验证报错信息中包含引导性修复建议
        error_msg = str(cm.exception)
        self.assertIn("LLM 运行配置缺失", error_msg)
        self.assertIn("ai.set_config", error_msg)
        self.assertIn("建议修复方案", error_msg)

if __name__ == '__main__':
    unittest.main()
