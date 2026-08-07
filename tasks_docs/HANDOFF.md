# HANDOFF — 常驻交接与固定化内容库

> 本文件**持久保留**（非临时交接）：为每个 session 提供**固定化模板 / 通用流程 / 工作原则**，
> 以及**当前任务状态**。
>
> **使用方式**（下一个 session 开始工作时）：
> 1. 根据当前任务分析：读 `NEXT_STEPS.md`（当前最紧要）+ `PENDING_TASKS.md`（长期规划）+
>    `PENDING_REVIEW_ITEMS.md`（审查清单，如适用）。
> 2. 从本文件 §一 获取**固定化内容**（goal 模板 / 工作流程 / 工作原则 / 约束）。
> 3. 按 §二 **动态状态** 接续当前工作。
>
> **维护规则**：§一 长期不变（新增用户裁定时补充）；§二 随任务更新。**不因任务完成删除本文件**。
> 工作流程权威源为 `AGENTS.md`，本文件只放指针与模板，不复制通用正文（单点真理）。

---

## 一、固定化内容（长期不变）

### 1.1 工作流程（AGENTS.md 为权威源，此处只列指针）

- **自主工作循环**：理解 → 设计质询 → 自主决策 → 实现 → 自反馈验证 → 自主纠错 → 交付自查 → 收尾。
- **上报阈值**：穷尽自主手段仍无法决定才上报；破坏性重构默认已授权；分支政策见 AGENTS.md。
- **交付纪律**：全程本地 commit；**禁止 push**（硬原则，除非用户显式授权）。
- **工作日志**：自主决策/方案取舍/变化前后记录于 `WORKLOG.md`（"只记录，不断决"）。
- **测试**：`conda activate ibci && python -m pytest tests/`（唯一命令）。
- **Skill 工作流**：code-workflow（实现）/ code-review（缺陷复核）/ code-quality（健康诊断）/
  code-odor（异味扫描）/ quality-maintenance（分层质量维护）/ doc-governance（文档治理）/
  self-grill（自我质询）/ design-philosophy（设计哲学）。

### 1.2 关键用户裁定与工作原则

| 原则 | 内容 |
|------|------|
| 碎片化判断基准 | 碎片化 = **设计语言（用户语义形态）统一**，非实现路径一致。同类内容内部路径差异有语义需求驱动且不改变用户语义形态，即非碎片 |
| "不删也不修" | 有缺陷/冗余的机制只能"**根本修复**"或"**彻底删除**"两档，禁止"废弃记录"中间态 |
| subagent 约束 | 所有 subagent 工作（含 review）**仅允许 general agent**，禁 explore/reviewer 特化 agent |
| 决策纪律 | 需拍板的决断项可大胆激进选方案；底线 = 架构原则/代码质量原则/非妥协/非 tricky/非临时兼容层/大方向主线 |
| 设计阶段文档 | 设计/决策先写 `tasks_docs/`，落地后按治理写入 `docs/`；`docs/` 只面向人类 |
| 工作模式定论 | 禁 compat shim/胶水/tricky/过程式硬编码；质量优先于速度；原则优先于行为维持；可推翻 IBCI 自身设计缺陷 |
| 破坏性重构授权 / 分支政策 / 禁 push | 见 AGENTS.md（权威源） |

### 1.3 goal objective 模板（通用骨架，可直接套用）

