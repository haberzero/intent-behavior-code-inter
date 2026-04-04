"""
Third File Analysis Plugin Implementation
Logic for advanced codebase analysis operations.
"""
import os
import re
from typing import List, Dict, Any, Optional

class ThirdFileLib:
    """
    Advanced file analysis library for IBC-Inter.
    Features: recursive search, file listing, line count, and range-based reading.
    """
    def setup(self, capabilities):
        """Plugin entry point for context-aware setup"""
        self.capabilities = capabilities
        self.permission_manager = capabilities.service_context.permission_manager

    def _resolve_path(self, path: str) -> str:
        """Helper to resolve paths with sandbox validation"""
        if os.path.isabs(path):
            self.permission_manager.validate_path(path)
            return os.path.normpath(path)
            
        # 1. Position-Independent Code support
        if path.startswith("./") or path.startswith("../"):
            script_dir = self.capabilities.stack_inspector.get_current_script_dir()
            if script_dir:
                abs_path = os.path.normpath(os.path.join(script_dir, path))
                self.permission_manager.validate_path(abs_path)
                return abs_path
        
        # 2. Backward compatibility (CWD relative)
        abs_path = os.path.normpath(os.path.abspath(path))
        self.permission_manager.validate_path(abs_path)
        return abs_path

    def search_in_files(self, root_dir: str, pattern: str, extensions: List[str]) -> List[Dict[str, Any]]:
        """
        Recursively searches for a pattern in files with given extensions.
        Returns matches: [{path: str, line: int, content: str}]
        """
        root_path = self._resolve_path(root_dir)
        matches = []
        
        # Compile regex for performance
        regex = re.compile(pattern)
        
        for root, _, files in os.walk(root_path):
            for file in files:
                if any(file.endswith(ext) for ext in extensions):
                    file_path = os.path.join(root, file)
                    try:
                        # Validate each file access
                        self.permission_manager.validate_path(file_path)
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                            for i, line in enumerate(f, 1):
                                if regex.search(line):
                                    matches.append({
                                        "path": os.path.relpath(file_path, root_path),
                                        "line": i,
                                        "content": line.strip()
                                    })
                    except (OSError, PermissionError):
                        continue
        return matches

    def list_files_recursive(self, root_dir: str, extensions: List[str]) -> List[str]:
        """Lists all files matching extensions recursively."""
        root_path = self._resolve_path(root_dir)
        result = []
        for root, _, files in os.walk(root_path):
            for file in files:
                if any(file.endswith(ext) for ext in extensions):
                    file_path = os.path.join(root, file)
                    try:
                        self.permission_manager.validate_path(file_path)
                        result.append(os.path.relpath(file_path, root_path))
                    except (OSError, PermissionError):
                        continue
        return result

    def get_line_count(self, file_path: str) -> int:
        """Returns the total number of lines in a file."""
        abs_path = self._resolve_path(file_path)
        try:
            with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                return sum(1 for _ in f)
        except (OSError, PermissionError):
            return 0

    def read_lines_range(self, file_path: str, start: int, end: int) -> List[str]:
        """Reads lines in range [start, end] (1-indexed)."""
        abs_path = self._resolve_path(file_path)
        lines = []
        try:
            with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                for i, line in enumerate(f, 1):
                    if i >= start and i <= end:
                        lines.append(line.rstrip())
                    if i > end:
                        break
        except (OSError, PermissionError):
            pass
        return lines

    def get_file_size(self, file_path: str) -> int:
        """Returns the file size in bytes."""
        abs_path = self._resolve_path(file_path)
        try:
            return os.path.getsize(abs_path)
        except (OSError, PermissionError):
            return -1

    def find_todos(self, root_dir: str) -> List[Dict[str, Any]]:
        """Convenience method to find TODO comments in the codebase."""
        return self.search_in_files(root_dir, r"TODO[:\s]", [".py", ".ibci", ".c", ".cpp", ".js", ".ts"])

def create_implementation():
    """Plugin factory"""
    return ThirdFileLib()
