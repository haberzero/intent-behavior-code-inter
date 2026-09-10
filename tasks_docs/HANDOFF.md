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

### 2.0 🔴 本 session 交接（2026-09-10 世界模型数据库主线 **P4 ✅ → P5 接手**）

> **接手起点**（下一位智能体）：读 **`tasks_docs/_world_model_db_design.md`**（本主线设计 +
> 调研结论 + 决策点/风险 + P0-P9 执行清单，**最核心**；artifact 共享契约见
> `docs/syntax/11_modules.md` §11.12 + 试用方配合项 ② 输入）+
> `tasks_docs/NEXT_STEPS.md`（当前主线 + 工作节奏 + ⛔ 工作模式定论）+
> `tasks_docs/_rust_kernel_survey.md`（Rust 内核替换调研 + 全量 pytest 临时策略）+
> `tasks_docs/WORKLOG.md`（P1/P2 裁定 + 环境重建 + 本交接）+ `git log --oneline -30`。
> **当前主线 = IBCI 原生数据库（世界模型知识图谱）+ 自指性主线收束 + 测试进程内化**；**当前批次 =
> P3 磁盘格式（IBCI 内容寻址 artifact + load_kb）**。需求源 = 试用方 v2
> （`/home/dsh/proj/ibci-trial/docs/REQ_IBCI_WORLD_MODEL_INTEGRATION.md`，D-ISO 只读）。
> 本 session goal（自主执行，`max_goal_rounds=100` + 总体规划灵活微调授权）**active**；
> 下一 session 据 §2.2 检查单**新建 goal**（resume 仅对同 session 内被解除武装的 active
> goal 有效）。本节 = 当前动态状态唯一节；历史 = §2.1（git / WORKLOG 承载）。
- **工程事实（本 session 收束点）**：
  - 分支 = `unsafe-vibe-dev`（日常开发主线）+ `main`（永不触碰）。**已 push 至 origin
    `63973071`**（本 session 收束点，2026-09-10 用户两次显式授权 push——P5 阶段末 1 次
    [origin f5a42db7] + P6 收束后 1 次[origin 63973071，含 P5 doc-sync + P6 F1/F2 向量面]——
    每次 push 前全量 pytest 零回归门通过[4191/1、4231/1]）。默认仍**不 push**（硬原则：push
    须用户单独授权；下次 push 待新的显式授权）。
  - **环境已验证**：venv Python 3.12.3 + editable 安装 ✅；probe ✅（SiliconFlow 35B 非思考基线）；
    maturin 1.15.0 + Rust 1.98.1 + 3.12 dev headers ✅（P9 无环境阻塞）。
  - 测试基线 = `.venv/bin/python -m pytest tests/`（**addopts 已含 `-q`，勿显式再加**——双 `-q`
    隐藏计数行）；**smoke 子集（tests/contracts+tests/compiler）832 passed / ~13s 进程内无子进程**
    （高频验证用）；末次全量 **4191/1**（~126s，P5 公理层放行门，以实跑为准）。

