# WORKLOG — 自主工作日志

> 记录所有自主决策、质询分析、方案取舍、变化前后（实现 + 测试 + 文档）。
> 原则：**"只记录，不断决"**——能自主决定的记录决定并推进；只有确实无法决定的才标记待决并上报。
> 最后更新：2026-08-04

---

## 2026-08-04 会话 2：线程对象模型方向修正（设计决策，未实现）

### 背景

PT-MT-1~8 主线实现完成后，对 spawn/join/cancel/task 关键字设计进行深度质询，确认存在设计缺陷：async/thread 领域混淆、关键字冗余（cancel→方法、join 与 await 重叠、spawn 与 fn 重合）、类型精度不足（join 返回 any 兜底）、系统碎片化（F-1~F-8）。

### 用户裁定（完整记录见 `tasks_docs/THREAD_DESIGN_REVISION.md`）

1. **async 与 thread 彻底分离**：`IbTask` 不得满足 Waitable；await 只服务异步；线程走句柄方法。
2. **关键字精简**：删 spawn/join/cancel/task，改用 `thread` 类型 + 句柄方法（疏漏 1 裁决：无用关键字直接删除）。
3. **`thread[T]` 泛型标注必须**（非参数传递）；返回类型显式标注；`thread[void]` 支持。
4. **`thread_result[T]` 泛型容器**：成功值/错误/状态，可继承可改写，禁止 any。
5. **配套方法**（Rust 对齐）：`unwrap()→Optional[T]` / `unwrap_or(default)` / `is_error()` / `.value`(fail-fast) / `.error`。
6. **err 类型统一**：接入既有 Exception 体系；TaskCancelled/TaskFailed 映射 IBCI 子类；`t.cancel()` 返回 err。
7. **挂起机制取消**（未来也不做）：无损挂起=协程帧保存，与领域分离冲突 + 高难度。
8. **统一泛型模型立即启动**：内置类型泛型化正式机制；`thread[T]` 首个消费者；不含用户级泛型类/约束求解。
9. **Optional 配套**：查证现状——编译期特化完整，**运行时无 IbOptional 对象**（`Optional[int] x = None` 的 `x.is_some()` 运行时失败）；补齐运行时实现。

### 疏漏裁决

- 疏漏 1：无用关键字直接删除。
- 疏漏 2：通信领域（chan/signal/slot）完善与统一化检查 = **下阶段任务，暂缓**。
- 疏漏 3：**大范围重构直接开始**，允许推翻/删除既有代码。
- 疏漏 4：内省用明确方法（非裸属性）；线程对象/容器瞬态；save_state 检测未完成线程则抛异常 fail。
- 疏漏 6：废除相关旧测试，新机制测试单独制作。

### 变化前后
- **新增**：`tasks_docs/THREAD_DESIGN_REVISION.md`（方向修正完整决策记录）。
- **修改**：无代码改动（本轮仅设计讨论与记录，按用户指示暂不实现）。

### 授权实现（2026-08-04）
- **用户裁定**："授权实现。完善相关决策文档。"——全部任务 A-F 已授权，含 Optional 配套完整实现。
- **决策文档更新**：`THREAD_DESIGN_REVISION.md` 状态改为"已授权实现"，任务清单细化为可执行计划（含验收标准），新增"实施细节"节（线程创建语法/容器成员/既有内核处置/分支政策：已确认边界，当前分支直接开始）。

### 待决
- 无。任务 A-F 已授权，待启动实现（顺序：A Optional 配套 → B 统一泛型模型 → C 线程对象模型 → D err 类型 → E 清理 → F 关键字精简+测试）。

---

## 2026-08-03 会话 1：主线交接 + PT-MT-1 详细设计文档

### 决策记录

#### 1. 禁止 push 硬原则（用户裁定）
- **内容**：非明确指示允许，一律禁止 `git push` 到任何远程仓库。全程只本地 commit；push 必须等用户显式授权。
- **落点**：`AGENTS.md`（新增硬原则块）、`.opencode/skills/code-workflow/SKILL.md`（Phase 5 交付纪律）、`tasks_docs/_HANDOFF.md`（三处）。

