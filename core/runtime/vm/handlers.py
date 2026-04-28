"""
core.runtime.vm.handlers — CPS 节点处理器。

每个 ``vm_handle_<NodeType>`` 是一个 **生成器函数**，遵循以下契约（M3b 起）：

* ``yield child_uid``        —— 挂起当前任务，调度器会启动 ``child_uid`` 的求值；
                                 求值完成后通过 ``generator.send(result)`` 把结果送回
* ``return value``           —— 任务完成，``value`` 通过 ``StopIteration.value``
                                 传给调用方
* ``return Signal(kind, v)`` —— 触发控制流信号（M3b 数据化路径）：调度器识别
                                 ``StopIteration.value`` 是 :class:`Signal` 时，
                                 把 Signal 通过 ``gen.send(Signal)`` 传给父帧；
                                 父 handler 用 ``isinstance(res, Signal)`` 检查
                                 是否拦截/继续传播

handler 形参：
    ``executor`` —— :class:`VMExecutor` 实例，提供 ``ec`` / ``runtime_context``
                    / ``registry`` / ``service_context`` 等访问入口

handler 内可调用 ``executor.fallback_visit(uid)`` 同步求值未实现的节点子树。

**多语句容器的信号检查约定（M3b）**：
``IbModule`` / ``IbIf`` / ``IbWhile`` 这类包含子语句序列的 handler，每次
``yield stmt_uid`` 后必须检查返回值是否为 ``Signal``：循环 handler 自行
消费 BREAK/CONTINUE，其余信号（RETURN/THROW）和非循环 handler 应通过
``return res`` 把信号继续向上传播。

**llmexcept 保护机制（M3c）**：
``IbLLMExceptionalStmt`` 节点在 module/block body 中以如下形式出现：

    body = [..., target_uid, llmexcept_uid, ...]

``node_protection["target_uid"] = llmexcept_uid``（由编译器建立）。

容器 handler（IbModule / IbIf / IbWhile）使用 ``_resolve_stmt_uid()`` 对
body 中每个 stmt_uid 进行"保护重定向"：
  * 若 stmt 本身是 IbLLMExceptionalStmt → 跳过（其执行由 target 重定向触发）
  * 若 stmt 有 node_protection 条目 → yield 其对应的 llmexcept handler uid
  * 其他 → 正常 yield

``vm_handle_IbLLMExceptionalStmt`` 在被重定向调用后，独立管理 retry 循环和
LLMExceptFrame 快照，彻底消除递归路径对 Python try/except 的依赖（M3c 目标）。
"""
from __future__ import annotations
from typing import Any, Mapping, Optional

from core.runtime.vm.task import (
    ControlSignal,
    ControlSignalException,
    Signal,
)
from core.runtime.interpreter.constants import (
    OP_MAPPING,
    UNARY_OP_MAPPING,
    AST_OP_MAP,
)
from core.runtime.objects.builtins import IbBehavior
from core.runtime.objects.kernel import IbObject


# ---------------------------------------------------------------------------
# 保护重定向辅助函数（M3c）
# ---------------------------------------------------------------------------

def _resolve_stmt_uid(executor, stmt_uid: str) -> Optional[str]:
    """返回容器 handler 应当 yield 的有效 UID。

    规则（M3c llmexcept 保护机制）：
    1. ``_type == "IbLLMExceptionalStmt"`` → 返回 ``None``（跳过；由其 target
       的 node_protection 重定向来驱动）
    2. ``node_protection[stmt_uid]`` 有值 → 返回 handler uid（重定向到
       vm_handle_IbLLMExceptionalStmt）
    3. 其他 → 原样返回 ``stmt_uid``

    容器 handler 收到 ``None`` 时应 ``continue`` 跳过该 stmt。
    """
    nd = executor.ec.get_node_data(stmt_uid)
    if nd and nd.get("_type") == "IbLLMExceptionalStmt":
        return None  # skip: driven by its target's redirect
    protection_uid = executor.ec.get_side_table("node_protection", stmt_uid)
    return protection_uid if protection_uid else stmt_uid


# ---------------------------------------------------------------------------
# 叶子 / 基础表达式
# ---------------------------------------------------------------------------

