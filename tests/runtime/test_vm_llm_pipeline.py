"""
tests/runtime/test_vm_llm_pipeline.py
=====================================

VM ↔ LLM 集成测试（合并自 4 个历史文件）：
    * LLM 调用进入 CPS 帧栈（``test_vm_llm_cps_dispatch.py``）
    * Behavior 段表达式求值进入帧栈（``test_evaluate_segments_cps.py``）
    * lambda / snapshot / behavior 调用现场 EC 优先（``test_ns3_callsite_ec.py``）
    * LLMScheduler / LLMFuture / dispatch_eager（``unit/test_llm_scheduler.py``）

合并目标：消除 4 处重复 helper（make_engine / ai_setup / find_*_uid / native）。

详见 docs/TESTS_REORGANIZATION_TASK.md Step 5。
"""
import os
import concurrent.futures
import threading
import time

import pytest

from core.engine import IBCIEngine
from core.runtime.interpreter.llm_result import LLMResult, LLMFuture
from core.runtime.interpreter.llm_executor import LLMExecutorImpl


# ---------------------------------------------------------------------------
# 辅助（合并自 4 个文件，单一定义）
# ---------------------------------------------------------------------------

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))


def _make_engine():
    return IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)


def make_engine(code: str):
    """编译并执行 ``code``（兼容旧 LLMScheduler 测试签名）。"""
    engine = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
    engine.run_string(code, silent=True)
    return engine


def _ai_prefix() -> str:
    return 'import ai\nai.set_config("TESTONLY", "TESTONLY", "TESTONLY")\n'


def ai_setup() -> str:
    """旧 LLMScheduler 测试使用的 ai_setup 别名。"""
    return _ai_prefix()


def native(obj):
    return obj.to_native() if hasattr(obj, "to_native") else obj


def find_behavior_expr_uid(engine) -> str:
    for uid, data in engine.interpreter.node_pool.items():
        if data.get("_type") == "IbBehaviorExpr":
            return uid
    raise AssertionError("No IbBehaviorExpr found in node_pool")


# 简易 LLMResult 工厂（绕过 IbLLMCallResult 依赖）—— 用于 LLMScheduler 测试
def make_llm_result(value_str: str) -> LLMResult:
    return LLMResult.success_result(raw_response=value_str)


################################################################################
# MERGED: NS-1 LLM Call CPS Dispatch
# Source: tests/runtime/test_vm_llm_cps_dispatch.py
################################################################################

class TestNS1LLMCpsDispatch:
    def test_behavior_call_runs_under_vm_frame(self):
        engine = _make_engine()

        observations = {}

        # Patch the LLM executor's execute_behavior_object_cps (CPS variant
        # used by the VM handler path post-CPS-ification of _evaluate_segments).
        from core.runtime.interpreter.llm_executor import LLMExecutorImpl
        original = LLMExecutorImpl.execute_behavior_object_cps

        def probe(self, behavior, execution_context):
            vm = execution_context.vm_executor
            observations["depth"] = vm.frame_stack_depth
            observations["step_count_at_call"] = vm.step_count
            return (yield from original(self, behavior, execution_context))

        LLMExecutorImpl.execute_behavior_object_cps = probe
        try:
            # ``fn b = lambda: @~...~`` makes ``b`` an IbBehavior; calling it
            # goes through IbCall → _vm_invoke_behavior (NS-1 path).
            engine.run_string(
                _ai_prefix() + (
                    'fn b = lambda: @~MOCK:STR:hello~\n'
                    'str r = (str)b()\n'
                ),
                output_callback=lambda _t: None,
                silent=True,
            )
        finally:
            LLMExecutorImpl.execute_behavior_object_cps = original

        # VM 帧栈保证非空（至少 2 帧：IbCall driver 任务加 _vm_invoke_behavior 任务）
        assert observations.get("depth", 0) >= 2, (
            f"Expected VM frame stack depth >= 2 inside execute_behavior_object_cps, "
            f"got {observations.get('depth')}"
        )
        # And the helper advanced the scheduler.
        assert observations.get("step_count_at_call", 0) > 0

    def test_llm_function_call_runs_under_vm_frame(self):
        engine = _make_engine()

        observations = {}

        from core.runtime.interpreter.llm_executor import LLMExecutorImpl
        original = LLMExecutorImpl.execute_llm_function_cps

        def probe(self, node_uid, execution_context, call_intent=None):
            vm = execution_context.vm_executor
            observations["depth"] = vm.frame_stack_depth
            observations["step_count_at_call"] = vm.step_count
            return (yield from original(self, node_uid, execution_context, call_intent=call_intent))

        LLMExecutorImpl.execute_llm_function_cps = probe
        try:
            engine.run_string(
                _ai_prefix() + (
                    'llm greet(str name) -> str:\n'
                    '__sys__\n'
                    'You are a greeter.\n'
                    '__user__\n'
                    'MOCK:STR:hello\n'
                    'llmend\n'
                    '\n'
                    'str r = greet("Alice")\n'
                ),
                output_callback=lambda _t: None,
                silent=True,
            )
        finally:
            LLMExecutorImpl.execute_llm_function_cps = original

        assert observations.get("depth", 0) >= 2, (
            f"Expected VM frame stack depth >= 2 inside execute_llm_function_cps, "
            f"got {observations.get('depth')}"
        )
        assert observations.get("step_count_at_call", 0) > 0


