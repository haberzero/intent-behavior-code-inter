import unittest
from core.engine import IBCIEngine
from core.types.exception_types import InterpreterError
import os

class TestEnhancedIntent(unittest.TestCase):
    def setUp(self):
        self.engine = IBCIEngine()
        # Ensure ai module is loaded and configured for test
        self.engine.run_string("import ai\nai.set_config('TESTONLY', 'TESTONLY', 'TESTONLY')")

    def test_global_intent(self):
        code = """
ai.set_global_intent("Global Style")
str res = @~ MOCK:RESPONSE:OK ~
dict info = ai.get_last_call_info()
"""
        self.engine.run_string(code, prepare_interpreter=False)
        # Check if global intent is in sys_prompt
        # The prompt synthesis logic in llm_executor adds it
        last_info = self.engine.interpreter.service_context.llm_executor.last_call_info
        self.assertIn("Global Style", last_info["sys_prompt"])

    def test_block_intent(self):
        code = """
intent "Block Style":
    str res = @~ MOCK:RESPONSE:OK ~
    dict info = ai.get_last_call_info()
"""
        self.engine.run_string(code, prepare_interpreter=False)
        last_info = self.engine.interpreter.service_context.llm_executor.last_call_info
        self.assertIn("Block Style", last_info["sys_prompt"])

    def test_call_intent_modifiers(self):
        # Test @! (Exclusive)
        code = """
ai.set_global_intent("Global Style")
@! Exclusive Intent
str res = @~ MOCK:RESPONSE:OK ~
dict info = ai.get_last_call_info()
"""
        self.engine.run_string(code, prepare_interpreter=False)
        last_info = self.engine.interpreter.service_context.llm_executor.last_call_info
        self.assertIn("Exclusive Intent", last_info["sys_prompt"])
        self.assertNotIn("Global Style", last_info["sys_prompt"])

        # Test @- (Exclusion)
        code = """
ai.set_global_intent("Global Style")
@- Global Style
str res = @~ MOCK:RESPONSE:OK ~
dict info = ai.get_last_call_info()
"""
        self.engine.run_string(code, prepare_interpreter=False)
        last_info = self.engine.interpreter.service_context.llm_executor.last_call_info
        self.assertNotIn("Global Style", last_info["sys_prompt"])

    def test_clear_global_intent(self):
        code = """
ai.set_global_intent("Global Style")
ai.clear_global_intents()
str res = @~ MOCK:RESPONSE:OK ~
dict info = ai.get_last_call_info()
"""
        self.engine.run_string(code, prepare_interpreter=False)
        last_info = self.engine.interpreter.service_context.llm_executor.last_call_info
        self.assertNotIn("Global Style", last_info["sys_prompt"])

    def test_intent_block_exclusive(self):
        code = """
ai.set_global_intent("Global Style")
intent ! "Exclusive Block":
    str res = @~ MOCK:RESPONSE:OK ~
    dict info = ai.get_last_call_info()
"""
        self.engine.run_string(code, prepare_interpreter=False)
        last_info = self.engine.interpreter.service_context.llm_executor.last_call_info
        self.assertIn("Exclusive Block", last_info["sys_prompt"])
        self.assertNotIn("Global Style", last_info["sys_prompt"])

if __name__ == "__main__":
    unittest.main()
