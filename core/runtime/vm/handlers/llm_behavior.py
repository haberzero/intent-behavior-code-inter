"""
core.runtime.vm.handlers.llm_behavior — LLM 行为 / 意图 / llmexcept CPS handler。
"""
from __future__ import annotations
from typing import Any, Mapping, Optional, Dict, List

from core.runtime.shared.signals import (
    Signal,
)
from core.runtime.exceptions import (
    ThrownException,
)
from core.runtime.objects.intent import IbIntent, IntentMode, IntentRole
from core.runtime.objects.deep_clone import try_deep_clone
from core.runtime.vm.handlers._shared import (
    _vm_execute_stmt_sequence,
)


def vm_handle_IbLLMExceptionalStmt(executor, node_uid: str, node_data: Mapping[str, Any]):
    """llmexcept 语句的 CPS 调度器实现。

    执行流程：
    1. 从 LLM Provider 读取 ``max_retry``（默认 3）
    2. 创建 ``LLMExceptFrame`` 并保存上下文快照
    3. 循环（最多 max_retry 次）：
       a. restore_snapshot（确保每次 LLM 看到一致的输入状态）
       b. 清除共享信号通道
       c. CPS 执行 target（yield target_uid）
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
        first_iteration = True
        while frame.should_continue_retrying():
            # 恢复快照：首次迭代跳过（刚刚 save_context 完成，状态一致）；
            # 后续迭代在此处统一恢复，确保每次 LLM 看到一致的输入状态。
            if not first_iteration:
                frame.restore_snapshot(executor.runtime_context)
            first_iteration = False

            # 清除共享信号通道，防止上次结果污染本次判断
            executor.runtime_context.set_last_llm_result(None)

            # dispatch table 覆盖所有节点类型。
            last_target_value = yield target_uid

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

            # 在 retry body 中禁用 write_overwrite 写入。
            executor.ec.enter_llmexcept_body()
            try:
                body_res = yield from _vm_execute_stmt_sequence(executor, body_uids)
            finally:
                executor.ec.exit_llmexcept_body()
            if isinstance(body_res, Signal):
                return body_res

            # 递增重试计数；若耗尽则抛出 LLMRetryExhaustedError
            if not frame.increment_retry():
                error = executor.registry.make_llm_retry_exhausted_error(
                    f"LLM call retry exhausted after {max_retry} attempt(s); "
                    f"no certain result was produced",
                    max_retry=max_retry,
                    raw_response=getattr(result, "raw_response", "") or "",
                )
                raise ThrownException(error)

    finally:
        # 无论正常结束、信号传播还是异常，帧都必须弹出
        executor.runtime_context.pop_llm_except_frame()

    return last_target_value


# === 意图操作 ===

def vm_handle_IbIntentAnnotation(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``@`` / ``@!`` 单次意图注释节点的执行路径。"""
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
    executor.runtime_context.activate_statement_one_shot_intent(intent)
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
# 剩余 CPS handler
#
# 这些 handler 与 ExprHandler / StmtHandler 中对应 visit_X 方法 1:1 同语义，
# 控制流通过 Signal 数据化；异常仍以 Python 异常机制处理（IbTry 在
# generator 内 try/except 捕获）。
# ---------------------------------------------------------------------------


