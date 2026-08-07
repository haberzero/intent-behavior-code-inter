# EXEC_FOUNDATION_DESIGN — 统一执行地基设计冻结（协作任务模型）

> **性质**：阶段 0 设计冻结文档（tasks_docs/，零代码）。设计定案后进入阶段 1 地基实现（独立分支实验）。
> **定位**：IBCI 统一执行模型（adopt 协作调度为 VM 唯一执行模型）——`CONCURRENCY_AUDIT.md` §十一 定案的落地设计。
> **最后更新**：2026-08-07
> **关联**：`CONCURRENCY_AUDIT.md`（审计 S1-S9/D1-D9）｜`THREAD_DESIGN.md`（并发/协程设计，Stage 2/3）｜
> `docs/architecture/04_vm_interpreter.md`（VM 架构）｜`DIAGNOSTIC_DESIGN.md`（PT-FEAT-9，阶段 4 依赖本设计 §3.6）。

---

## 〇、摘要

- **统一执行模型**：协作调度器成为 VM 唯一执行核心；"单栈阻塞"是"单任务调度器"的退化情形。
- **统一等待语言**：一切等待都是 `Waitable`（`is_done` 非阻塞查询 + `result()` 阻塞取结果）；执行上下文决定等待语义
  （调度器 poll / 线程体 block / 宿主 `.result()`）。阻塞语言操作统一返回 Waitable——与既有的 `collect`/`run_isolated`
  返回 HostAwaitable 模式**完全一致**（leaf.py:287-295 已支持 VM 挂起）。
- **阻塞即挂起**：任务内 `chan.recv` / `t.join` / `await` / LLM 读点 / 订阅 recv 一律挂起任务让出。
- **线程 = I/O 并行任务**：线程仍是 OS 线程，但完成 = Waitable，主调度器可协作等待（消 S6/D4/D5）。
- **取消统一**：协作式、调度器在任务步进边界检查，覆盖全任务体。
- **观测全局**：事件总线引擎级单实例共享（计算隔离、观测全局，消 D3），`runtime.subscribe` 返回标准订阅端点。
- **语言面**：任意函数可 `await`（无需 async fn 关键字——CPS VM 天然可挂起）；`yield` = 惰性生成器。
- **快照闭合**：yield 点 × llmexcept = llmexcept retry 的 re-drive 正确性（挂起瞬态，不序列化挂起协程）。

---

## 一、定位与目标

### 1.1 为什么这是唯一执行模型

- 整个 VM 是 CPS 构建（handler 生成器、yield child_uid、帧栈驱动、EXEC-1 无 Python 递归）——协作调度是其价值兑现点。
- 双轨（单栈阻塞 + 未接线 TaskScheduler + thread 阻塞句柄）是半成品，违背"不删也不修"。
- 长期每个停摆项（async fn、streaming、host 异步）都重开地基之争——现在统一，一次清偿。

### 1.2 设计约束（继承 THREAD_DESIGN §一）

- IBCI 运行于 Python，受 GIL 限制；**不追求 CPU 并行，不优化为通用并发框架**。
- 本统一执行模型只为服务 LLM IO（等待释放 GIL）与**设计语言统一**（一个等待模型）。
- 一切实现不得引入通用任务/调度框架（asyncio 等）；基于既有 CPS + Waitable 基础设施演进。

### 1.3 价值目标（用户 2026-08-07 定案）

系统设计优秀与统一、可维护性、宏观合理性、长期收益优先；**难度与工作量不参与权衡**。

---

## 二、统一设计语言（词汇表）

> 全系统一个概念一个名字；用户面与内核面同义。

| 术语 | 定义 | 对应 |
|------|------|------|
| **任务 Task** | 一个可挂起的执行单元 = VM 帧栈驱动生成器 + 元数据（node_uid/cancelled/结果槽） | VMTask 演进 |
| **调度器 Scheduler** | 驱动所有任务的执行核心（就绪/等待表，单线程轮转） | TaskScheduler 演进为 VM 执行核心 |
| **可等待 Waitable** | 任务等待的统一抽象：`is_done`（非阻塞查询）+ `result()`（阻塞取结果） | 既有协议扩展 |
| **非阻塞取 TryResult** | 调度器专用协议：`try_result()` → `(ok, value)`（**永不阻塞**）；调度器只经此取结果 | 新增（调度器不阻塞的不变量） |
| **挂起/恢复** | 任务在 waitable 上让出（yield），就绪后恢复（send） | 既有生成器语义 |
| **阻塞即挂起** | 任务内的"阻塞"操作 = 挂起任务（调度器语义）；OS 线程上下文 = 真阻塞 | 本设计核心语义 |
| **取消** | 协作式：任务置 cancelled，调度器在步进边界检查并终止 | 统一取消模型 |
| **执行上下文** | 决定等待语义的环境：调度器任务（poll）/ 专用线程体（block）/ 宿主（`.result()`） | 三种等待策略 |

