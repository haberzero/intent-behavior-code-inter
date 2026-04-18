# IBC-Inter 近期优先任务

> 记录接下来可以直接开工的具体任务，按优先级排列。  
> 中长期任务见 `docs/PENDING_TASKS.md`，已完成工作见 `docs/COMPLETED.md`。  
> VM 架构长期设想（含三层并发模型、llmexcept 危险悬案）见 `docs/PENDING_TASKS_VM.md`。
>
> **最后更新**：2026-04-18（Step 4b 完成；VM 架构深度讨论完成，涵盖三层并发/LLM流水线/IbIntentContext/llmexcept危险悬案。  
> 以下任务在全部已知 VM 未来的约束下重新规划，是通往完整 VM 的最小可执行步骤。）

---

## 当前整体状态评估

当前 IBCI 运行时的已有基础：
- ✅ 公理体系（Axiom）：`KernelRegistry` sealed 封印；primitive 类型已完成 Axiom 化（VoidAxiom、CallableAxiom、DeferredAxiom、BehaviorAxiom、BoundMethodAxiom）
- ✅ vtable 分发：`IbObject.receive()` + `IbClass.lookup_method()` 已建立消息传递模型
- ✅ LLM 执行路径统一：`LLMExecutorImpl` 通过 `capability_registry.get("llm_provider")` 唯一来源
- ✅ `LogicalCallStack` 影子栈作为调试基础设施
- ✅ `LLMExceptFrame` + `LLMExceptFrameStack` 串行 retry 机制

**缺失的三块拱心石**（是"公理体系进一步完善"的核心内容）：
1. `IExecutionFrame` — 执行帧作为第一公民（当前 `RuntimeContextImpl` + `ExecutionContextImpl` 是两个无名组合体）
2. `IbIntentContext` — 意图栈作为公理化对象（当前是 `RuntimeContextImpl` 的私有字段群）
3. `LLMCallAxiom` — LLM 调用能力的公理化（当前 `LLMExecutorImpl` 是执行引擎外的一个独立工具类，没有进入公理体系）

---

## Step 5：IExecutionFrame 接口归一 [P1 - 当前主线]

**本质**：给"当前执行状态"这个概念一个正式的名字和协议边界。这是零运行时改动的纯接口工作，但它是后续所有步骤的命名基础。

**为什么现在必须做**：
- `IbUserFunction.call()` 和 `IbBehavior._execution_context` 都需要"当前帧"，但两者的获取方式不一致（前者靠参数传递，后者靠创建时捕获），本质上都是对"IExecutionFrame"的引用，只是没有统一名字
- `LLMExceptFrame.save_context()` 直接操作 `RuntimeContextImpl` 的私有字段——这是因为没有"IExecutionFrame"这个协议层，快照操作无法通过接口进行，只能穿透内部

**具体任务**：

### 5a：定义 `IExecutionFrame` Protocol

在 `core/base/interfaces.py` 中新增：

```python
class IExecutionFrame(Protocol):
    """
    IBCI 执行帧：单次函数调用的完整状态单元。
    等价于 CPU 上下文切换寄存器组；是并发、快照、切片的最小单位。
    
    RuntimeContextImpl 是其当前实现（保持不变，只是通过此 Protocol 命名它）。
    未来 IbIntentContext 公理化后，intent_context 属性将持有 IbIntentContext 对象。
    """
    @property
    def scope(self) -> 'Scope': ...                     # 当前作用域链（局部变量）
    @property  
    def intent_top(self) -> Any: ...                    # 意图栈顶节点（IntentNode 链表）
    @property
    def llm_except_frames(self) -> List: ...            # LLM 异常帧栈（只读）
    @property
    def last_llm_result(self) -> Any: ...               # LLM 结果寄存器
    def fork_intent_context(self) -> Any: ...           # 为 dispatch/retry 返回意图快照
```

这个 Protocol 不需要 `RuntimeContextImpl` 做任何修改——它只是用来**命名和约定**当前已有的东西。

### 5b：ContextVar 引入（IbUserFunction 去除 context 参数）

**技术方案**：新建 `core/runtime/frame.py`，暴露两个全局函数：

```python
from contextvars import ContextVar
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core.base.interfaces import IExecutionFrame

_current_frame: ContextVar['IExecutionFrame'] = ContextVar('ibci_current_frame')

def get_current_frame() -> 'IExecutionFrame':
    return _current_frame.get()

def set_current_frame(frame: 'IExecutionFrame'):
    return _current_frame.set(frame)
```

**改动范围**：
- `core/runtime/interpreter/interpreter.py`：执行入口（`run()`/`execute_module()`）设置 ContextVar
- `core/runtime/objects/kernel.py` → `IbUserFunction.call()`：通过 `get_current_frame()` 自主获取当前帧，去除 `execution_context` 参数依赖
- `IbNativeFunction.call()`：同上

