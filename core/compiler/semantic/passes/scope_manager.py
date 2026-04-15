from typing import Optional, List, Dict
from core.kernel.symbols import SymbolTable, VariableSymbol, Symbol, SymbolKind
from core.kernel.spec import IbSpec


class ScopeManager:
    """
     作用域管理器。
    负责符号表的管理。
    """
    def __init__(self, global_scope: Optional[SymbolTable] = None, module_name: Optional[str] = None):
        self._global_scope = global_scope or SymbolTable(name=module_name)
        self._current_scope: SymbolTable = self._global_scope
        self._scope_stack: List[SymbolTable] = []

    def current_scope(self) -> SymbolTable:
        return self._current_scope

    def global_scope(self) -> SymbolTable:
        return self._global_scope

    def enter_scope(self, name: str) -> SymbolTable:
        new_scope = SymbolTable(name=name, parent=self._current_scope)
        self._scope_stack.append(self._current_scope)
        self._current_scope = new_scope
        return new_scope

    def exit_scope(self) -> SymbolTable:
        if not self._scope_stack:
            return self._current_scope
        self._current_scope = self._scope_stack.pop()
        return self._current_scope

    def define_var(
        self,
        name: str,
        var_type: IbSpec,
        def_node,
        allow_overwrite: bool = False
    ) -> VariableSymbol:
        sym = VariableSymbol(
            name=name,
            kind=SymbolKind.VARIABLE,
            descriptor=var_type,
            def_node=def_node,
            owned_scope=self._current_scope
        )
        self._current_scope.define(sym, force=allow_overwrite)
        return sym

    def resolve(self, name: str) -> Optional[Symbol]:
        return self._current_scope.resolve(name)
