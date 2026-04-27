# IBCI VM 架构长期设想与路线图

> 本文档记录 IBCI 运行时向"真正虚拟机（VM）"演进的长期架构设想。  
> 内容来源：2026-04-18 架构讨论（VM建模 / 三层并发建模 / 意图栈公理化 / 实例模型边界）；2026-04-19 补充 llmexcept 并发语义决议；2026-04-19 升级为快照隔离模型（更优的语义设计）；2026-04-19 Steps 5/6 全部落地（IExecutionFrame + ContextVar + IbIntentContext + IntentContextAxiom + RuntimeContextImpl 迁移）。  
> 这里记录的是**设想和目标**，不是当前任务，不阻塞近期工作。  
> 近期任务见 `docs/NEXT_STEPS.md`；已完成工作见 `docs/COMPLETED.md`。

---

## ✅ 已决议：llmexcept 快照隔离模型

> **状态：已从初期防守性"dispatch_eligible=false 限制"演进为更优的"快照隔离模型"。结论记录如下，不再是悬案。**

### 模型概述：快照隔离（Snapshot Isolation）

llmexcept 的核心语义是**快照隔离模型**：

> **每一个 LLM 语句执行，无论串行还是并行，本身都在一个独立的临时快照状态中运行。进入快照时与外部环境隔离；成功则将结果 commit 到目标变量（单赋值）；失败无法自愈则向外层传播异常。llmexcept 是附着于对应 LLM 节点的"快照内错误处理策略"，仅能读取外部变量（只读），仅能写入 retry-scoped 特殊变量（如 `retry_hint`）。**

这一模型与并发无关——并发安全性是快照语义的自然推论，而非外加约束。

对比旧方案（初期防守决策）与新模型：

| 维度 | 旧决策（dispatch_eligible=false 限制） | 新模型（快照隔离） |
|------|--------------------------------------|-----------------|
| **出发点** | 防守性：避免并发场景的竞争条件 | 语义设计：定义正确的执行语义 |
| **适用范围** | 仅串行节点（dispatch_eligible=false） | 所有 LLM 节点（快照隔离保证安全） |
| **用户感知** | 用户须理解 dispatch_eligible 概念 | 用户只需知道"llmexcept 保护对应 LLM 语句" |
| **并发安全** | 通过限制使用范围实现 | 通过语义正确性自然保证 |

### 快照内的变量访问约束

```
LLM 语句执行流程（快照模型）:

ENTER SNAPSHOT
  ├── 创建 LLMExceptFrame（保存 vars/intent_ctx/loop_ctx/retry_hint）
  ├── 执行 LLM 调用
  │     ├── 成功（is_certain=True）→ COMMIT（写入目标变量）→ EXIT SNAPSHOT
  │     └── 失败（is_uncertain=True）→ 执行 llmexcept body
  │             │
  │             ├── 允许：读取外部变量（只读）
  │             ├── 允许：写入 retry-scoped 变量（retry_hint 等）
  │             └── 禁止：写入快照外的外部变量
  │
  └── 重试次数耗尽 → 向外传播异常（PROPAGATE）
```

**约束说明**：

| 操作 | 当前状态 | 目标状态 |
|------|--------|--------|
| 读取外部变量 | 允许（fast path：直接读快照时值）| ✅ |
| 写入 `retry_hint` | 允许（retry-scoped，不 commit 到外部）| ✅ |
| 写入普通外部变量 | ~~未加限制（仅靠 restore_snapshot 回滚）~~ → **已产生 SEM_052 编译期错误** ✅ | ✅ |
| 快照失败后传播异常 | 目前仅 break + 返回最后值 | 应抛出明确异常 |

### 三个历史危机的消解方式（更新版）

| 危机 | 消解方式 |
|------|---------|
| **危机一（并发 Future 取消）** | 快照模型下，llmexcept body 在快照内执行，不感知外部 Future；并发 Future 的失败由 `LLMFuture` 机制独立处理 |
| **危机二（IntentContext 快照冲突）** | `LLMExceptFrame` 已使用 `intent_context.fork()` 做值快照（Step 6d 完成）✅ |
| **危机三（retry 原子性）** | 每次 retry 使用快照时刻的变量值，`restore_snapshot()` 确保一致性；快照隔离使原子性成立 ✅ |

### 代码现状验证

