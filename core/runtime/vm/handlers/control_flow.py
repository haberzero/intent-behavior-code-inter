"""
core.runtime.vm.handlers.control_flow — 控制流 CPS handler。

由原 ``core.runtime.vm.handlers`` 纯机械拆分而来，无逻辑改动。
"""
from __future__ import annotations
from typing import Any, Mapping, Optional

from core.runtime.shared.signals import (
    ControlSignal,
    Signal,
)
from core.runtime.objects.kernel import (
    IbValue,
    IbClass,
)
from core.runtime.exceptions import (
    ThrownException,
)
from core.kernel.issue import InterpreterError
from core.runtime.vm.handlers._shared import (
    _vm_execute_stmt_sequence,
    _raise_if_uncertain_condition,
    _vm_invoke_behavior,
    _vm_assign_to_target,
)


def vm_handle_IbPass(executor, node_uid: str, node_data: Mapping[str, Any]):
    if False:
        yield
    return executor.registry.get_none()


def vm_handle_IbExprStmt(executor, node_uid: str, node_data: Mapping[str, Any]):
    res = yield node_data.get("value")
    if isinstance(res, Signal):
        # 表达式求值理论上不产生控制信号；若子节点意外携带信号上来，
        # 仍按数据透传给父帧处理而不是当场丢弃。
        return res
    if isinstance(res, IbValue) and res.ib_class.name == "behavior":
        # IbBehavior 调用通过 CPS 执行，确保 behavior 帧在 VM 栈上
        result = yield from _vm_invoke_behavior(executor, res, [])
        return result
    return res


def vm_handle_IbIf(executor, node_uid: str, node_data: Mapping[str, Any]):
    """条件分支（与 StmtHandler.visit_IbIf 同语义）。

    每个子语句的执行结果都要检查 ``Signal``，若是则透传给上层。
    body/orelse 直接遍历，无需 ``_resolve_stmt_uid`` 过滤。
    """
    executor.runtime_context.set_last_llm_result(None)
    cond = yield node_data.get("test")
    last = executor.runtime_context.get_last_llm_result()
    _raise_if_uncertain_condition(executor, last)
    branch = node_data.get("body", []) if executor.ec.is_truthy(cond) else node_data.get("orelse", [])
    res = yield from _vm_execute_stmt_sequence(executor, branch)
    if isinstance(res, Signal):
        return res
    return executor.registry.get_none()


def vm_handle_IbWhile(executor, node_uid: str, node_data: Mapping[str, Any]):
    """while 循环：消费 BREAK/CONTINUE 数据信号；其他信号透传。
    body 直接遍历，无需 ``_resolve_stmt_uid`` 过滤。
    """
    test_uid = node_data.get("test")
    body = node_data.get("body", [])
    while True:
        executor.runtime_context.set_last_llm_result(None)
        cond = yield test_uid
        last = executor.runtime_context.get_last_llm_result()
        _raise_if_uncertain_condition(executor, last)
        if not executor.ec.is_truthy(cond):
            break

        # 执行循环体；任意 stmt 返回 Signal 时立即处理
        res = yield from _vm_execute_stmt_sequence(executor, body)
        if isinstance(res, Signal):
            if res.kind is ControlSignal.BREAK:
                break
            if res.kind is ControlSignal.CONTINUE:
                continue
            # RETURN / THROW：透传给上层（函数帧 / 顶层）
            return res
        # CONTINUE 或正常结束：进入下一轮循环
    return executor.registry.get_none()


def vm_handle_IbReturn(executor, node_uid: str, node_data: Mapping[str, Any]):
    """return：以 :class:`Signal` 数据化形式结束当前任务。"""
    value_uid = node_data.get("value")
    if value_uid:
        value = yield value_uid
    else:
        value = executor.registry.get_none()
    # Signal 对象由顶层 run() 处理
    return Signal(ControlSignal.RETURN, value)


def vm_handle_IbBreak(executor, node_uid: str, node_data: Mapping[str, Any]):
    if False:
        yield
    return Signal(ControlSignal.BREAK)


def vm_handle_IbContinue(executor, node_uid: str, node_data: Mapping[str, Any]):
    if False:
        yield
    return Signal(ControlSignal.CONTINUE)


