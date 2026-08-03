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