#### 2. 破坏性重构授权 + 分支政策（用户裁定 2026-08-03 补充）
- **破坏性重构授权**：符合一般工程经验/普适性/合理架构设计且经分析确实优于 IBCI 现有体系及已有代码时，哪怕设计已被文档记录也允许破坏性重构；不禁止修改已有代码；已有代码优先级低于架构正确性。默认已授权自主推进。
- **分支政策**：无法确认边界/危害程度的破坏性重构，100% 授权独立分支（不污染 main/unsafe-vibe-dev、不污染环境与用户目录）；仅当独立隔离分支也无法确定技术路线才阻塞；独立分支禁止直接合并到 unsafe-vibe-dev/main，确认技术路线后仅允许手动单独更新 unsafe-vibe-dev；永不触碰 main。
- **落点**：`AGENTS.md`、`NEXT_STEPS.md`（工作模式定论第 8/9 条）、`code-workflow/SKILL.md`、`THREADING_DESIGN.md`、`_HANDOFF.md`、goal。

#### 3. 全自主 goal 配置（用户裁定）
- 硬性定时 `max_duration_seconds=37217`（对应 2026-08-04 08:00 CST）+ `max_auto_turns=300`。
- goal 目标含：主线 PT-MT-1~8、自主推进偏好、禁止 push、破坏性重构授权与分支政策、支线、停止条件、非目标。
- 当前 session 仅做 PT-MT-1（设计文档），产出后停在用户审阅点，不越界实现。

#### 4. PT-MT-1 详细设计文档（自主决策记录）

产出 `tasks_docs/THREADING_DESIGN_DETAIL.md`（724 行），关键自主决策：

- **D-chan-method**：`chan.send/recv`/`slot` 读写**复用 `IbCall` + 对象方法分发**，不新增专用 AST 节点（避免与既有 `IbCall` 双通道，符合工作模式定论第 4 条）。§2.1 中的 `IbChanSend`/`IbChanRecv`/`IbSlotRead`/`IbSlotWrite` 明确不落地。
- **D-type-keyword（self-grill 修正）**：`task`/`chan`/`signal`/`slot` 作关键字会破坏 `parse_type_annotation`（`type_def.py` 仅接受 IDENTIFIER/AUTO/FN/NONE）。**必须**在 `parse_type_annotation` 新增 TASK/CHAN/SIGNAL/SLOT 分支，遵循 `fn`/`auto`/`None` 前例。
- **D-spawn-thread**：`spawn` 任务是**后台线程**（真并行，供实时 UI/输出刷新）；`TaskScheduler`/`run_many` 保留为内部 LLM 协作式并发。两者分工不同，不混用。
- **D-executor-per-vm**（D6）：每轻量 VM 实例独立 `LLMExecutorImpl`（自有单写槽/线程池），延续 Stage 1 去共享化，避免跨任务写竞争。
- **D6-D9 待决项**：均给出自主推荐，无阻塞用户项；用户审阅设计时若异议可调整。

#### 5. PT-MT-1 独立审查修正（通用 agent，只读验证）

对 `THREADING_DESIGN_DETAIL.md` 做独立只读审查（10 项代码库对照验证），发现并修复 6 处：

1. **spawn/join 表达式位置缺口（落地级硬伤）**：`task t = spawn compute(...)` 中 spawn 在 `=` 右侧表达式位置，但 §2.3 只注册语句。修复：SPAWN/JOIN 注册**表达式前缀规则**（同 AWAIT 模式），产出带 target 的语句节点。
2. **`task` 关键字 vs 变量名冲突**：§2.1 示例 `task = spawn fn(...)`（task 作变量名）与 §2.2 `task` 作保留字矛盾。修复：`task` 为保留字禁作变量名（与 fn/lambda/auto 一致），示例改用 `t`/`t2`/`renderer`。
3. **IbTaskRef 未收敛**：§2.1 定义但 §2.3/§2.6 不含。修复：移除 IbTaskRef，明确任务句柄是 spawn 运行时返回的 `IbObject`（`IbTask`），非 AST 节点。
4. **`chan T(...)` vs `chan(T, ...)` 机制未交代**：修复：明确 chan_expr 首参经 `parse_type_annotation`（含 `chan(str,...)` 中 str 是类型名的说明），两形态产出同一节点。
5. **"match 链"措辞**：`_parse_statement_core` 实为 if 分派链，修复措辞。
6. **基线数字冻结**：§9.3 改为"以实跑为准，不冻结数字"（AGENTS.md 纪律）。

