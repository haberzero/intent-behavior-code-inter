"""task_scheduler GIL-free 集成验证（阶段④：Python task_scheduler + Rust TaskPool）。

验证 Phase ④ 的 CPU+IO GIL-free 集成目标：Python task_scheduler（协作式调度 IO
任务，持 GIL）与 Rust TaskPool（GIL-free 真并行执行 CPU 任务）可**协同工作**——
IO 任务经 task_scheduler 协作式推进（持 GIL），CPU 任务经 TaskPool GIL-free 真并行
（释放 GIL），两者并发（墙钟 ≈ max[IO, CPU]，非 sum[串行]）。

方法（task_scheduler IO 任务 + TaskPool CPU 任务对等并行）：
- 线程 A：Python task_scheduler.run() 推进 IO 任务（协作式，持 GIL，时长 T_io）。
- 主线程：Rust TaskPool.run_all() 并行执行 CPU 任务（释放 GIL，时长 T_cpu）。
- 两者并发，测墙钟 T_wall。
- **GIL-free 真并行集成**：T_wall ≈ max(T_io, T_cpu)（两者真并行，互不阻塞）。
- **GIL-bound 串行**（对照）：T_wall ≈ T_io + T_cpu（若 TaskPool 持 GIL，串行）。

IO 任务是生成器（task_scheduler 契约：yield 挂起 / return 完成）；本演示的 IO 任务
为 CPU 密集（持 GIL，无实际 IO）——模拟 task_scheduler 的 IO 密集任务。
"""
from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor

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


def io_task(total_iters: int = 2_000_000):
    """IO 任务（生成器，task_scheduler 契约）——CPU 密集（持 GIL，无实际 IO），
    模拟 task_scheduler 的 IO 密集任务。yield from 空迭代使其成为生成器（无 yield
    挂起，一步完成）。"""
    s = 0
    for i in range(total_iters):
        s += i * 2
    yield from iter(())
    return s


def main() -> None:
    m = _load_rust()

    # IO 任务（经 Python task_scheduler 协作式调度，持 GIL）
    scheduler = TaskScheduler()
    scheduler.submit(io_task(), node_uid="io_task")

    # CPU 任务（经 Rust TaskPool GIL-free 真并行，4 个 artifact）
    pool = m.TaskPool(4)
    for i in range(4):
        code = f"s = 0\nfor j in range(1, 100001):\n    s = s + j + {i}\nprint(s)\n"
        pool.submit(
            json.dumps(
                FlatSerializer().serialize_artifact(compile_ibci(code)),
                ensure_ascii=False,
            )
        )

    # 单独测 IO 任务时长（task_scheduler 协作式推进，持 GIL）
    t0 = time.perf_counter()
    sched_io = TaskScheduler()
    sched_io.submit(io_task(), node_uid="io")
    sched_io.run()
    t_io = time.perf_counter() - t0

    # 两者并发：线程 A = task_scheduler（IO，持 GIL）；主线程 = TaskPool（CPU，GIL-free）
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=1) as ex:
        f_io = ex.submit(scheduler.run)
        results = pool.run_all()  # 主线程：Rust GIL-free 真并行（释放 GIL）
        io_results = f_io.result()  # 等待 IO 任务完成
    t_wall = time.perf_counter() - t0

    print(f"IO 任务（task_scheduler 协作式，持 GIL）时长 T_io = {t_io:.3f}s")
    print(f"CPU 任务（TaskPool GIL-free 并行）×4 完成（{len(results)} 项）")
    print(f"两者并发墙钟 T_wall = {t_wall:.3f}s")
    print(f"  期望 GIL-free 真并行 ≈ max(T_io, T_cpu) ≈ {t_io:.3f}s（IO 主导，CPU 并行叠加）")
    print(f"  对照 GIL-bound 串行 ≈ T_io + T_cpu（若 TaskPool 持 GIL）")
    print()
    # GIL-free 集成成立：墙钟 ≈ IO 任务时长（CPU 任务并行叠加，不串行阻塞 IO）
    ratio = t_wall / t_io
    print(
        f"并发比 T_wall / T_io = {ratio:.2f}"
        f"（≈1.0 = CPU 并行叠加[GIL-free 集成]；>1 明显 = CPU 串行阻塞 IO[GIL-bound]）"
    )
    print(f"  → task_scheduler GIL-free 集成（CPU+IO）：{'✅ 成立' if ratio < 1.5 else '❌ 未达预期'}")


if __name__ == "__main__":
    main()
