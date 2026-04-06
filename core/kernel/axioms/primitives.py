from typing import Optional, List, Dict, TYPE_CHECKING, Any, Union, Tuple
import re
import json
from core.runtime.support.fuzzy_json import FuzzyJsonParser
from core.kernel.axioms.protocols import TypeAxiom, CallCapability, IterCapability, SubscriptCapability, OperatorCapability, ConverterCapability, ParserCapability, FromPromptCapability, IlmoutputHintCapability
from core.kernel.types.descriptors import (
    FunctionMetadata, ListMetadata, DictMetadata,
    INT_DESCRIPTOR, STR_DESCRIPTOR, FLOAT_DESCRIPTOR,
    BOOL_DESCRIPTOR, VOID_DESCRIPTOR, ANY_DESCRIPTOR
)

if TYPE_CHECKING:
    from core.kernel.types.descriptors import TypeDescriptor
    from core.kernel.axioms.registry import AxiomRegistry

# [Axiom Layer] 原子类型公理实现

class BaseAxiom(TypeAxiom):
    """公理基类，提供默认实现"""
    def get_methods(self) -> Dict[str, FunctionMetadata]: return {}
    def get_operators(self) -> Dict[str, str]: return {}

    def is_dynamic(self) -> bool: return False
    def is_class(self) -> bool: return False
    def is_module(self) -> bool: return False
    def is_compatible(self, other: 'TypeDescriptor') -> bool:
        return other._axiom and type(other._axiom) is type(self)

    def get_parent_axiom_name(self) -> Optional[str]: return "Object"

    def get_writable_trait(self) -> Optional['WritableTrait']: return None

    def resolve_specialization(self, registry: Any, args: List['TypeDescriptor']) -> 'TypeDescriptor':
        return registry.resolve(self.name)

    def get_diff_hint(self, other: 'TypeDescriptor') -> Optional[str]:
        return None

    def can_return_from_isolated(self) -> bool:
        return False

    def get_from_prompt_capability(self) -> Optional['FromPromptCapability']: return None
    def get_llmoutput_hint_capability(self) -> Optional['IlmoutputHintCapability']: return None

class IntAxiom(BaseAxiom, OperatorCapability, ConverterCapability, ParserCapability, FromPromptCapability, IlmoutputHintCapability):
    """int 类型的行为公理"""

    @property
    def name(self) -> str: return "int"

    def get_operator_capability(self) -> Optional[OperatorCapability]: return self
    def get_converter_capability(self) -> Optional[ConverterCapability]: return self
    def get_parser_capability(self) -> Optional[ParserCapability]: return self
    def get_from_prompt_capability(self) -> Optional['FromPromptCapability']: return self
    def get_llmoutput_hint_capability(self) -> Optional['IlmoutputHintCapability']: return self

    def can_return_from_isolated(self) -> bool: return True

    def get_methods(self) -> Dict[str, FunctionMetadata]:
        return {
            "to_bool": FunctionMetadata(name="to_bool", param_types=[], return_type=BOOL_DESCRIPTOR),
            "to_list": FunctionMetadata(name="to_list", param_types=[], return_type=ListMetadata(element_type=INT_DESCRIPTOR)),
            "cast_to": FunctionMetadata(name="cast_to", param_types=[ANY_DESCRIPTOR], return_type=ANY_DESCRIPTOR)
        }

    def get_operators(self) -> Dict[str, str]:
        return {
            "+": "__add__", "-": "__sub__", "*": "__mul__", "/": "__truediv__",
            "//": "__floordiv__", "%": "__mod__", "**": "__pow__",
            "&": "__and__", "|": "__or__", "^": "__xor__", "<<": "__lshift__", ">>": "__rshift__",
            "==": "__eq__", "!=": "__ne__", ">": "__gt__", ">=": "__ge__", "<": "__lt__", "<=": "__le__",
            "unary+": "__pos__", "unary-": "__neg__", "~": "__invert__"
        }

    def resolve_operation(self, op: str, other: Optional['TypeDescriptor']) -> Optional[Union['TypeDescriptor', str]]:
        if op in ('+', '-', '*', '/', '//', '%', '&', '|', '^', '<<', '>>'):
            if other:
                axiom_name = other.get_base_axiom_name()
                if axiom_name == "int":
                    return "int"
                if axiom_name == "float":
                    return "float"
        if op in ('>', '>=', '<', '<=', '==', '!='):
            return "bool"
        return None

    def can_convert_from(self, source: 'TypeDescriptor') -> bool:
        return source.get_base_axiom_name() in ("str", "float", "bool", "int")

    def parse_value(self, raw_value: str) -> Any:
        match = re.search(r'-?\d+', raw_value)
        if match:
            return int(match.group())
        raise ValueError(f"No integer found in response: {raw_value}")

    def from_prompt(self, raw_response: str) -> Tuple[bool, Any]:
        """从 LLM 返回中解析整数"""
        clean = raw_response.strip()
        match = re.search(r'-?\d+', clean)
        if match:
            return (True, int(match.group()))
        return (False, f"无法从 '{raw_response}' 解析整数。请只返回一个整数，如: 42 或 -15")

    def __llmoutput_hint__(self) -> str:
        return "请只返回一个整数，如: 42 或 -15，不要包含任何其他文字"

    def get_call_capability(self) -> Optional[CallCapability]: return None
    def get_iter_capability(self) -> Optional[IterCapability]: return None
    def get_subscript_capability(self) -> Optional[SubscriptCapability]: return None

    def can_return_from_isolated(self) -> bool: return True

    def is_compatible(self, other: 'TypeDescriptor') -> bool: 
        return other.get_base_axiom_name() == "int"


