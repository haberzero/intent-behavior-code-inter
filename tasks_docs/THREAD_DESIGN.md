# THREAD_DESIGN — 并发/协程设计（Stage 2 已落地，Stage 3 规划）

> 本文档记录 IBCI 异步/协程相关设计要点（原 `docs/subsystems/05_coroutine.md` 迁入，2026-08-06）。
> 设计落地后收敛入技术手册的时机见 `AGENTS.md` 设计阶段文档放置规则。
> **状态**：Stage 2 调度器多任务化已落地（`await` 表达式可用）；语言级 async 函数/生成器为演进目标，保持规划不主动推进（`PENDING_TASKS.md` PT-FEAT-1）。

---

## 一、架构定案（Option A 混合模型）

LLM IO 保持线程池（仅纯 IO 边界，不触碰共享状态）；VM 多任务协作调度（单线程、无锁）；语言级 async/await 为 Stage 3 演进目标。

**核心洞察**：executor 共享状态去共享化（per-task 所有权）既是并行可靠性根因修复，也是多任务调度器的地基——两者是同一重构。

**设计约束**：IBCI 运行于 Python，受 GIL 限制，真正并行的 CPU 计算天然受限，**不是本设计的目标**。本异步/并发设计只为服务 LLM 调用：LLM 调用是 IO 密集，等待期间释放 GIL，故多线程/协作式调度能让多个 LLM 调用并发推进而不阻塞解释器。因此：单线程协作式调度（VM 侧）+ 线程池做纯 LLM IO 边界（Option A）是正确模型；不追求 CPU 并行，不优化为通用并发框架。

---

## 二、现有基础设施（可复用）

- **CPS 风格调度循环**：`VMExecutor`（`core/runtime/vm/vm_executor.py`）所有语句执行已转为 VM 帧栈驱动，递归 visit 已消除。这是协程化的必要前置——无 CPS 帧栈则无法实现 yield 点保存/恢复。
- **ControlSignal 枚举**（`core/runtime/vm/task.py`）：含 `break`/`continue`/`return`/`llm_uncertain`，可扩展 `YIELD` 信号用于协程挂起。
- **dispatch_eager + LLMFuture**：`core/runtime/vm/handlers/` 包中赋值上下文调度逻辑，"异步提交 → 延迟解析"模式，后台 LLM 请求 + 使用点阻塞解引用。
- **快照协议**：`try_deep_clone` 仅服务 llmexcept retry，不覆盖协程 yield 点——协程帧快照协议需与现有 llmexcept snapshot 兼容。

---

## 三、Stage 1：共享状态去共享化

executor 共享状态改为 per-task 所有权。既是并行可靠性根因修复，也是多任务调度器的地基。

---

## 四、Stage 2：调度器多任务化（已落地）

目标：把 VM 从"单栈生成器调度"升级为"多任务协作调度"，作为语言级 async/await（Stage 3）与宿主异步的**共同地基**。

### 4.1 现状与缺口

- **现状**：`VMExecutor._drive_loop_body`（`core/runtime/vm/vm_executor.py`）驱动单个栈（`VMTask` 列表，每个是一生成器），一次只服务一个逻辑计算。
- **缺口**：无"多任务队列"；`resolve`/`collect`/`run_isolated` 等 IO 等待阻塞整个 VM（`future.result()`），无法并发。
- **关键洞察**：生成器本身就是可挂起状态（yield=挂起、send=恢复），帧保存被生成器模型天然解决，无需额外帧快照协议。

### 4.2 核心机制

1. **挂起信号**：`ControlSignal` 新增 `SUSPEND`（携带 waitable：`LLMFuture` 或宿主句柄）。生成器在等待 IO 时返回 `SUSPEND(waitable)`，而非阻塞。
2. **任务队列**：调度器从"单栈"升级为"任务队列"（多个独立根任务，各自是栈），新增就绪队列 + 等待表。
3. **轮转**：调度器循环取一个就绪任务推进一步；若返回 `SUSPEND(waitable)`，移入等待表；waitable 完成则回到就绪队列。
4. **恢复**：对就绪任务的生成器 `send(完成值)` 继续。

### 4.3 关键设计点

