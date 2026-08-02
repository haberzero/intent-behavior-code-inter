"""
core.runtime.vm.handlers._shared — 跨类别 CPS 辅助函数。
"""
from __future__ import annotations
from typing import Any, Mapping, Optional, List

from core.base.diagnostics.debugger import CoreModule, DebugLevel, core_debugger
from core.runtime.shared.signals import (
    ControlSignal,
    Signal,
)
from core.kernel import ast
from core.kernel.arg_binding import (
    DUPLICATE_KEYWORD,
    TOO_MANY_POSITIONAL,
    UNKNOWN_KEYWORD,
    ParamDecl,
    resolve_call_binding,
)
from core.runtime.objects.kernel import (
    IbValue,
    IbLLMCallResult,
    IbUserFunction,
    IbLLMFunction,
    _is_intent_context_param,
    _should_activate_intent_context_arg,
)
from core.runtime.objects.kernel.functions import IbBoundMethod, IbNativeFunction
from core.base.source_atomic import Location
from core.runtime.exceptions import (
    ThrownException,
)
from core.runtime.objects.intent import IbIntent, IntentRole
from core.runtime.objects.cell import IbCell
from core.runtime.objects.deep_clone import try_deep_clone
from core.runtime.objects.primitives.callables import (
    bind_behavior_closure,
    bind_behavior_call_args,
)
from core.runtime.shared.llm_result import LLMFuture


def _expand_starred(executor, value):
    """把 *expr 求值得到的容器展开为 IbObject 位置实参序列。"""
    elems = getattr(value, "elements", None)
    if isinstance(elems, list):
        return list(elems)
    native = value.to_native() if hasattr(value, "to_native") else value
    if isinstance(native, (list, tuple)):
        return [executor.registry.box(e) if not hasattr(e, "ib_class") else e for e in native]
    raise RuntimeError(f"VM: cannot unpack non-iterable with '*': {type(value).__name__}")


def _merge_dstar(executor, keyword_map, value):
    """把 **expr 求值得到的字典合并进具名实参表。"""
    native = value.to_native() if hasattr(value, "to_native") else value
    if not isinstance(native, dict):
        raise RuntimeError(f"VM: cannot unpack non-mapping with '**': {type(value).__name__}")
    for key, item in native.items():
        keyword_map[key] = item if hasattr(item, "ib_class") else executor.registry.box(item)


def _build_runtime_param_specs(executor, arg_uids):
    """从调用体自身 IbArg 节点列表构建运行时参数签名。

    返回 ``[(name, kind, default_src)]``；``default_src`` 为 ``("uid", uid)``
    （用户级默认表达式，调用时惰性求值）或 None（无默认值）。
    """
    specs = []
    for arg_uid in arg_uids:
        arg_data = executor.ec.get_node_data(arg_uid)
        actual_uid = arg_uid
        actual_data = arg_data
        if arg_data and arg_data.get("_type") == "IbTypeAnnotatedExpr":
            actual_uid = arg_data.get("target")
            actual_data = executor.ec.get_node_data(actual_uid)
        name = (actual_data or {}).get("arg")
        if not name:
            continue
        kind = (actual_data or {}).get("kind", ast.ARG_POSITIONAL_OR_KEYWORD)
        default_uid = (actual_data or {}).get("default")
        specs.append((name, kind, ("uid", default_uid) if default_uid else None))
    return specs


def _get_callee_param_specs(executor, func):
    """获取调用体的运行时参数签名（无静态签名时返回 None）。

    用户/LLM 函数与 fn_callable/behavior 读取自身 AST 的 IbArg 节点；
    bound method 解包到其内层方法；原生模块函数读取 IbNativeFunction 的
    ``param_meta`` 字段（默认源为字面值）。
    """
    if isinstance(func, IbBoundMethod):
        return _get_callee_param_specs(executor, func.method)
    if isinstance(func, (IbUserFunction, IbLLMFunction)):
        node_data = executor.ec.get_node_data(func.node_uid)
        return _build_runtime_param_specs(executor, node_data.get("args", [])) or None
    if isinstance(func, IbValue):
        cls_name = func.ib_class.name if func.ib_class else None
        if cls_name in ("fn_callable", "behavior"):
            if not func.params_uids:
                return None
            return _build_runtime_param_specs(executor, func.params_uids) or None
    if isinstance(func, IbNativeFunction):
        return func.param_meta if func.param_meta else None
    return None


