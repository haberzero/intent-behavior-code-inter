"""
tests/meta/test_visitor_naming_consistency.py
=============================================

CI enforcement: AST visitor dispatch naming consistency.

The semantic passes dispatch to handlers via ``getattr(self, f"visit_{cls}")``
(``ScopedVisitor``/``TypeCheckBase``/``SymbolCollectionPass``/``TypeResolutionPass``).
A node-class rename silently falls through to ``generic_visit`` if the handler
isn't renamed too, changing behavior with no error.  This meta-test catches
the stale-handler failure mode: every ``visit_X`` method must correspond to an
existing ``ast.IbASTNode`` subclass named ``X``.

Known counterexample (fixed): ``visit_IbIntentAnnotations`` (plural) never
matched the ``IbIntentAnnotation`` node class, so it silently fell to
``generic_visit``.
"""

import os
import re
from pathlib import Path

import core.kernel.ast as ast


def _collect_ast_node_classes():
    """Return the set of IbASTNode subclass names."""
    names = set()
    for name, cls in vars(ast).items():
        if isinstance(cls, type) and issubclass(cls, ast.IbASTNode) and cls is not ast.IbASTNode:
            names.add(cls.__name__)
    return names


def _collect_visitor_handlers():
    """Scan compiler passes for ``def visit_Ib*`` handler definitions."""
    passes_dir = Path(__file__).parent.parent.parent / "core" / "compiler" / "semantic" / "passes"
    handlers = {}
    for py_file in sorted(passes_dir.glob("*.py")):
        text = py_file.read_text(encoding="utf-8")
        for m in re.finditer(r"^\s*def\s+(visit_Ib\w+)\s*\(", text, re.MULTILINE):
            handlers.setdefault(m.group(1), []).append(py_file.name)
    return handlers


def test_every_visit_handler_matches_an_ast_node_class():
    """Every ``visit_X`` handler must map to an existing IbASTNode subclass X."""
    node_names = _collect_ast_node_classes()
    handlers = _collect_visitor_handlers()

    stale = {
        handler: files
        for handler, files in handlers.items()
        if handler[len("visit_"):] not in node_names
    }

    assert not stale, (
        "\n\nStale visitor handlers (no matching AST node class):\n"
        + "".join(f"  - {h} in {', '.join(fs)}\n" for h, fs in sorted(stale.items()))
        + "\nFix: rename the handler to match the node class, or remove it if it is dead.\n"
    )
