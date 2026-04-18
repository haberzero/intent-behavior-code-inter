# IBCI VM 架构长期设想与路线图

> 本文档记录 IBCI 运行时向"真正虚拟机（VM）"演进的长期架构设想。  
> 内容来源：2026-04-18 架构讨论（VM建模 / 意图栈公理化 / 实例模型边界三轮探讨）。  
> 这里记录的是**设想和目标**，不是当前任务，不阻塞近期工作。  
> 近期任务见 `docs/NEXT_STEPS.md`；已完成工作见 `docs/COMPLETED.md`。

---

## 一、总体愿景：以计算机视角重建运行时

IBCI 已经在正确的道路上：公理体系（Axiom）建立了与 Python 隔离的分层模型，`IbObject` 的 vtable 设计、`KernelRegistry` 的封印机制、`LogicalCallStack` 的影子栈……这些都是正确的方向。

缺失的是**最后一块拱心石**：执行帧（`IExecutionFrame`）作为第一公民，以及与之配套的、用于描述 VM 完整状态的明确边界划分。

**完整的 IBCI VM 形态**：

```
IbVM
├── IbHeap            # IbObject 的分配与引用管理（当前：Python GC 隐式管理）
├── IbExecutionFrame  # 当前执行状态（PC + Scope + IntentContext + LLMExceptStack）
├── IbCallStack       # 帧栈（IbExecutionFrame 的 LIFO 序列）
├── IbDispatch        # AST 节点到 Handler 的分发表（visitor_cache 的正式形态）
└── IbServices        # 外部服务接口（LLMProvider、HostService 等 I/O 设备）
```

当这个 VM 完备时，IBCI 就真正具备了迁移基底语言（从 Python 迁移到 Rust/Go/C++ 等）的可能性——因为 VM 规范是语言无关的，现有的 E2E 测试套件天然成为跨实现的合规测试集。

---

## 二、双栈问题（核心阻塞点）

**现状**：`LogicalCallStack` 是调试用途的"影子栈"，真实调用栈是 Python 递归栈。  
`interpreter.py` 里有一段注释自白：

```python
# 每一层 IBCI 调用大约消耗 4 层 Python 栈帧
# 必须确保 max_call_stack * 4 < sys.getrecursionlimit() 以免进程崩溃
```

这意味着 IBCI 调用栈是 Python 递归栈的寄生体，而不是真正自主的调用栈。这导致：
- 快照无法捕获"调用中间状态"（只能在安全点做快照）
- 并发模型受制于 Python 线程栈深度
- 函数调用状态（local scope、intent context）必须通过参数逐层传递，无法真正"自主执行"

**根本解法**：把 `Interpreter.visit()` 从 Python 递归改为显式 CPS（Continuation-Passing Style）调度循环。但这是**最大代价的一步**，需要在层次 0、层次 1 完成之后才能安全推进。

---

## 三、增量演进路线（三个独立层次）

### 层次 0：接口归一（零运行时改动）

**目标**：在 `core/base/interfaces.py` 或 `core/runtime/interfaces.py` 中正式定义 `IExecutionFrame` Protocol，使现有的 `RuntimeContextImpl` + `ExecutionContextImpl` 组合成为其一个实现。

```python
class IExecutionFrame(Protocol):
    """
    IBCI 执行帧：一次执行的完整状态单元。
    等价于 CPU 的上下文切换寄存器组，是并发、快照、切片的最小单位。
    """
    @property
    def pc(self) -> str: ...                        # 当前 node_uid（程序计数器）
    @property
    def scope(self) -> Scope: ...                   # 当前作用域链（局部变量）
    @property
    def intent_context(self) -> 'IbIntentContext': ... # 意图上下文（见第四节）
    @property
    def llm_except_stack(self) -> List: ...         # LLM 异常帧栈
    @property
    def last_llm_result(self) -> Any: ...           # LLM 结果寄存器
    def visit(self, node_uid: str, **kwargs): ...   # 唯一的"执行"入口
```

**影响范围**：零。只是给现有东西命名，不改任何实现。  
**触发时机**：Step 5 前置设计阶段。

---

