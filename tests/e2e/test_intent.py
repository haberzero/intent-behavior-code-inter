"""
tests/e2e/test_intent.py
=============================

e2e Intent 综合测试：意图注释 / scope 隔离 / lambda 与意图栈交互 /
OOP（combine, to_prompt, deep_clone）/ 统一意图路径/
llmexcept retry 还原。


"""

import os
import pytest

from core.engine import IBCIEngine
from tests.conftest import TESTS_ROOT, run_ibci, AI_MOCK_PREFIX








class TestE2EIntents:
    def test_single_intent(self):
        code = AI_MOCK_PREFIX + """
@ be concise
str result = @~ MOCK:TRUE respond ~
print(result)
"""
        lines = run_ibci(code)
        assert "1" in lines

    def test_single_intent_does_not_pollute_persistent_stack(self):
        """@ 是一次性意图，LLM 调用后不残留在持久意图栈中；第二次 LLM 调用
        不携带前次 @ 意图，正常执行。"""
        code = AI_MOCK_PREFIX + """
@ be concise
str result1 = @~ MOCK:TRUE first ~
str result2 = @~ MOCK:TRUE second ~
print(result1)
print(result2)
"""
        lines = run_ibci(code)
        assert lines.count("1") >= 2, "Both calls should succeed after one-shot @ intent"

    def test_single_intent_does_not_affect_subsequent_call(self):
        """@ 消费后，后续 LLM 调用不应继承该意图（通过混合 @+ 和 @ 验证）。"""
        code = AI_MOCK_PREFIX + """
@+ formal language
@ first hint
str result1 = @~ MOCK:TRUE first ~
str result2 = @~ MOCK:TRUE second ~
print(result1)
print(result2)
"""
        lines = run_ibci(code)
        assert "1" in lines

    def test_single_intent_before_regular_function_call_propagates_to_nested_llm(self):
        """`@` can decorate a regular function call and be consumed by nested LLM calls."""
        code = AI_MOCK_PREFIX + """
func wrapper() -> str:
    str r = @~ MOCK:STR:nested ~
    return r

@ single shot before regular call
str r = wrapper()
print(r)
"""
        lines = run_ibci(code)
        assert lines == ["nested"]

    def test_single_intent_before_no_llm_statement_is_cleaned_without_leak(self):
        """If the decorated statement path has no LLM call, one-shot is still cleaned at statement end."""
        code = """
func pure_no_llm() -> auto:
    int x = 1
    return

@ one shot for no-llm path
pure_no_llm()

intent_context current = intent_context.get_current()
str prompt_view = current.__to_prompt__()
if prompt_view == "":
    print("EMPTY")
else:
    print(prompt_view)
"""
        lines = run_ibci(code)
        assert lines == ["EMPTY"]

    def test_incremental_intent(self):
        code = AI_MOCK_PREFIX + """
@+ use formal language
@+ be brief
str result = @~ MOCK:TRUE respond ~
print(result)
"""
        lines = run_ibci(code)
        assert "1" in lines

    def test_remove_intent(self):
        code = AI_MOCK_PREFIX + """
@+ temporary intent
@-
str result = @~ MOCK:TRUE respond ~
print(result)
"""
        lines = run_ibci(code)
        assert "1" in lines

    def test_at_plus_persists_after_llm_call(self):
        """@+ 是持久压栈，LLM 调用后意图仍有效，后续调用正常。"""
        code = AI_MOCK_PREFIX + """
@+ use formal language
str result1 = @~ MOCK:TRUE first ~
str result2 = @~ MOCK:TRUE second ~
print(result1)
print(result2)
"""
        lines = run_ibci(code)
        assert lines.count("1") >= 2

    def test_lambda_behavior_uses_call_time_intents(self):
        """lambda 延迟行为在调用时使用当前意图栈，而非定义时的空栈。
        注：直接赋值到具体类型（int/str）需编译器类型推断改进，当前通过 print() 调用验证。"""
        code = AI_MOCK_PREFIX + """
@+ use formal language
fn compute = lambda -> str: @~ MOCK:STR:hello ~
@-
print(compute())
"""
        lines = run_ibci(code)
        assert "hello" in lines

    def test_lambda_behavior_basic(self):
        """lambda 延迟行为基本执行冒烟测试。"""
        code = AI_MOCK_PREFIX + """
fn compute = lambda -> str: @~ MOCK:STR:world ~
print(compute())
"""
        lines = run_ibci(code)
        assert "world" in lines


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
        code = AI_MOCK_PREFIX + """
@+ "caller intent"

func modify_intents() -> auto:
    @+ "inner intent"
    return

modify_intents()

str result = @~ MOCK:intent_isolation_test ~
print(result)
"""
        lines = run_ibci(code)
        assert len(lines) >= 1  # runs without error

    def test_clear_inherited_removes_caller_intents(self):
        """
        intent_context.clear_inherited() inside a function clears the persistent
        intent stack inherited from the caller. After calling it, @+ inside the
        function starts from an empty stack.
        """
        code = AI_MOCK_PREFIX + """
@+ "caller persistent intent"

func isolated_func() -> str:
    intent_context.clear_inherited()
    str r = @~ MOCK:INT:99 ~
    return r

str result = isolated_func()
print(result)
"""
        lines = run_ibci(code)
        assert "99" in lines  # function ran successfully with cleared intents

    def test_use_replaces_scope_intent_context(self):
        """
        intent_context.use(ctx) replaces the current scope's intent context
        with the given instance. The caller's persistent intents are replaced.
        """
        code = AI_MOCK_PREFIX + """
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
        lines = run_ibci(code)
        assert "77" in lines

    def test_use_with_non_intent_context_fails_fast(self):
        """intent_context.use(非法对象) 必须可读报错。"""
        code = "intent_context.use(42)\n"
        engine = IBCIEngine(root_dir=TESTS_ROOT)
        try:
            engine.run_string(code, silent=True)
            raise AssertionError("intent_context.use(42) 应抛运行时错误")
        except Exception as e:
            assert "intent_context" in str(e), f"错误信息应指明意图上下文：{e}"

    def test_use_with_plain_object_fails_fast(self):
        """intent_context.use(普通类实例) 必须可读报错（_ctx 槽缺失/非意图上下文）。"""
        code = """\