- `LLMExceptFrame.save_context()` 保存完整快照（vars + intent_ctx.fork() + loop_ctx + retry_hint）✅
- `LLMExceptFrame.restore_snapshot()` 在每次 retry 前恢复快照 ✅
- `intent_context.fork()` 在快照进入时创建独立意图上下文 ✅
- `loop_resume` 支持 for 循环从断点处 retry 恢复 ✅
- `_last_llm_result` ~~仍在 `RuntimeContextImpl` 上（共享字段）~~ → **已迁移为 per-snapshot（§9.3）**：读取后立即清零共享字段，帧私有 `frame.last_result` 为权威来源 ✅
- llmexcept body 内的写操作 ~~无编译期约束~~ → **已实现 SEM_052 编译期错误（§9.2）** ✅

### 待落地工程工作

1. ~~**SEM 约束（§9.2）**：llmexcept body 内向外部变量的写操作产生编译期错误~~ → **已完成** ✅
2. ~~**`_last_llm_result` 迁移（§9.3）**：将该字段从 `RuntimeContextImpl`（共享）移入 `LLMExceptFrame`（per-snapshot）~~ → **已完成** ✅
3. ~~**用户自定义对象深克隆（§9.4，方案A）**：`_try_deep_clone` 支持 plain IbObject 实例~~ → **已完成** ✅
4. ~~**用户协议快照（§9.5，方案B）**：`__snapshot__` / `__restore__` vtable 协议~~ → **已完成** ✅
5. **编译器 DDG 分析**（Step 10a，独立任务）：标注 behavior 节点的 `dispatch_eligible` 字段
6. **失败传播语义**：重试耗尽时从 `break+返回最后值` 改为抛出明确的 `LLMPermanentFailureError`，由外层处理器接管

---

### llmexcept 快照策略三方案总结（已完成：方案A + 方案B）

| 方案 | 机制 | 状态 | 适用场景 |
|------|------|------|---------|
| **方案A（自动深克隆）** | `LLMExceptFrame._try_deep_clone()` 递归克隆用户 IbObject 实例、IbList、IbTuple、IbDict；循环引用通过 `memo` dict 安全处理 | ✅ **已落地** | 通用场景；无需用户干预；含函数引用的字段自动跳过 |
| **方案B（用户协议）** | 用户在 IBCI 类中定义 `func __snapshot__(self)` 和 `func __restore__(self, state)`；运行时在快照时调用前者，retry 前调用后者原地恢复 | ✅ **已落地** | 用户需要精确控制快照粒度（如只保存关键字段）；含不可克隆字段（如嵌套函数引用）的复杂对象 |
| **方案C（外部序列化）** | 用户通过 `func __to_json__(self)` / `func __from_json__(str json_str)` 将对象状态序列化为 JSON；支持跨进程持久化快照 | ⏳ **VM 阶段任务** | 跨 retry 持久化；VM 级并发模型（Step 11）；支持分布式 LLM 调用恢复 |

**方案B 用户代码约定**：
```ibci
class Config:
    str mode
    int attempts

    # __snapshot__ 返回值可以是任意类型（int、str、tuple、dict 等）
    func __snapshot__(self) -> int:
        return self.attempts   # 只保存关键字段

    # __restore__ 接收 __snapshot__ 的返回值，类型需与之一致
    func __restore__(self, int saved):
        self.attempts = saved
```

**优先级规则**：
- 若类定义了 `__snapshot__`：方案B 生效；`__restore__` 未定义时为最佳努力（不报错，不恢复）
- 若类未定义 `__snapshot__`：自动回退到方案A（`_try_deep_clone`）
- `__snapshot__` 调用抛出异常时：自动降级到方案A

**方案C 路线（待定）**：
适合 VM 阶段的并发模型。当 LLM 调用在独立线程/协程中并发执行时，快照需要支持跨线程序列化与恢复，此时 JSON 快照（方案C）比内存克隆（方案A）或原地恢复（方案B）更适合。具体设计待 Step 9（VM CPS 调度循环）完成后再推进。

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

### 层次 0：接口归一 ✅ COMPLETED（Step 5a）

**目标**：在 `core/base/interfaces.py` 中正式定义 `IExecutionFrame` Protocol，使现有的 `RuntimeContextImpl` + `ExecutionContextImpl` 组合成为其一个实现。

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

