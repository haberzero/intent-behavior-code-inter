#!/usr/bin/env python3
"""
REGISTER 骨架生成器 — 从 register.jsonl 自动生成 REGISTER 报告骨架（单一权威源）。

试用体系自动化机制（规范见 `_toolkit/AUTOMATION.md`）。数据源：`<trial>/logs/register.jsonl`（run_one.py 机械记录，
classification 由 harness 自动判定）。产出：stdout 打印 REGISTER 骨架（总览 + 逐例明细 +
缺陷清单骨架），人工补根因/结论/级别/commit 后覆盖 REGISTER.md。

用法：
  python _toolkit/gen_register.py <试用地基根目录> [--smoke <name>]

规则：
  - 只统计 register.jsonl 中最新一轮记录（每 case 最新一条）。
  - 总览：PASS/GUARD/KERNEL_ISSUE/BOUNDARY/DOC_ISSUE/LLM_BEHAVIOR/LIMIT/HARNESS 计数。
  - 逐例明细：case_id / script / 分类 / exit / 判定 note（out_head 摘要）。
  - 缺陷清单：KERNEL_ISSUE 触发用例（expect-class: KERNEL_ISSUE 且断言失败）与 BOUNDARY/
    LIMIT 骨架——核销判据（expect-out 修复后期望）自动标注。
"""
import argparse
import json
import os
import sys

VALID = ("PASS", "GUARD", "KERNEL_ISSUE", "BOUNDARY", "DOC_ISSUE",
         "LLM_BEHAVIOR", "LIMIT", "HARNESS")


def _load_latest(trial_dir):
    p = os.path.join(trial_dir, "logs", "register.jsonl")
    if not os.path.exists(p):
        sys.exit(f"register.jsonl not found: {p}")
    latest = {}
    for line in open(p, encoding="utf-8"):
        try:
            r = json.loads(line)
        except Exception:
            continue
        # B- 前缀为 run_batch 批量记录，去 B- 前缀后与单独运行记录同用例去重（保留后出现者）
        cid = r["case_id"]
        key = cid[2:] if cid.startswith("B-") else cid
        latest[key] = r
    return latest


def _expect_class(script_path):
    import re
    try:
        with open(script_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                m = re.match(r"^#\s*expect-class\s*:\s*(\S+)", line)
                if m:
                    return m.group(1)
                if line.strip() and not line.startswith("#"):
                    break
    except OSError:
        pass
    return ""


def main():
    ap = argparse.ArgumentParser(description="Generate REGISTER skeleton from register.jsonl")
    ap.add_argument("trial_dir", help="trial root (contains cases/ + logs/register.jsonl)")
    ap.add_argument("--smoke", default="smoke_deadloop", help="smoke case name for HARNESS note")
    args = ap.parse_args()

    trial_dir = os.path.abspath(args.trial_dir)
    latest = _load_latest(trial_dir)
    cases_dir = os.path.join(trial_dir, "cases")

    from collections import Counter
    counts = Counter()
    rows = []
    for cid in sorted(latest):
        r = latest[cid]
        cls = r.get("classification", "") or "<empty>"
        counts[cls] += 1
        script = r.get("script", "")
        exp_cls = _expect_class(os.path.join(cases_dir, os.path.basename(script))) if script else ""
        rows.append((cid, script, exp_cls, cls, r.get("exit_code"), (r.get("note") or "")[:80]))

    print("# REGISTER — <试用名>（骨架，由 gen_register.py 生成，人工补根因/结论）")
    print()
    print("> 分类/级别/编号规范见 `_toolkit/CLASSIFICATION.md`；用例即契约见 CONTRACT_FORMAT.md。")
    print("> 本骨架由 `logs/register.jsonl` 自动生成；人工补 KERNEL_ISSUE 根因、级别、修复状态、结论。")
    print()
    print("## 一、总览")
    print()
    total = len(rows)
    print(f"- **用例总数**：{total} 个（含冒烟）。")
    for c in VALID:
        if counts[c]:
            print(f"- **{c}**：{counts[c]} 例。")
    if counts["KERNEL_ISSUE"]:
        print(f"- **KERNEL_ISSUE 触发用例**：{counts['KERNEL_ISSUE']} 项（编号见 §二，触发用例即缺陷复现证据，不得规避）。")
    print()
    print("## 二、缺陷登记（骨架）")
    print()
    print("> 每条：编号 / 现象 / 证据（用例+日志）/ 根因 / 修复状态 / commit。")
    print("> 缺陷收敛义务：修复必须落 `tests/` 回归（收敛流程见 `_toolkit/AUTOMATION.md`），触发用例经回归试用核销。")
    for cid, script, exp_cls, cls, exit_code, note in rows:
        if cls == "KERNEL_ISSUE":
            print(f"### KERNEL_ISSUE-<域>-<n>（待编号）— {cid}")
            print()
            print(f"- **触发用例**：`{script}`（expect-class: {exp_cls or 'KERNEL_ISSUE'}，修复后期望未达成）")
            print(f"- **exit**：{exit_code}；**note**：{note}")
            print(f"- **根因分析起点**：<人工>")
            print(f"- **修复状态**：待修复（独立窗口）")
            print()
    print("## 三、逐例明细")
    print()
    print("| case_id | 分类 | exit | 判定 note |")
    print("|---------|------|------|-----------|")
    for cid, script, exp_cls, cls, exit_code, note in rows:
        print(f"| {cid} | {cls} | {exit_code} | {note} |")
    print()
    print("## 四、结论（人工）")
    print()
    print("<本试用地基验证了什么 / 发现什么 / 下一步>")


if __name__ == "__main__":
    main()
