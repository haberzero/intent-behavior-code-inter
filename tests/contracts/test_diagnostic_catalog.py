"""
tests/contracts/test_diagnostic_catalog.py
===========================================

Contract tests for the diagnostic code catalog.

Validates:
- CAT-1: Every code registered in codes.py has a catalog entry (no drift)
- CAT-2: No orphan catalog entries (every key is a real code)
- CAT-3: Catalog entries are non-empty / well-formed (title + fix)
- CAT-4: Formatter renders the friendly explanation for known codes
- CAT-5: Formatter fails open (no crash) for unknown codes
- CAT-6: The human reference doc (15_diagnostics.md) code set == catalog code set
- CAT-7: Every catalog code has a real production emission/use site (杜绝幽灵码)
"""

import os
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


class TestDocParity:
    """CAT-6：人类参考文档（15_diagnostics.md）码集合 == 目录码集合。"""

    DOC_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "docs", "syntax", "15_diagnostics.md",
    )

    def test_doc_code_set_matches_catalog(self):
        with open(self.DOC_PATH, encoding="utf-8") as f:
            src = f.read()
        doc_codes = set(re.findall(r"^#{1,6} `([A-Z][A-Z0-9_]*)`", src, re.M))
        catalog_codes = set(CODE_CATALOG)
        # 新增码登记目录后必须同步文档节；文档孤儿码必须从文档移除。
        assert doc_codes == catalog_codes, (
            f"doc/catalog code set drift: "
            f"in-catalog-not-in-doc={sorted(catalog_codes - doc_codes)}, "
            f"in-doc-not-in-catalog={sorted(doc_codes - catalog_codes)}"
        )


class TestEmitAbility:
    """CAT-7：每个目录码都有真实的生产发射/使用点（杜绝幽灵码）。

    幽灵码 = 仅在 codes.py/catalog.py 定义、生产代码（core/ / ibci_modules/）
    零引用的诊断码。这类码让用户看到文档却永远无法触发，属死契约。

    检查方式：在 core/ 与 ibci_modules/ 下扫描每个码常量名（排除定义文件
    codes.py 与目录 catalog.py，排除 __init__ 再导出）。至少一个生产文件
    引用即通过。
    """

    _PROD_ROOTS = ("core", "ibci_modules")
    _EXCLUDED_FILES = ("codes.py", "catalog.py", "__init__.py")

    @staticmethod
    def _prod_files():
        """生产目录下所有 .py 文件（排除定义/目录/包再导出文件）。"""
        import os

        repo = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        for root in TestEmitAbility._PROD_ROOTS:
            base = os.path.join(repo, root)
            for dirpath, _, files in os.walk(base):
                for fn in files:
                    if not fn.endswith(".py"):
                        continue
                    if fn in TestEmitAbility._EXCLUDED_FILES:
                        continue
                    yield os.path.join(dirpath, fn)

    def test_every_catalog_code_has_production_emission_site(self):
        import os

        # 收集每个码的生产引用文件
        prod_sources = {}
        for p in self._prod_files():
            try:
                src = open(p, encoding="utf-8").read()
            except OSError:
                continue
            for name in _all_code_names():
                if re.search(rf"\b{name}\b", src):
                    prod_sources.setdefault(name, []).append(p)

        orphan_codes = sorted(
            name for name in _all_code_names() if name not in prod_sources
        )
        assert not orphan_codes, (
            f"幽灵诊断码（生产代码零引用）: {orphan_codes}. "
            f"每个目录码必须有真实发射/使用点；无发射点的码应从 codes.py/catalog.py/文档删除。"
        )
