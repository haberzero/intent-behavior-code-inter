# HANDOFF_SESSION — 会话交接文档（一次性，下一 session 核验后并入 HANDOFF.md）

> **性质**：会话边界交接文档。内容自包含，下一 session 开工前读本文件 +
> `tasks_docs/NEXT_STEPS.md` + `tasks_docs/_planning_health_first.md`（排布规划）+
> `tasks_docs/WORKLOG.md` + `tasks_docs/HANDOFF.md`。
> **核验并接手后**：把本文件要点收敛进 `HANDOFF.md` §二，然后删除本文件（git 承载历史）。

> **本 session 主线**：上一 session 交接核验接手 + **阶段 A1 主线架构债务落地**（G5 意图值栈 +
> 行为统一装配入口收敛）+ **用户新增 PT-DEBT-34 变量语义建模技术债**（登记 + 迅速评估 + 排布细化）。
> 每步全量 pytest 零回归 + 本地 commit（本 session 未 push）。

---

## 一、总览（一句话）

本 session 完成：① 上一 session 交接核验接手（要点收敛入 `HANDOFF.md` §二并删除临时交接文件）；
② **阶段 A1 主线架构债务落地**——G5 意图值栈全量重构（一等值栈）+ 行为值深程统一装配入口收敛，
2 项登记架构债解除，判别测试 +8；③ **用户新增 PT-DEBT-34 变量语义建模技术债**（登记 + 迅速评估
定论：运行时模型一致非大重构、工作量中等，排布置顶阶段 A 先于真实试用）。基线 **3083 passed /
1 skipped**（以实跑为准），worktree 干净，本地领先 origin 6 提交（**未 push**）。

## 二、仓库状态（权威）

| 项 | 值 |
|----|----|
| 当前分支 | `unsafe-vibe-dev`（HEAD=`07ab423c`，**本地领先 origin 6 提交，未 push**） |
| 其它分支 | `main`（未触碰）；无其它本地分支 |
| 测试基线 | `~/miniconda3/envs/ibci/bin/python -m pytest tests/` → **3083 passed / 1 skipped**（以实跑为准） |
| 工作树 | 干净 |
| push | **本 session 未 push**；后续 push 需再获用户显式授权（授权不自动延续） |
| Goal | `goal-188bef05`（阶段 A1）已 complete；PT-DEBT-34 按排布新建 |
| 排布 | `tasks_docs/_planning_health_first.md`（四阶段规划；已含 A1 完成 + PT-DEBT-34 置顶为阶段 A 首位 P0） |

## 三、本 session 提交序列（unsafe-vibe-dev，旧→新）

| 提交 | 内容 | 基线 |
|------|------|------|
| `af258557` | 交接核验接手（HANDOFF_SESSION 收敛入 §2.1/§2.2 + 删除临时文件） | 3069 |
| `08c4b787` | G5 意图值栈全量重构（eager 一等值栈 + @- 按值匹配 + 消解链同步化 + @- 解析修复） | 3082 |
| `202c6ff3` | 行为值深程统一装配入口收敛（assemble_llm_call_request_cps 单一分派源） | 3082 |
| `527de5a3` | A1 收尾（docs 同步 + 判别测试 + 临时设计文档删除） | 3083 |
| `becff080` | 登记 PT-DEBT-34（PENDING/NEXT_STEPS/WORKLOG/_planning_health_first） | 3083 |
| `07ab423c` | PT-DEBT-34 迅速评估与排布细化 | 3083 |

## 四、待验证清单（下一 session 首步，按序）

- [ ] `git status` → 干净；`git branch -vv` → unsafe-vibe-dev 领先 origin 6 提交（未 push）、main 未动。
- [ ] `git log --oneline -6` 对齐 §三 提交序列。
- [ ] 全量 pytest 实跑 → 记录 passed/skipped（预期 3083 量级，**以实跑为准**）。
- [ ] 读 `tasks_docs/_planning_health_first.md` + `tasks_docs/NEXT_STEPS.md`（阶段 A 首位 = PT-DEBT-34）。
- [ ] 读本文件 §五-§六（契约 + 下一步）。
- [ ] 确认 push 授权状态：**后续 push 需用户显式授权**（本 session 未 push，授权不延续）。

## 五、关键处置定论与契约（下一 session 必须知道）

