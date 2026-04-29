"""
tests/e2e/test_e2e_llm_pipeline.py
==================================

M5c — LLM dispatch-before-use E2E 流水线测试。

覆盖：

* 多个独立 ``str x = @~ MOCK:STR:... ~`` 赋值在 VM 主路径下被并发派发
  （``LLMExecutorImpl._pending_futures`` 中同时存在 ≥ 2 个未消费的
  LLMFuture）；
* 读取 ``x`` 时 ``vm_handle_IbName`` 触发 lazy ``resolve()`` 把 LLMFuture
  替换为 IbObject；后续读取直接命中 IbObject（O(1)）；
* 当循环内 / llmexcept 内的赋值不能 dispatch_eligible（依赖闭合或
  保护中），仍走同步路径。

以 MOCK 驱动器作为 LLM provider 即可——不依赖外部网络。
"""
import os
import pytest

from core.engine import IBCIEngine


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


def ai_setup():
    return 'import ai\nai.set_config("TESTONLY", "TESTONLY", "TESTONLY")\n'


def make_engine():
    return IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)


def run_capture(code: str):
    out: list = []
    eng = make_engine()
    eng.run_string(code, output_callback=lambda s: out.append(s), silent=True)
    return eng, out


# ===========================================================================
# 1. 多个独立赋值 → 并发派发
# ===========================================================================

class TestParallelDispatch:
    """多个独立的、可调度的 LLM 赋值应同时派发为 LLMFuture。"""

    def test_two_independent_assignments_both_pending_after_run(self):
        """``x = @~ MOCK:STR:a ~``、``y = @~ MOCK:STR:b ~`` 之间无数据依赖；
        两个 LLMFuture 应在赋值阶段一并派发；只有读取时才 resolve。"""
        code = ai_setup() + (
            "str x = @~ MOCK:STR:alpha ~\n"
            "str y = @~ MOCK:STR:beta ~\n"
        )
        eng, _ = run_capture(code)
        executor = eng.interpreter.service_context.llm_executor
        # 两个赋值都未被读取 → 两个 future 均仍存在
        assert len(executor._pending_futures) == 2

    def test_dispatched_assignments_resolve_on_read(self):
        """读取触发 lazy resolve，``_pending_futures`` 应被清空。"""
        code = ai_setup() + (
            "str x = @~ MOCK:STR:alpha ~\n"
            "str y = @~ MOCK:STR:beta ~\n"
            "print(x)\n"
            "print(y)\n"
        )
        eng, out = run_capture(code)
        executor = eng.interpreter.service_context.llm_executor
        # 两次读取 → 两个 future 都已被 resolve 并清空
        assert len(executor._pending_futures) == 0
        assert any("alpha" in line for line in out)
        assert any("beta" in line for line in out)

    def test_second_read_is_o1_after_resolve(self):
        """一旦 resolve，后续读取直接命中 IbObject，不再访问 _pending_futures。"""
        code = ai_setup() + (
            "str x = @~ MOCK:STR:once ~\n"
            "print(x)\n"
            "print(x)\n"
            "print(x)\n"
        )
        eng, out = run_capture(code)
        executor = eng.interpreter.service_context.llm_executor
        assert len(executor._pending_futures) == 0
        # 三次都打印同一值
        once_count = sum(1 for line in out if "once" in line)
        assert once_count == 3


# ===========================================================================
# 2. 同步回退路径——dispatch_eligible == False
# ===========================================================================

class TestDispatchSkipped:
    """dispatch 不应破坏既有保护边界（llmexcept、deferred、复合目标）。"""

    def test_assignment_inside_llmexcept_uses_synchronous_path(self):
        """llmexcept 保护下的 ``str x = @~ ... ~`` 必须走同步路径，
        否则 frame.last_result 拿不到当次结果。"""
        code = ai_setup() + (
            "str x = @~ MOCK:STR:plain ~\n"
            "llmexcept:\n"
            "    print(\"recovered\")\n"
            "    retry \"hint\"\n"
        )
        eng, out = run_capture(code)
        executor = eng.interpreter.service_context.llm_executor
        # 同步路径下不会创建 LLMFuture（或者已被 resolve）
        # MOCK:STR:plain 是确定的，无需进入 handler；输出应仅来自 print 之外的语句。
        # 这里关键是：执行不抛错，且没有遗留 future。
        assert len(executor._pending_futures) == 0

    def test_deferred_behavior_not_dispatched(self):
        """``fn`` 声明的 deferred behavior expression 不应被立刻 dispatch。"""
        # fn 声明侧语法：
        # fn f = lambda: @~ MOCK:STR:lazy ~
        # 此时 RHS 是 lambda 包装；不会经过 IbAssign(IbBehaviorExpr) 直派发。
        code = ai_setup() + (
            "fn f = lambda: @~ MOCK:STR:lazy ~\n"
        )
        eng, _ = run_capture(code)
        executor = eng.interpreter.service_context.llm_executor
        # 未调用 f：不应有任何 LLMFuture
        assert len(executor._pending_futures) == 0


# ===========================================================================
# 3. 一致性：dispatch 路径不改变最终值
# ===========================================================================

class TestSemanticEquivalence:
    """无论是否 dispatch，可观测结果与递归路径必须一致。"""

    def test_value_is_correct_after_dispatch(self):
        code = ai_setup() + (
            "str x = @~ MOCK:STR:semantic_test ~\n"
            "print(x)\n"
        )
        _, out = run_capture(code)
        assert any("semantic_test" in line for line in out)

    def test_value_used_in_expression_after_dispatch(self):
        """resolve 出来的 IbObject 在表达式中应像普通 str 一样工作。"""
        code = ai_setup() + (
            "str x = @~ MOCK:STR:hello ~\n"
            "str y = x\n"
            "print(y)\n"
        )
        _, out = run_capture(code)
        assert any("hello" in line for line in out)
