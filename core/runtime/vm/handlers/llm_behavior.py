"""
core.runtime.vm.handlers.llm_behavior — LLM 行为 / 意图 CPS handler。
"""
from __future__ import annotations
from typing import Any, Mapping, Optional, Dict, List

from core.runtime.shared.signals import (
    Signal,
)
from core.runtime.objects.intent import IntentRole, IntentMode
from core.runtime.objects.kernel import IbObject
from core.runtime.objects.deep_clone import try_deep_clone
from core.runtime.vm.handlers._shared import (
    _vm_execute_stmt_sequence,
    _is_llm_uncertain_value,
    _make_uncertain_call_result,
    _evaluate_intent_segments_cps,
)


# === 意图操作 ===

def _capture_signature(
    executor,
    node_uid: str,
    params_uids: List[str],
    expected_type: Optional[Any],
) -> tuple:
    """从 node_to_type 侧表捕获可调用实例签名（param_types + return_type）。

    供运行时内省：``type(f)`` 签名形态与 ``f.__return_type__()``
    查询需要值自持签名。签名属值层属性（与 capture_mode / expected_type 同层），
    不落入 CALLABLE_INSTANCE 类型 spec。

    - return_type：``expected_type`` 是具体返回类型 spec 时取其 ``name``；
      否则回退读 ``node_to_type[node_uid]`` 的 ``value_type``（fn_callable[T]
      规范 spec 的载值类型）。
    - param_types：逐参数 ``node_to_type[param_uid]`` → spec ``name``。
    """
    param_types: List[str] = []
    for p_uid in params_uids:
        p_spec = executor.ec.get_side_table("node_to_type", p_uid)
        if p_spec is not None:
            param_types.append(p_spec.name)

    return_type: Optional[str] = None
    base = expected_type.get_base_name() if expected_type is not None else None
    if expected_type is not None and base not in ("fn_callable", "behavior"):
        return_type = expected_type.name
    else:
        node_spec = executor.ec.get_side_table("node_to_type", node_uid)
        value_type = getattr(node_spec, "value_type", None)
        if value_type is not None:
            return_type = value_type.canonical_name
    return param_types, return_type


def _build_intent_from_data(executor, intent_info_uid: str, intent_data: Mapping[str, Any], role) -> Any:
    """eager 求值意图段为一等值列表并构造意图对象（CPS，调用方须 ``yield from``）。"""
    values = yield from _evaluate_intent_segments_cps(
        executor.ec, intent_data.get("segments") or []
    )
    return executor.ec.factory.create_intent(
        values=values,
        mode=IntentMode.from_str(intent_data.get("mode", "+")),
        tag=intent_data.get("tag"),
        role=role,
        source_uid=intent_info_uid,
        pop_top=intent_data.get("pop_top", False),
    )