def _resolve_call_arguments_runtime(executor, specs, positional, keyword_map):
    """运行时统一实参解析：位置 → 具名 → 默认填充 → varargs/varkw。

    绑定算法收敛于 `core.kernel.arg_binding.resolve_call_binding`（共享纯核心）；
    本方法把中性绑定计划映射为按声明序的最终实参列表。是 generator：
    默认表达式求值经由 VM 调度（yield）。
    """
    params = [
        ParamDecl(name=name, kind=kind, has_default=default_src is not None)
        for name, kind, default_src in specs
    ]
    default_srcs = [default_src for _name, _kind, default_src in specs]
    keyword_items = list(keyword_map.items())
    binding = resolve_call_binding(params, positional, keyword_items)

    # 非填充类问题按处理顺序抛错（保持既有运行时语义）
    for issue in binding.issues:
        if issue.code == TOO_MANY_POSITIONAL:
            raise RuntimeError("VM: too many positional arguments for callable.")
        if issue.code == DUPLICATE_KEYWORD:
            raise RuntimeError(f"VM: multiple values for argument '{issue.name}'.")
        if issue.code == UNKNOWN_KEYWORD:
            raise RuntimeError(f"VM: unexpected keyword argument '{issue.name}'.")

    # 按声明序装配：默认值惰性求值（yield），缺失必填在此抛出
    varkw = {name: keyword_map[name] for name in binding.varkw_names}
    final = []
    for i, (src_kind, src) in enumerate(binding.slots):
        if src_kind == "varargs":
            final.append(executor.registry.box(
                [positional[idx] for idx in binding.varargs]
            ))
        elif src_kind == "varkw":
            final.append(executor.registry.box(varkw))
        elif src_kind == "positional":
            final.append(positional[src])
        elif src_kind == "keyword":
            final.append(keyword_map[src])
        elif src_kind == "missing":
            raise RuntimeError(f"VM: missing required argument '{params[i].name}'.")
        else:  # default
            default_kind, default_src = default_srcs[i]
            final.append((yield default_src) if default_kind == "uid" else default_src)
    return final


