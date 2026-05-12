"""
LLM 异常处理现场帧 (LLMExceptFrame)。

本模块定义了 LLMExceptFrame 类，用于管理 llmexcept/retry 机制的轻量级现场状态。
当前实现采用"影子执行驱动模式"（非异常驱动）：LLM 不确定性通过 LLMResult.is_uncertain
标志位传递，不再抛出任何异常。

核心设计思想（快照隔离模型）:
1. 状态化:   重试相关的所有状态都集中在一个帧对象中
2. 快照隔离: 每次 LLM 语句执行进入独立快照（vars/intent_ctx/loop_ctx），retry 前
             自动 restore_snapshot()，保证 LLM 始终看到一致的输入状态
3. 可追踪:   记录重试次数、最后 LLM 结果等调试信息

使用方式（影子执行驱动，由 visit_IbLLMExceptionalStmt 主控）:
    # 1. 保存快照（save_llm_except_state 内部调用 frame.save_context()）
    frame = runtime_context.save_llm_except_state(target_uid, node_type, max_retry)

    # 2. 驱动循环
    while frame.should_continue_retrying():
        frame.restore_snapshot(runtime_context)           # 恢复快照
        runtime_context.set_last_llm_result(None)         # 清除上次信号
        execution_context.visit(target_uid)               # 驱动 LLM 节点执行

        result = runtime_context.get_last_llm_result()
        if result is None or result.is_certain:
            break                                          # 成功，commit 到目标变量

        # LLM 返回不确定（is_uncertain=True）
        for stmt_uid in body_uids:                         # 执行 llmexcept body
            visit(stmt_uid)
        if not frame.increment_retry():
            break                                          # 重试耗尽

    # 3. 清理
    runtime_context.pop_llm_except_frame()

Author: IBCI Development Team
Status: Active
"""