class FloatAxiom(BaseAxiom, OperatorCapability, ConverterCapability, ParserCapability, FromPromptCapability, IlmoutputHintCapability):
    """float 类型的行为公理"""

    @property
    def name(self) -> str: return "float"

    def get_operator_capability(self) -> Optional[OperatorCapability]: return self
    def get_converter_capability(self) -> Optional[ConverterCapability]: return self
    def get_parser_capability(self) -> Optional[ParserCapability]: return self
    def get_from_prompt_capability(self) -> Optional['FromPromptCapability']: return self
    def get_llmoutput_hint_capability(self) -> Optional['IlmoutputHintCapability']: return self

    def can_return_from_isolated(self) -> bool: return True

    def get_methods(self) -> Dict[str, FunctionMetadata]:
        return {
            "to_bool": FunctionMetadata(name="to_bool", param_types=[], return_type=BOOL_DESCRIPTOR),
            "cast_to": FunctionMetadata(name="cast_to", param_types=[ANY_DESCRIPTOR], return_type=ANY_DESCRIPTOR)
        }

    def get_operators(self) -> Dict[str, str]:
        return {
            "+": "__add__", "-": "__sub__", "*": "__mul__", "/": "__truediv__",
            "//": "__floordiv__", "%": "__mod__", "**": "__pow__",
            "==": "__eq__", "!=": "__ne__", ">": "__gt__", ">=": "__ge__", "<": "__lt__", "<=": "__le__",
            "unary+": "__pos__", "unary-": "__neg__"
        }

    def resolve_operation(self, op: str, other: Optional['TypeDescriptor']) -> Optional[Union['TypeDescriptor', str]]:
        if op in ('+', '-', '*', '/', '//', '%'):
            if other and other.get_base_axiom_name() in ("int", "float"):
                return "float"
        if op in ('>', '>=', '<', '<=', '==', '!='):
            return "bool"
        return None

    def can_convert_from(self, source: 'TypeDescriptor') -> bool:
        return source.get_base_axiom_name() in ("str", "int", "bool", "float")

    def parse_value(self, raw_value: str) -> Any:
        match = re.search(r'-?\d+(?:\.\d+)?', raw_value)
        if match:
            return float(match.group())
        raise ValueError(f"No float found in response: {raw_value}")

    def from_prompt(self, raw_response: str) -> Tuple[bool, Any]:
        """从 LLM 返回中解析浮点数"""
        clean = raw_response.strip()
        match = re.search(r'-?\d+(?:\.\d+)?', clean)
        if match:
            return (True, float(match.group()))
        return (False, f"无法从 '{raw_response}' 解析浮点数。请只返回一个数字，如: 3.14 或 -2.5")

    def __llmoutput_hint__(self) -> str:
        return "请只返回一个数字，如: 3.14 或 -2.5，不要包含任何其他文字"

    def get_call_capability(self) -> Optional[CallCapability]: return None
    def get_iter_capability(self) -> Optional[IterCapability]: return None
    def get_subscript_capability(self) -> Optional[SubscriptCapability]: return None

    def can_return_from_isolated(self) -> bool: return True

    def is_compatible(self, other: 'TypeDescriptor') -> bool:
        return other.get_base_axiom_name() == "float"


