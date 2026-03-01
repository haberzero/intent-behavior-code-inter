import unittest
from core.engine import IBCIEngine

class TestPromptProtocol(unittest.TestCase):
    def setUp(self):
        self.engine = IBCIEngine()
        self.engine.run_string("import ai\nai.set_config('TESTONLY', 'TESTONLY', 'TESTONLY')")

    def test_to_prompt_protocol(self):
        code = """
class User:
    str name = "Alice"
    int age = 25
    
    func __to_prompt__(self) -> str:
        return "User(Name: " + self.name + ")"

User u = User()
str res = @~ hello $u ~
"""
        self.engine.run_string(code, prepare_interpreter=False)
        last_info = self.engine.interpreter.service_context.llm_executor.last_call_info
        # The prompt should contain "User(Name: Alice)" instead of default repr
        self.assertIn("hello User(Name: Alice)", last_info["user_prompt"])
        self.assertNotIn("25", last_info["user_prompt"])

    def test_default_repr_without_protocol(self):
        code = """
class User:
    str name = "Alice"

User u = User()
str res = @~ hello $u ~
"""
        self.engine.run_string(code, prepare_interpreter=False)
        last_info = self.engine.interpreter.service_context.llm_executor.last_call_info
        # Default repr is <Instance of User>
        self.assertIn("hello <Instance of User>", last_info["user_prompt"])

if __name__ == "__main__":
    unittest.main()
