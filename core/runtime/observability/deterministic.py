"""
core.runtime.observability.deterministic — run 级确定性执行模式守卫
（零 LLM 不变量：判定/验证路径的 D1 保证落地面）。

- 与 journal/budget 同汇点同边界（LLM 调用汇点 = 单一核算点；流式调用
  不经汇点 = 子系统既有边界）：CLI ``run --deterministic`` 创建并经引擎
  挂载，``_call_llm`` 在 provider 调用**前**拦截——被拦调用不发出（结构性
  零 LLM：无部分 LLM 态、无 API key 消耗）；
- 与 budget 分面（不同概念不同码）：budget = 用户配置阈值（warn/fail 两面、
  可超限继续/拦截）；deterministic = run 级零容忍不变量（无阈值、无 warn
  面、首个 LLM 调用即 fail-fast ``RUN_DETERMINISTIC_LLM_CALL``）；
- 审计凭证（机读"LLM 调用次数=0"）：``snapshot()`` =
  ``{"enforced": True, "llm_calls": 0}``——拦截在前 post-call 永不达，
  计数恒 0 = 结构事实（凭证非观测推断）；
- 边界（诚实记录）：守卫不跨 spawn 继承（``meta.eval`` 子进程 = 新引擎；
  quoted 表达式含 ``@~...~`` 时其 LLM 调用属子进程面——eval 环境参数
  边界同族）；流式 ``ai.stream_call`` 不经汇点（journal/budget 同边界）。
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from core.base.diagnostics.codes import RUN_DETERMINISTIC_LLM_CALL
from core.kernel.issue import InterpreterError


class DeterministicGuard:
    """run 级确定性守卫（run 级单实例；CLI 创建、汇点消费）。

    零 LLM 不变量的 fail-fast 面：provider 调用前的第一个检查点（强不变量
    优先于 budget 阈值面）；拦截上抛 ``InterpreterError``（IBCI ``try/except``
    可捕获——脚本可显式处理"确定性模式下禁止 LLM"的边界）。
    """

    def check_pre_call(self, node_uid: Optional[str]) -> None:
        """provider 调用前拦截（恒 fail-fast——确定性模式零容忍，无阈值面）。"""
        raise InterpreterError(
            "确定性执行模式（--deterministic）下禁止 LLM 调用："
            "本 run 的零 LLM 不变量在调用汇点结构性拦截（D1：判定/验证路径"
            "零 LLM）。移除此调用点、或去掉 --deterministic 以允许 LLM。",
            node_uid,
            error_code=RUN_DETERMINISTIC_LLM_CALL,
        )

    def snapshot(self) -> Dict[str, Any]:
        """审计凭证（result-json ``deterministic`` 字段，机读"LLM 调用次数=0"）。

        拦截在前 post-call 永不达——``llm_calls`` 恒 0 是结构事实（凭证非
        观测推断）；``enforced`` = 本 run 零 LLM 不变量处于生效态。
        """
        return {"enforced": True, "llm_calls": 0}
