from __future__ import annotations
from typing import Optional, Any, Dict, List, Union, TYPE_CHECKING
from core.runtime.interfaces import RuntimeSymbol, Scope, RuntimeContext, SymbolView
from core.base.source_atomic import Location
from core.runtime.exceptions import BreakException, ContinueException, ReturnException, StageTransitionError, RegistryIsolationError, ThrownException
from core.kernel.issue import InterpreterError
from core.base.diagnostics.codes import RUN_UNDEFINED_VARIABLE, RUN_TYPE_MISMATCH
from core.kernel.registry import KernelRegistry
from core.kernel.spec import IbSpec
from core.kernel.intent_resolver import IntentResolver
from core.runtime.objects.intent import IbIntent, IntentMode, IntentRole
from core.runtime.objects.kernel import IbClass, IbModule, IbObject

if TYPE_CHECKING:
    from core.runtime.interpreter.llm_except_frame import LLMExceptFrame, LLMExceptFrameStack
    from core.runtime.interpreter.llm_result import LLMResult

class RuntimeSymbolImpl:
    def __init__(self, name: str, value: Any, declared_type: Optional[IbSpec] = None, is_const: bool = False):
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

        # 特殊处理：IbLLMUncertain 可以赋值给任何类型
        from core.runtime.objects.kernel import IbLLMUncertain, IbFunction
        if isinstance(value, IbLLMUncertain):
            return

        # 特殊处理：函数对象赋值给 FuncSpec 类型时直接放行
        # (callable 类型可以赋值给任意 FuncSpec 声明)
        from core.kernel.spec.specs import FuncSpec, BoundMethodSpec, ClassSpec
        if isinstance(declared_type, (FuncSpec, BoundMethodSpec)) and isinstance(value, IbFunction):
            return

        # 用户定义类（含枚举）的赋值由编译器在语义分析阶段验证，运行时跳过类型检查
        if isinstance(declared_type, ClassSpec) and declared_type.is_user_defined:
            return
            
        # [Phase 3.3] 强契约：运行时类型校验
        if not hasattr(value, 'ib_class'):
            value = self._registry.box(value)

        val_spec = value.ib_class.spec if value.ib_class else None

        # declared_type 是 IbSpec（来自编译器的类型标注）
        if isinstance(declared_type, IbSpec):
            if val_spec:
                if not value.ib_class.is_assignable_to(value.ib_class.registry.get_class(declared_type.name) if declared_type.name else None):
                    pass  # runtime assignability checked below
            # Use class-level compatibility check
            spec_reg = value.ib_class.registry.get_metadata_registry()
            if spec_reg and val_spec and not spec_reg.is_assignable(val_spec, declared_type):
                raise InterpreterError(
                    f"Type mismatch: Cannot assign '{val_spec.name}' to '{declared_type.name}' for variable '{name}'",
                    error_code=RUN_TYPE_MISMATCH
                )

    def define(self, name: str, value: Any, declared_type: Any = None, is_const: bool = False, uid: Optional[str] = None, force: bool = False) -> None:
        """定义符号。如果 force=True，允许覆盖已存在的常量符号（用于内核特权恢复路径）"""
        boxed_value = self._registry.box(value)
        
        self._check_type(boxed_value, declared_type, name or uid or "unknown")

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
        else:
            import hashlib
            content_repr = f"{name}:{type(boxed_value).__name__}"
            if hasattr(boxed_value, 'value'):
                content_repr += f":{boxed_value.value!r}"
            fallback_uid = f"rt_{hashlib.sha256(content_repr.encode()).hexdigest()[:12]}"
            self._uid_to_symbol[fallback_uid] = sym

    def assign(self, name: str, value: Any) -> bool:
        boxed_value = self._registry.box(value)
        if name in self._symbols:
            symbol = self._symbols[name]
            if symbol.is_const:
                raise InterpreterError(f"Cannot reassign constant '{name}'", error_code=RUN_TYPE_MISMATCH)
            
            # 运行时类型校验
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
            
            # 运行时类型校验
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

