# 世界模型数据库 · 设计（R-B 一等 KB + 融合向量/传统/自然语言世界模型）

> **性质**：临时任务控制文档（设计阶段），供下一 session 接手**自主实现**。
> **来源**：试用方需求单 v2（`ibci-trial/docs/REQ_IBCI_WORLD_MODEL_INTEGRATION.md`）+
> 数据结构/数据库重构分析（`ibci-trial/docs/DATA_STRUCTURE_DATABASE_ANALYSIS.md`）+ 本轮深度调研。
> **裁定（用户 2026-09-10 授权，按智能体推荐推进）**：
> ① **演化现有 `knowledge`** 为一等世界模型知识图谱（单点真理，不另立平行类型）；
> ② **R-A quote/eval 先出最小设计+POC** 再定契约；
> ③ **向量面 = 纯 IBCI 值 + `ImmutableArtifact` 工件**（暴力 cosine 起步，格式预留 ANN/FAISS 派生加速）；
> ④ **磁盘格式 = IBCI 内容寻址 artifact**（`schema_version`+`content_hash`+`facts/vocab/vector` 分节；
> JSON 降级为传输/交换格式，IBCI 代码降级为派生视图）。
> **权威需求源（外部，不在本仓库）**：`/home/dsh/proj/ibci-trial/docs/`（D-ISO：只读参考，不修改）。

---

## 0. 一句话设计论点

> **IBCI 原生数据库 = 一个一等值类型（世界模型知识图谱）。单一权威源 = append-only 事实日志
> （UID 键 `(world,s,r,o)` + source/status）。融合两个查询平面——① 图/三元组平面（传统 DB：治理词表 +
> 8 倒排索引 + 矛盾/传递/展开，D1 零 LLM）；② 向量平面（内容信号：事实/词嵌入，相似度只作内容信号、
> 经 `ImmutableArtifact` 在推理时加载、从不做判定）。存储压缩态、按需展开；事实同时是数据又是程序
> （quote/eval）；跨尺度自指；整体是可加载/可序列化/哈希钉扎的**值**，而非外部服务。**

**为什么"独特"（四大自主贡献，无现成 DB 覆盖）**：
1. **quote/eval 数据行为二元**——事实同时是数据(可查/可打印/精确对比)又是命令(可执行/验证)，转换确定性。
2. **D1 确定性 + 可审计**——"本查询/本运行 LLM 调用=0、逐字节可复现"是一等保证（复用 knowledge 引擎单调序号审计 + llm_journal + budget）。
3. **跨尺度自指 + KB 自指**——尺度相对指涉（`atom→proton@modern / →quark@quantum` + `self_ref='self'` + `size_rank`）；KB 可含"关于 IBCI 自身"的事实（R-E）。
4. **压缩态存储/按需展开 + 值化存储**——存定理不存证明（三元组存，展开态确定性推导）；整个 KB 是内容寻址值（非服务）。

---

## 1. 需求溯源（试用方要什么，为什么）

- **北极星**：自指灰盒自然语言自动机（三纸带 D/I/M + quote/eval 地基 + 自指）。
- **缺口**：D 纸带（世界模型 KB）与 I/M 纸带（自动机）**无接口**——IBCI 不能原生加载/quote-eval/
  按需展开/确定性验证 KB。**现状 stopgap** = trial 侧 `schema_to_ibci.py` 把 KB 静态编译成冻结 IBCI class 代码。
- **要 IBCI 演进的 6 件事（R-A~R-F，按优先级）**：
  | 编号 | 需求 | 优先级 |
  |------|------|--------|
  | R-A | quote/eval 原语（表达式既是数据又是命令，转换确定性）——地基 | **P0** |
  | R-B | D 纸带一等存储（加载压缩态 KB + 8 索引/7 查找/5 对比/按需展开） | **P0** |
  | R-C | 确定性执行模式（零 LLM + 逐字节可复现 + "LLM=0" 审计凭证） | **P0** |
  | R-D | 推理时加载窄模型工件（离线训练，score/topk；**非运行时训练**） | P1 |
  | R-E | M 纸带/自指支持（意图栈/作用域；自动机描述自身） | P2 |
  | R-F | 原生 schema→IBCI 投影（派生视图，非数据层本身） | P2 |
