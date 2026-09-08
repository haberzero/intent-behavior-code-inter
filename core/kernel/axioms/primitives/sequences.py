"""
core/kernel/axioms/primitives/sequences.py

Collection / sequence axioms: str, list, dict, tuple.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from core.base.support.fuzzy_json import FuzzyJsonParser
from core.kernel.axioms.primitives.base import BaseAxiom, _m
from core.kernel.spec.type_ref import TypeRef
from core.kernel.spec.member import MethodMemberSpec

if TYPE_CHECKING:
    from core.kernel.spec.base import IbSpec


# ------------------------------------------------------------------ #
# str                                                                 #
# ------------------------------------------------------------------ #

class StrAxiom(BaseAxiom):
    has_operator_cap = True
    has_iter_cap = True
    has_subscript_cap = True
    has_parser_cap = True
    has_from_prompt_cap = True
    has_output_hint_cap = True  # 与 int/list/dict/tuple 一致（str 缺失 output_hint 能力）

    @property
    def name(self) -> str:
        return "str"
        return True

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "len":        _m("len",        ret="int"),
            "upper":      _m("upper",      ret="str"),
            "lower":      _m("lower",      ret="str"),
            "strip":      _m("strip",      ret="str"),
            "split":      _m("split",      params=["str"], ret="list"),
            "join":       _m("join",       params=["list"], ret="str"),
            "replace":    _m("replace",    params=["str", "str"], ret="str"),
            "startswith": _m("startswith", params=["str"], ret="bool"),
            "endswith":   _m("endswith",   params=["str"], ret="bool"),
            "contains":   _m("contains",   params=["str"], ret="bool"),
            "find":       _m("find",       params=["str", "int"], ret="int"),
            "rfind":      _m("rfind",      params=["str", "int"], ret="int"),
            "count":      _m("count",      params=["str", "int"], ret="int"),
            "is_empty":   _m("is_empty",   ret="bool"),
            "format":     _m("format",     params=["any"], ret="str"),
            "to_bool":    _m("to_bool",    ret="bool"),
            "cast_to":    _m("cast_to",    params=["any"], ret="any"),
        }

    def get_operators(self) -> Dict[str, str]:
        return {
            "+": "__add__",
            "*": "__mul__",
            "==": "__eq__", "!=": "__ne__",
            ">": "__gt__", ">=": "__ge__", "<": "__lt__", "<=": "__le__",
        }

    def resolve_operation_type_name(self, op: str, other_name: Optional[str]) -> Optional[str]:
        if other_name is None:
            if op == "not":
                return "bool"
            return None
        if op == "+":
            if other_name == "str":
                return "str"
            # str + llm_uncertain 已收紧。
            # 现在静态出现 `llm_uncertain` 操作数时按 SEM_TYPE_MISMATCH 处理，
            # 与运行期 `IbString.__add__` 抛 LLMParseError 的策略保持一致。
        if op == "*":
            if other_name in ("int", "any"):
                return "str"
        if op in ("==", "!="):
            # 相等/不等跨类型合法（运行期返回 False/True，Python 语义）
            return "bool"
        if op in (">", ">=", "<", "<="):
            # 排序比较仅 str 之间合法（运行期 _require_str_other 跨型报错）
            if other_name == "str":
                return "bool"
            return None
        return None

    def get_element_type_name(self) -> str:
        return "str"

    def resolve_item_type_name(self, key_type_name: str) -> Optional[str]:
        if key_type_name == "int":
            return "str"
        return None

    def parse_value(self, raw_value: str) -> Any:
        clean = raw_value.strip()
        m = re.search(r"```(?:json|text)?\s*([\s\S]*?)\s*```", clean)
        if m:
            return m.group(1).strip()
        return clean

    def from_prompt(self, raw_response: str, spec: Optional["IbSpec"] = None) -> Tuple[bool, Any]:
        return (True, self.parse_value(raw_response))

    def __outputhint_prompt__(self, spec: Optional["IbSpec"] = None) -> str:
        # str 与 int/list/dict/tuple 一致——提供 output_hint 能力。
        # 返回 str 的 LLM 输出格式约束（镜像 ListAxiom.__outputhint_prompt__ 模式）。
        return "请直接返回字符串内容，不要包含任何 Markdown 代码块或额外解释"

    def is_compatible(self, other: TypeRef) -> bool:
        return other.head == "str"


# ------------------------------------------------------------------ #
# list                                                                #
# ------------------------------------------------------------------ #

class ListAxiom(BaseAxiom):
    has_iter_cap = True
    has_subscript_cap = True
    has_operator_cap = True
    has_parser_cap = True
    has_converter_cap = True
    has_from_prompt_cap = True
    has_output_hint_cap = True

    @property
    def name(self) -> str:
        return "list"

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "append":        _m("append",        params=["any"],        ret="void", mutating=True),
            "insert":        _m("insert",         params=["int", "any"], ret="void", mutating=True),
            "remove":        _m("remove",         params=["any"],        ret="void", mutating=True),
            "pop":           _m("pop",                                   ret="any",  mutating=True),
            "index":         _m("index",          params=["any"],        ret="int"),
            "count":         _m("count",          params=["any"],        ret="int"),
            "contains":      _m("contains",       params=["any"],        ret="bool"),
            "len":           _m("len",                                   ret="int"),
            "sort":          _m("sort",                                  ret="void", mutating=True),
            "reverse":       _m("reverse",                               ret="void", mutating=True),
            "clear":         _m("clear",                                 ret="void", mutating=True),
            "cast_to":       _m("cast_to",        params=["any"],        ret="any"),
            "__getitem__":   _m("__getitem__",    params=["int"],        ret="any"),
            "__setitem__":   _m("__setitem__",    params=["int", "any"], ret="void", mutating=True),
        }

    def get_operators(self) -> Dict[str, str]:
        return {"+": "__add__", "*": "__mul__"}

    def resolve_operation_type_name(self, op: str, other_name: Optional[str]) -> Optional[str]:
        if other_name is None:
            if op == "not":
                return "bool"
            return None
        if op == "+" and other_name in ("list", "any"):
            return "list"
        if op == "*" and other_name in ("int", "any"):
            return "list"
        return None

    def get_element_type_name(self) -> str:
        return "any"

    def resolve_item_type_name(self, key_type_name: str) -> Optional[str]:
        if key_type_name == "int":
            return "any"
        return None

    def can_convert_from(self, source_type_name: str) -> bool:
        return source_type_name == "list"

    def parse_value(self, raw_value: str) -> Any:
        try:
            return FuzzyJsonParser.parse(raw_value, expected_type="list")
        except ValueError as e:
            raise ValueError(f"No valid JSON list found in response: {raw_value}. Error: {e}")

    def from_prompt(self, raw_response: str, spec: Optional["IbSpec"] = None) -> Tuple[bool, Any]:
        try:
            return (True, FuzzyJsonParser.parse(raw_response, expected_type="list"))
        except ValueError:
            return (False, f"无法从 '{raw_response}' 解析 JSON 数组。请返回一个 JSON 数组，如: [1, 2, 3]")

    def __outputhint_prompt__(self, spec: Optional["IbSpec"] = None) -> str:
        return "请返回一个 JSON 数组，如: [1, 2, 3]，不要包含任何其他文字"

    def is_compatible(self, other: TypeRef) -> bool:
        return other.head == "list"


# ------------------------------------------------------------------ #
# dict                                                                #
# ------------------------------------------------------------------ #

class DictAxiom(BaseAxiom):
    has_iter_cap = True
    has_subscript_cap = True
    has_operator_cap = True
    has_parser_cap = True
    has_converter_cap = True
    has_from_prompt_cap = True
    has_output_hint_cap = True

    @property
    def name(self) -> str:
        return "dict"

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "get":         _m("get",         params=["any", "any"], ret="any"),
            "pop":         _m("pop",         params=["any"],        ret="any",  mutating=True),
            "keys":        _m("keys",                               ret="list"),
            "values":      _m("values",                             ret="list"),
            "items":       _m("items",                              ret="list"),
            "update":      _m("update",      params=["any"],        ret="void", mutating=True),
            "len":         _m("len",                                ret="int"),
            "contains":    _m("contains",    params=["any"],        ret="bool"),
            "remove":      _m("remove",      params=["any"],        ret="void", mutating=True),
            "cast_to":     _m("cast_to",     params=["any"],        ret="any"),
            "__getitem__": _m("__getitem__", params=["any"],         ret="any"),
            "__setitem__": _m("__setitem__", params=["any", "any"],  ret="void", mutating=True),
        }

    def get_operators(self) -> Dict[str, str]:
        return {"not": "__not__"}

    def get_element_type_name(self) -> str:
        return "any"

    def resolve_item_type_name(self, key_type_name: str) -> Optional[str]:
        return "any"

    def resolve_operation_type_name(self, op: str, other_name: Optional[str]) -> Optional[str]:
        if op == "not" and other_name is None:
            return "bool"
        return None

    def can_convert_from(self, source_type_name: str) -> bool:
        return source_type_name == "dict"

    def parse_value(self, raw_value: str) -> Any:
        try:
            return FuzzyJsonParser.parse(raw_value, expected_type="dict")
        except ValueError as e:
            raise ValueError(f"No valid JSON dict found in response: {raw_value}. Error: {e}")

    def from_prompt(self, raw_response: str, spec: Optional["IbSpec"] = None) -> Tuple[bool, Any]:
        try:
            return (True, FuzzyJsonParser.parse(raw_response, expected_type="dict"))
        except ValueError:
            return (False, f"无法从 '{raw_response}' 解析 JSON 对象。请返回一个 JSON 对象，如: {{'key': 'value'}}")

    def __outputhint_prompt__(self, spec: Optional["IbSpec"] = None) -> str:
        return "请返回一个 JSON 对象，如: {'key': 'value'}，不要包含任何其他文字"

    def is_compatible(self, other: TypeRef) -> bool:
        return other.head == "dict"


# ------------------------------------------------------------------ #
# tuple (immutable, fixed-length, heterogeneous)                      #
# ------------------------------------------------------------------ #

class TupleAxiom(BaseAxiom):
    """
    元组公理：不可变、定长、异构集合。
    与 ListAxiom 的关键区别：
    - 没有 append / pop / sort / clear / __setitem__ (不可变)
    - 支持 cast_to list (向列表转换)
    """

    has_iter_cap = True
    has_subscript_cap = True
    has_operator_cap = True
    has_parser_cap = True
    has_converter_cap = True
    has_from_prompt_cap = True
    has_output_hint_cap = True

    @property
    def name(self) -> str:
        return "tuple"

    def get_operators(self) -> Dict[str, str]:
        return {"not": "__not__"}

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "len":         _m("len",                                 ret="int"),
            "cast_to":     _m("cast_to",     params=["any"],        ret="any"),
            "__getitem__": _m("__getitem__", params=["int"],         ret="any"),
        }

    def get_element_type_name(self) -> str:
        return "any"

    def resolve_item_type_name(self, key_type_name: str) -> Optional[str]:
        if key_type_name == "int":
            return "any"
        return None

    def resolve_operation_type_name(self, op: str, other_name: Optional[str]) -> Optional[str]:
        if op == "not" and other_name is None:
            return "bool"
        return None

    def can_convert_from(self, source_type_name: str) -> bool:
        return source_type_name in ("tuple", "list")

    def parse_value(self, raw_value: str) -> Any:
        try:
            result = FuzzyJsonParser.parse(raw_value, expected_type="list")
            return tuple(result) if isinstance(result, list) else result
        except ValueError as e:
            raise ValueError(f"No valid JSON array found for tuple: {raw_value}. Error: {e}")

    def from_prompt(self, raw_response: str, spec: Optional["IbSpec"] = None) -> Tuple[bool, Any]:
        try:
            parsed = FuzzyJsonParser.parse(raw_response, expected_type="list")
            return (True, tuple(parsed) if isinstance(parsed, list) else parsed)
        except ValueError:
            return (False, f"无法从 '{raw_response}' 解析 JSON 数组（元组）")

    def __outputhint_prompt__(self, spec: Optional["IbSpec"] = None) -> str:
        return "请返回一个 JSON 数组（将作为元组处理），如: [1, 2, 3]，不要包含任何其他文字"

    def is_compatible(self, other: TypeRef) -> bool:
        # 基础协变：所有特化 tuple[*] 都可赋值给裸 tuple；同名 spec 兼容。
        # 注意：不同位置元素的 tuple 之间默认不互相兼容（与 list[int]/list[str]
        # 不互兼容的方向一致，由 SpecRegistry 的 covariance 路径细化处理）。
        return other.head == "tuple"
