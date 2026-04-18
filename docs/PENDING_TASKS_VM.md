# IBCI VM 架构长期设想与路线图

> 本文档记录 IBCI 运行时向"真正虚拟机（VM）"演进的长期架构设想。  
> 内容来源：2026-04-18 架构讨论（VM建模 / 三层并发建模 / 意图栈公理化 / 实例模型边界）。  
> 这里记录的是**设想和目标**，不是当前任务，不阻塞近期工作。  
> 近期任务见 `docs/NEXT_STEPS.md`；已完成工作见 `docs/COMPLETED.md`。

---

## ⚠️ 危险悬案：llmexcept / retry 在并发模型下的语义危机

> **状态：需要进一步深度探讨，当前无明确答案。不阻塞近期工作，但在引入 Layer 1（LLM 流水线）之前必须解决。**

### 问题描述

`llmexcept` / `retry` 的当前设计是**完全串行假设下的"时间机器"模型**：

1. 遇到 LLM 调用不确定性时，`LLMExceptFrame.save_context()` 对 RuntimeContext 做快照（变量、意图栈 `_intent_top`、循环上下文、retry_hint）
2. LLM 调用失败后，`restore_context()` 把 RuntimeContext 的状态回滚到快照时刻
3. 重新触发 LLM 调用，直到成功或超出 max_retry

这个模型在串行执行时是正确的。**但在 Layer 1（LLM 调用流水线）引入后，这个模型将面临根本性的语义危机：**

### 危机一：并发 Future 的取消问题

```
str a = @~生成标题~    // dispatch → Future_A（已发出 HTTP）
str b = @~生成摘要~    // dispatch → Future_B（已发出 HTTP，与 A 无依赖）
// ... 使用点
print(a)               // resolve → Future_A 失败，进入 llmexcept
```

当 `Future_A` 在 resolve 时失败，`Future_B` 可能已经完成并等待被 resolve。此时：
- 如果 `llmexcept` 回滚到 dispatch 之前的状态并重试 A，那 `Future_B` 的结果怎么处理？
- 丢弃 `Future_B` 的结果并重新 dispatch？（浪费，且 B 的结果可能已经被后续代码依赖）
- 保留 `Future_B` 的结果？（但"快照"里没有 B 的 Future，restore 后 B 的状态未定义）

**当前的 `LLMExceptFrame.saved_vars` 快照机制没有任何 Future 的概念。`_is_serializable` 方法甚至明确排除了 `IbBehavior` 等复杂类型。**

### 危机二：IntentContext 快照时机的语义冲突

当前 `LLMExceptFrame.save_context()` 直接保存 `runtime_context._intent_top` 的引用：

```python
# llm_except_frame.py:115-116
if hasattr(runtime_context, '_intent_top'):
    self.saved_intent_stack = runtime_context._intent_top
```

这是一个**引用快照**，不是值快照。如果 IntentContext 被公理化（Step 6），则：
- dispatch 时必须 `fork()` IntentContext（为 Future 绑定发射时刻的意图快照）
- 但 `LLMExceptFrame.restore_context()` 调用的是 `restore_active_intents(self.saved_intent_stack)`——它回滚的是整个 intent_top 链表，而不是某个特定 Future 的意图快照

**这两种"保存意图状态"的需求（流水线的 dispatch-time fork vs. retry 的 restore-time rollback）在语义上存在根本冲突，当前实现没有区分这两件事。**

### 危机三：retry 的"原子性"假设在并发下不成立

`retry` 语句的语义是"重新执行当前 llmexcept 块保护的 LLM 调用"。在串行模型中，"重新执行"有明确含义：从快照时刻重新运行。

在并发模型中，"重新执行"意味着什么？
- 只重新 dispatch 失败的那个 Future？（那其他 Future 的状态怎么同步？）
- 回滚所有并发中的 Future 并全部重新 dispatch？（代价极高，且破坏已完成的 Future 结果）
- 还是说 `llmexcept` 只能保护串行的 LLM 调用（不能保护 dispatch_eligible 的并发调用）？

**这第三种选项是目前最可能的出路——将 `llmexcept` 的保护范围限定为不能被流水线化的 LLM 调用（即 `dispatch_eligible=false` 的节点）。但这需要在语言设计层面显式做出此决策，并在编译器层面强制执行。**

### 当前结论（待进一步探讨）

