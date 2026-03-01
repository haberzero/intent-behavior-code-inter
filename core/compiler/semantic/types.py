
from typing import List, Dict, Optional, Any, Union
from dataclasses import dataclass

@dataclass
class Type:
    name: str

    def is_assignable_to(self, other: 'Type') -> bool:
        """
        Check if this type can be assigned to 'other'.
        Subclasses should override this.
        """
        if isinstance(other, AnyType):
            return True
        if isinstance(self, AnyType):
            return True
        
        # None (represented by VOID_TYPE in current system) is assignable to any type
        if self == VOID_TYPE:
            return True

        # Default strict equality check
        return self == other
        
    def __str__(self):
        return self.name

@dataclass
class PrimitiveType(Type):
    pass

@dataclass
class AnyType(Type):
    """Represents 'var' or dynamic type."""
    def __init__(self):
        super().__init__("Any")

@dataclass
class ContainerType(Type):
    pass

@dataclass
class ListType(ContainerType):
    element_type: Type
    
    def __init__(self, element_type: Type):
        super().__init__(f"list[{element_type}]")
        self.element_type = element_type

    def is_assignable_to(self, other: 'Type') -> bool:
        if isinstance(other, AnyType): return True
        if not isinstance(other, ListType): return False
        return self.element_type.is_assignable_to(other.element_type)

@dataclass
class DictType(ContainerType):
    key_type: Type
    value_type: Type
    
    def __init__(self, key_type: Type, value_type: Type):
        super().__init__(f"dict[{key_type}, {value_type}]")
        self.key_type = key_type
        self.value_type = value_type

    def is_assignable_to(self, other: 'Type') -> bool:
        if isinstance(other, AnyType): return True
        if not isinstance(other, DictType): return False
        return (self.key_type.is_assignable_to(other.key_type) and 
                self.value_type.is_assignable_to(other.value_type))

@dataclass
class CallableType(Type):
    """Represents the 'callable' keyword type, a generic callable object."""
    def __init__(self):
        super().__init__("callable")
    
    def is_assignable_to(self, other: 'Type') -> bool:
        if isinstance(other, AnyType): return True
        return isinstance(other, CallableType)

@dataclass
class FunctionType(Type):
    param_types: List[Type]
    return_type: Type
    
    def __init__(self, param_types: List[Type], return_type: Type):
        super().__init__("function")
        self.param_types = param_types
        self.return_type = return_type
        
    def __repr__(self):
        return f"Function({self.param_types} -> {self.return_type})"

    def is_assignable_to(self, other: 'Type') -> bool:
        if isinstance(other, AnyType): return True
        if isinstance(other, CallableType): return True
        if not isinstance(other, FunctionType): return False
        # Simplified: Check return type and param count
        return (len(self.param_types) == len(other.param_types) and 
                self.return_type.is_assignable_to(other.return_type))

@dataclass
class ModuleType(Type):
    """
    Internal type to represent a module/package scope during semantic analysis.
    Not a user-visible type.
    """
    scope: Any # Should be ScopeNode, but avoid circular import
    
    def __init__(self, scope: Any):
        super().__init__("module")
        self.scope = scope
    
    def is_assignable_to(self, other: 'Type') -> bool:
        # Modules are not first-class values (yet)
        return False

@dataclass
class UserDefinedType(Type):
    """Represents a class type."""
    class_name: str
    scope: Any # Class scope
    
    def __init__(self, class_name: str, scope: Any):
        super().__init__(class_name)
        self.class_name = class_name
        self.scope = scope

    def is_assignable_to(self, other: 'Type') -> bool:
        if isinstance(other, AnyType): return True
        if not isinstance(other, UserDefinedType): return False
        return self.class_name == other.class_name

# Predefined Types instances
INT_TYPE = PrimitiveType("int")
FLOAT_TYPE = PrimitiveType("float")
STR_TYPE = PrimitiveType("str")
BOOL_TYPE = PrimitiveType("bool")
VOID_TYPE = PrimitiveType("void") # For functions without return
ANY_TYPE = AnyType() # Singleton instance for Any

def get_builtin_type(name: str) -> Optional[Type]:
    mapping = {
        "int": INT_TYPE,
        "float": FLOAT_TYPE,
        "str": STR_TYPE,
        "bool": BOOL_TYPE,
        "void": VOID_TYPE,
        "list": ListType(ANY_TYPE), # Default raw list is list[Any]
        "dict": DictType(ANY_TYPE, ANY_TYPE), # Default raw dict is dict[Any, Any]
        "var": ANY_TYPE,
        "callable": CallableType()
    }
    return mapping.get(name)

def get_promoted_type(op: str, t1: Type, t2: Type) -> Optional[Type]:
    """
    Strict type promotion logic for IBC-Inter.
    Only allows numerical promotion for int and float.
    """
    # Any type bypasses strict checks (runtime will handle)
    if isinstance(t1, AnyType) or isinstance(t2, AnyType):
        return ANY_TYPE

    # Arithmetic operators
    if op in ('+', '-', '*', '/', '%'):
        # Both are int -> int
        if t1 == INT_TYPE and t2 == INT_TYPE:
            return INT_TYPE
        
        # Numeric promotion (int and float)
        is_t1_num = t1 in (INT_TYPE, FLOAT_TYPE)
        is_t2_num = t2 in (INT_TYPE, FLOAT_TYPE)
        
        if is_t1_num and is_t2_num:
            return FLOAT_TYPE
            
        # String concatenation (Only +)
        if op == '+' and t1 == STR_TYPE and t2 == STR_TYPE:
            return STR_TYPE

        # List concatenation (Only +)
        if op == '+' and isinstance(t1, ListType) and isinstance(t2, ListType):
            if t1.element_type == t2.element_type:
                return t1
            return ListType(ANY_TYPE)

    # Bitwise operators (int only)
    elif op in ('&', '|', '^', '<<', '>>'):
        if t1 == INT_TYPE and t2 == INT_TYPE:
            return INT_TYPE
            
    # Comparison operators
    elif op in ('>', '>=', '<', '<=', '==', '!='):
        # Allow numerical comparison
        is_t1_num = t1 in (INT_TYPE, FLOAT_TYPE)
        is_t2_num = t2 in (INT_TYPE, FLOAT_TYPE)
        if is_t1_num and is_t2_num:
            return BOOL_TYPE
            
        # Allow same-type comparison
        if t1 == t2:
            return BOOL_TYPE
            
        # Allow comparison with None (VOID_TYPE)
        if (op in ('==', '!=')) and (t1 == VOID_TYPE or t2 == VOID_TYPE):
            return BOOL_TYPE
            
    return None
