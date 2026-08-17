"""``ProjectApiConfigAdapter`` —— 默认 api_config.json 配置源适配器（推荐格式）。

实现 :class:`ConfigSourceAdapter`（见 ``core.base.llm_protocol.config``），把
项目根目录的 ``api_config.json``（推荐 schema：``defaults`` / ``providers`` /
``models`` / ``default_model``）读取并解析为供应商无关的
:class:`LLMConnectionConfig`。

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


class ProjectApiConfigAdapter(ConfigSourceAdapter):
    """项目根目录 ``api_config.json`` 的推荐适配器（读文件 → LLMConnectionConfig）。"""

    def can_load(self, project_root: Optional[str]) -> bool:
        if not project_root:
            return False
        return os.path.isfile(os.path.join(project_root, _CONFIG_FILENAME))

    def load(self, project_root: Optional[str]) -> LLMConnectionConfig:
        """读取并解析 ``project_root/api_config.json``，返回逻辑配置。"""
        if not project_root:
            raise ValueError("project_root 未确立")
        path = os.path.join(project_root, _CONFIG_FILENAME)
        validated = ApiConfig.load(path)
        return to_llm_config(validated)

    def load_raw_dict(self, project_root: Optional[str]) -> Dict:
        """读取并解析文件为结构化 dict（含 ``defaults`` 等 provider 专属字段）。

        默认 adapter 额外暴露文件原始语义（如 ``defaults.mock`` 测试模式），
        供 provider 应用非逻辑层配置。
        """
        if not project_root:
            raise ValueError("project_root 未确立")
        path = os.path.join(project_root, _CONFIG_FILENAME)
        return ApiConfig.load(path)