1. **`llmexcept` 的语义需要在引入 Layer 1 流水线之前明确重新定义**，否则两个特性会产生不可调和的语义冲突
2. **最保守的出路**：`llmexcept` 只保护 `dispatch_eligible=false` 的 LLM 调用；对 `dispatch_eligible=true` 的调用，失败处理由 `LLMFuture` 的 Future 错误传播机制处理（类似 `concurrent.futures` 的 `as_completed` 模式）
3. **`LLMExceptFrame` 需要在 IbIntentContext 公理化之后重构**，使 `saved_intent_stack` 成为一个完整的 `IbIntentContext` 值快照（fork），而不是裸 `_intent_top` 引用
4. **这是 IBCI 语言设计中最复杂的未解问题之一**，直接影响 `retry` 作为语言关键字的语义完整性

---

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

## 五、三层并发模型（核心：轻量 LLM 流水线）

> **⚠️ 前一轮分析的错误订正**：之前的文档说"LLM 并发应放在多 Interpreter 实例层级"，这是错误的。
> 这相当于为每一次 HTTP 调用支付整个进程隔离的代价。正确的答案是三层并发模型，各层有不同的粒度和代价。

### 5.0 问题的本质：两个独立的并发需求被混淆了

| 需求 | 描述 | 正确粒度 |
|---|---|---|
| **A. 执行隔离** | 完全独立的程序片段在不同上下文中运行（沙箱、多租户、测试） | Interpreter 实例 |
| **B. LLM 调用流水线** | 同一程序内，多个数据无关的 behavior 表达式并发发起 HTTP 调用 | LLMFuture（单个 Future 对象） |

这两个需求的代价完全不同。把 B 用 A 的机制解决，等于为每次 LLM 调用创建整个执行沙箱，不可接受。

---

### 5.1 第一层：LLM 调用流水线（程序内，自动，轻量）

**什么时候需要**：同一个 IBCI 程序内，多个 `behavior` 表达式或 LLM 函数调用之间**没有数据依赖关系**。

**类比**：CPU 的乱序执行（Out-of-Order Execution）——硬件通过依赖分析发现无关指令，提前发射到执行单元，结果写入重排序缓冲区，最终在正确的程序序中提交。

IBCI 的等价物：
- **发射**（Dispatch）：编译器标注数据依赖信息；VM 调度器在 behavior 节点被"遇到"时立即向线程池提交 HTTP 调用（不等结果）
- **重排序缓冲区**（Reorder Buffer）：`LLMFuture[IbObject]`，保存待提交的 LLM 结果
- **提交**（Commit）：VM 在变量使用点解引用 Future；若已完成则零开销，否则阻塞到 HTTP 返回

```
IBCI 程序（单 Interpreter，单线程控制流）:

str a = @~生成标题~       // 遇到此节点时：立即 dispatch → Future_A（HTTP 发出，继续执行下一行）
str b = @~生成摘要~       // 立即 dispatch → Future_B（HTTP 发出，继续执行下一行）
str c = @~生成提纲~       // 立即 dispatch → Future_C（HTTP 发出，继续执行下一行）

print(a)                  // 解引用 Future_A：若已完成则零等待，否则 block
print(b)                  // 解引用 Future_B
print(c)                  // 解引用 Future_C
```

三个 HTTP 调用并发发起，总耗时 ≈ max(T_a, T_b, T_c) 而非 T_a + T_b + T_c。

**代价**：一个 `concurrent.futures.Future` 对象（约 200 字节），一次 `ThreadPoolExecutor.submit()` 调用。

**必要条件**：编译器必须能静态分析 behavior 表达式的数据依赖。如果 B 的提示词模板中引用了 A 的结果，则 B 不能被提前 dispatch，必须等 A 的 Future 解引用之后才能 dispatch。

**关键不变量（safety guarantee）**：
- `behavior` 表达式的**提示词组装**（读取变量值 + IntentContext）发生在 dispatch 时刻
- `behavior` 表达式**不允许**在执行期间写入任何 IBCI 变量（只输出自身结果）
- 因此：dispatch 的并发安全性完全依赖于"LLM 调用是只读-单写的"这一不变量

**如果这一不变量被违反**（例如：future 行为语义允许行为体修改外部变量），则整个流水线模型的安全基础崩塌，需要回退到串行模型。**这是 IBCI 语义设计中最重要的约束之一，必须在语言规范中显式保证。**

---

### 5.2 第二层：执行隔离（程序间，显式，重量）

