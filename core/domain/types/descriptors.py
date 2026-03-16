from dataclasses import dataclass, field
from typing import Optional, Any, Dict, List, Union, Protocol, runtime_checkable, TYPE_CHECKING
import copy

# [Axiom Layer Integration]
if TYPE_CHECKING:
    from core.domain.axioms.protocols import TypeAxiom, CallCapability, IterCapability, SubscriptCapability, OperatorCapability, ParserCapability
    from .registry import MetadataRegistry
    from core.domain.symbols import Symbol

@dataclass
class TypeDescriptor:
    """
    UTS (Unified Type System) 基础描述符。
    作为 [Axiom Container]，它不再包含硬编码逻辑，而是代理到底层的公理系统。
    """
    name: str = ""
    module_path: Optional[str] = None
    is_nullable: bool = True
    is_user_defined: bool = True # [CHANGE] 默认设为 True，仅内核类手动设为 False
    kind: str = field(init=False)
    # 成员字典：名称 -> 符号 (不再是 TypeDescriptor)
    # 这样我们可以同时追踪成员的类型和定义源
    members: Dict[str, 'Symbol'] = field(default_factory=dict)
    
    # 运行时绑定的注册表上下文
    _registry: Optional['MetadataRegistry'] = field(default=None, init=False, repr=False)
    
    # [New] 公理绑定
    _axiom: Optional['TypeAxiom'] = field(default=None, init=False, repr=False)

    def clone(self, memo: Optional[Dict[int, Any]] = None) -> 'TypeDescriptor':
        """
        [IES 2.0 Isolation] 深度克隆描述符，确保引擎实例间的物理隔离。
        使用 memo 字典防止循环引用导致的无限递归。
        """
        if memo is None: memo = {}
        if id(self) in memo:
            return memo[id(self)]
            
        # 1. 基础浅拷贝处理标量字段
        new_desc = copy.copy(self)
        memo[id(self)] = new_desc
        
        # 2. 重置运行时绑定状态
        new_desc._registry = None
        new_desc._axiom = None
        
        # 3. 递归克隆成员符号
        if self.members:
            # 注意：此处必须使用 dict comprehension 确保 Symbol.clone 也能使用同一个 memo
            # 同时 Symbol.clone 会递归调用 TypeDescriptor.clone(memo)
            new_desc.members = {name: sym.clone(memo) for name, sym in self.members.items()}
            
        # 4. 处理子类特有的描述符引用 (这些引用可能不在 members 中)
        if isinstance(self, ListMetadata) and self.element_type:
            new_desc.element_type = self.element_type.clone(memo)
        elif isinstance(self, DictMetadata):
            if self.key_type: new_desc.key_type = self.key_type.clone(memo)
            if self.value_type: new_desc.value_type = self.value_type.clone(memo)
        elif isinstance(self, FunctionMetadata):
            # 修正：FunctionMetadata.param_types 存储的是 TypeDescriptor 列表，不是 Symbol 列表
            new_desc.param_types = [p.clone(memo) for p in self.param_types]
            if self.return_type: new_desc.return_type = self.return_type.clone(memo)
        elif isinstance(self, BoundMethodMetadata):
            if self.receiver_type: new_desc.receiver_type = self.receiver_type.clone(memo)
            if self.function_type: new_desc.function_type = self.function_type.clone(memo)
            
        return new_desc

    def __post_init__(self):
        self.kind = self.__class__.__name__

    def unwrap(self) -> 'TypeDescriptor':
        return self

    # --- Capability Accessors (Delegated to Axiom) ---
    
    def get_call_trait(self) -> Optional['CallCapability']:
        return self._axiom.get_call_capability() if self._axiom else None

    def _resolve_type_ref(self, res: Optional[Union['TypeDescriptor', str]]) -> Optional['TypeDescriptor']:
        """[Helper] 将公理返回的类型引用（可能是字符串名称）转换为当前实例的描述符对象"""
        if res is None: return None
        if isinstance(res, str):
            resolved = self._registry.resolve(res) if self._registry else None
            return resolved
        return res

    def resolve_return(self, args: List['TypeDescriptor']) -> Optional['TypeDescriptor']:
        if self._axiom:
            trait = self._axiom.get_call_capability()
            if trait:
                return self._resolve_type_ref(trait.resolve_return(args))
        return None

    def get_element_type(self) -> Optional['TypeDescriptor']:
        if self._axiom:
            trait = self._axiom.get_iter_capability()
            if trait:
                return self._resolve_type_ref(trait.get_element_type())
        return None

    def resolve_item(self, key: 'TypeDescriptor') -> Optional['TypeDescriptor']:
        if self._axiom:
            trait = self._axiom.get_subscript_capability()
            if trait:
                return self._resolve_type_ref(trait.resolve_item(key))
        return None

    def get_operator_result(self, op: str, other: Optional['TypeDescriptor'] = None) -> Optional['TypeDescriptor']:
        """运算符决议 (Delegated to Axiom)"""
        if other:
            other = other.unwrap()
        
        if self._axiom:
            op_cap = self._axiom.get_operator_capability()
            if op_cap:
                return self._resolve_type_ref(op_cap.resolve_operation(op, other))
        return None

    def get_iter_trait(self) -> Optional['IterCapability']:
        return self._axiom.get_iter_capability() if self._axiom else None

    def get_subscript_trait(self) -> Optional['SubscriptCapability']:
        return self._axiom.get_subscript_capability() if self._axiom else None

    def get_parser_trait(self) -> Optional['ParserCapability']:
        return self._axiom.get_parser_capability() if self._axiom else None

    def is_dynamic(self) -> bool:
        """
        判断是否为动态/Any类型。
        完全委托给公理系统判断。如果未绑定公理，默认视为非动态（安全回退）。
        """
        if self._axiom:
            return self._axiom.is_dynamic()
        return False

    def is_assignable_to(self, other: 'TypeDescriptor') -> bool:
        """
        类型兼容性校验 (Axiom-Driven)
        """
        s = self.unwrap()
        o = other.unwrap()

        # 1. 引用相等 (Interning)
        if s is o: return True
            
        # 2. 公理级兼容性检查 (处理 Any/var/primitive 转换)
        if s._axiom and s._axiom.is_compatible(o):
            return True
        if o._axiom and o._axiom.is_compatible(s):
            return True

        # 3. 严格结构匹配 (由子类实现或默认名称匹配)
        return s._is_structurally_compatible(o)

    def get_diff_hint(self, other: 'TypeDescriptor') -> str:
        """
        [UTS Diagnostic] 生成类型不匹配的友好提示。
        """
        s = self.unwrap()
        o = other.unwrap()
        
        # 1. 极简匹配 (基础名不匹配)
        if s.name != o.name:
            # 特殊情况提示
            if s.name.startswith("list") and o.name == "str":
                return "Did you forget to join the list into a string?"
            if s.name == "str" and o.name == "int":
                return "Use .cast_to(int) or int(s) to convert string to integer."
            return f"Expected '{o.name}', but got '{s.name}'."

        # 2. 泛型参数匹配 (如果子类支持)
        if hasattr(s, 'element_type') and hasattr(o, 'element_type'):
            if s.element_type and o.element_type and not s.element_type.is_assignable_to(o.element_type):
                return f"Element type mismatch: {s.element_type.get_diff_hint(o.element_type)}"
        
        if hasattr(s, 'key_type') and hasattr(o, 'key_type'):
            if s.key_type and o.key_type and not s.key_type.is_assignable_to(o.key_type):
                return f"Key type mismatch: {s.key_type.get_diff_hint(o.key_type)}"
        
        if hasattr(s, 'value_type') and hasattr(o, 'value_type'):
            if s.value_type and o.value_type and not s.value_type.is_assignable_to(o.value_type):
                return f"Value type mismatch: {s.value_type.get_diff_hint(o.value_type)}"

        # 3. 函数签名匹配
        if isinstance(s, (FunctionMetadata, BoundMethodMetadata)) and isinstance(o, (FunctionMetadata, BoundMethodMetadata)):
            if len(s.param_types) != len(o.param_types):
                return f"Parameter count mismatch: expected {len(o.param_types)}, but got {len(s.param_types)}"
            for i, (p1, p2) in enumerate(zip(s.param_types, o.param_types)):
                if not p1.is_assignable_to(p2):
                    return f"Parameter {i+1} mismatch: {p1.get_diff_hint(p2)}"
            if s.return_type and o.return_type and not s.return_type.is_assignable_to(o.return_type):
                return f"Return type mismatch: {s.return_type.get_diff_hint(o.return_type)}"

        return f"Type '{s.name}' is not compatible with '{o.name}'."

    def _is_structurally_compatible(self, other: 'TypeDescriptor') -> bool:
        """子类可重写的结构化兼容性逻辑"""
        return self.name == other.name and self.module_path == other.module_path

    def resolve_member(self, name: str) -> Optional['Symbol']:
        """
        解析已存在的成员符号。
        [Architecture Policy] 此处不再负责动态创建符号，以保持底层纯净。
        """
        if name in self.members:
            return self.members[name]
            
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

    def resolve_member(self, name: str) -> Optional['Symbol']:
        return self.unwrap().resolve_member(name)

    def get_call_trait(self) -> Optional['CallCapability']:
        return self.unwrap().get_call_trait()

    def get_iter_trait(self) -> Optional['IterCapability']:
        return self.unwrap().get_iter_trait()

    def get_subscript_trait(self) -> Optional['SubscriptCapability']:
        return self.unwrap().get_subscript_trait()

    def get_parser_trait(self) -> Optional['ParserCapability']:
        return self.unwrap().get_parser_trait()

    def is_assignable_to(self, other: 'TypeDescriptor') -> bool:
        return self.unwrap().is_assignable_to(other)

    def resolve_return(self, args: List['TypeDescriptor']) -> Optional['TypeDescriptor']:
        return self.unwrap().resolve_return(args)

    def get_element_type(self) -> Optional['TypeDescriptor']:
        return self.unwrap().get_element_type()

    def resolve_item(self, key: 'TypeDescriptor') -> Optional['TypeDescriptor']:
        return self.unwrap().resolve_item(key)

