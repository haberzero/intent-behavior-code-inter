from dataclasses import dataclass, field
from typing import Optional, Any, Dict, List, Union

@dataclass
class TypeDescriptor:
    """
    UTS (Unified Type System) 基础描述符。
    仅包含类型的静态元数据，不包含任何执行逻辑。
    """
    name: str = ""
    module_path: Optional[str] = None
    is_nullable: bool = True
    kind: str = field(init=False)
    members: Dict[str, 'TypeDescriptor'] = field(default_factory=dict)
    
    # 运行时绑定的注册表上下文 (用于支持多引擎隔离)
    _registry: Optional['MetadataRegistry'] = field(default=None, init=False, repr=False)

    def __post_init__(self):
        self.kind = self.__class__.__name__

    def unwrap(self) -> 'TypeDescriptor':
        """解包描述符 (默认为自身，子类如 LazyDescriptor 可覆盖)"""
        return self

    def is_assignable_to(self, other: 'TypeDescriptor') -> bool:
        """
        Check if this type can be assigned to 'other' type.
        Implements the core type compatibility logic.
        """
        # 1. 自动解包延迟加载描述符
        s_unwrapped = self.unwrap() if hasattr(self, 'unwrap') else self
        o_unwrapped = other.unwrap() if hasattr(other, 'unwrap') else other

        # 2. 引用相等
        if s_unwrapped is o_unwrapped:
            return True
            
        # 3. 名字匹配
        if s_unwrapped.name == o_unwrapped.name and s_unwrapped.module_path == o_unwrapped.module_path:
            return True

        # 4. 动态类型兼容性
        if o_unwrapped.name in ("Any", "var") or s_unwrapped.name in ("Any", "var"):
            return True
            
        # 5. 内置类型的特殊兼容性规则
        if s_unwrapped.name == "int" and o_unwrapped.name in ("bool", "float"):
            return True
        if o_unwrapped.name == "callable":
             if s_unwrapped.name in ("callable", "function", "NativeFunction", "AnonymousLLMFunction", "behavior", "IbModule"):
                 return True
                 
        return False
        
    @property
    def is_callable(self) -> bool:
        """是否支持调用行为"""
        return False

    @property
    def is_iterable(self) -> bool:
        """是否支持迭代行为"""
        return False

    @property
    def is_subscriptable(self) -> bool:
        """是否支持下标访问行为"""
        return False

    def get_iterator_element_type(self) -> Optional['TypeDescriptor']:
        """解析迭代元素类型"""
        return None

    def get_subscript_result_type(self, key: 'TypeDescriptor') -> Optional['TypeDescriptor']:
        """解析下标访问结果类型"""
        return None

    def get_call_return_type(self, args: List['TypeDescriptor']) -> Optional['TypeDescriptor']:
        """解析调用返回类型"""
        return None

    def resolve_member(self, name: str) -> Optional['TypeDescriptor']:
        """Resolve a member (attribute/method) by name."""
        return self.members.get(name)

    def get_operator_result(self, op: str, other: Optional['TypeDescriptor'] = None) -> Optional['TypeDescriptor']:
        """解析运算符返回类型 (UTS 级决议)"""
        return None

    def __str__(self):
        if self.module_path:
            return f"{self.module_path}.{self.name}"
        return self.name

@dataclass
class LazyDescriptor(TypeDescriptor):
    """
    延迟加载描述符。
    用于解决模块加载时的循环依赖。
    """
    target_name: str = ""
    target_module: Optional[str] = None
    _resolved: Optional[TypeDescriptor] = None

    def __init__(self, name: str, module_path: Optional[str] = None):
        super().__init__(name=name, module_path=module_path)
        self.target_name = name
        self.target_module = module_path

    def unwrap(self) -> TypeDescriptor:
        if self._resolved:
            return self._resolved
            
        # 如果没有关联注册表，无法解包 (这在单引擎场景下不应该发生)
        if not self._registry:
            return self
            
        self._resolved = self._registry.resolve(self.target_name, self.target_module)
        if not self._resolved:
            # 仍然没找到，返回自身占位
            return self
            
        return self._resolved

    def resolve_member(self, name: str) -> Optional[TypeDescriptor]:
        return self.unwrap().resolve_member(name)

    @property
    def is_iterable(self) -> bool:
        return self.unwrap().is_iterable

    @property
    def is_subscriptable(self) -> bool:
        return self.unwrap().is_subscriptable

    def get_iterator_element_type(self) -> Optional[TypeDescriptor]:
        return self.unwrap().get_iterator_element_type()

    def get_subscript_result_type(self, key: TypeDescriptor) -> Optional[TypeDescriptor]:
        return self.unwrap().get_subscript_result_type(key)

    def is_assignable_to(self, other: TypeDescriptor) -> bool:
        return self.unwrap().is_assignable_to(other)

