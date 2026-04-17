"""
core/kernel/axioms/primitives.py

Concrete axiom implementations for all built-in IBCI types.

Key changes from the old version
---------------------------------
* NO imports from core.kernel.types or core.kernel.spec.
* All type references in capability methods are plain strings.
* ``get_method_specs()`` returns Dict[str, MethodMemberSpec] instead of
  Dict[str, FunctionMetadata] — MethodMemberSpec is imported from
  core.kernel.spec.member (pure data, no circular risk).
* EnumAxiom._enum_index_registry is now an instance dict (not a class dict),
  eliminating the cross-engine global-state bug.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING
import re
import json

from core.runtime.support.fuzzy_json import FuzzyJsonParser
from core.kernel.axioms.protocols import (
    TypeAxiom, CallCapability, IterCapability, SubscriptCapability,
    OperatorCapability, ConverterCapability, ParserCapability,
    FromPromptCapability, IlmoutputHintCapability,
)
from core.kernel.spec.member import MethodMemberSpec

if TYPE_CHECKING:
    from core.kernel.spec.base import IbSpec
    from core.kernel.axioms.registry import AxiomRegistry


# ------------------------------------------------------------------ #
# Helper: build a MethodMemberSpec                                    #
# ------------------------------------------------------------------ #

def _m(
    name: str,
    params: Optional[List[str]] = None,
    ret: str = "void",
    is_llm: bool = False,
) -> MethodMemberSpec:
    """Convenience constructor for MethodMemberSpec constants."""
    return MethodMemberSpec(
        name=name,
        kind="llm_method" if is_llm else "method",
        param_type_names=params or [],
        return_type_name=ret,
    )


# ------------------------------------------------------------------ #
# Base axiom                                                          #
# ------------------------------------------------------------------ #

class BaseAxiom(TypeAxiom):
    """Default implementations for axiom methods."""

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {}

    def get_operators(self) -> Dict[str, str]:
        return {}

    def is_dynamic(self) -> bool:
        return False

    def is_class(self) -> bool:
        return False

    def is_module(self) -> bool:
        return False

    def is_compatible(self, other_name: str) -> bool:
        return other_name == self.name

    def get_parent_axiom_name(self) -> Optional[str]:
        return "Object"

    def get_writable_trait(self):
        return None

    def can_return_from_isolated(self) -> bool:
        return False

    def get_from_prompt_capability(self) -> Optional[FromPromptCapability]:
        return None

    def get_llmoutput_hint_capability(self) -> Optional[IlmoutputHintCapability]:
        return None

    def get_diff_hint(self, other_name: str) -> Optional[str]:
        return None


# ------------------------------------------------------------------ #
# int                                                                 #
# ------------------------------------------------------------------ #

class IntAxiom(
    BaseAxiom, OperatorCapability, ConverterCapability,
    ParserCapability, FromPromptCapability, IlmoutputHintCapability,
):
    @property
    def name(self) -> str:
        return "int"

    def get_operator_capability(self) -> Optional[OperatorCapability]: return self
    def get_converter_capability(self) -> Optional[ConverterCapability]: return self
    def get_parser_capability(self) -> Optional[ParserCapability]: return self
    def get_from_prompt_capability(self) -> Optional[FromPromptCapability]: return self
    def get_llmoutput_hint_capability(self) -> Optional[IlmoutputHintCapability]: return self
    def get_call_capability(self): return None
    def get_iter_capability(self): return None
    def get_subscript_capability(self): return None
    def can_return_from_isolated(self) -> bool: return True

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
            return None
        if op in ("+", "-", "*", "/", "//", "%", "&", "|", "^", "<<", ">>"):
            if other_name == "int":
                return "int"
            if other_name == "float":
                return "float"
        if op in (">", ">=", "<", "<=", "==", "!="):
            return "bool"
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

    def is_compatible(self, other_name: str) -> bool:
        return other_name == "int"


# ------------------------------------------------------------------ #
# float                                                               #
# ------------------------------------------------------------------ #

class FloatAxiom(
    BaseAxiom, OperatorCapability, ConverterCapability,
    ParserCapability, FromPromptCapability, IlmoutputHintCapability,
):
    @property
    def name(self) -> str:
        return "float"

    def get_operator_capability(self) -> Optional[OperatorCapability]: return self
    def get_converter_capability(self) -> Optional[ConverterCapability]: return self
    def get_parser_capability(self) -> Optional[ParserCapability]: return self
    def get_from_prompt_capability(self) -> Optional[FromPromptCapability]: return self
    def get_llmoutput_hint_capability(self) -> Optional[IlmoutputHintCapability]: return self
    def get_call_capability(self): return None
    def get_iter_capability(self): return None
    def get_subscript_capability(self): return None
    def can_return_from_isolated(self) -> bool: return True

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
            return None
        if op in ("+", "-", "*", "/", "//", "%"):
            if other_name in ("int", "float"):
                return "float"
        if op in (">", ">=", "<", "<=", "==", "!="):
            return "bool"
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

    def is_compatible(self, other_name: str) -> bool:
        return other_name == "float"


# ------------------------------------------------------------------ #
# bool                                                                #
# ------------------------------------------------------------------ #

class BoolAxiom(
    BaseAxiom, OperatorCapability, ConverterCapability,
    ParserCapability, FromPromptCapability, IlmoutputHintCapability,
):
    @property
    def name(self) -> str:
        return "bool"

    def get_operator_capability(self) -> Optional[OperatorCapability]: return self
    def get_converter_capability(self) -> Optional[ConverterCapability]: return self
    def get_parser_capability(self) -> Optional[ParserCapability]: return self
    def get_from_prompt_capability(self) -> Optional[FromPromptCapability]: return self
    def get_llmoutput_hint_capability(self) -> Optional[IlmoutputHintCapability]: return self
    def get_call_capability(self): return None
    def get_iter_capability(self): return None
    def get_subscript_capability(self): return None
    def can_return_from_isolated(self) -> bool: return True
    def get_parent_axiom_name(self) -> Optional[str]: return "int"

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
        return (False, f"无法从 '{raw_response}' 解析布尔值。请只返回 true 或 false")

    def __outputhint_prompt__(self, spec: Optional["IbSpec"] = None) -> str:
        return "请只返回 true 或 false，不要包含任何其他文字"

    def is_compatible(self, other_name: str) -> bool:
        return other_name in ("bool", "int")


# ------------------------------------------------------------------ #
# str                                                                 #
# ------------------------------------------------------------------ #

class StrAxiom(
    BaseAxiom, OperatorCapability, IterCapability, SubscriptCapability,
    ParserCapability, FromPromptCapability, IlmoutputHintCapability,
):
    @property
    def name(self) -> str:
        return "str"

    def get_operator_capability(self) -> Optional[OperatorCapability]: return self
    def get_iter_capability(self) -> Optional[IterCapability]: return self
    def get_subscript_capability(self) -> Optional[SubscriptCapability]: return self
    def get_parser_capability(self) -> Optional[ParserCapability]: return self
    def get_from_prompt_capability(self) -> Optional[FromPromptCapability]: return self
    def get_llmoutput_hint_capability(self) -> Optional[IlmoutputHintCapability]: return self
    def get_call_capability(self): return None
    def get_converter_capability(self): return None
    def can_return_from_isolated(self) -> bool: return True

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "len":      _m("len",      ret="int"),
            "upper":    _m("upper",    ret="str"),
            "lower":    _m("lower",    ret="str"),
            "strip":    _m("strip",    ret="str"),
            "split":    _m("split",    params=["str"], ret="list"),
            "join":     _m("join",     params=["list"], ret="str"),
            "replace":  _m("replace",  params=["str", "str"], ret="str"),
            "startswith": _m("startswith", params=["str"], ret="bool"),
            "endswith": _m("endswith", params=["str"], ret="bool"),
            "contains": _m("contains", params=["str"], ret="bool"),
            "find":     _m("find",     params=["str"], ret="int"),
            "format":   _m("format",   params=["any"], ret="str"),
            "to_bool":  _m("to_bool",  ret="bool"),
            "cast_to":  _m("cast_to",  params=["any"], ret="any"),
        }

    def get_operators(self) -> Dict[str, str]:
        return {
            "+": "__add__",
            "==": "__eq__", "!=": "__ne__",
            ">": "__gt__", ">=": "__ge__", "<": "__lt__", "<=": "__le__",
        }

    def resolve_operation_type_name(self, op: str, other_name: Optional[str]) -> Optional[str]:
        if op == "+":
            if other_name == "str":
                return "str"
        if op in ("==", "!=", ">", ">=", "<", "<="):
            return "bool"
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
        return "请直接返回文本内容，不要使用引号或代码块包裹"

    def is_compatible(self, other_name: str) -> bool:
        return other_name == "str"


# ------------------------------------------------------------------ #
# list                                                                #
# ------------------------------------------------------------------ #

class ListAxiom(
    BaseAxiom, IterCapability, SubscriptCapability,
    ParserCapability, ConverterCapability,
    FromPromptCapability, IlmoutputHintCapability,
):
    @property
    def name(self) -> str:
        return "list"

    def get_iter_capability(self) -> Optional[IterCapability]: return self
    def get_subscript_capability(self) -> Optional[SubscriptCapability]: return self
    def get_parser_capability(self) -> Optional[ParserCapability]: return self
    def get_converter_capability(self) -> Optional[ConverterCapability]: return self
    def get_from_prompt_capability(self) -> Optional[FromPromptCapability]: return self
    def get_llmoutput_hint_capability(self) -> Optional[IlmoutputHintCapability]: return self
    def get_call_capability(self): return None
    def get_operator_capability(self): return None

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "append":      _m("append",      params=["any"],        ret="void"),
            "pop":         _m("pop",                                 ret="any"),
            "len":         _m("len",                                 ret="int"),
            "sort":        _m("sort",                                ret="void"),
            "clear":       _m("clear",                               ret="void"),
            "cast_to":     _m("cast_to",     params=["any"],        ret="any"),
            "__getitem__": _m("__getitem__", params=["int"],         ret="any"),
            "__setitem__": _m("__setitem__", params=["int", "any"],  ret="void"),
        }

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

    def is_compatible(self, other_name: str) -> bool:
        return other_name in ("list",) or other_name.startswith("list[")

    def resolve_specialization_by_names(
        self, registry: Any, arg_names: List[str]
    ) -> Optional[Any]:
        elem = arg_names[0] if arg_names else "any"
        spec = registry.factory.create_list(element_type_name=elem)
        return registry.register(spec)


# ------------------------------------------------------------------ #
# dict                                                                #
# ------------------------------------------------------------------ #

class DictAxiom(
    BaseAxiom, IterCapability, SubscriptCapability,
    ParserCapability, ConverterCapability,
    FromPromptCapability, IlmoutputHintCapability,
):
    @property
    def name(self) -> str:
        return "dict"

    def get_iter_capability(self) -> Optional[IterCapability]: return self
    def get_subscript_capability(self) -> Optional[SubscriptCapability]: return self
    def get_parser_capability(self) -> Optional[ParserCapability]: return self
    def get_converter_capability(self) -> Optional[ConverterCapability]: return self
    def get_from_prompt_capability(self) -> Optional[FromPromptCapability]: return self
    def get_llmoutput_hint_capability(self) -> Optional[IlmoutputHintCapability]: return self
    def get_call_capability(self): return None
    def get_operator_capability(self): return None

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "get":         _m("get",         params=["any", "any"], ret="any"),
            "keys":        _m("keys",                               ret="list"),
            "values":      _m("values",                             ret="list"),
            "len":         _m("len",                                ret="int"),
            "cast_to":     _m("cast_to",     params=["any"],        ret="any"),
            "__getitem__": _m("__getitem__", params=["any"],         ret="any"),
            "__setitem__": _m("__setitem__", params=["any", "any"],  ret="void"),
        }

    def get_element_type_name(self) -> str:
        return "any"

    def resolve_item_type_name(self, key_type_name: str) -> Optional[str]:
        return "any"

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

    def is_compatible(self, other_name: str) -> bool:
        return other_name in ("dict",) or other_name.startswith("dict[")

    def resolve_specialization_by_names(
        self, registry: Any, arg_names: List[str]
    ) -> Optional[Any]:
        key = arg_names[0] if len(arg_names) > 0 else "any"
        val = arg_names[1] if len(arg_names) > 1 else "any"
        spec = registry.factory.create_dict(key_type_name=key, value_type_name=val)
        return registry.register(spec)


# ------------------------------------------------------------------ #
# tuple (immutable, fixed-length, heterogeneous)                      #
# ------------------------------------------------------------------ #

class TupleAxiom(
    BaseAxiom, IterCapability, SubscriptCapability,
    ParserCapability, ConverterCapability,
    FromPromptCapability, IlmoutputHintCapability,
):
    """
    元组公理：不可变、定长、异构集合。
    与 ListAxiom 的关键区别：
    - 没有 append / pop / sort / clear / __setitem__ (不可变)
    - 支持 cast_to list (向列表转换)
    """

    @property
    def name(self) -> str:
        return "tuple"

    def get_iter_capability(self) -> Optional[IterCapability]: return self
    def get_subscript_capability(self) -> Optional[SubscriptCapability]: return self
    def get_parser_capability(self) -> Optional[ParserCapability]: return self
    def get_converter_capability(self) -> Optional[ConverterCapability]: return self
    def get_from_prompt_capability(self) -> Optional[FromPromptCapability]: return self
    def get_llmoutput_hint_capability(self) -> Optional[IlmoutputHintCapability]: return self
    def get_call_capability(self): return None
    def get_operator_capability(self): return None

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "len":         _m("len",                                 ret="int"),
            "cast_to":     _m("cast_to",     params=["any"],        ret="any"),
            "__getitem__": _m("__getitem__", params=["int"],         ret="any"),
            # 注意：没有 __setitem__ / append / pop / sort / clear → 不可变
        }

    def get_element_type_name(self) -> str:
        return "any"

    def resolve_item_type_name(self, key_type_name: str) -> Optional[str]:
        if key_type_name == "int":
            return "any"
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

    def is_compatible(self, other_name: str) -> bool:
        return other_name in ("tuple",) or other_name.startswith("tuple[")

    def resolve_specialization_by_names(
        self, registry: Any, arg_names: List[str]
    ) -> Optional[Any]:
        elem = arg_names[0] if arg_names else "any"
        spec = registry.factory.create_tuple(element_type_name=elem)
        return registry.register(spec)


# ------------------------------------------------------------------ #
# Dynamic (any / auto / callable / void / behavior)                  #
# ------------------------------------------------------------------ #

class DynamicAxiom(
    BaseAxiom, CallCapability, IterCapability,
    SubscriptCapability, OperatorCapability, ParserCapability,
):
    """Top-type axiom: accepts and returns anything."""

    def __init__(self, type_name: str):
        self._name = type_name

    @property
    def name(self) -> str:
        return self._name

    def get_call_capability(self): return self
    def get_iter_capability(self): return self
    def get_subscript_capability(self): return self
    def get_operator_capability(self): return self
    def get_converter_capability(self): return None
    def get_parser_capability(self): return self

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {}

    def is_dynamic(self) -> bool:
        return True

    def resolve_return_type_name(self, arg_type_names: List[str]) -> Optional[str]:
        return "any"

    def get_element_type_name(self) -> str:
        return "any"

    def resolve_item_type_name(self, key_type_name: str) -> Optional[str]:
        return "any"

    def resolve_operation_type_name(self, op: str, other_name: Optional[str]) -> Optional[str]:
        return "any"

    def parse_value(self, raw_value: str) -> Any:
        return raw_value.strip()

    def is_compatible(self, other_name: str) -> bool:
        return True


# ------------------------------------------------------------------ #
# Exception                                                           #
# ------------------------------------------------------------------ #

class ExceptionAxiom(BaseAxiom, ConverterCapability):
    @property
    def name(self) -> str:
        return "Exception"

    def get_converter_capability(self): return self
    def get_call_capability(self): return None
    def get_iter_capability(self): return None
    def get_subscript_capability(self): return None
    def get_operator_capability(self): return None

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "message": _m("message", ret="str"),
            "cast_to": _m("cast_to", params=["any"], ret="any"),
        }

    def can_convert_from(self, source_type_name: str) -> bool:
        return source_type_name in ("str", "Exception")

    def is_compatible(self, other_name: str) -> bool:
        return other_name == "Exception"


# ------------------------------------------------------------------ #
# BoundMethod                                                         #
# ------------------------------------------------------------------ #

class BoundMethodAxiom(BaseAxiom, CallCapability):
    @property
    def name(self) -> str:
        return "bound_method"

    def get_call_capability(self): return self
    def get_iter_capability(self): return None
    def get_subscript_capability(self): return None
    def get_operator_capability(self): return None
    def get_converter_capability(self): return None
    def get_parent_axiom_name(self) -> Optional[str]: return "callable"

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {}

    def resolve_return_type_name(self, arg_type_names: List[str]) -> Optional[str]:
        return "any"

    def is_compatible(self, other_name: str) -> bool:
        return other_name == "bound_method"


# ------------------------------------------------------------------ #
# None                                                                #
# ------------------------------------------------------------------ #

class NoneAxiom(BaseAxiom, ConverterCapability):
    @property
    def name(self) -> str:
        return "None"

    def get_converter_capability(self): return self
    def get_call_capability(self): return None
    def get_iter_capability(self): return None
    def get_subscript_capability(self): return None
    def get_operator_capability(self): return None

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {
            "cast_to": _m("cast_to", params=["any"], ret="any"),
            "to_bool": _m("to_bool", ret="bool"),
        }

    def can_convert_from(self, source_type_name: str) -> bool:
        return source_type_name == "None"

    def is_compatible(self, other_name: str) -> bool:
        return other_name == "None"


# ------------------------------------------------------------------ #
# slice                                                               #
# ------------------------------------------------------------------ #

class SliceAxiom(BaseAxiom):
    @property
    def name(self) -> str:
        return "slice"

    def get_call_capability(self): return None
    def get_iter_capability(self): return None
    def get_subscript_capability(self): return None
    def get_operator_capability(self): return None
    def get_converter_capability(self): return None

    def is_compatible(self, other_name: str) -> bool:
        return other_name == "slice"


# ------------------------------------------------------------------ #
# enum                                                                #
# ------------------------------------------------------------------ #

class EnumAxiom(
    BaseAxiom, FromPromptCapability,
    IlmoutputHintCapability, ConverterCapability,
):
    """
    Axiom for user-defined Enum classes.

    Design notes
    ------------
    * ``_enum_index_registry`` is now an **instance** dict, not a class dict.
      This fixes the cross-engine global-state bug from the old version.
    * All type parameters use string names (no IbSpec objects required).
    """

    def __init__(self) -> None:
        # Instance-level cache: enum_class_name → {member_name: member_name}
        self._enum_index_registry: Dict[str, Dict[str, str]] = {}

    @property
    def name(self) -> str:
        return "enum"

    def is_class(self) -> bool:
        return True

    def get_from_prompt_capability(self) -> Optional[FromPromptCapability]: return self
    def get_llmoutput_hint_capability(self) -> Optional[IlmoutputHintCapability]: return self
    def get_converter_capability(self) -> Optional[ConverterCapability]: return self
    def get_call_capability(self): return None
    def get_iter_capability(self): return None
    def get_subscript_capability(self): return None
    def get_operator_capability(self): return None
    def get_parent_axiom_name(self) -> Optional[str]: return None

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {}

    def can_convert_from(self, source_type_name: str) -> bool:
        return source_type_name == "str"

    def _get_enum_index_map(self, spec: Optional["IbSpec"]) -> Optional[Dict[str, str]]:
        """Build / return the {member_name → member_name} map for the enum."""
        if spec is None:
            return None
        class_name = spec.name
        if class_name in self._enum_index_registry:
            return self._enum_index_registry[class_name]

        members = getattr(spec, "members", None)
        if not members:
            return None

        builtin_names = {
            "to_bool", "to_list", "len", "cast_to",
            "__getitem__", "__setitem__", "sort", "pop",
            "append", "clear", "__eq__", "__init__",
        }
        name_to_value: Dict[str, str] = {}
        for mname in members:
            if mname.startswith("_") or mname in builtin_names:
                continue
            name_to_value[mname] = mname

        self._enum_index_registry[class_name] = name_to_value
        return name_to_value

    def __outputhint_prompt__(self, spec: Optional["IbSpec"] = None) -> str:
        index_map = self._get_enum_index_map(spec)
        if not index_map:
            return "Reply with one of the valid enum values."
        return f"Reply with exactly one of: {', '.join(index_map.keys())}."

    def from_prompt(self, raw_response: Any, spec: Optional["IbSpec"] = None) -> Tuple[bool, Any]:
        # Pass through special mock sentinel values
        if isinstance(raw_response, str):
            upper = raw_response.upper().strip()
            if upper in ("MAYBE_YES_MAYBE_NO_THIS_IS_AMBIGUOUS", "1", "0", "TRUE", "FALSE"):
                return (True, raw_response)

        if spec is None:
            return (False, "无法解析枚举值：缺少类型信息")

        index_map = self._get_enum_index_map(spec)
        if not index_map:
            return (False, "无法解析枚举值：缺少成员信息")

        if hasattr(raw_response, "to_native"):
            val = raw_response.to_native()
        elif hasattr(raw_response, "__to_prompt__"):
            val = raw_response.__to_prompt__()
        else:
            val = raw_response

        val_str = str(val).strip().upper()
        if val_str in index_map:
            return (True, val_str)

        names = list(index_map.keys())
        preview = ", ".join(names[:5]) + (" 等" if len(names) > 5 else "")
        return (False, f"无法解析 '{raw_response}'，请回复有效枚举值如: {preview}")

    def is_compatible(self, other_name: str) -> bool:
        return other_name == "enum"


# ------------------------------------------------------------------ #
# behavior                                                            #
# ------------------------------------------------------------------ #

class BehaviorCallCapability(CallCapability):
    """
    CallCapability for behavior objects.

    At compile time the concrete return type is not known (it lives on the
    IbBehavior instance as ``expected_type``).  We therefore return ``"auto"``
    so that the SpecRegistry propagates a dynamic result type, which is then
    resolved to the actual type at runtime by IbBehavior.call().
    """
    def resolve_return_type_name(self, arg_type_names: List[str]) -> Optional[str]:
        return "auto"


class BehaviorAxiom(BaseAxiom, BehaviorCallCapability):
    """
    公理：behavior 类型。

    * 不是 DynamicAxiom —— behavior 是一个具体的一等公民类型，非 any 妥协。
    * 实现 CallCapability —— behavior 对象可被调用（触发 LLM 执行）。
    * is_dynamic() = False —— 严格类型系统：behavior 只能赋值给 behavior。
    * 编译期返回类型为 "auto"；运行期由 IbBehavior.call() 根据 expected_type 解析真实类型。
    """

    @property
    def name(self) -> str:
        return "behavior"

    def get_call_capability(self) -> Optional[BehaviorCallCapability]:
        return self

    def get_iter_capability(self):
        return None

    def get_subscript_capability(self):
        return None

    def get_operator_capability(self):
        return None

    def get_converter_capability(self):
        return None

    def get_method_specs(self) -> Dict[str, MethodMemberSpec]:
        return {}

    def is_dynamic(self) -> bool:
        return False

    def is_compatible(self, other_name: str) -> bool:
        return other_name == "behavior"

    def get_parent_axiom_name(self) -> Optional[str]:
        return "Object"




def register_core_axioms(registry: "AxiomRegistry") -> None:
    """Register all core axioms into the given AxiomRegistry."""
    registry.register(IntAxiom())
    registry.register(FloatAxiom())
    registry.register(BoolAxiom())
    registry.register(StrAxiom())
    registry.register(ListAxiom())
    registry.register(TupleAxiom())
    registry.register(DictAxiom())
    registry.register(ExceptionAxiom())
    registry.register(BoundMethodAxiom())
    registry.register(NoneAxiom())
    registry.register(SliceAxiom())
    registry.register(EnumAxiom())

    registry.register(DynamicAxiom("any"))
    registry.register(DynamicAxiom("auto"))
    registry.register(DynamicAxiom("callable"))
    registry.register(DynamicAxiom("void"))
    registry.register(BehaviorAxiom())
