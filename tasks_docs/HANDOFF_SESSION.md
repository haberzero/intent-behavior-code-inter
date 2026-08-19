# HANDOFF_SESSION — 会话交接文档（一次性，下一 session 核验后并入 HANDOFF.md）

> **性质**：本文件是一次**会话边界交接文档**。内容自包含，下一 session 开工前读本文件 +
> `tasks_docs/NEXT_STEPS.md` + `tasks_docs/WORKLOG.md` + `tasks_docs/HANDOFF.md`。
> **核验并接手后**：把本文件要点收敛进 `HANDOFF.md` §二，然后删除本文件（git 承载历史）。

> **本 session 主线**：五大地基收官后的**审计清单处置 A+B/C/D** + **候选 #1 剩余债务评估定论**
> （无人值守，goal `50d30cd2`）。每步全量 pytest 零回归 + 本地 commit + 文档同步。

---

## 一、总览（一句话）

本 session 完成**审计处置 A+B（代号污染清理 + 死代码删除）**、**C（意图三层解析双写收敛）**、
**D（overlay 跨根并发隔离修复）**，并**候选 #1 剩余债务评估定论**（has_llm_call_cap 实证死字段
删除 + G5/行为装配评估）。当前 `unsafe-vibe-dev` HEAD=`033c9900`（领先 origin 232 提交），基线
**3066 passed / 1 skipped**（以实跑为准），worktree 干净（仅 HANDOFF.md 待提交本交接文档），
未 push、未触碰 main。

## 二、仓库状态（权威）

| 项 | 值 |
|----|----|
| 当前分支 | `unsafe-vibe-dev`（HEAD=`033c9900`，领先 origin **232** 提交，未 push） |
| 其它分支 | `main`（未触碰）；无其它本地分支 |
| 测试基线 | `~/miniconda3/envs/ibci/bin/python -m pytest tests/` → **3066 passed / 1 skipped**（以实跑为准） |
| 工作树 | 仅 `tasks_docs/HANDOFF.md` 修改（本交接文档提交时一并提交）；`_code_p4d_retry.md` 已删（G 项） |
| push | **一律禁止**（除非用户显式授权硬原则） |
| Goal | `goal-50d30cd2`（审计处置+候选评估）；跨会话不可 resume，下 session 新建 |
| 主线状态 | 五大地基 P1-P6 完成；审计处置 A-D 完成；候选 #1 剩余债务评估定论完成 |

## 三、本 session 提交序列（unsafe-vibe-dev，旧→新）

| 提交 | 内容 | 基线 |
|------|------|------|
| `90e66a90` | **审计 A+B**：注释/文档任务代号全仓清理（core 40+ / tests 45 / docs 7 / examples 1 / trials 18）+ 死代码删除 `_invoke_llm_callable_cps_boxed`/`_sync` | 3059 |
| `ed4502ef` | **审计 C+D**：C 意图三层解析双写收敛（行为路径调共享 `_resolve_llm_callable_intents_cps`）+ D overlay 覆层启用状态迁 RuntimeContext（跨根并发隔离）+ 判别测试 +3 | 3066 |
| `033c9900` | **候选 #1 定论**：has_llm_call_cap 死字段删除 + G5/行为装配评估（NEXT_STEPS/WORKLOG 同步） | 3066 |

## 四、待验证清单（下一 session 首步，按序）

- [ ] `git status` → 干净（或仅本交接文档）；`git branch -vv` → unsafe-vibe-dev、main 未动、未 push。
- [ ] `git log --oneline 90e66a90~1..HEAD` 对齐 §三 提交序列（3 笔）。
- [ ] 全量 pytest 实跑 → 记录 passed/skipped（预期 3066 量级，**以实跑为准**）。
- [ ] 读 `tasks_docs/NEXT_STEPS.md`（候选 #1 已更新定论 + 下一步候选）与 `tasks_docs/HANDOFF.md` §2.2 检查单。
- [ ] **读本文件 §五-§六**（契约 + 处置定论——下 session 的上下文）。
- [ ] 确认 goal：跨会话不可 resume → 按 HANDOFF §1.2.1 新建 goal（max_auto_turns=7）。