# --- 具体描述符实现 ---

@dataclass
class PrimitiveDescriptor(TypeDescriptor):
    """内置原子类型描述符"""
    @property
    def is_callable(self) -> bool:
        # 内置类型（如 int, str）允许调用，表示类型转换/构造
        return self.name in ("int", "str", "float", "bool", "list", "dict")

    @property
    def is_iterable(self) -> bool:
        return self.name in ("Any", "var", "list", "dict")

    @property
    def is_subscriptable(self) -> bool:
        return self.name in ("Any", "var", "list", "dict")

    def get_iterator_element_type(self) -> Optional['TypeDescriptor']:
        if self.name in ("Any", "var"): return ANY_DESCRIPTOR
        return None

    def get_subscript_result_type(self, key: 'TypeDescriptor') -> Optional['TypeDescriptor']:
        if self.name in ("Any", "var"): return ANY_DESCRIPTOR
        return None

    def get_call_return_type(self, args: List['TypeDescriptor']) -> Optional['TypeDescriptor']:
        # 内置类型调用返回其自身
        return self

    def get_operator_result(self, op: str, other: Optional['TypeDescriptor'] = None) -> Optional['TypeDescriptor']:
        n1 = self.name
        if not other: # 一元运算
            if op == '~' and n1 == "int": return INT_DESCRIPTOR
            if op == '-' and n1 in ("int", "float"): return self
            if op == 'not': return BOOL_DESCRIPTOR
            return None
            
        n2 = other.name
        # 1. 逻辑运算 (and/or)
        if op in ('and', 'or'):
            # IBCI 2.0 中逻辑运算返回 BOOL
            return BOOL_DESCRIPTOR

        # 2. 比较运算 (始终返回 bool)
        if op in ('>', '>=', '<', '<=', '==', '!='):
            return BOOL_DESCRIPTOR

        # 3. 数值运算
        if n1 == "int" and n2 == "int":
            if op in ('+', '-', '*', '/', '//', '%', '&', '|', '^', '<<', '>>'): return INT_DESCRIPTOR
            
        if (n1 in ("int", "float")) and (n2 in ("int", "float")):
            if op in ('+', '-', '*', '/'): return FLOAT_DESCRIPTOR
            
        # 4. 字符串运算
        if n1 == "str" and op == '+':
            if n2 == "str": return STR_DESCRIPTOR
            if n2 in ("Any", "var"): return ANY_DESCRIPTOR
            
        # 5. 列表运算
        if n1 == "list" and op == '+':
            if n2 == "list": return self
            
        return None

@dataclass
class ListMetadata(TypeDescriptor):
    """列表类型元数据"""
    element_type: Optional[TypeDescriptor] = None

    @property
    def is_iterable(self) -> bool:
        return True

    @property
    def is_subscriptable(self) -> bool:
        return True

    def get_iterator_element_type(self) -> Optional[TypeDescriptor]:
        return self.element_type or ANY_DESCRIPTOR

    def get_subscript_result_type(self, key: TypeDescriptor) -> Optional[TypeDescriptor]:
        # 列表下标暂时只支持 int
        if key.name == "int":
            return self.element_type or ANY_DESCRIPTOR
        return None

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

    @property
    def is_iterable(self) -> bool:
        return True

    @property
    def is_subscriptable(self) -> bool:
        return True

    def get_iterator_element_type(self) -> Optional[TypeDescriptor]:
        # 字典迭代产生键
        return self.key_type or ANY_DESCRIPTOR

    def get_subscript_result_type(self, key: TypeDescriptor) -> Optional[TypeDescriptor]:
        if self.key_type:
            if key.is_assignable_to(self.key_type):
                return self.value_type or ANY_DESCRIPTOR
        return self.value_type or ANY_DESCRIPTOR

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

    @property
    def is_callable(self) -> bool:
        return True

    def get_call_return_type(self, args: List['TypeDescriptor']) -> Optional['TypeDescriptor']:
        if len(args) != len(self.param_types):
            return None
        for i, (expected, actual) in enumerate(zip(self.param_types, args)):
            if not actual.is_assignable_to(expected):
                return None
        return self.return_type

    def is_assignable_to(self, other: TypeDescriptor) -> bool:
        if super().is_assignable_to(other):
            return True
        if other.name == "callable":
            return True
        if isinstance(other, FunctionMetadata):
            if self.return_type and other.return_type:
                if not self.return_type.is_assignable_to(other.return_type):
                    return False
            if len(self.param_types) != len(other.param_types):
                return False
            for p1, p2 in zip(self.param_types, other.param_types):
                if not p2.is_assignable_to(p1): 
                    return False
            return True
        return False

