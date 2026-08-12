# CONCURRENCY_AUDIT — 并发/通信体系深度审计与统一任务基线

> **性质**：深度审计报告 + 下一主线任务（并发/通信设计语言统一）基线。设计阶段文档（tasks_docs/），
> 落地后按 docs/ 治理纪律收敛入技术手册。
> **目的**：作为"通信机制进一步完善 + 设计语言统一化"主线任务的**重要参考**，列出已验证的碎片化清单、
> 健全性缺口、工作项与决策点。设计冻结前需完成 §八 决策点裁决。
> **审计日期**：2026-08-07。**方法**：实读代码 + 双 subagent 平行普查（用户面方法表面/内核同步并发全景）+ 本人逐项验证。
> **关联**：`DIAGNOSTIC_DESIGN.md`（PT-FEAT-9，构建在本审计结论之上，依赖 §八 决策先行）。

---

## 〇、摘要

- **用户面 = 内核面底层同一套体系**（chan/slot/subscriber/thread 直接包装 ChannelCore/SlotCore/RuntimeCoordinator；
  await/Waitable 统一 LLMFuture 与 HostAwaitable）。这是优点，保留。
- 但存在 **9 条已验证的设计语言碎片化**（S1-S9：非阻塞命名三变体、内核/用户契约分叉、双订阅契约 +
  monkeypatch、双扇出实现、"comm_"命名错位、双并发惯用法不可互通、线程结果不走 comm 语言、
  Slot CAS 死锁风险、Signal 撞名史）+ **9 条深核查新增发现**（D1-D9：TaskScheduler 已建未接线、
  闭包 cell 跨线程泄漏、线程事件归属不对称、thread.join 阻塞整个 VM、无 VM 中断 API、
  协作取消对用户函数分支失效、三处死状态、文档漂移、无界订阅缓冲）。
- **统一任务应先行于 PT-FEAT-9**：诊断机制站在 S3/S4/S5 之上，且 D3（线程事件归属）直接影响诊断事件可达性。
- 工作项 W1-W6 已列；**决策点 P1-P4 需用户拍板**（thread/await 关系、TaskScheduler 去留、cell 隔离、
  线程事件模型），P5-P9 已给推荐可自主决断。

---

## 一、审计范围与方法

- **范围**：core/runtime/shared/comm（buffer/channel/slot/registry）、core/runtime/observability（events/config/snapshot）、
  core/runtime/interpreter（runtime_context/llm_executor/llm_except_frame）、core/runtime/vm（vm_executor/task/task_scheduler/handlers）、
  core/runtime/coordinator、core/runtime/frame、core/runtime/host、core/runtime/objects（kernel/comm、thread、thread_result、stream、cell）、
  ibci_modules/ibci_iruntime、docs/syntax/14_concurrency.md、docs/KNOWN_LIMITS.md、docs/architecture/04_vm_interpreter.md、tasks_docs/THREAD_DESIGN.md。
- **方法**：实读关键文件 + 两个 general subagent 平行普查（①用户面对象方法表面与命名一致性；
  ②内核同步/并发机制全景）+ 本人对承重结论逐项复验（TaskScheduler 接线、cell 跨线程共享链、
  Slot.update、thread 构造自动启动、recv 命名、事件归属）。
- **证据标注**：所有结论带 file:line 或 commit。

---

## 二、用户面 vs 内核面：是否同一套体系（结论）

**结论：大体是同一套体系——这是显著优点（机制同构做得好），需保留。** 但有三处内核自有机制不与用户面同构。

| 用户面 | 内核底层 | 关系 | 证据 |
|--------|---------|------|------|
| `chan`/`subscriber`/`slot` | `IbChannel`/`IbSubscriber`/`IbSlot` 包装 `ChannelCore`/`_SubscriberView`/`SlotCore` | **同一套** | objects/kernel/comm.py:30/103/151；axioms/primitives/comm.py:91/117/138 |
| `thread` | `IbThread` 包装 `RuntimeCoordinator`+`SpawnedTask` | **同一套** | objects/thread.py:53；coordinator.py:57 |
| `runtime.subscribe()` | 复用 stream `ChannelCore` 包成 `IbChannel` | **复用同一套，但契约分叉**（见 S3） | ibci_modules/ibci_iruntime/core.py:49-82 |
| `await` | `Waitable` 协议统一 `LLMFuture`/`HostAwaitable`/`IbStreamHandle` | **同构** | shared/waitable.py:19-30；shared/llm_result.py:83；host/awaitable.py:29；objects/stream.py:24 |
| 任务本地上下文 | `ContextVar`（frame.py） | **同构**（内核线程任务与用户线程任务同一机制） | coordinator.py:213-214 |