# --- 具体描述符实现 ---

@dataclass
class ListMetadata(TypeDescriptor):
    """列表类型元数据"""
    element_type: Optional[TypeDescriptor] = None

    def __post_init__(self):
        super().__post_init__()
        self.name = f"list[{self.element_type.name}]" if self.element_type else "list"

    def get_subscript_trait(self) -> Optional['SubscriptCapability']:
        return self

    def resolve_item(self, key: TypeDescriptor) -> Optional[TypeDescriptor]:
        # 优先使用 Axiom (如果有)
        res = super().resolve_item(key)
        if res: return res
        # 回退到 element_type
        return self.element_type

    def is_assignable_to(self, other: TypeDescriptor) -> bool:
        if super().is_assignable_to(other): return True
        # 允许原始 list 与泛型 list 互转 (逻辑宽松处理)
        # 使用 unwrap() 确保 LazyDescriptor 能正确对比
        o = other.unwrap()
        if o is LIST_DESCRIPTOR or (isinstance(o, ListMetadata) and o.element_type is ANY_DESCRIPTOR):
             return True
        if isinstance(o, ListMetadata):
            if not self.element_type or not o.element_type:
                return True
            return self.element_type.is_assignable_to(o.element_type)
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

    def get_subscript_trait(self) -> Optional['SubscriptCapability']:
        return self

    def resolve_item(self, key: TypeDescriptor) -> Optional[TypeDescriptor]:
        res = super().resolve_item(key)
        if res: return res
        return self.value_type

    def is_assignable_to(self, other: TypeDescriptor) -> bool:
        if super().is_assignable_to(other): return True
        # 允许原始 dict 与泛型 dict 互转
        o = other.unwrap()
        if o is DICT_DESCRIPTOR or (isinstance(o, DictMetadata) and o.key_type is ANY_DESCRIPTOR and o.value_type is ANY_DESCRIPTOR):
            return True
        if isinstance(o, DictMetadata):
            # 如果其中一个没有具体类型，认为兼容
            if not self.key_type or not o.key_type or not self.value_type or not o.value_type:
                return True
            return self.key_type.is_assignable_to(o.key_type) and \
                   self.value_type.is_assignable_to(o.value_type)
        return False

