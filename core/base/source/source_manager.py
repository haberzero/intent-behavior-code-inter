from typing import Dict, List, Optional
from core.base.path import IbPath


def _canonical(file_path: str) -> str:
    """统一的源码路径键化（经 IbPath 规范化，消除散点 os.path.abspath 的 CWD 锚定）。"""
    return IbPath.from_native(file_path).resolve_dot_segments().to_native()


class SourceManager:
    """
    Centralized repository for source code content.
    Allows decoupling error reporting from the compilation phase.
    """
    def __init__(self):
        # Key: Canonical file path, Value: List of source lines
        self._sources: Dict[str, List[str]] = {}

    def add_source(self, file_path: str, content: str):
        """Register source code for a file."""
        abs_path = _canonical(file_path)
        self._sources[abs_path] = content.splitlines()

    def get_line(self, file_path: str, lineno: int) -> Optional[str]:
        """
        Get a specific line from a file (1-based index).
        Returns None if file not found or line out of range.
        """
        abs_path = _canonical(file_path)
        lines = self._sources.get(abs_path)

        if not lines:
            return None

        # lineno is 1-based
        if 1 <= lineno <= len(lines):
            return lines[lineno - 1]

        return None

    def get_full_source(self, file_path: str) -> Optional[str]:
        """Get the full source content of a file."""
        abs_path = _canonical(file_path)
        lines = self._sources.get(abs_path)
        if lines is None:
            return None
        return "\n".join(lines)

    def get_context(self, file_path: str, lineno: int, context_lines: int = 0) -> List[str]:
        """
        Get lines around the target line.
        """
        abs_path = _canonical(file_path)
        lines = self._sources.get(abs_path)

        if not lines:
            return []

        start = max(1, lineno - context_lines)
        end = min(len(lines), lineno + context_lines)

        result = []
        for i in range(start, end + 1):
            result.append(lines[i-1])

        return result
