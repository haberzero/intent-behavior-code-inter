"""
core.runtime.vm.handlers._shared — 跨类别 CPS 辅助函数。

本模块由原 ``core.runtime.vm.handlers`` 纯机械拆分而来，
无任何逻辑改动；函数体逐字保留。
"""
from __future__ import annotations
from typing import Any, Mapping, Optional, List

from core.runtime.shared.signals import (
    ControlSignal,
    Signal,
)
from core.runtime.objects.kernel import (
    IbValue,
    _is_intent_context_param,
    _should_activate_intent_context_arg,
)
from core.base.source_atomic import Location
from core.runtime.exceptions import (
    ThrownException,
)
from core.runtime.objects.intent import IbIntent, IntentRole
from core.runtime.objects.cell import IbCell
from core.runtime.objects.deep_clone import try_deep_clone
from core.runtime.shared.llm_result import LLMFuture


def _vm_call_fn_callable(executor, func, args):
    """CPS 内联执行 IbFnCallable（lambda/snapshot）调用。

    将原来 ``IbFnCallable.call()`` 中的 ``ec.visit(target_uid)`` 替换为
    ``yield target_uid``，使 lambda/snapshot 体完全在 VM CPS 循环中执行。
    控制流信号（RETURN/BREAK/CONTINUE）通过 Signal 数据对象传播，不再依赖
    Python 异常。

    snapshot 语义（reentrant / stateless）：
        snapshot 在定义时把所有自由变量深克隆为只读「种子」（见
        ``vm_handle_IbLambdaExpr``）。每次调用进入子作用域时，对种子再做一次
        深克隆作为本次调用的私有副本——即便函数体内部就地修改这些变量，
        也不会污染其它调用，从而保证并发与重入安全。snapshot 不缓存结果。
    """

    rt_context = executor.runtime_context
    needs_subscope = bool(func.params_uids) or bool(func.closure)
    if needs_subscope:
        rt_context.enter_scope()
    try:
        # 绑定闭包：lambda 走共享 IbCell，snapshot 走每次调用的独立深克隆。
        is_snapshot = func.capture_mode == "snapshot"
        for sym_uid, (name, slot) in func.closure.items():
            if is_snapshot:
                # snapshot：种子已是定义时刻的深克隆，调用时再克隆一份注入子作用域，
                # 保证函数体内的就地修改不会跨调用泄漏。
                fresh = try_deep_clone(slot) if slot is not None else None
                value = fresh if fresh is not None else slot
                if value is not None:
                    rt_context.define_variable(name, value, uid=sym_uid)
            elif isinstance(slot, IbCell):
                # lambda：共享 cell，调用时 deref 读最新值
                if not slot.is_empty():
                    rt_context.define_variable(name, slot.get(), uid=sym_uid)
            else:
                rt_context.define_variable(name, slot, uid=sym_uid)

        # 绑定形参（与 IbUserFunction.call 同构：处理 IbTypeAnnotatedExpr 包装）
        for i, arg_uid in enumerate(func.params_uids):
            arg_data = executor.ec.get_node_data(arg_uid)
            actual_arg_uid = arg_uid
            actual_arg_data = arg_data
            if arg_data and arg_data.get("_type") == "IbTypeAnnotatedExpr":
                actual_arg_uid = arg_data.get("target")
                actual_arg_data = executor.ec.get_node_data(actual_arg_uid)
            arg_name = (actual_arg_data or {}).get("arg")
            if arg_name and i < len(args):
                sym_uid = executor.ec.get_side_table("node_to_symbol", actual_arg_uid)
                rt_context.define_variable(arg_name, args[i], uid=sym_uid)

        # CPS 执行函数体
        target_uid = func.body_uid if func.body_uid else func.node_uid
        result = yield target_uid

        # 处理控制流信号：RETURN → 提取值；BREAK/CONTINUE/THROW → 透传给上层
        if isinstance(result, Signal):
            if result.kind is ControlSignal.RETURN:
                result = result.value
            else:
                return result  # finally 会负责 exit_scope
    finally:
        if needs_subscope:
            rt_context.exit_scope()

    return result


