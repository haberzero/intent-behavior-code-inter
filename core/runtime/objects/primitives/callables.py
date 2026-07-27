from typing import Any, Dict, List, Optional
from ..kernel import IbObject, IbValue, IbClass
from core.runtime.frame import get_current_execution_context
from core.runtime.objects.cell import IbCell
from core.runtime.objects.deep_clone import try_deep_clone
from ..ib_type_mapping import register_ib_type

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

    def call(self, receiver: IbObject, args: List[IbObject]) -> IbObject:
        """
        调用 lambda / snapshot：重新执行被延迟的 AST 节点。

        - lambda 模式：每次调用都重新求值（使用当前上下文，自由变量共享 IbCell）。
        - snapshot 模式：每次调用都重新求值，闭包种子按次再克隆——无缓存，可重入。

        当存在参数（``params_uids`` 非空）或闭包（``closure`` 非空）时，进入
        独立的子作用域并在其中绑定参数与闭包；调用结束后自动退出。

        EC 解析优先级：调用现场 ContextVar > 定义时刻字段 ``_execution_context``。
        VM CPS 主路径不走本方法；本方法仅为同步后备（外部 host / 反序列化后调用）。
        """
        # 调用现场 EC 优先于定义时刻快照
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

        rt_context = ec.runtime_context
        pushed_scope = False

        try:
            # 1) 若有参或有闭包，进入子作用域以承载 params 与 closure cells。
            #    lambda：通过共享 IbCell 读取调用时最新值；
            #    snapshot：对种子再次深克隆，作为本次调用的私有副本。
            needs_subscope = bool(self.params_uids) or bool(self.closure)
            if needs_subscope:
                rt_context.enter_scope()
                pushed_scope = True

                is_snapshot = self.capture_mode == "snapshot"
                for sym_uid, (name, slot) in self.closure.items():
                    if is_snapshot:
                        fresh = try_deep_clone(slot) if slot is not None else None
                        value = fresh if fresh is not None else slot
                        if value is not None:
                            rt_context.define_variable(name, value, uid=sym_uid)
                    elif isinstance(slot, IbCell):
                        if not slot.is_empty():
                            rt_context.define_variable(name, slot.get(), uid=sym_uid)
                    else:
                        rt_context.define_variable(name, slot, uid=sym_uid)

                # 绑定形参：与 IbUserFunction.call 同构地处理 IbTypeAnnotatedExpr 包装。
                for i, arg_uid in enumerate(self.params_uids):
                    arg_data = ec.get_node_data(arg_uid)
                    actual_arg_uid = arg_uid
                    actual_arg_data = arg_data
                    if arg_data and arg_data.get("_type") == "IbTypeAnnotatedExpr":
                        actual_arg_uid = arg_data.get("target")
                        actual_arg_data = ec.get_node_data(actual_arg_uid)
                    arg_name = (actual_arg_data or {}).get("arg")
                    if arg_name and i < len(args):
                        sym_uid = ec.get_side_table("node_to_symbol", actual_arg_uid)
                        rt_context.define_variable(arg_name, args[i], uid=sym_uid)

            # 2) 评估目标节点：参数化路径走 body_uid，否则走 node_uid（防御性回退）。
            target_uid = self.body_uid if self.body_uid else self.node_uid
            result = vm.run(target_uid)
        finally:
            if pushed_scope:
                rt_context.exit_scope()

        return result

    def to_native(self, memo: Optional[Dict[int, Any]] = None) -> Any:
        # fn_callable 不在执行外暴露值——未执行时显式抛错。
        raise RuntimeError(
            f"IbFnCallable '{self.node_uid}' has not been executed; "
            f"call .call(receiver, args) first before to_native()."
        )

    def __to_prompt__(self) -> str:
        return f"<FnCallable {self.node_uid}>"

    def receive(self, message: str, args: List[IbObject]) -> IbObject:
        if message in ("__get_metadata__", "__to_prompt__", "node_uid"):
            return self.ib_class.registry.box(str(self))

        if message == "__call__":
            return self.call(self.ib_class.registry.get_none(), args)

        raise RuntimeError(f"FnCallable '{self.node_uid}' is not yet evaluated. Cannot process message '{message}'.")

    def __repr__(self):
        mode = self.capture_mode or "immediate"
        return f"<FnCallable({mode}) {self.node_uid}>"


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
        call_intent: Optional[Any] = None,
        capture_mode: Optional[str] = None,
        execution_context: Optional[Any] = None,
        params_uids: Optional[List[str]] = None,
        closure: Optional[Dict[str, Any]] = None,
    ):
        """
        IbBehavior 是纯粹的数据描述符与自主执行单元。
        call_intent 用于保存 @! 排他意图，使延迟执行时意图不丢失。
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
                "call_intent": call_intent,
                "capture_mode": capture_mode,
                "params_uids": list(params_uids) if params_uids else [],
                "closure": dict(closure) if closure else {},
            },
        )
        self.node = node_uid
        self.captured_intents = captured_intents
        self.expected_type = expected_type
        self.call_intent = call_intent
        self.capture_mode = capture_mode
        self._execution_context = execution_context
        self._cache: Optional[IbObject] = None
        # 参数化调用支持
        self.params_uids: List[str] = list(params_uids) if params_uids else []
        self.closure: Dict[str, Any] = dict(closure) if closure else {}

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
        公理化自主调用：通过内核 LLM 执行器完成行为执行。

        执行流程：
        1. 从 KernelRegistry 获取 IILLMExecutor（注入点：engine._prepare_interpreter）。
        2. 调用 executor.invoke_behavior(self, execution_context)：
           - 使用 captured_intents（snapshot 模式）或当前意图栈（lambda 模式）。
           - 按 expected_type 解析 LLM 返回值。
           - 将 LLMResult 写入 RuntimeContext 供 llmexcept 使用。
        3. 返回解析后的 IbObject。

        参数化路径：当 ``params_uids`` / ``body_uid`` / ``closure`` 任一非空时，
        进入临时子作用域并绑定参数与闭包 cell，再委托给 executor。executor
        在 prompt 解析阶段查找 ``$name`` 时即可读取到已绑定的值。

        EC 解析优先级：调用现场 ContextVar > 定义时刻字段。
        VM CPS 主路径（``_vm_invoke_behavior``）不走本方法；本方法仅为同步后备。
        """
        executor = self.ib_class.registry.get_llm_executor()
        if executor is None:
            raise RuntimeError(
                f"IbBehavior '{self.node}': LLM executor not registered in KernelRegistry. "
                "Ensure engine._prepare_interpreter() has completed before invoking a behavior."
            )

        # 调用现场 EC 优先于定义时刻字段
        ec = get_current_execution_context() or self._execution_context

        # lambda / snapshot 模式：每次调用都应是独立的 LLM 推理；先清除可能存在的
        # 上次结果缓存，避免 execute_behavior_object 早期短路返回旧值。
        # immediate 模式（capture_mode is None）保留缓存：那是值语义的"求值一次"对象。
        if self.capture_mode in ("snapshot", "lambda"):
            self._cache = None

        needs_subscope = bool(self.params_uids) or bool(self.closure)
        if not needs_subscope:
            return executor.invoke_behavior(self, ec)

        if ec is None:
            raise RuntimeError(
                f"IbBehavior '{self.node}': no execution_context available for parametric behavior "
                "(neither call-site ContextVar nor definition-time field)."
            )

        rt_context = ec.runtime_context
        rt_context.enter_scope()
        try:
            is_snapshot = self.capture_mode == "snapshot"
            for sym_uid, (name, slot) in self.closure.items():
                if is_snapshot:
                    fresh = try_deep_clone(slot) if slot is not None else None
                    value = fresh if fresh is not None else slot
                    if value is not None:
                        rt_context.define_variable(name, value, uid=sym_uid)
                elif isinstance(slot, IbCell):
                    if not slot.is_empty():
                        rt_context.define_variable(name, slot.get(), uid=sym_uid)
                else:
                    rt_context.define_variable(name, slot, uid=sym_uid)

            for i, arg_uid in enumerate(self.params_uids):
                arg_data = ec.get_node_data(arg_uid)
                actual_arg_uid = arg_uid
                actual_arg_data = arg_data
                if arg_data and arg_data.get("_type") == "IbTypeAnnotatedExpr":
                    actual_arg_uid = arg_data.get("target")
                    actual_arg_data = ec.get_node_data(actual_arg_uid)
                arg_name = (actual_arg_data or {}).get("arg")
                if arg_name and i < len(args):
                    sym_uid = ec.get_side_table("node_to_symbol", actual_arg_uid)
                    rt_context.define_variable(arg_name, args[i], uid=sym_uid)

            return executor.invoke_behavior(self, ec)
        finally:
            rt_context.exit_scope()

    def receive(self, message: str, args: List[IbObject]) -> IbObject:
        """
        行为对象的消息处理。
        允许查询元数据，仅在尝试"执行行为本身"且无上下文时才抛出异常。
        """
        if self._cache: return self._cache.receive(message, args)

        if message in ("__get_metadata__", "__to_prompt__", "node_uid"):
            return self.ib_class.registry.box(str(self))

        raise RuntimeError(f"Behavior '{self.node}' is not executed. Cannot process message '{message}'.")