def vm_handle_IbConstant(executor, node_uid: str, node_data: Mapping[str, Any]):
    """常量字面量：直接装箱返回。"""
    if False:
        yield  # pragma: no cover — 强制 generator function
    return executor.registry.box(executor.ec.resolve_value(node_data.get("value")))


def vm_handle_IbName(executor, node_uid: str, node_data: Mapping[str, Any]):
    """变量读取（严格 UID 路径，与 ExprHandler.visit_IbName 同语义）。"""
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
        return executor.runtime_context.get_variable_by_uid(sym_uid)
    except Exception as e:
        raise RuntimeError(
            f"VM Execution Error: Symbol with UID '{sym_uid}' "
            f"(name: '{node_data.get('id')}') is not defined."
        ) from e


def vm_handle_IbPass(executor, node_uid: str, node_data: Mapping[str, Any]):
    if False:
        yield
    return executor.registry.get_none()


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
    from core.runtime.objects.builtins import IbNone
    from core.runtime.objects.kernel import IbLLMUncertain

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
    """函数调用（M3a 骨架）：调用方对象的 ``call()`` 内部仍走递归实现，
    但参数与函数表达式本身的求值通过 CPS 完成。
    """
    func = yield node_data.get("func")
    args = []
    for a_uid in node_data.get("args", []):
        args.append((yield a_uid))

    try:
        if hasattr(func, "call"):
            return func.call(executor.registry.get_none(), args)
        return func.receive("__call__", args)
    except ControlSignalException:
        # 透传：函数体内的 ReturnException 等可能从 fallback 路径冒出
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


# ---------------------------------------------------------------------------
# 语句节点
# ---------------------------------------------------------------------------

def vm_handle_IbModule(executor, node_uid: str, node_data: Mapping[str, Any]):
    result = executor.registry.get_none()
    for stmt_uid in node_data.get("body", []):
        effective_uid = _resolve_stmt_uid(executor, stmt_uid)
        if effective_uid is None:
            continue  # IbLLMExceptionalStmt 直接出现在 body 中：跳过
        result = yield effective_uid
        if isinstance(result, Signal):
            # 顶层模块遇到信号：直接透传给调度器，让 run() 决定包装为 ControlSignalException
            return result
    return result


def vm_handle_IbExprStmt(executor, node_uid: str, node_data: Mapping[str, Any]):
    res = yield node_data.get("value")
    if isinstance(res, Signal):
        # 表达式求值理论上不产生控制信号；但若子节点（如嵌套语句块的 fallback
        # 路径）意外携带信号上来，仍按数据透传给父帧处理而不是当场丢弃。
        return res
    if isinstance(res, IbBehavior):
        # IbBehavior 的 call() 仍走原实现（通过 LLMExecutor），M3a 不重写
        return res.call(executor.registry.get_none(), [])
    return res


def vm_handle_IbIf(executor, node_uid: str, node_data: Mapping[str, Any]):
    """条件分支（与 StmtHandler.visit_IbIf 同语义）。

    M3b：每个子语句的执行结果都要检查 ``Signal``，若是则透传给上层。
    M3c：通过 ``_resolve_stmt_uid`` 对 body/orelse 中的受保护节点进行重定向。
    """
    executor.runtime_context.set_last_llm_result(None)
    cond = yield node_data.get("test")
    last = executor.runtime_context.get_last_llm_result()
    if last and not last.is_certain:
        return executor.registry.get_none()
    branch = node_data.get("body", []) if executor.ec.is_truthy(cond) else node_data.get("orelse", [])
    for stmt_uid in branch:
        effective_uid = _resolve_stmt_uid(executor, stmt_uid)
        if effective_uid is None:
            continue
        res = yield effective_uid
        if isinstance(res, Signal):
            return res
    return executor.registry.get_none()


