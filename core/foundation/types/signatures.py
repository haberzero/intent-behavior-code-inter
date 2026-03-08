from dataclasses import dataclass, field
from typing import List, Dict, Optional
from .base import TypeDescriptor

@dataclass
class ListMetadata(TypeDescriptor):
    """列表类型元数据"""
    element_type: Optional[TypeDescriptor] = None

    def __post_init__(self):
        if self.element_type is None:
            # Avoid circular import by not importing ANY_DESCRIPTOR here
            # Instead, we'll just use a placeholder or handle it later
            self.name = "list"
        else:
            self.name = f"list[{self.element_type.name}]"

    def is_assignable_to(self, other: TypeDescriptor) -> bool:
        if super().is_assignable_to(other):
            return True
        if other.name == "list": # 协变：list[int] -> list
            return True
        if isinstance(other, ListMetadata) and self.element_type and other.element_type:
            return self.element_type.is_assignable_to(other.element_type)
        return False

@dataclass
class DictMetadata(TypeDescriptor):
    """字典类型元数据"""
    key_type: Optional[TypeDescriptor] = None
    value_type: Optional[TypeDescriptor] = None

    def __post_init__(self):
        if self.key_type and self.value_type:
            self.name = f"dict[{self.key_type.name}, {self.value_type.name}]"
        else:
            self.name = "dict"

    def is_assignable_to(self, other: TypeDescriptor) -> bool:
        if super().is_assignable_to(other):
            return True
        if other.name == "dict":
            return True
        if isinstance(other, DictMetadata) and self.key_type and other.key_type and self.value_type and other.value_type:
            return self.key_type.is_assignable_to(other.key_type) and \
                   self.value_type.is_assignable_to(other.value_type)
        return False

@dataclass
class FunctionMetadata(TypeDescriptor):
    """函数/方法签名元数据"""
    param_types: List[TypeDescriptor] = field(default_factory=list)
    return_type: Optional[TypeDescriptor] = None

    def __post_init__(self):
        if self.name == "TypeDescriptor": # Default if not set
            self.name = "callable"

@dataclass
class ClassMetadata(TypeDescriptor):
    """类元数据描述"""
    parent_name: Optional[str] = None
    parent_module: Optional[str] = None
    
    # 成员名称 -> 类型描述符
    members: Dict[str, TypeDescriptor] = field(default_factory=dict)
    
    def is_assignable_to(self, other: TypeDescriptor) -> bool:
        if super().is_assignable_to(other):
            return True
            
        # 简单的继承链检查（通过名称）
        # 注意：这里未来可能需要通过 MetadataRegistry 来解析真实的父类描述符
        if isinstance(other, ClassMetadata) and self.parent_name == other.name:
            return True
            
        return False

@dataclass
class ModuleMetadata(TypeDescriptor):
    """模块元数据描述"""
    exports: Dict[str, TypeDescriptor] = field(default_factory=dict)

    def __post_init__(self):
        if self.name == "TypeDescriptor":
            self.name = "module"
