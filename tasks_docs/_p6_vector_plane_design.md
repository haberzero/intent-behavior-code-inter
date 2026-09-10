# P6 向量面（KB 词嵌入 cosine 内容信号）设计单点真理

> 状态：设计定稿（2026-09-10，P6 批次开工）。主线设计 = `_world_model_db_design.md`
> §3.3/§3.4/§4/决策点3/§6-P6。本文 = P6 机制裁定（self-grill 全分支消解记录）。
> P6 收束后删除。

## 1. 调研结论（现有向量面实证）

- **`ai` 模块已有低层向量原语**：`embed(texts,...)`（文本→向量，经 embedding
  provider；`set_embedding_mock` 提供**确定性 mock 向量**——同输入同输出）+
  `retrieve(query: vector, corpus: list, k)`（**通用暴力 cosine 检索**，对临时
  corpus）+ `recall(query: str, corpus: list, k)`（文本→embed→retrieve）。
- **`vector` 原语已有一等值类型**（`dim/dot/norm/cosine/scale/add/sub`，不可变）。
- **缺口**：KB **无嵌入面**——词/事实嵌入无处持久化（KB artifact 无 vector
  节），KB 无原生相似检索（`ai.retrieve` 需传临时 corpus，非 KB 自身词表）。
- **裁定：P6 = KB 词嵌入面**（嵌入持久化进 KB artifact + KB 原生
  `embed_search` 内容信号检索）。`ai.embed`/`ai.retrieve` = 低层原语（生成/通用
  检索）保留；`kb.embed_search` = KB 自身词表上的高層内容信号检索（机制分层，
  非重复）。

## 2. 面定位（机制同构裁定）

**嵌入面挂在 `knowledge` 值类型上**（单点真理 = KB 值，决策点3；与 P2"演化
knowledge 就地"同纪律——不另立平行向量索引类型）：

| 面 | 语义 | 静态面 |
|----|------|--------|
| `kb.set_embedding(word, vec)` | 给已注册词挂/换嵌入（可变，同 add_fact 纪律） | `(str, vector) -> void` |
| `kb.embedding(word)` | 取词嵌入（未挂 = fail-fast） | `(str) -> vector` |
| `kb.embed_search(query, k)` | 全嵌入词暴力 cosine 取前 k（**内容信号非判定**） | `(vector, int) -> list` |
| `kb.embedding_dim()` | 嵌入维度（无嵌入 = fail-fast） | `() -> int` |
| `kb.has_embedding(word)` | 是否已挂嵌入 | `(str) -> bool` |

**裁定（self-grill 消解）**：
- **D1 词级（非事实级）**：嵌入挂治理词表（词全局，非 per-world）。事实级嵌入
  （需定义事实嵌入=词嵌入组合 or 独立嵌入）= 后置扩展——**不预置**（避免
  事实嵌入语义的臆测）。设计签名 `embed_search(query, world?, k)` 的 `world?`
  对词嵌入无意义（词全局）——本批落词级 `embed_search(query, k)`，world 过滤
  归事实级嵌入扩展。
- **D2 内容信号非判定**：`embed_search` 返回相似度 rank/分数（异常检测/语义
  对比用），**从不做判定**（D1 灰盒原则：判定走图平面确定性路径）——与
  narrow_model.score 同定位。
- **D3 query = vector**（纯内容信号，类型面 str/vector 无多态）：按词检索 =
  先 `kb.embedding(word)` 取向量再 `embed_search`；任意文本 = `ai.embed(text)`
  取向量。不内置 str→向量查找（保持纯向量面，与 `ai.retrieve` 分层清晰）。
- **D4 暴力 cosine**（小规模；格式预留 ANN）：无索引常驻服务（不可变工件
  加载，非常驻）；ANN/FAISS 派生加速 = 后置（决策点3：纯 IBCI 值+工件起步）。