class BoolAxiom(BaseAxiom, OperatorCapability, ConverterCapability, ParserCapability, FromPromptCapability, IlmoutputHintCapability):
    """bool 类型的行为公理"""

    @property
    def name(self) -> str: return "bool"

    def get_parent_axiom_name(self) -> Optional[str]: return "int"

    def get_operator_capability(self) -> Optional[OperatorCapability]: return self
    def get_converter_capability(self) -> Optional[ConverterCapability]: return self
    def get_parser_capability(self) -> Optional[ParserCapability]: return self
    def get_from_prompt_capability(self) -> Optional['FromPromptCapability']: return self
    def get_llmoutput_hint_capability(self) -> Optional['IlmoutputHintCapability']: return self

    def get_methods(self) -> Dict[str, FunctionMetadata]:
        return {}

    def get_operators(self) -> Dict[str, str]:
        return {
            "&": "__and__", "|": "__or__", "^": "__xor__", "and": "__and__", "or": "__or__",
            "==": "__eq__", "!=": "__ne__",
            "not": "__not__"
        }

    def resolve_operation(self, op: str, other: Optional['TypeDescriptor']) -> Optional[Union['TypeDescriptor', str]]:
        if op in ('&', '|', '^', 'and', 'or'):
            if other and other.get_base_axiom_name() == "bool":
                return "bool"
        if op in ('==', '!='):
            return "bool"
        return None

    def can_convert_from(self, source: 'TypeDescriptor') -> bool:
        return source.get_base_axiom_name() in ("int", "str", "bool")

    def parse_value(self, raw_value: str) -> Any:
        val = raw_value.strip().lower()

        if val in ("true", "1", "yes", "on"): return True
        if val in ("false", "0", "no", "off"): return False

        true_pattern = r'\b(true|yes|1|on)\b'
        false_pattern = r'\b(false|no|0|off)\b'

        if re.search(true_pattern, val): return True
        if re.search(false_pattern, val): return False

        raise ValueError(f"No boolean found in response: {raw_value}")

    def from_prompt(self, raw_response: str) -> Tuple[bool, Any]:
        """从 LLM 返回中解析布尔值"""
        val = raw_response.strip().lower()

        if val in ("true", "1", "yes", "on"):
            return (True, True)
        if val in ("false", "0", "no", "off"):
            return (True, False)

        true_pattern = r'\b(true|yes|1|on)\b'
        false_pattern = r'\b(false|no|0|off)\b'

        if re.search(true_pattern, val):
            return (True, True)
        if re.search(false_pattern, val):
            return (True, False)

        return (False, f"无法从 '{raw_response}' 解析布尔值。请明确回复: 1 表示是/true/yes，0 表示否/false/no")

    def __llmoutput_hint__(self) -> str:
        return "请只回复 1 表示是，0 表示否，不要包含任何其他文字"

    def get_call_capability(self) -> Optional[CallCapability]: return None
    def get_iter_capability(self) -> Optional[IterCapability]: return None
    def get_subscript_capability(self) -> Optional[SubscriptCapability]: return None

    def can_return_from_isolated(self) -> bool: return True

    def is_compatible(self, other: 'TypeDescriptor') -> bool:
        return other.get_base_axiom_name() == "bool"