### 变化前后
- **新增**：`tasks_docs/THREADING_DESIGN_DETAIL.md`（PT-MT-1 详细设计文档，736 行）、`tasks_docs/WORKLOG.md`（本工作日志）。
- **修改**：`AGENTS.md`（push 硬原则 + 破坏性重构授权 + 分支政策）、`tasks_docs/NEXT_STEPS.md`（工作模式定论第 8/9 条 + PT-MT-1 状态）、`tasks_docs/PENDING_TASKS.md`（PT-MT-1 已完成待审阅）、`tasks_docs/THREADING_DESIGN.md`（用户裁定表补充）、`tasks_docs/_HANDOFF.md`（授权原则/goal 模板/上报阈值/关键约束同步）、`.opencode/skills/code-workflow/SKILL.md`（Phase 5 交付纪律 + 配套原则）。
- **测试**：全量 pytest 1322 passed / 4 skipped 零回归（设计文档阶段无代码改动）。

### 待决（无需用户立即裁决）
- PT-MT-1 设计文档待用户审阅（尤其编译器改造范围、多 VM 实例共享只读数据边界、D6-D9）。**注：按用户自主推进偏好（最高优先，仅次于硬性定时），PT-MT-2 已自主推进落地；用户仍可随时审阅设计文档并调整。**

#### 6. PT-MT-2 编译器地基（自主实现，2026-08-03）

按 `THREADING_DESIGN_DETAIL.md` §二落地编译器地基，全量 pytest 零回归（1341 passed/4 skipped，+18 测试）。

**实现内容**：
- **AST**（`core/kernel/ast.py`）：新增 `IbSpawnStmt`/`IbJoinStmt`/`IbCancelStmt`（语句）+ `IbChannelExpr`/`IbSignalExpr`/`IbSlotExpr`（表达式）。移除设计稿中的 IbTaskRef（任务句柄是运行时对象非 AST 节点）。
- **Token/Lexer**（`tokens.py`/`core_scanner.py`）：SPAWN/JOIN/CANCEL/CHAN/SIGNAL/SLOT/TASK 7 关键字。
- **Parser**（`statement.py`/`expression.py`/`type_def.py`/`recognizer.py`）：
  - statement if-链注册 spawn/join/cancel；expression 前缀规则注册 spawn_expr/join_expr/chan_expr/signal_expr/slot_expr（spawn/join 表达式位置，`task t = spawn fn(...)`）。
  - type_def 新增 TASK/CHAN/SIGNAL/SLOT 类型分支；recognizer 把 task/chan/signal/slot 识别为 VARIABLE_DECLARATION。
- **类型注册**：TypeKind.TASK/CHANNEL/SIGNAL/SLOT + TASK_SPEC/CHANNEL_SPEC/SIGNAL_SPEC/SLOT_SPEC + 新 axiom 模块 `core/kernel/axioms/primitives/comm.py`（TaskAxiom/ChannelAxiom/SignalAxiom/SlotAxiom）。
- **语义**：`visit_IbSpawnStmt`（spawn 目标可调用校验，task 返回类型）、`visit_IbJoinStmt`/`visit_IbCancelStmt`（目标必须 task 类型）、`visit_IbChannelExpr`/`visit_IbSignalExpr`/`visit_IbSlotExpr`。
- **序列化**：vars(node) 通用序列化自动覆盖新字段，round-trip 验证通过。

**关键自主决策**：
- spawn/join 同时注册语句与表达式前缀（审查修正 #1 的落地）。
- `spawn compute("x")` 中 func 为 IbCall 节点（call 嵌入 func），args 字段保留给 `spawn(fn, args)` 形态——语义层对 IbCall 校验被调用者（func.func）可调用。
- `join` 返回类型当前保守为 any（任务-返回类型跟踪表留到 PT-MT-7 绑定，符合设计 §2.4）。

**变化前后**：+2 文件（comm.py axiom、test_concurrency_syntax.py），+7 修改文件。

**测试**：新增 `tests/compiler/test_concurrency_syntax.py`（18 用例：lexer 关键字、parser 节点、类型注解、语义正/负样本、序列化 round-trip）。全量 pytest 1341 passed/4 skipped 零回归。

#### 7. PT-MT-3 统一通信内核（自主实现，2026-08-03）

按 `THREADING_DESIGN_DETAIL.md` §三落地统一通信内核，全量 pytest 零回归（1382 passed/4 skipped，+41 测试）。

**实现内容**：
- **线程安全内核**（`core/runtime/shared/comm/`）：
  - `buffer.py` CommBuffer（threading.Condition 单锁、有界 send/recv、非阻塞、close 语义、qsize、snapshot）
  - `channel.py` ChannelCore（stream/message/pubsub 三模式、pubsub 每订阅者 CommBuffer 扇出）
  - `signal.py` SignalCore（frozen dataclass、kind 白名单 cancel/pause/resume/config_change、定向/广播）
  - `slot.py` SlotCore（get/set/update 原子读改写——锁外计算 + CAS 回写，避免锁内回调死锁，设计 D4 定案）
  - `registry.py` CommRegistry（name→对象、kind 枚举、snapshot）
