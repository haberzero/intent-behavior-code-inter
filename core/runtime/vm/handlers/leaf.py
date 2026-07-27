"""
core.runtime.vm.handlers.leaf — 叶子 / 基础表达式 CPS handler。

"""
from __future__ import annotations
from typing import Any, Mapping, Dict

from core.runtime.shared.op_constants import (
    OP_MAPPING,
    UNARY_OP_MAPPING,
    AST_OP_MAP,
)
from core.runtime.objects.kernel import (
    IbValue,
    IbLLMFunction,
    IbLLMUncertain,
)
from core.runtime.exceptions import (
    ThrownException,
)
from core.kernel.issue import InterpreterError
from core.runtime.objects.primitives import IbNone
from core.runtime.shared.llm_result import LLMFuture
from core.runtime.vm.handlers._shared import (
    _vm_call_fn_callable,
    _vm_invoke_behavior,
    _vm_invoke_llm_function,
)


# ---------------------------------------------------------------------------
# 叶子 / 基础表达式
# ---------------------------------------------------------------------------

def vm_handle_IbConstant(executor, node_uid: str, node_data: Mapping[str, Any]):
    """常量字面量：直接装箱返回。"""
    if False:
        yield  # pragma: no cover — 强制 generator function
    return executor.registry.box(executor.ec.resolve_value(node_data.get("value")))


def vm_handle_IbName(executor, node_uid: str, node_data: Mapping[str, Any]):
    """变量读取（严格 UID 路径，与 ExprHandler.visit_IbName 同语义）。

    若读到的值是 ``LLMFuture``（dispatch-before-use 残留的待解析占位符），
    在此处阻塞解析并写回，使后续读取为 O(1) 命中。
    """
    if False:
        yield
    sym_uid = executor.ec.get_side_table("node_to_symbol", node_uid)
    if not sym_uid:
        name = node_data.get("id")
        raise RuntimeError(
            f"VM Execution Error: Symbol UID missing for name '{name}'. "
            f"Artifact is corrupted or unanalyzed."
        )
    try:
        val = executor.runtime_context.get_variable_by_uid(sym_uid)
    except Exception as e:
        raise RuntimeError(
            f"VM Execution Error: Symbol with UID '{sym_uid}' "
            f"(name: '{node_data.get('id')}') is not defined."
        ) from e

    # 变量使用点的 LLMFuture 解引用。
    if isinstance(val, LLMFuture):
        sc = executor.service_context
        llm_executor = sc.llm_executor if sc is not None else None
        if llm_executor is not None and hasattr(llm_executor, "resolve"):
            resolved = llm_executor.resolve(val.node_uid)
        else:
            # service_context 不可用时回退到 LLMFuture.get（仍阻塞，结果等价）
            resolved = val.get(executor.registry)
        # 若 Future 解析出不确定值（LLM parse failure），根据是否在 llmexcept
        # 保护帧内决定处理方式：有帧则沿用 Uncertain 哨兵（llmexcept 机制接管），
        # 无帧则抛出 LLMParseError（无自愈机会，语义同情形 B）。
        if isinstance(resolved, IbLLMUncertain):
            if executor.runtime_context.get_current_llm_except_frame() is None:
                error = executor.registry.make_llm_parse_error(
                    "LLM output could not be parsed",
                    raw_response="",
                    type_name="unknown",
                )
                raise ThrownException(error)
        # 写回，避免后续读取再次 resolve
        # skip_type_check=True：写回是缓存优化，类型校验在首次赋值时完成
        executor.runtime_context.set_variable_by_uid(sym_uid, resolved, skip_type_check=True)
        val = resolved
    return val


# ---------------------------------------------------------------------------
# 复合表达式（带子节点）
# ---------------------------------------------------------------------------

def vm_handle_IbBinOp(executor, node_uid: str, node_data: Mapping[str, Any]):
    left = yield node_data.get("left")
    right = yield node_data.get("right")
    op = node_data.get("op")
    method = OP_MAPPING.get(op)
    if not method:
        raise RuntimeError(f"VM: Unsupported binary op: {op}")
    return left.receive(method, [right])


def vm_handle_IbUnaryOp(executor, node_uid: str, node_data: Mapping[str, Any]):
    operand = yield node_data.get("operand")
    op_symbol = node_data.get("op")
    op = AST_OP_MAP.get(op_symbol, op_symbol)
    method = UNARY_OP_MAPPING.get(op)
    if not method:
        raise RuntimeError(f"VM: Unsupported unary op: {op_symbol}")
    return operand.receive(method, [])


