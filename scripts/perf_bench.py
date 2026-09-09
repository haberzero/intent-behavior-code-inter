#!/usr/bin/env python3
"""
scripts/perf_bench.py — IBCI 执行期性能基准 harness（VISION-6 Phase 1 交付）

定位：数据平面性能线的**改前/改后裁判**（区别于 `main.py bench` 的编译期基准）。
跑一组代表性 IBCI 程序（算术/循环/递归/字符串/容器/类方法），量化**执行期**总耗时
+ **每迭代成本**（规模无关，更稳的基线指标），warmup + N 次取中位。P2/P3/P4 的性能
上修均以本 harness 的改前/改后数字为裁判。

用法：
    .venv/bin/python scripts/perf_bench.py              # 全部代表性程序（执行期基线）
    .venv/bin/python scripts/perf_bench.py --profile    # + cProfile 热点剖析（arith）
    .venv/bin/python scripts/perf_bench.py --runs 5     # 指定采样次数

说明：
- 每项 = fresh IBCIEngine → run_string（编译+水化+VM 执行的总耗时，即用户体感）。
- 规模已校准到每 run ~1-3s（warmup + runs 可在分钟级内完成全 harness）；**每迭代成本
  = 总耗时 / 迭代数**（规模无关，P2/P3/P4 改前/改后比较的主指标）。
- 字符串项 = D-3/D-3.3 逐字符热路径（既有实证 ~1000× 开销点，预期显著高于算术项）。
- 基线数字以实跑为准（机器/负载相关）；本 harness 的价值 = 可复现的相对比较。
"""
from __future__ import annotations

import argparse
import statistics
import sys
import time

from core.engine import IBCIEngine

REPO = "/home/dsh/proj/intent-behavior-code-inter"
N = 10_000  # 校准规模（每 run ~1-3s）


# 代表性 IBCI 程序集（执行期数据平面热路径覆盖）。
# 每项 = (name, code, loop_count)；loop_count 用于折算每迭代成本。
def _program_set() -> list[tuple[str, str, int]]:
    return [
        # 算术 + 变量 + binop（基础热路径）
        ("arith",
         f"int s = 0\nint i = 1\nwhile i <= {N}:\n    s = s + i\n    i = i + 1\nint _ = s\n",
         N),
        # 循环 + 分支（控制流骨架）
        ("branch",
         f"int s = 0\nint i = 0\nwhile i < {N}:\n    if i % 2 == 0:\n        s = s + 1\n    i = i + 1\nint _ = s\n",
         N),
        # 函数递归（trampoline + 调用帧）—— 500 次 fact(20)
        ("recurse",
         "func fact(int n) -> int:\n"
         "    if n <= 1:\n        return 1\n"
         "    return n * fact(n - 1)\n"
         "int acc = 0\nint i = 0\nwhile i < 500:\n    acc = acc + fact(20)\n    i = i + 1\nint _ = acc\n",
         500),
        # 字符串拼接（D-3/D-3.3 逐字符热路径 —— ~1000× 开销点）
        ("string",
         "str s = ''\nint i = 0\nwhile i < 500:\n    s = s + 'x'\n    i = i + 1\nstr _ = s\n",
         500),
        # 容器构建（list 特化）
        ("container",
         f"list xs = []\nint i = 0\nwhile i < {N}:\n    xs.append(i)\n    i = i + 1\nint _ = len(xs)\n",
         N),
        # 类方法调用（协议分派 receive + 类实例化）
        ("class",
         "class Accum:\n    int total\n    func add(self, int v) -> int:\n"
         "        self.total = self.total + v\n        return self.total\n"
         "int acc = 0\nint i = 0\nwhile i < 2000:\n    Accum a = Accum(0)\n"
         "    acc = acc + a.add(1)\n    i = i + 1\nint _ = acc\n",
         2000),
    ]


def _run_once(code: str) -> float:
    """fresh engine → run_string（编译+水化+执行总耗时），返回秒。"""
    engine = IBCIEngine(root_dir=REPO)
    t0 = time.perf_counter()
    engine.run_string(code, silent=True)
    return time.perf_counter() - t0


def bench(code: str, warmup: int, runs: int) -> tuple[float, float]:
    """warmup + runs 次采样，返回 (median_ms, stdev_ms)。"""
    for _ in range(warmup):
        _run_once(code)
    samples = [_run_once(code) for _ in range(runs)]
    ms = [s * 1000 for s in samples]
    return statistics.median(ms), (statistics.stdev(ms) if len(ms) > 1 else 0.0)


def profile(name: str, code: str) -> None:
    """cProfile 剖析单个程序（fresh engine → run_string）的热点路径。"""
    import cProfile
    import pstats

    def _target():
        engine = IBCIEngine(root_dir=REPO)
        engine.run_string(code, silent=True)

    prof = cProfile.Profile()
    prof.enable()
    _target()
    prof.disable()
    out = f"/tmp/perf_profile_{name}.txt"
    with open(out, "w") as f:
        stats = pstats.Stats(prof, stream=f)
        stats.sort_stats("cumulative").print_stats(45)
    print(f"[profile] {name}: 热点剖析 → {out}（cumulative 排序，前 45 项）")


def main() -> int:
    ap = argparse.ArgumentParser(description="IBC IBCI 执行期性能基准 harness（Phase 1 裁判）")
    ap.add_argument("--warmup", type=int, default=1, help="预热次数（默认 1）")
    ap.add_argument("--runs", type=int, default=3, help="每项采样次数（默认 3，取中位）")
    ap.add_argument("--profile", action="store_true",
                    help="对 arith 程序 cProfile 热点剖析（写入 /tmp）")
    ap.add_argument("--only", default="", help="只跑指定程序（逗号分隔）")
    args = ap.parse_args()

    prog_set = _program_set()
    names = {p[0] for p in prog_set if (not args.only or p[0] in args.only.split(","))}

    print("=" * 78)
    print("IBC IBCI 执行期性能基准（Phase 1 裁判）—— 数字以实跑为准，价值 = 改前/改后相对")
    print("=" * 78)
    print(f"{'program':<12}{'median ms':>13}{'stdev ms':>11}{'iters':>8}{'us/iter':>10}")
    print("-" * 78)
    for name, code, iters in prog_set:
        if name not in names:
            continue
        med, sd = bench(code, args.warmup, args.runs)
        print(f"{name:<12}{med:>13.1f}{sd:>11.1f}{iters:>8}{med * 1000 / iters:>10.1f}")
    print("-" * 78)
    if args.profile:
        arith = next(p for p in prog_set if p[0] == "arith")
        profile("arith", arith[1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
