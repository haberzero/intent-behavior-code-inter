# IBCI llmexcept 机制设计文档

> 本文档定义了 IBCI (Intent-Behavior Code Interpreter) 中 `llmexcept` 机制的完整设计方案。
>
> 版本: 2.0
> 日期: 2026-04-05
> 状态: 彻底重构 - 基于 Result 模式，不再使用 Python 异常

---

## 一、设计原则

### 1.1 核心原则

```
1. llmexcept 是独立 AST 节点，不是任何语句的附属
2. LLM 执行结果通过 LLMResult 返回，不使用异常机制
3. 解释器期间通过"上下文切片"实现状态保存/恢复
4. 同级节点通过 body 列表的索引关系确定
5. for 循环回溯到"当前迭代位置"，而非循环开始
6. 保持与现有侧表设计的一致性
```

### 1.2 架构决策：Result 模式 vs 异常模式

| 特性 | 异常模式 (已废弃) | Result 模式 (当前) |
|------|------------------|-------------------|
| LLM 不确定时 | `raise LLMUncertaintyError` | `return LLMResult(uncertain=True, ...)` |
| 调用方处理 | `try/catch` | `if result.is_uncertain:` |
| 传播机制 | 栈展开 | 显式传递 |
| 调试难度 | 难以追踪 | 易于追踪 |
| 架构一致性 | 违反 IBCI 显式语义 | 符合 IBCI 显式语义 |

### 1.3 与侧表设计的关系

| 数据类型 | 存储位置 | 说明 |
|---------|----------|------|
| llmexcept 关联 | AST 节点 (IbLLMExceptionalStmt.target) | 编译期确定 |
| 语义元数据 | SideTableManager | 符号、类型、场景、意图 |
| 运行时上下文 | LLMExceptFrame | 变量快照、Intent 栈、循环上下文 |
| LLM 执行结果 | LLMResult | 显式返回值，不使用异常 |

---

## 二、架构总览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           编译期 (Semantic Analysis)                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   源文件:                                                               │
│     if @~condition~:                    ← 同级 LLM 调用                   │
│         print("yes")                   ← body                             │
│     llmexcept:                          ← 独立 llmexcept 语句              │
│         retry()                         ← body                             │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│   Pass 1-2: 正常语义分析                                                 │
│   Pass 3:  llmexcept 关联                                               │
│                                                                          │
│   关联结果: IbLLMExceptionalStmt {                                       │
│       target: "node_uid_if_xxx",      ← 指向前一个语句                     │
│       body: ["stmt_retry", ...]       ← 自己的 body                       │
│   }                                                                           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           运行时 (Interpretation)                         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   RuntimeContextImpl                                                    │
│   ├── _llm_except_frames: List[LLMExceptFrame]  ← 帧栈                   │
│   ├── _intent_top: IntentNode                  ← 意图栈                   │
│   ├── _loop_stack: List[LoopContext]           ← 循环上下文               │
│   └── _current_scope: Scope                    ← 当前作用域               │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   visit_IbLLMExceptionalStmt(node_uid, node_data):                       │
│   ┌─────────────────────────────────────────────────────────────────┐   │
│   │  1. 创建 LLMExceptFrame                                         │   │
│   │  2. 保存上下文切片 (frame.save_snapshot())                       │   │
│   │  3. 压栈: runtime_context.push_llm_except_frame(frame)          │   │
│   │  4. 执行循环:                                                   │   │
│   │     ┌──────────────────────────────────────────────────────┐     │   │
│   │     │  while frame.should_retry:                           │     │   │
│   │     │      frame.restore_snapshot()  # 恢复上下文           │     │   │
│   │     │      result = execute_target(target_uid)              │     │   │
│   │     │      if not result.is_uncertain:                     │     │   │
│   │     │          break  # 成功，退出循环                      │     │   │
│   │     │      for stmt in body: visit(stmt)  # 执行处理块    │     │   │
│   │     │      if not frame.increment_retry():                 │     │   │
│   │     │          break  # 超限，退出循环                     │     │   │
│   │     └──────────────────────────────────────────────────────┘     │   │
│   │  5. 弹栈: runtime_context.pop_llm_except_frame()                │   │
│   └─────────────────────────────────────────────────────────────────┘   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 三、核心类型定义