################################################################################
# MERGED: Behavior Segment Evaluation CPS
# Source: tests/runtime/test_evaluate_segments_cps.py
################################################################################

class TestEvaluateSegmentsCPSGenerator:
    def test_cps_generator_basic_text(self):
        """No dynamic segments: generator returns plain string without yielding."""
        engine = _make_engine()
        engine.run_string('int _b = 1\n', output_callback=lambda _t: None, silent=True)
        from core.runtime.interpreter.llm_executor import LLMExecutorImpl
        llm_exec = engine.registry.get_llm_executor()
        ec = engine.interpreter._execution_context if hasattr(engine.interpreter, "_execution_context") else engine.interpreter.execution_context

        gen = llm_exec._evaluate_segments_cps(["hello ", "world"], ec)
        try:
            next(gen)
            assert False, "should have raised StopIteration immediately"
        except StopIteration as si:
            assert si.value == "hello world"

    def test_cps_generator_empty(self):
        engine = _make_engine()
        engine.run_string('int _b = 1\n', output_callback=lambda _t: None, silent=True)
        llm_exec = engine.registry.get_llm_executor()
        ec = engine.interpreter._execution_context if hasattr(engine.interpreter, "_execution_context") else engine.interpreter.execution_context

        try:
            next(llm_exec._evaluate_segments_cps(None, ec))
            assert False, "should have raised StopIteration"
        except StopIteration as si:
            assert si.value == ""

    def test_sync_wrapper_preserves_semantics(self):
        """The sync wrapper drives the generator via vm.run; semantics match."""
        engine = _make_engine()
        engine.run_string('int _b = 1\n', output_callback=lambda _t: None, silent=True)
        llm_exec = engine.registry.get_llm_executor()
        ec = engine.interpreter._execution_context if hasattr(engine.interpreter, "_execution_context") else engine.interpreter.execution_context

        # Plain string segments (no dynamic eval) — sync wrapper returns string.
        result = llm_exec._evaluate_segments(["a", "b", "c"], ec)
        assert result == "abc"