def vm_handle_IbIntentAnnotation(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``@`` / ``@!`` 单次意图注释节点的执行路径。"""
    intent_info_uid = node_data.get("intent")
    if not intent_info_uid:
        return executor.registry.get_none()
    intent_data = executor.ec.get_node_data(intent_info_uid)
    if not intent_data:
        return executor.registry.get_none()
    intent = yield from _build_intent_from_data(
        executor, intent_info_uid, intent_data, role=IntentRole.SMEAR
    )
    executor.runtime_context.activate_statement_one_shot_intent(intent)
    return executor.registry.get_none()


def vm_handle_IbIntentStackOperation(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``@+`` / ``@-`` 意图栈操作：与 StmtHandler.visit_IbIntentStackOperation 同。

    ``@-`` 按值匹配：操作数 eager 求值后经意图渲染文本（``__to_prompt__``）
    与栈内意图渲染文本比较（修复动态意图按退化字符串匹配失效）。
    """
    intent_info_uid = node_data.get("intent")
    if not intent_info_uid:
        return executor.registry.get_none()
    intent_data = executor.ec.get_node_data(intent_info_uid)
    if not intent_data:
        return executor.registry.get_none()
    mode = IntentMode.from_str(intent_data.get("mode", "+"))
    pop_top = intent_data.get("pop_top", False)
    tag = intent_data.get("tag")

    if mode == IntentMode.REMOVE:
        if pop_top:
            executor.runtime_context.pop_intent()
        elif tag:
            executor.runtime_context.remove_intent(tag=tag)
        else:
            # 按值匹配：操作数 eager 求值为值列表 → 渲染文本 → 移除匹配意图。
            operand = yield from _build_intent_from_data(
                executor, intent_info_uid, intent_data, role=IntentRole.STACK
            )
            executor.runtime_context.remove_intent(content=operand.render_text())
    else:
        intent = yield from _build_intent_from_data(
            executor, intent_info_uid, intent_data, role=IntentRole.STACK
        )
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

    直接同步执行 LLM 调用，确定时返回 ``result.value``；不确定时返回
    ``IbLLMCallResult(is_certain=False)`` 容器，由语句层消费者处理
    （llmexcept 重试或 LLMParseError）。

    注意：dispatch-before-use 路径**不**在这里触发——dispatch_eager
    由 ``vm_handle_IbAssign`` 在识别到 RHS 为本节点且 ``dispatch_eligible=True``
    时调用，避免 LLMFuture 占位符泄漏到非赋值上下文。
    """
    sc = executor.service_context

    # 提取命名模型 tag（@NAME~ 语法）用于模型路由
    target_model = node_data.get("tag", "")

    # CPS 执行：非赋值上下文内联 @~ 表达式接入 CPS——段求值 yield 嵌入外层
    # VM 帧栈、LLM 提交线程池 + yield LLMFuture 挂起让出（无同步重入/阻塞）。
    result = yield from sc.llm_executor.execute_behavior_expression_cps(
        node_uid, executor.ec, target_model=target_model,
    )
    if result is not None and result.is_uncertain:
        return _make_uncertain_call_result(
            executor.registry, result.raw_response or "", result.retry_hint or ""
        )
    if result is not None and result.value is not None:
        return result.value
    return executor.registry.get_none()


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

    body 节点在 lambda 被调用时才执行，此处为纯 return handler，
    由 VMExecutor 中央化包装为生成器。
    """
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

    # 意图冻结并入 capture_mode：snapshot 恒在定义时刻 fork 意图
    # 快照；lambda 恒不 fork（引用捕获，调用点读 live 意图——原初设计）。
    # 不再按 body_is_behavior 特判——纯 snapshot lambda（非行为体）同样冻结意图
    # （fn_callable 一路的意图栈不再"调用点 live"）。
    captured_intents = (
        executor.runtime_context.fork_intent_snapshot()
        if capture_mode == "snapshot"
        else None
    )

    if body_is_behavior:
        expected_type = executor.ec.get_side_table("node_to_type", body_uid)
        param_types, return_type = _capture_signature(
            executor, node_uid, params_uids, expected_type
        )
        return executor.service_context.object_factory.create_behavior(
            body_uid,
            captured_intents,
            expected_type=expected_type,
            capture_mode=capture_mode,
            execution_context=executor.ec,
            params_uids=params_uids,
            closure=closure,
            param_types=param_types,
            return_type=return_type,
        )

    param_types, return_type = _capture_signature(executor, node_uid, params_uids, None)
    return executor.service_context.object_factory.create_fn_callable(
        node_uid,
        capture_mode=capture_mode,
        execution_context=executor.ec,
        params_uids=params_uids,
        body_uid=body_uid,
        closure=closure,
        param_types=param_types,
        return_type=return_type,
        captured_intents=captured_intents,
    )


def vm_handle_IbRetry(executor, node_uid: str, node_data: Mapping[str, Any]):
    """``retry`` 语句：与 StmtHandler.visit_IbRetry 同语义。

    1. 求值可选的 retry hint，写入当前帧的 ``retry_hint``（持续覆盖，注入下一次
       重试的提示词）
    2. 设置 ``frame.should_retry = True``，由外层 llmexcept 重试循环重新求值被保护语句

    注意：状态恢复（restore_snapshot）由重试循环（``_retry_llm_uncertain``）在
    下一次迭代开始时统一执行，避免同一轮 retry 中出现冗余的双重 restore 调用。
    """
    hint_uid = node_data.get("hint")
    hint_val: Optional[str] = None
    if hint_uid:
        hint_obj = yield hint_uid
        hint_val = hint_obj.to_native() if isinstance(hint_obj, IbObject) else str(hint_obj)
    frame = executor.runtime_context.get_current_llm_except_frame()
    if frame is not None:
        frame.retry_hint = hint_val
        frame.should_retry = True
    return executor.registry.get_none()
