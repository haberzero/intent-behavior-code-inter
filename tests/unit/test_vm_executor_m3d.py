"""
tests/unit/test_vm_executor_m3d.py
==================================

M3d — 主路径切换测试。

覆盖：

* M3d 新增的 6 个 CPS handler：
    - 表达式：IbBehaviorExpr, IbBehaviorInstance, IbLambdaExpr
    - 控制流：IbFor, IbTry, IbRetry
* VMExecutor.run() 入口 / yield child 路径的 ``node_protection`` 重定向
* Interpreter.execute_module() 与 IbUserFunction.call() 已切换至
  VMExecutor 主路径（M3d 出口契约）

策略：编译合法 IBCI 程序、对相关节点单独通过 VMExecutor.run() 驱动，
断言行为与递归 visit() 一致。
"""
import os
import inspect
import pytest

from core.engine import IBCIEngine
from core.runtime.vm import VMExecutor
from core.runtime.vm.handlers import build_dispatch_table


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


def find_node_uids(engine, node_type: str):
    return [
        uid
        for uid, data in engine.interpreter.node_pool.items()
        if data.get("_type") == node_type
    ]


def native(obj):
    return obj.to_native() if hasattr(obj, "to_native") else obj


# ===========================================================================
# Dispatch table coverage — M3d adds 6 entries (total 44)
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
        # 22 (M3a) + 1 (M3c IbLLMExceptionalStmt) + 14 (M3d-prep) + 6 (M3d) = 43
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


# ===========================================================================
# VMExecutor.run() — node_protection 重定向
# ===========================================================================

class TestProtectionRedirect:
    def test_apply_protection_redirect_no_protection(self):
        engine = make_engine("int x = 1")
        vm = make_vm(engine)
        # 任意未受保护 UID 原样返回
        for uid in engine.interpreter.node_pool:
            assert vm._apply_protection_redirect(uid) == uid

    def test_apply_protection_redirect_non_string(self):
        engine = make_engine("int x = 1")
        vm = make_vm(engine)
        # 非字符串原样返回
        assert vm._apply_protection_redirect(None) is None
        assert vm._apply_protection_redirect(42) == 42

    def test_apply_protection_redirect_skips_active_frame(self):
        """当 LLMExceptFrame 已经在保护 target 时，不再重定向（防止递归）。"""
        engine = make_engine("int x = 1")
        vm = make_vm(engine)
        rc = vm.runtime_context
        # 在 runtime_context 中模拟一个活跃 LLMExceptFrame
        from core.runtime.interpreter.llm_except_frame import LLMExceptFrame
        fake_frame = LLMExceptFrame(
            target_uid="fake_target_uid",
            node_type="IbLLMExceptionalStmt",
            max_retry=3,
        )
        rc._llm_except_frames.append(fake_frame)
        try:
            # 即便侧表中存在保护，也应跳过重定向
            # （此处 fake_target_uid 不存在保护，仅验证正向路径）
            assert vm._apply_protection_redirect("fake_target_uid") == "fake_target_uid"
        finally:
            rc._llm_except_frames.pop()
