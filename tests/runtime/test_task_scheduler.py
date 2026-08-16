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
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

import pytest

from core.runtime.vm.task_scheduler import TaskScheduler, Waitable
from core.runtime.shared.llm_result import LLMFuture, LLMResult


class _ManualWaitable(Waitable):
    """可控完成的 waitable：外部 set_result 后 is_done 变 True。"""

    def __init__(self, delay_s: float = 0.0):
        self._delay = delay_s
        self._ready_after = time.monotonic() + delay_s
        self._result = None
        self._result_set = False

    @property
    def is_done(self) -> bool:
        return self._result_set or (self._delay > 0 and time.monotonic() >= self._ready_after)

    def try_result(self) -> Any:
        if self.is_done:
            return (True, self._result)
        return (False, None)

    def result(self) -> Any:
        return self._result

    def set_result(self, value):
        self._result = value
        self._result_set = True


class _FutureWaitable(Waitable):
    """把真实的 ``concurrent.futures.Future`` 适配为 Waitable（LLM executor 实际基底）。"""

    def __init__(self, future: Future):
        self._future = future

    @property
    def is_done(self) -> bool:
        return self._future.done()

    def try_result(self) -> Any:
        if self._future.done():
            return (True, self._future.result())
        return (False, None)

    def result(self) -> Any:
        return self._future.result()

    def register_wake(self, event) -> None:
        self._future.add_done_callback(lambda _f: event.set())


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

    def test_real_concurrent_futures_overlap(self):
        """用真实 concurrent.futures.Future（LLM executor 实际基底）验证并发。

        两个任务各等待一个由线程池 0.2s 后完成的 Future，总时应显著小于 0.4s。
        """
        s = TaskScheduler()
        with ThreadPoolExecutor(max_workers=2) as pool:
            f1 = pool.submit(lambda: time.sleep(0.2) or "t1")
            f2 = pool.submit(lambda: time.sleep(0.2) or "t2")
            s.submit(_task_await(_FutureWaitable(f1), "t1"))
            s.submit(_task_await(_FutureWaitable(f2), "t2"))
            t0 = time.monotonic()
            results = s.run()
            elapsed = time.monotonic() - t0
        # 并发完成序不确定，只断言结果集与总时（真并发）
        assert sorted(results) == ["t1", "t2"]
        assert elapsed < 0.35, f"串行化迹象: {elapsed:.3f}s"

    def test_real_llm_future_is_waitable(self):
        """LLMFuture 结构符合 Waitable 协议，可直接被调度器 await。"""
        f = Future()
        lf = LLMFuture(node_uid="n", future=f)
        assert isinstance(lf, Waitable)  # runtime_checkable Protocol 结构匹配

        s = TaskScheduler()
        s.submit(_task_await(lf, "llm-ok"))
        f.set_result(LLMResult.success_result(value=None, raw_response="r"))
        assert s.run() == ["llm-ok"]

    def test_results_in_submission_order_not_completion_order(self):
        """结果按提交序返回，而非完成序（完成序不可预测）。

        后提交的任务先完成（t2 先就绪），但 run() 结果仍按提交序 [t1, t2]。
        """
        s = TaskScheduler()
        w1 = _ManualWaitable(delay_s=0.2)  # t1 慢
        w2 = _ManualWaitable(delay_s=0.05)  # t2 快（先完成）
        s.submit(_task_await(w1, "t1"))  # index 0
        s.submit(_task_await(w2, "t2"))  # index 1
        results = s.run()
        # 提交序 [t1, t2]，而非完成序 [t2, t1]
        assert results == ["t1", "t2"]


class TestNotifyWake:
    """通知式唤醒：waitable 完成时经 register_wake 即时唤醒调度器（不轮询 park）。"""

    def test_register_wake_called_on_wait(self):
        """任务挂起时调度器对 waitable 注册完成通知。"""
        s = TaskScheduler()
        w = _ManualWaitable()
        events = []

        orig = _ManualWaitable.register_wake
        try:
            def _reg(self, event):
                events.append(event)
                orig(self, event)
            _ManualWaitable.register_wake = _reg
            s.submit(_task_await(w, "done"))
            w.set_result(None)
            assert s.run() == ["done"]
            assert len(events) == 1  # 挂起时注册了一次
            assert events[0] is s._wake_event
        finally:
            _ManualWaitable.register_wake = orig

    def test_wake_event_set_on_completion(self):
        """waitable 完成时设置唤醒事件（无需等待 park 超时）。"""
        import threading as _threading

        s = TaskScheduler()
        f = Future()
        events = []

        orig_reg = _FutureWaitable.register_wake
        try:
            def _traced_reg(self, event):
                events.append(event)
                orig_reg(self, event)
            _FutureWaitable.register_wake = _traced_reg
            s.submit(_task_await(_FutureWaitable(f), "done"))
            # 单独线程稍后完成 future → 应触发事件
            t0 = time.monotonic()
            def _finish():
                time.sleep(0.05)
                f.set_result("x")
            th = _threading.Thread(target=_finish, daemon=True)
            th.start()
            results = s.run()
            elapsed = time.monotonic() - t0
            assert results == ["done"]
            assert len(events) == 1  # register_wake 被调用（通知注册）
            # 通知式唤醒：总时≈waitable 完成时刻（~50ms），而非轮询延迟叠加（≫50ms）
            assert elapsed < 0.2
        finally:
            _FutureWaitable.register_wake = orig_reg

    def test_manual_waitable_without_register_wake_falls_back(self):
        """无 register_wake 的 waitable（结构性协议允许缺失）退回首轮询，仍可完成。"""
        s = TaskScheduler()
        w = _ManualWaitable(delay_s=0.05)  # 时间驱动，无通知
        s.submit(_task_await(w, "done"))
        assert s.run() == ["done"]


class TestTaskCancellation:
    """调度器级协作取消（阶段 1c）：步进边界 gen.throw(TaskCancelled)，finally 执行，结果槽标记取消。"""

    def test_cancel_delivers_and_unwinds(self):
        import threading as _threading

        from core.runtime.vm.task_scheduler import TaskCancelled

        s = TaskScheduler()
        events = []

        def gen():
            try:
                w = yield _ManualWaitable()
                events.append(("resumed", w))
            finally:
                events.append("finally")

        s.submit(gen())
        holder = {}

        def _run():
            holder["results"] = s.run()

        th = _threading.Thread(target=_run, daemon=True)
        th.start()
        time.sleep(0.05)  # 让任务进入等待
        s.cancel()
        th.join(timeout=2)
        assert not th.is_alive()
        assert "finally" in events  # 任务体 finally 执行（资源清理）
        assert isinstance(holder["results"][0], TaskCancelled)

    def test_cancel_before_run_delivers(self):
        from core.runtime.vm.task_scheduler import TaskCancelled

        s = TaskScheduler()
        events = []

        def gen():
            try:
                yield _ManualWaitable()
                events.append("resumed")
            finally:
                events.append("finally")

        s.submit(gen())
        s.cancel()
        results = s.run()
        assert isinstance(results[0], TaskCancelled)
        # 未启动即取消：生成器从未运行，body 未进入 → finally 不执行（无清理负担）
        assert events == []

    def test_cancel_one_of_many(self):
        from core.runtime.vm.task_scheduler import TaskCancelled

        s = TaskScheduler()
        s.submit(_task_await(_ManualWaitable(), "a"), node_uid="a")  # 永不完成
        s.submit(_task_immediate("b"), node_uid="b")
        s.cancel(0)
        results = s.run()
        assert isinstance(results[0], TaskCancelled)
        assert results[1] == "b"