- **核心原则（用户强调，本轮深化）**：
  - **不能永远用 IBCI 代码承载数据**（stopgap 实证 lossy，见 §2.2）；
  - **不能永远用 JSON 承载数据**（JSON = 传输/交换格式，≠ 运行时数据模型）；
  - 需求几乎意味着一种**独特数据库** = 向量库 + 传统库 + 自然语言世界模型真实需求的融合，
    **符合 IBCI 自身建模模式 + 内存结构模式**；可参考/借鉴成熟库，但**大幅自主设计**。
- **明确非目标（需求单 §5）**：不支持运行时训练；不内置世界模型数据（内容由试用方供给）；不改变 IBCI LLM-混合核心。

---

## 2. 实证调研结论（改变框架的事实——下一 session 无需重查）

### 2.1 v30 真实数据形态（`experiments/e68_flywheel_v29/world_model_v30.json`，160KB）
- 顶层键：`instance_name` / `schema_version`(="1.0") / `provenance` / `vocabularies` / `words` / `axioms`。
- **`axioms` = 451 条，形态极简 `{world, s, r, o}`**（**尚无** `id`/`source`/`status`——那是目标态设计）。
- **`words` = 99 个**，每个 `{lexeme, gloss, is_set, members, entries[world→{form,self_ref}], relations[world→{target,relation_type}]}`。
- **`vocabularies = {worlds[21], relation_types[51]}`**（relation_types 是**裸名字列表**，**无** semantics/transitive/multi_valued——元数据在 `experiments/e48_relation_space_extension/governed_vocab.json`：21 世界/59 关系 allowlist+语义）。⚠️ v30 的 51 vs governed_vocab 的 59 有差异，需对齐（见 §7 决策点）。
- **🔴 双写真相**：`word.relations`(417 事实) 与 `axioms`(451) 重叠；`only_in_axioms=34`（**34 条事实只存在于 axioms，word.relations 没有**）。→ 单一权威源必须 = axioms 事实日志，word.relations **须改为派生**（这正是 trial K58 要修的）。
- 关系分布（top）：`associated(96) depends_on(35) generates(26) composed_of(25) excites(25) transfers_energy(23) absorbs(20) is(14)`。
- 世界分布（top）：`modern(287) relativity(21) solid_state(21) nuclear(14) mechanical(12) optical(11) ...`（21 世界，modern 占 64%）。
- **数据规模小**（451 事实/99 词），但飞轮产新（产新率 0.233）→ 需支持**动态增长（append-only）**。

### 2.2 现状 stopgap（`experiments/e28_world_model_schema/tools/schema_to_ibci.py`）缺陷（实证）
- 每词生成一个 IBCI class，`form(world)`/`self_ref(world)`/`relations_of(world)` 用**硬编码 `if world=="...": return "..."` 字符串分支**；关系编码为 **`"target:relation_type"` 单字符串**（trial 抱怨的"关系字符串化/每 world 一条"）。
- **根本不存 axioms**（只读派生的 `word.relations`）→ **静默丢掉 34 条 only_in_axioms 事实**（**lossy**，有具体缺陷证据）。
- 用 `return "unknown"` / `return ""` 当**魔法默认**（code-quality 红线：魔法默认/静默回退）。
- 无查询/无索引/无对比/无展开/无 quote-eval；KB 增长需**全量重编译**。
- → **直接论证"不能永远用 IBCI 代码承载数据"**，且证明 R-F 投影应降级为**派生视图**（`to_ibci()`），存储层必须是**数据（值）**。

