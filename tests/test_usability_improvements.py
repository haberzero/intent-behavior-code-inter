import unittest
from tests.ibc_test_case import IBCTestCase

class TestUsabilityImprovements(IBCTestCase):
    def test_intent_interpolation(self):
        """Test variable interpolation in @ intent markers."""
        code = """
import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
str role = "Chef"
@ "You are a $role"
str res = @~ Describe yourself ~
dict last_call = ai.get_last_call_info()
"""
        self.engine.run_string(code)
        last_call = self.engine.get_variable("last_call")
        # Check if "Chef" is in the system prompt
        self.assertIn("Chef", last_call["sys_prompt"])
        self.assertIn("You are a Chef", last_call["sys_prompt"])

    def test_semantic_filter_loop(self):
        """Test for item in list if @~...~: syntax."""
        code = """
import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
list items = ["apple", "carrot", "banana"]
list fruits = []

# AI logic: return 0 if item is carrot, else 1
for item in items if @~ MOCK:RESPONSE:$item == "carrot" ? 0 : 1 ~:
    fruits.append(item)
"""
        # Since our mock doesn't actually evaluate the ternary, we need a better way.
        # Let's use multiple items and simple mocks.
        code = """
import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
list items = ["MOCK:TRUE", "MOCK:FALSE", "MOCK:TRUE"]
list results = []

for item in items if @~ Is $item true? ~:
    results.append(item)
"""
        self.engine.run_string(code)
        results = self.engine.get_variable("results")
        self.assertEqual(len(results), 2)

    def test_implicit_progress_awareness(self):
        """Test that loop metadata is injected into LLM calls."""
        code = """
import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
list items = ["a", "b"]
for item in items:
    str prompt = @~ Process $item ~
    dict last_call = ai.get_last_call_info()
    # On first iteration, index should be 0
    if item == "a":
        str sys_prompt_a = last_call["sys_prompt"]
    # On second iteration, index should be 1
    if item == "b":
        str sys_prompt_b = last_call["sys_prompt"]
"""
        self.engine.run_string(code)
        sys_prompt_a = self.engine.get_variable("sys_prompt_a")
        sys_prompt_b = self.engine.get_variable("sys_prompt_b")
        self.assertIn("当前正在处理第 1 个元素，总计 2 个", sys_prompt_a)
        self.assertIn("当前正在处理第 2 个元素，总计 2 个", sys_prompt_b)

    def test_declarative_retry(self):
        """Test llmexcept retry "hint" syntax."""
        code = """
import ai
# 1st call returns AMBIGUOUS, 2nd (after retry) returns 1
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
ai.set_global_intent("MOCK:RESPONSE:MOCK:AMBIGUOUS")

int count = 0
if @~ Is it a fruit? ~:
    count = 1
llmexcept retry "Please answer 1"

# After retry, it should eventually succeed in mock mode
"""
        self.engine.run_string(code)
        self.assertEqual(self.engine.get_variable("count"), 1)
        # We need a more complex test for retry as it involves exceptions
        # But we can at least check if it parses and doesn't crash
        self.engine.run_string(code)
        # Note: In mock mode, retry with a hint will eventually succeed 
        # because our mock executor handles the hint.
        self.assertEqual(self.engine.get_variable("count"), 1)

if __name__ == "__main__":
    unittest.main()
