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
（quality-maintenance Tier A/B + aimless-review，产出 AIMLESS_REVIEW.md）；2) PT-SMELL-1/2/3
代码质量审计（独立分支）；3) PT-SEM-1.1 错误用户友好化 / PT-4.1 Enum 非 str 成员；
4) 测试体系重构（TEST_REFACTOR）。每条支线仍须全量 pytest 零回归、commit+留痕（仅本地）。

六、停止条件：先穷尽自主手段，仅当确实无法自主决定时（用户意图不明穷尽无解/公理层语义
错误集确需用户裁决/与工作模式定论冲突/破坏性重构无法确认边界且独立隔离分支也无法确定
技术路线）才 update_goal(status="unmet", blocker=具体卡点+建议)。

七、非目标：media Phase 4、跨进程/CPU 并行、跨引擎通信、完整通用异步（async 函数/生成器）、
线程无损挂起/恢复、用户级泛型类（PT-4.4）、Hindley-Milner 约束求解。
```

### 1.4 tasks_docs/ 文档结构指针

| 文档 | 用途 |
|------|------|
| `NEXT_STEPS.md` | 当前最紧要项 / 下一阶段 / 已完成摘要 / 工作模式定论 / 工作规则 |
| `HANDOFF.md` | 本文件：固定化内容 + 动态状态 |
| `PENDING_TASKS.md` | 长期规划（PT-SEM/PT-4.x/PT-ARCH/PT-SMELL/TEST_REFACTOR/media 封存） |
| `PENDING_REVIEW_ITEMS.md` | 完整复核审查清单（R1/R2 ✅ / R3-R5 待做 + D1-D5 docs 同步） |
| `WORKLOG.md` | 自主工作日志（关键裁定 + 仍有效设计决策 + 遗留） |
| `AIMLESS_REVIEW.md` | 无目的审视潜在参考（背景过程） |
| `CODE_SMELL_AUDIT.md` / `BRANCH_NESTING_AUDIT.md` | PT-SMELL-1/2 审计（待执行，独立分支） |
| `TEST_REFACTOR.md` / `TEST_REFACTOR_REPORTS.md` | 测试体系重构（独立任务） |

---

## 二、动态状态（随任务更新）

> 本部分随任务推进由各 session 更新，**不因任务完成删除**。

### 2.1 当前任务 / 下一阶段

- **下一阶段：R4 覆盖率核对**（完整复核审查流程中；R1/R2/R3 已完成）。
- 清单：`PENDING_REVIEW_ITEMS.md` —— R4 覆盖率核对（待做）/
  R5 doc 治理 + D1-D5 docs 同步（待做）。
- 要求：subagent 仅 general agent；每批全量 pytest 零回归；新缺陷按"不删也不修"两档处置。

### 2.2 已完成摘要

- **线程对象模型方向修正（A-F）** + **通信领域设计完善三阶段** + **收尾 L1-L8 + T2** 全部落地
  unsafe-vibe-dev（本地 commit，未 push）。批次/commit 明细见 `NEXT_STEPS.md`"已完成"节。
- **R1 完整复核**（会话 13）+ **R2 健康诊断十查**（会话 14-15）+ **R3 code-odor 全面异味
  扫描**（会话 16）+ **注释卫生清理** 全部完成。R3 处置：4 批 23 项真缺陷
  （死代码清除 / 恒真守卫移除 / except 窄化 / 真缺陷重构，含 assignment 复杂目标双通道、
  behavior 序列化 round-trip、idbg 悬空属性）。每批全量 pytest 零回归。
  详细记录见 `PENDING_REVIEW_ITEMS.md` §〇b 与 `WORKLOG.md`。
- **测试基线**：1506 passed / 6 skipped（以实跑为准）。
- **分支**：unsafe-vibe-dev（唯一活动分支；main 永不触碰；无独立分支残留）。

### 2.3 交接检查单

- [ ] 读 NEXT_STEPS（当前最紧要）+ PENDING_TASKS（长期）
- [ ] 读本文件 §一 固定化内容（goal 模板 / 流程 / 原则）
- [ ] 读 §二 动态状态接续工作
- [ ] 工作全程本地 commit、禁 push、工作日志记录
