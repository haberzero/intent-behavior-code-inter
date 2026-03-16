from typing import Optional, List, Dict, TYPE_CHECKING, Any, Union
import re
import json
from core.domain.axioms.protocols import TypeAxiom, CallCapability, IterCapability, SubscriptCapability, OperatorCapability, ConverterCapability, ParserCapability
from core.domain.types.descriptors import (
    FunctionMetadata, ListMetadata, DictMetadata, 
    INT_DESCRIPTOR, STR_DESCRIPTOR, FLOAT_DESCRIPTOR, 
    BOOL_DESCRIPTOR, VOID_DESCRIPTOR, ANY_DESCRIPTOR
)

if TYPE_CHECKING:
    from core.domain.types.descriptors import TypeDescriptor
    from core.domain.axioms.registry import AxiomRegistry

# [Axiom Layer] 原子类型公理实现

class BaseAxiom(TypeAxiom):
    """公理基类，提供默认实现"""
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
        # 默认没有特殊提示
        return None

class IntAxiom(BaseAxiom, OperatorCapability, ConverterCapability, ParserCapability):
    """int 类型的行为公理"""
    
    @property
    def name(self) -> str: return "int"
    
    def get_operator_capability(self) -> Optional[OperatorCapability]: return self
    def get_converter_capability(self) -> Optional[ConverterCapability]: return self
    def get_parser_capability(self) -> Optional[ParserCapability]: return self

    def get_methods(self) -> Dict[str, FunctionMetadata]:
        return {
            "to_bool": FunctionMetadata(name="to_bool", param_types=[], return_type=BOOL_DESCRIPTOR),
            "to_list": FunctionMetadata(name="to_list", param_types=[], return_type=ListMetadata(element_type=INT_DESCRIPTOR)),
            "cast_to": FunctionMetadata(name="cast_to", param_types=[ANY_DESCRIPTOR], return_type=ANY_DESCRIPTOR)
        }

    def resolve_operation(self, op: str, other: Optional['TypeDescriptor']) -> Optional[Union['TypeDescriptor', str]]:
        # [Strict Axiom] 仅依赖公理定义
        if op in ('+', '-', '*', '/', '//', '%', '&', '|', '^', '<<', '>>'):
            if other and other._axiom:
                if isinstance(other._axiom, IntAxiom):
                    return "int" # int + int -> int
                if isinstance(other._axiom, FloatAxiom):
                    return "float" # int + float -> float
        if op in ('>', '>=', '<', '<=', '==', '!='):
            return "bool"
        return None

    def can_convert_from(self, source: 'TypeDescriptor') -> bool:
        return source._axiom and isinstance(source._axiom, (StrAxiom, FloatAxiom, BoolAxiom, IntAxiom))

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
    def is_compatible(self, other: 'TypeDescriptor') -> bool: 
        return other._axiom and isinstance(other._axiom, IntAxiom)


class FloatAxiom(BaseAxiom, OperatorCapability, ConverterCapability, ParserCapability):
    """float 类型的行为公理"""
    
    @property
    def name(self) -> str: return "float"
    
    def get_operator_capability(self) -> Optional[OperatorCapability]: return self
    def get_converter_capability(self) -> Optional[ConverterCapability]: return self
    def get_parser_capability(self) -> Optional[ParserCapability]: return self

    def get_methods(self) -> Dict[str, FunctionMetadata]:
        return {
            "to_bool": FunctionMetadata(name="to_bool", param_types=[], return_type=BOOL_DESCRIPTOR),
            "cast_to": FunctionMetadata(name="cast_to", param_types=[ANY_DESCRIPTOR], return_type=ANY_DESCRIPTOR)
        }

    def resolve_operation(self, op: str, other: Optional['TypeDescriptor']) -> Optional[Union['TypeDescriptor', str]]:
        if op in ('+', '-', '*', '/', '//', '%'):
            if other and other._axiom and isinstance(other._axiom, (IntAxiom, FloatAxiom)):
                return "float" # float wins
        if op in ('>', '>=', '<', '<=', '==', '!='):
            return "bool"
        return None

    def can_convert_from(self, source: 'TypeDescriptor') -> bool:
        return source._axiom and isinstance(source._axiom, (StrAxiom, IntAxiom, BoolAxiom, FloatAxiom))

    def parse_value(self, raw_value: str) -> Any:
        match = re.search(r'-?\d+(?:\.\d+)?', raw_value)
        if match:
            return float(match.group())
        raise ValueError(f"No float found in response: {raw_value}")

    def get_call_capability(self) -> Optional[CallCapability]: return None
    def get_iter_capability(self) -> Optional[IterCapability]: return None
    def get_subscript_capability(self) -> Optional[SubscriptCapability]: return None
    def is_compatible(self, other: 'TypeDescriptor') -> bool: 
        return other._axiom and isinstance(other._axiom, FloatAxiom)


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

    def resolve_operation(self, op: str, other: Optional['TypeDescriptor']) -> Optional[Union['TypeDescriptor', str]]:
        if op in ('&', '|', '^', 'and', 'or'):
            if other and other._axiom and isinstance(other._axiom, BoolAxiom):
                return "bool"
        if op in ('==', '!='):
            return "bool"
        return None

    def can_convert_from(self, source: 'TypeDescriptor') -> bool:
        return source._axiom and isinstance(source._axiom, (IntAxiom, StrAxiom, BoolAxiom))

    def parse_value(self, raw_value: str) -> Any:
        val = raw_value.strip().lower()
        if val in ("true", "1", "yes", "on"): return True
        if val in ("false", "0", "no", "off"): return False
        # 尝试从文本中搜索
        if "true" in val: return True
        if "false" in val: return False
        raise ValueError(f"No boolean found in response: {raw_value}")

    def get_call_capability(self) -> Optional[CallCapability]: return None
    def get_iter_capability(self) -> Optional[IterCapability]: return None
    def get_subscript_capability(self) -> Optional[SubscriptCapability]: return None
    def is_compatible(self, other: 'TypeDescriptor') -> bool: 
        return other._axiom and isinstance(other._axiom, BoolAxiom)