**什么时候需要**：完全独立的 IBCI 程序片段需要在隔离的状态空间中执行（不共享变量、不共享意图栈）。

**机制**：Interpreter 实例 + 独立 RuntimeContext。

**代价**：整个执行上下文（RuntimeContext、LLMExecutorImpl、scope 链）的创建代价。

**正确使用场景**：
- DynamicHost.spawn()：在动态宿主中运行子程序
- 测试框架：每个测试用例独立 Interpreter，状态完全隔离
- 多租户：用户 A 和用户 B 的程序在各自隔离的 Interpreter 中运行，不相互污染

**错误使用场景**：为优化同一程序内的独立 LLM 调用而创建多个 Interpreter（这是第一层的职责）。

---

### 5.3 第三层：语言级协程（程序语义，显式，未来）

**什么时候需要**：IBCI 程序需要在语言层面表达"我产生一些内容，等待调用方处理，然后继续"——即生成器/协程语义。

**机制**：CPS（Continuation-Passing Style）调度循环，VM 不再使用 Python 递归栈而是维护显式的续体队列。

**代价**：整个 VM 执行模型的重写（不可逆，高风险）。

**触发时机**：当 IBCI 需要 `yield` / `await` 关键字，或 DynamicHost 需要真正的暂停-恢复-切换语义时。目前不触发。

---

### 5.4 三层并发模型对比

| 维度 | 第一层（LLM 流水线） | 第二层（执行隔离） | 第三层（语言协程） |
|------|---------------------|------------------|--------------------|
| 粒度 | 单个 LLM 调用（HTTP 请求） | 整个程序片段执行 | 单个 yield 点 |
| 代价 | 1 个 Future 对象 | 1 个完整 RuntimeContext | VM 重写 |
| 触发 | 编译器自动检测依赖 | 显式 `spawn()` | 显式 `yield`（未来） |
| 状态共享 | 同一 RuntimeContext（只读读取，单写输出） | 无共享（完全隔离） | 协作共享（显式传递） |
| 当前状态 | **需要设计**（IR 变化 + VM 调度器改造） | **已实现**（基础设施存在，语义待精化） | 未来 |

---

### 5.5 实现第一层需要哪些 IR 和 VM 改动

**编译器侧：数据依赖图（DDG）提取**

当前 artifact dict 是纯控制流树（AST 节点树），没有数据流信息。要支持 LLM 流水线，需要在编译阶段提取每个 `IbBehaviorExpr` 节点的数据依赖集合：

```json
// 当前 artifact 中的 behavior 节点（无依赖信息）
{ "type": "IbBehaviorExpr", "uid": "node_007", "template": "生成关于 {a} 的摘要" }

// 需要增加的字段
{ "type": "IbBehaviorExpr", "uid": "node_007", "template": "生成关于 {a} 的摘要",
  "llm_deps": ["node_003"],   // 依赖 node_003（生成 a 的 behavior）的结果才能 dispatch
  "dispatch_eligible": false  // 不能提前 dispatch（依赖 a）
}

// 无依赖的节点
{ "type": "IbBehaviorExpr", "uid": "node_004", "template": "生成标题",
  "llm_deps": [],
  "dispatch_eligible": true   // 可以在遇到时立即 dispatch
}
```

这要求编译器（语义分析阶段）能够：
1. 识别 behavior 表达式模板中引用的变量（`{var_name}` 插值）
2. 向上追溯每个变量的定义来源——如果来源是另一个 behavior，则存在 LLM 层依赖
3. 将这个依赖关系写入 artifact（新的 `llm_deps` 字段）

**运行时侧：LLMScheduler**

`LLMExecutorImpl` 需要演进为 `LLMScheduler`，具备两个入口：

```python
class LLMScheduler:
    def dispatch_eager(self, node_uid, prompt_args, intent_ctx) -> LLMFuture:
        """立即提交到线程池，返回 Future（不等待）"""
        ...
    
    def resolve(self, node_uid) -> IbObject:
        """阻塞等待 Future 完成，返回结果（如果已完成则零开销）"""
        ...
```

VM 的 `visit()` 循环：
1. 遇到 `dispatch_eligible=True` 的 behavior 节点 → 调用 `dispatch_eager()`，不阻塞，继续执行下一条语句
2. 遇到变量使用点（变量的值来自一个已 dispatch 的 Future）→ 调用 `resolve()`，阻塞直到结果就绪
3. 遇到 `dispatch_eligible=False` 的 behavior 节点 → 先 `resolve()` 其依赖，再 `dispatch_eager()`，再等待

