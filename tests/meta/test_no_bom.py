"""
tests/meta/test_no_bom.py
=========================

CI enforcement: No source/test file may carry a UTF-8 BOM.

A leading U+FEFF (UTF-8 BOM) silently breaks `ast.parse(utf-8)` (syntax
error `invalid non-printable character U+FEFF`) and defeats start-of-line
pattern scans. All tracked `.py` files must be plain UTF-8 without BOM.
"""
from pathlib import Path


def _iter_py_files():
    for path in REPO_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts or ".git" in path.parts:
            continue
        yield path


def test_no_source_file_has_bom():
    bom_files = []
    for path in _iter_py_files():
        with open(path, "rb") as fh:
            if fh.read(3) == b"\xef\xbb\xbf":
                bom_files.append(path)
    assert not bom_files, (
        f"Files must not carry a UTF-8 BOM (breaks ast.parse + meta scans): "
        f"{[str(p) for p in bom_files]}"
    )


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
