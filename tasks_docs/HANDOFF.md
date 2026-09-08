# HANDOFF — 常驻交接与固定化内容库

> 本文件**持久保留**（非临时交接）：为每个 session 提供**固定化模板 / 通用流程 / 工作原则**，
> 以及**当前任务状态**。
>
> **使用方式**（下一个 session 开始工作时）：
> 1. 根据当前任务分析：读 `NEXT_STEPS.md`（当前最紧要）+ `PENDING_TASKS.md`（长期规划）。
> 2. 从本文件 §一 获取**固定化内容**（goal 模板 / 工作流程 / 工作原则 / 约束）。
> 3. 按 §二 **动态状态** 接续当前工作。
>
> **维护规则**：§一 长期不变（新增用户裁定时补充）；§二 随任务更新。**不因任务完成删除本文件**。
> 工作流程权威源为 `AGENTS.md`，本文件只放指针与模板，不复制通用正文（单点真理）。
>
> **书写要求**：更新本文档必须按尾部「书写模式」模板与格式书写，保持一致。

---

## 一、固定化内容（长期不变）

### 1.1 工作流程（AGENTS.md 为权威源，此处只列指针）

- **自主工作循环**：理解 → 设计质询 → 自主决策 → 实现 → 自反馈验证 → 自主纠错 → 交付自查 → 收尾。
- **上报阈值**：穷尽自主手段仍无法决定才上报；破坏性重构默认已授权；分支政策见 AGENTS.md。
- **交付纪律**：全程本地 commit；**禁止 push**（硬原则，除非用户显式授权）。
- **工作日志**：自主决策/方案取舍/变化前后记录于 `WORKLOG.md`（"只记录，不断决"）。
- **测试**：`python -m pytest tests/`（唯一命令；环境规格权威源 = `pyproject.toml` + `docs/guide/00_environment.md` 规范 recipe；本机事实见 `AGENTS.local.md`）。
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
| 破坏性重构授权 / 分支政策 / 禁 push | 见 AGENTS.md（权威源）。**分支合并细则（2026-08-18 更新，取消 cherry-pick）**：确认低风险/边界清晰（全量 pytest 零回归 + 复核放行）可直接 **merge** unsafe-vibe-dev；merge 无误即删无用分支（除 main 与 unsafe-vibe-dev 外不长期保留分支）；main 不更新不触碰；判定以"是否确认零风险"为准 |

### 1.2.1 goal 配置习惯（每个 session 新配置 goal 时自动采用，用户定案）

> 创建 goal（`create_goal` / `set_goal`）时按此默认参数，除非用户在本 session 显式覆盖：
>
> | 参数 | 值 | 说明 |
> |------|----|------|
> | `max_duration_seconds` | **14400（4 小时）** | 最晚结束时间 = 当前时刻 + 4h |
> | `max_auto_turns` | **7** | 允许 goal 自动续跑次数 |
> | `token_budget` | **null（无限制）** | 不设 token 预算上限（预算无限制；720K 为模型上下文窗口系统层硬限制，非 goal budget） |
>
> `objective` 正文仍按下方 §1.3 模板套用（无人值守 + 主线 + 交付纪律 + 工作流 + 停止条件 + 非目标）。

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
 默认已授权自主推进，仅需详尽记录决策依据与工作内容。大范围破坏性重构分支政策（硬原则，
 "零风险直接合并"细则；2026-08-18 更新合并流程，取消手动 cherry-pick）：无法确认边界/
 危害程度的破坏性重构 100% 授权在其独立分支实验，允许任意破坏性实验；永远不允许触碰主干
 分支（main）。**合并细则（2026-08-18 更新）**：确认低风险/边界清晰的改进（全量 pytest
 零回归 + 复核放行，无对外契约/架构级风险）可直接 **merge** 到 unsafe-vibe-dev；merge 无误后
 直接删除无用分支（除 main 与 unsafe-vibe-dev 外不长期保留分支，短期工作分支合并即删）。
 判定以"是否确认零风险"为准，非以改动规模。工作日志：所有自主决策/
 方案取舍/变化前后必须详尽记录于 WORKLOG，"只记录，不断决"。

四、工作流：每任务走 code-workflow Phase 0-5 + 质量门 + design-philosophy 对照 + self-grill
自我质询 + code-odor 自查 + 全量 pytest 零回归（python -m pytest tests/）。批量后 code-review
残留扫描。