**例外（内核自有机制不同构）**：
1. **线程结果信箱**：`SpawnedTask._future` = Python `concurrent.futures.Future`（coordinator.py:70），用户看到 `thread_result` 容器——**线程结果投递不走 comm 的 Channel/Slot 语言**（S7）。
2. **EventBus**：内核自建 sink 注册表（events.py:63-95），未复用 `ChannelCore` 原生 pubsub（S4）。
3. **事件总线/配置存储/注册表命名**：`_comm_*`（runtime_context.py:393-395）——观测/控制设施被贴 comm 标签（S5）。

---

## 三、机制健全性对表（用户点名的机制逐项）

| 机制 | IBCI 现状 | 健全性判定 | 证据 |
|------|-----------|-----------|------|
| **信箱 mailbox** | 无显式 mailbox 抽象；`chan(message)` 承担点对点队列；`thread_result` 承担线程结果信箱 | 功能覆盖但**无统一抽象名**；线程结果走 Python Future 而非 comm 原语 | channel.py:40-44；thread_result.py:39；coordinator.py:70 |
| **管道 pipe** | `chan(stream/message)` 有序 FIFO / 点对点 | ✅ 健全 | channel.py:31-44 |
| **信号 signal** | 通信 Signal **已移除**（零投递空壳 + 与 VM 控制流 Signal 撞名）；VM 控制流 Signal(RETURN/BREAK/CONTINUE/THROW) 保留 | "Signal"一词现仅指 VM 控制流；通信无 signal | KNOWN_LIMITS §二十二；commit 1da0b1c；shared/signals.py:21-67 |
| **订阅推送 subscribe** | `c.subscribe()`→subscriber；`runtime.subscribe()`→stream chan | 功能 ✓ 但**契约分叉 + monkeypatch**（S3） | channel.py:138；iruntime/core.py:49-82 |
| **同步阻塞通信** | `send`/`recv`/`join` 阻塞 | ✅（但 `join` 阻塞整个 VM，非协作，D4） | buffer.py Condition；thread.py:108-154 |
| **异步非阻塞通信** | `send_nowait`/`recv_nonblocking`/`is_done`/`cancel` | 功能 ✓ 但**命名三变体 + 契约分叉**（S1/S2） | comm.py:50/61/126；channel.py:127；stream.py:92 |
| **全局变量** | 模块级变量 **per-task 隔离**（任务不写主环境作用域；跨任务必须 chan/slot） | 设计选择且文档明确；但**闭包 cell 跨线程共享泄漏**（D2） | 14_concurrency.md §14.1；coordinator.py:17；D2 证据链 |
| **单例** | engine/registry/模块单例（`WeakKeyDictionary` 进程级 + `BoundPlugin` 身份隔离） | ✅ 有隔离设计；`KernelRegistry._registry_lock` 死锁对象（D6） | module_system/loader.py:54；registry.py:29 |
| **VM 中断** | **无通用 VM 中断/abort API**；仅协作式线程取消（且对用户函数分支失效，D5）+ 指令上限 | **缺口**：主 VM 不可中断；`thread.join()` 同步阻塞 | coordinator.py:283-285/215-232；vm_executor.py:57-58,238-241 |

---

## 四、设计语言碎片化清单（S1-S9，全部已验证）

