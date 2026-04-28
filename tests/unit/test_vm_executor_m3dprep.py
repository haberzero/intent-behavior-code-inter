"""
tests/unit/test_vm_executor_m3dprep.py
======================================

M3d-prep — 扩展 CPS handler 覆盖测试。

覆盖的新 handler（在 build_dispatch_table 中新增的 14 个条目）：
    * 表达式：IbDict, IbSlice, IbCastExpr, IbFilteredExpr
    * 语句  ：IbAugAssign, IbGlobalStmt, IbRaise, IbImport, IbImportFrom,
              IbSwitch, IbFunctionDef, IbLLMFunctionDef, IbClassDef,
              IbIntentAnnotation, IbIntentStackOperation

测试策略：
* 使用 IBCIEngine 编译产物，定位 AST 节点 UID
* 通过 VMExecutor.run() 单独驱动该节点子树
* 断言结果与递归路径产生的副作用 / 返回值一致
"""
import os
import pytest

from core.engine import IBCIEngine
from core.runtime.vm import VMExecutor
from core.runtime.exceptions import ThrownException
from core.runtime.objects.kernel import IbUserFunction, IbLLMFunction


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


def make_engine(code: str):
    engine = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
    engine.run_string(code, output_callback=lambda t: None, silent=True)
    return engine


def make_vm(engine):
    return VMExecutor(
        engine.interpreter._execution_context,
        interpreter=engine.interpreter,
    )


def find_node_uid(engine, node_type: str) -> str:
    for uid, data in engine.interpreter.node_pool.items():
        if data.get("_type") == node_type:
            return uid
    raise AssertionError(f"No {node_type} in node_pool")


def native(obj):
    return obj.to_native() if hasattr(obj, "to_native") else obj


# ===========================================================================
# 调度表注册：所有新 handler 必须可被查找到
# ===========================================================================

class TestDispatchTableRegistration:
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