### 3.1 LLMResult 类

**文件**: `core/runtime/interpreter/llm_result.py`

```python
from dataclasses import dataclass, field
from typing import Optional, Any
from core.runtime.objects.kernel import IbObject

@dataclass
class LLMResult:
    """
    LLM 执行结果的显式返回类型。

    替代传统的异常机制，提供清晰的成功/失败状态区分。

    字段说明:
    - success: 执行是否成功完成
    - is_uncertain: LLM 返回结果是否不确定/无法解析
    - value: 成功时的返回值
    - error_message: 错误信息（如果有）
    - raw_response: LLM 的原始回复
    - retry_hint: 重试提示（如果 is_uncertain=True）
    """
    success: bool = False
    is_uncertain: bool = False
    value: Optional[IbObject] = None
    error_message: Optional[str] = None
    raw_response: str = ""
    retry_hint: Optional[str] = None

    @property
    def is_success(self) -> bool:
        """执行成功且结果确定"""
        return self.success and not self.is_uncertain

    def unwrap(self) -> IbObject:
        """获取返回值，假设已成功"""
        if not self.success:
            raise RuntimeError(f"Cannot unwrap failed result: {self.error_message}")
        if self.value is None:
            from core.runtime.objects.builtins import IbNone
            return IbNone()
        return self.value
```

### 3.2 IbLLMExceptionalStmt 节点

**文件**: `core/kernel/ast.py`

```python
@dataclass(kw_only=True, eq=False)
class IbLLMExceptionalStmt(IbStmt):
    """
    llmexcept 语句。

    语义：
    - 独立语句，不是任何其他语句的附属
    - target 指向同级前一个包含 LLM 调用的语句
    - body 是异常处理块（retry 指令）
    """
    target: IbStmt  # 前向引用：在语义分析时填充
    body: List[IbStmt] = field(default_factory=list)
```

### 3.3 IbRetryStmt 节点

**文件**: `core/kernel/ast.py`

```python
@dataclass(kw_only=True, eq=False)
class IbRetryStmt(IbStmt):
    """
    retry 语句。

    语义：
    - 只能在 llmexcept 的 body 中使用
    - 从当前 llmexcept 帧恢复上下文
    - 设置 should_retry = True，让 llmexcept 重新执行
    """
    hint: Optional[IbExpr] = None  # 可选的 retry hint
```

---

## 四、运行时帧设计

### 4.1 LLMExceptFrame

**文件**: `core/runtime/interpreter/llm_except_frame.py`

```python
@dataclass
class LLMExceptFrame:
    """
    llmexcept/retry 机制的运行时帧。

    负责保存和恢复解释器执行现场的"上下文切片"。
    """

    # 基本信息
    target_uid: str = ""
    node_type: str = ""

    # 重试状态
    retry_count: int = 0
    max_retry: int = 3
    should_retry: bool = True

    # 核心上下文切片
    saved_vars: Dict[str, IbObject] = field(default_factory=dict)
    saved_intent_stack_root: Optional[Any] = None
    saved_loop_context: Optional[Dict[str, Any]] = None

    # LLM 结果追踪
    last_result: Optional['LLMResult'] = None

    def increment_retry(self) -> bool:
        """递增重试计数，返回是否可继续重试"""
        self.retry_count += 1
        return self.retry_count < self.max_retry

    def should_continue_retrying(self) -> bool:
        """判断是否应该继续重试"""
        return self.should_retry and self.retry_count < self.max_retry
```

---

## 五、解释器实现

### 5.1 visit_IbLLMExceptionalStmt (Result 模式)

