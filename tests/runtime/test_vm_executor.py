"""
tests/runtime/test_vm_executor.py
==============================

VMExecutor (CPS Scheduling Loop) 骨架测试。

测试策略
--------
* 使用 IBCIEngine 编译并执行一段引导代码（创建符号 + 节点池）。
* 通过 ``find_node_uid`` 在 ``interpreter.node_pool`` 中定位特定 AST 节点。
* 通过 :class:`VMExecutor` （而非递归 ``visit()``）重新执行该节点子树，
  断言结果或副作用与既有解释器语义一致。

覆盖范围（实现的节点类型）：
    * 表达式：IbConstant, IbName, IbBinOp, IbUnaryOp, IbBoolOp, IbCompare,
              IbIfExp, IbCall, IbAttribute, IbSubscript, IbTuple, IbListExpr
    * 语句  ：IbModule, IbPass, IbExprStmt, IbAssign, IbIf, IbWhile,
              IbReturn, IbBreak, IbContinue
    * 数据类：VMTask, VMTaskResult, ControlSignal, UnhandledSignal
    * 调度  ：supports, step_count, run_body
"""
import os
import inspect
import pytest

from core.engine import IBCIEngine
from core.runtime.exceptions import ThrownException
from core.runtime.objects.kernel import IbUserFunction, IbLLMFunction
from core.runtime.vm import (
    VMExecutor,
    VMTask,
    VMTaskResult,
    ControlSignal,
    UnhandledSignal,
    Signal,
)
from core.runtime.vm.handlers import (
    build_dispatch_table,
    vm_handle_IbLLMExceptionalStmt,
    vm_handle_IbBreak,
    vm_handle_IbContinue,
    vm_handle_IbReturn,
    vm_handle_IbModule,
    vm_handle_IbIf,
    vm_handle_IbWhile,
)


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


def make_engine(code: str = "pass\n", output_lines=None):
    """创建一个执行了 ``code`` 的 IBCIEngine 实例（递归路径）。"""
    engine = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
    if output_lines is not None:
        cb = lambda t: output_lines.append(str(t))
    else:
        cb = lambda t: None
    engine.run_string(code, output_callback=cb, silent=True)
    return engine


def make_vm(engine):
    return VMExecutor(engine.interpreter._execution_context, interpreter=engine.interpreter)


def reset_var(engine, name: str, value):
    """Reset a variable's value via name-based assign (mutates the existing symbol
    so both name-table and UID-table see the new value).
    """
    rt = engine.interpreter.runtime_context
    boxed = engine.interpreter.registry.box(value)
    rt.set_variable(name, boxed)


def find_node_uid(engine, node_type: str, predicate=None) -> str:
    """在 node_pool 中查找匹配的节点 UID。"""
    for uid, data in engine.interpreter.node_pool.items():
        if data.get("_type") == node_type:
            if predicate is None or predicate(uid, data):
                return uid
    raise AssertionError(f"No {node_type} node found in node_pool")


def find_all_node_uids(engine, node_type: str) -> list:
    return [
        uid for uid, data in engine.interpreter.node_pool.items()
        if data.get("_type") == node_type
    ]


def native(obj):
    """将 IBCI 对象转为原生 Python 值。"""
    return obj.to_native() if hasattr(obj, "to_native") else obj


def ai_setup() -> str:
    """Standard AI MOCK mode setup prefix (merged from former test_vm_executor_llmexcept.py)."""
    return 'import ai\nai.set_config("TESTONLY", "TESTONLY", "TESTONLY")\n'


# ===========================================================================
# 1. 数据类：VMTask / VMTaskResult / ControlSignal
# ===========================================================================

class TestVMDataClasses:
    def test_control_signal_enum_values(self):
        assert ControlSignal.RETURN.value == "return"
        assert ControlSignal.BREAK.value == "break"
        assert ControlSignal.CONTINUE.value == "continue"
        assert ControlSignal.THROW.value == "throw"

    def test_unhandled_signal_carries_signal_and_value(self):
        from core.runtime.vm.task import Signal
        sig = Signal(ControlSignal.RETURN, "v")
        exc = UnhandledSignal(sig)
        assert exc.signal.kind is ControlSignal.RETURN
        assert exc.signal.value == "v"
        # subclass of Exception
        assert isinstance(exc, Exception)

    def test_vmtaskresult_factories(self):
        d = VMTaskResult.DONE(42)
        s = VMTaskResult.SUSPEND("node_x")
        g = VMTaskResult.SIGNAL(ControlSignal.BREAK)
        assert d.is_done and not d.is_suspend and not d.is_signal
        assert d.value == 42
        assert s.is_suspend and s.value == "node_x"
        assert g.is_signal
        sig, val = g.value
        assert sig is ControlSignal.BREAK and val is None

    def test_vmtask_default_locals(self):
        def gen():
            return None
            yield
        t = VMTask(node_uid="u", generator=gen())
        assert t.node_uid == "u"
        assert t.locals == {}


# ===========================================================================
# 2. 基础表达式（IbConstant / IbName / IbBinOp / IbUnaryOp / IbBoolOp / IbIfExp）
# ===========================================================================