**完成情况**：`core/base/interfaces.py` 已定义 `IExecutionFrame` Protocol；`core/runtime/interpreter/runtime_context.py` 已实现该接口。

---

### 层次 1：ContextVar 引入 ✅ COMPLETED（Step 5b）

**目标**：用 `contextvars.ContextVar[IExecutionFrame]` 替代函数参数传递，使 `IbUserFunction.call()` 能自主获取当前执行帧，不再依赖外部 context 参数。

```python
# core/runtime/frame.py（已创建）
from contextvars import ContextVar
_current_frame: ContextVar['IExecutionFrame'] = ContextVar('ibci_current_frame')

def get_current_frame() -> IExecutionFrame: return _current_frame.get()
def set_current_frame(frame: IExecutionFrame): return _current_frame.set(frame)
def reset_current_frame(token) -> None: _current_frame.reset(token)
```

**为什么选 `contextvars.ContextVar` 而非 `threading.local`**：
- asyncio 协程安全：Task 创建时自动复制父 Context，协程之间帧状态天然隔离
- 嵌套 set/reset 原子性：`token = var.set(frame)` / `var.reset(token)` 是原子的
- 与 Python 生态对齐：FastAPI/Starlette 都用 ContextVar 做请求状态隔离

**完成情况**：`core/runtime/frame.py` 已创建，包含 `get_current_frame()`、`set_current_frame()`、`reset_current_frame()`；`IbUserFunction.call()` 已去除 context 参数；`Interpreter.execute_module()` / `run()` 入口已设置 ContextVar。

---

### 层次 2：VM 调度循环（长期目标，不阻塞近期工作）

**目标**：将 `Interpreter.visit()` 从递归实现改为显式 CPS 调度循环，彻底消除对 Python 递归栈的依赖。

完成后，`ihost.run_isolated()` 可以真正地"暂停一个执行中的帧、切换到另一个宿主上下文、然后恢复"——这才是完备的动态宿主机制。

**前提条件**：层次 0 + 层次 1 完成（✅ 均已具备）。  
**触发时机**：递归栈深度限制成为实际生产问题时，或开始支持真正的协程语义时。

---

## ✅ 四、意图栈公理化（IbIntentContext）— COMPLETED（Steps 6a–6d）

> **状态：Step 6 全部完成。以下记录设计目标的原始描述与当前实现状态的对应关系，供架构参考。**

### 4.1 问题描述（历史背景）

Step 6 之前，意图栈是 `RuntimeContextImpl` 中的四个独立全局字段：`_intent_top`、`_pending_smear_intents`、`_pending_override_intent`、`_global_intents`。这导致：
- 函数内部修改意图栈，会影响外部（全局共享）
- 函数内部 `@+ intent` 没有帧隔离语义
- 跨模块调用时，意图栈无规范

**根本原因**：意图栈被当作"专用寄存器组"而非公理体系中的对象。

### 4.2 设计目标与实现结果

将意图栈本身实例化为 `IbIntentContext`，成为公理体系中的一个类型：

```
IbIntentContext（意图上下文）✅ 已实现
├── _intent_top: IntentNode          持久意图（@+）的不可变链表
├── _smear_queue: List[IbIntent]     一次性意图（@）的消费队列
├── _override: Optional[IbIntent]    排他意图（@!）的单次覆盖槽
└── _global_intents: List[IbIntent]  全局意图（Engine 级）
```

**关键语义（当前实现）**：

| 操作 | 当前实现状态 |
|------|-------------|
| 进入 llmexcept 快照 | `LLMExceptFrame` 调用 `intent_context.fork()` 保存值快照 ✅ |
| `@+ x` 操作 | 修改当前 `_intent_ctx`，通过 `RuntimeContextImpl` 委托接口调用 ✅ |
| 快照恢复（retry） | `restore_snapshot()` 恢复 `_intent_ctx` 引用 ✅ |
| 函数调用帧级隔离 | ✅ **已实现**：`IbUserFunction.call()` 和 `IbLLMFunction.call()` 在函数入口处 `fork()` 调用者的 `_intent_ctx`，返回时恢复原引用（kernel.py:693-763, 814-881） |
| 显式 `f(intent_ctx=ctx)` | 语言层暂未支持 |

