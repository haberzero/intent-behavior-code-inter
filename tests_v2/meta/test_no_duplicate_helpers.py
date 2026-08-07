"""
tests_v2/meta/test_no_duplicate_helpers.py — 禁本地复刻统一 helper。

禁列从根 conftest / runtime conftest 公开 helper 名自动派生（避免漂移）。
测试文件不得重新 ``def`` 定义同名 helper（如 ``run_ibci``/``compile_ibci`` 等）。
"""

import inspect
from pathlib import Path

import pytest

TESTS_V2_ROOT = Path(__file__).resolve().parent.parent

# 统一 helper 禁列（与 tests_v2/conftest.py 公开 API 一致，单一来源）
_BANNED = {
    "run_ibci", "compile_ibci", "compile_or_errors", "expect_compile_error",
    "expect_runtime_error", "make_vm", "find_node", "find_nodes",
    "find_node_uid", "find_node_uids", "native", "make_intent",
}

# 排除 meta 自身
_EXEMPT_FILES = {"test_no_duplicate_helpers.py"}


def _all_test_files():
    for p in TESTS_V2_ROOT.rglob("test_*.py"):
        if p.name in _EXEMPT_FILES:
            continue
        yield p


class TestNoDuplicateHelpers:
    @pytest.mark.parametrize("test_file", list(_all_test_files()))
    def test_no_local_redefinition(self, test_file):
        src = test_file.read_text(encoding="utf-8")
        for name in _BANNED:
            assert not re_search_def(src, name), (
                f"{test_file.name}: 本地重定义统一 helper {name!r}（应 import 自 conftest）"
            )


def re_search_def(src: str, name: str) -> bool:
    import re

    return re.search(rf"^\s*def\s+{name}\s*\(", src, re.MULTILINE) is not None
