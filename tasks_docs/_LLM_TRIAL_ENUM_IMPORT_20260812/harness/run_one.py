#!/usr/bin/env python3
"""
Trial harness for the real-LLM IBCI stress trial (2026-08-12).

HARD DEAD-LOOP PROTECTION (user-mandated, non-negotiable):
  - Every trial run is executed via a dedicated process group and killed with
    SIGKILL after a mandatory wall-clock timeout. There is no code path that
    runs a case without this protection.
  - A per-case instruction cap (--max-inst) is passed to the CLI as a second
    guard inside the VM.
  - The LLM endpoint call timeout is enforced by the engine config
    (api_config.json defaults.timeout).
  The harness refuses to run if the timeout is not explicitly supplied.

DETERMINISTIC RECORDING (record-first, traceable):
  - Each run writes a full log to logs/<case_id>.log (stdout+stderr merged,
    wall-clock duration, exit code, timeout flag).
  - Each run appends one deterministic row to logs/register.jsonl:
    {case_id, script, dim, doc_ref, expected, timeout_s, exit_code,
     timed_out, duration_s, out_head, err_head, classification, severity,
     note}
  - classification/severity are filled by the trial agent after inspection;
     the mechanical fields are written by this harness.
"""
import argparse
import json
import os
import subprocess
import sys
import time

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
HARNESS_DIR = os.path.dirname(os.path.abspath(__file__))
TRIAL_DIR = os.path.abspath(os.path.join(HARNESS_DIR, ".."))
LOGS_DIR = os.path.join(TRIAL_DIR, "logs")
REGISTER = os.path.join(LOGS_DIR, "register.jsonl")
DEFAULT_ROOT = TRIAL_DIR
MAIN = os.path.join(REPO_ROOT, "main.py")
PYTHON = os.environ.get("IBCI_PYTHON", os.path.join(os.path.expanduser("~"), "miniconda3", "envs", "ibci", "bin", "python"))


def parse_args():
    p = argparse.ArgumentParser(description="Run one IBCI trial case under hard dead-loop protection.")
    p.add_argument("script", help="path to the .ibci case file")
    p.add_argument("--label", required=True, help="case id, e.g. D1-01-001")
    p.add_argument("--dim", required=True, help="dimension, e.g. D1/D2/D3")
    p.add_argument("--doc", default="", help="doc reference (chapter/section)")
    p.add_argument("--expected", default="", help="expected behavior description")
    p.add_argument("--timeout", required=True, type=float, help="hard wall-clock timeout in seconds (MANDATORY)")
    p.add_argument("--max-inst", type=int, default=5_000_000, help="VM instruction cap (default 5e6)")
    p.add_argument("--root", default=DEFAULT_ROOT, help="project root (must contain api_config.json)")
    p.add_argument("--extra", action="append", default=[], help="extra CLI args for main.py run, e.g. --no-sniff")
    p.add_argument("--expected-exit", type=int, default=None, help="expected exit code (0=ok, nonzero=error expected)")
    args = p.parse_args()

    if not os.path.exists(args.script):
        sys.exit(f"case script not found: {args.script}")
    if not os.path.exists(os.path.join(args.root, "api_config.json")):
        sys.exit(f"api_config.json missing in root: {args.root}")
    if args.timeout <= 0:
        sys.exit("timeout must be positive")
    return args


def main():
    args = parse_args()
    os.makedirs(LOGS_DIR, exist_ok=True)

    cmd = [PYTHON, MAIN, "run", args.script,
           "--root", args.root,
           "--max-inst", str(args.max_inst)] + args.extra
    log_path = os.path.join(LOGS_DIR, args.label + ".log")

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

    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"# {args.label}  dim={args.dim}  script={args.script}\n")
        f.write(f"# doc={args.doc}  expected={args.expected}\n")
        f.write(f"# timeout={args.timeout}s  max_inst={args.max_inst}  exit={exit_code}  timed_out={timed_out}  duration={duration_s}s\n")
        f.write("# " + " ".join(cmd) + "\n")
        f.write("=" * 72 + "\n")
        f.write(out if out else "<no output>")
        f.write("\n")

    row = {
        "case_id": args.label,
        "script": os.path.relpath(args.script, TRIAL_DIR),
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
        "classification": "",  # filled by trial agent after inspection
        "severity": "",        # filled by trial agent
        "note": "",
    }
    with open(REGISTER, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")

    # console summary (compact, for agent + tail)
    status = "TIMEOUT-KILLED" if timed_out else f"exit={exit_code}"
    print(f"[{args.label}] {status}  dur={duration_s}s  log={log_path}")


if __name__ == "__main__":
    main()
