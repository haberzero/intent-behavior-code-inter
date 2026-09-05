"""``config_normalize`` —— 配置归一基元（kernel-free 叶子）。

把 api_config.json 的**推荐 schema 归一**（``defaults`` / ``default_model`` /
``models`` → 供应商无关 :class:`LLMConnectionConfig`）与 provider 运行默认值
（timeout / retry / auto_intent_injection）收拢为**无 kernel 依赖的叶子模块**，
供三侧共用（单一权威源）：

- :class:`ibci_modules.ibci_ai.core.AIPlugin` 的 ``load_config`` /
  ``load_project_config``（经 :class:`ProjectApiConfigAdapter` 读取文件后应用）；
- 推荐 provider（``ibci_modules.ibci_ai.provider_impl``）的 ``apply_config``
  归一用户传入的旧式 dict（vtable ``apply_config`` 契约）；
- :class:`ibci_modules.ibci_ai.config_loader.ApiConfig` 的默认值校验回退。

本模块**只**依赖 ``core.base.llm_protocol.config``（最底层契约），不触碰
kernel / runtime / extension——保证推荐 provider 保持 kernel-free 可整文件替换。
"""

from __future__ import annotations

from typing import Dict

from core.base.llm_protocol.config import (
    LLMConnectionConfig,
    ModelSpec,
    CallDefaults,
)

# Provider / api_config schema 共用的运行默认值（单一权威源；config_loader 的
# schema 级默认校验与 provider 运行时默认均引用此处，避免双写真相）
_DEFAULT_TIMEOUT = 30.0
_DEFAULT_RETRY = 3
_DEFAULT_AUTO_INTENT = True


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
            max_tokens=m.get("max_tokens"),
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
            max_tokens=dm.get("max_tokens"),
        ),
        models=models,
        defaults=CallDefaults(
            retry=default_retry,
            timeout=default_timeout,
            auto_intent_injection=default_auto_intent,
        ),
    )