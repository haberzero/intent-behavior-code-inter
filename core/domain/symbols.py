from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any, Union, Set
from enum import Enum, auto

from . import types as uts

import uuid


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
    
    def is_assignable_to(self, other: 'StaticType') -> bool:
        """检查当前类型是否可以赋值给目标类型"""
        # [NEW] None (void) 允许赋值给任何非 void 变量 (或 Any)
        if self.name == "void" or self.name in ("Any", "var") or other.name in ("Any", "var"): 
            return True
        
        # 优先委托给 UTS 描述符进行逻辑判定
        if self.descriptor and other.descriptor:
            return self.descriptor.is_assignable_to(other.descriptor)
            
        return self.name == other.name

    # --- 行为协议 (Behavioral Protocols) ---

    def resolve_member(self, name: str) -> Optional['Symbol']:
        """解析成员访问 (e.g. obj.member)"""
        if self.name in ("Any", "var"):
            return VariableSymbol(name=name, kind=SymbolKind.VARIABLE, var_type=STATIC_ANY)
        return None

    def get_attribute_type(self, name: str) -> 'StaticType':
        """获取属性访问的结果类型"""
        sym = self.resolve_member(name)
        return sym.type_info if sym else STATIC_ANY

    @property
    def is_callable(self) -> bool:
        """是否支持调用行为 (e.g. func())"""
        return self.name in ("Any", "var")

    def get_call_return(self, args: List['StaticType']) -> Optional['StaticType']:
        """解析调用行为 (e.g. func(a, b))"""
        if self.name in ("Any", "var"):
            return STATIC_ANY
        return None

    def get_operator_result(self, op: str, other: Optional['StaticType'] = None) -> Optional['StaticType']:
        """解析运算符行为 (委托给描述符)"""
        # 基础类型运算逻辑协议化：由 symbols 决定最终类型，由描述符决定逻辑。
        # 这里保留简单的内置快捷路径，复杂的逻辑未来由 UTS 描述符统一。
        if self.name in ("Any", "var"):
            return STATIC_ANY
            
        n1 = self.name
        if not other:
            if op == '~' and n1 == "int": return STATIC_INT
            return None
            
        n2 = other.name
        if n1 == "int" and n2 == "int":
            if op in ('+', '-', '*', '/', '//', '%', '&', '|', '^', '<<', '>>'): return STATIC_INT
            if op in ('>', '>=', '<', '<=', '==', '!='): return STATIC_BOOL
            
        if (n1 in ("int", "float")) and (n2 in ("int", "float")):
            if op in ('+', '-', '*', '/'): return STATIC_FLOAT
            if op in ('>', '>=', '<', '<=', '==', '!='): return STATIC_BOOL
            
        if n1 == "str" and n2 == "str" and op == '+':
            return STATIC_STR
            
        return None

    @property
    def is_iterable(self) -> bool:
        """是否支持迭代 (e.g. for x in obj)"""
        return self.name in ("Any", "var")

    def get_iterator_type(self) -> 'StaticType':
        """获取迭代产生的元素类型"""
        return STATIC_ANY

    @property
    def is_subscriptable(self) -> bool:
        """是否支持下标访问 (e.g. obj[key])"""
        return self.name in ("Any", "var")

    def get_subscript_type(self, key_type: 'StaticType') -> 'StaticType':
        """获取下标访问的结果类型"""
        return STATIC_ANY

    @property
    def is_class(self) -> bool:
        """是否为类定义"""
        return False

    @property
    def is_module(self) -> bool:
        """是否为模块"""
        return False

class BehaviorType(StaticType):
    """行为描述行类型：在语义上它可以被视为 str，也可以被视为 function (Lambda)"""
    def __init__(self):
        super().__init__("behavior")

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
    @property
    def is_callable(self) -> bool:
        # 内置类型（如 int, str）允许调用，表示类型转换/构造
        return True

    def get_call_return(self, args: List['StaticType']) -> Optional['StaticType']:
        # 内置类型调用返回其自身类型
        return self

    def get_operator_result(self, op: str, other: Optional['StaticType'] = None) -> Optional['StaticType']:
        # 基础类型运算逻辑协议化
        n1 = self.name
        if not other: # 一元运算
            if op == '~' and n1 == "int": return STATIC_INT
            return None
            
        n2 = other.name
        if n1 == "int" and n2 == "int":
            if op in ('+', '-', '*', '/', '//', '%', '&', '|', '^', '<<', '>>'): return STATIC_INT
            if op in ('>', '>=', '<', '<=', '==', '!='): return STATIC_BOOL
            
        if (n1 in ("int", "float")) and (n2 in ("int", "float")):
            if op in ('+', '-', '*', '/'): return STATIC_FLOAT
            if op in ('>', '>=', '<', '<=', '==', '!='): return STATIC_BOOL
            
        if n1 == "str" and n2 == "str" and op == '+':
            return STATIC_STR
            
        return super().get_operator_result(op, other)

