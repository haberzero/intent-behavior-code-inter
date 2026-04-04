from typing import Optional, List, Dict, TYPE_CHECKING, Any, Union
import re
import json
from core.runtime.support.fuzzy_json import FuzzyJsonParser
from core.kernel.axioms.protocols import TypeAxiom, CallCapability, IterCapability, SubscriptCapability, OperatorCapability, ConverterCapability, ParserCapability
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
    def get_operators(self) -> Dict[str, str]: return {} # 默认不支持运算符

    def is_dynamic(self) -> bool: return False
    def is_class(self) -> bool: return False
    def is_module(self) -> bool: return False
    def is_compatible(self, other: 'TypeDescriptor') -> bool: 
        return other._axiom and type(other._axiom) is type(self)
    
    def get_parent_axiom_name(self) -> Optional[str]: return "Object" # 默认继承自 Object
    
    def get_writable_trait(self) -> Optional['WritableTrait']: return None
    
    def resolve_specialization(self, registry: Any, args: List['TypeDescriptor']) -> 'TypeDescriptor':
        # 默认不支持特化，返回自身（原子类型）
        return registry.resolve(self.name)

    def get_diff_hint(self, other: 'TypeDescriptor') -> Optional[str]:
        return None

    def can_return_from_isolated(self) -> bool:
        return False

class IntAxiom(BaseAxiom, OperatorCapability, ConverterCapability, ParserCapability):
    """int 类型的行为公理"""
    
    @property
    def name(self) -> str: return "int"
    
    def get_operator_capability(self) -> Optional[OperatorCapability]: return self
    def get_converter_capability(self) -> Optional[ConverterCapability]: return self
    def get_parser_capability(self) -> Optional[ParserCapability]: return self

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
            # 一元运算符
            "unary+": "__pos__", "unary-": "__neg__", "~": "__invert__"
        }

    def resolve_operation(self, op: str, other: Optional['TypeDescriptor']) -> Optional[Union['TypeDescriptor', str]]:
        # [Strict Axiom] 仅依赖公理定义
        if op in ('+', '-', '*', '/', '//', '%', '&', '|', '^', '<<', '>>'):
            if other:
                axiom_name = other.get_base_axiom_name()
                if axiom_name == "int":
                    return "int" # int + int -> int
                if axiom_name == "float":
                    return "float" # int + float -> float
        if op in ('>', '>=', '<', '<=', '==', '!='):
            return "bool"
        return None

    def can_convert_from(self, source: 'TypeDescriptor') -> bool:
        return source.get_base_axiom_name() in ("str", "float", "bool", "int")

    def parse_value(self, raw_value: str) -> Any:
        # 从 LLM 结果中解析整数
        match = re.search(r'-?\d+', raw_value)
        if match:
            return int(match.group())
        raise ValueError(f"No integer found in response: {raw_value}")

    # Int 不具备调用、迭代、下标能力
    def get_call_capability(self) -> Optional[CallCapability]: return None
    def get_iter_capability(self) -> Optional[IterCapability]: return None
    def get_subscript_capability(self) -> Optional[SubscriptCapability]: return None

    def can_return_from_isolated(self) -> bool: return True

    def is_compatible(self, other: 'TypeDescriptor') -> bool: 
        return other.get_base_axiom_name() == "int"


class FloatAxiom(BaseAxiom, OperatorCapability, ConverterCapability, ParserCapability):
    """float 类型的行为公理"""
    
    @property
    def name(self) -> str: return "float"
    
    def get_operator_capability(self) -> Optional[OperatorCapability]: return self
    def get_converter_capability(self) -> Optional[ConverterCapability]: return self
    def get_parser_capability(self) -> Optional[ParserCapability]: return self

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
            # 一元运算符
            "unary+": "__pos__", "unary-": "__neg__"
        }

    def resolve_operation(self, op: str, other: Optional['TypeDescriptor']) -> Optional[Union['TypeDescriptor', str]]:
        if op in ('+', '-', '*', '/', '//', '%'):
            if other and other.get_base_axiom_name() in ("int", "float"):
                return "float" # float wins
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

    def get_call_capability(self) -> Optional[CallCapability]: return None
    def get_iter_capability(self) -> Optional[IterCapability]: return None
    def get_subscript_capability(self) -> Optional[SubscriptCapability]: return None

    def can_return_from_isolated(self) -> bool: return True

    def is_compatible(self, other: 'TypeDescriptor') -> bool: 
        return other.get_base_axiom_name() == "float"