### 层次 1：ContextVar 引入（Step 5 的技术基础）

**目标**：用 `contextvars.ContextVar[IExecutionFrame]` 替代函数参数传递，使 `IbUserFunction.call()` 能自主获取当前执行帧，不再依赖外部 context 参数。

```python
# core/runtime/frame.py（新文件）
from contextvars import ContextVar
_current_frame: ContextVar['IExecutionFrame'] = ContextVar('ibci_current_frame')

def get_current_frame() -> IExecutionFrame: return _current_frame.get()
def push_frame(frame: IExecutionFrame): return _current_frame.set(frame)
```

**为什么选 `contextvars.ContextVar` 而非 `threading.local`**：
- asyncio 协程安全：Task 创建时自动复制父 Context，协程之间帧状态天然隔离
- 嵌套 set/reset 原子性：`token = var.set(frame)` / `var.reset(token)` 是原子的
- 与 Python 生态对齐：FastAPI/Starlette 都用 ContextVar 做请求状态隔离

**配套改动**：
- `IbUserFunction.call()` 去除 context 参数，通过 `get_current_frame()` 获取
- `Interpreter.execute_module()` / `run()` 入口设置 ContextVar
- `IbBehavior._execution_context` 捕获语义澄清：**意图是定义时捕获的，执行帧是调用时获取的**

**影响范围**：有限。主要改动集中在 `kernel.py` IbUserFunction 和 `interpreter.py` 执行入口。

---

### 层次 2：VM 调度循环（长期目标，不阻塞近期工作）

**目标**：将 `Interpreter.visit()` 从递归实现改为显式 CPS 调度循环，彻底消除对 Python 递归栈的依赖。

完成后，`ihost.run_isolated()` 可以真正地"暂停一个执行中的帧、切换到另一个宿主上下文、然后恢复"——这才是完备的动态宿主机制。

**前提条件**：层次 0 + 层次 1 完成（有了 IExecutionFrame 作为第一公民）。  
**触发时机**：递归栈深度限制成为实际生产问题时，或开始支持真正的协程语义时。

---

## 四、意图栈公理化（IbIntentContext）

### 4.1 问题描述

当前意图栈是 `RuntimeContextImpl` 中的全局状态：`_intent_top`、`_pending_smear_intents`、`_pending_override_intent`。当 IBCI 进入函数调用时，存在不明确行为：
- 函数内部修改意图栈，是否影响外部？（当前：是的，全局共享）
- 函数内部 `@+ intent` 是否应该只在函数作用域内有效？（当前：无此概念）
- 跨模块调用时，意图栈如何传递和隔离？（当前：无规范）

**根本原因**：意图栈被当作"专用寄存器组"而非公理体系中的对象。

### 4.2 设计目标：IbIntentContext 作为第一公民

将意图栈本身实例化为 `IbIntentContext`，它是公理体系中的一个类型，是 IBCI 语言层可见的对象：

```
IbIntentContext（意图上下文）
├── intent_stack: 持久意图（@+）的不可变链表
├── smear_queue:  一次性意图（@）的消费队列
├── override:     排他意图（@!）的单次覆盖槽
└── parent_ref:   父 IntentContext 的引用（用于继承语义）
```

**关键语义明确**：

| 操作 | 语义 |
|------|------|
| 进入函数调用（默认） | 创建新 IntentContext，**继承**父上下文的 intent_stack 快照（只读引用，非共享） |
| 函数内 `@+ x` | 修改**当前帧**的 IntentContext，不影响父帧 |
| 函数返回 | 当前帧 IntentContext 丢弃，恢复父帧 IntentContext |
| 显式传递 `f(intent_ctx=ctx)` | 将 ctx 作为参数传入，函数内部可以修改它并让修改对调用者可见（引用传递） |
| 全局意图 `@@ x` | 写入 Engine 级 IntentContext（跨函数调用持久），独立于帧级 IntentContext |

这个设计解决了"意图到底是全局的还是局部的"这个根本问题：**默认是帧级隔离（继承快照），显式传递才是引用共享**，和普通变量的传值/传引用语义完全对齐。

### 4.3 公理层表示

