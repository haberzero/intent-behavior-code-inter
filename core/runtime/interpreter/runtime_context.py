from __future__ import annotations
from typing import Optional, Any, Dict, List, Union, TYPE_CHECKING
from core.runtime.interfaces import RuntimeSymbol, Scope, RuntimeContext, SymbolView
from core.base.enums import Provenance
from core.base.source_atomic import Location
from core.runtime.exceptions import StageTransitionError, RegistryIsolationError, ThrownException
from core.kernel.issue import InterpreterError
from core.base.diagnostics.codes import RUN_UNDEFINED_VARIABLE, RUN_TYPE_MISMATCH
from core.kernel.registry import KernelRegistry
from core.kernel.spec import IbSpec
from core.kernel.spec.base import TypeKind
from core.runtime.objects.intent import IbIntent, IntentMode, IntentRole
from core.runtime.objects.kernel import IbClass, IbModule, IbObject, IbValue, IbLLMUncertain, IbFunction
from core.runtime.objects.kernel.base import unbox
from core.runtime.objects.intent_node import IntentNode
from core.runtime.objects.intent_context import IbIntentContext
from core.runtime.objects.cell import IbCell
from core.runtime.interpreter.llm_except_frame import LLMExceptFrame

class RuntimeSymbolImpl:
    def __init__(self, name: str, value: Any, declared_type: Optional[IbSpec] = None, is_const: bool = False, is_intrinsic: bool = False):
        self.name = name
        self.value = value
        self.declared_type = declared_type
        self.current_type = type(value) if value is not None else None
        self.is_const = is_const
        # 内置函数（intrinsic）标志位，由 IntrinsicManager 在注入 print/len/range/...
        # 时设置；``get_vars()`` 使用本标志过滤掉运行时调试不应显示的特权符号，
        # 替代硬编码名单 (``"len", "print", "range", ...``)。
        self.is_intrinsic = is_intrinsic
        # 当变量被内层 lambda 捕获时，提升为 Cell 变量；
        # 此字段指向独立堆对象 IbCell，确保赋值能同步到所有持有该 Cell 的 lambda 闭包。
        self.cell: Optional[Any] = None  # Optional[IbCell]

# 句柄类值承载 kind（S3 物化绑定白名单）：thread/chan/slot/generator/
# thread_result 值绑基类时可经声明类型 rebind 特化类。排除
# CALLABLE_INSTANCE（fn_callable/behavior 自持签名，非声明类型物化）。
_HANDLE_VALUE_KINDS = frozenset({
    "thread",
    "channel",
    "slot",
    "generator",
    "thread_result",
})

