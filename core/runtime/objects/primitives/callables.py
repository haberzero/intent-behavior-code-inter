from typing import Any, Dict, List, Optional
from ..kernel import IbObject, IbValue, IbClass
from core.runtime.frame import get_current_execution_context
from core.runtime.objects.cell import IbCell
from core.runtime.objects.deep_clone import try_deep_clone
from ..ib_type_mapping import register_ib_type


# --------------------------------------------------------------------------- #
# 可调用对象内部元数据消息（非语言级协议——集中声明，消除散落字符串；D2）
# --------------------------------------------------------------------------- #

def _meta_str(obj: "IbValue") -> IbObject:
    """内部元数据消息：对象呈现（__get_metadata__ / node_uid）。"""
    return obj.ib_class.registry.box(str(obj))


def _return_type_str(obj: "IbValue") -> IbObject:
    """内部元数据消息：签名返回类型查询（__return_type__）。"""
    return obj.ib_class.registry.box(obj.get_return_type())


# 类内部消息 → 处理函数映射（可调用对象族共享；若未来有第二个消费者再升级
# 为注册表协议）
_INTERNAL_MESSAGES = frozenset(("__get_metadata__", "node_uid", "__return_type__"))
_INTERNAL_DISPATCH: Dict[str, Any] = {
    "__get_metadata__": _meta_str,
    "node_uid": _meta_str,
    "__return_type__": _return_type_str,
}

