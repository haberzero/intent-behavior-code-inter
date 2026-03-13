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

class TestNestedIntent(BaseInterpreterTest):
    def setUp(self):
        super().setUp()
        self.mock_ai = MockAI()
        self.engine.host_interface.register_module(
            "ai", 
            self.mock_ai,
            metadata=ModuleMetadata(name="ai")
        )

    def test_nested_intent(self):
        code = """
        print("Start")
        intent "Level 1":
            print("Enter Level 1")
            intent "Level 2":
                print("Enter Level 2")
                str res = @~ Task ~
                print("Exit Level 2")
            print("Exit Level 1")
        print("End")
        """
        self.run_code(code)
        
        self.assertIn("Level 1", self.mock_ai.last_sys)
        self.assertIn("Level 2", self.mock_ai.last_sys)

if __name__ == '__main__':
    unittest.main()
