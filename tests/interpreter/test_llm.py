import unittest
from tests.interpreter.base import BaseInterpreterTest
from core.domain.types import ModuleMetadata, FunctionMetadata, STR_DESCRIPTOR

class MockAI:
    """模拟 AI 模块用于测试 LLM 相关功能"""
    def __init__(self):
        self.last_sys = ""
        self.last_user = ""
        self.response = "42"

    def setup(self, capabilities):
        # 核心：将自己注册为内核的 LLM Provider
        capabilities.llm_provider = self

    def __call__(self, sys, user, scene="general"):
        self.last_sys = sys
        self.last_user = user
        return self.response

    def get_last_call_info(self):
        return {"sys": self.last_sys, "user": self.last_user}

    def get_return_type_prompt(self, type_name):
        return f"Return a {type_name}"

    def set_retry_hint(self, hint):
        pass

class TestLLM(BaseInterpreterTest):
    """
    测试解释器的 LLM 交互与意图系统。
    """
    def setUp(self):
        super().setUp()
        # 注册模拟 AI 模块 (ModuleLoader 会自动发现并同步到内核 llm_executor)
        self.mock_ai = MockAI()
        self.engine.host_interface.register_module(
            "ai", 
            self.mock_ai,
            metadata=ModuleMetadata(name="ai")
        )

    def test_llm_block_and_call(self):
        """测试 LLM 块定义及调用过程中的提示词构建"""
        code = """
        llm ask_llm(str question) -> int:
            __sys__
                You are a helpful assistant.
            __user__
                The question is: $__question__
            llmend
            
        print(ask_llm("What is the answer?"))
        """
        self.run_code(code)
        
        # 校验输出
        self.assert_output("42")
        
        # 校验提示词构建 (通过 mock_ai 反查)
        self.assertIn("You are a helpful assistant.", self.mock_ai.last_sys)
        self.assertIn("The question is: What is the answer?", self.mock_ai.last_user)

    def test_intent_injection(self):
        """测试意图注入逻辑"""
        code = """
        intent "Always be concise.":
            llm simple_ask() -> str:
                __sys__
                    System prompt
                __user__
                    User prompt
                llmend
            
            simple_ask()
        """
        self.run_code(code)
        
        # 校验全局意图是否被注入到系统提示词
        self.assertIn("Always be concise.", self.mock_ai.last_sys)

    def test_behavior_expression(self):
        """测试行为表达式 (Behavior Expression) 的求值"""
        code = """
        var x = 10
        llm check_behavior() -> str:
            __sys__
                Value is $__x + 5__
            __user__
                Ping
            llmend
            
        check_behavior()
        """
        self.run_code(code)
        
        # 行为表达式 $__x + 5__ 应该被求值为 15 并插入提示词
        self.assertIn("Value is 15", self.mock_ai.last_sys)

if __name__ == '__main__':
    unittest.main()
