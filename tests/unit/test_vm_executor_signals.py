"""
tests/unit/test_vm_executor_signals.py
======================================

M3b / C5 — VMExecutor 控制信号数据化（``Signal(kind, value)``）专属测试。

测试目标
--------
1. **数据形态**：handler ``return Signal(...)`` 而非 raise 异常
2. **传播路径**：Signal 通过 ``StopIteration.value`` → ``gen.send(Signal)`` 沿帧栈
   数据化向上传递；非循环帧透传（``return res``），循环帧消费 BREAK/CONTINUE
3. **边界（C5）**：顶层未消费 Signal 时以 ``UnhandledSignal`` 抛给调用者
4. **多语句容器**：``IbModule`` / ``IbIf`` 在收到 Signal 后立即停止执行后续语句
   并向上透传

涵盖 ≥20 个独立测试点。
"""
import pytest

from core.engine import IBCIEngine
from core.runtime.vm import (
    VMExecutor,
    Signal,
    ControlSignal,
    UnhandledSignal,
)
from core.runtime.vm.handlers import (
    vm_handle_IbBreak,
    vm_handle_IbContinue,
    vm_handle_IbReturn,
    vm_handle_IbModule,
    vm_handle_IbIf,
    vm_handle_IbWhile,
)


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

def make_engine(code: str = "pass\n", output_lines=None):
    engine = IBCIEngine(root_dir=".", auto_sniff=False)
    cb = (lambda t: output_lines.append(str(t))) if output_lines is not None else (lambda t: None)
    engine.run_string(code, output_callback=cb, silent=True)
    return engine


def make_vm(engine):
    return VMExecutor(engine.interpreter._execution_context, interpreter=engine.interpreter)


def find_node_uid(engine, node_type: str, predicate=None) -> str:
    for uid, data in engine.interpreter.node_pool.items():
        if data.get("_type") == node_type:
            if predicate is None or predicate(uid, data):
                return uid
    raise AssertionError(f"No {node_type} node found in node_pool")


def native(obj):
    return obj.to_native() if hasattr(obj, "to_native") else obj


# ===========================================================================
# 1. Signal 数据对象基础属性
# ===========================================================================

class TestSignalDataObject:
    def test_signal_is_frozen_dataclass(self):
        sig = Signal(ControlSignal.BREAK)
        assert sig.kind is ControlSignal.BREAK
        assert sig.value is None
        # frozen: assignment raises
        with pytest.raises((AttributeError, Exception)):
            sig.kind = ControlSignal.CONTINUE  # type: ignore

    def test_signal_carries_value(self):
        sig = Signal(ControlSignal.RETURN, 42)
        assert sig.kind is ControlSignal.RETURN
        assert sig.value == 42

    def test_signal_equality_by_value(self):
        a = Signal(ControlSignal.BREAK)
        b = Signal(ControlSignal.BREAK)
        assert a == b
        c = Signal(ControlSignal.BREAK, 1)
        assert a != c

    def test_signal_kinds_distinct(self):
        kinds = {ControlSignal.RETURN, ControlSignal.BREAK,
                 ControlSignal.CONTINUE, ControlSignal.THROW}
        assert len(kinds) == 4

    def test_signal_repr_contains_kind(self):
        sig = Signal(ControlSignal.RETURN, "x")
        assert "return" in repr(sig)


# ===========================================================================
# 2. Handler 直接行为：return Signal vs raise CSE
# ===========================================================================

class TestHandlersReturnSignal:
    """单元级测试：直接驱动 generator 验证 handler 不再 raise，而是 return Signal。"""

    def test_break_handler_returns_signal(self):
        gen = vm_handle_IbBreak(None, "u", {})
        try:
            next(gen)
        except StopIteration as si:
            assert isinstance(si.value, Signal)
            assert si.value.kind is ControlSignal.BREAK
            assert si.value.value is None
        else:
            raise AssertionError("Generator did not stop with Signal")

    def test_continue_handler_returns_signal(self):
        gen = vm_handle_IbContinue(None, "u", {})
        try:
            next(gen)
        except StopIteration as si:
            assert isinstance(si.value, Signal)
            assert si.value.kind is ControlSignal.CONTINUE

    def test_break_handler_does_not_raise(self):
        """M3b 行为：旧的 raise 异常路径已彻底消失；仅通过 StopIteration.value 传递 Signal。"""
        gen = vm_handle_IbBreak(None, "u", {})
        # 不会抛出任何异常（除 StopIteration）
        with pytest.raises(StopIteration):
            next(gen)


