from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any, Union, Set
from enum import Enum, auto

from . import types as uts


# --- 符号系统 (Symbol System) ---

class SymbolKind(Enum):
    VARIABLE = auto()
    FUNCTION = auto()
    LLM_FUNCTION = auto()
    CLASS = auto()
    BUILTIN_TYPE = auto()
    INTENT = auto()
    MODULE = auto()

@dataclass(eq=False)
class Symbol:
    """静态符号基类，不依赖运行时对象"""
    name: str
    kind: SymbolKind
    def_node: Optional[Any] = None # 直接引用定义它的 AST 节点对象
    owned_scope: Optional['SymbolTable'] = None # 符号拥有的内部作用域 (如类、函数的内部作用域)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def type_info(self) -> 'StaticType':
        """统一获取符号的类型信息"""
        return STATIC_ANY


# --- 静态类型系统 (Static Type System) ---

@dataclass
class StaticType:
    """
    编译器前端使用的静态类型基类。
    贯彻“一切皆对象”思想：类型对象持有其自身的语义行为协议。
    """
    name: str
    descriptor: Optional[uts.TypeDescriptor] = None
    
    @property
    def prompt_name(self) -> str:
        """返回用于 LLM 提示词的类型名称"""
        return self.name

    def is_assignable_to(self, other: 'StaticType') -> bool:
        """检查当前类型是否可以赋值给目标类型"""
        if self.name == "void" or self.name in ("Any", "var") or other.name in ("Any", "var"): 
            return True
        
        if self.descriptor and other.descriptor:
            return self.descriptor.is_assignable_to(other.descriptor)
            
        return self.name == other.name

    # --- 行为协议 (Behavioral Protocols) ---

    def resolve_member(self, name: str) -> Optional['Symbol']:
        """解析成员访问 (e.g. obj.member)"""
        if self.name in ("Any", "var"):
            return VariableSymbol(name=name, kind=SymbolKind.VARIABLE, var_type=STATIC_ANY)
        
        if not self.descriptor:
            return None
            
        metadata = self.descriptor.resolve_member(name)
        if not metadata:
            return None
            
        return SymbolFactory.create_from_descriptor(name, metadata)

    def get_attribute_type(self, name: str) -> 'StaticType':
        """获取属性访问的结果类型"""
        sym = self.resolve_member(name)
        return sym.type_info if sym else STATIC_ANY

    @property
    def is_callable(self) -> bool:
        """是否支持调用行为"""
        if self.name in ("Any", "var"):
            return True
        return self.descriptor.get_call_trait() is not None if self.descriptor else False

    def get_call_return(self, args: List['StaticType']) -> Optional['StaticType']:
        """解析调用行为"""
        if self.name in ("Any", "var"):
            return STATIC_ANY
            
        if not self.descriptor:
            return None
            
        call_trait = self.descriptor.get_call_trait()
        if not call_trait:
            return None
            
        # 将静态参数转换为描述符进行校验
        arg_descriptors = [a.descriptor for a in args if a.descriptor]
        if len(arg_descriptors) != len(args):
            return STATIC_ANY # 降级处理
            
        ret_descriptor = call_trait.resolve_return(arg_descriptors)
        if not ret_descriptor:
            return None
            
        return StaticTypeFactory.create_from_descriptor(ret_descriptor)

    def get_operator_result(self, op: str, other: Optional['StaticType'] = None) -> Optional['StaticType']:
        """解析运算符行为 (委托给描述符)"""
        if self.name in ("Any", "var") or (other and other.name in ("Any", "var")):
            return STATIC_ANY

        if not self.descriptor:
            return None
            
        other_descriptor = other.descriptor if other else None
        ret_descriptor = self.descriptor.get_operator_result(op, other_descriptor)
        if not ret_descriptor:
            return None
            
        return StaticTypeFactory.create_from_descriptor(ret_descriptor)

    @property
    def is_iterable(self) -> bool:
        """是否支持迭代 (e.g. for x in obj)"""
        if self.name in ("Any", "var"):
            return True
        return self.descriptor.get_iter_trait() is not None if self.descriptor else False

    def get_iterator_type(self) -> 'StaticType':
        """获取迭代产生的元素类型"""
        if self.name in ("Any", "var"):
            return STATIC_ANY
        if not self.descriptor:
            return STATIC_ANY
        
        iter_trait = self.descriptor.get_iter_trait()
        if not iter_trait:
            return STATIC_ANY
            
        ret_desc = iter_trait.get_element_type()
        return StaticTypeFactory.create_from_descriptor(ret_desc) if ret_desc else STATIC_ANY

    @property
    def is_subscriptable(self) -> bool:
        """是否支持下标访问 (e.g. obj[key])"""
        if self.name in ("Any", "var"):
            return True
        return self.descriptor.get_subscript_trait() is not None if self.descriptor else False

    def get_subscript_type(self, key_type: 'StaticType') -> 'StaticType':
        """获取下标访问的结果类型"""
        if self.name in ("Any", "var"):
            return STATIC_ANY
        if not self.descriptor:
            return STATIC_ANY
            
        sub_trait = self.descriptor.get_subscript_trait()
        if not sub_trait:
            return STATIC_ANY
            
        ret_desc = sub_trait.resolve_item(key_type.descriptor) if key_type.descriptor else None
        return StaticTypeFactory.create_from_descriptor(ret_desc) if ret_desc else STATIC_ANY

    @property
    def is_class(self) -> bool:
        """是否为类定义"""
        return False

    @property
    def is_module(self) -> bool:
        """是否为模块"""
        return False

