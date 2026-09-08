"""
core.runtime.observability.budget — run 级 LLM 预算守卫
（round3 需求 R-3；设计：tasks_docs/_run_observability_design.md §四）。

- 阈值 = api_config.json 顶层 ``budget`` 节（可选；缺省 = 无预算，零侵入）：
  ``{max_tokens, max_calls, max_wall_s, on_exceed: "warn"|"fail"}``；
- 核算点 = LLM 调用汇点（单一核算点，与 journal 同源）：
  - ``check_pre_call``：provider 调用**前**检查——fail 模式超限即
    InterpreterError(RUN_BUDGET_EXCEEDED) 确定性拦截（零浪费：不发出被拦调用）；
  - ``record_post_call``：调用后累计（calls+1；tokens += usage.total_tokens，
    usage 缺失 = 0——provider 未上报时以 calls/wall 兜底；wall = monotonic）；
    失败调用同计（调用本身即预算消耗）；
- warn 模式：每维度首次超限 stderr 告警一次（run 继续）+ exceeded 标记
  （result-json 面，批 4）；
- 核算边界（诚实记录）：wall 维度仅在 LLM 调用点检查（非轮询——两次调用间的
  长非 LLM 段不检查）；流式调用不经汇点（不入 journal 同边界）。
"""

from __future__ import annotations

import sys
import threading
import time
from typing import Any, Dict, Optional

from core.kernel.issue import InterpreterError
from core.base.diagnostics.codes import RUN_BUDGET_EXCEEDED


class BudgetConfigError(Exception):
    """budget 节形态错误（CLI 加载期 fail-fast → CFG_CONFIG_INVALID_BUDGET 面）。"""


def parse_budget_section(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """从 api_config 顶层 dict 提取并校验 budget 节（纯函数，无副作用）。

    无 budget 节 / 显式 null = None（无预算）。节存在但形态错误 =
    BudgetConfigError（fail-fast——用户显式写了预算且写错，不静默忽略）。
    """
    raw = data.get("budget")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise BudgetConfigError("budget 节必须是 JSON 对象")
    limits: Dict[str, float] = {}
    for key in ("max_tokens", "max_calls", "max_wall_s"):
        if key in raw and raw[key] is not None:
            value = raw[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
                raise BudgetConfigError(
                    f"budget.{key} 必须是正数（收到 {value!r}）"
                )
            limits[key] = value
    on_exceed = raw.get("on_exceed", "warn")
    if on_exceed not in ("warn", "fail"):
        raise BudgetConfigError(
            f'budget.on_exceed 必须是 "warn" 或 "fail"（收到 {on_exceed!r}）'
        )
    unknown = set(raw) - {"max_tokens", "max_calls", "max_wall_s", "on_exceed"}
    if unknown:
        raise BudgetConfigError(f"budget 节含未知字段 {sorted(unknown)}")
    if not limits:
        return None  # 仅 on_exceed 无阈值 = 无预算（零侵入语义）
    return {"limits": limits, "on_exceed": on_exceed}


class BudgetGuard:
    """run 级预算守卫（run 级单实例；CLI 创建、汇点消费）。"""

    def __init__(self, spec: Dict[str, Any]):
        # 键名归一化：max_tokens/max_calls/max_wall_s → tokens/calls/wall_s
        # （维度短名与检查/告警面统一用词）
        self._limits: Dict[str, float] = {
            key[len("max_"):]: value for key, value in spec["limits"].items()
        }
        self._on_exceed: str = spec["on_exceed"]
        self._lock = threading.Lock()
        self._start_mono = time.monotonic()
        self._calls = 0
        self._tokens = 0
        self._exceeded: Dict[str, bool] = {}
        self._warned: set = set()

    # ------------------------------------------------------------------ #
    # 汇点接口

    def check_pre_call(self, node_uid: Optional[str]) -> None:
        """provider 调用前检查（fail 模式超限 → InterpreterError 拦截）。"""
        with self._lock:
            if self._on_exceed != "fail":
                return
            violation = self._current_violation()
        if violation is not None:
            dim, current, limit = violation
            raise InterpreterError(
                f"LLM 运行预算超限（fail 模式拦截）：{dim} 当前 {self._fmt(dim, current)}"
                f" ≥ 阈值 {self._fmt(dim, limit)}（api_config budget 节；"
                f"调高阈值或改 on_exceed=warn 解除）",
                node_uid,
                error_code=RUN_BUDGET_EXCEEDED,
            )

    def record_post_call(self, usage: Optional[Dict[str, Any]]) -> None:
        """调用后累计（成功/失败同计；usage 缺失 = tokens 记 0）。"""
        with self._lock:
            self._calls += 1
            if isinstance(usage, dict):
                total = usage.get("total_tokens")
                if isinstance(total, (int, float)) and not isinstance(total, bool):
                    self._tokens += total
            # warn 模式：每维度首次超限告警一次
            if self._on_exceed == "warn":
                for dim, current, limit in self._violations():
                    if dim not in self._warned:
                        self._warned.add(dim)
                        self._exceeded[dim] = True
                        print(
                            f"warning: LLM budget exceeded: {dim} "
                            f"{self._fmt(dim, current)} >= {self._fmt(dim, limit)} "
                            "(warn mode; run continues)",
                            file=sys.stderr,
                        )

    # ------------------------------------------------------------------ #
    # 快照（result-json 面，批 4）

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "calls": self._calls,
                "tokens": self._tokens,
                "wall_s": round(time.monotonic() - self._start_mono, 3),
                "exceeded": {d: self._exceeded.get(d, False) for d in ("tokens", "calls", "wall_s")},
            }

    # ------------------------------------------------------------------ #

    def _current_violation(self):
        v = self._violations()
        return v[0] if v else None

    def _violations(self):
        out = []
        if "tokens" in self._limits and self._tokens >= self._limits["tokens"]:
            out.append(("tokens", self._tokens, self._limits["tokens"]))
        if "calls" in self._limits and self._calls >= self._limits["calls"]:
            out.append(("calls", self._calls, self._limits["calls"]))
        if "wall_s" in self._limits:
            wall = time.monotonic() - self._start_mono
            if wall >= self._limits["wall_s"]:
                out.append(("wall_s", wall, self._limits["wall_s"]))
        return out

    @staticmethod
    def _fmt(dim: str, value) -> str:
        if dim == "wall_s":
            return f"{value:.1f}s"
        return f"{int(value)}"
