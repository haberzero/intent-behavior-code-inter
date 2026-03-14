from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any, Set, TYPE_CHECKING
from enum import Enum, auto

from .types import descriptors as uts
from .types.descriptors import TypeDescriptor


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
    """静态符号基类"""
    name: str
    kind: SymbolKind
    def_node: Optional[Any] = None # 直接引用定义它的 AST 节点对象
    owned_scope: Optional['SymbolTable'] = None # 符号拥有的内部作用域 (如类、函数的内部作用域)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # [Refactor] 直接持有 TypeDescriptor，不再使用 StaticType 中间层
    descriptor: Optional[TypeDescriptor] = None

    @property
    def type_info(self) -> 'TypeDescriptor':
        """统一获取符号的类型信息"""
        return self.descriptor or uts.ANY_DESCRIPTOR

@dataclass
class TypeSymbol(Symbol):
    """表示一个类型定义 (类或内置类型)"""
    # type_info 直接返回 descriptor (即该类型本身的元数据)
    pass

@dataclass
class FunctionSymbol(Symbol):
    """表示一个函数 (普通函数或 LLM 函数)"""
    
    @property
    def return_type(self) -> TypeDescriptor:
        if isinstance(self.descriptor, uts.FunctionMetadata):
            return self.descriptor.return_type or uts.VOID_DESCRIPTOR
        return uts.ANY_DESCRIPTOR
        
    @property
    def param_types(self) -> List[TypeDescriptor]:
        if isinstance(self.descriptor, uts.FunctionMetadata):
            return self.descriptor.param_types
        return []

@dataclass
class VariableSymbol(Symbol):
    """表示变量或字段"""
    is_const: bool = False
    is_global: bool = False
    
    # descriptor 存储变量的类型

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
    
    def add_global_ref(self, name: str):
        self.global_refs.add(name)

class SymbolFactory:
    """负责将元数据转换为符号对象"""
    @staticmethod
    def create_from_descriptor(name: str, descriptor: TypeDescriptor) -> 'Symbol':
        if isinstance(descriptor, uts.FunctionMetadata):
            return FunctionSymbol(name=name, kind=SymbolKind.FUNCTION, descriptor=descriptor)
        elif isinstance(descriptor, uts.ClassMetadata):
             # 类的符号，其类型就是该类本身 (ClassMetadata)
             # 但注意：Symbol.descriptor 通常代表"这个符号持有的值的类型"
             # 对于类定义 `class Foo`, 符号 Foo 的类型是 `type(Foo)` 还是 `Foo`?
             # 在静态分析中，通常认为 Foo 是一个 TypeSymbol，其 descriptor 指向 ClassMetadata
             return TypeSymbol(name=name, kind=SymbolKind.CLASS, descriptor=descriptor)
        elif isinstance(descriptor, uts.ModuleMetadata):
             return VariableSymbol(name=name, kind=SymbolKind.MODULE, descriptor=descriptor)
        else:
            return VariableSymbol(name=name, kind=SymbolKind.VARIABLE, descriptor=descriptor)
