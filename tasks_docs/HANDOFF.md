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

### 2.0 🔴 本 session 交接（2026-09-09 round3 P4+P5 收束 → 下一 agent 接 P6）

> **接手起点**：读本节 + `tasks_docs/NEXT_STEPS.md`（P4/P5 进度 + ⛔ 工作模式定论）+
> `git log --oneline -30`（近期提交动线）+ `tasks_docs/WORKLOG.md`（P4/P5 落账条目）。
> 本节取代下方 §2.1 的旧动态状态（round3/meta MVP 历史保留为参照）。

- **🔴 当前状态 = 内核完整系统工程化（VISION-6）自主推进主线；子方向 ① 真 JIT + ②
  缓存预编译已收束并入 unsafe-vibe-dev（全本地未 push），下一里程碑 = ③ 内核自举（P6）**。

- **工程事实（本 session 收束点）**：
  - 分支 = `free-explore`（工作分支）+ `unsafe-vibe-dev`（里程碑分支，已 ff 到
    free-explore，全本地未 push）+ `main`（永不触碰）。当前 HEAD = `9eb638ca`
    （P5 缓存根因修复）。`free-explore` = `unsafe-vibe-dev`（0 差异）。
  - 测试基线 = `.venv/bin/python -m pytest tests/`；末次全量 **3938 passed / 1 skipped
    零回归**（P5 复核根因修复后；数字以实跑为准，不冻结）。
  - 提交链（新→旧，P4 真 JIT + P5 缓存 + P5 复核修复）：`9eb638ca`(P5 缓存根因修复·
    信任域前缀策略) → `2dac1e11`(P5 pickle 信任域加固) → `2a377db3`(本交接 §2.0) →
    `f46d8f2d`(P5 落账) → `b146e602`(P5 持久 artifact 缓存) → `b370a3c8`(P4 里程碑
    合并落账) → 其后 P4 链（`e94afd7c`~`5fd9372e`，git 承载）。
  - 交付新功能面（本 session）：① **P4 真 JIT**（codegen 路线 ①——v1.0 循环体直接执行 +
    v1.5 cond-codegen[条件+体一起 codegen，drive-loop 交互归零，~5-7× 数据平面收益] +
    v1.1 控制流[break/continue] + 判别套件 D1-D7[15 例语义等价性验证]）；② **P5 持久
    artifact 缓存**（编译期上修——相同源码+内核版本编译产物缓存到磁盘，命中跳过 5 阶段
    管线，IBCI_ARTIFACT_CACHE=1 启用默认关闭零侵入，~8× 编译加速）。

- **🔴 主线延续点（下一位智能体的工作队列）**：
  1. **当前 P0 = P6 内核自举（bind 表达内核契约，台阶 ④ 之后方向）**——把 IBCI 内核
     契约用 `bind`（宿主绑定）表达，自举台阶 ④（meta 层/字符串级直接执行）之后的方向。
     设计起点 = `tasks_docs/_meta_layer_design.md` §六（自举台阶 ④ 端到端架构）+ §八
     （批次计划）。**注意**：§六 台阶 ④ 达成条件 = "类型层承诺清单经 VISION-4/5 落地"
     ——VISION-4/5 类型层是独立方向（user-gated，非内核工程化范畴）。P6 的"台阶 ④ 之后
     方向"须先**实证裁定**：内核契约 bind 化的具体范围（哪些既有 builtin 机制可经 bind
     表达 + 哪些须保持宿主侧）+ 设计确认（对照 9 不变量）→ 分阶段实施。
     **进度**：Phase 0 实证裁定 + B1 ✅（共享合成提取，判别 7 例）+ B2 ✅（工具 4
     契约源自举：契约源 4 件 contracts/{math,json,time,schema}.ibci + bootstrap 阶段
     kernel_contracts[parse→共享合成→per-engine 严格命名空间→register_module，零新
     运行期机制] + 实现重打包[类实例→模块级函数] + 4 字面量真删除 + kernel_version
     递增；全量 3963/1 零回归）。**B3（net）实施期实证取消**：net 8 方法 headers 默认
     参数面[has_default]超出 bind 表达力 + per-engine 状态双重边界 → net 维持宿主侧
     字面量（USER_DEFINED）；远期项登记 = bind 默认值语法（独立立项）。provenance
     变更（工具 4 → EXTERNAL_MODULE）行为安全实证完成。**下一 agent 起点 = B4 文档
     收敛**（01_native_host_binding 内核契约自举节 + 插件体系同步 + KNOWN_LIMITS
     边界注记 + P6 里程碑收束 ff unsafe-vibe-dev）。设计文档
     `tasks_docs/_p6_selfbootstrap_design.md`（含 B2 实施期裁定记录）。
  2. **后续 = P7 隔离改造 + 反射能力（档 B）**——高风险→隔离分支（100% 授权独立分支
     实验）。P7 与 P6 的交点 = 档 B 隔离改造是 VISION-6 唯一与 VISION-4 类型层有交点
     的方向（MVP 落地后联合重估）。
  3. **P3 D-3.3 VM 字符串扫描快速路径**——紧迫性下调（P1 实证已 O(n)），可交错。