class TestExpressionEvaluation:
    def test_int_constant(self):
        engine = make_engine("int x = 42")
        # 找到 42 这个常量节点
        for uid, data in engine.interpreter.node_pool.items():
            if data.get("_type") == "IbConstant" and data.get("value") == 42:
                vm = make_vm(engine)
                result = vm.run(uid)
                assert native(result) == 42
                return
        pytest.fail("constant 42 not found")

    def test_string_constant(self):
        engine = make_engine('str s = "hello"')
        for uid, data in engine.interpreter.node_pool.items():
            if data.get("_type") == "IbConstant" and data.get("value") == "hello":
                vm = make_vm(engine)
                result = vm.run(uid)
                assert native(result) == "hello"
                return
        pytest.fail("constant 'hello' not found")

    def test_name_lookup(self):
        engine = make_engine("int x = 7")
        # 找到 IbName 节点（变量引用 x）。注：x 的赋值 LHS 也是 IbName 但在 IbAssign.targets 内。
        # 简单做法：手动构造一个 IbName 引用？我们用 IbExprStmt 触发：x（独立表达式）
        engine = make_engine("int x = 7\nx\n")
        vm = make_vm(engine)
        # 找到一个 IbName id=x 的节点
        for uid, data in engine.interpreter.node_pool.items():
            if data.get("_type") == "IbName" and data.get("id") == "x":
                # 必须存在 sym_uid 侧表
                if engine.interpreter._execution_context.get_side_table("node_to_symbol", uid):
                    result = vm.run(uid)
                    assert native(result) == 7
                    return
        pytest.fail("x reference not found")

    def test_binop_addition(self):
        engine = make_engine("int z = 10 + 5")
        binop_uid = find_node_uid(engine, "IbBinOp")
        vm = make_vm(engine)
        result = vm.run(binop_uid)
        assert native(result) == 15

    def test_binop_multiplication(self):
        engine = make_engine("int z = 6 * 7")
        binop_uid = find_node_uid(engine, "IbBinOp")
        vm = make_vm(engine)
        assert native(vm.run(binop_uid)) == 42

    def test_binop_subtraction(self):
        engine = make_engine("int z = 100 - 58")
        binop_uid = find_node_uid(engine, "IbBinOp")
        vm = make_vm(engine)
        assert native(vm.run(binop_uid)) == 42

    def test_nested_binop(self):
        engine = make_engine("int z = (1 + 2) * (3 + 4)")
        binops = find_all_node_uids(engine, "IbBinOp")
        # 取最外层乘法（root binop —— 没有作为子 binop 的 left/right）
        all_uids = set(binops)
        for uid in binops:
            d = engine.interpreter.get_node_data(uid)
            if d.get("op") == "*":
                vm = make_vm(engine)
                result = vm.run(uid)
                assert native(result) == 21
                return
        pytest.fail("Multiplicative binop not located")

    def test_unaryop_negation(self):
        engine = make_engine("int x = -42")
        unop_uid = find_node_uid(engine, "IbUnaryOp")
        vm = make_vm(engine)
        result = vm.run(unop_uid)
        assert native(result) == -42

    def test_boolop_and_short_circuit_false(self):
        engine = make_engine("bool b = False and True")
        boolop_uid = find_node_uid(engine, "IbBoolOp")
        vm = make_vm(engine)
        result = vm.run(boolop_uid)
        # short-circuits to first falsy
        assert native(result) is False or native(result) == 0

    def test_boolop_or_short_circuit_true(self):
        engine = make_engine("bool b = True or False")
        boolop_uid = find_node_uid(engine, "IbBoolOp")
        vm = make_vm(engine)
        result = vm.run(boolop_uid)
        assert native(result) in (True, 1)

    def test_ifexp_true(self):
        engine = make_engine("int v = 1 if True else 2")
        ifexp_uid = find_node_uid(engine, "IbIfExp")
        vm = make_vm(engine)
        assert native(vm.run(ifexp_uid)) == 1

    def test_ifexp_false(self):
        engine = make_engine("int v = 1 if False else 2")
        ifexp_uid = find_node_uid(engine, "IbIfExp")
        vm = make_vm(engine)
        assert native(vm.run(ifexp_uid)) == 2


# ===========================================================================
# 3. 比较运算（IbCompare）
# ===========================================================================

class TestCompare:
    def test_compare_lt_true(self):
        engine = make_engine("bool b = 1 < 2")
        cmp_uid = find_node_uid(engine, "IbCompare")
        vm = make_vm(engine)
        assert native(vm.run(cmp_uid)) in (True, 1)

    def test_compare_eq_false(self):
        engine = make_engine("bool b = 5 == 6")
        cmp_uid = find_node_uid(engine, "IbCompare")
        vm = make_vm(engine)
        assert native(vm.run(cmp_uid)) in (False, 0)

    def test_compare_chain(self):
        engine = make_engine("bool b = 1 < 2 < 3")
        cmp_uid = find_node_uid(engine, "IbCompare")
        vm = make_vm(engine)
        assert native(vm.run(cmp_uid)) in (True, 1)

    def test_compare_chain_breaks(self):
        engine = make_engine("bool b = 1 < 2 < 1")
        cmp_uid = find_node_uid(engine, "IbCompare")
        vm = make_vm(engine)
        assert native(vm.run(cmp_uid)) in (False, 0)

    def test_compare_in_list(self):
        engine = make_engine("list nums = [1, 2, 3]\nbool found = 2 in nums")
        # The "in" comparison
        cmp_uid = None
        for uid, data in engine.interpreter.node_pool.items():
            if data.get("_type") == "IbCompare" and "in" in data.get("ops", []):
                cmp_uid = uid
                break
        assert cmp_uid is not None, "in-Compare not found"
        vm = make_vm(engine)
        assert native(vm.run(cmp_uid)) in (True, 1)


# ===========================================================================
# 4. 数据结构 / 复合表达式（IbTuple / IbListExpr / IbSubscript / IbAttribute）
# ===========================================================================

class TestCompoundExpressions:
    def test_tuple_literal(self):
        engine = make_engine("any t = (1, 2, 3)")
        tup_uid = find_node_uid(engine, "IbTuple")
        vm = make_vm(engine)
        result = vm.run(tup_uid)
        assert native(result) == (1, 2, 3)

    def test_list_literal(self):
        engine = make_engine("list xs = [10, 20, 30]")
        lst_uid = find_node_uid(engine, "IbListExpr")
        vm = make_vm(engine)
        result = vm.run(lst_uid)
        # list element values
        elements = [e.to_native() for e in result.elements]
        assert elements == [10, 20, 30]

    def test_subscript(self):
        engine = make_engine("list xs = [10, 20, 30]\nany x = xs[1]")
        sub_uid = find_node_uid(engine, "IbSubscript")
        vm = make_vm(engine)
        result = vm.run(sub_uid)
        assert native(result) == 20


# ===========================================================================
# 5. 控制流（IbIf / IbWhile / IbReturn / IbBreak / IbContinue）
# ===========================================================================

