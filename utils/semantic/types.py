
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
        return self.name == other.name
        
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
        # Invariant for now: list[int] is NOT list[float]
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
class FunctionType(Type):
    param_types: List[Type]
    return_type: Type
    
    def __init__(self, param_types: List[Type], return_type: Type):
        super().__init__("function")
        self.param_types = param_types
        self.return_type = return_type

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
        "var": ANY_TYPE
    }
    return mapping.get(name)
