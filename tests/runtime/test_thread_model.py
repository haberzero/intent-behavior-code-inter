"""
线程对象模型测试：thread[T] 构造 + 句柄方法 + 生命周期状态机。

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
    """is_done 状态机：阻塞挂起时 False → 完成后 True（以真实状态为准）。

    线程体阻塞在 chan recv 上（确定性挂起），is_done 如实反映未完成；
    send 唤醒后 join 取回结果，is_done 转 True。快函数线程可能在 is_done()
    前自然完成（竞态），旧读 _state 的实现掩盖了它。
    """
    code = """
chan c = chan(str, "message")
func add(chan x) -> int:
    str _ = x.recv()
    return 1 + 2

thread[int] t = thread(callable=add, args=[c])
print((str)t.is_done())
c.send("go")
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


def test_thread_body_recursion_trampolined():
    """线程体内用户函数递归经 trampoline 驱动，不嵌套 Python 栈。

    线程体 ``_drive_generator`` 经 trampoline 驱动 UserFunctionCall 递归，与
    VM 主路径同构：线程内深递归（n≈20）Python 深度恒定。同时验证线程体
    可解析模块级函数（全局作用域链到模块作用域）。
    """
    code = """
func compute(int n) -> int:
    if n <= 1:
        return 1
    return compute(n - 1) + 1

thread[int] t = thread(callable=compute, args=[300])
thread_result[int] r = t.join()
print((str)r.expect())
"""
    lines = run_ibci(code)
    assert lines == ["300"]


def test_thread_cancel():
    code = """
chan c = chan(str, "message")
func work(chan x) -> int:
    str m = x.recv()
    return 1

thread[int] t = thread(callable=work, args=[c])
ThreadCancelled e = t.cancel()
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

class TestThreadHostContract:
    """IbThread.join() Python 宿主契约：返回 Waitable，.result() = thread_result 容器。"""

    def test_join_returns_waitable_host(self, engine, captured_output):
        from core.runtime.shared.waitable import Waitable

        lines, callback = captured_output
        code = """
func add(int a, int b) -> int:
    return a + b

thread[int] t = thread(callable=add, args=[3, 4])
"""
        engine.run_string(code, output_callback=callback)
        scope = engine.interpreter.runtime_context.global_scope
        t = scope.get_symbol("t").value
        w = t.join()
        assert isinstance(w, Waitable)
        r = w.result()
        assert r.expect().to_native() == 7


class TestThreadCancelCoversUserFunction:
    """协作取消覆盖用户函数任务体：步进边界 + 等待中任务。"""

    def test_cancel_stops_while_loop_body(self):
        """用户函数 while 循环体在步进边界协作退出。"""
        code = """
func work() -> int:
    int i = 0
    while i < 1000000000:
        i = i + 1
    return i

thread[int] t = thread(callable=work, args=[])
ThreadCancelled e = t.cancel()
print(e.message)
t.join()
print((str)t.is_done())
print((str)t.join().status())
"""
        lines = run_ibci(code)
        assert lines[0] == "Task was cancelled"
        assert lines[1] == "True"           # 线程实际已结束
        assert lines[2] == "cancelled"      # thread_result status = cancelled

    def test_cancel_stops_body_blocked_on_recv(self):
        """用户函数阻塞在通道 recv 的任务也被协作取消（等待中任务）。"""
        code = """
chan c = chan(str, "message")
func work(chan x) -> int:
    str m = x.recv()
    return 1

thread[int] t = thread(callable=work, args=[c])
ThreadCancelled e = t.cancel()
print(e.message)
t.join()
print((str)t.is_done())
print((str)t.join().status())
"""
        lines = run_ibci(code)
        assert lines[0] == "Task was cancelled"
        assert lines[1] == "True"
        assert lines[2] == "cancelled"


class TestThreadCellIsolation:
    """任务内禁写"已共享给主线程"的闭包 cell。"""

    def test_write_shared_closure_cell_is_isolated(self):
        """任务写共享闭包 cell → 隔离违规 → thread_result failed。"""
        code = """
func make_counter() -> fn:
    int total = 0
    func tick() -> int:
        nonlocal total
        total = total + 1
        return total
    return tick

fn c = make_counter()
thread[int] t = thread(callable=c, args=[])
thread_result[int] r = t.join()
print((str)r.is_error())
print((str)r.status())
"""
        lines = run_ibci(code)
        assert lines == ["True", "failed"]

    def test_read_shared_closure_cell_is_allowed(self):
        """任务读共享闭包 cell（不写）→ 合法。"""
        code = """
func make_reader() -> fn:
    int total = 42
    func read() -> int:
        nonlocal total
        return total
    return read

fn c = make_reader()
thread[int] t = thread(callable=c, args=[])
thread_result[int] r = t.join()
print((str)r.is_error())
print((str)r.expect())
"""
        lines = run_ibci(code)
        assert lines == ["False", "42"]


class TestThreadWaitableDirect:
    """IbThread 本体满足 Waitable 协议。

    语言 ``await t`` 直接可用；``t.join()`` 返回自身；``t.is_done()`` 语言
    方法保留（auto-bind 对 property 的包装，读 property + 装箱）。
    """

    def test_await_thread_direct(self):
        """``await t`` 直接等待线程完成（无需 join 包装）。"""
        code = """
func add(int a, int b) -> int:
    return a + b

thread[int] t = thread(callable=add, args=[3, 4])
thread_result[int] r = await t
print((str)r.expect())
"""
        lines = run_ibci(code)
        assert lines == ["7"]

    def test_await_thread_with_chan_block(self):
        """``await t`` 在线程阻塞于 chan recv 时挂起，send 唤醒后完成。"""
        code = """
chan c = chan(str, "message")
func add(chan x) -> int:
    str _ = x.recv()
    return 1 + 2

thread[int] t = thread(callable=add, args=[c])
c.send("go")
thread_result[int] r = await t
print((str)r.expect())
"""
        lines = run_ibci(code)
        assert lines == ["3"]

    def test_join_returns_self_is_waitable(self, engine, captured_output):
        """宿主侧 t.join() 返回自身（IbThread），isinstance Waitable 成立。"""
        from core.runtime.shared.waitable import Waitable

        lines, callback = captured_output
        code = """
func add(int a, int b) -> int:
    return a + b

thread[int] t = thread(callable=add, args=[3, 4])
"""
        engine.run_string(code, output_callback=callback)
        scope = engine.interpreter.runtime_context.global_scope
        t = scope.get_symbol("t").value
        w = t.join()
        assert w is t
        assert isinstance(w, Waitable)
        r = w.result()
        assert r.expect().to_native() == 7

    def test_is_done_language_method_still_works(self):
        """语言 ``t.is_done()`` 保留（property 经 auto-bind 包装为方法）。"""
        code = """
func work(int x) -> int:
    return x * 2

thread[int] t = thread(callable=work, args=[21])
t.join()
print((str)t.is_done())
print((str)(t.is_done() and True))
"""
        lines = run_ibci(code)
        assert lines == ["True", "True"]