class StaticTypeFactory:
    """负责从描述符创建静态类型对象，解决循环引用"""
    @staticmethod
    def create_from_descriptor(descriptor: uts.TypeDescriptor) -> 'StaticType':
        if not descriptor: return STATIC_ANY
        
        # 1. 如果描述符已经关联了静态类型，直接返回
        if hasattr(descriptor, '_static_type') and descriptor._static_type:
            return descriptor._static_type
            
        # 2. 根据描述符种类创建对应的静态类型
        if isinstance(descriptor, uts.PrimitiveDescriptor):
            st = BuiltinType(descriptor.name, descriptor=descriptor)
        elif isinstance(descriptor, uts.ListMetadata):
            element_type = StaticTypeFactory.create_from_descriptor(descriptor.element_type) if descriptor.element_type else STATIC_ANY
            st = ListType(element_type, descriptor=descriptor)
        elif isinstance(descriptor, uts.DictMetadata):
            key_type = StaticTypeFactory.create_from_descriptor(descriptor.key_type) if descriptor.key_type else STATIC_ANY
            val_type = StaticTypeFactory.create_from_descriptor(descriptor.value_type) if descriptor.value_type else STATIC_ANY
            st = DictType(key_type, val_type, descriptor=descriptor)
        elif isinstance(descriptor, uts.FunctionMetadata):
            params = [StaticTypeFactory.create_from_descriptor(p) for p in descriptor.param_types]
            ret = StaticTypeFactory.create_from_descriptor(descriptor.return_type) if descriptor.return_type else STATIC_VOID
            # [FIX] 显式传递描述符中的名称，避免默认降级为 "callable"
            st = FunctionType(params, ret, name=descriptor.name or "callable", descriptor=descriptor)
        elif isinstance(descriptor, uts.ClassMetadata):
            st = ClassType(descriptor.name, descriptor=descriptor)
        else:
            st = StaticType(descriptor.name, descriptor=descriptor)
            
        # 缓存关联
        descriptor._static_type = st
        return st

class SymbolFactory:
    """负责将元数据转换为符号对象"""
    @staticmethod
    def create_from_descriptor(name: str, descriptor: uts.TypeDescriptor) -> 'Symbol':
        type_info = StaticTypeFactory.create_from_descriptor(descriptor)
        
        if isinstance(descriptor, uts.FunctionMetadata):
            return FunctionSymbol(name=name, kind=SymbolKind.FUNCTION, type_signature=type_info)
        else:
            return VariableSymbol(name=name, kind=SymbolKind.VARIABLE, var_type=type_info)

class BehaviorType(StaticType):
    """行为描述行类型：在语义上它可以被视为 str，也可以被视为 function (Lambda)"""
    def __init__(self):
        super().__init__("behavior")

    @property
    def prompt_name(self) -> str:
        return "str"

    def is_assignable_to(self, other: 'StaticType') -> bool:
        if super().is_assignable_to(other):
            return True
        # 行为描述行兼容 字符串 和 可调用类型
        return other.name in ("str", "callable", "Any", "var")

    @property
    def is_callable(self) -> bool:
        return True

    def get_call_return(self, args: List['StaticType']) -> Optional['StaticType']:
        # 调用后返回字符串结果
        return STATIC_STR

class BuiltinType(StaticType):
    """内置原子类型 (int, str, bool, float)"""
    def __init__(self, name: str, descriptor: Optional[uts.TypeDescriptor] = None):
        super().__init__(name, descriptor=descriptor)

