"""Cross-platform path utilities.

This module provides path helpers that handle edge cases not covered by
``os.path``. In particular, ``safe_relpath`` works around the Windows
``ValueError`` that ``os.path.relpath`` raises when the two paths reside
on different drive letters (e.g. ``C:\\\\temp`` vs ``D:\\\\repo``).
"""

import os


def safe_relpath(path: str, start: str) -> str:
    """Like ``os.path.relpath``, but falls back to the absolute path on
    cross-drive Windows scenarios.

    On Windows, ``os.path.relpath`` raises ``ValueError`` when *path* and
    *start* are on different drive letters.  This is a real-world issue
    when the system ``%TEMP%`` is on ``C:`` while the project repository
    is on ``D:`` (or vice-versa).  In that case the relative path is
    mathematically undefined, so we return the absolute path instead —
    callers that only need a stable string identifier (e.g. module-name
    derivation) continue to work; callers that genuinely need a relative
    path should ensure both inputs share a drive.
    """
    try:
        return os.path.relpath(path, start)
    except ValueError:
        return os.path.abspath(path)