- **语言层对象**（`core/runtime/objects/kernel/comm.py` + `core/runtime/objects/task.py`）：
  - `IbChannel`（send/recv/recv_nonblocking/close）、`IbSignal`、`IbSlot`（get/set/update）、`IbTask`（spawn 句柄）
  - `@register_ib_type` 注册，primitive_initializer axiom 驱动自动绑定方法
- **dispatch handler**（`core/runtime/vm/handlers/comm.py`）：6 个新节点全部接入 VM。
- **spawn/join/cancel 执行模型（关键决策）**：PT-MT-3 阶段为**协作式延迟任务**——spawn 记录可调用+实参不立即执行，join 触发求值（当前 VM 线程），cancel 在未启动时标记取消。**刻意不做后台线程**：后台线程共享 runtime_context 会产生作用域竞争（违反并发正确性 C4），轻量 VM 实例隔离在 PT-MT-7/8 落地时升级执行路径（任务句柄接口不变）。此决策符合工作模式定论（非 shim：任务抽象完整、语义自洽）。

**关键 bug 修复**：`vm_handle_IbChannelExpr` 原为普通函数（非生成器），违反 VM CPS handler 必须为 generator 的契约（`gen.send` 在非生成器上 AttributeError → VM 主循环死循环）。修复：加 `if False: yield` 保持生成器身份（对齐 `vm_handle_IbPass` 模式）。

**变化前后**：+7 文件（comm 包 6 模块、objects/comm.py、objects/task.py、handlers/comm.py、2 测试文件），+4 修改文件。

**测试**：`tests/runtime/test_comm_kernel.py`（33：CommBuffer 并发吞吐、Channel 三模式、pubsub 扇出、Signal 不可变、Slot 并发 update 100 线程 +1、CommRegistry）+ `tests/runtime/test_vm_comm.py`（8：语言面 e2e）。全量 pytest 1382 passed/4 skipped 零回归。

#### 8. PT-MT-4 内省层（自主实现，2026-08-03）

按 `THREADING_DESIGN_DETAIL.md` §四落地内省层，全量 pytest 零回归（1388 passed/4 skipped，+6 测试）。

**实现内容**：
- **快照聚合**（`core/runtime/observability/snapshot.py`）：`snapshot(executor)` 聚合 tasks（TaskScheduler 就绪/等待）、channels/slots（CommRegistry）、vms（解释器实例）、vars（模块级变量）、llm（pending_futures/call_info）。
- **事件流**（`core/runtime/observability/events.py`）：`EventSource`/`EventSink` 协议 + `EventBus`（线程安全广播）+ `ChannelSink`（推入 stream Channel）+ `RuntimeEvent`（不可变值对象）。
- **iruntime 模块**（`ibci_modules/ibci_iruntime/`）：kernel-native 模块（`KERNEL_NATIVE_MODULES` 注册）。`snapshot()` → dict；`subscribe()` → stream Channel（关闭即退订）。事件总线挂在 runtime_context 上（`_comm_event_bus`，与 CommRegistry 同级）。
- **VM 事件源**：comm handlers 在 chan/slot/spawn/join/cancel 处 emit（chan_created/slot_updated/task_started/task_done/task_cancelled）。

**关键修复**：
1. **关键字作成员名（设计遗漏修正）**：`iruntime.snapshot` 中 `snapshot` 是保留关键字（lambda snapshot 语法），`dot` 解析只接受 IDENTIFIER 导致 "Expect property name after '.'" 编译失败。修复：`dot`/`_parse_complex_access` 新增 `_consume_member_name()`——接受标识符样关键字（`val.isidentifier()`）作成员名，运算符等仍拒绝（Python 风格）。这是通用改进，非特例。
2. **ChannelSink 传参 bug**：`subscribe()` 误传 `event_bus` 而非 `core` 给 `ChannelSink`，事件推入 EventBus 而非 Channel。修复后事件流送达。
3. **chan 关键字参数解析**：`chan(str, "stream", name="my_ch")` 的 name= 关键字参数未处理。修复 chan_expr 解析逻辑。

**测试**：`tests/runtime/test_observability.py`（6：snapshot 字段、命名 channel 跟踪、subscribe 事件流、关键字成员访问）。全量 pytest 1388 passed/4 skipped 零回归。

