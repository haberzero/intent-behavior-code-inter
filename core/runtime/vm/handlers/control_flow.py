"""
core.runtime.vm.handlers.control_flow — 控制流 CPS handler。

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
from core.runtime.objects.primitives.collections import (
    IbList,
    IbTuple,
)
from core.runtime.exceptions import (
    ThrownException,
)
from core.kernel.issue import InterpreterError
from core.runtime.vm.handlers._shared import (
    _vm_execute_stmt_sequence,
    _vm_invoke_behavior,
    _vm_assign_to_target,
    _is_llm_uncertain_value,
    _resolve_condition,
    _retry_llm_uncertain,
    _raise_uncertain_parse_error,
)


def vm_handle_IbPass(executor, node_uid: str, node_data: Mapping[str, Any]):
    return executor.registry.get_none()


def vm_handle_IbExprStmt(executor, node_uid: str, node_data: Mapping[str, Any]):
    """表达式语句：求值后丢弃结果。

    llmexcept 保护：表达式返回不确定容器时，若有 handler 则创建帧并完整多轮
    重试；无 handler 则抛 ``LLMParseError``。
    """
    value_uid = node_data.get("value")
    res = yield value_uid
    if isinstance(res, Signal):
        return res
    if _is_llm_uncertain_value(res):
        handler_uid = node_data.get("llmexcept_handler")
        if handler_uid is None:
            _raise_uncertain_parse_error(executor, res, type_name="unknown")
        res = yield from _retry_llm_uncertain(executor, res, handler_uid, value_uid, "IbExprStmt")
        if isinstance(res, Signal):
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

    llmexcept 保护：条件值不确定（直接容器或 is_truthy 模糊判定）时，
    有 handler 则内联重试，无 handler 则抛 ``LLMParseError``。
    """
    test_uid = node_data.get("test")
    handler_uid = node_data.get("llmexcept_handler")
    cond = yield test_uid
    cond = yield from _resolve_condition(executor, cond, handler_uid, test_uid, "IbIf")
    if isinstance(cond, Signal):
        return cond
    branch = node_data.get("body", []) if executor.ec.is_truthy(cond) else node_data.get("orelse", [])
    res = yield from _vm_execute_stmt_sequence(executor, branch)
    if isinstance(res, Signal):
        return res
    return executor.registry.get_none()


def vm_handle_IbWhile(executor, node_uid: str, node_data: Mapping[str, Any]):
    """while 循环：消费 BREAK/CONTINUE 数据信号；其他信号透传。
    body 直接遍历，无需 ``_resolve_stmt_uid`` 过滤。

    llmexcept 保护：条件值不确定时，有 handler 则内联重试，无 handler 则抛
    ``LLMParseError``。
    """
    test_uid = node_data.get("test")
    handler_uid = node_data.get("llmexcept_handler")
    body = node_data.get("body", [])
    while True:
        cond = yield test_uid
        cond = yield from _resolve_condition(executor, cond, handler_uid, test_uid, "IbWhile")
        if isinstance(cond, Signal):
            return cond
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
    return Signal(ControlSignal.BREAK)


def vm_handle_IbContinue(executor, node_uid: str, node_data: Mapping[str, Any]):
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

    test 求值产生不确定 LLM 结果时，有 llmexcept handler 则内联重试，
    无 handler 则抛 ``LLMParseError``（不再静默返回 None）。
    case body 内的 Signal 被透传给上层（return / break / continue / throw）。
    case body 直接遍历，无需 ``_resolve_stmt_uid`` 过滤。
    """
    test_uid = node_data.get("test")
    handler_uid = node_data.get("llmexcept_handler")
    test_value = yield test_uid
    test_value = yield from _resolve_condition(executor, test_value, handler_uid, test_uid, "IbSwitch")
    if isinstance(test_value, Signal):
        return test_value

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
            if _is_llm_uncertain_value(pattern_value):
                return pattern_value
            eq_result = test_value.receive("__eq__", [pattern_value])
            eq_truthy = executor.ec.is_truthy(eq_result)
            if _is_llm_uncertain_value(eq_truthy):
                return eq_truthy
            if eq_truthy:
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
    （``IbLLMCallResult(is_certain=False)``）不再直接退出循环，而是通过
    ``_resolve_condition`` 创建 ``LLMExceptFrame``（保存快照）+ 执行 handler
    body + 完整多轮重试；无 handler 时抛 ``LLMParseError``。
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

        while True:
            condition = yield actual_iter_uid
            if isinstance(condition, Signal):
                return condition
            condition = yield from _resolve_condition(
                executor, condition, llmexcept_handler_uid, actual_iter_uid, "IbFor"
            )
            if isinstance(condition, Signal):
                return condition

            if not executor.ec.is_truthy(condition):
                break
            if filter_uid is not None:
                filter_val = yield filter_uid
                if isinstance(filter_val, Signal):
                    return filter_val
                # filter 是布尔位置：不确定时经 llmexcept handler 重试
                filter_val = yield from _resolve_condition(
                    executor, filter_val, llmexcept_handler_uid, filter_uid, "IbFor"
                )
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
    llmexcept_handler_uid = node_data.get("llmexcept_handler")
    iterable_obj = yield actual_iter_uid
    if isinstance(iterable_obj, Signal):
        return iterable_obj
    if _is_llm_uncertain_value(iterable_obj):
        if llmexcept_handler_uid is None:
            _raise_uncertain_parse_error(executor, iterable_obj, type_name="list")
        iterable_obj = yield from _retry_llm_uncertain(
            executor, iterable_obj, llmexcept_handler_uid, actual_iter_uid, "IbFor"
        )
        if isinstance(iterable_obj, Signal):
            return iterable_obj

    # 解析迭代序列（与 StmtHandler.visit_IbFor 同协议）
    elements_obj = None
    if isinstance(iterable_obj, (IbList, IbTuple)):
        elements_obj = iterable_obj
    else:
        # 结构化能力查询（不靠异常判定）：有 __iter__ 走迭代，否则尝试 to_list。
        # 用户 __iter__ 实现体内的真实错误不再被能力探测误吞。
        if iterable_obj.ib_class.lookup_method("__iter__") is not None:
            r = iterable_obj.receive("__iter__", [])
            if isinstance(r, (IbList, IbTuple)):
                elements_obj = r
        if elements_obj is None:
            if iterable_obj.ib_class.lookup_method("to_list") is not None:
                r = iterable_obj.receive("to_list", [])
                if isinstance(r, (IbList, IbTuple)):
                    elements_obj = r
    if elements_obj is None:
        raise RuntimeError(f"VM: Object is not iterable (uid={node_uid})")

    elements = elements_obj.elements
    total = len(elements)

    # llmexcept 帧的循环断点恢复（外层帧保护整个循环时按迭代索引续跑）
    rc = executor.runtime_context
    top_frame = rc.get_current_llm_except_frame()
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
            # filter 是布尔位置：不确定时经 llmexcept handler 重试
            filter_val = yield from _resolve_condition(
                executor, filter_val, llmexcept_handler_uid, filter_uid, "IbFor"
            )
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