def _vm_invoke_behavior(executor, behavior, args):
    """CPS-friendly counterpart of :meth:`IbBehavior.call`.

    Mirrors the bookkeeping in ``IbBehavior.call`` (scope/closure binding +
    parametric arg binding) but yields once **before** the synchronous LLM
    invocation so the VMTask running this helper is guaranteed to be on the
    frame stack at LLM execute time — giving "LLM 帧受 VM 调度管理" the
    practical snapshot / debug-visibility guarantee called for by NS-1.

    snapshot 行为体（``capture_mode == 'snapshot'``）：
        每次调用前清除 ``_cache`` 并在子作用域内对自由变量做一次额外深克隆，
        与 ``_vm_call_fn_callable`` 路径一致——snapshot 是无状态、可重入的。

    NS-3：始终使用**调用现场**的 ``executor.ec`` 作为执行机制（VM、节点池、
    runtime_context）；``behavior._execution_context`` 字段仅在跨 Interpreter
    的同步后备路径中作为兜底使用，CPS 主路径完全无视该字段。
    """

    llm_exec = behavior.ib_class.registry.get_llm_executor()
    if llm_exec is None:
        raise RuntimeError(
            f"IbBehavior '{behavior.node}': LLM executor not registered in KernelRegistry. "
            "Ensure engine._prepare_interpreter() has completed before invoking a behavior."
        )

    is_snapshot = behavior.capture_mode == "snapshot"
    is_lambda = behavior.capture_mode == "lambda"
    # lambda / snapshot 模式下严禁缓存上次结果：每次调用都应触发 LLM 推理。
    # immediate 模式（capture_mode is None）保留 _cache 短路（值语义对象）。
    if is_snapshot or is_lambda:
        behavior._cache = None

    # 调用现场 EC 优先
    ec = executor.ec
    rt_context = ec.runtime_context

    needs_subscope = bool(behavior.params_uids) or bool(behavior.closure)
    if not needs_subscope:
        # Segment evaluation is now driven via ``yield from`` inside
        # ``invoke_behavior_cps`` → the prompt-segment sub-tasks are properly
        # nested on the outer VM frame stack rather than spawning a separate
        # ``_drive_loop``. See ``_evaluate_segments_cps`` for the rationale.
        result = yield from llm_exec.invoke_behavior_cps(behavior, ec)
        return result

    rt_context.enter_scope()
    try:
        for sym_uid, (name, slot) in behavior.closure.items():
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

        for i, arg_uid in enumerate(behavior.params_uids):
            arg_data = ec.get_node_data(arg_uid)
            actual_arg_uid = arg_uid
            actual_arg_data = arg_data
            if arg_data and arg_data.get("_type") == "IbTypeAnnotatedExpr":
                actual_arg_uid = arg_data.get("target")
                actual_arg_data = ec.get_node_data(actual_arg_uid)
            arg_name = (actual_arg_data or {}).get("arg")
            if arg_name and i < len(args):
                sym_uid = ec.get_side_table(
                    "node_to_symbol", actual_arg_uid
                )
                rt_context.define_variable(arg_name, args[i], uid=sym_uid)

        yield None
        result = yield from llm_exec.invoke_behavior_cps(behavior, ec)
        return result
    finally:
        rt_context.exit_scope()


