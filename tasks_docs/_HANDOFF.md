# 临时交接文档（下一 session 交接后删除）

> 本文件为**临时交接**，记录当前工作状态、下一阶段目标、工作流程固定化内容指针。
> 下一 session 据此接手后，经确认删除本文件。
> 状态：**通信领域主线 + 收尾 L1-L8 全部完成（2026-08-05）**；下一阶段 = **完整复核审查工作流程**
> （用户明确准备开启）。
> ⚠️ **重要**：下一 session 必须先读 §三（工作流程固定化内容）与 §四（下一阶段目标），再启动。
> 工作流程**全部以 AGENTS.md 为权威源**，本文件只放指针与阶段信息，不复制通用内容。

---

## 一、当前工作状态

- **分支**：`unsafe-vibe-dev`（唯一活动分支；`main` 永不触碰；无独立分支残留）。
- **测试基线**：`python -m pytest tests/` = **1474 passed / 4 skipped**（以实跑为准）。
- **工作区**：git 干净（仅 `.opencode/opencode.json`、`.opencode/tui.json` 未跟踪，属 opencode 配置，非项目代码）。
- **已完成**（unsafe-vibe-dev，本地 commit，未 push）：
  - 通信领域设计完善三阶段（B1-B4/G1-G7）+ 收尾 L1-L8（L1 _by_kind 删除 / L2 泛型成员特化协议化 /
    L3-L4 清理 / L5 IbOptional 单承载 / L6 瞬态序列化协议化 / L7-A 泛型注解符号身份 / L8 类型符号
    class_ref / T2 _create_blank 构造入口统一）。
  - 决策记录：`tasks_docs/WORKLOG.md` 会话 6-12。
- **已归档**（git 历史保留，从 tasks_docs 移除）：STAGE2/MEMBER/TRANSIENT 设计文档、
  COMMS_DESIGN_REVIEW、THREAD_ARCH_HARDCODE_INVESTIGATION——其决策/发现已浓缩于 WORKLOG。

## 二、已完成工作摘要（供复核审查对照）

| 批次 | 内容 | commit |
|------|------|--------|
| 阶段1 | B1/B2/B4 | e217b8b |
| 阶段2 | D1-D5（instantiate 挂钩/thread 槽位化/thread_result IbValue/ThreadStatus/G4 诚实化） | f3037b2 |
| 阶段3 | G3/G5/G6/G7（kind 清理/协调器归位/Signal 移除/pubsub 打通） | 1da0b1c, 2c49240 |
| 收尾 | L1/L2/L3/L4/L6/L8/L5/L7-A/T2 | 149dd63, 8e0ada9, 3a2e5d1, af3ee21, 80b463e |

## 三、工作流程固定化内容（通用，AGENTS.md 为权威源）

> 以下**全部已在 AGENTS.md**，本处仅列指针，不复制正文（单点真理）。

- **自主工作循环**：理解 → 设计质询 → 自主决策 → 实现 → 自反馈验证 → 自主纠错 → 交付自查 → 收尾。
- **上报阈值**：穷尽自主手段仍无法决定才上报；破坏性重构默认已授权；分支政策见 AGENTS.md。
- **交付纪律**：全程本地 commit；**禁止 push**（硬原则，除非用户显式授权）。
- **工作日志**：所有自主决策/方案取舍/变化前后记录于 `tasks_docs/WORKLOG.md`（"只记录，不断决"）。
- **测试**：`conda activate ibci && python -m pytest tests/`（唯一命令）。
- **Skill 工作流**：code-workflow（实现）、code-review（缺陷复核）、code-quality（健康诊断）、
  code-odor（异味扫描）、quality-maintenance（分层质量维护）、doc-governance（文档治理）、
  self-grill（自我质询）、design-philosophy（设计哲学）。
- **关键用户裁定（须遵守）**：
  - 碎片化判断基准 = **设计语言（用户语义形态）统一**，非实现路径一致（会话 12）。
  - **"不删也不修 = 不可接受"**：有缺陷/冗余的机制只能"根本修复"或"彻底删除"两档。
  - subagent 工作（含 review）**仅允许 general agent**，禁 explore/reviewer 特化 agent。
  - 设计/决策先写 tasks_docs/，落地后按治理写入 docs/；docs/ 只面向人类。

## 四、下一阶段目标：完整复核审查工作流程

> **用户裁定（2026-08-05）**：准备开启完整复核审查。对会话 1-12 的所有改动（三阶段主线 +
> 收尾 L1-L8 + 泛型成员特化协议化等）做**完整独立复核**。

### 审查清单（核心：`tasks_docs/PENDING_REVIEW_ITEMS.md`）

| 编号 | 内容 |
|------|------|
| R1 | 正式 code-review 复核（三阶段 + 收尾全部改动，general agent 独立复核） |
| R2 | code-quality 健康诊断十查（全仓） |
| R3 | code-odor 全面异味扫描 |
| R4 | 覆盖率核对（新增测试覆盖全部新行为） |
| R5 | doc-governance 审计（配合 D1-D5 docs 同步） |
| D1-D5 | docs/ 技术手册同步（signal 移除/pubsub+subscriber/瞬态序列化协议/thread 槽位化/机制变化） |

### 执行要求

- 每批全量 pytest 零回归；产出缺陷清单合入 `PENDING_REVIEW_ITEMS.md`。
- 新缺陷按"不删也不修=不可接受"两档处置（根本修复 / 彻底删除），并记录 WORKLOG。
- commit 留痕（仅本地）；禁 push。

## 五、goal objective 模板（下一 session 可直接使用）

```
【完整复核审查 · 无人值守】主任务：对会话 1-12 所有改动（通信领域三阶段主线 + 收尾
L1-L8 + 泛型成员特化协议化等）做完整独立复核审查，按 tasks_docs/PENDING_REVIEW_ITEMS.md
的 R1-R5 审查动作逐项执行，D1-D5 文档同步收敛。

一、执行顺序（依赖驱动，每批全量 pytest 零回归 + commit + 同步 WORKLOG）：
  R1 正式 code-review（general agent，独立复核三阶段+收尾全部改动）→ 缺陷合入清单
  R4 覆盖率核对 → R2 健康诊断十查 → R3 异味扫描 → R5+D 文档治理与 docs 同步
  审查发现的新缺陷按"不删也不修=不可接受"两档处置并记录

二、工作流程（AGENTS.md 权威源）：自主工作循环；每任务 code-review/code-quality/
code-odor 对照；subagent 仅用 general agent；工作日志记录于 WORKLOG。

三、交付纪律：本地 commit；禁止 push（硬原则）；破坏性重构默认已授权（独立分支政策见
AGENTS.md）。

四、停止条件：穷尽自主手段仍无法决定才 update_goal(unmet, blocker)；审查完成且
PENDING_REVIEW_ITEMS 处置完毕后 update_goal(complete, 证据)。

五、非目标：media Phase 4、跨进程/CPU 并行、跨引擎通信、完整通用异步（async 函数/
生成器）、用户级泛型类、HM 约束求解。
```

---

> 交接完成阶段：本文件由下一 session 交接后删除。下一 session 启动前必须完整读取
> §三（工作流程固定化）与 §四（下一阶段目标）。
