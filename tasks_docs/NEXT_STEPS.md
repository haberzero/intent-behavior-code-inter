# NEXT_STEPS - 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `tasks_docs/PENDING_TASKS.md`。
> 已知语言级限制见 `docs/KNOWN_LIMITS.md`。
>
> **最后更新**：2026-08-03（新主线确立：IBCI 运行时多线程 + 统一通信机制 + 内省/控制；上一主线 LLM 并行化+同步异步全部完成）
---

## ⛔ 工作模式定论（强制，凌驾于本文件一切任务之上）

> **扎实推进，禁止任何形式的快速实现 / 兼容层 / 胶水实现 / tricky 实现。**

1. **禁止 compat shim / 兼容层**：不写"过渡性包装"。新设计就是真设计，旧代码要么真合并、要么真删除。
2. **禁止胶水实现**：不在两个不统一的子系统之间塞字符串拼接 / 魔法哨兵 / 隐式约定来强行粘合。
3. **禁止 tricky 实现**：不靠隐式字符串变换承载语义；不靠"凑巧相等"；不靠书写顺序掩盖数据依赖。
4. **禁止过程式硬编码分发**：同一决策只通过协议驱动（`receive()` / vtable）完成，不在运行流程里写 `if 能力标志位` 分支。
5. **质量优先于速度**：技术债必须先清，再推进依赖它的特性。潜伏 bug 不允许过渡修复。
6. **原则优先于行为维持**：当既有行为被确认违反一般性的工程/架构原则时，优先以架构原则与工程原则为准，**不以"保持已有行为"为主**。改前先分析，改后详尽记录变化前后（供追溯）。"已有代码不因'已在仓库里'而正确"。
7. **可推翻 IBCI 自身设计缺陷**：若为 IBCI 自身的设计缺陷/失误，**哪怕该设计思路已在文档中明确记录，也可被推翻**，按更普适、实践上更合理且有充分理由的方案重建。此类问题（IBCI 自身设计缺陷修正）**通常可不询问用户**，仅需详尽记录决策依据与工作内容（实现 + 测试 + 文档的变化前后）即推进。
8. **破坏性重构授权（用户 2026-08-03 明确，硬原则）**：当判断符合一般工程经验、符合通常意义下的普适性、属于合理的架构选择与设计，且经分析确实优于 IBCI 现有体系及已有代码时，**哪怕该设计已被 IBCI 文档明确记录，也允许进行破坏性重构**。用户**不禁止对已有代码的修改**；已有代码的优先级**低于**架构正确性与设计上的统一一致。此类破坏性变更（含已被文档记录的设计）**默认已授权自主推进**，仅需详尽记录决策依据与工作内容（实现+测试+文档变化前后）即推进。
9. **大范围破坏性重构的分支政策（用户 2026-08-03 明确，硬原则）**：对于**无法确认边界、无法判断危害程度**的破坏性重构，**100% 授权在其独立分支上**（不污染 `main` 与 `unsafe-vibe-dev`，不污染任何计算机环境与用户目录），允许任意程度破坏性实验与重构。**只有当即使该独立隔离分支也无法经自主实验确定工作路线时**，才将相关任务配置为阻塞。**独立分支禁止直接合并到 `unsafe-vibe-dev` 或 `main`**；只有在确认完整技术路线后，才允许单独进行手动 `unsafe-vibe-dev` 代码更新。**永远不允许触碰主干分支（`main`）的代码。**

---

## 当前测试基线

```bash
python -m pytest tests/
```

> 基线以实跑为准，不冻结数字。

---

## 当前主线：IBCI 运行时多线程 + 统一通信机制 + 内省/控制（新确立）

