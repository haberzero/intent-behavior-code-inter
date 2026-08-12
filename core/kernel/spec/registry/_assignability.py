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

        # fn[...]（CALLABLE_SIG）有具体签名约束，不做动态放行：源可调用必须
        # 结构签名匹配（参数数量 + 返回类型）。否则 `fn[()->int]` 槽会被任意
        # 可调用无条件接受，编译期承诺 int 而运行期返回 str（不一致）。
        if target.kind == TypeKind.CALLABLE_SIG.value:
            return self._matches_callable_sig(src, target)

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

    def _matches_callable_sig(self, src: IbSpec, target: IbSpec) -> bool:
        """``fn[...]`` 签名约束的结构匹配（谓词，供 is_assignable 消费）。

        - 动态源（auto / fn / 裸动态可调用）：推迟到运行时，放行。
        - 参数数量：CALLABLE_INSTANCE（lambda）spec 不携带参数信息，跳过。
        - 返回类型：FUNCTION/BOUND_METHOD 用 ``return_type``，CALLABLE_INSTANCE 用
          ``value_type``；任一侧为动态（any/auto）即放行，否则必须可赋值。
        """
        if self.is_dynamic(src):
            return True
        if not self.is_callable(src):
            return False
        # 参数数量（CALLABLE_INSTANCE 无参数签名，跳过）
        if src.kind != TypeKind.CALLABLE_INSTANCE.value:
            src_params = getattr(src, "param_types", None) or []
            tgt_params = getattr(target, "param_types", None) or []
            if len(src_params) != len(tgt_params):
                return False
        # 返回类型
        if src.kind == TypeKind.CALLABLE_INSTANCE.value:
            src_ret = getattr(src, "value_type", None)
        else:
            src_ret = getattr(src, "return_type", None)
        tgt_ret = getattr(target, "return_type", None)
        if src_ret is not None and tgt_ret is not None:
            src_head = getattr(src_ret, "head", None)
            tgt_head = getattr(tgt_ret, "head", None)
            if (src_head and tgt_head
                    and src_head not in ("any", "auto")
                    and tgt_head not in ("any", "auto")):
                src_ret_spec = self.resolve(src_head, getattr(src_ret, "module", None))
                tgt_ret_spec = self.resolve(tgt_head, getattr(tgt_ret, "module", None))
                if (src_ret_spec and tgt_ret_spec
                        and not self.is_assignable(src_ret_spec, tgt_ret_spec)):
                    return False
        return True

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