- **⚠️ 安全/稳定性评估（合并 unsafe-vibe-dev 的回顾性裁定）**：
  - **功能**：P4 真 JIT（~5-7× 数据平面）+ P5 缓存（~8× 编译期）均经**全量 3938/1 零回归
    + 判别套件 D1-D7（15 例语义等价性）+ P5 契约 4 例[含命中/未命中哨兵判别——
    复核发现加固提交白名单与产物真实类闭包不符致缓存静默死亡，已根因修复：信任域
    前缀策略 + 加载边界类型契约 + 篡改可观测，commit 9eb638ca]**验证，功能正确性已证。
  - **稳定**：P5 缓存**默认关闭**（IBCI_ARTIFACT_CACHE=1 才启用）——零侵入既有行为；
    P4 codegen 体经 `__builtins__: {}`（B7）+ 白名单判据（仅 IbAssign/IbIf/IbPass/
    IbBreak/IbContinue）+ LLM 污点声呐（B4）三重门控，不可 codegen 形状回退 CPS（不改变
    既有执行路径）。协作取消（cancel_event）在 codegen 体步进边界显式检查（与
    _drive_loop_gen 同语义）。
  - **安全**：① P4 codegen 体 = 生成 Python 直接执行函数（**非 eval 用户代码**）——生成
    源码仅经 `rt.get/set_variable_by_uid` + `receive`（协议分派）+ `ec.is_truthy`，无
    用户代码注入面；`__builtins__: {}` 禁内置访问。② **P5 缓存反序列化安全**：pickle
    信任域策略（仅 core/core.* + builtins 类引用，外部模块一律拒绝——安全前提实证 =
    core 全域零 `__reduce__`/`__setstate__` 定义，重建 = 分配 + 字段赋值无执行面）+ 缓存目录
    0700/payload 0600 + 篡改拒绝 stderr 可观测 + 命中/未命中哨兵判别（复核发现首版精确
    白名单与产物真实类闭包不符致缓存静默死亡，已根因修复为信任域前缀策略，9eb638ca）。
    当前评估：**已闭合**（无后续加固待办）。

- **安全待办清单（登记，非本轮阻塞）**：
  | 项 | 状态 | 加固方向 | 触发 |
  |----|------|---------|------|
  | P5 缓存 pickle 反序列化篡改风险 | 已闭合（2dac1e11 加固 + 9eb638ca 根因修复：信任域前缀策略 + 加载边界类型契约 + 篡改可观测 + 命中哨兵判别） | 无（已闭合） | 无 |
  | P4 codegen 体 `__builtins__: {}` 边界 | 已验证 | 确认 codegen 体无任何内置访问面（D1-D7 已覆盖值/错误/污点/Signal 面） | 无（已验证） |
  | P6 内核自举 bind 化范围 | 待设计 | 实证裁定 bind 表达内核契约的具体范围 + 对照 9 不变量 | P6 开工 |

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
- **运行注记（测试防卡死）**：pytest-timeout 每测试 60s + 进程看门狗 180s（无输出退出
  124 = 框架层 hang，读完整 stderr 线程栈定位）；daemon 孤儿线程（collect-timeout 测试）
  须控制在套件时间尺度内（P4 v1.5 cond-codegen ~5× 加速后，超时判别阈值已上调
  test_collect_timeout_policy 20000→100000 迭代）。

