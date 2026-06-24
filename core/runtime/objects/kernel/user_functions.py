from typing import Optional, Dict, Any, List, TYPE_CHECKING

from core.kernel.issue import InterpreterError
from core.base.diagnostics.debugger import CoreModule, DebugLevel, core_debugger
from core.base.diagnostics.codes import RUN_CALL_ERROR
from core.base.source_atomic import Location
from core.kernel.intent_logic import IntentRole
from core.kernel.spec import IbSpec
from core.runtime.frame import get_current_frame as _get_frame

from .base import IbObject
from .functions import IbFunction, IbSuperProxy
from ._helpers import _is_intent_context_param, _should_activate_intent_context_arg

if TYPE_CHECKING:
    from core.runtime.interfaces import IExecutionContext


class IbUserFunction(IbFunction):
    """
    用户定义的 IBC 函数。
    """
    def __init__(self, node_uid: str, context: 'IExecutionContext', ib_class: Optional['IbClass'] = None, spec: Optional[IbSpec] = None, module_name: Optional[str] = None, owner_class: Optional['IbClass'] = None):
        super().__init__(ib_class or context.registry.get_class("callable"))
        self.node_uid = node_uid
        self.context = context
        self._spec = spec
        self.module_name = module_name or context.current_module_name
        # 定义该方法的 IbClass（方法归属类）。用于 super() 支持。
        # 对于顶层函数，此字段为 None（不在类内）。
        self.owner_class: Optional['IbClass'] = owner_class
        # nonlocal 闭包：{sym_uid: (name, IbCell)} — 由 vm_handle_IbFunctionDef 设置
        self.closure: Optional[Dict[str, Any]] = None

    @property
    def spec(self) -> Optional[IbSpec]:
        return self._spec if self._spec is not None else self.ib_class.spec

    def call(self, receiver: IbObject, args: List[IbObject]) -> IbObject:
        """执行用户定义的函数"""
        # 切换到函数定义所在的模块上下文
        from core.runtime.objects.builtins import IbFnCallable, IbBehavior
        _frame = _get_frame()
        rt_context = _frame if _frame is not None else self.context.runtime_context
        old_module = self.context.current_module_name
        old_scope = rt_context.current_scope

        # --- 意图栈作用域隔離（拷贝传递语义）---
        # 每次函数调用 fork 调用者的意图上下文，函数内的 @+/@- 不泄漏给调用者。
        # 若需在函数体内屏蔽继承自调用者的意图，请显式调用：
        #   intent_context.clear_inherited()  — 清空继承来的持久意图栈
        #   intent_context.use(ctx)           — 以自定义上下文替换当前作用域的意图上下文
        old_intent_ctx = rt_context._intent_ctx
        # 函数调用进入时，子帧获得一个匿名活跃指针（共享 fork 后 _ctx 引用）。
        # 子帧默认未选择命名意图策略；若参数被标注为 ``intent_context`` 类型，
        # 后续参数自动绑定阶段（``use_intent_context``）会覆盖该匿名指针。
        old_active_ibobj = rt_context.get_active_intent_ibobj()
        child_ctx = old_intent_ctx.fork()
        rt_context._intent_ctx = child_ctx
        intent_context_class = self.context.registry.get_class("intent_context")
        if intent_context_class is not None:
            rt_context._set_active_intent_ibobj_for_current_ctx(intent_context_class)
        else:
            rt_context.set_active_intent_ibobj(None)

        if self.module_name and self.module_name != old_module:
            self.context.current_module_name = self.module_name
            # 获取目标模块的作用域
            try:
                mod_inst = self.context.module_manager.import_module(self.module_name, self.context)
                rt_context.current_scope = mod_inst.scope
            except Exception as e:
                core_debugger.trace(
                    CoreModule.INTERPRETER, DebugLevel.BASIC,
                    f"Failed to import module '{self.module_name}' for user function call: {e}"
                )
                raise InterpreterError(
                    f"Failed to import module '{self.module_name}' for function call: {e}",
                    error_code=RUN_CALL_ERROR
                ) from e

        try:
            node_data = self.context.get_node_data(self.node_uid)
            params_uids = node_data.get("args", [])

            rt_context.enter_scope()

            # 绑定 nonlocal 闭包变量（Cell 共享引用）
            if self.closure:
                from core.runtime.objects.cell import IbCell
                for sym_uid, (var_name, cell) in self.closure.items():
                    if isinstance(cell, IbCell):
                        # 即使 Cell 为空也需要绑定（内层函数可能先赋值再读取）
                        initial_value = cell.get() if not cell.is_empty() else self.ib_class.registry.get_none()
                        rt_context.define_variable(var_name, initial_value, uid=sym_uid)
                        # 将 Cell 引用附加到新创建的符号上，使赋值时能同步更新
                        new_sym = rt_context.current_scope.get_symbol_by_uid(sym_uid)
                        if new_sym is not None:
                            new_sym.cell = cell

            loc_data = self.context.get_side_table("node_to_loc", self.node_uid)
            loc = None
            if loc_data:
                loc = Location(
                    file_path=loc_data.get("file_path"),
                    line=loc_data.get("line", 0),
                    column=loc_data.get("column", 0)
                )

            self.context.push_stack(
                name=node_data.get("name", "anonymous"),
                location=loc,
                is_user_function=True
            )

            ib_none = self.ib_class.registry.get_none()
            if receiver and receiver is not ib_none:
                # 查找 self 符号的 UID（语义分析阶段将函数定义节点映射到 self 符号）
                self_sym = self.context.get_side_table("node_to_symbol", self.node_uid)
                self_uid = self_sym if isinstance(self_sym, str) else (self_sym.uid if self_sym else None)
                rt_context.define_variable("self", receiver, uid=self_uid)

                # super() 支持：若该函数有归属类（owner_class）且归属类有父类，
                # 则在方法作用域内注入 super 代理对象。
                # super 使用固定 UID "builtin:super" 以避免符号查找冲突。
                if self.owner_class and self.owner_class.parent:
                    super_proxy = IbSuperProxy(receiver, self.owner_class.parent)
                    rt_context.define_variable("super", super_proxy, uid="builtin:super")

            for i, arg_uid in enumerate(params_uids):
                arg_data = self.context.get_node_data(arg_uid)
                is_intent_ctx_param = _is_intent_context_param(self.context, arg_uid, arg_data)
                actual_arg_uid = arg_uid
                actual_arg_data = arg_data
                if arg_data.get("_type") == "IbTypeAnnotatedExpr":
                    actual_arg_uid = arg_data.get("target")
                    actual_arg_data = self.context.get_node_data(actual_arg_uid)

                arg_name = actual_arg_data.get("arg")
                if i < len(args):
                    arg_value = args[i]
                    sym_uid = self.context.get_side_table("node_to_symbol", actual_arg_uid)
                    rt_context.define_variable(arg_name, arg_value, uid=sym_uid)
                    if _should_activate_intent_context_arg(arg_value, is_intent_ctx_param):
                        rt_context.use_intent_context(arg_value)

            body = node_data.get("body", [])
            # Drive function body execution via VMExecutor (CPS main path).
            # run_body() propagates top-level control signals via UnhandledSignal.
            # Signals are consumed by except _CSE below; BREAK/CONTINUE are re-thrown.
            from core.runtime.shared.signals import (
                ControlSignal as _CS, UnhandledSignal as _CSE,
            )
            vm = self.context.vm_executor
            if vm is None:
                raise RuntimeError(
                    "IbUserFunction.call(): vm_executor not available on ExecutionContext. "
                    "Ensure Interpreter.execute_module() has been called before invoking user functions."
                )
            vm.run_body(body)

            return ib_none
        except _CSE as e:
            # 捕获 UnhandledSignal，按信号类型处理。
            if e.signal.kind is _CS.RETURN:
                return e.signal.value
            raise  # BREAK/CONTINUE 不应到达函数帧，透传至调用者
        finally:
            self.context.pop_stack()
            rt_context.exit_scope()
            # 恢复调用者的意图上下文和模块上下文
            rt_context._intent_ctx = old_intent_ctx
            # 恢复调用者的活跃实例指针。
            rt_context.set_active_intent_ibobj(old_active_ibobj)
            self.context.current_module_name = old_module
            rt_context.current_scope = old_scope

    def __repr__(self):
        node_data = self.context.get_node_data(self.node_uid)
        name = node_data.get("name", "unknown")
        return f"<Function '{name}'>"