- **D5 确定性**：cosine = IEEE 浮点纯算术；排序键 `(−score, word)` 升序
  （score 降序 + 平手按词名，稳定 tie-break）；同输入同输出。
- **D6 治理门**：`set_embedding` 词须已注册（复用 KNW_VOCAB_UNREGISTERED）；
  维度须与既有嵌入一致（KNW_EMB_DIM_MISMATCH）；`embedding` 未挂词
  （KNW_EMB_NOT_SET）；`embed_search` k 非正整数（KNW_EMB_SEARCH_INVALID，
  k 超嵌入词数 = 返回全部——同 narrow_model.topk 截断纪律）。

## 3. KB artifact 版本演进（v2 加法，v1 向后兼容）

- **v1**（P3）：`{schema_version:1, content_hash, facts, vocab, seq}`；
  canonical = `{facts, seq, vocab}`（无 vector 键——匹配既有存储 hash）。
- **v2**（P6）：`{schema_version:2, content_hash, facts, vocab, seq,
  vector: {dim, embeddings}}`；canonical = `{facts, seq, vocab, vector}`
  （vector 节入 hash）。
- **加载版本感知**：`schema_version ∈ {1,2}` 均支持——v1 无 vector 节
  （嵌入面空）+ hash 按 v1 canonical 验；v2 读 vector 节 + hash 按 v2
  canonical 验。未知版本 = KNW_KB_SCHEMA_VERSION（无自动迁移）。
- **保存 = v2**：`save_kb` 写 schema_version=2 + vector 节（嵌入面，可能空）
  + hash 按 v2 canonical。
- `KB_SCHEMA_VERSION = 2`（当前版本）；`_KB_KNOWN_VERSIONS = (1, 2)`（加载
  接受集）。canonical/hash 函数加 vector 参数（版本感知）。

## 4. 诊断码（+3，KNW_ 域扩展 = 嵌入面）

| 码 | 语义 |
|----|------|
| `KNW_EMB_DIM_MISMATCH` | set_embedding 向量维度与既有嵌入不一致 |
| `KNW_EMB_NOT_SET` | embedding/embedding_dim 引用未挂嵌入（词已注册但无嵌入 / 无嵌入面） |
| `KNW_EMB_SEARCH_INVALID` | embed_search 的 k 非正整数 |

（词未注册复用 KNW_VOCAB_UNREGISTERED；不新造。）

## 5. 测试面

- **F1 runtime 值类型面**（`tests/runtime/test_knowledge_embedding.py`）：
  set_embedding 治理门（未注册词/维度错）/ embedding 取回（未挂 fail-fast）/
  embed_search 暴力 cosine 排序 + 确定性 tie-break / 同输入同输出 / k 非法 /
  k 超界截断 / embedding_dim / has_embedding / 嵌入面序列化 round-trip。
- **F2 磁盘面 + e2e**：KB artifact v2 round-trip（嵌入保真）/ v1 向后兼容
  （无 vector 节加载 = 空嵌入面）/ hash 版本感知（v1 hash 不含 vector /
  v2 含）/ save 恒 v2 + e2e（ai mock 嵌入 → set_embedding → embed_search
  内容信号确定性 + 零 LLM 凭证）。
- **文档**（F2）：knowledge 参考节嵌入面 + 11_modules KB artifact vector 节 +
  15_diagnostics +3 码。

## 6. 批次

- **F1**：knowledge 嵌入面（payload + 5 方法 + 公理）+ 序列化 collect/hydrate
  + 3 诊断码 + catalog + 15_diagnostics + runtime 值类型面测试 + 受影响子集
  + smoke + commit。
- **F2**：KB artifact v2（版本感知 canonical/hash + vector 节 + v1 向后兼容 +
  save 恒 v2）+ load_kb/save_kb 更新 + runtime 磁盘面测试 + e2e（内容信号
  确定性）+ 文档同步 + 全量放行门（公理层变更——knowledge 新面）+
  WORKLOG/NEXT_STEPS/HANDOFF + commit。
