"""
tests/runtime/test_budget_guard.py

LLM 预算守卫白箱契约（round3 需求 R-3；设计：
tasks_docs/_run_observability_design.md §四）：

- parse_budget_section：无节/仅 on_exceed = None（零侵入）；形态错误 =
  BudgetConfigError（fail-fast，不静默忽略）；
- fail 模式：provider 调用前确定性拦截（InterpreterError +
  RUN_BUDGET_EXCEEDED，消息携带维度/当前/阈值）；
- warn 模式：每维度首次超限 stderr 告警一次（不重复、不阻断）+ exceeded 标记；
- 累计面：calls（成功/失败同计）/ tokens（usage 缺失 = 0）/ wall_s（monotonic）。
"""
import pytest

from core.base.diagnostics.codes import RUN_BUDGET_EXCEEDED
from core.kernel.issue import InterpreterError
from core.runtime.observability.budget import (
    BudgetConfigError, BudgetGuard, parse_budget_section,
)


class TestParseBudgetSection:
    def test_absent(self):
        assert parse_budget_section({}) is None

    def test_null_section(self):
        assert parse_budget_section({"budget": None}) is None

    def test_valid_all(self):
        spec = parse_budget_section({"budget": {
            "max_tokens": 100, "max_calls": 10, "max_wall_s": 60, "on_exceed": "fail",
        }})
        assert spec == {"limits": {"max_tokens": 100, "max_calls": 10, "max_wall_s": 60},
                        "on_exceed": "fail"}

    def test_default_on_exceed_warn(self):
        spec = parse_budget_section({"budget": {"max_calls": 5}})
        assert spec["on_exceed"] == "warn"

    def test_only_on_exceed_is_no_budget(self):
        # 仅 on_exceed 无阈值 = 无预算（零侵入语义）
        assert parse_budget_section({"budget": {"on_exceed": "fail"}}) is None

    @pytest.mark.parametrize("bad", [
        {"max_calls": -1},
        {"max_calls": 0},
        {"max_calls": "ten"},
        {"max_calls": True},          # bool 非数值语义
        {"max_wall_s": 1.5, "on_exceed": "crash"},
        {"max_calls": 1, "unknown_key": 3},
    ])
    def test_invalid_rejected(self, bad):
        with pytest.raises(BudgetConfigError):
            parse_budget_section({"budget": bad})

    def test_non_dict_section_rejected(self):
        with pytest.raises(BudgetConfigError):
            parse_budget_section({"budget": [1, 2]})


class TestBudgetGuardFail:
    def test_calls_limit_intercepts_before_call(self):
        """max_calls=1：第 1 次调用 pre-check 通过；第 2 次 pre-check 拦截。"""
        guard = BudgetGuard({"limits": {"max_calls": 1}, "on_exceed": "fail"})
        guard.check_pre_call("n1")            # 第 1 次 pre-check：calls=0 < 1，放行
        guard.record_post_call(None)          # 第 1 次完成（calls=1）
        with pytest.raises(InterpreterError) as ei:
            guard.check_pre_call("n2")        # 第 2 次 pre-check：1 >= 1 → 确定性拦截
        assert ei.value.error_code == RUN_BUDGET_EXCEEDED
        assert "calls" in ei.value.message

    def test_tokens_limit(self):
        guard = BudgetGuard({"limits": {"max_tokens": 100}, "on_exceed": "fail"})
        guard.record_post_call({"total_tokens": 60})
        guard.record_post_call({"total_tokens": 60})   # 120 >= 100
        with pytest.raises(InterpreterError):
            guard.check_pre_call(None)

    def test_usage_missing_counts_zero(self):
        guard = BudgetGuard({"limits": {"max_tokens": 1}, "on_exceed": "fail"})
        guard.record_post_call(None)          # tokens 记 0
        guard.check_pre_call(None)            # 不超（0 < 1）
        snap = guard.snapshot()
        assert snap["tokens"] == 0 and snap["calls"] == 1


class TestBudgetGuardWarn:
    def test_warn_once_per_dimension(self, capsys):
        guard = BudgetGuard({"limits": {"max_calls": 1}, "on_exceed": "warn"})
        guard.record_post_call(None)          # calls=1
        guard.record_post_call(None)          # calls=2 → 首次超限告警
        guard.record_post_call(None)          # calls=3 → 不重复告警
        errs = capsys.readouterr().err
        assert errs.count("budget exceeded") == 1
        snap = guard.snapshot()
        assert snap["exceeded"]["calls"] is True
        assert snap["calls"] == 3

    def test_warn_does_not_block(self):
        guard = BudgetGuard({"limits": {"max_calls": 1}, "on_exceed": "warn"})
        guard.record_post_call(None)
        guard.record_post_call(None)
        guard.check_pre_call(None)            # warn 模式检查无副作用
        # 下一调用仍可执行（检查不抛）
        guard.record_post_call(None)
        assert guard.snapshot()["calls"] == 3

    def test_wall_s_dimension(self):
        guard = BudgetGuard({"limits": {"max_wall_s": 0.001}, "on_exceed": "fail"})
        import time
        time.sleep(0.01)
        guard.record_post_call(None)
        with pytest.raises(InterpreterError, match="wall_s"):
            guard.check_pre_call(None)