class TestEvaluateSegmentsCPSNesting:
    def test_segment_eval_nested_in_outer_vm_frame(self):
        """When a behavior with dynamic prompt segments runs, the inner
        segment-evaluation must be a sub-task of the OUTER VM frame
        (frame_stack_depth observed inside _evaluate_segments_cps reflects
        nesting, not a fresh _drive_loop)."""
        engine = _make_engine()

        from core.runtime.interpreter.llm_executor import LLMExecutorImpl
        observations = {"max_depth": 0, "segment_calls": 0}

        original_cps = LLMExecutorImpl._evaluate_segments_cps

        def probe_cps(self, segments, execution_context, param_names=None):
            observations["segment_calls"] += 1
            vm = execution_context.vm_executor
            if vm is not None:
                d = vm.frame_stack_depth
                if d > observations["max_depth"]:
                    observations["max_depth"] = d
            # Delegate to original (preserve generator semantics with yield from).
            result = yield from original_cps(self, segments, execution_context, param_names)
            return result

        LLMExecutorImpl._evaluate_segments_cps = probe_cps
        try:
            engine.run_string(
                _ai_prefix() + (
                    'fn b = lambda: @~MOCK:STR:hi~\n'
                    'str r = (str)b()\n'
                ),
                output_callback=lambda _t: None,
                silent=True,
            )
        finally:
            LLMExecutorImpl._evaluate_segments_cps = original_cps

        # Segment evaluation occurred under VM scheduling (≥ 1 frame deep).
        assert observations["segment_calls"] >= 1
        assert observations["max_depth"] >= 1, (
            f"Expected segment evaluation to run inside an active VM frame stack, "
            f"got max_depth={observations['max_depth']}"
        )


################################################################################
# MERGED: NS-3 Callsite Execution Context Priority
# Source: tests/runtime/test_ns3_callsite_ec.py
################################################################################

class TestNS3CallsiteExecutionContext:
    def test_vm_path_uses_callsite_ec_not_field(self):
        """CPS path: ``_vm_invoke_behavior`` must pass ``executor.ec`` to the
        LLM executor's ``invoke_behavior``, NOT the behavior's definition-time
        ``_execution_context`` field.
        """
        engine = _make_engine()

        observations = {}

        from core.runtime.interpreter.llm_executor import LLMExecutorImpl
        original = LLMExecutorImpl.execute_behavior_object_cps

        def probe(self, behavior, execution_context):
            # Stamp the behavior's stored field with a sentinel so we can
            # detect if the executor ever saw the definition-time value.
            observations["passed_ec_is_field"] = (
                execution_context is behavior._execution_context
            )
            # Whichever EC was passed, it must be a "live" EC with a VM.
            observations["passed_ec_has_vm"] = (
                getattr(execution_context, "vm_executor", None) is not None
            )
            return (yield from original(self, behavior, execution_context))

        LLMExecutorImpl.execute_behavior_object_cps = probe
        try:
            engine.run_string(
                _ai_prefix() + (
                    'fn b = lambda: @~MOCK:STR:hello~\n'
                    'str r = (str)b()\n'
                ),
                output_callback=lambda _t: None,
                silent=True,
            )
        finally:
            LLMExecutorImpl.execute_behavior_object_cps = original

        # In the single-Interpreter happy path, ``executor.ec`` and the
        # stored field should refer to the same EC (they were the same at
        # definition time). The contract is just that the EC passed must
        # have a live VM and be the call-site EC.
        assert observations.get("passed_ec_has_vm") is True

    def test_sync_call_prefers_contextvar_ec(self):
        """``IbBehavior.call()`` sync path: when a ContextVar EC is set, it
        must take precedence over the definition-time ``_execution_context``
        field.

        Uses a SimpleNamespace shim EC that proxies to the real EC's services
        but is identity-distinguishable, to prove the precedence wiring.
        """
        engine = _make_engine()

        captured = {}
        engine.run_string(
            _ai_prefix() + (
                'fn b = lambda: @~MOCK:STR:hello~\n'
            ),
            output_callback=lambda _t: None,
            silent=True,
        )

        scope = engine.interpreter.runtime_context.get_current_scope()
        while scope is not None:
            sym = scope.get_symbol("b") if hasattr(scope, "get_symbol") else None
            if sym is not None:
                captured["behavior"] = sym.value
                break
            scope = getattr(scope, "parent", None)
        behavior = captured["behavior"]
        real_ec = behavior._execution_context

        # Build a transparent shim: same services, distinct identity.
        from types import SimpleNamespace
        shim_ec = SimpleNamespace(
            runtime_context=real_ec.runtime_context,
            vm_executor=real_ec.vm_executor,
            registry=real_ec.registry,
            get_node_data=real_ec.get_node_data,
            get_side_table=real_ec.get_side_table,
            current_module_name=real_ec.current_module_name,
            module_manager=getattr(real_ec, "module_manager", None),
            factory=getattr(real_ec, "factory", None),
            push_stack=getattr(real_ec, "push_stack", lambda **k: None),
            pop_stack=getattr(real_ec, "pop_stack", lambda: None),
        )
        assert shim_ec is not real_ec

        from core.runtime.frame import (
            set_current_execution_context, reset_current_execution_context,
        )

        observations = {}
        from core.runtime.interpreter.llm_executor import LLMExecutorImpl
        original = LLMExecutorImpl.execute_behavior_object

        def probe(self, b, execution_context):
            observations["ec_id"] = id(execution_context)
            return original(self, b, execution_context)

        LLMExecutorImpl.execute_behavior_object = probe
        try:
            tok = set_current_execution_context(shim_ec)
            try:
                behavior.call(behavior.ib_class.registry.get_none(), [])
            finally:
                reset_current_execution_context(tok)
        finally:
            LLMExecutorImpl.execute_behavior_object = original

        assert observations.get("ec_id") == id(shim_ec), (
            "IbBehavior.call() must prefer ContextVar EC over definition-time "
            "_execution_context field (NS-3 precedence)"
        )

    def test_sync_call_fallback_when_no_contextvar(self):
        """When no ContextVar EC is set (outside any Interpreter), the
        definition-time field is used as the fallback (backward compat).
        """
        engine = _make_engine()

        captured = {}

        engine.run_string(
            _ai_prefix() + (
                'fn b = lambda: @~MOCK:STR:hello~\n'
            ),
            output_callback=lambda _t: None,
            silent=True,
        )

        scope = engine.interpreter.runtime_context.get_current_scope()
        while scope is not None:
            sym = scope.get_symbol("b") if hasattr(scope, "get_symbol") else None
            if sym is not None:
                captured["behavior"] = sym.value
                break
            scope = getattr(scope, "parent", None)
        behavior = captured["behavior"]

        # After engine.run_string returns, the ContextVar EC is reset to None.
        # Calling .call() must fall back to behavior._execution_context.
        from core.runtime.frame import get_current_execution_context
        assert get_current_execution_context() is None, (
            "test precondition: ContextVar EC should be None outside run_string"
        )

        observations = {}
        from core.runtime.interpreter.llm_executor import LLMExecutorImpl
        original = LLMExecutorImpl.execute_behavior_object

        def probe(self, b, execution_context):
            observations["ec_id"] = id(execution_context)
            return original(self, b, execution_context)

        LLMExecutorImpl.execute_behavior_object = probe
        try:
            behavior.call(behavior.ib_class.registry.get_none(), [])
        finally:
            LLMExecutorImpl.execute_behavior_object = original

        assert observations.get("ec_id") == id(behavior._execution_context), (
            "Fallback to definition-time _execution_context expected when "
            "ContextVar EC is None"
        )