class ListType(BuiltinType):
    """内置列表类型，支持元素类型推导"""
    def __init__(self, element_type: Optional[StaticType] = None, descriptor: Optional[uts.TypeDescriptor] = None):
        super().__init__("list", descriptor=descriptor)
        self._element_type = element_type or STATIC_ANY

    @property
    def element_type(self) -> StaticType:
        return self._element_type

class DictType(BuiltinType):
    """内置字典类型，支持键值类型推导"""
    def __init__(self, key_type: Optional[StaticType] = None, value_type: Optional[StaticType] = None, descriptor: Optional[uts.TypeDescriptor] = None):
        super().__init__("dict", descriptor=descriptor)
        self._key_type = key_type or STATIC_ANY
        self._value_type = value_type or STATIC_ANY

    @property
    def key_type(self) -> StaticType:
        return self._key_type

    @property
    def value_type(self) -> StaticType:
        return self._value_type

# --- 常量类型实例 (作为原型) ---
STATIC_ANY = BuiltinType("Any", descriptor=uts.ANY_DESCRIPTOR)
STATIC_VOID = BuiltinType("void", descriptor=uts.VOID_DESCRIPTOR)
STATIC_INT = BuiltinType("int", descriptor=uts.INT_DESCRIPTOR)
STATIC_STR = BuiltinType("str", descriptor=uts.STR_DESCRIPTOR)
STATIC_FLOAT = BuiltinType("float", descriptor=uts.FLOAT_DESCRIPTOR)
STATIC_BOOL = BuiltinType("bool", descriptor=uts.BOOL_DESCRIPTOR)
STATIC_LIST = ListType(STATIC_ANY, descriptor=uts.LIST_DESCRIPTOR)
STATIC_DICT = DictType(STATIC_ANY, STATIC_ANY, descriptor=uts.DICT_DESCRIPTOR)
STATIC_CALLABLE = BuiltinType("callable", descriptor=uts.CALLABLE_DESCRIPTOR)
STATIC_BEHAVIOR = BehaviorType()

class ClassType(StaticType):
    """用户定义的类类型"""
    def __init__(self, name: str, parent: Optional['ClassType'] = None, descriptor: Optional[uts.ClassMetadata] = None):
        super().__init__(name, descriptor=descriptor)
        self.parent = parent

    @property
    def is_class(self) -> bool:
        return True

    def resolve_member(self, name: str) -> Optional['Symbol']:
        # 1. 彻底委托给描述符决议 (描述符内部已处理继承链)
        if not self.descriptor:
            return None
            
        metadata = self.descriptor.resolve_member(name)
        if not metadata:
            return None
            
        # 2. 包装为符号
        sym = SymbolFactory.create_from_descriptor(name, metadata)
        
        # 3. 绑定方法逻辑：如果是函数元数据，在符号层包装为 BoundMethodType
        if isinstance(metadata, uts.FunctionMetadata):
            return VariableSymbol(
                name=name, 
                kind=SymbolKind.VARIABLE, 
                var_type=BoundMethodType(self, StaticTypeFactory.create_from_descriptor(metadata))
            )
            
        return sym

    def get_call_return(self, args: List['StaticType']) -> Optional['StaticType']:
        # 类调用返回其实例类型（即自身）
        # 增加构造函数参数校验
        init_sym = self.resolve_member("__init__")
        if init_sym:
            init_type = init_sym.type_info
            if isinstance(init_type, (FunctionType, BoundMethodType)):
                # 校验参数 (BoundMethodType 已经处理了 self)
                if not init_type.get_call_return(args):
                    return None
        return self

class FunctionType(StaticType):
    """函数或方法的类型签名 (语言层表现为 callable)"""
    def __init__(self, param_types: List[StaticType], return_type: StaticType, name: str = "callable", descriptor: Optional[uts.FunctionMetadata] = None):
        super().__init__(name, descriptor=descriptor)
        self.param_types = param_types
        self.return_type = return_type

    @property
    def is_callable(self) -> bool:
        return True

    def get_call_return(self, args: List['StaticType']) -> Optional['StaticType']:
        if self.descriptor:
            # [FIX] 优先通过描述符进行调用决议 (使用 Trait 模式)
            call_trait = self.descriptor.get_call_trait()
            if call_trait:
                arg_descriptors = [a.descriptor for a in args if a.descriptor]
                if len(arg_descriptors) == len(args):
                    ret_descriptor = call_trait.resolve_return(arg_descriptors)
                    if ret_descriptor:
                        return StaticTypeFactory.create_from_descriptor(ret_descriptor)
        
        # 回退逻辑 (当描述符不可用或未覆盖时)
        if len(args) != len(self.param_types):
            return None
        for i, (expected, actual) in enumerate(zip(self.param_types, args)):
            if not actual.is_assignable_to(expected):
                return None
        return self.return_type

