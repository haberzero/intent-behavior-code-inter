"""
tests/unit/test_vm_executor.py
==============================

M3a — VMExecutor (CPS Scheduling Loop) 骨架测试。

测试策略
--------
* 使用 IBCIEngine 编译并执行一段引导代码（创建符号 + 节点池）。
* 通过 ``find_node_uid`` 在 ``interpreter.node_pool`` 中定位特定 AST 节点。
* 通过 :class:`VMExecutor` （而非递归 ``visit()``）重新执行该节点子树，
  断言结果或副作用与既有解释器语义一致。

覆盖范围（M3a 实现的节点类型）：
    * 表达式：IbConstant, IbName, IbBinOp, IbUnaryOp, IbBoolOp, IbCompare,
              IbIfExp, IbCall, IbAttribute, IbSubscript, IbTuple, IbListExpr
    * 语句  ：IbModule, IbPass, IbExprStmt, IbAssign, IbIf, IbWhile,
              IbReturn, IbBreak, IbContinue
    * 数据类：VMTask, VMTaskResult, ControlSignal, ControlSignalException
    * 调度  ：fallback_visit, supports, step_count
"""
import os
import pytest

from core.engine import IBCIEngine
from core.runtime.vm import (
    VMExecutor,
    VMTask,
    VMTaskResult,
    ControlSignal,
    ControlSignalException,
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


# ===========================================================================
# 1. 数据类：VMTask / VMTaskResult / ControlSignal
# ===========================================================================

class TestVMDataClasses:
    def test_control_signal_enum_values(self):
        assert ControlSignal.RETURN.value == "return"
        assert ControlSignal.BREAK.value == "break"
        assert ControlSignal.CONTINUE.value == "continue"
        assert ControlSignal.THROW.value == "throw"

    def test_control_signal_exception_carries_signal_and_value(self):
        exc = ControlSignalException(ControlSignal.RETURN, "v")
        assert exc.signal is ControlSignal.RETURN
        assert exc.value == "v"
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
        # IbBreak alone raises ControlSignalException; must propagate to caller.
        engine = make_engine("int x = 0\nwhile x < 1:\n    break\n    x = x + 1\n")
        # Find an IbBreak node and run it directly via VM
        break_uid = find_node_uid(engine, "IbBreak")
        vm = make_vm(engine)
        with pytest.raises(ControlSignalException) as ei:
            vm.run(break_uid)
        assert ei.value.signal is ControlSignal.BREAK

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
        with pytest.raises(ControlSignalException) as ei:
            vm.run(ret_uid)
        assert ei.value.signal is ControlSignal.RETURN
        assert native(ei.value.value) == 42


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
# 9. 调度器特性：supports / fallback_visit / step_count
# ===========================================================================

class TestSchedulerInfrastructure:
    def test_supports_known_node(self):
        engine = make_engine("int x = 1 + 2")
        binop_uid = find_node_uid(engine, "IbBinOp")
        vm = make_vm(engine)
        assert vm.supports(binop_uid) is True

    def test_supports_unknown_node(self):
        # M3d 完成后所有 IBCI AST 节点类型都纳入调度表；通过注入一个未实现的
        # 伪节点类型来验证 supports() 的兜底逻辑（_dispatch 查表 miss → False）。
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

    def test_fallback_visit_returns_value(self):
        engine = make_engine("int x = 1")
        binop_uid_or_const = find_node_uid(engine, "IbConstant", lambda u, d: d.get("value") == 1)
        vm = make_vm(engine)
        result = vm.fallback_visit(binop_uid_or_const)
        assert native(result) == 1

    def test_run_with_none_returns_none(self):
        engine = make_engine("pass")
        vm = make_vm(engine)
        result = vm.run(None)
        # Returns IbNone
        assert result is not None

    def test_run_unsupported_root_falls_back(self):
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
# 10. 端到端 CPS-vs-递归一致性
# ===========================================================================

class TestCpsVsRecursiveParity:
    def test_arithmetic_parity(self):
        engine = make_engine("int x = 0")
        # Build several expressions and compare results
        engine = make_engine("int a = 1 + 2\nint b = 3 * 4\nint c = (5 + 6) * 7\n")
        for binop_uid in find_all_node_uids(engine, "IbBinOp"):
            vm = make_vm(engine)
            cps_val = vm.run(binop_uid)
            recursive_val = engine.interpreter.visit(binop_uid)
            assert native(cps_val) == native(recursive_val)

    def test_compare_parity(self):
        engine = make_engine(
            "bool a = 1 < 2\n"
            "bool b = 5 == 5\n"
            "bool c = 7 != 8\n"
            "bool d = 3 >= 3\n"
        )
        for cmp_uid in find_all_node_uids(engine, "IbCompare"):
            vm = make_vm(engine)
            assert native(vm.run(cmp_uid)) == native(engine.interpreter.visit(cmp_uid))

    def test_module_parity_simple_program(self):
        # Run via recursive, capture variable;
        # reset, run via VM, ensure same final state.
        code = (
            "int total = 0\n"
            "int i = 0\n"
            "while i < 10:\n"
            "    total = total + i\n"
            "    i = i + 1\n"
        )
        engine = make_engine(code)
        recursive_total = native(engine.get_variable("total"))
        recursive_i = native(engine.get_variable("i"))
        # Reset and re-run via VM
        reset_var(engine, "total", 0)
        reset_var(engine, "i", 0)
        module_uid = find_node_uid(engine, "IbModule")
        vm = make_vm(engine)
        vm.run(module_uid)
        assert native(engine.get_variable("total")) == recursive_total == 45
        assert native(engine.get_variable("i")) == recursive_i == 10


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
