"""
core/kernel/spec/__init__.py

Public API for the spec layer.
"""

from .base import IbSpec
from .member import MemberSpec, MethodMemberSpec
from .specs import (
    FuncSpec,
    ClassSpec,
    ListSpec,
    TupleSpec,
    DictSpec,
    DeferredSpec,
    BoundMethodSpec,
    ModuleSpec,
    CallableSigSpec,
    LazySpec,
    # Built-in prototype constants
    INT_SPEC,
    FLOAT_SPEC,
    STR_SPEC,
    BOOL_SPEC,
    VOID_SPEC,
    ANY_SPEC,
    AUTO_SPEC,
    NONE_SPEC,
    SLICE_SPEC,
    CALLABLE_SPEC,
    BEHAVIOR_SPEC,
    DEFERRED_SPEC,
    EXCEPTION_SPEC,
    BOUND_METHOD_SPEC,
    LIST_SPEC,
    TUPLE_SPEC,
    DICT_SPEC,
    MODULE_SPEC,
    ENUM_SPEC,
    LLM_CALL_RESULT_SPEC,
    LLM_ERROR_SPEC,
    LLM_PARSE_ERROR_SPEC,
    LLM_RETRY_EXHAUSTED_ERROR_SPEC,
    LLM_CALL_ERROR_SPEC,
)
from .registry import SpecRegistry, SpecFactory, create_default_spec_registry

__all__ = [
    # Base
    "IbSpec",
    # Member specs
    "MemberSpec",
    "MethodMemberSpec",
    # Concrete spec kinds
    "FuncSpec",
    "ClassSpec",
    "ListSpec",
    "TupleSpec",
    "DictSpec",
    "DeferredSpec",
    "BoundMethodSpec",
    "ModuleSpec",
    "CallableSigSpec",
    "LazySpec",
    # Built-in constants
    "INT_SPEC",
    "FLOAT_SPEC",
    "STR_SPEC",
    "BOOL_SPEC",
    "VOID_SPEC",
    "ANY_SPEC",
    "AUTO_SPEC",
    "NONE_SPEC",
    "SLICE_SPEC",
    "CALLABLE_SPEC",
    "BEHAVIOR_SPEC",
    "DEFERRED_SPEC",
    "EXCEPTION_SPEC",
    "BOUND_METHOD_SPEC",
    "LIST_SPEC",
    "TUPLE_SPEC",
    "DICT_SPEC",
    "MODULE_SPEC",
    "ENUM_SPEC",
    "LLM_CALL_RESULT_SPEC",
    "LLM_ERROR_SPEC",
    "LLM_PARSE_ERROR_SPEC",
    "LLM_RETRY_EXHAUSTED_ERROR_SPEC",
    "LLM_CALL_ERROR_SPEC",
    # Registry / factory
    "SpecRegistry",
    "SpecFactory",
    "create_default_spec_registry",
]