- **🔴 主线延续点（下一位智能体 = P9 Rust 内核 阶段② Rust 前端，隔离分支续）**：
  - **P1 R-A quote/eval 已落地（本 session）**：`meta.quote`/`meta.eval` + `quoted` 一等值类型
    （单一验证门 + 值通道）。裁定 = WORKLOG（P1 R-A 条目）。
  - **P2 R-B 世界模型 KB 已落地（本 session）**：`knowledge` 就地演化为三元组知识图谱——
    facts 事实日志（KB 单一权威源，append-only + fact_id = str(seq) 确定性）+ vocab 治理词表
    （words/relations/worlds allowlist；transitive/multi_valued 元数据）+ 8 派生索引（日志权威、
    索引视图）+ 27 方法面（词表 9/事实 8/查找 7/对比展开 3；内建治理门零 LLM）+ 墓碑/版本化
    （retract/amend_fact reason 强制 + 全史可溯）。**双写根治**：词关系 = by_subject 派生 /
    展开态不存 / 索引不存。新发现语言边界：容器 `==` 恒等语义（KNOWN_LIMITS §10.5；字节对比
    经 `json.stringify` 路径）。裁定全记录 = WORKLOG（P2 R-B 条目）。
  - **P3 磁盘格式已落地（本 session）**：新 kernel-native 模块 `world_model`——
    `load_kb(path) -> knowledge`（三级验证门[结构/版本/完整性 hash]后水化为**活 KB 值**）/
    `save_kb(kb, path) -> str`（KB 面序列化落盘，返回 content_hash 钉扎基准）。artifact
    共享契约 = 单 JSON `{schema_version: 1, content_hash, facts[seq 序], vocab, seq}`；
    **JSON 降传输格式、身份 = canonical**（sort_keys + 紧凑分隔 sha256 全摘要；同内容不同
    排版 = 同 hash）。**试用方 B1 验收达成**（R-B 验收面 1/4）：load 后活查询 + 增量
    100 事实无需重编译（e2e 实证）；entries 面不入 artifact（持久化通道 = save_state
    全状态面，两通道各辖其面）。裁定全记录 = WORKLOG（P3 条目）。
  - **P4 R-C 确定性执行模式已落地（本 session）**：CLI `run --deterministic` + 引擎级
    `deterministic_guard` 参数（同 budget 装配路径）——LLM 调用汇点零 LLM 不变量 guard
    （provider 调用前结构性拦截，`RUN_DETERMINISTIC_LLM_CALL`，与 budget 分码）+ result-json
    审计凭证 `{enforced, llm_calls: 0}`（机读"LLM 调用次数=0"）。与 `--replay` 互斥。
    **M1 验收达成**（试用方里程碑 1：load_kb → 确定性模式下 quote/eval 一条事实全程零 LLM
    逐字节可复现——替代静态投影的最小活集成）。附带：budget location 既有缺陷修复（str 占位
    击穿 CLI 渲染面）+ KNOWN_LIMITS §二十七（行为值 future 惰性解析——未引用 LLM 值错误
    静默吞没边界）。裁定全记录 = WORKLOG（P4 条目）。
  - **设计裁定（用户已授权推进，见 `_world_model_db_design.md` 顶部）**：② 向量面 = 纯 IBCI 值 +
    `ImmutableArtifact` 工件（暴力 cosine 起步，格式预留 ANN/FAISS 派生加速）；③ 磁盘格式 =
    IBCI 内容寻址 artifact（**P3 已落**）；IBCI 代码降派生视图 `to_ibci()`（**P7 落**）。
  - **P5 R-D 工件加载已落地（本 session）**：新值类型 `narrow_model`（不可变冻结
    KG 嵌入工件，同 quoted/vector 纪律）+ `world_model.bind_artifact(path)`/
    `save_artifact(model,path)`（窄模型工件面，三级验证门同 load_kb 纪律）——
    推理时 TransE 纯算术推理 `model.score(s,r,o)`（`‖e_s+r_r−e_o‖`，越小越优）/
    `model.topk(s,r,k)`（全候选距离升序前 k，确定性 tie-break）；纯推理零训练
    （权重加载即冻结，无 optimizer/反向传播）。**R-D 验收达成**（bind 后
    score/topk 可调用且确定性同输入同输出，全程无训练调用）。裁定全记录 =
    WORKLOG（P5 条目）。
  - **P6 向量面已落地（本 session）**：`knowledge` 值类型加**词嵌入面**（单点
    真理 = KB 值，不另立平行向量索引类型）——`set_embedding(word, vec)` /
    `embedding(word)` / `has_embedding` / `embedding_dim()` / `embed_search(query, k)`
    （全嵌入词暴力 cosine 取前 k，**内容信号非判定**——D1 判定走图平面；确定性
    tie-break = (−score, word) 升序）；KB artifact **v2 加法演进**（加 `vector`
    节持久化嵌入，canonical/hash 版本感知，**v1 向后兼容**）。机制分层非重复：
    `ai.embed`/`ai.retrieve` = 低层原语保留，`kb.embed_search` = KB 自身词表高层
    内容信号检索。裁定全记录 = WORKLOG（P6 条目）。
  - **P7 R-F 投影派生视图已落地（本 session）**：`knowledge.to_ibci()` = KB
    **当前态**的确定性 IBCI 代码派生视图（**非存储层**——单一权威源 = 活 KB /
    artifact；代码投影从日志派生绝不独立存储）——全词汇/全事实（active+
    retracted）无 lossy + 确定性逐字节一致（同 KB 同投影）+ 对拍活 KB 查询
    结果一致；替代 lossy stopgap `schema_to_ibci.py`（无魔法默认 + 按需派生免
    全量重编译）。当前态非全史（amend 原始 o 不可恢复——不回放事件史）。裁定
    全记录 = WORKLOG（P7 条目）。
  - **P8 测试进程内化已落地（本 session）**：消端到端流水线可复现性的 4x
    冗余（dual-channel）——P5/P6/P7 e2e 两 run → 单 run CLI 凭证，确定性归并
    进 process（各 feature 同输入同输出）+ P4 M1 代表性流水线可复现性（单点）。
    **诚实结论**：e2e 子进程开销大部分不可化约（纯 CLI 机制测试 + ihost 子运行
    测试 = subprocess by design）；P8 安全内化空间有限（~3s，全量门噪声内），
    主价值 = 消 dual-channel 冗余（质量）。裁定全记录 = WORKLOG（P8 条目）。
  - **P9 Rust 内核 阶段① 地基已落地（本 session，隔离分支 `rust-kernel` → 已
    merge unsafe-vibe-dev 删分支）**：构建链（crate `ibci-ext/`[pyo3 0.23
    extension-module cdylib] + `scripts/build_rust_ext.sh`[pin CARGO_HOME=
    .cargo_local + CARGO_TARGET_DIR=target workspace 内 + PYO3_PYTHON=venv + 常规
    网络免审批]）+ 差分等价 harness（`tests/diff_harness/` **常设安全网**——双
    内核同输入→同输出逐字节等价；14 条语料种子面[算术/控制流/函数显式类型/容器/
    字符串/KB 世界模型] + Python 参考内核确定性验证 + Rust 未就绪不冒充）。
    **双内核协议**（核心裁定）：Python 内核 = 一等实验内核（默认保留不删）+ Rust
    内核 = 生产快路径（显式 opt-in **无静默回退** fail-fast）；两内核共享同一 AST
    契约 + contracts 语义红线；Rust 扩展 opt-in（默认 Python 零依赖可装，.so 可再
    生 gitignore）。**零风险加法式地基**（不动 Python 执行路径）。
  - **P9 阶段② 首增量 Rust lexer 已落地（本 session，隔离分支 `rust-kernel` →
    已 merge unsafe-vibe-dev 删分支）**：Rust lexer 移植（`ibci-ext/src/lexer.rs`
    对齐 Python `core/compiler/lexer` core normal 模式——StrStream + CoreScanner
    + IndentProcessor + 行处理）+ `ibci_ext.lex` 暴露 token 流 + 差分 harness 加
    **token 级差分面**（Rust token 流 == Python token 流，type/value/line/column
    逐条）——**14/14 语料 token 级逐条等价**（修 3 类移植 bug：运算符先消费首
    字符 / INDENT column 消费前记录 / EOF dedent column=0）。行为块(@~...~)/意图/
    三引号串/raw 串/变量引用 = 后续增量（渐进移植 + 差分门，非 subset 双通道）。
    **零风险加法式**（opt-in，不动 Python 执行路径）。
  - **P9 阶段② 第二增量 Rust parser 已落地（本 session，隔离分支 `rust-kernel`
    → 已 merge unsafe-vibe-dev 删分支）**：Rust parser 移植（`ibci-ext/src/
    parser.rs` 最小语句/表达式面——Assign / ExprStmt / Constant[int/str/bool/
    None] / Name / BinOp[+] / Call[func(args)]）+ **AST 规范 dumper**
    （`tests/diff_harness/ast_dump.py` structure 模式——IBC 语法树 → 规范字符串
    形态，AST 级差分参考工具）+ `ibci_ext.parse_struct` 暴露 + 差分 harness 加
    **AST 级差分面**（Rust AST structure == Python AST structure 逐字节）——
    **6/6 片段 AST 级逐字节等价**。渐进移植 + 差分门（非 subset 双通道，终点 =
    全量 Rust 前端）。**零风险加法式**（opt-in，不动 Python 执行路径）。
  - **P9 阶段② 第三增量 Rust parser 完整面 已落地（本 session，隔离分支
    `rust-kernel` → 已 merge unsafe-vibe-dev 删分支）**：Rust parser 从最小面扩至
    完整语料面（`ibci-ext/src/parser.rs` 完整重写）——语句面[Assign[Name/
    Subscript target，回退式前瞻] / ExprStmt / If[elif 链 = orelse 嵌套] / For
    [target ctx='Store'] / FunctionDef[typed args + returns] / Return / Break /
    Continue / Pass + INDENT/DEDENT body 解析] + 表达式面[BinOp[+ - * / // % **
    递归下降优先级] / UnaryOp / Compare[链] / List / Dict / Attribute / Subscript
    / Call]——**14/14 语料 AST 级逐字节等价**。**零风险加法式**（opt-in，不动
    Python 执行路径）。
  - **P9 阶段② 第四增量 位置跟踪对齐 已落地（本 session，隔离分支 `rust-kernel`
    → 已 merge unsafe-vibe-dev 删分支）**：Rust parser 每节点位置（lineno/
    col_offset/end_lineno/end_col_offset）对齐 Python `_loc`（start token 的
    line/col + end token 的 end_line/end_col）+ **lexer 合成 token[NEWLINE/EOF/
    INDENT/DEDENT] end 位置修复 = (0,0)**（此前 token 级差分只比 type/value/line/
    column，漏过 end 位置 bug）+ AST dumper 含位置 + 差分 harness 升级（AST 完整
    形态含位置比对 + token 完整位置比对）——**14/14 语料 AST 完整形态[含位置]
    逐字节等价 + token 完整位置 14/14 等价**。节点特定规则：IbAssign end=target.
    end / IbReturn end=RETURN.end / IbUnaryOp end=op.end / IbIf·For·FunctionDef
    end=DEDENT(0,0) / IbModule end=None。**零风险加法式**（opt-in，不动 Python 执行
    路径）。
  - **P9 阶段② 第五增量 剩余语句/表达式面 已落地（本 session，隔离分支
    `rust-kernel` → 已 merge unsafe-vibe-dev 删分支）**：Rust parser 扩至剩余面
    ——While / Try[except/else/finally，IbExceptHandler] / ClassDef[fields=Assign
    / methods=FunctionDef] / IfExp 三元[body if test else orelse，最低优先级层
    parse_ternary→parse_compare，右结合] / Lambda[IbLambdaExpr，typed params +
    返回类型]——**7/7 剩余面 AST 完整形态[含位置]逐字节等价 + 语料面 14/14 无回
    归**。**零风险加法式**（opt-in，不动 Python 执行路径）。
  - **战略微调（2026-09-10，据总体规划灵活微调授权）**：语义层（7427 行 + 完整
    环境依赖[registry/source manager]）Rust 移植**推迟 = 全量 Rust 化后续**；
    **直接推进阶段③ 执行核心（主战场）**——执行核心消费 Python 前端产出的序列化
    artifact（FlatSerializer JSON，含语义层输出[符号表/类型/侧表]），Rust 侧反序
    列化 + 执行（cProfile 实证性能瓶颈，价值最高）。渐进 Rust 化：执行核心（Rust）
    + 前端（Python）先行，前端 Rust 化（语义层）后续。
  - **P9 阶段③ 首增量 执行核心反序列化器 已落地（本 session，隔离分支
    `rust-kernel` → 已 merge unsafe-vibe-dev 删分支）**：Rust artifact 反序列化器
    （`ibci-ext/src/deserializer.rs`）——序列化 CompilationArtifact（FlatSerializer
    JSON，nodes/symbols/scopes/types 池 + UID 引用）→ Rust AST（复用 parser 的
    Expr/Stmt 类型 + dumper）。本增量 = nodes 池[语料面 19 种节点] → Rust AST。
    + serde_json 依赖 + 差分 harness 加反序列化器差分面——**14/14 语料反序列化
    AST 逐字节等价**（artifact → Rust AST == Python AST）。执行核心输入契约就位。
    **零风险加法式**（opt-in，不动 Python 执行路径）。
  - **P9 阶段③ 第二增量 执行核心对象模型 + 解释器 已落地（本 session，隔离分支
    `rust-kernel` → 已 merge unsafe-vibe-dev 删分支）**：Rust 执行核心（主战场）
    ——对象模型（IbValue：Int/Float/Str/Bool/None/List/Dict，List/Dict 经
    Rc<RefCell> 共享可变）+ tree-walking 解释器（反序列化 AST → 执行 → 数据面）
    + IBC 数值语义（`/`=`//`=floor 除，int+float=float）+ 环境/作用域链[递归] +
    `ibci_ext.run_artifact` 暴露 + 差分 harness 加数据面差分面——**11/11 非 KB
    语料数据面逐条等价**（Rust 执行 == Python 执行）。**主战场突破**。**零风险
    加法式**（opt-in，不动 Python 执行路径）。
  - **P9 阶段③ 第三增量 执行核心性能基准 已落地（本 session，加法式零风险直接
    提交 unsafe-vibe-dev）**：常设基准脚本 `scripts/bench_rust_kernel.py`（Python
    run_ibci vs Rust run_artifact，微秒/次，300 次均值）实证 **Rust 执行核心比
    Python 快 23–30x**（均值 ≈27x，tree-walking 未优化即显著领先）——主战场价值
    实证（cProfile 实证的 per-step Python 反射/间接瓶颈被 Rust 消除）。公平对比
    （两侧均含 load + execute：Python compile 缓存查找 vs Rust JSON 反序列化）。
    非测试（性能断言 flaky）。
  - **P9 阶段③ 第四增量 执行核心 KB 语料面 已落地（本 session，隔离分支
    `rust-kernel` → 已 merge unsafe-vibe-dev 删分支）**：host service 桥接
    （Rust → Python 回调，KB 逻辑留 Python 单点真理，不复制避免双通道）——
    `IbValue::Host`[宿主对象引用] + `knowledge()` 经桥接 `create_knowledge` + KB
    方法委托 Python 对象[register_world/add_fact/worlds/exists/lookup_pair/
    contradicts] + 参数/结果双向转换[Rust IbValue ↔ Python 对象，嵌套结构正确]
    + `ibci_ext.run_artifact(artifact_json, bridge)` 暴露 + 桥接助手
    bridge.py[经 registry 创建 knowledge]——**全语料 14/14 数据面逐条等价**[11
    非 KB + 3 KB]。**零风险加法式**（opt-in，不动 Python 执行路径）。
  - **P9 阶段③ 续（当前批次，隔离分支续）**：执行核心——CPS 优化[43 节点 enum
    分发，数据面等价后做性能优化，在 27x 基础上进一步提升] + 符号池/类型池/侧表
    反序列化 + 更宽 IBCI 语料[超出当前 14 条]。四阶段全貌：① 地基 ✅ → ② 前端
    （lexer ✅ / parser 完整面 + 剩余面 + 位置 ✅ / 语义推迟）→ **③ 执行核心
    [主战场：反序列化器 ✅ / 对象模型 + 解释器 + 数据面 11/11 ✅ / 性能基准
    23–30x ✅ / KB 语料面 host service 桥接 全语料 14/14 ✅ / CPS 优化当前]**
    → ④ 并发解除[task_scheduler IO-only → CPU+IO 真并行 GIL-free]。确认零风险
    （全量零回归 + 复核）后 merge unsafe-vibe-dev 并删分支。
  - **🔴 P9 终点（用户 2026-09-10 裁定，重新定义——全量 Rust 化）**：Rust 部分
    （阶段②③④）完成后开启**新评估 + 新自主执行模式**，评估**全核心逻辑全量
    Rust 化**（编译/语义/执行/调度/并发等核心面）；**保留关键部分 Python 接口**
    （灵活性 + 供 Python 入口能力，非 100% 无 Python）；**证明绝大部分关键核心
    逻辑可 Rust 化时全量转向 Rust，废弃 Python 双通道/对比**（迁移期安全网退场）。
    双内核 + 差分 harness = **迁移期临时安全网**（非永久——调研 §2.3 已从"永久
    双内核"演进为"迁移机制"）。裁定全记录 = WORKLOG（P9 终点裁定条目）+
    `_rust_kernel_survey.md` §2.3/§2.6。
  - **P0-P9 执行清单**（详见 `_world_model_db_design.md` §6 + `_rust_kernel_survey.md`）：
    P0 设计定稿 ✅ → **P1 R-A quote/eval ✅** → **P2 R-B 世界模型 KB ✅** →
    **P3 磁盘格式 ✅** → **P4 R-C 确定性模式 ✅** → **P5 R-D 工件加载 ✅** →
    **P6 向量面 ✅** → **P7 R-F 投影派生视图 ✅** → **P8 测试进程内化 ✅**
    → **P9 Rust 内核 阶段① 地基 ✅ / 阶段② 前端（当前批次）**。每步：受影响子集+
    smoke 验证零回归 + 本地 commit + 同步 NEXT_STEPS/WORKLOG。
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
- **差分等价 harness 已含 quote/eval + KB 语料（P9 phase ① 扩展，本 session）**：
  `scripts/differential_harness.py`（Python 内核参考基线 + 确定性验证 + `run_kernel("rust")`
  drop-in + `--diff` 对拍；语料 10 例：quote/eval 数据/命令二元判别面 + KB 确定性查询面
  `kb_query`/`kb_expand_determinism`[R-B 里程碑语料]）+ 常设门
  `tests/contracts/test_differential_harness.py`（smoke 子集）。后续并入 R-B 更大事实集
  语料（P3 load_kb 后以 v30 451 事实驱动）+ 实现 `run_kernel("rust")` 后即成 py↔rust
  差分门（Rust 安全网）。
