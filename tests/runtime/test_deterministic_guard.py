"""
tests/runtime/test_deterministic_guard.py

确定性执行守卫白箱契约（P4 R-C：run 级零 LLM 不变量；设计：
``_p4_deterministic_mode_design.md`` §2）：

- **单元面**（DeterministicGuard）：``check_pre_call`` 恒 fail-fast
  （``InterpreterError`` + ``RUN_DETERMINISTIC_LLM_CALL``，无阈值/warn 面）；
  ``snapshot()`` = 审计凭证 ``{"enforced": True, "llm_calls": 0}``（拦截在前
  post-call 永不达——计数恒 0 = 结构事实）；
- **引擎面**（``deterministic_guard`` 参数，同 budget_guard 装配路径）：
  挂 guard 跑纯代码 = 无副作用（零侵入）；挂 guard 跑 ``@~...~``（mock 模式）
  = 调用汇点 provider 前拦截（``RUN_DETERMINISTIC_LLM_CALL``，IBCI try/except
  可捕获）；
- **与 budget 分面**：deterministic 检查在 budget 之前（强不变量优先）——
  双 guard 组合时 deterministic 码先出（budget 阈值面不触发）。

注：CLI ``--deterministic`` 面 + M1 e2e（逐字节可复现 + 凭证）归同批次 e2e。
"""

import pytest

from core.base.diagnostics.codes import RUN_DETERMINISTIC_LLM_CALL, RUN_BUDGET_EXCEEDED
from core.kernel.issue import InterpreterError
from core.runtime.observability.budget import BudgetGuard
from core.runtime.observability.deterministic import DeterministicGuard


class TestDeterministicGuardUnit:
    def test_check_pre_call_always_intercepts(self):
        """零容忍：任意 node_uid 下 check_pre_call 恒 fail-fast（无阈值面）。"""
        guard = DeterministicGuard()
        with pytest.raises(InterpreterError) as ei:
            guard.check_pre_call("node-1")
        assert ei.value.error_code == RUN_DETERMINISTIC_LLM_CALL
        assert "确定性执行模式" in ei.value.message
        # 第二次同样拦截（无状态面——非累计阈值语义）
        with pytest.raises(InterpreterError) as ei2:
            guard.check_pre_call(None)
        assert ei2.value.error_code == RUN_DETERMINISTIC_LLM_CALL

    def test_snapshot_credential_form(self):
        """审计凭证 = 机读"LLM 调用次数=0"（enforced + llm_calls）。"""
        guard = DeterministicGuard()
        snap = guard.snapshot()
        assert snap == {"enforced": True, "llm_calls": 0}


class TestDeterministicGuardEngine:
    def test_pure_code_unaffected(self, engine):
        """零侵入：挂 guard 跑纯代码 = 与无 guard 同行为（无 LLM 调用点）。"""
        code = "str x = '1'\nprint(int(x) + 41)\n"
        lines = []
        engine.run_string(
            code,
            output_callback=lambda t: lines.append(str(t)),
            silent=True,
            deterministic_guard=DeterministicGuard(),
        )
        assert lines == ["42"]

    def test_behavior_expr_intercepted(self, engine):
        """@~...~（mock 模式）挂 guard = 调用汇点拦截（provider 前，
        RUN_DETERMINISTIC_LLM_CALL）。"""
        code = "import ai\nai.set_mock_mode()\nstr x = @~ MOCK:STR:alpha ~\nprint(x)\n"
        with pytest.raises(InterpreterError) as ei:
            engine.run_string(
                code,
                silent=True,
                deterministic_guard=DeterministicGuard(),
            )
        assert ei.value.error_code == RUN_DETERMINISTIC_LLM_CALL

    def test_behavior_expr_without_guard_baseline(self, engine):
        """基线对照：同代码无 guard = mock 正常产出（拦截面非 mock 面）。"""
        code = "import ai\nai.set_mock_mode()\nstr x = @~ MOCK:STR:alpha ~\nprint(x)\n"
        lines = []
        engine.run_string(code, output_callback=lambda t: lines.append(str(t)), silent=True)
        assert lines == ["alpha"]

    def test_guard_intercepts_before_budget(self, engine):
        """双 guard 组合：deterministic 在 budget 之前检查（强不变量优先）——
        拦截码 = RUN_DETERMINISTIC_LLM_CALL（budget 阈值面不触发）。"""
        code = "import ai\nai.set_mock_mode()\nstr x = @~ MOCK:STR:alpha ~\nprint(x)\n"
        budget = BudgetGuard({"limits": {"max_calls": 1}, "on_exceed": "fail"})
        with pytest.raises(InterpreterError) as ei:
            engine.run_string(
                code,
                silent=True,
                budget_guard=budget,
                deterministic_guard=DeterministicGuard(),
            )
        assert ei.value.error_code == RUN_DETERMINISTIC_LLM_CALL
        # budget 未消耗（拦截在 budget pre-check 之前）
        assert budget.snapshot()["calls"] == 0


class TestDeterministicGuardCatchability:
    def test_try_except_capturable(self, engine):
        """IBCI try/except 可捕获（脚本可显式处理"确定性模式禁 LLM"边界）。

        注：行为值 future 按需解析——错误在值被**消费**时显形（既有语义，
        见 KNOWN_LIMITS §二十七）；本测试消费 x（print）触发解析面。
        """
        code = (
            "import ai\n"
            "ai.set_mock_mode()\n"
            "try:\n"
            "    str x = @~ MOCK:STR:alpha ~\n"
            "    print(x)\n"
            "except Exception as e:\n"
            "    print(e.message)\n"
            "print('after')\n"
        )
        lines = []
        engine.run_string(
            code,
            output_callback=lambda t: lines.append(str(t)),
            silent=True,
            deterministic_guard=DeterministicGuard(),
        )
        assert "llm-ran-wrong" not in lines
        assert any(RUN_DETERMINISTIC_LLM_CALL in l for l in lines)
        assert lines[-1] == "after"