class StrAxiom(BaseAxiom, OperatorCapability, IterCapability, SubscriptCapability, ParserCapability):
    """str 类型的行为公理"""
    
    @property
    def name(self) -> str: return "str"
    
    def get_diff_hint(self, other: 'TypeDescriptor') -> Optional[str]:
        if other.name == "int":
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
            "cast_to": FunctionMetadata(name="cast_to", param_types=[ANY_DESCRIPTOR], return_type=ANY_DESCRIPTOR)
        }

    def resolve_operation(self, op: str, other: Optional['TypeDescriptor']) -> Optional[Union['TypeDescriptor', str]]:
        if op == '+':
            if other and other._axiom and isinstance(other._axiom, StrAxiom):
                return "str"
        if op in ('==', '!='):
            return "bool"
        return None

    def get_element_type(self) -> 'TypeDescriptor':
        return None # Should return STR_DESCRIPTOR (self)

    def resolve_item(self, key: 'TypeDescriptor') -> Optional['TypeDescriptor']:
        if key._axiom and isinstance(key._axiom, IntAxiom):
            return None # Should return STR_DESCRIPTOR
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
        return other._axiom and isinstance(other._axiom, StrAxiom)


class ListAxiom(BaseAxiom, IterCapability, SubscriptCapability, ParserCapability):
    """list 类型的行为公理"""
    
    @property
    def name(self) -> str: return "list"
    
    def get_diff_hint(self, other: 'TypeDescriptor') -> Optional[str]:
        if other.name == "str":
            return "Did you forget to join the list into a string?"
        return None
    
    def get_iter_capability(self) -> Optional[IterCapability]: return self
    def get_subscript_capability(self) -> Optional[SubscriptCapability]: return self
    def get_parser_capability(self) -> Optional[ParserCapability]: return self

    def get_methods(self) -> Dict[str, FunctionMetadata]:
        return {
            "append": FunctionMetadata(name="append", param_types=[ANY_DESCRIPTOR], return_type=VOID_DESCRIPTOR),
            "pop": FunctionMetadata(name="pop", param_types=[], return_type=ANY_DESCRIPTOR),
            "len": FunctionMetadata(name="len", param_types=[], return_type=INT_DESCRIPTOR),
            "sort": FunctionMetadata(name="sort", param_types=[], return_type=VOID_DESCRIPTOR),
            "clear": FunctionMetadata(name="clear", param_types=[], return_type=VOID_DESCRIPTOR),
            "__getitem__": FunctionMetadata(name="__getitem__", param_types=[INT_DESCRIPTOR], return_type=ANY_DESCRIPTOR),
            "__setitem__": FunctionMetadata(name="__setitem__", param_types=[INT_DESCRIPTOR, ANY_DESCRIPTOR], return_type=VOID_DESCRIPTOR)
        }

    def get_element_type(self) -> 'TypeDescriptor':
        # 泛型 List 的元素类型由 Descriptor 实例持有，Axiom 仅定义行为
        # 在这里返回 None 表示由 Descriptor 进一步处理，或者 Axiom 不知道具体类型
        return None 

    def resolve_specialization(self, registry: Any, args: List['TypeDescriptor']) -> 'TypeDescriptor':
        """[IES 2.1 Axiom-Driven] 实现列表泛型特化"""
        element_type = args[0] if args else ANY_DESCRIPTOR
        desc = registry.factory.create_list(element_type)
        registry.register(desc)
        return desc

    def resolve_item(self, key: 'TypeDescriptor') -> Optional['TypeDescriptor']:
        if key._axiom and isinstance(key._axiom, IntAxiom):
            return None # Delegate to descriptor
        return None

    def parse_value(self, raw_value: str) -> Any:
        start = raw_value.find('[')
        end = raw_value.rfind(']')
        if start != -1 and end != -1:
            try:
                json_str = raw_value[start:end+1]
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
        raise ValueError(f"No JSON list found in response: {raw_value}")

    def get_call_capability(self) -> Optional[CallCapability]: return None
    def get_operator_capability(self) -> Optional[OperatorCapability]: return None
    def get_converter_capability(self) -> Optional[ConverterCapability]: return None
    def is_compatible(self, other: 'TypeDescriptor') -> bool: 
        return other._axiom and isinstance(other._axiom, ListAxiom)