class ScopeImpl:
    def __init__(self, parent: Optional['Scope'] = None, registry: Optional[Registry] = None):
        self._symbols: Dict[str, RuntimeSymbol] = {}
        self._uid_to_symbol: Dict[str, RuntimeSymbol] = {} # 基于 Symbol UID 的直接映射
        # sym_uid → IbCell 映射，仅包含已提升为 Cell 变量的条目。
        self._cell_map: Dict[str, Any] = {}  # Dict[str, IbCell]
        self._parent = parent
        # 如果没有传入 registry，则从父作用域继承
        if registry:
            self._registry = registry
        elif parent and parent.registry:
            self._registry = parent.registry
        else:
            raise ValueError("Registry is required for Scope creation (no parent provided)")

    @property
    def registry(self) -> Registry:
        """本作用域关联的对象注册表。"""
        return self._registry

    def _check_type(self, value: Any, declared_type: Optional[Any], name: str):
        """运行时类型检查"""
        if declared_type is None:
            return

        # 类型参数占位（泛型方法体内 ``T x = ...`` 注解）：编译期特化已按实参
        # 校验类型（Box[int] 方法体内 T=int），运行时无对应真实类型（T 的真实
        # 类型由特化决定）——跳过检查，避免 TYPE_PARAM 占位误拒合法值。
        if (
            isinstance(declared_type, IbSpec)
            and declared_type.kind == TypeKind.TYPE_PARAM.value
        ):
            return

        # 特殊处理：IbLLMUncertain 可以赋值给任何类型
        if isinstance(value, IbLLMUncertain):
            return

        # 特殊处理：函数对象赋值给 TypeDef 类型时直接放行
        # (callable 类型可以赋值给任意 TypeDef 声明)
        if (
            isinstance(declared_type, IbSpec)
            and declared_type.kind in (TypeKind.FUNCTION.value, TypeKind.BOUND_METHOD.value, TypeKind.CALLABLE_SIG.value)
            and isinstance(value, IbFunction)
        ):
            return

        # 用户定义类（含枚举）的赋值由编译器在语义分析阶段验证，运行时跳过类型检查。
        # 例外：值为动态 any 逃生阀（`any` 类型类对象）时编译器无法静态验证，须运行时
        # 强制校验（"any 值用于类型化上下文时运行时强制校验"契约）——否则 any 类对象
        # 静默流入用户类变量，后续访问报困惑的 AttributeError 而非清晰的
        # RUN_TYPE_MISMATCH。注意 is_assignable 对动态 any 源会因"类可调用"
        # （is_callable）放行，故此处直接判定、不依赖 assignability。
        is_dynamic_any_marker = (
            isinstance(value, IbObject)
            and value.ib_class is not None
            and value.ib_class.name == "any"
        )
        if (
            isinstance(declared_type, IbSpec)
            and declared_type.kind == TypeKind.CLASS.value
            and declared_type.provenance == Provenance.USER_DEFINED
        ):
            if is_dynamic_any_marker:
                raise InterpreterError(
                    f"Type mismatch: Cannot assign dynamic 'any' value to '{declared_type.name}' for variable '{name}'",
                    error_code=RUN_TYPE_MISMATCH,
                )
            return
            
        # 强契约：运行时类型校验
        if not isinstance(value, IbObject):
            value = self._registry.box(value)

        val_spec = value.ib_class.spec if value.ib_class else None

        # 句柄类值身份物化（S3）：值绑基类（裸 thread/chan/slot/generator/
        # thread_result）+ 声明为特化（thread[int]）时，rebind 值到特化类——
        # 与容器 `_bind_container_specialization` 同构，但句柄值创建点无字面量
        # 节点，声明类型上下文在此统一生效（type() 内省一致 + 运行时区分
        # thread[int]/thread[str]）。仅限值承载句柄 kind（THREAD/CHANNEL/SLOT/
        # GENERATOR/THREAD_RESULT），排除 CALLABLE_INSTANCE（fn_callable/behavior
        # 是自持签名值，非声明类型物化）。rebind 幂等：特化类不存在则保守保持基类。
        if (
            isinstance(declared_type, IbSpec)
            and "[" in getattr(declared_type, "name", "")
            and isinstance(value, IbObject)
            and value.ib_class is not None
            and value.ib_class.spec is not None
            and "[" not in getattr(value.ib_class, "name", "")
            and getattr(declared_type, "kind", None) == value.ib_class.spec.kind
            and getattr(declared_type, "kind", None) in _HANDLE_VALUE_KINDS
            and value.ib_class.spec.get_base_name() == declared_type.get_base_name()
        ):
            specialized_cls = self._registry.get_class(
                declared_type.name, module=declared_type.module_path
            )
            if specialized_cls is None:
                try:
                    spec_reg = self._registry.get_metadata_registry()
                    spec = (
                        spec_reg.resolve(declared_type.name, declared_type.module_path)
                        if spec_reg is not None else None
                    )
                    if spec is not None and not self._registry.is_sealed:
                        specialized_cls = self._registry.create_subclass(
                            declared_type.name, spec, value.ib_class.spec.get_base_name()
                        )
                except Exception:
                    specialized_cls = None
            if specialized_cls is not None:
                from core.kernel.spec.type_ref import TypeRef

                value.ib_class = specialized_cls
                if isinstance(value, IbValue):
                    value.type_ref = TypeRef.from_spec(declared_type)

        val_spec = value.ib_class.spec if value.ib_class else None

        # declared_type 是 IbSpec（来自编译器的类型标注）
        if isinstance(declared_type, IbSpec):
            # Use class-level compatibility check
            spec_reg = value.ib_class.registry.get_metadata_registry()
            if spec_reg and val_spec and not spec_reg.is_assignable(val_spec, declared_type):
                raise InterpreterError(
                    f"Type mismatch: Cannot assign '{val_spec.name}' to '{declared_type.name}' for variable '{name}'",
                    error_code=RUN_TYPE_MISMATCH
                )

    def _wrap_optional(self, value: Any, declared_type: Optional[Any]) -> Any:
        """将值按 Optional 声明类型包装为 ``IbOptional``（幂等）。

        当 ``declared_type`` 是 Optional 类型（且值尚未是 ``IbOptional``）时，
        把值包装进 ``IbOptional``；否则原样返回。这是 Optional 运行时值的
        单一绑定入口——所有变量定义/赋值/函数参数/LLMFuture 解析均经此包装。

        统一委托 ``wrap_optional`` 权威函数（单一实现，杜绝表示分叉）。
        """
        from core.runtime.objects.primitives.optional import wrap_optional

        return wrap_optional(value, declared_type, self._registry)

    def define(self, name: str, value: Any, declared_type: Any = None, is_const: bool = False, uid: Optional[str] = None, force: bool = False, is_intrinsic: bool = False) -> None:
        """定义符号。如果 force=True，允许覆盖已存在的常量符号（用于内核特权恢复路径）"""
        boxed_value = self._registry.box(value)
        
        self._check_type(boxed_value, declared_type, name or uid or "unknown")
        boxed_value = self._wrap_optional(boxed_value, declared_type)

        existing = self._symbols.get(name)

        if not force:
            # 内建函数（is_intrinsic=True）是可遮蔽的默认绑定：用户声明同名变量
            # 即遮蔽（如 `int len = 5`）。内建类型（is_intrinsic=False）与用户
            # 常量不可遮蔽；赋值路径（assign）仍拒绝改写内建绑定。
            if existing is not None and existing.is_const and not existing.is_intrinsic:
                raise InterpreterError(f"Cannot redefine constant '{name}'", error_code=RUN_TYPE_MISMATCH)
            existing_uid = self._uid_to_symbol.get(uid) if uid else None
            if existing_uid is not None and existing_uid.is_const and not existing_uid.is_intrinsic:
                raise InterpreterError(f"Cannot redefine constant UID '{uid}'", error_code=RUN_TYPE_MISMATCH)

        sym = RuntimeSymbolImpl(name, boxed_value, declared_type, is_const, is_intrinsic=is_intrinsic)
        if name:
            self._symbols[name] = sym
        if uid:
            if existing is not None and existing is not sym:
                # 遮蔽被替换的内建符号：清除其旧的 uid 绑定，避免孤儿符号残留
                for k, v in list(self._uid_to_symbol.items()):
                    if v is existing:
                        del self._uid_to_symbol[k]
            self._uid_to_symbol[uid] = sym
        else:
            # 合法编译路径下语义分析始终提供 UID。剩余的无 UID 调用仅来自
            # 内核引导期 / ``HostService`` plugin 恢复等路径，它们持有可信的
            # ``name`` 但无符号 UID。此处使用 ``id(sym)`` 派生唯一 UID，不再发出
            # RuntimeWarning：经 -W error::RuntimeWarning 全测试套件验证（949 测试），
            # 常规执行路径下此分支永不命中。如新代码引入此路径请显式传入 ``uid``。
            assert name, (
                "ScopeImpl.define(): caller must provide either uid or name; "
                "both missing indicates a bootstrap bug."
            )
            fallback_uid = f"rt_{id(sym):x}"
            self._uid_to_symbol[fallback_uid] = sym

    def assign(self, name: str, value: Any) -> bool:
        boxed_value = self._registry.box(value)
        if name in self._symbols:
            symbol = self._symbols[name]
            if symbol.is_const:
                raise InterpreterError(f"Cannot reassign constant '{name}'", error_code=RUN_TYPE_MISMATCH)
            
            # 运行时类型校验
            self._check_type(boxed_value, symbol.declared_type, name)
            
            wrapped = self._wrap_optional(boxed_value, symbol.declared_type)
            symbol.value = wrapped
            symbol.current_type = type(boxed_value)
            # Cell 变量赋值时同步更新共享 IbCell，使持有该 Cell 的
            # lambda 闭包在下次调用时读到最新值。**Cell 同步必须与
            # symbol.value 一致（包装后值）**——读取路径优先 Cell
            # （get 先查 cell），写未包装值会使 Optional 包装丢失
            # （nonlocal 写 Optional 后 unwrap 失败的表示分叉根源）。
            if symbol.cell is not None:
                self._check_cell_isolation(symbol.name or name, symbol.cell)
                symbol.cell.set(wrapped)
            return True
        if self._parent:
            return self._parent.assign(name, value)
        return False

    def assign_by_uid(self, uid: str, value: Any, skip_type_check: bool = False) -> bool:
        """基于 UID 的赋值"""
        boxed_value = self._registry.box(value)
        if uid in self._uid_to_symbol:
            symbol = self._uid_to_symbol[uid]
            if symbol.is_const:
                raise InterpreterError(f"Cannot reassign constant UID '{uid}'", error_code=RUN_TYPE_MISMATCH)
            
            # 运行时类型校验（skip_type_check=True 用于内部缓存写回，如 LLMFuture 解析后的回写）
            if not skip_type_check:
                self._check_type(boxed_value, symbol.declared_type, symbol.name or uid)
            
            wrapped = self._wrap_optional(boxed_value, symbol.declared_type)
            symbol.value = wrapped
            symbol.current_type = type(boxed_value)
            # Cell 变量赋值时同步更新共享 IbCell（与 symbol.value 一致的
            # 包装后值，见 assign 注释——读取优先 Cell）。
            if symbol.cell is not None:
                self._check_cell_isolation(symbol.name or uid, symbol.cell)
                symbol.cell.set(wrapped)
            return True
        if self._parent:
            return self._parent.assign_by_uid(uid, value, skip_type_check=skip_type_check)
        return False

    @staticmethod
    def _check_cell_isolation(var_name: str, cell: Any) -> None:
        """P3 隔离检查：线程任务内禁止写"已共享给主线程"的闭包 cell。

        任务内对捕获变量赋值会写共享 cell（主线程可见），违反"任务不写主环境
        作用域"隔离承诺；跨任务共享必须显式经 chan/slot。任务本地 cell 不受限。
        """
        from core.runtime.frame import get_in_thread_task

        if get_in_thread_task() and cell.shared_with_main:
            raise InterpreterError(
                f"Task isolation violation: cannot assign captured variable "
                f"'{var_name}' inside a thread task (it writes the main thread's "
                f"shared closure cell). Use chan/slot for cross-task communication."
            )

    def get(self, name: str) -> Any:
        symbol = self.get_symbol(name)
        if symbol:
            # Cell 变量：始终从 Cell 读取最新值（nonlocal 写回后可能通过 Cell 更新）
            if symbol.cell is not None and not symbol.cell.is_empty():
                return symbol.cell.get()
            return symbol.value
        raise KeyError(name)

    def receive(self, message: str, args: List[Any]) -> Any:
        """模块作用域协议消息分发：``__getattr__`` 委托到 ``get``，其余按名字查找。"""
        if message == '__getattr__' and len(args) > 0:
            return self.get(args[0].to_native())
        return self.get(message)

    def get_by_uid(self, uid: str) -> Any:
        """基于 UID 的获取"""
        symbol = self.get_symbol_by_uid(uid)
        if symbol:
            # Cell 变量：始终从 Cell 读取最新值
            if symbol.cell is not None and not symbol.cell.is_empty():
                return symbol.cell.get()
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
        if self._parent:
            return self._parent.get_symbol_by_uid(uid)
        return None

    @property
    def parent(self) -> Optional['Scope']:
        return self._parent

    def get_all_symbols(self) -> Dict[str, RuntimeSymbol]:
        """返回当前作用域的所有符号（不包含父作用域）"""
        return dict(self._symbols)

    def get_all_symbols_by_uid(self) -> Dict[str, RuntimeSymbol]:
        """返回当前作用域的所有 UID → 符号映射（不包含父作用域）。

        序列化/快照恢复的公开枚举接口（替代对私有 ``_uid_to_symbol`` 的探测）。
        """
        return dict(self._uid_to_symbol)

    def bind_symbol_by_uid(self, uid: str, sym: RuntimeSymbol) -> None:
        """将既有符号对象绑定到指定 UID（反序列化恢复路径）。

        若同名符号已由按名恢复（``define``）创建，复用该符号对象而非新建，
        保持同一逻辑变量在 name 映射与 UID 映射中共享身份。
        """
        existing = self._symbols.get(sym.name) if sym.name else None
        target = existing if existing is not None else sym
        self._uid_to_symbol[uid] = target

    # ------------------------------------------------------------------
    # Cell 变量支持
    # ------------------------------------------------------------------

    def promote_to_cell(self, sym_uid: str) -> Optional[Any]:
        """
        将符号提升为 Cell 变量（公理 SC-3）。

        规则：
        - 若该 UID 在当前作用域的 _cell_map 中已有 IbCell，直接返回共享引用（幂等）。
        - 若该 UID 对应的符号在本作用域中且本作用域非全局（parent 非 None），
          创建 IbCell(current_value)，写入 symbol.cell 与 _cell_map，返回该 IbCell。
        - 全局作用域（parent 为 None）的变量不提升——它们始终可达，IbCell 无必要。
        - 若本作用域没有该 UID，向上查找父作用域递归处理（SC-4 向外层捕获）。

        返回：IbCell 引用，或 None（变量不存在 / 属于全局作用域不需要提升）。
        """
        if sym_uid in self._cell_map:
            return self._cell_map[sym_uid]
        if sym_uid in self._uid_to_symbol:
            # 全局作用域（顶层）的变量永远可达，不提升
            if self._parent is None:
                return None
            sym = self._uid_to_symbol[sym_uid]
            if sym.cell is not None:
                # 符号已有 cell（e.g. 通过 name-map 已提升），复用
                self._cell_map[sym_uid] = sym.cell
                return sym.cell
            cell = IbCell(sym.value)
            sym.cell = cell
            self._cell_map[sym_uid] = cell
            return cell
        # 向上查找
        if self._parent:
            return self._parent.promote_to_cell(sym_uid)
        return None

    def is_cell_promoted(self, sym_uid: str) -> bool:
        """判断 sym_uid 对应的符号是否已提升为 Cell 变量。

        供 VMExecutor 护栏（``_target_is_promoted_cell``）使用：
        不再直接访问 ``scope._cell_map``，通过本方法保持 ScopeImpl 内部封装。
        """
        return sym_uid in self._cell_map

    def define_raw(self, name: Optional[str], value: Any, uid: Optional[str] = None, declared_type: Any = None) -> 'RuntimeSymbolImpl':
        """低级符号写入：绕过类型检查与 box 操作（VM 特殊路径专用）。

        仅供 VMExecutor 的 ``LLMFuture`` 占位符写入使用（dispatch-before-use）。
        普通变量定义应使用 :meth:`define`；本方法不进行类型校验，不调用 ``registry.box``，
        也不触发 Cell 同步（LLMFuture 不是合法 ``IbObject``，不应进入 cell.set）。

        参数:
            name: 变量名（可为 None，但 name 和 uid 至少须提供其一）
            value: 原始值（通常为 ``LLMFuture`` 占位符）
            uid: 符号 UID（可为 None，此时以 name 生成回退 UID）
            declared_type: 可选的类型标注（来自编译器侧表，仅记录不校验）

        返回:
            新建或覆写的 :class:`RuntimeSymbolImpl` 实例。
        """
        new_sym = RuntimeSymbolImpl(
            name=name or "", value=value, declared_type=declared_type, is_const=False
        )
        if name:
            self._symbols[name] = new_sym
        if uid:
            self._uid_to_symbol[uid] = new_sym
        elif name:
            # 无 UID 时以对象 id 生成回退键（仅此特殊路径，不影响常规符号表）
            self._uid_to_symbol[f"rt_{id(new_sym):x}"] = new_sym
        return new_sym

    def iter_cells(self):
        """
        枚举本作用域（不递归父）的所有 IbCell（GC 根集合扫描入口）。
        """
        return iter(self._cell_map.values())