- **全量 pytest 基线（本 session P9 阶段③ 第四增量阶段边界实跑）**：**4274 passed /
  1 skipped / 133.26s / rc=0**（= 前基线 4272 + 数据面差分 2 例[KB 语料面 host
  service 桥接]；供下一 session 参照，不冻结）。

### 2.1 历史状态（git / WORKLOG 承载，本文件不再登记）

> round3 试用需求整合 / meta 层 MVP / VISION-6 P1-P6 的收束历史不在本节登记（章程红线：
> 不保留已完成历史叙述）。过程记录 = `tasks_docs/WORKLOG.md` + `git log`；长期项状态单点
> 真理 = `tasks_docs/PENDING_TASKS.md`；试用需求 intake 模式参照 = WORKLOG round3 条目。

### 2.2 交接检查单（当前有效）

- [ ] 读 **`_world_model_db_design.md`**（本主线设计 + 调研结论 + 决策点/风险 + P0-P9 执行清单；
  **首读**）+ `_rust_kernel_survey.md`（Rust 内核替换调研——P9 依据；P2/P3/P4/P5/P6/P7 设计
  文档已收束删除，裁定全在 WORKLOG + docs/）
- [ ] 读 `NEXT_STEPS.md`（当前主线 = 世界模型 DB + **当前批次 P9 阶段② Rust 前端[隔离分支续]** +
  工作节奏 + ⛔ 工作模式定论）