### 2.3 IBCI 已有子件（全部现成，缺的是"融合成一致数据层"）
- **`knowledge`（`KnowledgeAxiom` / `IbKnowledge`）**：文档明写**"语言自动机的知识层/D 纸带"**。
  方法面 `store(key,value,check,provenance)/get/amend/history/export/keys/len/cast_to`；
  **append-only**（amend 保留事件流+指针切换+强制 reason+再过 check 门）；
  **审计用引擎单调序号（非墙钟）= 确定性可复现**；条目值冻结（深克隆快照）。
  → 已提供 D1 血缘/审计/append-only 子集，但**是扁平 key→value，不是 (s,r,o) 图、无索引/无 world 维**。
- **`vector`（`VectorAxiom` / `IbVector`）**：不可变值 + `dim/dot/norm/cosine/scale/add/sub/__getitem__/__to_prompt__`；无 I/O、内存型。→ 向量**原语**（非向量**索引/DB**）。
- **`memory`（`MemoryAxiom`）**：分层值类型（working_set/session/knowledge/long_term）。
- **`behavior`**：行为作值（`meta.compile` 返回产物摘要 + `ihost.run_code` 执行源串）；SR-4 一等可执行是 Phase D。
- **`ai.recall` / `ai.embed`**：doc 缓存向量召回（现有"向量查询"面，低层原语）。
- **`ImmutableArtifact`（`core/runtime/serialization/immutable_artifact.py`）**：**只读、哈希钉扎、可加载的序列化值**（任何写抛 TypeError）；现用于编译器产物 + save_state/load_state 确定性。→ **正是"压缩态快照 / 离线窄模型工件（R-D）"的现成基座**。
- **`runtime_serializer`**：save_state/load_state + 内容寻址/哈希（持久化+完整性模式）。

### 2.4 `knowledge` 消费面轻 → 演化低风险
引用 `knowledge` 的多为**基础设施**（semantic 表达式访问器 / serializer / memory / environment / deep_clone / run_result / registry / specs），**无重用户面**。→ **演化 `knowledge` 为知识图谱不会破坏重依赖**（仍需逐一核对消费方，见 §7 决策点 #1）。

### 2.5 环境事实（本轮已核验，2026-09-10）
- Rust 工具链 **cargo/rustc 1.98.1**；**agent bash 对默认 cargo 写位置不可写**（`~/.cargo` 与
  `CARGO_HOME=/opt/rust/cargo` 均 Permission denied）→ **实际构建须 pin `CARGO_HOME`+`CARGO_TARGET_DIR`
  到 workspace 内**（如 `$PWD/.cargo_local`+`$PWD/target`）。**实测 `cargo fetch`（网络下载 libc
  v0.2.189）+ no-dep 构建 rc=0，免审批**（workspace 写 + 允许的常规网络）。
- **Rust↔Python 协同已端到端验证（2026-09-10）**：pyo3 crate（extension-module）`cargo build
  --release` → `.so` → Python import + 调用 Rust 函数 OK（`hello()="rust-py-ok"`/`add(20,22)=42`，
  `RUST_PY_COLLAB_OK`）。pyo3 3.12 用 0.22/0.23（3.14 需 ≥0.29）；工具链 maturin 1.15.0 + cargo/rustc
  1.98.1。**✅ Python 3.12 dev headers 已安装（用户 `apt-get install python3.12-dev`）+ 端到端已
  验证**：pyo3 0.23 crate `cargo build --release`（pin workspace + `PYO3_PYTHON`=venv）→ `.so` →
  venv（3.12.3）import + 调用 Rust 函数 OK（`PROJECT_RUST_PY_312_OK`）。**项目 Rust 构建路径全通，
  P9 无环境阻塞。**（agent 被 `NoNewPrivs=1` 锁死无法 sudo；`/etc/sudoers.d/dsh` 规则存在，人工
  dsh shell 可 sudo——供重装参考。）
