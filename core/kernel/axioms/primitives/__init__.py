"""
core/kernel/axioms/primitives

Concrete axiom implementations for all built-in IBCI types.

Design
------
* Single inheritance from ``BaseAxiom``.  The former multi-inheritance with
  per-capability Protocol classes (``CallCapability``, ``IterCapability``…)
  has been removed — all capability methods now live directly on the
  unified ``TypeAxiom`` interface.
* Each concrete axiom declares the capabilities it implements via
  ``has_*_cap`` class attributes.  ``BaseAxiom`` defaults all of them to
  ``False`` and provides safe no-op defaults for every capability method.
* No imports from ``core.kernel.types`` / ``core.kernel.spec``.  All type
  references in capability methods are plain strings.
* ``get_method_specs()`` returns ``Dict[str, MethodMemberSpec]`` —
  ``MemberSpec`` / ``MethodMemberSpec`` are pure data, no circular risk.
* ``EnumAxiom._enum_index_registry`` is an instance dict (eliminating the
  cross-engine global-state bug).

This package is a mechanical decomposition of the former ``primitives.py``.
Every name that used to live at ``core.kernel.axioms.primitives`` is
re-exported here so existing ``from core.kernel.axioms.primitives import X``
statements keep working unchanged.
"""

from core.kernel.axioms.primitives.base import BaseAxiom, _m
from core.kernel.axioms.primitives.numeric import IntAxiom, FloatAxiom, BoolAxiom
from core.kernel.axioms.primitives.sequences import StrAxiom, ListAxiom, DictAxiom, TupleAxiom
from core.kernel.axioms.primitives.errors import (
    ExceptionAxiom,
    LLMErrorAxiom,
    LLMParseErrorAxiom,
    LLMRetryExhaustedErrorAxiom,
    LLMCallErrorAxiom,
)
from core.kernel.axioms.primitives.sentinels import (
    VoidAxiom,
    DynamicAxiom,
    NoneAxiom,
    OptionalAxiom,
    SliceAxiom,
    LLMUncertainAxiom,
    LlmCallResultAxiom,
)
from core.kernel.axioms.primitives.callable import (
    CallableAxiom,
    FnCallableAxiom,
    BehaviorAxiom,
    BoundMethodAxiom,
)
from core.kernel.axioms.primitives.enum import EnumAxiom
from core.kernel.axioms.primitives.media import AudioAxiom, ImageAxiom, VideoAxiom
from core.kernel.axioms.primitives.file_handle import FileHandleAxiom
from core.kernel.axioms.intent_context import IntentContextAxiom
from core.kernel.axioms.intent import IntentAxiom
from core.kernel.axioms.primitives.registry import register_core_axioms

__all__ = [
    # base
    "BaseAxiom",
    "_m",
    # numeric
    "IntAxiom",
    "FloatAxiom",
    "BoolAxiom",
    # sequences
    "StrAxiom",
    "ListAxiom",
    "DictAxiom",
    "TupleAxiom",
    # errors
    "ExceptionAxiom",
    "LLMErrorAxiom",
    "LLMParseErrorAxiom",
    "LLMRetryExhaustedErrorAxiom",
    "LLMCallErrorAxiom",
    # sentinels
    "VoidAxiom",
    "DynamicAxiom",
    "NoneAxiom",
    "OptionalAxiom",
    "SliceAxiom",
    "LLMUncertainAxiom",
    "LlmCallResultAxiom",
    # callable
    "CallableAxiom",
    "FnCallableAxiom",
    "BehaviorAxiom",
    "BoundMethodAxiom",
    # enum
    "EnumAxiom",
    # media (multimodal)
    "AudioAxiom",
    "ImageAxiom",
    "VideoAxiom",
    # file handle
    "FileHandleAxiom",
    # imported axioms (re-exported for backward compatibility)
    "IntentContextAxiom",
    "IntentAxiom",
    # registry
    "register_core_axioms",
]
