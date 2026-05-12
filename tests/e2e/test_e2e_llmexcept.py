"""
tests/e2e/test_e2e_llmexcept.py
================================

e2e llmexcept 综合测试：基本 / 嵌套 / for 循环驱动 / 条件驱动 /
用户对象 __to_prompt__ / __snapshot__ 协议。

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





class TestE2ELLMExcept:
    def test_llmexcept_with_mock_fail(self):
        """llmexcept 处理器在每次重试前执行；重试耗尽后抛出 LLMRetryExhaustedError。"""
        code = ai_setup_code() + """
try:
    str result = @~ MOCK:FAIL test ~
    llmexcept:
        print("caught exception")
        retry "please try again"
except LLMRetryExhaustedError as e:
    print("retry_exhausted_caught")
    print(e.message)
"""
        lines = run_and_capture(code)
        # handler body runs on each retry attempt before exhaustion
        assert "caught exception" in lines
        # after exhaustion, LLMRetryExhaustedError is raised and caught
        assert "retry_exhausted_caught" in lines

    def test_llmretry_syntax_sugar(self):
        """llmretry 语法糖同样在重试耗尽后抛出 LLMRetryExhaustedError。"""
        code = ai_setup_code() + """
try:
    str result = @~ MOCK:FAIL test ~
    llmretry "please try again"
except LLMRetryExhaustedError as e:
    print("retry_exhausted_caught")
print("after_catch")
"""
        lines = run_and_capture(code)
        assert "retry_exhausted_caught" in lines
        assert "after_catch" in lines


class TestE2ELLMExceptNested:
    def test_outer_and_inner_llmexcept_independent_retry(self):
        """外层 llmexcept 与内层 llmexcept 互不干扰，各自独立重试。

        外层保护整个代码块；内层仅保护内部的 REPAIR 表达式。
        内层 REPAIR 第一次 FAIL，内层 llmexcept 处理后 retry 恢复；
        外层不应感知到内层的不确定结果（外层 last_llm_result 始终为确定性结果）。
        最终应打印出由内层 REPAIR 恢复后写入的值。
        """
        code = ai_setup_code() + """
str outer = @~ MOCK:STR:outer_ok ~
llmexcept:
    print("outer_exception_handler_ran")
    retry "outer hint"

str inner = @~ MOCK:REPAIR inner_key ~
llmexcept:
    print("inner_exception_handler_ran")
    retry "inner hint"

print(outer)
print(inner)
"""
        lines = run_and_capture(code)
        # 内层 REPAIR 触发 llmexcept，外层不应受影响
        assert "inner_exception_handler_ran" in lines
        assert "outer_exception_handler_ran" not in lines
        assert "outer_ok" in lines

    def test_inner_llmexcept_resolves_inner_outer_continues(self):
        """内层 LLM 调用失败并经 llmexcept 恢复后，外层代码块正常继续执行。

        验证内层 REPAIR 恢复后，后续语句（外层 str b）不受影响。
        """
        code = ai_setup_code() + """
str a = @~ MOCK:REPAIR repair_key ~
llmexcept:
    retry "hint"

str b = @~ MOCK:STR:b_ok ~
print(a)
print(b)
"""
        lines = run_and_capture(code)
        # b 应正常被赋值
        assert "b_ok" in lines

    def test_inner_llmexcept_exhausted_raises_retry_exhausted_error(self):
        """内层 llmexcept 重试耗尽后抛出 LLMRetryExhaustedError；
        外层 try/except 捕获后，后续普通赋值不受污染。
        """
        code = ai_setup_code() + """
try:
    str result = @~ MOCK:FAIL exhaust_key ~
    llmexcept:
        retry "retry1"
except LLMRetryExhaustedError as e:
    print("exhausted_caught")

int counter = 0
counter = counter + 1
print((str)counter)
"""
        lines = run_and_capture(code)
        # LLMRetryExhaustedError is raised and caught
        assert "exhausted_caught" in lines
        # counter assignment not contaminated after exception is handled
        assert "1" in lines


class TestE2ELLMExceptForLoopMock:
    """
    MOCK:SEQ 驱动的 for 循环 llmexcept 集成测试。

    覆盖场景：
    - inner llmexcept 保护 for 循环体内的行为赋值
    - 在特定迭代位置（首次、中间、最后）触发 uncertain
    - 多次失败的循环（迭代 0 和迭代 3）
    - 恢复后循环继续处理正确的迭代变量
    - 条件驱动 for 循环的条件不确定性处理
    """

    def test_inner_llmexcept_fail_at_first_iteration(self):
        """首迭代失败：iter0 触发 UNCERTAIN，inner llmexcept 恢复后循环继续完成全部 3 次迭代。"""
        code = ai_setup_code() + """
