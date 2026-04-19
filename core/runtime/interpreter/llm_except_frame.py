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
from core.runtime.objects.kernel import IbObject, IbNone

if TYPE_CHECKING:
    from core.runtime.interpreter.runtime_context import RuntimeContextImpl, RuntimeSymbol
    from core.runtime.objects.builtins import IbInteger, IbFloat, IbString, IbList, IbDict


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
        saved_vars: 重试前保存的变量快照
        saved_intent_ctx: 重试前保存的意图上下文快照（IbIntentContext.fork()）
        saved_loop_context: 重试前保存的循环上下文
        saved_retry_hint: 重试前保存的提示词
        last_error: 最后一次捕获的异常
        last_llm_response: 最后一次 LLM 响应
        is_in_fallback: 是否正在执行 fallback 块
        should_retry: 是否应该继续重试
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
    saved_loop_context: Optional[Dict[str, int]] = None

    # 循环迭代器断点恢复索引
    # 映射: for 循环节点 UID → 当次重试应从哪个迭代索引开始。
    # 此字段由 visit_IbFor 在每次迭代开始时动态更新，
    # restore_context() 故意 **不** 重置它，使得 retry 后 for 循环
    # 能从失败的迭代处继续，而不是从头开始。
    loop_resume: Dict[str, int] = field(default_factory=dict)
    
    # 错误信息
    last_error: Optional[Exception] = None
    last_llm_response: Optional[str] = None
    last_result: Optional[Any] = None  # LLMResult 对象
    
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

        可快照的类型（通过深克隆保存）：
        - IbNone, IbInteger, IbFloat, IbString（不可变原语，直接共享引用）
        - IbList, IbTuple, IbDict（递归深克隆所有元素/值）
        - 用户自定义 IbObject 实例（递归深克隆所有字段）

        不可快照的类型（跳过，不参与恢复）：
        - IbFunction / IbNativeFunction / IbBehavior（可调用对象）
        - IbNativeObject（Python 原生封装）
        - 其他无法深克隆的对象
        """
        self.saved_vars = {}
        scope = runtime_context.get_current_scope()

        for name, symbol in scope.get_all_symbols().items():
            val = symbol.value
            cloned = self._try_deep_clone(val)
            if cloned is not None:
                self.saved_vars[name] = cloned

    def _try_deep_clone(self, val: 'IbObject', memo: Optional[Dict[int, 'IbObject']] = None) -> Optional['IbObject']:
        """
        尝试深克隆一个 IbObject 实例（用于 llmexcept 快照）。

        对不可变原语（IbNone/IbInteger/IbFloat/IbString）返回原对象（无需复制）。
        对容器（IbList/IbTuple/IbDict）递归克隆所有元素/值。
        对用户自定义 IbObject 实例递归克隆所有字段。
        对函数/行为/原生对象等不可克隆类型返回 None（调用方跳过该变量）。

        memo 字典用于环形引用检测与去重。
        """
        from core.runtime.objects.builtins import IbInteger, IbFloat, IbString, IbList, IbDict, IbTuple
        from core.runtime.objects.kernel import IbObject as KernelIbObject

        if memo is None:
            memo = {}

        val_id = id(val)
        if val_id in memo:
            return memo[val_id]

        # 不可变原语：引用共享即可
        if isinstance(val, (IbNone, IbInteger, IbFloat, IbString)):
            return val

        # IbList / IbTuple：递归克隆 elements
        if isinstance(val, (IbList, IbTuple)):
            # 占位符：处理自引用列表
            new_elements: list = []
            placeholder = val.__class__(new_elements, val.ib_class)
            memo[val_id] = placeholder
            for elem in val.elements:
                cloned_elem = self._try_deep_clone(elem, memo)
                if cloned_elem is None:
                    return None  # 容器中有无法克隆的元素，放弃整个容器
                new_elements.append(cloned_elem)
            if isinstance(val, IbTuple):
                # IbTuple.elements 为 tuple（不可变），需重新赋值
                placeholder.elements = tuple(new_elements)
            return placeholder

        # IbDict：递归克隆所有键值对
        if isinstance(val, IbDict):
            new_fields: dict = {}
            placeholder_dict = IbDict(new_fields, val.ib_class)
            memo[val_id] = placeholder_dict
            for k, v in val.fields.items():
                cloned_v = self._try_deep_clone(v, memo)
                if cloned_v is None:
                    return None  # 值无法克隆，放弃整个 dict
                new_fields[k] = cloned_v
            return placeholder_dict

        # 用户自定义 IbObject 实例（type 严格为 KernelIbObject，不含内置子类）
        if type(val) is KernelIbObject:
            new_obj = KernelIbObject.__new__(KernelIbObject)
            new_obj.ib_class = val.ib_class
            new_obj.fields = {}
            memo[val_id] = new_obj
            for fname, fval in val.fields.items():
                cloned_fval = self._try_deep_clone(fval, memo)
                if cloned_fval is not None:
                    new_obj.fields[fname] = cloned_fval
                # 无法克隆的字段（如内嵌函数引用）直接跳过：恢复时保留原值
            return new_obj

        # 其他类型（函数、行为、原生对象等）：不可克隆
        return None

    def _is_serializable(self, val: IbObject) -> bool:
        """
        判断值是否可序列化（兼容旧接口，内部委托给 _try_deep_clone）。
        """
        return self._try_deep_clone(val) is not None
    
    def restore_context(self, runtime_context: 'RuntimeContextImpl') -> None:
        """
        恢复到保存的现场。

        恢复以下状态:
        - 变量（只恢复已存在的变量）
        - 意图上下文（通过 IbIntentContext.merge() 原子恢复）
        - 循环上下文
        - retry_hint
        """
        self._restore_vars(runtime_context)

        if self.saved_intent_ctx is not None:
            runtime_context.intent_context.merge(self.saved_intent_ctx)

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

        恢复策略:
        - 遍历 saved_vars（只含已深克隆的值），尝试恢复到当前作用域
        - 只恢复已存在的变量（通过 assign 方法）
        - 不存在的变量（如函数引用、行为对象）不参与快照，直接跳过

        注意：saved_vars 中的值为深克隆副本，因此不会与恢复前的引用共享状态。
        用户自定义对象的字段也会被完整回滚（前提是字段值本身可克隆）。
        适合 for 循环场景，因为迭代变量在循环开始时已定义。
        """
        scope = runtime_context.get_current_scope()

        for name, val in self.saved_vars.items():
            symbol = scope.get_symbol(name)
            if symbol and not symbol.is_const:
                scope.assign(name, val)
    
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
    
    def reset_for_retry(self) -> None:
        """
        重置状态以准备下一次重试。
        
        TODO [优先级: 中]:
            - 考虑清除 last_error 以便追踪重试历史
            - 考虑保留最后几次错误的记录
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
    
    TODO [优先级: 低]:
        - 考虑添加最大嵌套深度限制
        - 考虑添加调试用的帧历史记录
    """
    
    def __init__(self):
        self._frames: List[LLMExceptFrame] = []
    
    def push(self, frame: LLMExceptFrame) -> None:
        """压入一个新帧"""
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
    
    def clear(self) -> None:
        """清空栈"""
        self._frames.clear()
    
    def __repr__(self) -> str:
        return f"LLMExceptFrameStack(size={len(self._frames)})"
