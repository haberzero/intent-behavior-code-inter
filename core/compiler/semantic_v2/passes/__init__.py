"""Semantic analysis passes"""

from .base_pass import BasePass
from .symbol_collection_pass import SymbolCollectionPass
from .symbol_resolution_pass import SymbolResolutionPass
from .type_checking_pass import TypeCheckingPass
from .binding_analysis_pass import BindingAnalysisPass
from .behavior_dependency_pass import BehaviorDependencyPass

__all__ = [
    'BasePass',
    'SymbolCollectionPass',
    'SymbolResolutionPass',
    'TypeCheckingPass',
    'BindingAnalysisPass',
    'BehaviorDependencyPass'
]
