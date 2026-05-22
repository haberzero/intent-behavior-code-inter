"""
Node-Object-Keyed Metadata Storage

设计决策（2026-05-22 全量替换 v1 准备）:
- 编译期使用 Python 对象身份作为字典键（与 v1 SideTableManager 一致）。
- 序列化器已有成熟的"对象键 → 确定性 UID"转换路径（FlatSerializer._collect_node）。
- 不引入额外 UID 字段到 AST 节点；保持 AST dataclass 不变。

2026-05-15 立场对齐:
- MetadataStore 只承载 C2/C3 绑定（node_to_symbol / node_to_type / node_to_loc）
- callable_instances / capture_modes / annotations 已删除（AST 字段承载）
- cell_captured_symbols 保留（无 AST 对应字段）
- bind 操作为 mutable in-place（删除 O(n²) 拷字典反模式）
"""

from typing import Dict, Optional, Any, Set
from dataclasses import dataclass, field


@dataclass
class MetadataStore:
    """
    Node-object-keyed metadata storage for semantic analysis.

    键为 AST 节点对象（Python object identity），与 v1 SideTableManager 接口对齐。
    序列化阶段由 FlatSerializer 统一将对象键转换为确定性哈希 UID。

    After 2026-05-15 convergence:
    - node_to_symbol: Node object → Symbol (C2 binding)
    - node_to_type: Node object → Type specification (C2 binding)
    - node_to_loc: Node object → Location info (C3 binding)
    - cell_captured_symbols: Symbol UIDs captured by lambdas (no AST field equivalent)
    """
    # Node object → Symbol binding (C2)
    node_to_symbol: Dict[Any, Any] = field(default_factory=dict)

    # Node object → Type specification (C2)
    node_to_type: Dict[Any, Any] = field(default_factory=dict)

    # Node object → Location info (C3)
    node_to_loc: Dict[Any, Any] = field(default_factory=dict)

    # Set of symbol UIDs captured by lambdas as cells
    cell_captured_symbols: Set[str] = field(default_factory=set)

    @classmethod
    def create_empty(cls) -> 'MetadataStore':
        """Create an empty metadata store"""
        return cls()

    def bind_symbol(self, node: Any, symbol: Any) -> None:
        """Bind a symbol to a node (mutable in-place)"""
        self.node_to_symbol[node] = symbol

    def bind_type(self, node: Any, type_spec: Any) -> None:
        """Bind a type to a node (mutable in-place)"""
        self.node_to_type[node] = type_spec

    def bind_location(self, node: Any, loc: Any) -> None:
        """Bind a location to a node (mutable in-place)"""
        self.node_to_loc[node] = loc

    def add_cell_captured_symbol(self, symbol_uid: str) -> None:
        """Add a symbol to the cell-captured set (mutable in-place)"""
        self.cell_captured_symbols.add(symbol_uid)

    def get_symbol(self, node: Any) -> Optional[Any]:
        """Get symbol binding for a node"""
        return self.node_to_symbol.get(node)

    def get_type(self, node: Any) -> Optional[Any]:
        """Get type binding for a node"""
        return self.node_to_type.get(node)

    def get_location(self, node: Any) -> Optional[Any]:
        """Get location binding for a node"""
        return self.node_to_loc.get(node)

    def is_cell_captured(self, symbol_uid: str) -> bool:
        """Check if symbol is cell-captured"""
        return symbol_uid in self.cell_captured_symbols

    def merge(self, other: 'MetadataStore') -> 'MetadataStore':
        """
        Merge another metadata store into this one (returns new store).

        Used when exiting scopes to propagate metadata from child to parent.
        """
        merged = MetadataStore(
            node_to_symbol={**self.node_to_symbol, **other.node_to_symbol},
            node_to_type={**self.node_to_type, **other.node_to_type},
            node_to_loc={**self.node_to_loc, **other.node_to_loc},
            cell_captured_symbols=self.cell_captured_symbols | other.cell_captured_symbols,
        )
        return merged

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for diagnostics"""
        return {
            'symbol_count': len(self.node_to_symbol),
            'type_count': len(self.node_to_type),
            'loc_count': len(self.node_to_loc),
            'cell_captured_count': len(self.cell_captured_symbols),
        }