- **waitable 抽象**：`LLMFuture`（`is_done`/`get`）与宿主句柄（`spawn_isolated` 返回）统一为"可等待"协议，供调度器询问是否就绪。`Waitable` 为 `runtime_checkable Protocol`，置于叶子模块 `core/runtime/shared/waitable.py`（避免 vm↔host↔bootstrapper 循环导入），`task_scheduler` 重导出。
- **`resolve` 改造**：从"阻塞 `future.result()`"改为"未就绪则返回 `SUSPEND(future)`，就绪后恢复"——把阻塞整个 VM 变为仅挂起当前任务。
- **`collect`/`run_isolated` 改造**：未就绪则挂起（宿主异步依托）。
- **快照/状态**：per-task 状态所有权（对应 Stage 1 去共享化）；intent_context、llmexcept 帧栈随任务挂起持久化的方式在实现时确认。
- **结果序契约**：`TaskScheduler.run()` 返回各任务完成值**按提交序**（与 `submit` 顺序一致），而非完成序——完成序不可预测，按提交序才能让调用方按索引取回对应任务结果。实现：`Task` 携带 `index`，`submit` 预分配结果槽位，`_step` 完成时按索引写入。
- **单脚本内 LLM 挂起**：`vm_handle_IbName`（`leaf.py`）对变量持有的 `LLMFuture` 原为 `llm_executor.resolve()` 阻塞；改为 `yield from llm_executor.resolve_future_cps(future)`——yield future 给调度器挂起，LLM 就绪后恢复。`resolve_future_cps` 是 `resolve()` 的 CPS 平行（yield 挂起替代 `future.result()` 阻塞），结果处理（`_pending_futures` 清理 / 主线程单写槽记录 / 确定性转译）完全一致。

### 4.4 宿主异步统一架构

宿主异步（`spawn_isolated`/`collect`/`run_isolated`）接入 VM 协作式 `Waitable` 协议，统一为单一异步模型：

- `box()` 透传 `Waitable`（`bootstrapper.py`）：Waitable 是异步基础设施对象，非普通值，原样返回不装箱。
- `vm_handle_IbCall` 对 native 调用返回的 `Waitable` 做 `yield` 挂起（`leaf.py`）——native 异步函数（`collect`/`run_isolated`）不再阻塞 VM 线程。
- `HostAwaitable`（`core/runtime/host/awaitable.py`）：结构性满足 `Waitable`（`is_done` 非破坏轮询 + `result()` 消费取回 dict）。`engine.is_spawn_done` 提供非破坏检查。
- **统一 API**：`spawn_isolated` 返回非 Waitable handle；`collect`/`run_isolated` 返回 `HostAwaitable`（VM 透明 await → dict）。`run_isolated` 从 `bool` 改为多值 `dict`；移除冗余 `request_isolated_run`。
- **`ReceiveMode`**（枚举）：`COLLECT`（完整接收，已实现）、`STREAM`（流式，依赖多模态已封存，deferred）。
- 设计约束：`spawn_isolated` 返回**非 Waitable** handle（区分"创建"与"等待"），`collect`/`run_isolated` 返回 **Waitable**（VM 自动 yield），天然区分，无需 per-function 标记。

---

## 五、Stage 3：语言级 `await` 表达式（已落地）与 async 函数/生成器（规划）

### 5.1 `await` 表达式（已落地）

在统一 `Waitable` 地基之上实现语言级 `await <expr>` 显式语法表面。

- **定位**：`await` 是显式等待任意 Waitable（LLMFuture / HostAwaitable）完成的通用表面，与数据流自动 await（读 LLMFuture 变量自动解析、collect 返回 HostAwaitable 自动等待）**互补而非双通道**——数据流自动 await 是透明 future 便利，`await` 服务显式异步点与容器/非变量位置持有 Waitable 的等待，并作为未来 async 函数的地基。
- **五层实现**：lexer 加 `await`→`TokenType.AWAIT`；AST 新增 `IbAwaitExpr(value)`；parser 加 AWAIT 前缀规则（UNARY 优先级，`await x + 1` 解析为 `(await x) + 1`）；semantic `visit_IbAwaitExpr`（类型=操作数类型）+ `_handle_assign_target` 解包 `await <behavior>` 适配目标类型；VM `vm_handle_IbAwaitExpr`（LLMFuture→`resolve_future_cps`、Waitable→`yield`、非 Waitable 幂等返回）+ dispatch 注册。

### 5.2 async 函数 / 生成器（规划，PT-FEAT-1）

async 函数 / 生成器（`yield` 使函数成为生成器）是在 `await` 基础之上的语言级协程形态。依赖调度器多任务挂起恢复 + 快照协议覆盖 yield 点。保持现状规划，不主动推进。

---

## 六、语言层关键字演进（规划）

`async`/`yield` 不在现有 KEYWORDS 表中（`await` 已加入）。需设计语法与对应类型系统支持，涉及 lexer token 新增 + parser 语法规则 + semantic pass + VM handler。

---

## 七、被 L3 阻塞的子项（恢复协程层时复核）

| 编号 | 标题 | 依赖 L3 的原因 |
|------|------|---------------|
| 1 | `host.run_isolated()` 返回值改进 | 需协程句柄实现"异步等待子脚本完成" |
| 2 | `ReceiveMode` 枚举演进 | 需 yield/resume 语义支持流式接收模式 |

---

## 八、验证方式

- 多任务并发：两个独立任务各自等待不同的 SLEEP forever 的 mock future，断言总时近似 max 而非 sum（复用 `mock_server` 真并发思路）。
- 单任务行为不变：现有全量测试零回归（单栈语义保持，多任务只为并发生效）。
