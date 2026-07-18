"""
core/kernel/axioms/primitives/registry.py

``register_core_axioms`` — instantiates and registers every core axiom
into an :class:`AxiomRegistry`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from core.kernel.axioms.registry import AxiomRegistry


def register_core_axioms(registry: "AxiomRegistry") -> None:
    """Register all core axioms into the given AxiomRegistry."""
    registry.register(IntAxiom())
    registry.register(FloatAxiom())
    registry.register(BoolAxiom())
    registry.register(StrAxiom())
    registry.register(ListAxiom())
    registry.register(TupleAxiom())
    registry.register(DictAxiom())
    registry.register(ExceptionAxiom())
    registry.register(LLMErrorAxiom())
    registry.register(LLMParseErrorAxiom())
    registry.register(LLMRetryExhaustedErrorAxiom())
    registry.register(LLMCallErrorAxiom())
    registry.register(BoundMethodAxiom())
    registry.register(NoneAxiom())
    registry.register(OptionalAxiom())
    registry.register(SliceAxiom())
    registry.register(EnumAxiom())
    # file_handle 必须在 media 之前注册，因为 audio/image/video 继承自它。
    registry.register(FileHandleAxiom())
    registry.register(AudioAxiom())
    registry.register(ImageAxiom())
    registry.register(VideoAxiom())

    registry.register(DynamicAxiom("any"))
    registry.register(DynamicAxiom("auto"))
    registry.register(DynamicAxiom("fn"))
    registry.register(CallableAxiom())
    registry.register(VoidAxiom())
    registry.register(FnCallableAxiom())
    registry.register(BehaviorAxiom())
    registry.register(IntentContextAxiom())
    registry.register(IntentAxiom())
    registry.register(LlmCallResultAxiom())
    registry.register(LLMUncertainAxiom())
