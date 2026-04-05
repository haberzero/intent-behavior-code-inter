"""
File 文件操作插件核心实现
合并了基础文件操作和高级文件分析功能

使用 IBCI Path 模块进行路径管理，与 Python 解耦。
"""
import os
import re
from typing import List, Dict, Any
from core.runtime.path import IbPath, PathResolver


class FileLib:
    """
    File 插件核心类 (v2.4.0)
    合并基础文件操作和高级文件分析功能：
    - 基础操作: read, write, exists, remove
    - 高级分析: search_in_files, list_files_recursive, get_line_count, read_lines_range, get_file_size, find_todos

    使用 IBCI PathResolver 进行路径管理。
    """
    def setup(self, capabilities):
        """插件入口点，支持上下文感知设置"""
        self.capabilities = capabilities
        self.permission_manager = capabilities.service_context.permission_manager

        script_dir = capabilities.stack_inspector.get_current_script_dir()
        script_dir_ib = IbPath.from_native(script_dir) if script_dir else None

        project_root_ib = IbPath.from_native(
            capabilities.service_context.permission_manager.root_dir
        )

        self._path_resolver = PathResolver(project_root_ib, script_dir_ib)

    def _resolve_path(self, path: str) -> str:
        """
        核心路径解析逻辑（使用 IBCI PathResolver）

        - 绝对路径：直接校验权限并使用。
        - 以 ./ 或 ../ 开头：基于当前 IBCI 脚本所在目录解析。
        - 裸路径：基于项目根目录解析。
        """
        ib_path = self._path_resolver.resolve(path)
        native_path = ib_path.to_native()
        self.permission_manager.validate_path(native_path)
        return native_path

    # === 基础文件操作 ===

    def read(self, path: str) -> str:
        """读取文件内容"""
        res_path = self._resolve_path(path)
        with open(res_path, 'r', encoding='utf-8') as f:
            return f.read()

    def write(self, path: str, content: str) -> None:
        """写入文件内容"""
        res_path = self._resolve_path(path)
        with open(res_path, 'w', encoding='utf-8') as f:
            f.write(content)

    def exists(self, path: str) -> bool:
        """检查文件是否存在"""
        try:
            res_path = self._resolve_path(path)
            return os.path.exists(res_path)
        except:
            return False

    def remove(self, path: str) -> None:
        """删除文件"""
        try:
            res_path = self._resolve_path(path)
            if os.path.exists(res_path):
                os.remove(res_path)
        except:
            pass

    # === 高级文件分析功能 ===

    def search_in_files(self, root_dir: str, pattern: str, extensions: List[str]) -> List[Dict[str, Any]]:
        """
        递归搜索匹配的文件内容。
        参数:
            root_dir: 根目录
            pattern: 正则表达式模式
            extensions: 文件扩展名列表，如 [".py", ".txt"]
        返回:
            匹配结果列表: [{path: str, line: int, content: str}, ...]
        """
        root_path = self._resolve_path(root_dir)
        matches = []

        regex = re.compile(pattern)

        for root, _, files in os.walk(root_path):
            for file in files:
                if any(file.endswith(ext) for ext in extensions):
                    file_path = os.path.join(root, file)
                    try:
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
        """
        递归列出匹配扩展名的文件。
        参数:
            root_dir: 根目录
            extensions: 文件扩展名列表
        返回:
            文件相对路径列表
        """
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
        """
        获取文件总行数。
        参数:
            file_path: 文件路径
        返回:
            行数
        """
        abs_path = self._resolve_path(file_path)
        try:
            with open(abs_path, 'r', encoding='utf-8', errors='ignore') as f:
                return sum(1 for _ in f)
        except (OSError, PermissionError):
            return 0

    def read_lines_range(self, file_path: str, start: int, end: int) -> List[str]:
        """
        按范围读取文件行。
        参数:
            file_path: 文件路径
            start: 起始行号 (1-indexed，包含)
            end: 结束行号 (1-indexed，包含)
        返回:
            行内容列表
        """
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
        """
        获取文件大小（字节）。
        参数:
            file_path: 文件路径
        返回:
            文件大小，失败返回 -1
        """
        abs_path = self._resolve_path(file_path)
        try:
            return os.path.getsize(abs_path)
        except (OSError, PermissionError):
            return -1

    def find_todos(self, root_dir: str) -> List[Dict[str, Any]]:
        """
        查找代码中的 TODO 注释。
        参数:
            root_dir: 根目录
        返回:
            TODO 匹配结果列表
        """
        return self.search_in_files(
            root_dir,
            r"TODO[:\s]",
            [".py", ".ibci", ".c", ".cpp", ".js", ".ts", ".java", ".go", ".rs"]
        )


def create_implementation():
    """插件工厂函数"""
    return FileLib()