#### 9. PT-MT-5 控制层（自主实现，2026-08-03）

按 `THREADING_DESIGN_DETAIL.md` §五落地控制层，全量 pytest 零回归（1393 passed/4 skipped，+5 测试）。

**实现内容**：
- **ConfigStore**（`core/runtime/observability/config.py`）：全局→单调用→单实例三表链式覆盖，查询按 单实例→单调用→全局→默认 顺序解析（读时解析不缓存陈旧，单点真理）。默认：parallel/stream/observability=开、debug=关。
- **iruntime.configure/get_config**：VAR_KEYWORD 参数形态（`runtime.configure(parallel=False, debug=True)`），支持 `instance=`/`task=` 作用域定位。变更广播 `configured` 事件（observability 开启时）。
- **实际门控**：`parallel` 门控 dispatch_eager（`_parallel_enabled`，关闭走同步串行）；`observability` 门控事件流（`_emit_event` 关闭时抑制 chan/slot/task 事件）。

**关键决策**：configure 采用 VAR_KEYWORD vtable 参数而非固定参数——`configure(parallel=, stream=, ...)` 接受任意配置键，避免硬编码参数列表（工作模式定论：协议驱动）。语义层经 VAR_KEYWORD 契约校验（loader.py 已支持）。

**测试**：`tests/runtime/test_runtime_configure.py`（5：默认值、configure 生效、observability 门控、配置持久）。全量 pytest 1393 passed/4 skipped 零回归。

#### 10. PT-MT-6 流式 + 并行（自主实现，2026-08-03）

按 `THREADING_DESIGN_DETAIL.md` §六落地流式，全量 pytest 零回归（1401 passed/4 skipped，+8 测试）。

**实现内容**：
- **流式 provider 接口**（`ibci_modules/ibci_ai/core.py` `AIPlugin.stream()`）：ILLMProvider 协议扩展。MOCK 模式返回单块（进程内）；真实模式 OpenAI `stream=True` 逐 delta 产出增量迭代器。
- **IbStreamHandle**（`core/runtime/objects/stream.py`）：Waitable 协议 + stream Channel；后台线程消费迭代器逐块推入 Channel；`result()` 阻塞等待完整文本（修复：`_drive_gen_blocking` 直接 `waitable.result()` 不轮询 is_done，result() 必须阻塞 join 线程）。
- **Mock 流式**：`MOCK:STREAM:chunk1|chunk2|...` 指令（`MockScenarioResult.chunks`）+ MockServer `_respond_stream` 多块 SSE（真实 OpenAI 客户端流式收到分块）。
- **语言面**：`ai.stream_call()`（Waitable，await/赋值自动等待完整文本）+ `ai.stream_channel()`（返回承载增量块的 IbChannel，渲染线程 recv 逐块）。

**关键决策**：流式与并行（dispatch_eager/run_many）保持独立（设计 §六.1），都默认开启；`stream` config 键已注册但接入点在行为表达式自动流式（未来），当前经 ai.stream_call/stream_channel 显式暴露（非双通道——显式 API 是流式的一等入口）。

**测试**：`tests/runtime/test_streaming.py`（8：IbStreamHandle 单元、STREAM 指令、MockServer SSE 真实客户端、stream_call await/赋值、stream_channel 增量渲染）。全量 pytest 1401 passed/4 skipped 零回归。

#### 11. PT-MT-7 多 VM 实例（自主实现，2026-08-03）

按 `THREADING_DESIGN_DETAIL.md` §七落地多 VM 实例，全量 pytest 零回归（1407 passed/4 skipped，+6 测试）。

**实现内容**：
- **`core/runtime/coordinator.py`**：`RuntimeCoordinator`（spawn/lookup/is_done/join/cancel/snapshot）+ `SpawnedTask`（后台线程 + `concurrent.futures.Future` 结果槽，Waitable 协议）。
- **任务本地执行上下文**（`_run_task_body`）：fresh `RuntimeContextImpl` + `setup_context` 注入内置；fresh `ExecutionContextImpl`（共享只读 node_pool/side_tables/factory，任务本地 runtime_context/LogicalCallStack/current_module）；fresh `VMExecutor`。线程本地 ContextVar（`set_current_frame`/`set_current_execution_context`）保证任务线程内 LLM/内省解析到任务上下文。
- **IbTask 升级**：后台线程句柄（`_ensure_started` 惰性启动，join 阻塞等 Future 结果，cancel 协作式）。
- **spawn 支持**：用户函数（IbUserFunction.call）/ lambda/fn_callable（`_vm_call_fn_callable` CPS）/ behavior（`_vm_invoke_behavior`）。