**文件**: `core/runtime/interpreter/handlers/stmt_handler.py`

```python
def visit_IbLLMExceptionalStmt(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
    """
    执行 llmexcept 语句。

    语义：
    1. 创建帧并保存上下文切片
    2. 执行 target（被保护的语句）
    3. 检查 target 返回的 LLMResult:
       - 如果 is_uncertain=True:
         a. 执行 body（异常处理块）
         b. 如果 body 设置 should_retry=True，恢复上下文并重新执行 target
         c. 如果 body 没有设置 should_retry，增重重试计数后重新执行 target
       - 如果 is_uncertain=False: 成功，退出
    4. 如果重试次数超限，退出循环

    注意：
    - 不使用任何 Python 异常机制
    - 所有 LLM 不确定性通过 LLMResult.is_uncertain 显式返回
    """
    target_uid = node_data.get("target")
    body_uids = node_data.get("body", [])

    if not target_uid:
        return self.registry.get_none()

    # 创建帧并保存上下文切片
    frame = self.runtime_context.create_llm_except_frame(
        target_uid=target_uid,
        node_type="IbLLMExceptionalStmt",
        max_retry=3
    )

    try:
        while frame.should_continue_retrying():
            # 恢复上下文切片
            frame.restore_snapshot(self.runtime_context)

            # 执行目标语句
            self.visit(target_uid)

            # 检查 LLMResult
            result = self.runtime_context.get_last_llm_result()

            if result is None or not result.is_uncertain:
                # 成功或无 LLM 调用，退出循环
                break

            # LLM 返回不确定
            frame.last_result = result
            frame.should_retry = False  # 重置为需要显式 retry

            # 执行异常处理块
            for stmt_uid in body_uids:
                self.visit(stmt_uid)

            # 检查是否继续重试
            if not frame.increment_retry():
                # 超限，退出循环
                break

    finally:
        # 清理帧栈
        self.runtime_context.pop_llm_except_frame()

    return self.registry.get_none()
```

### 5.2 visit_IbRetryStmt

```python
def visit_IbRetryStmt(self, node_uid: str, node_data: Mapping[str, Any]) -> IbObject:
    """
    处理 retry 语句。

    语义：
    1. 获取可选的 retry hint
    2. 从当前 llmexcept 帧恢复上下文切片
    3. 设置 should_retry = True，让 llmexcept 重新执行 target

    注意：
    - 不抛出任何异常
    - 不使用 RetryException
    """
    hint_uid = node_data.get("hint")
    hint_val = None

    if hint_uid:
        hint_obj = self.visit(hint_uid)
        hint_val = hint_obj.to_native() if hasattr(hint_obj, 'to_native') else str(hint_obj)

    # 设置 retry hint
    self.runtime_context.retry_hint = hint_val

    # 从当前帧恢复上下文
    frame = self.runtime_context.get_current_llm_except_frame()
    if frame:
        frame.restore_snapshot(self.runtime_context)
        frame.should_retry = True  # 设置标志，让外层循环继续重试

    return self.registry.get_none()
```

### 5.3 行为执行入口 (Result 模式)

**文件**: `core/runtime/interpreter/handlers/base_handler.py`

```python
def _execute_behavior(self, behavior: IbObject) -> IbObject:
    """
    统一的行为对象执行入口。
    负责在解释器层管理意图栈的切换和结果处理。
    """
    if not isinstance(behavior, IIbBehavior):
        return behavior

    # 意图栈切换
    old_stack = self.runtime_context.intent_stack
    captured_stack = self._build_intent_stack(behavior.captured_intents)
    self.runtime_context.intent_stack = captured_stack

    try:
        node_uid = getattr(behavior, 'node', None)
        result = self.service_context.llm_executor.execute_behavior_expression(
            node_uid,
            self._execution_context,
            call_intent=None
        )

        # 将结果存储到运行时上下文，供 visit_IbLLMExceptionalStmt 检查
        self.runtime_context.set_last_llm_result(result)

        return result.value if result else self.registry.get_none()
    finally:
        self.runtime_context.intent_stack = old_stack
```