@dataclass
class ClassMetadata(TypeDescriptor):
    """类元数据描述"""
    parent_name: Optional[str] = None
    parent_module: Optional[str] = None
    
    @property
    def is_callable(self) -> bool:
        """类是可调用的（用于实例化）"""
        return True

    def get_call_return_type(self, args: List['TypeDescriptor']) -> Optional['TypeDescriptor']:
        # 类实例化返回其实例类型（即自身）
        # [TODO] 增加对 __init__ 方法签名的校验
        return self

    def resolve_parent(self) -> Optional[TypeDescriptor]:
        if not self.parent_name: return None
        if not self._registry: return None
        return self._registry.resolve(self.parent_name, self.parent_module)

    def is_assignable_to(self, other: TypeDescriptor) -> bool:
        if super().is_assignable_to(other): return True
        parent = self.resolve_parent()
        return parent.is_assignable_to(other) if parent else False

    def resolve_member(self, name: str) -> Optional[TypeDescriptor]:
        if name in self.members:
            return self.members[name]
        parent = self.resolve_parent()
        if parent:
            return parent.resolve_member(name)
        return None

@dataclass
class ModuleMetadata(TypeDescriptor):
    """模块元数据描述"""
    def __post_init__(self):
        super().__post_init__()
        if not self.name or self.name == "TypeDescriptor":
            self.name = "module"

# --- 常量与注册表 ---

class MetadataRegistry:
    """
    UTS 元数据注册表。
    不再使用类级别单例，改为实例管理以支持多引擎隔离。
    """
    def __init__(self):
        self._descriptors: Dict[str, TypeDescriptor] = {}

    def register(self, descriptor: TypeDescriptor):
        key = str(descriptor)
        self._descriptors[key] = descriptor
        # [Isolation] 将注册表上下文绑定到描述符上
        descriptor._registry = self

    def resolve(self, name: str, module_path: Optional[str] = None) -> Optional[TypeDescriptor]:
        key = f"{module_path}.{name}" if module_path else name
        return self._descriptors.get(key)

# 预定义常量描述符 (作为原型存在)
INT_DESCRIPTOR = PrimitiveDescriptor(name="int", is_nullable=False)
STR_DESCRIPTOR = PrimitiveDescriptor(name="str", is_nullable=False)
FLOAT_DESCRIPTOR = PrimitiveDescriptor(name="float", is_nullable=False)
BOOL_DESCRIPTOR = PrimitiveDescriptor(name="bool", is_nullable=False)
VOID_DESCRIPTOR = PrimitiveDescriptor(name="void", is_nullable=False)
ANY_DESCRIPTOR = PrimitiveDescriptor(name="Any", is_nullable=True)
VAR_DESCRIPTOR = PrimitiveDescriptor(name="var", is_nullable=True)
CALLABLE_DESCRIPTOR = PrimitiveDescriptor(name="callable", is_nullable=True)

# 集合类型占位描述符 (用于基础元数据注册)
LIST_DESCRIPTOR = ListMetadata(name="list", is_nullable=True)
DICT_DESCRIPTOR = DictMetadata(name="dict", is_nullable=True)

import copy

# ... (omitted)

def create_default_registry() -> MetadataRegistry:
    """创建并预填充基础类型的注册表实例 (通过克隆原型实现物理隔离)"""
    reg = MetadataRegistry()
    # 使用深拷贝确保不同引擎实例之间的描述符物理隔离，防止 members 污染
    for d in (INT_DESCRIPTOR, STR_DESCRIPTOR, FLOAT_DESCRIPTOR, 
              BOOL_DESCRIPTOR, VOID_DESCRIPTOR, ANY_DESCRIPTOR, 
              VAR_DESCRIPTOR, CALLABLE_DESCRIPTOR, LIST_DESCRIPTOR, DICT_DESCRIPTOR):
        reg.register(copy.deepcopy(d))
    return reg
