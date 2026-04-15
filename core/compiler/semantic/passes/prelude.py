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
        host_interface: Optional[Any] = None,
        registry: Optional[Any] = None,
    ):
        self.builtin_functions: Dict[str, FuncSpec] = {}
        self.builtin_modules: Dict[str, IbSpec] = {}
        self.builtin_types: Dict[str, IbSpec] = {}
        self.builtin_variables: Dict[str, IbSpec] = {}
        self.registry = registry
        self.host_interface = host_interface
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
            if spec_reg.is_callable(spec) and not spec_reg.is_class_spec(spec):
                if isinstance(spec, FuncSpec):
                    self.builtin_functions[name] = spec
            elif spec_reg.is_module_spec(spec):
                self.builtin_modules[name] = spec
            else:
                self.builtin_types[name] = spec

        # Normalise common aliases
        if "any" in self.builtin_types and "auto" not in self.builtin_types:
            self.builtin_types["auto"] = self.builtin_types["any"]
        if "void" in self.builtin_types and "none" not in self.builtin_types:
            self.builtin_types["none"] = self.builtin_types["void"]
        if "behavior" not in self.builtin_types and "callable" in self.builtin_types:
            self.builtin_types["behavior"] = self.builtin_types["callable"]

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
