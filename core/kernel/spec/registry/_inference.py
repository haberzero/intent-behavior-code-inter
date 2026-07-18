"""
core/kernel/spec/registry/_inference.py

_InferenceMixin — type-inference helpers (call/iter/subscript/operator
return types) and base-spec resolution.
"""

from __future__ import annotations

from typing import Any, List, Optional

from ..base import IbSpec, TypeKind
from .factory import _PRIMITIVE_CONSTRUCTORS


class _InferenceMixin:
    # ---------------------------------------------------------- #
    # Type-inference helpers                                     #
    # ---------------------------------------------------------- #

    def get_base_spec(self, spec: Optional["IbSpec"]) -> Optional["IbSpec"]:
        """
        Return the unspecialised base spec for a generic type.

        For specialised specs (e.g. ``list[int]``, ``dict[str,int]``) the name
        encodes the type arguments, but the axiom and capability lookup is always
        keyed on the base name (``list``, ``dict``).  Use this helper whenever
        you need to query capabilities or perform semantic classification on a
        type and want to tolerate generic specialisations transparently.

        Examples::

            get_base_spec(list[int])  → list spec
            get_base_spec(dict[str,int]) → dict spec
            get_base_spec(int)        → int spec  (already base)
            get_base_spec(None)       → None
        """
        if spec is None:
            return None
        base_name = spec.get_base_name()
        if base_name != spec.name:
            return self.resolve(base_name) or spec
        return spec


    def resolve_call_return(
        self,
        callee_spec: IbSpec,
        arg_specs: List[IbSpec],
        *,
        class_scope_lookup: Optional[Any] = None,
    ) -> Optional[IbSpec]:
        """
        Unified return-type resolution for ALL callable forms.

        This is the single entry point that handles:
        1. Primitive type constructors (str/int/float/bool/list/dict/Exception) → returns itself
        2. User-defined class constructors (TypeKind.CLASS) → returns itself
        3. Callable class instances (__call__ protocol) → resolves __call__ return type
        4. Structural callables (FUNCTION/CALLABLE_SIG) with explicit return_type
        5. Typed callable instances (fn_callable/behavior with value_type)
        6. Axiom-backed callables (axiom.resolve_return_type_name)
        7. Fallback: spec.return_type attribute direct read

        Parameters
        ----------
        callee_spec : IbSpec
            The type of the callee expression.
        arg_specs : List[IbSpec]
            Resolved types of each argument.
        class_scope_lookup : callable, optional
            A callback ``(class_name: str, method_name: str) -> Optional[IbSpec]``
            for resolving method specs from class scopes (used by the semantic
            pass to access owned_scope). If None, falls back to resolve_member.

        Returns
        -------
        Optional[IbSpec]
            The inferred return type, or None if the callee is not callable.
            Returns ``resolve("any")`` as last resort for callable but
            undetermined return types.
        """
        if callee_spec is None:
            return None

        kind = callee_spec.kind

        # --- Layer 1: Structural callables with explicit return_type ---
        if kind in (TypeKind.FUNCTION.value, TypeKind.CALLABLE_SIG.value):
            ret_ref = getattr(callee_spec, "return_type", None)
            if ret_ref is not None and ret_ref.head:
                return self.resolve_typeref(ret_ref) or self.resolve("any")
            # Function without explicit return type: axiom fallback
            axiom = self.get_axiom(callee_spec)
            if axiom and axiom.has_call_cap:
                arg_names = [a.get_base_name() for a in arg_specs if a]
                ret_name = axiom.resolve_return_type_name(arg_names)
                if ret_name:
                    return self.resolve(ret_name) or self.resolve("any")
            return self.resolve("any")

        # --- Layer 2: Class type (constructor or primitive type cast) ---
        if kind == TypeKind.CLASS.value:
            # Check for __call__ on class *instances* is handled by the caller
            # via is_type detection; here CLASS always means "constructor call"
            return callee_spec

        # --- Layer 2b: Primitive/container type used as constructor/cast ---
        # int(), str(), float(), bool() → returns itself
        # list(), dict() → returns itself (container constructor)
        if kind == TypeKind.PRIMITIVE.value:
            if callee_spec.name in _PRIMITIVE_CONSTRUCTORS:
                return callee_spec
        if kind in (TypeKind.LIST.value, TypeKind.DICT.value):
            return callee_spec

        # --- Layer 3: Callable instance (fn_callable / behavior with value_type) ---
        if kind == TypeKind.CALLABLE_INSTANCE.value:
            v_ref = getattr(callee_spec, "value_type", None)
            if v_ref is not None and v_ref.head not in ("auto", "any", "", None):
                return self.resolve_typeref(v_ref) or self.resolve("any")
            # Axiom fallback for untyped callable instances
            axiom = self.get_axiom(callee_spec)
            if axiom and axiom.has_call_cap:
                arg_names = [a.get_base_name() for a in arg_specs if a]
                ret_name = axiom.resolve_return_type_name(arg_names)
                if ret_name:
                    return self.resolve(ret_name) or self.resolve("any")
            return self.resolve("any")

        # --- Layer 4: Bound method ---
        if kind == TypeKind.BOUND_METHOD.value:
            ret_ref = getattr(callee_spec, "return_type", None)
            if ret_ref is not None and ret_ref.head:
                return self.resolve_typeref(ret_ref) or self.resolve("any")
            return self.resolve("any")

        # --- Layer 5: Axiom-backed callable (generic fallback) ---
        axiom = self.get_axiom(callee_spec)
        if axiom and axiom.has_call_cap:
            arg_names = [a.get_base_name() for a in arg_specs if a]
            ret_name = axiom.resolve_return_type_name(arg_names)
            if ret_name:
                return self.resolve(ret_name) or self.resolve("any")

        # Not callable
        return None

    def resolve_callable_instance_return(
        self,
        callee_spec: IbSpec,
        arg_specs: List[IbSpec],
        *,
        class_scope_lookup: Optional[Any] = None,
    ) -> Optional[IbSpec]:
        """
        Resolve return type for a callable class instance (object with __call__).

        This handles the case where a variable holds a class *instance* (not
        the class itself) that defines __call__. The caller must determine
        that the callee is an instance (not a type reference) before calling.

        Parameters
        ----------
        callee_spec : IbSpec
            The class spec of the instance's type.
        class_scope_lookup : callable, optional
            ``(class_name, method_name) -> Optional[IbSpec]`` for resolving
            from the class's owned scope (preferred over resolve_member).

        Returns
        -------
        Optional[IbSpec]
            The return type of __call__, or None if no __call__ found.
        """
        if callee_spec is None or callee_spec.kind != TypeKind.CLASS.value:
            return None

        members = callee_spec.members or {}
        if '__call__' not in members:
            return None

        # Try class_scope_lookup first (accesses live semantic scope)
        call_spec = None
        if class_scope_lookup:
            call_spec = class_scope_lookup(callee_spec.name, '__call__')

        # Fallback to resolve_member
        if not call_spec:
            call_spec = self.resolve_member(callee_spec, '__call__')

        if call_spec and call_spec.kind in (TypeKind.FUNCTION.value, TypeKind.CALLABLE_SIG.value):
            ret_ref = getattr(call_spec, 'return_type', None)
            if ret_ref and ret_ref.head:
                return self.resolve_typeref(ret_ref) or self.resolve("any")
            return self.resolve("any")

        return self.resolve("any")

    def resolve_op(
        self,
        spec: IbSpec,
        op: str,
        other: Optional[IbSpec],
    ) -> Optional[IbSpec]:
        """Infer the result type for a binary operator."""
        axiom = self.get_axiom(spec)
        if axiom and axiom.has_operator_cap:
            other_name = other.get_base_name() if other else None
            ret_name = axiom.resolve_operation_type_name(op, other_name)
            if ret_name:
                return self.resolve(ret_name) or self.resolve("any")

        # None 比较：任何类型均可与 None 用 == 或 != 比较，返回 bool
        if op in ("==", "!=") and (spec.name == "None" or (other and other.name == "None")):
            return self.resolve("bool")

        # User-defined class types support == and != by identity
        if spec.kind == TypeKind.CLASS.value and op in ("==", "!="):
            return self.resolve("bool")

        # All user-defined class instances support 'not' via IbObject.__not__ base implementation
        if spec.kind == TypeKind.CLASS.value and op == "not" and other is None:
            return self.resolve("bool")

        # P0-2: Check if user-defined class has operator method in its members
        if spec.kind == TypeKind.CLASS.value and spec.members:
            # Map operator symbol to dunder method name
            op_to_method = {
                '+': '__add__', '-': '__sub__', '*': '__mul__',
                '/': '__truediv__', '//': '__floordiv__', '%': '__mod__',
                '**': '__pow__', '&': '__and__', '|': '__or__',
                '^': '__xor__', '<<': '__lshift__', '>>': '__rshift__',
                '<': '__lt__', '<=': '__le__', '>': '__gt__', '>=': '__ge__',
                # Note: __eq__ and __ne__ already handled above
            }
            method_name = op_to_method.get(op)
            if method_name and method_name in spec.members:
                # User class has this operator method in its type definition
                method_member = spec.members[method_name]
                if method_member.is_method() and hasattr(method_member, 'return_type'):
                    # Use the declared return type
                    return self.resolve(method_member.return_type.head, method_member.return_type.module) or self.resolve("any")
                # Default: assume operator returns same type as left operand
                return spec

        return None

    def resolve_iter_element(self, spec: IbSpec) -> Optional[IbSpec]:
        """Infer the element type of an iterable."""
        if spec.kind in (TypeKind.LIST.value, TypeKind.TUPLE.value):
            # Multi-type list: element access returns any (user must cast explicitly)
            if spec.kind == TypeKind.LIST.value and getattr(spec, 'allowed_element_types', None):
                return self.resolve("any")
            return self.resolve(spec.element_type.head, spec.element_type.module) or self.resolve("any")
        axiom = self.get_axiom(spec)
        if axiom and axiom.has_iter_cap:
            elem_name = axiom.get_element_type_name()
            if elem_name:
                return self.resolve(elem_name) or self.resolve("any")
        return None

    def resolve_subscript(
        self,
        spec: IbSpec,
        key_spec: IbSpec,
    ) -> Optional[IbSpec]:
        """Infer the item type when spec[key] is accessed."""
        if spec.kind in (TypeKind.LIST.value, TypeKind.TUPLE.value):
            if key_spec.get_base_name() == "int":
                # Multi-type list: subscript access returns any
                if spec.kind == TypeKind.LIST.value and getattr(spec, 'allowed_element_types', None):
                    return self.resolve("any")
                return self.resolve(spec.element_type.head, spec.element_type.module) or self.resolve("any")
        if spec.kind == TypeKind.DICT.value:
            return self.resolve(spec.value_type.head, spec.value_type.module) or self.resolve("any")
        axiom = self.get_axiom(spec)
        if axiom and axiom.has_subscript_cap:
            item_name = axiom.resolve_item_type_name(key_spec.get_base_name())
            if item_name:
                return self.resolve(item_name) or self.resolve("any")
        return None