五、主任务阻塞/暂停时的支线（按优先级，解阻立即回主线）：1) 质量维护/代码健康
（quality-maintenance Tier A/B）；2) PT-AUDIT-1/2 代码质量审计（独立分支）；
3) PT-FEAT-5 错误用户友好化（剩余 CI/CD 可靠化设计；PT-FEAT-2 已完成、已移除）；
4) 测试体系补测（PT-TEST-2 覆盖矩阵缺口；PT-TEST-1 已完成、已移除）。每条支线仍须全量 pytest 零回归、commit+留痕（仅本地）。

六、停止条件：先穷尽自主手段，仅当确实无法自主决定时（用户意图不明穷尽无解/公理层语义
错误集确需用户裁决/与工作模式定论冲突/破坏性重构无法确认边界且独立隔离分支也无法确定
技术路线）才 update_goal(status="unmet", blocker=具体卡点+建议)。

七、非目标：media Phase 4（PT-SEALED-1）、跨进程/CPU 并行、跨引擎通信、线程无损挂起/恢复、用户级泛型类（PT-FEAT-3）、Hindley-Milner 约束求解。`yield` 惰性生成器（PT-FEAT-1）是阶段 5 下一主线，非"非目标"；是否纳入本 goal 视主任务界定。
```

### 1.4 tasks_docs/ 文档结构指针

| 文档 | 用途 |
|------|------|
| `NEXT_STEPS.md` | 当前最紧要项 / 工作模式定论（强制约束）/ 工作规则 / 下一步候选 |
| `PENDING_TASKS.md` | 长期规划与搁置任务（任务代号按性质分域：PT-FEAT/PT-DEBT/PT-AUDIT/PT-DOC/PT-TEST/PT-DECIDE/PT-SEALED） |
| `HANDOFF.md` | 本文件：固定化内容 + 动态状态 |
| `WORKLOG.md` | 自主工作日志（关键裁定；设计决策收敛于 `PENDING_TASKS.md`） |
| `trials/` | 试用地基（T01-T07）与工具链 `trials/_toolkit/`（harness / batch / 用例即契约 / LLM_SERVICE）——测试资产，非任务控制文档 |

---

## 二、动态状态（随任务更新）

### 2.1 当前工程状态 / 下一阶段

> **接手起点（下一位智能体 = 主线任务延续）**：读本节 + `tasks_docs/NEXT_STEPS.md`
> （当前最紧要 + ⛔ 工作模式定论）+ `tasks_docs/PENDING_TASKS.md`（远期规划）+
> `tasks_docs/GOVERNANCE.md`（任务控制治理）+ `git log --oneline -30`（近期提交与工作动线）
> + `tasks_docs/WORKLOG.md`（round3 整合条目，逐项详录）。

- **🔴 当前状态 = round3 试用需求整合队列全部收束（2026-09-08）→ 收敛判据达成，转稳定维护态**。
  round3 需求单（`ibci_feedback_round3.md`，试用方 v3 统一自动机 R185–R202 实证摩擦全集）
  全阶段完成：A（P0 R3-①~⑥ + Tier B 窗口）/ B（P1 R3-⑦~⑬）/ C（P2 文档批 R3-⑭~⑮）/
  D（meta 层/代码作值设计交付）/ E（原阶段 E 顺延批终态裁定）/ F（收敛：Tier B 窗口 +
  长期注册项复查）。单点记录 = `tasks_docs/_trial_round3_intake.md`（逐条核验 + 耦合分析 +
  队列 + 终态）；每项实施细节见 WORKLOG round3 条目 + git log。

- **工程事实**：
  - 分支 = `free-explore`（`main` 不触碰；`unsafe-vibe-dev` 不触碰）；HEAD = `a2d9e096`
    （Phase F 收敛）；工作区干净；**全程未 push（全本地，硬原则）**。
  - 测试基线 = `.venv/bin/python -m pytest tests/`（本机解释器见 `AGENTS.local.md`——
    本机无 miniconda3 `ibci` 环境，§2.2 旧条目的 miniconda3 路径作废）；末次全量
    **3867 passed / 1 skipped 零回归**（数字以实跑为准，不冻结）。
  - 本轮提交链（round3 全段，新→旧）：`a2d9e096`(Phase F) → `e6a8cfe4`(Phase E) →
    `8d8242e7`(Phase D) → `ce55f4ce`(R3-⑭/⑮) → `82aa9804`(R3-⑬) → `97da922e`(R3-⑫) →
    `7ab0cc6e`(R3-⑪) → `6f4c5ce9`(R3-⑩) → `458a7aa6`(R3-⑨) → `dba9e3c6`(R3-⑧) →
    `a4b3d8b4`(R3-⑦) → `76373b44`(Tier B 窗口) → `1905b2a2`(R3-⑥) → `9c887f9d`~
    `47d1562a`(R3-⑤ 四批) → `84d0911f`(R3-④) → `f5656c53`(R3-③) → `87787e3b`(R3-②) →
    `f74c82ee`(R3-①) → `46d5534d`(intake)。
  - 本轮交付新功能面（试用方视角速览）：① run 级可观测子系统（LLM journal 默认开 +
    `--replay` 确定性重放 + 预算核算 + `--result-json` trailer）；② ihost 子环境（E1 LLM
    配置继承 + `ihost.run_file` 进程内运行 .ibci 文件 + 结果捕获错误作值）；③ json 鲁棒面
    （parse 直值 + `parse_or_none` + fail-fast）；④ 429 限流退避（`backoff_s` + call_info
    事件）；⑤ 思考抑制警告可配置静默（`accept_forced_thinking`，警告移 stderr）；⑥ knowledge
    扩展面（provenance / history kind 过滤 / export）；⑦ 诊断精化批（缩进提示 / 小写布尔
    did-you-mean / 赋值定位 RHS / 裸声明编译期拒绝）；⑧ CLI `check --format json` 结构化
    诊断导出；⑨ 弱模型测量 howto 组 + 多模型组合编排 howto + 保留词表 + fs.write --root 示例；
    ⑩ 设计文档 `_meta_layer_design.md`（meta 层/代码作值）+ `_n3_measure_freq_design.md`
    （N3 探针实证 + 待决裁定）。

- **⏳ 主线延续点（下一位智能体的工作队列）**——round3 队列已空，稳定维护态：
  1. **round4 试用需求单到达时**：按恒高优先重新 intake（参照 `_trial_round3_intake.md`
     模式：逐条核验 + 耦合分析 + 新队列 + NEXT_STEPS 插队）；试用方 run 存档
     （`/home/dsh/proj/ibci-trial/`）为实证证据源（只读）。
  2. **周期质量维护**：Tier A 随主线顺带 / Tier B 阶段边界窗口（Phase F 窗口已完成，
     结果见 WORKLOG）/ Tier C 专项审计仅用户指定时独立分支执行。
  3. **候选下一主线（长期登记项，不自主开工——需用户指示或重估触发条件成立）**：
     - **VISION-4 类型理论加固**：开工输入已就绪——`_meta_layer_design.md` §四 类型层
       承诺需求清单 5 项（CompilationArtifact/RunResult/BehaviorExpr 值类型 / fn[...]
       高阶签名 / Verdict 类型）+ ref A2/A5/A6/B2 挂起整合推进。
     - **N3 measure_freq（logprob 通道）**：待决（探针实证：SiliconFlow chat 通道静默
       忽略 logprobs、legacy completions 通道完整支持——能力存在但 IBCI 现用通道不暴露）；
       重估触发 = provider 支持 completions/logprob 通道 或 corpus/probe 设计内化。
     - **R-2b meta.compile / R-6 行为表达式作值**（"运行中执行字符串代码"的语言级接通）：
       登记不实施，设计就绪（`_meta_layer_design.md`）；机制面已存在（Python 宿主层
       `engine.compile_string`/`run_string` + IBCI 语言级 `ihost.run_file`[文件级]）；
       缺口 = 语言级 `meta.compile(code_str)` 入口 + 代码工件作类型值（类型层承诺，待
       VISION-4）——不半接通。
     - **D-3.3 VM 字符串扫描快速路径**：长期登记（Tier C 专项候选；与演化平面设计合流
       规划）。**B5 并发成熟化**：挂起（一等原语已成熟，专项需单独立项）。**远程 CI**：
       待用户显式授权（`ci_local.sh` 四层本地复现已就绪）。
  4. **每轮自主评估现状**（队列有活持续推进；调整顺序/优先级/批次划分的理由记入 WORKLOG）。

- **本 session 重要设计裁定（下一位智能体须知，均见 WORKLOG 详录）**：
  - R3-⑤ journal/replay/budget/result-json = 单一子系统单一设计（`_run_observability_design.md`）；
    journal CLI 默认开；replay = 能力槽 SYSTEM 优先级替换 provider（不新建执行模型）；预算 =
    独立治理码（不复用 RUN_LIMIT_EXCEEDED）；重放耗尽 = 既有 LLMCallError 路径 fail-fast（不设
    专用码）。
  - R3-⑥ E1 继承 = **spawn 时点活状态快照**（IbStatefulPlugin save/restore 机制同构；
    api_config.json 只是初始源，活状态 = 单一权威源——偏离早期"文件快照 + to_llm_config"
    措辞）；`ihost.run_file` = 错误作值（{exit_status, stdout, exception}）；
    ThrownException 显示面 = "TypeName: message"（Python 异常显示对等）。
  - R3-⑧ 裸声明 = 编译期拒绝（裁定 (c)——语句域裸声明无合法运行期语义 = 死语法，
    fail-first；类字段/for 变量/形参合法形态不受限）；D-10 json.parse fail-fast
    （RUN_JSON_PARSE_ERROR 新码；_list/_value 魔法包装键移除——试用方"数组须包装"摩擦消除，
    数组直 parse 为 list）；F-2 警告 = stderr（数据面纪律）+ 可配置静默；R-7 429 退避 =
    provider 层检测 + sleep（`backoff_s` 缺省 0 零侵入）；R-8 knowledge = 纯增面。
  - Phase D meta 层 = **选项 A**（用户 2026-09-08 裁定：调用方表达治理 + 语言原语；三门
    管线[编译门/隔离门/判定门]固化为文档化惯用法 + 参考实现；ihost policy 参数 = 未来策略
    模型演进点，A 不堵死此路）；meta.compile/R-6 不半接通（登记不实施）。
  - Phase E 终态裁定：A2/A5/A6/B2 = 挂起 → VISION-4 整合推进（类型层同域，不半接通）；
    D3 = 挂起（随新能力配套）；B5 = 挂起（并发一等原语已成熟）；C6 = 完成（多模型组合
    编排 howto）；D2 = 完成（check --format json）。

- **挂起/待决清单（本轮 7 项 + 长期登记 8 项）**：

  | 项 | 状态 | 重估触发 / 条件 |
  |----|------|----------------|
  | A2 泛型约束 / A5 解构 / A6 Enum-tagged union / B2 惰性结构 | 挂起 → VISION-4 整合推进 | VISION-4 开工（类型理论设计落地） |
  | D3 新能力配套诊断码 | 挂起 | 随新能力实施（纯增面 + catalog + 15_diagnostics + parity 门） |
  | B5 并发原语成熟化 | 挂起 | 专项需单独立项评估（一等原语已成熟；流式观测边界记 KNOWN_LIMITS 待评估） |
  | N3 measure_freq（logprob 通道） | 待决（方向保留） | provider 支持 completions/logprob 通道 或 corpus/probe 设计内化 |
  | R-2b meta.compile / R-6 行为表达式作值 | 登记不实施（设计就绪） | VISION-4/5 类型层承诺落地（`_meta_layer_design.md` §四 清单） |
  | D-3.3 VM 字符串扫描快速路径 | 长期登记（Tier C 候选） | 与演化平面设计合流规划（VM 执行模型性能架构面） |
  | 远程 CI | 待用户显式授权 | 用户授权后启用（`ci_local.sh` 四层本地复现已就绪） |
  | #33 / LLM-5 事件驱动监视 | 被动项 | 待重估 |
  | PT-SEALED-1 media Phase 4 | 封存 | 需显式解封并重估 |
  | VISION-4 / VISION-5 / VISION-6 | 长期·无排期 | VISION-4 开工输入已就绪（见上）；VISION-6 档 B = 长期主线、真 JIT 挂数据平面性能线 |

- **硬约束（延续）**：全程本地 commit、**禁 push**（硬原则，除非用户显式授权）；不触碰
  `main` / `unsafe-vibe-dev`；`/home/dsh/proj/ibci-trial/` 只读（其 run 存档 = 实证证据源；
  向该目录写入须用户明确指示——2026-09-08 "复制代码到试用者文件夹" 指令已被用户撤销）。
  工作模式定论九条（禁 compat shim/胶水/tricky/过程式硬编码分发；质量优先于速度；原则
  优先于行为维持；可推翻 IBCI 自身设计缺陷）凌驾一切；改动公理层或语义错误集须全量
  pytest 评估破坏面。
- **落账纪律**：WORKLOG 条目经临时文件 splice 至 `## 附、书写模式（本文档专用模板，
  书写必须参照）` 锚点前；commit 消息 = 描述性中文（可引用队列项 R3-x）；每项完成同步
  NEXT_STEPS / intake / HANDOFF；测试数字以实跑为准（不冻结）；设计阶段文档先写
  `tasks_docs/_<task>.md`（落地后删除，最终内容按治理收敛入 `docs/`）。
- **运行注记（测试防卡死）**：测试套件双层防卡死已就位（pytest-timeout 每测试 60s 自动
  报告 + 进程看门狗 180s——无输出退出 124 = 框架层 hang，读完整 stderr 线程栈定位；
  用法见 `docs/howto/keep_tests_safe.md`）。daemon 孤儿线程（collect-timeout 测试）须
  控制在套件时间尺度内完成。

### 2.2 交接检查单（当前有效）

- [x] **✅ round3 试用需求整合队列全部收束（2026-09-08 session 交付）**：A/B/C/D/E/F 全阶段
  完成/挂起/裁定不做终态——收敛判据达成，转稳定维护态。本轮 21 提交（`46d5534d`~`a2d9e096`，
  全本地未 push）；末次全量 **3867 passed / 1 skipped 零回归**；逐项详录见
  `tasks_docs/WORKLOG.md` round3 条目 + git log（历史状态条目已按书写模式移除，git 承载）。
- [x] 读 `NEXT_STEPS.md`（当前状态：round3 全收束 + ⛔ 工作模式定论 + 下一步候选）
- [x] 读 `PENDING_TASKS.md`（远期：VISION-4/5/6 + 长期登记项；VISION-4 已补开工输入指针）
- [x] 读 `GOVERNANCE.md`（任务控制治理章程）
- [x] 读 `WORKLOG.md`（round3 整合条目：R3-①~⑬ + P2 文档批 + Phase D/E/F + 各设计裁定）
- [x] 读 `tasks_docs/_trial_round3_intake.md`（round3 需求单逐条核验 + 队列 + 终态——下一轮
  round4 intake 的模式参照）
- [x] 读设计文档：`tasks_docs/_meta_layer_design.md`（meta 层/代码作值 + 选项 A + 类型层
  承诺清单）/ `tasks_docs/_n3_measure_freq_design.md`（N3 探针实证 + 待决）/
  `tasks_docs/_run_observability_design.md`（run 级可观测子系统）/
  `tasks_docs/_ihost_subenv_design.md`（ihost 子环境 E1 + run_file）/
  `tasks_docs/_knowledge_registry_design.md`（知识注册表）
- [x] 测试基线：`.venv/bin/python -m pytest tests/`（以实跑为准，不冻结数字；本机无
  miniconda3 `ibci` 环境——`AGENTS.local.md` 为准）
- [x] 全程本地 commit、禁 push（除非用户显式授权）；分支 `free-explore`（main 不触碰）
- [x] 稳定维护态工作模式：round4 需求单到达 → 重新 intake 插队；周期质量维护 Tier A/B；
  长期注册项按重估触发条件推进（不自主开工 VISION-4 等长期项）
- [x] 试用方目录 `/home/dsh/proj/ibci-trial/` 只读（run 存档 = 实证证据源；写入须用户明确
  指示——2026-09-08 代码复制指令已撤销）

---

## 附、书写模式（本文档专用模板，书写必须参照）

> 本节是本文档书写的**唯一权威模板**（模板归属 = 文档自身；`GOVERNANCE.md`
> §三 仅做索引）。更新本文档一律按下列结构与格式书写。

### 1. 文档结构

```
# HANDOFF — 常驻交接与固定化内容库
定位段（持久保留说明 + 使用方式 + 维护规则 + 书写要求）
一、固定化内容（长期不变）
  1.1 工作流程（指针，AGENTS.md 为权威源）
  1.2 关键用户裁定与工作原则（表格）
  1.2.1 goal 配置习惯
  1.3 goal objective 模板
  1.4 tasks_docs/ 文档结构指针（表格）
二、动态状态（随任务更新）
  2.1 当前工程状态 / 下一阶段
  2.2 交接检查单（当前有效）
```

### 2. 分区规则

| 区 | 维护规则 |
|----|----------|
| §一 固定化内容 | **长期不变**；仅新增用户裁定时补充；不复制 AGENTS.md 正文（单点真理，只放指针与模板） |
| §二 动态状态 | **随任务更新**：只保留当前任务/下一阶段状态；任务完成即移除（git 承载）；待用户确认项标注 ⏳ 并给出登记位置 |
| 检查单 | 随任务状态增删勾选项，保持与当前任务一致 |

### 3. 条目格式

- 状态条目：`- **<状态标记>**：<当前状态>——<内容摘要>。`
- 状态标记：🔴 当前任务 / ⏳ 待用户确认 / ❌ 阻塞（**不登记已完成记录**——git 承载）。
- 指针一律用仓库相对路径，不复制被指文档正文。

### 4. 维护规则

- **不因任务完成删除本文件**（常驻文档）；git 承载历史版本。
- 新增用户裁定时：先入 WORKLOG（长期约束力）或本节 §1.2（工作原则），不重复登记。