- **全量 pytest 基线（2026-09-10 实跑，干净）**：**3990 passed / 1 skipped / 103.58s / rc=0**。
- venv Python 3.12.3 + editable 安装 ✅；api_config.json ✅（probe 通过）；smoke 子集 `tests/contracts`+`tests/compiler` = **828 passed, 11.3s**（进程内无子进程，无审批）。

---

## 3. 设计详案

### 3.1 单一权威源 + 全派生（design-philosophy §一）
`facts.log`（append-only，UID 键 `(world,s,r,o)`+source/status）= **唯一权威**。
**倒排索引 / 展开态 / 向量索引 / IBCI 代码投影** 全部**从它派生**（加载时重建或追加时增量维护），**绝不独立存储**。
→ 一次根治 §2.1 的 `word.relations × axioms` 双写；`word.relations` 改为 `by_subject[lexeme]` 派生。

### 3.2 三层结构 → 映射到现有原语（机制同构）
| 层 | 职责 | 承载的现有原语 |
|----|------|---------------|
| **存储层 D**（压缩态） | 事实日志 + 治理词表 + 向量工件（append-only、冻结值、UID） | `knowledge`（事实/词表/血缘/审计）+ `vector`（向量）+ `ImmutableArtifact`（哈希钉扎快照） |
| **解释层 I**（按需展开） | 倒排索引/查找/矛盾/传递/展开/对比/quote-eval（**零 LLM**） | 新**方法面**（挂同一值类型，确定性）；语义对比走 `vector.cosine` 内容信号 |
| **契约层**（磁盘格式） | 压缩态序列化布局 + schema_version + content_hash（加载/验证） | `runtime_serializer` + `ImmutableArtifact`（内容寻址、可复现） |

### 3.3 方法面契约（给试用方的"库" API；显式方法、无运算符面，与 memory/knowledge 同构）
```
kb = world_model.load(path)            # 加载压缩态（facts.log+vocab+vector artifact），内容寻址验证
-- 图/三元组平面（确定性，D1 零 LLM）--
kb.lookup_pair(s,r) / kb.exists(world,s,r,o) / kb.all_in_world(w) / kb.by_source(src)
kb.contradicts(s,r,o')                 # 按 multi_valued 判定
kb.transitive(s,r)                     # 传递闭包（小图链式；格式预留 Datalog 定点）
kb.expand(fact)                        # 按需确定性展开（词结构/关系语义/世界上下文），逐字节一致
kb.compare(a,b) / kb.same_word(a,b)    # 5 层对比（1-3/5 确定性）
-- 向量平面（内容信号，非判定）--
kb.embed_search(query, world?, k)      # 相似度 rank/分数，标注为内容信号（异常检测用）
-- 血缘/审计（复用 knowledge）--
kb.history(fact) / kb.amend(fact, reason) / kb.source(fact)
-- quote/eval（R-A 地基）--
quote(e) / eval(e)                     # 表达式既是数据(可查/可打印/精确对比)又是命令(可执行)，转换确定性
-- 投影（R-F，派生视图）--
kb.to_ibci()                           # 确定性导出 IBCI 代码视图（替代 lossy 静态投影器）
-- 推理时工件（R-D，非训练）--
model = bind_artifact(path); model.score(s,r) / model.topk(s,r,k)   # 经 ImmutableArtifact 加载
-- 确定性模式（R-C，横切）--
run --deterministic  →  "LLM 调用=0" 审计凭证（复用 llm_journal + budget 守卫）
```

### 3.4 磁盘格式（IBCI 内容寻址 artifact；替换"永远 JSON / 永远 IBCI 代码"）
- 一个 **IBCI 内容寻址 artifact**：`{ schema_version, content_hash, facts[], vocab{words,relations,worlds}, vector{...} }`。
- 由 `ImmutableArtifact` + `runtime_serializer` 承载：可加载/可验证（content_hash 校验）/可增量追加（append-only）。
- **对齐 v30 真实形态**（§2.1）：facts = `(world,s,r,o)`+补 `id`(UID)/`source`/`status`（目标态）；vocab 含 governed 元数据（semantics/transitive/multi_valued，源自 governed_vocab.json）。
- **JSON 降级为"传输/交换格式"**（试用方导出/导入），**不再是运行时模型**；**IBCI 代码降级为派生视图**（`to_ibci()`），不再是存储。