class StrAxiom(BaseAxiom, OperatorCapability, IterCapability, SubscriptCapability, ParserCapability, FromPromptCapability, IlmoutputHintCapability):
    """str 类型的行为公理"""

    @property
    def name(self) -> str: return "str"

    def get_diff_hint(self, other: 'TypeDescriptor') -> Optional[str]:
        if other.get_base_axiom_name() == "int":
            return "Use .cast_to(int) or int(s) to convert string to integer."
        return None

    def get_operator_capability(self) -> Optional[OperatorCapability]: return self
    def get_iter_capability(self) -> Optional[IterCapability]: return self
    def get_subscript_capability(self) -> Optional[SubscriptCapability]: return self
    def get_parser_capability(self) -> Optional[ParserCapability]: return self
    def get_from_prompt_capability(self) -> Optional['FromPromptCapability']: return self
    def get_llmoutput_hint_capability(self) -> Optional['IlmoutputHintCapability']: return self

    def get_methods(self) -> Dict[str, FunctionMetadata]:
        return {
            "len": FunctionMetadata(name="len", param_types=[], return_type=INT_DESCRIPTOR),
            "to_bool": FunctionMetadata(name="to_bool", param_types=[], return_type=BOOL_DESCRIPTOR),
            "cast_to": FunctionMetadata(name="cast_to", param_types=[ANY_DESCRIPTOR], return_type=ANY_DESCRIPTOR),
            "upper": FunctionMetadata(name="upper", param_types=[], return_type=STR_DESCRIPTOR),
            "lower": FunctionMetadata(name="lower", param_types=[], return_type=STR_DESCRIPTOR),
            "strip": FunctionMetadata(name="strip", param_types=[], return_type=STR_DESCRIPTOR),
            "split": FunctionMetadata(name="split", param_types=[STR_DESCRIPTOR], return_type=ListMetadata(element_type=STR_DESCRIPTOR)),
            "is_empty": FunctionMetadata(name="is_empty", param_types=[], return_type=BOOL_DESCRIPTOR),
            "find": FunctionMetadata(name="find", param_types=[STR_DESCRIPTOR], return_type=INT_DESCRIPTOR),
            "find_last": FunctionMetadata(name="find_last", param_types=[STR_DESCRIPTOR], return_type=INT_DESCRIPTOR),
            "contains": FunctionMetadata(name="contains", param_types=[STR_DESCRIPTOR], return_type=BOOL_DESCRIPTOR),
        }

    def get_operators(self) -> Dict[str, str]:
        return {
            "+": "__add__", "==": "__eq__", "!=": "__ne__"
        }

    def resolve_operation(self, op: str, other: Optional['TypeDescriptor']) -> Optional[Union['TypeDescriptor', str]]:
        if op == '+':
            if other and other.get_base_axiom_name() == "str":
                return "str"
        if op in ('==', '!='):
            return "bool"
        return None

    def get_element_type(self) -> 'TypeDescriptor':
        return STR_DESCRIPTOR

    def resolve_item(self, key: 'TypeDescriptor') -> Optional['TypeDescriptor']:
        if key.get_base_axiom_name() == "int":
            return STR_DESCRIPTOR
        return None

    def parse_value(self, raw_value: str) -> Any:
        clean_res = raw_value.strip()
        code_block_match = re.search(r'```(?:json|text)?\s*([\s\S]*?)\s*```', clean_res)
        if code_block_match:
            return code_block_match.group(1).strip()
        return clean_res

    def from_prompt(self, raw_response: str) -> Tuple[bool, Any]:
        """从 LLM 返回中解析字符串"""
        return (True, self.parse_value(raw_response))

    def __llmoutput_hint__(self) -> str:
        return "请直接返回文本内容，不要使用引号或代码块包裹"

    def get_call_capability(self) -> Optional[CallCapability]: return None
    def get_converter_capability(self) -> Optional[ConverterCapability]: return None
    def is_compatible(self, other: 'TypeDescriptor') -> bool:
        return other.get_base_axiom_name() == "str"