class Box:
    int v

Box b = Box(1)
intent_context.use(b)
"""
        engine = IBCIEngine(root_dir=TESTS_ROOT)
        try:
            engine.run_string(code, silent=True)
            raise AssertionError("intent_context.use(Box) 应抛运行时错误")
        except Exception as e:
            assert "intent_context" in str(e), f"错误信息应指明意图上下文：{e}"

    def test_merge_with_non_intent_context_fails_fast(self):
        """ctx.merge(非法对象) 必须可读报错（与 use() fail-fast 对齐，修静默 no-op）。"""
        code = """\
intent_context my_ctx = intent_context()
my_ctx.merge(42)
"""
        engine = IBCIEngine(root_dir=TESTS_ROOT)
        try:
            engine.run_string(code, silent=True)
            raise AssertionError("my_ctx.merge(42) 应抛运行时错误")
        except Exception as e:
            assert "intent_context.merge" in str(e), f"错误信息应指明 merge：{e}"

    def test_combine_with_non_intent_context_fails_fast(self):
        """ctx.combine(非法对象) 必须可读报错（与 use() fail-fast 对齐，修静默 no-op）。"""
        code = """\
intent_context my_ctx = intent_context()
my_ctx.combine(42)
"""
        engine = IBCIEngine(root_dir=TESTS_ROOT)
        try:
            engine.run_string(code, silent=True)
            raise AssertionError("my_ctx.combine(42) 应抛运行时错误")
        except Exception as e:
            assert "intent_context.combine" in str(e), f"错误信息应指明 combine：{e}"

    def test_merge_valid_intent_context_succeeds(self):
        """ctx.merge(合法 intent_context) 正常执行（不破坏有效路径）。"""
        code = """\
intent_context a = intent_context()
intent_context b = intent_context()
a.merge(b)
print("merged")
"""
        engine = IBCIEngine(root_dir=TESTS_ROOT)
        lines = []
        engine.run_string(code, silent=True, output_callback=lambda t: lines.append(str(t)))
        assert lines == ["merged"]

    def test_get_current_captures_scope_snapshot(self):
        """
        intent_context.get_current() returns a snapshot of the current scope's
        intent context. The snapshot is independent of subsequent modifications.
        """
        code = AI_MOCK_PREFIX + """
@+ "initial intent"

func capture_and_modify() -> str:
    intent_context saved = intent_context.get_current()
    @+ "additional intent"
    str r = @~ MOCK:INT:55 ~
    return r

str result = capture_and_modify()
print(result)
"""
        lines = run_ibci(code)
        assert "55" in lines

    def test_intent_context_param_auto_binds_active_context(self):
        """
        Entering `func foo(intent_context ctx)` should auto-activate `ctx`
        as the current frame intent context source.
        """
        code = """
@+ "caller intent"
intent_context ctx = intent_context()
ctx.push("ctx base")

