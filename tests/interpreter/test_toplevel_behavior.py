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
        print(f"DEBUG: MockAI called with sys='{sys}', user='{user}'")
        return self.response

    def get_return_type_prompt(self, type_name):
        return ""

    def set_retry_hint(self, hint):
        pass

class TestTopLevelBehavior(BaseInterpreterTest):
    def setUp(self):
        super().setUp()
        self.mock_ai = MockAI()
        self.engine.host_interface.register_module(
            "ai", 
            self.mock_ai,
            metadata=ModuleMetadata(name="ai")
        )

    def test_simple_behavior(self):
        print("\n--- Running test_simple_behavior ---")
        code = """
        str res = @~ Task ~
        print(res)
        """
        self.run_code(code)
        
        print(f"Last Sys: '{self.mock_ai.last_sys}'")
        self.assertIn("Task", self.mock_ai.last_user)

if __name__ == '__main__':
    unittest.main()
