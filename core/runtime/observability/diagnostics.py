"""
core.runtime.observability.diagnostics — 内核结构化诊断发射（诊断面）。

定位：独立语义面（诊断面），与状态面（snapshot）/事件面（EventBus 域事件）/
测试合作面（test_hooks）/渲染层（idbg）正交。职责：发射"内核为何降级 /
做了什么异常决策"（异常/降级/策略点），覆盖原 CORE_DEBUG 的观测价值。

机制（与域事件同构，经统一发射入口 ``emit_runtime_event``）：
    - 单一记录、双投影：
        投影A（开发者可见，不门控）：``warnings.warn(message, stacklevel=3)``
            —— 归属行与站点内直接 ``warnings.warn(stacklevel=2)`` 一致。
            ``message`` 缺省时生成 ``f"{code}: {detail!r}"``。
        投影B（程序化观测，受 ``observability`` 门控）：经
            ``emit_runtime_event(rc, "kernel_diagnostic", data)`` 发射。
    - 代码即数据，非发射门控（与旧 DebugLevel 本质不同）：``KDIAG_*`` 是
      事件数据（消费端过滤），不是发射开关；过滤在消费端，不在发射端。
    - rc 解析 best-effort（显式 ``rc=`` > 当前 EC > 无）；rc 不可达
      （无活跃 EC）→ 仅投影A，事件面跳过（fail-open，开发者可见性不丢）。

事件形态（schema 冻结，见 DIAGNOSTIC_DESIGN §三）::

    {"type": "kernel_diagnostic",
     "data": {"code": KDIAG_*, "detail": {...}, "message": "..."}}
"""

from __future__ import annotations

import warnings
from typing import Any, Dict, Optional

from core.runtime.frame import get_current_execution_context
from core.runtime.observability.events import emit_runtime_event
from core.runtime.shared.env_limits import is_environment_limit
from core.base.diagnostics.codes import KDIAG_RUNTIME_ENV_LIMIT


def kernel_diagnostic(
    code: str,
    detail: Optional[Dict[str, Any]] = None,
    message: Optional[str] = None,
    *,
    rc: Any = None,
) -> None:
    """记录一条内核诊断（异常/降级/策略）。

    投影A（开发者可见，不门控）：``warnings.warn(message, stacklevel=3)``，
    归属行与站点内直接 ``warnings.warn(stacklevel=2)`` 一致；
    ``message`` 缺省时生成 ``f"{code}: {detail!r}"``。
    投影B（程序化观测，受 ``observability`` 门控）：
    ``rc = rc or (get_current_execution_context().runtime_context)``；
    rc 不可达 → 仅投影A；observability 关 → 事件跳过，警告保留。
    经 ``emit_runtime_event`` 统一发射入口（机制同构，零订阅者零成本）。
    """
    if message is None:
        message = f"{code}: {detail!r}"
    warnings.warn(message, stacklevel=3)

    if rc is None:
        ec = get_current_execution_context()
        rc = ec.runtime_context if ec is not None else None
    if rc is None:
        return
    emit_runtime_event(
        rc,
        "kernel_diagnostic",
        {"code": code, "detail": detail or {}, "message": message},
    )


def handle_environment_limit(exc: BaseException, *, rc: Any = None) -> bool:
    """环境限制异常的语义错误包装防护（PT-DEBT-9）。

    若 ``exc`` 是环境限制异常（栈溢出 / 内存耗尽 / 系统错误），发射
    ``KDIAG_RUNTIME_ENV_LIMIT`` 诊断并返回 ``True``（调用方应原样 ``raise``
    保留根因，不得包装成语义错误）；否则返回 ``False``。

    用法（VM 语义错误包装站点）::

        except Exception as e:
            if handle_environment_limit(e, rc=executor.runtime_context):
                raise
            raise RuntimeError(f"VM: Call failed: {e}") from e
    """
    if not is_environment_limit(exc):
        return False
    kernel_diagnostic(
        KDIAG_RUNTIME_ENV_LIMIT,
        {"exc_type": type(exc).__name__, "message": str(exc)},
        message=f"环境限制异常 {type(exc).__name__}: 非语义错误，保留根因传播",
        rc=rc,
    )
    return True
