from dataclasses import dataclass
from typing import List, Optional, Dict

@dataclass
class Type:
    def __str__(self):
        return "Type"

@dataclass
class AnyType(Type):
    def __str__(self):
        return "Any"

@dataclass
class VoidType(Type):
    def __str__(self):
        return "void"

@dataclass
class PrimitiveType(Type):
    name: str
    
    def __str__(self):
        return self.name

@dataclass
class ListType(Type):
    element_type: Type
    
    def __str__(self):
        return f"List[{self.element_type}]"

@dataclass
class DictType(Type):
    key_type: Type
    value_type: Type
    
    def __str__(self):
        return f"Dict[{self.key_type}, {self.value_type}]"

@dataclass
class FunctionType(Type):
    param_types: List[Type]
    return_type: Type
    
    def __str__(self):
        params = ", ".join(str(t) for t in self.param_types)
        return f"({params}) -> {self.return_type}"

@dataclass
class UnionType(Type):
    types: List[Type]
    
    def __str__(self):
        return " | ".join(str(t) for t in self.types)
