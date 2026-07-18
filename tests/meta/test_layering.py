"""
tests/meta/test_layering.py
===========================

CI enforcement: Prevent test-layering red-line violations.

The test suite is organized into layers with explicit boundaries
(see tests/README.md §"分层红线"):

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
                f"(see PENDING_TASKS §八 PT-TEST-2)"
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

    @pytest.mark.parametrize("test_file", _find_test_files("e2e"))
    def test_e2e_does_not_import_runtime_internals(self, test_file):
        src = _read_source(test_file)
        for pattern in self.BANNED_IMPORTS:
            assert pattern not in src, (
                f"{test_file.name}: e2e/ layer must not import '{pattern}' "
                f"— these are interpreter/VM internals. "
                f"Move the test to tests/runtime/ if it needs internals access."
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