---

## 六、LLMExecutor 接口变更

### 6.1 新接口签名

**文件**: `core/runtime/interpreter/llm_executor.py`

```python
from core.runtime.interpreter.llm_result import LLMResult

class LLMExecutor:
    def execute_behavior_expression(
        self,
        node_uid: str,
        execution_context: IExecutionContext,
        call_intent: Optional[IbIntent] = None,
        captured_intents: Optional[Any] = None
    ) -> LLMResult:
        """
        执行行为表达式，返回 LLMResult。

        不再抛出 LLMUncertaintyError，所有不确定性通过 LLMResult 返回。
        """
        ...
```

### 6.2 决策场景处理

```python
def execute_behavior_expression(self, ...) -> LLMResult:
    # ... 构造 prompt ...

    response = self._call_llm(...)

    # 决策场景处理
    if is_decision_scene:
        decision_map = self._get_decision_map(node_uid, execution_context)

        if decision_map:
            clean_res = response.strip().lower()

            # 尝试匹配
            for k, v in decision_map.items():
                if self._matches_decision(clean_res, k):
                    return LLMResult(
                        success=True,
                        is_uncertain=False,
                        value=self.registry.box(v),
                        raw_response=response
                    )

            # 匹配失败，返回不确定性结果
            return LLMResult(
                success=True,
                is_uncertain=True,
                value=None,
                raw_response=response,
                retry_hint=f"期望匹配 {list(decision_map.keys())} 之一"
            )

    return LLMResult(
        success=True,
        is_uncertain=False,
        value=self.registry.box(response),
        raw_response=response
    )
```

---

## 七、RuntimeContextImpl 扩展

**文件**: `core/runtime/interpreter/runtime_context.py`

```python
class RuntimeContextImpl(RuntimeContext, IStateReader, IStateProvider):
    def __init__(self, ...):
        # ... 现有初始化 ...

        # LLMExceptFrame 帧栈
        self._llm_except_frames: List[LLMExceptFrame] = []

        # 最后一个 LLM 执行结果
        self._last_llm_result: Optional['LLMResult'] = None

    # --- LLM Result 管理 ---

    def set_last_llm_result(self, result: 'LLMResult') -> None:
        """设置最后一个 LLM 执行结果"""
        self._last_llm_result = result

    def get_last_llm_result(self) -> Optional['LLMResult']:
        """获取最后一个 LLM 执行结果"""
        return self._last_llm_result

    def clear_last_llm_result(self) -> None:
        """清除最后一个 LLM 执行结果"""
        self._last_llm_result = None

    # --- 帧栈管理方法 ---

    def push_llm_except_frame(self, frame: LLMExceptFrame) -> None:
        """压入新的 llmexcept 帧"""
        self._llm_except_frames.append(frame)

    def pop_llm_except_frame(self) -> Optional[LLMExceptFrame]:
        """弹出 llmexcept 帧"""
        return self._llm_except_frames.pop() if self._llm_except_frames else None

    def get_current_llm_except_frame(self) -> Optional[LLMExceptFrame]:
        """获取当前 llmexcept 帧（不弹出）"""
        return self._llm_except_frames[-1] if self._llm_except_frames else None

    def create_llm_except_frame(
        self,
        target_uid: str,
        node_type: str = "unknown",
        max_retry: int = 3
    ) -> LLMExceptFrame:
        """创建新的 llmexcept 帧并保存快照"""
        frame = LLMExceptFrame(
            target_uid=target_uid,
            node_type=node_type,
            max_retry=max_retry
        )
        frame.save_snapshot(self)
        self.push_llm_except_frame(frame)
        return frame

    def restore_llm_except_frame(self) -> bool:
        """从当前帧恢复上下文切片"""
        frame = self.get_current_llm_except_frame()
        if frame:
            frame.restore_snapshot(self)
            return True
        return False
```