def vm_handle_IbBehaviorExpr(executor, node_uid: str, node_data: Mapping[str, Any]):
    """LLM 行为描述行（``@~ ... ~``）。

    与 ExprHandler.visit_IbBehaviorExpr 同语义：
    * 若被标记为 fn_callable，根据 ``capture_mode`` 创建 ``IbBehavior`` 包装
      （snapshot 捕获意图栈快照，lambda 不捕获）。
    * 否则直接同步执行 LLM 调用，把 ``LLMResult`` 写入
      ``runtime_context.set_last_llm_result``，返回 ``result.value``。

    注意：dispatch-before-use 路径**不**在这里触发——dispatch_eager
    由 ``vm_handle_IbAssign`` 在识别到 RHS 为本节点且 ``dispatch_eligible=True``
    时调用，避免 LLMFuture 占位符泄漏到非赋值上下文。
    """
    if False:
        yield
    is_callable_instance = node_data.get("is_callable_instance")

    intent_uid = node_data.get("intent")
    call_intent: Optional[IbIntent] = None
    if intent_uid:
        intent_data = executor.ec.get_node_data(intent_uid)
        intent_class = executor.registry.get_class("Intent")
        call_intent = IbIntent.from_node_data(
            intent_uid, intent_data, intent_class, role=IntentRole.SMEAR
        )

    sc = executor.service_context

    if is_callable_instance:
        capture_mode = node_data.get("capture_mode")
        captured_intents = (
            None if capture_mode == "lambda"
            else executor.runtime_context.fork_intent_snapshot()
        )
        return sc.object_factory.create_behavior(
            node_uid,
            captured_intents,
            expected_type=executor.ec.get_side_table("node_to_type", node_uid),
            call_intent=call_intent,
            capture_mode=capture_mode,
            execution_context=executor.ec,
        )

    # 提取命名模型 tag（@NAME~ 语法）用于模型路由
    target_model = node_data.get("tag", "")

    # 同步执行（fallback 共享同一 LLMExecutor）
    result = sc.llm_executor.execute_behavior_expression(
        node_uid, executor.ec, call_intent=call_intent,
        target_model=target_model,
    )
    executor.runtime_context.set_last_llm_result(result)
    if result is not None and result.value is not None:
        return result.value
    return executor.registry.get_none()


