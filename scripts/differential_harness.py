#!/usr/bin/env python3
"""
differential_harness — 双内核差分等价 harness（Rust 内核替换的**常设安全网**）。

职责
----
同一 IBCI 输入 → 经 Python 内核（现）/ Rust 内核（P9 接入）执行 → 输出**逐字节比对**。
- 现（Rust 内核未就绪）：① 建立 Python 内核**参考输出**（golden 基线）；② 验证**确定性**
  （同内核同输入两次运行输出逐字节一致）——这是 Rust 内核也必须满足的性质。
- 后（Rust 内核就绪）：``run_kernel("rust", code)`` 接入后，``--diff`` 逐条对拍 py vs rust。

设计纪律
--------
- **语料全确定性**：零 LLM / 零实时等待——差分等价只对确定性执行面成立（LLM 面非确定，不在对拍范围）。
- **进程内**：经 ``IBCIEngine.run_string``，无子进程（高频可重复，契合 smoke/差分高频验证）。
- **单点真理**：语料 = 本文件 ``CORPUS``（可扩）；比对 = 输出逐字节（print 行 + 退出态）。
- **drop-in**：Rust 内核只需实现 ``run_kernel("rust", ...)``，返回同一 ``{"output", "ok"}`` 契约。

用法
----
  python scripts/differential_harness.py --check       # 验证 Python 内核确定性 + 打印
  python scripts/differential_harness.py --snapshot     # 输出 Python 参考快照（JSON，存基线）
  python scripts/differential_harness.py --diff         # （P9 Rust 就绪后）py vs rust 对拍
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# 确定性面默认 root（测试目录；语料为自包含脚本，无外部文件依赖）
_DEFAULT_ROOT = os.path.join(_REPO_ROOT, "tests")


def run_kernel(kernel: str, code: str, *, root_dir: str | None = None) -> dict:
    """经指定内核执行 IBCI 代码，返回 ``{"output": [str], "ok": bool}``。

    ``kernel="py"`` = 现（进程内 IBCIEngine）；``kernel="rust"`` = P9 接入点（未就绪 raise）。
    契约：同 kernel 同 code 多次运行，``output``/``ok`` 逐字节/逐值一致（确定性）。
    """
    # 规范化输入：确保尾部换行（两内核见同一规范化字节，差分输入 canonical）。
    code = code if code.endswith("\n") else code + "\n"
    if kernel == "py":
        from core.engine import IBCIEngine
        from core.kernel.issue import CompilerError

        lines: list[str] = []
        ok, error = True, None
        try:
            engine = IBCIEngine(root_dir=root_dir or _DEFAULT_ROOT)
            engine.run_string(code, output_callback=lambda t: lines.append(str(t)), silent=True)
        except CompilerError as e:
            # 编译错误亦属差分面（两内核应一致报错）——捕获而非静默/崩溃。
            ok, error = False, "compile:" + (e.diagnostics[0].code if e.diagnostics else "?")
        except Exception as e:
            ok, error = False, f"run:{type(e).__name__}"
        return {"output": lines, "ok": ok, "error": error}
    if kernel == "rust":
        raise NotImplementedError(
            "Rust 内核尚未构建（P9）。接入后在此经同一 {'output','ok'} 契约返回，"
            "本 harness 即成为 py↔rust 差分等价门。"
        )
    raise ValueError(f"未知内核: {kernel!r}（支持 'py' / 'rust'）")


# 语料（单点真理 = 本列表；全确定性；按语义面覆盖，可扩——R-B 世界模型里程碑 /
# R-A quote/eval 表达式后续并入此处作差分 fuzz 语料）。
CORPUS: list[tuple[str, str]] = [
    ("arithmetic", 'print(21 * 2)'),
    ("control_flow", 'int n = 5\nif n > 3:\n    print("big")\nelse:\n    print("small")'),
    ("recursion", 'func s(int n) -> int:\n    if n <= 0:\n        return 0\n    return n + s(n - 1)\nprint(s(10))'),
    ("string_op", 'print("hello" + " world")'),
    ("container", 'print(len([1, 2, 3]))'),
    # 数据/命令二元性最小面（R-A quote/eval 的朴素实例）：字符串是数据（原样打印），
    # 同一字面量被运算是命令（求值为 4）。
    ("data_command_duality", 'msg = "2 + 2"\nprint(msg)\nprint(2 + 2)'),
]


def _digest(res: dict) -> str:
    """输出指纹（确定性可比的稳定摘要；含退出态 + 错误码——差分面含错误行为）。"""
    payload = "\n".join(res["output"]) + "\x00" + str(res["ok"]) + "\x00" + str(res.get("error"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def check_determinism() -> tuple[bool, list[str]]:
    """验证 Python 内核确定性：语料每项跑两次，输出逐字节一致。返回 (全通过, 报告行)。"""
    report: list[str] = []
    all_ok = True
    for name, code in CORPUS:
        a = run_kernel("py", code)
        b = run_kernel("py", code)
        det = a["output"] == b["output"] and a["ok"] == b["ok"]
        all_ok = all_ok and det
        tag = "DETERMINISTIC" if det else "DRIFT!"
        report.append(f"  [{tag}] {name}: output={a['output']} ok={a['ok']} digest={_digest(a)}")
    return all_ok, report


def reference_snapshot() -> dict:
    """Python 内核参考输出（Rust 对拍的 golden 基线）。"""
    out: dict = {}
    for name, code in CORPUS:
        res = run_kernel("py", code)
        out[name] = {**res, "digest": _digest(res)}
    return out


def diff_rust_vs_python() -> tuple[bool, list[str]]:
    """（P9 Rust 内核就绪后）逐条对拍 py vs rust 输出。Rust 未就绪时逐项 SKIP。"""
    report: list[str] = []
    all_ok = True
    for name, code in CORPUS:
        try:
            rust = run_kernel("rust", code)
        except NotImplementedError as e:
            report.append(f"  [SKIP] {name}: Rust 内核未就绪（{str(e).split('。')[0]}）")
            continue
        py = run_kernel("py", code)
        eq = rust["output"] == py["output"] and rust["ok"] == py["ok"]
        all_ok = all_ok and eq
        tag = "EQUIV" if eq else "DIFF!"
        report.append(f"  [{tag}] {name}: py={py['output']} rust={rust['output']}")
    return all_ok, report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="双内核差分等价 harness（Rust 内核替换安全网）")
    ap.add_argument("--check", action="store_true", help="验证 Python 内核确定性 + 打印参考")
    ap.add_argument("--snapshot", action="store_true", help="输出 Python 参考快照（JSON）")
    ap.add_argument("--diff", action="store_true", help="（P9 Rust 就绪后）py vs rust 对拍")
    args = ap.parse_args(argv)

    if args.check:
        ok, report = check_determinism()
        print("=== differential_harness: Python 内核确定性 + 参考 ===")
        print("\n".join(report))
        print("ALL_DETERMINISTIC" if ok else "DETERMINISM_DRIFT")
        return 0 if ok else 1
    if args.snapshot:
        print(json.dumps(reference_snapshot(), ensure_ascii=False, indent=2))
        return 0
    if args.diff:
        ok, report = diff_rust_vs_python()
        print("=== differential_harness: py vs rust 对拍 ===")
        print("\n".join(report))
        print("ALL_EQUIV" if ok else "DIFF_FOUND")
        return 0 if ok else 1
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
