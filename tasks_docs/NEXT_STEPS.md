# NEXT_STEPS - 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `tasks_docs/PENDING_TASKS.md`。
> 已知语言级限制见 `docs/KNOWN_LIMITS.md`。
>
> **最后更新**：2026-08-05（类型强化完成；下一阶段 = **序列化工作 PT-ARCH-31 档位 A+B**）

---

## 🔴 下一阶段：序列化工作——闭包序列化 + fn_callable round-trip 修复（当前最紧要）

> **PT-ARCH-31**（`PENDING_TASKS.md`）：behavior/fn_callable 闭包序列化缺陷 +
> fn_callable round-trip 完全损坏。用户裁定**档位 A + B 都必须完成**。
> 完整缺陷取证、修复设计与测试要求见 PT-ARCH-31。

### 执行要点

- **档位 A**：序列化端补 closure（snapshot 种子值 / lambda cell 当前值）+ fn_callable 补
  closure/params_uids/body_uid + 作用域符号补 `is_cell`；反序列化端**新增 fn_callable 分支**、
  behavior/fn_callable 重建 closure。
- **档位 B**：作用域反序列化重建 cell；closure 反序列化后 post-pass 按 sym_uid 重链恢复的
  cell（修复 A 的两个退化：外层重赋值不可见 + 多闭包共享分叉）。
- **测试**：round-trip（snapshot 保真 / lambda 值拷贝 / 双闭包共享 / 调用一致）。
- **约束**：每批全量 `python -m pytest tests/` 零回归；commit 留痕（仅本地，禁 push）。

### 后续（序列化之后）

| 编号 | 内容 | 说明 |
|------|------|------|
| **R4** | 覆盖率核对 | 完整复核审查流程中待做（见 `PENDING_REVIEW_ITEMS.md`） |
| **R5 / D1-D5** | doc-governance 审计 + docs 同步 | 完整复核审查流程中待做 |
| **PT-ARCH-32** | Axiom 家族分裂（IntentAxiom/IntentContextAxiom 并入 BaseAxiom） | 未修缺陷待办（碎片化，机械修复） |
| **PT-ARCH-33** | EnumAxiom.from_prompt 双通道 + 静默吞错 | R3 疑似真缺陷 #3 未修 |
| **PT-ARCH-34** | use_intent_context 恒真守卫 + 静默 False | R3 疑似真缺陷 #6 未修 |
| **PT-SMELL-R3** | R3 code-odor 需讨论项全量待办（约 30 项，Zone A-D） | 用户裁定全部记录，处置三档（修/复核定案/设计确认） |
| **PT-INTRO-1** | 运行时内省/常用内置函数体系设计（`type()`/`len()` 等） | 独立设计任务（用户 2026-08-05 裁定） |

---

## ✅ 已完成：完整复核审查 R1/R2/R3 + 类型强化（2026-08-05）

- **R1 正式 code-review**（会话 13）：三阶段主线 + 收尾 L1-L8 独立复核，无高严重缺陷；
  新增缺陷 A1/C1/B1-B6/D1-D6 全部处置（D 系列重分类修正）。
- **R2 健康诊断十查**（会话 14-15）：约 50 项问题；经二次复核（架构层面 + 设计思路），
  30 项彻底修复/删除（批次 A-E），12 项设计决策保留+文档化。
  含 IbSlot.update 方案 A 接通 CAS RMW、Task→Thread 语言面改名（用户授权）。
- **R3 code-odor 全面异味扫描**（会话 16）：4 个 general agent 独立扫描（Zone A-D）+
  主会话实证核验；23 项真缺陷按 4 批处置（死代码清除 / 恒真守卫移除 / except 窄化 /
  真缺陷重构），含 assignment 复杂目标双通道消除、behavior 序列化 round-trip 修复、
  idbg 悬空属性潜伏崩溃等。每批全量 pytest 零回归。
- **类型强化（会话 16 尾）**：func/llm/lambda 强制返回标注（SEM_MISSING_RETURN_ANNOTATION）
  + lambda `-> auto` 推断 + 行为体 `-> auto` 唯一 str + 裸赋值 auto 锁定 + 多类型 list 移除
  （强制 list[any]）+ fn[...] 调用点签名校验补齐（CALLABLE_SIG 结构化 TypeRef）。
