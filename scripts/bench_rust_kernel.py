"""Rust 执行核心 vs Python 执行核心 性能基准（P9 阶段③ 主战场）。

测量同一 IBCI 语料的两执行核心耗时（微秒/次）：
- Python：run_ibci（compile[artifact 缓存] + VM 执行）——全流水线。
- Rust：compile[Python, 缓存] → serialize → run_artifact（反序列化 + 执行）。

用途：追踪 Rust 执行核心的性能收益（cProfile 实证的 per-step Python 反射/间接
瓶颈）。非测试（性能断言 flaky）——基准脚本，结果记录 WORKLOG。

运行：``.venv/bin/python scripts/bench_rust_kernel.py``
"""
from __future__ import annotations

import json
import os
import sys
import time

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(REPO_ROOT)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tests.conftest import compile_ibci, run_ibci  # noqa: E402
from core.compiler.serialization.serializer import FlatSerializer  # noqa: E402
from tests.diff_harness.corpus import CORPUS  # noqa: E402

_N = 300  # 每语料迭代次数（微秒级，取均值）


def _load_rust():
    import importlib.util

    p = os.path.join("core", "runtime", "kernels", "ibci_ext.so")
    if not os.path.exists(p):
        return None
    spec = importlib.util.spec_from_file_location("ibci_ext", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def bench_python(code: str, n: int = _N) -> float:
    """Python 执行核心（run_ibci = compile[缓存] + VM 执行）——微秒/次。"""
    t0 = time.perf_counter()
    for _ in range(n):
        run_ibci(code)
    return (time.perf_counter() - t0) / n * 1e6


def bench_rust(rust, code: str, n: int = _N) -> float:
    """Rust 执行核心（compile[Python 缓存] → serialize → run_artifact）——微秒/次。"""
    artifact = compile_ibci(code)
    js = json.dumps(FlatSerializer().serialize_artifact(artifact), ensure_ascii=False)
    t0 = time.perf_counter()
    for _ in range(n):
        rust.run_artifact(js)
    return (time.perf_counter() - t0) / n * 1e6


def main() -> None:
    rust = _load_rust()
    if rust is None:
        print("[bench] Rust .so 未构建——仅 Python 参考（跑 ./scripts/build_rust_ext.sh 后复跑）")
    # 预热（artifact 缓存）
    for _name, code in CORPUS:
        try:
            compile_ibci(code)
        except Exception:
            pass
    print(f"{'corpus':20s} {'py_us':>10s} {'rust_us':>10s} {'speedup':>9s}")
    for name, code in CORPUS:
        if name.startswith("kb_"):
            continue  # KB 语料需宿主服务（后续增量）
        try:
            py = bench_python(code)
            if rust is None:
                print(f"{name:20s} {py:10.1f} {'-':>10s} {'-':>9s}")
                continue
            rs = bench_rust(rust, code)
            print(f"{name:20s} {py:10.1f} {rs:10.1f} {py / rs:8.2f}x")
        except Exception as e:  # noqa: BLE001
            print(f"{name:20s} ERR: {str(e)[:50]}")


if __name__ == "__main__":
    main()
