"""Semantic analysis passes"""

from .base_pass import BasePass
from .symbol_collection_pass import SymbolCollectionPass

__all__ = ['BasePass', 'SymbolCollectionPass']
