"""
UID-based Metadata Storage

Key insight from V1 limitations:
- V1 uses Python object identity (id()) as dict keys
- This breaks on serialization/deserialization
- V2 uses string UIDs, enabling serialization and cross-process sharing

Design principle: All metadata is keyed by node UID, not object reference.
"""

from typing import Dict, Optional, Any, Set
from dataclasses import dataclass, field


@dataclass
class MetadataStore:
    """
    UID-based metadata storage for AST nodes.

    Replaces V1's side_table.py which used object identity.

    Advantages over V1:
    - Serializable (UIDs are strings)
    - Works across process boundaries
    - Survives AST reconstruction
    - No memory leaks from holding node references
    """
    # Node UID → Symbol binding
    symbol_bindings: Dict[str, Any] = field(default_factory=dict)

    # Node UID → Type specification
    type_bindings: Dict[str, Any] = field(default_factory=dict)

    # Node UID → Whether it's a callable instance
    callable_instances: Set[str] = field(default_factory=set)

    # Node UID → Capture mode for lambda variables
    capture_modes: Dict[str, str] = field(default_factory=dict)

    # Set of symbol UIDs captured by lambdas as cells
    cell_captured_symbols: Set[str] = field(default_factory=set)

    # Additional annotations (extensible)
    annotations: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    @classmethod
    def create_empty(cls) -> 'MetadataStore':
        """Create an empty metadata store"""
        return cls()

    def bind_symbol(self, node_uid: str, symbol: Any) -> 'MetadataStore':
        """Bind a symbol to a node (returns new store)"""
        new_bindings = {**self.symbol_bindings, node_uid: symbol}
        return MetadataStore(
            symbol_bindings=new_bindings,
            type_bindings=self.type_bindings,
            callable_instances=self.callable_instances,
            capture_modes=self.capture_modes,
            cell_captured_symbols=self.cell_captured_symbols,
            annotations=self.annotations
        )

    def bind_type(self, node_uid: str, type_spec: Any) -> 'MetadataStore':
        """Bind a type to a node (returns new store)"""
        new_bindings = {**self.type_bindings, node_uid: type_spec}
        return MetadataStore(
            symbol_bindings=self.symbol_bindings,
            type_bindings=new_bindings,
            callable_instances=self.callable_instances,
            capture_modes=self.capture_modes,
            cell_captured_symbols=self.cell_captured_symbols,
            annotations=self.annotations
        )

    def mark_callable_instance(self, node_uid: str) -> 'MetadataStore':
        """Mark a node as a callable instance (returns new store)"""
        new_callables = self.callable_instances | {node_uid}
        return MetadataStore(
            symbol_bindings=self.symbol_bindings,
            type_bindings=self.type_bindings,
            callable_instances=new_callables,
            capture_modes=self.capture_modes,
            cell_captured_symbols=self.cell_captured_symbols,
            annotations=self.annotations
        )

    def set_capture_mode(self, node_uid: str, mode: str) -> 'MetadataStore':
        """Set capture mode for a lambda variable (returns new store)"""
        new_modes = {**self.capture_modes, node_uid: mode}
        return MetadataStore(
            symbol_bindings=self.symbol_bindings,
            type_bindings=self.type_bindings,
            callable_instances=self.callable_instances,
            capture_modes=new_modes,
            cell_captured_symbols=self.cell_captured_symbols,
            annotations=self.annotations
        )

    def add_cell_captured_symbol(self, symbol_uid: str) -> 'MetadataStore':
        """Add a symbol to the cell-captured set (returns new store)"""
        new_cells = self.cell_captured_symbols | {symbol_uid}
        return MetadataStore(
            symbol_bindings=self.symbol_bindings,
            type_bindings=self.type_bindings,
            callable_instances=self.callable_instances,
            capture_modes=self.capture_modes,
            cell_captured_symbols=new_cells,
            annotations=self.annotations
        )

    def annotate(self, node_uid: str, key: str, value: Any) -> 'MetadataStore':
        """Add arbitrary annotation to a node (returns new store)"""
        new_annotations = {**self.annotations}
        if node_uid not in new_annotations:
            new_annotations[node_uid] = {}
        new_annotations[node_uid] = {**new_annotations[node_uid], key: value}
        return MetadataStore(
            symbol_bindings=self.symbol_bindings,
            type_bindings=self.type_bindings,
            callable_instances=self.callable_instances,
            capture_modes=self.capture_modes,
            cell_captured_symbols=self.cell_captured_symbols,
            annotations=new_annotations
        )

    def get_symbol(self, node_uid: str) -> Optional[Any]:
        """Get symbol binding for a node"""
        return self.symbol_bindings.get(node_uid)

    def get_type(self, node_uid: str) -> Optional[Any]:
        """Get type binding for a node"""
        return self.type_bindings.get(node_uid)

    def is_callable_instance(self, node_uid: str) -> bool:
        """Check if node is marked as callable instance"""
        return node_uid in self.callable_instances

    def get_capture_mode(self, node_uid: str) -> Optional[str]:
        """Get capture mode for a node"""
        return self.capture_modes.get(node_uid)

    def is_cell_captured(self, symbol_uid: str) -> bool:
        """Check if symbol is cell-captured"""
        return symbol_uid in self.cell_captured_symbols

    def get_annotation(self, node_uid: str, key: str, default: Any = None) -> Any:
        """Get arbitrary annotation"""
        return self.annotations.get(node_uid, {}).get(key, default)

    def merge(self, other: 'MetadataStore') -> 'MetadataStore':
        """
        Merge another metadata store into this one (returns new store).

        Used when exiting scopes to propagate metadata from child to parent.
        """
        return MetadataStore(
            symbol_bindings={**self.symbol_bindings, **other.symbol_bindings},
            type_bindings={**self.type_bindings, **other.type_bindings},
            callable_instances=self.callable_instances | other.callable_instances,
            capture_modes={**self.capture_modes, **other.capture_modes},
            cell_captured_symbols=self.cell_captured_symbols | other.cell_captured_symbols,
            annotations={**self.annotations, **other.annotations}
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'symbol_count': len(self.symbol_bindings),
            'type_count': len(self.type_bindings),
            'callable_instances': list(self.callable_instances),
            'capture_modes': self.capture_modes,
            'cell_captured_count': len(self.cell_captured_symbols),
            'annotation_count': len(self.annotations)
        }