`IntentContextAxiom` 将成为 `core/kernel/axioms/` 中的一个正式 Axiom，拥有完整的 vtable：

```
IntentContextAxiom.capabilities:
├── CreateCapability   # new IntentContext() / new IntentContext(parent=parent_ctx)
├── PushCapability     # ctx.push(intent)
├── PopCapability      # ctx.pop()
├── ResolveCapability  # ctx.resolve() → 返回当前有效意图列表（用于 LLM 调用）
└── ForkCapability     # ctx.fork() → 创建继承快照的子上下文
```

### 4.4 与 IExecutionFrame 的关系

`IExecutionFrame.intent_context` 持有当前帧的 `IbIntentContext` 引用。  
帧切换时，IntentContext 的 fork/restore 由 VM 调度循环自动管理，开发者无需手动操作。

**意图栈不再是 RuntimeContextImpl 的内部状态，而是 IExecutionFrame 持有的一个 IbIntentContext 对象实例。**

### 4.5 现有代码的映射关系

| 现有状态字段 | 对应 IbIntentContext 字段 |
|---|---|
| `RuntimeContextImpl._intent_top` | `IbIntentContext.intent_stack`（持久链表头） |
| `RuntimeContextImpl._pending_smear_intents` | `IbIntentContext.smear_queue` |
| `RuntimeContextImpl._pending_override_intent` | `IbIntentContext.override` |
| `RuntimeContextImpl._global_intents` | Engine 级 `IbIntentContext`（全局单例） |

### 4.6 实现前提

意图栈公理化依赖层次 1（ContextVar）完成，因为 `IbIntentContext` 需要绑定到当前 `IExecutionFrame`，而不是全局状态。

**触发时机**：Step 5 完成后，作为 Step 6 的主要内容推进。

---

## 五、实例模型边界（Interpreter / Engine / Context / DynamicHost）

### 5.1 边界定义

这四个概念的职责边界必须明确，不允许任何模糊：

| 概念 | 职责 | 生命周期 |
|---|---|---|
| **KernelRegistry** | 类型系统 + 方法 vtable 的**只读**存储（sealed 后不可变） | Engine 生命周期，可跨 Interpreter 共享 |
| **Interpreter** | 执行引擎：持有 node_pool、logical_stack、LLMExecutor；执行一次完整的 run() | 一次执行任务的生命周期 |
| **IExecutionFrame（RuntimeContext）** | 运行时可变状态：scope、intent_context、llm_except_stack | 单个函数调用的生命周期（嵌套帧栈） |
| **Engine** | 组装者：创建 KernelRegistry、Interpreter、加载 artifact、注入插件 | 应用程序生命周期 |
| **DynamicHost** | 编排者：管理多个 Engine/Interpreter 实例，实现隔离执行、快照恢复、结果聚合 | 动态任务的生命周期 |

### 5.2 多解释器实例的语义

**解释器实例不是实现多线程的工具，而是实现执行隔离的工具。**

每个 Interpreter 实例拥有：
- 独立的 `node_pool`（可共享不可变 artifact，使用 `ImmutableArtifact`）
- 独立的 `RuntimeContext`（完全隔离的变量、意图、LLM 结果）
- 独立的 `LLMExecutorImpl`（独立的 `last_call_info`，防止并发写冲突）

多个 Interpreter 实例可以共享的：
- `KernelRegistry`（sealed 后只读，天然线程安全）
- `ImmutableArtifact`（编译产物，只读）
- `LLMProvider`（通过 capability_registry 暴露的 `llm_provider`，实现需保证线程安全）

### 5.3 LLM 并发的正确层级

**LLM 并发不应该放在单 Interpreter 内部，而应该放在多 Interpreter 实例层级。**

原因：
- 单 Interpreter 的执行是单一 IbCallStack 的顺序遍历，内部并发需要引入异步调度器，复杂度极高
- 多 Interpreter 实例之间完全隔离（KernelRegistry sealed 后只读），可以安全地在不同线程/协程中并发运行
- DynamicHost 的 `spawn()` 已经提供了创建子 Interpreter 的基础设施

**正确的并发模型**：

