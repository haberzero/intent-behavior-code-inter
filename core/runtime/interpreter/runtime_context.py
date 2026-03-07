from typing import Any, Dict, List, Optional
from core.foundation.interfaces import RuntimeSymbol, Scope, RuntimeContext
from core.types import parser_types as ast
from core.types.exception_types import InterpreterError
from core.support.diagnostics.codes import RUN_UNDEFINED_VARIABLE, RUN_TYPE_MISMATCH
from core.foundation.capabilities import IStateReader

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
        from core.foundation.bootstrapper import Bootstrapper
        boxed_value = Bootstrapper.box(value)
        self._symbols[name] = RuntimeSymbolImpl(name, boxed_value, declared_type, is_const)

    def assign(self, name: str, value: Any) -> bool:
        from core.foundation.bootstrapper import Bootstrapper
        boxed_value = Bootstrapper.box(value)
        if name in self._symbols:
            symbol = self._symbols[name]
            if symbol.is_const:
                raise InterpreterError(f"Cannot reassign constant '{name}'", error_code=RUN_TYPE_MISMATCH)
            
            # 运行时类型检查逻辑
            if symbol.declared_type and symbol.declared_type != 'var':
                # TODO: 接入更完善的类型检查逻辑
                pass
                
            symbol.value = boxed_value
            symbol.current_type = type(boxed_value)
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

    def get_all_symbols(self) -> Dict[str, RuntimeSymbol]:
        """返回当前作用域的所有符号（不包含父作用域）"""
        return dict(self._symbols)

    @property
    def parent(self) -> Optional['Scope']:
        return self._parent

class RuntimeContextImpl(RuntimeContext, IStateReader):
    def __init__(self, initial_scope: Optional[Scope] = None):
        self._global_scope = initial_scope or ScopeImpl()
        self._current_scope = self._global_scope
        self._intent_stack: List[ast.IntentInfo] = []
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
                    # 在 UTS 架构下，Object 类型通常代表包装的 Native 对象或通用实例
                    if type_name == "Object" or type_name == "Function" or name.startswith("_"):
                        continue
                    # 同时也过滤掉类对象 (首字母大写且 type_name 为 Type)
                    if type_name == "Type" and name[0].isupper():
                        continue

                    res[name] = {
                        "value": val.to_native() if hasattr(val, 'to_native') else val,
                        "type": type_name,
                        "metadata": val.serialize_for_debug() if hasattr(val, 'serialize_for_debug') else {},
                        "is_const": symbol.is_const
                    }
            scope = scope.parent # 使用新添加的 parent 属性
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

    def get_symbol(self, name: str) -> Optional[RuntimeSymbol]:
        return self._current_scope.get_symbol(name)

    def set_variable(self, name: str, value: Any) -> None:
        if not self._current_scope.assign(name, value):
            raise InterpreterError(f"Variable '{name}' is not defined", error_code=RUN_UNDEFINED_VARIABLE)

    def define_variable(self, name: str, value: Any, declared_type: Any = None, is_const: bool = False) -> None:
        # 检查是否试图重定义常量（包括全局内置常量）
        existing = self.get_symbol(name)
        if existing and existing.is_const:
            # 允许重复定义相同的值 (例如 bootstrap 阶段)
            if existing.value is value:
                return
            raise InterpreterError(f"Cannot reassign constant '{name}'", error_code=RUN_TYPE_MISMATCH)

        self._current_scope.define(name, value, declared_type, is_const)

    def push_intent(self, intent: ast.IntentInfo) -> None:
        self._intent_stack.append(intent)

    def pop_intent(self) -> Optional[ast.IntentInfo]:
        if self._intent_stack:
            return self._intent_stack.pop()
        return None

    def get_active_intents(self) -> List[ast.IntentInfo]:
        return list(self._intent_stack)

    @property
    def intent_stack(self) -> List[ast.IntentInfo]:
        return self._intent_stack
        
    @intent_stack.setter
    def intent_stack(self, value: List[ast.IntentInfo]):
        self._intent_stack = value

    @property
    def current_scope(self) -> Scope:
        return self._current_scope

    @property
    def global_scope(self) -> Scope:
        return self._global_scope
