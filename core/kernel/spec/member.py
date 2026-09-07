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