```
【<任务名> · 无人值守】主任务：<按 NEXT_STEPS/PENDING_TASKS 定位的当前最紧要目标，
写明阶段/批次/具体项>。

一、主线任务（按序，依赖驱动，每步全量 pytest 零回归 + commit + 同步 NEXT_STEPS/WORKLOG）：
  <列出任务项；每完成一项用描述性 commit 提交并自动接续下一项>

二、自主推进偏好（最高优先）：总体偏向无人值守，允许较大限度自我裁定与自我质询分析并
尽可能推进。只有经过最大限度反思/质询/分析后仍确实无法彻底自主决定的内容才造成阻塞。
凡能自主决断的一律自主决断并详尽记录决策依据（工作日志）。上报阈值统一为"尽可能自主推进"。
决策纪律：可大胆激进选方案，底线=架构设计原则/代码质量原则/非妥协/非tricky/非临时兼容层/
大方向主线任务。不因需拍板而停滞。

三、交付纪律：全程本地 git commit；禁止 push 到 GitHub（硬原则）——除非用户明确指示允许
push，否则一律禁止 git push 到任何远程仓库。破坏性重构授权（硬原则）：符合一般工程经验/
普适性/合理架构设计且经分析确实优于现有体系时，哪怕设计已被文档记录也允许破坏性重构，
默认已授权自主推进，仅需详尽记录决策依据与工作内容。大范围破坏性重构分支政策（硬原则）：
无法确认边界/危害程度的破坏性重构 100% 授权在其独立分支实验，独立分支禁止直接合并到
unsafe-vibe-dev 或 main，确认技术路线后仅允许手动单独更新 unsafe-vibe-dev；永远不允许触碰
主干分支（main）。工作日志：所有自主决策/方案取舍/变化前后必须详尽记录于 WORKLOG，"只记录，
不断决"。

四、工作流：每任务走 code-workflow Phase 0-5 + 质量门 + design-philosophy 对照 + self-grill
自我质询 + code-odor 自查 + 全量 pytest 零回归（python -m pytest tests/）。批量后 code-review
残留扫描。

五、主任务阻塞/暂停时的支线（按优先级，解阻立即回主线）：1) 质量维护/代码健康
（quality-maintenance Tier A/B + aimless-review，产出 AIMLESS_REVIEW.md）；2) PT-AUDIT-1/2
代码质量审计（独立分支）；3) PT-FEAT-5 错误用户友好化 / PT-FEAT-2 Enum 非 str 成员；
4) 测试体系重构（PT-TEST-1）。每条支线仍须全量 pytest 零回归、commit+留痕（仅本地）。

六、停止条件：先穷尽自主手段，仅当确实无法自主决定时（用户意图不明穷尽无解/公理层语义
错误集确需用户裁决/与工作模式定论冲突/破坏性重构无法确认边界且独立隔离分支也无法确定
技术路线）才 update_goal(status="unmet", blocker=具体卡点+建议)。

七、非目标：media Phase 4（PT-SEALED-1）、跨进程/CPU 并行、跨引擎通信、PT-FEAT-1 的 `yield` 惰性生成器（属阶段 5，R 批次之后实现，不在本批次范围；async 函数关键字已由 D-08 定案取消，任意函数可 await）、线程无损挂起/恢复、用户级泛型类（PT-FEAT-3）、Hindley-Milner 约束求解。
```

### 1.4 tasks_docs/ 文档结构指针

| 文档 | 用途 |
|------|------|
| `NEXT_STEPS.md` | 当前最紧要项（下一主线待择定）/ 已完成摘要 / 工作模式定论 / 工作规则 |
| `HANDOFF.md` | 本文件：固定化内容 + 动态状态 |
| `PENDING_TASKS.md` | 长期规划（任务代号按性质分域：PT-FEAT/PT-DEBT/PT-AUDIT/PT-DOC/PT-TEST/PT-DECIDE/PT-SEALED） |
| `PENDING_REVIEW_ITEMS.md` | 代码复核审查循环（PT-AUDIT-3：R1/R2/R3 已执行，R4/R5 待做） |
| `DOC_AUDIT_REPORT.md` | docs/ 治理审核记录（2026-08-06，F0-F4 已执行完成，归档） |
| `TEST_MATRIX_FINDINGS.md` | 测试矩阵核对发现（PT-TEST-3 研究存档，PT-TEST-1 重构输入） |
| `THREAD_DESIGN.md` / `PROMPT_DESIGN_REVIEW.md` / `MEDIA_DESIGN.md` | 设计要点迁入（并发 / `__prompt__` 待决项 / media 封存） |
| `WORKLOG.md` | 自主工作日志（关键裁定；设计决策收敛于 `PENDING_TASKS.md` §十） |
| `AIMLESS_REVIEW.md` | 无目的审视潜在参考（背景过程） |
| `CODE_SMELL_AUDIT.md` / `BRANCH_NESTING_AUDIT.md` | PT-AUDIT-1/2 审计（长期周期，独立分支） |
| `TEST_REFACTOR.md` / `TEST_REFACTOR_REPORTS.md` | 测试体系重构（PT-TEST-1，**已并入 OBSERVABILITY_REFACTOR**） |
| `OBSERVABILITY_REFACTOR.md` / `test_baseline_20260806.txt` | **当前主线任务控制文档**（可观测性统一重构 Phase 0-4）/ 覆盖基准快照 |

