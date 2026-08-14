"""
core/kernel/spec/registry/_members.py

_MemberMixin — attribute/method member resolution and diff hints.
"""

from __future__ import annotations

from typing import Optional

from core.base.enums import Provenance

from ..base import IbSpec, TypeKind
from ..member import MethodMemberSpec
from ..type_ref import TypeRef


class _MemberMixin:
    def resolve_member(self, spec: IbSpec, attr_name: str) -> Optional[IbSpec]:
        """
        Resolve the type of an attribute / method on ``spec``.

        Searches own members first, then the parent class chain.
        """
        member = spec.members.get(attr_name)
        if member is not None:
            if isinstance(member, MethodMemberSpec):
                # 泛型成员特化（协议驱动）：经 GenericTypeRegistry 查声明回调。
                # 回调返回结构化 TypeRef（如 TypeRef.generic("list", elem)），
                # 直接透传，不再 head 字符串化——保留嵌套泛型实参身份。
                effective_return = member.return_type
                effective_params = list(member.param_types)

                decl = self.generic_types.get(spec.get_base_name())
                if decl is not None and decl.resolve_member is not None:
                    spec_result = decl.resolve_member(self, spec, attr_name, member)
                    if spec_result is not None:
                        effective_return = spec_result.return_type
                        if spec_result.param_types is not None:
                            effective_params = spec_result.param_types

                from ..base import TypeDef

                # 实例方法成员建模为 BOUND_METHOD kind（BoundMethodAxiom：
                # bound_method IS-A callable 编译期接线——此前无条件 FUNCTION kind
                # 使 `a.calc` 编译期类型恒为 FUNCTION、BoundMethodAxiom 从不触发，
                # 编译期/运行期类型身份不对称）。MODULE 函数（模块级符号、无
                # receiver）保持 FUNCTION。容器/类等对象类型的方法均视为绑定
                # 接收者的实例方法：携带签名（param_types 不含 self——parser 把
                # self 消费为保留 token，不进入成员 param_types；return_type
                # 结构化保真），receiver_type 记录接收者类型。
                if spec.kind == TypeKind.MODULE.value:
                    resolved_kind = TypeKind.FUNCTION.value
                    resolved_name = attr_name
                else:
                    resolved_kind = TypeKind.BOUND_METHOD.value
                    resolved_name = "bound_method"
                resolved_member = TypeDef(
                    name=resolved_name,
                    kind=resolved_kind,
                    provenance=spec.provenance,
                    visibility=spec.visibility,
                    return_type=effective_return,
                    param_types=list(effective_params),
                )
                if resolved_kind == TypeKind.BOUND_METHOD.value:
                    resolved_member.receiver_type = TypeRef.from_spec(spec)
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
        if src_axiom:
            return src_axiom.get_diff_hint(target.get_base_name())
        return None
