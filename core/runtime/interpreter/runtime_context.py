from typing import Any, Dict, List, Optional, Union
from core.runtime.interfaces import RuntimeSymbol, Scope, RuntimeContext
from core.domain.issue import InterpreterError
from core.foundation.diagnostics.codes import RUN_UNDEFINED_VARIABLE, RUN_TYPE_MISMATCH
from core.foundation.registry import Registry, get_default_registry
from core.foundation.interfaces import IStateReader

class RuntimeSymbolImpl:
    def __init__(self, name: str, value: Any, declared_type: Any = None, is_const: bool = False):
        self.name = name
        self.value = value
        self.declared_type = declared_type
        self.current_type = type(value) if value is not None else None
        self.is_const = is_const

class ScopeImpl:
    def __init__(self, parent: Optional['Scope'] = None, registry: Optional[Registry] = None):
        self._symbols: Dict[str, RuntimeSymbol] = {}
        self._uid_to_symbol: Dict[str, RuntimeSymbol] = {} # 基于 Symbol UID 的直接映射
        self._parent = parent
        # 如果没有传入 registry，则继承父作用域的，或者使用默认的
        if registry:
            self._registry = registry
        elif parent and hasattr(parent, '_registry'):
            self._registry = parent._registry
        else:
            self._registry = get_default_registry()

    def define(self, name: str, value: Any, declared_type: Any = None, is_const: bool = False, uid: Optional[str] = None) -> None:
        boxed_value = self._registry.box(value)
        sym = RuntimeSymbolImpl(name, boxed_value, declared_type, is_const)
        if name:
            self._symbols[name] = sym
        if uid:
            self._uid_to_symbol[uid] = sym

    def assign(self, name: str, value: Any) -> bool:
        boxed_value = self._registry.box(value)
        if name in self._symbols:
            symbol = self._symbols[name]
            if symbol.is_const:
                raise InterpreterError(f"Cannot reassign constant '{name}'", error_code=RUN_TYPE_MISMATCH)
            symbol.value = boxed_value
            symbol.current_type = type(boxed_value)
            return True
        if self._parent:
            return self._parent.assign(name, value)
        return False

    def assign_by_uid(self, uid: str, value: Any) -> bool:
        """基于 UID 的赋值"""
        boxed_value = self._registry.box(value)
        if uid in self._uid_to_symbol:
            symbol = self._uid_to_symbol[uid]
            if symbol.is_const:
                raise InterpreterError(f"Cannot reassign constant UID '{uid}'", error_code=RUN_TYPE_MISMATCH)
            symbol.value = boxed_value
            symbol.current_type = type(boxed_value)
            return True
        if self._parent and hasattr(self._parent, 'assign_by_uid'):
            return self._parent.assign_by_uid(uid, value)
        return False

    def get(self, name: str) -> Any:
        symbol = self.get_symbol(name)
        if symbol:
            return symbol.value
        raise KeyError(name)

    def get_by_uid(self, uid: str) -> Any:
        """基于 UID 的获取"""
        symbol = self.get_symbol_by_uid(uid)
        if symbol:
            return symbol.value
        raise KeyError(uid)

    def get_symbol(self, name: str) -> Optional[RuntimeSymbol]:
        if name in self._symbols:
            return self._symbols[name]
        if self._parent:
            return self._parent.get_symbol(name)
        return None

    def get_symbol_by_uid(self, uid: str) -> Optional[RuntimeSymbol]:
        """向上查找 UID 符号"""
        if uid in self._uid_to_symbol:
            return self._uid_to_symbol[uid]
        if self._parent and hasattr(self._parent, 'get_symbol_by_uid'):
            return self._parent.get_symbol_by_uid(uid)
        return None

    @property
    def parent(self) -> Optional['Scope']:
        return self._parent

    def get_all_symbols(self) -> Dict[str, RuntimeSymbol]:
        """返回当前作用域的所有符号（不包含父作用域）"""
        return dict(self._symbols)

