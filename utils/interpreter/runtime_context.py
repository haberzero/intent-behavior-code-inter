from typing import Any, Dict, List, Optional
from .interfaces import RuntimeSymbol, Scope, RuntimeContext

class RuntimeSymbolImpl:
    def __init__(self, name: str, value: Any, declared_type: Any = None, is_const: bool = False):
        self.name = name
        self.value = value
        self.declared_type = declared_type
        self.current_type = type(value) if value is not None else None
        self.is_const = is_const

class ScopeImpl:
    def __init__(self, parent: Optional['Scope'] = None):
        self._symbols: Dict[str, RuntimeSymbol] = {}
        self._parent = parent

    def define(self, name: str, value: Any, declared_type: Any = None, is_const: bool = False) -> None:
        self._symbols[name] = RuntimeSymbolImpl(name, value, declared_type, is_const)

    def assign(self, name: str, value: Any) -> bool:
        if name in self._symbols:
            symbol = self._symbols[name]
            if symbol.is_const:
                from typedef.exception_types import InterpreterError
                raise InterpreterError(f"Cannot reassign constant '{name}'")
            
            # 运行时类型检查逻辑
            if symbol.declared_type and symbol.declared_type != 'var':
                # TODO: 接入更完善的类型检查逻辑
                # 目前简单通过 isinstance 检查，或者延迟到具体的 Type 系统实现
                pass
                
            symbol.value = value
            symbol.current_type = type(value)
            return True
        if self._parent:
            return self._parent.assign(name, value)
        return False

    def get(self, name: str) -> Any:
        symbol = self.get_symbol(name)
        if symbol:
            return symbol.value
        raise KeyError(name)

    def get_symbol(self, name: str) -> Optional[RuntimeSymbol]:
        if name in self._symbols:
            return self._symbols[name]
        if self._parent:
            return self._parent.get_symbol(name)
        return None

    @property
    def parent(self) -> Optional['Scope']:
        return self._parent

class RuntimeContextImpl:
    def __init__(self):
        self._global_scope = ScopeImpl()
        self._current_scope = self._global_scope
        self._intent_stack: List[str] = []

    def enter_scope(self) -> None:
        self._current_scope = ScopeImpl(parent=self._current_scope)

    def exit_scope(self) -> None:
        if self._current_scope.parent:
            self._current_scope = self._current_scope.parent

    def get_variable(self, name: str) -> Any:
        return self._current_scope.get(name)

    def get_symbol(self, name: str) -> Optional[RuntimeSymbol]:
        return self._current_scope.get_symbol(name)

    def set_variable(self, name: str, value: Any) -> None:
        if not self._current_scope.assign(name, value):
            from typedef.exception_types import InterpreterError
            raise InterpreterError(f"Variable '{name}' is not defined")

    def define_variable(self, name: str, value: Any, declared_type: Any = None, is_const: bool = False) -> None:
        # 检查是否试图重定义常量（包括全局内置常量）
        existing = self.get_symbol(name)
        if existing and existing.is_const:
            from typedef.exception_types import InterpreterError
            raise InterpreterError(f"Cannot reassign constant '{name}'")

        self._current_scope.define(name, value, declared_type, is_const)

    def push_intent(self, intent: str) -> None:
        self._intent_stack.append(intent)

    def pop_intent(self) -> Optional[str]:
        if self._intent_stack:
            return self._intent_stack.pop()
        return None

    def get_active_intents(self) -> List[str]:
        return list(self._intent_stack)

    @property
    def current_scope(self) -> Scope:
        return self._current_scope

    @property
    def global_scope(self) -> Scope:
        return self._global_scope