---

## 三、目标架构

### 3.1 执行核心：调度器

```
                    ┌──────────────────────────────────────────┐
                    │  Scheduler（每个执行上下文一个）            │
                    │  ┌────────┐    ┌────────┐    ┌────────┐  │
   run(uid) ──────► │  │ ready  │    │ waiting│    │ 结果槽  │  │
   run_body ──────► │  │ queue  │◄──►│ table  │    │(按提交序)│  │
   run_many ──────► │  └────────┘    └────────┘    └────────┘  │
                    │    poll is_done / park（全等待时）          │
                    └──────────────────────────────────────────┘
                         ▲ 每任务 = _drive_loop_gen（yield Waitable）
```

- **唯一驱动生成器**：`_drive_loop_gen`（vm_executor.py:222）为每任务的可挂起驱动；`_drive_gen_blocking`（:209）与
  `_drive_loop`（:190）降级为"同步跑完单任务"的宿主/线程体便捷入口（不参与调度器内推进）。
- **`run()` / `run_body()` / `run_many()`** 全部经调度器：`run` = 提交单任务跑完；`run_many` = 多任务协作推进
  （现 TaskScheduler 语义）；`run_body` 逐语句 `run()`——**每个语句子树为一个调度器任务**（语句内 `await` 挂起
  不重入调度器；body 级意图 one-shot 处理留在 run_body 的 Python 循环内，逐语句激活/清理）。
- **等待策略**：调度器对 waiting 表 poll `is_done`；就绪 → `try_result()` 非阻塞取回 → send 恢复；全等待时 park
  （默认 ~1ms 可配置）。专用线程体同一调度器（其线程可阻塞等待）。
- **同步入口约束**：`IbUserFunction.call` / `IbBehavior.call` / `IbFnCallable.call` 的同步后备 = "同步跑完单任务"；
  **禁止从调度器运行中的任务内部再进入同步入口**（会死锁）——检测并报错，或路由经调度器。

### 3.2 任务与 Waitable 家族

- **Waitable 统一**：`LLMFuture`（shared/llm_result.py:83）｜`HostAwaitable`（host/awaitable.py:29）｜
  `IbStreamHandle`（objects/stream.py:24）｜`SpawnedTask`（线程完成，新增）｜`ChannelRecvWaitable`（新增，comm recv）。
- **协议扩展（D-02）**：Waitable = `is_done`（非阻塞）+ `try_result()`（非阻塞，`(ok, value)`，**调度器专用**）+ `result()`
  （阻塞，宿主/线程体专用）。现有实现者（LLMFuture/HostAwaitable）增量补 `try_result`；`runtime_checkable` 结构协议同步。
- **调度器不阻塞不变量**：调度器**只**调用 `try_result()`（never block）。`is_done` 观察与 `try_result` 之间有竞态时
  （如同一通道多消费者，数据被先序任务取走）→ `try_result` 返回 `(False, None)` → 任务重新回到等待表（正确重等，不阻塞）。
- **通道消费契约**：stream/message 通道每缓冲**单消费者**（文档化契约）；pubsub 每个订阅者端点独占自己缓冲——
  均无共享消费者竞争；多任务并发 recv 同一 stream/message 属契约外用法，由 try_result 协议保证**不挂起调度器**
  （先到先得，后者重等）。
- 新增 waitable 均放 `core/runtime/shared/` 叶子层（避免循环导入，同 waitable.py 既有定位）。

### 3.3 阻塞即挂起

- **阻塞语言操作统一返回 Waitable**（与 `collect`/`run_isolated` 返回 HostAwaitable 模式完全一致）：
  - `IbChannel.recv()` / `IbSubscriber.recv()` / `IbThread.join()` 返回 Waitable；
  - VM 经 leaf.py:287-295 既有逻辑挂起（`isinstance(result, Waitable) → yield result`）；
  - 线程体经调度器（block）驱动；宿主显式 `.result()`。