**这是一个"数据流 VM"而不是"控制流 VM"。** 当前 IBCI 是纯控制流 VM（tree-walker）。LLM 流水线要求引入数据流调度能力。这是一次真正的 VM 执行模型升级，不是小改动。

---

### 5.6 内存模型：LLM 流水线下的安全边界

并发 dispatch 的安全性完全依赖以下内存模型约束：

**约束 1（已有）**：`behavior` 表达式只读取 IBCI 变量（在提示词模板中插值），不写入任何变量。  
→ 多个 dispatch 并发读取同一变量是安全的（无写-写竞争，无读-写竞争）

**约束 2（已有）**：每个 behavior 表达式的结果只能写入它自己对应的目标变量（单赋值），且此写入发生在 resolve 时（串行的使用点），不在 dispatch 时。  
→ 写入是串行发生的，不存在并发写

**约束 3（需要保证）**：`IbIntentContext`（意图栈）在 dispatch 时被快照，而不是在 resolve 时被读取。  
→ 如果 dispatch A 后，程序修改了意图栈，再 dispatch B，A 和 B 的 IntentContext 应该是各自 dispatch 时刻的快照，不受后续意图栈修改影响。  
→ **这是 IbIntentContext 公理化（第四节）的必要性之一：IntentContext.fork() 在 dispatch 时自动调用。**

**约束 4（危险地带）**：如果 IBCI 未来允许 behavior 表达式通过某种机制修改外部状态（例如副作用型的 LLM 行为），则约束 1 被打破，流水线模型不再安全。**必须在语言规范层面明确 behavior 表达式是纯函数（无副作用），或提供显式的 `impure` 标记使调度器保守处理。**

---

### 5.7 实例模型边界（订正版）

| 概念 | 职责 | 生命周期 | 并发角色 |
|---|---|---|---|
| **KernelRegistry** | 类型系统 + vtable（sealed 后只读） | Engine 生命周期 | 可跨所有层安全共享 |
| **LLMScheduler** | dispatch + resolve LLM 调用（第一层并发的实现者） | Interpreter 生命周期 | 内部持有 ThreadPoolExecutor |
| **Interpreter** | 控制流执行引擎（第二层隔离的单元） | 一次执行任务 | 一个 Interpreter = 一个独立沙箱 |
| **IExecutionFrame** | 当前帧状态（scope + IntentContext + LLM 帧栈） | 单次函数调用 | 属于某一 Interpreter，不跨越 |
| **Engine** | 组装者 | 应用程序生命周期 | 无并发角色 |
| **DynamicHost** | 编排多个 Interpreter（第二层隔离的调度者） | 动态任务生命周期 | 不参与第一层并发 |

**解释器实例的唯一使命是执行隔离**：它不是实现 LLM 调用并发的工具（那是 LLMScheduler 的职责），也不是实现语言级并发的工具（那是未来 CPS 调度循环的职责）。

---

### 5.8 DynamicHost 创建新 Engine 时的收敛与同步

当 DynamicHost 的 `create_engine()` 行为要求多个解释器实例收敛时：

1. 每个子 Interpreter 在独立执行流中运行（Thread 或 asyncio Task），不共享 RuntimeContext
2. 每个子 Interpreter 内部独立拥有自己的 LLMScheduler 实例（独立线程池）
3. DynamicHost 的 `collect()` 原语等待所有子 Interpreter 的 `run()` 完成
4. 结果通过**约定接口**（特定变量名 / return 值）从子 Interpreter 中提取，注入主 Interpreter 的 RuntimeContext
5. 子 Interpreter 销毁（RuntimeContext GC 回收）

**子 Interpreter 不直接写主 Interpreter 的 RuntimeContext**，这一原则不变。所有同步都通过显式 collect 完成。

---

## 六、async 建模：asyncio vs Threading

IBCI 的第一层并发（LLM 流水线）需要选择底层并发机制：

### asyncio（协程模型）

**优点**：
- 极低的上下文切换开销（Python 协程切换约 1μs，线程切换约 1ms）
- 内置 backpressure（事件循环自然形成限流）
- `contextvars.ContextVar` 天然支持 asyncio 协程隔离

