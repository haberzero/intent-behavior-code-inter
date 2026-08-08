# _ASYNC_UNIFY — 异步地基遗留妥协根治（统一执行模型闭环）

> **性质**：临时任务文档（实施完删除）。独立分支实验，全量 pytest 零回归后手动应用 unsafe-vibe-dev。
> **背景**：统一执行地基（TaskScheduler + Waitable + 阻塞即挂起 + CPS trampoline + await/yield）已落地，
> 但**函数调用/回调路径仍存在"任务内同步重入调度器"的遗留旁路**——这些是旧异步地基缺失时留下的妥协。
> **审计**：general subagent 全量只读审计（F1-F3 高 / M1-M4 中 / B1 高），本文件收敛为实施计划。
> **最后更新**：2026-08-08

---

## 〇、核心结论（回答"异步是否已完整接入内核"）

**主流已完整**：协作调度器作为 VM 唯一执行核心、阻塞即挂起、Waitable 统一、trampoline 深递归、
通知式唤醒、线程=IO 并行任务、await/yield 语言面——这些已落地且一致。

**但内核层仍有妥协点**：真正调用用户方法 / `slot.update(fn)` / prompt hint 时，仍可能经**同步 `.call()`**
嵌套重入一个新的调度器（`vm.run`/`vm.run_body`），与"禁同步重入调度器""阻塞即挂起"相悖，且有死锁风险。
根因是**大批可调用对象保留同步 `.call()` 后备，且这些后备在任务内可达**。

---

## 一、发现清单（按实施优先级）

### 高严重度（真遗留·任务内同步重入调度器 / 真阻塞）

| # | 位置 | 问题 | 改造 |
|---|------|------|------|
| **F1** | `vm_handle_IbCall`（leaf.py:298-326）不展开 `IbBoundMethod` → `receive('__call__')` → `BaseFun.call` → `vm.run_body`（嵌套调度器） | **最常见**的用户方法 `obj.method(x)` 任务内同步重入调度器；方法含 Waitable 时死锁；深递归方法嵌套 Python 栈 | `vm_handle_IbCall` 解包 `IbBoundMethod`：`.method` 是 `IbUserFunction/IbLLMFunction` 时经 `_vm_call_user_function`/`_vm_invoke_llm_function` 传 receiver 走 CPS trampoline（与函数调用同构） |
| **B1** | `IbChannel.send`（comm.py:74）→ `CommBuffer.send`（buffer.py:81 满时 `_cond.wait()`） | 有界满通道 `send` 任务内**真阻塞**线程；与 `recv`（已转 Waitable）**不对称**；唯一消费者同调度器时死锁 | `send` 满时返回 Waitable（`send_waitable`，与 `recv_waitable` 对称），生成侧挂起纳入统一地基；保留 `send_nowait` |
| **F2** | `slot.update(fn)` CAS 回调（comm.py:205-228）→ `fn.call` → `vm.run`（嵌套调度器）/ `invoke_behavior`（阻塞 LLM） | CAS 锁外同步调 fn；docstring 自认"可能死锁"；lambda 嵌套、behavior 真阻塞 | update 可调用分支返回 Waitable 让 VM 挂起，或收敛为"仅纯同步确定性函数"（文档+强制）；至少不得经同步 `.call` |
| **F3** | `_get_llmoutput_hint`（_prompt.py:268）在 CPS 行为路径内同步 `.call()` | CPS 主段化未覆盖 hint 方法查找；用户 hint 方法含 Waitable → 死锁 | hint vtable 分支 CPS 化（yield 方法调用），或复用 F1 统一用户方法 CPS 路径 |

### 中严重度（双路径 / 双写 / 重复实现）