class BoundMethodType(StaticType):
    """绑定方法类型：包装了实例（或其实例类型）的函数签名"""
    def __init__(self, instance_type: StaticType, method_type: 'FunctionType'):
        # [Phase 1.4] 结构化合成描述符
        descriptor = None
        if instance_type.descriptor and isinstance(method_type.descriptor, uts.FunctionMetadata):
             descriptor = uts.BoundMethodMetadata(
                 receiver_type=instance_type.descriptor,
                 function_type=method_type.descriptor
             )
        
        super().__init__("bound_method", descriptor=descriptor)
        self.instance_type = instance_type
        self.method_type = method_type

    @property
    def is_callable(self) -> bool:
        return True

    def get_call_return(self, args: List[StaticType]) -> Optional[StaticType]:
        # 核心：在调用点自动注入实例类型作为第一个参数 (self) 进行签名校验
        return self.method_type.get_call_return([self.instance_type] + args)

class ModuleType(StaticType):
    """模块类型：支持通过属性访问导出符号"""
    def __init__(self, name: str, exported_scope: 'SymbolTable'):
        super().__init__(f"module<{name}>")
        self.exported_scope = exported_scope

    @property
    def is_module(self) -> bool:
        return True

    def resolve_member(self, name: str) -> Optional['Symbol']:
        return self.exported_scope.resolve(name)

# --- 符号系统子类 ---

@dataclass
class TypeSymbol(Symbol):
    """表示一个类型定义 (类或内置类型)"""
    static_type: Optional[StaticType] = None
    
    @property
    def type_info(self) -> 'StaticType':
        return self.static_type or STATIC_ANY

@dataclass
class FunctionSymbol(Symbol):
    """表示一个函数 (普通函数或 LLM 函数)"""
    type_signature: Optional[FunctionType] = None # 重命名以避免冲突
    is_llm: bool = False
    
    @property
    def type_info(self) -> 'StaticType':
        return self.type_signature or STATIC_ANY
        
    @property
    def return_type(self) -> StaticType:
        return self.type_signature.return_type if self.type_signature else STATIC_ANY
        
    @property
    def param_types(self) -> List[StaticType]:
        return self.type_signature.param_types if self.type_signature else []

@dataclass
class VariableSymbol(Symbol):
    """表示变量或字段"""
    var_type: Optional[StaticType] = None # 重命名以避免冲突
    is_const: bool = False
    is_global: bool = False
    
    @property
    def type_info(self) -> 'StaticType':
        return self.var_type or STATIC_ANY

@dataclass
class IntentSymbol(Symbol):
    """表示一个意图块"""
    content: str = ""
    is_exclusive: bool = False
    parent_intent: Optional['IntentSymbol'] = None

class SymbolTable:
    """
    静态符号表，支持作用域嵌套。
    用于语义分析阶段。
    """
    def __init__(self, parent: Optional['SymbolTable'] = None):
        self.parent = parent
        self.symbols: Dict[str, Symbol] = {}
        self.global_refs: Set[str] = set() # 记录被 global 关键字显式声明的变量名

    def define(self, sym: Symbol, allow_overwrite: bool = False):
        """定义一个符号，如果已存在且不允许覆盖，则抛出 ValueError"""
        if not allow_overwrite and sym.name in self.symbols:
            existing = self.symbols[sym.name]
            # [FIX] 如果是内置符号且类型/属性相同，允许静默跳过或覆盖
            if existing.metadata.get("is_builtin") and sym.metadata.get("is_builtin"):
                self.symbols[sym.name] = sym
                return
            raise ValueError(f"Symbol '{sym.name}' is already defined in this scope")
        self.symbols[sym.name] = sym

    def resolve(self, name: str) -> Optional[Symbol]:
        if name in self.symbols:
            return self.symbols[name]
        if self.parent:
            return self.parent.resolve(name)
        return None

    def get_global_scope(self) -> 'SymbolTable':
        """获取顶层全局作用域"""
        curr = self
        while curr.parent:
            curr = curr.parent
        return curr

def get_builtin_type(name: str) -> Optional[StaticType]:
    """[Factory] 获取静态内置类型的单例"""
    mapping = {
        "var": STATIC_ANY,
        "Any": STATIC_ANY,
        "int": STATIC_INT,
        "float": STATIC_FLOAT,
        "str": STATIC_STR,
        "bool": STATIC_BOOL,
        "list": STATIC_LIST,
        "dict": STATIC_DICT,
        "callable": STATIC_CALLABLE,
        "void": STATIC_VOID,
        "none": STATIC_VOID
    }
    return mapping.get(name)
