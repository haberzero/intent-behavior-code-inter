"""
IBC-Inter Extension SDK

推荐导入方式：
    from core.extension import ibcext

直接导入：
    from core.extension.ibcext import IbPlugin
    from core.base.llm_protocol import LLMProvider
"""

from core.extension.ibcext import (
    IbPlugin,
    ExtensionCapabilities,
    PluginCapabilities,
)
from core.extension.exceptions import PluginError, CompilerError
from core.extension.capabilities import (
    PluginCapabilities,
    ExtensionCapabilities,
)
from core.kernel.issue import InterpreterError

__all__ = [
    "IbPlugin",
    "PluginError",
    "InterpreterError",
    "CompilerError",
    "ExtensionCapabilities",
    "PluginCapabilities",
]
