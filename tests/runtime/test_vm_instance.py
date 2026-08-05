"""
tests/runtime/test_vm_instance.py
=================================

线程对象模型多 VM 实例测试。

锁定：
- thread 函数在后台线程运行，join 取回结果（thread_result）
- thread lambda 后台执行
- 多线程并发（各自独立执行上下文）
- 线程隔离：任务内作用域/意图不污染主环境
- cancel（未启动协作式取消）
- iruntime.snapshot 反映任务状态
- 实时输出：后台 worker 写 Channel，主线程消费渲染
"""
import time

from tests.conftest import run_ibci


class TestBackgroundThread:
    def test_thread_function_join(self):
        lines = run_ibci("""
func compute(str x) -> int:
    return 42
thread[int] t = thread(callable=compute, args=["x"])
print((str)t.join().expect())
""")
        assert lines == ["42"]

    def test_thread_lambda_join(self):
        lines = run_ibci("""
fn f = lambda() -> int: 7
thread[int] t = thread(callable=f, args=[])
print((str)t.join().expect())
""")
        assert lines == ["7"]

    def test_multiple_threads(self):
        lines = run_ibci("""
func f1() -> int:
    return 1
func f2() -> int:
    return 2
thread[int] t1 = thread(callable=f1, args=[])
thread[int] t2 = thread(callable=f2, args=[])
print((str)t1.join().expect())
print((str)t2.join().expect())
""")
        assert lines == ["1", "2"]


class TestTaskIsolation:
    def test_task_does_not_leak_main_scope(self):
        """任务内作用域不污染主环境（任务本地 runtime_context）。"""
        lines = run_ibci("""
func inner() -> int:
    int local_var = 99
    return local_var

thread[int] t = thread(callable=inner, args=[])
print((str)t.join().expect())
""")
        assert lines == ["99"]


class TestTaskCancel:
    def test_cancel_before_join(self):
        """线程可协作式取消。

        线程体阻塞在 chan recv 上（确定性挂起），cancel 命中挂起点——
        快函数线程可能在 cancel 前自然完成（竞态），旧无条件返回 TaskCancelled
        掩盖了它；改为阻塞挂起场景验证协作取消。
        """
        lines = run_ibci("""
chan c = chan(str, "message")
func f(chan x) -> int:
    str m = x.recv()
    return 1
thread[int] t = thread(callable=f, args=[c])
TaskCancelled e = t.cancel()
print(e.message)
c.send("x")
""")
        assert lines == ["Task was cancelled"]


class TestSnapshotReflectsTasks:
    def test_snapshot_includes_task_fields(self):
        """snapshot() 返回 tasks 字段（字段存在性）。"""
        lines = run_ibci("""
import iruntime
dict snap = iruntime.snapshot()
print(snap)
""")
        assert "tasks" in lines[0]


class TestRealtimeOutput:
    """实时 UI/输出刷新场景——线程写 Channel，主线程消费渲染。"""

    def test_worker_sends_chunks_to_channel(self):
        """后台 worker 线程逐块写 Channel，主线程 recv 渲染（实时输出）。"""
        lines = run_ibci("""
func worker(chan out) -> void:
    out.send("chunk1")
    out.send("chunk2")
    out.send("chunk3")

chan out = chan(str, "stream")
thread[void] t = thread(callable=worker, args=[out])
str a = out.recv()
str b = out.recv()
str c = out.recv()
print(a)
print(b)
print(c)
""")
        assert lines == ["chunk1", "chunk2", "chunk3"]

    def test_eager_start_runs_in_background(self):
        """thread 构造即后台启动（非惰性）：主线程无需 join 即可收到 worker 输出。"""
        lines = run_ibci("""
func worker(chan out) -> void:
    out.send("hi")

chan out = chan(str, "stream")
thread[void] t = thread(callable=worker, args=[out])
str msg = out.recv()
print(msg)
""")
        assert lines == ["hi"]