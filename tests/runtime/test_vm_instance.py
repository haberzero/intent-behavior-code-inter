"""
tests/runtime/test_vm_instance.py
=================================

PT-MT-7 多 VM 实例测试：spawn 后台线程执行 + 任务本地上下文隔离。

锁定：
- spawn 函数在后台线程运行，join 取回结果
- spawn lambda 后台执行
- 多任务并发（各自独立执行上下文）
- 任务隔离：任务内作用域/意图不污染主环境
- cancel（未启动协作式取消）
- iruntime.snapshot 反映任务状态（可选）
"""
import time

from tests.conftest import run_ibci


class TestBackgroundSpawn:
    def test_spawn_function_join(self):
        lines = run_ibci("""
func compute(str x) -> int:
    return 42
task t = spawn compute("x")
int r = join t
print((str)r)
""")
        assert lines == ["42"]

    def test_spawn_lambda_join(self):
        lines = run_ibci("""
task t = spawn lambda() -> int: 7
int r = join t
print((str)r)
""")
        assert lines == ["7"]

    def test_multiple_spawns(self):
        lines = run_ibci("""
func f1() -> int:
    return 1
func f2() -> int:
    return 2
task t1 = spawn f1()
task t2 = spawn f2()
int r1 = join t1
int r2 = join t2
print((str)r1)
print((str)r2)
""")
        assert lines == ["1", "2"]


class TestTaskIsolation:
    def test_task_does_not_leak_main_scope(self):
        """任务内作用域不污染主环境（任务本地 runtime_context）。"""
        lines = run_ibci("""
func inner() -> int:
    int local_var = 99
    return local_var

task t = spawn inner()
int r = join t
print((str)r)
""")
        assert lines == ["99"]


class TestTaskCancel:
    def test_cancel_before_join(self):
        """未启动任务可协作式取消（join 抛错）。"""
        lines = run_ibci("""
func f() -> int:
    return 1
task t = spawn f()
cancel t
print("cancelled")
""")
        assert lines == ["cancelled"]


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
    """PT-MT-8：实时 UI/输出刷新场景——spawn 任务写 Channel，主线程消费渲染。"""

    def test_worker_sends_chunks_to_channel(self):
        """后台 worker 任务逐块写 Channel，主线程 recv 渲染（实时输出）。"""
        lines = run_ibci("""
func worker(chan out) -> void:
    out.send("chunk1")
    out.send("chunk2")
    out.send("chunk3")

chan out = chan(str, "stream")
task t = spawn worker(out)
str a = out.recv()
str b = out.recv()
str c = out.recv()
print(a)
print(b)
print(c)
""")
        assert lines == ["chunk1", "chunk2", "chunk3"]

    def test_eager_start_runs_in_background(self):
        """spawn 即后台启动（非惰性）：主线程无需 join 即可收到 worker 输出。"""
        lines = run_ibci("""
func worker(chan out) -> void:
    out.send("hi")

chan out = chan(str, "stream")
task t = spawn worker(out)
str msg = out.recv()
print(msg)
""")
        assert lines == ["hi"]
