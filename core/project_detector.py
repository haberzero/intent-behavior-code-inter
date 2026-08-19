"""
IBCI 项目根目录自动检测模块

提供智能的项目根目录检测功能：
1. 从入口脚本位置向上查找标志性目录
2. 支持多种项目结构检测

路径语义：
- 本模块内部统一使用 IbPath 进行路径构造/导航；
- 与 Python 文件系统交互（isdir/isfile/abspath）处保留原生字符串边界；
- 对外返回原生绝对路径字符串，与 engine / CLI 调用方兼容。
"""
import os
from typing import Optional

from core.base.path import IbPath
from core.kernel.path import safe_relpath


class ProjectDetector:
    """
    IBCI 项目根目录检测器

    自动检测项目根目录的标志性目录：
    - ibci_modules/ - IBCI 模块目录
    - .ibci/ - IBCI 配置目录
    - ibci.lock - IBCI 锁定文件
    """

    SIGNATURE_DIRS = [
        "ibci_modules",
        ".ibci",
    ]

    SIGNATURE_FILES = [
        "ibci.lock",
        "ibci.json",
        "project.ibci",
    ]

    @classmethod
    def detect_project_root(cls, entry_file: str) -> Optional[str]:
        """
        从入口文件自动检测项目根目录

        算法：
        1. 从入口文件所在目录开始向上查找
        2. 查找标志性目录或文件
        3. 如果找到，则该目录为项目根目录
        4. 如果未找到，返回入口文件所在目录

        参数:
            entry_file: 入口文件路径

        返回:
            Optional[str]: 检测到的项目根目录，未检测到则返回 None
        """
        if not entry_file:
            return None

        entry_path = IbPath.from_native(os.path.abspath(entry_file))
        entry_dir = entry_path.parent
        if entry_dir is None:
            return None

        return cls._find_project_root(entry_dir.to_native())

    @classmethod
    def _find_project_root(cls, start_dir: str) -> Optional[str]:
        """
        从起始目录向上查找项目根目录

        参数:
            start_dir: 起始目录

        返回:
            Optional[str]: 项目根目录，未找到则返回 None
        """
        if not start_dir or not os.path.isdir(start_dir):
            return None

        current = IbPath.from_native(os.path.abspath(start_dir))

        # 向上查找直到根目录
        while True:
            # 检查标志性目录
            for sig_dir in cls.SIGNATURE_DIRS:
                sig_path = (current / sig_dir).to_native()
                if os.path.isdir(sig_path):
                    return current.to_native()

            # 检查标志性文件
            for sig_file in cls.SIGNATURE_FILES:
                sig_path = (current / sig_file).to_native()
                if os.path.isfile(sig_path):
                    return current.to_native()

            # 到达根目录，停止查找
            parent = current.parent
            if parent is None or parent == current:
                break

            current = parent

        return None

    @classmethod
    def describe_detection(cls, entry_file: str) -> str:
        """
        描述项目检测结果的详细信息

        参数:
            entry_file: 入口文件路径

        返回:
            str: 检测结果的描述信息
        """
        if not entry_file:
            return "No entry file provided"

        entry_path = IbPath.from_native(os.path.abspath(entry_file))
        entry_dir_path = entry_path.parent
        if entry_dir_path is None:
            return f"No project root detected. Using entry directory: {entry_path.to_native()}"

        entry_dir = entry_dir_path.to_native()
        project_root = cls.detect_project_root(entry_file)

        if project_root:
            # 检查是否在入口目录找到了标志性目录
            found_signature = False
            entry_dir_ib = IbPath.from_native(entry_dir)
            for sig_dir in cls.SIGNATURE_DIRS:
                sig_path = (entry_dir_ib / sig_dir).to_native()
                if os.path.isdir(sig_path):
                    found_signature = True
                    break

            if found_signature:
                # 在入口目录找到了标志性目录
                return f"Project root detected at entry directory: {project_root}"
            elif project_root != entry_dir:
                # 在上级目录找到了标志性目录
                rel_path = safe_relpath(project_root, entry_dir)
                return f"Detected project root: {project_root} (found signature at {rel_path})"
            else:
                return f"No project root detected. Using entry directory: {project_root}"
        else:
            return f"No project root detected. Using entry directory: {entry_dir}"
