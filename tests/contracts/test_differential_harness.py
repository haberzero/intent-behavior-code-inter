"""差分等价 harness 常设门（Python 内核确定性 + 结构可用；Rust 对拍为 P9 drop-in）。

- 属 smoke 子集（contracts，机器无关白箱）：高频、进程内、无 LLM、无实时等待。
- 现：验证 Python 内核对确定性语料两次运行**逐字节一致**（参考基线）+ harness 结构可用
  （语料非空/名唯一；Rust drop-in 显式 raise；未知内核 fail-fast）。
- 后（P9）：`scripts/differential_harness.py --diff` 逐条对拍 py vs rust——``run_kernel("rust")``
  接入后自动生效，无需改本门。
"""
import os
import sys

import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (_REPO_ROOT, os.path.join(_REPO_ROOT, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from differential_harness import (  # noqa: E402
    CORPUS,
    check_determinism,
    run_kernel,
)


def test_corpus_nonempty_and_unique_names():
    assert len(CORPUS) >= 5, "差分语料至少覆盖 5 个确定性语义面"
    names = [n for n, _ in CORPUS]
    assert len(set(names)) == len(names), f"语料名重复: {names}"


def test_python_kernel_deterministic_reference():
    all_ok, report = check_determinism()
    assert all_ok, "Python 内核确定性漂移:\n" + "\n".join(report)


def test_rust_kernel_drop_in_is_explicit_not_silent():
    # Rust 内核未就绪：必须显式 raise（非静默回退），drop-in 契约在位（P9 接入点）。
    with pytest.raises(NotImplementedError):
        run_kernel("rust", "print(1)")


def test_unknown_kernel_fail_fast():
    with pytest.raises(ValueError):
        run_kernel("nope", "print(1)")
