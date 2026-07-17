from typing import Dict, Optional, List, Any

from core.kernel.spec import (
    IbSpec,
    TypeDef,
    INT_SPEC,
    STR_SPEC,
    FLOAT_SPEC,
    BOOL_SPEC,
    VOID_SPEC,
    ANY_SPEC,
    AUTO_SPEC,
)
from core.kernel.spec.base import TypeKind


class Prelude:
    """
    Static prelude: manages the pre-imported type/function/module catalogue
    that the compiler front-end uses during semantic analysis.

    命名（ADR-020 §E）：原 ``builtin_*`` 目录（"builtin" 一词五义之一）改为非前缀属性，
    由 ``Prelude`` 类名限定语义——这些是 prelude（免 import 的语言原语）目录。
    """

    def __init__(
        self,
        registry: Optional[Any] = None,
    ):
        self.functions: Dict[str, TypeDef] = {}
        self.modules: Dict[str, IbSpec] = {}
        self.types: Dict[str, IbSpec] = {}
        self.variables: Dict[str, IbSpec] = {}
        self.registry = registry
        self._init_defaults()

    # ------------------------------------------------------------------ #
    # Initialisation                                                       #
    # ------------------------------------------------------------------ #

    def _init_defaults(self) -> None:
        if not self.registry:
            raise ValueError("Prelude requires a valid SpecRegistry.")

        spec_reg = self.registry

        for name, spec in spec_reg.all_specs.items():
            if "." in name:
                continue
            # Only TypeDef instances are prelude functions; all other specs are types.
            # TypeDef with is_user_defined=True are plugin modules that must be
            # explicitly imported by ibci code — they must NOT be pre-registered as
            # prelude symbols here (that would make every plugin visible in every file
            # without an import statement).
            if spec.kind in (TypeKind.FUNCTION.value, TypeKind.CALLABLE_SIG.value):
                self.functions[name] = spec
            elif spec_reg.is_module_spec(spec):
                if not getattr(spec, 'is_user_defined', True):
                    # Only truly kernel-native module types (is_user_defined=False) belong here
                    self.modules[name] = spec
            else:
                self.types[name] = spec

        # Normalise common aliases
        if "any" in self.types and "auto" not in self.types:
            self.types["auto"] = self.types["any"]
        # Do NOT alias "none" → void: lowercase 'none' is intentionally trapped
        # as an error in visit_IbName (Bug #4 fix) to guide users towards 'None'.
        # Ensure 'None' (capitalised) is exposed as a type that _resolve_type can find.
        if "None" not in self.types:
            none_spec = self.registry.resolve("None")
            if none_spec:
                self.types["None"] = none_spec
        # Expose 'llm_uncertain' as a named prelude type (for isinstance checks, type comparisons).
        if "llm_uncertain" not in self.types:
            lu_spec = self.registry.resolve("llm_uncertain")
            if lu_spec:
                self.types["llm_uncertain"] = lu_spec
        # Expose 'fn' as a prelude type marker (callable type inference sentinel).
        if "fn" not in self.types:
            fn_spec = self.registry.resolve("fn")
            if fn_spec:
                self.types["fn"] = fn_spec

    # ------------------------------------------------------------------ #
    # Registration / query                                                 #
    # ------------------------------------------------------------------ #

    def register_func(
        self,
        name: str,
        param_type_names: List[str],
        return_type_name: str,
    ) -> None:
        spec = self.registry.factory.create_func(
            name=name,
            param_type_names=param_type_names,
            return_type_name=return_type_name,
        )
        self.functions[name] = spec

    def get_functions(self) -> Dict[str, TypeDef]:
        return dict(self.functions)

    def get_types(self) -> Dict[str, IbSpec]:
        return dict(self.types)

    def get_modules(self) -> Dict[str, IbSpec]:
        return dict(self.modules)

    def get_variables(self) -> Dict[str, IbSpec]:
        return dict(self.variables)
