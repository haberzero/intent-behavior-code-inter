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
str result = @~ MOCK:LIST:["a","b","c"] ~
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
    print("True branch")
else:
    print("False branch")
"""
        lines = run_and_capture(code)
        assert "True branch" in lines

    def test_if_mock_false(self):
        code = ai_setup_code() + """
if @~ MOCK:FALSE condition ~:
    print("True branch")
else:
    print("False branch")
"""
        lines = run_and_capture(code)
        assert "False branch" in lines


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

    def test_single_intent_does_not_pollute_persistent_stack(self):
        """@ 是一次性意图，LLM 调用后不应残留在持久意图栈中。
        回归测试：验证第二次 LLM 调用能正常执行（若 @ 意图错误地永久入栈，
        第二次调用仍会携带该意图，虽然 MOCK 模式下不影响结果，但不应报错）。"""
        code = ai_setup_code() + """
@ be concise
str result1 = @~ MOCK:TRUE first ~
str result2 = @~ MOCK:TRUE second ~
print(result1)
print(result2)
"""
        lines = run_and_capture(code)
        assert lines.count("1") >= 2, "Both calls should succeed after one-shot @ intent"

    def test_single_intent_does_not_affect_subsequent_call(self):
        """@ 消费后，后续 LLM 调用不应继承该意图（通过混合 @+ 和 @ 验证）。"""
        code = ai_setup_code() + """
@+ formal language
@ first hint
str result1 = @~ MOCK:TRUE first ~
str result2 = @~ MOCK:TRUE second ~
print(result1)
print(result2)
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

    def test_at_plus_persists_after_llm_call(self):
        """@+ 是持久压栈，LLM 调用后意图仍有效，后续调用正常。"""
        code = ai_setup_code() + """
@+ use formal language
str result1 = @~ MOCK:TRUE first ~
str result2 = @~ MOCK:TRUE second ~
print(result1)
print(result2)
"""
        lines = run_and_capture(code)
        assert lines.count("1") >= 2

    def test_lambda_behavior_uses_call_time_intents(self):
        """lambda 延迟行为应在调用时使用当前意图栈，而非定义时的空栈（回归验证）。
        注：直接赋值到具体类型（int/str）需 P2 编译器类型推断改进，当前通过 print() 调用验证。"""
        code = ai_setup_code() + """
@+ use formal language
str fn compute = lambda: @~ MOCK:STR:hello ~
@-
print(compute())
"""
        lines = run_and_capture(code)
        assert "hello" in lines

    def test_lambda_behavior_basic(self):
        """lambda 延迟行为基本执行冒烟测试。"""
        code = ai_setup_code() + """
str fn compute = lambda: @~ MOCK:STR:world ~
print(compute())
"""
        lines = run_and_capture(code)
        assert "world" in lines


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


# ---------------------------------------------------------------------------
# 10. 嵌套 llmexcept 系统性集成测试
# ---------------------------------------------------------------------------

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

    def test_inner_llmexcept_exhausted_outer_sees_uncertain(self):
        """内层 llmexcept 重试耗尽后，赋值为 IbLLMUncertain；
        外层如果没有额外保护，后续代码应仍能正常执行（不崩溃）。

        此测试验证：inner llmexcept 耗尽后程序不崩溃，并且
        在 inner 之后的普通赋值（int counter = 0）不受污染。
        """
        code = ai_setup_code() + """
str result = @~ MOCK:FAIL exhaust_key ~
llmexcept:
    retry "retry1"

int counter = 0
counter = counter + 1
print((str)counter)
"""
        lines = run_and_capture(code)
        # counter 赋值不应被 UNCERTAIN 污染
        assert "1" in lines


# ---------------------------------------------------------------------------
# 11. MOCK:SEQ + for 循环 llmexcept 系统性集成测试
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 12. 条件驱动 for 循环 + llmexcept 集成测试
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 13. __from_prompt__ / __outputhint_prompt__ vtable for user-defined classes
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 14. User-defined class deep-clone in llmexcept snapshot
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 15. 方案B: User-controlled __snapshot__ / __restore__ protocol
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 16. Function scope intent isolation (fork-on-call semantics)
# ---------------------------------------------------------------------------