1. **阶段 A1 主线架构债务落地完成（2 项登记架构债解除）**：
   - **G5 意图值栈**（`08c4b787`）：意图段在注释/栈操作执行点 eager 求值为一等值列表
     （`IbIntent.values`，content/segments 双表示收敛为协议计算属性）；`@-` 按值派生渲染文本匹配；
     意图消解链同步化收敛（去死 CPS 包装）；`@- "text"`/`@- $x` 带空格 pop_top 解析修复。
   - **行为统一装配入口**（`202c6ff3`）：`assemble_llm_call_request_cps` 单一分派源
     （行为→语义槽 / llm 类→用户 dict），run_batch/invoke/stream 值路径收敛；
     行为表达式路径保持 `_prepare_behavior_call_cps`（无值对象，非双通道）。
2. **PT-DEBT-34 登记（用户 2026-08-20）**：变量**引用/拷贝/赋值/传递**值语义建模显式化——
   用户判定**巨大隐患**，排布置顶阶段 A（真实 LLM 全面试用前）。
3. **PT-DEBT-34 迅速评估定论（本 session）**：运行时值语义模型**一致完整、非大重构**——复合对象
   共享引用（同 Python）、赋值=引用复制、传参共享引用、copy/deepcopy 内建正确、snapshot/llmexcept
   深克隆、类静态字段每实例深克隆。"混乱不清晰"集中在**文档契约缺失**（02_variables 无赋值语义、
   05_functions 无传参语义、共享引用只在 KNOWN_LIMITS §五、is vs == 无用户文档）+ **文档漂移**
   （KNOWN_LIMITS §五.2 建议构造器初始化字段，代码已每实例深克隆静态默认值 ib_class.py:413）+
   **判别测试缺口**。**工作量中等（约 4-6 个专注窗口）**；修复四步：调研对照 → 文档权威契约 →
   判别测试 → 运行时审计+小修（详见 PENDING PT-DEBT-34 / WORKLOG）。
4. **push 契约**：本 session 未 push；后续 push 一律需再获用户显式授权，不因历史授权而默许
   （禁 push 硬原则，AGENTS.md）。
5. **goal 契约**：A1 goal（`goal-188bef05`）已 complete；PT-DEBT-34 按排布新建 goal 时用
   HANDOFF §1.2.1 配置习惯（`max_auto_turns`=7、objective 按 §1.3 模板）。

## 六、下一步（按排布，阶段 A 当前 P0）

1. **[主线] PT-DEBT-34 变量语义建模显式化**：① 调研对照（主流语言值语义 Python/C++/Rust/Java，
   产出对照结论）→ ② 文档权威契约（新增"值语义"章节 + 02_variables/05_functions 教学段 +
   修 KNOWN_LIMITS §五.2 漂移）→ ③ 判别测试锁定（赋值别名/传引用/copy vs deepcopy/snapshot
   冻结/llmexcept 快照/静态字段独立性）→ ④ 运行时审计（发散点 + 小修）。
2. **[架构] A3 PT-DEBT-29 生成器消费协作化**（Waitable 让出型消费；无生产触发，独立专项窗口）。
3. **[类型] A4 PT-DEBT-30/33 类型边界闭合**。
4. **[审计] A5 Tier C 专项审计**。
5. **[周期] A6 PT-AUDIT-1/3 + quality-maintenance Tier B**。
   阶段 B/C/D 见规划文档 §三/§四/§五（**C 真实试用阈值含 PT-DEBT-34 完成**）。

## 七、环境与纪律（勿忘）

- 测试唯一命令：`~/miniconda3/envs/ibci/bin/python -m pytest tests/`（conda env `ibci`）。
- 全程本地 `git commit`；**禁止 `git push`**（除非用户显式授权）；**永不触碰 `main`**。
- 每步：全量 pytest 零回归 + 描述性 commit + 同步 WORKLOG/NEXT_STEPS/HANDOFF。
- 工作模式定论（NEXT_STEPS ⛔）：禁 compat shim / 胶水 / tricky / 过程式硬编码；质量优先；
  原则优先于行为维持；可推翻 IBCI 自身设计缺陷；"只记录，不断决"。
- **注释纪律**：代码注释禁任务代号（P#/D#/G#/F#/决策 N/章节指针/历史叙述），只写功能设计与
  已知问题；docs/ 面向人类禁一切代号标签。规范/公理编号（INV/LT/IT/EXEC-1）属正式引用标识保留。
- **goal 配置习惯（HANDOFF §1.2.1）**：`max_auto_turns` = 7；objective 按 §1.3 模板。
