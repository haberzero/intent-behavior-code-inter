"""
tests_v2/meta/test_matrix_sync.py — 覆盖矩阵机器校验（三段式引用对账）。

解析 ``tests_v2/COVERAGE_MATRIX.md`` 中 ``file::class::method`` 三段式引用，
与 ``pytest --collect-only`` 的 nodeid 集合对账；引用不存在即失败。
当前矩阵为骨架（0 条目）；随逐域移植逐步填充（Phase 4 与 PT-TEST-3 收敛）。
"""

import re
from pathlib import Path

import pytest

TESTS_V2_ROOT = Path(__file__).resolve().parent.parent
MATRIX_PATH = TESTS_V2_ROOT / "COVERAGE_MATRIX.md"


def _collect_nodeids() -> set:
    """经 ``pytest --collect-only`` 获取真实 nodeid 集合。"""
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(TESTS_V2_ROOT), "--collect-only", "-q"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    nodeids = set()
    for line in proc.stdout.splitlines():
        line = line.strip()
        if "::" in line and not line.startswith("no tests"):
            nodeids.add(line)
    return nodeids


def _matrix_entries() -> list:
    """解析矩阵三段式引用：``<file>::<class>::<method>``。"""
    if not MATRIX_PATH.exists():
        return []
    entries = []
    for line in MATRIX_PATH.read_text(encoding="utf-8").splitlines():
        m = re.search(r"`([^`]+\.py::[^`]+::[^`]+)`", line)
        if m:
            entries.append(m.group(1))
    return entries


class TestMatrixSync:
    def test_matrix_entries_exist_in_collection(self):
        entries = _matrix_entries()
        if not entries:
            return  # 骨架阶段：矩阵空，无引用可校验
        nodeids = _collect_nodeids()
        missing = [e for e in entries if e not in nodeids]
        assert not missing, (
            "覆盖矩阵引用的测试不存在：\n"
            + "\n".join(missing)
            + "\n矩阵与测试集合漂移（三段式引用必须可解析）"
        )