**为什么选 ContextVar 而非 threading.local**：asyncio Task 创建时自动复制父 Context，协程间天然隔离；`set/reset` 原子性；与 Python 生态（FastAPI/Starlette）对齐。详见 `PENDING_TASKS_VM.md`。

**文件**：`core/base/interfaces.py`、新增 `core/runtime/frame.py`、`core/runtime/objects/kernel.py`、`core/runtime/interpreter/interpreter.py`

---

## Step 6：IbIntentContext 公理化 [P1 - Step 5 完成后立即开始]

**本质**：把"意图栈"从 `RuntimeContextImpl` 的私有字段群提升为公理体系中的独立类型。

**为什么这是 LLM 流水线正确性的前提**（不只是架构美观）：

在 Layer 1（LLM 调用流水线）中，一个 `behavior` 节点被 dispatch 时，必须捕获此时刻的完整意图上下文（`fork()`），而不是等到 resolve 时再读取（那时意图栈可能已变化）。如果没有 `IbIntentContext.fork()` 这个语义，流水线的意图注入就无法保证正确性。

同时，这也是 `LLMExceptFrame` 危险悬案（见 `PENDING_TASKS_VM.md` §⚠️）的修复前提：`saved_intent_stack` 需要从裸引用改为 `IbIntentContext` 值快照。

**具体任务**：

### 6a：新建 `IntentContextAxiom`

在 `core/kernel/axioms/` 下新建 `intent_context.py`，注册公理：

```python
class IntentContextAxiom(TypeAxiom):
    """
    IbIntentContext 的类型公理。
    
    Capabilities（vtable 槽位）：
    - fork()     → 返回当前 IntentContext 的不可变快照（用于 dispatch 时刻绑定）
    - resolve()  → 返回当前有效意图列表（传给 LLMExecutor 组装提示词）
    - push(intent, mode)  → 压入意图（@+ 语义，只修改当前帧，不影响父帧）
    - pop()      → 弹出栈顶意图
    - merge(snapshot)    → 将 fork 快照的内容合并到当前上下文（用于 retry 恢复）
    """
```

### 6b：新建 `IbIntentContext` 运行时对象

在 `core/runtime/objects/` 下新建 `intent_context.py`：

```python
class IbIntentContext(IbObject):
    """
    意图上下文运行时对象。
    
    内部结构：
    - _intent_top: IntentNode（不可变链表，结构共享）
    - _smear_queue: List[IbIntent]（一次性意图队列）
    - _override: Optional[IbIntent]（排他意图槽）
    - _parent_ref: Optional[IbIntentContext]（父上下文引用，用于继承语义）
    
    语义约束：
    - fork() 返回的是值快照，不是引用——修改 fork 结果不影响原上下文
    - push() 只修改当前 IbIntentContext 实例，不影响 _parent_ref 指向的父上下文
    - 这与普通变量的"传值/传引用"语义完全对齐
    """
    def fork(self) -> 'IbIntentContext': ...
    def resolve(self) -> List[IbIntent]: ...
    def push(self, intent: IbIntent, mode: IntentMode) -> None: ...
    def pop(self) -> Optional[IbIntent]: ...
```

### 6c：迁移 `RuntimeContextImpl` 意图字段

将 `RuntimeContextImpl` 中的意图相关字段迁移到 `IbIntentContext`：

| 旧字段 | 新位置 |
|--------|--------|
| `_intent_top: IntentNode` | `IbIntentContext._intent_top` |
| `_pending_smear_intents: List[IbIntent]` | `IbIntentContext._smear_queue` |
| `_pending_override_intent: Optional[IbIntent]` | `IbIntentContext._override` |
| `_global_intents: List[IbIntent]` | Engine 级全局 `IbIntentContext` 单例 |

`RuntimeContextImpl` 保留一个 `intent_context: IbIntentContext` 属性作为当前帧的意图上下文持有者。

### 6d：修复 `LLMExceptFrame` 意图快照

将 `LLMExceptFrame.saved_intent_stack` 从裸 `IntentNode` 引用改为 `IbIntentContext` fork 快照：

```python
# 旧实现（危险）
self.saved_intent_stack = runtime_context._intent_top

# 新实现（正确）
self.saved_intent_ctx = runtime_context.intent_context.fork()
```

**文件**：新增 `core/kernel/axioms/intent_context.py`、新增 `core/runtime/objects/intent_context.py`、重构 `core/runtime/interpreter/runtime_context.py`、修改 `core/runtime/interpreter/llm_except_frame.py`

---

## Step 7：LLMCallAxiom — LLM 执行的公理化拼图 [P2 - Step 6 完成后]

**本质**：将 LLM 调用能力正式引入公理体系，使 `LLMExecutorImpl` 不再是一个游离在公理体系之外的工具类。