def _vm_call_fn_callable(executor, func, args):
    """CPS 内联执行 IbFnCallable（lambda/snapshot）调用。

    使 lambda/snapshot 体完全在 VM CPS 循环中执行。
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
    practical snapshot / debug-visibility guarantee.

    snapshot 行为体（``capture_mode == 'snapshot'``）：
        每次调用前清除 ``_cache`` 并在子作用域内对自由变量做一次额外深克隆，
        与 ``_vm_call_fn_callable`` 路径一致——snapshot 是无状态、可重入的。

    始终使用**调用现场**的 ``executor.ec`` 作为执行机制（VM、节点池、
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
        bind_behavior_closure(behavior, rt_context)
        bind_behavior_call_args(behavior, args, ec, rt_context)

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

    saved_intent = rt_context.enter_intent_scope()

    if func.module_name and func.module_name != old_module:
        func.context.current_module_name = func.module_name
        try:
            mod_inst = func.context.module_manager.import_module(
                func.module_name, func.context
            )
            rt_context.current_scope = mod_inst.scope
        except Exception as e:
            core_debugger.trace(CoreModule.INTERPRETER, DebugLevel.DETAIL, f"function-context module import '{func.module_name}' failed: {e!r}")

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
        rt_context.exit_intent_scope(saved_intent)
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
    seq_result = executor.registry.get_none()
    pending_one_shot: Optional[IbIntent] = None

    for stmt_uid in stmt_uids or ():
        node_data = executor.ec.get_node_data(stmt_uid) if stmt_uid else None
        if node_data and node_data.get("_type") == "IbIntentAnnotation":
            pending_one_shot = build_one_shot_intent_from_annotation(executor, node_data)
            continue

        if pending_one_shot is not None:
            executor.runtime_context.activate_statement_one_shot_intent(pending_one_shot)

        try:
            seq_result = yield stmt_uid
        finally:
            if pending_one_shot is not None:
                executor.runtime_context.cleanup_statement_one_shot_intent(pending_one_shot)
                pending_one_shot = None

        if isinstance(seq_result, Signal):
            return seq_result

    return seq_result


# ---------------------------------------------------------------------------
# llmexcept 统一机制：certainty 经 IbLLMCallResult 返回值传递
# ---------------------------------------------------------------------------

def _is_llm_uncertain_value(value: Any) -> bool:
    """判断值是否为 LLM 不确定性结果（``IbLLMCallResult`` 且 ``is_certain=False``）。

    产生者（行为表达式 / is_truthy / cast）在无法产生确定结果时返回该容器，
    消费者（赋值 / if / while / for / switch / 表达式语句）从返回值检查。
    """
    return isinstance(value, IbLLMCallResult) and not value.is_certain


def _make_uncertain_call_result(registry, raw_response: str = "", retry_hint: str = "") -> IbLLMCallResult:
    """构造内部 uncertain 传递容器 ``IbLLMCallResult``。"""
    cls = registry.get_class("llm_call_result")
    if cls is None:
        raise RuntimeError("Registry missing 'llm_call_result' class")
    return IbLLMCallResult(
        ib_class=cls,
        is_certain=False,
        raw_response=raw_response or "",
        retry_hint=retry_hint or "",
    )


def _get_max_retry(executor) -> int:
    """从 LLM Provider 读取最大重试次数（默认 3）。"""
    sc = executor.service_context
    if sc is not None:
        cap_reg = getattr(sc, "capability_registry", None)
        if cap_reg is not None:
            llm_provider = cap_reg.get("llm_provider") if hasattr(cap_reg, "get") else None
            if llm_provider is not None and hasattr(llm_provider, "get_retry"):
                return llm_provider.get_retry()
    return 3


def _raise_uncertain_parse_error(executor, uncertain_result, type_name: str = "unknown") -> None:
    """无 llmexcept 保护时，将不确定结果转为 ``LLMParseError`` 抛出。"""
    error = executor.registry.make_llm_parse_error(
        uncertain_result.retry_hint or "LLM output could not be parsed",
        raw_response=uncertain_result.raw_response or "",
        type_name=type_name,
    )
    raise ThrownException(error)


def _retry_llm_uncertain(executor, uncertain_result, handler_uid: str, re_eval_uid: str,
                         node_type: str, on_uncertain_attempt=None, is_acceptable=None):
    """在 llmexcept 保护帧内对不确定结果执行完整多轮重试（生成器）。

    调用方必须以 ``yield from`` 调用，并传入已求值出的不确定结果
    ``uncertain_result``。重试循环内通过 ``yield re_eval_uid`` 重新求值被保护
    表达式（经调用方的 ``yield from`` 转发给 VM 调度器），并通过 send 接收新值。

    ``on_uncertain_attempt``：可选的生成器/可调用对象，在每个不确定轮次
    （handler body 执行前）触发。IbAssign 用它把目标变量临时标记为
    ``IbLLMUncertain``（快照/重试通信令牌）。

    ``is_acceptable``：可选谓词 ``(value) -> bool``。提供时，重试循环在
    ``is_acceptable(final_value)`` 为真时才返回——用于条件消费者把
    "直接不确定容器" 与 "is_truthy 模糊判定" 统一收敛在**同一个帧**的重试计数内，
    避免外层循环反复新建帧导致重试永不止步。

    返回：重试循环结束时最终可接受的值；若被控制流信号打断则返回该 ``Signal``。
    抛出：重试耗尽时 ``LLMRetryExhaustedError``。
    """
    frame = executor.runtime_context.save_llm_except_state(
        target_uid=re_eval_uid,
        node_type=node_type,
        max_retry=_get_max_retry(executor),
    )
    try:
        frame.target_result = uncertain_result
        first_attempt = True
        final_value = uncertain_result
        while frame.should_continue_retrying():
            if not first_attempt:
                frame.restore_snapshot(executor.runtime_context)
                final_value = yield re_eval_uid
                if isinstance(final_value, Signal):
                    return final_value
                if is_acceptable is not None:
                    if is_acceptable(final_value):
                        return final_value
                elif not _is_llm_uncertain_value(final_value):
                    return final_value
                # target_result 始终保留 IbLLMCallResult 容器（certainty 信号载体）
                if _is_llm_uncertain_value(final_value):
                    frame.target_result = final_value
            first_attempt = False

            if on_uncertain_attempt is not None:
                hook_res = on_uncertain_attempt(executor)
                if hook_res is not None:
                    yield from hook_res

            # 执行 handler body（retry 语句设置 retry_hint / should_retry）
            frame.should_retry = False
            handler_data = executor.ec.get_node_data(handler_uid)
            handler_body = handler_data.get("body", []) if handler_data else []
            executor.ec.enter_llmexcept_body()
            try:
                body_res = yield from _vm_execute_stmt_sequence(executor, handler_body)
            finally:
                executor.ec.exit_llmexcept_body()
            if isinstance(body_res, Signal):
                return body_res

            # 运行期影子存储校验：检测被保护变量是否在 body 中被篡改
            violations = frame.verify_snapshot_integrity(executor.runtime_context)
            if violations:
                frame.restore_snapshot(executor.runtime_context)

            if not frame.increment_retry():
                error = executor.registry.make_llm_retry_exhausted_error(
                    f"LLM call retry exhausted after {frame.max_retry} attempt(s); "
                    f"no certain result was produced",
                    max_retry=frame.max_retry,
                    raw_response=getattr(frame.target_result, "raw_response", "") or "",
                )
                raise ThrownException(error)
    finally:
        executor.runtime_context.pop_llm_except_frame()
    return final_value


def _condition_is_acceptable(executor):
    """构造条件值的可接受谓词：非不确定容器，且 is_truthy 不返回模糊容器。"""
    def check(value) -> bool:
        if _is_llm_uncertain_value(value):
            return False
        return not _is_llm_uncertain_value(executor.ec.is_truthy(value))
    return check


def _resolve_condition(executor, cond, handler_uid, re_eval_uid, node_type):
    """解析条件值并处理不确定性（生成器）。

    覆盖两种不确定来源，并在**同一个帧**的重试计数内收敛：
    1. 条件值本身是 ``IbLLMCallResult(is_certain=False)``（行为表达式直接产生）；
    2. ``is_truthy`` 在 llmexcept 帧内对模糊字符串的判定返回不确定容器。

    有 handler 时进入 ``_retry_llm_uncertain`` 完整多轮重试（以
    ``_condition_is_acceptable`` 为收敛谓词，防止模糊字符串导致外层反复
    新建帧而永不止步）；无 handler 时抛 ``LLMParseError``。

    返回确定且可接受的条件值或 ``Signal``。
    """
    if _is_llm_uncertain_value(cond):
        if handler_uid is None:
            _raise_uncertain_parse_error(executor, cond, type_name="bool")
        return (yield from _retry_llm_uncertain(
            executor, cond, handler_uid, re_eval_uid, node_type,
            is_acceptable=_condition_is_acceptable(executor),
        ))
    truthy = executor.ec.is_truthy(cond)
    if _is_llm_uncertain_value(truthy):
        if handler_uid is None:
            _raise_uncertain_parse_error(executor, truthy, type_name="bool")
        return (yield from _retry_llm_uncertain(
            executor, truthy, handler_uid, re_eval_uid, node_type,
            is_acceptable=_condition_is_acceptable(executor),
        ))
    return cond


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
        except Exception as e:
            core_debugger.trace(CoreModule.INTERPRETER, DebugLevel.DETAIL, f"set_variable '{name}' failed, falling back to define: {e!r}")
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
            except Exception as e:
                core_debugger.trace(CoreModule.INTERPRETER, DebugLevel.DETAIL, f"unpack iterable extraction failed: {e!r}")
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
