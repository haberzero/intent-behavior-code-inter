"""
Type Environment

Manages type bindings and inference state during semantic analysis.

Key insight from V1:
- V1 scatters type state across multiple variables and side tables
- V2 centralizes in TypeEnvironment
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set


@dataclass(frozen=True)
class TypeEnvironment:
    """
    Immutable type environment for semantic analysis.

    Tracks:
    - Type constraints and bindings
    - Auto-inference state for `-> auto` functions
    - Generic type instantiations
    """
    # Variable name → inferred type
    bindings: Dict[str, Any] = field(default_factory=dict)

    # For `-> auto` functions: accumulated return types
    auto_return_accumulator: List[Any] = field(default_factory=list)

    # Generic type instantiations (e.g., list[T] → list[int])
    generic_instances: Dict[str, Any] = field(default_factory=dict)

    # Type constraints for incremental inference
    # (node_uid, constraint_type) → type_spec
    constraints: Dict[tuple, Any] = field(default_factory=dict)

    @classmethod
    def create_empty(cls) -> 'TypeEnvironment':
        """Create an empty type environment"""
        return cls()

    def bind(self, name: str, type_spec: Any) -> 'TypeEnvironment':
        """Bind a variable to a type (returns new environment)"""
        new_bindings = {**self.bindings, name: type_spec}
        from dataclasses import replace
        return replace(self, bindings=new_bindings)

    def lookup(self, name: str) -> Optional[Any]:
        """Look up a variable's type"""
        return self.bindings.get(name)

    def accumulate_return(self, type_spec: Any) -> 'TypeEnvironment':
        """Accumulate a return type for auto inference (returns new environment)"""
        new_accumulator = self.auto_return_accumulator + [type_spec]
        from dataclasses import replace
        return replace(self, auto_return_accumulator=new_accumulator)

    def get_accumulated_returns(self) -> List[Any]:
        """Get all accumulated return types"""
        return self.auto_return_accumulator

    def clear_auto_accumulator(self) -> 'TypeEnvironment':
        """Clear auto return accumulator (returns new environment)"""
        from dataclasses import replace
        return replace(self, auto_return_accumulator=[])

    def add_constraint(self, node_uid: str, constraint_type: str, type_spec: Any) -> 'TypeEnvironment':
        """Add a type constraint (returns new environment)"""
        new_constraints = {**self.constraints, (node_uid, constraint_type): type_spec}
        from dataclasses import replace
        return replace(self, constraints=new_constraints)

    def get_constraint(self, node_uid: str, constraint_type: str) -> Optional[Any]:
        """Get a type constraint"""
        return self.constraints.get((node_uid, constraint_type))

    def merge(self, other: 'TypeEnvironment') -> 'TypeEnvironment':
        """Merge another type environment (returns new environment)"""
        from dataclasses import replace
        return replace(
            self,
            bindings={**self.bindings, **other.bindings},
            auto_return_accumulator=self.auto_return_accumulator + other.auto_return_accumulator,
            generic_instances={**self.generic_instances, **other.generic_instances},
            constraints={**self.constraints, **other.constraints}
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for diagnostics"""
        return {
            'bindings_count': len(self.bindings),
            'auto_returns': len(self.auto_return_accumulator),
            'constraints_count': len(self.constraints),
        }
