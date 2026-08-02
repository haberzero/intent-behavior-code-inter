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
    _is_llm_uncertain_value,
    _make_uncertain_call_result,
    _raise_uncertain_parse_error,
    _expand_starred,
    _merge_dstar,
    _get_callee_param_specs,
    _resolve_call_arguments_runtime,
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
        if llm_executor is not None:
            resolved = llm_executor.resolve(val.node_uid)
        # 若 Future 解析出不确定容器（LLM parse failure），无 llmexcept 保护帧
        # 则抛 LLMParseError（保留 retry_hint/raw_response）；有帧则由
        # llmexcept 机制接管（容器沿变量流动）。
        if _is_llm_uncertain_value(resolved):
            if executor.runtime_context.get_current_llm_except_frame() is None:
                _raise_uncertain_parse_error(executor, resolved, type_name="unknown")
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
    if _is_llm_uncertain_value(left):
        return left
    right = yield node_data.get("right")
    if _is_llm_uncertain_value(right):
        return right
    op = node_data.get("op")
    method = OP_MAPPING.get(op)
    if not method:
        raise RuntimeError(f"VM: Unsupported binary op: {op}")
    return left.receive(method, [right])


def vm_handle_IbUnaryOp(executor, node_uid: str, node_data: Mapping[str, Any]):
    operand = yield node_data.get("operand")
    if _is_llm_uncertain_value(operand):
        return operand
    op_symbol = node_data.get("op")
    op = AST_OP_MAP.get(op_symbol, op_symbol)
    method = UNARY_OP_MAPPING.get(op)
    if not method:
        raise RuntimeError(f"VM: Unsupported unary op: {op_symbol}")
    return operand.receive(method, [])


def vm_handle_IbBoolOp(executor, node_uid: str, node_data: Mapping[str, Any]):
    is_or = node_data.get("op") == "or"
    seq_result = executor.registry.get_none()
    for val_uid in node_data.get("values", []):
        val = yield val_uid
        if _is_llm_uncertain_value(val):
            return val
        seq_result = val
        truthy = executor.ec.is_truthy(val)
        if _is_llm_uncertain_value(truthy):
            return truthy
        if is_or and truthy:
            return val
        if not is_or and not truthy:
            return val
    return seq_result


def vm_handle_IbIfExp(executor, node_uid: str, node_data: Mapping[str, Any]):
    cond = yield node_data.get("test")
    if _is_llm_uncertain_value(cond):
        return cond
    truthy = executor.ec.is_truthy(cond)
    if _is_llm_uncertain_value(truthy):
        return truthy
    if truthy:
        res = yield node_data.get("body")
        return res
    return (yield node_data.get("orelse"))


def vm_handle_IbCompare(executor, node_uid: str, node_data: Mapping[str, Any]):
    """比较运算（支持链式 + in / not in / is / is not）。"""

    left = yield node_data.get("left")
    if _is_llm_uncertain_value(left):
        return left
    ops = node_data.get("ops", [])
    comparators = node_data.get("comparators", [])
    current_left = left
    final_res = executor.registry.box(True)

    for op, comparator_uid in zip(ops, comparators):
        right = yield comparator_uid
        if _is_llm_uncertain_value(right):
            return right

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

        truthy = executor.ec.is_truthy(cmp_res)
        if _is_llm_uncertain_value(truthy):
            return truthy
        if not truthy:
            return cmp_res
        final_res = cmp_res
        current_left = right

    return final_res


def vm_handle_IbCall(executor, node_uid: str, node_data: Mapping[str, Any]):
    """函数调用：CPS 求值函数对象与实参（含 *expr/**expr splat），
    经统一实参绑定器解析后按声明序绑定；IbFnCallable 完全内联 CPS 执行，
    其他 callable 仍通过 call() 同步完成。
    """
    func = yield node_data.get("func")
    if _is_llm_uncertain_value(func):
        return func

    # --- 求值位置实参（*expr 序列解包展开） ---
    positional = []
    for a_uid in node_data.get("args", []):
        a_data = executor.ec.get_node_data(a_uid)
        if a_data and a_data.get("_type") == "IbStarred":
            starred = yield a_data.get("value")
            if _is_llm_uncertain_value(starred):
                return starred
            positional.extend(_expand_starred(executor, starred))
        else:
            arg = yield a_uid
            if _is_llm_uncertain_value(arg):
                return arg
            positional.append(arg)

    # --- 求值具名实参（**expr 字典解包合并） ---
    keyword_map = {}
    for kw_uid in node_data.get("keywords", []):
        kw_data = executor.ec.get_node_data(kw_uid)
        kw_value = yield kw_data.get("value")
        if _is_llm_uncertain_value(kw_value):
            return kw_value
        kw_name = (kw_data or {}).get("arg")
        if kw_name is None:
            _merge_dstar(executor, keyword_map, kw_value)
        else:
            keyword_map[kw_name] = kw_value

    # --- 统一实参解析：位置 → 具名 → 默认填充 → varargs/varkw ---
    specs = _get_callee_param_specs(executor, func)
    if specs is not None:
        args = yield from _resolve_call_arguments_runtime(
            executor, specs, positional, keyword_map
        )
    else:
        # 无静态签名（内置构造器 / axiom-backed / 运行时 callable）：
        # 保持位置直传，splat 已展开、具名实参忽略（与语义层动态策略一致）。
        args = positional

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
    if _is_llm_uncertain_value(value):
        return value
    attr = node_data.get("attr")
    return value.receive("__getattr__", [executor.registry.box(attr)])