def vm_handle_IbBehaviorInstance(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``(Type) @~ ... ~`` 强制转换语法（PAR_DEPRECATED_CAST_SYNTAX）的运行时路径。

    解析器不再生成此节点类型；此 handler 作为防御性兜底保留。
    segments 为字面字符串与 ext_ref dicts，不含子表达式 UID，故无需 yield。
    逻辑与 ExprHandler.visit_IbBehaviorInstance 完全对应，但走 VM 路径。
    """
    if False:
        yield
    segments = node_data.get("segments", [])
    target_type_name = node_data.get("target_type_name", "")

    intent_content_parts = []
    for seg in segments:
        if isinstance(seg, str):
            intent_content_parts.append(seg)
        elif isinstance(seg, dict) and seg.get("_type") == "ext_ref":
            intent_content_parts.append(executor.ec.get_asset(seg.get("uid", "")))
        elif hasattr(seg, "to_native"):
            intent_content_parts.append(str(seg.to_native()))
        else:
            intent_content_parts.append(str(seg))
    intent_content = "".join(intent_content_parts)

    intent_class = executor.registry.get_class("Intent")
    if intent_class:
        call_intent = IbIntent(ib_class=intent_class, content=intent_content, mode=IntentMode.APPEND)
    else:
        call_intent = None

    target_descriptor = executor.ec.get_side_table("node_to_type", node_uid)
    if not target_descriptor and target_type_name:
        meta_reg = executor.registry.get_metadata_registry()
        if meta_reg:
            target_descriptor = meta_reg.resolve(target_type_name)

    sc = executor.service_context
    llm_exec = sc.llm_executor if sc is not None else None
    if llm_exec is None:
        executor.runtime_context.set_last_llm_result(None)
        return executor.registry.get_none()

    result = llm_exec.execute_behavior_expression(node_uid, executor.ec, call_intent=call_intent)
    executor.runtime_context.set_last_llm_result(result)

    if not result or not result.value:
        return executor.registry.get_none()

    if target_type_name:
        target_class = executor.registry.get_class(target_type_name)
        if target_class:
            return target_class.receive("__call__", [result.value])

    return result.value


def vm_handle_IbLambdaExpr(executor, node_uid: str, node_data: Mapping[str, Any]):
    """lambda / snapshot 表达式：构造 ``IbFnCallable`` 或 ``IbBehavior``（公理 SC-3/SC-4）。

    自由变量列表 ``free_vars`` 由 ``semantic_analyzer.visit_IbLambdaExpr`` 在 Pass 4
    末尾写入并序列化到 artifact node_data，运行时无需再走访 AST。

    闭包语义
    --------
    * **lambda**：自由变量通过共享 ``IbCell`` 捕获（SC-4）。调用时 deref 当前最新值，
      不拷贝任何内容；外层后续对该变量的赋值/突变在调用时可见。
    * **snapshot**：定义时对每个自由变量做**深克隆**作为只读「种子」存入 closure。
      调用路径（``_vm_call_fn_callable`` / ``_vm_invoke_behavior``）会在每次调用前
      对种子再做一次深克隆，作为该次调用的私有副本注入子作用域——确保 snapshot
      作为**无状态、可重入**的可调用实例存在，多次调用之间彼此独立。

    body 节点在 lambda 被调用时才执行，此处无需 yield——handler 为 generator
    function（``if False: yield``）满足 VMExecutor 调度协议。
    """
    if False:
        yield
    params_uids: List[str] = list(node_data.get("params") or [])
    body_uid = node_data.get("body")
    capture_mode = node_data.get("capture_mode") or "lambda"
    free_vars = node_data.get("free_vars") or []  # [[name, sym_uid], ...]

    body_data = executor.ec.get_node_data(body_uid) if body_uid else None
    body_is_behavior = bool(body_data) and body_data.get("_type") == "IbBehaviorExpr"

    # 根据编译期收集的自由变量列表构建 closure。
    # closure[sym_uid] = (name, slot) 其中 slot 的类型由 capture_mode 决定：
    #   - lambda   → IbCell（共享引用，调用时读最新值）
    #   - snapshot → 深克隆后的 IbObject 种子（不可被外层突变影响）
    closure: Dict[str, Any] = {}
    if free_vars:
        current_scope = executor.runtime_context.current_scope
        for name, sym_uid in free_vars:
            if sym_uid in closure:
                continue
            if capture_mode == "snapshot":
                # snapshot：定义时刻对自由变量做一次深克隆，作为只读种子。
                # 不可克隆的值（如函数引用）退回保留原引用——这类对象本身就是
                # 不可变身份对象，不存在「外部突变泄漏」风险。
                try:
                    val = current_scope.get_by_uid(sym_uid)
                except (KeyError, AttributeError):
                    val = None
                if val is not None:
                    frozen = try_deep_clone(val)
                    closure[sym_uid] = (name, frozen if frozen is not None else val)
            else:
                # lambda：共享 IbCell（promote_to_cell 返回 None 表示全局变量，SC-4）
                cell = current_scope.promote_to_cell(sym_uid)
                if cell is not None:
                    closure[sym_uid] = (name, cell)

    if body_is_behavior:
        captured_intents = (
            None if capture_mode == "lambda"
            else executor.runtime_context.fork_intent_snapshot()
        )
        expected_type = executor.ec.get_side_table("node_to_type", body_uid)
        return executor.service_context.object_factory.create_behavior(
            body_uid,
            captured_intents,
            expected_type=expected_type,
            capture_mode=capture_mode,
            execution_context=executor.ec,
            params_uids=params_uids,
            closure=closure,
        )

    return executor.service_context.object_factory.create_fn_callable(
        node_uid,
        capture_mode=capture_mode,
        execution_context=executor.ec,
        params_uids=params_uids,
        body_uid=body_uid,
        closure=closure,
    )


def vm_handle_IbRetry(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``retry`` 语句：与 StmtHandler.visit_IbRetry 同语义。

    1. 求值可选的 retry hint，写入 ``runtime_context.retry_hint``
    2. 设置 ``frame.should_retry = True``，由外层 llmexcept handler 重新执行 target

    注意：状态恢复（restore_snapshot）由外层 ``vm_handle_IbLLMExceptionalStmt``
    在下一次迭代开始时统一执行，避免同一轮 retry 中出现冗余的双重 restore 调用。
    """
    hint_uid = node_data.get("hint")
    hint_val: Optional[str] = None
    if hint_uid:
        hint_obj = yield hint_uid
        hint_val = hint_obj.to_native() if hasattr(hint_obj, "to_native") else str(hint_obj)
    executor.runtime_context.retry_hint = hint_val
    frame = executor.runtime_context.get_current_llm_except_frame()
    if frame is not None:
        frame.should_retry = True
    return executor.registry.get_none()