from typing import Any, Dict, Optional, List, TYPE_CHECKING
from dataclasses import dataclass, field
from core.runtime.objects.kernel import IbObject, IbValue, IbNone

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
        saved_vars: 方案A深克隆变量快照 {变量名 → 克隆值}
        saved_protocol_states: 方案B用户协议快照 {变量名 → (原始对象, __snapshot__()返回值)}
        saved_intent_ctx: 重试前保存的意图上下文快照（IbIntentContext.fork()）
        saved_loop_context: 重试前保存的循环上下文
        saved_retry_hint: 重试前保存的提示词
        last_error: 最后一次捕获的异常
        last_llm_response: 最后一次 LLM 响应
        is_in_fallback: 是否正在执行 fallback 块
        should_retry: 是否应该继续重试

    快照策略（方案B优先，方案A兜底）:
        若用户 IBCI 类定义了 ``func __snapshot__(self)`` 和 ``func __restore__(self, state)``，
        llmexcept 帧优先使用该协议：在进入帧时调用 ``__snapshot__()``，
        在每次 retry 前调用 ``__restore__(state)`` 原地恢复对象状态。
        用户对快照粒度拥有完全控制权（可以只保存关键字段）。

        对于未定义 ``__snapshot__`` 的类型，自动使用方案A（``_try_deep_clone``）。
    """
    
    # 基本信息
    target_uid: str = ""
    node_type: str = ""
    
    # 重试状态
    retry_count: int = 0
    max_retry: int = 3
    saved_retry_hint: Optional[str] = None
    
    # 上下文快照
    saved_vars: Dict[str, IbObject] = field(default_factory=dict)
    saved_intent_ctx: Any = field(default=None, repr=False)    # IbIntentContext 快照
    # retry 时需要同时还原帧级活跃 intent_context IBCI 实例指针，
    # 否则 llmexcept body 内部对意图策略的切换（``use(ctx)``/``clear_inherited()``）
    # 在 retry 后仍会"残留"于活跃指针，造成与 ``_intent_ctx`` 的双轨断裂。
    saved_active_intent_ibobj: Any = field(default=None, repr=False)
    saved_loop_context: Optional[Dict[str, int]] = None

    # 循环迭代器断点恢复索引
    # 映射: for 循环节点 UID → 当次重试应从哪个迭代索引开始。
    # 此字段由 visit_IbFor 在每次迭代开始时动态更新，
    # restore_context() 故意 **不** 重置它，使得 retry 后 for 循环
    # 能从失败的迭代处继续，而不是从头开始。
    loop_resume: Dict[str, int] = field(default_factory=dict)

    # 方案B：用户协议快照（__snapshot__ / __restore__）
    # 映射: 变量名 → (原始对象引用, __snapshot__() 返回的状态对象)
    # 当用户 IBCI 类定义了 func __snapshot__ / func __restore__，此字段优先于方案A（_try_deep_clone）。
    saved_protocol_states: Dict[str, Any] = field(default_factory=dict)
    
    # 错误信息
    last_error: Optional[Exception] = None
    last_llm_response: Optional[str] = None
    last_result: Optional[Any] = None  # LLMResult 对象
    # 重试错误历史，按发生顺序追加。
    # 每项结构：
    #   {
    #       "retry_count": int,
    #       "error_type": str,
    #       "error_message": str,
    #       "response": Optional[str],
    #   }
    error_history: List[Dict[str, Any]] = field(default_factory=list)
    
    # 状态标志
    is_in_fallback: bool = False
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
        if hasattr(runtime_context, "get_active_intent_ibobj"):
            self.saved_active_intent_ibobj = runtime_context.get_active_intent_ibobj()

        if hasattr(runtime_context, '_loop_stack') and runtime_context._loop_stack:
            # 深拷贝 dict 对象，确保保存的快照与运行时 _loop_stack 完全独立，
            # 即使 (将来) 循环上下文 dict 被就地修改，也不影响快照的正确性。
            self.saved_loop_context = {
                'iterators': [dict(d) for d in runtime_context._loop_stack]
            }

        if hasattr(runtime_context, 'retry_hint'):
            self.saved_retry_hint = runtime_context.retry_hint

    def _save_vars_snapshot(self, runtime_context: 'RuntimeContextImpl') -> None:
        """
        保存当前作用域的变量快照。

        查找顺序（每个变量独立决策）：

        **方案B（用户协议，优先）**：
        - 目标类型为用户自定义 IbObject 且 vtable 中定义了 `func __snapshot__(self)`
        - 调用 `obj.__snapshot__()` 获取状态对象（可以是任意类型）
        - 存入 `saved_protocol_states`；`_restore_vars` 时调用 `__restore__(state)` 原地恢复
        - 如果 `__snapshot__` 调用出现异常，自动降级到方案A

        **方案A（自动深克隆，回退）**：
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

        from core.runtime.objects.kernel import IbObject as KernelIbObject

        for name, symbol in scope.get_all_symbols().items():
            val = symbol.value

            # 方案B 优先：用户类定义了 __snapshot__ / __restore__ 协议方法
            if type(val) is KernelIbObject:
                snapshot_method = val.ib_class.lookup_method('__snapshot__')
                if snapshot_method:
                    try:
                        state = snapshot_method.call(val, [])
                        self.saved_protocol_states[name] = (val, state)
                        continue  # 跳过方案A克隆
                    except Exception:
                        pass  # 协议调用失败，降级到方案A

            # 方案A：自动深克隆
            cloned = self._try_deep_clone(val)
            if cloned is not None:
                self.saved_vars[name] = cloned

    def _try_deep_clone(self, val: 'IbObject', memo: Optional[Dict[int, 'IbObject']] = None) -> Optional['IbObject']:
        """
        尝试深克隆一个 IbObject 实例（用于 llmexcept 快照）。

        实际逻辑下沉到 ``core.runtime.objects.deep_clone.try_deep_clone``，
        与 snapshot lambda 路径共用同一深克隆实现。
        """
        from core.runtime.objects.deep_clone import try_deep_clone
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
            runtime_context._intent_ctx = forked
            # 同步重建活跃实例指针：保留命名身份（ib_class），但 _ctx 指向新底层。
            if hasattr(runtime_context, "_set_active_intent_ibobj_for_current_ctx"):
                intent_context_class = None
                saved_ibobj = self.saved_active_intent_ibobj
                if saved_ibobj is not None and hasattr(saved_ibobj, "ib_class"):
                    intent_context_class = saved_ibobj.ib_class
                else:
                    registry = getattr(runtime_context, "_registry", None)
                    if registry is not None and hasattr(registry, "get_class"):
                        intent_context_class = registry.get_class("intent_context")
                if intent_context_class is not None:
                    runtime_context._set_active_intent_ibobj_for_current_ctx(intent_context_class)
                else:
                    runtime_context.set_active_intent_ibobj(None)

        if hasattr(runtime_context, '_loop_stack') and self.saved_loop_context:
            runtime_context._loop_stack = self.saved_loop_context.get('iterators', [])

        if hasattr(runtime_context, 'retry_hint'):
            runtime_context.retry_hint = self.saved_retry_hint

        # 注意：loop_resume 字段故意不在此处重置。
        # visit_IbFor 依赖 loop_resume[node_uid] 来判断 retry 后应从哪个迭代索引继续，
        # 如果此处清零，for 循环将重头开始，失去断点恢复能力。

    def _restore_vars(self, runtime_context: 'RuntimeContextImpl') -> None:
        """
        恢复变量快照。

        恢复顺序：

        **方案B（用户协议，原地恢复）**：
        - 遍历 `saved_protocol_states`，找到对应变量的原始对象引用
        - 若变量槽已被替换为其他对象，先将变量重新指向原始对象
        - 调用 `original_obj.__restore__(saved_state)` 原地恢复字段状态
        - 若 `__restore__` 未定义或调用失败，保留当前状态（最佳努力语义）

        **方案A（替换绑定）**：
        - 遍历 `saved_vars`（深克隆副本），将变量槽替换为克隆副本
        - 只恢复已存在的变量（通过 assign）；不存在的变量直接跳过

        注意：`loop_resume` 字段故意不在此处重置，以便 retry 后 for 循环从断点处继续。
        """
        scope = runtime_context.get_current_scope()

        # 方案B：通过 __restore__ 协议原地恢复用户对象
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
                    except Exception:
                        pass  # 协议调用失败：保留当前状态（最佳努力）

        # 方案A：每次恢复时从黄金快照重新深克隆，防止上一轮 llmexcept body 修改了快照对象
        for name, val in self.saved_vars.items():
            symbol = scope.get_symbol(name)
            if symbol and not symbol.is_const:
                fresh = self._try_deep_clone(val)
                scope.assign(name, fresh if fresh is not None else val)
    
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
    
    def set_error(self, error: Exception, response: Optional[str] = None) -> None:
        """
        设置错误信息。
        
        参数:
            error: 捕获的异常
            response: LLM 的原始响应 (如果有)
        """
        self.last_error = error
        self.last_llm_response = response
        self.error_history.append({
            "retry_count": self.retry_count,
            "error_type": type(error).__name__,
            "error_message": str(error),
            "response": response,
        })
    
    def reset_for_retry(self) -> None:
        """
        重置状态以准备下一次重试。

        设计注：会清除 ``last_error``/``last_llm_response``（当前尝试状态），
        但保留 ``error_history`` 作为跨重试可追踪历史。
        """
        self.last_error = None
        self.last_llm_response = None
        self.should_retry = True
    
    def get_retry_info(self) -> Dict[str, Any]:
        """
        获取重试信息的摘要。
        
        用于调试和日志记录。
        
        返回:
            包含重试相关信息的字典
        """
        return {
            'target_uid': self.target_uid,
            'node_type': self.node_type,
            'retry_count': self.retry_count,
            'max_retry': self.max_retry,
            'should_retry': self.should_retry,
            'has_error': self.last_error is not None,
            'error_type': type(self.last_error).__name__ if self.last_error else None,
            'error_message': str(self.last_error) if self.last_error else None,
            'error_history_count': len(self.error_history),
            'error_history': list(self.error_history),
        }
    
    def __repr__(self) -> str:
        return (
            f"LLMExceptFrame(target={self.target_uid}, "
            f"type={self.node_type}, "
            f"retry={self.retry_count}/{self.max_retry}, "
            f"should_retry={self.should_retry})"
        )