@register_ib_type("fn_callable")
class IbFnCallable(IbValue):
    """
    普通可调用实例对象（fn_callable）。

    ``lambda`` / ``snapshot`` 修饰的任意表达式都会被包装为 IbFnCallable。
    调用时重新执行捕获的 AST 节点。

    公理化设计
    ----------
    * IbFnCallable 在创建时捕获 ``execution_context`` 引用。
    * ``call()`` 重新访问捕获的 AST 节点以完成求值。
    * capture_mode='lambda'   —— 每次调用使用当前作用域 / 当前活跃意图栈，
      自由变量经由共享 ``IbCell`` 引用——不拷贝任何内容。
    * capture_mode='snapshot' —— 定义时所有自由变量已被深克隆为只读种子；
      每次调用前对种子再做一次深克隆作为本次调用的私有副本——snapshot 是
      **无状态、可重入** 的可调用实例，多次调用之间彼此独立，绝不缓存结果。

    继承链：IbFnCallable → IbObject (axiom: fn_callable → callable → Object)

    参数化拓展
    ----------
    * ``params_uids``  —— 来自 ``IbLambdaExpr`` 的参数节点 uid 列表，调用时按位
      绑定到本地作用域（与 ``IbUserFunction`` 同构）。
    * ``body_uid``     —— 当 fn_callable 由 ``IbLambdaExpr`` 创建时，此为 lambda
      函数体表达式 uid；``call()`` 会评估该 uid 而不是 ``node_uid``。
    * ``closure``      —— Dict[sym_uid, (name, slot)]。slot 类型由 capture_mode 决定：
      lambda 为共享 ``IbCell``，snapshot 为深克隆后的 IbObject 种子。
    """

    def __init__(
        self,
        node_uid: str,
        ib_class: IbClass,
        capture_mode: str = "lambda",
        execution_context: Optional[Any] = None,
        params_uids: Optional[List[str]] = None,
        body_uid: Optional[str] = None,
        closure: Optional[Dict[str, Any]] = None,
        param_types: Optional[List[str]] = None,
        return_type: Optional[str] = None,
    ):
        super().__init__(
            ib_class,
            payload=node_uid,
            meta={
                "capture_mode": capture_mode,
                "params_uids": list(params_uids) if params_uids else [],
                "body_uid": body_uid,
                "closure": dict(closure) if closure else {},
            },
        )
        self.node_uid = node_uid
        self.capture_mode = capture_mode
        self._execution_context = execution_context
        # parametric/closure 字段，无参/无闭包路径下默认 None/空。
        self.params_uids: List[str] = list(params_uids) if params_uids else []
        self.body_uid: Optional[str] = body_uid
        self.closure: Dict[str, Any] = dict(closure) if closure else {}
        # 内省签名：编译期 node_to_type 捕获，JSON 安全纯字符串。
        self.param_types: List[str] = list(param_types) if param_types else []
        self.return_type: Optional[str] = return_type

    def get_return_type(self) -> str:
        """返回类型查询：规范类型名；未捕获具体类型时回退 'auto'。"""
        return self.return_type or "auto"

    def signature_name(self) -> str:
        """含签名的类型名形态：'fn_callable[()->int]' / 'fn_callable[(int,str)->bool]'。

        返回类型非具体（auto/any）时退化为裸 'fn_callable'，与类型 spec 的命名
        约定（create_fn_callable 对 auto 省略泛型实参）一致。
        """
        rt = self.get_return_type()
        if rt in ("auto", "any"):
            return self.ib_class.name
        params = ",".join(self.param_types)
        return f"{self.ib_class.name}[({params})->{rt}]"

    def call(self, receiver: IbObject, args: List[IbObject]) -> IbObject:
        """
        调用 lambda / snapshot：重新执行被延迟的 AST 节点。

        **收敛**：本方法为宿主侧薄包装——委托 CPS 权威路径
        ``_vm_call_fn_callable`` + ``_drive_generator``（TaskScheduler 驱动
        ``_drive_loop_gen``），不再重复绑定闭包/实参逻辑（消双写）。VM 主路径
        本就经 ``_vm_call_fn_callable`` 执行本对象；本方法仅作宿主/反序列化同步后备。
        """
        ec = get_current_execution_context() or self._execution_context
        if ec is None:
            raise RuntimeError(
                f"IbFnCallable '{self.node_uid}': no execution_context available "
                "(neither call-site ContextVar nor definition-time field). "
                "Ensure this callable is invoked from within an active Interpreter."
            )

        vm = ec.vm_executor
        if vm is None:
            raise RuntimeError(
                f"IbFnCallable '{self.node_uid}': vm_executor not available. "
                "Ensure Interpreter.execute_module() has been called first."
            )

        from core.runtime.vm.handlers._shared import _vm_call_fn_callable
        from core.runtime.coordinator import _drive_generator

        gen = _vm_call_fn_callable(vm, self, args)
        return _drive_generator(vm, gen)

    def to_native(self, memo: Optional[Dict[int, Any]] = None) -> Any:
        # fn_callable 不在执行外暴露值——未执行时显式抛错。
        raise RuntimeError(
            f"IbFnCallable '{self.node_uid}' has not been executed; "
            f"call .call(receiver, args) first before to_native()."
        )

    def __to_prompt__(self) -> str:
        return f"<FnCallable {self.node_uid}>"

    def receive(self, message: str, args: List[IbObject]) -> IbObject:
        """FnCallable 消息分派：内部元数据消息 → 协议处理器 → 未求值 fail-fast。"""
        if message in _INTERNAL_MESSAGES:
            return _INTERNAL_DISPATCH[message](self)

        # 协议处理器（__call__ 执行 / __getattr__ 基类三段式等）
        if message in self._protocol_message_names():
            handler = getattr(self, f"_dispatch_{message.strip('_')}", None)
            if handler is not None:
                result = handler(message, args)
                if result is not None:
                    return result

        raise RuntimeError(f"FnCallable '{self.node_uid}' is not yet evaluated. Cannot process message '{message}'.")

    def _dispatch_call(self, message: str, args: List[IbObject]) -> IbObject:
        """``__call__`` 协议：执行捕获的表达式（原 receive __call__ 分支语义）。"""
        return self.call(self.ib_class.registry.get_none(), args)

    def _dispatch_to_prompt(self, message: str, args: List[IbObject]) -> IbObject:
        """``__to_prompt__`` 协议：FnCallable 呈现为可读描述。"""
        return self.ib_class.registry.box(str(self))

    def __repr__(self):
        mode = self.capture_mode or "immediate"
        return f"<FnCallable({mode}) {self.node_uid}>"


def bind_behavior_closure(behavior: "IbBehavior", rt_context: Any) -> None:
    """在子作用域中安装行为闭包（lambda 共享 cell / snapshot 深克隆种子）。

    与单次调用路径同构：snapshot 每次深克隆种子保证无状态可重入；
    lambda 通过 IbCell 读最新值。``rt_context`` 必须是已 enter_scope 的当前作用域。
    """
    is_snapshot = behavior.capture_mode == "snapshot"
    ec = behavior._execution_context
    for sym_uid, (name, slot) in behavior.closure.items():
        # declared_type 与单次调用路径同构解析（统一 Optional 值模型：行为
        # 闭包捕获的 Optional 变量保持包装语义）。resolve 经 execution_context。
        declared_type = (
            ec.resolve_type_from_symbol(sym_uid) if ec is not None and sym_uid else None
        )
        if is_snapshot:
            fresh = try_deep_clone(slot) if slot is not None else None
            value = fresh if fresh is not None else slot
            if value is not None:
                rt_context.define_variable(name, value, uid=sym_uid, declared_type=declared_type)
        elif isinstance(slot, IbCell):
            if not slot.is_empty():
                rt_context.define_variable(name, slot.get(), uid=sym_uid, declared_type=declared_type)
        else:
            rt_context.define_variable(name, slot, uid=sym_uid, declared_type=declared_type)