def vm_handle_IbRaise(executor, node_uid: str, node_data: Mapping[str, Any]):
    """raise 语句：求值异常对象后抛出 ``ThrownException``。

    ``ThrownException`` 通过生成器的 try/except 在 IbTry CPS handler 中捕获。
    """
    exc_uid = node_data.get("exc")
    if exc_uid:
        exc_val = yield exc_uid
    else:
        exc_val = executor.registry.get_none()
    raise ThrownException(exc_val)


# === Switch ===

def vm_handle_IbSwitch(executor, node_uid: str, node_data: Mapping[str, Any]):
    """Switch-Case 语句：与 StmtHandler.visit_IbSwitch 同语义。

    test 求值产生不确定 LLM 结果时直接返回 None（与 IbIf 一致）。
    case body 内的 Signal 被透传给上层（return / break / continue / throw）。
    case body 直接遍历，无需 ``_resolve_stmt_uid`` 过滤。
    """
    executor.runtime_context.set_last_llm_result(None)
    test_value = yield node_data.get("test")
    last = executor.runtime_context.get_last_llm_result()
    if last and not last.is_certain:
        return executor.registry.get_none()

    case_uids = node_data.get("cases", [])
    matched = False
    for case_uid in case_uids:
        case_data = executor.ec.get_node_data(case_uid)
        if not case_data:
            continue
        pattern = case_data.get("pattern")
        if pattern is None:
            matched = True
        else:
            pattern_value = yield pattern
            eq_result = test_value.receive("__eq__", [pattern_value])
            if executor.ec.is_truthy(eq_result):
                matched = True

        if matched:
            res = yield from _vm_execute_stmt_sequence(executor, case_data.get("body", []))
            if isinstance(res, Signal):
                return res
            break
    return executor.registry.get_none()