---

## 八、for 循环回溯语义

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         for 循环回溯语义                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   源文件:                                                                │
│     fruits = ["apple", "banana", "cherry"]                               │
│     for fruit in fruits:                                                 │
│         @~检查水果~                                                      │
│         if fruit == "banana":                                           │
│             print("found")                                              │
│     llmexcept:                                                          │
│         retry()                                                         │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   执行过程:                                                              │
│                                                                          │
│   第 1 次迭代 (index=0, fruit="apple"):                                  │
│     LLMResult(is_uncertain=True) 返回！                                  │
│     frame.save_snapshot() 捕获:                                          │
│       - saved_vars = {"fruits": IbList, "fruit": "apple"}              │
│       - saved_loop_context = {"index": 0, "total": 3}                  │
│                                                                          │
│   llmexcept body 执行 retry():                                           │
│     frame.restore_snapshot() 恢复:                                        │
│       - saved_vars 恢复                                                  │
│       - saved_loop_context 恢复 (index=0)                                │
│     frame.should_retry = True                                           │
│     继续 while 循环                                                     │
│                                                                          │
│   第 2 次迭代 (index=1, fruit="banana"):                                  │
│     LLMResult(is_uncertain=False) 返回！成功！                           │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│   关键点:                                                                │
│   1. 不使用任何异常机制                                                  │
│   2. saved_vars 保存了 fruits 列表和 fruit 变量                          │
│   3. saved_loop_context 保存了 index=0                                   │
│   4. 恢复时，for 循环从 index=1 继续（不是从 0 开始！）                   │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 九、实现清单

### 9.1 创建文件

| 文件 | 说明 | 状态 |
|------|------|------|
| `core/runtime/interpreter/llm_result.py` | LLMResult 类定义 | 待创建 |

### 9.2 修改文件

| 文件 | 修改内容 | 状态 |
|------|----------|------|
| `core/runtime/interpreter/llm_executor.py` | 返回 LLMResult，移除异常抛出 | 待修改 |
| `core/runtime/interpreter/runtime_context.py` | 添加 LLMResult 管理 | 待修改 |
| `core/runtime/interpreter/handlers/stmt_handler.py` | 重写 visit_IbLLMExceptionalStmt | 待修改 |
| `core/runtime/interpreter/handlers/base_handler.py` | 重写 _execute_behavior | 待修改 |
| `core/runtime/interpreter/interpreter.py` | 移除 LLMUncertaintyError 传播处理 | 待修改 |
| `core/kernel/issue.py` | 保留 LLMUncertaintyError 用于真正意外错误 | 待清理 |

### 9.3 待删除代码

| 位置 | 待删除内容 |
|------|----------|
| `interpreter.py` | `except LLMUncertaintyError: raise` 代码块 |
| `stmt_handler.py` | 所有 `except LLMUncertaintyError` 代码块 |
| `expr_handler.py` | 所有异常处理中的 LLMUncertaintyError |

---

## 十、测试用例

```ibci
# 测试 1: 基本 llmexcept/retry
x = @~ 计算 x 的值 ~
if x > 0:
    print("positive")
llmexcept:
    print("retrying...")
    retry()

# 测试 2: for 循环中的 llmexcept
fruits = ["apple", "banana", "cherry"]
for fruit in fruits:
    result = @~ 检查水果 ~
    if result == "bad":
        print("bad fruit")
llmexcept:
    retry()

# 测试 3: 嵌套 if 中的 llmexcept
if @~ 条件A ~:
    if @~ 条件B ~:
        print("both true")
llmexcept:
    retry()
```

---

## 十一、架构方案深入分析

### 11.1 IBCI 核心设计原则

