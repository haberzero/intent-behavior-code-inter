"""
core/kernel/factory.py

Replaces the old ``create_default_registry()`` that returned a
MetadataRegistry.  Now returns a SpecRegistry pre-populated with
all built-in primitive specs and their axiom method signatures.
"""

from core.kernel.axioms.registry import AxiomRegistry
from core.kernel.axioms.primitives import register_core_axioms
from core.kernel.spec.registry import SpecRegistry, create_default_spec_registry


def create_default_registry() -> SpecRegistry:
    """
    Create a SpecRegistry pre-populated with all built-in types.

    Builds an AxiomRegistry, registers all core axioms, then creates
    a SpecRegistry with every primitive spec cloned and axiom method
    signatures bootstrapped into members.
    """
    axiom_reg = AxiomRegistry()
    register_core_axioms(axiom_reg)
    return create_default_spec_registry(axiom_reg)
