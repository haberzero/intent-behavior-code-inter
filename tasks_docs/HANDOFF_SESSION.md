# HANDOFF_SESSION — 会话交接文档（一次性，下一 session 核验后并入 HANDOFF.md）

> **性质**：会话边界交接文档。内容自包含，下一 session 开工前读本文件 +
> `tasks_docs/NEXT_STEPS.md` + `tasks_docs/_planning_health_first.md`（排布规划）+
> `tasks_docs/WORKLOG.md` + `tasks_docs/HANDOFF.md`。
> **核验并接手后**：把本文件要点收敛进 `HANDOFF.md` §二，然后删除本文件（git 承载历史）。

> **本 session 主线**：技术债收敛 8 阶段全部完成（无人值守 goal `88ccadec`，已 complete）+
> 用户授权 push 到 GitHub + 后续任务排布（健康度优先四阶段 + 真实 LLM 全面试用纳入）。
> 每步全量 pytest 零回归 + 本地 commit。

---

## 一、总览（一句话）

本 session 完成**技术债收敛 8 阶段**（交接收手/任务控制文档收敛/注释代号清理/死代码孤儿清理/
质量红线修复/PT-DEBT-4 file→fs 全量迁移/PT-DECIDE-3 项①③ 语义裁定落地）+ **用户授权 push**
（`unsafe-vibe-dev` 已推送 origin，含收敛+排布 247 提交）+ **后续任务排布**（四阶段：A 代码/架构
健康 P0 → B 功能稳健/对外能力 → C 真实 LLM 全面试用重启[阈值后] → D 远期演进；微调 A3/A4 交换、
PT-DECIDE-2 封存、PT-DOC-3P2 提前至 B3、PT-FEAT-6/12 划远期）。基线 **3069 passed / 1 skipped**
（以实跑为准），worktree 干净。

## 二、仓库状态（权威）

| 项 | 值 |
|----|----|
| 当前分支 | `unsafe-vibe-dev`（HEAD=`<HEAD>`，**已 push origin，与 origin 同步**；用户本次显式授权 push） |
| 其它分支 | `main`（未触碰）；无其它本地分支 |
| 测试基线 | `~/miniconda3/envs/ibci/bin/python -m pytest tests/` → **3069 passed / 1 skipped**（以实跑为准） |
| 工作树 | 干净 |
| push | **本次已授权并已执行**；后续 push 需再获用户显式授权（授权不自动延续） |
| Goal | `goal-88ccadec`（技术债收敛）已 complete；后续任务按排布新建 |
| 排布 | `tasks_docs/_planning_health_first.md`（四阶段规划，下一 session 执行依据） |

## 三、本 session 提交序列（unsafe-vibe-dev，旧→新）

| 提交 | 内容 | 基线 |
|------|------|------|
| `69952657` | 交接收手（HANDOFF_SESSION 收敛入 §二 + 删除） | 3066 |
| `a1b66755` | 阶段 1 任务控制文档收敛 | 3066 |
| `0093527d` | 阶段 2 注释代号清理（F# 清零含测试层等） | 3066 |
| `d08f42c4` | 阶段 3 死代码孤儿清理 | 3066 |
| `855ae13e` | 阶段 4 质量红线 | 3066 |
| `ce297e88` | 阶段 5a PT-DEBT-4 file→fs 全量迁移（47 文件） | 3066 |
| `704c4f3e` | 阶段 5b CATCH-5 补测 + 矩阵编号修正 + PT-AUDIT-2 复核 | 3066 |
| `f9f47324` | 阶段 6 __from_prompt__ 单向契约 | 3069 |
| `9b5c5fd8` | 阶段 7 SEM_PROTOCOL_SIGNATURE required=error | 3069 |
| `fa2333c1` | 收尾文档同步 | 3069 |
| `42cf4e6d` | 后续任务排布（四阶段写入 NEXT_STEPS + WORKLOG） | 3069 |
| `<HEAD>` | 排布微调 + 规划文档 `_planning_health_first.md` + 本交接文档 | 3069 |

## 四、待验证清单（下一 session 首步，按序）

- [ ] `git status` → 干净；`git branch -vv` → unsafe-vibe-dev 与 origin 同步、main 未动。
- [ ] `git log --oneline -14` 对齐 §三 提交序列。
- [ ] 全量 pytest 实跑 → 记录 passed/skipped（预期 3069 量级，**以实跑为准**）。
- [ ] 读 `tasks_docs/_planning_health_first.md`（排布规划）+ `tasks_docs/NEXT_STEPS.md`（候选已按排布重写）。
- [ ] 读本文件 §五-§六（契约 + 下一步）。
- [ ] 确认 push 授权状态：**后续 push 需用户显式授权**（本次授权不自动延续）。