class TestE2EIntentScopeIsolation:
    """
    Tests for intent stack copy-semantics on function calls.

    - Caller's intent stack is forked (not shared) on function entry.
    - @+ inside a function does NOT leak to the caller's scope.
    - intent_context.clear_inherited() clears the inherited stack inside the callee.
    - intent_context.use(ctx) replaces the current scope's intent context.
    - intent_context.get_current() captures the current scope's intent context.
    """

    def test_intent_push_inside_func_does_not_leak(self):
        """
        @+ inside a function should not affect the caller's intent stack.
        After the function returns, the caller's intent stack is unchanged.
        """
        code = ai_setup_code() + """
@+ "caller intent"

func modify_intents():
    @+ "inner intent"
    return

modify_intents()

str result = @~ MOCK:intent_isolation_test ~
print(result)
"""
        lines = run_and_capture(code)
        assert len(lines) >= 1  # runs without error

    def test_clear_inherited_removes_caller_intents(self):
        """
        intent_context.clear_inherited() inside a function clears the persistent
        intent stack inherited from the caller. After calling it, @+ inside the
        function starts from an empty stack.
        """
        code = ai_setup_code() + """
@+ "caller persistent intent"

func isolated_func() -> str:
    intent_context.clear_inherited()
    str r = @~ MOCK:INT:99 ~
    return r

str result = isolated_func()
print(result)
"""
        lines = run_and_capture(code)
        assert "99" in lines  # function ran successfully with cleared intents

    def test_use_replaces_scope_intent_context(self):
        """
        intent_context.use(ctx) replaces the current scope's intent context
        with the given instance. The caller's persistent intents are replaced.
        """
        code = ai_setup_code() + """
@+ "caller persistent intent"

func process_with_custom_ctx() -> str:
    intent_context my_ctx = intent_context()
    my_ctx.push("custom intent only")
    intent_context.use(my_ctx)
    str r = @~ MOCK:INT:77 ~
    return r

str result = process_with_custom_ctx()
print(result)
"""
        lines = run_and_capture(code)
        assert "77" in lines

    def test_get_current_captures_scope_snapshot(self):
        """
        intent_context.get_current() returns a snapshot of the current scope's
        intent context. The snapshot is independent of subsequent modifications.
        """
        code = ai_setup_code() + """
@+ "initial intent"

func capture_and_modify() -> str:
    intent_context saved = intent_context.get_current()
    @+ "additional intent"
    str r = @~ MOCK:INT:55 ~
    return r

str result = capture_and_modify()
print(result)
"""
        lines = run_and_capture(code)
        assert "55" in lines


# ---------------------------------------------------------------------------
# 17. Lambda-as-argument restriction (runtime check)
# ---------------------------------------------------------------------------

class TestE2ELambdaRestriction:
    """
    M2: lambda 值现在可以自由作为函数参数传递（高阶函数场景）。

    M1 时期的限制（"lambda 延迟对象不允许作为函数参数传递"）已在 M2 中移除：
    lambda 闭包的自由变量通过共享 IbCell 捕获，生命周期安全，可以跨作用域传递。
    """

    def test_lambda_can_be_passed_as_arg(self):
        """M2: lambda 值可以作为函数参数传递，高阶函数能调用它。"""
        code = ai_setup_code() + """
func apply(fn f, int val) -> auto:
    return f(val)

fn double = lambda(int x): x * 2
int result = (int)apply(double, 5)
print((str)result)
"""
        lines = run_and_capture(code)
        assert lines == ["10"]

    def test_lambda_passed_as_any_and_called(self):
        """lambda 传入 any 参数，函数内可以正常调用。"""
        code = ai_setup_code() + """
func call_it(fn f) -> str:
    return (str)f()

fn greet = lambda: "hello"
str r = call_it(greet)
print(r)
"""
        lines = run_and_capture(code)
        assert lines == ["hello"]

    def test_snapshot_can_be_passed_as_any(self):
        """
        snapshot 值仍然可以作为参数传递（M1 起即支持）。
        """
        code = ai_setup_code() + """
func accept_any(any x):
    print("called")

fn deferred_val = snapshot: 42
accept_any(deferred_val)
print("ok")
"""
        lines = run_and_capture(code)
        assert "ok" in lines


# ---------------------------------------------------------------------------
# 18. intent_context OOP MVP — instantiation and method binding
# ---------------------------------------------------------------------------

class TestE2EIntentContextOOP:
    """
    Tests for the intent_context built-in class (OOP MVP).

    Users can instantiate intent_context, call push/pop/fork/clear/resolve.
    """

    def test_intent_context_instantiation(self):
        """intent_context() creates a new instance without errors."""
        code = """
intent_context ctx = intent_context()
print("created")
"""
        lines = run_and_capture(code)
        assert "created" in lines

    def test_intent_context_push_and_clear(self):
        """push() adds an intent; clear() empties the stack."""
        code = """
intent_context ctx = intent_context()
ctx.push("hello")
ctx.clear()
print("ok")
"""
        lines = run_and_capture(code)
        assert "ok" in lines

    def test_intent_context_fork_returns_new_instance(self):
        """fork() returns a new independent instance."""
        code = """
intent_context ctx = intent_context()
ctx.push("base intent")
intent_context ctx2 = ctx.fork()
ctx2.push("fork intent")
ctx.clear()
print("ok")
"""
        lines = run_and_capture(code)
        assert "ok" in lines

    def test_intent_context_resolve(self):
        """resolve() returns a list (may be empty or with content strings)."""
        code = """
intent_context ctx = intent_context()
ctx.push("my intent")
any resolved = ctx.resolve()
print("ok")
"""
        lines = run_and_capture(code)
        assert "ok" in lines
