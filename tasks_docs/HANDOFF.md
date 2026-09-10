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
| 总体规划灵活微调（2026-09-10） | 基准规划（如 `_world_model_db_design.md` §6 P0-P9 执行清单）可据项目进度与具体实验情况（实证证据/阻塞项/新发现/成本变化）**自行灵活微调**——批次重排/合并/细分/补充验证/推迟或提前均允许；不改变主线方向、不违反硬约束（工作模式定论/禁 push/不碰 main/验证纪律）时无需用户拍板；微调依据须详尽记录 WORKLOG（调了什么+为何+变化前后） |

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
> **默认参数（用户定案习惯）**：`max_goal_rounds` = **100**（轮次预算；2026-09-10 用户裁定
> 由 7 上调——长期主线无人值守需要充足轮次）；objective 正文按
> 下方 §1.3 模板套用（无人值守 + 主线 + 交付纪律 + 工作流 + 支线 + 停止条件 + 非目标），
> 并含 §1.2"总体规划灵活微调"授权段。
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

### 2.0 🔴 本 session 交接（2026-09-10 世界模型数据库主线 **P1 ✅ → P2 接手**）

> **接手起点**（下一位智能体）：读 **`tasks_docs/_world_model_db_design.md`**（本主线设计 +
> 调研结论 + 决策点/风险 + P0-P9 执行清单，**最核心**）+ `tasks_docs/_ra_quote_eval_design.md`
> （P1 quote/eval 机制裁定 + **§7 边界裁定 = P2 输入**：eval 环境参数/归一化对比归 P2 事实层
> UID/SR-4 承载候选——P2 开工后删除本文）+ `tasks_docs/NEXT_STEPS.md`（当前主线 + 工作节奏 +
> ⛔ 工作模式定论）+ `tasks_docs/_rust_kernel_survey.md`（Rust 内核替换调研 + 全量 pytest 临时
> 策略）+ `tasks_docs/WORKLOG.md`（P1 裁定 + 环境重建 + 本交接）+ `git log --oneline -30`。
> **当前主线 = IBCI 原生数据库（世界模型知识图谱）+ 自指性主线收束 + 测试进程内化**；**当前批次 =
> P2 R-B 世界模型 KB（演化 knowledge）**。需求源 = 试用方 v2
> （`/home/dsh/proj/ibci-trial/docs/REQ_IBCI_WORLD_MODEL_INTEGRATION.md`，D-ISO 只读）。
> 本 session goal（自主执行，`max_goal_rounds=7`）**active**；下一 session 据 §2.2 检查单
> **新建 goal**（resume 仅对同 session 内被解除武装的 active goal 有效）。本节 = 当前动态状态
> 唯一节；历史 = §2.1（git / WORKLOG 承载）。
- **工程事实（本 session 收束点）**：
  - 分支 = `unsafe-vibe-dev`（日常开发主线）+ `main`（永不触碰）。**领先 origin 12 提交未 push**
    （P1 设计/实现 + 上一 session 的 docs/handoff/harness 系列）——**不 push**（用户 2026-09-10
    本 session 明确"不 push，直接开工"；push 待用户显式授权，硬原则）。
  - **环境已验证**：venv Python 3.12.3 + editable 安装 ✅；probe ✅（SiliconFlow 35B 非思考基线）；
    maturin 1.15.0 + Rust 1.98.1 + 3.12 dev headers ✅（P9 无环境阻塞）。
  - 测试基线 = `.venv/bin/python -m pytest tests/`（**addopts 已含 `-q`，勿显式再加**——双 `-q`
    隐藏计数行）；**smoke 子集（tests/contracts+tests/compiler）832 passed / ~13s 进程内无子进程**
    （高频验证用）；末次全量 **4038/1**（~115s，P1 公理层放行门，以实跑为准）。

