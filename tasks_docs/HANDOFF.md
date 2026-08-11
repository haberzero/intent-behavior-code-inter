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
| 破坏性重构授权 / 分支政策 / 禁 push | 见 AGENTS.md（权威源）。**分支合并细则（2026-08-11）**：零风险/边界清晰改进（全量 pytest 零回归 + 复核放行）可**直接合并** unsafe-vibe-dev；大风险/无法确认边界仍走独立分支 + 手动 cherry-pick；判定以"是否确认零风险"为准 |

### 1.2.1 goal 配置习惯（每个 session 新配置 goal 时自动采用，2026-08-09 用户定案）

> 创建 goal（`create_goal` / `set_goal`）时按此默认参数，除非用户在本 session 显式覆盖：
>
> | 参数 | 值 | 说明 |
> |------|----|------|
> | `max_duration_seconds` | **14400（4 小时）** | 最晚结束时间 = 当前时刻 + 4h |
> | `max_auto_turns` | **10** | 允许 goal 自动续跑次数 |
> | `token_budget` | **720000（720K）** | token 窗口预算上限 |
> | token 总预算 | 无上限 | 不设总预算上限 |
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
  2026-08-11 补充"零风险直接合并"细则）：无法确认边界/危害程度的破坏性重构 100% 授权在其
  独立分支实验，独立分支禁止直接合并到 unsafe-vibe-dev 或 main，确认技术路线后仅允许手动
  单独更新 unsafe-vibe-dev；永远不允许触碰主干分支（main）。**零风险细则**：经充分验证零风险/
  边界清晰的改进（全量 pytest 零回归 + 复核放行，无对外契约/架构级风险）允许**直接合并**到
  unsafe-vibe-dev；识别到大风险/无法确认边界的破坏性重构仍走"独立分支 + 手动 cherry-pick 单独
  更新 unsafe-vibe-dev"。判定以"是否确认零风险"为准，非以改动规模。工作日志：所有自主决策/
  方案取舍/变化前后必须详尽记录于 WORKLOG，"只记录，不断决"。

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

