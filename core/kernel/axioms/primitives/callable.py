"""
core/kernel/axioms/primitives/callable.py

Callable-family axioms: callable, fn_callable, behavior, bound_method.
"""

from __future__ import annotations

from typing import List, Optional

from core.kernel.axioms.primitives.base import BaseAxiom
from core.kernel.spec.type_ref import TypeRef


# ------------------------------------------------------------------ #
# BoundMethod                                                         #
# ------------------------------------------------------------------ #

class BoundMethodAxiom(BaseAxiom):
    has_call_cap = True

    @property
    def name(self) -> str:
        return "bound_method"

    def get_parent_axiom_name(self) -> Optional[str]:
        return "callable"

    def resolve_return_type_name(self, arg_type_names: List[str]) -> Optional[str]:
        return "any"

    def is_compatible(self, other: TypeRef) -> bool:
        # bound_method IS-A callable.
        return other.head in ("bound_method", "callable")


# ------------------------------------------------------------------ #
# callable                                                             #
# ------------------------------------------------------------------ #

class CallableAxiom(BaseAxiom):
    """
    公理：callable 类型。

    * is_dynamic() = False —— callable 是具体类型，不是 "any" 的妥协。
    * has_call_cap = True；resolve_return_type_name 返回 "auto"——编译期返回类型
      取决于具体的 TypeDef/IbFnCallable/IbBehavior。

    is_compatible(target) 语义：source 能否被赋值给 target 类型的变量。
    callable 只能赋值给 callable 槽；子类型（fn_callable、behavior、bound_method）
    通过自身的 is_compatible() 声明向上兼容父类型。
    """

    has_call_cap = True

    @property
    def name(self) -> str:
        return "callable"

    def resolve_return_type_name(self, arg_type_names: List[str]) -> Optional[str]:
        return "auto"

    def is_compatible(self, other: TypeRef) -> bool:
        return other.head == "callable"


# ------------------------------------------------------------------ #
# fn_callable                                                          #
# ------------------------------------------------------------------ #

class FnCallableAxiom(BaseAxiom):
    """
    公理：fn_callable 类型（普通可调用实例）。

    lambda/snapshot 修饰任意表达式产生的可调用实例。
    * 不是 DynamicAxiom —— fn_callable 是一个具体的一等公民类型。
    * has_call_cap —— fn_callable 对象可被调用（执行捕获的表达式）。
    * is_dynamic() = False。
    * 编译期返回类型为 "auto"；运行期由 IbFnCallable.call() 求值。

    is_compatible 方向：fn_callable IS-A callable。
    """

    has_call_cap = True

    @property
    def name(self) -> str:
        return "fn_callable"

    def resolve_return_type_name(self, arg_type_names: List[str]) -> Optional[str]:
        return "auto"

    def is_compatible(self, other: TypeRef) -> bool:
        return other.head in ("fn_callable", "callable")

    def get_parent_axiom_name(self) -> Optional[str]:
        return "callable"


# ------------------------------------------------------------------ #
# behavior                                                            #
# ------------------------------------------------------------------ #

class BehaviorAxiom(BaseAxiom):
    """
    公理：behavior 类型（LLM 行为表达式的可调用实例）。

    behavior 是 fn_callable 的特化子类型——它执行的不是普通表达式，而是 LLM 行为描述。
    * 不是 DynamicAxiom —— behavior 是一个具体的一等公民类型。
    * has_call_cap —— behavior 对象可被调用（触发 LLM 执行）。
    * 编译期返回类型为 "auto"；运行期由 IbBehavior.call() 根据 expected_type 解析真实类型。
    * 继承链：behavior → fn_callable → callable → Object
    """

    has_call_cap = True

    @property
    def name(self) -> str:
        return "behavior"

    def resolve_return_type_name(self, arg_type_names: List[str]) -> Optional[str]:
        return "auto"

    def is_compatible(self, other: TypeRef) -> bool:
        return other.head in ("behavior", "fn_callable", "callable")

    def get_parent_axiom_name(self) -> Optional[str]:
        return "fn_callable"