---

## 二、动态状态（随任务更新）

> 本部分随任务推进由各 session 更新，**不因任务完成删除**。

### 2.1 当前任务 / 下一阶段

- **下一主线（阶段 5）**：**`yield` 惰性生成器**——设计 `EXEC_FOUNDATION_DESIGN.md` §5.2（D-08 定案：任意函数可
  await、yield 自标记函数种类，async 关键字已取消）。**前置已全部就绪**：调度器执行核心 + R 批次
  （trampoline/通知式唤醒/Waitable 家族）+ PT-FEAT-9 诊断机制（阶段 4）稳定。大型独立特性
  （生成器体需单可恢复驱动），建议独立分支实验。
- **PT-FEAT-9 阶段 4 已完成（2026-08-07，unsafe-vibe-dev，全量 2021 passed / 1 skipped）**：
  `kernel_diagnostic` helper（单一记录双投影：警告不门控 + 事件受 observability 门控，rc best-effort）+
  12 处站点迁移（文案逐字）+ e2e 事件投影测试 + `docs/architecture/09_observability.md`。设计权威
  `DIAGNOSTIC_DESIGN.md`（实施步骤 A-E 全部完成）。
- **R 批次全部完成（2026-08-07，unsafe-vibe-dev，全量 2001 passed / 1 skipped）**：R4+R3（82c9c0f，1988/1）
  P3 公开协议 + D-04 `IbThread` 满足 Waitable → R6（35f1437，1995/1）嵌套函数自动只读捕获 → R2（c16b05e/c4c63aa，
  1998/1）调度器通知式唤醒 → R1（6dc9214，2001/1）函数调用 trampoline 化（EXEC-1 根治，深递归 Python 深度恒定）。
  各独立分支实验、手动 cherry-pick 应用 unsafe-vibe-dev。设计/决策见 `EXEC_REFACTOR_BATCH.md`（无悬而未决问题）。
- **已定案（不再重议）**：R5 撤回（`await` 幂等是 auto-yield 组合承载，改报错破坏 `await collect(h)`）；
  D-08 保留透明 async（CPS 天然可挂起 + auto-yield 组合 + 值契约 + yield 自标记）。
- **R 批次遗留技术债（2026-08-07 评估登记，见 `PENDING_TASKS.md` §五 PT-DEBT-9/10/11）**：
  ① PT-DEBT-9 RecursionError 被 `VM: Call failed` 级联包装掩盖根因（随下次执行层重构承接）；
  ② PT-DEBT-10 线程体用户函数递归仍同步嵌套（`_drive_generator` 非 trampoline，既有行为非回归，与阶段 5 线程主题相关）；
  ③ PT-DEBT-11 `_UserFunctionCall` 定义位置（handler 层依赖 VMExecutor 内部，建议下沉 `shared` 层或协议化）。
  三项均不阻塞阶段 5，择机评估。
