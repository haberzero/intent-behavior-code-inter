# IBC-Inter 近期优先任务

> 记录接下来可以直接开工的具体任务，按优先级排列。  
> 中长期任务见 `docs/PENDING_TASKS.md`，已完成工作见 `docs/COMPLETED.md`。  
> VM 架构长期设想（含三层并发模型、llmexcept 危险悬案）见 `docs/PENDING_TASKS_VM.md`。
>
> **最后更新**：2026-04-18（Step 5/6/7 全部完成；IbLLMCallResult 完整接入；vibe 代码债务清理。  
> 以下任务是 VM 并发基础完成后的下一优先级。）

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

---

## Step 8：概念边界文档化 [P3 - 可随时推进]

在完成 Step 5-7 后，用代码注释强化已明确的架构边界：

- `core/runtime/interpreter/interpreter.py` 头部：明确 Interpreter = 执行隔离单元，不是 LLM 并发单元
- `core/engine.py` 头部：明确 Engine = 组装者，不参与执行
- `core/runtime/host/service.py` 头部：明确 DynamicHost = 编排者，不亲自执行 IBCI 代码

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

**下一优先路径**：Step 9（CPS 调度循环）→ Step 10（LLM 流水线）→ Step 11（多解释器并发）

---

*本文档记录近期可执行任务。VM 架构长期设想（三层并发/llmexcept危险悬案）见 `docs/PENDING_TASKS_VM.md`。*