def _vm_invoke_llm_function(executor, func, receiver, args):
    """CPS-friendly counterpart of :meth:`IbLLMFunction.call`.

    Performs the same intent-context fork / module switch / scope enter /
    push_stack / argument auto-binding bookkeeping as ``IbLLMFunction.call``,
    yields once before the LLM HTTP invocation so the VMTask is on the frame
    stack at execute time, then delegates to ``executor.invoke_llm_function``.
    """
    llm_exec = func.ib_class.registry.get_llm_executor()
    if llm_exec is None:
        raise RuntimeError(
            f"IbLLMFunction '{func.node_uid}': LLM executor not registered in KernelRegistry. "
            "Ensure engine._prepare_interpreter() has completed before invoking an LLM function."
        )

    rt_context = func.context.runtime_context
    old_module = func.context.current_module_name
    old_scope = rt_context.current_scope

    old_intent_ctx = rt_context._intent_ctx
    old_active_ibobj = rt_context.get_active_intent_ibobj()
    child_ctx = old_intent_ctx.fork()
    rt_context._intent_ctx = child_ctx
    intent_context_class = func.context.registry.get_class("intent_context")
    if intent_context_class is not None:
        rt_context._set_active_intent_ibobj_for_current_ctx(intent_context_class)
    else:
        rt_context.set_active_intent_ibobj(None)

    if func.module_name and func.module_name != old_module:
        func.context.current_module_name = func.module_name
        try:
            mod_inst = func.context.module_manager.import_module(
                func.module_name, func.context
            )
            rt_context.current_scope = mod_inst.scope
        except Exception:
            pass

    try:
        node_data = func.context.get_node_data(func.node_uid)
        rt_context.enter_scope()

        loc_data = func.context.get_side_table("node_to_loc", func.node_uid)
        loc = None
        if loc_data:
            loc = Location(
                file_path=loc_data.get("file_path"),
                line=loc_data.get("line", 0),
                column=loc_data.get("column", 0),
            )

        func.context.push_stack(
            name=node_data.get("name", "llm_anonymous"),
            location=loc,
            is_user_function=True,
        )

        params_uids = node_data.get("args", [])
        for i, arg_uid in enumerate(params_uids):
            arg_data = func.context.get_node_data(arg_uid)
            is_intent_ctx_param = _is_intent_context_param(func.context, arg_uid, arg_data)
            actual_arg_uid = arg_uid
            actual_arg_data = arg_data
            if arg_data.get("_type") == "IbTypeAnnotatedExpr":
                actual_arg_uid = arg_data.get("target")
                actual_arg_data = func.context.get_node_data(actual_arg_uid)

            arg_name = actual_arg_data.get("arg")
            if i < len(args):
                arg_value = args[i]
                sym_uid = func.context.get_side_table("node_to_symbol", actual_arg_uid)
                rt_context.define_variable(arg_name, arg_value, uid=sym_uid)
                if _should_activate_intent_context_arg(arg_value, is_intent_ctx_param):
                    rt_context.use_intent_context(arg_value)

        intent_uid = node_data.get("intent")
        func._pending_call_intent = None
        if intent_uid:
            intent_data = func.context.get_node_data(intent_uid)
            func._pending_call_intent = func.context.factory.create_intent_from_node(
                intent_uid,
                intent_data,
                role=IntentRole.SMEAR,
            )

        yield None
        result = yield from llm_exec.invoke_llm_function_cps(func, func.context)
        return result
    finally:
        func._pending_call_intent = None
        func.context.pop_stack()
        rt_context.exit_scope()
        rt_context._intent_ctx = old_intent_ctx
        rt_context.set_active_intent_ibobj(old_active_ibobj)
        func.context.current_module_name = old_module
        rt_context.current_scope = old_scope


def build_one_shot_intent_from_annotation(
    executor, stmt_data: Mapping[str, Any]
) -> Optional[IbIntent]:
    """从 ``IbIntentAnnotation`` 节点数据构建一次性意图对象。"""
    intent_info_uid = stmt_data.get("intent")
    if not intent_info_uid:
        return None
    intent_data = executor.ec.get_node_data(intent_info_uid)
    if not intent_data:
        return None
    return executor.ec.factory.create_intent_from_node(
        intent_info_uid, intent_data, role=IntentRole.SMEAR
    )