# ===========================================================================
# 3. 顶层执行：未消费 Signal 以 UnhandledSignal 抛出（C5 边界）
# ===========================================================================

class TestTopLevelSignalEscape:
    def test_break_outside_loop_escapes_as_unhandled(self):
        engine = make_engine("pass\n")
        # 单独执行一个 IbBreak 节点
        # 先获取一个真实存在的 IbBreak 节点（构造一段含 while 的代码）
        engine2 = make_engine("while False:\n    break\n")
        break_uid = find_node_uid(engine2, "IbBreak")
        vm = make_vm(engine2)
        with pytest.raises(UnhandledSignal) as ei:
            vm.run(break_uid)
        assert ei.value.signal.kind is ControlSignal.BREAK

    def test_continue_outside_loop_escapes_as_unhandled(self):
        engine = make_engine("while False:\n    continue\n")
        cont_uid = find_node_uid(engine, "IbContinue")
        vm = make_vm(engine)
        with pytest.raises(UnhandledSignal) as ei:
            vm.run(cont_uid)
        assert ei.value.signal.kind is ControlSignal.CONTINUE

    def test_return_at_module_level_escapes_with_value(self):
        engine = make_engine("func f():\n    return 99\n")
        # 找到函数体内的 return 节点，单独 run 它
        ret_uid = find_node_uid(engine, "IbReturn")
        vm = make_vm(engine)
        with pytest.raises(UnhandledSignal) as ei:
            vm.run(ret_uid)
        assert ei.value.signal.kind is ControlSignal.RETURN
        assert native(ei.value.signal.value) == 99

    def test_return_with_no_value_carries_none(self):
        engine = make_engine("func f():\n    return\n")
        ret_uid = find_node_uid(engine, "IbReturn")
        vm = make_vm(engine)
        with pytest.raises(UnhandledSignal) as ei:
            vm.run(ret_uid)
        assert ei.value.signal.kind is ControlSignal.RETURN
        # value is IbNone or has to_native()==None
        assert native(ei.value.signal.value) is None


# ===========================================================================
# 4. while 循环消费 BREAK / CONTINUE
# ===========================================================================

class TestWhileLoopConsumesSignal:
    def test_break_terminates_while(self):
        # i=0; while i<5: if i==2: break; i+=1
        # 完成后 i 必须 == 2（循环在 i==2 时退出，未执行 i+=1）
        engine = make_engine(
            "int i = 0\n"
            "while i < 5:\n"
            "    if i == 2:\n"
            "        break\n"
            "    i = i + 1\n"
        )
        # 直接通过 VM 重跑 module 体验证不退化
        rt = engine.interpreter.runtime_context
        assert native(rt.get_variable("i")) == 2

        # 还可以单独通过 VM 跑 IbWhile 节点（i 已是 2 → 直接退出，i 不变）
        engine2 = make_engine(
            "int i = 0\n"
            "while i < 5:\n"
            "    if i == 2:\n"
            "        break\n"
            "    i = i + 1\n"
        )
        while_uid = find_node_uid(engine2, "IbWhile")
        # 重置 i=0 再用 VM 跑
        rt2 = engine2.interpreter.runtime_context
        rt2.set_variable("i", engine2.interpreter.registry.box(0))
        vm = make_vm(engine2)
        vm.run(while_uid)
        assert native(rt2.get_variable("i")) == 2

    def test_continue_skips_remainder_of_iteration(self):
        # 累加 i=0..4 中只在 i!=2 时累加 sum：sum 应为 0+1+3+4=8
        engine = make_engine(
            "int i = 0\n"
            "int sum = 0\n"
            "while i < 5:\n"
            "    if i == 2:\n"
            "        i = i + 1\n"
            "        continue\n"
            "    sum = sum + i\n"
            "    i = i + 1\n"
        )
        while_uid = find_node_uid(engine, "IbWhile")
        rt = engine.interpreter.runtime_context
        # 重置初值
        rt.set_variable("i", engine.interpreter.registry.box(0))
        rt.set_variable("sum", engine.interpreter.registry.box(0))
        vm = make_vm(engine)
        vm.run(while_uid)
        assert native(rt.get_variable("sum")) == 8
        assert native(rt.get_variable("i")) == 5

    def test_break_inside_nested_if_inside_while(self):
        engine = make_engine(
            "int i = 0\n"
            "while i < 100:\n"
            "    if i > 3:\n"
            "        if i > 5:\n"
            "            break\n"
            "    i = i + 1\n"
        )
        while_uid = find_node_uid(engine, "IbWhile")
        rt = engine.interpreter.runtime_context
        rt.set_variable("i", engine.interpreter.registry.box(0))
        vm = make_vm(engine)
        vm.run(while_uid)
        # i grows to 6; outer if true at i>3, inner if true at i>5, break.
        assert native(rt.get_variable("i")) == 6


