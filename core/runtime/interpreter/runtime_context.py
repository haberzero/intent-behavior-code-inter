from typing import Any, Dict, List, Optional
from .interfaces import RuntimeSymbol, Scope, RuntimeContext
from core.types.exception_types import InterpreterError
from core.support.diagnostics.codes import RUN_UNDEFINED_VARIABLE, RUN_TYPE_MISMATCH
from core.runtime.ext.capabilities import IStateReader

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
                raise InterpreterError(f"Cannot reassign constant '{name}'", error_code=RUN_TYPE_MISMATCH)
            
            # 运行时类型检查逻辑
            if symbol.declared_type and symbol.declared_type != 'var':
                # TODO: 接入更完善的类型检查逻辑
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

    def get_all_symbols(self) -> Dict[str, RuntimeSymbol]:
        """返回当前作用域的所有符号（不包含父作用域）"""
        return dict(self._symbols)

    @property
    def parent(self) -> Optional['Scope']:
        return self._parent

class RuntimeContextImpl(IStateReader):
    def __init__(self):
        self._global_scope = ScopeImpl()
        self._current_scope = self._global_scope
        self._intent_stack: List[str] = []

    def get_vars_snapshot(self) -> Dict[str, Any]:
        """实现 IStateReader 接口：获取当前可见的所有变量快照"""
        all_symbols = {}
        scope = self._current_scope
        while scope:
            current_symbols = scope.get_all_symbols()
            for name, sym in current_symbols.items():
                if name not in all_symbols:
                    all_symbols[name] = sym
            scope = getattr(scope, "parent", None)
        
        result = {}
        for name, sym in all_symbols.items():
            val = sym.value
            # 基础过滤：仅导出基础数据类型和容器，防止泄露内核对象
            if not isinstance(val, (int, float, str, bool, list, dict)) and val is not None:
                continue
            
            result[name] = {
                "value": val,
                "type": str(sym.declared_type) if sym.declared_type else type(val).__name__,
                "is_const": sym.is_const
            }
        return result

    def enter_scope(self) -> None:
        self._current_scope = ScopeImpl(parent=self._current_scope)

    def exit_scope(self) -> None:
        if self._current_scope.parent:
            self._current_scope = self._current_scope.parent

    def get_variable(self, name: str) -> Any:
        try:
            return self._current_scope.get(name)
        except KeyError:
            raise InterpreterError(f"Variable '{name}' is not defined", error_code=RUN_UNDEFINED_VARIABLE)

    def get_symbol(self, name: str) -> Optional[RuntimeSymbol]:
        return self._current_scope.get_symbol(name)

    def set_variable(self, name: str, value: Any) -> None:
        if not self._current_scope.assign(name, value):
            raise InterpreterError(f"Variable '{name}' is not defined", error_code=RUN_UNDEFINED_VARIABLE)

    def define_variable(self, name: str, value: Any, declared_type: Any = None, is_const: bool = False) -> None:
        # 检查是否试图重定义常量（包括全局内置常量）
        existing = self.get_symbol(name)
        if existing and existing.is_const:
            raise InterpreterError(f"Cannot reassign constant '{name}'", error_code=RUN_TYPE_MISMATCH)

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