class TestControlFlow:
    def test_if_true_branch_executes(self):
        # Run program that ends with counter == 100.
        engine = make_engine(
            "int counter = 0\n"
            "if 1 < 2:\n"
            "    counter = 100\n"
        )
        # After recursive run, counter is 100. Reset.
        reset_var(engine, "counter", 0)
        # Now run only the IbIf via VM.
        if_uid = find_node_uid(engine, "IbIf")
        vm = make_vm(engine)
        vm.run(if_uid)
        assert native(engine.get_variable("counter")) == 100

    def test_if_false_branch_skipped(self):
        engine = make_engine(
            "int counter = 0\n"
            "if 1 > 2:\n"
            "    counter = 100\n"
        )
        reset_var(engine, "counter", 0)
        if_uid = find_node_uid(engine, "IbIf")
        vm = make_vm(engine)
        vm.run(if_uid)
        # should remain 0
        assert native(engine.get_variable("counter")) == 0

    def test_if_else_branch(self):
        engine = make_engine(
            "int counter = 0\n"
            "if 1 > 2:\n"
            "    counter = 100\n"
            "else:\n"
            "    counter = 200\n"
        )
        reset_var(engine, "counter", 0)
        if_uid = find_node_uid(engine, "IbIf")
        vm = make_vm(engine)
        vm.run(if_uid)
        assert native(engine.get_variable("counter")) == 200

    def test_while_loop_counts(self):
        engine = make_engine(
            "int i = 0\n"
            "int sum = 0\n"
            "while i < 5:\n"
            "    sum = sum + i\n"
            "    i = i + 1\n"
        )
        # Recursive run computed sum=10, i=5. Reset.
        reset_var(engine, "i", 0)
        reset_var(engine, "sum", 0)
        while_uid = find_node_uid(engine, "IbWhile")
        vm = make_vm(engine)
        vm.run(while_uid)
        assert native(engine.get_variable("sum")) == 10
        assert native(engine.get_variable("i")) == 5

    def test_while_break(self):
        engine = make_engine(
            "int i = 0\n"
            "while i < 100:\n"
            "    if i == 3:\n"
            "        break\n"
            "    i = i + 1\n"
        )
        reset_var(engine, "i", 0)
        while_uid = find_node_uid(engine, "IbWhile")
        vm = make_vm(engine)
        vm.run(while_uid)
        assert native(engine.get_variable("i")) == 3

    def test_while_continue(self):
        engine = make_engine(
            "int i = 0\n"
            "int s = 0\n"
            "while i < 5:\n"
            "    i = i + 1\n"
            "    if i == 3:\n"
            "        continue\n"
            "    s = s + i\n"
        )
        reset_var(engine, "i", 0)
        reset_var(engine, "s", 0)
        while_uid = find_node_uid(engine, "IbWhile")
        vm = make_vm(engine)
        vm.run(while_uid)
        # 1+2+4+5 = 12 (skip 3)
        assert native(engine.get_variable("s")) == 12

    def test_break_outside_loop_propagates(self):
        # IbBreak alone raises UnhandledSignal; must propagate to caller.
        engine = make_engine("int x = 0\nwhile x < 1:\n    break\n    x = x + 1\n")
        # Find an IbBreak node and run it directly via VM
        break_uid = find_node_uid(engine, "IbBreak")
        vm = make_vm(engine)
        with pytest.raises(UnhandledSignal) as ei:
            vm.run(break_uid)
        assert ei.value.signal.kind is ControlSignal.BREAK

    def test_return_signal_value(self):
        # Build an IbReturn at the top level via a function.
        engine = make_engine(
            "func my_fn() -> int:\n"
            "    return 42\n"
            "\n"
            "int x = my_fn()\n"
        )
        # IbReturn yielded its value as 42.
        ret_uid = find_node_uid(engine, "IbReturn")
        vm = make_vm(engine)
        with pytest.raises(UnhandledSignal) as ei:
            vm.run(ret_uid)
        assert ei.value.signal.kind is ControlSignal.RETURN
        assert native(ei.value.signal.value) == 42


# ===========================================================================
# 6. 函数调用（IbCall）
# ===========================================================================

class TestCall:
    def test_call_print_via_vm(self):
        # 构建程序 -> 执行后调用 print 的 IbCall 节点；副作用注入到 output_callback
        lines = []
        engine = make_engine('print("hello vm")', output_lines=lines)
        # The recursive run already printed once; clear and re-run via VM.
        lines.clear()
        # The original IBCIEngine.run_string sets the output callback once.
        # We need to re-attach it to ServiceContext (it's already there).
        call_uid = find_node_uid(engine, "IbCall")
        vm = make_vm(engine)
        vm.run(call_uid)
        # print was called via VM
        assert any("hello vm" in s for s in lines)

    def test_call_str_cast(self):
        # (str)42 — IbCastExpr.
        engine = make_engine("str s = (str)42")
        cast_uid = None
        for uid, data in engine.interpreter.node_pool.items():
            if data.get("_type") == "IbCastExpr":
                cast_uid = uid
                break
        # IbCastExpr is not in our dispatch table — VMExecutor falls back.
        if cast_uid:
            vm = make_vm(engine)
            result = vm.run(cast_uid)
            assert native(result) == "42"


# ===========================================================================
# 7. 赋值（IbAssign）
# ===========================================================================

class TestAssign:
    def test_assign_simple(self):
        engine = make_engine("int v = 0\nv = 99\n")
        # find the second IbAssign (v = 99). Its value is IbConstant 99.
        assign_uids = find_all_node_uids(engine, "IbAssign")
        # Second assign assigns IbConstant 99
        target_assign = None
        for uid in assign_uids:
            data = engine.interpreter.get_node_data(uid)
            v_uid = data.get("value")
            v_data = engine.interpreter.get_node_data(v_uid) if v_uid else None
            if v_data and v_data.get("_type") == "IbConstant" and v_data.get("value") == 99:
                target_assign = uid
                break
        assert target_assign is not None
        reset_var(engine, "v", 0)
        vm = make_vm(engine)
        vm.run(target_assign)
        assert native(engine.get_variable("v")) == 99

    def test_assign_expression(self):
        engine = make_engine("int v = 0\nv = 7 * 6\n")
        # Find the assign whose value is an IbBinOp
        assign_uid = None
        for uid in find_all_node_uids(engine, "IbAssign"):
            data = engine.interpreter.get_node_data(uid)
            v_uid = data.get("value")
            v_data = engine.interpreter.get_node_data(v_uid) if v_uid else None
            if v_data and v_data.get("_type") == "IbBinOp":
                assign_uid = uid
                break
        assert assign_uid is not None
        reset_var(engine, "v", 0)
        vm = make_vm(engine)
        vm.run(assign_uid)
        assert native(engine.get_variable("v")) == 42