| # | 碎片 | 证据 | 影响面 |
|---|------|------|--------|
| **S1 同物多名：非阻塞操作三变体** | 用户层同一对象 `send_nowait`（comm.py:50）vs `recv_nonblocking`（comm.py:61/126）——两个后缀；core 层 `recv_nowait`（channel.py:127）；`IbStreamHandle.recv_nowait`（stream.py:92）同层不同名 | comm.py:50/61/126；channel.py:127；stream.py:92；axioms/primitives/comm.py:106/108/130 | 用户面 API 命名不一致 |
| **S2 内核/用户契约分叉** | core `ChannelCore.recv_nowait()→(ok,item)`（channel.py:127-136）vs 用户 `IbChannel.recv_nonblocking()→T\|None`（comm.py:61-66/126-131）；名字不同 + 返回形态不同 | channel.py:127；comm.py:61 | 内核/用户两套契约 |
| **S3 两个订阅契约** | `c.subscribe()→subscriber`（pubsub 视图，close=干净 unsubscribe，channel.py:138-163/_SubscriberView.close）vs `runtime.subscribe()→stream chan`（close 靠 **monkeypatch** detach，iruntime/core.py:74-80） | channel.py:138；iruntime/core.py:49-82 | 同一"subscribe"两种返回/退订方式；PT-FEAT-9 消费端契约未定 |
| **S4 两套扇出实现** | EventBus 自定义 sink 注册表（events.py:63-95）vs ChannelCore 原生 pubsub（channel.py:138-163）——"广播到多"两种实现 | events.py:63；channel.py:138 | 机制重复；双维护 |
| **S5 "comm_" 命名错位** | 事件总线/配置存储被归入"通信域"：`_comm_event_bus`/`_comm_config_store`/`_comm_registry`（runtime_context.py:393-395，注释"通信域/线程协调器槽"）——观测/控制身份与投递机制混为一谈 | runtime_context.py:392-447 | 设计语言混淆；PT-FEAT-9 站在其上 |
| **S6 两个并发惯用法不可互通** | thread（阻塞 join 句柄）vs await（协作挂起）；`IbThread` 明确不满足 `Waitable`（thread.py:18）；用户不能 `await` 线程 | thread.py:18；coordinator.py:13 | 用户心智两模型 |
| **S7 线程结果不走 comm 语言** | 线程结果经 Python `Future`+`thread_result` 容器，而非 comm 的 Channel/Slot；"信箱"概念在 comm 域无统一形态 | coordinator.py:70；thread_result.py | 内核内部不一致 |
| **S8 Slot.update CAS+用户函数** | `update(fn)` 锁外执行 fn，文档警告"fn 不应内嵌通信操作（否则可能死锁）" | slot.py:20-22（docstring）；comm.py:182 | 已知坑（设计风险点） |
| **S9 Signal 撞名史** | 通信 Signal 因与 VM 控制流 Signal 撞名被移除（commit 1da0b1c）；"Signal"现仅 VM 控制流 | KNOWN_LIMITS §二十二；git 历史 | 命名空间教训；未来加"通信信号"需避名 |

---

## 五、深核查新增发现（D1-D9）