**关键决策**：
- spawn 从 PT-MT-3 的"协作式延迟任务"升级为"后台线程 + 任务本地上下文"——实现用户裁定"用户可见多线程"（实时 UI/输出刷新）。任务隔离遵循并发正确性 C4（per-task 所有权）+ C5（全局只读）。
- cancel 为协作式（Python 无法强杀线程）：未启动可取消；运行中任务无法中断（挂起点检查在 PT-MT-8 细化）。
- 共享注册表/artifact/node_pool 只读（C5），任务写隔离经作用域隔离天然保证。

**测试**：`tests/runtime/test_vm_instance.py`（6：后台函数 spawn、lambda spawn、多任务、作用域隔离、cancel、snapshot 任务字段）。全量 pytest 1407 passed/4 skipped 零回归。

#### 12. PT-MT-8 用户代码多线程收尾（自主实现，2026-08-03）

主线 PT-MT-1~8 **全部完成**，全量 pytest 零回归（1409 passed/4 skipped）。

**实现内容**：
- **eager spawn**（`objects/task.py`）：IbTask 构造即 `_ensure_started()`（后台线程立即运行），非惰性——主线程无需 join 即可收到 worker 经 Channel 的输出（实时 UI/输出刷新）。
- **协作式取消**（`core/runtime/coordinator.py`）：`TaskCancelled` 异常 + `SpawnedTask.cancel()` 设置取消事件；任务在挂起点（`_drive_generator` 的 Waitable 等待 / 子节点驱动前）检查 `cancel_event`，命中即抛 `TaskCancelled`（join 时重抛）。纯 CPU 任务无可挂起点时 cancel 无法强制中断（Python 无法强杀线程，文档注明）。
- **任务本地函数包装**：IbUserFunction 构建 task-local 副本（绑定 task EC），使函数体经任务 runtime_context 驱动，避免共享主上下文作用域竞争（修复跨线程 channel send 场景）。
- **实时输出场景验证**：`spawn worker(chan out)` 后台逐块 send，主线程 recv 渲染。

**测试**：`test_vm_instance.py` 新增 2（实时输出 worker→Channel→主线程 recv、eager start 后台运行）。全量 pytest 1409 passed/4 skipped 零回归。

#### 13. 交接准备（2026-08-04）

- 更新 `_HANDOFF.md`：反映当前真实状态（PT-MT-1~8 完成 → 方向修正已授权未实现、任务 A-F、完整 goal 工作原则模板）。
- 提炼用户**系统级设计哲学** → 新增 `.opencode/skills/design-philosophy/SKILL.md`（单一权威源/设计语言统一/设计思路统一/机制同构/配合模式统一/一致性先于便利/宏观反思/命名粒度统一），注册进 `skills/README.md` + `AGENTS.md`。
- 同步 `NEXT_STEPS.md`（当前主线改为方向修正任务 A-F）+ `PENDING_TASKS.md`（PT-MT 系列标完成 + 记录方向修正）。

> 注：用户两次纠正 design-philosophy 提炼方向——第一次误提炼为 IBCI 语言特性（不合格），第二次才对准"系统级统一性"（碎片化/设计语言/设计思路/机制/配合模式/一致性/宏观反思/命名）。此为重要教训：提炼用户工作哲学应抓**宏观元层面**（系统统一性），而非项目专属特性。

---

## 2026-08-04 会话 3：任务 A — Optional 配套完整实现（自主实现）

### 背景

按 `THREAD_DESIGN_REVISION.md` 任务 A 实施。查证现状：Optional 编译期（`Optional[T]` spec 特化、`resolve_member` 返回包装类型、空安全编译期校验、artifact 还原）已完整；**运行时无 `IbOptional`**——`Optional[int] x = None` 是裸 `IbNone`，`x.is_some()` 运行时失败（"Object of type 'None' has no method '__call__'"）。

### 设计决策