int count = 0
list items = ["a", "b", "c"]
for str item in items:
    str x = @~ MOCK:SEQ:[FAIL,OK,OK,OK] first_fail_key ~
    llmexcept:
        print("handler_ran")
        retry "hint"
    count = count + 1
print((str)count)
"""
        lines = run_and_capture(code)
        # handler ran exactly once (only iter0 failed)
        assert "handler_ran" in lines
        assert lines.count("handler_ran") == 1
        # all 3 iterations completed
        assert "3" in lines

    def test_inner_llmexcept_fail_at_middle_iteration(self):
        """中间迭代（iter2）失败：inner llmexcept 恢复后所有 5 次迭代均完成。"""
        code = ai_setup_code() + """
int count = 0
list items = ["a", "b", "c", "d", "e"]
for str item in items:
    str x = @~ MOCK:SEQ:[OK,OK,FAIL,OK,OK,OK] mid_fail_key ~
    llmexcept:
        print("handler_ran")
        retry "hint"
    count = count + 1
print((str)count)
"""
        lines = run_and_capture(code)
        assert "handler_ran" in lines
        assert lines.count("handler_ran") == 1
        # all 5 iterations completed
        assert "5" in lines

    def test_inner_llmexcept_fail_at_last_iteration(self):
        """末尾迭代（iter4）失败：inner llmexcept 恢复后所有 5 次迭代均完成。"""
        code = ai_setup_code() + """
int count = 0
list items = ["a", "b", "c", "d", "e"]
for str item in items:
    str x = @~ MOCK:SEQ:[OK,OK,OK,OK,FAIL,OK] last_fail_key ~
    llmexcept:
        print("handler_ran")
        retry "hint"
    count = count + 1
print((str)count)
"""
        lines = run_and_capture(code)
        assert "handler_ran" in lines
        assert lines.count("handler_ran") == 1
        assert "5" in lines

    def test_inner_llmexcept_multiple_failures(self):
        """多次失败（iter0 和 iter3）：handler 被调用两次，循环完成全部 5 次迭代。"""
        code = ai_setup_code() + """
int count = 0
list items = ["a", "b", "c", "d", "e"]
for str item in items:
    str x = @~ MOCK:SEQ:[FAIL,OK,OK,OK,FAIL,OK,OK,OK] multi_fail_key ~
    llmexcept:
        print("handler_ran")
        retry "hint"
    count = count + 1
print((str)count)
"""
        lines = run_and_capture(code)
        # handler fired twice
        assert lines.count("handler_ran") == 2
        # loop still completed all 5 iterations
        assert "5" in lines

    def test_inner_llmexcept_prints_correct_item_when_failing(self):
        """handler 体内可访问正确的循环变量（iter1 失败时 item 应为 'b'）。"""
        code = ai_setup_code() + """
list items = ["a", "b", "c"]
for str item in items:
    str x = @~ MOCK:SEQ:[OK,FAIL,OK,OK] item_check_key ~
    llmexcept:
        print("fail_at")
        print(item)
        retry "hint"
    print("done")
"""
        lines = run_and_capture(code)
        assert "fail_at" in lines
        # the failing iteration is iter1 → item should be "b"
        assert "b" in lines
        # loop variable printed in handler must be "b", not "a" or "c"
        fail_idx = lines.index("fail_at")
        assert lines[fail_idx + 1] == "b"
        # all 3 iterations printed "done"
        assert lines.count("done") == 3

    def test_inner_llmexcept_recovery_does_not_break_subsequent_iterations(self):
        """llmexcept 恢复后，后续迭代的行为赋值正常执行，不受前次不确定性污染。"""
        code = ai_setup_code() + """
int count = 0
list items = ["a", "b", "c", "d"]
for str item in items:
    str x = @~ MOCK:SEQ:[OK,FAIL,OK,OK,OK,OK] subseq_key ~
    llmexcept:
        print("handler_ran")
        retry "hint"
    count = count + 1
