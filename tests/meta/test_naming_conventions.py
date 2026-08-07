"""
tests/meta/test_naming_conventions.py — 命名规范机器校验。

约束（测试体系设计冻结 Phase 0.2）：
- 文件名 ``test_<concept>.py``
- 类名 ``Test<Concept><Aspect>``（大驼峰）
- 禁里程碑代号（如 ``TestG1``/``TestM2``/``TestD3``/``NS2b``/``PT21`` 等）
- e2e 文件去 ``e2e_`` 前缀（目录承载层义）
- runtime 文件去冗余 ``test_runtime_`` 前缀
"""

import re
from pathlib import Path

import pytest

TESTS_ROOT = Path(__file__).resolve().parent.parent

# 里程碑代号类名（测试类名前缀，违反"禁里程碑代号"）
_BANNED_CLASS_PREFIXES = re.compile(
    r"^Test(?:\d+[A-Za-z]*|M\d|D\d|G\d|NS\d+[a-z]*|PT\d+|[a-z]\d)",
)

_DIRS = ["kernel", "compiler", "compiler/semantic", "runtime", "plugins",
         "contracts", "e2e", "compliance", "sdk", "meta"]


def _all_test_files():
    for d in _DIRS:
        for p in sorted((TESTS_ROOT / d).glob("test_*.py")):
            yield p


class TestFileNameConventions:
    @pytest.mark.parametrize("test_file", list(_all_test_files()))
    def test_filename_matches_concept(self, test_file):
        name = test_file.name
        assert name.startswith("test_"), f"{name}: must start with 'test_'"
        assert name.endswith(".py")
        # e2e 文件禁 e2e_ 前缀（目录承载层义）
        if test_file.parent.name == "e2e":
            assert not name.startswith("test_e2e_"), (
                f"{name}: e2e/ 文件禁 'e2e_' 前缀（目录承载层义）"
            )
        # runtime 文件禁冗余 test_runtime_ 前缀
        if test_file.parent.name == "runtime":
            assert not name.startswith("test_runtime_"), (
                f"{name}: runtime/ 文件禁冗余 'test_runtime_' 前缀"
            )


class TestClassNameConventions:
    @pytest.mark.parametrize("test_file", list(_all_test_files()))
    def test_class_names_avoid_milestone_codes(self, test_file):
        src = test_file.read_text(encoding="utf-8")
        for m in re.finditer(r"^class\s+(\w+)", src, re.MULTILINE):
            cls = m.group(1)
            assert not _BANNED_CLASS_PREFIXES.match(cls), (
                f"{test_file.name}: 类名 {cls!r} 含里程碑代号，违反命名规范"
            )
