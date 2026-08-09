"""
tests/contracts/test_diagnostic_catalog.py
===========================================

Contract tests for the diagnostic code catalog (PT-FEAT-5).

Validates:
- CAT-1: Every code registered in codes.py has a catalog entry (no drift)
- CAT-2: No orphan catalog entries (every key is a real code)
- CAT-3: Catalog entries are non-empty / well-formed (title + fix)
- CAT-4: Formatter renders the friendly explanation for known codes
- CAT-5: Formatter fails open (no crash) for unknown codes
"""

import re

import pytest

from core.base.diagnostics import codes
from core.base.diagnostics.catalog import CODE_CATALOG, lookup
from core.kernel.issue import Diagnostic
from core.base.source_atomic import Severity
from core.compiler.diagnostics.formatter import DiagnosticFormatter


def _all_code_names() -> set:
    """从 codes.py 提取全部诊断码常量名。"""
    src = open(codes.__file__, encoding="utf-8").read()
    return set(re.findall(r"^([A-Z][A-Z0-9_]*)\s*=\s*\"\1\"", src, re.M))


class TestCatalogCompleteness:
    """目录覆盖完备性。"""

    def test_every_code_has_catalog_entry(self):
        """codes.py 每个码都有目录条目（新增码必须登记，否则契约失败）。"""
        for name in sorted(_all_code_names()):
            value = getattr(codes, name)
            assert value in CODE_CATALOG, (
                f"diagnostic code {name!r} has no catalog entry; "
                f"add it to core/base/diagnostics/catalog.py"
            )

    def test_no_orphan_catalog_entries(self):
        """目录没有孤儿条目（每个键都是真实码）。"""
        known = {getattr(codes, name) for name in _all_code_names()}
        for key in CODE_CATALOG:
            assert key in known, f"catalog entry {key!r} is not a registered code"

    def test_catalog_entries_well_formed(self):
        """条目 title/fix 非空，且是完整中文陈述。"""
        for code, info in CODE_CATALOG.items():
            assert info.title and info.fix, f"catalog entry {code!r} has empty fields"
            assert isinstance(info.title, str) and isinstance(info.fix, str)


class TestFormatterIntegration:
    """Formatter 集成与 fail-open。"""

    def test_known_code_renders_explanation(self):
        d = Diagnostic(
            severity=Severity.ERROR,
            code="SEM_UNDEFINED_SYMBOL",
            message="Undefined symbol 'x'",
            location=None,
        )
        out = DiagnosticFormatter.format(d, use_color=False)
        assert "SEM_UNDEFINED_SYMBOL" in out
        assert "说明:" in out
        assert "修复:" in out
        info = lookup("SEM_UNDEFINED_SYMBOL")
        assert info.title in out and info.fix in out

    def test_unknown_code_fails_open(self):
        d = Diagnostic(
            severity=Severity.ERROR,
            code="SOME_UNREGISTERED_CODE",
            message="raw message",
            location=None,
        )
        out = DiagnosticFormatter.format(d, use_color=False)
        # 未登记码不阻断展示：正文照常输出，不附加说明段
        assert "SOME_UNREGISTERED_CODE" in out
        assert "说明:" not in out