在评估方案之前，需要明确 IBCI 的核心设计原则：

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         IBCI 核心设计原则                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. AST 设计原则                                                         │
│     - 每个节点是自包含的（self-contained）                               │
│     - 父子关系表示结构包含，不表示关联                                    │
│     - 节点语义应该是完整的，不需要外部依赖                                │
│                                                                          │
│  2. 侧表设计原则                                                         │
│     - 元数据与 AST 分离                                                  │
│     - 侧表存储"派生信息"（场景、类型、符号、意图）                        │
│     - AST 存储"固有信息"                                                  │
│                                                                          │
│  3. 解释器设计原则                                                       │
│     - 严格遵循 AST 结构执行                                              │
│     - 每种节点类型有对应的 visit_* 方法                                  │
│     - 无隐藏的控制流或跨节点依赖                                          │
│                                                                          │
│  4. Parser 角色分离原则                                                  │
│     - Parser 只关心语法，不关心语义                                      │
│     - llmexcept 关联在语义分析阶段完成                                    │
│                                                                          │
│  5. llmexcept 设计原则                                                   │
│     - llmexcept 应该是独立的 AST 节点                                     │
│     - 不是任何语句的"附属"                                               │
│     - 有自己完整的执行语义                                                │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 11.2 当前架构问题

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         当前架构的核心问题                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  当前 AST 结构：                                                          │
│                                                                          │
│    IbIf                                                                │
│    ├── test: IbBehaviorExpr ← LLM 调用                                 │
│    ├── body: [...]                                                     │
│    └── orelse: []                                                      │
│                                                                          │
│    IbLLMExceptionalStmt                                                │
│    ├── target: IbIf ← 指向前一个语句（整个 If）                          │
│    └── body: [...]                                                     │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  问题：IbIf 是一个"复合语句"，它内部包含 LLM 调用                          │
│                                                                          │
│  当 IbLLMExceptionalStmt 执行 target (IbIf) 时：                          │
│    1. visit_IbIf 被调用                                                 │
│    2. visit_IbIf 执行 test (IbBehaviorExpr)                             │
│    3. IbBehaviorExpr 返回 LLMResult                                     │
│    4. visit_IbIf 不知道 LLM 返回了不确定结果                             │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 11.3 方案评估

#### 方案 1：重新设计 AST（target 直接指向 LLM 调用）

```
AST 结构变更：
  IbLLMExceptionalStmt
  ├── target: IbBehaviorExpr (直接指向 LLM 调用)
  └── body: [retry 语句]
```

| 设计原则 | 符合度 | 说明 |
|---------|--------|------|
| AST 原则 | ✅ 高 | 节点自包含，无隐藏关联 |
| 侧表原则 | ✅ 高 | 关联信息在侧表中明确 |
| 解释器原则 | ✅ 高 | 标准 visitor 模式 |
| Parser 分离 | ✅ 高 | Parser 不变 |
| llmexcept 原则 | ✅ 高 | 独立节点，完整语义 |
| **可维护性** | **✅ 高** | 结构清晰，易于理解 |

**优点：**
- 最符合"独立节点"原则
- 1:1 映射 llmexcept 和它的 target
- 无隐藏关联
- 执行流程清晰

**缺点：**
- 改变用户可见的语法/结构
- 当前语法 `if @~...~: ... llmexcept:` 语义变化

---

#### 方案 2：修改执行语义（分解复合语句）

```
让 IbLLMExceptionalStmt 在执行时"分解" IbIf：
  1. 识别 IbIf 内部的 LLM 调用
  2. 单独执行 LLM 调用
  3. 根据结果决定是否执行 if body
```

| 设计原则 | 符合度 | 说明 |
|---------|--------|------|
| AST 原则 | ❌ 低 | 引入隐藏的 AST 转换 |
| 侧表原则 | ⚠️ 中 | 关联管理复杂 |
| 解释器原则 | ❌ 低 | 非标准 visitor 模式 |
| Parser 分离 | ⚠️ 中 | 语义分析变复杂 |
| llmexcept 原则 | ⚠️ 中 | 依赖特殊处理 |
| **可维护性** | **❌ 低** | 复杂、脆弱、难以理解 |

