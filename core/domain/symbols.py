import copy
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
    
    # [Refactor] 直接持有 TypeDescriptor，不再使用 StaticType 中称层
    descriptor: Optional[TypeDescriptor] = None

    def walk_references(self, callback: Any) -> None:
        """
        [IES 2.1] 遍历符号持有的类型引用。
        """
        if self.descriptor:
            self.descriptor = callback(self.descriptor)

    @property
    def is_type(self) -> bool:
        return self.kind == SymbolKind.CLASS

    @property
    def is_function(self) -> bool:
        return self.kind in (SymbolKind.FUNCTION, SymbolKind.LLM_FUNCTION)

    @property
    def is_variable(self) -> bool:
        return self.kind == SymbolKind.VARIABLE

    def clone(self, memo: Optional[Dict[int, Any]] = None) -> 'Symbol':
        """
        [IES 2.0 Isolation] 克隆符号对象。
        注意：递归克隆关联的描述符以确保物理隔离。
        """
        if memo is None: memo = {}
        if id(self) in memo:
            return memo[id(self)]
            
        new_sym = copy.copy(self)
        memo[id(self)] = new_sym
        
        if self.descriptor:
            new_sym.descriptor = self.descriptor.clone(memo)
        return new_sym

@dataclass
class TypeSymbol(Symbol):
    """表示一个类型定义 (类或内置类型)"""
    pass

@dataclass
class FunctionSymbol(Symbol):
    """表示一个函数 (普通函数或 LLM 函数)"""
    
    @property
    def return_type(self) -> TypeDescriptor:
        sig = self.descriptor.get_signature() if self.descriptor else None
        if sig:
            _, ret = sig
            return ret or uts.VOID_DESCRIPTOR
        return uts.ANY_DESCRIPTOR
        
    @property
    def param_types(self) -> List[TypeDescriptor]:
        sig = self.descriptor.get_signature() if self.descriptor else None
        if sig:
            params, _ = sig
            return params
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
            # [IES 2.1 UTS Integration] 内置符号允许通过 identity (Interning) 判定一致性，消除名称比对的脆弱性
            if existing.metadata.get("is_builtin") and sym.metadata.get("is_builtin"):
                if existing.descriptor and sym.descriptor:
                    # 在 UTS 体系下，Interning 确保了同类描述符在同一引擎下是唯一的
                    if existing.descriptor is not sym.descriptor:
                         raise ValueError(f"Builtin Symbol Conflict: Symbol '{sym.name}' redefined with incompatible descriptor (existing: '{existing.descriptor.name}')")
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
        if descriptor.get_call_trait() and not descriptor.is_class():
            return FunctionSymbol(name=name, kind=SymbolKind.FUNCTION, descriptor=descriptor)
        elif descriptor.is_class():
            # 类符号描述符指向 ClassMetadata，表示该符号代表类定义本身。
            return TypeSymbol(name=name, kind=SymbolKind.CLASS, descriptor=descriptor)
        elif descriptor.is_module():
            return VariableSymbol(name=name, kind=SymbolKind.MODULE, descriptor=descriptor)
        else:
            return VariableSymbol(name=name, kind=SymbolKind.VARIABLE, descriptor=descriptor)
