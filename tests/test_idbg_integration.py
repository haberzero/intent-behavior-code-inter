
import unittest
import os
import json
from core.engine import IBCIEngine

class TestIDbgIntegration(unittest.TestCase):
    def setUp(self):
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.engine = IBCIEngine(root_dir=self.root_dir)
        # 模拟 API 配置
        self.config = {
            "url": "http://mock",
            "key": "key",
            "model": "gpt-3.5-turbo"
        }

    def test_idbg_import_and_call(self):
        """测试在 ibci 代码中导入并调用 idbg"""
        code = """
import idbg
int test_val = 123
dict v = idbg.vars()
"""
        # 准备环境
        self.engine._prepare_interpreter(output_callback=None)
        for k, v in self.config.items():
            self.engine.interpreter.context.define_variable(k, v)
            
        # 运行代码
        from core.compiler.lexer.lexer import Lexer
        from core.compiler.parser.parser import Parser
        
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast_node = parser.parse()
        
        self.engine.interpreter.interpret(ast_node)
        
        # 验证变量 v 是否包含了 test_val
        v_result = self.engine.interpreter.context.get_variable("v")
        self.assertIn("test_val", v_result)
        self.assertEqual(v_result["test_val"]["value"], 123)

    def test_idbg_last_llm_integration(self):
        """测试 LLM 交互后 idbg.last_llm() 的集成表现"""
        code = """
import ai
import idbg
ai.set_config("TESTONLY", "key", "model")
str res = @~MOCK:RESPONSE:OK~
dict last = idbg.last_llm()
"""
        self.engine._prepare_interpreter(output_callback=None)
        # 注入变量以满足 ai 模块
        self.engine.interpreter.context.define_variable("url", "TESTONLY")
        self.engine.interpreter.context.define_variable("key", "key")
        self.engine.interpreter.context.define_variable("model", "model")
        
        # 运行
        from core.compiler.lexer.lexer import Lexer
        from core.compiler.parser.parser import Parser
        
        lexer = Lexer(code)
        tokens = lexer.tokenize()
        parser = Parser(tokens)
        ast_node = parser.parse()
        
        self.engine.interpreter.interpret(ast_node)
        
        # 验证 last
        last = self.engine.interpreter.context.get_variable("last")
        self.assertEqual(last["response"], "OK")

if __name__ == "__main__":
    unittest.main()