def vm_handle_IbWhile(executor, node_uid: str, node_data: Mapping[str, Any]):
    """while 循环（M3b：消费 BREAK/CONTINUE 数据信号；其他信号透传）。
    M3c：通过 ``_resolve_stmt_uid`` 对 body 中的受保护节点进行重定向。
    """
    test_uid = node_data.get("test")
    body = node_data.get("body", [])
    while True:
        executor.runtime_context.set_last_llm_result(None)
        cond = yield test_uid
        last = executor.runtime_context.get_last_llm_result()
        if last and not last.is_certain:
            return executor.registry.get_none()
        if not executor.ec.is_truthy(cond):
            break

        # 执行循环体；任意 stmt 返回 Signal 时立即处理
        consumed = None  # type: ControlSignal | None
        for stmt_uid in body:
            effective_uid = _resolve_stmt_uid(executor, stmt_uid)
            if effective_uid is None:
                continue
            res = yield effective_uid
            if isinstance(res, Signal):
                if res.kind is ControlSignal.BREAK:
                    consumed = ControlSignal.BREAK
                    break
                if res.kind is ControlSignal.CONTINUE:
                    consumed = ControlSignal.CONTINUE
                    break
                # RETURN / THROW：透传给上层（函数帧 / 顶层）
                return res
        if consumed is ControlSignal.BREAK:
            break
        # CONTINUE 或正常结束：进入下一轮循环
    return executor.registry.get_none()


def vm_handle_IbReturn(executor, node_uid: str, node_data: Mapping[str, Any]):
    """return：以 :class:`Signal` 数据化形式结束当前任务（M3b）。"""
    value_uid = node_data.get("value")
    if value_uid:
        value = yield value_uid
    else:
        value = executor.registry.get_none()
    # M3b：return Signal 而非 raise ControlSignalException
    return Signal(ControlSignal.RETURN, value)


def vm_handle_IbBreak(executor, node_uid: str, node_data: Mapping[str, Any]):
    if False:
        yield
    return Signal(ControlSignal.BREAK)


def vm_handle_IbContinue(executor, node_uid: str, node_data: Mapping[str, Any]):
    if False:
        yield
    return Signal(ControlSignal.CONTINUE)


def vm_handle_IbAssign(executor, node_uid: str, node_data: Mapping[str, Any]):
    """赋值语句（M3a 骨架）：仅支持 IbName / IbTypeAnnotatedExpr(IbName) 目标，
    其余目标（属性 / 下标 / 元组解包）回退到原 ``_assign_to_target`` 路径。
    """
    executor.runtime_context.set_last_llm_result(None)
    value_uid = node_data.get("value")

    is_deferred = False
    if value_uid:
        is_deferred = bool(executor.ec.get_side_table("node_is_deferred", value_uid))

    if is_deferred and value_uid:
        # 延迟值的创建涉及对 IbBehaviorExpr / 普通子树的特殊处理；
        # 直接复用 ExprHandler 的处理路径，避免 M3a 阶段重写 deferred 语义。
        value = executor.fallback_visit(value_uid)
    else:
        value = yield value_uid

    last = executor.runtime_context.get_last_llm_result()
    if last and not last.is_certain:
        value = executor.registry.get_llm_uncertain()

    for target_uid in node_data.get("targets", []):
        executor.assign_to_target(target_uid, value)
    return executor.registry.get_none()


# ---------------------------------------------------------------------------
# M3c：IbLLMExceptionalStmt CPS handler
# ---------------------------------------------------------------------------