class RuntimeContextImpl(RuntimeContext, IStateReader):
    def __init__(self, initial_scope: Optional[Scope] = None, registry: Optional[Registry] = None):
        self._registry = registry or get_default_registry()
        self._global_scope = initial_scope or ScopeImpl(registry=self._registry)
        self._current_scope = self._global_scope
        self._intent_stack: List[Any] = []
        self._global_intents: List[str] = []
        self._intent_exclusive_depth = 0
        self._loop_stack: List[Dict[str, int]] = []

    def push_loop_context(self, index: int, total: int) -> None:
        self._loop_stack.append({"index": index, "total": total})

    def pop_loop_context(self) -> None:
        if self._loop_stack:
            self._loop_stack.pop()

    def get_loop_context(self) -> Optional[Dict[str, int]]:
        if self._loop_stack:
            return self._loop_stack[-1]
        return None

    def enter_intent_exclusive_scope(self) -> None:
        self._intent_exclusive_depth += 1

    def exit_intent_exclusive_scope(self) -> None:
        self._intent_exclusive_depth = max(0, self._intent_exclusive_depth - 1)

    def is_intent_exclusive(self) -> bool:
        return self._intent_exclusive_depth > 0

    def set_global_intent(self, intent: str) -> None:
        if intent not in self._global_intents:
            self._global_intents.append(intent)

    def clear_global_intents(self) -> None:
        self._global_intents = []

    def remove_global_intent(self, intent: str) -> None:
        if intent in self._global_intents:
            self._global_intents.remove(intent)

    def get_global_intents(self) -> List[str]:
        return list(self._global_intents)

    def get_vars_snapshot(self) -> Dict[str, Any]:
        """获取当前所有可见变量的快照（用于调试）"""
        res = {}
        scope = self._current_scope
        while scope:
            for name, symbol in scope.get_all_symbols().items():
                if name not in res:
                    val = symbol.value
                    # 获取运行时类型名称
                    type_name = "var"
                    if hasattr(val, 'ib_class') and val.ib_class:
                        type_name = val.ib_class.name
                    elif symbol.declared_type:
                        type_name = str(symbol.declared_type)
                        
                    # IDBG 过滤策略：目前为了对齐旧测试，过滤掉非基础类型和下划线变量
                    if type_name == "Object" or type_name == "Function" or name.startswith("_"):
                        continue
                    if type_name == "Type" and name[0].isupper():
                        continue

                    res[name] = {
                        "value": val.to_native() if hasattr(val, 'to_native') else val,
                        "type": type_name,
                        "metadata": val.serialize_for_debug() if hasattr(val, 'serialize_for_debug') else {},
                        "is_const": symbol.is_const
                    }
            scope = scope.parent
        return res

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

    def get_variable_by_uid(self, uid: str) -> Any:
        """基于 UID 获取变量值"""
        try:
            return self._current_scope.get_by_uid(uid)
        except KeyError:
            raise InterpreterError(f"Variable UID '{uid}' is not defined", error_code=RUN_UNDEFINED_VARIABLE)

    def get_symbol(self, name: str) -> Optional[RuntimeSymbol]:
        return self._current_scope.get_symbol(name)

    def get_symbol_by_uid(self, uid: str) -> Optional[RuntimeSymbol]:
        """基于 UID 获取符号"""
        return self._current_scope.get_symbol_by_uid(uid)

    def set_variable(self, name: str, value: Any) -> None:
        if not self._current_scope.assign(name, value):
            raise InterpreterError(f"Variable '{name}' is not defined", error_code=RUN_UNDEFINED_VARIABLE)

    def set_variable_by_uid(self, uid: str, value: Any) -> None:
        """基于 UID 赋值"""
        if not self._current_scope.assign_by_uid(uid, value):
            raise InterpreterError(f"Variable UID '{uid}' is not defined", error_code=RUN_UNDEFINED_VARIABLE)

    def define_variable(self, name: str, value: Any, declared_type: Any = None, is_const: bool = False, uid: Optional[str] = None) -> None:
        # 检查是否试图重定义常量
        existing = self.get_symbol_by_uid(uid) if uid else self.get_symbol(name)
        if existing and existing.is_const:
            if existing.value is value:
                return
            raise InterpreterError(f"Cannot reassign constant '{name or uid}'", error_code=RUN_TYPE_MISMATCH)

        self._current_scope.define(name, value, declared_type, is_const, uid=uid)

    def push_intent(self, intent: Any) -> None:
        self._intent_stack.append(intent)

    def pop_intent(self) -> Optional[Any]:
        if self._intent_stack:
            return self._intent_stack.pop()
        return None

    def get_active_intents(self) -> List[Any]:
        return list(self._intent_stack)

    @property
    def intent_stack(self) -> List[Any]:
        return self._intent_stack
        
    @intent_stack.setter
    def intent_stack(self, value: List[Any]):
        self._intent_stack = value

    @property
    def current_scope(self) -> Scope:
        return self._current_scope

    @property
    def global_scope(self) -> Scope:
        return self._global_scope
