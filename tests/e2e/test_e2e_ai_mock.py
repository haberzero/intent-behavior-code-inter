"""
tests/e2e/test_e2e_ai_mock.py

End-to-end tests for IBCI AI/LLM features using MOCK mode.

Coverage:
  - Behavior expression with MOCK:TRUE/FALSE
  - Behavior expression with MOCK:INT/STR/FLOAT
  - LLM function definitions (llm ... llmend)
  - llmexcept with retry
  - llmretry syntax sugar
  - Intent annotations (@, @+, @-)
  - MOCK:REPAIR recovery
  - AI in if/while conditions
"""

import os
import pytest
from core.engine import IBCIEngine


def run_and_capture(code: str):
    lines = []
    def callback(text):
        lines.append(str(text))
    engine = IBCIEngine(root_dir=os.path.dirname(os.path.abspath(__file__)), auto_sniff=False)
    engine.run_string(code, output_callback=callback, silent=True)
    return lines


def ai_setup_code():
    """Standard AI MOCK mode setup prefix."""
    return """import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
"""


# ---------------------------------------------------------------------------
# 1. Basic behavior expressions with MOCK
# ---------------------------------------------------------------------------

class TestE2EAIMockBasic:
    def test_mock_true(self):
        code = ai_setup_code() + """
str result = @~ MOCK:TRUE is sky blue ~
print(result)
"""
        lines = run_and_capture(code)
        assert "1" in lines

    def test_mock_false(self):
        code = ai_setup_code() + """
str result = @~ MOCK:FALSE is it raining ~
print(result)
"""
        lines = run_and_capture(code)
        assert "0" in lines

    def test_mock_custom_value(self):
        code = ai_setup_code() + """
str result = @~ MOCK:HELLO ~
print(result)
"""
        lines = run_and_capture(code)
        assert "HELLO" in lines

    def test_mock_int_type(self):
        code = ai_setup_code() + """
str result = @~ MOCK:INT:42 ~
print(result)
"""
        lines = run_and_capture(code)
        assert "42" in lines

    def test_mock_float_type(self):
        code = ai_setup_code() + """
str result = @~ MOCK:FLOAT:3.14 ~
print(result)
"""
        lines = run_and_capture(code)
        assert "3.14" in lines

    def test_mock_list_direct(self):
        code = ai_setup_code() + """
str result = @~ MOCK:["a","b","c"] ~
print(result)
"""
        lines = run_and_capture(code)
        assert any("a" in l for l in lines)


# ---------------------------------------------------------------------------
# 2. Behavior expression with type casting
# ---------------------------------------------------------------------------

class TestE2EAITypeCast:
    def test_int_cast_from_behavior(self):
        code = ai_setup_code() + """
int x = @~ MOCK:INT:99 ~
print((str)x)
"""
        lines = run_and_capture(code)
        assert "99" in lines


# ---------------------------------------------------------------------------
# 3. AI in control flow (MOCK:TRUE/FALSE)
# ---------------------------------------------------------------------------

class TestE2EAIControlFlow:
    def test_if_mock_true(self):
        code = ai_setup_code() + """
if @~ MOCK:TRUE condition ~:
    print("true branch")
else:
    print("false branch")
"""
        lines = run_and_capture(code)
        assert "true branch" in lines

    def test_if_mock_false(self):
        code = ai_setup_code() + """
if @~ MOCK:FALSE condition ~:
    print("true branch")
else:
    print("false branch")
"""
        lines = run_and_capture(code)
        assert "false branch" in lines


# ---------------------------------------------------------------------------
# 4. LLM function definitions
# ---------------------------------------------------------------------------

class TestE2ELLMFunctions:
    def test_llm_function_call(self):
        code = ai_setup_code() + """
llm greet(str name) -> str:
__sys__
You are a greeter.
__user__
Greet $name
llmend

str result = greet("Alice")
print(result)
"""
        lines = run_and_capture(code)
        # In MOCK mode, it should return something
        assert len(lines) > 0


# ---------------------------------------------------------------------------
# 5. llmexcept and retry
# ---------------------------------------------------------------------------

