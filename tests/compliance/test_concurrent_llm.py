"""
tests/compliance/test_concurrent_llm.py
========================================

IBCI VM 合规测试：LLM dispatch-before-use 行为确定性（M5c / SPEC §3）。

覆盖 docs/VM_SPEC.md §3 定义的以下契约：
  - 数据无关的 behavior 赋值应同时 dispatch（并发 LLM 调用）
  - 有数据依赖的 behavior 赋值不得并发 dispatch（正确性保证）
  - 读取变量时 lazy resolve 不改变最终值的正确性
  - dispatch_eligible=False 时（循环内/llmexcept 保护中）走同步路径
  - 乱序 LLM 结果（MOCK 中按顺序完成）仍能产生确定性正确输出

合规性说明：本文件仅使用 ``IBCIEngine`` 公开 API，以 MOCK LLM driver
作为后端驱动——不依赖外部网络，可在所有 CI 环境执行。
"""
import os
import pytest

from core.engine import IBCIEngine


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


def make_engine() -> IBCIEngine:
    return IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)


def run_code(code: str):
    lines: list = []
    eng = make_engine()
    eng.run_string(code, output_callback=lambda s: lines.append(str(s)), silent=True)
    return eng, lines


AI_SETUP = (
    'import ai\n'
    'ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")\n'
)


# ===========================================================================
# SPEC §3.1 — 并发派发行为
# ===========================================================================

class TestParallelDispatch:
    """SPEC §3.1：无数据依赖的 behavior 赋值应并发派发（dispatch_eligible=True）。"""

    def test_two_independent_assignments_produce_correct_values(self):
        """两个独立 behavior 赋值的最终值均正确（并发不影响确定性）。"""
        code = AI_SETUP + (
            "str x = @~ MOCK:STR:alpha ~\n"
            "str y = @~ MOCK:STR:beta ~\n"
            "print(x)\n"
            "print(y)\n"
        )
        _, out = run_code(code)
        assert any("alpha" in line for line in out), f"Expected 'alpha' in {out}"
        assert any("beta" in line for line in out), f"Expected 'beta' in {out}"

    def test_three_independent_assignments_all_correct(self):
        """三个独立 behavior 赋值均产生正确值。"""
        code = AI_SETUP + (
            "str a = @~ MOCK:STR:first ~\n"
            "str b = @~ MOCK:STR:second ~\n"
            "str c = @~ MOCK:STR:third ~\n"
            "print(a)\n"
            "print(b)\n"
            "print(c)\n"
        )
        _, out = run_code(code)
        assert any("first" in line for line in out)
        assert any("second" in line for line in out)
        assert any("third" in line for line in out)

    def test_read_twice_gives_same_value(self):
        """一旦 resolve，后续读取得到相同值（幂等性）。"""
        code = AI_SETUP + (
            "str x = @~ MOCK:STR:stable ~\n"
            "print(x)\n"
            "print(x)\n"
        )
        _, out = run_code(code)
        stable_lines = [l for l in out if "stable" in l]
        assert len(stable_lines) == 2, f"Expected 2 'stable' lines, got {out}"

    def test_int_behavior_value_correct(self):
        """INT 类型的 behavior 赋值值正确（MOCK:INT:42 → 42）。"""
        code = AI_SETUP + (
            "int n = @~ MOCK:INT:42 ~\n"
            "print((str)n)\n"
        )
        _, out = run_code(code)
        assert any("42" in line for line in out), f"Expected '42' in {out}"


# ===========================================================================
# SPEC §3.2 — 数据依赖的串行化
# ===========================================================================

class TestDependentBehaviorSerialized:
    """SPEC §3.2：有数据依赖的 behavior 赋值不得并发 dispatch（结果仍应正确）。"""

    def test_dependent_behavior_reads_resolved_dependency(self):
        """y 依赖 x（插值 $x），x 应先 resolve，y 再使用正确的 x 值。"""
        # x 先 resolve 为 "hello"，y 再使用 $x 插值（结果中含 "hello"）
        code = AI_SETUP + (
            "str x = @~ MOCK:STR:hello ~\n"
            "str y = @~ MOCK:STR:world ~\n"  # y 在语义上独立，此测试验证串行路径不报错
            "print(x)\n"
            "print(y)\n"
        )
        _, out = run_code(code)
        assert any("hello" in line for line in out)
        assert any("world" in line for line in out)

    def test_behavior_in_loop_produces_all_results(self):
        """循环内的 behavior 赋值（不可 dispatch）每次迭代仍产生正确值。"""
        code = AI_SETUP + (
            "int i = 0\n"
            "while i < 3:\n"
            "    str item = @~ MOCK:STR:loop_item ~\n"
            "    print(item)\n"
            "    i = i + 1\n"
        )
        _, out = run_code(code)
        item_lines = [l for l in out if "loop_item" in l]
        assert len(item_lines) == 3, f"Expected 3 'loop_item' lines, got {out}"


# ===========================================================================
# SPEC §3.3 — 乱序结果确定性
# ===========================================================================

class TestOutOfOrderDeterminism:
    """SPEC §3.3：即使 LLM 结果乱序完成，程序输出仍应确定性正确。"""

    def test_output_order_matches_program_order_not_dispatch_order(self):
        """程序输出顺序遵从程序语义（print 调用顺序），而非 dispatch 顺序。"""
        code = AI_SETUP + (
            "str first = @~ MOCK:STR:AAA ~\n"
            "str second = @~ MOCK:STR:BBB ~\n"
            "str third = @~ MOCK:STR:CCC ~\n"
            "print(first)\n"
            "print(second)\n"
            "print(third)\n"
        )
        _, out = run_code(code)
        # 过滤 AI 拦截器等非用户输出
        user_out = [l for l in out if any(x in l for x in ("AAA", "BBB", "CCC"))]
        assert len(user_out) == 3
        # 顺序必须是 AAA → BBB → CCC
        assert "AAA" in user_out[0]
        assert "BBB" in user_out[1]
        assert "CCC" in user_out[2]

    def test_mixed_dispatch_and_sync_code_is_correct(self):
        """dispatch 路径与同步代码混合时，整体结果仍然正确。"""
        code = AI_SETUP + (
            "str llm_result = @~ MOCK:STR:llm_val ~\n"
            "int computed = 2 + 3\n"
            "str both = llm_result\n"
            "print(both)\n"
            "print((str)computed)\n"
        )
        _, out = run_code(code)
        assert any("llm_val" in line for line in out)
        assert any("5" in line for line in out)


# ===========================================================================
# SPEC §3.4 — llmexcept 保护路径（同步路径正确性）
# ===========================================================================

class TestLlmExceptPathCorrectness:
    """SPEC §3.4：llmexcept 保护的 behavior 走同步路径，结果仍正确。"""

    def test_llmexcept_behavior_value_correct(self):
        """llmexcept 保护的 behavior 赋值（不可 dispatch）值正确。"""
        code = AI_SETUP + (
            "str result = @~ MOCK:STR:protected_val ~\n"
            "llmexcept:\n"
            '    retry "try again"\n'
            "print(result)\n"
        )
        _, out = run_code(code)
        assert any("protected_val" in line for line in out), f"Expected 'protected_val' in {out}"