def bind_behavior_call_args(behavior: "IbBehavior", args: List[Any], ec: Any, rt_context: Any) -> None:
    """在子作用域中按行为参数 UID 绑定实参（与单次调用路径同构）。"""
    for i, arg_uid in enumerate(behavior.params_uids):
        arg_data = ec.get_node_data(arg_uid)
        actual_arg_uid = arg_uid
        actual_arg_data = arg_data
        if arg_data and arg_data.get("_type") == "IbTypeAnnotatedExpr":
            actual_arg_uid = arg_data.get("target")
            actual_arg_data = ec.get_node_data(actual_arg_uid)
        arg_name = (actual_arg_data or {}).get("arg")
        if arg_name and i < len(args):
            sym_uid = ec.get_side_table("node_to_symbol", actual_arg_uid)
            param_declared = (
                ec.resolve_type_from_symbol(sym_uid) if sym_uid else None
            )
            rt_context.define_variable(arg_name, args[i], uid=sym_uid, declared_type=param_declared)


@register_ib_type("behavior")
class IbBehavior(IbValue):
    """
    LLM 行为可调用实例对象。

    公理化设计原则
    --------------
    IbBehavior 是 fn_callable 家族中针对 LLM 行为表达式的特化。
    继承链：behavior → fn_callable → callable → Object

    * 行为对象在创建时捕获 ``execution_context`` 引用（与 IbUserFunction 同构）。
    * ``call()`` 通过 ``ib_class.registry.get_llm_executor().invoke_behavior()``
      完成自主执行，不再依赖外部的 ``_execute_behavior`` 路由。
    * BaseHandler 中的 ``_execute_behavior`` 方法已删除。
    * 与 IbFnCallable 的区别：IbBehavior 执行的是 LLM 调用（需要意图栈），
      IbFnCallable 执行的是普通表达式（纯 AST 重访）。
    """
    def __init__(
        self,
        node_uid: str,
        captured_intents: Optional[Any],  # Optional[IbIntentContext]
        ib_class: IbClass,
        expected_type: Optional[str] = None,
        capture_mode: Optional[str] = None,
        execution_context: Optional[Any] = None,
        params_uids: Optional[List[str]] = None,
        closure: Optional[Dict[str, Any]] = None,
        param_types: Optional[List[str]] = None,
        return_type: Optional[str] = None,
    ):
        """
        IbBehavior 是纯粹的数据描述符与自主执行单元。
        capture_mode: 'lambda' | 'snapshot' | None (immediate)
        execution_context: 创建时的执行上下文引用（供 call() 使用）。
        captured_intents: None（lambda 模式）或 IbIntentContext fork 值快照（snapshot
            模式 / dispatch_eager）。不再支持 IntentNode 链表 / list。

        参数化调用支持（与 IbFnCallable 同构）：
            * ``params_uids`` —— ``IbLambdaExpr`` 提供的参数节点 uid 列表；
              当 ``IbLambdaExpr`` 的 body 是 ``IbBehaviorExpr`` 时，``call()``
              在子作用域中绑定参数后再调用 LLM 执行器。注意：``node_uid``
              本身已指向 ``IbBehaviorExpr``（即 lambda 的 body），无需另设
              字段——执行器解析 prompt 时直接使用 ``self.node``。
            * ``closure``     —— Dict[str, IbCell]，snapshot 模式下持有自由
              变量值快照；调用时安装到本地作用域，使 prompt 中的变量引用
              读取定义时的值。
        """
        super().__init__(
            ib_class,
            payload=node_uid,
            meta={
                "captured_intents": captured_intents,
                "expected_type": expected_type,
                "capture_mode": capture_mode,
                "params_uids": list(params_uids) if params_uids else [],
                "closure": dict(closure) if closure else {},
            },
        )
        self.node = node_uid
        self.captured_intents = captured_intents
        self.expected_type = expected_type
        self.capture_mode = capture_mode
        self._execution_context = execution_context
        self._cache: Optional[IbObject] = None
        # 参数化调用支持
        self.params_uids: List[str] = list(params_uids) if params_uids else []
        self.closure: Dict[str, Any] = dict(closure) if closure else {}
        # 内省签名：编译期 node_to_type 捕获，JSON 安全纯字符串。
        self.param_types: List[str] = list(param_types) if param_types else []
        self.return_type: Optional[str] = return_type

    def get_return_type(self) -> str:
        """返回类型查询：规范类型名；未捕获具体类型时回退 'auto'。"""
        return self.return_type or "auto"

    def signature_name(self) -> str:
        """含签名的类型名形态：'behavior[()->str]' / 'behavior[(int,str)->bool]'。

        返回类型非具体（auto/any）时退化为裸 'behavior'，与类型 spec 的命名
        约定（create_behavior 对 auto 省略泛型实参）一致。
        """
        rt = self.get_return_type()
        if rt in ("auto", "any"):
            return self.ib_class.name
        params = ",".join(self.param_types)
        return f"{self.ib_class.name}[({params})->{rt}]"

    def value(self):
        if self._cache: return self._cache.to_native()
        raise RuntimeError("Behavior is not executed. Please use LLMExecutor to run it.")

    def to_native(self) -> Any:
        if self._cache: return self._cache.to_native()
        # 未执行时显式抛错（避免调用方获得类型混淆的 IBCI 运行时对象）。
        raise RuntimeError(
            f"IbBehavior '{self.node}' has not been executed; "
            f"call via LLM executor (or .call(receiver, args)) first before to_native()."
        )

    def __to_prompt__(self) -> str:
        if self._cache: return self._cache.__to_prompt__()
        return f"<Behavior {self.node}>"

    def __repr__(self):
        return f"<Behavior {self.node}>"

    def serialize_for_debug(self) -> Dict[str, Any]:
        # captured_intents 现在是 None 或 IbIntentContext（非可迭代）
        ci = self.captured_intents
        if ci is None:
            ci_repr: List[str] = []
        elif hasattr(ci, "get_active_intents"):
            ci_repr = [str(i) for i in ci.get_active_intents()]
        else:
            ci_repr = [str(ci)]
        return {
            "type": self.ib_class.name,
            "node_uid": self.node,
            "captured_intents": ci_repr,
            "expected_type": self.expected_type
        }

    def call(self, receiver: IbObject, args: List[IbObject]) -> IbObject:
        """
        公理化自主调用：委托 CPS 权威路径执行行为体。

        **收敛**：本方法为宿主侧薄包装——委托 ``_vm_invoke_behavior`` +
        ``_drive_generator``（TaskScheduler 驱动 ``_drive_loop_gen``），不再重复
        子作用域/闭包/实参绑定逻辑（消双写）。VM 主路径（leaf.py）本就经
        ``_vm_invoke_behavior`` 执行本对象；本方法仅作 vtable receive('__call__')
        后备与宿主/反序列化同步调用。
        """
        ec = get_current_execution_context() or self._execution_context
        if ec is None:
            raise RuntimeError(
                f"IbBehavior '{self.node}': no execution_context available "
                "(neither call-site ContextVar nor definition-time field). "
                "Ensure this behavior is invoked from within an active Interpreter."
            )

        vm = ec.vm_executor
        if vm is None:
            raise RuntimeError(
                f"IbBehavior '{self.node}': vm_executor not available. "
                "Ensure Interpreter.execute_module() has been called first."
            )

        from core.runtime.vm.handlers._shared import _vm_invoke_behavior
        from core.runtime.coordinator import _drive_generator

        gen = _vm_invoke_behavior(vm, self, args)
        return _drive_generator(vm, gen)

    def receive(self, message: str, args: List[IbObject]) -> IbObject:
        """
        行为对象的消息处理。
        允许查询元数据，仅在尝试"执行行为本身"且无上下文时才抛出异常。
        """
        # 签名查询反映行为声明形态，与执行状态无关，先于 _cache 委派处理。
        if message in _INTERNAL_MESSAGES:
            return _INTERNAL_DISPATCH[message](self)

        # 已执行缓存：委派缓存对象（原 _cache 分支语义）
        if self._cache:
            return self._cache.receive(message, args)

        # 协议处理器（__getattr__ 基类三段式等；__call__ 显式关闭默认处理器）
        if message in self._protocol_message_names():
            handler = getattr(self, f"_dispatch_{message.strip('_')}", None)
            if handler is not None:
                result = handler(message, args)
                if result is not None:
                    return result

        raise RuntimeError(f"Behavior '{self.node}' is not executed. Cannot process message '{message}'.")

    def _dispatch_call(self, message: str, args: List[IbObject]):
        """无行为对象专属调用语义（执行经 call()/缓存路径）：关闭基类默认处理器。"""
        return None