class TestE2ELLMExcept:
    def test_llmexcept_with_mock_fail(self):
        code = ai_setup_code() + """
str result = @~ MOCK:FAIL test ~
llmexcept:
    print("caught exception")
    retry "please try again"

print(result)
"""
        lines = run_and_capture(code)
        assert "caught exception" in lines

    def test_llmretry_syntax_sugar(self):
        code = ai_setup_code() + """
str result = @~ MOCK:FAIL test ~
llmretry "please try again"

print(result)
"""
        lines = run_and_capture(code)
        # Should complete without crash
        assert len(lines) > 0


# ---------------------------------------------------------------------------
# 6. MOCK:REPAIR recovery
# ---------------------------------------------------------------------------

class TestE2EMockRepair:
    def test_repair_first_fails_then_succeeds(self):
        code = ai_setup_code() + """
str result = @~ MOCK:REPAIR mykey ~
llmexcept:
    print("first attempt failed")
    retry "retry hint"

print(result)
"""
        lines = run_and_capture(code)
        assert "first attempt failed" in lines


# ---------------------------------------------------------------------------
# 7. Intent annotations
# ---------------------------------------------------------------------------

class TestE2EIntents:
    def test_single_intent(self):
        code = ai_setup_code() + """
@ be concise
str result = @~ MOCK:TRUE respond ~
print(result)
"""
        lines = run_and_capture(code)
        assert "1" in lines

    def test_incremental_intent(self):
        code = ai_setup_code() + """
@+ use formal language
@+ be brief
str result = @~ MOCK:TRUE respond ~
print(result)
"""
        lines = run_and_capture(code)
        assert "1" in lines

    def test_remove_intent(self):
        code = ai_setup_code() + """
@+ temporary intent
@-
str result = @~ MOCK:TRUE respond ~
print(result)
"""
        lines = run_and_capture(code)
        assert "1" in lines


# ---------------------------------------------------------------------------
# 8. MOCK:STR 引号剥除
# ---------------------------------------------------------------------------

class TestE2EMockStrQuoted:
    def test_mock_str_unquoted_value(self):
        """MOCK:STR:hello 应返回 hello"""
        code = ai_setup_code() + """
str result = @~ MOCK:STR:hello ~
print(result)
"""
        lines = run_and_capture(code)
        assert "hello" in lines

    def test_mock_str_double_quoted_value(self):
        """MOCK:STR:"hello" 应返回 hello（不含引号）"""
        code = ai_setup_code() + '''
str result = @~ MOCK:STR:"hello" ~
print(result)
'''
        lines = run_and_capture(code)
        assert "hello" in lines
        assert '"hello"' not in lines

    def test_mock_str_quoted_with_spaces(self):
        """MOCK:STR:"hello world" 应返回 hello world"""
        code = ai_setup_code() + '''
str result = @~ MOCK:STR:"hello world" ~
print(result)
'''
        lines = run_and_capture(code)
        assert "hello world" in lines


# ---------------------------------------------------------------------------
# 9. _last_llm_result 过期污染 - 回归测试
# ---------------------------------------------------------------------------

class TestE2EStaleResultIsolation:
    def test_plain_assignment_not_contaminated_after_fail(self):
        """MOCK:FAIL 后的普通赋值（int i = 0）不应被污染为 IbLLMUncertain"""
        code = ai_setup_code() + """
str x = @~ MOCK:FAIL first ~
int i = 0
print((str)i)
"""
        lines = run_and_capture(code)
        assert "0" in lines

    def test_while_loop_runs_after_fail_in_body(self):
        """循环体内出现 MOCK:FAIL（无 llmexcept）后，下一次迭代的普通条件不应被过期结果终止"""
        code = ai_setup_code() + """
int i = 0
while i < 3:
    str x = @~ MOCK:FAIL body ~
    i = i + 1
print((str)i)
"""
        lines = run_and_capture(code)
        assert "3" in lines

    def test_if_condition_not_contaminated_by_prior_fail(self):
        """MOCK:FAIL 后的 if 语句使用普通条件时不应被过期不确定结果阻断"""
        code = ai_setup_code() + """
str x = @~ MOCK:FAIL first ~
int v = 10
if v > 5:
    print("big")
else:
    print("small")
"""
        lines = run_and_capture(code)
        assert "big" in lines
