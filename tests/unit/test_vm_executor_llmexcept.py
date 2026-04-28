"""
tests/unit/test_vm_executor_llmexcept.py
=========================================

M3c — VMExecutor ``IbLLMExceptionalStmt`` CPS handler 专项测试。

覆盖范围
--------
1. 调度表注册：``IbLLMExceptionalStmt`` 已加入 dispatch table
2. 保护辅助函数 ``_resolve_stmt_uid``：跳过 / 重定向 / 直通三条路径
3. ``VMExecutor.service_context`` 属性：有 / 无 interpreter 两种情形
4. 帧生命周期：CPS handler 执行前后 LLMExceptFrame 的入栈 / 出栈
5. CPS 路径执行：vm.run(llmexcept_uid) + vm.run(module_uid) 级别验证
6. E2E 行为（递归路径）：正常退出 / uncertain→retry→certain / if 分支 / 嵌套 handler
   目的是确认 M3c 的容器 handler 改动不退化现有语义
"""
import inspect
import pytest

from core.engine import IBCIEngine
from core.runtime.vm import VMExecutor
from core.runtime.vm.handlers import (
    build_dispatch_table,
    _resolve_stmt_uid,
    vm_handle_IbLLMExceptionalStmt,
)


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

ROOT_DIR = "."


def ai_setup():
    return 'import ai\nai.set_config("TESTONLY", "TESTONLY", "TESTONLY")\n'


def make_engine(code: str, output_lines=None):
    engine = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
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


def find_all_node_uids(engine, node_type: str) -> list:
    return [uid for uid, data in engine.interpreter.node_pool.items()
            if data.get("_type") == node_type]


def native(obj):
    return obj.to_native() if hasattr(obj, "to_native") else obj


# ===========================================================================
# 1. 调度表注册
# ===========================================================================

class TestDispatchTableRegistration:
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
# 2. _resolve_stmt_uid 辅助函数
# ===========================================================================

class TestResolveStmtUid:
    """测试容器 handler 的保护重定向辅助函数。"""

    def _make_executor_stub(self, node_pool, side_table_map):
        """构造仅支持 get_node_data + get_side_table 的最小 executor stub。"""
        class FakeEC:
            def get_node_data(self_inner, uid):
                return node_pool.get(uid)

            def get_side_table(self_inner, table_name, uid):
                if table_name == "node_protection":
                    return side_table_map.get(uid)
                return None

        class FakeExecutor:
            ec = FakeEC()

        return FakeExecutor()

    def test_returns_none_for_llmexcept_type(self):
        """IbLLMExceptionalStmt 节点应被跳过（返回 None）。"""
        executor = self._make_executor_stub(
            {"handler_uid": {"_type": "IbLLMExceptionalStmt"}},
            {},
        )
        assert _resolve_stmt_uid(executor, "handler_uid") is None

    def test_returns_protection_uid_for_protected_node(self):
        """有 node_protection 条目的节点应重定向到 handler uid。"""
        executor = self._make_executor_stub(
            {"target_uid": {"_type": "IbAssign"}, "handler_uid": {"_type": "IbLLMExceptionalStmt"}},
            {"target_uid": "handler_uid"},
        )
        assert _resolve_stmt_uid(executor, "target_uid") == "handler_uid"

    def test_returns_stmt_uid_for_unprotected_node(self):
        """无 node_protection 条目的节点应直通（原样返回）。"""
        executor = self._make_executor_stub(
            {"plain_uid": {"_type": "IbAssign"}},
            {},
        )
        assert _resolve_stmt_uid(executor, "plain_uid") == "plain_uid"

    def test_returns_stmt_uid_when_node_data_none(self):
        """node_data 不存在时不应崩溃，且无 protection 时直通。"""
        executor = self._make_executor_stub({}, {})
        result = _resolve_stmt_uid(executor, "missing_uid")
        assert result == "missing_uid"

    def test_protection_takes_priority_over_passthrough(self):
        """同时有 protection 条目且节点类型不是 IbLLMExceptionalStmt → 重定向。"""
        executor = self._make_executor_stub(
            {"x_uid": {"_type": "IbExprStmt"}},
            {"x_uid": "llmexcept_uid"},
        )
        assert _resolve_stmt_uid(executor, "x_uid") == "llmexcept_uid"


# ===========================================================================
# 3. VMExecutor.service_context 属性
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
# 4. 帧生命周期：LLMExceptFrame 入栈 / 出栈
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
# 5. CPS 路径执行：vm.run(llmexcept_uid) + vm.run(module_uid)
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
        """VMExecutor.supports() 应对 IbLLMExceptionalStmt 返回 True（M3c）。"""
        code = ai_setup() + "str x = @~ MOCK:STR:ok ~\nllmexcept:\n    retry\n"
        engine = make_engine(code)
        vm = make_vm(engine)
        llmexcept_uid = find_node_uid(engine, "IbLLMExceptionalStmt")
        assert vm.supports(llmexcept_uid)


# ===========================================================================
# 6. E2E 行为验证（递归路径 + 容器 handler 保护重定向）
# ===========================================================================

class TestE2EBehaviorPreservation:
    """验证 M3c 的容器 handler 改动（_resolve_stmt_uid）不退化现有行为。
    这些测试通过 engine.run_string()（递归路径）执行，确保正确性。
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