class ListAxiom(BaseAxiom, IterCapability, SubscriptCapability, ParserCapability, ConverterCapability, FromPromptCapability, IlmoutputHintCapability):
    """list 类型的行为公理"""

    @property
    def name(self) -> str: return "list"

    def get_iter_capability(self) -> Optional[IterCapability]: return self
    def get_subscript_capability(self) -> Optional[SubscriptCapability]: return self
    def get_parser_capability(self) -> Optional[ParserCapability]: return self
    def get_converter_capability(self) -> Optional[ConverterCapability]: return self
    def get_from_prompt_capability(self) -> Optional['FromPromptCapability']: return self
    def get_llmoutput_hint_capability(self) -> Optional['IlmoutputHintCapability']: return self

    def get_methods(self) -> Dict[str, FunctionMetadata]:
        return {
            "append": FunctionMetadata(name="append", param_types=[ANY_DESCRIPTOR], return_type=VOID_DESCRIPTOR),
            "pop": FunctionMetadata(name="pop", param_types=[], return_type=ANY_DESCRIPTOR),
            "len": FunctionMetadata(name="len", param_types=[], return_type=INT_DESCRIPTOR),
            "sort": FunctionMetadata(name="sort", param_types=[], return_type=VOID_DESCRIPTOR),
            "clear": FunctionMetadata(name="clear", param_types=[], return_type=VOID_DESCRIPTOR),
            "cast_to": FunctionMetadata(name="cast_to", param_types=[ANY_DESCRIPTOR], return_type=ANY_DESCRIPTOR),
            "__getitem__": FunctionMetadata(name="__getitem__", param_types=[INT_DESCRIPTOR], return_type=ANY_DESCRIPTOR),
            "__setitem__": FunctionMetadata(name="__setitem__", param_types=[INT_DESCRIPTOR, ANY_DESCRIPTOR], return_type=VOID_DESCRIPTOR)
        }

    def get_element_type(self) -> 'TypeDescriptor':
        return None

    def resolve_specialization(self, registry: Any, args: List['TypeDescriptor']) -> 'TypeDescriptor':
        element_type = args[0] if args else ANY_DESCRIPTOR
        desc = registry.factory.create_list(element_type)
        registry.register(desc)
        return desc

    def resolve_item(self, key: 'TypeDescriptor') -> Optional['TypeDescriptor']:
        if key.get_base_axiom_name() == "int":
            return None
        return None

    def parse_value(self, raw_value: str) -> Any:
        try:
            return FuzzyJsonParser.parse(raw_value, expected_type="list")
        except ValueError as e:
            raise ValueError(f"No valid JSON list found in response: {raw_value}. Error: {str(e)}")

    def from_prompt(self, raw_response: str) -> Tuple[bool, Any]:
        """从 LLM 返回中解析列表"""
        try:
            return (True, FuzzyJsonParser.parse(raw_response, expected_type="list"))
        except ValueError:
            return (False, f"无法从 '{raw_response}' 解析 JSON 数组。请返回一个 JSON 数组，如: [1, 2, 3]")

    def __llmoutput_hint__(self) -> str:
        return "请返回一个 JSON 数组，如: [1, 2, 3]，不要包含任何其他文字"

    def get_call_capability(self) -> Optional[CallCapability]: return None
    def get_operator_capability(self) -> Optional[OperatorCapability]: return None
    def get_converter_capability(self) -> Optional[ConverterCapability]: return None
    def is_compatible(self, other: 'TypeDescriptor') -> bool:
        return other.get_base_axiom_name() == "list"