### 2.1 当前工程状态 / 下一阶段（历史保留：round3 + meta 层 MVP）

> **接手起点（下一位智能体 = 主线任务延续）**：读本节 + `tasks_docs/NEXT_STEPS.md`
> （当前最紧要 + ⛔ 工作模式定论）+ `tasks_docs/PENDING_TASKS.md`（远期规划）+
> `tasks_docs/GOVERNANCE.md`（任务控制治理）+ `git log --oneline -30`（近期提交与工作动线）
> + `tasks_docs/WORKLOG.md`（round3 整合条目，逐项详录）。

- **🔴 当前状态 = 内核完整系统工程化 + 真 JIT（数据平面性能线）自主执行主线进行中（2026-09-08 用户定向扩展，把内核工程化 + JIT 纳入无人值守自主推进）**；meta 层 MVP[自举台阶 ④] 已收束（M1/M2/M3 全完成）+ 按用户指示一次 fast-forward 并入 unsafe-vibe-dev[全本地未 push]。Phase 0 = 现状实证调查 + 数据平面性能基线 → JIT/性能上修插入点 + 分阶段路线图 → 分阶段实施。硬约束 = 9 项 VM 设计不变量（04_vm_interpreter §11）+ 工作模式定论。VISION-4 类型层 = 独立方向[user-gated，非内核工程化范畴]（2026-09-08 用户定向再评估后列入主线的 meta 层 MVP 已收束——
  依赖评估结论：MVP 前置依赖 = 0[机制面全部既有] / VISION-6 内核工程化非前置[独立线，
  唯一交点档 B 隔离改造 MVP 落地后联合重估] / VISION-4/5 类型层只约束全形态[artifact
  作值/R-6/fn[...]/Verdict]；批次计划 M1→M2→M3 + 范围重划对账[防半接通原则不变] =
  `tasks_docs/_meta_layer_design.md` §八，详见下方主线延续点）。
  round3 需求单（`ibci_feedback_round3.md`，试用方 v3 统一自动机 R185–R202 实证摩擦全集）
  全阶段完成：A（P0 R3-①~⑥ + Tier B 窗口）/ B（P1 R3-⑦~⑬）/ C（P2 文档批 R3-⑭~⑮）/
  D（meta 层/代码作值设计交付）/ E（原阶段 E 顺延批终态裁定）/ F（收敛：Tier B 窗口 +
  长期注册项复查）。单点记录 = `tasks_docs/_trial_round3_intake.md`（逐条核验 + 耦合分析 +
  队列 + 终态）；每项实施细节见 WORKLOG round3 条目 + git log。

- **工程事实**：
  - 分支 = `free-explore`（本 session 后续开发在此；`main` 不触碰）；HEAD = `f598a609`
    （M3 + 质量收尾）；**meta 层 MVP 已并入 unsafe-vibe-dev**（用户 2026-09-08 指示，一次 fast-forward：unsafe = free-explore = f598a609，全本地未 push）；工作区干净；**全程未 push（全本地，硬原则）**。
    **session 级分支裁定（2026-09-08 用户指示）**：开代码修改前已把 free-explore
    fast-forward merge 到 `unsafe-vibe-dev`（0 behind/105 ahead，纯 ff；unsafe-vibe-dev
    = free-explore = `b67d87b0` 起，现推进至 `359b1eef`）；free-explore 不删除（后续
    在其上开发）——详见 WORKLOG 本 session 分支拓扑条目。
  - 测试基线 = `.venv/bin/python -m pytest tests/`（本机解释器见 `AGENTS.local.md`——
    本机无 miniconda3 `ibci` 环境，§2.2 旧条目的 miniconda3 路径作废）；末次全量
    **3909 passed / 1 skipped 零回归**（M2 后；数字以实跑为准，不冻结）。
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

