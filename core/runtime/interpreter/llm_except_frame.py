"""
LLM 异常处理现场帧 (LLMExceptFrame)。

本模块定义了 LLMExceptFrame 类，用于管理 llmexcept/retry 机制的轻量级现场状态。
当前实现采用"影子执行驱动模式"（非异常驱动）：LLM 不确定性通过 LLMResult.is_uncertain
标志位传递，不再抛出任何异常。

核心设计思想（快照隔离模型）:
1. 状态化:   重试相关的所有状态都集中在一个帧对象中
2. 快照隔离: 帧创建时保存一次快照（save_context），retry 时还原，保证
             LLM 始终看到一致的输入状态
3. 可追踪:   记录重试次数、最后 LLM 结果等调试信息

快照/恢复调用规则:
    - ``__snapshot__()``：帧创建时调用**一次**（save_context 内部）
    - ``__restore__(state)``：**仅在 retry 时**调用，且**每轮 retry 恰好一次**。
      首次迭代不调用（刚 save_context 完成，状态一致）。
    - ``retry`` 语句本身**不**调用 restore_snapshot（只设置 should_retry 标志），
      restore 统一由外层 while 循环顶部执行，消除冗余双重 restore。

使用方式（消费者驱动，由各被保护语句 handler 主控）:
    # 1. 保存快照（save_llm_except_state 内部调用 frame.save_context()）
    frame = runtime_context.save_llm_except_state(target_uid, node_type, max_retry)

    # 2. 驱动循环（见 vm/handlers/_shared._retry_llm_uncertain）
    frame.target_result = uncertain_result       # 记录本次不确定结果
    first_attempt = True
    while frame.should_continue_retrying():
        if not first_attempt:
            frame.restore_snapshot(runtime_context)     # retry 前恢复快照
            value = yield re_eval_uid                   # 重新求值被保护表达式
            if 值确定: break
            frame.target_result = value
        first_attempt = False
        # 执行 llmexcept body（retry 语句设 should_retry / retry_hint）
        if not frame.increment_retry():
            raise LLMRetryExhaustedError

    # 3. 清理
    runtime_context.pop_llm_except_frame()

Author: IBCI Development Team
Status: Active
"""

from typing import Any, Dict, Optional, List, TYPE_CHECKING
from dataclasses import dataclass, field
from core.runtime.objects.kernel import IbObject, IbValue, IbNone, IbLLMCallResult
from core.runtime.objects.kernel.base import unbox
from core.runtime.objects.kernel.ib_class import IbClass
from core.runtime.objects.deep_clone import try_deep_clone
from core.runtime.observability.diagnostics import kernel_diagnostic
from core.base.diagnostics.codes import (
    KDIAG_PROTOCOL_SNAPSHOT_FALLBACK,
    KDIAG_PROTOCOL_RESTORE_FALLBACK,
)
from core.kernel.issue import InterpreterError

if TYPE_CHECKING:
    from core.runtime.interpreter.runtime_context import RuntimeContextImpl, RuntimeSymbol