## 五、关键处置定论与契约（下一 session 必须知道）

1. **审计 A+B**（`90e66a90`）：注释纪律全仓执行——代码注释与 docs 禁任务代号/章节指针/历史叙述。
   **保留标准**：INV-*/LT-*/IT-* 规范/公理编号（正式引用标识，如 docs/01_intent_system.md 声明
   "Rule IT-1 是规范正式引用标识"）保留；trials 用例编号（D1-08-001/T09-N1/R1-001 等试用地基
   身份，INDEX.md 对应）保留；docs EXEC-1 公理编号保留；tests/README 元规则保留。**不变量编号
   INV-EXCEPT-\* 等已被 subagent 误删过、已回退**——遇到同类编号先判性质（任务代号 vs 规范
   标识）再动。
2. **审计 D overlay 并发隔离**（`ed4502ef`）：覆层启用状态 = RuntimeContext 计数集合
   （`enter_overlay`/`exit_overlay`/`is_overlay_enabled`，`(type_name, message) -> depth`）。
   分派点 `_dispatch_protocol_message` 经 `get_current_execution_context()` 查询；无活跃 EC
   （宿主直调）默认未启用。`ProtocolSlot` 已删 `overlay_enabled` 共享槽（跨根污染源）。
   判别测试 `tests/runtime/test_overlay_concurrency.py`（并行根隔离/嵌套计数/无 EC 默认关）。
3. **审计 C 意图双写收敛**（`ed4502ef`）：`_prepare_behavior_call_cps` 行为路径现调用共享
   `_resolve_llm_callable_intents_cps`（含 IbIntentContext 类型校验 fail-fast）。
4. **候选 #1 定论**（`033c9900`）：has_llm_call_cap **是死字段**（无协议映射/访问器/消费者；
   上 session"编译期 DDG 层"记录有误，DDG 实际用 IbBehaviorExpr AST 类型）——已删除
   （BaseAxiom/BehaviorAxiom/TypeAxiom + 03_type_system.md）。G5 意图值栈全量重构**维持登记
   不推进**（P3 核心切片已落地、勿半接通）。行为统一装配**评估为值自身差异承载**（非双通道）
   收窄为登记项。NEXT_STEPS 候选 #1 已更新为定论状态。

## 六、下一步候选（下 session）

1. **[主线后续] 审计 E 半接通边界 / F 登记债务核对复核**（本 session 未动，登记项核对）。
2. **[主线后续] 候选 #1 收尾后主线推进**：G5 意图值栈（如需）、行为统一装配（如需）——
   均为中大型设计项，需先设计再评估。
3. 支线：PT-DEBT-29/30/31、PT-DECIDE-2/3/4、PT-DEBT-4/5；VISION-3；文档 P9 收尾
   （docs 代号污染已在 A 清理，P9 剩余为体系治理）；三份 `_five_foundation_*` 设计文档
   （P1-P6 竣工后评估收敛入 docs 或删除）。
4. 质量维护（quality-maintenance Tier A/B）随主线顺带。

## 七、环境与纪律（勿忘）

- 测试唯一命令：`~/miniconda3/envs/ibci/bin/python -m pytest tests/`（conda env `ibci`）。
- 全程本地 `git commit`，**禁止 `git push`**（除非用户显式授权）；**永不触碰 `main`**。
- 每步：全量 pytest 零回归 + 描述性 commit + 同步 WORKLOG/NEXT_STEPS/HANDOFF。
- 工作模式定论（NEXT_STEPS ⛔）：禁 compat shim / 胶水 / tricky / 过程式硬编码；质量优先；
  原则优先于行为维持；可推翻 IBCI 自身设计缺陷；"只记录，不断决"。
- **注释纪律**：代码注释禁任务代号（P#/D#/G#/决策 N/章节指针/历史叙述），只写功能设计与
  已知问题；docs/ 面向人类禁一切代号标签。规范/公理编号（INV/LT/IT/EXEC-1）属正式引用标识。
- **goal 配置习惯（HANDOFF §1.2.1）**：`max_auto_turns` = **7**；objective 按 §1.3 模板。
