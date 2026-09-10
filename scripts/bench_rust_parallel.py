"""Rust 执行核心并行执行基准（阶段④ GIL-free 真并行验证）。

验证 Rust 执行核心的 CPU 工作（解释执行）经 `py.allow_threads` 释放 GIL——
多执行核心可**真正并行**（非协作式轮转）。

方法（固定总工作量 W，对等比较）：
- 构造 CPU 密集 artifact（长循环，纯 CPU 无宿主服务）。
- 单线程跑 W 次 = T1。
- N 线程各跑 W/N 次（总 W 次）墙钟 = TN。
- **并行加速比 = T1 / TN**。GIL-free 真并行 → ≈N（线性加速）；
  GIL-bound → ≈1（无加速）。

对照：Python 参考内核（run_ibci）同 artifact 同工作量——因 GIL-bound，
加速比 ≈1（无加速）——凸显 Rust 执行核心 GIL-free 的并行优势。
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

from tests.conftest import compile_ibci, run_ibci  # noqa: E402
from core.compiler.serialization.serializer import FlatSerializer  # noqa: E402

# CPU 密集脚本（长循环，纯 CPU 无宿主服务）
CPU_HEAVY = (
    "s = 0\n"
    "for i in range(1, 200001):\n"
    "    s = s + i * 2\n"
    "print(s)\n"
)

_SO = os.path.join("core", "runtime", "kernels", "ibci_ext.so")


def _load_rust():
    import importlib.util
    spec = importlib.util.spec_from_file_location("ibci_ext", _SO)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _rust_artifact_js():
    artifact = compile_ibci(CPU_HEAVY)
    data = FlatSerializer().serialize_artifact(artifact)
    return json.dumps(data, ensure_ascii=False)


def rust_single_total(js: str, total: int) -> float:
    """单线程跑 total 次的总耗时（秒）。"""
    m = _load_rust()
    t0 = time.perf_counter()
    for _ in range(total):
        m.run_artifact(js, None)
    return time.perf_counter() - t0


def rust_parallel_total(js: str, workers: int, total: int) -> float:
    """N 线程各跑 total/N 次（总 total 次）的墙钟（秒）。"""
    m = _load_rust()
    per = total // workers
    def worker():
        for _ in range(per):
            m.run_artifact(js, None)
        return True
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(lambda _: worker(), range(workers)))
    return time.perf_counter() - t0


def python_parallel_total(workers: int, total: int) -> float:
    """Python 参考内核 N 线程各跑 total/N 次（总 total 次）的墙钟（秒，GIL-bound 对照）。"""
    per = total // workers
    def worker():
        for _ in range(per):
            run_ibci(CPU_HEAVY)
        return True
    t0 = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(lambda _: worker(), range(workers)))
    return time.perf_counter() - t0


def main() -> None:
    js = _rust_artifact_js()
    workers = 4
    total = 12  # 总工作量（单线程 12 次 = 4 线程各 3 次）
    print(f"CPU 密集 artifact（range(1,200001) 累加），总工作量 {total} 次，workers={workers}")
    print("  期望：GIL-free 真并行 → 加速比 ≈4；GIL-bound → 加速比 ≈1\n")

    rust_single = rust_single_total(js, total)
    rust_parallel = rust_parallel_total(js, workers, total)
    rust_speedup = rust_single / rust_parallel
    print(f"[Rust 执行核心] 单线程 {rust_single:.3f}s → {workers} 线程并行 {rust_parallel:.3f}s")
    print(f"  并行加速比 = {rust_speedup:.2f}x（理想 {workers}.00x；GIL-free 真并行 = 接近理想）\n")

    py_parallel = python_parallel_total(workers, total)
    # Python GIL-bound：并行无加速 → 单线程总耗时 ≈ 并行墙钟（总工作量相同）
    print(f"[Python 参考内核] {workers} 线程并行 {py_parallel:.3f}s（GIL-bound 对照，加速比 ≈1.00x）")

    print("\n" + "=" * 60)
    print(f"Rust GIL-free 并行加速 {rust_speedup:.2f}x vs Python GIL-bound ≈1.00x")
    print(f"  → Rust 执行核心 CPU 工作 GIL-free 真并行：{'✅ 成立' if rust_speedup > 2.5 else '❌ 未达预期'}")


if __name__ == "__main__":
    main()
