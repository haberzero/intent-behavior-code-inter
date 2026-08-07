"""
tests_v2/e2e/test_llmexcept.py
================================

e2e llmexcept 综合测试：基本 / 嵌套 / for 循环驱动 / 条件驱动 /
用户对象 __to_prompt__ / __snapshot__ 协议。

"""

from tests_v2.conftest import run_ibci, AI_MOCK_PREFIX








class TestE2ELLMExcept:
    def test_llmexcept_with_mock_fail(self):
        """llmexcept 处理器在每次重试前执行；重试耗尽后抛出 LLMRetryExhaustedError。"""
        code = AI_MOCK_PREFIX + """
try:
    str result = @~ MOCK:FAIL test ~
    llmexcept:
        print("caught exception")
        retry "please try again"
except LLMRetryExhaustedError as e:
    print("retry_exhausted_caught")
    print(e.message)
"""
        lines = run_ibci(code)
        # handler body runs on each retry attempt before exhaustion
        assert "caught exception" in lines
        # after exhaustion, LLMRetryExhaustedError is raised and caught
        assert "retry_exhausted_caught" in lines

    def test_llmretry_syntax_sugar(self):
        """llmretry 语法糖同样在重试耗尽后抛出 LLMRetryExhaustedError。"""
        code = AI_MOCK_PREFIX + """
try:
    str result = @~ MOCK:FAIL test ~
    llmretry "please try again"
except LLMRetryExhaustedError as e:
    print("retry_exhausted_caught")
print("after_catch")
"""
        lines = run_ibci(code)
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
        code = AI_MOCK_PREFIX + """
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
        lines = run_ibci(code)
        # 内层 REPAIR 触发 llmexcept，外层不应受影响
        assert "inner_exception_handler_ran" in lines
        assert "outer_exception_handler_ran" not in lines
        assert "outer_ok" in lines

    def test_inner_llmexcept_resolves_inner_outer_continues(self):
        """内层 LLM 调用失败并经 llmexcept 恢复后，外层代码块正常继续执行。

        验证内层 REPAIR 恢复后，后续语句（外层 str b）不受影响。
        """
        code = AI_MOCK_PREFIX + """
str a = @~ MOCK:REPAIR repair_key ~
llmexcept:
    retry "hint"

str b = @~ MOCK:STR:b_ok ~
print(a)
print(b)
"""
        lines = run_ibci(code)
        # b 应正常被赋值
        assert "b_ok" in lines

    def test_inner_llmexcept_exhausted_raises_retry_exhausted_error(self):
        """内层 llmexcept 重试耗尽后抛出 LLMRetryExhaustedError；
        外层 try/except 捕获后，后续普通赋值不受污染。
        """
        code = AI_MOCK_PREFIX + """
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
        lines = run_ibci(code)
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
        code = AI_MOCK_PREFIX + """
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
        lines = run_ibci(code)
        # handler ran exactly once (only iter0 failed)
        assert "handler_ran" in lines
        assert lines.count("handler_ran") == 1
        # all 3 iterations completed
        assert "3" in lines

    def test_inner_llmexcept_fail_at_middle_iteration(self):
        """中间迭代（iter2）失败：inner llmexcept 恢复后所有 5 次迭代均完成。"""
        code = AI_MOCK_PREFIX + """
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
        lines = run_ibci(code)
        assert "handler_ran" in lines
        assert lines.count("handler_ran") == 1
        # all 5 iterations completed
        assert "5" in lines

    def test_inner_llmexcept_fail_at_last_iteration(self):
        """末尾迭代（iter4）失败：inner llmexcept 恢复后所有 5 次迭代均完成。"""
        code = AI_MOCK_PREFIX + """
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
        lines = run_ibci(code)
        assert "handler_ran" in lines
        assert lines.count("handler_ran") == 1
        assert "5" in lines

    def test_inner_llmexcept_multiple_failures(self):
        """多次失败（iter0 和 iter3）：handler 被调用两次，循环完成全部 5 次迭代。"""
        code = AI_MOCK_PREFIX + """
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
        lines = run_ibci(code)
        # handler fired twice
        assert lines.count("handler_ran") == 2
        # loop still completed all 5 iterations
        assert "5" in lines

    def test_inner_llmexcept_prints_correct_item_when_failing(self):
        """handler 体内可访问正确的循环变量（iter1 失败时 item 应为 'b'）。"""
        code = AI_MOCK_PREFIX + """
list items = ["a", "b", "c"]
for str item in items:
    str x = @~ MOCK:SEQ:[OK,FAIL,OK,OK] item_check_key ~
    llmexcept:
        print("fail_at")
        print(item)
        retry "hint"
    print("done")
"""
        lines = run_ibci(code)
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
        code = AI_MOCK_PREFIX + """
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
        lines = run_ibci(code)
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
        code = AI_MOCK_PREFIX + """
