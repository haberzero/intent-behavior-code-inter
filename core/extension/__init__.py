"""
[IES 2.1 SDK] IBC-Inter Extension SDK

推荐导入方式：
    from core.extension import ibcext
    from core.extension import SpecBuilder

或直接导入：
    from core.extension.ibcext import IbPlugin, method, PluginError
    from core.base.interfaces import ILLMProvider
    from core.extension.spec_builder import SpecBuilder
"""

from core.extension.ibcext import (
    IbPlugin,
    method,
    module,
    PluginError,
    InterpreterError,
    CompilerError,
    ExtensionCapabilities,
    PluginCapabilities,
)
from core.extension.capabilities import (
    PluginCapabilities,
    ExtensionCapabilities,
)
from core.base.interfaces import ILLMProvider
from core.extension.spec_builder import SpecBuilder, ClassSpecBuilder

__all__ = [
    "IbPlugin",
    "method",
    "module",
    "PluginError",
    "InterpreterError",
    "CompilerError",
    "ExtensionCapabilities",
    "PluginCapabilities",
    "ILLMProvider",
    "SpecBuilder",
    "ClassSpecBuilder",
]
