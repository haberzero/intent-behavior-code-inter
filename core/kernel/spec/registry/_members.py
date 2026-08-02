"""
core/kernel/spec/registry/_members.py

_MemberMixin — attribute/method member resolution and diff hints.
"""

from __future__ import annotations

from typing import List, Optional

from core.base.enums import Provenance

from ..base import IbSpec, TypeKind
from ..member import MethodMemberSpec
from ..type_ref import TypeRef


class _MemberMixin:
    def resolve_member(self, spec: IbSpec, attr_name: str) -> Optional[IbSpec]:
        """
        Resolve the type of an attribute / method on ``spec``.

        Searches own members first, then the parent class chain.
        For ``TypeDef`` placeholders the real spec is looked up first so
        that cross-file imports resolve correctly during semantic analysis.
        """
        # Transparently resolve lazy placeholders created by the scheduler.
        if spec.kind == TypeKind.LAZY.value and not spec.members:
            resolved = self.resolve(spec.name, spec.module_path)
            if resolved and resolved is not spec:
                return self.resolve_member(resolved, attr_name)
            return self.resolve("any")

        member = spec.members.get(attr_name)
        if member is not None:
            if isinstance(member, MethodMemberSpec):
                # For specialized generic containers, override the return type of
                # methods that return the element/value type.
                # Override is applied regardless of the axiom's declared return type —
                # specialization is based on the container's runtime type parameter.
                #
                # TypeDef[T]:
                #   pop()         → T  (was "any")
                #   __getitem__() → T  (was "any")
                # TypeDef[K,V]:
                #   pop(key)  → V  (was "any")
                #   get(key)  → V  (was "any")
                #   values()  → list[V]  (was bare "list")
                #   keys()    → list[K]  (was bare "list")
                effective_return = member.return_type.head
                effective_return_module = member.return_type.module

                if (
                    spec.kind == TypeKind.LIST.value
                    # Multi-type lists (list[int,str,...]) have allowed_element_types set and
                    # use element_type="any" intentionally — skip specialization for them.
                    and not spec.allowed_element_types
                ):
                    elem = spec.element_type.head
                    if elem != "any" and attr_name in ("pop", "__getitem__"):
                        effective_return = elem
                        effective_return_module = spec.element_type.module
                elif spec.kind == TypeKind.DICT.value:
                    val = spec.value_type.head
                    key = spec.key_type.head
                    if attr_name in ("pop", "get") and val != "any":
                        # dict[K,V].get(key) → V  (same as pop)
                        effective_return = val
                        effective_return_module = spec.value_type.module
                    elif attr_name == "values" and val != "any":
                        # dict[K,V].values() → list[V]
                        # Eagerly register list[V] if not yet in registry so that
                        # resolve_return (called by visit_IbCall) can find it by name.
                        list_v_name = f"list[{val}]"
                        if not self.resolve(list_v_name):
                            list_base = self.resolve("list")
                            elem_spec = self.resolve(val) or self.resolve("any")
                            if list_base and elem_spec:
                                self.resolve_specialization(list_base, [elem_spec])
                        effective_return = list_v_name
                        effective_return_module = None
                    elif attr_name == "keys" and key != "any":
                        # dict[K,V].keys() → list[K]
                        list_k_name = f"list[{key}]"
                        if not self.resolve(list_k_name):
                            list_base = self.resolve("list")
                            key_spec = self.resolve(key) or self.resolve("any")
                            if list_base and key_spec:
                                self.resolve_specialization(list_base, [key_spec])
                        effective_return = list_k_name
                        effective_return_module = None

                # specialize write-method parameter types for list[T].
                # append(item: any) → append(item: T)
                # insert(idx: int, item: any) → insert(idx: int, item: T)
                # __setitem__(idx: int, value: any) → __setitem__(idx: int, value: T)
                effective_params = [t.head for t in member.param_types]
                effective_param_modules: List[Optional[str]] = [t.module for t in member.param_types]
                if (
                    spec.kind == TypeKind.LIST.value
                    and attr_name in ("append", "insert", "__setitem__")
                    and spec.element_type.head != "any"
                    and not spec.allowed_element_types
                ):
                    elem = spec.element_type.head
                    elem_mod = spec.element_type.module
                    # last param is always the element (value/item)
                    if effective_params:
                        effective_params[-1] = elem
                        effective_param_modules[-1] = elem_mod
                elif spec.kind == TypeKind.OPTIONAL.value:
                    wrapped = spec.wrapped_type.head
                    wrapped_mod = spec.wrapped_type.module
                    if wrapped != "any" and attr_name in ("unwrap", "or_else"):
                        effective_return = wrapped
                        effective_return_module = wrapped_mod
                    if wrapped != "any" and attr_name == "or_else" and effective_params:
                        # Optional[T].or_else(default) expects default of type T.
                        effective_params[0] = wrapped
                        effective_param_modules[0] = wrapped_mod
                from ..base import TypeDef
                resolved_member = TypeDef(
                    name=attr_name,
                    kind=TypeKind.FUNCTION.value,
                    provenance=spec.provenance,
                    visibility=spec.visibility,
                    return_type=TypeRef.of(effective_return, effective_return_module),
                    param_types=[TypeRef.of(n, m) for n, m in zip(effective_params, effective_param_modules)],
                )
                # 携带模块成员声明的参数描述符（具名/默认/varargs 实参校验依据）。
                # 容器特化方法无描述符（空列表），拷贝为空操作。
                resolved_member.param_descriptors = list(member.param_descriptors)
                return resolved_member
            # Enum variant access: return the enum class type itself
            if (spec.kind == TypeKind.CLASS.value and spec.parent_type is not None
                    and spec.parent_type.head == "Enum" and spec.provenance == Provenance.USER_DEFINED):
                return spec
            return self.resolve_typeref(member.type_ref) or self.resolve("any")

        # Walk parent chain for class specs
        if spec.kind == TypeKind.CLASS.value and spec.parent_type is not None:
            parent = self.resolve_typeref(spec.parent_type)
            if parent and parent is not spec:
                return self.resolve_member(parent, attr_name)

        # Dynamic fallback
        if self.is_dynamic(spec):
            return self.resolve("any")

        return None

    def get_diff_hint(self, src: IbSpec, target: IbSpec) -> Optional[str]:
        """Return an axiom-provided diagnostic hint for a type mismatch."""
        src_axiom = self._axiom_registry.get_axiom(src.get_base_name())
        if src_axiom and hasattr(src_axiom, "get_diff_hint"):
            return src_axiom.get_diff_hint(target.get_base_name())
        return None