- **🔴 主线延续点（下一位智能体的工作队列）**：
  1. **当前 P0 = 内核完整系统工程化 + 真 JIT（数据平面性能线）**（2026-09-08 用户定向扩展：
     把内核工程化 + JIT 纳入无人值守自主推进范畴；VISION-6 范畴[数据平面性能线/真 JIT[优先]
     + 缓存预编译 + 内核自举 + 隔离改造 + 反射能力]；硬约束 = 9 项 VM 设计不变量
     04_vm_interpreter §11 + 工作模式定论；Phase 0 = 现状实证调查 + 数据平面性能基线 →
     JIT/性能上修插入点 + 分阶段路线图 → 分阶段实施）：
     - **前置里程碑（已完成）**：meta 层 MVP[自举台阶 ④，字符串级直接执行]✅（M1/M2/M3
       全完成 + 按用户指示一次 ff 并入 unsafe-vibe-dev）——批次记录见下。
     - **依赖评估结论**（§8.1/§8.2）：MVP 前置依赖 = 0（机制面全部既有并验证：
       `compile_string`/`run_string` 合成 entry `__string_exec__` / `request_spawn_isolated`
       子环境[E1 继承/防卡死/输出捕获] / 诊断面 / 值类型注册模式[file_handle/knowledge
       先例]；字符串源扩展点 = spawn 子线程体 `run(abs_path)`↔`run_string(code)` 同构
       单点）；**VISION-6 内核工程化非前置**（独立线；档 B 隔离改造 = 唯一交点，MVP
       落地后联合重估[新增隔离消费方 + 威胁模型边界]）；VISION-4/5 类型层只约束
       **全形态**（artifact 作值/R-6/fn[...]/Verdict），MVP 不依赖。
     - **批次计划**（每批 = 设计确认 → 实现 → 全量 pytest 零回归 → 落账 → commit）：
       ~~**M1**~~ **✅ 已完成（2026-09-08，commit 359b1eef，判别 23 项 + 3896/1 零回归；设计细化
        `_meta_layer_design.md` §八.4 + WORKLOG M1 条目）** run_result 值类型（三字段 attribute 访问
        r.exit_status/r.stdout/r.exception + 值相等 + 序列化保真；exception 结构化单一
        权威源 exception_record[CLI+host 共用]）+ 执行路径统一（单一 spawn 核心两源形式：
        文件源既有 + 字符串源新）+ run_file dict→run_result 精化 + run_code 落地）→
        原批次：run_result 值类型（新内核原生值类型 exit_status: str / stdout: str /
       exception: any[结构化 dict {code, message, source}]，exception 捕获面从平坦错误串
       升级为结构化[CLI result-json exception 面同构]）+ 执行路径统一（单一 spawn 核心
       两源形式：run_file 精化 dict→run_result + 新 run_code 字符串形式）→
       ~~**M2**~~ **✅ 已完成（2026-09-08，commit 3fa51eec，判别 7 项 + 3909/1 零回归）** meta 模块
        + meta.compile(code: str) fail-fast 校验面[子引擎 compile-only + ibci 源定位 +
        IBCI try/except 可捕获；不新增 IBCI 异常类型]
       （子引擎 compile-only；失败抛 CompilerError[ibci 源定位]，成功 void；与 CLI check
       面同构）→ ~~**M3**~~ **✅ 已完成（2026-09-08，判别 3 门实测 + 文档同步[README 单点真理
       表 + howto + use_isolation LLM 继承面修正] + 全量零回归）** 三门管线惯用法固化
       （howto run_code_safely.md + 参考实现
       [预注册向量 + 机械判定 e34_p4 形态] + 文档同步）。
     - **范围重划对账**（§8.3）：MVP/全形态重划非推翻 Phase D"防半接通"裁定——MVP 边界
       crisp 自洽无空洞承诺（每个交付面机制完整 + 判别测试）；全形态继续登记（VISION-4
       依赖，§四清单收窄为 ①③④⑤ + ② 类型层深度参与——run_result 类型存在半被 MVP 满足）。
     - **边界注记**（入 KNOWN_LIMITS）：威胁模型 = 受信任候选代码（选项 A 调用方治理；
       非对抗性代码安全边界[无进程级隔离]）；性能 = 每调用一次子引擎构造（候选验证场景
       充分；热循环 = VISION-6 档 A/真 JIT 上修输入）。
  2. **round4 试用需求单到达时**：按恒高优先重新 intake（参照 `_trial_round3_intake.md`
     模式：逐条核验 + 耦合分析 + 新队列 + NEXT_STEPS 插队）；试用方 run 存档
     （`/home/dsh/proj/ibci-trial/`）为实证证据源（只读）。
  3. **周期质量维护**（MVP 主线之外并行）：Tier A 随主线顺带 / Tier B 阶段边界窗口 /
     Tier C 专项审计仅用户指定时独立分支执行。
  4. **候选后续主线（长期登记项，不自主开工——需用户指示或重估触发条件成立）**：
     - **VISION-4 类型理论加固**：开工输入已就绪——`_meta_layer_design.md` §四 类型层
       承诺需求清单（MVP 后收窄：① CompilationArtifact 作类型值 / ③ BehaviorExpr 值
       类型 / ④ fn[...] 高阶签名 / ⑤ Verdict 类型 + ② run_result 类型层深度参与）+
       ref A2/A5/A6/B2 挂起整合推进。
     - **N3 measure_freq（logprob 通道）**：待决（探针实证：SiliconFlow chat 通道静默
       忽略 logprobs、legacy completions 通道完整支持）；重估触发 = provider 支持
       completions/logprob 通道 或 corpus/probe 设计内化。
   - **D-3.3 VM 字符串扫描快速路径**：已并入内核工程化 P0（数据平面性能线，§1；与演化平面性能方向合流）。
       **B5 并发成熟化**：挂起（一等原语已成熟，专项需单独立项）。**远程 CI**：
       待用户显式授权（`ci_local.sh` 四层本地复现已就绪）。
  5. **每轮自主评估现状**（队列有活持续推进；调整顺序/优先级/批次划分的理由记入 WORKLOG）。

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
  - **M1（meta 层 MVP 批次 M1，commit 359b1eef）落地裁定**（M2/M3 须沿用）：
    ① run_result = 不可变值类型（CLASS kind / PRELUDE 可见；字段访问面 = **字段**
    attribute `r.exit_status`/`r.stdout`/`r.exception`——`MemberSpec kind="field"` 经
    `_dispatch_getattr` 实例字段优先命中，Exception.message 先例；**非方法**[误导须括号]
    **非下标**[map 语义]）；② exception 结构化 `{code,message,source{file,line,column,
    snippet}}` = 单一权威源 `core/runtime/exception_record.py`（CLI --result-json + host
    run_file/run_code 共用，消双写真相）；③ 执行路径统一 = `request_spawn_isolated`
    单一 spawn 核心两源形式（文件源 entry_path XOR 字符串源 code，fail-fast 恰好一源；
    字符串源 sub project_root = 父 project_root 合成 entry 锚定，沙箱外 = 既有
    RUN_PERMISSION_ERROR）；④ 诊断码零新增（子运行失败经 exception 值面传递既有码）。
    威胁模型/性能边界入 KNOWN_LIMITS §二十六。