```
DynamicHost
├── spawn("task_A") → Interpreter_A （Thread/Coroutine A）  ──→ LLM call A
├── spawn("task_B") → Interpreter_B （Thread/Coroutine B）  ──→ LLM call B
└── collect_results() → 等待所有子解释器完成，聚合结果
```

每个 Interpreter 实例在独立线程中运行（Python GIL 在 LLM HTTP 调用期间释放，真正并行）。

### 5.4 解释器实例的创建与销毁规范

**创建时机**：
- 主 Interpreter：Engine 创建时自动创建，用于主程序执行
- 子 Interpreter：DynamicHost.spawn() 时创建，继承 KernelRegistry，拥有独立 RuntimeContext
- 子 Interpreter 的 artifact 可以和主 Interpreter 相同（共享编译产物），也可以独立（隔离执行）

**销毁规范**：
- 子 Interpreter 执行完成后，DynamicHost 负责回收其 RuntimeContext
- 子 Interpreter 的结果（如果需要）在销毁前通过 `collect()` 机制返回给调用者
- 不允许子 Interpreter 直接写入主 Interpreter 的 RuntimeContext（单向隔离）

**禁止的模式**：
- 多个 Interpreter 实例共享可变的 RuntimeContext（数据竞争）
- 子 Interpreter 修改 KernelRegistry（Registry 在 seal 后只读，违反此规则会抛 PermissionError）
- 主 Interpreter 在子 Interpreter 运行期间修改 artifact（ImmutableArtifact 保证此不可能）

### 5.5 DynamicHost 的职责边界

DynamicHost 是"编排者"而非"执行者"：
- **创建** Engine/Interpreter 实例（不亲自执行 IBCI 代码）
- **注入**需要共享的服务（如同一个 LLMProvider 实例）
- **同步**多个子 Interpreter 的执行（收集结果、等待完成）
- **快照**和**恢复**（通过 HostService.snapshot() / load_state()）

DynamicHost **不应该**：
- 直接操作 RuntimeContext（这是 Interpreter 的内部状态）
- 实现 IBCI 语义（这是 Interpreter + Axiom 的职责）
- 持有 IBCI 对象引用（IbObject）超过结果收集阶段

---

## 六、可移植性路径

当层次 0 + 层次 1 + 意图栈公理化完成后，IBCI 运行时会形成一个**可写规范**：

> IBCI VM = 一个管理 IbExecutionFrame 栈的调度循环  
>           + 一个 IbObject 堆（由 KernelRegistry 管理类型元数据）  
>           + 对 IbServices 的 I/O 接口（LLMProvider、HostService）  
>           + IbIntentContext 作为意图寄存器组的公理化对象

这个规范可以被任何语言实现。现有的 E2E 测试套件（`tests/e2e/`）天然成为跨实现的合规测试集，因为这些测试是行为测试，不耦合 Python 实现细节。

**可移植性路径**：
1. 完整规范文档（从代码反向导出 VM 规范）
2. 将 artifact dict 格式规范化为正式的 JSON Schema
3. 实现一个最小化的参考 VM（纯 Python，但严格遵循 IExecutionFrame 模型，不使用 Python 递归）
4. 外部语言实现只需满足：能加载 artifact JSON，能执行 VM 调度循环，能调用 LLMProvider

---

## 七、里程碑规划（参考，非承诺）

| 里程碑 | 主要内容 | 前提 |
|--------|---------|------|
| **Step 5** | IbFunction.call() 去除 context 参数（ContextVar 引入） | Step 4b 完成 ✅ |
| **Step 6** | IbIntentContext 公理化（意图栈实例化） | Step 5 完成 |
| **Step 7** | IExecutionFrame 接口归一 + 快照完整性修复 | Step 6 完成 |
| **Step 8** | 多 Interpreter 实例并发（DynamicHost.spawn 线程化） | Step 5 完成（独立） |
| **Step 9** | VM 调度循环（消除 Python 递归依赖） | Step 7 完成 |
| **Step 10** | 可移植性参考实现 | Step 9 完成 |

---

*本文档记录长期架构设想。近期任务见 `docs/NEXT_STEPS.md`。*