**为什么需要**：

目前 `IbBehavior.call()` 调用链是：

```
IbBehavior.call()
    → registry.get_llm_executor().invoke_behavior(self, ctx)
        → LLMExecutorImpl.execute_behavior_object()
            → llm_callback.generate(prompt)
```

`LLMExecutorImpl` 直接读取 `RuntimeContextImpl` 的内部字段（通过 `execution_context` 参数）。它不是一个 vtable 方法，它是一个穿透实现细节的工具类。**公理体系中没有"LLM 调用能力"这个概念，只有"有 LLMExecutor 的 Interpreter 可以调用 LLM"这个绕行路径。**

**具体任务**：

### 7a：`LLMCallCapability` 进入 `BehaviorAxiom`

```python
class BehaviorAxiom(TypeAxiom):
    # 现有 capabilities 中新增：
    capabilities = [
        ...,
        LLMCallCapability(),   # 新增：声明 behavior 类型拥有发起 LLM 调用的能力
    ]
```

`LLMCallCapability` 不包含执行逻辑，它只是一个"此类型可以发起 LLM 调用"的**能力声明标记**，用于编译期 DDG（数据依赖图）分析识别 behavior 节点。

### 7b：`IbLLMCallResult` 作为独立类型

LLM 调用的结果（不确定性 + 值）应该是一个有完整 Axiom 的独立类型，而不是 `IbLLMUncertain` 这个"例外情况特殊对象"。

```
LLMCallResultAxiom
├── is_certain: bool        # 结果是否确定
├── value: IbObject         # 确定时的值
├── raw_response: str       # LLM 原始响应
└── retry_hint: str         # 不确定时的重试提示
```

这样 `llmexcept` 可以接收一个 `LLMCallResult` 对象而不是捕获"异常"，使 retry 语义变得可以精确建模（不再依赖异常机制）。

**文件**：`core/kernel/axioms/primitives.py`（BehaviorAxiom 新增 LLMCallCapability）、新增 `core/kernel/axioms/llm_call.py`、`core/runtime/objects/kernel.py`（新增 IbLLMCallResult）

---

## Step 8：概念边界文档化 [P3 - 不阻塞代码工作]

在完成 Step 5-7 后，用代码注释强化已明确的架构边界：

- `core/runtime/interpreter/interpreter.py` 头部：明确 Interpreter = 执行隔离单元，不是 LLM 并发单元
- `core/engine.py` 头部：明确 Engine = 组装者，不参与执行
- `core/runtime/host/service.py` 头部：明确 DynamicHost = 编排者，不亲自执行 IBCI 代码

---

## 任务依赖图

```
Step 4b（完成）
    │
    ├──→ Step 5a（IExecutionFrame Protocol 定义）
    │        │
    │        └──→ Step 5b（ContextVar，IbUserFunction 去除 context 参数）
    │                    │
    │                    └──→ Step 6a（IntentContextAxiom）
    │                                 │
    │                                 ├──→ Step 6b（IbIntentContext 运行时对象）
    │                                 │            │
    │                                 │            └──→ Step 6c（RuntimeContextImpl 迁移）
    │                                 │                         │
    │                                 │                         └──→ Step 6d（LLMExceptFrame 修复）
    │                                 │
    │                                 └──→ Step 7（LLMCallAxiom，与 6b 并行可推进）
    │
    └──→ Step 8（文档化，任何时候都可以做，不阻塞）
```

**最紧急路径（Critical Path）**：Step 5a → 5b → 6a → 6b → 6c → 6d

完成此路径后，IBCI 具备了：
1. 执行帧的统一协议名称（是 VM CPS 重构的接口前提）
2. IbUserFunction 的自洽执行能力（不再依赖外部 context 参数）
3. 意图栈的公理化（是 LLM 流水线 dispatch-time IntentContext fork 的正确性前提）
4. LLMExceptFrame 的安全快照（消除当前的裸引用危险）

---

## 近期不做的事（明确边界）

以下工作在近期**不开展**，原因是前提条件尚不具备：

| 工作 | 原因 |
|------|------|
| Layer 1 LLM 流水线（DDG 编译器 + LLMScheduler） | 前提：Step 6 意图 fork + `llmexcept` 语义重定义 |
| VM CPS 调度循环（消除 Python 递归） | 前提：Step 5 IExecutionFrame 接口完整 |
| Layer 2 多 Interpreter 并发（DynamicHost.spawn 线程化） | 前提：Step 5 ContextVar（多线程下帧状态隔离） |
| `llmexcept` 语义重定义 | 前提：先明确 Layer 1 流水线的边界（`dispatch_eligible` 节点能否被 llmexcept 保护） |

---

*本文档记录近期可执行任务。VM 架构长期设想（三层并发/llmexcept危险悬案）见 `docs/PENDING_TASKS_VM.md`。*

