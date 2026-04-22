from typing import Dict, Optional, List, Any

from core.kernel.spec import (
    IbSpec, FuncSpec, ModuleSpec,
    INT_SPEC, STR_SPEC, FLOAT_SPEC, BOOL_SPEC,
    VOID_SPEC, ANY_SPEC, AUTO_SPEC,
)


class Prelude:
    """
    Static prelude: manages the built-in type/function/module catalogue
    that the compiler front-end uses during semantic analysis.
    """

    def __init__(
        self,
        registry: Optional[Any] = None,
    ):
        self.builtin_functions: Dict[str, FuncSpec] = {}
        self.builtin_modules: Dict[str, IbSpec] = {}
        self.builtin_types: Dict[str, IbSpec] = {}
        self.builtin_variables: Dict[str, IbSpec] = {}
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
            # Only FuncSpec instances are builtin functions; all other specs are types.
            # ModuleSpec with is_user_defined=True are plugin modules that must be
            # explicitly imported by ibci code — they must NOT be pre-registered as
            # builtin symbols here (that would make every plugin visible in every file
            # without an import statement).
            if isinstance(spec, FuncSpec):
                self.builtin_functions[name] = spec
            elif spec_reg.is_module_spec(spec):
                if not getattr(spec, 'is_user_defined', True):
                    # Only truly built-in module types (is_user_defined=False) belong here
                    self.builtin_modules[name] = spec
            else:
                self.builtin_types[name] = spec

        # Normalise common aliases
        if "any" in self.builtin_types and "auto" not in self.builtin_types:
            self.builtin_types["auto"] = self.builtin_types["any"]
        # Do NOT alias "none" → void: lowercase 'none' is intentionally trapped
        # as an error in visit_IbName (Bug #4 fix) to guide users towards 'None'.
        # Ensure 'None' (capitalised) is exposed as a type that _resolve_type can find.
        if "None" not in self.builtin_types:
            none_spec = self.registry.resolve("None")
            if none_spec:
                self.builtin_types["None"] = none_spec
        # Expose 'llm_uncertain' as a named builtin type (for isinstance checks, type comparisons).
        if "llm_uncertain" not in self.builtin_types:
            lu_spec = self.registry.resolve("llm_uncertain")
            if lu_spec:
                self.builtin_types["llm_uncertain"] = lu_spec

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
        self.builtin_functions[name] = spec

    def get_builtins(self) -> Dict[str, FuncSpec]:
        return dict(self.builtin_functions)

    def get_builtin_types(self) -> Dict[str, IbSpec]:
        return dict(self.builtin_types)

    def get_builtin_modules(self) -> Dict[str, IbSpec]:
        return dict(self.builtin_modules)

    def get_builtin_variables(self) -> Dict[str, IbSpec]:
        return dict(self.builtin_variables)