def vm_handle_IbLLMExceptionalStmt(executor, node_uid: str, node_data: Mapping[str, Any]):
    """llmexcept 语句的 CPS 调度器实现（M3c）。

    把原来 ``StmtHandler.visit_IbLLMExceptionalStmt`` 中的 Python
    try/except retry 循环迁移到 VMExecutor 调度循环中管理。

    执行流程：
    1. 从 LLM Provider 读取 ``max_retry``（默认 3）
    2. 创建 ``LLMExceptFrame`` 并保存上下文快照
    3. 循环（最多 max_retry 次）：
       a. restore_snapshot（确保每次 LLM 看到一致的输入状态）
       b. 清除共享信号通道
       c. CPS 执行 target（yield target_uid；若未支持则 fallback + bypass_protection）
       d. 读取 last_llm_result：
          - None 或 is_certain → 成功，break
          - is_uncertain → 执行 handler body（body 中的 retry 语句会设置
            frame.should_retry = True）
       e. increment_retry：若耗尽重试次数则 break
    4. finally：保证 pop_llm_except_frame 始终执行

    信号传播：target 或 body 返回 Signal（RETURN/BREAK/CONTINUE/THROW）时
    立即透传给父帧，并在 finally 中完成帧清理。
    """
    target_uid: Optional[str] = node_data.get("target")
    body_uids = node_data.get("body", [])

    if not target_uid:
        if False:
            yield  # pragma: no cover — 无 target 时仍需维持 generator function 签名
        return executor.registry.get_none()

    # 从 LLM Provider 获取重试次数配置
    max_retry = 3
    sc = executor.service_context
    if sc is not None and sc.capability_registry:
        llm_provider = sc.capability_registry.get("llm_provider")
        if llm_provider and hasattr(llm_provider, "get_retry"):
            max_retry = llm_provider.get_retry()

    # 创建 LLMExceptFrame 并保存上下文快照
    frame = executor.runtime_context.save_llm_except_state(
        target_uid=target_uid,
        node_type="IbLLMExceptionalStmt",
        max_retry=max_retry,
    )

    last_target_value = executor.registry.get_none()
    try:
        while frame.should_continue_retrying():
            # 恢复快照（首次进入为 no-op，retry 时确保 LLM 看到一致输入）
            frame.restore_snapshot(executor.runtime_context)

            # 清除共享信号通道，防止上次结果污染本次判断
            executor.runtime_context.set_last_llm_result(None)

            # 执行 target：CPS 路径（若 target 类型在调度表中），否则 fallback
            # 使用 bypass_protection=True 等价语义：此 handler 本身即是保护控制器，
            # 无需再通过 node_protection 重定向。
            if executor.supports(target_uid):
                last_target_value = yield target_uid
            else:
                last_target_value = executor.ec.visit(target_uid, bypass_protection=True)

            # 信号透传：target 内部产生控制流信号时立即向上传播
            if isinstance(last_target_value, Signal):
                return last_target_value

            # 读取并立即消费 last_llm_result（缩短生命周期至快照内通信）
            result = executor.runtime_context.get_last_llm_result()
            executor.runtime_context.set_last_llm_result(None)

            # LLM 调用确定或无 LLM 调用：任务完成
            if result is None or result.is_certain:
                break

            # LLM 返回不确定：执行 handler body
            frame.last_result = result
            frame.should_retry = False  # 等待 body 中的 retry 语句重新设为 True

            for stmt_uid in body_uids:
                effective_uid = _resolve_stmt_uid(executor, stmt_uid)
                if effective_uid is None:
                    continue
                body_res = yield effective_uid
                if isinstance(body_res, Signal):
                    return body_res

            # 递增重试计数；若耗尽则退出
            if not frame.increment_retry():
                break

    finally:
        # 无论正常结束、信号传播还是异常，帧都必须弹出
        executor.runtime_context.pop_llm_except_frame()

    return last_target_value


# ---------------------------------------------------------------------------
# 注册表
# ---------------------------------------------------------------------------

def build_dispatch_table() -> dict:
    """返回 node_type → generator-handler 的查询表。"""
    return {
        # 表达式
        "IbConstant": vm_handle_IbConstant,
        "IbName": vm_handle_IbName,
        "IbBinOp": vm_handle_IbBinOp,
        "IbUnaryOp": vm_handle_IbUnaryOp,
        "IbBoolOp": vm_handle_IbBoolOp,
        "IbIfExp": vm_handle_IbIfExp,
        "IbCompare": vm_handle_IbCompare,
        "IbCall": vm_handle_IbCall,
        "IbAttribute": vm_handle_IbAttribute,
        "IbSubscript": vm_handle_IbSubscript,
        "IbTuple": vm_handle_IbTuple,
        "IbListExpr": vm_handle_IbListExpr,
        # 语句
        "IbModule": vm_handle_IbModule,
        "IbPass": vm_handle_IbPass,
        "IbExprStmt": vm_handle_IbExprStmt,
        "IbIf": vm_handle_IbIf,
        "IbWhile": vm_handle_IbWhile,
        "IbReturn": vm_handle_IbReturn,
        "IbBreak": vm_handle_IbBreak,
        "IbContinue": vm_handle_IbContinue,
        "IbAssign": vm_handle_IbAssign,
        # M3c：llmexcept 保护机制
        "IbLLMExceptionalStmt": vm_handle_IbLLMExceptionalStmt,
    }
