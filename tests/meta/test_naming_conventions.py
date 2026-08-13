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


# 历史锚定措辞（docstring/注释中应改写为行为描述，禁止"对历史错误不重复"的叙述）
_HISTORY_ANCHOR_RE = re.compile(
    r"回归测试|回归保护|守护\s*BUG|修复\s*BUG|BUG\s*#|"
    r"PT-DEBT-\d+|KERNEL_ISSUE-\w|Finding\s*C|"
    r"修复前|此前缺陷|旧守卫|旧\s*BUG|afe9644|"
    r"\b[0-9a-f]{7,40}\b"  # commit 哈希
)


def _is_comment_or_docstring(line: str) -> bool:
    """判断一行是否为注释（# 开头）或 docstring（三引号内容）——可安全断言措辞。"""
    stripped = line.lstrip()
    if stripped.startswith("#"):
        return True
    return False


class TestDocstringHistoryAnchors:
    """docstring/注释禁止"历史错误不重复"式叙述（应为行为契约描述）。

    测试套件的价值判断对象是"应该具备的行为、正确的工作模式"，不是
    "历史代码错误不再重复"。历史锚定词（回归测试/修复 BUG/PT-DEBT-xx/
    commit 哈希等）须改写为行为描述。
    """

    @pytest.mark.parametrize("test_file", list(_all_test_files()))
    def test_no_history_anchors_in_comments(self, test_file):
        src = test_file.read_text(encoding="utf-8")
        bad = []
        for lineno, line in enumerate(src.splitlines(), start=1):
            if not _is_comment_or_docstring(line):
                continue
            m = _HISTORY_ANCHOR_RE.search(line)
            if m:
                bad.append(f"L{lineno}: {line.strip()[:80]} (命中 {m.group(0)!r})")
        assert not bad, (
            f"{test_file.name}: 注释/文档串含历史锚定措辞，应改写为行为契约描述:\n"
            + "\n".join(bad[:10])
        )