| # | 位置 | 问题 | 改造 |
|---|------|------|------|
| **M1** | 各 `.call()` 孪生 vs CPS 路径（user_functions / callables / _shared） | 每条 CPS 路径保留同步 `.call()` 孪生（作用域/实参绑定双写）；F1/F2 根源 | 收敛为单一 CPS 权威路径；`.call` 变薄宿主包装（驱动 CPS 生成器），消双写 |
| **M2** | `_drive_generator`（coordinator.py:307）vs `_drive_loop_gen`（vm_executor.py:204） | 线程体独立驱动循环与主 VM 重复实现；trampoline/GeneratorYield 语义需双维护 | 线程体复用 `_drive_loop_gen`（per-thread 上下文已由任务本地 VMExecutor 隔离），或抽公共驱动 |
| **M4** | `_call_llm`（_core.py:177）CPS 路径内同步阻塞 | 段求值挂起但实际 LLM HTTP 调用仍阻塞调度线程（"可挂起但未挂起"）；`run_many` LLM 并发不达 CPS 直连路径 | `_call_llm` 返回 Waitable（LLMFuture）或路由 dispatch_eager+resolve_future_cps |
| **M3** | `_evaluate_segments`（_prompt.py:126）vs `_evaluate_segments_cps`（:157） | prompt 构建双实现；同步版经 `vm.run`（合法宿主侧，但双写） | 收敛单一源 + 宿主薄驱动 |

### 合法宿主契约（非遗留，不改）

- `SpawnedTask.join()/result()`：宿主侧阻塞，线程句柄明确不满足 Waitable（async/thread 分离），合法。
- `IbThread.join()`：返回自身作 Waitable，语言挂起/宿主 `.result()` 阻塞，一致合法。
- `chan.recv()`/`subscriber.recv()`：已转 Waitable，合法。
- `_evaluate_segments` 同步版在后台线程/宿主路径：宿主侧合法（问题只在 M3 双写）。

---

## 二、实施顺序（依赖驱动）

按"最常见 × 死锁风险 × 独立可验"排序：

| 序 | 项 | 独立可验 | 依据 |
|----|----|----------|------|
| 1 | **F1** 用户方法调用 CPS 化 | 用户类方法含 chan.recv/LLM 的任务 e2e（验证不重入调度器、真挂起） | 最常见路径，高死锁风险，与函数调用同构改动最小 |
| 2 | **B1** send Waitable 化 | 有界满通道 send 任务挂起测试 | 真阻塞无挂起，与 recv 对称 |
| 3 | **F2** slot.update 收敛 | update(fn) 任务内挂起测试 | CAS×挂起互斥语义需定案 |
| 4 | **F3** hint CPS 化 | 用户 hint 方法含 Waitable e2e | 命中面窄但死锁 |
| 5 | **M1** `.call` 收敛薄宿主包装 | 全量回归（宿主侧调用语义不变） | 根治 F1/F2 双写根源 |
| 6 | **M4** LLM 挂起 | CPS 内 LLM 调用不阻塞调度线程基准 | 可挂起但未挂起 |
| 7 | **M2** 驱动去重 | 线程体 trampoline/GeneratorYield 一致性回归 | 重复实现 |
| 8 | **M3** prompt 构建收敛 | prompt 构建双写消除 | 去重 |

> 每项独立分支实验，全量 pytest 零回归后手动 apply。F1 是最高价值（最常见、死锁、与既有函数调用机制同构）。

---

## 三、风险与边界

- **F1**：动 `vm_handle_IbCall` 热路径，须确保 `IbBoundMethod` 解包后 receiver 传递正确（self/super）。
- **B1**：`send` 从同步返回 None 改为 Waitable 是**宿主契约变更**（Python 侧 `c.send(x)` 语义），须评估宿主直调面。
- **F2**：CAS 语义与挂起互斥，需定案（返回 Waitable 但锁外重试语义如何保持）。
- **M1/M2/M3**：纯内部收敛，网络面不变，须全量回归防漂移。
- **不做**：跨引擎通信、挂起协程序列化（瞬态挂起，EXEC_FOUNDATION §七）。

---

## 四、成功判据

- F1/B1/F2/F3 落地后：任务内所有用户方法调用 / send / update(fn) 均不再同步重入调度器或真阻塞。
- 全量 pytest 零回归；新增针对"任务内 Waitable 操作 @@ 方法/通道/slot"的 e2e。
- M1-M4 收敛后：单一 CPS 权威路径 + 薄宿主包装 + 单一驱动循环 + LLM 真挂起。