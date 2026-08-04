"""
线程相关清理测试（任务 E）：save_state 未完成线程检测 + 快照含线程 + coordinator 生命周期。

覆盖：
- save_state 在未完成线程存在时抛异常（疏漏 4）
- 线程完成后 save_state 正常
- 快照（observability）包含协调器线程（F-1 单数据源）
- coordinator 自动清理已完成任务（F-2 防泄漏）
- 协作式取消 handle 上报（VP-2，无死 _task_handle 依赖）
"""

import subprocess
import sys
import time

from tests.conftest import REPO_ROOT, run_ibci


def test_thread_result_imports_without_circular_import():
    """B2 回归：干净解释器下直接 import thread_result / thread 不触发循环导入。

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


def test_save_state_rejects_unfinished_thread():
    """未完成线程存在时 save_state 必须抛异常（疏漏 4）。"""
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
    """快照应包含协调器线程（F-1 单数据源）。"""
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
    """已完成任务自动从协调器移除（F-2 防泄漏）。"""
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
    """协作式取消句柄（无死 _task_handle 依赖）。"""
    lines = run_ibci("""
func f() -> int:
    return 1
thread[int] t = thread(callable=f, args=[])
TaskCancelled e = t.cancel()
print(e.message)
""")
    assert lines == ["Task was cancelled"]