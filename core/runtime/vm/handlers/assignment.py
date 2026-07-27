"""
core.runtime.vm.handlers.assignment — 赋值 / global / nonlocal CPS handler。

"""
from __future__ import annotations
from typing import Any, Mapping, Optional

from core.runtime.shared.op_constants import (
    OP_MAPPING,
    AST_OP_MAP,
)
from core.runtime.exceptions import (
    ThrownException,
)
from core.runtime.shared.llm_result import LLMFuture
from core.runtime.vm.handlers._shared import (
    _is_simple_name_target,
    _assign_future_to_name_target,
    _vm_assign_to_target,
)


def vm_handle_IbAssign(executor, node_uid: str, node_data: Mapping[str, Any]):
    """赋值语句完整 CPS 实现。

    当 RHS 为 ``IbBehaviorExpr`` 且其 ``dispatch_eligible=True``、非 fn_callable
    时，调用 ``LLMScheduler.dispatch_eager`` 立即提交后台 LLM 调用，得到
    ``LLMFuture`` 占位符并直接绑定到目标变量；后续在使用点（``IbName``）解析。
    这是 LLM 数据流流水线的核心机制：相邻独立 LLM 表达式可并发执行，时序近似
    ``max(T_a, T_b, ..)`` 而非 ``sum``。

    所有赋值目标（IbName / IbTypeAnnotatedExpr / IbAttribute / IbSubscript /
    IbTuple 解包）均通过 CPS ``_vm_assign_to_target`` 处理。

    is_callable_instance 路径：``yield value_uid``，``vm_handle_IbBehaviorExpr``
    已完整实现 fn_callable 模式的 IbBehavior 包装。
    """
    executor.runtime_context.set_last_llm_result(None)
    value_uid = node_data.get("value")

    is_callable_instance = False
    if value_uid:
        value_node_data = executor.ec.get_node_data(value_uid)
        is_callable_instance = bool(value_node_data.get("is_callable_instance")) if value_node_data else False

    # 识别 dispatch-before-use 路径
    dispatched_future: Optional[LLMFuture] = None
    if value_uid and not is_callable_instance:
        value_node_data = executor.ec.get_node_data(value_uid)
        if (
            value_node_data
            and value_node_data.get("_type") == "IbBehaviorExpr"
            and value_node_data.get("dispatch_eligible", False)
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
        # cell 捕获变量已在编译期被标记为 dispatch_eligible=False，
        # 故 dispatched_future 不会为被 cell 捕获的目标变量生成。
        # 此处只需简单判断目标形式，不再需要运行时 scope 链扫描。
        targets = node_data.get("targets", [])
        future_assignable = all(
            _is_simple_name_target(executor, t_uid)
            for t_uid in targets
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
            sync_result = None
        if sync_result is not None:
            for target_uid in targets:
                yield from _vm_assign_to_target(executor, target_uid, sync_result)
            return executor.registry.get_none()
        # 兜底：让下面的同步路径继续执行（极少触发）

    # is_callable_instance 路径：vm_handle_IbBehaviorExpr 已完整实现 fn_callable 模式
    # 的 IbBehavior 包装，直接 yield 走 CPS 调度。
    value = yield value_uid

    last = executor.runtime_context.get_last_llm_result()
    if last and not last.is_certain:
        # 检查是否在 llmexcept 保护帧内
        if executor.runtime_context.get_current_llm_except_frame() is not None:
            # 在保护帧内：赋值 Uncertain 哨兵，llmexcept 机制负责重试
            value = executor.registry.get_llm_uncertain()
        else:
            # 无保护帧：无法自愈，抛出真正的 LLMParseError
            error = executor.registry.make_llm_parse_error(
                last.retry_hint or "LLM output could not be parsed",
                raw_response=last.raw_response or "",
                type_name="unknown",
            )
            raise ThrownException(error)

    # 所有目标类型均通过 CPS helper 处理
    for target_uid in node_data.get("targets", []):
        yield from _vm_assign_to_target(executor, target_uid, value)
    return executor.registry.get_none()


# === 简单语句 ===

def vm_handle_IbGlobalStmt(executor, node_uid: str, node_data: Mapping[str, Any]):
    """global 声明是编译期语义，运行时无操作。"""
    if False:
        yield  # pragma: no cover — 强制 generator function
    return executor.registry.get_none()


def vm_handle_IbNonlocalStmt(executor, node_uid: str, node_data: Mapping[str, Any]):
    """nonlocal 声明是编译期语义，运行时无操作。

    nonlocal 的语义效果在编译期通过 SymbolResolutionPass 完成：
    - 阻止 _prescan_body_locals 为 nonlocal 名称创建局部符号
    - 将外层作用域的符号引用注入当前作用域
    运行时赋值操作通过符号 UID 解析自然穿透到外层作用域（Cell 提升机制）。
    """
    if False:
        yield  # pragma: no cover — 强制 generator function
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
