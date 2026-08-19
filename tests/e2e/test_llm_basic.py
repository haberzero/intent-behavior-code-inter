"""
tests/e2e/test_llm_basic.py
================================

e2e LLM 基础测试（MOCK 协议 / behavior 表达式 / LLM 函数 / 类型 cast /
control flow / mock repair / stale result 隔离）。

"""

import pytest

from tests.conftest import run_ibci, AI_MOCK_PREFIX








class TestE2EAIMockBasic:
    """MOCK 基础协议（str 声明语境）：每种指令产生可断言的值。"""

    @pytest.mark.parametrize("directive,expected", [
        ("MOCK:TRUE is sky blue", "1"),
        ("MOCK:FALSE is it raining", "0"),
        ("MOCK:INT:42", "42"),
        ("MOCK:FLOAT:3.14", "3.14"),
        ('MOCK:LIST:["a","b","c"]', "a"),
        ("MOCK:STR:hello", "hello"),
    ])
    def test_mock_directive_value(self, directive, expected):
        code = AI_MOCK_PREFIX + f"""
str result = @~ {directive} ~
print(result)
"""
        lines = run_ibci(code)
        assert any(expected in l for l in lines)


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
        """llm 可调用类实例直接调用（P4c 迁移）：参数按位绑定 + prompt_slots 自定义槽。"""
        code = AI_MOCK_PREFIX + """
class Greet:
    func __llm_call__(self, any name) -> dict:
        return {"user_prompt": "Greet " + str(name), "prompt_slots": [{"kind": "user_sys", "text": "You are a greeter."}], "expected_type": "str"}

Greet greet = Greet()
str result = greet("Alice")
print(result)
"""
        lines = run_ibci(code)
        # MOCK 模式：验证参数插值实际发生（name → Alice），而非仅"有输出"
        assert len(lines) == 1
        assert "Greet Alice" in lines[0]


class TestE2ELLMFunctionContainerReturn:
    def test_llm_function_returns_list_int(self):
        """llm 可调用类返回 list[int] 应按容器类型解析，而不是退化为 str。"""
        code = AI_MOCK_PREFIX + """
class 取列表:
    func __llm_call__(self) -> dict:
        return {"user_prompt": "MOCK:LIST:[1,2,3]", "prompt_slots": [{"kind": "user_sys", "text": "你只返回 JSON 数组。"}], "expected_type": "list[int]"}

取列表 inst = 取列表()
list[int] nums = inst()
print((str)nums.len())
print((str)nums[0])
print((str)nums[2])
"""
        lines = run_ibci(code)
        assert lines == ["3", "1", "3"]

    def test_llm_function_returns_dict_str_int(self):
        """llm 可调用类返回 dict[str,int] 应按容器类型解析。"""
        code = AI_MOCK_PREFIX + """
class 取分数:
    func __llm_call__(self) -> dict:
        return {"user_prompt": "MOCK:DICT:{\\"math\\":90,\\"english\\":85}", "prompt_slots": [{"kind": "user_sys", "text": "你只返回 JSON 对象。"}], "expected_type": "dict[str,int]"}

取分数 inst = 取分数()
dict[str,int] scores = inst()
print((str)scores.len())
print((str)scores["math"])
"""
        lines = run_ibci(code)
        assert lines == ["2", "90"]


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

    def test_while_loop_fail_without_llmexcept_raises(self):
        """循环体内 MOCK:FAIL（无 llmexcept）→ 同步路径抛 LLMParseError，循环终止。

        循环体内行为不可 dispatch（可重复执行上下文），走同步路径；
        不确定结果无 llmexcept 保护即在赋值点报错（统一机制语义）。
        """
        code = AI_MOCK_PREFIX + """
int i = 0
try:
    while i < 3:
        str x = @~ MOCK:FAIL body ~
        i = i + 1
except:
    print("caught")
"""
        lines = run_ibci(code)
        assert "caught" in lines

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