- **注释卫生清理**：全仓 66 文件删除任务代号/进度标记（恢复"注释只注功能"纪律）。
- 详细记录见 `tasks_docs/PENDING_REVIEW_ITEMS.md` §〇b 与 `tasks_docs/WORKLOG.md` 会话 13-16。

---

## ✅ 已完成：通信领域设计完善（三阶段）+ 收尾 L1-L8（2026-08-04/05）

> 全部完成并落地 unsafe-vibe-dev。批次/commit 明细见 git 历史；决策见 WORKLOG 会话 6-12。

| 批次 | 内容 | commit |
|------|------|--------|
| 阶段1 | B1 thread_result 序列化往返 / B2 循环导入 / B4 except:pass 兜底 | e217b8b |
| 阶段2 | D1 instantiate 挂钩（_create_blank）/ D2 thread 槽位化 / D3 thread_result IbValue / D4 ThreadStatus 单枚举 / D5 G4 诚实化 | f3037b2 |
| 阶段3 | G3 TASK→THREAD kind / G5 协调器归位 / G6 通信 Signal 移除 / G7 pubsub 打通 | 1da0b1c, 2c49240 |
| 收尾-L1/L3/L4 | _by_kind 索引彻底删除 / serializer done 字面量统一 / SpawnedTask Waitable 残留清理 | 149dd63 |
| 收尾-L2 | 泛型成员特化协议化（resolve_member 级联收敛为声明回调） | 8e0ada9 |
| 收尾-L6 | 瞬态序列化协议化（__transient_state__ 统一存根） | 3a2e5d1 |
| 收尾-L8 | 类型符号 class_ref 序列化（IbClass 身份保留） | af3ee21 |
| 收尾-L5/L7-A/T2 | IbOptional 单承载 / 泛型注解符号身份精确化 / _create_blank 构造入口统一 | 80b463e |

**遗留记录（后续窗口）**：运行时值 type_ref 保持基础 spec（设计决策：可变值不固有泛型身份）；
PT-SMELL-1/2 审计、TEST_REFACTOR、语言级协程（PT-4.3 async 函数/生成器）等见 `PENDING_TASKS.md`。

---

## ✅ 已完成：线程对象模型方向修正（任务 A-F）

> 2026-08-04 全部完成。`thread` 取代 `spawn/join/cancel/task`，async/thread 领域彻底分离。
> 关键裁定与摘要见 `tasks_docs/WORKLOG.md`。

| 任务 | 内容 | 状态 |
|------|------|------|
| A | Optional 配套完整实现（运行时 IbOptional） | ✅ commit b7b3e77 |
| B | 统一泛型模型（GenericTypeRegistry 单一权威源 + thread[T] 首个消费者） | ✅ commit d814568 |
| C | 线程对象模型（IbThread + 状态机 + thread(callable=,args=) + thread_result[T] + join 返回容器 + expect()） | ✅ commit 5ebbcfd/e30487c/21b3ce6 |
| D | err 类型统一（TaskError/TaskCancelled/TaskFailed + cancel 返回 err） | ✅ commit bd14381 |
| E | 线程相关清理（VP-2/F-1/F-2/疏漏4 + save_state 修复） | ✅ commit b0fe530 |
| F | 关键字精简（删 spawn/join/cancel/task 全链 + 废除旧测试） | ✅ commit 24baa3e |

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
conda activate ibci
python -m pytest tests/
```

> 基线以实跑为准，不冻结数字。

---

## 独立并行任务

- **测试体系治理与彻底重构**：独立、较低优先级，`tasks_docs/TEST_REFACTOR.md`（含 4 份调研报告 `TEST_REFACTOR_REPORTS.md`），不与主线混置。
- **技术债审计分支任务**：PT-SMELL-1/2（`CODE_SMELL_AUDIT.md` / `BRANCH_NESTING_AUDIT.md`），独立分支执行；PT-SMELL-3 已完成（见 `PENDING_TASKS.md` §六）。
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
