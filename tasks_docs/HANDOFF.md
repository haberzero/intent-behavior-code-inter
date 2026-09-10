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
  self-grill（自我质询）/ design-philosophy（设计哲学）/ user-principles（裁决基准四问/历史
  非权威）/ aimless-review（无目的审视）。全集与加载规则（含分析类任务不豁免）=
  `AGENTS.md` 开工前必读清单。

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

> 创建 goal 时按**当前 goal 工具面**与下列默认参数，除非用户在本 session 显式覆盖：
>
> **API（唯一权威 = 当前工具面，勿按旧形态调用）**：
> - `create_goal(objective, max_goal_rounds)` — 创建（objective = §1.3 模板全文；
>   `max_goal_rounds` = 自动续跑轮次预算）；
> - `get_goal` — 读当前 goal 状态（id / revision / phase / 已用轮次；**更新前必须先调**，
>   取精确 goal_id 与 revision）；
> - `update_goal(action, goal_id, revision)` — `action` ∈ {`edit`, `pause`, `resume`,
>   `complete`, `blocked`}。
>
> **默认参数（用户定案习惯）**：`max_goal_rounds` = **7**（轮次预算）；objective 正文按
> 下方 §1.3 模板套用（无人值守 + 主线 + 交付纪律 + 工作流 + 支线 + 停止条件 + 非目标）。
>
> **生命周期语义**：
> - session resume / fork 后 active goal 自动**解除武装**（不自动续跑）——人要求接续
>   （任何措辞）时用 `update_goal(action="resume")` 重新武装；
> - 用户显式要求暂停 → `update_goal(action="pause")`（pause/resume 须直接顶级人类请求）；
> - `blocked` 仅同一阻塞条件连续 ≥3 个 goal 轮次后允许，`blocked_reason` 写具体条件；
> - `complete` 仅目标实际达成时允许（达成判据 = 主线各批全收束 + 全量零回归 + 落账同步）。

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
（quality-maintenance Tier A/B）；2) 长期登记项中重估触发已到达者（状态单点 =
PENDING_TASKS.md）；3) 周期文档对账/残留扫描。每条支线仍须全量 pytest 零回归、commit+留痕（仅本地）。

六、停止条件：先穷尽自主手段，仅当确实无法自主决定时（用户意图不明穷尽无解/公理层语义
错误集确需用户裁决/与工作模式定论冲突/破坏性重构无法确认边界且独立隔离分支也无法确定
技术路线）才 update_goal(action="blocked", blocked_reason=具体卡点+建议)（须先 get_goal
取 goal_id/revision；同一条件连续 ≥3 轮方可 blocked）。