> **说明**：函数调用时的帧级意图隔离已通过 `IbUserFunction.call()` 和 `IbLLMFunction.call()` 中的 fork/restore 机制实现（2026-04-19，§9.4）。函数内的 `@+`/`@-` 操作不会泄漏给调用者。llmexcept 快照同样通过 `fork()` 安全隔离。

### 4.3 公理层表示（已完成）

`IntentContextAxiom`（`core/kernel/axioms/intent_context.py`）已注册为正式 Axiom：

```
IntentContextAxiom  ✅ 已实现（core/kernel/axioms/intent_context.py）
└── is_class = True（IBCI 用户可通过 `intent_context()` 显式实例化，§9.5 OOP MVP）
```

`IntentAxiom`（`core/kernel/axioms/intent.py`）已注册，`is_class=True`，公开 `get_content()`、`get_tag()`、`get_mode()` 三个方法。

### 4.4 与 IExecutionFrame 的关系（当前状态）

`RuntimeContextImpl` 通过 `_intent_ctx: IbIntentContext` 字段持有意图上下文，并暴露 `fork_intent_snapshot()` 方法供 `LLMExceptFrame` 调用。

函数调用时的 fork/restore 已在 `IbUserFunction.call()` 和 `IbLLMFunction.call()` 中实现（§9.4）。未来 VM 调度循环（层次 2）可进一步将此机制与帧生命周期自动绑定。

### 4.5 现有代码的映射关系

| Step 6 之前的字段 | Step 6 之后的位置 |
|---|---|
| `RuntimeContextImpl._intent_top` | `RuntimeContextImpl._intent_ctx._intent_top` |
| `RuntimeContextImpl._pending_smear_intents` | `RuntimeContextImpl._intent_ctx._smear_queue` |
| `RuntimeContextImpl._pending_override_intent` | `RuntimeContextImpl._intent_ctx._override` |
| `RuntimeContextImpl._global_intents` | `RuntimeContextImpl._intent_ctx._global_intents` |

所有外部调用接口（`push_intent()`、`add_smear_intent()` 等）保持不变，内部委托给 `_intent_ctx`。

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

## 九、里程碑规划（订正版，与 `docs/NEXT_STEPS.md` 编号统一）

| 里程碑 | 主要内容 | 前提 | 状态 |
|--------|---------|------|------|
| **Step 5** | IbFunction.call() 去除 context 参数（ContextVar 引入） | Step 4b 完成 | ✅ 完成 |
| **Step 6** | IbIntentContext 公理化（意图栈实例化 + fork 语义） | Step 5 完成 | ✅ 完成 |
| **Step 7** | IExecutionFrame 接口归一 + LlmCallResultAxiom + IbLLMCallResult 接入 | Step 6 完成 | ✅ 完成 |
| **Step 8-pre** | llmexcept 快照隔离语义落地（SEM_052 read-only 约束 + `_last_llm_result` per-snapshot 化 + 用户协议快照） | 独立 | ✅ 完成（2026-04-19） |
| **Step 8** | 概念边界文档化（`interpreter.py`/`engine.py`/`service.py` 头部边界注释） | 独立 | ✅ 完成（2026-04-20） |
| **Step 9** | VM CPS 调度循环（消除 Python 递归依赖，解锁第三层并发） | Step 7 完成 | ⏳ 待推进 |
| **Step 10** | Layer 1 LLM 流水线（DDG 分析 + LLMScheduler + dispatch-before-use 集成） | Step 7 完成 | ⏳ 待推进 |
| ├ **Step 10a** | DDG 编译器分析（behavior 节点标注 llm_deps + dispatch_eligible） | Step 7 完成 | ⏳ 待推进 |
| ├ **Step 10b** | LLMScheduler（ThreadPoolExecutor + LLMFuture + dispatch_eager/resolve） | Step 10a 完成 | ⏳ 待推进 |
| └ **Step 10c** | VM dispatch-before-use 集成（`visit()` 感知 dispatch_eligible） | Step 10b + Step 9 完成 | ⏳ 待推进 |
| **Step 11** | Layer 2 多 Interpreter 并发（DynamicHost.spawn 线程化 + collect） | Step 5 完成（独立） | ⏳ 待推进 |
| **Step 12** | 可移植性参考实现 + 完整并发行为测试套件 | Step 9 + Step 11 完成 | ⏳ 待推进 |

---

*本文档记录长期架构设想。近期任务见 `docs/NEXT_STEPS.md`。*
