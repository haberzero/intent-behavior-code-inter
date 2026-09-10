"""CPU+IO GIL-free 真并行验证（阶段④ task_scheduler 集成目标）。

验证 Rust 执行核心的 CPU 工作（GIL-free，经 py.allow_threads 释放 GIL）可与
**GIL-bound 的 Python 任务真并行**——这是 Phase ④ 的 CPU+IO 真并行目标（task_
scheduler IO-only → CPU+IO GIL-free）的核心能力。

方法（CPU 与 GIL-bound IO 对等并行）：
- 线程 A：GIL-bound Python 任务（纯 Python CPU 计算，持 GIL，时长 T_io）。
- 线程 B：GIL-free Rust 执行核心（run_artifacts_parallel，释放 GIL，时长 T_cpu）。
- 两线程并行跑，测墙钟 T_wall。
- **GIL-free 真并行**：T_wall ≈ max(T_io, T_cpu)（两者真并行，互不阻塞）。
- **GIL-bound 串行**（对照）：T_wall ≈ T_io + T_cpu（若 Rust 持 GIL，两者串行）。

若 T_wall 接近 max（而非 sum），证明 Rust CPU 工作 GIL-free，可与 GIL-bound Python
任务真并行——task_scheduler 可调度 CPU+IO 真并行（GIL-free）。
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

from tests.conftest import compile_ibci  # noqa: E402
from core.compiler.serialization.serializer import FlatSerializer  # noqa: E402

_SO = os.path.join("core", "runtime", "kernels", "ibci_ext.so")

# GIL-bound Python 任务（纯 Python CPU 计算，持 GIL）
def gil_bound_work(total_iters: int = 2_000_000) -> int:
    s = 0
    for i in range(total_iters):
        s += i * 2
    return s


def _load_rust():
    import importlib.util
    spec = importlib.util.spec_from_file_location("ibci_ext", _SO)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main() -> None:
    m = _load_rust()
    # GIL-free Rust CPU 任务（4 个 artifact 并行）
    artifacts = []
    for i in range(4):
        code = f"s = 0\nfor j in range(1, 100001):\n    s = s + j + {i}\nprint(s)\n"
        artifacts.append(
            json.dumps(FlatSerializer().serialize_artifact(compile_ibci(code)), ensure_ascii=False)
        )

    # 单独测各任务时长
    t0 = time.perf_counter()
    gil_bound_work()
    t_io = time.perf_counter() - t0

    t0 = time.perf_counter()
    m.run_artifacts_parallel(artifacts, 4)
    t_cpu = time.perf_counter() - t0

    # 两任务并行（线程 A = GIL-bound Python，线程 B = GIL-free Rust）
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=2) as ex:
        f_io = ex.submit(gil_bound_work)
        f_cpu = ex.submit(m.run_artifacts_parallel, artifacts, 4)
        f_io.result()
        f_cpu.result()
    t_wall = time.perf_counter() - t0

    print(f"GIL-bound Python 任务时长 T_io  = {t_io:.3f}s（持 GIL）")
    print(f"GIL-free Rust 执行核心 T_cpu    = {t_cpu:.3f}s（释放 GIL）")
    print(f"两任务并行墙钟 T_wall           = {t_wall:.3f}s")
    print(f"  max(T_io, T_cpu) = {max(t_io, t_cpu):.3f}s（GIL-free 真并行期望）")
    print(f"  T_io + T_cpu     = {t_io + t_cpu:.3f}s（GIL-bound 串行对照）")
    print()
    ratio = t_wall / max(t_io, t_cpu)
    print(f"并行比 T_wall / max = {ratio:.2f}（≈1.0 = 真并行；≈{ (t_io+t_cpu)/max(t_io,t_cpu):.1f} = 串行）")
    print(f"  → CPU+IO GIL-free 真并行：{'✅ 成立' if ratio < 1.4 else '❌ 未达预期'}")


if __name__ == "__main__":
    main()
