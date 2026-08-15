#!/usr/bin/env python3
"""旧套件全量重跑驱动（T07 配套，2026-08-14）。

用户要求：以前的已有试用体系（T01-T06）在当前 HEAD 下全量重跑。
本驱动处理各套混合布局（单文件用例 / 目录型多文件用例 main.ibci）、
各套自有 api_config（目录自带 api_config.json 时 root 指向该目录），
并按 expect-llm 头部标记分层（mock / llm），经 _toolkit/run_one.py 运行
（复用单一权威 harness，B- 前缀记录，register.jsonl 保留后出现者）。

用法：
  python rerun_old_suites.py [--suites "T01 T02 ..."] [--timeout 60] [--parallel 4]
                             [--llm-only | --mock-only] [--suite-cases-dir T05:cases_D3]
"""
import argparse
import concurrent.futures as cf
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))          # T07 目录
TRIALS = os.path.dirname(ROOT)                              # trials/
TOOLKIT = os.path.join(TRIALS, "_toolkit")
RUN_ONE = os.path.join(TOOLKIT, "run_one.py")
PY = os.environ.get("IBCI_PYTHON",
                    os.path.join(os.path.expanduser("~"), "miniconda3", "envs", "ibci", "bin", "python"))
REPO_ROOT = os.path.abspath(os.path.join(ROOT, "..", "..", ".."))  # 上溯到仓库根（含 main.py）

_LLM_RE = re.compile(r"^#\s*expect-llm\s*:\s*(\S+)")

def expect_llm(script_path):
    try:
        with open(script_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    break
                m = _LLM_RE.match(line)
                if m:
                    return m.group(1).strip().lower() == "true"
    except OSError:
        pass
    return False

def collect_cases(suite_dir, cases_dir_name):
    """返回 [(label, script_abs, root, is_llm)]；目录型取 main.ibci。"""
    cases_dir = os.path.join(suite_dir, cases_dir_name)
    if not os.path.isdir(cases_dir):
        return []
    out = []
    for name in sorted(os.listdir(cases_dir)):
        p = os.path.join(cases_dir, name)
        if os.path.isfile(p) and name.endswith(".ibci"):
            label = name[:-5]
            out.append((label, p, suite_dir, expect_llm(p)))
        elif os.path.isdir(p):
            main = os.path.join(p, "main.ibci")
            if not os.path.exists(main):
                continue
            # 目录自带 api_config.json → root 指向该目录（各套自有配置）
            root = p if os.path.exists(os.path.join(p, "api_config.json")) else suite_dir
            out.append((name, main, root, expect_llm(main)))
    return out

def run_one_case(label, script, root, timeout):
    cmd = [PY, RUN_ONE, os.path.relpath(script, root),
           "--label", "B-" + label, "--dim", "RERUN", "--doc", "", "--expected", "",
           "--timeout", str(timeout),
           "--root", root, "--repo-root", REPO_ROOT]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 60)
        line = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else f"[{label}] no output"
    except subprocess.TimeoutExpired:
        line = f"[{label}] DRIVER-TIMEOUT"
    except Exception as exc:
        line = f"[{label}] DRIVER-ERROR {exc}"
    return {"label": label, "line": line}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suites", default="T01_llm_full T02_enum_import T03_user_class_generics T04_generics_fix_regression T05_critical_stress T06_class_identity")
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--llm-only", action="store_true")
    ap.add_argument("--mock-only", action="store_true")
    ap.add_argument("--suite-cases-dir", default="", help="额外用例目录映射，如 T05:cases_D3（逗号分隔多个）")
    args = ap.parse_args()

    extra_dirs = {}
    if args.suite_cases_dir:
        for pair in args.suite_cases_dir.split(","):
            s, d = pair.split(":")
            extra_dirs[s.strip()] = d.strip()

    suites = args.suites.split()
    total_done = 0
    for suite in suites:
        suite_dir = os.path.join(TRIALS, suite)
        if not os.path.isdir(suite_dir):
            print(f"[skip] {suite}: not found")
            continue
        cases = collect_cases(suite_dir, "cases")
        for s, d in extra_dirs.items():
            if s == suite:
                cases += collect_cases(suite_dir, d)
        if args.llm_only:
            cases = [c for c in cases if c[3]]
        if args.mock_only:
            cases = [c for c in cases if not c[3]]
        if not cases:
            print(f"[{suite}] no cases")
            continue
        print(f"=== {suite}: {len(cases)} cases (parallel={args.parallel}) ===", flush=True)
        results = []
        with cf.ThreadPoolExecutor(max_workers=max(1, min(args.parallel, len(cases)))) as ex:
            futs = {ex.submit(run_one_case, label, script, root, args.timeout): label
                    for label, script, root, _ in cases}
            for fut in cf.as_completed(futs):
                r = fut.result()
                results.append(r)
                total_done += 1
                print(f"[{total_done}] {r['line']}", flush=True)
        passed = sum(1 for r in results if "cls=PASS" in r["line"])
        print(f"--- {suite} done: {len(results)} cases, auto-PASS={passed}", flush=True)

    print(f"\nALL SUITES DONE: {total_done} cases")

if __name__ == "__main__":
    main()