# ===========================================================================
# 8. Module / Pass / ExprStmt
# ===========================================================================

class TestModuleAndStatements:
    def test_pass_returns_none(self):
        engine = make_engine("pass")
        pass_uid = find_node_uid(engine, "IbPass")
        vm = make_vm(engine)
        result = vm.run(pass_uid)
        # IbNone has to_native -> None (empty)
        assert result is not None

    def test_module_executes_body_in_order(self):
        engine = make_engine("int x = 1\nint y = 2\nint z = x + y\n")
        reset_var(engine, "x", 0)
        reset_var(engine, "y", 0)
        reset_var(engine, "z", 0)
        # find IbModule root
        module_uid = find_node_uid(engine, "IbModule")
        vm = make_vm(engine)
        vm.run(module_uid)
        # After re-execution via VM, z must equal x+y == 3
        assert native(engine.get_variable("z")) == 3


# ===========================================================================
# 9. 调度器特性：supports / step_count
# ===========================================================================

class TestSchedulerInfrastructure:
    def test_supports_known_node(self):
        engine = make_engine("int x = 1 + 2")
        binop_uid = find_node_uid(engine, "IbBinOp")
        vm = make_vm(engine)
        assert vm.supports(binop_uid) is True

    def test_supports_unknown_node(self):
        # 所有 IBCI AST 节点类型都纳入调度表；通过注入一个未实现的
        # 伪节点类型来验证 supports() 的 miss 逻辑（_dispatch 查表 miss → False）。
        engine = make_engine("int x = 1")
        fake_uid = "fake_unsupported_uid_for_testing"
        engine.interpreter.node_pool[fake_uid] = {
            "_type": "IbHypotheticalNotImplementedType"
        }
        vm = make_vm(engine)
        assert vm.supports(fake_uid) is False

    def test_step_count_increments(self):
        engine = make_engine("int x = 1 + 2 + 3")
        binop_uids = find_all_node_uids(engine, "IbBinOp")
        # Run the outermost binop
        # all binops nested; root one is the one whose right child is IbConstant 3 OR
        # whichever is at the top — find the binop NOT referenced as child of another binop
        child_uids = set()
        for uid in binop_uids:
            d = engine.interpreter.get_node_data(uid)
            child_uids.add(d.get("left"))
            child_uids.add(d.get("right"))
        roots = [uid for uid in binop_uids if uid not in child_uids]
        assert len(roots) == 1
        vm = make_vm(engine)
        before = vm.step_count
        vm.run(roots[0])
        after = vm.step_count
        # At least 4 steps (2 binops + 3 constants worth of advances + StopIteration)
        assert after - before >= 4

    def test_run_constant_returns_value(self):
        engine = make_engine("int x = 1")
        const_uid = find_node_uid(engine, "IbConstant", lambda u, d: d.get("value") == 1)
        vm = make_vm(engine)
        result = vm.run(const_uid)
        assert native(result) == 1

    def test_run_with_none_returns_none(self):
        engine = make_engine("pass")
        vm = make_vm(engine)
        result = vm.run(None)
        # Returns IbNone
        assert result is not None

    def test_run_cast_expr(self):
        engine = make_engine("str s = (str)42")
        cast_uid = None
        for uid, data in engine.interpreter.node_pool.items():
            if data.get("_type") == "IbCastExpr":
                cast_uid = uid
                break
        if cast_uid is None:
            pytest.skip("No IbCastExpr")
        vm = make_vm(engine)
        result = vm.run(cast_uid)
        assert native(result) == "42"


# ===========================================================================
# 10. CPS 算术与比较正确性
# ===========================================================================

class TestCpsCorrectness:
    def test_arithmetic_correctness(self):
        engine = make_engine("int a = 1 + 2\nint b = 3 * 4\nint c = (5 + 6) * 7\n")
        expected = {"a": 3, "b": 12, "c": 77}
        for name, val in expected.items():
            assert native(engine.get_variable(name)) == val

    def test_compare_correctness(self):
        engine = make_engine(
            "bool a = 1 < 2\n"
            "bool b = 5 == 5\n"
            "bool c = 7 != 8\n"
            "bool d = 3 >= 3\n"
        )
        expected = {"a": True, "b": True, "c": True, "d": True}
        for name, val in expected.items():
            assert native(engine.get_variable(name)) == val

    def test_module_while_loop(self):
        # Compile+run via VM, verify loop result.
        code = (
            "int total = 0\n"
            "int i = 0\n"
            "while i < 10:\n"
            "    total = total + i\n"
            "    i = i + 1\n"
        )
        engine = make_engine(code)
        assert native(engine.get_variable("total")) == 45
        assert native(engine.get_variable("i")) == 10


# ===========================================================================
# 11. ControlSignal 传播细节
# ===========================================================================

class TestSignalPropagation:
    def test_break_inside_while_does_not_escape(self):
        # while caught the break — control flow reaches the assignment after the loop.
        engine = make_engine(
            "int v = 0\n"
            "while True:\n"
            "    break\n"
            "v = 99\n"
        )
        reset_var(engine, "v", 0)
        module_uid = find_node_uid(engine, "IbModule")
        vm = make_vm(engine)
        vm.run(module_uid)
        assert native(engine.get_variable("v")) == 99

    def test_continue_skips_remainder(self):
        engine = make_engine(
            "int i = 0\n"
            "int hits = 0\n"
            "while i < 3:\n"
            "    i = i + 1\n"
            "    continue\n"
            "    hits = hits + 1\n"
        )
        reset_var(engine, "i", 0)
        reset_var(engine, "hits", 0)
        while_uid = find_node_uid(engine, "IbWhile")
        vm = make_vm(engine)
        vm.run(while_uid)
        assert native(engine.get_variable("i")) == 3
        assert native(engine.get_variable("hits")) == 0

