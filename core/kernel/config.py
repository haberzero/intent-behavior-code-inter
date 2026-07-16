"""
IBCI 项目配置（ibci.json）加载 —— ADR-019 §6。

位置：``<project_root>/ibci.json``（与 ``api_config.json`` 同目录，**不合并**——后者含敏感信息）。

字段：
  - ``plugin_paths``：显式插件搜索路径（数组）。配置后嗅探不触发（explicit > implicit）。
  - ``global_plugin``：全局插件（数组）。高于普通 plugin_paths，不被覆盖；
    项目未定义则查全局 ibci.json（**本轮预留，不实现**）。

路径规范化：相对路径锚定 project_root（ibci.json 所在），统一走 ``canonicalize_for_security``。
未来可承载更多非敏感项目配置。
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from core.kernel.path import IbPath, PathValidator


class IbciConfig:
    """``ibci.json`` 项目配置加载器（ADR-019 §6）。"""

    CONFIG_FILENAME = "ibci.json"

    @classmethod
    def load(cls, project_root: str) -> Dict[str, Any]:
        """加载 ``<project_root>/ibci.json``；不存在或解析失败返回空 dict。

        参数:
            project_root: 项目根目录（ibci.json 所在）。
        """
        path = os.path.join(project_root, cls.CONFIG_FILENAME)
        if not os.path.isfile(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            return {}

    @classmethod
    def plugin_paths(cls, config: Dict[str, Any], project_root: str) -> List[str]:
        """提取并规范化 ``plugin_paths``（相对路径锚定 project_root，canonicalize）。"""
        return cls._extract_path_list(config, "plugin_paths", project_root)

    @classmethod
    def global_plugin(cls, config: Dict[str, Any], project_root: str) -> List[str]:
        """提取并规范化 ``global_plugin``（相对路径锚定 project_root，canonicalize）。"""
        return cls._extract_path_list(config, "global_plugin", project_root)

    @classmethod
    def _extract_path_list(cls, config: Dict[str, Any], key: str, project_root: str) -> List[str]:
        raw = config.get(key, [])
        if not isinstance(raw, list):
            return []
        return [cls._resolve_path(p, project_root) for p in raw if isinstance(p, str) and p]

    @staticmethod
    def _resolve_path(raw: str, project_root: str) -> str:
        """规范化：绝对路径直接 canonicalize；相对路径先锚定 project_root 再 canonicalize。"""
        ib = IbPath.from_native(raw)
        if not ib.is_absolute:
            ib = IbPath.from_native(project_root) / raw
        return PathValidator.canonicalize_for_security(ib.to_native()).to_native()