### 3.5 对齐 IBCI 内存结构模式
引用容器 + 条目值冻结（深克隆快照）+ append-only 事件流 + 内容寻址哈希钉扎快照 + 显式方法面（无运算符）
——**与 memory/knowledge/vector 完全同构**。这就是"符合 IBCI 自身内存结构模式"的落法。

---

## 4. 借鉴 vs 自主（点名成熟系统；核心自主）

| 方面 | 借鉴（成熟） | IBCI 自主（独特） |
|------|-------------|-------------------|
| 事实模型 (s,r,o) | RDF/SPARQL 三元组库（Jena/Virtuoso） | **事实同时是数据+程序**（quote/eval） |
| 治理词表/本体 | RDF/OWL（轻量化） | 治理 allowlist 即**命令↔数据同构**（关系既是命令又是数据） |
| 倒排索引/查找 | 任意关系型 DB | **D1 零 LLM + 可审计凭证** |
| 传递闭包 | Datalog 定点 | 小图链式即可，格式预留 Datalog 升级 |
| ANN 向量索引 | FAISS(IVF-PQ)/pgvector/Milvus-Qdrant-Weaviate | **向量只作内容信号、从不做判定**（判定走图平面）；**不可变工件加载、非常驻服务**；小规模先暴力 cosine |
| 混合检索 | Milvus/Qdrant/Weaviate vector+结构化 | "向量=内容信号/图=判定"的**原则性切分** |
| append-only/审计 | 事件溯源 / WAL（SQLite WAL） | **引擎单调序号**（确定性非墙钟）+ amend 再过 check 门 |
| 跨尺度自指（self_ref 跨 world） | 无直接对应 | **独创**——尺度相对指涉 + size_rank |
| 自指 KB（含"关于 IBCI 自身"） | 无 | **独创**——R-E |
| 压缩态存储/按需展开 | （编译器存 IR 不存全树，弱类比） | **独创原则**——存定理不存证明 |
| 值类型存储 | 内容寻址存储（git objects/IPFS） | **KB 是"值"**（可加载/可序列化/哈希钉扎），非服务 |

---

## 5. 与工作节奏契合（收束进自指弧线，不新设竞争主线）

- **主线收束**：R-A（quote/eval）**并入 selfref 弧线**（selfref SR-1/2/3 已依赖"行为作值"二元性；R-A 是其地基一等化，推进 C3/D1）；R-B（此 DB）**演化 knowledge**（机制同构 memory/knowledge）；R-C（确定性模式）**横切**。
- **Rust 内核**：**仅设计**（`_rust_kernel_design.md` + 差分等价 harness 设计）；**构建/编译延期**（需 `~/.cargo`+网络=审批）。harness **语料 = 世界模型里程碑**（KB 事实集/quote-eval 表达式/零 LLM 逐字节）。Rust = 独立隔离分支 `rust-kernel`（永不触碰 main）。
- **测试进程内化**：e2e 44% 子进程开销 → 用 `conftest run_ibci` 进程内助手进程内化，**降低全量门成本**（dev ~114s → 下降），服务本阶段高频进程内验证（DB 测试 + Rust 差分 harness 都须进程内）。**升格为早期使能项**。
- **kernel-agnostic**：DB 语义契约落 axiom/语言层（与内核无关）；先落 Python 内核，Rust 作快路径；两内核共享同一 DB 契约（差分 harness 保等价）。

---

## 6. 实施任务序列（P0–P9，给下一 session 的执行清单）

