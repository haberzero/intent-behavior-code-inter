"""
core/kernel/spec/generic.py

统一泛型模型（任务 B）——内置泛型类型的正式声明机制。

背景
----
此前 list/dict/tuple/Optional/fn/behavior 等内置泛型类型的创建、特化、
序列化、还原散落在多个 ad-hoc 入口（SpecFactory 的 create_* 方法、
``_assignability.resolve_specialization`` 的函数特判、``TypeRef.from_spec``
的 kind 分派、``artifact_rehydrator`` 的 kind 分派）。这是碎片化。

本模块引入 **GenericTypeDeclaration**（内置泛型类型声明）作为单一权威源：
每个内置泛型类型声明一次，描述其生命周期四操作：
- ``build``    ：创建（经 SpecFactory 从类型实参名构造特化 TypeDef）
- ``to_typeref``：序列化（特化 TypeDef → TypeRef）
- ``restore``  ：还原（经 SpecFactory 从序列化数据重建特化 TypeDef）

设计哲学（design-philosophy）：单一权威源、机制同构、设计语言统一。
"thread[T]" 是本模型的第一个正式消费者。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from .base import TypeKind
from .type_ref import TypeRef

if TYPE_CHECKING:
    from .base import TypeDef
    from .registry.factory import SpecFactory


@dataclass(frozen=True)
class GenericTypeDeclaration:
    """内置泛型类型的正式声明。

    ``name``      : 基础类型名（不含方括号），如 "list"、"thread"、"Optional"
    ``kind``      : 特化 TypeDef 的 TypeKind
    ``build``     : ``(factory, arg_names, arg_modules) -> TypeDef``
                    从实参类型名构造特化 TypeDef。
    ``to_typeref``: ``(TypeDef) -> TypeRef`` 序列化特化 spec → 结构化 TypeRef。
    ``restore``   : ``(factory, data) -> TypeDef`` 从序列化数据还原特化 TypeDef。
    """

    name: str
    kind: str
    build: Callable[["SpecFactory", List[str], List[Optional[str]]], "TypeDef"]
    to_typeref: Callable[["TypeDef"], TypeRef]
    restore: Callable[["SpecFactory", Dict[str, Any]], "TypeDef"]


class GenericTypeRegistry:
    """内置泛型类型声明的注册表（单一权威源）。

    同时按 ``name`` 与 ``kind`` 索引，供创建（按名）与序列化/还原（按 kind）
    两条路径复用同一份声明。
    """

    def __init__(self) -> None:
        self._by_name: Dict[str, GenericTypeDeclaration] = {}
        self._by_kind: Dict[str, GenericTypeDeclaration] = {}

    def register(self, decl: GenericTypeDeclaration) -> None:
        self._by_name[decl.name] = decl
        self._by_kind[decl.kind] = decl

    def get(self, name: str) -> Optional[GenericTypeDeclaration]:
        return self._by_name.get(name)

    def get_by_kind(self, kind: str) -> Optional[GenericTypeDeclaration]:
        return self._by_kind.get(kind)

    def names(self) -> List[str]:
        return sorted(self._by_name)

    def __contains__(self, name: str) -> bool:
        return name in self._by_name


# ------------------------------------------------------------------ #
# 内置泛型类型声明（构建默认注册表）                                  #
# ------------------------------------------------------------------ #

def _build_list(factory: "SpecFactory", names: List[str], modules: List[Optional[str]]) -> "TypeDef":
    if len(names) == 1:
        return factory.create_list(
            element_type_name=names[0],
            element_type_module=modules[0] if modules else None,
        )
    return factory.create_list(allowed_element_type_names=list(names))


def _build_dict(factory: "SpecFactory", names: List[str], modules: List[Optional[str]]) -> "TypeDef":
    key = names[0] if len(names) > 0 else "any"
    val = names[1] if len(names) > 1 else "any"
    key_mod = modules[0] if modules and len(modules) > 0 else None
    val_mod = modules[1] if modules and len(modules) > 1 else None
    return factory.create_dict(key_type_name=key, value_type_name=val,
                               key_type_module=key_mod, value_type_module=val_mod)


def _build_tuple(factory: "SpecFactory", names: List[str], modules: List[Optional[str]]) -> "TypeDef":
    if len(names) >= 2:
        return factory.create_tuple(positional_element_type_names=list(names))
    elem = names[0] if names else "any"
    elem_mod = modules[0] if modules else None
    return factory.create_tuple(element_type_name=elem, element_type_module=elem_mod)


def _build_optional(factory: "SpecFactory", names: List[str], modules: List[Optional[str]]) -> "TypeDef":
    wrapped = names[0] if names else "any"
    wrapped_mod = modules[0] if modules else None
    return factory.create_optional(wrapped_type_name=wrapped, wrapped_type_module=wrapped_mod)


def _build_fn_callable(factory: "SpecFactory", names: List[str], modules: List[Optional[str]]) -> "TypeDef":
    value = names[0] if names else "auto"
    value_mod = modules[0] if modules else None
    return factory.create_fn_callable(value_type_name=value, value_type_module=value_mod)


def _build_behavior(factory: "SpecFactory", names: List[str], modules: List[Optional[str]]) -> "TypeDef":
    value = names[0] if names else "auto"
    value_mod = modules[0] if modules else None
    return factory.create_behavior(value_type_name=value, value_type_module=value_mod)


def _build_thread(factory: "SpecFactory", names: List[str], modules: List[Optional[str]]) -> "TypeDef":
    value = names[0] if names else "any"
    value_mod = modules[0] if modules else None
    return factory.create_thread(value_type_name=value, value_type_module=value_mod)


# -- to_typeref（序列化：特化 TypeDef → 结构化 TypeRef） ------------- #

def _to_typeref_list(spec: "TypeDef") -> TypeRef:
    if spec.allowed_element_types:
        return TypeRef.generic("list", *spec.allowed_element_types)
    elem = spec.element_type
    if elem is not None and elem.head != "any":
        return TypeRef.generic("list", elem)
    return TypeRef.of("list")


def _to_typeref_tuple(spec: "TypeDef") -> TypeRef:
    if spec.positional_element_types:
        return TypeRef.generic("tuple", *spec.positional_element_types)
    elem = spec.element_type
    if elem is not None and elem.head != "any":
        return TypeRef.generic("tuple", elem)
    return TypeRef.of("tuple")


def _to_typeref_dict(spec: "TypeDef") -> TypeRef:
    return TypeRef.generic("dict", spec.key_type, spec.value_type)


def _to_typeref_optional(spec: "TypeDef") -> TypeRef:
    wrapped = spec.wrapped_type
    if wrapped is not None and wrapped.head != "any":
        return TypeRef.generic("Optional", wrapped)
    return TypeRef.of("Optional")


def _to_typeref_callable(spec: "TypeDef") -> TypeRef:
    head = spec.get_base_name()
    val = spec.value_type
    if val is not None and val.head not in ("auto", "any", "", None):
        return TypeRef.generic(head, val)
    return TypeRef.of(head)


# -- restore（还原：序列化数据 → 特化 TypeDef） ----------------------- #

def _restore_list(factory: "SpecFactory", data: Dict[str, Any]) -> "TypeDef":
    return factory.create_list(
        element_type_name=data.get("element_type_name", "any"),
        element_type_module=data.get("element_type_module"),
    )


def _restore_dict(factory: "SpecFactory", data: Dict[str, Any]) -> "TypeDef":
    return factory.create_dict(
        key_type_name=data.get("key_type_name", "any"),
        value_type_name=data.get("value_type_name", "any"),
        key_type_module=data.get("key_type_module"),
        value_type_module=data.get("value_type_module"),
    )


def _restore_tuple(factory: "SpecFactory", data: Dict[str, Any]) -> "TypeDef":
    return factory.create_tuple(
        element_type_name=data.get("element_type_name", "any"),
        element_type_module=data.get("element_type_module"),
    )


def _restore_optional(factory: "SpecFactory", data: Dict[str, Any]) -> "TypeDef":
    return factory.create_optional(
        wrapped_type_name=data.get("wrapped_type_name", "any"),
        wrapped_type_module=data.get("wrapped_type_module"),
    )


def _restore_fn_callable(factory: "SpecFactory", data: Dict[str, Any]) -> "TypeDef":
    return factory.create_fn_callable(
        value_type_name=data.get("value_type_name", "auto"),
        value_type_module=data.get("value_type_module"),
    )


def _restore_behavior(factory: "SpecFactory", data: Dict[str, Any]) -> "TypeDef":
    return factory.create_behavior(
        value_type_name=data.get("value_type_name", "auto"),
        value_type_module=data.get("value_type_module"),
    )


def _restore_thread(factory: "SpecFactory", data: Dict[str, Any]) -> "TypeDef":
    return factory.create_thread(
        value_type_name=data.get("value_type_name", "any"),
        value_type_module=data.get("value_type_module"),
    )


def create_generic_registry() -> GenericTypeRegistry:
    """构建全部内置泛型类型的声明注册表（单一权威源）。"""
    reg = GenericTypeRegistry()
    reg.register(GenericTypeDeclaration(
        name="list", kind=TypeKind.LIST.value,
        build=_build_list, to_typeref=_to_typeref_list, restore=_restore_list,
    ))
    reg.register(GenericTypeDeclaration(
        name="dict", kind=TypeKind.DICT.value,
        build=_build_dict, to_typeref=_to_typeref_dict, restore=_restore_dict,
    ))
    reg.register(GenericTypeDeclaration(
        name="tuple", kind=TypeKind.TUPLE.value,
        build=_build_tuple, to_typeref=_to_typeref_tuple, restore=_restore_tuple,
    ))
    reg.register(GenericTypeDeclaration(
        name="Optional", kind=TypeKind.OPTIONAL.value,
        build=_build_optional, to_typeref=_to_typeref_optional, restore=_restore_optional,
    ))
    reg.register(GenericTypeDeclaration(
        name="fn_callable", kind=TypeKind.CALLABLE_INSTANCE.value,
        build=_build_fn_callable, to_typeref=_to_typeref_callable, restore=_restore_fn_callable,
    ))
    reg.register(GenericTypeDeclaration(
        name="behavior", kind=TypeKind.CALLABLE_INSTANCE.value,
        build=_build_behavior, to_typeref=_to_typeref_callable, restore=_restore_behavior,
    ))
    reg.register(GenericTypeDeclaration(
        name="thread", kind=TypeKind.TASK.value,
        build=_build_thread, to_typeref=_to_typeref_callable, restore=_restore_thread,
    ))
    return reg