- **🔴 主线延续点（下一位智能体 = P2 R-B 世界模型 KB）**：
  - **P1 R-A quote/eval 已落地（本 session）**：`meta.quote(source) -> quoted` / `meta.eval(expr) ->
    any` + `quoted` 一等不可变值类型（单字段 source；无运算符/无 call 面）；quote 单一验证门
    （子引擎 compile-only 包装 `__qeval__ = <source>`：自包含性由构造成立）+ eval 值通道
    （子进程 spawn + JSON 值交换，返回值非 stdout；结果槽缺失 fail-fast）。裁定全记录 =
    `_ra_quote_eval_design.md` + WORKLOG（P1 R-A 条目）。
  - **设计裁定（用户已授权推进，见 `_world_model_db_design.md` 顶部）**：① 演化现有 `knowledge` 为
    一等世界模型知识图谱（单点真理，不另立平行类型）；② 向量面 = 纯 IBCI 值 + `ImmutableArtifact`
    工件（暴力 cosine 起步，格式预留 ANN/FAISS 派生加速）；③ 磁盘格式 = IBCI 内容寻址 artifact
    （JSON 降为传输格式，IBCI 代码降为派生视图 `to_ibci()`）。
  - **P0-P9 执行清单**（详见 `_world_model_db_design.md` §6）：P0 设计定稿 ✅ → **P1 R-A quote/eval
    ✅** → **P2 R-B 世界模型 KB（演化 knowledge，当前批次）** → P3 磁盘格式 → P4 R-C 确定性模式
    → P5 R-D 工件加载 → P6 向量面 → P7 R-F 投影派生视图 → P8 测试进程内化 → P9 Rust 内核
    （设计 + 构建；pin `CARGO_HOME` 到 workspace + 网络，免审批；harness 语料已含 quote/eval
    判别面）。每步：受影响子集+smoke 验证零回归 + 本地 commit + 同步 NEXT_STEPS/WORKLOG。
  - **工作节奏（三轴收束进自指弧线，不新设竞争主线）**：R-A 并入 selfref 弧线 / R-B 演化 knowledge /
    R-C 横切；Rust 内核 = 独立隔离分支 `rust-kernel`（**设计 + 构建均可**：pin `CARGO_HOME`+
    `CARGO_TARGET_DIR` 到 workspace + 允许网络 → 免审批），harness 语料 = 世界模型里程碑；
    e2e 进程内化 = 早期使能项（降全量门成本，服务高频进程内验证）。
  - **🔴 硬约束（下一 session）**：全程本地 commit；**禁 push**（须用户单独授权）；**常规网络操作
    允许**（依赖/下载不触发审批）；**Rust 构建可行**（pin `CARGO_HOME`+`CARGO_TARGET_DIR` 到
    workspace → 免审批；默认 `~/.cargo`/`/opt/rust/cargo` 不可写，勿用）；**仍须避免**：写 workspace
    外文件、无必要的沙箱提权。**若用户不在场且需 push** → 延后记录 WORKLOG 待办、不阻塞。

- **⚠️ 关键调研结论（防下一 session 重查，详见 `_world_model_db_design.md` §2）**：
  - IBCI **已有全部子件**：`knowledge`（文档明写=D 纸带，append-only amend/history+引擎单调序号）/
    `vector`（不可变+cosine+`__to_prompt__`）/`memory`/`behavior`/`ai.recall`/`ImmutableArtifact`
    （哈希钉扎只读可加载值）——**缺的是"融合成一致数据层"**，非从零造库。
  - 现状 stopgap（trial `schema_to_ibci.py`）**lossy**（丢 34 条 only_in_axioms / 关系字符串化 /
    `return "unknown"` 魔法默认 / 无查询 / 全量重编译）→ 论证"不能永远用 IBCI 代码承载数据"。
  - v30 真实数据：`axioms=[{world,s,r,o}]`(451，无 id/source/status=目标态)；`word.relations`×`axioms`
    双写（only_in_axioms=34）；99 词/51 关系(v30 裸名 vs governed_vocab 59 带语义)/21 世界。
  - `knowledge` 消费面轻（多为类型系统/序列化基础设施）→ 演化低风险（仍需审计消费方，§7 决策点 #1）。

- **硬约束（延续）**：全程本地 commit、**禁 push**（硬原则，须显式授权）；不触碰 `main`；9 项 VM
  设计不变量（04_vm_interpreter §11）+ 工作模式定论九条（禁 compat shim/胶水/tricky/过程式硬编码分发；
  质量优先于速度；原则优先于行为维持；可推翻 IBCI 自身设计缺陷）凌驾一切；改动公理层或语义错误集须
  全量 pytest 评估破坏面；破坏性重构默认已授权（详尽记录决策依据 + 变化前后）；无法确认边界的破坏性
  重构 100% 授权独立分支实验（永不触碰 main）。
- **落账纪律**：WORKLOG 条目 splice 至 `## 附、书写模式` 锚点前；commit 消息 = 描述性中文；每项完成
  同步 NEXT_STEPS / HANDOFF；测试数字以实跑为准（不冻结）；设计阶段文档先写 `tasks_docs/_<task>.md`
  （落地后删除，最终内容按治理收敛入 `docs/`；公理/语义重大决策写 `docs/architecture/` 对应章节）。
