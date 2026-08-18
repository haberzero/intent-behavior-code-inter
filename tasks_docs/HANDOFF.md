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
| 破坏性重构授权 / 分支政策 / 禁 push | 见 AGENTS.md（权威源）。**分支合并细则（2026-08-18 更新，取消 cherry-pick）**：确认低风险/边界清晰（全量 pytest 零回归 + 复核放行）可直接 **merge** unsafe-vibe-dev；merge 无误即删无用分支（除 main 与 unsafe-vibe-dev 外不长期保留分支）；main 不更新不触碰；判定以"是否确认零风险"为准 |

### 1.2.1 goal 配置习惯（每个 session 新配置 goal 时自动采用，用户定案）

> 创建 goal（`create_goal` / `set_goal`）时按此默认参数，除非用户在本 session 显式覆盖：
>
> | 参数 | 值 | 说明 |
> |------|----|------|
> | `max_duration_seconds` | **14400（4 小时）** | 最晚结束时间 = 当前时刻 + 4h |
> | `max_auto_turns` | **10** | 允许 goal 自动续跑次数 |
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
3) PT-FEAT-5 错误用户友好化 / PT-FEAT-2 Enum 非 str 成员；
4) 测试体系重构（PT-TEST-1）。每条支线仍须全量 pytest 零回归、commit+留痕（仅本地）。

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

> **接手起点**：读本节 + `tasks_docs/NEXT_STEPS.md`（当前最紧要 + ⛔ 工作模式定论）+
> `tasks_docs/PENDING_TASKS.md`（远期规划）+ `tasks_docs/GOVERNANCE.md`（任务控制治理）
> + `git log --oneline -30`（近期提交与工作动线）。

- **🔴 当前主线**：**远期原生宿主绑定（F0-F5）已全部完成**（路线图
  `tasks_docs/ROADMAP_NATIVE_BINDING.md`）。宿主导入一等语法 `import python "pkg" as lib:
  bind ...` + 宿主类型绑定 + 插件体系重构 + Provider 自定义经宿主绑定统一均已落地：
  - **F0-F2**：宿主导入/宿主类型一等绑定（EXTERNAL_MODULE CLASS + per-instance vtable）。
  - **F3**：废弃 Python `_spec.py` 磁盘发现/加载通道，用户侧扩展唯一边 = 宿主绑定
    `bind`；内置 11 模块（内核原生 5 + 工具 5 + file）TypeDef 字面量集中
    `core/runtime/bootstrap/builtin_modules.py` 构造期一次注册；插件搜索路径配置面/
    ibci_sdk/__ibcext_axiom__ 死协议等全铲除；Engine 签名简化 `IBCIEngine(root_dir=...)`。
  - **F4**：Provider 自定义经宿主绑定统一——用户写实现 `LLMProvider` 契约的 Python 类，
    经 `import python "my_provider" as lib: bind provider` + `ai.set_provider(lib.provider)`
    注册为激活 `llm_provider`（HIGH 优先级覆盖内置默认 RecommendedProvider）；R 期"改
    provider_impl.py"临时形态已拆除（provider_impl.py 降为内置默认实现）。
  - **F5**：架构统一/文档收敛——档 A 缓存/内核自举/档 B 真 JIT/隔离/反射评估为**远期
    pending 规划**（当前"引擎单次执行"模型下收益有限）；文档与代码一致。
- **当前代码状态**：
  - 分支 `unsafe-vibe-dev`，本地领先 `origin`（**未 push**；禁 push 硬原则）。
  - 用户侧扩展唯一边 = 宿主绑定 `bind`（`docs/howto/extend_with_host_binding.md`）；
    自定义 LLM provider = 宿主绑定 + `ai.set_provider`（`docs/howto/modify_llm_provider.md`）。
  - LLM 供应商无关中间层 `core/base/llm_protocol/`；MOCK 哨兵在该层 `llm_call.py`。
- **⏳ 下一步（新主线）**：**五大地基完整改造**（llm 可调用类 + LLM 体系彻底协议化（总统一性）
  + 函数式 / 类型类 / 类型理论 / 高阶函数 / 协议化）——用户 2026-08-18 定方向 + 6 项关键决策
  已拍板：① 内置类型协议方法表选 B（per-IbClass 协议方法表，系统化重构）；② 内置类型行为改写
  = **临时覆层机制**（默认不生效、flag 启用、作用域化，最关键新设计约束）；③ snapshot 意图冻结
  按文档补齐；④ `llm ... llmend` 语法**彻底删除**（非语法糖）；⑤ retry 帧机制保留 + 语法/策略
  高阶化；⑥ P1-P6 本主线、P7/P8 远期。
  **调研/可行性/规划/决策已全部产出**（临时文档 `tasks_docs/_llm_callable_redesign.md` +
  `tasks_docs/_five_foundation_redesign.md`：交接清单 6 项补充调研全部完成 + 五大地基现状评估 +
  总路线 P1-P9 + 决策 §五 + P1 开工输入 §六）；**下一 session 开工 = P1 设计定稿**，详见
  `NEXT_STEPS.md` 下一步候选 #1。次后按需推进支线（PT-DEBT / VISION-3 / 文档）。

### 2.2 交接检查单（当前有效）

- [x] **读 `tasks_docs/ROADMAP_NATIVE_BINDING.md`（本主干任务总路线图与事实基石 — 首位必读）**
- [x] 读 `NEXT_STEPS.md`（当前状态 + ⛔ 工作模式定论 + 下一步候选）
- [x] 读 `PENDING_TASKS.md`（远期任务正式清单：FEAT/DEBT/AUDIT/DOC/TEST/DECIDE/SEALED/愿景）
- [x] 读 `GOVERNANCE.md`（任务控制治理章程：文档职责/书写模板/生命周期/红线）
- [x] 读 `WORKLOG.md`（关键裁定与长期约束）
- [x] 试用体系：`trials/_toolkit/`（run_batch/run_one/CLASSIFICATION/LLM_SERVICE）+ `trials/INDEX.md`
- [x] 测试基线：`~/miniconda3/envs/ibci/bin/python -m pytest tests/`（以实跑为准，不冻结数字）
- [x] 全程本地 commit、禁 push（除非用户显式授权）

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
