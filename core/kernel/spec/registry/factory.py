"""
core/kernel/spec/registry/factory.py

SpecFactory — factory for creating IbSpec instances.

All type-name parameters are plain strings — no spec objects are required
as input, so there are no circular reference risks.
"""

from __future__ import annotations

from typing import List, Optional

from core.base.enums import Provenance, Visibility

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

    def create_primitive(self, name: str) -> IbSpec:
        return IbSpec(
            name=name,
            kind=TypeKind.PRIMITIVE.value,
            provenance=Provenance.KERNEL_NATIVE,
            visibility=Visibility.PRELUDE_VISIBLE,
        )

    def create_type_param(self, name: str) -> TypeDef:
        """创建用户类泛型类型参数占位 spec（class Box[T] 的 T）。

        TYPE_PARAM 非实体类型（无 axiom/成员/运行时类），仅承载类型参数名
        供语义层解析与特化替换。
        """
        return TypeDef(
            name=name,
            kind=TypeKind.TYPE_PARAM.value,
            provenance=Provenance.USER_DEFINED,
            visibility=Visibility.IMPORT_GATED,
        )

    def create_func(
        self,
        name: str = "callable",
        param_type_names: Optional[List[str]] = None,
        param_type_modules: Optional[List[Optional[str]]] = None,
        return_type_name: str = "void",
        return_type_module: Optional[str] = None,
        param_types: Optional[List["TypeRef"]] = None,
        return_type: Optional["TypeRef"] = None,
        provenance: Provenance = Provenance.KERNEL_NATIVE,
        visibility: Visibility = Visibility.PRELUDE_VISIBLE,
    ) -> "TypeDef":
        """创建 FUNCTION kind 函数 spec。

        ``param_types`` / ``return_type``（结构化 TypeRef）**优先**——早期
        "字符串级" API（``TypeRef.of`` 扁平化 fn[(签名)]/泛型/Optional 返回）的
        架构断层根治：结构化注解解析出的 spec 不再被 `.name` 字符串降级。
        缺失时由 ``param_type_names`` / ``return_type_name`` 经 ``TypeRef.parse``
        结构化解析（与 create_list/create_optional 同构，嵌套泛型名保真）。
        """
        if param_types is not None:
            refs = list(param_types)
        elif param_type_names:
            mods = list(param_type_modules or [])
            while len(mods) < len(param_type_names):
                mods.append(None)
            refs = [TypeRef.parse(n, m) for n, m in zip(param_type_names, mods)]
        else:
            refs = []
        ret_ref = (
            return_type
            if return_type is not None
            else TypeRef.parse(return_type_name, return_type_module)
        )
        return TypeDef(
            name=name,
            kind=TypeKind.FUNCTION.value,
            provenance=provenance,
            visibility=visibility,
            return_type=ret_ref,
            param_types=refs,
        )

    def create_class(
        self,
        name: str,
        module: Optional[str] = None,
        parent_name: Optional[str] = None,
        parent_module: Optional[str] = None,
        provenance: Provenance = Provenance.USER_DEFINED,
        visibility: Visibility = Visibility.IMPORT_GATED,
    ) -> "TypeDef":
        parent_type = TypeRef.of(parent_name, parent_module) if parent_name else None
        return TypeDef(
            name=name,
            kind=TypeKind.CLASS.value,
            module_path=module,
            provenance=provenance,
            visibility=visibility,
            parent_type=parent_type,
        )

    def create_list(
        self,
        element_type_name: str = "any",
        element_type_module: Optional[str] = None,
        allowed_element_type_names: Optional[list] = None,
        allowed_element_type_modules: Optional[list] = None,
        element_type: Optional["TypeRef"] = None,
    ) -> "TypeDef":
        """Create a ``list[T]`` TypeDef.

        ``element_type`` (TypeRef) 优先；缺失时由 ``element_type_name`` 经
        ``TypeRef.parse`` 结构化解析（嵌套泛型名 ``"list[int]"`` 保真为
        ``TypeRef('list',(int,))``，避免 ``TypeRef.of`` 扁平化）。
        """
        if element_type is None:
            element_type = TypeRef.parse(element_type_name, element_type_module)
        if allowed_element_type_names:
            modules = allowed_element_type_modules or [None] * len(allowed_element_type_names)
            sorted_pairs = sorted(
                zip(allowed_element_type_names, modules),
                key=lambda p: p[0],
            )
            sorted_names = [p[0] for p in sorted_pairs]
            sorted_modules = [p[1] for p in sorted_pairs]
            list_name = f"list[{','.join(sorted_names)}]"
            return TypeDef(
                name=list_name,
                kind=TypeKind.LIST.value,
                provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE,
                element_type=TypeRef.of("any"),
                allowed_element_types=[
                    TypeRef.parse(n, m) for n, m in zip(sorted_names, sorted_modules)
                ],
            )
        list_name = f"list[{element_type.canonical_name}]" if element_type.head != "any" else "list"
        return TypeDef(
            name=list_name,
            kind=TypeKind.LIST.value,
            provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE,
            element_type=element_type,
        )

    def create_dict(
        self,
        key_type_name: str = "any",
        value_type_name: str = "any",
        key_type_module: Optional[str] = None,
        value_type_module: Optional[str] = None,
        key_type: Optional["TypeRef"] = None,
        value_type: Optional["TypeRef"] = None,
    ) -> "TypeDef":
        """Create a ``dict[K,V]`` TypeDef（类型实参结构化，嵌套保真）。"""
        if key_type is None:
            key_type = TypeRef.parse(key_type_name, key_type_module)
        if value_type is None:
            value_type = TypeRef.parse(value_type_name, value_type_module)
        return TypeDef(
            name=f"dict[{key_type.canonical_name},{value_type.canonical_name}]",
            kind=TypeKind.DICT.value,
            provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE,
            key_type=key_type,
            value_type=value_type,
        )

    def create_tuple(
        self,
        element_type_name: str = "any",
        element_type_module: Optional[str] = None,
        positional_element_type_names: Optional[list] = None,
        positional_element_type_modules: Optional[list] = None,
        element_type: Optional["TypeRef"] = None,
    ) -> "TypeDef":
        # 位置元素类型路径（`tuple[T1, T2, ...]`，元素数 ≥ 2）。
        # 与单类型路径 `tuple[T]` 互斥；前者使用 ``positional_element_types``，
        # 后者保持 ``element_type`` 单字段。
        if positional_element_type_names and len(positional_element_type_names) >= 2:
            # 保持位置顺序：tuple[int, str] ≠ tuple[str, int]
            positional = [
                TypeRef.parse(n, m)
                for n, m in zip(
                    positional_element_type_names,
                    positional_element_type_modules
                    or [None] * len(positional_element_type_names),
                )
            ]
            tuple_name = f"tuple[{','.join(p.canonical_name for p in positional)}]"
            return TypeDef(
                name=tuple_name,
                kind=TypeKind.TUPLE.value,
                provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE,
                element_type=TypeRef.of("any"),
                positional_element_types=positional,
            )
        if element_type is None:
            element_type = TypeRef.parse(element_type_name, element_type_module)
        tuple_name = f"tuple[{element_type.canonical_name}]" if element_type.head != "any" else "tuple"
        return TypeDef(
            name=tuple_name,
            kind=TypeKind.TUPLE.value,
            provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE,
            element_type=element_type,
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
            provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE,
            func_spec_name=func_spec_name,
            receiver_type=TypeRef.of(receiver_type_name, receiver_type_module),
        )

    def create_module(self, name: str, module: Optional[str] = None) -> "TypeDef":
        return TypeDef(
            name=name,
            kind=TypeKind.MODULE.value,
            module_path=module,
            provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE,
        )

    def create_fn_callable(
        self,
        value_type_name: str = "auto",
        value_type_module: Optional[str] = None,
        value_type: Optional["TypeRef"] = None,
    ) -> "TypeDef":
        """Create a TypeDef describing a fn_callable (lambda/snapshot) expression.

        Capture mode (``lambda`` vs ``snapshot``) is a property of the *value*
        (``IbFnCallable.capture_mode``) and of the creating AST node
        (``IbLambdaExpr.capture_mode``); it is intentionally NOT stored on the
        type spec.

        ``value_type`` (TypeRef) 优先；缺失时经 ``TypeRef.parse`` 结构化解析
        （嵌套泛型名保真）。
        """
        if value_type is None:
            value_type = TypeRef.parse(value_type_name, value_type_module)
        fn_callable_name = f"fn_callable[{value_type.canonical_name}]" if value_type.head != "auto" else "fn_callable"
        spec = TypeDef(
            name=fn_callable_name,
            kind=TypeKind.CALLABLE_INSTANCE.value,
            provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE,
            value_type=value_type,
        )
        # Route axiom dispatch to the "fn_callable" axiom even for parameterised
        # specs like "fn_callable[int]".
        spec._axiom_name = "fn_callable"
        return spec

    def create_optional(
        self,
        wrapped_type_name: str = "any",
        wrapped_type_module: Optional[str] = None,
        wrapped_type: Optional["TypeRef"] = None,
    ) -> "TypeDef":
        """Create an Optional[T] spec（嵌套保真结构化）。"""
        if wrapped_type is None:
            wrapped_type = TypeRef.parse(wrapped_type_name, wrapped_type_module)
        return TypeDef(
            name=f"Optional[{wrapped_type.canonical_name}]" if wrapped_type.head != "any" else "Optional",
            kind=TypeKind.OPTIONAL.value,
            provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE,
            wrapped_type=wrapped_type,
        )

    def create_behavior(
        self,
        value_type_name: str = "auto",
        value_type_module: Optional[str] = None,
        value_type: Optional["TypeRef"] = None,
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
        if value_type is None:
            value_type = TypeRef.parse(value_type_name, value_type_module)
        beh_name = f"behavior[{value_type.canonical_name}]" if value_type.head != "auto" else "behavior"
        spec = TypeDef(
            name=beh_name,
            kind=TypeKind.CALLABLE_INSTANCE.value,
            provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE,
            value_type=value_type,
        )
        # Route axiom dispatch to the "behavior" axiom even for parameterised
        # specs like "behavior[int]".
        spec._axiom_name = "behavior"
        return spec

    def create_thread(
        self,
        value_type_name: str = "any",
        value_type_module: Optional[str] = None,
        value_type: Optional["TypeRef"] = None,
    ) -> "TypeDef":
        """Create a ``TypeDef`` for a ``thread[T]`` type annotation.

        ``value_type_name`` is the thread's return value type (join 结果类型).
        ``thread[T]`` 是必选泛型注解；``t.join()`` yields ``T``。
        """
        if value_type is None:
            value_type = TypeRef.parse(value_type_name, value_type_module)
        thread_name = f"thread[{value_type.canonical_name}]" if value_type.head != "any" else "thread"
        spec = TypeDef(
            name=thread_name,
            kind=TypeKind.THREAD.value,
            provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE,
            value_type=value_type,
        )
        # Route axiom dispatch to the "thread" axiom even for parameterised
        # specs like "thread[int]".
        spec._axiom_name = "thread"
        return spec

    def create_thread_result(
        self,
        value_type_name: str = "any",
        value_type_module: Optional[str] = None,
        value_type: Optional["TypeRef"] = None,
    ) -> "TypeDef":
        """Create a ``TypeDef`` for a ``thread_result[T]`` container.

        ``value_type_name`` is the thread's return value type (join 结果类型).
        ``thread_result[T]`` is the container returned by ``t.join()``;
        ``T`` is the payload type (success value).
        """
        if value_type is None:
            value_type = TypeRef.parse(value_type_name, value_type_module)
        result_name = f"thread_result[{value_type.canonical_name}]" if value_type.head != "any" else "thread_result"
        spec = TypeDef(
            name=result_name,
            kind=TypeKind.THREAD_RESULT.value,
            provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE,
            value_type=value_type,
        )
        # Route axiom dispatch to the "thread_result" axiom even for parameterised
        # specs like "thread_result[int]".
        spec._axiom_name = "thread_result"
        return spec

    def create_chan(
        self,
        value_type_name: str = "any",
        value_type_module: Optional[str] = None,
        value_type: Optional["TypeRef"] = None,
    ) -> "TypeDef":
        """Create a ``TypeDef`` for a ``chan[T]`` type annotation.

        ``value_type_name`` is the channel's element type（消息类型）。
        ``chan[T]`` 经统一泛型模型承载：此前注解实参丢弃，符号 declared_type
        退化为裸 chan；纳入 GenericTypeDeclaration 后身份保留。
        """
        if value_type is None:
            value_type = TypeRef.parse(value_type_name, value_type_module)
        chan_name = f"chan[{value_type.canonical_name}]" if value_type.head != "any" else "chan"
        spec = TypeDef(
            name=chan_name,
            kind=TypeKind.CHANNEL.value,
            provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE,
            value_type=value_type,
        )
        spec._axiom_name = "chan"
        return spec

    def create_slot(
        self,
        value_type_name: str = "any",
        value_type_module: Optional[str] = None,
        value_type: Optional["TypeRef"] = None,
    ) -> "TypeDef":
        """Create a ``TypeDef`` for a ``slot[T]`` type annotation.

        ``value_type_name`` is the slot's value type（共享状态类型）。
        ``slot[T]`` 经统一泛型模型承载：此前注解实参丢弃，符号 declared_type
        退化为裸 slot。
        """
        if value_type is None:
            value_type = TypeRef.parse(value_type_name, value_type_module)
        slot_name = f"slot[{value_type.canonical_name}]" if value_type.head != "any" else "slot"
        spec = TypeDef(
            name=slot_name,
            kind=TypeKind.SLOT.value,
            provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE,
            value_type=value_type,
        )
        spec._axiom_name = "slot"
        return spec

    def create_generator(
        self,
        value_type_name: str = "any",
        value_type_module: Optional[str] = None,
        value_type: Optional["TypeRef"] = None,
    ) -> "TypeDef":
        """Create a ``TypeDef`` for a ``generator[T]`` type annotation.

        ``value_type_name`` is the generator's element (yield) type.
        ``generator[T]`` 是惰性生成器类型：含 ``yield`` 函数调用产出，迭代
        （``for``/``next``）产出 ``T`` 值。
        """
        if value_type is None:
            value_type = TypeRef.parse(value_type_name, value_type_module)
        gen_name = f"generator[{value_type.canonical_name}]" if value_type.head != "any" else "generator"
        spec = TypeDef(
            name=gen_name,
            kind=TypeKind.GENERATOR.value,
            provenance=Provenance.KERNEL_NATIVE, visibility=Visibility.PRELUDE_VISIBLE,
            value_type=value_type,
        )
        spec._axiom_name = "generator"
        return spec
