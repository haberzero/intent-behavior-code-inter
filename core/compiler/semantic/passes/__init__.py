"""Semantic analysis passes"""

from .base_pass import BasePass
from .scoped_visitor import ScopedVisitor
from .symbol_collection_pass import SymbolCollectionPass
from .symbol_resolution_pass import SymbolResolutionPass
from .type_checking_pass import TypeCheckingPass
from .binding_analysis_pass import BindingAnalysisPass
from .behavior_dependency_pass import BehaviorDependencyPass
from .integrity_check_pass import IntegrityCheckPass
from .symbol_phase import SymbolPhase
from .type_phase import TypePhase
from .binding_phase import BindingPhase
from .integrity_phase import IntegrityPhase

__all__ = [
    'BasePass',
    'ScopedVisitor',
    'SymbolCollectionPass',
    'SymbolResolutionPass',
    'TypeCheckingPass',
    'BindingAnalysisPass',
    'BehaviorDependencyPass',
    'IntegrityCheckPass',
    'SymbolPhase',
    'TypePhase',
    'BindingPhase',
    'IntegrityPhase',
]