class BoolAxiom(BaseAxiom, OperatorCapability, ConverterCapability, ParserCapability):
    """bool 类型的行为公理"""
    
    @property
    def name(self) -> str: return "bool"
    
    def get_parent_axiom_name(self) -> Optional[str]: return "int"
    
    def get_operator_capability(self) -> Optional[OperatorCapability]: return self
    def get_converter_capability(self) -> Optional[ConverterCapability]: return self
    def get_parser_capability(self) -> Optional[ParserCapability]: return self

    def get_methods(self) -> Dict[str, FunctionMetadata]:
        return {} # No specific methods for bool yet

    def get_operators(self) -> Dict[str, str]:
        return {
            "&": "__and__", "|": "__or__", "^": "__xor__", "and": "__and__", "or": "__or__",
            "==": "__eq__", "!=": "__ne__",
            # 一元运算符
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
        import re
        val = raw_value.strip().lower()
        
        # 1. 优先精确匹配
        if val in ("true", "1", "yes", "on"): return True
        if val in ("false", "0", "no", "off"): return False
        
        # 2. 使用正则边界匹配 (防止 "not true" 误匹配)
        # 同步 llm_executor 的健壮解析逻辑
        true_pattern = r'\b(true|yes|1|on)\b'
        false_pattern = r'\b(false|no|0|off)\b'
        
        if re.search(true_pattern, val): return True
        if re.search(false_pattern, val): return False
        
        raise ValueError(f"No boolean found in response: {raw_value}")

    def get_call_capability(self) -> Optional[CallCapability]: return None
    def get_iter_capability(self) -> Optional[IterCapability]: return None
    def get_subscript_capability(self) -> Optional[SubscriptCapability]: return None

    def can_return_from_isolated(self) -> bool: return True

    def is_compatible(self, other: 'TypeDescriptor') -> bool:
        return other.get_base_axiom_name() == "bool"


class StrAxiom(BaseAxiom, OperatorCapability, IterCapability, SubscriptCapability, ParserCapability):
    """str 类型的行为公理"""
    
    @property
    def name(self) -> str: return "str"
    
    def get_diff_hint(self, other: 'TypeDescriptor') -> Optional[str]:
        # 使用公理名称判定替代 identity 判定
        if other.get_base_axiom_name() == "int":
            return "Use .cast_to(int) or int(s) to convert string to integer."
        return None
    
    def get_operator_capability(self) -> Optional[OperatorCapability]: return self
    def get_iter_capability(self) -> Optional[IterCapability]: return self
    def get_subscript_capability(self) -> Optional[SubscriptCapability]: return self
    def get_parser_capability(self) -> Optional[ParserCapability]: return self

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
        # 移除可能的 Markdown 代码块包裹
        clean_res = raw_value.strip()
        code_block_match = re.search(r'```(?:json|text)?\s*([\s\S]*?)\s*```', clean_res)
        if code_block_match:
            return code_block_match.group(1).strip()
        return clean_res
        
    def get_call_capability(self) -> Optional[CallCapability]: return None
    def get_converter_capability(self) -> Optional[ConverterCapability]: return None
    def is_compatible(self, other: 'TypeDescriptor') -> bool: 
        return other.get_base_axiom_name() == "str"


class ListAxiom(BaseAxiom, IterCapability, SubscriptCapability, ParserCapability, ConverterCapability):
    """list 类型的行为公理"""
    
    @property
    def name(self) -> str: return "list"
    
    def get_iter_capability(self) -> Optional[IterCapability]: return self
    def get_subscript_capability(self) -> Optional[SubscriptCapability]: return self
    def get_parser_capability(self) -> Optional[ParserCapability]: return self
    def get_converter_capability(self) -> Optional[ConverterCapability]: return self

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
        # 泛型 List 的元素类型由 Descriptor 实例持有，Axiom 仅定义行为
        # 在这里返回 None 表示由 Descriptor 进一步处理，或者 Axiom 不知道具体类型
        return None 

    def resolve_specialization(self, registry: Any, args: List['TypeDescriptor']) -> 'TypeDescriptor':
        """实现列表泛型特化"""
        element_type = args[0] if args else ANY_DESCRIPTOR
        desc = registry.factory.create_list(element_type)
        registry.register(desc)
        return desc

    def resolve_item(self, key: 'TypeDescriptor') -> Optional['TypeDescriptor']:
        if key.get_base_axiom_name() == "int":
            return None # Delegate to descriptor
        return None

    def parse_value(self, raw_value: str) -> Any:
        try:
            return FuzzyJsonParser.parse(raw_value, expected_type="list")
        except ValueError as e:
            raise ValueError(f"No valid JSON list found in response: {raw_value}. Error: {str(e)}")

    def get_call_capability(self) -> Optional[CallCapability]: return None
    def get_operator_capability(self) -> Optional[OperatorCapability]: return None
    def get_converter_capability(self) -> Optional[ConverterCapability]: return None
    def is_compatible(self, other: 'TypeDescriptor') -> bool: 
        return other.get_base_axiom_name() == "list"


class DictAxiom(BaseAxiom, IterCapability, SubscriptCapability, ParserCapability, ConverterCapability):
    """dict 类型的行为公理"""
    
    @property
    def name(self) -> str: return "dict"

    def get_iter_capability(self) -> Optional[IterCapability]: return self
    def get_subscript_capability(self) -> Optional[SubscriptCapability]: return self
    def get_parser_capability(self) -> Optional[ParserCapability]: return self
    def get_converter_capability(self) -> Optional[ConverterCapability]: return self

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
        return None # Keys

    def resolve_specialization(self, registry: Any, args: List['TypeDescriptor']) -> 'TypeDescriptor':
        """实现字典泛型特化"""
        key_type = args[0] if len(args) > 0 else ANY_DESCRIPTOR
        val_type = args[1] if len(args) > 1 else ANY_DESCRIPTOR
        desc = registry.factory.create_dict(key_type, val_type)
        registry.register(desc)
        return desc

    def resolve_item(self, key: 'TypeDescriptor') -> Optional['TypeDescriptor']:
        return None # Values

    def parse_value(self, raw_value: str) -> Any:
        try:
            return FuzzyJsonParser.parse(raw_value, expected_type="dict")
        except ValueError as e:
            raise ValueError(f"No valid JSON dict found in response: {raw_value}. Error: {str(e)}")

    def get_call_capability(self) -> Optional[CallCapability]: return None
    def get_operator_capability(self) -> Optional[OperatorCapability]: return None
    def get_converter_capability(self) -> Optional[ConverterCapability]: return None
    def is_compatible(self, other: 'TypeDescriptor') -> bool: 
        return other.get_base_axiom_name() == "dict"


class DynamicAxiom(BaseAxiom, CallCapability, IterCapability, SubscriptCapability, OperatorCapability, ParserCapability):
    """Any/var 类型的行为公理 (The Top Type)"""
    
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

def register_core_axioms(registry: 'AxiomRegistry'):
    """[Factory] 向指定的公理注册表注册所有核心公理"""
    registry.register(IntAxiom())
    registry.register(FloatAxiom())
    registry.register(BoolAxiom())
    registry.register(StrAxiom())
    registry.register(ListAxiom())
    registry.register(DictAxiom())
    registry.register(ExceptionAxiom())
    registry.register(BoundMethodAxiom())
    registry.register(NoneAxiom())
    
    registry.register(DynamicAxiom("Any"))
    registry.register(DynamicAxiom("var"))
    registry.register(DynamicAxiom("callable"))
    registry.register(DynamicAxiom("void"))
    registry.register(DynamicAxiom("behavior"))
