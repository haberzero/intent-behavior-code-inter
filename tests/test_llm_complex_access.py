
import unittest
import os
import json
from core.engine import IBCIEngine
from core.support.diagnostics.issue_tracker import IssueTracker
from core.types.exception_types import InterpreterError
from core.compiler.lexer.lexer import Lexer
from core.compiler.parser.parser import Parser

class TestLLMComplexAccess(unittest.TestCase):
    def setUp(self):
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.engine = IBCIEngine(root_dir=self.root_dir)
        self.variables = {
            "url": "http://mock-api.com",
            "key": "mock-key",
            "model": "mock-model"
        }

    def test_behavior_expr_complex_access(self):
        """测试行为描述行中的复杂访问：$items[0], $obj.attr[0]"""
        code = """
import ai
ai.set_config(url, key, model)

list items = ["apple", "banana"]
dict data = {"fruits": ["orange", "grape"], "info": {"id": 1}}

# 模拟 LLM 返回
# 我们通过 mock ai.set_config 的底层调用来验证插值结果
# 但这里我们直接运行，观察是否报错即可，验证解析和求值链路
str res1 = @~第一个水果是 $items[0]~
str res2 = @~第二个数据水果是 $data.fruits[1]~
str res3 = @~信息 ID 是 $data.info.id~
"""
        # 为了验证插值结果，我们需要捕获 LLM 调用
        captured_prompts = []
        def mock_llm_callback(sys_prompt, user_prompt, **kwargs):
            captured_prompts.append((sys_prompt, user_prompt))
            return "1"

        self.engine._prepare_interpreter(output_callback=None)
        self.engine.interpreter.llm_executor.llm_callback = mock_llm_callback
        
        # 注入变量
        for k, v in self.variables.items():
            self.engine.interpreter.context.define_variable(k, v)
            
        # 编译并运行
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast_node = parser.parse()
        
        self.engine.interpreter.interpret(ast_node)
        
        # 验证插值后的 user_prompt
        self.assertEqual(captured_prompts[0][1], "第一个水果是 apple")
        self.assertEqual(captured_prompts[1][1], "第二个数据水果是 grape")
        self.assertEqual(captured_prompts[2][1], "信息 ID 是 1")

    def test_llm_func_complex_access(self):
        """测试 LLM 函数中的复杂访问：$__param.attr__, $__param[0]__"""
        code = """
import ai
ai.set_config(url, key, model)

llm test_func(dict obj, list arr):
__sys__
System info: $__obj.info.name__
__user__
User info: $__arr[1]__
llmend

dict my_obj = {"info": {"name": "Alice"}}
list my_arr = ["ignore", "Bob"]
test_func(my_obj, my_arr)
"""
        captured_prompts = []
        def mock_llm_callback(sys_prompt, user_prompt, **kwargs):
            captured_prompts.append((sys_prompt, user_prompt))
            return "OK"

        self.engine._prepare_interpreter(output_callback=None)
        self.engine.interpreter.llm_executor.llm_callback = mock_llm_callback
        
        for k, v in self.variables.items():
            self.engine.interpreter.context.define_variable(k, v)
            
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast_node = parser.parse()
        
        self.engine.interpreter.interpret(ast_node)
        
        # 验证插值结果
        self.assertIn("System info: Alice", captured_prompts[0][0])
        self.assertIn("User info: Bob", captured_prompts[0][1])

if __name__ == "__main__":
    unittest.main()
