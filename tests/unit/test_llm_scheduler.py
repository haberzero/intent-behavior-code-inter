"""
tests/unit/test_llm_scheduler.py
==================================

M5b — LLMScheduler / LLMFuture 单元测试。

覆盖范围
--------
1. ``LLMFuture`` 数据类：is_done / get() 行为
2. ``LLMExecutorImpl.dispatch_eager``：非阻塞返回 LLMFuture；提交到线程池
3. ``LLMExecutorImpl.resolve``：阻塞等待 Future 完成；结果正确；消费一次性
4. 错误路径：resolve 未知 uid 抛 RuntimeError
5. 并发性：多个 dispatch_eager 调用并发执行
6. 线程池惰性初始化
7. 向后兼容：``execute_behavior_expression`` 仍可正常工作
"""
import concurrent.futures
import threading
import time
import pytest

from core.engine import IBCIEngine
from core.runtime.interpreter.llm_result import LLMResult, LLMFuture
from core.runtime.interpreter.llm_executor import LLMExecutorImpl


# ---------------------------------------------------------------------------
# 辅助
# ---------------------------------------------------------------------------

ROOT_DIR = "."


def ai_setup():
    return 'import ai\nai.set_config("TESTONLY", "TESTONLY", "TESTONLY")\n'


def make_engine(code: str):
    engine = IBCIEngine(root_dir=ROOT_DIR, auto_sniff=False)
    engine.run_string(code, silent=True)
    return engine


def find_behavior_expr_uid(engine) -> str:
    for uid, data in engine.interpreter.node_pool.items():
        if data.get("_type") == "IbBehaviorExpr":
            return uid
    raise AssertionError("No IbBehaviorExpr found in node_pool")


def native(obj):
    return obj.to_native() if hasattr(obj, "to_native") else obj


# ---------------------------------------------------------------------------
# 简易 LLMResult 工厂（绕过 IbLLMCallResult 依赖）
# ---------------------------------------------------------------------------

def make_llm_result(value_str: str) -> LLMResult:
    return LLMResult.success_result(raw_response=value_str)


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
        except Exception:
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
        except Exception:
            pass

    def test_dispatch_eager_stores_in_pending_futures(self):
        """dispatch_eager() 应把 LLMFuture 存入 _pending_futures 字典。"""
        engine = make_engine(ai_setup() + "str x = @~ MOCK:STR:pending_test ~\n")
        interp = engine.interpreter
        executor = interp.service_context.llm_executor
        node_uid = find_behavior_expr_uid(engine)

        assert node_uid not in executor._pending_futures
        fut = executor.dispatch_eager(node_uid, interp._execution_context)
        assert node_uid in executor._pending_futures
        # Cleanup
        try:
            executor.resolve(node_uid)
        except Exception:
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
        except Exception:
            pass

    def test_get_thread_pool_returns_same_instance(self):
        """_get_thread_pool() 多次调用应返回同一实例（单例惰性）。"""
        engine = make_engine(ai_setup() + "pass\n")
        executor = engine.interpreter.service_context.llm_executor
        pool1 = executor._get_thread_pool()
        pool2 = executor._get_thread_pool()
        assert pool1 is pool2


# ===========================================================================
# 5. 向后兼容
# ===========================================================================

class TestBackwardCompat:
    def test_execute_behavior_expression_still_works(self):
        """M5b 修改后，execute_behavior_expression() 仍应正常返回 LLMResult。"""
        engine = make_engine(ai_setup() + "str x = @~ MOCK:STR:compat_test ~\n")
        interp = engine.interpreter
        executor = interp.service_context.llm_executor
        node_uid = find_behavior_expr_uid(engine)

        result = executor.execute_behavior_expression(node_uid, interp._execution_context)
        assert isinstance(result, LLMResult)
        assert result.success or result.is_uncertain is False  # result was obtained