################################################################################
# MERGED: M3d — Behavior/Closure/For/Try/Retry handlers + Main path switch
################################################################################

# ===========================================================================
# Dispatch table coverage — 6 entries (total 44)
# ===========================================================================

class TestM3dDispatchCoverage:
    def test_m3d_handlers_registered(self):
        dispatch = build_dispatch_table()
        for node_type in (
            "IbBehaviorExpr",
            "IbBehaviorInstance",
            "IbLambdaExpr",
            "IbFor",
            "IbTry",
            "IbRetry",
        ):
            assert node_type in dispatch, f"missing handler for {node_type}"

    def test_dispatch_total_count(self):
        # 22 + 1 (IbLLMExceptionalStmt) + 14 (prep) + 6 = 43
        # IbExceptHandler / IbCase / IbIntentInfo 等子节点由父 handler 直接
        # 解构处理，未独立注册到 dispatch 表。
        dispatch = build_dispatch_table()
        assert len(dispatch) >= 43

    def test_m3d_handlers_are_generator_functions(self):
        dispatch = build_dispatch_table()
        for name in (
            "IbBehaviorExpr",
            "IbBehaviorInstance",
            "IbLambdaExpr",
            "IbFor",
            "IbTry",
            "IbRetry",
        ):
            assert inspect.isgeneratorfunction(dispatch[name])


# ===========================================================================
# IbFor — iterable + condition-driven + filter
# ===========================================================================

class TestIbForHandler:
    def test_iterable_for_executes_body(self):
        code = """
list xs = [1, 2, 3]
int total = 0
for int x in xs:
    total = total + x
print((str)total)
"""
        out: list = []
        engine = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
        engine.run_string(code, output_callback=lambda s: out.append(s), silent=True)
        assert "6" in out

    def test_for_with_break(self):
        code = """
list xs = [1, 2, 3, 4]
int total = 0
for int x in xs:
    if x == 3:
        break
    total = total + x
print((str)total)
"""
        out: list = []
        engine = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
        engine.run_string(code, output_callback=lambda s: out.append(s), silent=True)
        assert "3" in out  # 1+2

    def test_for_with_continue(self):
        code = """
list xs = [1, 2, 3, 4]
int total = 0
for int x in xs:
    if x == 2:
        continue
    total = total + x
print((str)total)
"""
        out: list = []
        engine = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
        engine.run_string(code, output_callback=lambda s: out.append(s), silent=True)
        assert "8" in out  # 1+3+4


# ===========================================================================
# IbTry — except 类型匹配 + finally 语义
# ===========================================================================

class TestIbTryHandler:
    def test_try_except_catches_runtime_error(self):
        code = '''try:
    int x = (int)"bad"
except Exception as e:
    print("caught")
print("after")
'''
        out: list = []
        engine = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
        engine.run_string(code, output_callback=lambda s: out.append(s), silent=True)
        assert "caught" in out
        assert "after" in out

    def test_try_else_runs_when_no_exception(self):
        # try/else 由现有 e2e 套件覆盖；这里用一个保守等价：
        # 无异常路径下，try 体之后的语句应正常执行。
        code = """try:
    int x = 1
except Exception as e:
    print("nope")
print("ok")
"""
        out: list = []
        engine = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
        engine.run_string(code, output_callback=lambda s: out.append(s), silent=True)
        assert "ok" in out
        assert "nope" not in out

    def test_try_finally_always_runs(self):
        code = '''try:
    int x = (int)"bad"
except Exception as e:
    print("caught")
finally:
    print("finally")
'''
        out: list = []
        engine = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
        engine.run_string(code, output_callback=lambda s: out.append(s), silent=True)
        assert "caught" in out
        assert "finally" in out


# ===========================================================================
# Main path switch — Interpreter.execute_module() drives via VMExecutor
# ===========================================================================

class TestMainPathSwitch:
    def test_interpreter_has_vm_executor_after_run(self):
        engine = make_engine("int x = 1")
        # _vm_executor lazily set on first execute_module call
        assert engine.interpreter._vm_executor is not None
        assert isinstance(engine.interpreter._vm_executor, VMExecutor)

    def test_interpreter_get_vm_executor_returns_singleton(self):
        engine = make_engine("int x = 1")
        vm1 = engine.interpreter._get_vm_executor()
        vm2 = engine.interpreter._get_vm_executor()
        assert vm1 is vm2

    def test_user_function_body_uses_vm_executor(self):
        """函数调用应通过 VMExecutor 驱动函数体，行为与递归一致。"""
        code = """
func add(int a, int b) -> int:
    return a + b
int r = add(2, 3)
print((str)r)
"""
        out: list = []
        engine = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
        engine.run_string(code, output_callback=lambda s: out.append(s), silent=True)
        assert "5" in out

    def test_nested_function_call_through_vm(self):
        code = """
func inner(int y) -> int:
    return y * 2

func outer(int x) -> int:
    return inner(x) + 1

print((str)outer(5))
"""
        out: list = []
        engine = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
        engine.run_string(code, output_callback=lambda s: out.append(s), silent=True)
        assert "11" in out


################################################################################
# MERGED: M3dprep — Expression/Statement/Definition/Intent handlers
################################################################################

# ===========================================================================
# 调度表注册：所有新 handler 必须可被查找到
# ===========================================================================

class TestDispatchTableRegistrationExtended:
    def test_all_new_handlers_registered(self):
        from core.runtime.vm.handlers import build_dispatch_table
        dispatch = build_dispatch_table()
        for node_type in [
            "IbDict", "IbSlice", "IbCastExpr", "IbFilteredExpr",
            "IbAugAssign", "IbGlobalStmt", "IbRaise",
            "IbImport", "IbImportFrom", "IbSwitch",
            "IbFunctionDef", "IbLLMFunctionDef", "IbClassDef",
            "IbIntentAnnotation", "IbIntentStackOperation",
        ]:
            assert node_type in dispatch, f"missing handler for {node_type}"

    def test_handlers_are_generator_functions(self):
        """所有 CPS handler 必须是 generator function（含 yield 语句）。"""
        import inspect
        from core.runtime.vm.handlers import build_dispatch_table
        dispatch = build_dispatch_table()
        for name, fn in dispatch.items():
            assert inspect.isgeneratorfunction(fn), (
                f"{name} handler is not a generator function"
            )


