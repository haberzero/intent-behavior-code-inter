# IBC-Inter 近期优先任务

> 记录接下来可以直接开工的具体任务，按优先级排列。  
> 中长期任务见 `docs/PENDING_TASKS.md`，已完成工作见 `docs/COMPLETED.md`。  
> VM 架构长期设想（含三层并发模型、llmexcept 危险悬案）见 `docs/PENDING_TASKS_VM.md`。
>
> **最后更新**：2026-04-19（Step 5-7 全部完成；IntentAxiom 落地；Step 8-pre llmexcept 快照隔离完整落地（§9.2 SEM_052 + §9.3 `_last_llm_result` per-snapshot 化）；`**` 幂运算 + `//` 整除运算符落地；523 个测试通过。）

---

## 当前整体状态评估

**核心公理化路径已全部完成**（Step 1 → Step 7）：

- ✅ 公理体系（Axiom）：`KernelRegistry` sealed 封印；primitive 类型已完成 Axiom 化
- ✅ vtable 分发：`IbObject.receive()` + `IbClass.lookup_method()` 消息传递模型
- ✅ LLM 执行路径统一：`LLMExecutorImpl` 通过 `capability_registry.get("llm_provider")` 唯一来源
- ✅ `IExecutionFrame` Protocol（Step 5）：`core/base/interfaces.py`，`ContextVar` 帧注册表
- ✅ `IbIntentContext` 公理化（Step 6）：独立意图上下文类型；`RuntimeContextImpl` 完整迁移（6c/6d）
- ✅ `LlmCallResultAxiom` + `IbLLMCallResult`（Step 7）：LLM 结果类型完整接入公理体系
- ✅ `IbLLMCallResult` 全链路接入：`set_last_llm_result()` 自动转换；所有读取点使用 `is_certain`
- ✅ vibe 代码债务清理：`interpreter.py:229` kwargs bug 修复；`engine.py` orchestrator 注入规范化
- ✅ **Step 8-pre（快照隔离完整落地）**：§9.2 SEM_052 编译期 read-only 约束 + §9.3 `_last_llm_result` per-snapshot 化；idbg `last_result()` / `last_llm()` 帧优先模式；`retry_stack()` 含帧私有 `last_result` 详情

---

## __prompt__ 系列协议对用户自定义类的局限性 [P2 - 需设计后实现]

**问题描述**：

IBCI 的 `__prompt__` 系列协议目前存在分裂的实现路径，导致用户在 IBCI 代码中定义的自定义类只能使用其中一个协议：

| 协议 | 用户 IBCI 自定义类 | Python Axiom 内置类型 |
|------|-------------------|----------------------|
| `__to_prompt__` | ✅ 有效（vtable 消息传递路由） | ✅ 有效 |
| `__from_prompt__` | ❌ **无效** | ✅ 有效 |
| `__outputhint_prompt__` | ❌ **无效** | ✅ 有效 |

**根本原因**：

- `__to_prompt__`：`IbObject.__to_prompt__()` → `self.receive('__to_prompt__', [])` → `IbInstance.receive` → `ib_class.lookup_method('__to_prompt__')` → 用户 vtable 方法。vtable 消息传递正常工作。
- `__from_prompt__`：调用链为 `LLMExecutorImpl._parse_result()` → `meta_reg.get_from_prompt_cap(descriptor)` → 只有注册了 `FromPromptCapability` Axiom 的内置类型有此能力；用户类无 Axiom，fallback 直接 box 原始字符串。
- `__outputhint_prompt__`：调用链为 `LLMExecutorImpl._get_llmoutput_hint()` → `meta_reg.get_llm_output_hint_cap(descriptor)` → 同上，只有内置 Axiom 实现了 `IlmoutputHintCapability`。

**代码位置**：
- `core/runtime/interpreter/llm_executor.py`：`_parse_result()`（第 298 行）、`_get_llmoutput_hint()`（第 254 行）
- `core/runtime/objects/kernel.py`：`IbObject.__to_prompt__()`（第 105 行）、`IbObject.__from_prompt__()`（第 115 行，当前实现只走 Axiom 路径）