def _vm_execute_stmt_sequence(executor, stmt_uids: List[str]):
    """
    统一执行语句序列，并实现 ``@`` / ``@!`` 的"下一条语句绑定"生命周期。

    语义：
    - 读取到 ``IbIntentAnnotation`` 时，不立即执行节点；仅记录为 pending one-shot。
    - 下一条真实语句开始前安装该 one-shot；语句结束后（无论是否出现 LLM 调用）清理残留。
    - 语句返回 ``Signal`` 时立即透传给调用方。
    """
    last_result = executor.registry.get_none()
    pending_one_shot: Optional[IbIntent] = None

    for stmt_uid in stmt_uids or ():
        node_data = executor.ec.get_node_data(stmt_uid) if stmt_uid else None
        if node_data and node_data.get("_type") == "IbIntentAnnotation":
            pending_one_shot = build_one_shot_intent_from_annotation(executor, node_data)
            continue

        if pending_one_shot is not None:
            executor.runtime_context.activate_statement_one_shot_intent(pending_one_shot)

        try:
            last_result = yield stmt_uid
        finally:
            if pending_one_shot is not None:
                executor.runtime_context.cleanup_statement_one_shot_intent(pending_one_shot)
                pending_one_shot = None

        if isinstance(last_result, Signal):
            return last_result

    return last_result


def _raise_if_uncertain_condition(executor, last):
    """Raise LLMParseError if LLM condition result is uncertain (shared by if/while/for)."""
    if last and not last.is_certain:
        error = executor.registry.make_llm_parse_error(
            getattr(last, "retry_hint", None) or "LLM condition output could not be parsed",
            raw_response=getattr(last, "raw_response", "") or "",
            type_name="bool",
        )
        raise ThrownException(error)


def _is_simple_name_target(executor, target_uid: str) -> bool:
    """判断赋值目标是否为简单 ``IbName`` 或 ``IbTypeAnnotatedExpr(IbName)``。"""
    target_data = executor.ec.get_node_data(target_uid)
    if not target_data:
        return False
    t = target_data.get("_type")
    if t == "IbName":
        return True
    if t == "IbTypeAnnotatedExpr":
        inner = target_data.get("target")
        return _is_simple_name_target(executor, inner) if inner else False
    return False


def _assign_future_to_name_target(executor, target_uid: str, future: LLMFuture) -> None:
    """把 ``LLMFuture`` 占位符直接写入目标变量符号绑定，跳过类型/值校验。

    与 ``StmtHandler._assign_to_target`` 中 ``IbName`` 分支语义一致，
    但写入的值是 ``LLMFuture``（非 ``IbObject``）。读取点（``vm_handle_IbName``）
    会在第一次访问时阻塞 resolve 并写回真实 ``IbObject``。

    改用 ``scope.define_raw()`` 接口写入新符号，不再直接操作
    ``scope._symbols`` / ``scope._uid_to_symbol`` 私有字段。已存在符号
    的覆写（``sym.value = future``）仍通过 ``RuntimeSymbolImpl`` 公开属性进行，
    这是有意的——``define_raw`` 仅用于首次定义路径。

    调用方已通过编译期 ``dispatch_eligible=False`` 保证不会对被 lambda
    捕获的变量（cell 变量）产生 LLMFuture，故此处无需 cell 同步检查。
    """
    target_data = executor.ec.get_node_data(target_uid)
    if not target_data:
        return
    if target_data.get("_type") == "IbTypeAnnotatedExpr":
        _assign_future_to_name_target(executor, target_data.get("target"), future)
        return

    sym_uid = executor.ec.get_side_table("node_to_symbol", target_uid)
    name = target_data.get("id")
    rc = executor.runtime_context

    # 选择落地作用域（尊重 global 语义）
    target_scope = rc.current_scope
    if (
        sym_uid
        and rc.is_global_symbol_uid(sym_uid)
        and rc.current_scope is not rc.global_scope
    ):
        target_scope = rc.global_scope

    # 1) 已存在符号 → 直接覆盖 .value，绕过 _check_type 与 box
    sym = rc.get_symbol_by_uid(sym_uid) if sym_uid else None
    if sym is not None:
        sym.value = future
        sym.current_type = type(future)
        return

    # 2) 首次定义 → 通过 define_raw() 写入，避免直接操作私有字段
    declared_type = (
        executor.ec.resolve_type_from_symbol(sym_uid) if sym_uid else None
    )
    target_scope.define_raw(name, future, uid=sym_uid, declared_type=declared_type)