class IbLLMFunction(IbFunction):
    """
    用户定义的 LLM 函数。

    公理化设计原则
    --------------
    IbLLMFunction 与 IbBehavior 同构：不再在构造时持有 llm_executor 引用。
    call() 通过 ib_class.registry.get_llm_executor().invoke_llm_function() 自主执行。
    """
    def __init__(self, node_uid: str, context: 'IExecutionContext', spec: Optional[IbSpec] = None, module_name: Optional[str] = None):
        super().__init__(context.registry.get_class("callable"))
        self.node_uid = node_uid
        self.context = context
        self._spec = spec
        self.module_name = module_name or context.current_module_name
        # 暂存由 call() 解析的呼叫级意图，供 invoke_llm_function 消费
        self._pending_call_intent: Optional[Any] = None

    @property
    def spec(self) -> Optional[IbSpec]:
        return self._spec if self._spec is not None else self.ib_class.spec

    def call(self, receiver: IbObject, args: List[IbObject]) -> IbObject:
        """
        执行 LLM 函数：负责作用域管理和参数绑定，然后通过 KernelRegistry 分发给执行器。

        与 IbBehavior.call() 同构：通过 registry.get_llm_executor() 获取执行器，
        不再持有 llm_executor 直接引用。
        """
        executor = self.ib_class.registry.get_llm_executor()
        if executor is None:
            raise RuntimeError(
                f"IbLLMFunction '{self.node_uid}': LLM executor not registered in KernelRegistry. "
                "Ensure engine._prepare_interpreter() has completed before invoking an LLM function."
            )

        # 切换到函数定义所在的模块上下文
        rt_context = self.context.runtime_context
        old_module = self.context.current_module_name
        old_scope = rt_context.current_scope

        # --- 意图栈作用域隔离（拷贝传递语义）---
        # 与 IbUserFunction.call() 对称：fork 调用者意图上下文，函数内操作不泄漏。
        # 若需在函数体内屏蔽继承的意图，请在函数体内显式调用 intent_context.clear_inherited()。
        old_intent_ctx = rt_context._intent_ctx
        # 与 IbUserFunction.call 对称，进入 LLM 函数时为子帧建立匿名活跃指针。
        old_active_ibobj = rt_context.get_active_intent_ibobj()
        child_ctx = old_intent_ctx.fork()
        rt_context._intent_ctx = child_ctx
        intent_context_class = self.context.registry.get_class("intent_context")
        if intent_context_class is not None:
            rt_context._set_active_intent_ibobj_for_current_ctx(intent_context_class)
        else:
            rt_context.set_active_intent_ibobj(None)

        if self.module_name and self.module_name != old_module:
            self.context.current_module_name = self.module_name
            # 获取目标模块的作用域
            try:
                mod_inst = self.context.module_manager.import_module(self.module_name, self.context)
                rt_context.current_scope = mod_inst.scope
            except Exception as e:
                core_debugger.trace(
                    CoreModule.INTERPRETER, DebugLevel.BASIC,
                    f"Failed to import module '{self.module_name}' for user function call: {e}"
                )
                raise InterpreterError(
                    f"Failed to import module '{self.module_name}' for function call: {e}",
                    error_code=RUN_CALL_ERROR
                ) from e

        try:
            node_data = self.context.get_node_data(self.node_uid)
            rt_context.enter_scope()

            loc_data = self.context.get_side_table("node_to_loc", self.node_uid)
            loc = None
            if loc_data:
                loc = Location(
                    file_path=loc_data.get("file_path"),
                    line=loc_data.get("line", 0),
                    column=loc_data.get("column", 0)
                )

            self.context.push_stack(
                name=node_data.get("name", "llm_anonymous"),
                location=loc,
                is_user_function=True
            )

            params_uids = node_data.get("args", [])

            for i, arg_uid in enumerate(params_uids):
                arg_data = self.context.get_node_data(arg_uid)
                is_intent_ctx_param = _is_intent_context_param(self.context, arg_uid, arg_data)
                # 处理类型标注包装
                actual_arg_uid = arg_uid
                actual_arg_data = arg_data
                if arg_data.get("_type") == "IbTypeAnnotatedExpr":
                    actual_arg_uid = arg_data.get("target")
                    actual_arg_data = self.context.get_node_data(actual_arg_uid)

                arg_name = actual_arg_data.get("arg")
                if i < len(args):
                    arg_value = args[i]
                    sym_uid = self.context.get_side_table("node_to_symbol", actual_arg_uid)
                    rt_context.define_variable(arg_name, arg_value, uid=sym_uid)
                    if _should_activate_intent_context_arg(arg_value, is_intent_ctx_param):
                        rt_context.use_intent_context(arg_value)

            # 解析呼叫级意图（函数头上的意图），暂存供 invoke_llm_function 消费
            intent_uid = node_data.get("intent")
            self._pending_call_intent = None
            if intent_uid:
                intent_data = self.context.get_node_data(intent_uid)
                self._pending_call_intent = self.context.factory.create_intent_from_node(
                    intent_uid,
                    intent_data,
                    role=IntentRole.SMEAR
                )

            # 公理化调用：通过 KernelRegistry 获取执行器，不再直接持有
            return executor.invoke_llm_function(self, self.context)
        finally:
            self._pending_call_intent = None
            self.context.pop_stack()
            rt_context.exit_scope()
            # 恢复调用者的意图上下文和模块上下文
            rt_context._intent_ctx = old_intent_ctx
            # 恢复调用者的活跃实例指针。
            rt_context.set_active_intent_ibobj(old_active_ibobj)
            self.context.current_module_name = old_module
            rt_context.current_scope = old_scope


    def __repr__(self):
        node_data = self.context.get_node_data(self.node_uid)
        name = node_data.get("name", "unknown")
        return f"<LLMFunction '{name}'>"