| # | 发现 | 证据 | 性质 |
|---|------|------|------|
| **D1 TaskScheduler/run_many 已建未接线** | `TaskScheduler`（task_scheduler.py:49-121）仅被 `run_many`（vm_executor.py:134-146）引用，而 `run_many` 生产代码（core/ibci_sdk/ibci_modules/main）**零调用**；仅测试接线（tests/runtime/test_vm_run_many.py、test_task_scheduler.py）。多任务协作调度是"半成品基础设施" | task_scheduler.py:49；vm_executor.py:134 | 违反"不删也不修"；Stage 2 核心未接入主路径 |
| **D2 闭包 cell 跨线程共享泄漏** | `_run_task_body`：`task_func.closure = callable_obj.closure`（coordinator.py:230）**直接共享同一组 IbCell**；任务函数绑定 `new_sym.cell = cell`（user_functions.py:79-83）；赋值走 `symbol.cell.set(...)`（runtime_context.py:170-171）→ 写入共享 IbCell；`IbCell.get/set` 为**无锁**裸读写（cell.py:95-116）→ **任务内写闭包变量反向可见于主线程，无同步**，与 coordinator.py:17"任务不写主环境作用域"设计陈述相悖 | coordinator.py:230；user_functions.py:79-83；runtime_context.py:170-171；cell.py:95-116 | 隔离边界语义缺口（真问题） |
| **D3 线程事件归属不对称** | VM handler 事件（chan_created/slot_updated）走任务本地 EventBus（coordinator.py:176 新建 task_rt；vm/handlers/comm.py:34 用 `executor.runtime_context`）；LLM 事件（llm_dispatched/llm_resolved）走**主总线**（llm_executor/_core.py:123 用**构造时固定**的 `self._execution_context`，interpreter.py:198-201 注入主 EC）→ 跨任务观测盲区 + 语义不一致 | coordinator.py:176；vm/handlers/comm.py:34；llm_executor/_core.py:121-123 | 直接影响 PT-FEAT-9 诊断事件可达性 |
| **D4 `thread.join()` 阻塞整个 VM** | `join()` = `SpawnedTask.join()` = `Future.result()` 同步阻塞（thread.py:121；coordinator.py:120-122）；无 VM 侧协作挂起路径；且 `thread(...)` 构造即自动启动（primitive_initializer.py:712 `_ensure_started()`），`start()` 方法冗余但仍在语言面 | thread.py:108-154；primitive_initializer.py:669-719 | 并发模型局限（与 await 协作模型割裂） |
| **D5 协作取消对用户函数分支失效** | `cancel_event` 仅经 CPS `_drive_generator` 检查（coordinator.py:283-285/295/301）；`IbUserFunction` 分支（coordinator.py:215-232）调 `task_func.call()` **不传 cancel_event** → 语言层 `thread(callable=用户函数)` 任务体内**无任何取消检查点**，cancel 仅对 lambda/snapshot/behavior 生效 | coordinator.py:215-232 | 取消机制覆盖缺口 |
| **D6 三处死状态** | ① `KernelRegistry._registry_lock` 定义后从未使用（registry.py:29）；② `IRuntimeLib._event_bus` setup 后无读取（ibci_iruntime/core.py:26,30，实际走 `rc.get_comm_event_bus()`）；③ events.py:9-11 文档声明事件类型 `task_started/task_done/task_cancelled` 从未发射 | registry.py:29；iruntime/core.py:26,30；events.py:9-11 | 死代码/契约漂移 |
| **D7 文档漂移（14_concurrency.md vs 代码）** | ① 缺 `c.close()`、`t.start()`、`thread_result.unwrap()/unwrap_or()`；② `c.subscribe(buffer=0)` 参数名与实现 `size` 不匹配（doc:19 vs comm.py:68/channel.py:138）；③ `subscriber.recv_nonblocking/close` 未文档化 | 14_concurrency.md:13-19/74-99；comm.py:68/82/126/133；thread.py:89；thread_result.py:97/107 | 用户手册与实现不一致 |
| **D8 runtime.subscribe 无界缓冲** | `runtime.subscribe()` 创建 `ChannelCore(mode="stream")` 默认 `buffer=0`（无界，iruntime/core.py:65）→ 订阅者不消费则事件**无限积压**（内存风险），无驱逐/丢弃策略 | iruntime/core.py:65；channel.py:31-44；test_comm_kernel（size=0 无界） | 诊断/事件馈送内存风险 |
| **D9 主线程并发惰性创建 comm 槽无锁** | runtime_context.py:402-447 四个槽（CommRegistry/ConfigStore/EventBus/RuntimeCoordinator）为无同步惰性单例创建，依赖"每 ContextImpl 单线程写"假设；GIL 下单操作原子，风险低但**无契约文档** | runtime_context.py:402-447 | 潜在竞态（低危，无契约） |

---

## 六、影响分析

1. **对 PT-FEAT-9（内核结构化诊断机制）**：
   - 设计站在 **S3/S4/S5** 之上（订阅契约、扇出实现、comm 命名）——不先统一，诊断事件词汇表与消费者文档会固化在错误契约上。
   - **D3** 直接决定诊断事件可达性：线程任务内 VM-handler 事件进任务本地总线、LLM 事件进主总线——**不对称**；诊断机制必须先行定义"线程任务内诊断事件归属哪个总线"（§八 P4）。
   - **D8** 影响诊断事件馈送：若诊断事件也经无界 stream 通道，未消费订阅者会积压。
2. **对用户心智模型**：
   - S1/S2（命名与契约分叉）、S3（两个 subscribe）、S6（thread vs await 两模型）→ 用户面不一致，破坏"学一处处处适用"。
   - 14_concurrency.md 的文档漂移（D7）加剧。
3. **对内核维护**：
   - D1（TaskScheduler 半成品）、D6（死状态）违反"不删也不修"；S4（双扇出）双维护。

---

## 七、统一任务工作项（W1-W6，按优先级）

> 前置：完成 §八 决策点裁决；每个工作项独立 commit、全量 pytest 零回归。

| # | 工作项 | 解决 | 建议方案 |
|---|--------|------|---------|
| **W1** | 非阻塞命名与契约统一 | S1/S2 | 统一后缀（推荐 `_nowait`，与 core/发送侧一致）：用户层 `recv_nonblocking`→`recv_nowait`；契约显式分层（core 返回 `(ok,item)` 原始、用户层返回 `T\|None` 友好）并文档化 |
| **W2** | 订阅契约统一 | S3/S4 | EventBus 复用 `ChannelCore` pubsub（或同构）；`runtime.subscribe()` 返回标准订阅端点（close=干净退订），**消除 monkeypatch**；单一扇出实现 |
| **W3** | comm 命名回归 | S5 | `_comm_event_bus`→`_event_bus`、`_comm_config_store`→`_config_store`；"通信域"注释更正；`_comm_registry` 视归属保留 |
| **W4** | 死状态清理 | D6 | 删 `_registry_lock`、`IRuntimeLib._event_bus` 死字段；events.py docstring 对账为如实事件清单 |
| **W5** | 文档同步 | D7 | 14_concurrency.md 方法表补全（close/start/unwrap）；`subscribe` 参数名统一（buffer↔size）；subscriber 方法补文档 |
| **W6** | 决策后落地 | D1/D2/D3/D4/D5/D8 | 见 §八 P1-P4 裁决 + 自主项 P5-P9；含 TaskScheduler 去留、cell 隔离、线程事件模型、VM 中断机制评估 |

