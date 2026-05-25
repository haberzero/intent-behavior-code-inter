"""
Node-Object-Keyed Metadata Storage

MetadataStore 承载 C2/C3 绑定（node_to_symbol / node_to_type / node_to_loc）。
实例不可变：由 Pipeline 在所有 Phase 完成后从合并的 PassOutput 构建。
"""

from typing import Dict, Optional, Any, Set
from dataclasses import dataclass, field


@dataclass(frozen=True)
class MetadataStore:
    """Immutable metadata store for semantic analysis results.

    键为 AST 节点对象（Python object identity）。
    序列化阶段由 FlatSerializer 统一将对象键转换为确定性哈希 UID。
    """
    node_to_symbol: Dict[Any, Any] = field(default_factory=dict)
    node_to_type: Dict[Any, Any] = field(default_factory=dict)
    node_to_loc: Dict[Any, Any] = field(default_factory=dict)
    cell_captured_symbols: Set[str] = field(default_factory=set)

    @classmethod
    def create_empty(cls) -> 'MetadataStore':
        return cls()

    @classmethod
    def from_outputs(cls, outputs: 'list') -> 'MetadataStore':
        """Construct a MetadataStore by merging multiple PassOutputs."""
        merged_symbols: Dict[Any, Any] = {}
        merged_types: Dict[Any, Any] = {}
        merged_locs: Dict[Any, Any] = {}
        merged_cells: Set[str] = set()
        for output in outputs:
            merged_symbols.update(output.symbol_bindings)
            merged_types.update(output.type_bindings)
            merged_locs.update(output.location_bindings)
            merged_cells.update(output.cell_captured_symbols)
        return cls(
            node_to_symbol=merged_symbols,
            node_to_type=merged_types,
            node_to_loc=merged_locs,
            cell_captured_symbols=merged_cells,
        )

    def get_symbol(self, node: Any) -> Optional[Any]:
        return self.node_to_symbol.get(node)

    def get_type(self, node: Any) -> Optional[Any]:
        return self.node_to_type.get(node)

    def get_location(self, node: Any) -> Optional[Any]:
        return self.node_to_loc.get(node)

    def is_cell_captured(self, symbol_uid: str) -> bool:
        return symbol_uid in self.cell_captured_symbols

    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol_count': len(self.node_to_symbol),
            'type_count': len(self.node_to_type),
            'loc_count': len(self.node_to_loc),
            'cell_captured_count': len(self.cell_captured_symbols),
        }