- 非阻塞操作（`send_nowait` / `recv_nonblocking`）**保持**即时返回（bool / T|None），不引入 Waitable。
- 效果：IBCI 代码 `c.recv()` 语义不变（VM 透明等待）；Python 宿主契约变为"返回 Waitable，`.result()` 取值"（与 collect 一致）。

### 3.4 线程 = I/O 并行任务（线程-await 桥）

- `SpawnedTask` 满足 `Waitable`：`is_done` = `_future.done()`；`result()` = `_future.result()`（阻塞 join）。
- `IbThread` 满足 `Waitable`：`result()` = `thread_result` 容器（join 现逻辑）；`join()` 返回自身（Waitable）→ VM 挂起等待。
- 线程体 = 专用线程上的单任务调度器（同一调度器代码，阻塞等待）。
- 消解：S6（可 `await` 线程）、D4（join 不再阻塞主栈）、D5（取消经调度器步进检查，覆盖用户函数体）。

### 3.5 协作取消（统一）

- 任务持有 `cancelled` 标志；调度器在**每个任务步进边界**检查：已取消 → `gen.throw(TaskCancelled)`（沿 CPS 传播）
  或直接终止并标记。
- 覆盖**全任务体**（用户函数 / lambda / behavior / LLM 等待 / 通信等待）——不再依赖线程体的 `_drive_generator` 单点检查。
- `thread.cancel()` / 未来 VM 级取消共用同一机制（顺带提供"协作式 VM 中断"能力，P9 缺口收敛，但硬中断仍不做）。

### 3.6 全局事件总线（观测统一，阶段 3 落地，本设计定义目标形态）

- **引擎级单实例 EventBus**：所有 RuntimeContextImpl 构造时注入同一份 EventBus（替换"每 rc 各自新建"）。
- 事件数据携带 `source`（`"main"` 或任务句柄）供过滤。
- `runtime.subscribe()` 返回**标准订阅端点**（ChannelCore pubsub 视图）——干净退订、消 monkeypatch。
- 消解：D3（线程事件归属不对称）、S3（双订阅契约）、S4（双扇出）、S5（总线不再"每 rc 一个 comm 设施"）。
- 计算隔离不变：scope/意图/comm 对象仍 per-task；**观测全局**（诊断事件跨任务可达，PT-FEAT-9 前提）。

---

## 四、关键机制设计

### 4.1 调度器接入主路径（vm_executor 改造）

| 现状 | 目标 |
|------|------|
| `run()` → `_drive_loop([task])` → `_drive_gen_blocking(_drive_loop_gen(stack))` | `run()` → scheduler.submit(生成器) → run_to_completion |
| `_drive_loop_gen` 内部管理栈、向外 yield Waitable | 不变（调度器契约：向外仅 yield Waitable / return 值） |
| `_drive_gen_blocking` 阻塞每个 Waitable | 降级为同步便捷入口（宿主/线程体），调度器内不使用 |
| `_drive_loop` 绑定 `_current_stack` 供 `frame_stack_depth` 观察 | 绑定"当前任务栈"；调度器多任务时取当前推进任务 |
| `run_body` 逐语句 `run()`（每语句一次调度器入口） | `run_body` 逐语句 `run()`——每语句一个调度器任务（语句内 await 不重入调度器） |
| `run_many` 用 TaskScheduler（生产零调用） | 成为调度器多根入口，生产启用 |

- **TaskScheduler 演进**：加 per-task `cancelled` / 结果槽 / park 策略；`submit` 契约 = 生成器（`_drive_loop_gen`）。
- **等待策略**：poll `is_done`；全等待时 park（默认 ~1ms 可配置）；专用线程体可改用阻塞 `result()`（同代码、策略可配）。

### 4.2 Waitable 家族扩展（新增两个）

1. **`SpawnedTask` 满足 Waitable**（coordinator.py:57）：`is_done` / `try_result()`（非阻塞，=`_future.done()` 时取 `_future.result()`）/ `result()`（阻塞 join）。
2. **`ChannelRecvWaitable`**（comm 层，`core/runtime/shared/`）：
   - `is_done` = 目标缓冲有数据 或 通道已关闭（**非阻塞** peek，锁内取 qsize/closed）；
   - `try_result()` = 非阻塞"取走一项"（`(ok, item)`；数据被先序任务取走 → `(False, None)`，调用方重等）；
   - `result()` = `buffer.recv()`（阻塞取项，复用既有 Condition 语义；空且关闭抛 CommClosedError）。
   - 由 `ChannelCore` / `_SubscriberView` 提供 `recv_waitable()` 投影；`IbChannel.recv()` 包装之。