## 五、关键处置定论与契约（下一 session 必须知道）

1. **技术债收敛 8 阶段完成**：F# 任务代号全仓清零（含测试层）；`inherit_plugins` 孤儿字段删除；
   `IbBehaviorInstance` 死类型删除（+4 死分支 + binding_analysis 能力探测收敛）；
   `interpreter.py:989` 双通道收敛（删除 node_to_symbol 错误 fallback——其对方法 def 绑定
   self 符号非函数 spec，主扫描为权威路径）；snapshot/coordinator 私有穿透 → `VMExecutor.interpreter`
   公开访问器；`_llm_callable` 能力判定去除 except 掩错（satisfies 异常 fail-fast 暴露）。
2. **PT-DEBT-4 done**：`file` 模块重命名为 `fs`（用户侧模块名 + 内部 `file_impl.py`→`fs_impl.py`，
   47 文件迁移；`file_handle` 类型名不变；编译/运行时 SEM_LLMEXCEPT_FILE_WRITE 消息同步为 fs）。
3. **PT-DECIDE-3 项①③ 定案**：① `__from_prompt__` **单向契约**——返回值必须是目标类型实例，
   非实例=契约违约（诊断+uncertain retry_hint），`_auto_box_value` 三级兜底已删（对齐 06_oop §6.7
   既有文档，此前代码漂移为 auto-box）；③ `SEM_PROTOCOL_SIGNATURE` **required=error**（fail-fast），
   optional 成员（`__intent__`/`__retry__`）运行期 fail-fast 不经此路径。
4. **排布微调（用户 2026-08-19）**：A3（PT-DEBT-30/33）与 A4（Tier C 审计）交换；
   **PT-DECIDE-2 封存**（短期不再启动，PENDING 标 sealed + 解封条件）；**PT-DOC-3P2 提前至 B3**；
   **PT-FEAT-6/12 划远期**（近期不处理）。
5. **真实 LLM 全面试用（VISION-3）**：健康度/稳定性达标后重启（阶段 A/B 之后），
   对五大地基重构后全部新特性重试用（llm 可调用类/意图三层改写/retry 高阶化/流式/覆层/
   prompt 协议族/fs 等）；**非最高优先但必做**（用户明确）。清单见规划文档 §四。
6. **push 契约**：本次用户显式授权 push 并已执行；**后续 push 一律需再获显式授权**，
   不因"本次已授权"而默许（禁 push 硬原则，AGENTS.md）。

## 六、下一步（按排布，阶段 A 当前 P0）

1. **[主线] A1 主线架构债务落地**：G5 意图值栈全量重构 + 行为值深程统一装配入口收敛——
   **先设计**（临时设计文档 `tasks_docs/_<task>.md`），评估破坏面后落地，勿半接通。
2. **[架构] A2 PT-DEBT-29** 生成器消费协作化（Waitable 让出型消费）。
3. **[类型] A3 PT-DEBT-30/33** 类型边界闭合。
4. **[审计] A4 Tier C 专项审计**（C 类异味判定 + 静默降级补诊断 + 深嵌套可读性）。
5. **[周期] A5 PT-AUDIT-1/3 + quality-maintenance Tier B**。
   阶段 B/C/D 见规划文档 §三/§四/§五。

## 七、环境与纪律（勿忘）

- 测试唯一命令：`~/miniconda3/envs/ibci/bin/python -m pytest tests/`（conda env `ibci`）。
- 全程本地 `git commit`；**禁止 `git push`**（除非用户显式授权）；**永不触碰 `main`**。
- 每步：全量 pytest 零回归 + 描述性 commit + 同步 WORKLOG/NEXT_STEPS/HANDOFF。
- 工作模式定论（NEXT_STEPS ⛔）：禁 compat shim / 胶水 / tricky / 过程式硬编码；质量优先；
  原则优先于行为维持；可推翻 IBCI 自身设计缺陷；"只记录，不断决"。
- **注释纪律**：代码注释禁任务代号（P#/D#/G#/F#/决策 N/章节指针/历史叙述），只写功能设计与
  已知问题；docs/ 面向人类禁一切代号标签。规范/公理编号（INV/LT/IT/EXEC-1）属正式引用标识保留。
- **goal 配置习惯（HANDOFF §1.2.1）**：`max_auto_turns` = **7**；objective 按 §1.3 模板。
