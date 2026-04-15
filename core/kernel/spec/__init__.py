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
    DictSpec,
    BoundMethodSpec,
    ModuleSpec,
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
    EXCEPTION_SPEC,
    BOUND_METHOD_SPEC,
    LIST_SPEC,
    DICT_SPEC,
    MODULE_SPEC,
    ENUM_SPEC,
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
    "DictSpec",
    "BoundMethodSpec",
    "ModuleSpec",
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
    "EXCEPTION_SPEC",
    "BOUND_METHOD_SPEC",
    "LIST_SPEC",
    "DICT_SPEC",
    "MODULE_SPEC",
    "ENUM_SPEC",
    # Registry / factory
    "SpecRegistry",
    "SpecFactory",
    "create_default_spec_registry",
]