**结论：不推荐**

---

#### 方案 3：引入"保护"元属性

```
在语义分析阶段，标记被保护的节点：
  IbIf (protected=True)
  └── test: IbBehaviorExpr

 IbLLMExceptionalStmt
  └── target: IbIf (已标记为 protected)
```

| 设计原则 | 符合度 | 说明 |
|---------|--------|------|
| AST 原则 | ⚠️ 中 | 引入外部依赖 |
| 侧表原则 | ✅ 高 | 利用现有侧表机制 |
| 解释器原则 | ⚠️ 中 | 需要条件判断 |
| Parser 分离 | ✅ 高 | 语义分析不变 |
| llmexcept 原则 | ⚠️ 中 | 保护属性模糊 |
| **可维护性** | **⚠️ 中** | 需要小心处理 |

**优点：**
- 向后兼容
- 最小化结构变化

**缺点：**
- "protected"属性仍然是关联的一种形式
- 可能造成混淆（到底在保护什么？）

---

### 11.4 推荐方案：方案 1（精化版）

**核心思想**：将 llmexcept 的 target 从"整个语句"改为"LLM 调用点"

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         推荐方案：语法保持，语义调整                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  用户语法（不变）：                                                       │
│                                                                          │
│    if @~ 判断 ~:                    ← 复合语句                            │
│        print("yes")                                                       │
│    llmexcept:                                                              │
│        retry()                                                            │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  AST 结构（调整）：                                                       │
│                                                                          │
│  IbProtectedBlock  ← 包装被保护的结构                                    │
│  ├── protected_nodes: [IbIf]  ← 标记哪些节点被保护                       │
│  ├── body: [...]                                                         │
│  └── handler: IbRetryHandler                                             │
│                                                                          │
│  或者更简单的方案：                                                       │
│                                                                          │
│  IbLLMExceptionalStmt                                                    │
│  ├── target: IbIf                                                        │
│  ├── llm_call_uids: [uid_behavior_expr]  ← 明确标记 LLM 调用点           │
│  └── body: [...]                                                         │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 11.5 方案对比总结

| 方案 | AST 完整 | 侧表清晰 | 解释器简洁 | Parser 分离 | 可维护性 | 推荐 |
|------|---------|---------|-----------|------------|---------|------|
| 方案 1: 重新设计 AST | ✅ | ✅ | ✅ | ✅ | ✅ | **推荐** |
| 方案 2: 修改执行语义 | ❌ | ⚠️ | ❌ | ⚠️ | ❌ | 不推荐 |
| 方案 3: 保护属性 | ⚠️ | ✅ | ⚠️ | ✅ | ⚠️ | 备选 |

---

## 十二、版本历史

| 日期 | 版本 | 说明 |
|------|------|------|
| 2026-04-04 | 1.0 | 初始版本，异常模式设计 |
| 2026-04-05 | 2.0 | 彻底重构为 Result 模式，不再使用异常 |
| 2026-04-05 | 2.1 | 架构方案深入分析，确定推荐方案 |

---

## 十三、参考文件

| 文件 | 说明 |
|------|------|
| `core/kernel/ast.py` | AST 节点定义 |
| `core/runtime/interpreter/llm_result.py` | LLMResult 类定义 |
| `core/runtime/interpreter/llm_executor.py` | LLM 执行器 |
| `core/compiler/semantic/passes/semantic_analyzer.py` | 语义分析器 |
| `core/runtime/interpreter/llm_except_frame.py` | 运行时帧实现 |
| `core/runtime/interpreter/runtime_context.py` | 运行时上下文 |
| `core/runtime/interpreter/handlers/stmt_handler.py` | 语句处理器 |
| `core/runtime/interpreter/handlers/base_handler.py` | 基础处理器 |
| `core/runtime/interpreter/interpreter.py` | 解释器调度器 |