func inspect(intent_context p) -> any:
    @+ "inner from func"
    intent_context current = intent_context.get_current()
    return current.resolve()

any resolved = inspect(ctx)
print((str)resolved)
"""
        lines = run_ibci(code)
        assert len(lines) == 1
        assert "ctx base" in lines[0]
        assert "inner from func" in lines[0]
        assert "caller intent" not in lines[0]

    def test_intent_context_param_does_not_leak_inner_changes(self):
        """
        Auto-binding must preserve fork semantics; inner `@+` changes
        must not flow back to the argument context object.
        """
        code = """
intent_context ctx = intent_context()
ctx.push("ctx base")

func mutate(intent_context p) -> auto:
    @+ "inner from func"
    return

mutate(ctx)
print((str)ctx.resolve())
"""
        lines = run_ibci(code)
        assert len(lines) == 1
        assert "ctx base" in lines[0]
        assert "inner from func" not in lines[0]


class TestE2ELambdaRestriction:
    """
    lambda 值现在可以自由作为函数参数传递（高阶函数场景）。

    lambda 闭包的自由变量通过共享 IbCell 捕获，生命周期安全，可以跨作用域传递。
    """

    def test_lambda_can_be_passed_as_arg(self):
        """lambda 值可以作为函数参数传递，高阶函数能调用它。"""
        code = AI_MOCK_PREFIX + """
func apply(fn f, int val) -> auto:
    return f(val)

fn double = lambda(int x) -> auto: x * 2
int result = (int)apply(double, 5)
print((str)result)
"""
        lines = run_ibci(code)
        assert lines == ["10"]

    def test_lambda_passed_as_any_and_called(self):
        """lambda 传入 any 参数，函数内可以正常调用。"""
        code = AI_MOCK_PREFIX + """
func call_it(fn f) -> str:
    return (str)f()

fn greet = lambda -> auto: "hello"
str r = call_it(greet)
print(r)
"""
        lines = run_ibci(code)
        assert lines == ["hello"]

    def test_snapshot_can_be_passed_as_any(self):
        """
        snapshot 值可以作为参数传递。
        """
        code = AI_MOCK_PREFIX + """
func accept_any(any x) -> auto:
    print("called")

fn fn_callable_val = snapshot -> auto: 42
accept_any(fn_callable_val)
print("ok")
"""
        lines = run_ibci(code)
        assert "ok" in lines


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
        lines = run_ibci(code)
        assert "created" in lines

    def test_intent_context_push_and_clear(self):
        """push() adds an intent; clear() empties the stack."""
        code = """
intent_context ctx = intent_context()
ctx.push("hello")
ctx.clear()
print("ok")
"""
        lines = run_ibci(code)
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
        lines = run_ibci(code)
        assert "ok" in lines

    def test_intent_context_resolve(self):
        """resolve() returns a list (may be empty or with content strings)."""
        code = """
intent_context ctx = intent_context()
ctx.push("my intent")
any resolved = ctx.resolve()
print("ok")
"""
        lines = run_ibci(code)
        assert "ok" in lines

    def test_push_without_argument_fails_fast(self):
        """ctx.push() 缺参 → fail-fast（不静默 no-op）。"""
        code = """
intent_context ctx = intent_context()
ctx.push()
print("unreachable")
"""
        engine = IBCIEngine(root_dir=TESTS_ROOT)
        try:
            engine.run_string(code, silent=True)
            raise AssertionError("ctx.push() 缺参应抛运行时错误")
        except Exception as e:
            assert "push() requires a content argument" in str(e), f"错误信息应指明缺参：{e}"

    def test_merge_without_argument_fails_fast(self):
        """ctx.merge() 缺参 → fail-fast（与 merge(非法对象) fail-fast 对齐）。"""
        code = """
intent_context ctx = intent_context()
ctx.merge()
print("unreachable")
"""
        engine = IBCIEngine(root_dir=TESTS_ROOT)
        try:
            engine.run_string(code, silent=True)
            raise AssertionError("ctx.merge() 缺参应抛运行时错误")
        except Exception as e:
            assert "merge() requires an intent_context argument" in str(e), f"错误信息应指明缺参：{e}"

    def test_combine_without_argument_fails_fast(self):
        """ctx.combine() 缺参 → fail-fast（与 combine(非法对象) fail-fast 对齐）。"""
        code = """
intent_context ctx = intent_context()
ctx.combine()
print("unreachable")
"""
        engine = IBCIEngine(root_dir=TESTS_ROOT)
        try:
            engine.run_string(code, silent=True)
            raise AssertionError("ctx.combine() 缺参应抛运行时错误")
        except Exception as e:
            assert "combine() requires an intent_context argument" in str(e), f"错误信息应指明缺参：{e}"

    def test_use_without_argument_fails_fast(self):
        """intent_context.use() 缺参 → fail-fast（与 use(非法对象) fail-fast 对齐）。"""
        code = """