**缺点**：
- **传染性**：整个调用链必须是 `async`。`LLMScheduler.dispatch_eager()` 如果是 `async def`，则 `visit()` 也必须是 `async def`，整个 Interpreter 必须是 async。这是 VM 级别的改变。
- 当前代码完全没有 async，迁移代价极高

### ThreadPoolExecutor（线程模型）

**优点**：
- 非传染性：`dispatch_eager()` 提交任务到线程池后立即返回（同步 API）；`resolve()` 调用 `Future.result()`（阻塞等待），两者都是普通 `def`，不需要改 VM
- Python GIL 在 LLM HTTP 调用期间释放，I/O bound 场景真正并行
- 不需要改动现有的 Interpreter 控制流

**缺点**：
- 每个 LLM 调用需要一个线程，线程池大小成为瓶颈
- 无法精确控制背压

### 结论

**第一层并发（LLM 流水线）应使用 ThreadPoolExecutor**，不采用 asyncio。原因：
- LLM HTTP 调用是 I/O bound，线程池在此场景等同于 asyncio 的性能表现
- 避免 async 传染整个 VM，保持控制流代码的同步可读性
- ContextVar 在线程模型中也正常工作（每个线程有独立的 ContextVar 值）

**asyncio 的入场时机**：第三层（语言级协程）引入时，VM 的调度循环本身需要改为异步，届时整体迁移到 asyncio 是合理的。但这是长期目标，不是近期任务。

---

## 七、实例模型边界（Interpreter / Engine / Context / DynamicHost）

### 7.1 边界定义（订正版）

见 §5.7。

### 7.2 解释器实例的创建与销毁规范

**创建时机**：
- 主 Interpreter：Engine 创建时自动创建，用于主程序执行
- 子 Interpreter：DynamicHost.spawn() 时创建，继承 KernelRegistry（只读共享），拥有独立 RuntimeContext

**销毁规范**：
- 子 Interpreter 执行完成后，RuntimeContext 释放（Python GC 回收）
- 结果通过 collect() 在销毁前提取
- 不允许子 Interpreter 直接写入主 Interpreter 的 RuntimeContext

**禁止的模式**：
- 多个 Interpreter 实例共享可变 RuntimeContext（数据竞争）
- 为轻量 LLM 并发创建 Interpreter 实例（错误的粒度，应用 LLMScheduler）

---

## 八、可移植性路径（更新）

完整的 IBCI VM 规范需要包含：

1. **控制流执行模型**（当前 tree-walker，未来 CPS 循环）
2. **数据流调度模型**（LLMScheduler + LLMFuture + DDG 注解）
3. **IbIntentContext 规范**（fork/resolve/restore 语义）
4. **IbObject 内存模型**（LLM 流水线下的读写安全约束）
5. **三层并发接口规范**（LLMScheduler API / Interpreter 实例 API / 协程 API）

现有 E2E 测试套件天然成为跨实现合规测试集的前提是：测试必须覆盖并发行为（乱序 LLM 结果的确定性验证），当前测试套件尚不包含此类覆盖，需在设计 LLMScheduler 时同步补充。

---

## 九、里程碑规划（订正版）

| 里程碑 | 主要内容 | 前提 |
|--------|---------|------|
| **Step 5** | IbFunction.call() 去除 context 参数（ContextVar 引入） | Step 4b 完成 ✅ |
| **Step 6** | IbIntentContext 公理化（意图栈实例化 + fork 语义） | Step 5 完成 |
| **Step 7** | IExecutionFrame 接口归一 + 快照完整性 | Step 6 完成 |
| **Step 8a** | DDG 编译器分析（behavior 节点标注 llm_deps + dispatch_eligible） | 独立，不依赖上述 |
| **Step 8b** | LLMScheduler（ThreadPoolExecutor + LLMFuture + dispatch_eager/resolve） | Step 8a 完成 |
| **Step 8c** | VM dispatch-before-use 集成（visit() 感知 dispatch_eligible） | Step 7 + 8b 完成 |
| **Step 9** | 多 Interpreter 实例并发（DynamicHost.spawn 线程化 + collect） | Step 5 完成（独立） |
| **Step 10** | VM CPS 调度循环（消除 Python 递归依赖，解锁第三层并发） | Step 7 完成 |
| **Step 11** | 可移植性参考实现 + 完整并发行为测试套件 | Step 10 完成 |

---

*本文档记录长期架构设想。近期任务见 `docs/NEXT_STEPS.md`。*