七、非目标：media Phase 4（PT-SEALED-1）、跨进程/CPU 并行、跨引擎通信、线程无损挂起/恢复、用户级泛型类（PT-FEAT-3）、Hindley-Milner 约束求解。`yield` 惰性生成器（PT-FEAT-1）是阶段 5 下一主线，非"非目标"；是否纳入本 goal 视主任务界定。
```

### 1.4 tasks_docs/ 文档结构指针

| 文档 | 用途 |
|------|------|
| `NEXT_STEPS.md` | 当前最紧要项（下一主线待择定）/ 已完成摘要 / 工作模式定论 / 工作规则 |
| `HANDOFF.md` | 本文件：固定化内容 + 动态状态 |
| `PENDING_TASKS.md` | 长期规划（任务代号按性质分域：PT-FEAT/PT-DEBT/PT-AUDIT/PT-DOC/PT-TEST/PT-DECIDE/PT-SEALED） |
| `PENDING_REVIEW_ITEMS.md` | 代码复核审查循环（PT-AUDIT-3：R1/R2/R3 已执行，R4 覆盖率核对已执行（2026-08-09），R5 doc 聚焦治理已执行（全量待独立窗口）） |
| `DOC_AUDIT_REPORT.md` | docs/ 治理审核记录（2026-08-06，F0-F4 已执行完成，归档） |
| `TEST_MATRIX_FINDINGS.md` | 测试矩阵核对发现（PT-TEST-3 研究存档，PT-TEST-1 重构输入） |
| `THREAD_DESIGN.md` / `PROMPT_DESIGN_REVIEW.md` / `MEDIA_DESIGN.md` | 设计要点迁入（并发 / `__prompt__` 待决项 / media 封存） |
| `WORKLOG.md` | 自主工作日志（关键裁定；设计决策收敛于 `PENDING_TASKS.md` §十） |
| `AIMLESS_REVIEW.md` | 无目的审视潜在参考（背景过程） |
| `CODE_SMELL_AUDIT.md` / `BRANCH_NESTING_AUDIT.md` | PT-AUDIT-1/2 审计（长期周期，独立分支） |
| `TEST_REFACTOR.md` / `TEST_REFACTOR_REPORTS.md` | 测试体系重构（PT-TEST-1，**已并入 OBSERVABILITY_REFACTOR**） |
| `OBSERVABILITY_REFACTOR.md` / `test_baseline_20260806.txt` | 可观测性统一重构任务控制文档（**已完成**，Phase 0-4 落地）/ 覆盖基准快照 |
| `DIAGNOSTIC_DESIGN.md` | PT-FEAT-9 设计权威（**已完成**，实施步骤 A-E 落地，归档） |
| `YIELD_GENERATOR_DESIGN.md` | 阶段 5 yield 惰性生成器设计权威（**已完成**，独立分支 exp/yield-generator） |
| `_ASYNC_UNIFY.md` | 异步地基遗留妥协根治实施计划（PT-DEBT-12/13/14/15，F1→B1→F2/F3→M1-M4 **全部收尾，2026-08-09**） |
| `_code_yield_from.md` | 阶段 5 增量 `yield from` 生成器委托设计记录（**已完成**，2026-08-09；按惯例汇报后待删，当前保留供追溯） |
| `_code_m1_call_dedup.md` / `_code_m2_drive_dedup.md` | M1 `.call` 双写收敛 / M2 驱动去重设计记录（**已完成**，2026-08-09，独立分支 exp/async-m1m2；保留供追溯） |
| `_HEALTH_AUDIT_PLAN.md` | **三轴健康盘点**（2026-08-09 只读调查）：异步统一完整性 A1-A6 遗留 + 内核健康（深层嵌套/死同步包装）+ 技术手册健康（P1/P2 待修）。**下一步规划输入** |
| `_REAL_LLM_E2E_PLAN.md` | **真实 LLM e2e 全面试用 + 高强度批判检测**（2026-08-11 用户定案，下一 session 主任务）：本地 LLM 服务搭建、全语法特性试用清单、MOCK-vs-真实差异批判检测、成功门。设计权威 |
| `_MAIN_MERGE_PLAN.md` | **unsafe-vibe-dev 合并取代 main 规划**（2026-08-11）：合并时机/进度/前置（文档 README 更新/版本评估/examples）/细则/风险 |
| `_DOC_HEALTH_20260811.md` | **docs/ 全量健康检查记录**（2026-08-11，doc-governance Phase 2 审计）：P0/P1/P2 全部问题清单 + 已修复/剩余标记。**晚上自主续做依据** |
| `_API_CONFIG_DESIGN.md` | **`api_config.json` 配置机制分析与改进设计**（2026-08-11 用户提出，PT-FEAT-13）：现非原生加载（脚本约定）、schema 极简、无校验、mock 字符串嗅探；改进 C1-C8（原生加载/set_config 结构化/校验诊断/env 引用/mock 配置化/命名路由/reasoning 标志/容器类型）。C1-C3 为真实 LLM e2e 前置 |

---

## 二、动态状态（随任务更新）

> 本部分随任务推进由各 session 更新，**不因任务完成删除**。

### 2.1 当前任务 / 下一阶段

> **接手起点**：先读本节（当前状态）+ `PENDING_TASKS.md` §〇（优先级总表，单一权威源）+
> 本 session 成果记录（`WORKLOG.md` 尾部 + git 历史 `c61a6e0..HEAD`）。

- **🔴 下一 session 主任务（2026-08-11 用户定案）**：**基于本地 LLM 服务的真实 e2e 全面试用 + 高强度批判检测**，
  通过后评估 **unsafe-vibe-dev 合并取代 main**。详细见 `_REAL_LLM_E2E_PLAN.md` + `_MAIN_MERGE_PLAN.md`。
  - **接手第一步**：起本地 OpenAI 兼容 LLM（Ollama/LM Studio/vLLM，**非思考模型**），`ai.set_config(base_url,key,model)`
    指向它，最小探针 `str r = @~ 说你好 ~` 验证连通。
  - **配置机制前置（PT-FEAT-13 C1-C3，`_API_CONFIG_DESIGN.md`）**：现 api_config.json 非原生加载（脚本约定）——
    建议先落地**原生配置加载 + set_config 结构化 + 校验诊断**，使本地 LLM 试用配置成为一等机制
    （替代每脚本 `file.exists/json.parse/set_config` 约定；`reasoning:false` 承载非思考模型约束）。
  - **主任务**：按 `_REAL_LLM_E2E_PLAN.md` §四 全语法特性真实试用 + §五 e2e 批判检测（MOCK-vs-真实差异 = 缺陷候选 +
    对抗场景），产出验证报告，处置暴露问题，评估合并条件。
  - **CI/CD**：GitHub 侧已停用自动触发（`ci.yml` → `workflow_dispatch`），勿自动恢复；待单独设计"可靠化/实用化"。
  - **goal 配置**：按 §1.2.1（max_duration_seconds=14400 / max_auto_turns=10 / token_budget=720000 / 总预算无上限）；
    objective 套 §1.3 模板，主任务 = 真实 LLM e2e 试用 + 批判检测 + 验证报告 + 合并评估。

- **PT-DEBT-17 `ai.run_batch` 同步阻塞根治（2026-08-11，独立分支 exp/run-batch-cps → 手动应用 unsafe-vibe-dev ebbb7f8，全量 2135 passed / 1 skipped）**：
  - **三层不一致全部根治**：`run_batch` 返回 `CPSDrivable` Waitable（与 `stream_call` 返回 `IbStreamHandle`、A3
    `_SlotUpdateWaitable.cps_drive` 同构）——VM `vm_handle_IbCall` `yield from result.cps_drive(executor)` 帧内驱动。
    **① 主线程 `fut.result()` 硬阻塞** → `_run_batch_cps` 把多 LLM Future 聚合为 `LLMBatchFuture`（新聚合 Waitable）
    由调度器非阻塞等待；**② 同步 `_prepare_behavior_call` `vm.run` 重入** → 用 `_prepare_behavior_call_cps`（段求值/
    意图消解/hint 嵌入 VM 帧栈）消除；**③ 与 `stream_call` Waitable 范式割裂** → 返回 Waitable 统一。vtable
    return_type=list 契约不变（auto-yield 后仍收 boxed IbList）。宿主/线程体无 VM 走 `_run_batch_sync` 同步兜底。
  - **顺带清理死代码**：`LLMExecutorImpl.resolve()` + `LLMFuture.get()`（VM 全走 `resolve_future_cps`）+ 其 5 个
    死测试 + 死 import + `LLMExecutor` 协议声明同步；统一批量聚合 `_aggregate_batch_results`（消除双路径分叉）。
  - 设计记录 `tasks_docs/_code_run_batch_cps.md`；general 复核 3 建议级全整改；补判别性回归测试
    `TestRunBatchWaitableContract`（旧实现返回 List 必失败）。文档 `05_vm_specification.md` §3.4 公理 LLM-4 同步。
- **A5 用户类构造帧内 CPS 根治（2026-08-11，独立分支 exp/a5-cps-construct → 直接合并 unsafe-vibe-dev 356b0d8，全量 2137 passed / 1 skipped）**：用户类（不含原生 __init__）构造改返回 `_ClassInstantiateDrive`（Waitable+CPSDrivable）——`cps_drive` 在 VM 帧内 yield 字段默认值 + 用户 __init__（UserFunctionCall），消除 `vm.run` 重入与 `init_method.call` 嵌套 TaskScheduler；leaf.py 兜底细化（CPSDrivable 无论 func 是否 IbClass 均帧内驱动，纯 Waitable 仅非 IbClass auto-yield，thread 原生 __init__ 返回 IbThread 句柄仍不 auto-yield）；宿主/线程体走同步 instantiate 兜底。general 复核 5 检查点 PASS + 全量 2137/1 零回归。**A6 评估维持现状**（niche + 条件触发，登记已知项）。**分支政策细则**：2026-08-11 用户明确"零风险直接合并"，A5 因零风险直接合并到 unsafe-vibe-dev。
- **当前主线（架构健康性优先，2026-08-08 用户定案）**：**异步地基遗留妥协根治（统一执行模型闭环）——全部收尾（2026-08-09）**。
  审计确认内核层仍有"任务内同步重入调度器"遗留旁路（登记 PT-DEBT-12/13/14/15）：
  - **PT-DEBT-12（F1）用户方法 CPS 化、PT-DEBT-13（B1）chan.send Waitable 化、PT-DEBT-14（F2/F3）
    slot.update + prompt hint CPS 化、PT-DEBT-15（M4）LLM 真挂起——已完成（2026-08-08）**；M3（prompt 单源）
    已确认收敛。
  - **PT-DEBT-15 剩余 M1（.call 双写收敛）/ M2（驱动去重）已完成（2026-08-09，独立分支 exp/async-m1m2，
    全量 2137 passed / 1 skipped）**。M2 线程体 `_drive_generator` 复用 `_drive_loop_gen` + `TaskScheduler`
    （单一权威驱动）；M1 四个可调用对象（IbUserFunction/IbFnCallable/IbBehavior/IbLLMFunction）`.call()` 变薄
    宿主包装委托 CPS 生成器（消绑定双写）。实施计划与落地状态 `_ASYNC_UNIFY.md`（F1→B1→F2/F3→M1-M4 全部收尾）。
- **低风险推进（2026-08-09，unsafe-vibe-dev，4 commit）**：
  - **PENDING_REVIEW_ITEMS 状态同步**（29e7017）：D1-D5 已落地、R5 聚焦治理已执行（消除与 PENDING_TASKS 交叉滞后）。
  - **PT-AUDIT-2 宽 except 核验**（314e260/5bed073，独立分支 exp/audit-branch-nesting）：ibci_ai 已窄化
    `_PROVIDER_ERRORS`、auto_discovery 为 fail-fast 重抛——A 类保留，无代码变更。
  - **docs/ 过时表述修复**（92a1676）：05_coroutine/04_vm 标记 yield 惰性生成器已落地；L3 收敛为生成器内
    LLM 并发流水线未实现。
- **技术手册三修 + 文档残留清理（2026-08-10，unsafe-vibe-dev，PT-DOC-3）**：① `01_principles.md:255` §6.3
  改写为现状（意图栈继承由 `IbIntentContext.fork()` 承担公理 IC-1；`IsolationPolicy` 实际字段
  `inherit_plugins`/`collect_timeout`，跨隔离边界不继承意图）；② `04_vm_interpreter.md:29` 统一执行入口表述
  （模块入口 `execute_module`→`run_body`；宿主入口 `.call` 薄包装委托 `_vm_call_*`+`_drive_generator`）；
  ③ `docs/README.md` 目录树补 `15_diagnostics.md`；④ NEXT_STEPS.md:50 旧"遗留技术债"表述改归档记录。
- **异步统一完整性 A1/A3/A4 完成（2026-08-10，独立分支 exp/async-unify-a，全量 2138/1，待手动应用 unsafe-vibe-dev）**：
  - **A1 内联 `@~` 接 CPS**（llm_behavior.py）：`vm_handle_IbBehaviorExpr` 非 callable 分支切
    `execute_behavior_expression_cps`（段求值 yield 嵌入帧栈 + LLM 线程池挂起）。顺带补 `IbGenerator.generic_next`
    Waitable 契约缺口（`_drive_generator_loop` 声明"向外 yield 的只有 GeneratorYield 与 Waitable"，迭代侧此前只实现其一）。
  - **A4 LLM 函数 CPS-yield**（_llm_function.py，PT-FEAT-1 直接项）：`execute_llm_function_cps` 拆分
    `_prepare_llm_function_call_cps`（CPS 段求值 + `LLMFunctionCallSpec` 快照）+ `_call_and_parse_llm_function`
    （worker 安全、record_current=False）+ 提交线程池 yield LLMFuture。
  - **A3 `_SlotUpdateWaitable` 并入调度器**（comm.py + leaf.py）：新增 `cps_drive` 帧内 CPS 驱动生成器；
    `vm_handle_IbCall` 对 `getattr(result, "cps_drive", None)` 非 None 的 Waitable 帧内 `yield from`（消除
    `try_result` 内嵌套 TaskScheduler）。宿主 `_drive` 路径保留。
  - 测试 +1（slot.update(snapshot) 帧内驱动）；独立复核通过；A2（意图消解）/A5（类构造）/A6（协议方法）遗留待评估。
- **内核健康三项 + A2（2026-08-10，unsafe-vibe-dev，全量 2138/1，0 warning）**：
  - **测试持续 warning 修复**：`test_recursion_overflow_propagates_root_cause` 改用 `pytest.warns` 显式断言
    `KDIAG_RUNTIME_ENV_LIMIT` 警告投影（PT-FEAT-9 设计内"警告不门控"，非缺陷；生产代码不动）。
  - **死同步包装清理（-241 行）**：删 `invoke_behavior`/`execute_behavior_object`/`execute_llm_function`/
    `invoke_llm_function`（M1 收敛后零消费者互引成环，协议注释"唯一对外接触点"已过时）；保留
    `_prepare_behavior_call`/`_evaluate_segments`（dispatch_eager/run_batch 后台线程依赖）与 `run_batch`
    （ai.run_batch 消费）；同步更新 IILLMExecutor/LLMExecutor 协议声明。
  - **双驱动循环合并（-105 行）**：`_drive_generator_loop` 并入 `_drive_loop_gen`（`yield_generator_values` 参数），
    顺带修复生成器体缺 step/cancel 检查。
  - **A2 意图消解 CPS 化（+76 行）**：`resolve_content_cps`/`IntentResolver.resolve_cps`/
    `get_resolved_prompt_intents_cps`，CPS 预求值路径消除 `vm.run` 同步重入；同步 `_prepare_behavior_call`
    保留（后台线程合法）。
- **彻查：`run_batch` 三层设计不一致 + 同类排查（2026-08-10，只读彻查，登记 PT-DEBT-17）**：
  - **PT-DEBT-17 `ai.run_batch` 同步阻塞（确凿，待彻底修复）**：`run_batch`（`_behavior.py:339`）返回
    `List`（非 Waitable）→ 不走 auto-yield → 主线程 `fut.result()`（:383）同步阻塞等全部 LLM（实测
    main_thread=True + `_prepare_behavior_call`（:369）`vm.run` 重入 + 同模块 `stream_call`/`stream_channel`
    返回 Waitable 协作对比范式割裂（design-philosophy §三/§四）。修复方向：CPS 化（预求值改 yield +
    多 Future 聚合 Waitable）+ `ai.run_batch` vtable return_type 契约评估。涉及对外契约，独立窗口。
  - **彻查证伪（非问题）**：`ihost.collect`/`run_isolated` 返回 `HostAwaitable`（标准 Waitable），经
    `request_collect` 精确打点证实 fast 子任务完成后立即返回、总时=max 非 sum——是文档化透明异步契约
    （`14_concurrency.md` auto-yield），非同步阻塞。一度误判已撤回。
  - **死代码发现**：同步 `LLMExecutorImpl.resolve()`（`_scheduler.py:78`）与 `LLMFuture.get()`（`llm_result.py:129`）
    零真实调用（仅 docstring 示例），VM 全走 CPS `resolve_future_cps`——可随 PT-DEBT-17 清理。
  - **同类排查结论**：`collect`/`stream_call`/`thread`/`stream` 均正确 Waitable 范式；`run_batch` 是唯一
    "返回非 Waitable 的等待型原语"；无其它 `fut.result()`/`thread.join()` 在 VM 主路径同步阻塞（已全量扫描）。
  - 详见 WORKLOG 与 PENDING_TASKS PT-DEBT-17。
- **三轴健康盘点（2026-08-09，只读调查，见 `_HEALTH_AUDIT_PLAN.md`）**：从异步统一完整性 + 内核健康 +
  技术手册健康三维度，结合真实代码给出下一步规划（见下方"下一步候选"）。
- **本 session（2026-08-09，崩溃恢复点 c61a6e0 起，全量 2074 → 2137 passed / 1 skipped）**：
  - **P0 阶段 5 增量**：`next()` 内建 + `yield from` 生成器委托（主交付）——顺带根治 `_drive_generator_loop`
    生成器体内调用生成器函数的预存缺陷、迭代解析收敛 `_resolve_iterable`（现居 `shared/iterable.py`）。
  - **PT-FEAT-5 三项**：诊断码目录（`catalog.py` 76 码 + formatter fail-open + `15_diagnostics.md`）、
    符号表/类型绑定导出（`exporter.py` + 修 `inspect`/`semantic` CLI 死路径）、`bench` 编译基准。
  - **P1 PT-FEAT-10 UID 生成统一**：`core/base/uid.py` 单一权威源（11 家族），零内联，round-trip 保真。
  - **P2 审计**：R4 覆盖率核对（2 处 TRUE_GAP 补测）、R5 聚焦治理、PT-AUDIT-1 smell 全量事实回顾（A/B/C/D 定案）。
  - **质量**：三次独立 general 复核（中间/交付门/兜底专项）全部整改（含 `is_generator` 基类化、迭代解析中立归属、
    非可迭代测试修正、注释卫生）。兜底专项审计结论：全部属职责分离型合法 fallback，无 tricky/兼容妥协。
  - **异步地基收尾（M1/M2）**：见上——统一执行模型闭环完成。独立分支 exp/async-m1m2 实验，复核（general agent）
    A/B/D 放行 + C 记录（IbUserFunction void 返回语义向主路径收敛）。补回归测试 +9（`test_call_drive_convergence.py`）。
  - 设计记录 `tasks_docs/_code_yield_from.md` / `_code_m1_call_dedup.md` / `_code_m2_drive_dedup.md`；完整逐项见 `WORKLOG.md` 与 git 历史。
- **下一步候选（按优先级，见 `PENDING_TASKS.md` §〇 + `_HEALTH_AUDIT_PLAN.md`）**：
  1. **技术手册三修**（低风险立即可做）：`01_principles.md:258` P1 过时 `inherit_intents` 字段、`04_vm_interpreter.md:29`
     P2 `.call` 路径表述、`README` 目录树补 `15_diagnostics.md`。
  2. **PT-DEBT-9/10/11 文档残留清理**：NEXT_STEPS.md:50 旧"遗留技术债"表述与根治状态不同步。
  3. **异步统一完整性（中风险，独立分支）**：A1 内联 `@~` 表达式接 CPS（llm_behavior.py:156，最高价值）、
     A4 LLM 函数 CPS-yield（_llm_function.py:202，PT-FEAT-1 直接项）、A3 `_SlotUpdateWaitable` 并入当前调度器。
  4. **PT-DEBT-4 `file` 模块重命名**（P1，破坏性变更独立窗口——已授权但需独立窗口审慎执行）。
  5. **PT-FEAT-5 剩余 CI/CD**（P0，涉远程 push，禁 push 硬原则，须用户显式授权后另行执行）。
  6. **P3 VISION**（PT-FEAT-8 分层张力待独立窗口；PT-FEAT-2 Enum 设计冻结级；PT-AUDIT-2 深嵌套/长 elif 链独立分支）。
- **评估为维持现状（已登记 PENDING_TASKS，勿重复推进）**：PT-FEAT-11（序列化器自动化）、PT-FEAT-12（AST uid 字段）、
  PT-FEAT-2（Enum 非 str 成员）、PT-FEAT-8（`.ibc_meta` 快照，分层张力）。
- **阶段 5 `yield` 惰性生成器已完成（2026-08-08，unsafe-vibe-dev，全量 2043 passed / 1 skipped）**：
  含 `yield` 函数自动为惰性生成器（D-08 自标记，async 关键字已取消），单可恢复驱动
  `_drive_generator_loop` + `GeneratorYield` 标记 + `IbGenerator` 值对象 + `generator[T]` 类型。
  设计权威 `tasks_docs/YIELD_GENERATOR_DESIGN.md`。
- **PT-FEAT-9 阶段 4 已完成（2026-08-07，unsafe-vibe-dev，全量 2021 passed / 1 skipped）**：
  `kernel_diagnostic` helper（单一记录双投影：警告不门控 + 事件受 observability 门控，rc best-effort）+
  12 处站点迁移（文案逐字）+ e2e 事件投影测试 + `docs/architecture/09_observability.md`。设计权威
  `DIAGNOSTIC_DESIGN.md`（实施步骤 A-E 全部完成）。
- **kernel→runtime 穿透已根治（2026-08-08，unsafe-vibe-dev，commit d11bad0）**：用户红线"禁止一切
  kernel→runtime 穿透"。两处穿透（registry 惰性 import EventBus、host_interface 惰性 import
  kernel_diagnostic）改为依赖注入——registry 新增 `set_event_bus`（未注入 get fail-fast、peek fail-open）、
  HostInterface 新增 `set_diagnostic_emitter`（未注入回退 warnings.warn），engine 组装期注入。
  残留扫描确认 core/kernel/ 零 runtime import。
- **意图栈扁平化历史兼容已彻底移除（2026-08-08，unsafe-vibe-dev，commit 3ce9b7d）**：用户裁定"无事实
  用户，历史兼容不是考虑项"。删除序列化 `intent_stack` 平铺双写与旧格式反序列化回退、`context.intent_stack`
  property、两处接口协议声明；补意图上下文 6 槽位 round-trip 测试（+3）。
- **R 批次全部完成（2026-08-07，unsafe-vibe-dev，全量 2001 passed / 1 skipped）**：R4+R3（82c9c0f，1988/1）
  P3 公开协议 + D-04 `IbThread` 满足 Waitable → R6（35f1437，1995/1）嵌套函数自动只读捕获 → R2（c16b05e/c4c63aa，
  1998/1）调度器通知式唤醒 → R1（6dc9214，2001/1）函数调用 trampoline 化（EXEC-1 根治，深递归 Python 深度恒定）。
  各独立分支实验、手动 cherry-pick 应用 unsafe-vibe-dev。设计/决策见 `EXEC_REFACTOR_BATCH.md`（无悬而未决问题）。
- **已定案（不再重议）**：R5 撤回（`await` 幂等是 auto-yield 组合承载，改报错破坏 `await collect(h)`）；
  D-08 保留透明 async（CPS 天然可挂起 + auto-yield 组合 + 值契约 + yield 自标记）。
- **阶段 1/3 已完成（2026-08-07，unsafe-vibe-dev，全量 1984 passed / 1 skipped）**：地基 1a-1e（调度器执行核心/
  Waitable 家族 try_result/阻塞即挂起/协作取消/llmexcept×await/取消覆盖用户函数）+ 统一清理 W1-W5/P3/P4
  （非阻塞命名/订阅契约/pubsub EventBus/comm 命名回归/死状态/文档/cell 隔离/引擎级全局事件总线）。
- **后续增量（可选起点）**：streaming / host async 改进（`YIELD_GENERATOR_DESIGN.md` §五遗留）或
  `_ASYNC_UNIFY.md` M1/M2（当前主线未完）。
- **保留规划**：media Phase 4（PT-SEALED-1，彻底封存）。
- 要求：subagent 仅 general agent；每批全量 pytest 零回归；新缺陷按"不删也不修"两档处置；全程本地 commit、禁 push。

### 2.2 已完成摘要

- **2026-08-09（本 session：P0 阶段5增量 + PT-FEAT-5×3 + PT-FEAT-10 + P2 审计 + 异步地基 M1/M2 收尾 + 低风险推进，unsafe-vibe-dev + 独立分支 exp/async-m1m2 / exp/audit-branch-nesting，全量 2074 → 2137 passed / 1 skipped）**：
  - **异步地基 M1/M2 收尾**：PT-DEBT-15 剩余 M1（.call 双写收敛）/ M2（驱动去重）完成——统一执行模型闭环
    全部收尾。M2 线程体 `_drive_generator` 复用 `_drive_loop_gen` + `TaskScheduler`（单一权威驱动）；M1 四个
    可调用对象 `.call()` 变薄宿主包装委托 CPS 生成器。独立分支 exp/async-m1m2 实验 + general 复核 + 补回归测试 +9
    （`test_call_drive_convergence.py`）。设计记录 `_code_m1_call_dedup.md` / `_code_m2_drive_dedup.md`。
  - **低风险推进**：PENDING_REVIEW_ITEMS 状态同步（D1-D5/R5）；PT-AUDIT-2 宽 except 核验（A 类保留）；docs/
    过时表述修复（yield 已落地）。4 commit（29e7017/314e260/5bed073/92a1676）。
  - **三轴健康盘点**：只读调查产出 `_HEALTH_AUDIT_PLAN.md`（异步遗留 A1-A6 + 内核健康 + 技术手册健康）。
  - **P0 阶段 5 增量**：`next()` 内建（c61a6e0）+ `yield from` 生成器委托（本 session 主交付，6c9555c）——
    完整文法管线（AST `IbYieldFromExpr`/语法 match(FROM)/语义 `SEM_YIELD_OUTSIDE_FUNCTION`/类型 GENERATOR/
    VM 委托 handler），顺带根治 `_drive_generator_loop` 生成器体内调用生成器函数的预存缺陷、迭代解析收敛
    `_resolve_iterable`（现居 `core/runtime/shared/iterable.py`，VM 与内建共用单一权威源）。e2e 13 项。
  - **PT-FEAT-5 三项**：诊断码目录（`core/base/diagnostics/catalog.py` 76 码 → 说明/修复 + `DiagnosticFormatter`
    集成 fail-open + `docs/syntax/15_diagnostics.md` + 契约测试 CAT-1~6）；符号表/类型绑定 JSON/dot 导出
    （`core/compiler/diagnostics/exporter.py` + 修 `inspect`/`semantic` 两处 CLI 预存死路径 + `bench` 编译基准）。
  - **P1 PT-FEAT-10 UID 生成统一**：`core/base/uid.py` 单一权威源（11 家族 UID 函数），调用方全部接入、
    格式逐字不变（round-trip 保真）、零内联格式字符串；契约测试 UID-1~4。
  - **P2 审计**：R4 覆盖率核对（12 项，2 处 TRUE_GAP 补测：subscriber 语言层生命周期、generator[T] 泛型身份）；
    R5 聚焦治理（session 改动文档核验）；PT-AUDIT-1 smell 审计全量事实回顾（A/B/C/D 定案，A7/A15 失效确认、
    多数设计内、C6 已解决）。
  - **质量**：三次独立 general 复核（中间/交付门/兜底专项）全部整改——含 `is_generator` 基类化（IbFunction）、
    迭代解析中立归属 `shared/iterable.py`、非可迭代测试修正（`yield from` 无协议对象）、注释卫生（生产代码零任务代号）、
    文档单点真理（catalog↔doc 契约一致）。**兜底专项审计结论**：全部兜底属职责分离型合法 fallback
    （声明面能力查询/显式 None/决策点报错/契约强制完备），无 tricky/兼容妥协。
  - 设计记录 `tasks_docs/_code_yield_from.md`；完整逐项见 `WORKLOG.md` 尾部。
- **2026-08-08（异步地基遗留妥协审计，unsafe-vibe-dev，全量 2043 passed / 1 skipped）**：
  用户追问"异步是否已完整接入内核" → general subagent 全面只读审计 + 逐项代码核实。结论：**主流已完整**
  （协作调度器唯一执行核心/阻塞即挂起/Waitable 统一/trampoline/通知式唤醒/线程=IO/await+yield），
  但内核层仍有"任务内同步重入调度器"遗留旁路（同步 `.call()` 后备在任务内可达）。发现 F1-F3 高严重度 +
  B1 真阻塞 + M1-M4 中严重度；登记 PT-DEBT-12/13/14/15；用户定案新主线（异步遗留根治）+ 认可优先级表。
  详见 WORKLOG 与 `_ASYNC_UNIFY.md`。
- **2026-08-08（阶段 5 yield 惰性生成器，unsafe-vibe-dev，全量 2043 passed / 1 skipped）**：
  含 `yield` 函数自动为惰性生成器（D-08 自标记，async 关键字已取消）。词法 `yield` 关键字 + 语法
  `yield` 表达式（LOWEST 优先级）+ AST `IbYieldExpr`/`is_generator`；语义 `_contains_yield` 自动标记 +
  yield 仅函数体内（`SEM_YIELD_OUTSIDE_FUNCTION`）+ 返回类型 `generator[T]`；类型 `GENERATOR` TypeKind +
  `generator[T]` 泛型全链路；VM `vm_handle_IbYieldExpr` yield `GeneratorYield` 标记 + `_drive_generator_loop`
  单可恢复驱动（与 `_drive_loop_gen` 同构）；运行时 `IbGenerator` 值对象 + `for`/`to_list` 迭代。
  独立分支 exp/yield-generator 实验 → 手动应用 c8b8956。设计权威 `tasks_docs/YIELD_GENERATOR_DESIGN.md`。
  e2e 9 项（基础迭代/状态保留/嵌套循环/条件内 yield/break/生成器 as 值/LLM 组合/auto 赋值/非函数体报错）。
- **2026-08-08（PT-DEBT-11/9/10 根治，unsafe-vibe-dev，全量 2029 passed / 1 skipped）**：
  ① **PT-DEBT-11**（4bf2644）——`UserFunctionCall` 下沉 `core/runtime/shared/user_call.py`（与 Signal/Waitable 同类叶子），handler/线程体不再向上依赖 VMExecutor 内部类；② **PT-DEBT-9**（c75541f）——环境限制异常（RecursionError/MemoryError/SystemError）根因保留：`core/runtime/shared/env_limits.py` 判定 + `diagnostics.handle_environment_limit` 发射 `KDIAG_RUNTIME_ENV_LIMIT` 诊断，VM 五处语义错误包装站点不再掩盖根因（+2 测试）；③ **PT-DEBT-10**——`_drive_generator` 改显式生成器栈（trampoline，与 `_drive_loop_gen` 同构），线程体内深递归不再嵌套 Python 栈；顺带根治线程体模块级函数解析（任务全局作用域链到模块作用域）、线程逻辑栈上限对齐主路径、`_vm_call_user_function`/`IbUserFunction.call`/`IbLLMFunction.call` push 后 finally 无条件 pop 的栈不均衡潜在 bug（+1 测试）。详见 WORKLOG 与 git 历史。
- **2026-08-08（本 session 收尾，unsafe-vibe-dev，全量 2026 passed / 1 skipped）**：
  ① **kernel→runtime 穿透根治**（d11bad0）——事件总线/诊断发射器依赖注入，kernel 层零 runtime 依赖；
  ② **死代码清理**（ffaffc0）——删 `KernelRegistry.clone()`（零调用方，spawn 隔离走独立 engine 路径）；
  ③ **文档-代码对账治理**（fe80595/5f5e26d/a8de1b1/3368c28）——P0 断链/自相矛盾 4 处、P1 过期/红线/事实错误
  ~20 处（执行模型对齐调度器、kernel-native 补 iruntime、意图系统穿透代码块、红线清理等）、P2 缺失/格式/体系
  ~15 处（14_concurrency 补 await/auto-yield、TestHooks、意图语法权威收敛 syntax/09、插件 howto 收敛等）；
  ④ **意图栈扁平化历史兼容彻底移除**（3ce9b7d）+ 补意图上下文 6 槽位 round-trip 测试（+3）；
  ⑤ **登记 PT-FEAT-10/11/12**（UID 统一/序列化器自动化/AST UID 字段，原被删愿景中值得保留的未来任务）。
  详见 WORKLOG 与 git 历史。
- **2026-08-08（文档-代码对账审查）**：5 个并行 general task 全量审查 + 逐项代码核实 + 独立交叉复核。
  结论：8 篇文档需修（重点：arch/04、05 执行模型停在旧叙事）；5 篇与代码一致。修复后残留扫描清零。
- **2026-08-07（PT-FEAT-9 阶段 4 完成）**：内核结构化诊断机制重建——`kernel_diagnostic` helper（单一记录双投影：
  警告不门控 + 事件受 observability 门控，rc best-effort）+ 12 处运行时站点迁移（文案逐字）+ e2e 事件投影测试
  （协议回退双投影/策略忽略 fail-open/门控）+ `docs/architecture/09_observability.md`（观测体系统一文档）。
- **2026-08-07（R 批次完成）**：统一执行地基复核与根治——R4+R3 P3 公开协议 + `IbThread` 满足 Waitable（`await t` 可用）、
  R6 嵌套函数自动只读捕获、R2 调度器通知式唤醒（根治 poll+park）、R1 函数调用 trampoline 化（深递归 Python 深度恒定）。
- **2026-08-06**：**OBSERVABILITY_REFACTOR 主体完成**——Phase 0-2C + 2C-2（idbg 深度收敛：protection_map
  内核化/统一变量视图/snapshot vars bug/LLM 事件流）+ 2D 测试体系全面重建（tests_v2 全域迁移 + 切换 +
  矩阵三段式 + tests_docs 治理）+ Phase 4 收敛全部落地。测试体系现为单一分层模型（kernel/compiler/runtime/
  plugins/contracts/e2e/compliance/sdk/meta/fixtures），meta 机器强制（分层/命名/helper 去重/矩阵对账）。
- **2026-08-05**：闭包序列化 round-trip 修复 + Axiom 家族分裂收敛 + EnumAxiom 双通道收敛 +
  use_intent_context 守卫修复 + R3 异味四 Zone 处置 + import-* 精确成员枚举根治（含 IBC 文件
  跨模块导入三层断裂修复）+ `type()` 内建落地 + 任务控制文档全面重整（任务代号按性质分域）。
- **线程对象模型方向修正（A-F）** + **通信领域设计完善三阶段** + **收尾 L1-L8 + T2** +
  **代码复核审查（code-review / 健康诊断 / 异味扫描）** + **类型强化** 全部落地（详见 git 历史）。
- **测试基线**：以实跑为准，不冻结数字（当前 **2137 passed / 1 skipped**）。
- **分支**：unsafe-vibe-dev（唯一活动分支；main 永不触碰；实验分支 exp/obs-2a/2b/2c/2c2/2d、exp/exec-ra/rb/rc/rd、
  exp/yield-generator、exp/async-m1m2、exp/async-unify-a、exp/run-batch-cps、exp/refactor-nesting、exp/a5-cps-construct
  保留供追溯——其中 exp/a5-cps-construct 因零风险已直接合并 unsafe-vibe-dev，其余未合并/部分已手动应用）。

### 2.3 交接检查单

- [ ] 读 NEXT_STEPS（当前最紧要）+ PENDING_TASKS §〇（长期，单一权威源）
- [ ] 读本文件 §一 固定化内容（goal 模板 / 流程 / 原则）
- [ ] 读 §二 动态状态接续工作（含 2026-08-11 session：PT-DEBT-17 run_batch 根治 + PT-AUDIT-2 _collect_instance 重构 + A5 类构造 CPS 根治 + A6 维持现状 + 文档健康检查 P0/P1 部分 + 真实 LLM e2e 规划 + main 合并规划 + CI/CD 退役 + 分支政策"零风险直接合并"细则）
- [ ] 确认测试基线：`~/miniconda3/envs/ibci/bin/python -m pytest tests/`（当前 2137 passed / 1 skipped）
- [ ] 工作全程本地 commit、禁 push、工作日志记录