- [ ] 读 `WORKLOG.md`（P1 R-A + P2 R-B + P3 磁盘格式 + P4 确定性模式 + P5 窄模型工件 + P6 向量面
  + P7 投影派生视图 + P8 测试进程内化 + P9 Rust 内核阶段① 地基 裁定 + 世界模型 DB 设计裁定 +
  环境重建 + 本交接）
- [ ] **P9 环境**：Rust 构建 pin `CARGO_HOME=$PWD/.cargo_local` + `CARGO_TARGET_DIR=$PWD/target`
  （默认 cargo 位置不可写[agent bash EACCES]）+ PYO3_PYTHON=venv + 常规网络免审批；构建链 =
  `scripts/build_rust_ext.sh`（产物 `core/runtime/kernels/ibci_ext.so`，gitignore 可再生）；
  差分 harness = `tests/diff_harness/`（常设安全网——Rust 每阶段落地后须差分等价零差异放行）。
- [ ] **设 goal**（据 §2.0 主线 + `_world_model_db_design.md` §6 P9 阶段②-④；objective 按
  §1.3 模板套用，含约束：**禁 push**（须用户单独授权）；**常规网络允许**（不触发审批）；
  **Rust 构建可行**（pin `CARGO_HOME`+`CARGO_TARGET_DIR` 到 workspace，免审批）；**避免**写
  workspace 外文件 / 无必要沙箱提权；用户不在场且需 push 时延后记录不阻塞）；跨 session 需
  **新建** goal（旧 goal 不跨 session 续跑）
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
