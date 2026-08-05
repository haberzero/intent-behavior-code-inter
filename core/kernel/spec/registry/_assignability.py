"""
core/kernel/spec/registry/_assignability.py

_AssignabilityMixin — assignment compatibility and generic specialisation.
"""

from __future__ import annotations

from typing import List, Optional

from ..base import IbSpec, TypeKind


class _AssignabilityMixin:
    def is_assignable(self, src: Optional[IbSpec], target: Optional[IbSpec],
                       _visited: Optional[frozenset] = None) -> bool:
        """
        Check whether a value of type ``src`` can be assigned to a
        variable of type ``target``.

        ``_visited`` is an internal cycle-guard set used when walking the
        class inheritance chain; callers should never pass it explicitly.
        """
        if src is None or target is None:
            return False
        if src is target:
            return True
        if self.is_dynamic(target):
            return True
        if self.is_dynamic(src):
            if self.is_dynamic(target):
                return True
            # A dynamic callable (fn / auto) can be assigned to any callable slot,
            # including typed TypeDef/TypeDef (e.g. `fn f = make_adder()`).
            if self.is_callable(target):
                return True
            return False

        if target.kind == TypeKind.OPTIONAL.value:
            inner_target = self.resolve(target.wrapped_type.head, target.wrapped_type.module) or self.resolve("any")
            if src.name == "None":
                return True
            if src.kind == TypeKind.OPTIONAL.value:
                inner_src = self.resolve(src.wrapped_type.head, src.wrapped_type.module) or self.resolve("any")
                # 基础 Optional（wrapped=any）缺失类型精度，可赋值给任何 Optional[T]。
                if inner_src.name == "any":
                    return True
                return self.is_assignable(inner_src, inner_target, _visited)
            return self.is_assignable(src, inner_target, _visited)

        if src.kind == TypeKind.OPTIONAL.value:
            return False

        if src.name == target.name and src.module_path == target.module_path:
            return True

        # Multi-type list compatibility: list[int,str] is assignable to list or list[int,str]
        if src.kind == TypeKind.LIST.value and target.kind == TypeKind.LIST.value:
            src_allowed = src.allowed_element_types
            tgt_allowed = target.allowed_element_types
            if src_allowed or tgt_allowed:
                # If target is bare list, accept any list variant
                if not tgt_allowed and target.element_type.head == "any":
                    return True
                # If target has allowed types, source must have same or subset
                if tgt_allowed and src_allowed:
                    return {t.head for t in src_allowed} <= {t.head for t in tgt_allowed}
                # Single-type target, multi-type source: relaxed — allow
                return True

        # Axiom-driven compatibility (e.g. bool isa int)
        # Pass the full target name so axioms can handle typed variants like "fn_callable[int]".
        src_axiom = self._axiom_registry.get_axiom(src.get_base_name())
        if src_axiom and src_axiom.is_compatible(target.name):
            return True

        # Class inheritance: walk src's parent chain.
        # _visited guards against malformed circular inheritance declarations.
        if src.kind == TypeKind.CLASS.value and src.parent_type is not None:
            visit_key = f"{src.name}@{src.module_path or ''}"
            visited = _visited or frozenset()
            if visit_key in visited:
                # Cycle detected in inheritance chain — stop traversal.
                return False
            parent = self.resolve_typeref(src.parent_type)
            if parent and parent is not src:
                return self.is_assignable(parent, target, visited | {visit_key})

        return False

    def resolve_specialization(
        self,
        spec: IbSpec,
        arg_specs: List[IbSpec],
    ) -> Optional[IbSpec]:
        """Resolve a generic type specialisation, e.g. list[int].

        Special case: ``fn[TYPE]`` — internal subscript for expression-side return-type inference.
        ``fn f = lambda -> int: EXPR`` causes the semantic analyser to build a
        ``TypeDef(value_type_name="int")`` via this path.  This enables
        call-site inference: ``int r = f()`` compiles without SEM_TYPE_MISMATCH.

        其余内置泛型类型（list/dict/tuple/Optional/fn_callable/behavior/thread）
        统一经 ``GenericTypeRegistry``（单一权威源）路由创建/解析。
        """
        # Special case: fn[RETURN_TYPE] → TypeDef(value_type_name=RETURN_TYPE)
        if spec.name == "fn" and arg_specs:
            value_type = arg_specs[0]
            return self.factory.create_fn_callable(
                value_type_name=value_type.name,
                value_type_module=value_type.module_path,
            )

        # 统一泛型模型：按基础名查声明的内置泛型类型。
        base_name = spec.get_base_name()
        decl = self.generic_types.get(base_name)
        if decl is not None:
            arg_names = [a.name for a in arg_specs]
            arg_modules = [a.module_path for a in arg_specs]
            # 使用完整特化名（含参数）作缓存键，支持嵌套泛型 list[list[int]]。
            candidate_key = f"{base_name}[{','.join(arg_names)}]"
            cached = self.resolve(candidate_key)
            if cached is not None:
                return cached
            result = decl.build(self.factory, arg_names, arg_modules)
            result = self.register(result)
            # Bootstrap axiom methods for the newly registered specialised spec.
            axiom = self.get_axiom(result)
            if axiom:
                method_specs = axiom.get_method_specs()
                for m_name, m_spec in method_specs.items():
                    result.members.setdefault(m_name, m_spec)
            return result
        return None
