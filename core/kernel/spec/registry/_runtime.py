"""
core/kernel/spec/registry/_runtime.py

_RuntimeMixin — axiom-method bootstrapping, value resolution, aggregate
accessors, and the default-registry factory.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, TYPE_CHECKING

from ..base import IbSpec, TypeKind
from ..specs import (
    INT_SPEC, FLOAT_SPEC, STR_SPEC, BOOL_SPEC, VOID_SPEC, ANY_SPEC, AUTO_SPEC, FN_SPEC,
    NONE_SPEC, SLICE_SPEC, CALLABLE_SPEC, BEHAVIOR_SPEC, FN_CALLABLE_SPEC, OPTIONAL_SPEC, EXCEPTION_SPEC,
    BOUND_METHOD_SPEC, LIST_SPEC, TUPLE_SPEC, DICT_SPEC, MODULE_SPEC, ENUM_SPEC,
    LLM_CALL_RESULT_SPEC, LLM_UNCERTAIN_SPEC, INTENT_SPEC, INTENT_CONTEXT_SPEC,
    LLM_ERROR_SPEC, LLM_PARSE_ERROR_SPEC, LLM_RETRY_EXHAUSTED_ERROR_SPEC, LLM_CALL_ERROR_SPEC,
    AUDIO_SPEC, IMAGE_SPEC, VIDEO_SPEC, FILE_HANDLE_SPEC,
)

if TYPE_CHECKING:
    from core.kernel.axioms.registry import AxiomRegistry
    from . import SpecRegistry


class _RuntimeMixin:
    # ---------------------------------------------------------- #
    # Axiom-method bootstrapping                                 #
    # ---------------------------------------------------------- #

    def _bootstrap_axiom_methods(self) -> None:
        """
        After all axioms and primitive specs are registered, populate
        each spec's members dict with the method signatures declared by
        its axiom.  This replaces the old AxiomHydrator.inject_axioms().
        """
        for key, spec in list(self._specs.items()):
            axiom = self.get_axiom(spec)
            if not axiom:
                continue
            method_specs = axiom.get_method_specs()
            for m_name, m_spec in method_specs.items():
                spec.members.setdefault(m_name, m_spec)

    # ---------------------------------------------------------- #
    # Convenience resolution helpers                             #
    # ---------------------------------------------------------- #

    def resolve_from_value(self, value: Any) -> Optional[IbSpec]:
        """Resolve a spec from a Python native value's type."""
        if isinstance(value, bool):
            return self.resolve("bool")
        if isinstance(value, int):
            return self.resolve("int")
        if isinstance(value, float):
            return self.resolve("float")
        if isinstance(value, str):
            # Uncertain 字面量哨兵：Uncertain 关键字被解析为此特殊字符串
            if value == "__IBCI_UNCERTAIN_LITERAL__":
                return self.resolve("llm_uncertain")
            return self.resolve("str")
        if value is None:
            return self.resolve("None")
        return None

    def get_all_modules(self) -> Dict[str, IbSpec]:
        return {k: v for k, v in self._specs.items() if v.kind == TypeKind.MODULE.value}

    def get_all_funcs(self) -> Dict[str, IbSpec]:
        return {k: v for k, v in self._specs.items() if v.kind in (TypeKind.FUNCTION.value, TypeKind.CALLABLE_SIG.value)}

    def get_all_classes(self) -> Dict[str, IbSpec]:
        return {k: v for k, v in self._specs.items() if v.kind == TypeKind.CLASS.value}

    def get_metadata_registry(self) -> "SpecRegistry":
        """Return self. Allows ContractValidator to receive the registry."""
        return self


# ------------------------------------------------------------------ #
# Default registry factory                                            #
# ------------------------------------------------------------------ #

def create_default_spec_registry(axiom_registry: "AxiomRegistry") -> "SpecRegistry":
    """
    Create and populate a SpecRegistry with all built-in primitive specs.
    Replaces the old ``create_default_registry()`` from kernel/factory.py.
    """
    from . import SpecRegistry
    reg = SpecRegistry(axiom_registry)

    # file_handle 必须在 media 之前注册，因为 audio/image/video 继承自它。
    for proto in (
        INT_SPEC, FLOAT_SPEC, STR_SPEC, BOOL_SPEC, VOID_SPEC,
        ANY_SPEC, AUTO_SPEC, FN_SPEC, NONE_SPEC, SLICE_SPEC,
        CALLABLE_SPEC, BEHAVIOR_SPEC, FN_CALLABLE_SPEC, EXCEPTION_SPEC,
        OPTIONAL_SPEC, BOUND_METHOD_SPEC, LIST_SPEC, TUPLE_SPEC, DICT_SPEC, MODULE_SPEC,
        ENUM_SPEC, LLM_CALL_RESULT_SPEC, LLM_UNCERTAIN_SPEC, INTENT_SPEC, INTENT_CONTEXT_SPEC,
        LLM_ERROR_SPEC, LLM_PARSE_ERROR_SPEC, LLM_RETRY_EXHAUSTED_ERROR_SPEC, LLM_CALL_ERROR_SPEC,
        FILE_HANDLE_SPEC, AUDIO_SPEC, IMAGE_SPEC, VIDEO_SPEC,
    ):
        reg.register(proto)

    # Populate method members from axioms
    reg._bootstrap_axiom_methods()

    return reg
