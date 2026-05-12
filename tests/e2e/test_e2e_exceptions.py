"""
tests/e2e/test_e2e_exceptions.py
=================================

e2e 异常体系测试：LLM 异常层级（E5）+ 用户自定义异常 / NetworkError
inheritance / LLMError 子类化。

从 tests/e2e/test_e2e_ai_mock.py 拆分 — 详见
docs/TESTS_REORGANIZATION_TASK.md Step 11。
"""

import os
import pytest

from core.engine import IBCIEngine


def run_and_capture(code: str):
    lines = []
    engine = IBCIEngine(
        root_dir=os.path.dirname(os.path.abspath(__file__)),
        auto_sniff=False,
    )
    engine.run_string(code, output_callback=lambda t: lines.append(str(t)), silent=True)
    return lines


def ai_setup_code():
    return 'import ai\nai.set_config("TESTONLY", "TESTONLY", "TESTONLY")\n'





class TestE2ELLMExceptionHierarchy:
    """
    端到端验证 LLM 异常体系：
    - 无保护裸 LLM 赋值失败 → LLMParseError
    - llmexcept 重试耗尽 → LLMRetryExhaustedError
    - 异常可被 LLMError 基类捕获
    - 异常可被顶层 Exception 基类捕获
    - 异常 message 字段可访问
    """

    def test_unprotected_llm_fail_raises_llm_parse_error(self):
        """无 llmexcept 保护的 LLM 赋值失败，使用变量时抛出 LLMParseError。"""
        code = ai_setup_code() + """
try:
    str x = @~ MOCK:FAIL bare_fail ~
    print(x)
except LLMParseError as e:
    print("llm_parse_error_caught")
    print(e.message)
print("after_catch")
"""
        lines = run_and_capture(code)
        assert "llm_parse_error_caught" in lines
        assert "after_catch" in lines

    def test_llm_parse_error_catchable_by_llm_error_base(self):
        """LLMParseError 可被其基类 LLMError 捕获。"""
        code = ai_setup_code() + """
try:
    str x = @~ MOCK:FAIL base_catch ~
    print(x)
except LLMError as e:
    print("llm_error_caught")
print("done")
"""
        lines = run_and_capture(code)
        assert "llm_error_caught" in lines
        assert "done" in lines

    def test_llm_error_catchable_by_exception_base_class(self):
        """LLMRetryExhaustedError 可被顶层 Exception 基类捕获。"""
        code = ai_setup_code() + """
try:
    str result = @~ MOCK:FAIL exception_catch ~
    llmexcept:
        retry "hint"
except Exception as e:
    print("base_exception_caught")
print("done")
"""
        lines = run_and_capture(code)
        assert "base_exception_caught" in lines
        assert "done" in lines

    def test_llm_retry_exhausted_error_message_field(self):
        """LLMRetryExhaustedError 包含可读 message 和 max_retry 字段。"""
        code = ai_setup_code() + """
try:
    str result = @~ MOCK:FAIL msg_field ~
    llmexcept:
        retry "hint"
except LLMRetryExhaustedError as e:
    print("caught")
    print(e.message)
"""
        lines = run_and_capture(code)
        assert "caught" in lines
        # message should mention retry exhaustion
        assert any("retry" in line.lower() for line in lines)

    def test_llm_parse_error_leaves_scope_clean_after_catch(self):
        """try/except LLMParseError 后，作用域内后续普通赋值不受污染。"""
        code = ai_setup_code() + """
int x = 0
try:
    str bad = @~ MOCK:FAIL scope_clean ~
    print(bad)
except LLMParseError as e:
    x = 99
int y = x + 1
print((str)y)
"""
        lines = run_and_capture(code)
        assert "100" in lines

    def test_repair_succeeds_before_exhaustion(self):
        """MOCK:REPAIR 第一次失败后第二次成功，不抛异常，正常打印结果。"""
        code = ai_setup_code() + """
str result = @~ MOCK:REPAIR repair_ok ~
llmexcept:
    retry "hint"
print(result)
"""
        lines = run_and_capture(code)
        # successful second attempt → prints the result string, no exception
        assert len(lines) > 0