# --- 常量类型实例 ---
STATIC_ANY = BuiltinType("Any", descriptor=uts.ANY_DESCRIPTOR)
STATIC_VOID = BuiltinType("void", descriptor=uts.VOID_DESCRIPTOR)
STATIC_INT = BuiltinType("int", descriptor=uts.INT_DESCRIPTOR)
STATIC_STR = BuiltinType("str", descriptor=uts.STR_DESCRIPTOR)
STATIC_FLOAT = BuiltinType("float", descriptor=uts.FLOAT_DESCRIPTOR)
STATIC_BOOL = BuiltinType("bool", descriptor=uts.BOOL_DESCRIPTOR)
STATIC_BEHAVIOR = BehaviorType()

class ListType(BuiltinType):
    """内置列表类型，支持元素类型推导"""
    def __init__(self, element_type: StaticType = STATIC_ANY):
        super().__init__("list")
        self._element_type = element_type
        
    @property
    def is_iterable(self) -> bool:
        return True

    def get_iterator_type(self) -> StaticType:
        """实现迭代协议以获取元素类型"""
        return self._element_type

    @property
    def is_subscriptable(self) -> bool:
        return True

    def get_subscript_type(self, key_type: StaticType) -> StaticType:
        # 目前简化：列表下标访问返回元素类型
        return self._element_type

class DictType(BuiltinType):
    """内置字典类型，支持键值类型推导"""
    def __init__(self, key_type: StaticType = STATIC_ANY, value_type: StaticType = STATIC_ANY):
        super().__init__("dict")
        self._key_type = key_type
        self._value_type = value_type
        
    @property
    def key_type(self) -> StaticType:
        return self._key_type
        
    @property
    def value_type(self) -> StaticType:
        return self._value_type

    @property
    def is_iterable(self) -> bool:
        # 字典迭代产生键
        return True

    def get_iterator_type(self) -> StaticType:
        return self._key_type

    @property
    def is_subscriptable(self) -> bool:
        return True

    def get_subscript_type(self, key_type: StaticType) -> StaticType:
        return self._value_type

class ClassType(StaticType):
    """用户定义的类类型"""
    def __init__(self, name: str, parent: Optional['ClassType'] = None, scope: Optional['SymbolTable'] = None):
        super().__init__(name)
        self.parent = parent
        self.scope = scope # 类的成员作用域

    @property
    def is_class(self) -> bool:
        return True

    @property
    def is_callable(self) -> bool:
        return True

    def is_assignable_to(self, other: 'StaticType') -> bool:
        if super().is_assignable_to(other):
            return True
        if isinstance(other, ClassType):
            # 检查继承链
            curr = self.parent
            while curr:
                if curr.name == other.name:
                    return True
                curr = curr.parent
        return False

    def resolve_member(self, name: str) -> Optional['Symbol']:
        sym = None
        if self.scope:
            sym = self.scope.resolve(name)
        
        if not sym and self.parent:
            sym = self.parent.resolve_member(name)
            
        # [NEW] 绑定方法逻辑：如果成员是函数/方法，返回其绑定后的版本
        if sym and sym.kind in (SymbolKind.FUNCTION, SymbolKind.LLM_FUNCTION):
            sig = sym.type_info
            if isinstance(sig, FunctionType):
                # 返回包装了 BoundMethodType 的符号
                return VariableSymbol(name=name, kind=SymbolKind.VARIABLE, var_type=BoundMethodType(self, sig))
                
        return sym

    def get_call_return(self, args: List['StaticType']) -> Optional['StaticType']:
        # 类调用返回其实例类型（即自身）
        # [NEW] 增加构造函数参数校验
        init_sym = self.resolve_member("__init__")
        if init_sym and init_sym.kind == SymbolKind.FUNCTION:
            init_type = init_sym.type_info
            if isinstance(init_type, FunctionType):
                # 校验时需加上隐含的 self 参数
                if not init_type.get_call_return([self] + args):
                    return None
        return self

class FunctionType(StaticType):
    """函数或方法的类型签名 (语言层表现为 callable)"""
    def __init__(self, param_types: List[StaticType], return_type: StaticType, name: str = "callable"):
        super().__init__("callable")
        self.param_types = param_types
        self.return_type = return_type

    @property
    def is_callable(self) -> bool:
        return True

    def get_call_return(self, args: List['StaticType']) -> Optional['StaticType']:
        if len(args) != len(self.param_types):
            return None
        for i, (expected, actual) in enumerate(zip(self.param_types, args)):
            if not actual.is_assignable_to(expected):
                return None
        return self.return_type

class BoundMethodType(StaticType):
    """绑定方法类型：包装了实例（或其实例类型）的函数签名"""
    def __init__(self, instance_type: StaticType, method_type: 'FunctionType'):
        super().__init__(f"bound_method<{method_type.name}>")
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
        "void": STATIC_VOID,
        "none": STATIC_VOID
    }
    return mapping.get(name)
