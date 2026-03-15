from __future__ import annotations
from typing import Any, Dict, List, Optional, Union, TYPE_CHECKING
from core.runtime.interfaces import RuntimeSymbol, Scope, RuntimeContext, SymbolView
from core.domain.issue import InterpreterError
from core.foundation.diagnostics.codes import RUN_UNDEFINED_VARIABLE, RUN_TYPE_MISMATCH
from core.foundation.registry import Registry
from core.foundation.interfaces import IStateReader
from core.domain.types.descriptors import TypeDescriptor
from core.runtime.objects.intent import IbIntent, IntentMode, IntentRole
from core.runtime.objects.kernel import IbClass, IbModule

class RuntimeSymbolImpl:
    def __init__(self, name: str, value: Any, declared_type: TypeDescriptor | None = None, is_const: bool = False):
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
        # 如果没有传入 registry，则从父作用域继承
        if registry:
            self._registry = registry
        elif parent and hasattr(parent, '_registry'):
            self._registry = parent._registry
        else:
            raise ValueError("Registry is required for Scope creation (no parent provided)")

    def _check_type(self, value: Any, declared_type: Optional[Any], name: str):
        """运行时类型检查"""
        if declared_type is None:
            return
            
        # [Phase 3.3] 强契约：唯一使用描述符进行校验
        if not hasattr(value, 'descriptor'):
            value = self._registry.box(value)
            
        val_desc = value.descriptor
        
        # 如果 declared_type 是 TypeDescriptor
        if isinstance(declared_type, TypeDescriptor):
            if val_desc:
                if not val_desc.is_assignable_to(declared_type):
                    raise InterpreterError(
                        f"Type mismatch: Cannot assign '{val_desc.name}' to '{declared_type.name}' for variable '{name}'",
                        error_code=RUN_TYPE_MISMATCH
                    )
            else:
                # 理论上所有运行时对象必须具备描述符 (由 Phase 1.1/1.3 保证)
                raise InterpreterError(
                    f"System Error: Runtime object of class '{value.ib_class.name}' missing UTS descriptor.",
                    error_code=RUN_TYPE_MISMATCH
                )
        elif hasattr(declared_type, 'is_assignable_to'):
            # 支持其他具备兼容性检查接口的对象
            # 注意：此处回退到 val_class 校验，仅作为非 UTS 描述符的补充
            val_class = value.ib_class
            if not val_class.is_assignable_to(declared_type):
                 raise InterpreterError(
                    f"Type mismatch: '{val_class.name}' is not assignable to declared type for variable '{name}'",
                    error_code=RUN_TYPE_MISMATCH
                )

    def define(self, name: str, value: Any, declared_type: Any = None, is_const: bool = False, uid: Optional[str] = None, force: bool = False) -> None:
        """定义符号。如果 force=True，允许覆盖已存在的常量符号（用于内核特权恢复路径）"""
        boxed_value = self._registry.box(value)
        
        # [NEW] 运行时类型校验
        self._check_type(boxed_value, declared_type, name or uid or "unknown")

        # [IES 2.0 Privileged] 检查冲突
        if not force:
            if name in self._symbols and self._symbols[name].is_const:
                raise InterpreterError(f"Cannot redefine constant '{name}'", error_code=RUN_TYPE_MISMATCH)
            if uid in self._uid_to_symbol and self._uid_to_symbol[uid].is_const:
                raise InterpreterError(f"Cannot redefine constant UID '{uid}'", error_code=RUN_TYPE_MISMATCH)

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
            
            # [NEW] 运行时类型校验
            self._check_type(boxed_value, symbol.declared_type, name)
            
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
            
            # [NEW] 运行时类型校验
            self._check_type(boxed_value, symbol.declared_type, symbol.name or uid)
            
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

class SymbolViewImpl(SymbolView):
    """[Active Defense] 只读符号表视图实现"""
    def __init__(self, context: RuntimeContext):
        self._context = context

    def get(self, name: str) -> Any:
        return self._context.get_variable(name)

    def get_symbol(self, name: str) -> Optional[RuntimeSymbol]:
        return self._context.get_symbol(name)

    def has(self, name: str) -> bool:
        try:
            self._context.get_symbol(name)
            return True
        except:
            return False

class IntentNode:
    """[IES 2.0] 不可变意图节点，支持结构共享以优化内存"""
    def __init__(self, intent: Union[IbIntent, Any], parent: Optional['IntentNode'] = None):
        self.intent = intent
        self.parent = parent
        self._cached_list: Optional[List[IbIntent]] = None

    def to_list(self) -> List[IbIntent]:
        """展平为列表（带缓存）"""
        if self._cached_list is not None:
            return self._cached_list
        
        res = []
        curr = self
        while curr:
            res.append(curr.intent)
            curr = curr.parent
        # 由于是向上链接，展平后需要反转以保持从底到顶的顺序
        res.reverse()
        self._cached_list = res
        return res