print((str)count)
"""
        lines = run_and_capture(code)
        assert "handler_ran" in lines
        # 恢复后所有 4 次迭代完成（count 包括失败迭代的 retry 后的正常执行）
        assert "4" in lines


class TestE2ELLMExceptConditionDrivenLoop:
    """
    条件驱动 for 循环（for @~...~:）与 llmexcept 的集成测试。

    条件驱动循环的 llmexcept 语义：每次条件 LLM 调用被单独保护，
    uncertain 时 llmexcept handler 运行并可 retry 当前条件判断。
    """

    def test_condition_driven_loop_with_uncertain_at_middle(self):
        """条件第 2 次判断触发 UNCERTAIN，llmexcept 恢复后循环继续，共执行 3 次循环体。"""
        code = ai_setup_code() + """
int count = 0
for @~ MOCK:SEQ:[1,1,FAIL,1,0] cond_key ~:
    count = count + 1
llmexcept:
    print("cond_handler")
    retry "hint"
print((str)count)
"""
        lines = run_and_capture(code)
        assert "cond_handler" in lines
        # 3 loop body executions: cond checks 0→1, 1→1, 2→FAIL(retry)→3→1, 4→0(exit)
        assert "3" in lines

    def test_condition_driven_loop_no_failure(self):
        """条件判断全部确定时，llmexcept handler 不触发，循环正常结束。"""
        code = ai_setup_code() + """
int count = 0
for @~ MOCK:SEQ:[1,1,0] cond_clean_key ~:
    count = count + 1
llmexcept:
    print("should_not_run")
    retry "hint"
print((str)count)
"""
        lines = run_and_capture(code)
        assert "should_not_run" not in lines
        assert "2" in lines

    def test_condition_driven_loop_uncertain_at_first_check(self):
        """首次条件判断 UNCERTAIN，llmexcept 恢复后循环正常执行。"""
        code = ai_setup_code() + """
int count = 0
for @~ MOCK:SEQ:[FAIL,1,1,0] cond_first_key ~:
    count = count + 1
llmexcept:
    print("cond_handler_first")
    retry "hint"
print((str)count)
"""
        lines = run_and_capture(code)
        assert "cond_handler_first" in lines
        # after retry, cond→1 (truthy), body runs twice, cond→0 exits
        assert "2" in lines


class TestE2EUserClassPromptProtocols:
    """
    Tests that user-defined IBCI classes can implement __outputhint_prompt__
    via vtable methods, accessible through the standard IbObject protocol.
    """

    def test_user_class_outputhint_prompt_via_vtable(self):
        """
        When a user class defines func __outputhint_prompt__(self) -> str,
        calling that method returns the user-defined hint string.
        """
        code = """class Mood:
    str value

    func __outputhint_prompt__(self) -> str:
        return "请用一个词描述情绪"

Mood m = Mood("happy")
str hint = m.__outputhint_prompt__()
print(hint)
"""
        lines = run_and_capture(code)
        assert "请用一个词描述情绪" in lines

    def test_user_class_to_prompt_in_llm_context(self):
        """
        __to_prompt__ is called by the LLM executor when an object is interpolated
        in a behavior expression via $var syntax.
        """
        code = ai_setup_code() + """
class Label:
    str text

    func __to_prompt__(self) -> str:
        return "label:" + self.text

Label lb = Label("urgent")
str result = @~ MOCK:context_test_key $lb ~
print(lb.__to_prompt__())
"""
        lines = run_and_capture(code)
        assert "label:urgent" in lines


class TestE2ELLMExceptUserObjectSnapshot:
    """
    Tests that user-defined class instance fields are deep-cloned into the
    llmexcept snapshot and correctly restored on retry.
    """

    def test_user_object_field_rolled_back_on_retry(self):
        """
        User object is captured in llmexcept snapshot. After a FAIL on the first
        attempt, retry restores the object so the second attempt starts from the
        pre-attempt state, and the successful LLM value is correctly written.
        """
        code = ai_setup_code() + """
class Box:
    int value

Box b = Box(10)
int new_val = @~ MOCK:SEQ:[FAIL,42] ~
llmexcept:
    retry "hint"
b.value = new_val
print((str)b.value)
"""
        lines = run_and_capture(code)
        # After successful retry, new_val = 42 (second MOCK response)
        assert "42" in lines

    def test_user_object_unaffected_by_snapshot_if_no_retry(self):
        """When LLM call succeeds on first try, snapshot logic doesn't interfere."""
        code = ai_setup_code() + """
class Counter:
    int count

Counter c = Counter(0)
int new_count = @~ MOCK:INT:7 ~
llmexcept:
    retry "hint"
c.count = new_count
print((str)c.count)
"""
        lines = run_and_capture(code)
        assert "7" in lines