def vm_handle_IbBoolOp(executor, node_uid: str, node_data: Mapping[str, Any]):
    is_or = node_data.get("op") == "or"
    last_val = executor.registry.get_none()
    for val_uid in node_data.get("values", []):
        val = yield val_uid
        last_val = val
        if is_or and executor.ec.is_truthy(val):
            return val
        if not is_or and not executor.ec.is_truthy(val):
            return val
    return last_val


def vm_handle_IbIfExp(executor, node_uid: str, node_data: Mapping[str, Any]):
    cond = yield node_data.get("test")
    if executor.ec.is_truthy(cond):
        return (yield node_data.get("body"))
    return (yield node_data.get("orelse"))


def vm_handle_IbCompare(executor, node_uid: str, node_data: Mapping[str, Any]):
    """比较运算（支持链式 + in / not in / is / is not）。"""

    left = yield node_data.get("left")
    ops = node_data.get("ops", [])
    comparators = node_data.get("comparators", [])
    current_left = left
    final_res = executor.registry.box(True)

    for op, comparator_uid in zip(ops, comparators):
        right = yield comparator_uid

        if op == "in":
            contained = right.receive("__contains__", [current_left])
            native = contained.to_native() if hasattr(contained, "to_native") else contained
            cmp_res = executor.registry.box(bool(native))
        elif op == "not in":
            contained = right.receive("__contains__", [current_left])
            native = contained.to_native() if hasattr(contained, "to_native") else contained
            cmp_res = executor.registry.box(not bool(native))
        elif op == "is":
            if isinstance(right, IbNone):
                cmp_res = executor.registry.box(isinstance(current_left, IbNone))
            elif isinstance(right, IbLLMUncertain):
                cmp_res = executor.registry.box(isinstance(current_left, IbLLMUncertain))
            else:
                cmp_res = executor.registry.box(current_left is right)
        elif op == "is not":
            if isinstance(right, IbNone):
                cmp_res = executor.registry.box(not isinstance(current_left, IbNone))
            elif isinstance(right, IbLLMUncertain):
                cmp_res = executor.registry.box(not isinstance(current_left, IbLLMUncertain))
            else:
                cmp_res = executor.registry.box(current_left is not right)
        else:
            method = OP_MAPPING.get(op)
            if not method:
                raise RuntimeError(f"VM: Unsupported comparison: {op}")
            cmp_res = current_left.receive(method, [right])

        if not executor.ec.is_truthy(cmp_res):
            return cmp_res
        final_res = cmp_res
        current_left = right

    return final_res


def vm_handle_IbCall(executor, node_uid: str, node_data: Mapping[str, Any]):
    """函数调用：CPS 求值函数对象和实参；IbFnCallable 完全内联 CPS 执行，
    其他 callable 仍通过 call() 同步完成。
    """
    func = yield node_data.get("func")
    args = []
    for a_uid in node_data.get("args", []):
        args.append((yield a_uid))

    # IbFnCallable（lambda/snapshot）完全 CPS 内联
    if isinstance(func, IbValue) and func.ib_class.name == "fn_callable":
        result = yield from _vm_call_fn_callable(executor, func, args)
        return result

    # IbBehavior / IbLLMFunction: CPS 内联以使 LLM 帧受 VM 调度管理。
    if isinstance(func, IbValue) and func.ib_class.name == "behavior":
        result = yield from _vm_invoke_behavior(executor, func, args)
        return result
    if isinstance(func, IbLLMFunction):
        result = yield from _vm_invoke_llm_function(
            executor, func, executor.registry.get_none(), args
        )
        return result

    try:
        if hasattr(func, "call"):
            return func.call(executor.registry.get_none(), args)
        return func.receive("__call__", args)
    except ThrownException:
        # 用户代码主动抛出的语言级异常必须穿透函数调用边界，由 IbTry / 顶层
        # try-except 体系按 IBCI 类型匹配处理；不得包装成 Python RuntimeError，
        # 否则会丢失 IBCI 异常类型。
        raise
    except Exception as e:
        # 与 ExprHandler.visit_IbCall 同语义：对外汇报为通用调用错误
        raise RuntimeError(f"VM: Call failed: {e}") from e


