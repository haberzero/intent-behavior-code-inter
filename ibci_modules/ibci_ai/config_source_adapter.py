"""``ProjectApiConfigAdapter`` —— 默认 api_config.json 配置源适配器（推荐格式）。

实现 :class:`ConfigSourceAdapter`（见 ``core.base.llm_protocol.config``），把
``api_config.json``（推荐 schema：``defaults`` / ``providers`` / ``models`` /
``default_model``）读取并解析为供应商无关的 :class:`LLMConnectionConfig`。

**配置文件发现**：自 ``project_root`` 向上寻找最近的 ``api_config.json``（最近者
胜，支持子目录就近覆盖），搜索上界为含 ``.git`` 标记的仓库根目录——防止拾取仓库
之外的无关配置；无 ``.git`` 的部署环境退化为文件系统根。仓库根单源放置即可服务
全部子目录（trial 体系以此收敛配置单点真理），子目录配置仅在需要差异化时放置。

该适配器是**推荐实现**：它是 IBCI 内置的默认 api_config.json 用法；用户若想用
自己的书写格式 / 字段名 / 环境变量解析规则，可自写 :class:`ConfigSourceAdapter`
实现并替换（内核 / 语言层不感知具体文件 schema）。具体文件读取 / 校验 / env 引用
解析委托给 :mod:`ibci_modules.ibci_ai.config_loader.ApiConfig`（既有校验器）。
"""

from __future__ import annotations

import os
from typing import Dict, Optional

from core.base.llm_protocol.config import (
    ConfigSourceAdapter,
    LLMConnectionConfig,
)
from ibci_modules.ibci_ai.config_loader import ApiConfig
from ibci_modules.ibci_ai.config_normalize import to_llm_config

_CONFIG_FILENAME = "api_config.json"
_REPO_MARKER = ".git"


def discover_config_path(project_root: str) -> Optional[str]:
    """自 ``project_root`` 向上寻找最近的 ``api_config.json``，返回绝对路径或 None。

    就近覆盖：最近祖先的配置胜出；搜索上界 = 含 ``.git`` 的仓库根目录（该目录
    自身仍参与匹配），不拾取仓库之外的配置。未找到返回 None（调用方按"无配置"
    契约处理，如 ``load_project_config`` no-op）。
    """
    directory = os.path.abspath(project_root)
    while True:
        candidate = os.path.join(directory, _CONFIG_FILENAME)
        if os.path.isfile(candidate):
            return candidate
        if os.path.exists(os.path.join(directory, _REPO_MARKER)):
            return None
        parent = os.path.dirname(directory)
        if parent == directory:
            return None
        directory = parent


class ProjectApiConfigAdapter(ConfigSourceAdapter):
    """``api_config.json`` 的推荐适配器（向上发现 + 读文件 → LLMConnectionConfig）。"""

    def can_load(self, project_root: Optional[str]) -> bool:
        if not project_root:
            return False
        return discover_config_path(project_root) is not None

    def load(self, project_root: Optional[str]) -> LLMConnectionConfig:
        """发现并解析最近的 ``api_config.json``，返回逻辑配置。"""
        path = self._require_config_path(project_root)
        validated = ApiConfig.load(path)
        return to_llm_config(validated)

    def load_raw_dict(self, project_root: Optional[str]) -> Dict:
        """读取并解析文件为结构化 dict（含 ``defaults`` 等 provider 专属字段）。

        默认 adapter 额外暴露文件原始语义（如 ``defaults.mock`` 测试模式），
        供 provider 应用非逻辑层配置。
        """
        path = self._require_config_path(project_root)
        return ApiConfig.load(path)

    @staticmethod
    def _require_config_path(project_root: Optional[str]) -> str:
        if not project_root:
            raise ValueError("project_root 未确立")
        path = discover_config_path(project_root)
        if path is None:
            raise ValueError(
                f"api_config.json 未找到（自 {project_root} 向上至仓库边界）；"
                "load 前应先经 can_load 判定"
            )
        return path
