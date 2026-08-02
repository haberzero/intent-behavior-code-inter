# LLM 并行化 + 同步异步主线 — 任务追踪

> **主线**：LLM 真正可用的并行化 + 同步异步（用户裁定 2026-08-02，多媒体无限期搁置）。定义见 `NEXT_STEPS.md`（含 Tier 1-4 任务分层 + PT-SYNC-1/2/3 隐含任务）。
> **性质**：原 PENDING_TASKS §二 L3 协程方向由 SHELVED 升为主线；叠加现有并行 dispatch 可靠性加固。
> **状态（2026-08-02）**：代码任务已暂停，聚焦任务目标分析。Stage 1 已实施两项根因修复（见下），等待用户恢复代码工作。
> **验证**：每批 `python -m pytest tests/` 全量零回归 + 残留扫描。

## Phase 1 理解纪要（2026-08-02）

- **现有并行基建**：`dispatch_eager`/`resolve`/`run_batch`（`_SchedulerMixin`/`_BehaviorMixin`，`_core.py` ThreadPoolExecutor，`_max_workers=8`）；CPS 生成器单根驱动循环（`vm_executor.py`）。
- **并行可靠性缺口（PT-HEALTH-3 核心）**：
  - `_expected_type_stack`（`_core.py:76`）实例级全局 List[str]，`_behavior.py:260/273/396/408` push/pop——worker 线程读写潜在竞争。
  - `_current_call_info`（`_core.py:74`）"主线程单写槽"——注释已声明并发约束，需核验实际并发路径是否遵守。
  - 意图上下文 fork 语义（`IbIntentContext.fork()`）已为 dispatch 时刻绑定快照，需核验并行隔离完整性。
- **L3 协程方向（原 SHELVED）**：调度器单根→多任务挂起/恢复；`async`/`await`/`yield` 不在 KEYWORDS；快照协议覆盖 yield 点；PT-3.1 run_isolated 异步句柄；PT-3.2 ReceiveMode 演进。
- **语言现状**：无 async/await 语法；`@~...~` 行为表达式是同步 dispatch。

## 待定架构决策（需用户裁定）

> **已定案（2026-08-02，Option A 混合模型）**：
> 1. 并行模型：LLM IO 保持线程池（仅纯 IO 边界，不触碰共享状态）；VM 多任务协作调度（单线程、无锁）
> 2. async/await：作为多任务调度器之上的显式表面，Stage 3 落地（暂缓完整语言机制，演进目标不变）
> 3. 与 CPS 调度的关系：**升级**现有 CPS 生成器调度为多任务，非平行引入
> 4. 核心洞察：**共享状态去共享化（per-task 所有权）= 多任务调度器地基**，Stage 1 与 Stage 2 是同一重构的两面

## 阶段规划（定案）

- **Stage 1 并行可靠性地基**：executor/behavior 共享状态去共享化——`_expected_type_stack`（`_core.py:76`，`_behavior.py:260/273/396/408` push/pop）、`_current_call_info`（`_core.py:74`）、意图上下文隔离。根因：状态不应跨线程共享 → per-dispatch/per-task 所有权。
- **Stage 2 VM 多任务化**：任务句柄/`YIELD` 挂起恢复/快照覆盖 yield 点（L3 解封）
- **Stage 3 语言级 async/await**：`async def`/`await`（暂缓）
- **Stage 4 宿主级异步**：run_isolated 句柄（PT-3.1）、ReceiveMode 演进（PT-3.2）

## Stage 1 当前工作

### 共享状态盘点（已完成，2026-08-02）

| 状态 | 分析 | 处置 |
|---|---|---|
| `_expected_type_stack`（`_core.py:76`） | **纯死写状态**——全仓零读取，仅 push/pop；expected_type 实际经 `behavior.expected_type` 随调用传递 | ✅ **删除**（根因消除，同时移除理论竞争 + 死代码） |
| `_result_parser` 懒重建（`_prompt.py:314-316`） | worker 路径可触发的**潜在竞争**（两 worker 同时见 None 各自建）+ 静默兜底 | ✅ **改 fail-fast**（hydrate 后必非 None；未水化即执行显式报错） |
| `_current_call_info`（`_core.py:74`） | 主线程单写槽**按构造维护**（worker 全用 `record_current=False`，resolve/同步路径主线程写）；无真实竞争 | 保留；Stage 2 多任务时评估 per-task 化（全局"最近一次"槽随任务数增长语义模糊） |
| `_pending_futures` + lock | 已有锁保护，正确 | 保留 |
| worker 数据流 | `_call_and_parse` 只读预构建 `BehaviorCallSpec` + registry/debugger（只读）；不访问 live context（docstring 与实现一致） | 确认无共享写 |

### 待办
- [ ] `LLMResultParser.parse_result` 线程安全核验（strategy 链是否无实例突变）
- [ ] `_prompt.py`/`_llm_function.py` 实例级状态审计
- [ ] 意图上下文并行隔离核验（fork 语义完整性）
- [ ] Stage 1 全量 pytest + 残留扫描（✅ 已过一轮）
