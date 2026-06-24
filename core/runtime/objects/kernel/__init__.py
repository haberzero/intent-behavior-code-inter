"""
``core.runtime.objects.kernel`` — IBC-Inter runtime kernel object hierarchy.

This package is a pure mechanical split of the former monolithic
``kernel.py`` module.  Importing this package imports every submodule so
that all ``@register_ib_type`` decorators fire, and re-exports the full
public surface (plus the private helpers and transitive re-exports that
external modules depend on).
"""

from .base import IbObject, IbValue
from ._helpers import (
    _is_intent_context_param,
    _should_activate_intent_context_arg,
    CoreModule,
    DebugLevel,
    core_debugger,
)
from .functions import IbFunction, IbNativeFunction, IbBoundMethod, IbSuperProxy
from .native_module import IbNativeObject, IbModule
from .ib_class import IbClassField, IbClass
from .sentinels import IbNone, IbLLMUncertain, IbLLMCallResult
from .user_functions import IbUserFunction, IbLLMFunction

__all__ = [
    "IbObject",
    "IbValue",
    "IbNativeObject",
    "IbModule",
    "IbClassField",
    "IbClass",
    "IbFunction",
    "IbNativeFunction",
    "IbBoundMethod",
    "IbSuperProxy",
    "IbNone",
    "IbLLMUncertain",
    "IbLLMCallResult",
    "IbUserFunction",
    "IbLLMFunction",
    "_is_intent_context_param",
    "_should_activate_intent_context_arg",
    "CoreModule",
    "DebugLevel",
    "core_debugger",
]