# ---------------------------------------------------------------------------
# CPS-friendly 通用赋值目标辅助
# ---------------------------------------------------------------------------

def _assign_name_target(
    executor, target_uid: str, target_data: dict, value: Any, define_only: bool = False
) -> None:
    """``IbName`` 目标的纯同步赋值（无 yield）。

    与 ``StmtHandler._assign_to_target`` 中 IbName 分支语义完全一致。
    """
    sym_uid = executor.ec.get_side_table("node_to_symbol", target_uid)
    name = target_data.get("id")
    rc = executor.runtime_context
    if sym_uid:
        existing = rc.get_symbol_by_uid(sym_uid)
        if not define_only and existing:
            rc.set_variable_by_uid(sym_uid, value)
        else:
            declared_type = executor.ec.resolve_type_from_symbol(sym_uid)
            if (
                rc.is_global_symbol_uid(sym_uid)
                and rc.current_scope is not rc.global_scope
            ):
                rc.define_variable_at_global(
                    name, value, declared_type=declared_type, uid=sym_uid
                )
            else:
                rc.define_variable(name, value, declared_type=declared_type, uid=sym_uid)
    elif not executor.ec.strict_mode:
        try:
            rc.get_variable(name)
            if define_only:
                rc.define_variable(name, value)
            else:
                rc.set_variable(name, value)
        except Exception:
            rc.define_variable(name, value)
    else:
        raise RuntimeError(
            f"VM: Strict mode: Symbol UID missing for assignment to '{name}'."
        )


def _vm_assign_to_target(executor, target_uid: str, value: Any, define_only: bool = False):
    """CPS-friendly 通用赋值目标求值辅助。

    支持所有赋值目标类型：
    * ``IbName``               — 纯同步，直接操作作用域（无 yield）
    * ``IbTypeAnnotatedExpr``  — 递归以 ``define_only=True`` 处理内层目标
    * ``IbAttribute``          — ``yield`` 求值 obj，再调用 ``__setattr__``
    * ``IbSubscript``          — ``yield`` 求值 obj 和 slice，再调用 ``__setitem__``
    * ``IbTuple``              — 解包迭代对象，对每个子目标 ``yield from`` 递归

    是 generator function（因包含 ``yield``/``yield from``），在父 handler
    中用 ``yield from _vm_assign_to_target(...)`` 调用。
    """
    target_data = executor.ec.get_node_data(target_uid)
    if not target_data:
        return
    t = target_data.get("_type")

    if t == "IbName":
        _assign_name_target(executor, target_uid, target_data, value, define_only)

    elif t == "IbTypeAnnotatedExpr":
        inner_uid = target_data.get("target")
        if inner_uid:
            yield from _vm_assign_to_target(executor, inner_uid, value, define_only=True)

    elif t == "IbAttribute":
        obj = yield target_data.get("value")
        attr = target_data.get("attr")
        obj.receive("__setattr__", [executor.registry.box(attr), value])

    elif t == "IbSubscript":
        obj = yield target_data.get("value")
        slice_obj = yield target_data.get("slice")
        obj.receive("__setitem__", [slice_obj, value])

    elif t == "IbTuple":
        if isinstance(value, IbValue) and value.ib_class.name in ("list", "tuple"):
            vals = list(value.elements)
        else:
            try:
                r = value.receive("to_list", [])
                if isinstance(r, list):
                    vals = r
                elif hasattr(r, "elements") and isinstance(r.elements, list):
                    vals = list(r.elements)
                else:
                    vals = None
            except Exception:
                vals = None
            if vals is None:
                raise RuntimeError(
                    f"VM: Cannot unpack non-iterable for target {target_uid}"
                )
        elts = target_data.get("elts", [])
        if len(vals) != len(elts):
            raise RuntimeError(
                f"VM: Unpack error: expected {len(elts)} values, got {len(vals)}"
            )
        for t_uid, val in zip(elts, vals):
            yield from _vm_assign_to_target(executor, t_uid, val, define_only=define_only)