---

## 八、决策点

### P1-P4 需用户拍板（跨子系统语义 / 语言面契约）

| # | 决策 | 选项 | 推荐 |
|---|------|------|------|
| **P1** | thread/await 关系（S6/D4） | A 保持"彻底分离"（thread=阻塞句柄，await=协作挂起），文档化为显式双模型；B 提供 await-thread 桥（IbThread 满足 Waitable，join 可协作）；C 统一协作模型（thread.join 经 TaskScheduler 挂起） | 倾向 **A**（现行为已文档化、隔离简单），但补 D4（join 阻塞 VM）与 D5（取消覆盖）缺口说明；B/C 为远期演进（依赖 D1 决策） |
| **P2** | TaskScheduler 去留（D1） | A 接线（run_many 成为多根并发主路径，或多任务协作接入 VM 主循环）；B 移除（"不删也不修"，Stage 2 独立核心回退）；C 保留仅测试驱动 | 倾向 **A**（异步协作是 THREAD_DESIGN 既定方向；已建未接线是半成品），但属较大行为面，需评估破坏面；若暂缓则 **B**（从代码移除，规划留 THREAD_DESIGN） |
| **P3** | 闭包 cell 跨线程隔离（D2） | A 禁止（编译期或运行期检查：任务内写共享 cell 变量报错）；B 线程安全化（IbCell 加锁）；C 文档化为"引用共享"语义（cell 是显式共享内存，跨任务可写） | 倾向 **C**（最小改动、语义诚实）或 **A**（保隔离承诺）；**B 不可取**（把热路径锁进 cell，代价高） |
| **P4** | 线程任务事件模型（D3，影响 PT-FEAT-9） | A 每任务事件域（VM-handler 事件→任务总线；LLM 事件也归任务总线，修正不对称）；B 统一主总线（任务事件全部汇入主总线，需线程安全 + 明确生命周期）；C 明确定义双域并文档化（现状 + 修正 LLM 事件归属） | 倾向 **C**（先修 D3 不对称，明确"任务内 LLM 事件归主总线"为有意语义）或 **A**；此为诊断面前提 |

### P5-P9 自主可决（已给推荐，记录依据即可推进）

| # | 决策 | 推荐 |
|---|------|------|
| **P5** | 非阻塞后缀选择 | `_nowait`（与 core 一致、与 send_nowait 一致）；`recv_nonblocking`→`recv_nowait`（破坏性重命名，已授权） |
| **P6** | `runtime.subscribe()` 契约 | 复用 pubsub/subscriber 惯用法，返回标准订阅端点，消 monkeypatch（与 P2A 联动） |
| **P7** | comm 命名回归 | 去 comm 前缀（W3）；`_comm_registry` 保留（通信对象注册表名实相符） |
| **P8** | 死状态删除 | W4 全部删除；events.py 对账 |
| **P9** | VM 中断机制（D5 缺口） | 本次不新增通用 VM 中断 API（超出本统一任务范围）；D5 取消覆盖缺口（用户函数分支）作为独立小修复项记录 |

---

## 九、关联文档

- `DIAGNOSTIC_DESIGN.md`（PT-FEAT-9）：诊断机制设计冻结，**依赖 §八 P4 决策**。
- `THREAD_DESIGN.md`：并发/协程设计（Stage 2 已落地、Stage 3 规划）；D1（TaskScheduler）与其"多任务协作"方向直接相关。
- `docs/syntax/14_concurrency.md`：用户面并发/通信手册（D7 文档漂移源）。
- `docs/architecture/04_vm_interpreter.md`：VM 架构（CPS 调度、三层并发模型 §5.1）。
- `docs/KNOWN_LIMITS.md` §二十二：通信原语面（signal 移除裁定）。
- `OBSERVABILITY_REFACTOR.md`：观测骨架（S3/S4/S5 的历史来源）。

