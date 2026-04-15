import copy
import hashlib
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any, Set, TYPE_CHECKING
from enum import Enum, auto

from .spec import IbSpec, FuncSpec, ClassSpec, ModuleSpec


# --- Symbol System ---

class SymbolKind(Enum):
    VARIABLE = auto()
    FUNCTION = auto()
    LLM_FUNCTION = auto()
    CLASS = auto()
    INTENT = auto()
    MODULE = auto()


@dataclass(eq=False)
class Symbol:
    """Static symbol base class.

    ``spec`` holds the pure-data IbSpec of this symbol's type.
    The old field was named ``descriptor`` and held a TypeDescriptor;
    keeping the field name ``spec`` makes the new semantics explicit.
    """
    name: str
    kind: SymbolKind
    uid: Optional[str] = None
    def_node: Optional[Any] = None
    owned_scope: Optional['SymbolTable'] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # The IbSpec for this symbol's type (pure data, no runtime state).
    spec: Optional[IbSpec] = None

    # ------------------------------------------------------------------
    # Backward-compatibility shim
    # ------------------------------------------------------------------
    # Many call sites still use ``sym.descriptor``.  This property
    # redirects to ``spec`` so we can migrate callers incrementally.
    @property
    def descriptor(self) -> Optional[IbSpec]:
        return self.spec

    @descriptor.setter
    def descriptor(self, value: Optional[IbSpec]) -> None:
        self.spec = value

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def is_type(self) -> bool:
        return self.kind == SymbolKind.CLASS

    @property
    def is_function(self) -> bool:
        return self.kind in (SymbolKind.FUNCTION, SymbolKind.LLM_FUNCTION)

    @property
    def is_variable(self) -> bool:
        return self.kind == SymbolKind.VARIABLE

    def clone(self, memo: Optional[Dict[int, Any]] = None) -> 'Symbol':
        """Clone this symbol.  IbSpec objects are pure data; sharing is safe."""
        if memo is None:
            memo = {}
        if id(self) in memo:
            return memo[id(self)]
        new_sym = copy.copy(self)
        memo[id(self)] = new_sym
        # No deep-clone of spec: pure data can be shared
        return new_sym

    def get_content_hash(self) -> str:
        parts = [self.name, self.kind.name]
        if self.spec:
            parts.append(f"type:{self.spec.module_path or 'root'}.{self.spec.name}")
        for k, v in sorted(self.metadata.items()):
            if isinstance(v, (str, int, float, bool)):
                parts.append(f"{k}:{v}")
        content = "|".join(parts)
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


@dataclass
class TypeSymbol(Symbol):
    """A type definition (class or built-in type)."""
    pass


@dataclass
class FunctionSymbol(Symbol):
    """A function (regular or LLM)."""

    @property
    def return_type_name(self) -> str:
        if isinstance(self.spec, FuncSpec):
            return self.spec.return_type_name
        return "any"

    @property
    def param_type_names(self) -> List[str]:
        if isinstance(self.spec, FuncSpec):
            return list(self.spec.param_type_names)
        return []


@dataclass
class VariableSymbol(Symbol):
    """A variable or field."""
    is_const: bool = False
    is_global: bool = False


@dataclass
class IntentSymbol(Symbol):
    """An intent block."""
    content: str = ""
    is_exclusive: bool = False
    parent_intent: Optional['IntentSymbol'] = None


class SymbolTable:
    """Static symbol table with scope nesting."""

    def __init__(
        self,
        parent: Optional['SymbolTable'] = None,
        name: Optional[str] = None,
    ):
        self.parent = parent
        self.name = name
        self.depth = (parent.depth + 1) if parent else 0
        self.symbols: Dict[str, Symbol] = {}
        self.global_refs: Set[str] = set()
        self._uid: Optional[str] = None
        self._child_count = 0

        if parent:
            parent._child_count += 1
            self._anon_id = parent._child_count

    @property
    def uid(self) -> str:
        if self._uid:
            return self._uid
        if not self.parent:
            self._uid = f"scope_{self.name or 'global'}"
        else:
            child_name = self.name or f"anon_{self._anon_id}"
            self._uid = f"{self.parent.uid}/{child_name}"
        return self._uid

    def define(self, sym: Symbol, allow_overwrite: bool = False) -> None:
        """Define a symbol; raise ValueError on conflict."""
        if not sym.uid:
            sym.uid = f"{self.uid}:{sym.name}"

        if not allow_overwrite and sym.name in self.symbols:
            existing = self.symbols[sym.name]
            is_compatible = (
                (existing.metadata.get("is_builtin") and sym.metadata.get("is_builtin"))
                or (existing.metadata.get("is_external_module") and sym.metadata.get("is_builtin"))
                or (existing.metadata.get("is_builtin") and sym.metadata.get("is_external_module"))
                or (existing.metadata.get("is_external_module") and sym.metadata.get("is_external_module"))
            )
            if is_compatible:
                if existing.spec and sym.spec:
                    if existing.spec is not sym.spec:
                        if existing.spec.name == sym.spec.name:
                            return  # same-name external module dup
                        raise ValueError(
                            f"Builtin Symbol Conflict: '{sym.name}' redefined with "
                            f"incompatible spec (existing: '{existing.spec.name}')"
                        )
                self.symbols[sym.name] = sym
                return
            raise ValueError(f"Symbol '{sym.name}' is already defined in this scope")

        self.symbols[sym.name] = sym

    def resolve(self, name: str) -> Optional[Symbol]:
        if name in self.symbols:
            return self.symbols[name]
        if self.parent:
            return self.parent.resolve(name)
        return None

    def get_global_scope(self) -> 'SymbolTable':
        curr = self
        while curr.parent:
            curr = curr.parent
        return curr

    def add_global_ref(self, name: str) -> None:
        self.global_refs.add(name)


class SymbolFactory:
    """Creates Symbol objects from IbSpec instances."""

    @staticmethod
    def create_from_spec(name: str, spec: IbSpec) -> 'Symbol':
        from core.kernel.spec import FuncSpec, ClassSpec, ModuleSpec
        if isinstance(spec, FuncSpec):
            return FunctionSymbol(name=name, kind=SymbolKind.FUNCTION, spec=spec)
        if isinstance(spec, ClassSpec):
            return TypeSymbol(name=name, kind=SymbolKind.CLASS, spec=spec)
        if isinstance(spec, ModuleSpec):
            return VariableSymbol(name=name, kind=SymbolKind.MODULE, spec=spec)
        return VariableSymbol(name=name, kind=SymbolKind.VARIABLE, spec=spec)

    @staticmethod
    def create_builtin_method(name: str, spec: IbSpec) -> 'FunctionSymbol':
        return FunctionSymbol(
            name=name,
            kind=SymbolKind.FUNCTION,
            spec=spec,
            metadata={"is_builtin": True, "axiom_provided": True},
        )