class TestE2EUserDefinedException:
    """
    端到端验证用户可继承内置 `Exception` 体系定义自定义异常。

    背景：在 `EXCEPTION_SPEC` 由 `IbSpec` 升级为 `TypeDef` 之前，
    `class MyError(Exception):` 会在语义分析阶段报 SEM_001
    （"Base class 'Exception' is not defined or not a class"）。
    本测试组锁定升级后的可用能力，并以注释形式标注一个已知
    pre-existing 限制：`except X as e:` 中 e 的类型仍按基类公理解析，
    访问子类新增字段需要先 `(MyError)e` 强制转换。
    """

    def test_user_exception_subclass_basic_raise_and_catch(self):
        """`class MyError(Exception)` 可被声明、raise 并按具体类型 except 捕获。"""
        code = """
class MyError(Exception):
    func __init__(self, str msg):
        self.message = msg

try:
    raise MyError("oops")
except MyError as e:
    print("caught_my_error")
    print(e.message)
print("after_catch")
"""
        lines = run_and_capture(code)
        assert "caught_my_error" in lines
        assert "oops" in lines
        assert "after_catch" in lines

    def test_user_exception_subclass_caught_by_exception_base(self):
        """用户自定义 Exception 子类可被 `except Exception` 捕获。"""
        code = """
class AppError(Exception):
    func __init__(self, str msg):
        self.message = msg

try:
    raise AppError("base-catch")
except Exception as e:
    print("caught_as_exception")
    print(e.message)
"""
        lines = run_and_capture(code)
        assert "caught_as_exception" in lines
        assert "base-catch" in lines

    def test_user_exception_two_level_inheritance(self):
        """两级用户自定义继承链：`NetworkError -> AppError -> Exception` 全链路捕获生效。"""
        code = """
class AppError(Exception):
    func __init__(self, str msg):
        self.message = msg

class NetworkError(AppError):
    func __init__(self, str msg):
        self.message = msg

try:
    raise NetworkError("conn refused")
except AppError as e:
    print("caught_app_error")
    print(e.message)
"""
        lines = run_and_capture(code)
        assert "caught_app_error" in lines
        assert "conn refused" in lines

    def test_user_subclass_of_llm_error(self):
        """用户可继承内置 LLMError 派生异常，并被 LLMError / Exception 捕获。"""
        code = """
class MyLLMErr(LLMError):
    func __init__(self, str msg):
        self.message = msg

try:
    raise MyLLMErr("custom-llm")
except LLMError as e:
    print("caught_llm_error")
    print(e.message)
"""
        lines = run_and_capture(code)
        assert "caught_llm_error" in lines
        assert "custom-llm" in lines

    def test_user_exception_extra_field_via_cast_workaround(self):
        """已知限制：`except X as e:` 中 e 仅按 Exception 基类解析成员。
        访问子类新增字段必须先 `(MyError)e` 强转 — 此测试锁定该 workaround 始终可用。"""
        code = """
class MyError(Exception):
    str detail
    func __init__(self, str msg, str detail):
        self.message = msg
        self.detail = detail

try:
    raise MyError("oops", "deep-context")
except MyError as e:
    MyError me = (MyError)e
    print(me.message)
    print(me.detail)
"""
        lines = run_and_capture(code)
        assert "oops" in lines
        assert "deep-context" in lines

    def test_user_exception_does_not_match_unrelated_class(self):
        """用户自定义异常不会错误匹配到无关类型的 except 分支。"""
        code = """
class FooError(Exception):
    func __init__(self, str msg):
        self.message = msg

class BarError(Exception):
    func __init__(self, str msg):
        self.message = msg

try:
    raise FooError("foo-only")
except BarError as e:
    print("wrong_branch")
except FooError as e:
    print("right_branch")
    print(e.message)
"""
        lines = run_and_capture(code)
        assert "right_branch" in lines
        assert "foo-only" in lines
        assert "wrong_branch" not in lines

    def test_llm_call_error_user_raise_and_catch(self):
        """LLMCallError 当前由 VM 不自动抛出（仅供用户手动 raise）；
        本测试锁定其作为 IBCI 用户层异常类型的可用性。"""
        code = """
try:
    raise LLMCallError("provider down")
except LLMCallError as e:
    print("caught_call_error")
    print(e.message)
except LLMError as e:
    print("wrong_branch")
"""
        lines = run_and_capture(code)
        assert "caught_call_error" in lines
        assert "provider down" in lines
        assert "wrong_branch" not in lines
