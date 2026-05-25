"""Metadata package initialization"""

from .metadata_store import MetadataStore
from .symbol_table import SymbolTableContext
from .type_environment import TypeInferenceState, TypeEnvironment, TypeSlot, TypeSlotConflict

__all__ = [
    'MetadataStore',
    'SymbolTableContext',
    'TypeInferenceState',
    'TypeEnvironment',  # backward compat alias
    'TypeSlot',
    'TypeSlotConflict',
]