class LLMExceptFrameStack:
    """
    LLM 异常处理帧栈。
    
    用于管理嵌套的 llmexcept 块。
    在复杂场景下，可能会有多层嵌套的 llmexcept，
    帧栈确保每个层级都有独立的现场状态。

    支持最大嵌套深度限制，防止异常情况下的无界增长。
    """
    
    DEFAULT_MAX_DEPTH = 128

    def __init__(self, max_depth: int = DEFAULT_MAX_DEPTH):
        self._frames: List[LLMExceptFrame] = []
        self._max_depth = max_depth
    
    def push(self, frame: LLMExceptFrame) -> None:
        """压入一个新帧"""
        if len(self._frames) >= self._max_depth:
            raise RuntimeError(
                f"LLMExceptFrameStack overflow: max depth {self._max_depth} exceeded"
            )
        self._frames.append(frame)
    
    def pop(self) -> Optional[LLMExceptFrame]:
        """弹出栈顶帧"""
        if self._frames:
            return self._frames.pop()
        return None
    
    def peek(self) -> Optional[LLMExceptFrame]:
        """查看栈顶帧但不弹出"""
        if self._frames:
            return self._frames[-1]
        return None
    
    def is_empty(self) -> bool:
        """检查栈是否为空"""
        return len(self._frames) == 0
    
    def size(self) -> int:
        """返回栈的大小"""
        return len(self._frames)

    @property
    def max_depth(self) -> int:
        """返回帧栈允许的最大嵌套深度"""
        return self._max_depth
    
    def clear(self) -> None:
        """清空栈"""
        self._frames.clear()
    
    def __repr__(self) -> str:
        return f"LLMExceptFrameStack(size={len(self._frames)})"
