from dataclasses import dataclass
from .base import TypeDescriptor

@dataclass
class PrimitiveDescriptor(TypeDescriptor):
    """内置原子类型描述符"""
    pass

# 预定义常量描述符
INT_DESCRIPTOR = PrimitiveDescriptor(name="int", is_nullable=False)
STR_DESCRIPTOR = PrimitiveDescriptor(name="str", is_nullable=False)
FLOAT_DESCRIPTOR = PrimitiveDescriptor(name="float", is_nullable=False)
BOOL_DESCRIPTOR = PrimitiveDescriptor(name="bool", is_nullable=False)
VOID_DESCRIPTOR = PrimitiveDescriptor(name="void", is_nullable=False)
ANY_DESCRIPTOR = PrimitiveDescriptor(name="Any", is_nullable=True)
VAR_DESCRIPTOR = PrimitiveDescriptor(name="var", is_nullable=True)
