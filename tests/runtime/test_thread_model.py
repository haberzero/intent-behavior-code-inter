"""
线程对象模型测试（任务 C1）：thread[T] 构造 + 句柄方法 + 生命周期状态机。

覆盖：
- 构造：``thread(callable=..., args=...)`` 关键字参数
- join：返回 thread_result[T] 容器
- is_done：状态查询
- 多线程并发
- 状态机：done 后 is_done 为 True
"""

from tests.conftest import run_ibci


def test_thread_construct_and_join():
    code = """
func compute(str x) -> int:
    return 42

thread[int] t = thread(callable=compute, args=["x"])
thread_result[int] r = t.join()
print((str)r.expect())
"""
    lines = run_ibci(code)
    assert lines == ["42"]


def test_thread_join_with_args():
    code = """
func add(int a, int b) -> int:
    return a + b

thread[int] t = thread(callable=add, args=[1, 2])
thread_result[int] r = t.join()
print((str)r.expect())
"""
    lines = run_ibci(code)
    assert lines == ["3"]


def test_thread_is_done_state_machine():
    code = """
func add(int a, int b) -> int:
    return a + b

thread[int] t = thread(callable=add, args=[1, 2])
print((str)t.is_done())
thread_result[int] r = t.join()
print((str)r.expect())
print((str)t.is_done())
"""
    lines = run_ibci(code)
    assert lines == ["False", "3", "True"]


def test_thread_multiple_concurrency():
    code = """
func work(int x) -> int:
    return x * 2

thread[int] a = thread(callable=work, args=[21])
thread[int] b = thread(callable=work, args=[50])
print((str)a.join().expect())
print((str)b.join().expect())
print((str)(a.is_done() and b.is_done()))
"""
    lines = run_ibci(code)
    assert lines == ["42", "100", "True"]


def test_thread_void_return():
    code = """
func greet(str name) -> void:
    print("hi")
    return

thread[void] t = thread(callable=greet, args=["world"])
t.join()
print("done")
"""
    lines = run_ibci(code)
    assert lines == ["hi", "done"]


def test_thread_cancel():
    code = """
chan c = chan(str, "message")
func work(chan x) -> int:
    str m = x.recv()
    return 1

thread[int] t = thread(callable=work, args=[c])
TaskCancelled e = t.cancel()
print(e.message)
c.send("x")
t.join()
print((str)t.is_done())
"""
    lines = run_ibci(code)
    assert lines == ["Task was cancelled", "True"]


def test_thread_isolation_does_not_leak_main_scope():
    code = """
int shared = 100

func mutate() -> int:
    shared = 999
    return shared

thread[int] t = thread(callable=mutate, args=[])
t.join()
print((str)shared)
print((str)t.join().expect())
"""
    lines = run_ibci(code)
    # 任务不写主环境作用域（隔离边界）；主作用域 shared 保持 100。
    assert lines == ["100", "999"]