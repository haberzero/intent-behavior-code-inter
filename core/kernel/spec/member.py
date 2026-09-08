"""
core/kernel/spec/member.py

Pure-data member descriptors stored inside IbSpec.members.

Storage model
-------------
Each member's declared type is stored as a :class:`TypeRef` (frozen, hashable,
structurally recursive).  Resolution happens at call-time via
``SpecRegistry.resolve_typeref(member.type_ref)`` (or, equivalently,
``SpecRegistry.resolve(member.type_ref.head, member.type_ref.module)``).

There are NO object references to IbSpec, Symbol, or any runtime object —
this is what breaks the historic Symbol ↔ TypeDescriptor circular dependency.

Hierarchy
---------
MemberSpec          — base (field or alias)
  MethodMemberSpec  — a callable member (method / llm-method)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional

from .type_ref import TypeRef


_ANY_REF: TypeRef = TypeRef.of("any")
_VOID_REF: TypeRef = TypeRef.of("void")


@dataclass
class MemberSpec:
    """
    Pure-data description of a single member of a class or module.

    The member's declared type is stored as ``type_ref`` (TypeRef).
    """

    name: str
    kind: str  # "field" | "method"
    type_ref: TypeRef = field(default_factory=lambda: _ANY_REF)
    metadata: dict = field(default_factory=dict)

    def is_method(self) -> bool:
        return self.kind == "method"


@dataclass
class MethodMemberSpec(MemberSpec):
    """
    Pure-data description of a callable member.

    Parameter types and return type are stored as TypeRef values.

    The ``kind`` field defaults to ``"method"``.

    ``mutating`` declares that this method modifies the receiver's state.
    Used by llmexcept body protection to block mutation of LLM-participating
    variables. Propagates transitively: a user function calling a mutating
    method on its parameter is inferred as mutating.

    ``llmexcept_safe`` marks methods that are sanctioned for use inside
    llmexcept handler bodies (e.g. ai.set_retry_hint, print).

    ``unbox_args`` 控制原生代理参数面（True = 调用边界拆箱 IbObject →
    native，缺省行为；False = 参数保留 IbObject 原形——值身份敏感的方法，
    如以不可拆箱值类型（vector）为参数的检索面）。
    """

    kind: str = "method"
    param_types: List[TypeRef] = field(default_factory=list)
    return_type: TypeRef = field(default_factory=lambda: _VOID_REF)
    mutating: bool = False
    llmexcept_safe: bool = False
    unbox_args: bool = True
    # 参数描述符（与 TypeDef.param_descriptors 对齐）。供方法覆写契约校验
    # 判断"子类多出的参数是否带默认值 / 是否为 varargs"。
    param_descriptors: List[ParamDescriptor] = field(default_factory=list)


def merge_decl_fields(field_maps):
    """生效字段表：``field_maps`` 为 base → derived 序的 ``{字段名: 值}`` 映射序列，
    子类同名字段覆盖父类，位置保持首次出现序；返回按生效序的 dict（值 = 最后胜出
    方的原值，对值类型不透明）。

    编译期（auto 构造器绑定检查：值 = ``(has_default, type_ref)``）与运行期
    （hydration auto-init：值 = ``has_default`` 布尔）的构造器参数收集共享此单一
    覆盖/位置规则——双端不各自实现，规则漂移结构性不可能。
    """
    effective: dict = {}
    for fmap in field_maps:
        effective.update(fmap)
    return effective


def collect_decl_only_fields(field_maps):
    """构造器须位置参数绑定的字段名：生效字段表中无默认值者（值真值 = 有默认）。

    运行期 hydration auto-init 的字段收集规则（父类优先、子类同名覆盖、仅留无
    默认值声明字段）；编译期构造器绑定检查经 :func:`merge_decl_fields` 同源。
    """
    return [name for name, value in merge_decl_fields(field_maps).items() if not value]


@dataclass(frozen=True)
class ParamDescriptor:
    """
    Pure-data description of a single callable parameter.

    Mirrors the ``IbArg`` AST node shape (name / kind / annotation /
    default-presence) in a resolved form (``TypeRef``), so that semantic
    argument resolution (positional → named → default fill → varargs) and
    future vtable declarations share one structure.

    ``kind`` values align with the ``ARG_*`` constants in ``core.kernel.ast``:
    POSITIONAL_OR_KEYWORD / VAR_POSITIONAL / VAR_KEYWORD.
    """

    name: str
    kind: str = "POSITIONAL_OR_KEYWORD"
    type_ref: TypeRef = field(default_factory=lambda: _ANY_REF)
    has_default: bool = False
    # 默认值字面值（仅原生模块函数声明使用：_spec.py 中显式给出的 Python 值）。
    # 用户级函数默认值是 AST 表达式，运行期经惰性求值，本字段保持 None。
    default_value: Any = None