> **用户裁定（2026-08-03）**：上一主线（LLM 并行化 + 同步异步，Stages 1-4 + `await` 表达式）**已全部完成**。确立下一主线：**IBCI 运行时多线程 + 统一通信机制（Channel/Signal/Slot）+ 内省/控制**。这是基于"用 ibci 设计一个完整虚拟机运行时"的视角，对 IBCI 内核的**大范围破坏性改造**（用户明确接受，架构正确性 > 维持现状）。
>
> **核心动机**：现有通信机制碎片化（`output_callback`/`call_info`/`Waitable`/`future`），无统一官方设计；用户需实时监控/流式时被迫手写轮询（不可维护）。需要**一等通信机制** + **运行时内省** + **默认开启的控制能力**。
>
> **范围分解（设计已综合，见 `tasks_docs/THREADING_DESIGN.md`）**：
> 1. **统一通信内核**：`Channel`（数据流，mode=stream/message/pubsub）+ `Signal`（控制流，target 可选定向/广播）+ `Slot`（状态，具名原子读写），三抽象共享线程安全内核，语言层全部暴露
> 2. **内省层**：**快照式 + 事件流** 两者都提供（`runtime.snapshot()` / `runtime.subscribe()`）
> 3. **控制层**：统一启停接口（有开有关，部分默认开、部分默认关），`runtime.configure(...)` 粒度全局→单调用→单实例
> 4. **流式 vs 并行**：两个独立概念，**都默认开启**；流式需 provider 流式接口 + Worker 增量 → Channel → 渲染线程
> 5. **多 VM 实例**：每个并发路径一个轻量 VM 实例（完全隔离，留出全局可见只读数据），内核协调器管理生命周期；经 Channel 协调
> 6. **编译器改造**：新 AST 节点（spawn/join/task/chan/signal/slot）+ parser 语法 + 4 阶段语义 + dispatch + 序列化（并发任务为运行时瞬态，不进入持久化状态）
> 7. **用户代码多线程**：`task = spawn(fn)` 显式任务句柄（join/cancel），供实时 UI/输出刷新
>
> **明确排除**：跨进程/CPU 并行（性能瓶颈在 IBCI 包装，非 CPU 并发）；跨引擎通信（隔离运行是自我进化窗口，现阶段仅维护+同步演进，保持文件/序列化机制）。
>
> **参考**：现有 `Waitable`/`LLMFuture`/`TaskScheduler`/`spawn_isolated` 多 VM 机制作为演进基础；`docs/subsystems/05_coroutine.md §7.7/§7.8` 记录 Stage 3/4 成果。
>
> **完成状态**：上一主线（LLM 并行化 + 同步异步）全部完成——Stage 1（executor 去共享化）、Stage 2（VM 多任务调度）、Stage 4（宿主异步统一 Waitable）、Stage 3（`await` 表达式）、PT-SEM-4、PT-4.2、PT-SYNC-1/2/3、PT-TEST-9。
>
> **下一步**：**PT-MT-1 详细设计文档已产出（2026-08-03，见 `tasks_docs/THREADING_DESIGN_DETAIL.md`）**——覆盖架构总览、编译器改造（AST/lexer/parser/语义/dispatch/序列化）、统一通信内核、内省层、控制层、流式+并行、多 VM 实例、并发正确性、测试策略、待决项 D1-D9。**已按自主推进偏好进入实现**。
>
> **PT-MT-2 编译器地基已完成（2026-08-03）**：新 AST 节点（IbSpawnStmt/IbJoinStmt/IbCancelStmt/IbChannelExpr/IbSignalExpr/IbSlotExpr）+ 7 个关键字（spawn/join/cancel/chan/signal/slot/task）+ parser（语句 if-链 + 表达式前缀规则 + type_def 分支）+ 4 阶段语义（spawn 可调用校验、join/cancel 目标 task 校验）+ 类型注册（TypeKind.TASK/CHANNEL/SIGNAL/SLOT + Spec + Axiom）+ 序列化 round-trip。测试：新增 `tests/compiler/test_concurrency_syntax.py`（18 用例），全量 pytest 1341 passed/4 skipped 零回归。
>
> **PT-MT-3 统一通信内核已完成（2026-08-03）**：线程安全内核（`core/runtime/shared/comm/`：CommBuffer/ChannelCore/SignalCore/SlotCore/CommRegistry）+ 语言层对象（`IbChannel`/`IbSignal`/`IbSlot`/`IbTask`）+ dispatch handler（6 个新节点全部接入 VM）。语言面可用：`chan.send/recv/recv_nonblocking/close`、`slot.set/get`、`spawn/join/cancel`（PT-MT-3 阶段为协作式延迟任务：join 触发求值；后台线程/轻量 VM 在 PT-MT-7/8 升级）。测试：`test_comm_kernel.py`（33）+ `test_vm_comm.py`（8），全量 pytest 1382 passed/4 skipped 零回归。
>
> **下一步**：PT-MT-4 内省层（`runtime.snapshot()` + `runtime.subscribe()`）。

---

## 独立并行任务

- **测试体系治理与彻底重构**：独立、较低优先级，`tasks_docs/TEST_REFACTOR.md`（含 4 份调研报告 `TEST_REFACTOR_REPORTS.md`），不与主线混置。
- **技术债审计分支任务**：PT-SMELL-1/2/3（`CODE_SMELL_AUDIT.md` / `BRANCH_NESTING_AUDIT.md` / `LOCAL_IMPORT_AUDIT.md`），独立分支执行。
- **media Phase 4**（多模态容器）：**已彻底封存（2026-08-01），且 2026-08-02 起无限期搁置**；恢复需显式解封并重估；代码层零启动（`PENDING_TASKS.md` §六）。

---

## 工作规则

- **每次开新分支前**，先复跑 `python -m pytest tests/`，把当前 pass/fail 计数写在 PR 描述里。
- **同一时刻只主推一个 P0 阶段**。
- **工作模式定论优先**：任何与"⛔ 工作模式定论"冲突的提议一律以定论为准。
- 任何改动公理层公约或语义错误集的任务，需在分支早期跑全量 pytest 评估破坏面。
- 每个阶段完成后，用描述性 commit message 记录完成的工作，并把对应条目从本文件移除。
- **本文件不冻结具体测试通过数字**。
- 重大架构决策记录在技术文档中（`docs/ARCHITECTURE.md`、`docs/architecture/02_metadata_ast.md`、`docs/architecture/01_principles.md`），不再使用独立 ADR 文件。
