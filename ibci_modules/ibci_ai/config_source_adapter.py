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
    ModelSpec,
    CallDefaults,
)
from ibci_modules.ibci_ai.config_loader import (
    ApiConfig,
    _DEFAULT_RETRY,
    _DEFAULT_TIMEOUT,
    _DEFAULT_AUTO_INTENT,
)

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
        return self.to_llm_config(validated)

    def load_raw_dict(self, project_root: Optional[str]) -> Dict:
        """读取并解析文件为结构化 dict（含 ``defaults`` 等 provider 专属字段）。

        默认 adapter 额外暴露文件原始语义（如 ``defaults.mock`` 测试模式），
        供 provider 应用非逻辑层配置。
        """
        if not project_root:
            raise ValueError("project_root 未确立")
        path = os.path.join(project_root, _CONFIG_FILENAME)
        return ApiConfig.load(path)

    @staticmethod
    def to_llm_config(validated: dict) -> LLMConnectionConfig:
        """把 api_config.json 结构 (``defaults`` / ``default_model`` / ``models``)
        转为逻辑 :class:`LLMConnectionConfig`（推荐格式映射）。

        兼容两种输入：``ApiConfig.validate`` 的完整结构化输出，或测试/调用方传入的
        部分 dict（缺失字段用默认值）。用户自定义适配器可完全另写自己的映射。

        ``default_model`` 可能为命名模型引用字符串（``defaults`` 分支）或含连接
        信息的对象——此处兼容两者（对象路径按旧 schema 解析连接字段）。
        """
        defaults = validated.get("defaults", {}) or {}
        default_retry = defaults.get("retry", _DEFAULT_RETRY)
        default_timeout = defaults.get("timeout", _DEFAULT_TIMEOUT)
        default_auto_intent = defaults.get("auto_intent_injection", _DEFAULT_AUTO_INTENT)

        dm_raw = validated.get("default_model", {})
        if isinstance(dm_raw, str):
            # 命名模型引用：从 models 解析连接信息
            models_raw = validated.get("models", {}) or {}
            dm_raw = models_raw.get(dm_raw, {"model": dm_raw})

        def _thinking(v):
            return "on" if v is True else ("off" if v is False else "auto")

        models: Dict[str, ModelSpec] = {}
        for name, m in (validated.get("models", {}) or {}).items():
            if isinstance(m, str):
                m = {"model": m}
            models[name] = ModelSpec(
                provider="openai",
                model_id=m.get("model", name),
                endpoint=m.get("base_url"),
                auth=m.get("api_key"),
                timeout=m.get("timeout"),
                thinking_mode=_thinking(m.get("reasoning")),
            )
        dm = dm_raw
        return LLMConnectionConfig(
            default_model=ModelSpec(
                provider="openai",
                model_id=dm.get("model", "default"),
                endpoint=dm.get("base_url"),
                auth=dm.get("api_key"),
                timeout=dm.get("timeout", default_timeout),
                thinking_mode=_thinking(dm.get("reasoning")),
            ),
            models=models,
            defaults=CallDefaults(
                retry=default_retry,
                timeout=default_timeout,
                auto_intent_injection=default_auto_intent,
            ),
        )
