"""
core/kernel/axioms/primitives/generator.py

GeneratorAxiom — 惰性生成器类型（``generator[T]``）公理。

与 thread_result/chan/slot 同构的"值承载型泛型"公理：建立类型身份与方法表面
（to_list / generic_next），供语义层类型检查；运行时行为由 ``IbGenerator``
值对象提供（``@register_ib_type("generator")``，注册于 interpreter bootstrap）。
"""

from __future__ import annotations

from typing import Dict

from core.kernel.axioms.primitives.base import BaseAxiom, _m
from core.kernel.spec.member import MethodMemberSpec


class GeneratorAxiom(BaseAxiom):
    """公理：generator 类型（含 ``yield`` 函数调用产出的惰性生成器）。

    ``generator[T]`` 泛型：元素类型经 value_type 承载。提供 to_list / generic_next
    方法表面供语义层类型检查——运行时实现由 ``IbGenerator`` 值对象提供。
    """

    @property
    def name(self) -> str:
        return "generator"

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "to_list": _m("to_list", ret="list"),
            "generic_next": _m("generic_next", ret="any"),
        }

    def is_compatible(self, other_name: str) -> bool:
        return other_name == "generator" or other_name.startswith("generator[")