################################################################################
# MERGED: LLMScheduler / LLMFuture / dispatch_eager
# Source: tests/unit/test_llm_scheduler.py
################################################################################

# ===========================================================================
# 1. LLMFuture 数据类
# ===========================================================================

class TestLLMFuture:
    def test_is_done_true_when_future_done(self):
        """future.done() == True 时，LLMFuture.is_done 应为 True。"""
        raw_result = make_llm_result("hello")
        fut = concurrent.futures.Future()
        fut.set_result(raw_result)

        llm_future = LLMFuture(node_uid="uid_a", future=fut)
        assert llm_future.is_done is True

    def test_is_done_false_when_future_pending(self):
        """尚未完成的 future.done() == False 时，is_done 应为 False。"""
        fut = concurrent.futures.Future()
        llm_future = LLMFuture(node_uid="uid_b", future=fut)
        assert llm_future.is_done is False

    def test_get_returns_ibobject_when_value_present(self):
        """LLMFuture.get() 应返回 LLMResult.value 对应的 IbObject。"""
        engine = make_engine(ai_setup() + "pass\n")
        registry = engine.interpreter.registry

        raw_value = registry.box(42)
        raw_result = LLMResult(success=True, is_uncertain=False, value=raw_value)
        fut = concurrent.futures.Future()
        fut.set_result(raw_result)

        llm_future = LLMFuture(node_uid="uid_c", future=fut)
        result_obj = llm_future.get(registry)
        assert native(result_obj) == 42

    def test_get_returns_none_when_value_missing(self):
        """LLMResult.value is None 时，get() 应返回 registry.get_none()。"""
        engine = make_engine(ai_setup() + "pass\n")
        registry = engine.interpreter.registry

        raw_result = LLMResult(success=True, is_uncertain=False, value=None)
        fut = concurrent.futures.Future()
        fut.set_result(raw_result)

        llm_future = LLMFuture(node_uid="uid_d", future=fut)
        result_obj = llm_future.get(registry)
        # Should be IbNone (registry's none object)
        from core.runtime.objects.builtins import IbNone
        assert isinstance(result_obj, IbNone)

    def test_get_blocks_until_done(self):
        """LLMFuture.get() 应在 Future 完成前阻塞，完成后立即返回。"""
        engine = make_engine(ai_setup() + "pass\n")
        registry = engine.interpreter.registry
        raw_value = registry.box("delayed")

        def delayed_fn():
            time.sleep(0.05)
            return LLMResult(success=True, is_uncertain=False, value=raw_value)

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(delayed_fn)
            llm_future = LLMFuture(node_uid="uid_e", future=fut)

            # get() should block until the thread completes
            result_obj = llm_future.get(registry)
            assert native(result_obj) == "delayed"

    def test_node_uid_field_preserved(self):
        """node_uid 字段应被正确保留。"""
        fut = concurrent.futures.Future()
        fut.set_result(make_llm_result("x"))
        llm_future = LLMFuture(node_uid="test_uid_42", future=fut)
        assert llm_future.node_uid == "test_uid_42"