int count = 0
for @~ MOCK:SEQ:[1,1,FAIL,1,0] cond_key ~:
    count = count + 1
llmexcept:
    print("cond_handler")
    retry "hint"
print((str)count)
"""
        lines = run_ibci(code)
        assert "cond_handler" in lines
        # 3 loop body executions: cond checks 0→1, 1→1, 2→FAIL(retry)→3→1, 4→0(exit)
        assert "3" in lines

    def test_condition_driven_loop_no_failure(self):
        """条件判断全部确定时，llmexcept handler 不触发，循环正常结束。"""
        code = AI_MOCK_PREFIX + """
int count = 0
for @~ MOCK:SEQ:[1,1,0] cond_clean_key ~:
    count = count + 1
llmexcept:
    print("should_not_run")
    retry "hint"
print((str)count)
"""
        lines = run_ibci(code)
        assert "should_not_run" not in lines
        assert "2" in lines

    def test_condition_driven_loop_uncertain_at_first_check(self):
        """首次条件判断 UNCERTAIN，llmexcept 恢复后循环正常执行。"""
        code = AI_MOCK_PREFIX + """
int count = 0
for @~ MOCK:SEQ:[FAIL,1,1,0] cond_first_key ~:
    count = count + 1
llmexcept:
    print("cond_handler_first")
    retry "hint"
print((str)count)
"""
        lines = run_ibci(code)
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
        lines = run_ibci(code)
        assert "请用一个词描述情绪" in lines

    def test_user_class_to_prompt_in_llm_context(self):
        """
        __to_prompt__ is called by the LLM executor when an object is interpolated
        in a behavior expression via $var syntax.
        """
        code = AI_MOCK_PREFIX + """
class Label:
    str text

    func __to_prompt__(self) -> str:
        return "label:" + self.text

Label lb = Label("urgent")
str result = @~ MOCK:context_test_key $lb ~
print(lb.__to_prompt__())
"""
        lines = run_ibci(code)
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
        code = AI_MOCK_PREFIX + """
class Box:
    int value

Box b = Box(10)
int new_val = @~ MOCK:SEQ:[FAIL,42] ~
llmexcept:
    retry "hint"
b.value = new_val
print((str)b.value)
"""
        lines = run_ibci(code)
        # After successful retry, new_val = 42 (second MOCK response)
        assert "42" in lines

    def test_user_object_unaffected_by_snapshot_if_no_retry(self):
        """When LLM call succeeds on first try, snapshot logic doesn't interfere."""
        code = AI_MOCK_PREFIX + """
class Counter:
    int count

Counter c = Counter(0)
int new_count = @~ MOCK:INT:7 ~
llmexcept:
    retry "hint"
c.count = new_count
print((str)c.count)
"""
        lines = run_ibci(code)
        assert "7" in lines