- **挂起/待决清单（本轮 7 项 + 长期登记 8 项）**：

  | 项 | 状态 | 重估触发 / 条件 |
  |----|------|----------------|
  | A2 泛型约束 / A5 解构 / A6 Enum-tagged union / B2 惰性结构 | 挂起 → VISION-4 整合推进 | VISION-4 开工（类型理论设计落地） |
  | D3 新能力配套诊断码 | 挂起 | 随新能力实施（纯增面 + catalog + 15_diagnostics + parity 门） |
  | B5 并发原语成熟化 | 挂起 | 专项需单独立项评估（一等原语已成熟；流式观测边界记 KNOWN_LIMITS 待评估） |
  | N3 measure_freq（logprob 通道） | 待决（方向保留） | provider 支持 completions/logprob 通道 或 corpus/probe 设计内化 |
  | R-2b meta.compile / R-6 行为表达式作值 | **MVP ✅ 已收束并入 unsafe**（不依赖类型层，§八 批次计划 M1→M2→M3）/ 全形态登记不实施 | 全形态前置 = VISION-4/5 类型层（§四清单收窄 ①③④⑤ + ② 深度参与）；当前 P0 = 内核完整系统工程化 + JIT |
  | D-3.3 VM 字符串扫描快速路径 | 已并入内核工程化 P0（数据平面性能线，§1） | 与演化平面性能方向合流（VM 执行模型性能架构面） |
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