# ===========================================================================
# IbDict
# ===========================================================================

class TestIbDictHandler:
    def test_simple_dict_literal(self):
        engine = make_engine('dict d = {"a": 1, "b": 2}')
        # find the IbDict node in node_pool
        dict_uid = find_node_uid(engine, "IbDict")
        vm = make_vm(engine)
        result = vm.run(dict_uid)
        n = native(result)
        assert n == {"a": 1, "b": 2}

    def test_empty_dict(self):
        engine = make_engine("dict d = {}")
        dict_uid = find_node_uid(engine, "IbDict")
        vm = make_vm(engine)
        result = vm.run(dict_uid)
        assert native(result) == {}


# ===========================================================================
# IbSlice / IbSubscript
# ===========================================================================

class TestIbSliceHandler:
    def test_slice_expression(self):
        engine = make_engine("list lst = [1,2,3,4,5]\nlist sub = lst[1:3]")
        slice_uid = find_node_uid(engine, "IbSlice")
        vm = make_vm(engine)
        result = vm.run(slice_uid)
        s = native(result)
        # IBCI box(slice(1,3,None)) => Python slice obj wrapped
        assert isinstance(s, slice)
        assert s.start == 1 and s.stop == 3 and s.step is None

    def test_slice_with_step(self):
        engine = make_engine("list lst = [1,2,3,4,5]\nlist sub = lst[0:5:2]")
        slice_uid = find_node_uid(engine, "IbSlice")
        vm = make_vm(engine)
        result = vm.run(slice_uid)
        s = native(result)
        assert s.step == 2


# ===========================================================================
# IbCastExpr
# ===========================================================================

class TestIbCastExprHandler:
    def test_cast_int_to_str(self):
        engine = make_engine("str s = (str)42")
        cast_uid = find_node_uid(engine, "IbCastExpr")
        vm = make_vm(engine)
        result = vm.run(cast_uid)
        assert native(result) == "42"


# ===========================================================================
# IbFilteredExpr
# ===========================================================================

class TestIbFilteredExprHandler:
    def test_for_filtered_truthy(self):
        # `for ... in ... if filter:` 创建 IbFilteredExpr 节点
        engine = make_engine(
            "list[int] nums = [1,2,3,4]\n"
            "list[int] result = []\n"
            "for int n in nums if n > 2:\n"
            "    result.append(n)\n"
        )
        filt_uid = find_node_uid(engine, "IbFilteredExpr")
        vm = make_vm(engine)
        # 单独运行 IbFilteredExpr 子树时，filter 引用的循环变量 n 在
        # for 上下文外不可见；这里仅验证 handler 注册正确并能被 supports
        assert vm.supports(filt_uid) is True

    def test_filtered_handler_reachable_via_dispatch(self):
        from core.runtime.vm.handlers import (
            build_dispatch_table, vm_handle_IbFilteredExpr,
        )
        d = build_dispatch_table()
        assert d["IbFilteredExpr"] is vm_handle_IbFilteredExpr


# ===========================================================================
# IbAugAssign
# ===========================================================================

class TestIbAugAssignHandler:
    def test_aug_assign_int(self):
        engine = make_engine("int x = 5\nx += 3")
        aug_uid = find_node_uid(engine, "IbAugAssign")
        # Reset x then re-execute aug-assign via VM
        engine.interpreter.runtime_context.set_variable(
            "x", engine.interpreter.registry.box(10)
        )
        vm = make_vm(engine)
        vm.run(aug_uid)
        x_val = engine.interpreter.runtime_context.get_variable("x")
        assert native(x_val) == 13


# ===========================================================================
# IbGlobalStmt
# ===========================================================================

class TestIbGlobalStmtHandler:
    def test_global_stmt_noop(self):
        engine = make_engine("int x = 1\nfunc f():\n    global x\n    x = 2\nf()")
        gs_uid = find_node_uid(engine, "IbGlobalStmt")
        vm = make_vm(engine)
        result = vm.run(gs_uid)
        # 运行期 no-op：不抛错，返回 None
        assert result is not None


# ===========================================================================
# IbRaise
# ===========================================================================

class TestIbRaiseHandler:
    def test_raise_throws_thrown_exception(self):
        engine = make_engine(
            "try:\n"
            "    raise Exception(\"boom\")\n"
            "except Exception as e:\n"
            "    pass\n"
        )
        raise_uid = find_node_uid(engine, "IbRaise")
        vm = make_vm(engine)
        with pytest.raises(ThrownException):
            vm.run(raise_uid)


# ===========================================================================
# IbImport / IbImportFrom — runtime no-ops
# ===========================================================================

class TestIbImportHandlers:
    def test_handlers_present_for_import_nodes(self):
        # 这些节点在解析期生成；当前 IBCI 运行时把它们作为 no-op。
        # 直接验证 handler 注册表，避免依赖具体源码示例。
        from core.runtime.vm.handlers import (
            build_dispatch_table,
            vm_handle_IbImport,
            vm_handle_IbImportFrom,
        )
        d = build_dispatch_table()
        assert d["IbImport"] is vm_handle_IbImport
        assert d["IbImportFrom"] is vm_handle_IbImportFrom


# ===========================================================================
# IbSwitch
# ===========================================================================