---

## 十、决策记录

| 日期 | 决策 | 依据 |
|------|------|------|
| 2026-08-07 | 确认"用户面=内核面同一底层体系"为设计优点，统一任务**不重建 comm 原语**，只统一命名/契约/扇出/命名空间 | 机制复用健康（ChannelCore/SlotCore/Waitable/RuntimeCoordinator 共享）；碎片在语义命名层 |
| 2026-08-07 | **统一任务先于 PT-FEAT-9**；诊断机制设计（DIAGNOSTIC_DESIGN.md D1-D7）概念不变，落地待 P4 裁决 | 诊断机制站在 S3/S4/S5 + D3 之上，先统一避免返工 |
| 2026-08-07 | 决策点 P1-P4 上报用户拍板；P5-P9 自主可决（推荐已列） | 跨子系统语义/语言面契约（P1-P4）触及上报阈值；命名/清理（P5-P9）属自主范围 |

---

## 十一、方向定案与任务重排（2026-08-07 增补）

> **用户裁定（2026-08-07）**：价值前提 = 系统设计优秀与统一、可维护性、宏观合理性、长期收益优先；**难度与工作量不在权衡之列**。

### 11.1 定案：adopt 统一协作任务模型（P1/P2 不再二选一）

- **协作调度成为 VM 唯一执行模型**（P1 adopt + P2 接线 + 线程-await 桥）。
- 排除 "abandon / 保持双轨"：CPS 架构价值兑现点即协作调度；双轨=半成品，违背"不删也不修"；
  每个停摆项都将重开地基之争（长期补账）。
- **目标端态**：任务抽象统一（LLM/宿主/线程完成/用户 async fn/流 = 一个 Waitable 家族）；
  主 VM 跑在调度器上（单栈阻塞 = 单任务退化情形，两条驱动循环合一）；**阻塞即挂起**（任务内
  一切等待挂起让出；OS 线程任务本地循环真阻塞）；线程 = I/O 并行任务且完成可 await；
  取消协作式覆盖全任务体；yield 点快照 × llmexcept 闭合；语言面 async fn/yield 在此长出。

### 11.2 消解映射

| 缝 | 消解 |
|----|------|
| D1 调度器未接线 → 接线为唯一执行核心；D4 join 阻塞 → 任务内挂起；S6 双轨 → 线程完成=Waitable |
| S3 双订阅契约 → 订阅端点可等待统一惯用法；S4 双扇出 → EventBus 复用 ChannelCore pubsub |
| D3/P4 事件归属 → 计算隔离、观测全局（全局事件总线）；D5 cancel → 挂起点统一检查 |

### 11.3 任务重排（W1-W6 从主线降级为阶段 3 机械清理）

> **2026-08-07 更新**：阶段 1/3 已落地（unsafe-vibe-dev）；阶段 1-3 暴露的妥协处理列 **R 批次**
> （`EXEC_REFACTOR_BATCH.md`）为下一主线（R1 trampoline/R2 通知式唤醒/R3 D-04 unify/R4 P3 公开/R6 函数自动捕获），
> 之后为 PT-FEAT-9（阶段 4）与 yield（阶段 5）。下表为原定案顺序（历史记录）。

| 阶段 | 内容 | 性质 |
|------|------|------|
| 0 | 统一执行地基设计定案（任务抽象/调度器接入/阻塞即挂起/线程桥/取消/yield 快照×llmexcept/语言面形态）——tasks_docs 设计冻结 | 设计（零代码） |
| 1 | 地基实现（独立分支实验）：调度器接入主路径、线程桥、取消全路径、快照交互 | 实现+实验 |
| 2 | 语言面 async fn/yield（同一地基上，PT-FEAT-1 解封） | 实现 |
| 3 | 统一清理：W1-W5/P3/P4（命名、订阅契约、命名空间、死状态、文档、cell 隔离、全局事件总线） | 机械统一 |
| 4 | PT-FEAT-9 诊断机制（全局事件总线之上） | 实现 |
| 5 | 增量：streaming、host async 改进、PT-FEAT-1 剩余面 | 增量 |

### 11.4 硬骨头（影响资源安排，不影响决策）

1. yield 点快照 × llmexcept（挂起帧状态保存/恢复/序列化 × retry 语义闭合）。
2. 阻塞即挂起：comm 等待语义重写 + 相关测试迁移。
3. 热路径（调度器进主循环）正确性 + 全量测试迁移（独立分支实验政策）。