class RuntimeContextImpl(RuntimeContext, IStateReader):
    def __init__(self, initial_scope: Optional[Scope] = None, registry: Optional[Registry] = None):
        if not registry:
            raise ValueError("Registry is required for RuntimeContext creation")
        self._registry = registry
        self._global_scope = initial_scope or ScopeImpl(registry=self._registry)
        self._current_scope = self._global_scope
        self._intent_top: Optional[IntentNode] = None # 意图栈顶节点
        self._global_intents: List[IbIntent] = []
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

    def set_global_intent(self, intent: Union[str, IbIntent]) -> None:
        if isinstance(intent, str):
            intent = IbIntent(
                ib_class=self._registry.get_class("Intent"),
                content=intent,
                mode=IntentMode.APPEND,
                role=IntentRole.GLOBAL
            )
        if intent not in self._global_intents:
            self._global_intents.append(intent)

    def clear_global_intents(self) -> None:
        self._global_intents = []

    def remove_global_intent(self, intent: Union[str, IbIntent]) -> None:
        if isinstance(intent, str):
            # 匹配内容的移除
            self._global_intents = [i for i in self._global_intents if i.content != intent]
        else:
            if intent in self._global_intents:
                self._global_intents.remove(intent)

    def get_global_intents(self) -> List[IbIntent]:
        return list(self._global_intents)

    def get_vars(self) -> Dict[str, Any]:
        """[IES 2.0] 获取当前可见的所有真实变量对象 (IbObject)。"""
        res = {}
        scope = self._current_scope
        while scope:
            for name, symbol in scope.get_all_symbols().items():
                if name not in res:
                    val = symbol.value
                    is_class = isinstance(val, IbClass)
                    is_module = isinstance(val, IbModule)
                    type_name = val.ib_class.name if hasattr(val, 'ib_class') and val.ib_class else "Object"
                    
                    # 过滤逻辑：过滤掉非基础类型、下划线变量、类定义、模块、以及内置全局函数
                    if type_name == "Object" or type_name == "Function" or name.startswith("_"):
                        continue
                    if is_class or is_module or type_name == "Type": # 过滤所有类定义和模块
                        continue
                    # [IES 2.0] 额外过滤掉全局内置函数 (如 len, print)，以允许方法调用 (如 v.len())
                    if symbol.is_const and name in ("len", "print", "range", "input", "get_self_source"):
                        continue
                    res[name] = val
            scope = scope.parent
        return res

    def get_vars_snapshot(self) -> Dict[str, Any]:
        """获取当前所有可见变量的快照（用于调试）"""
        res = {}
        scope = self._current_scope
        while scope:
            symbols = scope.get_all_symbols()
            for name, symbol in symbols.items():
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

    def define_variable(self, name: str, value: Any, declared_type: Any = None, is_const: bool = False, uid: Optional[str] = None, force: bool = False) -> None:
        self._current_scope.define(name, value, declared_type, is_const, uid=uid, force=force)

    def push_intent(self, intent: Union[str, IbIntent], mode: str = "+", tag: Optional[str] = None) -> None:
        if isinstance(intent, str):
            intent = IbIntent(
                ib_class=self._registry.get_class("Intent"),
                content=intent,
                mode=IntentMode.from_str(mode),
                tag=tag,
                role=IntentRole.DYNAMIC
            )
        # [IES 2.0] 模式逻辑：
        # 1. 我们不再物理切断链条，以保证 pop_intent 能够正确恢复之前的栈状态。
        # 2. 逻辑上的切断（排他性/移除）由 LLMExecutor 在合并时根据 IntentMode 处理。
        self._intent_top = IntentNode(intent, self._intent_top)

    def pop_intent(self) -> Optional[Union[IbIntent, Any]]:
        if self._intent_top:
            content = self._intent_top.intent
            self._intent_top = self._intent_top.parent
            return content
        return None

    def get_active_intents(self) -> List[Union[IbIntent, Any]]:
        if not self._intent_top:
            return []
        return self._intent_top.to_list()

    @property
    def intent_stack(self) -> Union[Optional[IntentNode], List[Any]]:
        # [IES 2.0] 为了 IbBehavior 优化，直接返回栈顶节点
        return self._intent_top
        
    @intent_stack.setter
    def intent_stack(self, value: Union[Optional[IntentNode], List[Any]]):
        if isinstance(value, list):
            # 兼容模式：从列表重建链表
            self._intent_top = None
            for i in value:
                self.push_intent(i)
        elif value is None or isinstance(value, IntentNode):
            self._intent_top = value
        else:
            raise TypeError(f"Invalid intent stack type: {type(value)}")

    @property
    def current_scope(self) -> Scope:
        return self._current_scope

    @property
    def global_scope(self) -> Scope:
        return self._global_scope

    @property
    def registry(self) -> Registry:
        return self._registry

    def get_symbol_view(self) -> SymbolView:
        return SymbolViewImpl(self)
