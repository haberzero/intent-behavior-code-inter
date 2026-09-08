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
                # bound_method IS-A callable 编译期接线——无条件 FUNCTION kind
                # 会使 `a.calc` 编译期类型恒为 FUNCTION、BoundMethodAxiom 从不触发，
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

    def get_constructor_descriptors(self, spec: IbSpec) -> Optional[list]:
        """类构造器参数描述符的编译期单一入口（auto/explicit ``__init__``）。

        与运行期 hydration auto-constructor 规则同源（interpreter auto-init）：

        - 显式 ``__init__`` 成员且描述符已精化（``descriptors_synced``）→ 返回其
          描述符（零参 = 空列表，同样是权威签名）；未精化（调用点先于定义）→
          None（动态跳过，维持运行期裁决，防误报）。
        - 否则 auto 构造器：继承链（父类优先、子类同名覆盖）全部无默认值字段 =
          必填位置参数；覆盖/位置规则与运行期共享 ``merge_decl_fields`` 单点，
          字段 type_ref 取生效覆盖方声明。链上无必填字段时与运行期回退同判据：
          链上有字段（全部带默认值，含子类同名覆盖）→ 零参构造器；链上无字段
          → 继承祖先显式 ``__init__``（已精化时）否则零参。
        - 仅 USER_DEFINED 类（内置/enum 走各自构造路径，与运行期 auto-init 同门）。

        返回 None = 静态签名不可用（调用方回落动态跳过）。
        """
        from ...ast import ARG_POSITIONAL_OR_KEYWORD
        from ..member import ParamDescriptor, merge_decl_fields

        if spec.kind != TypeKind.CLASS.value or spec.provenance != Provenance.USER_DEFINED:
            return None
        parent_ref = spec.parent_type
        if parent_ref is not None and parent_ref.head == "Enum":
            return None  # Enum 变体访问走成员路径，不经构造器
        members = getattr(spec, "members", None) or {}
        init_member = members.get("__init__")
        if init_member is not None:
            if (getattr(init_member, "metadata", None) or {}).get("descriptors_synced"):
                return list(getattr(init_member, "param_descriptors", None) or [])
            return None  # 显式 __init__ 尚未经类型检查精化 → 动态跳过
        # auto 构造器：继承链字段收集（self → base 遍历，base → self 序入表）
        chain = [spec]
        seen = {id(spec)}
        cls = spec
        while True:
            pt = cls.parent_type
            if pt is None:
                break
            parent = self.resolve_typeref(pt)
            if parent is None or id(parent) in seen:
                break
            seen.add(id(parent))
            chain.append(parent)
            cls = parent
        # 显式内置父（非 Object 的内置类型，如 `class MyList[T](list[T])`）：
        # auto 构造器字段规则仅适用纯用户类链——内置父带来原生构造机制
        # （运行期边界按既有形态裁决）→ 静态检查不覆盖，动态跳过。
        for ancestor in chain[1:]:
            if (ancestor.provenance != Provenance.USER_DEFINED
                    and ancestor.get_base_name() != "Object"):
                return None
        field_maps = [
            {
                name: ((m.metadata or {}).get("has_default", False), m.type_ref)
                for name, m in (getattr(c, "members", None) or {}).items()
                if m.kind == "field"
            }
            for c in reversed(chain)
        ]
        effective = merge_decl_fields(field_maps)
        required = [(name, value) for name, value in effective.items() if not value[0]]
        if required:
            return [
                ParamDescriptor(name=name, kind=ARG_POSITIONAL_OR_KEYWORD, type_ref=value[1])
                for name, value in required
            ]
        # 链上无必填字段（与运行期回退同判据）：
        # ① 链上有字段（全部带默认值，含子类同名覆盖父类无默认字段）→ 零参
        #    auto 构造器（权威签名，仍走结构检查）；
        # ② 链上无字段 → 继承祖先显式 __init__（lookup_method 同规则；描述符
        #    已精化时取其签名），否则零参。
        if effective:
            return []
        for ancestor in chain[1:]:
            pinit = (getattr(ancestor, "members", None) or {}).get("__init__")
            if pinit is not None and (getattr(pinit, "metadata", None) or {}).get(
                "descriptors_synced"
            ):
                return list(pinit.param_descriptors or [])
        return []

    def get_diff_hint(self, src: IbSpec, target: IbSpec) -> Optional[str]:
        """Return an axiom-provided diagnostic hint for a type mismatch."""
        src_axiom = self._axiom_registry.get_axiom(src.get_base_name())
        if src_axiom:
            return src_axiom.get_diff_hint(target.get_base_name())
        return None