class DictAxiom(BaseAxiom, IterCapability, SubscriptCapability, ParserCapability, ConverterCapability, FromPromptCapability, IlmoutputHintCapability):
    """dict 类型的行为公理"""

    @property
    def name(self) -> str: return "dict"

    def get_iter_capability(self) -> Optional[IterCapability]: return self
    def get_subscript_capability(self) -> Optional[SubscriptCapability]: return self
    def get_parser_capability(self) -> Optional[ParserCapability]: return self
    def get_converter_capability(self) -> Optional[ConverterCapability]: return self
    def get_from_prompt_capability(self) -> Optional['FromPromptCapability']: return self
    def get_llmoutput_hint_capability(self) -> Optional['IlmoutputHintCapability']: return self

    def get_methods(self) -> Dict[str, FunctionMetadata]:
        return {
            "get": FunctionMetadata(name="get", param_types=[ANY_DESCRIPTOR, ANY_DESCRIPTOR], return_type=ANY_DESCRIPTOR),
            "keys": FunctionMetadata(name="keys", param_types=[], return_type=ListMetadata(element_type=ANY_DESCRIPTOR)),
            "values": FunctionMetadata(name="values", param_types=[], return_type=ListMetadata(element_type=ANY_DESCRIPTOR)),
            "len": FunctionMetadata(name="len", param_types=[], return_type=INT_DESCRIPTOR),
            "cast_to": FunctionMetadata(name="cast_to", param_types=[ANY_DESCRIPTOR], return_type=ANY_DESCRIPTOR),
            "__getitem__": FunctionMetadata(name="__getitem__", param_types=[ANY_DESCRIPTOR], return_type=ANY_DESCRIPTOR),
            "__setitem__": FunctionMetadata(name="__setitem__", param_types=[ANY_DESCRIPTOR, ANY_DESCRIPTOR], return_type=VOID_DESCRIPTOR)
        }

    def get_element_type(self) -> 'TypeDescriptor':
        return None

    def resolve_specialization(self, registry: Any, args: List['TypeDescriptor']) -> 'TypeDescriptor':
        key_type = args[0] if len(args) > 0 else ANY_DESCRIPTOR
        val_type = args[1] if len(args) > 1 else ANY_DESCRIPTOR
        desc = registry.factory.create_dict(key_type, val_type)
        registry.register(desc)
        return desc

    def resolve_item(self, key: 'TypeDescriptor') -> Optional['TypeDescriptor']:
        return None

    def parse_value(self, raw_value: str) -> Any:
        try:
            return FuzzyJsonParser.parse(raw_value, expected_type="dict")
        except ValueError as e:
            raise ValueError(f"No valid JSON dict found in response: {raw_value}. Error: {str(e)}")

    def from_prompt(self, raw_response: str) -> Tuple[bool, Any]:
        """从 LLM 返回中解析字典"""
        try:
            return (True, FuzzyJsonParser.parse(raw_response, expected_type="dict"))
        except ValueError:
            return (False, f"无法从 '{raw_response}' 解析 JSON 对象。请返回一个 JSON 对象，如: {{'key': 'value'}}")

    def __llmoutput_hint__(self) -> str:
        return "请返回一个 JSON 对象，如: {'key': 'value'}，不要包含任何其他文字"

    def get_call_capability(self) -> Optional[CallCapability]: return None
    def get_operator_capability(self) -> Optional[OperatorCapability]: return None
    def get_converter_capability(self) -> Optional[ConverterCapability]: return None
    def is_compatible(self, other: 'TypeDescriptor') -> bool: 
        return other.get_base_axiom_name() == "dict"