@dataclass
class FunctionMetadata(TypeDescriptor):
    """函数/方法签名元数据"""
    param_types: List[TypeDescriptor] = field(default_factory=list)
    return_type: Optional[TypeDescriptor] = None

    # --- Trait Implementations ---

    def get_call_trait(self) -> Optional['CallCapability']:
        return self

    def resolve_return(self, args: List['TypeDescriptor']) -> Optional['TypeDescriptor']:
        # 优先使用 Axiom (如果有)
        res = super().resolve_return(args)
        if res: return res
        
        # 回退到静态推导
        if len(args) != len(self.param_types):
            return None
        for i, (expected, actual) in enumerate(zip(self.param_types, args)):
            if not actual.is_assignable_to(expected):
                return None
        return self.return_type

    def is_assignable_to(self, other: TypeDescriptor) -> bool:
        if super().is_assignable_to(other):
            return True
        o = other.unwrap()
        if o is CALLABLE_DESCRIPTOR:
            return True
        if isinstance(o, FunctionMetadata):
            if self.return_type and o.return_type:
                if not self.return_type.is_assignable_to(o.return_type):
                    return False
            if len(self.param_types) != len(o.param_types):
                return False
            for p1, p2 in zip(self.param_types, o.param_types):
                if not p2.is_assignable_to(p1): 
                    return False
            return True
        return False