- **环境注记（下一 session Rust 路径）**：maturin 1.15.0 已装 `.venv`；Rust 1.98.1；**agent bash 对
  默认 cargo 写位置（`~/.cargo`、`CARGO_HOME=/opt/rust/cargo`）不可写 → 构建须 pin `CARGO_HOME`+
  `CARGO_TARGET_DIR` 到 workspace 内**（`$PWD/.cargo_local`+`$PWD/target`）；常规网络允许（依赖下载
  免审批）。**Rust↔Python 协同已端到端验证**：pyo3 crate（extension-module）`cargo build --release`
  → `.so` → Python import + 调用 Rust 函数 OK（pyo3 3.12 用 0.22/0.23；工具链全通）。
  **✅ Python 3.12 dev headers 已安装（用户 `apt-get install python3.12-dev`）+ 端到端已验证**：
  pyo3 0.23 crate `cargo build --release`（pin workspace + `PYO3_PYTHON`=venv）→ `.so` → venv
  （3.12.3）import + 调用 Rust 函数 OK（`PROJECT_RUST_PY_312_OK`）。**项目 Rust 构建路径全通，
  P9 无环境阻塞。**（备注：agent 被 `NoNewPrivs=1` 锁死无法 sudo；`/etc/sudoers.d/dsh` 规则存在，
  人工 dsh shell 可 sudo——供未来重装参考。）
- **差分等价 harness 已含 quote/eval 语料（P9 phase ① 扩展，本 session）**：`scripts/differential_harness.py`
  （Python 内核参考基线 + 确定性验证 + `run_kernel("rust")` drop-in + `--diff` 对拍；语料 8 例含
  quote/eval 数据/命令二元判别面）+ 常设门 `tests/contracts/test_differential_harness.py`（smoke 子集）。
  后续并入 R-B 里程碑语料（KB 事实集）+ 实现 `run_kernel("rust")` 后即成 py↔rust 差分门（Rust 安全网）。
- **全量 pytest 基线（本 session P1 放行门实跑）**：**4038 passed / 1 skipped / 115.28s / rc=0**
  （= 前基线 3998 + P1 新增 30 + tests/meta 治理参数化增量 10[docs 同步所致]；供下一 session
  参照，不冻结）。

### 2.1 历史状态（git / WORKLOG 承载，本文件不再登记）

> round3 试用需求整合 / meta 层 MVP / VISION-6 P1-P6 的收束历史不在本节登记（章程红线：
> 不保留已完成历史叙述）。过程记录 = `tasks_docs/WORKLOG.md` + `git log`；长期项状态单点
> 真理 = `tasks_docs/PENDING_TASKS.md`；试用需求 intake 模式参照 = WORKLOG round3 条目。

### 2.2 交接检查单（当前有效）

- [ ] 读 **`_world_model_db_design.md`**（本主线设计 + 调研结论 + 决策点/风险 + P0-P9 执行清单；
  **首读**）+ **`_ra_quote_eval_design.md` §7**（P1 边界裁定 = P2 输入：eval 环境参数/归一化对比
  归 P2 事实层 UID/SR-4 承载候选；P2 开工后删除该文档）
- [ ] 读 `NEXT_STEPS.md`（当前主线 = 世界模型 DB + **当前批次 P2 R-B** + 工作节奏 + ⛔ 工作模式定论）
- [ ] 读 `_rust_kernel_survey.md`（Rust 内核替换调研 + 全量 pytest 临时策略：单任务=受影响子集+smoke）
- [ ] 读 `WORKLOG.md`（P1 R-A 裁定 + 世界模型 DB 设计裁定 + 环境重建 + 本交接）
- [ ] **设 goal**（据 §2.0 主线 + `_world_model_db_design.md` §6 P2-P9；objective 按 §1.3 模板套用，
  含约束：**禁 push**（须用户单独授权）；**常规网络允许**（不触发审批）；**Rust 构建可行**
  （pin `CARGO_HOME`+`CARGO_TARGET_DIR` 到 workspace，免审批）；**避免**写 workspace 外文件 /
  无必要沙箱提权；用户不在场且需 push 时延后记录不阻塞）；跨 session 需**新建** goal（旧 goal
  不跨 session 续跑）
- [ ] **环境自检**：`.venv/bin/python -m pytest tests/contracts tests/compiler`（smoke，~13s 进程内；
  **勿显式加 `-q`**——addopts 已含，双 `-q` 隐藏计数行）+ `.venv/bin/python trials/_toolkit/probe.py`
  （LLM 端点鉴权+模型可用）
- [ ] 全程本地 commit；**禁 push**（须用户显式授权）；常规网络允许；Rust 构建 pin `CARGO_HOME` 到
  workspace（见 §2.0 环境注记 / 硬约束）

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