- **阶段 1/3 已完成（2026-08-07，unsafe-vibe-dev，全量 1984 passed / 1 skipped）**：地基 1a-1e（调度器执行核心/
  Waitable 家族 try_result/阻塞即挂起/协作取消/llmexcept×await/取消覆盖用户函数）+ 统一清理 W1-W5/P3/P4
  （非阻塞命名/订阅契约/pubsub EventBus/comm 命名回归/死状态/文档/cell 隔离/引擎级全局事件总线）。
- **后续路线**：阶段 5 `yield` 惰性生成器（`EXEC_FOUNDATION_DESIGN.md` §5.2，下一主线）→ 增量（streaming / host async 改进）。
- **保留规划**：media Phase 4（PT-SEALED-1，彻底封存）。
- 要求：subagent 仅 general agent；每批全量 pytest 零回归；新缺陷按"不删也不修"两档处置；全程本地 commit、禁 push。

### 2.2 已完成摘要

- **2026-08-07（PT-FEAT-9 阶段 4 完成）**：内核结构化诊断机制重建——`kernel_diagnostic` helper（单一记录双投影：
  警告不门控 + 事件受 observability 门控，rc best-effort）+ 12 处运行时站点迁移（文案逐字）+ e2e 事件投影测试
  （协议回退双投影/策略忽略 fail-open/门控）+ `docs/architecture/09_observability.md`（观测体系统一文档）。
  全量 **2021 passed / 1 skipped**。详见 WORKLOG 与 git 历史。
- **2026-08-07（R 批次完成）**：统一执行地基复核与根治——R4+R3 P3 公开协议 + `IbThread` 满足 Waitable（`await t` 可用）、
  R6 嵌套函数自动只读捕获、R2 调度器通知式唤醒（根治 poll+park）、R1 函数调用 trampoline 化（深递归 Python 深度恒定）。
  全量 **2001 passed / 1 skipped**。详见 WORKLOG 与 git 历史。
- **2026-08-06**：**OBSERVABILITY_REFACTOR 主体完成**——Phase 0-2C + 2C-2（idbg 深度收敛：protection_map
  内核化/统一变量视图/snapshot vars bug/LLM 事件流）+ 2D 测试体系全面重建（tests_v2 全域迁移 + 切换 +
  矩阵三段式 + tests_docs 治理）+ Phase 4 收敛全部落地，全量 **1962 passed / 1 skipped**。测试体系现为
  单一分层模型（kernel/compiler/runtime/plugins/contracts/e2e/compliance/sdk/meta/fixtures），meta 机器强制
  （分层/命名/helper 去重/矩阵对账）。commit 明细见 git 历史。
- **2026-08-05**：闭包序列化 round-trip 修复 + Axiom 家族分裂收敛 + EnumAxiom 双通道收敛 +
  use_intent_context 守卫修复 + R3 异味四 Zone 处置 + import-* 精确成员枚举根治（含 IBC 文件
  跨模块导入三层断裂修复）+ `type()` 内建落地 + 任务控制文档全面重整（任务代号按性质分域）。
- **线程对象模型方向修正（A-F）** + **通信领域设计完善三阶段** + **收尾 L1-L8 + T2** +
  **代码复核审查（code-review / 健康诊断 / 异味扫描）** + **类型强化** 全部落地（详见 git 历史）。
- **测试基线**：以实跑为准，不冻结数字（当前 2001 passed / 1 skipped）。
- **分支**：unsafe-vibe-dev（唯一活动分支；main 永不触碰；实验分支 exp/obs-2a/2b/2c/2c2/2d 与 R 批次
  exp/exec-ra/rb/rc/rd 保留未合并）。

### 2.3 交接检查单

- [ ] 读 NEXT_STEPS（当前最紧要）+ PENDING_TASKS（长期）
- [ ] 读本文件 §一 固定化内容（goal 模板 / 流程 / 原则）
- [ ] 读 §二 动态状态接续工作
- [ ] 工作全程本地 commit、禁 push、工作日志记录