class TestE2ELLMExceptSnapshotProtocol:
    """
    Tests for user IBCI classes implement __snapshot__(self) and
    __restore__(self, state) to take full control over what gets snapshotted
    and how it is restored during llmexcept retry cycles.

    Priority rule: if __snapshot__ is defined on the class, the user protocol is used
    for that variable; otherwise auto deep-clone is the fallback.
    """

    def test_snapshot_and_restore_are_called(self):
        """
        __snapshot__ is called once when the llmexcept frame is entered;
        __restore__ is called before each retry.
        Both calls print observable output to confirm they were executed.
        """
        code = AI_MOCK_PREFIX + """
class Watcher:
    int val

    func __snapshot__(self) -> int:
        print("snap:" + (str)self.val)
        return self.val

    func __restore__(self, int s) -> auto:
        print("restore:" + (str)s)
        self.val = s

Watcher w = Watcher(7)
str r = @~ MOCK:SEQ:[FAIL,DONE] ~
llmexcept:
    retry "hint"
print("final:" + (str)w.val)
"""
        lines = run_ibci(code)
        assert "snap:7" in lines       # __snapshot__ invoked on frame setup
        assert "restore:7" in lines    # __restore__ invoked before retry
        assert "final:7" in lines      # val correctly preserved by protocol

    def test_restore_reverts_mutation_caused_before_llm_call(self):
        """
        A mutation to the object that happens AFTER the snapshot was taken
        (e.g. inside the previous iteration) is correctly rolled back by
        __restore__ before the next attempt.
        """
        code = AI_MOCK_PREFIX + """
class Counter:
    int n

    func __snapshot__(self) -> int:
        return self.n

    func __restore__(self, int saved) -> auto:
        self.n = saved

Counter c = Counter(5)
str r = @~ MOCK:SEQ:[FAIL,OK] ~
llmexcept:
    retry "hint"
print((str)c.n)
"""
        lines = run_ibci(code)
        # After retry, c.n must still be 5 (restored to snapshot value)
        assert "5" in lines

    def test_snapshot_protocol_takes_priority_over_auto_clone(self):
        """
        When __snapshot__ is defined, the user protocol is used instead of
        method A auto deep-clone. Demonstrated by the __restore__ print being
        visible (only called in the user protocol path), not the auto-clone path.
        """
        code = AI_MOCK_PREFIX + """
class Tracked:
    int x
    str label

    func __snapshot__(self) -> int:
        print("protocol_snap")
        return self.x

    func __restore__(self, int saved_x) -> auto:
        print("protocol_restore")
        self.x = saved_x

Tracked t = Tracked(42, "test")
str r = @~ MOCK:SEQ:[FAIL,OK] ~
llmexcept:
    retry "hint"
print("done")
"""
        lines = run_ibci(code)
        assert "protocol_snap" in lines     # the user protocol's __snapshot__ was called
        assert "protocol_restore" in lines  # the user protocol's __restore__ was called
        assert "done" in lines

    def test_snapshot_only_defined_no_restore_is_safe(self):
        """
        If only __snapshot__ is defined (no __restore__), the runtime handles
        this gracefully: the object is kept in saved_protocol_states but
        __restore__ is not called (best-effort semantics — no crash).
        """
        code = AI_MOCK_PREFIX + """
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
        lines = run_ibci(code)
        # No crash; code should complete normally
        assert "ok" in lines

    def test_fallback_to_auto_clone_when_no_snapshot_defined(self):
        """
        When __snapshot__ is NOT defined, auto deep-clone is used as
        fallback. The existing auto-clone behavior is preserved.
        """
        code = AI_MOCK_PREFIX + """
class Plain:
    int value

Plain obj = Plain(99)
str r = @~ MOCK:SEQ:[FAIL,OK] ~
llmexcept:
    retry "hint"
print((str)obj.value)
"""
        lines = run_ibci(code)
        # obj.value unchanged, auto-clone fallback works correctly
        assert "99" in lines


class TestE2EConditionUncertainBugA:
    """
    BUG #A 回归测试：if/while/for 在面对不确定 LLM 条件时应统一抛出 LLMParseError。

    此测试确保 if-condition-uncertain 路径有回归保护。
    """

    def test_if_condition_uncertain_raises_llm_parse_error(self):
        """if 条件行为表达式返回模糊值时应触发 llmexcept（而非静默跳过）。"""
        code = AI_MOCK_PREFIX + """
try:
    if @~ MOCK:FAIL uncertain if condition ~:
        print("should_not_reach")
    print("also_should_not_reach")
except:
    print("caught_uncertain_if")
"""
        lines = run_ibci(code)
        assert "caught_uncertain_if" in lines
        assert "should_not_reach" not in lines

    def test_while_condition_uncertain_raises_llm_parse_error(self):
        """while 条件行为表达式返回模糊值时应触发 llmexcept。"""
        code = AI_MOCK_PREFIX + """
try:
    while @~ MOCK:FAIL uncertain while condition ~:
        print("should_not_reach")
    print("also_should_not_reach")
except:
    print("caught_uncertain_while")
"""
        lines = run_ibci(code)
        assert "caught_uncertain_while" in lines
        assert "should_not_reach" not in lines

    def test_if_and_while_uncertain_both_raise_consistently(self):
        """if 和 while 条件不确定时应一致地抛出错误（BUG #A 正交性验证）。"""
        # if 测试
        code_if = AI_MOCK_PREFIX + """
try:
    if @~MOCK:FAIL~:
        print("no")
    print("also_no")
except:
    print("if_caught")
"""
        lines_if = run_ibci(code_if)
        assert "if_caught" in lines_if

        # while 测试
        code_while = AI_MOCK_PREFIX + """
try:
    while @~MOCK:FAIL~:
        print("no")
    print("also_no")
except:
    print("while_caught")
"""
        lines_while = run_ibci(code_while)
        assert "while_caught" in lines_while