@dataclass
class ClassMetadata(TypeDescriptor):
    """类元数据描述"""
    parent_name: Optional[str] = None
    parent_module: Optional[str] = None
    
    # --- Trait Implementations ---

    def get_call_trait(self) -> Optional['CallCapability']:
        """类是可调用的（用于实例化）"""
        return self

    def resolve_return(self, args: List['TypeDescriptor']) -> Optional['TypeDescriptor']:
        # 类实例化返回其实例类型（即自身）
        return self

    def resolve_parent(self) -> Optional[TypeDescriptor]:
        if not self.parent_name: return None
        if not self._registry: return None
        return self._registry.resolve(self.parent_name, self.parent_module)

    def is_assignable_to(self, other: TypeDescriptor) -> bool:
        if super().is_assignable_to(other): return True
        parent = self.resolve_parent()
        return parent.is_assignable_to(other) if parent else False

    def resolve_member(self, name: str) -> Optional['Symbol']:
        if name in self.members:
            return self.members[name]
        parent = self.resolve_parent()
        if parent:
            return parent.resolve_member(name)
        return None

@dataclass
class BoundMethodMetadata(TypeDescriptor):
    """绑定方法类型元数据 (合成类型)"""
    receiver_type: Optional[TypeDescriptor] = None
    function_type: Optional[TypeDescriptor] = None

    @property
    def param_types(self) -> List[TypeDescriptor]:
        """[IES 2.1] 代理函数签名的参数列表，并移除第一个 self 参数"""
        if isinstance(self.function_type, FunctionMetadata):
            # 如果是类方法，第一个参数通常是 self，在绑定后应被移除
            if len(self.function_type.param_types) > 0:
                return self.function_type.param_types[1:]
            return self.function_type.param_types
        return []

    @property
    def return_type(self) -> Optional[TypeDescriptor]:
        """代理函数签名的返回类型"""
        if isinstance(self.function_type, FunctionMetadata):
            return self.function_type.return_type
        return None

    # --- Trait Implementations ---

    def get_call_trait(self) -> Optional['CallCapability']:
        return self

    def resolve_return(self, args: List['TypeDescriptor']) -> Optional['TypeDescriptor']:
        if self.function_type:
            # 1. 尝试直接决议 (适用于内置方法，它们在公理中通常不显式声明 self)
            res = self.function_type.resolve_return(args)
            if res: return res
            
            # 2. 如果失败，尝试注入 receiver 后决议 (适用于用户定义的类方法，它们在推导中显式包含了 self 参数)
            if self.receiver_type:
                full_args = [self.receiver_type] + args
                return self.function_type.resolve_return(full_args)
        return None

    def __post_init__(self):
        super().__post_init__()
        # [NEW] 统一绑定方法的名称标识，通过结构化校验实现强类型
        self.name = "bound_method"

    def is_assignable_to(self, other: TypeDescriptor) -> bool:
        if super().is_assignable_to(other):
            return True
        o = other.unwrap()
        if o is CALLABLE_DESCRIPTOR:
            return True
        if isinstance(o, BoundMethodMetadata):
            # 结构化语义校验：接收者与函数签名都必须兼容
            if self.receiver_type and o.receiver_type:
                if not self.receiver_type.is_assignable_to(o.receiver_type):
                    return False
            if self.function_type and o.function_type:
                return self.function_type.is_assignable_to(o.function_type)
        return False

@dataclass
class ModuleMetadata(TypeDescriptor):
    """模块元数据描述"""
    required_capabilities: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        super().__post_init__()
        if not self.name or self.name == "TypeDescriptor":
            self.name = "module"

# 预定义常量描述符 (作为原型存在)
INT_DESCRIPTOR = TypeDescriptor(name="int", is_nullable=False)
STR_DESCRIPTOR = TypeDescriptor(name="str", is_nullable=False)
FLOAT_DESCRIPTOR = TypeDescriptor(name="float", is_nullable=False)
BOOL_DESCRIPTOR = TypeDescriptor(name="bool", is_nullable=False)
VOID_DESCRIPTOR = TypeDescriptor(name="void", is_nullable=False)
ANY_DESCRIPTOR = TypeDescriptor(name="Any", is_nullable=True)
VAR_DESCRIPTOR = TypeDescriptor(name="var", is_nullable=True)
CALLABLE_DESCRIPTOR = TypeDescriptor(name="callable", is_nullable=True)
EXCEPTION_DESCRIPTOR = TypeDescriptor(name="Exception", is_nullable=True)

# [New] Missing Descriptors
NONE_DESCRIPTOR = TypeDescriptor(name="None", is_nullable=True)
BEHAVIOR_DESCRIPTOR = TypeDescriptor(name="behavior", is_nullable=True)
BOUND_METHOD_DESCRIPTOR = BoundMethodMetadata() # name will be "bound_method"

# 集合类型占位描述符 (用于基础元数据注册)
LIST_DESCRIPTOR = ListMetadata(name="list", is_nullable=True)
DICT_DESCRIPTOR = DictMetadata(name="dict", is_nullable=True)
MODULE_DESCRIPTOR = ModuleMetadata(name="module", is_nullable=False)