> 每步纪律：受影响子集 + smoke 子集（`tests/contracts`+`tests/compiler`）验证零回归 + 本地 commit +
> 同步 NEXT_STEPS/WORKLOG/本设计文档。**全量 pytest 仅**：merge 门 / 公理层或语义错误集变更 / 阶段边界 / 开新分支前。

- **P0 设计定稿**：本文件（`_world_model_db_design.md`）为契约草案。✅（本轮已写，待用户确认方向后进入 P1）
- **P1 R-A quote/eval**：最小 POC + 机制设计。**触及公理层/语义错误集 → 全量 pytest 评估破坏面 + 详尽记录变化前后**。先定契约（`quote`/`eval` 的精确语义 + 现有 `__to_prompt__`/`__from_prompt__` 是否足够 vs 新原语）。
- **P2 R-B 世界模型 KB**：演化 `knowledge` 为 `(world,s,r,o)` 三元组知识图谱（单一权威=append-only 事实日志+UID+source/status；8 倒排索引/7 查找/5 对比/按需确定性展开/矛盾/传递闭包；治理词表 words/relations/worlds[semantics/transitive/multi_valued]；消除 word.relations×axioms 双写，index/展开/投影全派生）。
- **P3 磁盘格式**：IBCI 内容寻址 artifact（复用 `ImmutableArtifact`+`runtime_serializer`；可加载/哈希钉扎/可增量追加；对齐 v30 真实形态）。
- **P4 R-C 确定性执行模式**：`--deterministic` 零 LLM + 逐字节可复现 + "LLM 调用=0" 审计凭证（复用 llm_journal + budget 守卫）。
- **P5 R-D 推理时工件加载**：`bind_artifact` + score/topk（经 `ImmutableArtifact`；纯推理零训练）。
- **P6 向量面**：KB 事实/词嵌入 cosine 内容信号（非判定）；磁盘格式预留 ANN。
- **P7 R-F 投影降级为派生视图** `kb.to_ibci()`（确定性导出，替代 lossy 静态投影器；对拍试用方参考）。
- **P8 测试进程内化**：e2e 用 conftest run_ibci 进程内助手进程内化（降全量门成本）。
- **P9 Rust 内核**：① **差分等价 harness 骨架已就绪**（`scripts/differential_harness.py` + 常设门
  `tests/contracts/test_differential_harness.py`；Python 内核参考基线 + 确定性已验证，`run_kernel("rust")`
  drop-in 点 + `--diff` 对拍在位）；② 写 `_rust_kernel_design.md`（crate 结构 frontend/exec/pyo3 三层 +
  AST 序列化契约对接 + kernel 选择协议）；③ 实际构建（**3.12 headers 已装 + pyo3 0.23 端到端已验证 →
  可行**；CARGO pin workspace + 允许网络）。harness 语料后续并入 R-B 世界模型里程碑（KB 事实 /
  quote-eval 表达式）作 fuzz 语料。

---

## 7. 开放决策点与风险（self-grill：下一 session 须质询/拍板项）

