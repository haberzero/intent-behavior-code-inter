"""
core/kernel/spec/registry/_base.py

SpecRegistryBase — the foundational mixin for SpecRegistry.

Shared-state protocol
---------------------
All mixins composed into ``SpecRegistry`` rely on the following instance
attributes, which are initialised by ``SpecRegistryBase.__init__``:

* ``self._specs: Dict[str, IbSpec]`` — flat registry of cloned specs keyed
  by ``_key(spec)`` (``"module.name"`` or bare ``"name"``).
* ``self._axiom_registry: AxiomRegistry`` — the axiom layer; mixins use it
  both directly (``self._axiom_registry.get_axiom(...)``) and via the
  ``get_axiom()`` helper defined here.
* ``self.factory: SpecFactory`` — factory used by ``resolve_specialization``
  and the default-registry builder.

Mixins additionally rely on these base methods:

* ``resolve(name, module)`` / ``resolve_typeref(ref)`` — look up specs.
* ``get_axiom(spec)`` — fetch the TypeAxiom for a spec.
* ``_key(spec)`` — compute the registration key.
"""

from __future__ import annotations

from typing import Dict, Optional, TYPE_CHECKING

from ..base import IbSpec
from ..type_ref import TypeRef
from .factory import SpecFactory

if TYPE_CHECKING:
    from core.kernel.axioms.registry import AxiomRegistry
    from core.kernel.axioms.protocols import TypeAxiom


# ------------------------------------------------------------------ #
# SpecRegistryBase                                                     #
# ------------------------------------------------------------------ #

class SpecRegistryBase:
    """
    Central type registry.

    Stores cloned IbSpec objects by qualified name.
    Delegates all capability queries to the held AxiomRegistry.

    Usage pattern (compiler / runtime):

        spec = registry.resolve("int")       # look up a type
        cap  = registry.get_call_cap(spec)   # query capability
        ret  = registry.resolve_call_return(spec, [arg_spec])  # unified type inference
    """

    def __init__(self, axiom_registry: "AxiomRegistry"):
        self._specs: Dict[str, IbSpec] = {}
        self._axiom_registry = axiom_registry
        self.factory = SpecFactory()
        # 统一泛型模型：内置泛型类型声明注册表（单一权威源）。
        # 创建/解析/序列化/还原统一经此路由。
        from ..generic import create_generic_registry
        self.generic_types = create_generic_registry()

    # ---------------------------------------------------------- #
    # Registration                                               #
    # ---------------------------------------------------------- #

    def register(self, spec: IbSpec) -> IbSpec:
        """
        Register a (clone of a) spec.

        If a spec with the same qualified name is already registered,
        the existing one is returned (idempotent for built-ins).
        For user-defined specs the caller may want to force-overwrite;
        use ``register_force`` in that case.
        """
        key = self._key(spec)
        if key in self._specs:
            existing = self._specs[key]
            # Merge members from incoming spec into existing (supports incremental build)
            for mname, mspec in spec.members.items():
                existing.members.setdefault(mname, mspec)
            return existing
        cloned = spec.clone()
        self._specs[key] = cloned
        return cloned

    def register_force(self, spec: IbSpec) -> IbSpec:
        """Register, overwriting any existing entry."""
        key = self._key(spec)
        cloned = spec.clone()
        self._specs[key] = cloned
        return cloned

    def resolve(
        self,
        name: str,
        module: Optional[str] = None,
    ) -> Optional[IbSpec]:
        """
        Look up a spec by (module, name).

        Falls back to an unqualified lookup if the module-qualified key
        is not found.  Returns None if the type is genuinely unknown.
        """
        if module:
            spec = self._specs.get(f"{module}.{name}")
            if spec:
                return spec
        return self._specs.get(name)

    def resolve_typeref(self, ref: "TypeRef") -> Optional[IbSpec]:
        """
        Look up a spec by TypeRef compatibility entry point.

        For non-generic TypeRefs this delegates to ``resolve(head, module)``.
        For generic TypeRefs (e.g. list[int]) it first attempts to look up
        the fully-encoded canonical name, then falls back to building the
        specialization from the structured args (R2-D1：结构化 ref 懒构建，
        不再依赖调用方预注册特化 spec）。

        This method is the primary resolution path for new code that already
        holds a TypeRef and needs an IbSpec for capability queries.
        """
        if ref.args:
            # Try canonical name first (e.g. "list[int]", "dict[str,int]")
            result = self.resolve(ref.canonical_name, ref.module)
            if result is not None:
                return result
            # 懒构建：canonical 名未命中时，从结构化 args 经 resolve_specialization
            # 构建特化 spec（list[int] / Optional[int] / thread_result[int] 等）。
            base_spec = self.resolve(ref.head, ref.module)
            if base_spec is not None:
                arg_specs = [
                    self.resolve_typeref(a) or self.resolve("any")
                    for a in ref.args
                ]
                if all(a is not None for a in arg_specs):
                    built = self.resolve_specialization(base_spec, arg_specs)
                    if built is not None:
                        return built
        # Fall back to bare head name (works for non-generic and base-type lookup)
        return self.resolve(ref.head, ref.module)

    @property
    def all_specs(self) -> Dict[str, IbSpec]:
        return dict(self._specs)

    def get_axiom_registry(self) -> "AxiomRegistry":
        return self._axiom_registry

    def get_axiom(self, spec: Optional[IbSpec]) -> Optional["TypeAxiom"]:
        """Return the axiom for this spec, or None."""
        if spec is None:
            return None
        return self._axiom_registry.get_axiom(spec.get_base_name())

    # ---------------------------------------------------------- #
    # Internal helpers                                           #
    # ---------------------------------------------------------- #

    @staticmethod
    def _key(spec: IbSpec) -> str:
        if spec.module_path:
            return f"{spec.module_path}.{spec.name}"
        return spec.name