### 4.3 阻塞方法返回 Waitable 的统一契约

| 方法 | 现状 | 目标 | 宿主调用 |
|------|------|------|---------|
| `IbChannel.recv()` | 阻塞返回 T | 返回 `ChannelRecvWaitable` | `.result()` |
| `IbSubscriber.recv()` | 阻塞返回 T | 返回 `ChannelRecvWaitable` | `.result()` |
| `IbThread.join()` | 阻塞返回 thread_result | 返回 self（Waitable，result=thread_result） | `.result()` |
| `collect`/`run_isolated` | 返回 HostAwaitable | 不变（既有模式） | `.result()`（已一致） |

- 语言面语义不变（VM 透明等待）；Python 契约统一为"Waitable + `.result()`"。
- 迁移面：直调这些方法的 Python 测试/宿主代码需加 `.result()`（阶段 1 清单项）。

### 4.4 线程桥实现

- `SpawnedTask`：加 `is_done` property（已有 `is_done` 属性）与 `result()`（=`_future.result()`）→ 满足 Waitable 结构协议。
- `IbThread`：`join()` 改为返回 self；新增 `is_done`（满足 Waitable）——`result()` 复用 join 现逻辑产出 thread_result。
- 线程体：coordinator `_drive_generator` 替换为"单任务调度器阻塞策略"（同代码统一）。
- `ThreadCancelled` 保留为线程取消信号；统一取消经调度器步进边界。

### 4.5 取消实现

- 任务元数据加 `cancelled`；调度器步进前检查 → `gen.throw(TaskCancelled)`。
- 线程任务：`SpawnedTask.cancel()` 置事件（线程调度器轮询同标志）；`IbThread.cancel()` 不变语义。
- 取消后任务结果槽标记 cancelled（thread_result.status 复用）。

### 4.6 yield 点快照 × llmexcept 闭合

**范围界定**：挂起为**瞬态**（运行期内存）；**不序列化挂起协程**（长时持久化挂起态为阶段 5 之后，显式排除）。

**闭合设计**：
1. **llmexcept retry 的 re-drive 正确性**：`_retry_llm_uncertain` 的 `yield re_eval_uid` 在调度器下 = 重新驱动被保护
   语句子树（fresh 生成器）；语句内 `await` 点重新挂起自然成立（驱动生成器 re-yield Waitable）。
2. **快照有效性不变量**：LLMExceptFrame 进入时快照变量/意图；挂起期间其他任务不修改被保护变量（隔离模型：cell
   跨任务写禁止 [P3]、slot 为显式共享）；恢复 + 重驱后快照仍有效。
3. **验证矩阵（阶段 1）**：llmexcept 保护含 await 的语句；retry 发生在挂起之后；嵌套 llmexcept × await；多任务各自
   llmexcept 并发。

---

## 五、语言面形态（阶段 2）

### 5.1 `await`（已落地，语义延续）

- `await <expr>`：Waitable → 挂起；非 Waitable → 幂等返回。
- **任意函数内可用**（无需 async fn 关键字）——CPS VM 中所有函数体已是可挂起生成器，无"协程函数 vs 普通函数"之分
  （决策 D-08；与 Python 的 async-def 区分不同：那是运行时限制，本设计无此限制）。

### 5.2 `yield`（新增，惰性生成器）

- 含 `yield` 的函数 = 惰性生成器（可迭代序列）：`yield x` 挂起产出值，`next()`/迭代恢复。
- 与 `await` 正交可组合：生成器体内可 await（可挂起生成器）。
- 需：lexer/parser/AST/类型/VM handler（`IbYield`）/迭代协议。依赖统一地基（挂起/恢复机制同一）。

### 5.3 与意图/llmexcept/cell 交互

- 意图上下文：函数调用 fork/restore 语义延续；生成器挂起期间意图栈随任务挂起（调度器不阻塞意图状态）。
- llmexcept：§4.6 闭合。
- cell：P3 决定（禁止跨任务写）；生成器内 cell 读写遵循作用域规则。

---

## 六、设计决策表

