"""``core.base.llm_protocol`` —— LLM 调用层插件化的供应商无关契约包。

把 LLM 组件与内核解耦的核心契约层，位于 ``core/base``（最底层，只出不进）：

- :mod:`core.base.llm_protocol.llm_call`   —— ``LLMCallRequest`` / ``LLMCallResult``
  一次完整 LLM 调用请求/响应的结构化数据契约（不含供应商字段）。
- :mod:`core.base.llm_protocol.config`     —— ``ModelSpec`` / ``LLMConnectionConfig`` /
  ``ConfigSourceAdapter``：api_config.json 逻辑配置形态 + 可插拔配置源适配器。
- :mod:`core.base.llm_protocol.provider`   —— ``LLMProvider``：内核调 LLM 的抽象动作
  协议（供应商无关），实现对供应商细节封装。

设计动机与决策记录见 ``tasks_docs/WORKLOG.md``（LLM 调用层插件化主线）与
``docs/KNOWN_LIMITS.md`` / ``docs/architecture/`` 对应章节。
"""

from core.base.llm_protocol.llm_call import (
    LLMCallRequest,
    LLMCallResult,
    OutputContract,
    IntentBlock,
    PromptSlot,
    ContentValue,
)
from core.base.llm_protocol.config import (
    ModelSpec,
    CallDefaults,
    LLMConnectionConfig,
    ConfigSourceAdapter,
    THINKING_AUTO,
    THINKING_ON,
    THINKING_OFF,
)
from core.base.llm_protocol.provider import LLMProvider

__all__ = [
    # llm_call
    "LLMCallRequest",
    "LLMCallResult",
    "OutputContract",
    "IntentBlock",
    "PromptSlot",
    "ContentValue",
    # config
    "ModelSpec",
    "CallDefaults",
    "LLMConnectionConfig",
    "ConfigSourceAdapter",
    "THINKING_AUTO",
    "THINKING_ON",
    "THINKING_OFF",
    # provider
    "LLMProvider",
]
