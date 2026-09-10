"""task_scheduler GIL-free 集成验证（阶段④：task_scheduler 内部接入 TaskPool——
异步 CPU 任务 waitable）。

验证 Phase ④ 的 CPU+IO GIL-free 集成目标（task_scheduler 内部接入）：task_scheduler
可调度**异步 CPU 任务**（CPU 工作经 TaskPool 在后台线程 GIL-free 真并行执行）——CPU
任务 waitable 符合 task_scheduler 的 waitable 协议（is_done / 非阻塞 try_result /
register_wake）；task_scheduler 推进 IO 任务（持 GIL）时，CPU 任务在后台线程 GIL-free
真并行（墙钟 ≈ max[IO, CPU]，非 sum[串行]）。

方法（task_scheduler 内部接入 TaskPool——异步 CPU 任务）：
- IO 任务（生成器）：task_scheduler 协作式推进（持 GIL，时长 T_io）。
- CPU 任务（生成器）：yield 一个 CPU 任务 waitable（后台线程经 TaskPool GIL-free 执行
  CPU 工作，时长 T_cpu）；task_scheduler 等待该 waitable（poll is_done / 非阻塞
  try_result），完成后恢复 CPU 任务取结果。
- task_scheduler.run() 推进两任务；IO 任务持 GIL 推进时，CPU 任务后台线程 GIL-free 真
  并行——墙钟 T_wall ≈ max(T_io, T_cpu)（非 T_io + T_cpu 串行）。

**异步 CPU 任务 waitable 协议**（task_scheduler 契约）：is_done（非阻塞查询完成）/
try_result（非阻塞取结果[未完成 = (False, None) 继续等待]）/ register_wake（完成时设
事件，唤醒全等待 park）。
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO_ROOT)
sys.path.insert(0, REPO_ROOT)

from core.runtime.vm.task_scheduler import TaskScheduler  # noqa: E402
from tests.conftest import compile_ibci  # noqa: E402
from core.compiler.serialization.serializer import FlatSerializer  # noqa: E402

_SO = os.path.join("core", "runtime", "kernels", "ibci_ext.so")


def _load_rust():
    import importlib.util
    spec = importlib.util.spec_from_file_location("ibci_ext", _SO)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


class CPUTaskWaitable:
    """异步 CPU 任务 waitable（task_scheduler 内部接入 TaskPool）：CPU 工作（artifact
    列表）经 TaskPool 在后台线程 GIL-free 真并行执行。符合 task_scheduler 的 waitable
    协议——is_done（非阻塞查询完成）/ try_result（非阻塞取结果[未完成 = (False, None)
    继续等待]）/ register_wake（完成时设事件）/ result（阻塞取结果[宿主/线程体兜底]）。
    每 waitable 独立 TaskPool（避免共享池 run_all 竞争）。"""

    def __init__(self, rust, artifacts: list[str], workers: int = 4) -> None:
        self._rust = rust
        self._pool = rust.TaskPool(workers)
        for a in artifacts:
            self._pool.submit(a)
        self._done = False
        self._result = None
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        # 后台线程：TaskPool GIL-free 真并行执行 CPU 工作（释放 GIL）
        self._result = self._pool.run_all()
        self._done = True

    @property
    def is_done(self) -> bool:
        return self._done

    def try_result(self):
        # 非阻塞取结果（task_scheduler 契约）：未完成 = (False, None) 继续等待
        if self._done:
            return (True, self._result)
        return (False, None)

    def register_wake(self, event) -> None:
        if self._done:
            event.set()

    def result(self):
        # 阻塞取结果（宿主/线程体同步兜底）
        self._thread.join()
        return self._result


def io_task(total_iters: int = 2_000_000):
    """IO 任务（生成器，task_scheduler 契约）——CPU 密集（持 GIL，无实际 IO），模拟
    task_scheduler 的 IO 密集任务。yield from 空迭代使其成为生成器（无 yield 挂起，
    一步完成）。"""
    s = 0
    for i in range(total_iters):
        s += i * 2
    yield from iter(())
    return s


def cpu_task(rust, artifacts: list[str], workers: int = 4):
    """CPU 任务（生成器，task_scheduler 契约）：yield 异步 CPU 任务 waitable（后台线程
    经 TaskPool GIL-free 执行 CPU 工作），完成后取结果。"""
    waitable = CPUTaskWaitable(rust, artifacts, workers)
    result = yield waitable  # task_scheduler 等待该 waitable（poll is_done / try_result）
    return result


def main() -> None:
    m = _load_rust()
    # CPU 任务 artifact（4 个纯 CPU，无宿主服务）
    artifacts = []
    for i in range(4):
        code = f"s = 0\nfor j in range(1, 100001):\n    s = s + j + {i}\nprint(s)\n"
        artifacts.append(
            json.dumps(FlatSerializer().serialize_artifact(compile_ibci(code)), ensure_ascii=False)
        )

    # IO 任务时长（task_scheduler 协作式推进，持 GIL）
    t0 = time.perf_counter()
    sched_io = TaskScheduler()
    sched_io.submit(io_task(), node_uid="io")
    sched_io.run()
    t_io = time.perf_counter() - t0

    # task_scheduler 内部接入：异步 CPU 任务（waitable，先提交→后台线程先启动）+
    # IO 任务（后跑→期间 CPU 后台 GIL-free 真并行）。task_scheduler 按提交序推进：
    # CPU 任务先生成器推进至 yield waitable（启动后台线程），IO 任务后推进（持 GIL
    # T_io）——期间 CPU 后台线程 GIL-free 真并行。
    scheduler = TaskScheduler()
    scheduler.submit(cpu_task(m, artifacts, workers=4), node_uid="cpu")
    scheduler.submit(io_task(), node_uid="io")

    t0 = time.perf_counter()
    results = scheduler.run()  # 推进 IO 任务[持 GIL] + CPU 任务[waitable，后台 GIL-free]
    t_wall = time.perf_counter() - t0

    print(f"IO 任务（task_scheduler 协作式，持 GIL）时长 T_io = {t_io:.3f}s")
    print(f"CPU 任务（异步 waitable，后台 TaskPool GIL-free）×4 完成")
    print(f"task_scheduler 并发墙钟 T_wall = {t_wall:.3f}s")
    print(f"  期望 GIL-free 真并行 ≈ max(T_io, T_cpu) ≈ {t_io:.3f}s（IO 主导，CPU 后台并行叠加）")
    print(f"  对照 GIL-bound 串行 ≈ T_io + T_cpu（若 CPU 任务持 GIL[非后台 GIL-free]）")
    print()
    # GIL-free 集成成立：墙钟 ≈ IO 任务时长（CPU 任务后台 GIL-free 并行叠加，不串行阻塞 IO）
    ratio = t_wall / t_io
    print(
        f"并发比 T_wall / T_io = {ratio:.2f}"
        f"（≈1.0 = CPU 后台 GIL-free 并行叠加[task_scheduler 内部接入]；>1 明显 = CPU 串行阻塞 IO[GIL-bound]）"
    )
    print(f"  → task_scheduler 内部接入 TaskPool（异步 CPU 任务 GIL-free）：{'✅ 成立' if ratio < 1.5 else '❌ 未达预期'}")


if __name__ == "__main__":
    main()
