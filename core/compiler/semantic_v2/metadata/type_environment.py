"""
Type Environment

Manages type bindings and inference state during semantic analysis.

Key insight from V1:
- V1 scatters type state across multiple variables and side tables
- V2 centralizes in TypeEnvironment

2026-05-15 立场对齐:
- 删除 constraints / generic_instances（IBCI 是单次推断 + 静态强类型，不需要约束求解）
- 仅保留 bindings 和 auto_return_accumulator
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class TypeEnvironment:
    """
    Type environment for semantic analysis.

    Tracks:
    - Type bindings (variable name → inferred type)
    - Auto-inference state for `-> auto` functions
    """
    # Variable name → inferred type
    bindings: Dict[str, Any] = field(default_factory=dict)

    # For `-> auto` functions: accumulated return types
    auto_return_accumulator: List[Any] = field(default_factory=list)

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

    def merge(self, other: 'TypeEnvironment') -> 'TypeEnvironment':
        """Merge another type environment (returns new environment)"""
        from dataclasses import replace
        return replace(
            self,
            bindings={**self.bindings, **other.bindings},
            auto_return_accumulator=self.auto_return_accumulator + other.auto_return_accumulator,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for diagnostics"""
        return {
            'bindings_count': len(self.bindings),
            'auto_returns': len(self.auto_return_accumulator),
        }