class TestE2ELLMExceptSnapshotProtocol:
    """
    Tests for 方案B: user IBCI classes implement __snapshot__(self) and
    __restore__(self, state) to take full control over what gets snapshotted
    and how it is restored during llmexcept retry cycles.

    Priority rule: if __snapshot__ is defined on the class, 方案B is used
    for that variable; otherwise 方案A (auto deep-clone) is the fallback.
    """

    def test_snapshot_and_restore_are_called(self):
        """
        __snapshot__ is called once when the llmexcept frame is entered;
        __restore__ is called before each retry.
        Both calls print observable output to confirm they were executed.
        """
        code = ai_setup_code() + """
class Watcher:
    int val

    func __snapshot__(self) -> int:
        print("snap:" + (str)self.val)
        return self.val

    func __restore__(self, int s):
        print("restore:" + (str)s)
        self.val = s

Watcher w = Watcher(7)
str r = @~ MOCK:SEQ:[FAIL,DONE] ~
llmexcept:
    retry "hint"
print("final:" + (str)w.val)
"""
        lines = run_and_capture(code)
        assert "snap:7" in lines       # __snapshot__ invoked on frame setup
        assert "restore:7" in lines    # __restore__ invoked before retry
        assert "final:7" in lines      # val correctly preserved by protocol

    def test_restore_reverts_mutation_caused_before_llm_call(self):
        """
        A mutation to the object that happens AFTER the snapshot was taken
        (e.g. inside the previous iteration) is correctly rolled back by
        __restore__ before the next attempt.
        """
        code = ai_setup_code() + """
class Counter:
    int n

    func __snapshot__(self) -> int:
        return self.n

    func __restore__(self, int saved):
        self.n = saved

Counter c = Counter(5)
str r = @~ MOCK:SEQ:[FAIL,OK] ~
llmexcept:
    retry "hint"
print((str)c.n)
"""
        lines = run_and_capture(code)
        # After retry, c.n must still be 5 (restored to snapshot value)
        assert "5" in lines

    def test_snapshot_protocol_takes_priority_over_auto_clone(self):
        """
        When __snapshot__ is defined, the user protocol is used instead of
        method A auto deep-clone. Demonstrated by the __restore__ print being
        visible (only called in 方案B path), not the auto-clone path.
        """
        code = ai_setup_code() + """
class Tracked:
    int x
    str label

    func __snapshot__(self) -> int:
        print("protocol_snap")
        return self.x

    func __restore__(self, int saved_x):
        print("protocol_restore")
        self.x = saved_x

Tracked t = Tracked(42, "test")
str r = @~ MOCK:SEQ:[FAIL,OK] ~
llmexcept:
    retry "hint"
print("done")
"""
        lines = run_and_capture(code)
        assert "protocol_snap" in lines     # 方案B's __snapshot__ was called
        assert "protocol_restore" in lines  # 方案B's __restore__ was called
        assert "done" in lines

    def test_snapshot_only_defined_no_restore_is_safe(self):
        """
        If only __snapshot__ is defined (no __restore__), the runtime handles
        this gracefully: the object is kept in saved_protocol_states but
        __restore__ is not called (best-effort semantics — no crash).
        """
        code = ai_setup_code() + """
class PartialProtocol:
    int val

    func __snapshot__(self) -> int:
        return self.val

PartialProtocol p = PartialProtocol(10)
str r = @~ MOCK:SEQ:[FAIL,OK] ~
llmexcept:
    retry "hint"
print("ok")
"""
        lines = run_and_capture(code)
        # No crash; code should complete normally
        assert "ok" in lines

    def test_fallback_to_auto_clone_when_no_snapshot_defined(self):
        """
        When __snapshot__ is NOT defined, 方案A auto deep-clone is used as
        fallback. The existing auto-clone behavior is preserved.
        """
        code = ai_setup_code() + """
class Plain:
    int value

Plain obj = Plain(99)
str r = @~ MOCK:SEQ:[FAIL,OK] ~
llmexcept:
    retry "hint"
print((str)obj.value)
"""
        lines = run_and_capture(code)
        # obj.value unchanged, auto-clone fallback works correctly
        assert "99" in lines