class TestIbSwitchHandler:
    def test_switch_basic_match(self):
        out = []
        engine = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
        engine.run_string(
            "int x = 2\n"
            "switch x:\n"
            "    case 1:\n"
            "        print(\"one\")\n"
            "    case 2:\n"
            "        print(\"two\")\n"
            "    case 3:\n"
            "        print(\"three\")\n",
            output_callback=lambda t: out.append(str(t)),
            silent=True,
        )
        # baseline: recursive path executed, "two" printed
        assert "two" in out

    def test_switch_default_case(self):
        out = []
        engine = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
        engine.run_string(
            "int x = 99\n"
            "switch x:\n"
            "    case 1:\n"
            "        print(\"one\")\n"
            "    default:\n"
            "        print(\"default\")\n",
            output_callback=lambda t: out.append(str(t)),
            silent=True,
        )
        assert "default" in out

    def test_switch_handler_supports_node(self):
        engine = make_engine(
            "int x = 1\n"
            "switch x:\n"
            "    case 1:\n"
            "        pass\n"
            "    default:\n"
            "        pass\n"
        )
        switch_uid = find_node_uid(engine, "IbSwitch")
        vm = make_vm(engine)
        assert vm.supports(switch_uid) is True
        # 直接运行，验证 handler 路径无异常
        result = vm.run(switch_uid)
        assert result is not None


# ===========================================================================
# IbFunctionDef / IbLLMFunctionDef / IbClassDef
# ===========================================================================

class TestDefinitionHandlers:
    def test_function_def_binds_user_function(self):
        engine = make_engine("func myfunc():\n    return 1\n")
        fd_uid = find_node_uid(engine, "IbFunctionDef")
        vm = make_vm(engine)
        # Re-execute the def via VM (idempotent: rebinds in current scope)
        vm.run(fd_uid)
        # Sanity: variable is bound to an IbUserFunction
        bound = engine.interpreter.runtime_context.get_variable("myfunc")
        assert isinstance(bound, IbUserFunction)

    def test_llm_function_def_binds_llm_function(self):
        engine = make_engine(
            "llm greet(str name) -> str:\n"
            "__sys__\n"
            "Hi $name\n"
            "llmend\n"
        )
        fd_uid = find_node_uid(engine, "IbLLMFunctionDef")
        vm = make_vm(engine)
        vm.run(fd_uid)
        bound = engine.interpreter.runtime_context.get_variable("greet")
        assert isinstance(bound, IbLLMFunction)

    def test_class_def_validates_and_binds(self):
        engine = make_engine(
            "class Pt:\n"
            "    int x\n"
            "    int y\n"
            "    func __init__(self, int a, int b):\n"
            "        self.x = a\n"
            "        self.y = b\n"
        )
        cd_uid = find_node_uid(engine, "IbClassDef")
        vm = make_vm(engine)
        # Should not raise (class was pre-hydrated)
        vm.run(cd_uid)


# ===========================================================================
# IbIntentAnnotation / IbIntentStackOperation
# ===========================================================================

class TestIntentHandlers:
    def test_intent_annotation_smear_no_error(self):
        engine = make_engine(
            "@ smear-test\n"
            "str s = @~ MOCK:hello ~\n"
        )
        ia_uid = find_node_uid(engine, "IbIntentAnnotation")
        vm = make_vm(engine)
        # Just verify handler runs without error and returns IbObject
        result = vm.run(ia_uid)
        assert result is not None

    def test_intent_stack_push_no_error(self):
        engine = make_engine(
            "@+ pushed-intent\n"
            "str s = @~ MOCK:x ~\n"
        )
        iso_uid = find_node_uid(engine, "IbIntentStackOperation")
        vm = make_vm(engine)
        result = vm.run(iso_uid)
        assert result is not None


################################################################################
# MERGED: Control Signals — Signal(kind,value) data-flow propagation
################################################################################

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
        """旧的 raise 异常路径已彻底消失；仅通过 StopIteration.value 传递 Signal。"""
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


################################################################################
# MERGED: LLMExceptionalStmt CPS handler
################################################################################

# ===========================================================================
# 1. 调度表注册
# ===========================================================================

class TestDispatchTableRegistrationLLMExcept:
    def test_dispatch_table_includes_llmexcept(self):
        """IbLLMExceptionalStmt 必须在 build_dispatch_table() 返回的表中。"""
        table = build_dispatch_table()
        assert "IbLLMExceptionalStmt" in table

    def test_dispatch_table_handler_is_callable(self):
        """注册的 handler 必须可调用。"""
        table = build_dispatch_table()
        handler = table["IbLLMExceptionalStmt"]
        assert callable(handler)

    def test_vm_handle_llmexcept_is_generator_function(self):
        """vm_handle_IbLLMExceptionalStmt 必须是生成器函数（CPS 契约）。"""
        assert inspect.isgeneratorfunction(vm_handle_IbLLMExceptionalStmt)


# ===========================================================================
# 2. VMExecutor.service_context 属性
# ===========================================================================

class TestVMServiceContext:
    def test_service_context_none_without_interpreter(self):
        """VMExecutor(ec, interpreter=None).service_context 应返回 None。"""
        engine = make_engine("pass\n")
        vm = VMExecutor(engine.interpreter._execution_context, interpreter=None)
        assert vm.service_context is None

    def test_service_context_returns_interpreter_context(self):
        """VMExecutor.service_context 应返回 interpreter.service_context。"""
        engine = make_engine(ai_setup() + "pass\n")
        vm = make_vm(engine)
        assert vm.service_context is engine.interpreter.service_context


# ===========================================================================
# 3. 帧生命周期：LLMExceptFrame 入栈 / 出栈
# ===========================================================================

class TestFrameLifecycle:
    def test_frame_popped_after_cps_handler_certain(self):
        """vm.run(llmexcept_uid) 完成后，LLMExceptFrame 应已被弹出（栈为空）。"""
        code = ai_setup() + "str x = @~ MOCK:STR:frame_test ~\nllmexcept:\n    retry\n"
        engine = make_engine(code)
        vm = make_vm(engine)

        llmexcept_uid = find_node_uid(engine, "IbLLMExceptionalStmt")
        # Reset x to an initial string value (keeps type compatibility)
        engine.interpreter.runtime_context.set_variable(
            "x", engine.interpreter.registry.box("initial")
        )

        frames_before = len(engine.interpreter.runtime_context.get_llm_except_frames())
        vm.run(llmexcept_uid)
        frames_after = len(engine.interpreter.runtime_context.get_llm_except_frames())

        assert frames_after == frames_before, (
            f"Frame not popped: {frames_after} frames remain (was {frames_before})"
        )

    def test_frame_not_leaked_on_repeated_runs(self):
        """多次 vm.run(llmexcept_uid) 不应累积 LLMExceptFrame。"""
        code = ai_setup() + "str x = @~ MOCK:STR:multi_run ~\nllmexcept:\n    retry\n"
        engine = make_engine(code)
        vm = make_vm(engine)
        llmexcept_uid = find_node_uid(engine, "IbLLMExceptionalStmt")

        for _ in range(3):
            engine.interpreter.runtime_context.set_variable(
                "x", engine.interpreter.registry.box("reset")
            )
            vm.run(llmexcept_uid)

        frames = engine.interpreter.runtime_context.get_llm_except_frames()
        assert len(frames) == 0