| # | 决策点 | 推荐 | 风险/注意 |
|---|--------|------|-----------|
| 1 | **类型归属**：演化现有 `knowledge` vs 新建 `world_model` | **演化 `knowledge`**（单点真理、消费面轻、文档已定位其为 D 纸带） | 需审计 knowledge 现有消费方（§2.4），确保图化不破坏扁平 key→value 消费；若冲突则图作 knowledge 的**值形态**（knowledge 存 fact 结构），而非替换 |
| 2 | **R-A 精确机制**：`__to_prompt__`/`__from_prompt__` 够否 vs 新原语 | 先出最小 POC 再定契约 | **语言级语义/公理层变更 → 全量 pytest + 近上报阈值**（全案最高风险块）；试用方自标 Open Question |
| 3 | **向量面形态**：纯 IBCI 值+工件（暴力 cosine 起步，格式预留 ANN）vs 早期即接 FAISS | **纯 IBCI 值+工件起步**（单点真理=KB 值；FAISS 仅作派生加速器后置） | 影响磁盘格式与"自主 vs 依赖"边界；FAISS 需额外依赖（审批/环境） |
| 4 | **磁盘格式定案**：IBCI 内容寻址 artifact（替换 JSON 为传输格式） | **是**（schema_version+content_hash+facts/vocab/vector 分节） | 定格式即定**共享契约**（影响试用方对接 + 双方 D-ISO） |
| 5 | **v30 关系元数据对齐**：v30 `relation_types[51]`（裸名）vs governed_vocab[59]（allowlist+语义） | 以 governed_vocab 为元数据权威，v30 事实对齐之 | 数量/覆盖差异需明确（哪 8 条多出的关系、是否有 v30 引用了 governed_vocab 外的关系） |
| 6 | **knowledge 方法面扩展**：现有 store/get/amend/history 保留 vs 扩展 | 保留既有面 + 新增图平面方法面（lookup/exists/contradicts/transitive/expand/compare/embed_search/to_ibci） | 方法面膨胀——按 design-philosophy 统一命名/粒度；避免与既有 memory 方法面混淆（KB≠memory） |
| 7 | **R-A 与 selfref 的边界**：quote/eval 是 selfref 的一部分 vs 独立语言原语 | 并入 selfref 弧线但作为**独立语言原语**（selfref 消费它） | 触及公理层——需明确 quote/eval 的类型系统落点（什么类型的值可 quote/eval） |

---

## 8. 交付给试用方的契约草案 + 分工

- **分工（需求单 §5.4 已定）**：**IBCI 拥有** 引擎 + 磁盘格式 + 查询/quote-eval/确定性原语；**试用方拥有** 内容（KB 数据，按 IBCI 定义格式供给）。
- **交付形态**：新值类型 + 方法面进**上游 runtime**（unsafe-vibe-dev），试用方经 `bin/run-ibci.sh` **重钉扎**消费（D-ISO 不变）；**磁盘格式 = 双方共享契约**。
- **给试用方的"库"**：§3.3 方法面（一个 `world_model` 值 + 确定性 ops + `to_ibci()` 派生视图 + `bind_artifact` 工件加载 + `--deterministic` 凭证）。
- **替代关系**：`to_ibci()` 派生视图**取代** lossy 静态投影器（R-F）；IBCI 值化 KB **取代**"永远 JSON / 永远 IBCI 代码"。
- **试用方配合项**：① 重钉扎上游 tip（当前钉在 `123a341f`，**落后** selfref C1/C2 落地点 `255d31ce`/`fdfb1c81`）→ **对照 selfref 表面重估 R-A 净新增量**（避免重复造已收敛的地基）；② 按 IBCI 磁盘格式（§3.4）重新导出 KB（补 id/source/status 元数据）。

---

## 9. 非目标与硬约束（与 goal 一致）

- **非目标**：media Phase 4（PT-SEALED-1 封存）/ 线程无损挂起恢复 / Hindley-Milner 约束求解；IBCI 运行时训练（R-D 只推理时加载工件）；IBCI 内置世界模型数据；不改变 IBCI LLM-混合核心；不触碰 `main` 分支。
- **硬约束**：工作模式定论九条（禁 compat shim/胶水/tricky/过程式硬编码；质量优先；原则优先于行为维持；可推翻 IBCI 自身设计缺陷）+ 9 项 VM 不变量；改动公理层或语义错误集须全量 pytest 评估破坏面；破坏性重构默认已授权（详记决策+变化前后）；大范围/边界不明破坏性重构走独立隔离分支（Rust=`rust-kernel`，仅设计）。
- **D1（灰盒原则）**：判定/验证零 LLM；LLM 仅内容/获取/提案层。KB 的查找/对比/展开/quote-eval 全 D1 零 LLM；向量/窄模型只作**内容信号**，从不做判定。
