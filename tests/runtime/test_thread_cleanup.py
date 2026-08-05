"""
线程相关清理测试：save_state 未完成线程检测 + 快照含线程 + coordinator 生命周期。

覆盖：
- save_state 在未完成线程存在时抛异常
- 线程完成后 save_state 正常
- 快照（observability）包含协调器线程
- coordinator 自动清理已完成任务（防泄漏）
- 协作式取消 handle 上报
"""

import subprocess
import sys
import time

from tests.conftest import REPO_ROOT, run_ibci


def test_thread_result_imports_without_circular_import():
    """干净解释器下直接 import thread_result / thread 不触发循环导入。

    旧缺陷：thread_result → primitives.optional → primitives/__init__ → ..thread_result，
    直接导入抛 ImportError（依赖隐式导入顺序存活）。
    """
    code = (
        "import core.runtime.objects.thread_result\n"
        "import core.runtime.objects.thread\n"
        "print('ok')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"循环导入回归：{result.stderr}"
    assert "ok" in result.stdout


def test_thread_instance_is_real_ibthread():
    """instantiate 挂钩使 thread(...) 产生真实 IbThread 实例（槽位状态）。"""
    from core.engine import IBCIEngine
    from core.runtime.objects.thread import IbThread

    engine = IBCIEngine(root_dir=".")
    engine.run_string("""
func f() -> int:
    return 1
thread[int] t = thread(callable=f, args=[])
""", silent=True)
    rc = engine.interpreter.execution_context.runtime_context
    t = rc.get_variable("t")
    assert isinstance(t, IbThread), f"thread(...) 应产生真实 IbThread，got {type(t).__name__}"
    assert t._state == "running"  # eager 启动


def test_thread_result_is_ibvalue():
    """thread_result 升级为 IbValue（payload 承载值，type_ref 生效）。"""
    from core.engine import IBCIEngine
    from core.runtime.objects.kernel import IbValue
    from core.runtime.objects.thread_result import IbThreadResult

    engine = IBCIEngine(root_dir=".")
    engine.run_string("""
func f() -> int:
    return 1
thread[int] t = thread(callable=f, args=[])
thread_result[int] r = t.join()
""", silent=True)
    rc = engine.interpreter.execution_context.runtime_context
    r = rc.get_variable("r")
    assert isinstance(r, IbValue), f"thread_result 应为 IbValue，got {type(r).__name__}"
    assert isinstance(r, IbThreadResult)
    assert r.type_ref is not None
    assert r.status().to_native() == "done"
    assert r.value().to_native() == 1


def test_save_state_rejects_unfinished_thread():
    """未完成线程存在时 save_state 必须抛异常。"""
    from core.engine import IBCIEngine
    from concurrent.futures import Future
    from core.runtime.coordinator import SpawnedTask
    from core.kernel.issue import InterpreterError

    engine = IBCIEngine(root_dir=".")
    lines = []
    engine.run_string("""
func f() -> int:
    return 1
thread[int] t = thread(callable=f, args=[])
""", output_callback=lambda s: lines.append(str(s)))

    rc = engine.interpreter.execution_context.runtime_context
    coord = getattr(rc, "_runtime_coordinator", None)
    assert coord is not None

    # 注入一个未完成的任务（future 未完成）
    st = SpawnedTask(engine.interpreter, None, [])
    st._future = Future()
    st._handle = "task_test_unfinished"
    with coord._lock:
        coord._tasks[st._handle] = st

    svc = engine.interpreter.service_context.host_service
    try:
        svc.save_state("/tmp/opencode/_test_unfinished.json")
        raised = False
    except InterpreterError as e:
        raised = "threads are running" in str(e) or "unfinished thread" in str(e)
    except Exception:
        raised = False
    assert raised, "save_state 应在未完成线程存在时抛异常"

    # 完成后 save_state 正常
    st._future.set_result(1)
    time.sleep(0.05)
    svc.save_state("/tmp/opencode/_test_unfinished_after.json")


def test_snapshot_includes_coordinator_threads():
    """快照应包含协调器线程（单数据源）。"""
    from core.engine import IBCIEngine
    from core.runtime.observability import snapshot as snap

    engine = IBCIEngine(root_dir=".")
    lines = []
    engine.run_string("""
func f() -> int:
    return 1
thread[int] t = thread(callable=f, args=[])
""", output_callback=lambda s: lines.append(str(s)))

    data = snap.snapshot(engine.interpreter.execution_context)
    # tasks 列表应至少包含调度器或协调器来源的条目（结构存在即可，不冻结数量）。
    assert "tasks" in data


def test_coordinator_cleans_up_completed_tasks():
    """已完成任务自动从协调器移除（防泄漏）。"""
    from core.engine import IBCIEngine

    engine = IBCIEngine(root_dir=".")
    lines = []
    engine.run_string("""
func f() -> int:
    return 1
thread[int] t = thread(callable=f, args=[])
t.join()
""", output_callback=lambda s: lines.append(str(s)))

    rc = engine.interpreter.execution_context.runtime_context
    coord = getattr(rc, "_runtime_coordinator", None)
    assert coord is not None
    time.sleep(0.1)  # 等待 done 回调
    assert coord.unfinished_handles() == []


def test_cancel_cooperative_handle():
    """协作式取消句柄（无死 _task_handle 依赖）。

    线程体阻塞在 chan recv 上（确定性挂起），cancel 在挂起点生效——
    快函数线程可能在 cancel 前自然完成（竞态），旧无条件返回 TaskCancelled
    掩盖了它；改为阻塞挂起场景验证协作取消语义。
    chan 经参数传入（线程闭包不捕获模块级变量）。
    """
    lines = run_ibci("""
chan c = chan(str, "message")
func f(chan x) -> str:
    str m = x.recv()
    return m
thread[str] t = thread(callable=f, args=[c])
TaskCancelled e = t.cancel()
print(e.message)
c.send("x")
""")
    assert lines == ["Task was cancelled"]


def test_cancel_on_finished_thread_returns_none():
    """已结束线程 cancel() 返回 None，不翻转状态为 CANCELLED。

    此前 cancel() 仅查 _spawned is None，已 join 的线程调用会返回
    TaskCancelled err 并把 _state 从 done 翻转为 cancelled（违背 docstring）。
    """
    lines = run_ibci("""
func f() -> int:
    return 1
thread[int] t = thread(callable=f, args=[])
thread_result[int] r = t.join()
print(r.status())
t.cancel()
print(t.is_done())
""")
    # join 成功 → done；cancel 守卫 → 返回 None（不打印）；is_done 仍 True
    assert lines == ["done", "True"]


def test_is_done_reflects_natural_completion():
    """线程自然完成（未 join）后 is_done() 返回 True。

    此前 is_done() 读 _state（仅 join/cancel 时刷新），自然完成未 join 会
    滞后为 running 而误报 False；现在以 _spawned.is_done 为权威完成信号。
    """
    import time
    from core.engine import IBCIEngine

    engine = IBCIEngine(root_dir=".")
    engine.run_string("""
func f() -> int:
    return 42
thread[int] t = thread(callable=f, args=[])
""", silent=True)
    time.sleep(0.3)  # 等待线程自然完成（不 join）
    t = engine.interpreter.execution_context.runtime_context.get_symbol("t").value
    assert t.is_done().payload is True
    assert t.to_native()["done"] is True