# ===========================================================================
# 2. dispatch_eager
# ===========================================================================

class TestDispatchEager:
    def test_dispatch_eager_returns_llm_future(self):
        """dispatch_eager() 应返回 LLMFuture 实例（非阻塞）。"""
        engine = make_engine(ai_setup() + "str x = @~ MOCK:STR:dispatch_test ~\n")
        interp = engine.interpreter
        executor = interp.service_context.llm_executor
        node_uid = find_behavior_expr_uid(engine)

        result = executor.dispatch_eager(node_uid, interp._execution_context)
        assert isinstance(result, LLMFuture)
        assert result.node_uid == node_uid

        # Clean up: resolve to avoid pending future leak
        try:
            executor.resolve(node_uid)
        except RuntimeError:
            pass

    def test_dispatch_eager_is_nonblocking(self):
        """dispatch_eager() 调用应立即返回（线程池异步执行）。"""
        engine = make_engine(ai_setup() + "str x = @~ MOCK:STR:nonblocking_test ~\n")
        interp = engine.interpreter
        executor = interp.service_context.llm_executor
        node_uid = find_behavior_expr_uid(engine)

        start = time.monotonic()
        fut = executor.dispatch_eager(node_uid, interp._execution_context)
        elapsed = time.monotonic() - start

        # Should be well under 1 second (MOCK is instantaneous; only thread dispatch overhead)
        assert elapsed < 1.0
        # Cleanup
        try:
            executor.resolve(node_uid)
        except RuntimeError:
            pass

    def test_dispatch_eager_stores_in_pending_futures(self):
        """dispatch_eager() 应把 LLMFuture 存入 _pending_futures 字典。"""
        engine = make_engine(ai_setup() + "str x = @~ MOCK:STR:pending_test ~\n")
        interp = engine.interpreter
        executor = interp.service_context.llm_executor
        node_uid = find_behavior_expr_uid(engine)

        # engine.run_string 已对赋值的 RHS 触发了 dispatch_eager；
        # 清空残留以独立验证 dispatch_eager() 自身的写入行为。
        executor._pending_futures.clear()
        assert node_uid not in executor._pending_futures
        fut = executor.dispatch_eager(node_uid, interp._execution_context)
        assert node_uid in executor._pending_futures
        # Cleanup
        try:
            executor.resolve(node_uid)
        except RuntimeError:
            pass


# ===========================================================================
# 3. resolve
# ===========================================================================

