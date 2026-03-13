import unittest
from tests.interpreter.base import BaseInterpreterTest
from core.domain.types import ModuleMetadata

class MockAI:
    def __init__(self):
        self.last_sys = ""
        self.last_user = ""
        self.response = "mock_response"

    def setup(self, capabilities):
        capabilities.llm_provider = self

    def __call__(self, sys, user, scene="general"):
        self.last_sys = sys
        self.last_user = user
        return self.response

    def get_return_type_prompt(self, type_name):
        return ""

    def set_retry_hint(self, hint):
        pass

class TestIntentSystem(BaseInterpreterTest):
    """
    专门测试意图系统 (Intent System) 的高级特性。
    覆盖：叠加 (@+), 排他 (@!), 删除 (@-), 以及 IbIntent 对象行为。
    """
    def setUp(self):
        super().setUp()
        self.mock_ai = MockAI()
        self.engine.host_interface.register_module(
            "ai", 
            self.mock_ai,
            metadata=ModuleMetadata(name="ai")
        )

    def test_intent_stacking_default(self):
        """测试默认意图叠加顺序"""
        code = """
        intent "Global Intent":
            intent "Block Intent":
                @ Line Intent
                str res = @~ Task ~
                print(res)
        """
        self.run_code(code)
        
        # 验证顺序：通常是 Global -> Block -> Line
        sys_prompt = self.mock_ai.last_sys
        self.assertIn("Global Intent", sys_prompt)
        self.assertIn("Block Intent", sys_prompt)
        self.assertIn("Line Intent", sys_prompt)
        
        # 验证它们同时存在
        self.assertTrue(sys_prompt.find("Global Intent") < sys_prompt.find("Block Intent"))
        self.assertTrue(sys_prompt.find("Block Intent") < sys_prompt.find("Line Intent"))

    def test_intent_override(self):
        """测试排他模式 (@!)"""
        code = """
        intent "Global Intent":
            intent "Block Intent":
                # @! 应该屏蔽掉 Global 和 Block Intent
                intent ! "Override Intent":
                    str res = @~ Task ~
                    print(res)
        """
        self.run_code(code)
        
        sys_prompt = self.mock_ai.last_sys
        self.assertIn("Override Intent", sys_prompt)
        # 核心验证：被屏蔽的意图不应出现
        self.assertNotIn("Global Intent", sys_prompt)
        self.assertNotIn("Block Intent", sys_prompt)

    def test_intent_block_override(self):
        """测试块级排他模式 (intent ! ...)"""
        code = """
        intent "Global Intent":
            # 块级排他：进入此块时，外部意图被屏蔽
            intent ! "Override Block":
                @ Line Intent
                str res = @~ Task ~
                print(res)
        """
        self.run_code(code)
        
        sys_prompt = self.mock_ai.last_sys
        self.assertIn("Override Block", sys_prompt)
        self.assertIn("Line Intent", sys_prompt)
        self.assertNotIn("Global Intent", sys_prompt)

    def test_intent_remove(self):
        """测试删除模式 (@-)"""
        code = """
        intent "Global Intent":
            intent "Block Intent":
                # 删除特定的意图 (使用 shorthand 语法)
                @- Global Intent
                str res = @~ Task ~
                print(res)
        """
        self.run_code(code)
        
        sys_prompt = self.mock_ai.last_sys
        self.assertIn("Block Intent", sys_prompt)
        self.assertNotIn("Global Intent", sys_prompt)

    def test_intent_restoration(self):
        """测试意图栈的自动恢复"""
        code = """
        intent "Global Intent":
            intent ! "Override Block":
                str res1 = @~ Task 1 ~
                print(res1)
            
            # 退出排他块后，Global Intent 应该恢复
            str res2 = @~ Task 2 ~
            print(res2)
        """
        self.run_code(code)
        
        # Task 2 应该包含 Global Intent
        sys_prompt = self.mock_ai.last_sys
        self.assertIn("Global Intent", sys_prompt)

if __name__ == '__main__':
    unittest.main()
