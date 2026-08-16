"""
core/kernel/spec/registry/_assignability.py

_AssignabilityMixin — assignment compatibility and generic specialisation.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from ..base import IbSpec, TypeKind
from ..type_ref import TypeRef, specialization_key


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
            inner_target = self.resolve_typeref(target.wrapped_type) or self.resolve("any")
            if src.name == "None":
                return True
            if src.kind == TypeKind.OPTIONAL.value:
                inner_src = self.resolve_typeref(src.wrapped_type) or self.resolve("any")
                # 基础 Optional（wrapped=any）缺失类型精度，可赋值给任何 Optional[T]。
                if inner_src.name == "any":
                    return True
                return self.is_assignable(inner_src, inner_target, _visited)
            return self.is_assignable(src, inner_target, _visited)

        if src.kind == TypeKind.OPTIONAL.value:
            return False

        if src.name == target.name and src.module_path == target.module_path:
            return True

        # 内置泛型特化实参比较（缺陷一根治）：同泛型家族（list/dict/tuple/thread/
        # chan/slot/generator/fn_callable/behavior）的赋值必须校验特化实参——axiom
        # ``is_compatible`` 此前用前缀匹配（``startswith("list[")``）无视实参，导致
        # ``list[int]`` 可赋给 ``list[str]`` 等错误类型静默流入。此处按结构化实参
        # 逐个 ``is_assignable`` 递归（与用户类泛型特化（type_args）路径机制同构）。
        # 用户类（CLASS kind）不走本分支：其无 axiom、经 name 比较 + 继承链已正确拦截。
        if (
            src.kind != TypeKind.CLASS.value
            and target.kind != TypeKind.CLASS.value
        ):
            src_fam = src.get_base_name()
            # 家族兼容：src 家族与 target 家族相同，或 src 家族是 target 家族
            # 的 axiom 子类型链成员（behavior → fn_callable → callable）。此类
            # 跨家族赋值（behavior[int] → fn_callable[str]）是合法子类型转换，
            # 但特化实参必须校验（实参不兼容应拒绝）。
            if src_fam and self._generic_family_compatible(src_fam, target.get_base_name()):
                src_args = self._generic_spec_args(src)
                tgt_args = self._generic_spec_args(target)
                if src_args:
                    if not tgt_args:
                        # 协变：list[int] → list（特化 → 裸基类）放行。
                        return True
                    if len(src_args) != len(tgt_args):
                        # 实参数量不匹配（如 dict 单键 vs 双键、tuple 位置元素数不等）。
                        return False
                    for sa, ta in zip(src_args, tgt_args):
                        s_spec = self.resolve_typeref(sa) or self.resolve("any")
                        t_spec = self.resolve_typeref(ta) or self.resolve("any")
                        if not self.is_assignable(s_spec, t_spec):
                            return False
                    return True
                # src 为裸基类（无实参）→ 保持既有语义（axiom 前缀匹配放行），
                # 不在本分支收紧"裸 → 特化"方向（另一语义决策点）。

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
        # 结构化 family 判定：axiom is_compatible 接收 TypeRef（B2——不再传特化名
        # 字符串，head 即家族名）。
        src_axiom = self._axiom_registry.get_axiom(src.get_base_name())
        if src_axiom and src_axiom.is_compatible(TypeRef.from_spec(target)):
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
        - 逐参数类型：结构化 ref 经 resolve_typeref 解析（CALLABLE_SIG 签名模型
          根治：补 is_assignable 路径的逐参数检查——此前只查数量+返回，漏洞 1）。
          任一侧不可解析即拒绝（fail-fast，不静默跳过）。
        - 返回类型：FUNCTION/BOUND_METHOD 用 ``return_type``，CALLABLE_INSTANCE 用
          ``value_type``；任一侧为动态（any/auto）即放行，否则必须可赋值。
        """
        if self.is_dynamic(src):
            return True
        if not self.is_callable(src):
            return False
        # 参数数量 + 逐参数类型（CALLABLE_INSTANCE 无参数签名，跳过）
        if src.kind != TypeKind.CALLABLE_INSTANCE.value:
            src_params = getattr(src, "param_types", None) or []
            tgt_params = getattr(target, "param_types", None) or []
            if len(src_params) != len(tgt_params):
                return False
            for sp, tp in zip(src_params, tgt_params):
                s_spec = self.resolve_typeref(sp)
                t_spec = self.resolve_typeref(tp)
                # 裸类型参数占位（T，无实参）不可解析：延后至特化后校验（模板体内
                # fn[(T)->int] x = c 不误拒）。
                if s_spec is None and not getattr(sp, "args", None):
                    continue
                if t_spec is None and not getattr(tp, "args", None):
                    continue
                # 带实参的 ref 不可解析（如 module 限定 concrete 解析失败）→ 拒绝
                # （fail-fast，不静默跳过——否则漏洞 2 重新打开）。
                if s_spec is None or t_spec is None:
                    return False
                # 任一侧含 any 泛型实参（T 降级占位 Box[any] 或显式 any 通配）：
                # 动态通配无法静态拒绝，延后（模板字段/参数赋值不误拒）。
                from ..base import spec_has_any_generic_arg

                if spec_has_any_generic_arg(s_spec) or spec_has_any_generic_arg(t_spec):
                    continue
                if (not self.is_dynamic(s_spec) and not self.is_dynamic(t_spec)
                        and not self.is_assignable(s_spec, t_spec)):
                    return False
        # 返回类型
        if src.kind == TypeKind.CALLABLE_INSTANCE.value:
            src_ret = getattr(src, "value_type", None)
        else:
            src_ret = getattr(src, "return_type", None)
        tgt_ret = getattr(target, "return_type", None)
        if src_ret is not None and tgt_ret is not None:
            src_ret_spec = self.resolve_typeref(src_ret)
            tgt_ret_spec = self.resolve_typeref(tgt_ret)
            if (src_ret_spec and tgt_ret_spec
                    and not self.is_dynamic(src_ret_spec)
                    and not self.is_dynamic(tgt_ret_spec)
                    and not self.is_assignable(src_ret_spec, tgt_ret_spec)):
                return False
        return True

    def _generic_family_compatible(self, src_fam: str, tgt_fam: str) -> bool:
        """泛型家族兼容判定：src 家族与 target 家族相同，或 src 家族是 target
        家族的 axiom 子类型链成员。

        behavior → fn_callable → callable（axiom 父链）：``behavior[int]`` 赋给
        ``fn_callable[str]`` 是合法子类型转换方向，但实参须校验。非泛型家族
        （无法经 axiom 解析）视为不兼容（返回 False，保持既有行为）。
        """
        if src_fam == tgt_fam:
            return True
        cur = src_fam
        visited = set()
        while cur and cur not in visited:
            visited.add(cur)
            axiom = self._axiom_registry.get_axiom(cur)
            if axiom is None:
                return False
            parent = axiom.get_parent_axiom_name()
            if parent == tgt_fam:
                return True
            cur = parent
        return False

    def _generic_spec_args(self, spec: IbSpec) -> List[TypeRef]:
        """提取内置泛型特化 spec 的结构化实参 TypeRef 列表。

        各 kind 的实参承载字段（与 ``SpecFactory``/``TypeRef.from_spec`` 同构，
        单一权威源）：
        - list → ``element_type``；dict → ``key_type`` + ``value_type``
        - tuple → ``positional_element_types``（多参）或 ``element_type``（单参）
        - thread/thread_result/chan/slot/generator → ``value_type``
        - fn_callable/behavior → ``value_type``（语义 = 返回类型，与用户类泛型
          实参意义不同：``fn_callable[int]`` 的 ``int`` 是调用返回类型）
        - 裸基类（无实参）返回空列表——调用方据此区分"特化 vs 裸"。

        返回空列表表示"裸类型/无实参"，不参与实参比较。
        """
        kind = spec.kind
        if kind == TypeKind.LIST.value:
            el = spec.element_type
            if el is not None and el.head != "any":
                return [el]
            return []
        if kind == TypeKind.DICT.value:
            # dict[K,V] 双实参（key + value）。不过滤 any：``dict[K]`` 是
            # ``dict[K,any]``（value 动态），保留完整实参让递归 is_assignable
            # 经 is_dynamic 自然放行（``dict[K,V] → dict[K]`` 合法协变）。
            # 裸基类（key/value 均 any）返回空列表（视为无实参，不参与比较）。
            args = []
            if spec.key_type is not None:
                args.append(spec.key_type)
            if spec.value_type is not None:
                args.append(spec.value_type)
            if all(a.head == "any" for a in args):
                return []
            return args
        if kind == TypeKind.TUPLE.value:
            pos = getattr(spec, "positional_element_types", None) or []
            if pos:
                return list(pos)
            el = spec.element_type
            if el is not None and el.head != "any":
                return [el]
            return []
        if kind in (
            TypeKind.THREAD.value,
            TypeKind.THREAD_RESULT.value,
            TypeKind.CHANNEL.value,
            TypeKind.SLOT.value,
            TypeKind.GENERATOR.value,
            TypeKind.CALLABLE_INSTANCE.value,
        ):
            val = spec.value_type
            if val is not None and val.head not in ("any", "auto", "", None):
                return [val]
            return []
        return []

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
            # 结构化实参 TypeRef（嵌套泛型保真）：从 arg_specs 经 from_spec 构造，
            # 不经 `a.name` 字符串——扁平化会使 substitute 无法穿透嵌套实参。
            arg_refs = [TypeRef.from_spec(a) for a in arg_specs]
            arg_modules = [a.module_path for a in arg_specs]
            # 使用完整特化名（含参数）作缓存键，支持嵌套泛型 list[list[int]]
            # （specialization_key 单点生成，见 type_ref.py）。
            candidate_key = specialization_key(base_name, [r.canonical_name for r in arg_refs])
            cached = self.resolve(candidate_key)
            if cached is not None:
                return cached
            result = decl.build(self.factory, arg_refs, arg_modules)
            result = self.register(result)
            # Bootstrap axiom methods for the newly registered specialised spec.
            axiom = self.get_axiom(result)
            if axiom:
                method_specs = axiom.get_method_specs()
                for m_name, m_spec in method_specs.items():
                    result.members.setdefault(m_name, m_spec)
            return result

        # 用户类泛型：class Box[T] → Box[int]（特化 spec 构造）。
        if spec.kind == TypeKind.CLASS.value and getattr(spec, "type_params", None):
            return self._specialize_user_class(spec, arg_specs)
        return None

    def _specialize_user_class(self, spec: "IbSpec", arg_specs: List[IbSpec]) -> Optional[IbSpec]:
        """构造用户类泛型特化 spec（``class Box[T]`` → ``Box[int]``）。

        - 校验类型实参数量 == 类型参数数量（不等报语义错误，调用方报告）。
        - 特化名 ``"Box[int]"``（对齐内置泛型 ``f"{base}[{args}]"`` 缓存键）。
        - 复制基类 spec（kind=CLASS，parent 递归特化），成员类型经
          ``TypeRef.substitute`` 把类型参数占位替换为实参。
        - 已注册（缓存命中）直接返回。
        """
        type_params = list(spec.type_params)
        if len(arg_specs) != len(type_params):
            return None  # 参数数量不匹配：语义层报 SEM，这里不构造
        # 类型参数协议约束：实参不满足 bound 时拒绝构造（语义层负责报错）。
        if self.type_param_bound_errors(spec, arg_specs):
            return None
        # 结构化实参 TypeRef（嵌套泛型 Box[list[int]] 保真）：经 from_spec 构造，
        # 供 substitute 穿透与序列化 round-trip。
        arg_refs = [TypeRef.from_spec(a) for a in arg_specs]
        mapping = {
            param: TypeRef.from_spec(a)
            for param, a in zip(type_params, arg_specs)
        }
        arg_names = [r.canonical_name for r in arg_refs]
        specialized_name = specialization_key(spec.name, arg_names)
        cached = self.resolve(specialized_name, getattr(spec, "module_path", None))
        if cached is not None:
            return cached

        result = self.factory.create_class(
            name=specialized_name,
            module=getattr(spec, "module_path", None),
            parent_name=None,
            parent_module=None,
            provenance=spec.provenance,
            visibility=spec.visibility,
        )
        # 特化 spec 不携带类型参数（已代入）。
        result.type_params = []
        # 特化实参 + 原始基类名：供 from_spec 结构化构造与序列化保真。
        result.base_name = spec.name
        result.type_args = list(arg_refs)
        # 父类特化：基类 parent 若是泛型引用（class Sub[T](Box[T])）递归替换。
        if spec.parent_type is not None:
            parent_ref = spec.parent_type.substitute(mapping)
            result.parent_type = parent_ref
            # 父特化 spec 递归创建并注册：Sub[T](Box[T]) 特化为 Sub[str] 时，
            # 父 Box[str] 特化 spec 须存在（否则序列化/运行时继承链断裂）。
            # 仅对**具体**实参（非类型参数占位）递归——模板自身（Sub[T]）的
            # 父引用 Box[T] 是占位，不创建 Box[T] 实体。
            self._ensure_parent_specialization(parent_ref)
        result.members = self._substitute_members(spec.members, mapping)
        result = self.register(result)
        return result

    def _ensure_parent_specialization(self, parent_ref: TypeRef) -> None:
        """递归创建并注册父特化 spec（Sub[str] 的父 Box[str]）。

        ``parent_ref`` 是泛型父引用（带 args）。对**具体**实参（可被注册表
        解析且非类型参数占位）递归 ``resolve_specialization`` 创建父特化——
        否则序列化/运行时继承链找不到父特化类。类型参数占位（模板自身
        ``Sub[T]`` 的父 ``Box[T]``）不创建（无实体）。
        """
        if not parent_ref.args:
            return
        # 解析父基类 spec。
        base_spec = self.resolve(parent_ref.head, parent_ref.module)
        if base_spec is None:
            return
        # 实参递归：嵌套泛型实参（list[int]）也须已特化存在。
        for a in parent_ref.args:
            if a.args:
                self._ensure_parent_specialization(a)
        # 把实参 TypeRef 解析为 spec（递归经 resolve_specialization）。
        arg_specs = []
        for a in parent_ref.args:
            if a.args:
                arg_specs.append(self.resolve(a.canonical_name))
            else:
                arg_specs.append(self.resolve(a.head, a.module))
        arg_specs = [s for s in arg_specs if s is not None]
        if len(arg_specs) != len(parent_ref.args):
            return  # 含占位/未解析实参 → 模板形态，跳过
        if getattr(base_spec, "type_params", None):
            self.resolve_specialization(base_spec, arg_specs)

    def _substitute_members(self, members: Dict[str, Any], mapping: dict) -> Dict[str, Any]:
        """对类成员表的类型做类型参数替换。

        字段（MemberSpec.type_ref）、方法（MethodMemberSpec 的
        type_ref/param_types/return_type/param_descriptors）中的类型参数占位
        → 实参 TypeRef。返回新 dict（不改写原成员——基类 spec 保持未特化形态）。
        """
        from ..member import MethodMemberSpec, ParamDescriptor

        out: Dict[str, Any] = {}
        for name, member in members.items():
            if member is None:
                out[name] = None
                continue
            if isinstance(member, MethodMemberSpec):
                new_member = MethodMemberSpec(
                    name=member.name,
                    kind=member.kind,
                    type_ref=member.type_ref.substitute(mapping),
                )
                new_member.param_types = [
                    p.substitute(mapping) for p in member.param_types
                ]
                new_member.return_type = member.return_type.substitute(mapping)
                # param_descriptors 深度替换：ParamDescriptor.type_ref 中的
                # 类型参数占位 → 实参（特化方法参数类型在调用侧据此校验）。
                new_member.param_descriptors = [
                    ParamDescriptor(
                        name=d.name,
                        kind=d.kind,
                        type_ref=d.type_ref.substitute(mapping),
                        has_default=d.has_default,
                        default_value=d.default_value,
                    )
                    for d in member.param_descriptors
                ]
                new_member.metadata = dict(member.metadata)
                out[name] = new_member
            else:
                new_member = type(member)(
                    name=member.name,
                    kind=member.kind,
                    type_ref=member.type_ref.substitute(mapping),
                    metadata=dict(getattr(member, "metadata", {}) or {}),
                )
                out[name] = new_member
        return out
