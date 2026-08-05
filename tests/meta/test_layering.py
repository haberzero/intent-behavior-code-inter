"""
tests/meta/test_layering.py
===========================

CI enforcement: Prevent test-layering red-line violations.

The test suite is organized into layers with explicit boundaries
(see tests/README.md):

- ``kernel/``     — pure data-structure unit tests; MUST NOT start IBCIEngine
- ``compiler/``   — compile-only tests; MUST NOT call run_ibci()
- ``runtime/``    — small-snippet runtime tests; no complex multi-module scripts
- ``e2e/``        — full-program end-to-end tests; MUST NOT import core.runtime internals
- ``compliance/`` — black-box public-API tests; MUST NOT import core.runtime internals

This meta-test statically scans test files to enforce these boundaries,
preventing layer drift that makes the test suite harder to maintain.
"""
import os
import re
from pathlib import Path

import pytest

TESTS_ROOT = Path(__file__).resolve().parent.parent


def _read_source(path: Path) -> str:
    """Read a Python source file as text (UTF-8)."""
    return path.read_text(encoding="utf-8")


def _find_test_files(subdir: str) -> list[Path]:
    """Find all test_*.py files in a tests subdirectory."""
    d = TESTS_ROOT / subdir
    if not d.is_dir():
        return []
    return sorted(d.rglob("test_*.py"))


# ---------------------------------------------------------------------------
# runtime/modules/ MUST NOT contain a file.py that shadows the IBCI "file" module
# ---------------------------------------------------------------------------

class TestRuntimeModulesNamingRedLine:
    """Prevent Python-level shadowing of IBCI kernel-native module names."""

    REPO_ROOT = TESTS_ROOT.parent

    def test_no_file_py_in_runtime_modules(self):
        """core/runtime/modules/file.py would shadow the IBCI 'file' module implementation."""
        forbidden = self.REPO_ROOT / "core" / "runtime" / "modules" / "file.py"
        assert not forbidden.exists(), (
            f"{forbidden}: must not exist — it would shadow the IBCI 'file' kernel-native module. "
            f"Use a non-conflicting implementation filename like file_impl.py instead."
        )


# ---------------------------------------------------------------------------
# kernel/ MUST NOT start IBCIEngine or call run_ibci
# ---------------------------------------------------------------------------

class TestKernelLayerRedLine:
    """kernel/ tests must be pure unit tests — no engine, no IBCI code execution."""

    @pytest.mark.parametrize("test_file", _find_test_files("kernel"))
    def test_kernel_does_not_run_ibci(self, test_file):
        src = _read_source(test_file)
        assert "run_ibci(" not in src, (
            f"{test_file.name}: kernel/ layer must not call run_ibci() "
            f"— use pure unit tests on data structures only."
        )
        assert "IBCIEngine(" not in src, (
            f"{test_file.name}: kernel/ layer must not instantiate IBCIEngine "
            f"— use pure unit tests on data structures only."
        )


# ---------------------------------------------------------------------------
# compiler/ MUST NOT call run_ibci (compile-only layer)
# ---------------------------------------------------------------------------

# 已知违规白名单：这些文件混合了编译测试和运行时测试，需要拆分。
# 拆分后应从此列表中移除对应条目。
_COMPILER_KNOWN_RUN_IBCI_VIOLATIONS: frozenset[str] = frozenset({
    "test_generics.py",
    "test_import_position.py",
    "test_type_annotations.py",
})


class TestCompilerLayerRedLine:
    """compiler/ tests must only compile — not execute."""

    @pytest.mark.parametrize("test_file", _find_test_files("compiler"))
    def test_compiler_does_not_run_ibci(self, test_file):
        src = _read_source(test_file)
        if test_file.name in _COMPILER_KNOWN_RUN_IBCI_VIOLATIONS:
            pytest.skip(
                f"{test_file.name}: known mixed-concerns file pending split "
                "(TEST_REFACTOR 拆分任务；拆分完成后须从白名单移除)"
            )
        assert "run_ibci(" not in src, (
            f"{test_file.name}: compiler/ layer must not call run_ibci() "
            f"— move runtime-execution tests to tests/e2e/."
        )