| # | 决策 | 依据 |
|---|------|------|
| **D-01** | 调度器为 VM 唯一执行核心；单栈阻塞 = 单任务退化；`_drive_loop_gen` 为唯一驱动生成器 | 统一执行模型；CPS 价值兑现；消 D1/D4 |
| **D-02** | 统一 Waitable 家族 + 协议扩展：`is_done`（非阻塞）+ `try_result()`（非阻塞，调度器专用）+ `result()`（阻塞，宿主/线程体）；调度器只经 `try_result`（**永不阻塞**不变量） | 一个等待模型；复用既有 Waitable 协议；竞态安全（多消费者不挂起调度器） |
| **D-03** | 阻塞语言操作统一返回 Waitable（与 collect/run_isolated 一致）；VM 挂起经 leaf.py:293 既有路径 | 统一设计语言；机制同构；最小新机制 |
| **D-04** | 线程完成 = Waitable；IbThread 满足 Waitable；join = 返回自身 | 消 S6/D4/D5；线程=I/O 并行任务 |
| **D-05** | 取消 = 协作式、调度器步进边界检查、覆盖全任务体 | 消 D5；顺带协作式 VM 中断能力 |
| **D-06** | 事件总线引擎级单实例共享（计算隔离、观测全局）；runtime.subscribe 返回标准订阅端点 | 消 D3/S3/S4/S5；PT-FEAT-9 前提 |
| **D-07** | yield 点快照范围 = llmexcept retry re-drive 正确性；挂起瞬态、不序列化挂起协程 | 范围克制；挂起序列化为阶段 5+ 显式排除 |
| **D-08** | 语言面无 async fn 关键字（任意函数可 await）；yield = 惰性生成器 | CPS VM 天然可挂起，无"协程/普通"之分 |

---

## 七、边界与非目标

- **不做** CPU 并行 / 通用并发框架（GIL 约束，THREAD_DESIGN §一）。
- **不做** 挂起协程的序列化/持久化（瞬态挂起；阶段 5+ 再议）。
- **不做** 硬中断/抢占（协作式取消即上限；Python 无法强杀线程）。
- **不做** 跨引擎通信 / 进程间。
- **不做** media Phase 4（封存）。
- **禁止** asyncio / 通用任务框架引入；基于既有 CPS + Waitable + TaskScheduler 演进。

---

## 八、实施阶段与验证（阶段 1 起）

| 阶段 | 内容 | 验证 |
|------|------|------|
| 1a | 调度器接入主路径（run/run_body/run_many 统一） | 全量 pytest 零回归（单任务语义不变）；run_many 并发真推进测试 |
| 1b | Waitable 家族扩展（SpawnedTask / ChannelRecvWaitable）+ 阻塞方法返回 Waitable | comm 挂起化测试；线程桥测试；宿主 `.result()` 迁移清单 |
| 1c | 协作取消全路径 | 用户函数/线程取消测试 |
| 1d | llmexcept × await 闭合 | §4.6 验证矩阵 |
| 1e | 线程体调度器统一 | thread 全量测试迁移 |
| 1f | 语言面 async/yield（阶段 2 入同一地基） | 生成器/await 组合测试 |

- 每步独立分支实验（`exp/exec-1a` 起），全绿后手动应用 unsafe-vibe-dev。
- 基线：当前 1963 passed / 1 skipped（实跑）。

---

## 九、风险

| 风险 | 缓解 |
|------|------|
| 调度器进热路径（正确性/性能） | 独立分支实验 + 全量零回归 + run_many 真并发基准 |
| 阻塞方法返回 Waitable 的宿主契约迁移 | 迁移清单 + 直调点 `.result()` 改造（与 collect 既有模式同构，模式已熟悉） |
| yield 点 × llmexcept 交互 | §4.6 验证矩阵专测；隔离模型（P3）先落地 |
| park 策略延迟 | 默认 ~1ms，可配置；专用线程阻塞策略可选 |
| 同步入口重入死锁 | 检测 + 报错（明确约束） |

---

## 十、决策记录

| 日期 | 决策 | 依据 |
|------|------|------|
| 2026-08-07 | adopt 协作调度为唯一执行模型（本文档冻结） | 用户 2026-08-07 定案；CPS 架构价值兑现；消 S6/D1/D4/D5 |
| 2026-08-07 | 阻塞操作统一返回 Waitable（D-03），与 collect/run_isolated 同构 | 统一设计语言；leaf.py:287-295 既有支持 |
| 2026-08-07 | 挂起瞬态、不序列化挂起协程（D-07） | 范围克制；避免把瞬态调度与持久化耦合成一次改动 |
| 2026-08-07 | 语言面无 async fn 关键字（D-08） | CPS VM 天然可挂起；避免 Python 式"协程/普通"二分 |
