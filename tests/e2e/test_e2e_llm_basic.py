"""
tests/e2e/test_e2e_llm_basic.py
================================

e2e LLM 基础测试（MOCK 协议 / behavior 表达式 / LLM 函数 / 类型 cast /
control flow / mock repair / stale result 隔离）。

从 tests/e2e/test_e2e_ai_mock.py 拆分 — 详见
docs/TESTS_REORGANIZATION_TASK.md Step 11。
"""

import os
import pytest

from core.engine import IBCIEngine
from tests.conftest import run_ibci, AI_MOCK_PREFIX








class TestE2EAIMockBasic:
    def test_mock_true(self):
        code = AI_MOCK_PREFIX + """
str result = @~ MOCK:TRUE is sky blue ~
print(result)
"""
        lines = run_ibci(code)
        assert "1" in lines

    def test_mock_false(self):
        code = AI_MOCK_PREFIX + """
str result = @~ MOCK:FALSE is it raining ~
print(result)
"""
        lines = run_ibci(code)
        assert "0" in lines

    def test_mock_int_type(self):
        code = AI_MOCK_PREFIX + """
str result = @~ MOCK:INT:42 ~
print(result)
"""
        lines = run_ibci(code)
        assert "42" in lines

    def test_mock_float_type(self):
        code = AI_MOCK_PREFIX + """
str result = @~ MOCK:FLOAT:3.14 ~
print(result)
"""
        lines = run_ibci(code)
        assert "3.14" in lines

    def test_mock_list_direct(self):
        code = AI_MOCK_PREFIX + """
str result = @~ MOCK:LIST:["a","b","c"] ~
print(result)
"""
        lines = run_ibci(code)
        assert any("a" in l for l in lines)


class TestE2EAITypeCast:
    def test_int_cast_from_behavior(self):
        code = AI_MOCK_PREFIX + """
int x = @~ MOCK:INT:99 ~
print((str)x)
"""
        lines = run_ibci(code)
        assert "99" in lines


class TestE2EAIControlFlow:
    def test_if_mock_true(self):
        code = AI_MOCK_PREFIX + """
if @~ MOCK:TRUE condition ~:
    print("True branch")
else:
    print("False branch")
"""
        lines = run_ibci(code)
        assert "True branch" in lines

    def test_if_mock_false(self):
        code = AI_MOCK_PREFIX + """
if @~ MOCK:FALSE condition ~:
    print("True branch")
else:
    print("False branch")
"""
        lines = run_ibci(code)
        assert "False branch" in lines


class TestE2ELLMFunctions:
    def test_llm_function_call(self):
        code = AI_MOCK_PREFIX + """
llm greet(str name) -> str:
__sys__
You are a greeter.
__user__
Greet $name
llmend

str result = greet("Alice")
print(result)
"""
        lines = run_ibci(code)
        # In MOCK mode, it should return something
        assert len(lines) > 0


class TestE2EMockRepair:
    def test_repair_first_fails_then_succeeds(self):
        code = AI_MOCK_PREFIX + """
str result = @~ MOCK:REPAIR mykey ~
llmexcept:
    print("first attempt failed")
    retry "retry hint"

print(result)
"""
        lines = run_ibci(code)
        assert "first attempt failed" in lines


class TestE2EMockStrQuoted:
    def test_mock_str_unquoted_value(self):
        """MOCK:STR:hello 应返回 hello"""
        code = AI_MOCK_PREFIX + """
str result = @~ MOCK:STR:hello ~
print(result)
"""
        lines = run_ibci(code)
        assert "hello" in lines

    def test_mock_str_double_quoted_value(self):
        """MOCK:STR:"hello" 应返回 hello（不含引号）"""
        code = AI_MOCK_PREFIX + '''
str result = @~ MOCK:STR:"hello" ~
print(result)
'''
        lines = run_ibci(code)
        assert "hello" in lines
        assert '"hello"' not in lines

    def test_mock_str_quoted_with_spaces(self):
        """MOCK:STR:"hello world" 应返回 hello world"""
        code = AI_MOCK_PREFIX + '''
str result = @~ MOCK:STR:"hello world" ~
print(result)
'''
        lines = run_ibci(code)
        assert "hello world" in lines


class TestE2EStaleResultIsolation:
    def test_plain_assignment_not_contaminated_after_fail(self):
        """MOCK:FAIL 后的普通赋值（int i = 0）不应被污染为 IbLLMUncertain"""
        code = AI_MOCK_PREFIX + """
str x = @~ MOCK:FAIL first ~
int i = 0
print((str)i)
"""
        lines = run_ibci(code)
        assert "0" in lines

    def test_while_loop_runs_after_fail_in_body(self):
        """循环体内出现 MOCK:FAIL（无 llmexcept）后，下一次迭代的普通条件不应被过期结果终止"""
        code = AI_MOCK_PREFIX + """
int i = 0
while i < 3:
    str x = @~ MOCK:FAIL body ~
    i = i + 1
print((str)i)
"""
        lines = run_ibci(code)
        assert "3" in lines

    def test_if_condition_not_contaminated_by_prior_fail(self):
        """MOCK:FAIL 后的 if 语句使用普通条件时不应被过期不确定结果阻断"""
        code = AI_MOCK_PREFIX + """
str x = @~ MOCK:FAIL first ~
int v = 10
if v > 5:
    print("big")
else:
    print("small")
"""
        lines = run_ibci(code)
        assert "big" in lines