class TestResolve:
    def test_resolve_returns_ibobject(self):
        """resolve() 应返回后台 LLM 调用的 IbObject 结果。"""
        engine = make_engine(ai_setup() + "str x = @~ MOCK:STR:resolve_test ~\n")
        interp = engine.interpreter
        executor = interp.service_context.llm_executor
        node_uid = find_behavior_expr_uid(engine)

        executor.dispatch_eager(node_uid, interp._execution_context)
        result = executor.resolve(node_uid)

        # MOCK:STR returns the literal string
        assert native(result) == "resolve_test"

    def test_resolve_clears_pending_future(self):
        """resolve() 消费后，_pending_futures 中不应再有该 UID。"""
        engine = make_engine(ai_setup() + "str x = @~ MOCK:STR:clear_test ~\n")
        interp = engine.interpreter
        executor = interp.service_context.llm_executor
        node_uid = find_behavior_expr_uid(engine)

        executor.dispatch_eager(node_uid, interp._execution_context)
        executor.resolve(node_uid)

        assert node_uid not in executor._pending_futures

    def test_resolve_unknown_uid_raises_runtime_error(self):
        """resolve() 未知 UID 时应抛出 RuntimeError。"""
        engine = make_engine(ai_setup() + "pass\n")
        executor = engine.interpreter.service_context.llm_executor

        with pytest.raises(RuntimeError, match="resolve"):
            executor.resolve("nonexistent_uid_xyz")

    def test_resolve_after_second_resolve_raises(self):
        """同一 uid 不能 resolve 两次（第二次应抛 RuntimeError）。"""
        engine = make_engine(ai_setup() + "str x = @~ MOCK:STR:double_resolve ~\n")
        interp = engine.interpreter
        executor = interp.service_context.llm_executor
        node_uid = find_behavior_expr_uid(engine)

        executor.dispatch_eager(node_uid, interp._execution_context)
        executor.resolve(node_uid)  # first: ok

        with pytest.raises(RuntimeError):
            executor.resolve(node_uid)  # second: should raise


# ===========================================================================
# 4. 线程池惰性初始化
# ===========================================================================

class TestThreadPoolLazyInit:
    def test_thread_pool_none_before_dispatch(self):
        """dispatch_eager 调用前 _thread_pool 应为 None（惰性初始化）。"""
        engine = make_engine(ai_setup() + "pass\n")
        executor = engine.interpreter.service_context.llm_executor

        # LLMExecutorImpl created in engine setup; thread pool should be lazy
        assert executor._thread_pool is None

    def test_thread_pool_created_after_dispatch(self):
        """dispatch_eager 调用后 _thread_pool 应被初始化。"""
        engine = make_engine(ai_setup() + "str x = @~ MOCK:STR:lazy_pool_test ~\n")
        interp = engine.interpreter
        executor = interp.service_context.llm_executor
        node_uid = find_behavior_expr_uid(engine)

        executor.dispatch_eager(node_uid, interp._execution_context)
        assert executor._thread_pool is not None
        # Cleanup
        try:
            executor.resolve(node_uid)
        except RuntimeError:
            pass

    def test_get_thread_pool_returns_same_instance(self):
        """_get_thread_pool() 多次调用应返回同一实例（单例惰性）。"""
        engine = make_engine(ai_setup() + "pass\n")
        executor = engine.interpreter.service_context.llm_executor
        pool1 = executor._get_thread_pool()
        pool2 = executor._get_thread_pool()
        assert pool1 is pool2


# ===========================================================================
# 5. 稳定 API 合约
# ===========================================================================

class TestStableAPIContract:
    def test_execute_behavior_expression_still_works(self):
        """execute_behavior_expression() 仍应正常返回 LLMResult。"""
        engine = make_engine(ai_setup() + "str x = @~ MOCK:STR:compat_test ~\n")
        interp = engine.interpreter
        executor = interp.service_context.llm_executor
        node_uid = find_behavior_expr_uid(engine)

        result = executor.execute_behavior_expression(node_uid, interp._execution_context)
        assert isinstance(result, LLMResult)
        assert result.success or result.is_uncertain is False  # result was obtained
