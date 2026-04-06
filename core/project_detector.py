"""
IBCI 项目根目录自动检测模块

提供智能的项目根目录检测功能：
1. 从入口脚本位置向上查找标志性目录
2. 支持多种项目结构检测
"""
import os
from typing import Optional, Tuple
from pathlib import Path


class ProjectDetector:
    """
    IBCI 项目根目录检测器

    自动检测项目根目录的标志性目录：
    - plugins/ - 插件目录
    - ibci_modules/ - IBCI 模块目录
    - .ibci/ - IBCI 配置目录
    - ibci.lock - IBCI 锁定文件
    """

    SIGNATURE_DIRS = [
        "plugins",
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

        entry_path = os.path.abspath(entry_file)
        entry_dir = os.path.dirname(entry_path)

        return cls._find_project_root(entry_dir)

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

        current_dir = os.path.abspath(start_dir)

        # 向上查找直到根目录
        while True:
            # 检查标志性目录
            for sig_dir in cls.SIGNATURE_DIRS:
                sig_path = os.path.join(current_dir, sig_dir)
                if os.path.isdir(sig_path):
                    return current_dir

            # 检查标志性文件
            for sig_file in cls.SIGNATURE_FILES:
                sig_path = os.path.join(current_dir, sig_file)
                if os.path.isfile(sig_path):
                    return current_dir

            # 到达根目录，停止查找
            parent_dir = os.path.dirname(current_dir)
            if parent_dir == current_dir:
                break

            current_dir = parent_dir

        return None

    @classmethod
    def is_valid_project_root(cls, directory: str) -> bool:
        """
        检查目录是否为有效的 IBCI 项目根目录

        参数:
            directory: 要检查的目录

        返回:
            bool: 是否为有效项目根目录
        """
        if not directory or not os.path.isdir(directory):
            return False

        # 检查是否有标志性目录
        for sig_dir in cls.SIGNATURE_DIRS:
            if os.path.isdir(os.path.join(directory, sig_dir)):
                return True

        # 检查是否有标志性文件
        for sig_file in cls.SIGNATURE_FILES:
            if os.path.isfile(os.path.join(directory, sig_file)):
                return True

        return False

    @classmethod
    def get_plugin_paths(cls, project_root: str) -> list:
        """
        获取项目中的插件搜索路径

        参数:
            project_root: 项目根目录

        返回:
            list: 插件搜索路径列表
        """
        if not project_root:
            return []

        plugin_paths = []

        # 主插件目录
        main_plugins = os.path.join(project_root, "plugins")
        if os.path.isdir(main_plugins):
            plugin_paths.append(main_plugins)

        # IBCI 模块目录
        ibci_modules = os.path.join(project_root, "ibci_modules")
        if os.path.isdir(ibci_modules):
            plugin_paths.append(ibci_modules)

        # .ibci 目录下的插件
        dot_ibci = os.path.join(project_root, ".ibci")
        if os.path.isdir(dot_ibci):
            dot_plugins = os.path.join(dot_ibci, "plugins")
            if os.path.isdir(dot_plugins):
                plugin_paths.append(dot_plugins)

        return plugin_paths

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

        entry_path = os.path.abspath(entry_file)
        entry_dir = os.path.dirname(entry_path)
        project_root = cls.detect_project_root(entry_file)

        if project_root:
            # 检查是否在入口目录找到了标志性目录
            found_signature = False
            for sig_dir in cls.SIGNATURE_DIRS:
                sig_path = os.path.join(entry_dir, sig_dir)
                if os.path.isdir(sig_path):
                    found_signature = True
                    break

            if found_signature:
                # 在入口目录找到了标志性目录
                return f"Project root detected at entry directory: {project_root}"
            elif project_root != entry_dir:
                # 在上级目录找到了标志性目录
                rel_path = os.path.relpath(project_root, entry_dir)
                return f"Detected project root: {project_root} (found signature at {rel_path})"
            else:
                return f"No project root detected. Using entry directory: {project_root}"
        else:
            return f"No project root detected. Using entry directory: {entry_dir}"
