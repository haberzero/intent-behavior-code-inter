"""
tests/runtime/test_scheduler_threadpool_lifecycle.py
=====================================================

PT-SYNC-3：LLMExecutor 线程池资源生命周期（fail-fast）测试。

锁定关闭后禁止复用线程池的不变量：
- 首次 ``_get_thread_pool()`` 惰性建池且复用同一实例
- ``close()`` 后再次 ``_get_thread_pool()`` 抛 ``RuntimeError``（不再静默重建）
- ``close()`` 幂等（重复调用安全）
- ``close()`` 后 ``_thread_pool`` 置 None

用最小 stub 直接驱动 ``_SchedulerMixin`` 的池生命周期逻辑（白盒不变式测试）；
真实 executor 的 ``_closed`` 初始化由全量并发/批处理测试间接守护（若 __init__
未置位，所有并发路径会 AttributeError）。
"""
import threading

import pytest

from core.runtime.interpreter.llm_executor._scheduler import _SchedulerMixin


class _StubScheduler(_SchedulerMixin):
    """最小调度器：仅承载线程池生命周期所需状态。"""

    def __init__(self):
        self._thread_pool = None
        self._max_workers = 4
        self._closed = False
        self._pending_futures = {}
        self._pending_futures_lock = threading.Lock()


class TestThreadPoolLifecycle:
    def test_lazy_pool_created_and_reused(self):
        s = _StubScheduler()
        assert s._thread_pool is None
        pool = s._get_thread_pool()
        assert s._thread_pool is not None
        assert s._get_thread_pool() is pool  # 复用同一实例

    def test_close_then_get_pool_raises(self):
        s = _StubScheduler()
        s._get_thread_pool()
        s.close()
        with pytest.raises(RuntimeError):
            s._get_thread_pool()

    def test_close_idempotent(self):
        s = _StubScheduler()
        s.close()
        s.close()  # 第二次调用不抛

    def test_close_sets_pool_none(self):
        s = _StubScheduler()
        s._get_thread_pool()
        s.close()
        assert s._thread_pool is None