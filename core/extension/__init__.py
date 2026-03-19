"""
[IES 2.1 SDK] IBC-Inter Extension SDK

推荐导入方式：
    from core.extension import ibcext
    from ibcext import IbPlugin, method, module, PluginError

或直接导入：
    from core.extension.sdk import IbPlugin, method, PluginError
"""

from core.extension.sdk import (
    IbPlugin,
    method,
    module,
    PluginError,
    InterpreterError,
    CompilerError,
    IbObject,
    Location,
    Severity,
    ExtensionCapabilities,
    MethodBinding,
)

__all__ = [
    "IbPlugin",
    "method",
    "module",
    "PluginError",
    "InterpreterError",
    "CompilerError",
    "IbObject",
    "Location",
    "Severity",
    "ExtensionCapabilities",
    "MethodBinding",
]
