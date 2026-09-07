"""
core/kernel/axioms/primitives/numeric.py

Numeric axioms: int, float, bool.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from core.kernel.axioms.primitives.base import BaseAxiom, _m
from core.kernel.spec.member import MethodMemberSpec
from core.kernel.spec.type_ref import TypeRef

if TYPE_CHECKING:
    from core.kernel.spec.base import IbSpec


# ------------------------------------------------------------------ #
# int                                                                 #
# ------------------------------------------------------------------ #

class IntAxiom(BaseAxiom):
    has_operator_cap = True
    has_converter_cap = True
    has_parser_cap = True
    has_from_prompt_cap = True
    has_output_hint_cap = True

    @property
    def name(self) -> str:
        return "int"

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "to_bool":  _m("to_bool",  ret="bool"),
            "to_list":  _m("to_list",  ret="list"),
            "cast_to":  _m("cast_to",  params=["any"], ret="any"),
        }

    def get_operators(self) -> Dict[str, str]:
        return {
            "+": "__add__", "-": "__sub__", "*": "__mul__",
            "/": "__truediv__", "//": "__floordiv__", "%": "__mod__",
            "**": "__pow__", "&": "__and__", "|": "__or__",
            "^": "__xor__", "<<": "__lshift__", ">>": "__rshift__",
            "==": "__eq__", "!=": "__ne__", ">": "__gt__",
            ">=": "__ge__", "<": "__lt__", "<=": "__le__",
            "unary+": "__pos__", "unary-": "__neg__", "~": "__invert__",
        }

    def resolve_operation_type_name(self, op: str, other_name: Optional[str]) -> Optional[str]:
        if other_name is None:
            if op in ("-", "+", "unary-", "unary+", "~"):
                return "int"
            if op == "not":
                return "bool"
            return None
        if op in ("+", "-", "*", "/", "//", "%", "&", "|", "^", "<<", ">>"):
            if other_name == "int":
                return "int"
            if other_name == "float":
                return "float"
            if op == "*" and other_name == "str":
                # 字符串重复（int * str，运行期合法——Python 同语义）
                return "str"
        if op == "**":
            if other_name == "int":
                return "int"
            if other_name == "float":
                return "float"
        if op in ("==", "!="):
            # 相等/不等跨类型合法（运行期返回 False/True，Python 语义）
            return "bool"
        if op in (">", ">=", "<", "<="):
            # 排序比较仅数值族内合法（运行期跨型 TypeError）；
            # bool 静态类型为独立基名（运行期 int 语义，可相互排序）
            if other_name in ("int", "float", "bool"):
                return "bool"
            return None
        return None

    def can_convert_from(self, source_type_name: str) -> bool:
        return source_type_name in ("str", "float", "bool", "int")

    def parse_value(self, raw_value: str) -> Any:
        m = re.search(r"-?\d+", raw_value)
        if m:
            return int(m.group())
        raise ValueError(f"No integer found in response: {raw_value}")

    def from_prompt(self, raw_response: str, spec: Optional["IbSpec"] = None) -> Tuple[bool, Any]:
        m = re.search(r"-?\d+", raw_response.strip())
        if m:
            return (True, int(m.group()))
        return (False, f"无法从 '{raw_response}' 解析整数。请只返回一个整数，如: 42 或 -15")

    def __outputhint_prompt__(self, spec: Optional["IbSpec"] = None) -> str:
        return "请只返回一个整数，如: 42 或 -15，不要包含任何其他文字"

    def is_compatible(self, other: TypeRef) -> bool:
        return other.head == "int"


# ------------------------------------------------------------------ #
# float                                                               #
# ------------------------------------------------------------------ #

class FloatAxiom(BaseAxiom):
    has_operator_cap = True
    has_converter_cap = True
    has_parser_cap = True
    has_from_prompt_cap = True
    has_output_hint_cap = True

    @property
    def name(self) -> str:
        return "float"
        return True

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "to_bool": _m("to_bool", ret="bool"),
            "cast_to": _m("cast_to", params=["any"], ret="any"),
        }

    def get_operators(self) -> Dict[str, str]:
        return {
            "+": "__add__", "-": "__sub__", "*": "__mul__",
            "/": "__truediv__", "//": "__floordiv__", "%": "__mod__",
            "**": "__pow__",
            "==": "__eq__", "!=": "__ne__", ">": "__gt__",
            ">=": "__ge__", "<": "__lt__", "<=": "__le__",
            "unary+": "__pos__", "unary-": "__neg__",
        }

    def resolve_operation_type_name(self, op: str, other_name: Optional[str]) -> Optional[str]:
        if other_name is None:
            if op in ("-", "+", "unary-", "unary+"):
                return "float"
            if op == "not":
                return "bool"
            return None
        if op in ("+", "-", "*", "/", "//", "%"):
            if other_name in ("int", "float"):
                return "float"
        if op == "**":
            if other_name in ("int", "float"):
                return "float"
        if op in ("==", "!="):
            # 相等/不等跨类型合法（运行期返回 False/True，Python 语义）
            return "bool"
        if op in (">", ">=", "<", "<="):
            # 排序比较仅数值族内合法（float * str 无重复语义——不声明）
            if other_name in ("int", "float", "bool"):
                return "bool"
            return None
        return None

    def can_convert_from(self, source_type_name: str) -> bool:
        return source_type_name in ("str", "int", "bool", "float")

    def parse_value(self, raw_value: str) -> Any:
        m = re.search(r"-?\d+(?:\.\d+)?", raw_value)
        if m:
            return float(m.group())
        raise ValueError(f"No float found in response: {raw_value}")

    def from_prompt(self, raw_response: str, spec: Optional["IbSpec"] = None) -> Tuple[bool, Any]:
        m = re.search(r"-?\d+(?:\.\d+)?", raw_response.strip())
        if m:
            return (True, float(m.group()))
        return (False, f"无法从 '{raw_response}' 解析浮点数。请只返回一个数字，如: 3.14 或 -2.5")

    def __outputhint_prompt__(self, spec: Optional["IbSpec"] = None) -> str:
        return "请只返回一个数字，如: 3.14 或 -2.5，不要包含任何其他文字"

    def is_compatible(self, other: TypeRef) -> bool:
        return other.head == "float"


# ------------------------------------------------------------------ #
# bool                                                                #
# ------------------------------------------------------------------ #

class BoolAxiom(BaseAxiom):
    has_operator_cap = True
    has_converter_cap = True
    has_parser_cap = True
    has_from_prompt_cap = True
    has_output_hint_cap = True

    @property
    def name(self) -> str:
        return "bool"
        return True

    def get_parent_axiom_name(self) -> Optional[str]:
        return "int"

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "to_bool": _m("to_bool", ret="bool"),
            "cast_to": _m("cast_to", params=["any"], ret="any"),
        }

    def get_operators(self) -> Dict[str, str]:
        return {
            "==": "__eq__", "!=": "__ne__",
            "&": "__and__", "|": "__or__", "^": "__xor__",
            "unary!": "__not__",
        }

    def resolve_operation_type_name(self, op: str, other_name: Optional[str]) -> Optional[str]:
        if other_name is None:
            if op in ("not", "unary!"):
                return "bool"
            return None
        if op in ("&", "|", "^"):
            if other_name in ("bool", "int"):
                return "bool"
        if op in ("==", "!="):
            return "bool"
        if op in ("+", "-", "*", "//"):
            if other_name in ("bool", "int"):
                return "int"
            if other_name == "float":
                return "float"
            if op == "*" and other_name == "str":
                # 字符串重复（bool * str，运行期 int 语义合法）
                return "str"
        if op in (">", ">=", "<", "<="):
            # 排序比较仅数值族内合法（bool 运行期 int 语义）
            if other_name in ("bool", "int", "float"):
                return "bool"
            return None
        return None

    def can_convert_from(self, source_type_name: str) -> bool:
        return True  # almost everything can be truthy-tested

    def parse_value(self, raw_value: str) -> Any:
        val = raw_value.strip().lower()
        if val in ("true", "yes", "1"):
            return True
        if val in ("false", "no", "0"):
            return False
        raise ValueError(f"No boolean found in response: {raw_value}")

    def from_prompt(self, raw_response: str, spec: Optional["IbSpec"] = None) -> Tuple[bool, Any]:
        val = raw_response.strip().lower()
        if val in ("true", "yes", "1"):
            return (True, True)
        if val in ("false", "no", "0"):
            return (True, False)
        return (False, f"无法从 '{raw_response}' 解析布尔值。请返回 true/false、yes/no 或 1/0")

    def __outputhint_prompt__(self, spec: Optional["IbSpec"] = None) -> str:
        return "请返回一个布尔值：true/false、yes/no 或 1/0，不要包含任何其他文字"

    def is_compatible(self, other: TypeRef) -> bool:
        return other.head in ("bool", "int")
