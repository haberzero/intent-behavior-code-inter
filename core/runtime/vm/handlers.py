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
from typing import Any, Mapping, Optional, Dict, List, Set

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
from core.runtime.objects.kernel import (
    IbObject,
    IbUserFunction,
    IbLLMFunction,
    IbClass,
)
from core.runtime.exceptions import (
    ReturnException,
    BreakException,
    ContinueException,
    ThrownException,
)
from core.runtime.objects.intent import IbIntent, IntentMode, IntentRole
from core.runtime.interpreter.llm_result import LLMFuture
from core.kernel.issue import InterpreterError


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
    """变量读取（严格 UID 路径，与 ExprHandler.visit_IbName 同语义）。

    M5c：若读到的值是 ``LLMFuture``（dispatch-before-use 残留的待解析占位符），
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

    # M5c：变量使用点的 LLMFuture 解引用。
    if isinstance(val, LLMFuture):
        sc = executor.service_context
        llm_executor = sc.llm_executor if sc is not None else None
        if llm_executor is not None and hasattr(llm_executor, "resolve"):
            resolved = llm_executor.resolve(val.node_uid)
        else:
            # service_context 不可用时回退到 LLMFuture.get（仍阻塞，结果等价）
            resolved = val.get(executor.registry)
        # 写回，避免后续读取再次 resolve（且每个 Future 只能 resolve 一次）
        executor.runtime_context.set_variable_by_uid(sym_uid, resolved)
        val = resolved
    return val


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

    M5c：当 RHS 为 ``IbBehaviorExpr`` 且其 ``dispatch_eligible=True``、非 deferred
    时，调用 ``LLMScheduler.dispatch_eager`` 立即提交后台 LLM 调用，得到
    ``LLMFuture`` 占位符并直接绑定到目标变量；后续在使用点（``IbName``）解析。
    这是 LLM 数据流流水线的核心机制：相邻独立 LLM 表达式可并发执行，时序近似
    ``max(T_a, T_b, ..)`` 而非 ``sum``。
    """
    executor.runtime_context.set_last_llm_result(None)
    value_uid = node_data.get("value")

    is_deferred = False
    if value_uid:
        is_deferred = bool(executor.ec.get_side_table("node_is_deferred", value_uid))

    # M5c：识别 dispatch-before-use 路径
    dispatched_future: Optional[LLMFuture] = None
    if value_uid and not is_deferred:
        value_node_data = executor.ec.get_node_data(value_uid)
        if (
            value_node_data
            and value_node_data.get("_type") == "IbBehaviorExpr"
            and value_node_data.get("dispatch_eligible", True)
            # 不在 llmexcept 保护下调度：llmexcept 协议依赖同步读取 LLM 结果
            # 来检测不确定性并触发 retry；异步 dispatch 会绕过该协议导致占位符
            # 直接落入用户变量。
            and executor.runtime_context.get_current_llm_except_frame() is None
        ):
            sc = executor.service_context
            llm_executor = sc.llm_executor if sc is not None else None
            if llm_executor is not None and hasattr(llm_executor, "dispatch_eager"):
                # 在 dispatch 时刻 fork 当前意图栈快照，确保后台线程看到的
                # 意图状态与同步执行点一致（避免 dispatch 后主线程 push/pop
                # 改变 LLM 提示词构造的语义）。
                try:
                    intent_snapshot = executor.runtime_context.fork_intent_snapshot()
                except Exception:
                    intent_snapshot = None
                dispatched_future = llm_executor.dispatch_eager(
                    value_uid, executor.ec, intent_ctx=intent_snapshot
                )

    if dispatched_future is not None:
        # 直接把 LLMFuture 写入目标，跳过 LLM 不确定性检查与同步求值。
        # 仅支持简单的 IbName / IbTypeAnnotatedExpr(IbName) 目标——
        # 复杂目标（attribute/subscript/tuple unpack）此处不并发化，
        # fallback 到同步路径以保证语义一致。
        targets = node_data.get("targets", [])
        future_assignable = all(
            _is_simple_name_target(executor, t_uid) for t_uid in targets
        )
        if future_assignable:
            for target_uid in targets:
                _assign_future_to_name_target(executor, target_uid, dispatched_future)
            return executor.registry.get_none()
        # 复杂目标：撤销 dispatch 改走同步路径
        try:
            sync_result = executor.service_context.llm_executor.resolve(
                dispatched_future.node_uid
            )
        except Exception:
            # 万一 resolve 失败，仍走同步 fallback；下方 yield 路径会重新求值
            sync_result = None
        if sync_result is not None:
            for target_uid in targets:
                executor.assign_to_target(target_uid, sync_result)
            return executor.registry.get_none()
        # 兜底：让下面的同步路径继续执行（极少触发）

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

    M5c：与 ``StmtHandler._assign_to_target`` 中 ``IbName`` 分支语义一致，
    但写入的值是 ``LLMFuture``（非 ``IbObject``）。读取点（``vm_handle_IbName``）
    会在第一次访问时阻塞 resolve 并写回真实 ``IbObject``。

    实现细节：``RuntimeContext.set_variable_by_uid`` / ``define_variable`` 走的
    是 ``ScopeImpl.assign_by_uid`` / ``define`` 路径，会触发 ``_check_type`` 和
    ``registry.box`` 把 ``LLMFuture`` 包装成普通 ``IbObject``——这与占位符语义
    冲突。本函数直接操作底层 ``RuntimeSymbolImpl``（与 vm/handlers 同层），
    保留原始 ``LLMFuture`` 引用直到被 resolve 写回。
    """
    from core.runtime.interpreter.runtime_context import RuntimeSymbolImpl

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
        # 显式不同步 IbCell：LLMFuture 不是合法 IbObject，不应进入 cell.set。
        # 该路径覆盖的变量已在 ScopeImpl.promote_to_cell 中提升为 Cell 时
        # 的不变式：lambda HOF 捕获的变量不应在 LLM 并发管道中被
        # dispatch_eager 路径写入。该约束由 SemanticAnalyzer 保证。
        return

    # 2) 首次定义 → 直接构造 RuntimeSymbolImpl 写入 _uid_to_symbol/_symbols
    declared_type = (
        executor.ec.resolve_type_from_symbol(sym_uid) if sym_uid else None
    )
    new_sym = RuntimeSymbolImpl(
        name=name, value=future, declared_type=declared_type, is_const=False
    )
    if name:
        target_scope._symbols[name] = new_sym
    if sym_uid:
        target_scope._uid_to_symbol[sym_uid] = new_sym


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
# M3d-prep：扩展 CPS handler 覆盖
#
# 以下 handler 把 ExprHandler / StmtHandler 中对应 visit_X 方法的语义 1:1
# 镜像到 CPS 风格，但保留下面几个事实：
#   * 对象的 ``call()`` / ``receive()`` 仍是 Python 调用——这与 IbCall handler
#     的 M3a 选择一致（M3d 才需要把函数体本身用 CPS 驱动）；
#   * 控制流仍由父级容器 handler（Module/If/While/llmexcept）承担消费；
#     IbReturn/IbBreak/IbContinue 仍 ``return Signal(...)``；新增的 IbRaise
#     则把 ThrownException 显式抛出，沿用 fallback 路径在 IbTry 中捕获。
# ---------------------------------------------------------------------------


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
    """
    value = yield node_data.get("value")
    target_descriptor = executor.ec.get_side_table("node_to_type", node_uid)
    if not target_descriptor:
        return value
    target_class = executor.registry.get_class(target_descriptor.name)
    if not target_class:
        return value
    return value.receive("cast_to", [target_class])


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


