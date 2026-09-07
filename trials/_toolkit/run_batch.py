#!/usr/bin/env python3
"""
Batch runner — 试用地基批量运行器（单一权威源，与 run_one.py 配合）。

可靠性与耗时分层：
  - 每个用例经 run_one.py 子进程运行（OS 级超时 SIGKILL 死循环保护），单用例卡住
    被强制终止，不影响后续用例（不串行堵死整批）。
  - 用例按是否依赖真实 LLM 分层：头部 `# expect-llm: true` 判为 llm 组，否则 mock 组。
    先跑 mock 组（快），再跑 llm 组（真实服务，耗时大）——`--llm-only` 可只跑 llm 组。
  - 本机 LLM 服务见 _toolkit/LLM_SERVICE.md（服务无关规范；端点/模型等本机事实
    见本机 AGENTS.local.md，不入库）。

用法：
  python <toolkit>/run_batch.py <试用地基根目录> [--timeout 秒]
      [--cases "name1 name2 ..."] [--llm-only] [--repo-root 路径]

产出：
  - 每个用例经 run_one.py 写 logs/<case>.log + logs/register.jsonl
  - 批次汇总打印 + 写 logs/batch_result.jsonl（覆盖式）
"""
import argparse
import json
import os
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
        paths = []
        for n in os.listdir(cases_dir):
            p = os.path.join(cases_dir, n)
            if n.endswith(".ibci"):
                paths.append(p)
            elif os.path.isdir(p):
                # 用例目录布局（多文件用例：入口 = main.ibci，同目录辅助
                # 模块文件如 geo.ibci 非入口，按入口相对路径解析）
                main = os.path.join(p, "main.ibci")
                if os.path.exists(main):
                    paths.append(main)
        paths = sorted(paths)
    return [p for p in paths if os.path.exists(p)]


def _run_one_case(case, trial_dir, run_one, py, timeout, repo_root):
    """在线程中执行单个用例（独立 subprocess + 独立超时，卡死不拖垮整批）。"""
    import subprocess
    # 用例名 = 相对 cases/ 的路径（顶层 = 文件名，子目录布局 = 目录/入口名，
    # 避免多目录 main.ibci 同名混淆）
    cases_dir = os.path.join(trial_dir, "cases")
    name = os.path.splitext(os.path.relpath(case, cases_dir))[0]
    label = f"B-{name.replace('/', '-')}"
    # 目录型用例（子目录布局，多文件自包含工程——KERNEL_ISSUE-IMPORT-2 短期
    # harness 解）：以用例目录为 root，入口 = 目录内 main.ibci；
    # 顶层用例：root = trial_dir（既有形态）。
    if "/" in name or (os.sep in name):
        root_arg = os.path.dirname(case)
        entry_rel = os.path.basename(case)
    else:
        root_arg = trial_dir
        entry_rel = os.path.relpath(case, trial_dir)
    cmd = [py, run_one, entry_rel,
           "--label", label, "--dim", "BATCH", "--doc", "", "--expected", "",
           "--timeout", str(timeout),
           "--root", root_arg]
    if repo_root:
        cmd += ["--repo-root", repo_root]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 30)
        line = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else f"[{name}] no output"
    except subprocess.TimeoutExpired:
        line = f"[{name}] BATCH-TIMEOUT"
    except Exception as exc:
        line = f"[{name}] BATCH-ERROR {exc}"
    return {"case": name, "line": line}


def main():
    ap = argparse.ArgumentParser(description="Batch-run trial cases with per-case hard timeout.")
    ap.add_argument("trial_dir", help="trial root (contains cases/; api_config.json discovered upward)")
    ap.add_argument("--timeout", type=float, default=30.0, help="per-case hard timeout (s)")
    ap.add_argument("--cases", default=None, help="space-separated case names (omit = all)")
    ap.add_argument("--llm-only", action="store_true", help="only run expect-llm: true cases")
    ap.add_argument("--mock-only", action="store_true", help="only run expect-llm: false cases")
    ap.add_argument("--repo-root", default=None)
    ap.add_argument("--parallel", type=int, default=1,
                    help="并发度（1=串行）。mock 用例可设 4-8（快）；真实 LLM 用例建议 1-2"
                         "（非思考模式单例快，高并发仍可能压爆本地服务）")
    ap.add_argument("--probe", action="store_true",
                    help="llm 组运行前探测端点（失败则 llm 用例跳过记 HARNESS，不误判缺陷）")
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
    # 分阶段：mock 快（可用较高并发），llm 真实服务（自动限并发防过载）。
    # 每用例独立 subprocess + 独立超时，单用例卡死不拖垮整批。
    stages = []
    if args.llm_only:
        stages = [("llm", llm_cases, min(args.parallel, 2))]
    elif args.mock_only:
        stages = [("mock", mock_cases, args.parallel)]
    else:
        stages = [("mock", mock_cases, args.parallel), ("llm", llm_cases, min(args.parallel, 2))]

    total = sum(len(s[1]) for s in stages)
    if total == 0:
        sys.exit("no cases match the filter")

    # llm 组预检（--probe）：端点探测未通过时 llm 用例整体跳过记 HARNESS（环境缺失），
    # 不误判为内核缺陷；mock 组不受影响。
    skipped = []
    if args.probe and any(name == "llm" and cases for name, cases, _ in stages):
        from probe import probe_connection, format_probe
        pd = probe_connection(trial_dir)
        print(f"[probe] {format_probe(pd)}", flush=True)
        if not pd["ok"]:
            for name, cases, workers in stages:
                if name == "llm":
                    for c in cases:
                        cname = os.path.splitext(os.path.basename(c))[0]
                        skipped.append({"case": cname,
                                        "line": f"[{cname}] cls=HARNESS note=LLM 服务探测未通过（{pd['reason']}）"})
                    stages = [(n, [], w) if n == "llm" else (n, cs, w) for n, cs, w in stages]

    py = os.environ.get("IBCI_PYTHON", sys.executable)
    results = []
    done = 0
    for r in skipped:
        results.append(r)
        print("   " + r["line"], flush=True)
    for stage_name, stage_cases, workers in stages:
        if not stage_cases:
            continue
        workers = max(1, min(workers, len(stage_cases)))
        if workers == 1:
            for case in stage_cases:
                name = os.path.splitext(os.path.basename(case))[0]
                done += 1
                print(f"[{done}/{total}] ({stage_name}) {name} ...", flush=True)
                r = _run_one_case(case, trial_dir, run_one, py, args.timeout, args.repo_root)
                results.append(r)
                print("   " + r["line"], flush=True)
        else:
            import concurrent.futures as cf
            print(f"[batch] ({stage_name}) parallel={workers}  cases={len(stage_cases)}", flush=True)
            with cf.ThreadPoolExecutor(max_workers=workers) as ex:
                futures = {ex.submit(_run_one_case, case, trial_dir, run_one, py,
                                     args.timeout, args.repo_root): case
                           for case in stage_cases}
                for fut in cf.as_completed(futures):
                    r = fut.result()
                    results.append(r)
                    done += 1
                    print(f"[{done}/{total}] ({stage_name}) {r['case']} ...", flush=True)
                    print("   " + r["line"], flush=True)

    summary = os.path.join(trial_dir, "logs", "batch_result.jsonl")
    os.makedirs(os.path.dirname(summary), exist_ok=True)
    with open(summary, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    passed = sum(1 for r in results if "cls=PASS" in r["line"])
    print(f"\nBATCH DONE: {len(results)} cases, {passed} auto-PASS; summary={summary}")


if __name__ == "__main__":
    main()
