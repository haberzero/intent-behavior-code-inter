"""
tests/e2e/test_callable_unification.py — ordinary and LLM functions as unified callable values.

This is the first user-visible step toward unifying normal functions and
LLM functions: both are callable values and both render through the same
PromptRenderer with distinct, readable descriptions.
"""

from tests.conftest import run_ibci


class TestCallableUnification:
    def test_normal_and_llm_functions_render_distinctly(self):
        code = """
func f() -> int:
    return 1

llm g() -> str:
__sys__
You are helpful.
__user__
Say hi.
llmend

print(f)
print(g)
"""
        lines = run_ibci(code)
        assert lines == ["<Function 'f'>", "<LLMFunction 'g'>"]

    def test_normal_function_still_callable(self):
        code = """
func f() -> int:
    return 42

print(f())
"""
        assert run_ibci(code) == ["42"]

    def test_llm_function_still_callable(self):
        code = """
import ai
ai.set_mock_mode()

llm g() -> str:
__sys__
You are helpful.
__user__
MOCK:STR:hello
llmend

print(g())
"""
        assert run_ibci(code) == ["hello"]


class TestCallableAsFirstClassValues:
    def test_normal_and_llm_functions_assignable_to_fn(self):
        code = """
func f() -> int:
    return 1

llm g() -> str:
__sys__
You are helpful.
__user__
MOCK:STR:hi
llmend

fn a = f
fn b = g
print(a)
print(b)
"""
        lines = run_ibci(code)
        assert lines == ["<Function 'f'>", "<LLMFunction 'g'>"]
