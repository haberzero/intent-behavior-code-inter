"""
core/kernel/spec/registry/factory.py

SpecFactory — factory for creating IbSpec instances.

All type-name parameters are plain strings — no spec objects are required
as input, so there are no circular reference risks.
"""

from __future__ import annotations

from typing import List, Optional

from ..base import IbSpec, TypeDef, TypeKind
from ..type_ref import TypeRef


# Primitive types that can be used as constructors/casts (e.g., int("42"), str(x)).
# These have PRIMITIVE kind but should return themselves when "called".
_PRIMITIVE_CONSTRUCTORS = frozenset({'str', 'int', 'float', 'bool'})


# ------------------------------------------------------------------ #
# SpecFactory                                                          #
# ------------------------------------------------------------------ #


class SpecFactory:
    """
    Creates IbSpec instances.

    All type-name parameters are plain strings — no spec objects are
    required as input, so there are no circular reference risks.
    """

    def create_primitive(self, name: str, is_nullable: bool = False) -> IbSpec:
        return IbSpec(name=name, kind=TypeKind.PRIMITIVE.value, is_nullable=is_nullable, is_user_defined=False)

    def create_func(
        self,
        name: str = "callable",
        param_type_names: Optional[List[str]] = None,
        param_type_modules: Optional[List[Optional[str]]] = None,
        return_type_name: str = "void",
        return_type_module: Optional[str] = None,
        is_user_defined: bool = False,
        is_llm: bool = False,
    ) -> "TypeDef":
        names = list(param_type_names or [])
        mods = list(param_type_modules or [])
        while len(mods) < len(names):
            mods.append(None)
        return TypeDef(
            name=name,
            kind=TypeKind.FUNCTION.value,
            is_nullable=True,
            is_user_defined=is_user_defined,
            is_llm=is_llm,
            return_type=TypeRef.of(return_type_name, return_type_module),
            param_types=[TypeRef.of(n, m) for n, m in zip(names, mods)],
        )

    def create_class(
        self,
        name: str,
        module: Optional[str] = None,
        parent_name: Optional[str] = None,
        parent_module: Optional[str] = None,
        is_user_defined: bool = True,
    ) -> "TypeDef":
        parent_type = TypeRef.of(parent_name, parent_module) if parent_name else None
        return TypeDef(
            name=name,
            kind=TypeKind.CLASS.value,
            module_path=module,
            is_nullable=True,
            is_user_defined=is_user_defined,
            parent_type=parent_type,
        )

    def create_list(
        self,
        element_type_name: str = "any",
        element_type_module: Optional[str] = None,
        allowed_element_type_names: Optional[list] = None,
    ) -> "TypeDef":
        if allowed_element_type_names:
            sorted_names = sorted(allowed_element_type_names)
            list_name = f"list[{','.join(sorted_names)}]"
            return TypeDef(
                name=list_name,
                kind=TypeKind.LIST.value,
                is_nullable=True,
                is_user_defined=False,
                element_type=TypeRef.of("any"),
                allowed_element_types=[TypeRef.of(n) for n in allowed_element_type_names],
            )
        list_name = f"list[{element_type_name}]" if element_type_name != "any" else "list"
        return TypeDef(
            name=list_name,
            kind=TypeKind.LIST.value,
            is_nullable=True,
            is_user_defined=False,
            element_type=TypeRef.of(element_type_name, element_type_module),
        )

    def create_dict(
        self,
        key_type_name: str = "any",
        value_type_name: str = "any",
        key_type_module: Optional[str] = None,
        value_type_module: Optional[str] = None,
    ) -> "TypeDef":
        return TypeDef(
            name=f"dict[{key_type_name},{value_type_name}]",
            kind=TypeKind.DICT.value,
            is_nullable=True,
            is_user_defined=False,
            key_type=TypeRef.of(key_type_name, key_type_module),
            value_type=TypeRef.of(value_type_name, value_type_module),
        )

    def create_tuple(
        self,
        element_type_name: str = "any",
        element_type_module: Optional[str] = None,
        positional_element_type_names: Optional[list] = None,
    ) -> "TypeDef":
        # 位置元素类型路径（`tuple[T1, T2, ...]`，元素数 ≥ 2）。
        # 与单类型路径 `tuple[T]` 互斥；前者使用 ``positional_element_types``，
        # 后者保持 ``element_type`` 单字段。
        if positional_element_type_names and len(positional_element_type_names) >= 2:
            # 保持位置顺序：tuple[int, str] ≠ tuple[str, int]
            tuple_name = f"tuple[{','.join(positional_element_type_names)}]"
            return TypeDef(
                name=tuple_name,
                kind=TypeKind.TUPLE.value,
                is_nullable=True,
                is_user_defined=False,
                element_type=TypeRef.of("any"),
                positional_element_types=[TypeRef.of(n) for n in positional_element_type_names],
            )
        tuple_name = f"tuple[{element_type_name}]" if element_type_name != "any" else "tuple"
        return TypeDef(
            name=tuple_name,
            kind=TypeKind.TUPLE.value,
            is_nullable=True,
            is_user_defined=False,
            element_type=TypeRef.of(element_type_name, element_type_module),
        )

    def create_bound_method(
        self,
        receiver_type_name: str,
        func_spec_name: str,
        receiver_type_module: Optional[str] = None,
    ) -> "TypeDef":
        return TypeDef(
            name="bound_method",
            kind=TypeKind.BOUND_METHOD.value,
            is_nullable=True,
            is_user_defined=False,
            func_spec_name=func_spec_name,
            receiver_type=TypeRef.of(receiver_type_name, receiver_type_module),
        )

    def create_module(self, name: str, module: Optional[str] = None) -> "TypeDef":
        return TypeDef(
            name=name,
            kind=TypeKind.MODULE.value,
            module_path=module,
            is_nullable=False,
            is_user_defined=False,
        )

    def create_fn_callable(
        self,
        value_type_name: str = "auto",
        value_type_module: Optional[str] = None,
    ) -> "TypeDef":
        """Create a TypeDef describing a fn_callable (lambda/snapshot) expression.

        Capture mode (``lambda`` vs ``snapshot``) is a property of the *value*
        (``IbFnCallable.capture_mode``) and of the creating AST node
        (``IbLambdaExpr.capture_mode``); it is intentionally NOT stored on the
        type spec.
        """
        fn_callable_name = f"fn_callable[{value_type_name}]" if value_type_name != "auto" else "fn_callable"
        spec = TypeDef(
            name=fn_callable_name,
            kind=TypeKind.CALLABLE_INSTANCE.value,
            is_nullable=True,
            is_user_defined=False,
            value_type=TypeRef.of(value_type_name, value_type_module),
        )
        # Route axiom dispatch to the "fn_callable" axiom even for parameterised
        # specs like "fn_callable[int]".
        spec._axiom_name = "fn_callable"
        return spec

    def create_optional(
        self,
        wrapped_type_name: str = "any",
        wrapped_type_module: Optional[str] = None,
    ) -> "TypeDef":
        """Create an Optional[T] spec."""
        return TypeDef(
            name=f"Optional[{wrapped_type_name}]",
            kind=TypeKind.OPTIONAL.value,
            is_nullable=True,
            is_user_defined=False,
            wrapped_type=TypeRef.of(wrapped_type_name, wrapped_type_module),
        )

    def create_behavior(
        self,
        value_type_name: str = "auto",
        value_type_module: Optional[str] = None,
    ) -> "TypeDef":
        """
        Create a ``TypeDef`` for a typed ``@~...~`` behavior expression.

        ``value_type_name`` is the LLM output type declared by the user (e.g. "int",
        "str").  When it is ``"auto"`` the compiler cannot infer the return type at
        call sites (same behaviour as before this feature was introduced).

        Capture mode (``lambda`` vs ``snapshot``) lives on the *value*
        (``IbBehavior.capture_mode``), not on the type.

        Example::

            # fn f = lambda -> int: @~...~  →  create_behavior(value_type_name="int")
            factory.create_behavior(value_type_name="int")
        """
        beh_name = f"behavior[{value_type_name}]" if value_type_name != "auto" else "behavior"
        spec = TypeDef(
            name=beh_name,
            kind=TypeKind.CALLABLE_INSTANCE.value,
            is_nullable=True,
            is_user_defined=False,
            value_type=TypeRef.of(value_type_name, value_type_module),
        )
        # Route axiom dispatch to the "behavior" axiom even for parameterised
        # specs like "behavior[int]".
        spec._axiom_name = "behavior"
        return spec
