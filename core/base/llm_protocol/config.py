"""``core.base.llm_protocol.config`` —— 供应商无关的 LLM 连接配置契约。

api_config.json 的**书写格式**不是内核的契约：本模块只定义内核/插件共同消费的
**逻辑配置形态**（:class:`ModelSpec` / :class:`LLMConnectionConfig`），以及一个
可插拔的**配置源适配器**（:class:`ConfigSourceAdapter`）。

- 系统提供一个"推荐格式"的默认适配器（可把当前 main-line 的
  ``defaults/providers/models/default_model`` schema 作为推荐实现）；
- 用户若想用自己的格式 / 字段名 / 环境变量解析规则，可自写一个
  ：class:`ConfigSourceAdapter` 实现来替换——内核不感知具体文件 schema。

本模块只定义抽象与纯数据结构，不读文件、不解析、无副作用（具体读取在实现方）。
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Dict, Optional


#: 思考模式：与 :mod:`core.base.llm_protocol.llm_call` 一致，供应商无关。
THINKING_AUTO = "auto"
THINKING_ON = "on"
THINKING_OFF = "off"


@dataclass(frozen=True)
class ModelSpec:
    """命名模型 / 默认模型的逻辑描述（供应商无关）。

    - ``provider``：供应商标识名（映射到具体调用服务实现）。
    - ``model_id``：模型标识（供应商侧的模型名 / 端点资源名）。
    - ``endpoint``：HTTP 端点（可选；由 provider 决定是否使用）。
    - ``auth``：认证凭据（可选，如 API key；敏感信息）。
    - ``timeout``：超时秒数（可选）。
    - ``thinking_mode``：该模型的思考模式偏好（自动跟随负载默认或显式指定）。
    - ``max_tokens``：单次生成上限（可选；provider 内置默认兜底）。
    """

    provider: str
    model_id: str
    endpoint: Optional[str] = None
    auth: Optional[str] = None
    timeout: Optional[float] = None
    thinking_mode: str = THINKING_AUTO
    max_tokens: Optional[int] = None


@dataclass(frozen=True)
class CallDefaults:
    """全局调用默认值（供应商无关逻辑层）。"""

    retry: int = 3
    timeout: float = 30.0
    auto_intent_injection: bool = True
    thinking_mode: str = THINKING_AUTO


@dataclass(frozen=True)
class LLMConnectionConfig:
    """适配器产出的完整逻辑配置（内核/插件共同消费，不绑定文件 schema）。"""

    #: 默认模型（调用未指定 @NAME~ 时使用）。
    default_model: ModelSpec
    #: 命名模型注册表（@NAME~ 路由）。
    models: Dict[str, ModelSpec] = field(default_factory=dict)
    #: embedding 命名模型注册表（api_config ``kind: "embedding"`` 条目；
    #: 无默认模型概念——embedding 调用显式选模型）。
    embedding_models: Dict[str, ModelSpec] = field(default_factory=dict)
    #: 全局默认值。
    defaults: CallDefaults = field(default_factory=CallDefaults)


class ConfigSourceAdapter(abc.ABC):
    """可插拔的配置源适配器（api_config.json 等配置来源的读取/解析抽象）。

    实现方负责：从配置来源（通常是项目根目录的某个文件）读取原始配置，按
    自身 schema 校验/解析/env 展开，产出一个 :class:`LLMConnectionConfig`。

    内核不感知具体文件格式；替换此适配器即可自定义 api_config.json 的写法。
    """

    @abc.abstractmethod
    def can_load(self, project_root: Optional[str]) -> bool:
        """判断给定项目根目录是否存在本适配器可消费的配置源。"""

    @abc.abstractmethod
    def load(self, project_root: Optional[str]) -> LLMConnectionConfig:
        """读取并解析配置源，返回供应商无关的逻辑配置。

        失败应抛带诊断码的可定位错误（fail-fast），不静默回退默认。
        """
