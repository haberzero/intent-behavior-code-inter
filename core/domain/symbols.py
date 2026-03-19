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
    uid: Optional[str] = None # [IES 2.1] 唯一标识符，用于解决变量遮蔽 (Shadowing)
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

    def get_content_hash(self) -> str:
        """
        [IES 2.1 Deterministic] 获取符号的内容哈希，用于生成匿名 UID。
        """
        import hashlib
        # 基础特征：名称 + 类型
        parts = [self.name, self.kind.name]
        # 类型特征：描述符全名 (如果存在)
        if self.descriptor:
            parts.append(f"type:{self.descriptor.module_path or 'root'}.{self.descriptor.name}")
        # 元数据特征 (可选，但为了确定性，排除不可序列化的 id)
        for k, v in sorted(self.metadata.items()):
            if isinstance(v, (str, int, float, bool)):
                parts.append(f"{k}:{v}")
        
        content = "|".join(parts)
        return hashlib.sha256(content.encode('utf-8')).hexdigest()[:16]

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
    def __init__(self, parent: Optional['SymbolTable'] = None, name: Optional[str] = None):
        self.parent = parent
        self.name = name # [IES 2.1] 作用域名称 (如函数名、类名)
        self.depth = (parent.depth + 1) if parent else 0 # [IES 2.1] 作用域深度
        self.symbols: Dict[str, Symbol] = {}
        self.global_refs: Set[str] = set() # 记录被 global 关键字显式声明的变量名
        self._uid = None
        self._child_count = 0 # [IES 2.1] 用于生成确定性匿名 UID
        
        if parent:
            parent._child_count += 1
            self._anon_id = parent._child_count

    @property
    def uid(self) -> str:
        """[IES 2.1] 生成确定性作用域 UID"""
        if self._uid: return self._uid
        if not self.parent:
            # 模块/全局作用域：UID = scope_{name}
            name = self.name or "global"
            self._uid = f"scope_{name}"
        else:
            # 嵌套作用域：UID = parent_uid / name
            prefix = self.parent.uid
            # 优先使用名称，否则使用其在父作用域中的确定性序号
            name = self.name or f"anon_{self._anon_id}"
            self._uid = f"{prefix}/{name}"
        return self._uid

    def define(self, sym: Symbol, allow_overwrite: bool = False):
        """定义一个符号，如果已存在且不允许覆盖，则抛出 ValueError"""
        # [IES 2.1 Shadowing] 为符号分配唯一的 UID (基于作用域路径，确保全局唯一)
        # 格式：scope_uid:symbol_name
        # 这确保了即使是同名变量 (Shadowing)，在扁平池中也拥有不同的物理 UID
        if not sym.uid:
            sym.uid = f"{self.uid}:{sym.name}"

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
