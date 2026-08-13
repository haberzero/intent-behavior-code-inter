#!/usr/bin/env python3
"""
Batch runner — 试用地基批量运行器（单一权威源，与 run_one.py 配合）。

可靠性与耗时分层：
  - 每个用例经 run_one.py 子进程运行（OS 级超时 SIGKILL 死循环保护），单用例卡住
    被强制终止，不影响后续用例（不串行堵死整批）。
  - 用例按是否依赖真实 LLM 分层：头部 `# expect-llm: true` 判为 llm 组，否则 mock 组。
    先跑 mock 组（快），再跑 llm 组（真实服务，耗时大）——`--llm-only` 可只跑 llm 组。
  - 本机 LLM 服务见 _toolkit/LLM_SERVICE.md（qwen3.6-35b-a3b @ 127.0.0.1:1234，
    非通用化服务，仅本机）。

用法：
  python <toolkit>/run_batch.py <试用地基根目录> [--timeout 秒] [--max-inst N]
      [--cases "name1 name2 ..."] [--llm-only] [--repo-root 路径]

产出：
  - 每个用例经 run_one.py 写 logs/<case>.log + logs/register.jsonl
  - 批次汇总打印 + 写 logs/batch_result.jsonl（覆盖式）
"""
import argparse
import json
import os
import subprocess
import sys

_EXPECT_LLM_RE = None  # 由 _parse_llm_flag 惰性构造

def _parse_llm_flag(script_path: str) -> bool:
    """读取用例头部 `# expect-llm: true|false`（默认 false）。"""
    global _EXPECT_LLM_RE
    import re
    if _EXPECT_LLM_RE is None:
        _EXPECT_LLM_RE = re.compile(r"^#\s*expect-llm\s*:\s*(\S+)")
    try:
        with open(script_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    break
                m = _EXPECT_LLM_RE.match(line)
                if m:
                    return m.group(1).strip().lower() == "true"
    except OSError:
        pass
    return False


def _collect_cases(trial_dir: str, only_names):
    cases_dir = os.path.join(trial_dir, "cases")
    if only_names:
        names = [n if n.endswith(".ibci") else n + ".ibci" for n in only_names.split()]
        paths = [os.path.join(cases_dir, n) for n in names]
    else:
        paths = sorted(
            os.path.join(cases_dir, n) for n in os.listdir(cases_dir)
            if n.endswith(".ibci")
        )
    return [p for p in paths if os.path.exists(p)]


def main():
    ap = argparse.ArgumentParser(description="Batch-run trial cases with per-case hard timeout.")
    ap.add_argument("trial_dir", help="trial root (contains cases/ + api_config.json)")
    ap.add_argument("--timeout", type=float, default=30.0, help="per-case hard timeout (s)")
    ap.add_argument("--max-inst", type=int, default=5_000_000)
    ap.add_argument("--cases", default=None, help="space-separated case names (omit = all)")
    ap.add_argument("--llm-only", action="store_true", help="only run expect-llm: true cases")
    ap.add_argument("--mock-only", action="store_true", help="only run expect-llm: false cases")
    ap.add_argument("--repo-root", default=None)
    args = ap.parse_args()

    trial_dir = os.path.abspath(args.trial_dir)
    toolkit = os.path.dirname(os.path.abspath(__file__))
    run_one = os.path.join(toolkit, "run_one.py")
    if not os.path.exists(run_one):
        sys.exit(f"run_one.py not found next to run_batch.py: {run_one}")

    cases = _collect_cases(trial_dir, args.cases)
    if not cases:
        sys.exit("no case files found")

    llm_cases = [c for c in cases if _parse_llm_flag(c)]
    mock_cases = [c for c in cases if not _parse_llm_flag(c)]
    if args.llm_only:
        selected = llm_cases
    elif args.mock_only:
        selected = mock_cases
    else:
        selected = mock_cases + llm_cases  # mock 先（快），llm 后（真实服务）

    if not selected:
        sys.exit("no cases match the filter")

    py = os.environ.get("IBCI_PYTHON", os.path.join(os.path.expanduser("~"), "miniconda3", "envs", "ibci", "bin", "python"))
    results = []
    for i, case in enumerate(selected, 1):
        name = os.path.splitext(os.path.basename(case))[0]
        label = f"B-{name}"
        print(f"[{i}/{len(selected)}] {name} ...", flush=True)
        cmd = [py, run_one, os.path.relpath(case, trial_dir),
               "--label", label, "--dim", "BATCH", "--doc", "", "--expected", "",
               "--timeout", str(args.timeout), "--max-inst", str(args.max_inst),
               "--root", trial_dir]
        if args.repo_root:
            cmd += ["--repo-root", args.repo_root]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout + 30)
            line = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else f"[{name}] no output"
        except subprocess.TimeoutExpired:
            line = f"[{name}] BATCH-TIMEOUT"
        results.append({"case": name, "line": line})
        print("   " + line)

    summary = os.path.join(trial_dir, "logs", "batch_result.jsonl")
    os.makedirs(os.path.dirname(summary), exist_ok=True)
    with open(summary, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    passed = sum(1 for r in results if "cls=PASS" in r["line"])
    print(f"\nBATCH DONE: {len(results)} cases, {passed} auto-PASS; summary={summary}")


if __name__ == "__main__":
    main()