class DictAxiom(BaseAxiom, IterCapability, SubscriptCapability, ParserCapability):
    """dict 类型的行为公理"""
    
    @property
    def name(self) -> str: return "dict"

    def get_iter_capability(self) -> Optional[IterCapability]: return self
    def get_subscript_capability(self) -> Optional[SubscriptCapability]: return self
    def get_parser_capability(self) -> Optional[ParserCapability]: return self

    def get_methods(self) -> Dict[str, FunctionMetadata]:
        return {
            "get": FunctionMetadata(name="get", param_types=[ANY_DESCRIPTOR, ANY_DESCRIPTOR], return_type=ANY_DESCRIPTOR),
            "keys": FunctionMetadata(name="keys", param_types=[], return_type=ListMetadata(element_type=ANY_DESCRIPTOR)),
            "values": FunctionMetadata(name="values", param_types=[], return_type=ListMetadata(element_type=ANY_DESCRIPTOR)),
            "len": FunctionMetadata(name="len", param_types=[], return_type=INT_DESCRIPTOR),
            "__getitem__": FunctionMetadata(name="__getitem__", param_types=[ANY_DESCRIPTOR], return_type=ANY_DESCRIPTOR),
            "__setitem__": FunctionMetadata(name="__setitem__", param_types=[ANY_DESCRIPTOR, ANY_DESCRIPTOR], return_type=VOID_DESCRIPTOR)
        }

    def get_element_type(self) -> 'TypeDescriptor':
        return None # Keys

    def resolve_specialization(self, registry: Any, args: List['TypeDescriptor']) -> 'TypeDescriptor':
        """[IES 2.1 Axiom-Driven] 实现字典泛型特化"""
        key_type = args[0] if len(args) > 0 else ANY_DESCRIPTOR
        val_type = args[1] if len(args) > 1 else ANY_DESCRIPTOR
        desc = registry.factory.create_dict(key_type, val_type)
        registry.register(desc)
        return desc

    def resolve_item(self, key: 'TypeDescriptor') -> Optional['TypeDescriptor']:
        return None # Values

    def parse_value(self, raw_value: str) -> Any:
        start = raw_value.find('{')
        end = raw_value.rfind('}')
        if start != -1 and end != -1:
            try:
                json_str = raw_value[start:end+1]
                return json.loads(json_str)
            except json.JSONDecodeError:
                pass
        raise ValueError(f"No JSON dict found in response: {raw_value}")

    def get_call_capability(self) -> Optional[CallCapability]: return None
    def get_operator_capability(self) -> Optional[OperatorCapability]: return None
    def get_converter_capability(self) -> Optional[ConverterCapability]: return None
    def is_compatible(self, other: 'TypeDescriptor') -> bool: 
        return other._axiom and isinstance(other._axiom, DictAxiom)


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
        return True # 动态类型兼容一切

class ExceptionAxiom(BaseAxiom):
    """Exception 类型的行为公理"""
    
    @property
    def name(self) -> str: return "Exception"
    
    def get_methods(self) -> Dict[str, FunctionMetadata]:
        return {
            "message": FunctionMetadata(name="message", param_types=[], return_type=STR_DESCRIPTOR)
        }

class BoundMethodAxiom(BaseAxiom, CallCapability):
    """[IES 2.1] bound_method 类型的行为公理"""
    
    @property
    def name(self) -> str: return "bound_method"
    
    def get_parent_axiom_name(self) -> Optional[str]: return "callable"
    
    def get_call_capability(self) -> Optional[CallCapability]: return self
    
    def get_methods(self) -> Dict[str, FunctionMetadata]:
        return {} # Delegated to original function

    def resolve_return(self, args: List['TypeDescriptor']) -> Optional['TypeDescriptor']:
        return ANY_DESCRIPTOR

    def is_compatible(self, other: 'TypeDescriptor') -> bool:
        # 异常兼容性：子类异常兼容父类 (这里简化处理，认为 Exception 兼容所有 Exception 及其子类)
        # 实际需要继承树判断，但在公理层，只要是 ExceptionAxiom 及其变体即可
        return other._axiom and isinstance(other._axiom, ExceptionAxiom)


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
    
    registry.register(DynamicAxiom("Any"))
    registry.register(DynamicAxiom("var"))
    registry.register(DynamicAxiom("callable"))
    registry.register(DynamicAxiom("None"))
    registry.register(DynamicAxiom("void"))
    registry.register(DynamicAxiom("behavior"))