七、非目标：media Phase 4（PT-SEALED-1）、线程无损挂起/恢复、Hindley-Milner 约束求解；
其余非目标 = **任务特定**（按当前主线界定填写——不硬编码旧任务码；长期项状态见
PENDING_TASKS.md，主线范围变更时非目标面随之重估）。
```

> **危险工作变体（隔离分支里程碑，如 P7）**：objective 的批次结构以本文件 §2.0"主线
> 延续点"开工指令为准（分支政策 / Phase 0 只读实证先行[代码零改动] / 性能锚 / 零风险 ff
> 合并细则）；主线任务节改为"Phase 0 只读实证 → 设计文档 → 批次实施（隔离分支内）"。

### 1.4 tasks_docs/ 文档结构指针

| 文档 | 用途 |
|------|------|
| `GOVERNANCE.md` | 任务控制治理章程（文档职责/生命周期/红线；体系级规则单点） |
| `NEXT_STEPS.md` | 当前最紧要项 / 工作模式定论（强制约束，单点）/ 工作规则 / 下一步候选 / 测试基线锚点 |
| `PENDING_TASKS.md` | 长期规划与搁置任务（任务代号按性质分域：PT-FEAT/PT-DEBT/PT-AUDIT/PT-DOC/PT-TEST/PT-DECIDE/PT-SEALED） |
| `HANDOFF.md` | 本文件：固定化内容 + 动态状态 |
| `WORKLOG.md` | 自主工作日志（关键裁定 + 重大方向决策的详尽记录，记录类） |
| `trials/` | 试用地基（T01-T18，清单见 `trials/INDEX.md`）与工具链 `trials/_toolkit/`（harness / batch / 用例即契约 / LLM_SERVICE）——测试资产，非任务控制文档 |

---

## 二、动态状态（随任务更新）

### 2.0 🔴 本 session 交接（2026-09-09 Round5 自指性架构主线 → **机器更换交接**）

> **接手起点**：读 **`tasks_docs/HANDOFF_MACHINE_CHANGE.md`**（机器更换自包含交接：环境重建 +
> 完整任务清单 + gitignored 丢失项 + 协作状态）+ `tasks_docs/NEXT_STEPS.md`（Round5 主线 + ⛔ 工作模式
> 定论）+ `tasks_docs/WORKLOG.md`（Round5 自指性转向 + ai.recall 调和 + C1/C2 裁定）+ `git log --oneline -30`。
> **当前主线 = Round5 自指性体系架构（`selfref` 模块）**：C1 自描述地基 ✅ / C2 verify 三关门 ✅ /
> 下一步 C3 自修改 + 回滚。本轮已 push unsafe-vibe-dev（用户 2026-09-09 授权）。
> 本节 = 当前动态状态唯一节；历史 = §2.1（git / WORKLOG 承载）。
- **工程事实（本 session 收束点）**：
  - 分支 = `unsafe-vibe-dev`（日常开发主线 = `123a341f`）+ `main`（永不触碰）。
    `free-explore` 工作分支已删（内容已 ff 并入 unsafe-vibe-dev）。**已推送 origin**
    [`11a893a7..123a341f`，13 提交：P7 + round4 MEM/REC + round5 整合，用户 2026-09-09
    显式授权]。
  - 测试基线 = `.venv/bin/python -m pytest tests/`；末次全量 **3973 passed / 1 skipped 零回归
    （干净环境 ~243s；数字以实跑为准，不冻结）**。
  - 提交链（新→旧，本 session 段）：`d0fa88be`(P6 契约源解析进程级缓存·A/B 实证 +12.6→+3.3ms
    构造回归根因修复) → `aadc459e`(看门狗阶段边界=collection 结束·98% 误杀根因) → `4e024377`
    (P6 收束账目) → `be0cb55a`(看门狗 dump 文件通道) → `af15f7c8`(看门狗阶段感知+P6 收束) →
    `e645d3ee`(P6·B4 文档) → `a5ebc996`(P6·B2 契约源自举) → `df4af9c2`(P6·B1 共享合成) →
    `9eb638ca`(P5 缓存根因修复) → 其后 P4/P5 链（git 承载）。
  - 交付面（本 session）：**P6 内核自举 ✅**（工具 4 契约源 IBCI bind 声明化 + bootstrap 通道
    + 实现重打包 + 4 字面量真删除；net 实施期实证维持宿主侧；设计文档
    设计文档已随 B4 收敛删除[git 承载]，实施期裁定记录见 WORKLOG P6 条目 +
    docs/architecture/01_native_host_binding.md §六）+ **测试基础设施看门狗根因修复
    ×2**（固定窗口误杀 → collection 边界阶段感知 + dump 文件通道）+ **合并安全评估**（四面
    实证，见下）。

- **🔴 主线延续点（下一位智能体 = P7 危险工作开工指令）**：
  1. **P7 档 B 进程级隔离 + 反射能力 = 当前 P0（危险工作，隔离分支）**：
     - **是什么**：档 B 隔离改造（进程级引擎隔离——消除同进程多引擎共享 sys.modules/模块级
       状态的边界，KNOWN_LIMITS 已登记的"IBC-Inter 无强制力"面）+ 反射能力（F5 档案项，
       消费方重估未做）。
     - **为什么危险**：执行模型过程边界的根本性改变——跨进程生命周期/IPC 或序列化边界/沙箱
       策略/引擎内部服务通道面全变；影响面大、边界无法预先完全确认。
     - **分支政策（硬规则）**：100% 授权独立隔离分支（建议名 `p7-process-isolation`，自
       `free-explore` 拉出）；允许任意程度破坏性实验；**永不触碰 main/unsafe-vibe-dev/
       free-explore**；确认零风险（全量 pytest 零回归 + 复核放行）后 ff 并入 unsafe-vibe-dev，
       merge 无误删分支。
     - **开工顺序（Phase 0 只读实证先行，代码零改动）**：① 现状隔离边界面实证（sys.modules
       共享面、ihost spawn 子环境机制、LLM 通道[不变量 #4]、文件沙箱/isys 外访面、引擎间
       通信面现状）→ ② 进程隔离实现形态对比（multiprocessing/subprocess+协议/…）对照 9 项
       VM 不变量（尤其 #1 统一执行入口）→ ③ 反射能力消费方重估（无消费方 = 裁定延期，
       实证后登记）→ ④ VISION-4 类型层交点联合重估（档 B 是唯一交点方向）→ 设计文档
       `tasks_docs/_p7_process_isolation_design.md`（**待产出**，Phase 0 交付物；设计
       阶段文档规则：先 tasks_docs，落地后收敛 docs/）。
     - **硬约束**：9 项 VM 不变量 + 工作模式定论九条 + 全量零回归门（每批）+ 禁 push +
       详尽落账（WORKLOG）。
     - **性能锚**：`scripts/perf_bench.py` = 数据平面官方改前/改后裁判（5 轮取中位；
       post-P6 本机基线 2026-09-09 实跑：arith ~352/branch ~494/recurse ~2292/string ~30/
       container ~2100/class ~1061 ms——机器/负载相关，价值 = 相对裁判）。A/B 方法论：
       `git worktree add /tmp/<name> <commit>` + `AB_TREE`/`PYTHONPATH` 注入双树对比
       （本 session 合并安全评估技术，WORKLOG 有全记录）。
  2. **P6 内核自举 ✅ 完成 + 里程碑收束（2026-09-09）**：工具 4（math/json/time/schema）
     契约单一权威源 = IBCI bind 声明契约源（`core/runtime/bootstrap/contracts/*.ibci`）+ 
     bootstrap 通道（`kernel_contracts`，零新运行期机制）+ 实现重打包 + 4 字面量真删除；
     net 实施期实证维持宿主侧（默认参数面 + per-engine 状态超出 bind 表达力；远期项 = bind
     默认值语法独立立项）；全量 3963/1；已 ff 收束 unsafe-vibe-dev。细节 = WORKLOG +
     设计文档。
  3. **支线（P7 解阻/间隙期）**：P3 D-3.3 VM 字符串快速路径（紧迫性下调，可交错）/ 质量
     维护 Tier B 巡检 / 文档对账。

- **⚠️ 合并安全评估（用户指定四面实证，2026-09-09，unsafe-vibe-dev 收束态）**：
  - **功能**：全量 3963/1 零回归（干净环境）+ P6 判别 8 例 + P4 D1-D7 语义等价 15 例 +
    P5 命中/未命中哨兵（套件内全过）。
  - **性能**：① 数据平面官方裁判 harness A/B（pre-P6 worktree 9eb638ca vs post-P6，5 轮取
    中位）六项皆噪声内——P4 ~7× 收益完整保留；② 构造期 A/B 发现 P6 +12.6 ms/engine 回归
    → 根因 = 每引擎 4 次契约源重复 lex+parse（10.2ms）→ 修复 = 解析进程级缓存（内容哈希
    自失效）→ +3.3 ms/engine（-74%，残余皆内存有界操作）；③ 编译期 = P5 通道未触碰。
  - **内核稳定性**：10 引擎同进程链（工具 4 运行正确性 + 10 独立 per-engine 实现，registry
    隔离守卫 intact）+ net per-engine 状态隔离（set_timeout 不跨引擎泄漏）。
  - **风险回归**：残留扫描全绿（任务代号/孤儿引用/未用导入零命中）+ B4 文档一致性（两域
    分述单点真理）。**结论：四面全绿，合并安全成立**。
  - **评估期附发现**：测试看门狗阶段边界缺陷第二次形态（执行期 98% 误杀）→ collection
    边界根因修复（aadc459e）；"test_task_scheduler 偶发 hang"旧诊断更正 = 皆为看门狗
    误杀，该观察项关闭（WORKLOG 更正注记）。

- **安全待办清单（登记，非本轮阻塞）**：
  | 项 | 状态 | 备注 |
  |----|------|------|
  | P5 缓存 pickle 反序列化篡改风险 | 已闭合 | 信任域前缀策略 + 加载边界类型契约 + 篡改可观测 + 命中哨兵判别（9eb638ca） |
  | P4 codegen 体 `__builtins__: {}` 边界 | 已验证 | 无内置访问面（D1-D7 覆盖值/错误/污点/Signal 面） |
  | P6 bind 化范围 + net 边界 | 已闭合 | 工具 4 契约源自举落地；net/kernel 5+fs 维持宿主侧（实证裁定记录在设计文档 + 边界表在 01_native_host_binding §六）；远期项 = bind 默认值语法独立立项 |
  | P7 进程级隔离 | 待开工（下一 agent） | 危险工作 → 独立隔离分支（p7-process-isolation）；Phase 0 只读实证先行（见主线延续点 1） |

- **硬约束（延续）**：全程本地 commit、**禁 push**（硬原则）；不触碰 `main`；里程碑
  fast-forward 并入 `unsafe-vibe-dev`（全本地）；9 项 VM 设计不变量（04_vm_interpreter
  §11）+ 工作模式定论九条（禁 compat shim/胶水/tricky/过程式硬编码分发；质量优先于速度；
  原则优先于行为维持；可推翻 IBCI 自身设计缺陷）凌驾一切；改动公理层或语义错误集须全量
  pytest 评估破坏面；破坏性重构默认已授权（详尽记录决策依据 + 变化前后）；无法确认边界
  的破坏性重构 100% 授权独立分支实验（永不触碰 main）。
- **落账纪律**：WORKLOG 条目经临时文件 splice 至 `## 附、书写模式（本文档专用模板，
  书写必须参照）` 锚点前；commit 消息 = 描述性中文；每项完成同步 NEXT_STEPS / HANDOFF；
  测试数字以实跑为准（不冻结）；设计阶段文档先写 `tasks_docs/_<task>.md`（落地后删除，
  最终内容按治理收敛入 `docs/`）。
- **运行注记（测试防卡死，本 session 更新）**：pytest-timeout 每测试 60s（第一层）+ 进程
  看门狗 180s **阶段感知**（第二层：仅框架层 collect/plugin 死锁；collect 结束即解除，
  与套件总时长零竞态）。**无输出退出 124 = 框架层真卡死**，读线程栈 dump 文件
  `.tmp_pytest/deadlock_watchdog_dump.txt`（**非 stderr**——collect 期 stderr 被 pytest fd
  capture 吞没，文件通道阶段无关；文档 = docs/howto/keep_tests_safe.md）。basetemp 强制
  `.tmp_pytest/`；bash landlock partial enforcement 警告无害。

### 2.1 历史状态（git / WORKLOG 承载，本文件不再登记）

> round3 试用需求整合 / meta 层 MVP / VISION-6 P1-P6 的收束历史不在本节登记（章程红线：
> 不保留已完成历史叙述）。过程记录 = `tasks_docs/WORKLOG.md` + `git log`；长期项状态单点
> 真理 = `tasks_docs/PENDING_TASKS.md`；试用需求 intake 模式参照 = WORKLOG round3 条目。

### 2.2 交接检查单（当前有效）

- [ ] **P7 危险工作开工（下一 agent 首任务）**：读 §2.0"主线延续点"第 1 条开工指令
  （分支政策 + Phase 0 只读实证顺序 + 硬约束 + 性能锚）；拉独立隔离分支
  `p7-process-isolation`（自 free-explore）；Phase 0 产出 = 设计文档
  `tasks_docs/_p7_process_isolation_design.md`（代码零改动）。
- [ ] 读 `NEXT_STEPS.md`（P6 ✅ 收束 + P7 开工指令 + ⛔ 工作模式定论）
- [ ] 读 `WORKLOG.md`（P6 批次条目 + 合并安全评估条目 + 看门狗根因条目 + 更正注记）
- [ ] 读 P6 实施期裁定（net 边界/bind 默认值远期项/F5 精化，P7 设计须知悉）：
  `WORKLOG.md` P6 条目 + `docs/architecture/01_native_host_binding.md` §六 边界表
- [ ] 测试基线：`.venv/bin/python -m pytest tests/`（唯一命令；末次 3963/1 干净环境实跑；
  数字以实跑为准不冻结）
- [ ] 看门狗语义：collection 边界 180s + dump 文件 `.tmp_pytest/deadlock_watchdog_dump.txt`
  （docs/howto/keep_tests_safe.md；旧"读 stderr 线程栈"说法作废）
- [ ] 全程本地 commit、禁 push（硬原则）；P7 实验限独立隔离分支（main/unsafe-vibe-dev/
  free-explore 永不触碰）；确认零风险后 ff unsafe-vibe-dev 并删分支。

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
  2.0 本 session 交接（接手起点 / 工程事实 / 主线延续点[开工指令] / 安全评估收束记录 /
      安全待办清单 / 硬约束延续 / 落账纪律 / 运行注记）——当前 session 动态状态唯一节
  2.1 历史状态（git / WORKLOG 承载；已完成历史叙述不登记，仅留指针）
  2.2 交接检查单（当前有效；已完成项移除）
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