def vm_handle_IbAttribute(executor, node_uid: str, node_data: Mapping[str, Any]):
    value = yield node_data.get("value")
    attr = node_data.get("attr")
    return value.receive("__getattr__", [executor.registry.box(attr)])


def vm_handle_IbSubscript(executor, node_uid: str, node_data: Mapping[str, Any]):
    value = yield node_data.get("value")
    slice_obj = yield node_data.get("slice")
    return value.receive("__getitem__", [slice_obj])


def vm_handle_IbTuple(executor, node_uid: str, node_data: Mapping[str, Any]):
    elts = []
    for e_uid in node_data.get("elts", []):
        elts.append((yield e_uid))
    return executor.registry.box(tuple(elts))


def vm_handle_IbListExpr(executor, node_uid: str, node_data: Mapping[str, Any]):
    elts = []
    for e_uid in node_data.get("elts", []):
        elts.append((yield e_uid))
    return executor.registry.box(elts)


# === 简单表达式扩展 ===

def vm_handle_IbDict(executor, node_uid: str, node_data: Mapping[str, Any]):
    """字典字面量 -> 装箱 dict（以 native key 索引）。"""
    keys = node_data.get("keys", [])
    values = node_data.get("values", [])
    data: Dict[Any, Any] = {}
    for k_uid, v_uid in zip(keys, values):
        if k_uid:
            key_obj = yield k_uid
        else:
            key_obj = executor.registry.get_none()
        val_obj = yield v_uid
        native_key = key_obj.to_native() if hasattr(key_obj, "to_native") else key_obj
        data[native_key] = val_obj
    return executor.registry.box(data)


def vm_handle_IbSlice(executor, node_uid: str, node_data: Mapping[str, Any]):
    """切片对象（lower/upper/step 任意可空）-> Python slice 装箱。"""
    lower_uid = node_data.get("lower")
    upper_uid = node_data.get("upper")
    step_uid = node_data.get("step")

    l_val = None
    u_val = None
    s_val = None
    if lower_uid:
        lo = yield lower_uid
        l_val = lo.to_native() if hasattr(lo, "to_native") else lo
    if upper_uid:
        up = yield upper_uid
        u_val = up.to_native() if hasattr(up, "to_native") else up
    if step_uid:
        st = yield step_uid
        s_val = st.to_native() if hasattr(st, "to_native") else st
    return executor.registry.box(slice(l_val, u_val, s_val))


def vm_handle_IbCastExpr(executor, node_uid: str, node_data: Mapping[str, Any]):
    """类型强转：与 ExprHandler.visit_IbCastExpr 同语义。

    若目标类型描述符或目标 IbClass 缺失，按既有保守语义直接返回原值。

    LLM-aware: 当转换失败且处于 llmexcept 保护帧内时，通过 LLMResult 信号不确定性
    以便 llmexcept 重试，而非直接抛出异常。LLM 不确定性检测属于 VM handler 层职责，
    不应由原始包装层越层访问。
    """
    value = yield node_data.get("value")
    target_descriptor = executor.ec.get_side_table("node_to_type", node_uid)
    if not target_descriptor:
        return value
    target_class = executor.registry.get_class(target_descriptor.name)
    if not target_class:
        return value
    try:
        return value.receive("cast_to", [target_class])
    except (InterpreterError, Exception) as e:
        rc = executor.runtime_context
        if rc is not None and rc.get_current_llm_except_frame() is not None:
            from core.runtime.shared.llm_result import LLMResult
            raw_val = getattr(value, 'value', '') if hasattr(value, 'value') else str(value)
            rc.set_last_llm_result(
                LLMResult.uncertain_result(
                    raw_response=raw_val,
                    retry_hint=f"类型强制转换失败: {str(e)}"
                )
            )
            return executor.registry.get_none()
        raise


def vm_handle_IbFilteredExpr(executor, node_uid: str, node_data: Mapping[str, Any]):
    """带过滤条件的表达式（while ... if filter 等）。

    与 ExprHandler.visit_IbFilteredExpr 同语义：主表达式为假则短路返回；
    过滤条件为假则返回 IbNone。
    """
    result = yield node_data.get("expr")
    if not executor.ec.is_truthy(result):
        return result
    filter_val = yield node_data.get("filter")
    if not executor.ec.is_truthy(filter_val):
        return executor.registry.get_none()
    return result