class TestE2EUnifiedMechanism:
    """
    统一 llmexcept 机制回归测试：certainty 经 IbLLMCallResult 返回值传递，
    各被保护语句 handler 内联重试，不确定容器经表达式层透传到语句消费者。

    覆盖：
    - BoolOp 嵌套（`@~...~ and True`）条件的不确定传递与重试
    - BinOp 嵌套 RHS（`base + @~...~`）的不确定传递与重试
    - 模糊字符串条件在帧内重试收敛（有界，不无限循环）
    """

    def test_boolop_nested_condition_retries(self):
        """`if @~REPAIR~ and True:` 嵌套 BoolOp：首次不确定，重试后恢复。"""
        code = AI_MOCK_PREFIX + """
if @~ MOCK:REPAIR:BOOL:TRUE boolop_key ~ and True:
    print("cond_ok")
llmexcept:
    print("cond_retry")
    retry "hint"
"""
        lines = run_ibci(code)
        assert "cond_retry" in lines
        assert "cond_ok" in lines

    def test_boolop_nested_condition_no_handler_raises(self):
        """`if @~FAIL~ and True:` 无 handler → LLMParseError（而非静默吞掉容器）。"""
        code = AI_MOCK_PREFIX + """
try:
    if @~ MOCK:FAIL deep_fail ~ and True:
        print("no")
    print("also_no")
except:
    print("caught")
"""
        lines = run_ibci(code)
        assert "caught" in lines
        assert "no" not in lines

    def test_binop_nested_rhs_retries(self):
        """`str r = base + @~REPAIR~`：BinOp 嵌套 RHS 不确定容器透传到赋值消费者并重试。"""
        code = AI_MOCK_PREFIX + """
str base = "x"
str r = base + @~ MOCK:REPAIR:STR:ok concat_key ~
llmexcept:
    print("concat_retry")
    retry "hint"
print(r)
"""
        lines = run_ibci(code)
        assert "concat_retry" in lines
        assert "xok" in lines

    def test_ambiguous_str_condition_retry_is_bounded(self):
        """模糊字符串条件在 llmexcept 帧内重试有界：耗尽后抛错，不无限循环。

        行为表达式返回无法判定的字符串（如 "maybe"）时，is_truthy 在帧内返回
        不确定容器；重试必须在同一帧计数内收敛（max_retry 后 LLMRetryExhaustedError）。
        """
        code = AI_MOCK_PREFIX + """
try:
    while @~ MOCK:STR:maybe ambig_key ~:
        print("body")
    llmexcept:
        retry "hint"
    print("after")
except:
    print("exhausted_or_error")
"""
        lines = run_ibci(code)
        assert "exhausted_or_error" in lines
        assert "after" not in lines


class TestE2EBoolContextTyping:
    """
    布尔上下文行为表达式定型 bool（恒真陷阱修复）的 e2e 回归。

    修复前：`while @~...~ and True:` / `if not @~...~:` 中行为表达式落到
    `behavior` 占位符 → 运行期装箱为 str → "0" 按 Python 真值语义判真 → 恒真死循环。
    修复后：布尔上下文行为定型 bool，0/1 正确判定，循环正常终止。
    """

    def test_while_boolop_condition_terminates(self):
        """`while @~...~ and True:` 中行为定型 bool，TRUE/FALSE 正确判定并终止。"""
        code = AI_MOCK_PREFIX + """
int count = 0
while @~ MOCK:SEQ:[TRUE,TRUE,FALSE] w_bt ~ and True:
    count = count + 1
llmexcept:
    retry "hint"
print((str)count)
"""
        # TRUE→body(1), TRUE→body(2), FALSE→exit
        assert run_ibci(code) == ["2"]

    def test_while_boolop_condition_with_retry_terminates(self):
        """FAIL 触发 llmexcept 重试后恢复，循环仍正确终止（不恒真）。"""
        code = AI_MOCK_PREFIX + """
int count = 0
while @~ MOCK:SEQ:[TRUE,FAIL,TRUE,FALSE] w_bt2 ~ and True:
    count = count + 1
llmexcept:
    print("w_retry")
    retry "hint"
print((str)count)
"""
        lines = run_ibci(code)
        assert "w_retry" in lines
        assert "2" in lines

    def test_not_condition(self):
        """`if not @~REPAIR~:` 重试后恢复；not True → False → else 分支。"""
        code = AI_MOCK_PREFIX + """
if not @~ MOCK:REPAIR:BOOL:TRUE not_bt ~:
    print("taken")
else:
    print("not_taken")
llmexcept:
    retry "hint"
"""
        assert run_ibci(code) == ["not_taken"]

    def test_for_filter_retries(self):
        """foreach filter 是布尔位置：REPAIR 重试后恢复，两元素均通过。"""
        code = AI_MOCK_PREFIX + """
list items = ["a", "b"]
for str x in items if @~ MOCK:REPAIR:BOOL:TRUE filt_bt ~:
    print(x)
llmexcept:
    retry "hint"
"""
        assert run_ibci(code) == ["a", "b"]