1. **`IbOptional` 运行时值类**（`core/runtime/objects/primitives/optional.py`，`@register_ib_type("Optional")`）：包装内层值 + `is_some` 标志。方法表面 `is_some`/`unwrap`/`or_else` 由 `OptionalAxiom` 声明，经 `primitive_initializer` 的 axiom-driven auto-bind 自动绑定到语言层（复用既有 spec/axiom/factory 基础设施，符合"机制同构"）。
2. **绑定入口单一化**：`ScopeImpl` 新增 `_wrap_optional(value, declared_type)`——当 `declared_type.kind == OPTIONAL` 且值非 `IbOptional` 时包装为 `IbOptional`（幂等，不重复包装）。在 `define`/`assign`/`assign_by_uid` 三处调用（覆盖变量定义、重赋值、函数参数、LLMFuture 解析回写）。这是 Optional 运行时值的**单一权威入口**（design-philosophy：单一权威源，反碎片化）。
3. **`Optional` 基础可赋值性**：`_assignability.py` 中 `Optional`（wrapped=any）→ `Optional[T]` 返回 True（复制 Optional 场景 `Optional[int] y = x` 需要）。否则基础 Optional 无法赋值给特定 Optional[int]。
4. **值协议补齐**：`OptionalAxiom.get_method_specs()` 增加 `to_bool`/`cast_to`/`__to_prompt__`（auto-bind 只绑定 axiom 声明的方法，`to_bool` 若不声明会落到基类 Object 默认 True）。
5. **序列化**：serializer 增加 `_type=="optional"`（is_some + inner），deserializer 增加对应分支。

### 变化前后

**实现（新增）**：
- `core/runtime/objects/primitives/optional.py`（IbOptional：is_some/unwrap/or_else/to_native/__to_prompt__/to_bool/cast_to/receive(__eq__/__ne__)/serialize_for_debug）
- `tests/runtime/test_optional_runtime.py`（17 用例：is_some/unwrap/or_else/复制/重赋值/类型覆盖/空 unwrap fail-fast/真值/序列化 round-trip）

**实现（修改）**：
- `core/runtime/objects/primitives/__init__.py`（注册 IbOptional）
- `core/runtime/interpreter/runtime_context.py`（`_wrap_optional` + define/assign/assign_by_uid 三处接入 + 导入）
- `core/kernel/spec/registry/_assignability.py`（Optional 基础 → Optional[T] 可赋值）
- `core/kernel/axioms/primitives/sentinels.py`（OptionalAxiom 增加 to_bool/cast_to/__to_prompt__ 方法表面）
- `core/runtime/serialization/runtime_serializer.py`（serialize + deserialize optional 分支）

**测试**：全量 pytest **1426 passed / 4 skipped**（1409 + 17 新增，零回归）。

### 待决
- 无。任务 A 完成，校验通过。下一步任务 B（统一泛型模型）。

---

## 2026-08-04 会话 3：任务 B — 统一泛型模型（自主实现）

### 背景

按 `THREAD_DESIGN_REVISION.md` 任务 B 实施。查证现状：内置泛型类型（list/dict/tuple/Optional/fn_callable/behavior）的创建、特化、序列化、还原散落多个 ad-hoc 入口——`SpecFactory.create_*` 方法、`_assignability.resolve_specialization` 的 fn/Optional 函数特判 + Axiom 的 `resolve_specialization_by_names`、`TypeRef.from_spec` 的 kind 分派、`artifact_rehydrator` 的 kind 分派。这是碎片化（design-philosophy：单一权威源/机制同构）。

### 设计决策

1. **`GenericTypeDeclaration` + `GenericTypeRegistry`**（`core/kernel/spec/generic.py`）：内置泛型类型声明的单一权威源。每个声明描述生命周期四操作——`build`（创建）、`to_typeref`（序列化）、`restore`（还原）。注册表同时按 name 与 kind 索引。
2. **统一创建入口**：`SpecRegistry.resolve_specialization` 改为按基础名查注册表，经 `decl.build` 创建 + register + bootstrap axiom 方法。删除 `fn`/`Optional` 函数特判中的旧 `Optional` 分支（保留 `fn[RETURN]` 的表达式侧推断特判）。
3. **删除历史遗留路径**：删除 `Optional/List/Dict/Tuple` Axiom 的 `resolve_specialization_by_names` 方法（死代码），删除 `resolve_specialization` 的遗留兜底分支（axiom `resolve_specialization_by_names` 路径）。用户明确要求"不保留历史包袱，最终删除"。
4. **`thread[T]` 首个消费者**：新增 `THREAD_SPEC`（kind=TASK，`_axiom_name="thread"`）、`ThreadAxiom`（start/join/cancel/is_done 方法表面）、`SpecFactory.create_thread`，注册进 `GenericTypeRegistry`。`_members.py` 增加 thread 特化（`thread[T].join()` → T）。
5. **序列化/还原**：serializer 增加 thread 的 `value_type_name/module` 持久化；rehydrator 增加 TASK→thread shell 创建与值类型填充。