**修复方向**：
1. `__from_prompt__`：`_parse_result()` 在 Axiom 能力缺失时，应通过 vtable 发送 `'__from_prompt__'` 消息给目标类型的实例，允许用户在 IBCI 类中定义解析逻辑。
2. `__outputhint_prompt__`：`_get_llmoutput_hint()` 在 Axiom 能力缺失时，应通过类（`IbClass`）的 vtable 查找 `'__outputhint_prompt__'` 静态/类方法。
3. 需明确约定用户 IBCI 类实现 `__from_prompt__` 的签名：接受一个 `str` 参数，返回 `(bool, any)` 元组（成功标志 + 解析值）。

---

## Step 8：概念边界文档化 [P3 - 可随时推进]

在完成 Step 5-7 后，用代码注释强化已明确的架构边界：

- `core/runtime/interpreter/interpreter.py` 头部：明确 Interpreter = 执行隔离单元，不是 LLM 并发单元
- `core/engine.py` 头部：明确 Engine = 组装者，不参与执行
- `core/runtime/host/service.py` 头部：明确 DynamicHost = 编排者，不亲自执行 IBCI 代码

---

## Step 8-pre：llmexcept 快照隔离约束完整落地 [✅ COMPLETED — 2026-04-19]

快照隔离模型已在代码层面完全自洽：

1. **§9.2 编译期 read-only 约束**（SEM_052）✅：llmexcept body 内向外部作用域变量的任何赋值（含类型标注重声明）产生 `SEM_052` 编译期错误；body-local 新声明变量和 `retry` 语句不受限制。新增 `TestLLMExceptBodyReadOnly` 覆盖 6 个测试场景。
2. **§9.3 `_last_llm_result` per-snapshot 化** ✅：读取后立即清零共享字段（不再依赖 `finally` 块恢复）；`LLMExceptFrame.last_result` 是 per-snapshot 权威来源；idbg `last_result()` / `last_llm()` 改为帧优先模式；`retry_stack()` 含帧私有 `last_result` 详情（替代始终为 None 的 `last_llm_response`）。

---

## Step 9：VM CPS 调度循环 [P2 - IExecutionFrame 接口完整后可推进]

**前提**：Step 5 IExecutionFrame 接口已完整（✅ 已具备）

**本质**：消除当前解释器的 Python 递归调用栈，改用 CPS（Continuation-Passing Style）调度循环，支持：
- 解释器不再受 Python 调用栈深度限制
- 为 Layer 2 多 Interpreter 并发（`DynamicHost.spawn` 线程化）铺路

详见 `docs/PENDING_TASKS_VM.md`。

---

## Step 10：Layer 1 LLM 流水线 [P2 - Step 6 意图 fork 完成后可推进]

**前提**：Step 6 `IbIntentContext.fork()` 已完整（✅ 已具备）

**本质**：DDG 编译器 + `LLMScheduler` 实现 dispatch 时刻意图绑定，支持 LLM 调用并行化。

详见 `docs/PENDING_TASKS_VM.md`。

---

## Step 11：Layer 2 多 Interpreter 并发 [P3 - Step 5 ContextVar 完整后]

**前提**：Step 5 ContextVar（多线程下帧状态隔离）已完整（✅ 已具备）

**本质**：`DynamicHost.spawn` 线程化，每个 Interpreter 实例持有独立 ContextVar 槽位。

详见 `docs/PENDING_TASKS_VM.md`。

---

## 任务依赖图（历史完成路径）

```
Step 4b（完成）
    │
    ├──→ Step 5a（IExecutionFrame Protocol 定义）[✅ 完成]
    │        │
    │        └──→ Step 5b（ContextVar，IbUserFunction 去除 context 参数）[✅ 完成]
    │                    │
    │                    └──→ Step 6a（IntentContextAxiom）[✅ 完成]
    │                                 │
    │                                 ├──→ Step 6b（IbIntentContext 运行时对象）[✅ 完成]
    │                                 │            │
    │                                 │            └──→ Step 6c（RuntimeContextImpl 迁移）[✅ 完成]
    │                                 │                         │
    │                                 │                         └──→ Step 6d（LLMExceptFrame 修复）[✅ 完成]
    │                                 │
    │                                 └──→ Step 7（LlmCallResultAxiom + IbLLMCallResult 接入）[✅ 完成]
    │
    └──→ Step 8（文档化，随时可做）
```

**下一优先路径**：Step 8（架构边界文档化，随时可做）→ Step 9（CPS 调度循环）→ Step 10（LLM 流水线）→ Step 11（多解释器并发）

---

*本文档记录近期可执行任务。VM 架构长期设想（三层并发/llmexcept危险悬案）见 `docs/PENDING_TASKS_VM.md`。*