@dataclass
class LLMExceptFrame:
    """
    LLM 异常处理的现场帧。

    用于保存和恢复 llmexcept 块的执行状态，实现清晰、可追踪的重试逻辑。

    字段说明:
        target_uid: LLM 调用节点的唯一标识符
        node_type: 节点类型 (如 "IbIf", "IbExprStmt" 等)
        retry_count: 当前重试次数
        max_retry: 最大重试次数 (默认 3)
        saved_vars: 深克隆变量快照 {变量名 → 克隆值}
        saved_protocol_states: 用户协议快照 {变量名 → (原始对象, __snapshot__()返回值)}
        saved_intent_ctx: 重试前保存的意图上下文快照（IbIntentContext.fork()）
        saved_loop_context: 重试前保存的循环上下文
        saved_retry_hint: 重试前保存的提示词
        should_retry: 是否应该继续重试

    快照策略（用户协议优先，深克隆兜底）:
        若用户 IBCI 类定义了 ``func __snapshot__(self)`` 和 ``func __restore__(self, state)``，
        llmexcept 帧优先使用该协议：在进入帧时调用 ``__snapshot__()``，
        在每次 retry 前调用 ``__restore__(state)`` 原地恢复对象状态。
        用户对快照粒度拥有完全控制权（可以只保存关键字段）。

        对于未定义 ``__snapshot__`` 的类型，自动使用深克隆（``_try_deep_clone``）。
    """
    
    # 基本信息
    target_uid: str = ""
    node_type: str = ""
    
    # 重试状态
    retry_count: int = 0
    max_retry: int = 3
    retry_hint: Optional[str] = None  # 持续覆盖，不参与 save/restore（retry "hint" 写入，跨轮次存活）
    
    # 上下文快照
    saved_vars: Dict[str, IbObject] = field(default_factory=dict)
    saved_intent_ctx: Any = field(default=None, repr=False)    # IbIntentContext 快照
    # retry 时需要同时还原帧级活跃 intent_context IBCI 实例指针，
    # 否则 llmexcept body 内部对意图策略的切换（``use(ctx)``/``clear_inherited()``）
    # 在 retry 后仍会"残留"于活跃指针，造成与 ``_intent_ctx`` 的双轨断裂。
    saved_active_intent_ibobj: Any = field(default=None, repr=False)
    saved_loop_context: Optional[List[Dict[str, int]]] = None

    # 循环迭代器断点恢复索引
    # 映射: for 循环节点 UID → 当次重试应从哪个迭代索引开始。
    # 此字段由 visit_IbFor 在每次迭代开始时动态更新，
    # restore_context() 故意 **不** 重置它，使得 retry 后 for 循环
    # 能从失败的迭代处继续，而不是从头开始。
    loop_resume: Dict[str, int] = field(default_factory=dict)

    # 用户协议快照（__snapshot__ / __restore__）
    # 映射: 变量名 -> (原始对象引用, __snapshot__() 返回的状态对象)
    # 当用户 IBCI 类定义了 func __snapshot__ / func __restore__，此字段优先于深克隆（_try_deep_clone）。
    saved_protocol_states: Dict[str, Any] = field(default_factory=dict)
    
    target_result: Optional[Any] = None  # 最近一次不确定调用的 IbLLMCallResult（certainty 信号载体）
    # 失败尝试历史（标准多轮重试对话用）。每项：
    #   {"raw_response": 上次原始响应, "parse_error": 解析错误, "user_hint": 下一轮用户补充要求}
    # 由 _retry_llm_uncertain 在每轮 handler body 执行后、下一轮重试前记录。
    attempt_history: List[Dict[str, Any]] = field(default_factory=list)

    def record_uncertain_attempt(self) -> None:
        """把当前不确定调用记录进重试历史（多轮对话的 assistant 输出 + 下一轮纠错）。"""
        if isinstance(self.target_result, IbLLMCallResult) and self.target_result.is_uncertain:
            self.attempt_history.append({
                "raw_response": self.target_result.raw_response or "",
                "parse_error": self.target_result.retry_hint or None,
                "user_hint": self.retry_hint,
            })

    # 状态标志
    should_retry: bool = True
    
    def save_context(self, runtime_context: 'RuntimeContextImpl') -> None:
        """
        从运行时上下文保存现场。

        保存以下状态:
        - 当前变量快照 (只保存可序列化类型)
        - 意图栈
        - 循环上下文
        - retry_hint

        参数:
            runtime_context: 运行时上下文对象
        """
        self._save_vars_snapshot(runtime_context)

        self.saved_intent_ctx = runtime_context.intent_context.fork()
        # 同时快照活跃实例指针，restore 时一并还原。
        self.saved_active_intent_ibobj = runtime_context.get_active_intent_ibobj()

        if runtime_context.get_loop_context_stack():
            self.saved_loop_context = runtime_context.get_loop_context_stack()

    def _save_vars_snapshot(self, runtime_context: 'RuntimeContextImpl') -> None:
        """
        保存当前作用域的变量快照。

        查找顺序（每个变量独立决策）：

        **用户协议，优先**：
        - 目标类型为用户自定义 IbObject 且 vtable 中定义了 `func __snapshot__(self)`
        - 调用 `obj.__snapshot__()` 获取状态对象（可以是任意类型）
        - 存入 `saved_protocol_states`；`_restore_vars` 时调用 `__restore__(state)` 原地恢复
        - 如果 `__snapshot__` 调用出现异常，自动降级到深克隆

        **自动深克隆，回退**：
        - None 及标量类型（int/float/str/bool）—— 不可变原语，直接共享引用
        - list/tuple —— 递归深克隆所有元素
        - dict —— 递归深克隆所有键值对
        - 用户自定义 IbObject（递归克隆所有字段，无法克隆的字段跳过）

        **不可快照的类型（跳过）**：
        - fn / behavior / fn_callable（可调用对象）
        - NativeObject（Python 原生封装）
        """
        self.saved_vars = {}
        self.saved_protocol_states = {}
        scope = runtime_context.get_current_scope()

        for name, symbol in scope.get_all_symbols().items():
            val = symbol.value

            # 跳过类型/类符号（值为 IbClass 的类对象）——类对象是类型元数据，
            # 非受保护的可变实例状态；且若类声明了 __snapshot__/__restore__
            # 协议方法，快照会把类对象误当协议变量捕获（__restore__ 以类为
            # receiver 调用，参数绑定类型检查失败暴露）。只快照真实实例/值。
            if isinstance(val, IbClass):
                continue

            # 优先：用户类定义了 __snapshot__ / __restore__ 协议方法
            # isinstance（非 type() is）确保 IbObject 子类（如未来的 IbAudio/IbImage）也能匹配；
            # 但需要 val.ib_class 存在才能查找方法
            if isinstance(val, IbObject) and val.ib_class:
                snapshot_method = val.ib_class.lookup_method('__snapshot__')
                if snapshot_method:
                    try:
                        state = snapshot_method.call(val, [])
                        self.saved_protocol_states[name] = (val, state)
                        continue  # 跳过克隆
                    except Exception as e:
                        kernel_diagnostic(
                            code=KDIAG_PROTOCOL_SNAPSHOT_FALLBACK,
                            detail={"name": name, "error": repr(e)},
                            message=(
                                f"__snapshot__ protocol call failed for '{name}', "
                                f"falling back to deep clone: {e!r}"
                            ),
                        )

            # 自动深克隆
            cloned = self._try_deep_clone(val)
            if cloned is not None:
                self.saved_vars[name] = cloned

    def _try_deep_clone(self, val: 'IbObject', memo: Optional[Dict[int, 'IbObject']] = None) -> Optional['IbObject']:
        """
        尝试深克隆一个 IbObject 实例（用于 llmexcept 快照）。

        实际逻辑下沉到 ``core.runtime.objects.deep_clone.try_deep_clone``，
        与 snapshot lambda 路径共用同一深克隆实现。
        """
        return try_deep_clone(val, memo)

    def restore_context(self, runtime_context: 'RuntimeContextImpl') -> None:
        """
        恢复到保存的现场。

        恢复以下状态:
        - 变量（只恢复已存在的变量）
        - 意图上下文（直接以快照的 fork 副本替换 ``_intent_ctx``，并同步
          重建活跃 intent_context IBCI 实例指针使其与新 ``_intent_ctx`` 共享引用）
        - 循环上下文
        - retry_hint

        意图上下文恢复说明：
            原实现使用 ``intent_context.merge(saved)``，会将 retry body 内
            对全局/排他/涂抹槽的修改"叠加"到恢复结果上；新实现采用
            ``_intent_ctx = saved.fork()`` 替换语义，保证 retry 看到的是
            llmexcept 进入时刻完全一致的意图快照，与 vars/loop_context 的恢复
            语义对齐（均为干净还原）。同时活跃实例指针被重建：若原帧持有
            命名策略，则同步指向新底层；若原帧匿名，则建立新的匿名封装。
        """
        self._restore_vars(runtime_context)

        if self.saved_intent_ctx is not None:
            # 直接以快照 fork 替换 ``_intent_ctx``（取代 ``merge()``）。
            forked = self.saved_intent_ctx.fork()
            runtime_context.replace_intent_context(forked)

        if self.saved_loop_context is not None:
            runtime_context.restore_loop_context_stack(self.saved_loop_context)

        # 注意：loop_resume 字段故意不在此处重置。
        # visit_IbFor 依赖 loop_resume[node_uid] 来判断 retry 后应从哪个迭代索引继续，
        # 如果此处清零，for 循环将重头开始，失去断点恢复能力。

    def _restore_vars(self, runtime_context: 'RuntimeContextImpl') -> None:
        """
        恢复变量快照。

        恢复顺序：

        **用户协议，原地恢复**：
        - 遍历 `saved_protocol_states`，找到对应变量的原始对象引用
        - 若变量槽已被替换为其他对象，先将变量重新指向原始对象
        - 调用 `original_obj.__restore__(saved_state)` 原地恢复字段状态
        - 若 `__restore__` 未定义或调用失败，保留当前状态（最佳努力语义）

        **替换绑定**：
        - 遍历 `saved_vars`（深克隆副本），将变量槽替换为克隆副本
        - 只恢复已存在的变量（通过 assign）；不存在的变量直接跳过

        注意：`loop_resume` 字段故意不在此处重置，以便 retry 后 for 循环从断点处继续。
        """
        scope = runtime_context.get_current_scope()

        # 通过 __restore__ 协议原地恢复用户对象
        for name, (original_obj, saved_state) in self.saved_protocol_states.items():
            symbol = scope.get_symbol(name)
            if symbol and not symbol.is_const:
                restore_method = original_obj.ib_class.lookup_method('__restore__')
                if restore_method:
                    # 如果变量槽被替换为其他对象，先恢复原始对象引用
                    if symbol.value is not original_obj:
                        scope.assign(name, original_obj)
                    try:
                        restore_method.call(original_obj, [saved_state])
                    except Exception as e:
                        kernel_diagnostic(
                            code=KDIAG_PROTOCOL_RESTORE_FALLBACK,
                            detail={"name": name, "error": repr(e)},
                            message=(
                                f"__restore__ protocol call failed for '{name}', "
                                f"keeping current state (best-effort): {e!r}"
                            ),
                        )

        # 每次恢复时从黄金快照重新深克隆，防止上一轮 llmexcept body 修改了快照对象
        for name, val in self.saved_vars.items():
            symbol = scope.get_symbol(name)
            if symbol and not symbol.is_const:
                fresh = self._try_deep_clone(val)
                if fresh is None:
                    raise InterpreterError(
                        f"Cannot re-clone variable '{name}' from golden snapshot during retry. "
                        f"This indicates an environment change that invalidates the snapshot."
                    )
                scope.assign(name, fresh)
    
    def increment_retry(self) -> bool:
        """
        递增重试计数并返回是否允许继续重试。

        返回:
            True 如果还可以继续重试
            False 如果已达到最大重试次数
        """
        self.retry_count += 1
        self.should_retry = self.retry_count < self.max_retry
        return self.should_retry

    def verify_snapshot_integrity(self, runtime_context: 'RuntimeContextImpl') -> list:
        """校验 llmexcept body 执行后被保护变量是否被篡改。

        比对当前作用域中的变量值与黄金快照。返回被篡改的变量名列表。
        调用方负责发出 WARNING 并在下一轮 retry 前强制恢复。
        """
        violations = []
        scope = runtime_context.get_current_scope()
        for name, golden_val in self.saved_vars.items():
            symbol = scope.get_symbol(name)
            if symbol is None:
                continue
            current_val = symbol.value
            if current_val is golden_val:
                continue
            if not self._values_equal(current_val, golden_val):
                violations.append(name)
        return violations

    def _values_equal(self, a, b) -> bool:
        """浅层值比较：对 IbValue 使用 to_native()，否则用 identity/==。

        值比较降级链路（llmexcept 篡改完整性校验的最后一环，设计机制）：
        1. 正常路径：原生值 ``==`` 比较；
        2. 降级路径：``==`` 抛异常（自定义对象 ``__eq__`` 故障 / 类型不可比较）
           → 保守判定"不相等"（返回 False）。这是有意的 fail-safe 方向：
           完整性校验宁可误报篡改而触发恢复，也不可漏报。调用方对 False
           一律视为"被篡改"。（调用方在进入本方法前已排除同对象恒等情况。）
        """
        a_native = unbox(a)
        b_native = unbox(b)
        try:
            return a_native == b_native
        except Exception:
            return False

    def should_continue_retrying(self) -> bool:
        """
        判断是否应该继续重试。

        返回:
            True 如果 should_retry=True 且 retry_count < max_retry
        """
        return self.should_retry and self.retry_count < self.max_retry

    def save_snapshot(self, runtime_context: 'RuntimeContextImpl') -> None:
        """save_context 的别名，用于代码可读性"""
        self.save_context(runtime_context)

    def restore_snapshot(self, runtime_context: 'RuntimeContextImpl') -> None:
        """restore_context 的别名，用于代码可读性"""
        self.restore_context(runtime_context)
    
    def __repr__(self) -> str:
        return (
            f"LLMExceptFrame(target={self.target_uid}, "
            f"type={self.node_type}, "
            f"retry={self.retry_count}/{self.max_retry}, "
            f"should_retry={self.should_retry})"
        )