class SymbolViewImpl:
    """[Active Defense] 只读符号表视图实现"""
    def __init__(self, context: RuntimeContext):
        self._context = context

    def get(self, name: str) -> Any:
        return self._context.get_variable(name)

    def get_symbol(self, name: str) -> Optional[RuntimeSymbol]:
        return self._context.get_symbol(name)

    def has(self, name: str) -> bool:
        return self._context.get_symbol(name) is not None

class RuntimeContextImpl(RuntimeContext):
    def __init__(self, initial_scope: Optional[Scope] = None, registry: Optional[Registry] = None):
        if not registry:
            raise ValueError("Registry is required for RuntimeContext creation")
        self._registry = registry
        self._global_scope = initial_scope or ScopeImpl(registry=self._registry)
        self._current_scope = self._global_scope
        self._loop_stack: List[Dict[str, int]] = []

        # 意图上下文：
        # 持久意图栈、涂抹意图队列、排他意图槽、全局意图全部统一持有在此对象中。
        self._intent_ctx: IbIntentContext = IbIntentContext()

        # 帧级活跃 intent_context IBCI 实例指针
        # ----------------------------------------------------------------
        # 指向当前帧"正在使用"的 intent_context IBCI 对象（用户命名身份）。
        # 不变量：当 ``_active_intent_ibobj`` 非 None 时，
        #   ``_active_intent_ibobj.fields['_ctx'] is self._intent_ctx``
        # 共享引用而非 fork 副本，确保语法路径 (`@+`/`@-`) 与 OOP 路径
        # （``intent_context`` 方法调用）在当前活跃实例上操作的是同一底层 IbIntentContext。
        #
        # 维护点（任一发生即更新此指针）：
        #   - ``use_intent_context(ibobj)``  → 设置为新的封装实例（共享 _ctx 引用）
        #   - ``clear_inherited_intents()``  → 设置为新的匿名封装（清空持久栈）
        #   - 函数调用进入时（fork 调用方）→ 重置为 None（子帧未选择策略）
        #
        # 设计目的：使调试器能够直接观察"当前帧正在使用哪个用户命名的意图策略对象"，
        # 而不是面对一个匿名 Python 对象。``get_current()`` 返回该指针的 fork，
        # 既保留用户对象身份语义，又确保 fork 语义不泄漏。
        self._active_intent_ibobj: Optional[IbObject] = None

        # [LLMExceptFrame] LLM 异常重试帧栈
        self._llm_except_frames: List['LLMExceptFrame'] = []
        # 最大 llmexcept 嵌套深度限制
        self._llm_except_max_depth: int = 128
        # 运行时共享设施槽（由访问器惰性创建；未挂载时默认 None）：
        # 通信注册表 / 线程协调器（通信域）+ 控制配置存储（观测控制域）。
        # 事件总线为引擎级共享实例（registry 承载），非本 rc 私有。
        self._comm_registry: Optional[Any] = None
        self._config_store: Optional[Any] = None
        self._runtime_coordinator: Optional[Any] = None

    # --- 运行时共享设施访问器（公开接口，替代跨对象私有槽穿透） ---
    # 每槽两形态：``get_*`` 惰性创建（调用方需要对象本身）；``peek_*`` 只读
    # 返回（调用方仅检查存在性/读取，不产生副作用）。

    def peek_comm_registry(self) -> Optional[Any]:
        """通信注册表（只读；未创建返回 None）。"""
        return self._comm_registry

    def get_comm_registry(self) -> Any:
        """通信注册表（惰性创建）。供广播枚举 / 定向查找 / 内省统一经此访问。"""
        if self._comm_registry is None:
            from core.runtime.shared.comm.registry import CommRegistry
            self._comm_registry = CommRegistry()
        return self._comm_registry

    def peek_config_store(self) -> Optional[Any]:
        """控制层配置存储（只读；未创建返回 None）。"""
        return self._config_store

    def get_config_store(self) -> Any:
        """控制层配置存储（惰性创建）。供 parallel/observability 等开关读取。"""
        if self._config_store is None:
            from core.runtime.observability.config import ConfigStore
            self._config_store = ConfigStore()
        return self._config_store

    def peek_event_bus(self) -> Optional[Any]:
        """内省事件总线（只读；未创建返回 None）。

        引擎级共享实例（registry 承载）：所有 RuntimeContextImpl 共享同一总线，
        线程任务事件可达主订阅者（计算隔离、观测全局）。
        """
        return self._registry.peek_event_bus()

    def get_event_bus(self) -> Any:
        """内省事件总线（惰性创建于引擎级）。供事件源广播内省事件流。"""
        return self._registry.get_event_bus()

    def peek_runtime_coordinator(self) -> Optional[Any]:
        """线程协调器（只读；未创建返回 None）。"""
        return self._runtime_coordinator

    def get_runtime_coordinator(self, interpreter: Optional[Any] = None) -> Any:
        """线程协调器（惰性创建；interpreter 仅在首次创建时需要）。

        供线程构造（primitive_initializer）与 save_state/snapshot 统一经此访问。
        """
        if self._runtime_coordinator is None:
            from core.runtime.coordinator import RuntimeCoordinator
            self._runtime_coordinator = RuntimeCoordinator(interpreter)
        return self._runtime_coordinator

    # --- 排他意图管理 ---

    # --- 涂抹意图管理 (@) ---

    def add_smear_intent(self, intent: IbIntent) -> None:
        """添加一次性涂抹意图（@）。"""
        self._intent_ctx.add_smear(intent)

    def activate_statement_one_shot_intent(self, intent: IbIntent) -> None:
        """
        为"下一条语句"安装一次性意图。

        - override：安装到 override 槽（优先级最高）
        - smear：追加到 smear 队列（由后续 LLM 调用被动消费）
        """
        if intent.is_override:
            self._intent_ctx.set_override(intent)
        else:
            self._intent_ctx.add_smear(intent)

    def cleanup_statement_one_shot_intent(self, intent: IbIntent) -> None:
        """
        清理上一条语句绑定的一次性意图残留（若尚未被消费）。

        语义：
        - 若该 one-shot 已在语句执行期间被 LLM 消费，则此处 no-op。
        - 若语句路径没有任何 LLM 调用，则主动清理，防止泄漏到后续语句。
        """
        if intent.is_override:
            self._intent_ctx.clear_override_if(intent)
        else:
            self._intent_ctx.discard_smear(intent)

    # --- LLM 结果状态（调试内省） ---

    def push_llm_except_frame(self, frame: 'LLMExceptFrame') -> None:
        """
        将新的 LLMExceptFrame 入栈。
        用于 llmexcept 语句执行前保存现场。
        """
        if len(self._llm_except_frames) >= self._llm_except_max_depth:
            raise RuntimeError(
                f"LLMExceptFrame stack overflow: max depth {self._llm_except_max_depth} exceeded"
            )
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

    def get_llm_except_frames(self) -> List['LLMExceptFrame']:
        """
        获取完整的 LLMExcept 帧栈（只读副本）。
        供核心层插件（如 ibci_idbg）通过 IStateReader 接口访问，
        避免直接访问内部属性 _llm_except_frames。
        """
        return list(self._llm_except_frames)

    def save_llm_except_state(self, target_uid: str, node_type: str = "unknown", max_retry: int = 3) -> 'LLMExceptFrame':
        """
        创建并保存 LLMExceptFrame 现场。
        1. 序列化当前作用域的变量快照
        2. 保存 intent 栈状态
        3. 保存 loop 上下文
        4. 保存 retry_hint
        """
        frame = LLMExceptFrame(
            target_uid=target_uid,
            node_type=node_type,
            max_retry=max_retry
        )
        frame.save_context(self)
        self.push_llm_except_frame(frame)
        return frame

    def get_current_scope(self) -> Scope:
        return self._current_scope

    def push_loop_context(self, index: int, total: int) -> None:
        self._loop_stack.append({"index": index, "total": total})

    def pop_loop_context(self) -> None:
        if self._loop_stack:
            self._loop_stack.pop()

    def get_loop_context(self) -> Optional[Dict[str, int]]:
        if self._loop_stack:
            return self._loop_stack[-1]
        return None

    def get_loop_context_stack(self) -> List[Dict[str, int]]:
        """返回当前循环上下文栈的深拷贝快照（llmexcept 帧保存用）。

        深拷贝保证快照与运行时 ``_loop_stack`` 完全独立，即使后续栈内 dict
        被就地修改也不影响快照正确性。
        """
        return [dict(d) for d in self._loop_stack]

    def restore_loop_context_stack(self, stack: List[Dict[str, int]]) -> None:
        """以快照整体替换循环上下文栈（llmexcept 帧恢复用）。"""
        self._loop_stack = list(stack)

    def set_global_intent(self, intent: Union[str, IbIntent]) -> None:
        if isinstance(intent, str):
            intent = IbIntent(
                ib_class=self._registry.get_class("Intent"),
                content=intent,
                mode=IntentMode.APPEND,
                role=IntentRole.GLOBAL
            )
        current = self._intent_ctx.get_global_intents()
        if intent not in current:
            self._intent_ctx.set_global_intents(current + [intent])

    def clear_global_intents(self) -> None:
        self._intent_ctx.set_global_intents([])

    def remove_global_intent(self, intent: Union[str, IbIntent]) -> None:
        if isinstance(intent, str):
            filtered = [i for i in self._intent_ctx.get_global_intents() if i.content != intent]
        else:
            filtered = [i for i in self._intent_ctx.get_global_intents() if i is not intent]
        self._intent_ctx.set_global_intents(filtered)

    def get_global_intents(self) -> List[IbIntent]:
        return self._intent_ctx.get_global_intents()

    def _iter_user_vars(self):
        """单一权威：作用域链用户可见变量遍历（统一过滤策略）。

        从当前作用域向外遍历，内层同名遮蔽外层；yield
        ``(name, value_ibobject, type_name, is_const)``。

        过滤：非基础类型（Object/Function/Type）、下划线变量、
        类定义/模块、内置 intrinsic 函数（不暴露给调试/观测面板）。
        供 ``get_vars`` / ``get_vars_snapshot`` 共享（消除双入口过滤分歧）。
        """
        seen: set = set()
        scope = self._current_scope
        while scope:
            for name, symbol in scope.get_all_symbols().items():
                if name in seen:
                    continue
                seen.add(name)
                val = symbol.value
                type_name = val.ib_class.name if isinstance(val, IbObject) and val.ib_class else "Object"
                if type_name in ("Object", "Function", "Type"):
                    continue
                if name.startswith("_"):
                    continue
                if isinstance(val, (IbClass, IbModule)):
                    continue
                if getattr(symbol, "is_intrinsic", False):
                    continue
                yield name, val, type_name, symbol.is_const
            scope = scope.parent

    def get_vars(self) -> Dict[str, Any]:
        """获取当前可见的所有真实变量对象 (IbObject)。"""
        return {name: val for name, val, _type, _const in self._iter_user_vars()}

    def get_vars_snapshot(self) -> Dict[str, Any]:
        """获取当前所有可见变量的快照（用于调试/观测）。

        统一变量视图的富形态：``{name: {"value": 原生值, "type": 类型名,
        "is_const": 是否常量}}``。与 ``get_vars`` 共享单一遍历与过滤策略。
        """
        res = {}
        for name, val, type_name, is_const in self._iter_user_vars():
            res[name] = {
                "value": unbox(val),
                "type": type_name,
                "is_const": is_const,
            }
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

    def set_variable_by_uid(self, uid: str, value: Any, skip_type_check: bool = False) -> None:
        """基于 UID 赋值"""
        if not self._current_scope.assign_by_uid(uid, value, skip_type_check=skip_type_check):
            raise InterpreterError(f"Variable UID '{uid}' is not defined", error_code=RUN_UNDEFINED_VARIABLE)

    def define_variable(self, name: str, value: Any, declared_type: Any = None, is_const: bool = False, uid: Optional[str] = None, force: bool = False, is_intrinsic: bool = False) -> None:
        self._current_scope.define(name, value, declared_type, is_const, uid=uid, force=force, is_intrinsic=is_intrinsic)

    def define_variable_at_global(self, name: str, value: Any, declared_type: Any = None, is_const: bool = False, uid: Optional[str] = None) -> None:
        """在全局作用域中定义变量（用于 global 语句创建新全局变量）。"""
        self._global_scope.define(name, value, declared_type, is_const, uid=uid)

    def is_global_symbol_uid(self, uid: str) -> bool:
        """
        判断符号 UID 是否属于全局作用域。

        UID 格式约定：
        - 全局作用域变量：`scope_<module>:<varname>`（作用域部分不含 '/'）
        - 函数/类局部变量：`scope_<module>/<func>:<varname>`（作用域部分含 '/'）
        """
        scope_part = uid.rsplit(":", 1)[0] if ":" in uid else uid
        return "/" not in scope_part

    def push_intent(self, intent: Union[str, IbIntent], mode: str = "+", tag: Optional[str] = None) -> None:
        if isinstance(intent, str):
            intent = IbIntent(
                ib_class=self._registry.get_class("Intent"),
                content=intent,
                mode=IntentMode.from_str(mode),
                tag=tag,
                role=IntentRole.DYNAMIC
            )
        self._intent_ctx.push(intent)

    def pop_intent(self) -> Optional[Union[IbIntent, Any]]:
        return self._intent_ctx.pop()

    def remove_intent(self, tag: Optional[str] = None, content: Optional[str] = None) -> bool:
        """
        从持久意图栈中物理移除匹配的意图。

        @- #tag → 按标签移除（移除最近添加的匹配标签的意图）
        @- content → 按内容移除
        返回是否成功移除。
        """
        return self._intent_ctx.remove(tag=tag, content=content)

    def get_active_intents(self) -> List[Union[IbIntent, Any]]:
        return self._intent_ctx.get_active_intents()

    def fork_intent_snapshot(self) -> 'IbIntentContext':
        """
        返回当前意图上下文的不可变值快照（IbIntentContext.fork()）。
        用于 LLM 流水线 dispatch 时刻和 LLMExceptFrame 的快照保存。
        """
        return self._intent_ctx.fork()

    @property
    def intent_context(self) -> 'IbIntentContext':
        """当前帧的意图上下文（直接持有的 IbIntentContext 实例）。"""
        return self._intent_ctx

    def use_intent_context(self, intent_ctx_obj: Any) -> None:
        """
        以指定 intent_context IBCI 实例替换当前帧意图上下文（fork 拷贝语义）。

        行为与 intent_context.use(ctx) 对齐：
        - 使用 ctx._ctx 的 fork 副本，避免引用共享
        - 保留当前帧的全局意图（Engine 级注入）

        在替换底层 IbIntentContext 的同时，重建当前帧的
        ``_active_intent_ibobj`` 指针——它持有一个**新的** intent_context IBCI
        包装对象，其 ``fields['_ctx']`` 与帧的 ``_intent_ctx`` 共享引用。
        因此后续语法路径（``@+``/``@-``）与 OOP 路径（``active.push(...)``）
        操作的是同一底层 IbIntentContext，而原始实参 ``intent_ctx_obj``
        因 fork 语义不会受到泄漏影响。

        非法入参（非 intent_context 对象）fail-fast 抛 InterpreterError——
        静默返回会吞掉语言面错误输入，无任何诊断。
        """
        if not isinstance(intent_ctx_obj, IbObject):
            raise InterpreterError(
                "intent_context.use(): expected an intent_context instance, "
                f"got {type(intent_ctx_obj).__name__}"
            )
        other_ctx = intent_ctx_obj.fields.get("_ctx")
        if not isinstance(other_ctx, IbIntentContext):
            raise InterpreterError(
                "intent_context.use(): the given object is not an intent_context "
                f"(its '_ctx' slot holds {type(other_ctx).__name__})"
            )
        forked = other_ctx.fork()
        forked.set_global_intents(self._intent_ctx.get_global_intents())
        self._intent_ctx = forked
        # 同步更新活跃实例指针，使其封装与 _intent_ctx 共享引用。
        self._set_active_intent_ibobj_for_current_ctx(intent_ctx_obj.ib_class)

    # ------------------------------------------------------------------ #
    # active intent_context IBCI handle                                   #
    # ------------------------------------------------------------------ #

    def _set_active_intent_ibobj_for_current_ctx(self, ib_class: Any) -> None:
        """
        构造一个新的 ``intent_context`` IBCI 封装对象，其 ``_ctx`` 与
        当前帧的 ``self._intent_ctx`` 共享引用，并将其登记为活跃实例指针。

        共享引用不变量：当用户在该封装上调用 ``push()`` 时，
        修改的就是帧的 ``_intent_ctx``；反之 ``@+`` 修改的也是该封装的 ``_ctx``。
        """
        wrapper = IbObject(ib_class)
        wrapper.fields['_ctx'] = self._intent_ctx
        self._active_intent_ibobj = wrapper

    def get_active_intent_ibobj(self) -> Optional[Any]:
        """返回当前帧活跃的 intent_context IBCI 实例指针（可能为 None）。"""
        return self._active_intent_ibobj

    def set_active_intent_ibobj(self, ibobj: Optional[Any]) -> None:
        """
        直接设置活跃实例指针。

        调用方约定：
        - 传入 ``None`` 时表示当前帧没有命名策略（匿名意图状态）。
        - 传入 ``IbObject`` 时，调用方需保证 ``ibobj.fields['_ctx'] is self._intent_ctx``
          才能维持共享引用不变量。
        """
        self._active_intent_ibobj = ibobj

    def clear_inherited_intents(self) -> None:
        """
        清空当前帧从调用者继承的持久意图栈。

        与 ``intent_context.clear_inherited()`` IBCI API 一致：
        - 重置 ``_intent_ctx`` 的持久意图栈为空
        - 重建 ``_active_intent_ibobj`` 为新的匿名封装（共享 _ctx 引用），
          表示当前帧重置为干净的匿名意图状态

        全局意图和涂抹/排他槽位**不**被清除（仅清空持久 ``@+`` 栈）。
        """
        self._intent_ctx.set_intent_top(None)
        intent_context_class = self._registry.get_class("intent_context")
        if intent_context_class is not None:
            self._set_active_intent_ibobj_for_current_ctx(intent_context_class)
        else:
            self._active_intent_ibobj = None

    def restore_active_intents(self, intents: Union[List[IbIntent], Optional['IntentNode']]) -> None:
        """
        恢复活跃意图栈。支持直接设置 IntentNode (结构共享) 或 扁平列表重建。
        """
        if intents is None:
            self._intent_ctx.set_intent_top(None)
        elif isinstance(intents, IntentNode):
            self._intent_ctx.set_intent_top(intents)
        elif isinstance(intents, list):
            self._intent_ctx.set_intent_top(None)
            for intent in intents:
                self._intent_ctx.push(intent)
        else:
            raise TypeError(f"Invalid intent stack type for restoration: {type(intents)}")

    def enter_intent_scope(self) -> tuple:
        """函数调用进入时 fork 当前意图上下文，返回 (old_ctx, old_active_ibobj) 供 exit_intent_scope 恢复。"""
        old_ctx = self._intent_ctx
        old_active = self._active_intent_ibobj
        self._intent_ctx = old_ctx.fork()
        intent_context_class = self._registry.get_class("intent_context") if self._registry else None
        if intent_context_class is not None:
            self._set_active_intent_ibobj_for_current_ctx(intent_context_class)
        else:
            self._active_intent_ibobj = None
        return (old_ctx, old_active)

    def exit_intent_scope(self, saved: tuple) -> None:
        """函数调用退出时恢复调用者的意图上下文和活跃指针。"""
        old_ctx, old_active = saved
        self._intent_ctx = old_ctx
        self._active_intent_ibobj = old_active

    def replace_intent_context(self, new_ctx) -> None:
        """整替换意图上下文（供 llmexcept retry / 反序列化使用），并重建活跃指针。"""
        self._intent_ctx = new_ctx
        intent_context_class = self._registry.get_class("intent_context") if self._registry else None
        if intent_context_class is not None:
            self._set_active_intent_ibobj_for_current_ctx(intent_context_class)
        else:
            self._active_intent_ibobj = None

    def get_resolved_prompt_intents(self, execution_context: Any, call_intent: Optional[Any] = None) -> List[str]:
        """
        获取最终消解后的 Prompt 字符串列表。

        优先级（从高到低）：
        1. @! 排他意图（pending_override）：只返回该意图，清除所有 pending smear
        2. @ 涂抹意图（pending_smear）：一次性，合并入本次结果后清除
        3. 持久意图栈（active_intents via @+）
        4. 全局意图

        实现委托 ``IbIntentContext.resolve_to_prompts``（单一权威源，与
        dispatch-before-use 路径的快照解析共用同一逻辑）。

        ``call_intent`` 为协议预留参数（当前消解逻辑未消费；签名与
        ``IRuntimeContext`` 对齐）。
        """
        return self._intent_ctx.resolve_to_prompts(self, execution_context)

    def get_resolved_prompt_intents_cps(self, execution_context: Any, call_intent: Optional[Any] = None):
        """CPS 版 :meth:`get_resolved_prompt_intents`；意图内容解析嵌入外层 VM 帧栈。

        与同步版同语义（override / smear / active / global 优先级与消费逻辑），
        但意图段求值经 ``resolve_content_cps`` / ``IntentResolver.resolve_cps``
        （``yield from``）——消除 ``vm.run`` 同步重入调度循环（任务内同步重入）。
        ``call_intent`` 为协议预留参数（当前消解逻辑未消费；签名与
        ``IRuntimeContext`` 对齐）。
        实现委托 ``IbIntentContext.resolve_to_prompts_cps``（单一权威源）。
        """
        return (yield from self._intent_ctx.resolve_to_prompts_cps(self, execution_context))

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
