"""
tests/runtime/test_task_scheduler.py
====================================

Stage 2 多任务协作调度器（``TaskScheduler``）测试。

锁定：
- 多任务并发：等待不同 waitable 的任务总时近似 max 而非 sum（真并发）
- 挂起/恢复：waitable 未就绪 → 挂起；就绪 → 恢复
- 完成值按提交序收集
- yield 非 waitable → fail-fast（RuntimeError）
- 空调度器 → 空结果
"""
import time
from typing import Any

import pytest

from core.runtime.vm.task_scheduler import TaskScheduler, Waitable


class _ManualWaitable(Waitable):
    """可控完成的 waitable：外部 set_result 后 is_done 变 True。"""

    def __init__(self, delay_s: float = 0.0):
        self._delay = delay_s
        self._ready_after = time.monotonic() + delay_s
        self._result = None
        self._result_set = False

    def is_done(self) -> bool:
        return self._result_set or (self._delay > 0 and time.monotonic() >= self._ready_after)

    def result(self) -> Any:
        return self._result

    def set_result(self, value):
        self._result = value
        self._result_set = True


def _task_await(waitable, value):
    """一个任务：等待 waitable，返回 value。"""
    res = yield waitable
    return value


def _task_immediate(value):
    """一个任务：不挂起，直接完成（生成器）。"""
    return value
    yield  # pragma: no cover


class TestTaskScheduler:

    def test_empty_returns_empty(self):
        assert TaskScheduler().run() == []

    def test_immediate_tasks_complete_in_order(self):
        s = TaskScheduler()
        s.submit(_task_immediate("a"))
        s.submit(_task_immediate("b"))
        s.submit(_task_immediate("c"))
        assert s.run() == ["a", "b", "c"]

    def test_suspend_and_resume_on_waitable(self):
        s = TaskScheduler()
        w = _ManualWaitable()
        s.submit(_task_await(w, "done"))
        # 未就绪 → 挂起，run 不应返回（仍等待）
        # 手动就绪后 run 才完成
        w.set_result(None)
        assert s.run() == ["done"]

    def test_concurrent_tasks_overlap(self):
        """两个任务各等 0.2s，总时应显著小于 0.4s（真并发）。"""
        s = TaskScheduler()
        w1 = _ManualWaitable(delay_s=0.2)
        w2 = _ManualWaitable(delay_s=0.2)
        s.submit(_task_await(w1, "t1"))
        s.submit(_task_await(w2, "t2"))
        t0 = time.monotonic()
        results = s.run()
        elapsed = time.monotonic() - t0
        assert results == ["t1", "t2"]
        # 并发：总时 ~ max(0.2) 而非 sum(0.4)
        assert elapsed < 0.35, f"串行化迹象: {elapsed:.3f}s"

    def test_yield_non_waitable_fails_fast(self):
        s = TaskScheduler()

        def bad_gen():
            yield 42  # 非 waitable

        s.submit(bad_gen())
        with pytest.raises(RuntimeError):
            s.run()

    def test_mixed_immediate_and_awaiting(self):
        s = TaskScheduler()
        w = _ManualWaitable(delay_s=0.05)
        s.submit(_task_immediate("fast"))
        s.submit(_task_await(w, "slow"))
        assert s.run() == ["fast", "slow"]