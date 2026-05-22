"""
UID-based Metadata Storage

Key insight from V1 limitations:
- V1 uses Python object identity (id()) as dict keys
- This breaks on serialization/deserialization
- V2 uses string UIDs, enabling serialization and cross-process sharing

Design principle: All metadata is keyed by node UID, not object reference.

2026-05-15 立场对齐:
- MetadataStore 只承载 C2/C3 绑定（symbol_bindings / type_bindings / loc_bindings）
- callable_instances / capture_modes / annotations 已删除（AST 字段承载）
- cell_captured_symbols 保留（无 AST 对应字段）
- bind 操作改为 mutable in-place（删除 O(n²) 拷字典反模式）
"""

from typing import Dict, Optional, Any, Set
from dataclasses import dataclass, field


@dataclass
class MetadataStore:
    """
    UID-based metadata storage for AST nodes.

    After 2026-05-15 convergence:
    - symbol_bindings: Node UID → Symbol (C2 binding)
    - type_bindings: Node UID → Type specification (C2 binding)
    - loc_bindings: Node UID → Location info (C3 binding)
    - cell_captured_symbols: Symbol UIDs captured by lambdas (no AST field equivalent)
    """
    # Node UID → Symbol binding (C2)
    symbol_bindings: Dict[str, Any] = field(default_factory=dict)

    # Node UID → Type specification (C2)
    type_bindings: Dict[str, Any] = field(default_factory=dict)

    # Node UID → Location info (C3)
    loc_bindings: Dict[str, Any] = field(default_factory=dict)

    # Set of symbol UIDs captured by lambdas as cells
    cell_captured_symbols: Set[str] = field(default_factory=set)

    @classmethod
    def create_empty(cls) -> 'MetadataStore':
        """Create an empty metadata store"""
        return cls()

    def bind_symbol(self, node_uid: str, symbol: Any) -> None:
        """Bind a symbol to a node (mutable in-place)"""
        self.symbol_bindings[node_uid] = symbol

    def bind_type(self, node_uid: str, type_spec: Any) -> None:
        """Bind a type to a node (mutable in-place)"""
        self.type_bindings[node_uid] = type_spec

    def bind_location(self, node_uid: str, loc: Any) -> None:
        """Bind a location to a node (mutable in-place)"""
        self.loc_bindings[node_uid] = loc

    def add_cell_captured_symbol(self, symbol_uid: str) -> None:
        """Add a symbol to the cell-captured set (mutable in-place)"""
        self.cell_captured_symbols.add(symbol_uid)

    def get_symbol(self, node_uid: str) -> Optional[Any]:
        """Get symbol binding for a node"""
        return self.symbol_bindings.get(node_uid)

    def get_type(self, node_uid: str) -> Optional[Any]:
        """Get type binding for a node"""
        return self.type_bindings.get(node_uid)

    def get_location(self, node_uid: str) -> Optional[Any]:
        """Get location binding for a node"""
        return self.loc_bindings.get(node_uid)

    def is_cell_captured(self, symbol_uid: str) -> bool:
        """Check if symbol is cell-captured"""
        return symbol_uid in self.cell_captured_symbols

    def merge(self, other: 'MetadataStore') -> 'MetadataStore':
        """
        Merge another metadata store into this one (returns new store).

        Used when exiting scopes to propagate metadata from child to parent.
        """
        merged = MetadataStore(
            symbol_bindings={**self.symbol_bindings, **other.symbol_bindings},
            type_bindings={**self.type_bindings, **other.type_bindings},
            loc_bindings={**self.loc_bindings, **other.loc_bindings},
            cell_captured_symbols=self.cell_captured_symbols | other.cell_captured_symbols,
        )
        return merged

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'symbol_count': len(self.symbol_bindings),
            'type_count': len(self.type_bindings),
            'loc_count': len(self.loc_bindings),
            'cell_captured_count': len(self.cell_captured_symbols),
        }
