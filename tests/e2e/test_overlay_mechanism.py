"""
tests/e2e/test_overlay_mechanism.py — 临时覆层机制判别性契约。

覆层机制核心语义：
- 覆层声明（``impl overlay for <内置类型>:``）：登记 per-IbClass 协议方法表的
  **影子条目**（ProtocolSlot.overlay），**默认不参与分派**（内置按原生行为）；
- 作用域化启用（``with overlay(<类型>.<协议方法>):``）：块执行窗口内，覆层影子
  条目成为分派候选（优先级高于原生 vtable 方法）；块外恢复默认行为；
- 语义校验：覆层目标须为内置具体值类型、方法须为协议消息；``with overlay`` 须
  引用已声明覆层；声明但从未启用 → SEM_OVERLAY_UNUSED 告警。
"""

import os

import pytest

from core.engine import IBCIEngine

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _engine():
    return IBCIEngine(root_dir=_ROOT)


def _run(code: str):
    eng = _engine()
    eng.run_string(code, silent=True)
    return eng


class TestOverlayDispatch:
    """覆层作用域化分派：块内生效 / 块外恢复默认。"""

    def test_overlay_receive_dispatch_inside_and_outside(self):
        """``with overlay(int.__to_prompt__)`` 块内 receive('__to_prompt__')
        返回覆层结果，块外恢复原生——作用域化启用语义。

        覆层启用状态挂执行上下文（作用域化；多根并发隔离）：块内经
        ``enter_overlay`` 启用、块外默认不启用。宿主侧无活跃执行上下文时
        视为块外（覆层仅经执行窗口生效）。
        """
        from core.runtime.frame import (
            set_current_execution_context,
            reset_current_execution_context,
        )

        eng = _run(
            "impl overlay for int:\n"
            "    func __to_prompt__(self) -> str:\n"
            "        return 'overlayed-int'\n"
            "int x = 5\n"
        )
        int_cls = eng.registry.get_class("int")
        slot = int_cls.protocol_slot("__to_prompt__")
        assert slot is not None
        assert slot.overlay is not None  # 影子条目已登记

        v = eng.registry.box(5)
        # 块外（默认 / 无活跃执行上下文）：原生 int.__to_prompt__ → "5"
        assert v.receive("__to_prompt__", []).to_native() == "5"
        # 块内：进入执行窗口（enter_overlay + 活跃 EC）
        token = set_current_execution_context(eng.interpreter.execution_context)
        rc = eng.interpreter.runtime_context
        rc.enter_overlay("int", "__to_prompt__")
        try:
            assert v.receive("__to_prompt__", []).to_native() == "overlayed-int"
        finally:
            rc.exit_overlay("int", "__to_prompt__")
            reset_current_execution_context(token)
        # 恢复后：原生
        assert v.receive("__to_prompt__", []).to_native() == "5"

    def test_overlay_declaration_default_inactive(self):
        """仅声明覆层（无 with overlay）→ 默认不参与分派（原生行为）。"""
        eng = _run(
            "impl overlay for int:\n"
            "    func __to_prompt__(self) -> str:\n"
            "        return 'overlayed-int'\n"
            "int x = 5\n"
        )
        v = eng.registry.box(5)
        assert v.receive("__to_prompt__", []).to_native() == "5"
        # 影子条目已登记但未启用（默认不参与分派）
        int_cls = eng.registry.get_class("int")
        slot = int_cls.protocol_slot("__to_prompt__")
        assert slot.overlay is not None
        assert not eng.interpreter.execution_context.runtime_context.is_overlay_enabled("int", "__to_prompt__")

    def test_with_overlay_block_end_to_end_via_prompt_rendering(self):
        """``with overlay`` 语句驱动的端到端判别（真实消费路径，非手动翻转 flag）。

        块内行为 prompt 渲染 ``$x``（int）走覆层影子条目 → "overlayed-int"、
        块外恢复原生 → "5"：经行为插值 → PromptRenderer ``receive('__to_prompt__')``
        → 覆层生效面；mock LLM 回显 prompt 以观测渲染结果。同时覆盖
        ``vm_handle_IbWithOverlay`` 的执行上下文启用/退出生命周期。
        """
        lines: list = []
        eng = _engine()
        eng.run_string(
            "import ai\n"
            "ai.set_mock_mode()\n"
            "impl overlay for int:\n"
            "    func __to_prompt__(self) -> str:\n"
            "        return 'overlayed-int'\n"
            "int x = 5\n"
            "with overlay(int.__to_prompt__):\n"
            "    str inside = @~ report: $x ~\n"
            "    print(inside)\n"
            "str outside = @~ report: $x ~\n"
            "print(outside)\n",
            output_callback=lambda t: lines.append(str(t)),
            silent=True,
        )
        assert lines == ["[MOCK] report: overlayed-int", "[MOCK] report: 5"]


class TestOverlaySemantic:
    """覆层语义校验：目标约束 / with 目标校验 / 未启用告警。"""

    def test_unused_overlay_warns(self):
        """声明覆层但从不被 with overlay 引用 → SEM_OVERLAY_UNUSED 告警。"""
        from core.engine import IBCIEngine
        e = _engine()
        e.compile_string(
            "impl overlay for int:\n"
            "    func __to_prompt__(self) -> str:\n"
            "        return 'x'\n",
            silent=True,
        )
        tracker = e.issue_tracker
        assert tracker.warning_count >= 1
        codes = [d.code for d in tracker.diagnostics]
        assert "SEM_OVERLAY_UNUSED" in codes

    def test_with_overlay_on_undeclared_overlay_errors(self):
        """``with overlay`` 须引用已声明覆层；未声明 → 编译期 SEM_TYPE_MISMATCH。"""
        from core.kernel.issue import CompilerError
        e = _engine()
        with pytest.raises(CompilerError):
            e.compile_string(
                "func f() -> str:\n"
                "    with overlay(str.__to_prompt__):\n"
                "        str s = 'a'\n"
                "        return s.__to_prompt__()\n"
                "    return ''\n",
                silent=True,
            )

    def test_overlay_on_non_protocol_method_errors(self):
        """覆层方法须为协议消息（dunder 方法集）；非协议消息在水化期 fail-fast。"""
        e = _engine()
        with pytest.raises(RuntimeError):
            e.run_string(
                "impl overlay for int:\n"
                "    func not_a_protocol_method(self) -> str:\n"
                "        return 'x'\n",
                silent=True,
            )