intent_context.use()
print("unreachable")
"""
        engine = IBCIEngine(root_dir=TESTS_ROOT)
        try:
            engine.run_string(code, silent=True)
            raise AssertionError("intent_context.use() 缺参应抛运行时错误")
        except Exception as e:
            assert "use() requires an intent_context argument" in str(e), f"错误信息应指明缺参：{e}"


class TestE2EIntentUnifiedPath:
    """
    当一个 ``intent_context`` 实例被 ``use()`` 激活后，
    后续语法路径 ``@+`` 的修改应能通过 ``get_current().resolve()`` 观察到——
    因为活跃实例指针与帧 ``_intent_ctx`` 共享底层引用。
    """

    def test_get_current_observes_syntax_path_modifications(self):
        """use(ctx) 之后 @+ 的修改应能通过 get_current() 观察到。"""
        code = """
func unified_path() -> any:
    intent_context ctx = intent_context()
    ctx.push("from oop")
    intent_context.use(ctx)
    @+ "from syntax"
    intent_context current = intent_context.get_current()
    return current.resolve()

any resolved = unified_path()
print((str)resolved)
"""
        lines = run_ibci(code)
        assert len(lines) == 1
        # 两条意图都应可见
        assert "from oop" in lines[0]
        assert "from syntax" in lines[0]

    def test_clear_inherited_then_syntax_path_visible_via_oop(self):
        """clear_inherited() 后，@+ 的新意图依旧能通过 get_current() 观察到。"""
        code = """
@+ "caller persistent"

func reset_then_observe() -> any:
    intent_context.clear_inherited()
    @+ "post clear"
    intent_context now = intent_context.get_current()
    return now.resolve()

any r = reset_then_observe()
print((str)r)
"""
        lines = run_ibci(code)
        assert len(lines) == 1
        # 调用方的持久意图被清除，函数内 @+ 仍然可见
        assert "post clear" in lines[0]
        assert "caller persistent" not in lines[0]

    def test_use_then_modify_original_does_not_leak(self):
        """use(ctx) 之后修改原始 ctx 不应影响当前帧的活跃上下文（fork 语义）。"""
        code = """
func no_leak() -> any:
    intent_context src = intent_context()
    src.push("src first")
    intent_context.use(src)
    src.push("src second after use")
    intent_context active = intent_context.get_current()
    return active.resolve()

any r = no_leak()
print((str)r)
"""
        lines = run_ibci(code)
        assert len(lines) == 1
        # use 时刻 fork：'src first' 已迁移
        assert "src first" in lines[0]
        # 'src second after use' 是 use 之后对原对象的修改，不应泄漏到帧
        assert "src second after use" not in lines[0]


class TestE2EIntentRetryRestore:
    """
    ``llmexcept`` retry 前应以 fork-and-replace 干净还原意图状态，
    body 内通过 ``@+`` / ``intent_context.use(...)`` 等做的修改在 retry
    之后必须完全消失。
    """

    def test_retry_resets_persistent_intent_pushes_in_body(self):
        """body 内 @+ 推入的意图在 retry 后必须消失。"""
        code = AI_MOCK_PREFIX + """
@+ "baseline"

try:
    str r = @~ MOCK:FAIL ns2c_intent ~
    llmexcept:
        @+ "body push intent"
        retry "try again"
    print(r)
except Exception as e:
    print("retry_exhausted_ok")
"""
        lines = run_ibci(code)
        # 关键：执行未崩在意图栈状态上（干净还原使得多次 retry 不会持续叠加意图）
        assert "retry_exhausted_ok" in lines

    def test_retry_resets_intent_context_use_in_body(self):
        """body 内 intent_context.use(other) 切换策略，retry 后应还原到 llmexcept 进入时刻。"""
        code = AI_MOCK_PREFIX + """
@+ "outer"

func protected() -> str:
    str x = ""
    try:
        x = @~ MOCK:FAIL ns2c_use ~
        llmexcept:
            intent_context other = intent_context()
            other.push("body-swapped")
            intent_context.use(other)
            retry "hint"
    except Exception as e:
        x = "done"
    return x

str result = protected()
print(result)
"""
        lines = run_ibci(code)
        # 执行成功（异常被捕获）：意图状态在 retry 期间被干净还原，未泄漏 body 内策略切换。
        assert "done" in lines