def vm_handle_IbFor(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``for`` 循环：与 StmtHandler.visit_IbFor 同语义。

    支持三种形态：
    * 标准 foreach：``for T name in iterable [if filter]:``
    * 条件驱动：``for @~...~ [if filter]:`` （``target`` 为 ``None``）
    * llmexcept loop_resume：从当前帧的 ``loop_resume[node_uid]`` 索引继续

    条件驱动 for + llmexcept 的内联重试逻辑
    --------------------------------------------------
    当 ``node_data["llmexcept_handler"]`` 存在时，条件 LLM 调用返回 uncertain
    (``last_result.is_certain == False``) 不再直接退出循环，而是：
    1. 创建 ``LLMExceptFrame``（保存快照、记录 target_uid）
    2. 执行 handler body（通常含 ``retry "hint"`` 语句）
    3. 若 ``frame.should_retry`` 为 True（由 ``vm_handle_IbRetry`` 设置）且重试
       次数未耗尽（``frame.increment_retry()`` 返回 True），则 continue 重试条件求值
    4. 否则退出循环（等同于 uncertain-无-handler 情形：``return get_none()``）

    此方案通过 AST 字段（``IbFor.llmexcept_handler``）直接引用 handler，
    避免了旧 ``node_protection`` 侧表 + ``_apply_protection_redirect``
    重定向机制对 ``node_to_type[behavior_expr]`` 的隐式覆写问题。
    """
    target_uid = node_data.get("target")
    iter_uid = node_data.get("iter")
    body = node_data.get("body", [])

    # 拆包 IbFilteredExpr：``for ... in items if filter``
    filter_uid: Optional[str] = None
    actual_iter_uid = iter_uid
    iter_node_data = executor.ec.get_node_data(iter_uid) if iter_uid else None
    if iter_node_data and iter_node_data.get("_type") == "IbFilteredExpr":
        actual_iter_uid = iter_node_data.get("expr")
        filter_uid = iter_node_data.get("filter")

    # ----- 条件驱动循环 -----
    if target_uid is None:
        # 读取 llmexcept_handler uid（由语义分析阶段写入）
        llmexcept_handler_uid: Optional[str] = node_data.get("llmexcept_handler")

        # 从 LLM provider 读取 max_retry（与 vm_handle_IbLLMExceptionalStmt 保持一致）
        max_retry = 3
        sc = executor.service_context
        if sc is not None:
            cap_reg = getattr(sc, "capability_registry", None)
            if cap_reg is not None:
                llm_provider = cap_reg.get("llm_provider") if hasattr(cap_reg, "get") else None
                if llm_provider is not None and hasattr(llm_provider, "get_retry"):
                    max_retry = llm_provider.get_retry()

        while True:
            executor.runtime_context.set_last_llm_result(None)
            condition = yield actual_iter_uid
            if isinstance(condition, Signal):
                return condition
            last_result = executor.runtime_context.get_last_llm_result()

            if last_result and not last_result.is_certain:
                if llmexcept_handler_uid is not None:
                    # uncertain + llmexcept —— 内联重试逻辑
                    llmexcept_data = executor.ec.get_node_data(llmexcept_handler_uid)
                    handler_body_uids = llmexcept_data.get("body", []) if llmexcept_data else []

                    # 创建 LLMExceptFrame，保存当前作用域快照
                    frame = executor.runtime_context.save_llm_except_state(
                        target_uid=actual_iter_uid,
                        node_type="IbLLMExceptionalStmt",
                        max_retry=max_retry,
                    )
                    frame.last_result = last_result
                    frame.should_retry = False  # 等待 retry 语句显式设置

                    try:
                        handler_res = yield from _vm_execute_stmt_sequence(executor, handler_body_uids)
                        if isinstance(handler_res, Signal):
                            return handler_res
                    finally:
                        executor.runtime_context.pop_llm_except_frame()

                    # 仅当 retry 语句被执行（should_retry=True）且重试次数未耗尽时继续
                    if frame.should_retry and frame.increment_retry():
                        continue  # 重试条件求值
                    else:
                        # 重试耗尽：抛出 LLMRetryExhaustedError
                        error = executor.registry.make_llm_retry_exhausted_error(
                            f"LLM condition retry exhausted after {max_retry} attempt(s); "
                            f"no certain result was produced",
                            max_retry=max_retry,
                            raw_response=getattr(last_result, "raw_response", "") or "",
                        )
                        raise ThrownException(error)
                else:
                    # uncertain 且无 llmexcept handler：抛出 LLMParseError
                    error = executor.registry.make_llm_parse_error(
                        getattr(last_result, "retry_hint", None) or "LLM condition output could not be parsed",
                        raw_response=getattr(last_result, "raw_response", "") or "",
                        type_name="bool",
                    )
                    raise ThrownException(error)

            if not executor.ec.is_truthy(condition):
                break
            if filter_uid is not None:
                filter_val = yield filter_uid
                if isinstance(filter_val, Signal):
                    return filter_val
                if not executor.ec.is_truthy(filter_val):
                    break

            res = yield from _vm_execute_stmt_sequence(executor, body)
            if isinstance(res, Signal):
                if res.kind is ControlSignal.BREAK:
                    break
                if res.kind is ControlSignal.CONTINUE:
                    continue
                return res
        return executor.registry.get_none()

    # ----- 标准 Foreach 循环 -----
    iterable_obj = yield actual_iter_uid
    if isinstance(iterable_obj, Signal):
        return iterable_obj

    # 解析迭代序列（与 StmtHandler.visit_IbFor 同协议）
    elements_obj = None
    if hasattr(iterable_obj, "elements") and isinstance(iterable_obj.elements, list):
        elements_obj = iterable_obj
    else:
        try:
            r = iterable_obj.receive("__iter__", [])
            if hasattr(r, "elements") and isinstance(r.elements, list):
                elements_obj = r
        except (AttributeError, InterpreterError):
            pass
        if elements_obj is None:
            try:
                r = iterable_obj.receive("to_list", [])
                if hasattr(r, "elements") and isinstance(r.elements, list):
                    elements_obj = r
            except (AttributeError, InterpreterError):
                elements_obj = None
    if elements_obj is None:
        raise RuntimeError(f"VM: Object is not iterable (uid={node_uid})")

    elements = elements_obj.elements
    total = len(elements)

    # llmexcept 帧的循环断点恢复
    rc = executor.runtime_context
    top_frame = (
        rc._llm_except_frames[-1]
        if hasattr(rc, "_llm_except_frames") and rc._llm_except_frames
        else None
    )
    resume_from = top_frame.loop_resume.get(node_uid, 0) if top_frame is not None else 0

    for i, item in enumerate(elements):
        if i < resume_from:
            continue
        if top_frame is not None:
            top_frame.loop_resume[node_uid] = i
        rc.push_loop_context(i, total)

        # 先赋值循环目标（filter 可能引用循环变量）
        if target_uid:
            yield from _vm_assign_to_target(executor, target_uid, item, define_only=True)

        if filter_uid is not None:
            filter_val = yield filter_uid
            if isinstance(filter_val, Signal):
                rc.pop_loop_context()
                return filter_val
            if not executor.ec.is_truthy(filter_val):
                rc.pop_loop_context()
                continue

        res = yield from _vm_execute_stmt_sequence(executor, body)
        if isinstance(res, Signal):
            if res.kind is ControlSignal.BREAK:
                rc.pop_loop_context()
                break
            if res.kind is ControlSignal.CONTINUE:
                rc.pop_loop_context()
                continue
            rc.pop_loop_context()
            return res

        rc.pop_loop_context()
    return executor.registry.get_none()


def vm_handle_IbTry(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``try / except / else / finally`` 块。

    与 StmtHandler.visit_IbTry 同语义；CPS 适配：
    * body 中的 stmt 通过 ``yield`` 求值；返回 Signal 直接透传（finally 仍执行）
    * 子树抛出的 ``ThrownException`` / 通用异常通过 generator 的 try/except 捕获
    * else 仅在 body 正常结束（无 Signal、无异常）时执行
    * finally 在所有路径上都执行
    * 所有 body/handlers/orelse/finalbody 直接遍历，无需 ``_resolve_stmt_uid``
    """
    body = node_data.get("body", [])
    handlers = node_data.get("handlers", [])
    orelse = node_data.get("orelse", [])
    finalbody = node_data.get("finalbody", [])

    pending_signal: Optional[Signal] = None
    raised_exc: Optional[BaseException] = None
    handled_exc = False

    try:
        res = yield from _vm_execute_stmt_sequence(executor, body)
        if isinstance(res, Signal):
            pending_signal = res
    except ThrownException as te:
        raised_exc = te
    except Exception as e:
        # 与 StmtHandler.visit_IbTry 同语义：``InterpreterError`` 等
        # 解释器内部包装的 Python 异常也作为可捕获错误对待。
        raised_exc = e

    if raised_exc is not None:
        # 构造异常对象
        if isinstance(raised_exc, ThrownException):
            error_obj = raised_exc.value
        else:
            exc_class = executor.registry.get_class("Exception")
            if not exc_class:
                raise RuntimeError(
                    "VM: Critical Error: 'Exception' primitive class not found in registry."
                )
            error_obj = exc_class.instantiate([])
            error_obj.fields["message"] = executor.registry.box(str(raised_exc))

        # 匹配 except 处理器
        for handler_uid in handlers:
            handler_data = executor.ec.get_node_data(handler_uid)
            if not handler_data:
                continue
            type_uid = handler_data.get("type")
            if type_uid:
                expected_type_obj = yield type_uid
                if isinstance(expected_type_obj, Signal):
                    pending_signal = expected_type_obj
                    handled_exc = True  # 防止再次 raise；signal 触发 finally 路径
                    break
                if isinstance(expected_type_obj, IbClass):
                    if not error_obj.ib_class.is_assignable_to(expected_type_obj):
                        continue
                elif expected_type_obj is not error_obj:
                    continue
            # 绑定异常变量
            name = handler_data.get("name")
            if name:
                sym_uid = executor.ec.get_side_table("node_to_symbol", handler_uid)
                executor.runtime_context.define_variable(name, error_obj, uid=sym_uid)
            # 执行处理体
            handler_body_signal: Optional[Signal] = None
            res = yield from _vm_execute_stmt_sequence(executor, handler_data.get("body", []))
            if isinstance(res, Signal):
                handler_body_signal = res
            handled_exc = True
            if handler_body_signal is not None:
                pending_signal = handler_body_signal
            break

        if not handled_exc:
            # 没有匹配的 handler：先跑 finally，再 re-raise
            res = yield from _vm_execute_stmt_sequence(executor, finalbody)
            if isinstance(res, Signal):
                # finally 中的信号优先级最高（覆盖原始异常，与原递归路径一致）
                return res
            raise raised_exc
    else:
        # 没有异常：执行 else（仅当 body 没有 signal 终止）
        if pending_signal is None:
            res = yield from _vm_execute_stmt_sequence(executor, orelse)
            if isinstance(res, Signal):
                pending_signal = res

    # finally：所有路径都要执行
    res = yield from _vm_execute_stmt_sequence(executor, finalbody)
    if isinstance(res, Signal):
        # finally 中的 signal 覆盖任何 pending signal
        return res

    if pending_signal is not None:
        return pending_signal
    return executor.registry.get_none()