def vm_handle_IbSubscript(executor, node_uid: str, node_data: Mapping[str, Any]):
    value = yield node_data.get("value")
    if _is_llm_uncertain_value(value):
        return value
    slice_obj = yield node_data.get("slice")
    if _is_llm_uncertain_value(slice_obj):
        return slice_obj
    return value.receive("__getitem__", [slice_obj])


def vm_handle_IbTuple(executor, node_uid: str, node_data: Mapping[str, Any]):
    elts = []
    for e_uid in node_data.get("elts", []):
        elt = yield e_uid
        if _is_llm_uncertain_value(elt):
            return elt
        elts.append(elt)
    return executor.registry.box(tuple(elts))


def vm_handle_IbListExpr(executor, node_uid: str, node_data: Mapping[str, Any]):
    elts = []
    for e_uid in node_data.get("elts", []):
        elt = yield e_uid
        if _is_llm_uncertain_value(elt):
            return elt
        elts.append(elt)
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
        if _is_llm_uncertain_value(key_obj):
            return key_obj
        val_obj = yield v_uid
        if _is_llm_uncertain_value(val_obj):
            return val_obj
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
        if _is_llm_uncertain_value(lo):
            return lo
        l_val = lo.to_native() if hasattr(lo, "to_native") else lo
    if upper_uid:
        up = yield upper_uid
        if _is_llm_uncertain_value(up):
            return up
        u_val = up.to_native() if hasattr(up, "to_native") else up
    if step_uid:
        st = yield step_uid
        if _is_llm_uncertain_value(st):
            return st
        s_val = st.to_native() if hasattr(st, "to_native") else st
    return executor.registry.box(slice(l_val, u_val, s_val))


def vm_handle_IbCastExpr(executor, node_uid: str, node_data: Mapping[str, Any]):
    """类型强转：与 ExprHandler.visit_IbCastExpr 同语义。

    若目标类型描述符或目标 IbClass 缺失，按既有保守语义直接返回原值。

    LLM-aware: 当转换失败且处于 llmexcept 保护帧内时，返回
    ``IbLLMCallResult(is_certain=False)`` 不确定容器以便 llmexcept 重试，
    而非直接抛出异常。LLM 不确定性检测属于 VM handler 层职责，
    不应由原始包装层越层访问。
    """
    value = yield node_data.get("value")
    if _is_llm_uncertain_value(value):
        return value
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
            raw_val = getattr(value, 'value', '') if hasattr(value, 'value') else str(value)
            return _make_uncertain_call_result(
                executor.registry,
                raw_response=raw_val,
                retry_hint=f"类型强制转换失败: {str(e)}",
            )
        raise


def vm_handle_IbFilteredExpr(executor, node_uid: str, node_data: Mapping[str, Any]):
    """带过滤条件的表达式（while ... if filter 等）。

    与 ExprHandler.visit_IbFilteredExpr 同语义：主表达式为假则短路返回；
    过滤条件为假则返回 IbNone。任何子表达式产生不确定容器时透传。
    """
    result = yield node_data.get("expr")
    if _is_llm_uncertain_value(result):
        return result
    result_truthy = executor.ec.is_truthy(result)
    if _is_llm_uncertain_value(result_truthy):
        return result_truthy
    if not result_truthy:
        return result
    filter_val = yield node_data.get("filter")
    if _is_llm_uncertain_value(filter_val):
        return filter_val
    filter_truthy = executor.ec.is_truthy(filter_val)
    if _is_llm_uncertain_value(filter_truthy):
        return filter_truthy
    if not filter_truthy:
        return executor.registry.get_none()
    return result