### 变化前后

**实现（新增）**：
- `core/kernel/spec/generic.py`（GenericTypeDeclaration + GenericTypeRegistry + 内置声明 + 默认注册表）
- `tests/kernel/test_generic_model.py`（16 用例：注册表完备性/统一解析/thread 泛型/to_typeref/遗留路径删除验证）

**实现（修改）**：
- `core/kernel/spec/registry/_assignability.py`（resolve_specialization 统一走注册表，删除遗留路径）
- `core/kernel/spec/registry/_base.py`（SpecRegistry 持有 generic_types 注册表）
- `core/kernel/spec/registry/factory.py`（新增 create_thread）
- `core/kernel/spec/registry/_members.py`（thread[T].join → T 特化）
- `core/kernel/spec/specs.py`（新增 THREAD_SPEC）
- `core/kernel/spec/registry/_runtime.py`（注册 THREAD_SPEC）
- `core/kernel/axioms/primitives/comm.py`（新增 ThreadAxiom）
- `core/kernel/axioms/primitives/registry.py`（注册 ThreadAxiom）
- `core/kernel/axioms/primitives/sentinels.py`（删除 OptionalAxiom.resolve_specialization_by_names）
- `core/kernel/axioms/primitives/sequences.py`（删除 List/Dict/TupleAxiom.resolve_specialization_by_names）
- `core/compiler/serialization/serializer.py`（thread 值类型持久化）
- `core/runtime/loader/artifact_rehydrator.py`（thread shell 创建 + 值类型填充）

**测试**：全量 pytest **1443 passed / 4 skipped**（1426 + 17 新增，零回归）。

### 待决
- 无。任务 B 完成，校验通过。下一步任务 C（线程对象模型 thread[T] + 句柄方法 + 状态机）。

---

## 2026-08-04 会话 3：任务 C 调研 + 交接准备（用户要求暂停）

### 背景

任务 A、B 完成后进入任务 C（线程对象模型）调研。用户中途要求暂停所有工作、停止自动化 goal，并准备交接以便下一 session 接手。

### 任务 C 调研结论（已确认，供下一 session 使用，勿重复调研）

- **`thread` 类型已就绪**：`registry.get_class("thread")` 存在（ThreadAxiom 驱动创建）；`thread[T]` 解析经 GenericTypeRegistry 工作（`thread[int]` 解析成功、kind=TASK、`get_base_name()="thread"`、`value_type.head="int"`）。
- **`thread[T].join()` 返回类型特化已就绪**（`_members.py` thread 特化：`thread[T].join()`→T）。
- **既有内核机制可复用**：`core/runtime/coordinator.py` 的 `RuntimeCoordinator` + `SpawnedTask`（后台线程 + 任务本地执行上下文）。现有 `IbTask`（`core/runtime/objects/task.py`）是 spawn 句柄，方向修正要求改造为 thread 对象 + 句柄方法。
- **当前 spawn/join/cancel 是关键字**（TokenType.SPAWN/JOIN/CANCEL/TASK），走 `vm_handle_IbSpawnStmt/IbJoinStmt/IbCancelStmt`（`core/runtime/vm/handlers/comm.py`），任务 F 删除。
- **parser 构造函数模式参考**：chan/signal/slot 是关键字前缀（`chan_expr`/`signal_expr`/`slot_expr`），产 `IbChannelExpr/IbSignalExpr/IbSlotExpr`。但 `thread` 不是关键字，`thread(...)` 如何解析为构造函数需自主设计。
- **设计重点**：`thread[T] t = thread(fn=..., args=...)` 构造函数 + `t.join()/t.cancel()/t.start()/t.is_done()` 句柄方法 + 生命周期状态机。`join()` 返回 T（任务 B 已特化好）。`cancel()` 返回 err（任务 D 落地）。需从 comp_parser → semantic → VM dispatch → 运行时对象全链设计。

### 变化前后

- **修改**：`tasks_docs/_HANDOFF.md`（更新为任务 A、B 完成 + 任务 C 调研结论 + 任务 C 起 goal 模板），`NEXT_STEPS.md`/`PENDING_TASKS.md`/`WORKLOG.md` 已如实同步。
- **代码**：无新增代码改动（任务 C 仅调研，未写实现）。

### 状态

- **goal 已暂停**（用户要求）。测试基线：全量 pytest **1443 passed / 4 skipped** 零回归。
- **待决**：无。任务 C-F 已授权待实现；交接文档已备好，下一 session 从任务 C 继续。
