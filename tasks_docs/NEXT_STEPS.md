# NEXT_STEPS - 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `tasks_docs/PENDING_TASKS.md`。
> 已知语言级限制见 `docs/KNOWN_LIMITS.md`。
>
> **最后更新**：2026-08-04（阶段 1 实锤 bug 修复 + 阶段 2 统一值对象机制完成；阶段 3 通信领域设计完善为当前项）

---

## 🔴 当前主线：通信领域（chan/signal/slot）设计完善与统一化检查

> **用户裁定（2026-08-04）**：通信领域设计完善与统一化检查为下阶段任务（THREAD_DESIGN_REVISION §三 疏漏 2）。方向修正任务 A-F 全部完成后启动。
>
> **前置审查（已完成 2026-08-04）**：对线程对象模型方向修正代码做了全方位审查（系统级一致性/设计语言统一/碎片化），完整发现记录见 `tasks_docs/COMMS_DESIGN_REVIEW.md`（唯一审查依据）。
>
> **修复路径（三阶段，见 COMMS_DESIGN_REVIEW §六）**：
> - **阶段 1（✅ 已完成 2026-08-04，commit e217b8b）**：
>   - B1：`thread_result` 序列化往返丢数据——序列化守卫改按 ib_class.name 分发 + 3 条往返测试锁定
>   - B2：循环导入——移除 primitives 反向再导出 + primitive_initializer 显式注册导入 + 干净解释器回归测试
>   - B4：VP-4 未修（`comm.py` 的 `except: pass` 兜底）——改为 fail-fast 直写
>   - 全量 pytest 1457 passed / 4 skipped（+4，零回归）
> - **阶段 2（✅ 已完成 2026-08-04，commit f3037b2；设计见 STAGE2_VALUE_OBJECT_UNIFICATION.md）**：
>   - D1 `instantiate` 挂钩（`_create_blank` 协议）→ thread 实例真实化
>   - D2 thread 状态迁移 `__slots__`（消 G1 fields 承载模式）+ 实例方法
>   - D3 thread_result 升级 IbValue（payload + type_ref，修 B1 深根因）
>   - D4 `ThreadStatus` 单一状态枚举（消 G2 三写）
>   - D5 G4 机制诚实化（from_spec 补分支 / rehydrator 去嗅探+幽灵回退 / to_typeref 语义改名）
>   - 独立分支验证后手动应用；全量 pytest 1464 passed / 4 skipped（+7，零回归）
> - **阶段 3（当前）**：Signal 投递语义设计（G6）、pubsub 语言层打通（G7）、TASK kind 清理（G3）、协调器归属修正（G5）
>
> **约束**：工作模式定论（质量优先、不留历史包袱、原则优先于行为维持）；每批全量 pytest 零回归 + commit + 同步 NEXT_STEPS/WORKLOG。

---

## ✅ 已完成：线程对象模型方向修正（任务 A-F）

> 2026-08-04 全部完成。`thread` 取代 `spawn/join/cancel/task`，async/thread 领域彻底分离。详细记录见 `tasks_docs/THREAD_DESIGN_REVISION.md`（决策依据，历史保留）与 `tasks_docs/WORKLOG.md`（实现记录）。

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