# ---------------------------------------------------------------------------
# e2e/ MUST NOT import core.runtime interpreter internals
# ---------------------------------------------------------------------------

class TestE2ELayerRedLine:
    """e2e/ tests must be black-box — no interpreter/VM internals."""

    BANNED_IMPORTS = [
        "from core.runtime.interpreter.",
        "from core.runtime.vm.",
        "from core.runtime.objects.",
    ]

    # 已知白盒测试（构造期内部状态契约，R2-E5 记录豁免；下沉成本高收益低）。
    #   - test_e2e_engine_lifecycle.py：验证 engine 构造期 _explicit_root/_cwd 契约
    #   - test_e2e_multi_interpreter.py：验证 spawn 任务表内部状态
    PRIVATE_ACCESS_EXEMPT = {
        "test_e2e_engine_lifecycle.py",
        "test_e2e_multi_interpreter.py",
    }

    @pytest.mark.parametrize("test_file", _find_test_files("e2e"))
    def test_e2e_does_not_import_runtime_internals(self, test_file):
        src = _read_source(test_file)
        for pattern in self.BANNED_IMPORTS:
            assert pattern not in src, (
                f"{test_file.name}: e2e/ layer must not import '{pattern}' "
                f"— these are interpreter/VM internals. "
                f"Move the test to tests/runtime/ if it needs internals access."
            )

    @pytest.mark.parametrize("test_file", _find_test_files("e2e"))
    def test_e2e_does_not_access_private_attributes(self, test_file):
        """e2e/ 黑盒红线：禁止私有属性穿透（``obj._attr``）。

        R2-E5：此前红线只查 import，`eng.interpreter.service_context.llm_executor
        ._pending_futures` 这类属性链穿透检测不到。允许豁免名单内的构造期白盒测试。
        """
        if test_file.name in self.PRIVATE_ACCESS_EXEMPT:
            pytest.skip(f"known white-box test (R2-E5 exempt): {test_file.name}")
        src = _read_source(test_file)
        # 数据结构字段白名单（序列化/诊断码访问，非穿透）
        DATA_FIELDS = ("._type", "._name", "._data", "._value", "._lock", "._error")
        violations = []
        for m in re.finditer(r"\.(_[a-z]\w*)", src):
            attr = "." + m.group(1)
            # 排除 self._xxx（方法调用/内部实现）与数据结构字段
            if attr in DATA_FIELDS:
                continue
            if "self." + m.group(1) in src[m.start() - 5:m.start() + 1]:
                continue
            line = src.count("\n", 0, m.start()) + 1
            violations.append(f"{test_file.name}:{line}: private attr {attr}")
        assert not violations, (
            "e2e/ layer must not access private attributes (black-box):\n"
            + "\n".join(violations)
            + "\nMove white-box assertions to tests/runtime/."
        )


# ---------------------------------------------------------------------------
# compliance/ MUST NOT import core.runtime internals
# ---------------------------------------------------------------------------

class TestComplianceLayerRedLine:
    """compliance/ tests must be black-box — public API only."""

    BANNED_IMPORTS = [
        "from core.runtime.interpreter.",
        "from core.runtime.vm.",
        "from core.runtime.objects.",
    ]

    @pytest.mark.parametrize("test_file", _find_test_files("compliance"))
    def test_compliance_does_not_import_runtime_internals(self, test_file):
        src = _read_source(test_file)
        for pattern in self.BANNED_IMPORTS:
            assert pattern not in src, (
                f"{test_file.name}: compliance/ layer must not import '{pattern}' "
                f"— compliance tests verify public API conformance only."
            )
