from dataclasses import dataclass, field
from typing import Optional, Any, Dict, List

@dataclass
class TypeDescriptor:
    """
    UTS (Unified Type System) 基础描述符。
    仅包含类型的静态元数据，不包含任何执行逻辑。
    """
    name: str
    module_path: Optional[str] = None
    is_nullable: bool = True
    kind: str = field(init=False)

    def __post_init__(self):
        self.kind = self.__class__.__name__

    def is_assignable_to(self, other: 'TypeDescriptor') -> bool:
        """基于协议的逻辑比较。"""
        if self.name in ("Any", "var") or other.name in ("Any", "var"):
            return True
        if self.name == other.name and self.module_path == other.module_path:
            return True
        
        # 内置类型的特殊兼容性规则
        if self.name == "int" and other.name == "bool":
            return True
        if other.name == "callable":
             if self.name in ("callable", "NativeFunction", "AnonymousLLMFunction", "behavior", "IbModule"):
                 return True
        return False

    def __str__(self):
        if self.module_path:
            return f"{self.module_path}.{self.name}"
        return self.name

# --- 具体描述符实现 ---

@dataclass
class PrimitiveDescriptor(TypeDescriptor):
    """内置原子类型描述符"""
    pass

@dataclass
class ListMetadata(TypeDescriptor):
    """列表类型元数据"""
    element_type: Optional[TypeDescriptor] = None

    def __post_init__(self):
        super().__post_init__()
        self.name = f"list[{self.element_type.name}]" if self.element_type else "list"

    def is_assignable_to(self, other: TypeDescriptor) -> bool:
        if super().is_assignable_to(other): return True
        if other.name == "list": return True
        if isinstance(other, ListMetadata) and self.element_type and other.element_type:
            return self.element_type.is_assignable_to(other.element_type)
        return False

@dataclass
class DictMetadata(TypeDescriptor):
    """字典类型元数据"""
    key_type: Optional[TypeDescriptor] = None
    value_type: Optional[TypeDescriptor] = None

    def __post_init__(self):
        super().__post_init__()
        if self.key_type and self.value_type:
            self.name = f"dict[{self.key_type.name}, {self.value_type.name}]"
        else:
            self.name = "dict"

    def is_assignable_to(self, other: TypeDescriptor) -> bool:
        if super().is_assignable_to(other): return True
        if other.name == "dict": return True
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
        super().__post_init__()
        if not self.name or self.name == "TypeDescriptor":
            self.name = "callable"

@dataclass
class ClassMetadata(TypeDescriptor):
    """类元数据描述"""
    parent_name: Optional[str] = None
    parent_module: Optional[str] = None
    members: Dict[str, TypeDescriptor] = field(default_factory=dict)
    
    def resolve_parent(self) -> Optional[TypeDescriptor]:
        if not self.parent_name: return None
        return MetadataRegistry.resolve(self.parent_name, self.parent_module)

    def is_assignable_to(self, other: TypeDescriptor) -> bool:
        if super().is_assignable_to(other): return True
        parent = self.resolve_parent()
        return parent.is_assignable_to(other) if parent else False

@dataclass
class ModuleMetadata(TypeDescriptor):
    """模块元数据描述"""
    exports: Dict[str, TypeDescriptor] = field(default_factory=dict)

    def __post_init__(self):
        super().__post_init__()
        if not self.name or self.name == "TypeDescriptor":
            self.name = "module"

# --- 常量与注册表 ---

class MetadataRegistry:
    """Domain 层内部的元数据注册表"""
    _descriptors: Dict[str, TypeDescriptor] = {}

    @classmethod
    def register(cls, descriptor: TypeDescriptor):
        cls._descriptors[str(descriptor)] = descriptor

    @classmethod
    def resolve(cls, name: str, module_path: Optional[str] = None) -> Optional[TypeDescriptor]:
        key = f"{module_path}.{name}" if module_path else name
        return cls._descriptors.get(key)

# 预定义常量描述符
INT_DESCRIPTOR = PrimitiveDescriptor(name="int", is_nullable=False)
STR_DESCRIPTOR = PrimitiveDescriptor(name="str", is_nullable=False)
FLOAT_DESCRIPTOR = PrimitiveDescriptor(name="float", is_nullable=False)
BOOL_DESCRIPTOR = PrimitiveDescriptor(name="bool", is_nullable=False)
VOID_DESCRIPTOR = PrimitiveDescriptor(name="void", is_nullable=False)
ANY_DESCRIPTOR = PrimitiveDescriptor(name="Any", is_nullable=True)
VAR_DESCRIPTOR = PrimitiveDescriptor(name="var", is_nullable=True)

for d in (INT_DESCRIPTOR, STR_DESCRIPTOR, FLOAT_DESCRIPTOR, 
          BOOL_DESCRIPTOR, VOID_DESCRIPTOR, ANY_DESCRIPTOR, VAR_DESCRIPTOR):
    MetadataRegistry.register(d)