# === 简单语句 ===

def vm_handle_IbGlobalStmt(executor, node_uid: str, node_data: Mapping[str, Any]):
    """global 声明是编译期语义，运行时无操作。"""
    if False:
        yield  # pragma: no cover — 强制 generator function
    return executor.registry.get_none()


def vm_handle_IbRaise(executor, node_uid: str, node_data: Mapping[str, Any]):
    """raise 语句：求值异常对象后抛出 ``ThrownException``。

    ``ThrownException`` 在 IbTry 的 fallback 路径中捕获；M3d 完成后，IbTry
    的 CPS 实现会用 Signal 模式接管，这里仍保留显式异常以兼容现有 fallback。
    """
    exc_uid = node_data.get("exc")
    if exc_uid:
        exc_val = yield exc_uid
    else:
        exc_val = executor.registry.get_none()
    raise ThrownException(exc_val)


def vm_handle_IbImport(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``import x`` 在 IBCI 当前阶段为编译期语义，运行时无操作。"""
    if False:
        yield
    return executor.registry.get_none()


def vm_handle_IbImportFrom(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``from x import y`` 在 IBCI 当前阶段为编译期语义，运行时无操作。"""
    if False:
        yield
    return executor.registry.get_none()


# === 复合赋值 ===

def vm_handle_IbAugAssign(executor, node_uid: str, node_data: Mapping[str, Any]):
    """复合赋值（``a += b`` 等）：与 StmtHandler.visit_IbAugAssign 同语义。

    支持 IbName / IbAttribute 目标。下标 / 元组解包在原 handler 中也未支持，
    此处一并保持不变。
    """
    target_uid = node_data.get("target")
    target_data = executor.ec.get_node_data(target_uid)
    value = yield node_data.get("value")
    op_symbol = node_data.get("op")
    base_op = (
        op_symbol.rstrip("=") if op_symbol and op_symbol.endswith("=") else op_symbol
    )
    op = AST_OP_MAP.get(base_op, base_op)
    method = OP_MAPPING.get(op)
    if not method:
        raise RuntimeError(f"VM: Unsupported aug op: {op_symbol}")

    # 1. 读取旧值
    old_val = yield target_uid
    # 2. 计算新值
    new_val = old_val.receive(method, [value])
    # 3. 写回
    if target_data and target_data.get("_type") == "IbName":
        sym_uid = executor.ec.get_side_table("node_to_symbol", target_uid)
        if sym_uid:
            executor.runtime_context.set_variable_by_uid(sym_uid, new_val)
        else:
            executor.runtime_context.set_variable(target_data.get("id"), new_val)
    elif target_data and target_data.get("_type") == "IbAttribute":
        obj = yield target_data.get("value")
        attr = target_data.get("attr")
        obj.receive("__setattr__", [executor.registry.box(attr), new_val])
    return executor.registry.get_none()


# === Switch ===

def vm_handle_IbSwitch(executor, node_uid: str, node_data: Mapping[str, Any]):
    """Switch-Case 语句：与 StmtHandler.visit_IbSwitch 同语义。

    test 求值产生不确定 LLM 结果时直接返回 None（与 IbIf 一致）。
    case body 内的 Signal 被透传给上层（return / break / continue / throw）。
    case body 内的受保护节点通过 _resolve_stmt_uid 重定向到 llmexcept handler。
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
            for stmt_uid in case_data.get("body", []):
                effective_uid = _resolve_stmt_uid(executor, stmt_uid)
                if effective_uid is None:
                    continue
                res = yield effective_uid
                if isinstance(res, Signal):
                    return res
            break
    return executor.registry.get_none()


# === 定义类语句（不下钻 body 内子节点） ===

def vm_handle_IbFunctionDef(executor, node_uid: str, node_data: Mapping[str, Any]):
    """普通函数定义：在当前作用域绑定 IbUserFunction。"""
    if False:
        yield
    sym_uid = executor.ec.get_side_table("node_to_symbol", node_uid)
    declared_type = executor.ec.resolve_type_from_symbol(sym_uid)
    func = IbUserFunction(node_uid, executor.ec, spec=declared_type)
    name = node_data.get("name")
    executor.runtime_context.define_variable(
        name, func, declared_type=declared_type, uid=sym_uid
    )
    return executor.registry.get_none()


def vm_handle_IbLLMFunctionDef(executor, node_uid: str, node_data: Mapping[str, Any]):
    """LLM 函数定义：在当前作用域绑定 IbLLMFunction。"""
    if False:
        yield
    sym_uid = executor.ec.get_side_table("node_to_symbol", node_uid)
    declared_type = executor.ec.resolve_type_from_symbol(sym_uid)
    func = IbLLMFunction(node_uid, executor.ec, spec=declared_type)
    name = node_data.get("name")
    executor.runtime_context.define_variable(
        name, func, declared_type=declared_type, uid=sym_uid
    )
    return executor.registry.get_none()


def vm_handle_IbClassDef(executor, node_uid: str, node_data: Mapping[str, Any]):
    """类契约校验 + 作用域绑定。

    与 StmtHandler.visit_IbClassDef 同语义：类必须在 STAGE 5 已预水合，此处
    仅做契约校验并绑定到当前作用域。校验失败时抛 RuntimeError（与原 handler
    的 self.report_error 等价的"严格模式"）。
    """
    if False:
        yield
    name = node_data.get("name")
    existing_class = executor.registry.get_class(name)
    if not existing_class:
        raise RuntimeError(
            f"VM: Sealed Registry Error: Class '{name}' must be pre-hydrated in STAGE 5."
        )
    sym_uid = executor.ec.get_side_table("node_to_symbol", node_uid)
    executor.runtime_context.define_variable(name, existing_class, uid=sym_uid)

    # 深度契约校验：AST body 中声明的方法必须已注入虚表
    body = node_data.get("body", [])
    for stmt_uid in body:
        stmt_data = executor.ec.get_node_data(stmt_uid)
        if not stmt_data:
            continue
        if stmt_data.get("_type") in ("IbFunctionDef", "IbLLMFunctionDef"):
            method_name = stmt_data.get("name")
            if method_name not in existing_class.methods:
                raise RuntimeError(
                    f"VM: Hydration Leak: Method '{method_name}' of class "
                    f"'{name}' was not hydrated in STAGE 5."
                )
            method_obj = existing_class.methods[method_name]
            if hasattr(method_obj, "spec") and method_obj.spec:
                params = stmt_data.get("args", [])
                expected_count = (
                    len(method_obj.spec.params)
                    if hasattr(method_obj.spec, "params")
                    else -1
                )
                if expected_count != -1 and len(params) != expected_count:
                    raise RuntimeError(
                        f"VM: Contract Mismatch: Method '{method_name}' of class "
                        f"'{name}' parameter count mismatch. "
                        f"AST: {len(params)}, Descriptor: {expected_count}"
                    )
    return executor.registry.get_none()


# === 意图操作 ===

def vm_handle_IbIntentAnnotation(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``@`` / ``@!`` 单次意图涂抹：与 StmtHandler.visit_IbIntentAnnotation 同。"""
    if False:
        yield
    intent_info_uid = node_data.get("intent")
    if not intent_info_uid:
        return executor.registry.get_none()
    intent_data = executor.ec.get_node_data(intent_info_uid)
    if not intent_data:
        return executor.registry.get_none()
    intent = executor.ec.factory.create_intent_from_node(
        intent_info_uid, intent_data, role=IntentRole.SMEAR
    )
    if intent.is_override:
        executor.runtime_context.set_pending_override_intent(intent)
    else:
        executor.runtime_context.add_smear_intent(intent)
    return executor.registry.get_none()


def vm_handle_IbIntentStackOperation(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``@+`` / ``@-`` 意图栈操作：与 StmtHandler.visit_IbIntentStackOperation 同。"""
    if False:
        yield
    intent_info_uid = node_data.get("intent")
    if not intent_info_uid:
        return executor.registry.get_none()
    intent_data = executor.ec.get_node_data(intent_info_uid)
    if not intent_data:
        return executor.registry.get_none()
    intent = executor.ec.factory.create_intent_from_node(
        intent_info_uid, intent_data, role=IntentRole.STACK
    )
    if intent.is_pop_top:
        executor.runtime_context.pop_intent()
    elif intent.is_remove:
        if intent.tag:
            executor.runtime_context.remove_intent(tag=intent.tag)
        elif intent.content:
            executor.runtime_context.remove_intent(content=intent.content)
    else:
        executor.runtime_context.push_intent(intent)
    return executor.registry.get_none()


# ---------------------------------------------------------------------------
# M3d：剩余节点 CPS handler
#
# 这些 handler 与 ExprHandler / StmtHandler 中对应 visit_X 方法 1:1 同语义，
# 控制流通过 Signal 数据化（M3b）；异常仍以 Python 异常机制处理（IbTry 在
# generator 内 try/except 捕获）。
# ---------------------------------------------------------------------------


def vm_handle_IbBehaviorExpr(executor, node_uid: str, node_data: Mapping[str, Any]):
    """LLM 行为描述行（``@~ ... ~``）。

    与 ExprHandler.visit_IbBehaviorExpr 同语义：
    * 若被标记为 deferred，根据 ``deferred_mode`` 创建 ``IbBehavior`` 包装
      （snapshot 捕获意图栈快照，lambda 不捕获）。
    * 否则直接同步执行 LLM 调用，把 ``LLMResult`` 写入
      ``runtime_context.set_last_llm_result``，返回 ``result.value``。

    注意：M5c 的 dispatch-before-use 路径**不**在这里触发——dispatch_eager
    由 ``vm_handle_IbAssign`` 在识别到 RHS 为本节点且 ``dispatch_eligible=True``
    时调用，避免 LLMFuture 占位符泄漏到非赋值上下文。
    """
    if False:
        yield
    is_deferred = executor.ec.get_side_table("node_is_deferred", node_uid)

    intent_uid = node_data.get("intent")
    call_intent: Optional[IbIntent] = None
    if intent_uid:
        intent_data = executor.ec.get_node_data(intent_uid)
        intent_class = executor.registry.get_class("Intent")
        call_intent = IbIntent.from_node_data(
            intent_uid, intent_data, intent_class, role=IntentRole.SMEAR
        )

    sc = executor.service_context

    if is_deferred:
        deferred_mode = executor.ec.get_side_table("node_deferred_mode", node_uid)
        captured_intents = (
            None if deferred_mode == "lambda"
            else executor.runtime_context.fork_intent_snapshot()
        )
        return sc.object_factory.create_behavior(
            node_uid,
            captured_intents,
            expected_type=executor.ec.get_side_table("node_to_type", node_uid),
            call_intent=call_intent,
            deferred_mode=deferred_mode,
            execution_context=executor.ec,
        )

    # 同步执行（fallback 共享同一 LLMExecutor）
    result = sc.llm_executor.execute_behavior_expression(
        node_uid, executor.ec, call_intent=call_intent
    )
    executor.runtime_context.set_last_llm_result(result)
    if result is not None and result.value is not None:
        return result.value
    return executor.registry.get_none()


def vm_handle_IbBehaviorInstance(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``(Type) @~ ... ~`` 隐式实例化。

    与 ExprHandler.visit_IbBehaviorInstance 同语义。该节点不下钻子节点
    （segments 在 LLM Executor 内部求值），故无 yield。
    """
    if False:
        yield
    return executor.fallback_visit(node_uid)


def vm_handle_IbLambdaExpr(executor, node_uid: str, node_data: Mapping[str, Any]):
    """lambda / snapshot 表达式：构造 ``IbDeferred`` 或 ``IbBehavior``（M2 SC-3/SC-4）。

    自由变量分析与 IbCell 提升涉及大量 AST 走访 + 作用域操作，且不下钻 body
    节点（body 在调用时才执行），CPS 化收益为零。直接 fallback 到
    ExprHandler.visit_IbLambdaExpr。
    """
    if False:
        yield
    return executor.fallback_visit(node_uid)


def vm_handle_IbRetry(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``retry`` 语句：与 StmtHandler.visit_IbRetry 同语义。

    1. 求值可选的 retry hint，写入 ``runtime_context.retry_hint``
    2. 通过 ``frame.restore_snapshot`` 恢复 llmexcept 帧的快照
    3. 设置 ``frame.should_retry = True``，由外层 llmexcept handler 重新执行 target
    """
    hint_uid = node_data.get("hint")
    hint_val: Optional[str] = None
    if hint_uid:
        hint_obj = yield hint_uid
        hint_val = hint_obj.to_native() if hasattr(hint_obj, "to_native") else str(hint_obj)
    executor.runtime_context.retry_hint = hint_val
    frame = executor.runtime_context.get_current_llm_except_frame()
    if frame is not None:
        frame.restore_snapshot(executor.runtime_context)
        frame.should_retry = True
    return executor.registry.get_none()


def vm_handle_IbFor(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``for`` 循环：与 StmtHandler.visit_IbFor 同语义。

    支持三种形态：
    * 标准 foreach：``for T name in iterable [if filter]:``
    * 条件驱动：``for @~...~ [if filter]:`` （``target`` 为 ``None``）
    * llmexcept loop_resume：从当前帧的 ``loop_resume[node_uid]`` 索引继续
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
        while True:
            executor.runtime_context.set_last_llm_result(None)
            condition = yield actual_iter_uid
            if isinstance(condition, Signal):
                return condition
            last_result = executor.runtime_context.get_last_llm_result()
            if last_result and not last_result.is_certain:
                return executor.registry.get_none()
            if not executor.ec.is_truthy(condition):
                break
            if filter_uid is not None:
                filter_val = yield filter_uid
                if isinstance(filter_val, Signal):
                    return filter_val
                if not executor.ec.is_truthy(filter_val):
                    break

            consumed: Optional[ControlSignal] = None
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
                    return res
            if consumed is ControlSignal.BREAK:
                break
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
            executor.assign_to_target(target_uid, item)
            # define_only=True 语义在标准 fallback _assign_to_target 中通过
            # IbTypeAnnotatedExpr 包装实现；此处统一路径使用 assign_to_target
            # 调用与原 fallback 完全一致。

        if filter_uid is not None:
            filter_val = yield filter_uid
            if isinstance(filter_val, Signal):
                rc.pop_loop_context()
                return filter_val
            if not executor.ec.is_truthy(filter_val):
                rc.pop_loop_context()
                continue

        consumed = None
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
                rc.pop_loop_context()
                return res

        rc.pop_loop_context()
        if consumed is ControlSignal.BREAK:
            break
    return executor.registry.get_none()


def vm_handle_IbTry(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``try / except / else / finally`` 块。

    与 StmtHandler.visit_IbTry 同语义；CPS 适配：
    * body 中的 stmt 通过 ``yield`` 求值；返回 Signal 直接透传（finally 仍执行）
    * 子树抛出的 ``ThrownException`` / 通用异常通过 generator 的 try/except 捕获
    * else 仅在 body 正常结束（无 Signal、无异常）时执行
    * finally 在所有路径上都执行
    """
    body = node_data.get("body", [])
    handlers = node_data.get("handlers", [])
    orelse = node_data.get("orelse", [])
    finalbody = node_data.get("finalbody", [])

    pending_signal: Optional[Signal] = None
    raised_exc: Optional[BaseException] = None
    handled_exc = False

    try:
        for stmt_uid in body:
            effective_uid = _resolve_stmt_uid(executor, stmt_uid)
            if effective_uid is None:
                continue
            res = yield effective_uid
            if isinstance(res, Signal):
                pending_signal = res
                break
    except (ReturnException, BreakException, ContinueException):
        # 控制流异常（fallback 路径）：透传，但仍要走 finally
        raise
    except ThrownException as te:
        raised_exc = te
    except InterpreterError:
        raise
    except Exception as e:
        raised_exc = e

    if raised_exc is not None:
        # 构造异常对象
        if isinstance(raised_exc, ThrownException):
            error_obj = raised_exc.value
        else:
            exc_class = executor.registry.get_class("Exception")
            if not exc_class:
                raise RuntimeError(
                    "VM: Critical Error: 'Exception' builtin class not found in registry."
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
            for stmt_uid in handler_data.get("body", []):
                effective_uid = _resolve_stmt_uid(executor, stmt_uid)
                if effective_uid is None:
                    continue
                res = yield effective_uid
                if isinstance(res, Signal):
                    handler_body_signal = res
                    break
            handled_exc = True
            if handler_body_signal is not None:
                pending_signal = handler_body_signal
            break

        if not handled_exc:
            # 没有匹配的 handler：先跑 finally，再 re-raise
            for stmt_uid in finalbody:
                effective_uid = _resolve_stmt_uid(executor, stmt_uid)
                if effective_uid is None:
                    continue
                res = yield effective_uid
                if isinstance(res, Signal):
                    # finally 中的信号优先级最高（覆盖原始异常，与原递归路径一致）
                    return res
            raise raised_exc
    else:
        # 没有异常：执行 else（仅当 body 没有 signal 终止）
        if pending_signal is None:
            for stmt_uid in orelse:
                effective_uid = _resolve_stmt_uid(executor, stmt_uid)
                if effective_uid is None:
                    continue
                res = yield effective_uid
                if isinstance(res, Signal):
                    pending_signal = res
                    break

    # finally：所有路径都要执行
    for stmt_uid in finalbody:
        effective_uid = _resolve_stmt_uid(executor, stmt_uid)
        if effective_uid is None:
            continue
        res = yield effective_uid
        if isinstance(res, Signal):
            # finally 中的 signal 覆盖任何 pending signal
            return res

    if pending_signal is not None:
        return pending_signal
    return executor.registry.get_none()



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
        # M3d-prep 表达式扩展
        "IbDict": vm_handle_IbDict,
        "IbSlice": vm_handle_IbSlice,
        "IbCastExpr": vm_handle_IbCastExpr,
        "IbFilteredExpr": vm_handle_IbFilteredExpr,
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
        # M3d-prep 语句扩展
        "IbAugAssign": vm_handle_IbAugAssign,
        "IbGlobalStmt": vm_handle_IbGlobalStmt,
        "IbRaise": vm_handle_IbRaise,
        "IbImport": vm_handle_IbImport,
        "IbImportFrom": vm_handle_IbImportFrom,
        "IbSwitch": vm_handle_IbSwitch,
        "IbFunctionDef": vm_handle_IbFunctionDef,
        "IbLLMFunctionDef": vm_handle_IbLLMFunctionDef,
        "IbClassDef": vm_handle_IbClassDef,
        "IbIntentAnnotation": vm_handle_IbIntentAnnotation,
        "IbIntentStackOperation": vm_handle_IbIntentStackOperation,
        # M3d：剩余节点
        "IbBehaviorExpr": vm_handle_IbBehaviorExpr,
        "IbBehaviorInstance": vm_handle_IbBehaviorInstance,
        "IbLambdaExpr": vm_handle_IbLambdaExpr,
        "IbFor": vm_handle_IbFor,
        "IbTry": vm_handle_IbTry,
        "IbRetry": vm_handle_IbRetry,
    }
