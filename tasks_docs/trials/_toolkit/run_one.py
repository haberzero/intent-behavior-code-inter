#!/usr/bin/env python3
"""
Trial harness — 单一权威源（IBCI 试用地基统一运行入口）。

被各试用地基引用（软链），非复制。位置无关：试用目录经 ``--root`` 显式传入，
仓库根自动从 ``--root`` 上溯查找 main.py（或用 ``--repo-root`` 显式覆盖）。

硬性死循环保护（用户强制，不可妥协）：
  - 每次试用运行在独立进程组，超时（--timeout，必填）后 SIGKILL 整个进程组。
    不存在绕过保护的执行路径。
  - 每用例指令上限（--max-inst）作为 VM 内第二道守卫。
  - LLM 端点调用超时由引擎配置（api_config.json defaults.timeout）承担。
  未显式提供 timeout 时 harness 拒绝运行。

确定性记录（record-first，可溯源）：
  - 每次运行写 logs/<case_id>.log（stdout+stderr 合并、墙钟时长、退出码、超时标志）。
  - 每次运行向 logs/register.jsonl 追加一行确定性记录：
    {case_id, script, dim, doc_ref, expected, timeout_s, exit_code,
     timed_out, duration_s, out_head, err_head, classification, severity, note}
  - classification 由本 harness 依用例头部断言**自动判定**（见 _toolkit/CONTRACT_FORMAT.md）；
    **无断言的用例判 HARNESS**（用例必须声明 expect-class + 至少一个断言条件，不保留
    人工判定双轨）。severity/note 由试用 agent 检查后填写。

用例即契约（用例头部断言）：
  # expect-class: <PASS|GUARD|KERNEL_ISSUE|BOUNDARY|DOC_ISSUE|LLM_BEHAVIOR|LIMIT|HARNESS>
  # expect-out: <期望输出行，多行用 | 分隔>
  # expect-exit: <0|1|nonzero>
  # expect-code: <诊断码，可逗号分隔>

用法：
  python <toolkit>/run_one.py cases/<case>.ibci \
      --label <case_id> --dim <dim> --doc <doc_ref> --expected <描述> \
      --timeout <秒(必填)> --max-inst <指令上限> --root <试用地基根目录>
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

# 诊断码前缀（对齐 core/base/diagnostics/codes.py 命名制：LEX/PAR/SEM/DEP/INT/RUN/KDIAG/CFG）
_CODE_RE = re.compile(r"\b(SEM|PAR|LEX|DEP|INT|RUN|KDIAG|CFG)_[A-Z0-9_]+\b")
_EXPECT_RE = re.compile(r"^#\s*expect-(\w+)\s*:\s*(.*)$")

VALID_CLASSES = {
    "PASS", "GUARD", "KERNEL_ISSUE", "BOUNDARY", "DOC_ISSUE",
    "LLM_BEHAVIOR", "LIMIT", "HARNESS",
}


def _parse_expectations(script_path: str):
    """从 .ibci 头部解析 ``# expect-*:`` 断言；无断言返回 {}。"""
    exps = {}
    try:
        with open(script_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = _EXPECT_RE.match(line)
                if not m:
                    if line.strip() and not line.startswith("#"):
                        break  # 头部注释结束（进入代码）
                    continue
                key, val = m.group(1), m.group(2).strip()
                if key == "class":
                    exps["class"] = val
                elif key == "out":
                    exps["out"] = [p.strip() for p in val.split("|") if p.strip()]
                elif key == "exit":
                    exps["exit"] = val
                elif key == "code":
                    exps["code"] = [c.strip() for c in val.split(",") if c.strip()]
    except OSError:
        return {}
    return exps


def _extract_codes(text: str):
    """从输出文本提取出现的诊断码（有序去重）。"""
    return list(dict.fromkeys(_CODE_RE.findall(text)))


def _judge(exps: dict, stdout_text: str, exit_code: int):
    """依断言判定分类。无断言或断言失败均判 HARNESS（彻底，无人工判定双轨）。"""
    if not exps:
        return "HARNESS", "<无断言：用例必须声明 expect-class + 至少一个断言条件>"
    expect_class = exps.get("class", "")
    if expect_class not in VALID_CLASSES:
        return "HARNESS", f"<非法 expect-class: {expect_class!r}>"
    has_assertion = any(k in exps for k in ("out", "exit", "code"))
    if not has_assertion:
        return "HARNESS", "<无断言条件（expect-out/exit/code 至少其一）>"

    lines = stdout_text.splitlines()
    fails = []

    if "out" in exps:
        expected_lines = exps["out"]
        remaining = list(lines)
        for want in expected_lines:
            if want in remaining:
                idx = remaining.index(want)
                remaining = remaining[idx + 1:]
            else:
                fails.append(f"expect-out 缺行 {want!r}")
                break

    if "exit" in exps:
        want_exit = exps["exit"]
        if want_exit == "nonzero":
            if exit_code == 0:
                fails.append(f"expect-exit=nonzero 但 exit_code=0")
        else:
            try:
                if exit_code != int(want_exit):
                    fails.append(f"expect-exit={want_exit} 但 exit_code={exit_code}")
            except ValueError:
                fails.append(f"非法 expect-exit: {want_exit!r}")

    if "code" in exps:
        got_codes = _extract_codes(stdout_text)
        for want in exps["code"]:
            if want not in got_codes:
                fails.append(f"expect-code {want} 未出现（got: {got_codes}）")

    if fails:
        # KERNEL_ISSUE 触发用例：断言是"修复后期望"——断言失败 = 缺陷仍存在（归 KERNEL_ISSUE，
        # 即缺陷证据）；断言达成 = 修复后行为达成（归 PASS + 待核销）。其余分类断言失败一律
        # 判 HARNESS（防止跑通即 PASS 掩盖断言缺口）。
        if expect_class == "KERNEL_ISSUE":
            return "KERNEL_ISSUE", "缺陷复现确认（修复后期望未达成）; " + "; ".join(fails)
        return "HARNESS", "; ".join(fails)
    if expect_class == "KERNEL_ISSUE":
        # 修复后期望已达成：缺陷应已修复，转为 PASS 待核销（agent 更新 INDEX/PENDING_TASKS）。
        return "PASS", "KERNEL_ISSUE 修复后行为达成，待核销"
    return expect_class, "auto-judged"


def _find_repo_root(start: str):
    """从起始目录逐级上溯查找含 ``main.py`` 的仓库根；找不到返回 None。"""
    d = os.path.abspath(start)
    while True:
        if os.path.exists(os.path.join(d, "main.py")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent
    return None


def parse_args():
    p = argparse.ArgumentParser(description="Run one IBCI trial case under hard dead-loop protection.")
    p.add_argument("script", help="path to the .ibci case file (relative to trial root)")
    p.add_argument("--label", required=True, help="case id, e.g. D1-01-001")
    p.add_argument("--dim", required=True, help="dimension, e.g. D1/D2/D3")
    p.add_argument("--doc", default="", help="doc reference (chapter/section)")
    p.add_argument("--expected", default="", help="expected behavior description")
    p.add_argument("--timeout", required=True, type=float, help="hard wall-clock timeout in seconds (MANDATORY)")
    p.add_argument("--max-inst", type=int, default=5_000_000, help="VM instruction cap (default 5e6)")
    p.add_argument("--root", required=True, help="trial root dir (must contain api_config.json + cases/ + logs/)")
    p.add_argument("--repo-root", default=None, help="repo root containing main.py (auto-detected if omitted)")
    p.add_argument("--extra", action="append", default=[], help="extra CLI args for main.py run, e.g. --no-sniff")
    p.add_argument("--expected-exit", type=int, default=None, help="expected exit code (0=ok, nonzero=error expected)")
    args = p.parse_args()

    if not os.path.exists(args.script) and not os.path.exists(os.path.join(args.root, args.script)):
        sys.exit(f"case script not found: {args.script}")
    if not os.path.exists(os.path.join(args.root, "api_config.json")):
        sys.exit(f"api_config.json missing in root: {args.root}")
    if args.timeout <= 0:
        sys.exit("timeout must be positive")
    return args


def main():
    args = parse_args()
    trial_dir = os.path.abspath(args.root)
    repo_root = args.repo_root or _find_repo_root(trial_dir)
    if repo_root is None:
        sys.exit("repo root (containing main.py) not found from --root; pass --repo-root explicitly")
    logs_dir = os.path.join(trial_dir, "logs")
    register = os.path.join(logs_dir, "register.jsonl")
    main_py = os.path.join(repo_root, "main.py")
    python = os.environ.get("IBCI_PYTHON", os.path.join(os.path.expanduser("~"), "miniconda3", "envs", "ibci", "bin", "python"))

    # script 路径：绝对路径或相对 trial_dir
    script = args.script if os.path.isabs(args.script) else os.path.abspath(os.path.join(trial_dir, args.script))
    if not os.path.exists(script):
        sys.exit(f"case script not found: {script}")

    os.makedirs(logs_dir, exist_ok=True)

    cmd = [python, main_py, "run", script,
           "--root", trial_dir,
           "--max-inst", str(args.max_inst)] + args.extra
    log_path = os.path.join(logs_dir, args.label + ".log")

    start = time.monotonic()
    timed_out = False
    try:
        # start_new_session=True -> child gets its own process group so a SIGKILL
        # to that group kills the VM and any LLM client worker it spawns.
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            text=True,
            errors="replace",
        )
        try:
            out, _ = proc.communicate(timeout=args.timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(proc.pid, 9)
            except ProcessLookupError:
                pass
            try:
                out, _ = proc.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                out, _ = proc.communicate()
        exit_code = proc.returncode
    except Exception as exc:  # harness-level guard: never leave a hung process
        out = f"[HARNESS-ERROR] {exc}\n"
        exit_code = -1
        try:
            os.killpg(proc.pid, 9)
        except Exception:
            pass
    duration_s = round(time.monotonic() - start, 2)

    classification, judge_note = _judge(_parse_expectations(script), out or "", exit_code)

    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"# {args.label}  dim={args.dim}  script={os.path.relpath(script, trial_dir)}\n")
        f.write(f"# doc={args.doc}  expected={args.expected}\n")
        f.write(f"# timeout={args.timeout}s  max_inst={args.max_inst}  exit={exit_code}  timed_out={timed_out}  duration={duration_s}s\n")
        f.write(f"# auto-classification={classification}  judge={judge_note}\n")
        f.write("# " + " ".join(cmd) + "\n")
        f.write("=" * 72 + "\n")
        f.write(out if out else "<no output>")
        f.write("\n")

    row = {
        "case_id": args.label,
        "script": os.path.relpath(script, trial_dir),
        "dim": args.dim,
        "doc": args.doc,
        "expected": args.expected,
        "timeout_s": args.timeout,
        "max_inst": args.max_inst,
        "exit_code": exit_code,
        "timed_out": timed_out,
        "duration_s": duration_s,
        "out_head": (out[:400] if out else "").replace("\n", " "),
        "err_head": "",
        "classification": classification,  # auto-judged from assertions (HARNESS if none/failed)
        "severity": "",                    # filled by trial agent
        "note": judge_note,
    }
    with open(register, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # console summary (compact, for agent + tail)
    status = "TIMEOUT-KILLED" if timed_out else f"exit={exit_code}"
    print(f"[{args.label}] {status}  dur={duration_s}s  cls={classification or 'manual'}  log={log_path}")


if __name__ == "__main__":
    main()