class SymbolViewImpl:
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
    """ 不可变意图节点，支持结构共享以优化内存"""
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

class RuntimeContextImpl(RuntimeContext):
    def __init__(self, initial_scope: Optional[Scope] = None, registry: Optional[Registry] = None):
        if not registry:
            raise ValueError("Registry is required for RuntimeContext creation")
        self._registry = registry
        self._global_scope = initial_scope or ScopeImpl(registry=self._registry)
        self._current_scope = self._global_scope
        self._intent_top: Optional[IntentNode] = None # 意图栈顶节点
        self._global_intents: List[IbIntent] = []
        self._loop_stack: List[Dict[str, int]] = []
        self._retry_hint: Optional[str] = None # 运行时重试提示词

        # [排他意图] 临时的单次作用排他意图
        # @! 创建一个临时的 IntentStack 实例，用于当前这一次 LLM 调用后销毁
        # 全局意图栈保持不变
        self._pending_override_intent: Optional[IbIntent] = None

        # [涂抹意图] 一次性单行意图（@）
        # @ 不压入持久栈，只对紧跟的下一次 LLM 调用有效，调用后自动清除
        self._pending_smear_intents: List[IbIntent] = []

        # [LLMExceptFrame] LLM 异常重试帧栈
        # 当 llmexcept/retry 机制完全迁移到帧栈后，此属性用于管理嵌套的 llmexcept 结构。
        # 每个帧保存执行状态（变量快照、intent 栈、loop 上下文），支持状态恢复和精确重试。
        self._llm_except_frames: List['LLMExceptFrame'] = []

        # [LLMResult] 最后一个 LLM 执行结果
        # 用于 visit_IbLLMExceptionalStmt 检查 LLM 调用是否返回不确定性
        self._last_llm_result: Optional['LLMResult'] = None

    # --- 排他意图管理 ---

    def set_pending_override_intent(self, intent: IbIntent) -> None:
        """
        设置临时的排他意图。

        @! 创建临时的单次作用 IntentStack 实例，用于当前这一次 LLM 调用后销毁。
        全局意图栈保持不变。
        """
        self._pending_override_intent = intent

    def consume_pending_override_intent(self) -> Optional[IbIntent]:
        """
        消费并清除临时的排他意图。

        返回排他意图（如果有），并清除状态。
        这在 LLM 调用完成后被调用。
        """
        intent = self._pending_override_intent
        self._pending_override_intent = None
        return intent

    def has_pending_override_intent(self) -> bool:
        """检查是否存在待处理的排他意图"""
        return self._pending_override_intent is not None

    # --- 涂抹意图管理 (@) ---

    def add_smear_intent(self, intent: IbIntent) -> None:
        """
        添加一次性涂抹意图（@）。

        @ 不压入持久意图栈，只对紧跟的下一次 LLM 调用有效，
        调用完成后自动清除。与 @+ 的持久压栈语义不同。
        """
        self._pending_smear_intents.append(intent)

    # --- LLM Result 管理 ---

    def set_last_llm_result(self, result: 'LLMResult') -> None:
        """设置最后一个 LLM 执行结果"""
        self._last_llm_result = result

    def get_last_llm_result(self) -> Optional['LLMResult']:
        """获取最后一个 LLM 执行结果"""
        return self._last_llm_result

    def clear_last_llm_result(self) -> None:
        """清除最后一个 LLM 执行结果"""
        self._last_llm_result = None

    def push_llm_except_frame(self, frame: 'LLMExceptFrame') -> None:
        """
        将新的 LLMExceptFrame 入栈。
        用于 llmexcept 语句执行前保存现场。
        """
        self._llm_except_frames.append(frame)

    def pop_llm_except_frame(self) -> Optional['LLMExceptFrame']:
        """
        弹出栈顶 LLMExceptFrame。
        用于 llmexcept body 执行完毕后清理现场。
        """
        if self._llm_except_frames:
            return self._llm_except_frames.pop()
        return None

    def get_current_llm_except_frame(self) -> Optional['LLMExceptFrame']:
        """
        获取当前 LLMExceptFrame（不弹出）。
        用于 retry 语句访问当前帧信息。
        """
        if self._llm_except_frames:
            return self._llm_except_frames[-1]
        return None

    def save_llm_except_state(self, target_uid: str, node_type: str = "unknown", max_retry: int = 3) -> 'LLMExceptFrame':
        """
        创建并保存 LLMExceptFrame 现场。
        1. 序列化当前作用域的变量快照
        2. 保存 intent 栈状态
        3. 保存 loop 上下文
        4. 保存 retry_hint
        """
        from core.runtime.interpreter.llm_except_frame import LLMExceptFrame
        frame = LLMExceptFrame(
            target_uid=target_uid,
            node_type=node_type,
            max_retry=max_retry
        )
        frame.save_context(self)
        self.push_llm_except_frame(frame)
        return frame

    def restore_llm_except_state(self) -> bool:
        """
        从当前 LLMExceptFrame 恢复现场。
        1. 恢复变量快照
        2. 恢复 intent 栈
        3. 恢复 loop 上下文
        4. 恢复 retry_hint
        
        Returns:
            True 如果恢复成功，False 如果帧栈为空
        """
        frame = self.get_current_llm_except_frame()
        if frame:
            frame.restore_context(self)
            return True
        return False

    def get_current_scope(self) -> Scope:
        return self._current_scope

    @property
    def retry_hint(self) -> Optional[str]:
        return self._retry_hint

    @retry_hint.setter
    def retry_hint(self, value: Optional[str]):
        self._retry_hint = value

    def push_loop_context(self, index: int, total: int) -> None:
        self._loop_stack.append({"index": index, "total": total})

    def pop_loop_context(self) -> None:
        if self._loop_stack:
            self._loop_stack.pop()

    def get_loop_context(self) -> Optional[Dict[str, int]]:
        if self._loop_stack:
            return self._loop_stack[-1]
        return None

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
        """ 获取当前可见的所有真实变量对象 (IbObject)。"""
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
                    # 额外过滤掉全局内置函数 (如 len, print)，以允许方法调用 (如 v.len())
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
                    type_name = "auto"
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
        # 模式逻辑：
        # 1. 我们不再物理切断链条，以保证 pop_intent 能够正确恢复之前的栈状态。
        # 2. 逻辑上的切断（排他性/移除）由 LLMExecutor 在合并时根据 IntentMode 处理。
        self._intent_top = IntentNode(intent, self._intent_top)

    def pop_intent(self) -> Optional[Union[IbIntent, Any]]:
        if self._intent_top:
            content = self._intent_top.intent
            self._intent_top = self._intent_top.parent
            return content
        return None

    def remove_intent(self, tag: Optional[str] = None, content: Optional[str] = None) -> bool:
        """
        从栈中物理移除匹配的意图。

        @- #tag → 按标签移除（移除最近添加的匹配标签的意图）
        @- content → 按内容移除（移除最近添加的匹配内容的意图）

        返回是否成功移除。
        """
        if not self._intent_top:
            return False

        if tag:
            removed = self._remove_by_tag(tag)
            if removed:
                return True

        if content:
            removed = self._remove_by_content(content)
            if removed:
                return True

        return False

    def _remove_by_tag(self, tag: str) -> bool:
        """按标签移除意图（栈顶优先）"""
        if not self._intent_top:
            return False

        current = self._intent_top
        previous = None

        while current:
            intent = current.intent
            if intent.tag == tag:
                if previous:
                    previous.parent = current.parent
                else:
                    self._intent_top = current.parent
                # 清除 _intent_top 的缓存，因为 to_list() 是从它开始调用的
                self._intent_top._cached_list = None if self._intent_top else None
                self._invalidate_cache_up_to_root(previous)
                return True
            previous = current
            current = current.parent

        return False

    def _remove_by_content(self, content: str) -> bool:
        """按内容移除意图（栈顶优先）"""
        if not self._intent_top:
            return False

        current = self._intent_top
        previous = None

        while current:
            intent = current.intent
            has_content = hasattr(intent, 'content')
            intent_content = getattr(intent, 'content', None) if has_content else None
            if has_content and intent_content == content:
                if previous:
                    previous.parent = current.parent
                else:
                    self._intent_top = current.parent
                # 清除 _intent_top 的缓存，因为 to_list() 是从它开始调用的
                self._intent_top._cached_list = None if self._intent_top else None
                self._invalidate_cache_up_to_root(previous)
                return True
            previous = current
            current = current.parent

        return False

    def _invalidate_cache_up_to_root(self, node: Optional['IntentNode']) -> None:
        """清除从节点到根节点的所有缓存"""
        while node:
            node._cached_list = None
            node = node.parent

    def get_active_intents(self) -> List[Union[IbIntent, Any]]:
        if not self._intent_top:
            return []
        return self._intent_top.to_list()

    def restore_active_intents(self, intents: Union[List[IbIntent], Optional[IntentNode]]) -> None:
        """
         恢复活跃意图栈。支持直接设置 IntentNode (结构共享) 或 扁平列表重建。
        """
        if intents is None:
            self._intent_top = None
        elif isinstance(intents, IntentNode):
            self._intent_top = intents
        elif isinstance(intents, list):
            # 扁平列表恢复：假设列表顺序为 [bottom, ..., top]
            self._intent_top = None
            for intent in intents:
                self._intent_top = IntentNode(intent, self._intent_top)
        else:
            raise TypeError(f"Invalid intent stack type for restoration: {type(intents)}")

    def get_resolved_prompt_intents(self, execution_context: Any) -> List[str]:
        """
        获取最终消解后的 Prompt 字符串列表。

        优先级（从高到低）：
        1. @! 排他意图（pending_override）：只返回该意图，清除所有 pending smear
        2. @ 涂抹意图（pending_smear）：一次性，合并入本次结果后清除
        3. 持久意图栈（active_intents via @+）
        4. 全局意图
        """
        # 检查是否有待处理的排他意图 (@!)
        pending_override = self._pending_override_intent
        if pending_override:
            # 消费排他意图（清除状态）
            self._pending_override_intent = None
            # @! 排他：丢弃同时存在的涂抹意图（两者语义互斥，编译器已阻止共存）
            self._pending_smear_intents.clear()
            content = pending_override.resolve_content(self, execution_context)
            return [content] if content else []

        # 消费一次性涂抹意图（@ 单行意图）
        smear_intents = list(self._pending_smear_intents)
        self._pending_smear_intents.clear()

        # 正常解析意图栈
        active_intents = self.get_active_intents()
        global_intents = self.get_global_intents()

        return IntentResolver.resolve(
            active_intents=active_intents + smear_intents,
            global_intents=global_intents,
            context=self,
            execution_context=execution_context
        )

    @property
    def intent_stack(self) -> Union[Optional[IntentNode], List[Any]]:
        # 为了 IbBehavior 优化，直接返回栈顶节点
        return self._intent_top
        
    @intent_stack.setter
    def intent_stack(self, value: Optional[IntentNode]):
        """ 仅支持基于 IntentNode 的链表设置，确保栈状态一致性"""
        if value is None or isinstance(value, IntentNode):
            self._intent_top = value
        else:
            raise TypeError(f"Invalid intent stack type: {type(value)}. Must be IntentNode or None.")

    @property
    def current_scope(self) -> Scope:
        return self._current_scope

    @current_scope.setter
    def current_scope(self, value: Scope) -> None:
        """ 允许切换当前作用域（用于跨模块调用）"""
        self._current_scope = value

    @property
    def global_scope(self) -> Scope:
        return self._global_scope

    def get_symbol_view(self) -> SymbolView:
        return SymbolViewImpl(self)