class DynamicAxiom(BaseAxiom, CallCapability, IterCapability, SubscriptCapability, OperatorCapability, ParserCapability):
    """any/auto 类型的行为公理 (The Top Type)"""
    
    def __init__(self, name: str):
        self._name = name
        
    @property
    def name(self) -> str: return self._name
    
    # 动态类型具备所有能力，且返回自身
    def get_call_capability(self) -> Optional[CallCapability]: return self
    def get_iter_capability(self) -> Optional[IterCapability]: return self
    def get_subscript_capability(self) -> Optional[SubscriptCapability]: return self
    def get_operator_capability(self) -> Optional[OperatorCapability]: return self
    def get_converter_capability(self) -> Optional[ConverterCapability]: return None
    def get_parser_capability(self) -> Optional[ParserCapability]: return self

    def get_methods(self) -> Dict[str, FunctionMetadata]:
        return {} # Dynamic types accept any method call usually, but define none statically

    def is_dynamic(self) -> bool: return True

    def resolve_return(self, args: List['TypeDescriptor']) -> Optional[Union['TypeDescriptor', str]]: return self.name
    def get_element_type(self) -> Optional[Union['TypeDescriptor', str]]: return self.name
    def resolve_item(self, key: 'TypeDescriptor') -> Optional[Union['TypeDescriptor', str]]: return self.name
    def resolve_operation(self, op: str, other: Optional['TypeDescriptor']) -> Optional[Union['TypeDescriptor', str]]: return self.name
    
    def parse_value(self, raw_value: str) -> Any:
        # Any 类型默认按字符串处理
        return raw_value.strip()

    def is_compatible(self, other: 'TypeDescriptor') -> bool:
        return True

class ExceptionAxiom(BaseAxiom, ConverterCapability):
    """Exception 类型的行为公理"""
    
    @property
    def name(self) -> str: return "Exception"
    
    def get_converter_capability(self) -> Optional[ConverterCapability]: return self
    
    def get_methods(self) -> Dict[str, FunctionMetadata]:
        return {
            "message": FunctionMetadata(name="message", param_types=[], return_type=STR_DESCRIPTOR),
            "cast_to": FunctionMetadata(name="cast_to", param_types=[ANY_DESCRIPTOR], return_type=ANY_DESCRIPTOR)
        }

class BoundMethodAxiom(BaseAxiom, CallCapability):
    """ bound_method 类型的行为公理"""
    
    @property
    def name(self) -> str: return "bound_method"
    
    def get_parent_axiom_name(self) -> Optional[str]: return "callable"
    
    def get_call_capability(self) -> Optional[CallCapability]: return self
    
    def get_methods(self) -> Dict[str, FunctionMetadata]:
        return {} # Delegated to original function

    def resolve_return(self, args: List['TypeDescriptor']) -> Optional['TypeDescriptor']:
        return ANY_DESCRIPTOR

    def is_compatible(self, other: 'TypeDescriptor') -> bool:
        return other.get_base_axiom_name() == "bound_method"

class NoneAxiom(BaseAxiom, ConverterCapability):
    """None 类型的行为公理"""
    
    @property
    def name(self) -> str: return "None"
    
    def get_converter_capability(self) -> Optional[ConverterCapability]: return self
    
    def get_methods(self) -> Dict[str, FunctionMetadata]:
        return {
            "cast_to": FunctionMetadata(name="cast_to", param_types=[ANY_DESCRIPTOR], return_type=ANY_DESCRIPTOR),
            "to_bool": FunctionMetadata(name="to_bool", param_types=[], return_type=BOOL_DESCRIPTOR)
        }

    def is_compatible(self, other: 'TypeDescriptor') -> bool:
        return other.get_base_axiom_name() == "None"

class SliceAxiom(BaseAxiom):
    """slice 类型的行为公理"""
    @property
    def name(self) -> str: return "slice"
    
    def get_base_axiom_name(self) -> str: return "slice"

    def is_compatible(self, other: 'TypeDescriptor') -> bool: 
        return other.get_base_axiom_name() == "slice"

def register_core_axioms(registry: 'AxiomRegistry'):
    """[Factory] 向指定的公理注册表注册所有核心公理"""
    registry.register(IntAxiom())
    registry.register(SliceAxiom())
    registry.register(FloatAxiom())
    registry.register(BoolAxiom())
    registry.register(StrAxiom())
    registry.register(ListAxiom())
    registry.register(DictAxiom())
    registry.register(ExceptionAxiom())
    registry.register(BoundMethodAxiom())
    registry.register(NoneAxiom())
    
    registry.register(DynamicAxiom("any"))
    registry.register(DynamicAxiom("auto"))
    registry.register(DynamicAxiom("callable"))
    registry.register(DynamicAxiom("void"))
    registry.register(DynamicAxiom("behavior"))