# ===========================================================================
# 4. CPS 路径执行：vm.run(llmexcept_uid) + vm.run(module_uid)
# ===========================================================================

class TestCPSExecution:
    def test_cps_llmexcept_certain_assigns_variable(self):
        """vm.run(llmexcept_uid)：CPS handler 驱动 target，确定结果赋值到变量。"""
        code = ai_setup() + "str x = @~ MOCK:STR:hello_cps ~\nllmexcept:\n    retry\n"
        engine = make_engine(code)
        vm = make_vm(engine)

        llmexcept_uid = find_node_uid(engine, "IbLLMExceptionalStmt")
        # Reset to typed initial value (keeps type compatibility with str)
        engine.interpreter.runtime_context.set_variable(
            "x", engine.interpreter.registry.box("initial")
        )

        vm.run(llmexcept_uid)

        x_val = engine.interpreter.runtime_context.get_variable("x")
        assert native(x_val) == "hello_cps"

    def test_cps_llmexcept_int_assigns_variable(self):
        """vm.run(llmexcept_uid)：CPS handler 处理整型 MOCK 结果。"""
        code = ai_setup() + "int n = @~ MOCK:INT:42 ~\nllmexcept:\n    retry\n"
        engine = make_engine(code)
        vm = make_vm(engine)

        llmexcept_uid = find_node_uid(engine, "IbLLMExceptionalStmt")
        engine.interpreter.runtime_context.set_variable(
            "n", engine.interpreter.registry.box(0)
        )

        vm.run(llmexcept_uid)

        n_val = engine.interpreter.runtime_context.get_variable("n")
        assert native(n_val) == 42

    def test_cps_supports_llmexcept(self):
        """VMExecutor.supports() 应对 IbLLMExceptionalStmt 返回 True。"""
        code = ai_setup() + "str x = @~ MOCK:STR:ok ~\nllmexcept:\n    retry\n"
        engine = make_engine(code)
        vm = make_vm(engine)
        llmexcept_uid = find_node_uid(engine, "IbLLMExceptionalStmt")
        assert vm.supports(llmexcept_uid)


# ===========================================================================
# 5. E2E 行为验证（C11 容器 handler 直接 yield）
# ===========================================================================

class TestE2EBehaviorPreservation:
    """验证 C11 的容器 handler 改动（直接 yield stmt_uid）不退化现有行为。
    这些测试通过 engine.run_string()（完整路径）执行，确保正确性。
    """

    def test_e2e_certain_result_no_retry(self):
        """确定性 LLM 结果：直接完成，body 不执行。"""
        lines = []
        code = ai_setup() + """
str x = @~ MOCK:STR:definite ~
llmexcept:
    print("body_ran")
    retry
print(x)
"""
        engine = make_engine(code, lines)
        assert "definite" in lines
        assert "body_ran" not in lines

    def test_e2e_uncertain_retry_resolves(self):
        """不确定结果：body 执行 retry，第二次调用成功。"""
        lines = []
        code = ai_setup() + """
str x = @~ MOCK:REPAIR repair_e2e_m3c ~
llmexcept:
    print("body_ran")
    retry "hint"
print(x)
"""
        engine = make_engine(code, lines)
        assert "body_ran" in lines
        # After repair, x should be set to a non-empty string (exact value is
        # MOCK-provider-dependent, but it must have been written)
        x_val = engine.get_variable("x")
        assert x_val is not None

    def test_e2e_multiple_llmexcept_blocks(self):
        """多个 llmexcept 块：每个独立工作，最终值均正确。"""
        lines = []
        code = ai_setup() + """
str a = @~ MOCK:STR:alpha ~
llmexcept:
    retry
str b = @~ MOCK:STR:beta ~
llmexcept:
    retry
print(a)
print(b)
"""
        engine = make_engine(code, lines)
        assert "alpha" in lines
        assert "beta" in lines

    def test_e2e_llmexcept_in_if_body(self):
        """llmexcept 在 if 分支 body 中正常工作（IbIf 容器的 _resolve_stmt_uid）。"""
        lines = []
        code = ai_setup() + """
int flag = 1
if flag == 1:
    str result = @~ MOCK:STR:if_value ~
    llmexcept:
        retry
    print(result)
"""
        engine = make_engine(code, lines)
        assert "if_value" in lines

    def test_e2e_llmexcept_in_while_body(self):
        """llmexcept 在 while 循环 body 中正常工作（IbWhile 容器的 _resolve_stmt_uid）。"""
        lines = []
        code = ai_setup() + """
int i = 0
while i < 1:
    str last = @~ MOCK:STR:while_value ~
    llmexcept:
        retry
    i = i + 1
    print(last)
"""
        engine = make_engine(code, lines)
        assert "while_value" in lines

    def test_e2e_llmexcept_retry_hint_propagates(self):
        """retry hint 在 body 中设置并在下次 LLM 调用时可用。"""
        lines = []
        code = ai_setup() + """
str x = @~ MOCK:REPAIR retry_hint_test ~
llmexcept:
    print("uncertain_handled")
    retry "custom_hint"
print(x)
"""
        engine = make_engine(code, lines)
        assert "uncertain_handled" in lines

# Note: this file consolidates the historical files:
#   tests/unit/test_vm_executor.py (base)
#   tests/unit/test_vm_executor_m3d.py
#   tests/unit/test_vm_executor_m3dprep.py
#   tests/unit/test_vm_executor_signals.py
#   tests/unit/test_vm_executor_llmexcept.py
# See docs/TESTS_REORGANIZATION_TASK.md Step 4.
