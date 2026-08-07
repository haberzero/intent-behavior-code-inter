"""
tests/runtime/test_kernel_diagnostic.py
=======================================

诊断面（PT-FEAT-9）发射 helper 单测：``kernel_diagnostic``。

锁定：
- 投影A（开发者可见，不门控）：总是产生 ``UserWarning``，文案逐字保留，
  ``message`` 缺省时生成 ``f"{code}: {detail!r}"``。
- 投影B（程序化观测，受 observability 门控）：显式 ``rc=`` 时事件送达订阅者；
  observability 关 → 事件不发射、警告保留。
- rc 解析 best-effort：无活跃 EC 且未传 rc → 仅警告面，事件面跳过。
- stacklevel 归属：警告归属到调用方调用行（helper 引入间接帧后对齐原归属）。
"""
import warnings

import pytest

from core.base.diagnostics.codes import KDIAG_PROTOCOL_FROM_PROMPT_FALLBACK
from core.runtime.observability.diagnostics import kernel_diagnostic


class TestWarningProjection:
    """投影A：警告不门控、文案逐字、缺省 message 生成式。"""

    def test_warns_with_explicit_message(self):
        with pytest.warns(UserWarning, match="parse failed for Point: ValueError"):
            kernel_diagnostic(
                code=KDIAG_PROTOCOL_FROM_PROMPT_FALLBACK,
                detail={"type_name": "Point"},
                message="__from_prompt__ parse failed for Point: ValueError(x)",
            )

    def test_warns_with_default_message(self):
        """message 缺省 → f"{code}: {detail!r}"。"""
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            kernel_diagnostic(
                code=KDIAG_PROTOCOL_FROM_PROMPT_FALLBACK,
                detail={"type_name": "Point"},
            )
        assert len(caught) == 1
        assert isinstance(caught[0].message, UserWarning)
        assert KDIAG_PROTOCOL_FROM_PROMPT_FALLBACK in str(caught[0].message)
        assert "Point" in str(caught[0].message)

    def test_warns_even_without_rc(self):
        """无 rc 且无活跃 EC → 仅警告面（fail-open），不抛错。"""
        with pytest.warns(UserWarning, match="parse failed"):
            kernel_diagnostic(
                code=KDIAG_PROTOCOL_FROM_PROMPT_FALLBACK,
                detail={"type_name": "Point"},
                message="parse failed",
            )


class TestStacklevelAttribution:
    """stacklevel 归属：警告归属到 helper 的调用方调用行（对齐原 stacklevel=2）。

    原站点行为：``warnings.warn(msg, stacklevel=2)`` → 归属到站点函数的**调用方**
    （即触发站点逻辑的外层调用行）。helper 引入一层间接帧，故用 ``stacklevel=3``
    对齐：归属到调用 ``kernel_diagnostic`` 的站点函数的调用方。
    """

    def _emit_from_here(self):
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            kernel_diagnostic(
                code=KDIAG_PROTOCOL_FROM_PROMPT_FALLBACK,
                detail={},
                message="attribution probe",
            )
            return caught[0]

    def test_warning_attributes_to_site_caller(self):
        """归属行 = 调用站点函数的外层行（此处为 ``_emit_from_here()`` 调用行）。"""
        warning = self._emit_from_here()
        assert warning.filename == __file__
        # 归属行应为本测试中调用站点函数的那一行（stacklevel=3 已跳过 helper
        # 与站点函数两层间接帧）
        with open(__file__, encoding="utf-8") as f:
            line = f.readlines()[warning.lineno - 1]
        assert "_emit_from_here()" in line


class TestEventProjection:
    """投影B：显式 rc → 事件送达订阅者；门控关闭 → 事件不发射、警告保留。"""

    def test_event_reaches_subscriber(self, ctx):
        bus = ctx.get_event_bus()
        sub = bus.subscribe()
        with pytest.warns(UserWarning, match="parse failed"):
            kernel_diagnostic(
                code=KDIAG_PROTOCOL_FROM_PROMPT_FALLBACK,
                detail={"type_name": "Point"},
                message="parse failed for Point",
                rc=ctx,
            )
        ok, event = sub.recv_nowait()
        assert ok
        assert event["type"] == "kernel_diagnostic"
        assert event["data"]["code"] == KDIAG_PROTOCOL_FROM_PROMPT_FALLBACK
        assert event["data"]["detail"] == {"type_name": "Point"}
        assert event["data"]["message"] == "parse failed for Point"

    def test_observability_off_suppresses_event_keeps_warning(self, ctx):
        ctx.get_config_store().set_global("observability", False)
        bus = ctx.get_event_bus()
        sub = bus.subscribe()
        with pytest.warns(UserWarning, match="parse failed"):
            kernel_diagnostic(
                code=KDIAG_PROTOCOL_FROM_PROMPT_FALLBACK,
                detail={"type_name": "Point"},
                message="parse failed for Point",
                rc=ctx,
            )
        ok, _ = sub.recv_nowait()
        assert not ok

    def test_rc_unreachable_emits_no_event(self, ctx):
        """显式 rc=None 且无活跃 EC → 事件面跳过（仅警告）。"""
        bus = ctx.get_event_bus()
        sub = bus.subscribe()
        with pytest.warns(UserWarning, match="parse failed"):
            kernel_diagnostic(
                code=KDIAG_PROTOCOL_FROM_PROMPT_FALLBACK,
                detail={"type_name": "Point"},
                message="parse failed for Point",
            )
        ok, _ = sub.recv_nowait()
        assert not ok

    def test_detail_defaults_to_empty_dict(self, ctx):
        bus = ctx.get_event_bus()
        sub = bus.subscribe()
        with pytest.warns(UserWarning):
            kernel_diagnostic(
                code=KDIAG_PROTOCOL_FROM_PROMPT_FALLBACK,
                message="no detail",
                rc=ctx,
            )
        ok, event = sub.recv_nowait()
        assert ok
        assert event["data"]["detail"] == {}