# ===========================================================================
# 5. 非循环容器透传信号
# ===========================================================================

class TestNonLoopContainersPropagate:
    def test_module_propagates_break_signal(self):
        # 用 while 内 if break，然后取 IbIf 节点单独跑（IbIf 应透传 break Signal）
        engine2 = make_engine(
            "while True:\n"
            "    if True:\n"
            "        break\n"
        )
        if_uid = find_node_uid(engine2, "IbIf")
        vm = make_vm(engine2)
        with pytest.raises(UnhandledSignal) as ei:
            vm.run(if_uid)
        assert ei.value.signal.kind is ControlSignal.BREAK

    def test_if_stops_after_signal_in_branch(self):
        # if 体内第一条语句产生 break，第二条不应执行
        engine = make_engine(
            "int x = 0\n"
            "while True:\n"
            "    if True:\n"
            "        break\n"
            "        x = 999\n"  # 不可达；保留作为副作用见证
        )
        rt = engine.interpreter.runtime_context
        assert native(rt.get_variable("x")) == 0

    def test_signal_in_else_branch(self):
        engine = make_engine(
            "int i = 5\n"
            "while True:\n"
            "    if i > 10:\n"
            "        i = i + 1\n"
            "    else:\n"
            "        break\n"
        )
        while_uid = find_node_uid(engine, "IbWhile")
        rt = engine.interpreter.runtime_context
        rt.set_variable("i", engine.interpreter.registry.box(5))
        vm = make_vm(engine)
        vm.run(while_uid)
        # i 不变，循环立即从 else 分支 break
        assert native(rt.get_variable("i")) == 5


# ===========================================================================
# 6. 内部不再使用 Python 异常做控制流（行为见证）
# ===========================================================================

class TestNoExceptionForControlFlow:
    def test_break_signal_does_not_appear_as_cse_when_consumed(self):
        """循环内 break 必须被 while handler 消费而不抛任何异常到 run() 调用者。"""
        engine = make_engine(
            "int i = 0\n"
            "while i < 10:\n"
            "    if i == 3:\n"
            "        break\n"
            "    i = i + 1\n"
        )
        while_uid = find_node_uid(engine, "IbWhile")
        rt = engine.interpreter.runtime_context
        rt.set_variable("i", engine.interpreter.registry.box(0))
        vm = make_vm(engine)
        # Must NOT raise
        result = vm.run(while_uid)
        assert result is not None
        assert native(rt.get_variable("i")) == 3

    def test_continue_signal_does_not_appear_as_cse_when_consumed(self):
        engine = make_engine(
            "int i = 0\n"
            "int sum = 0\n"
            "while i < 3:\n"
            "    i = i + 1\n"
            "    if i == 2:\n"
            "        continue\n"
            "    sum = sum + i\n"
        )
        while_uid = find_node_uid(engine, "IbWhile")
        rt = engine.interpreter.runtime_context
        rt.set_variable("i", engine.interpreter.registry.box(0))
        rt.set_variable("sum", engine.interpreter.registry.box(0))
        vm = make_vm(engine)
        result = vm.run(while_uid)
        assert result is not None
        # sum = 1 + 3 = 4
        assert native(rt.get_variable("sum")) == 4


# ===========================================================================
# 7. UnhandledSignal 构造（C5）
# ===========================================================================

class TestUnhandledSignal:
    def test_unhandled_signal_carries_signal(self):
        sig = Signal(ControlSignal.RETURN, 7)
        exc = UnhandledSignal(sig)
        assert exc.signal.kind is ControlSignal.RETURN
        assert exc.signal.value == 7

    def test_unhandled_signal_is_exception(self):
        sig = Signal(ControlSignal.BREAK)
        exc = UnhandledSignal(sig)
        assert isinstance(exc, Exception)

    def test_unhandled_signal_for_break(self):
        sig = Signal(ControlSignal.BREAK)
        exc = UnhandledSignal(sig)
        assert exc.signal.kind is ControlSignal.BREAK
        assert exc.signal.value is None
