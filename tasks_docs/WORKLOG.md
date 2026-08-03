# WORKLOG — 自主工作日志

> 记录所有自主决策、质询分析、方案取舍、变化前后（实现 + 测试 + 文档）。
> 原则：**"只记录，不断决"**——能自主决定的记录决定并推进；只有确实无法决定的才标记待决并上报。
> 最后更新：2026-08-03

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
