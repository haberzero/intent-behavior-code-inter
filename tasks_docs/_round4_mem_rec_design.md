# Round4 Phase B 设计文档 —— MEM 记忆基底 + REC 指令条件化召回

> Phase B 系统级架构设计（B1 交付物）。需求权威源 = `/home/dsh/proj/ibci-trial/docs/
> ibci_round4_vision_requirements.md` §3(MEM) + §4(REC) + §2b(技术锚点)。
> 设计纪律：与 LLM/embedding 同等严肃（语言级形态/职责/数据结构/系统角色/全元素交互）。
> 机制同构基准：knowledge（一等值类型先例）/ vector（数值值类型先例）/
> ai.embedding 模块面（模块服务先例）/ 9 项 VM 不变量。

---

## 一、系统定位（design-philosophy 全面审视）

### 1.1 核心洞察（需求单 §2）

**记忆 / 学习 / 自修改 是同一个子系统**——不应分散在 knowledge + M6 + M7 三处，
应统一为 IBCI 原生一等"记忆基底"（`memory`）。

### 1.2 与既有组件的关系

| 既有组件 | 与 memory 的关系 | 处置 |
|---------|-----------------|------|
| `knowledge`（已验证知识注册表） | memory 的**知识层特化**——带验证门/审计链的不可变知识条目 | 保留为独立类型（语义不同：knowledge = 已验证/不可变知识；memory = 通用记忆层/可层级/可遗忘）；memory 可**存储** knowledge 实例作为条目值 |
| `vector`（向量值类型） | memory 条目的**索引/检索辅助**（向量索引 = 加速召回） | 保留独立；memory 内部可选使用 vector 索引 |
| `ai.retrieve`（线性 top-k） | 被 `recall` **取代升级**（任务感知/层级/预算/instruction） | `ai.retrieve` 保留为底层原语（recall 内部可调用）；用户面推荐用 `recall` |
| `ai.embedding`（嵌入生成） | recall 的**底层依赖**（query/doc 向量生成） | 保留；recall 内部调用 embedding 生成向量 |

### 1.3 单一权威源原则

- **记忆状态的单一权威** = `memory` 值对象（分层/条目/元数据全在内部）
- **召回决策的单一权威** = `recall` 操作返回的 `recall_result`（含所用 instruction/成本/relevance）
- **向量索引的单一权威** = `memory` 内部索引（非独立对象）
- **LLM 调用记录** = 既有 journal 机制（recall 内 LLM 调用自动入 journal）

---

## 二、MEM —— `memory` 值类型设计

### 2.1 类型形态

**一等内置值类型**（同 knowledge/vector 地位）：
- 可构造（`memory.new()`）
- 多实例（每个 `memory` 对象独立）
- 可 `save_state` / `load_state`（完整序列化/水化）
- 可变容器（引用语义）——条目可增/删/改；**条目值 = 深克隆快照**（同 knowledge）

### 2.2 分层模型（MEM-1）

```
memory
├── working_set    （工作集/寄存器层——直接进 LLM 上下文的片段）
├── session        （会话层——当前 run/会话内的中间记忆）
├── knowledge      （知识层——已验证/稳定的长期记忆）
└── long_term      （长时层——持久/归档/低活跃记忆）
```

**每层属性**：
- `capacity`（容量上限，条数或总 token 估计）
- `access_cost`（语义标注：working=0 / session=1 / knowledge=2 / long_term=3）
- 条目结构：`{key, value, tier, vector?(可选), metadata{}}`

**层级操作**（一等确定性操作）：
- `mem.promote(key, to_tier)` —— 条目提升（e.g., session → knowledge）
- `mem.demote(key, to_tier)` —— 条目降级（e.g., working → session）
- `mem.tier(key)` —— 查询条目所在层
- `mem.tier_size(tier)` —— 某层条目数
- `mem.tier_keys(tier)` —— 某层所有键

**容量管理**（MEM-3）：
- `mem.set_capacity(tier, n)` —— 设置层容量上限
- 超容量时的处理：`working_set` 满 → 最旧 demote 到 `session`；其余层满 → 拒绝写入（fail-fast）

### 2.3 生命周期（MEM-2）

| 操作 | 语义 | 对应 knowledge 面 |
|------|------|------------------|
| `mem.encode(key, value, tier)` | 登记新条目（深克隆快照 + 可选 vector 索引） | `store`（无验证门——memory 不需 check） |
| `mem.consolidate(policy)` | 巩固：按策略批量处理（如 session → knowledge + 合并相似条目） | 新增（knowledge 无此操作） |
| `mem.prune(policy)` | 遗忘：按策略删除低价值条目（如 long_term 中超过 N 时间未访问） | 新增 |
| `mem.retrieve(key)` | 查询当前值（深克隆快照返回） | `get` |

**consolidate policy**（结构化 dict）：
```python
{"from_tier": "session", "to_tier": "knowledge", "min_age_events": 5}
```

**prune policy**：
```python
{"tier": "long_term", "max_age_events": 100, "min_access_count": 1}
```

### 2.4 完整性 + 内容寻址（MEM-4）

- **内容哈希**：条目值 `to_native()` → JSON 序列化 → SHA-256 → `content_hash`
  （tamper-evident：修改后哈希变更，`mem.verify(key)` 可检测）
- **provenance**：`{source, round, timestamp_event_seq}`（来源/轮次/事件序号）
- **append-only 变更链**：同 knowledge（`events` 列表，每操作追加事件）

### 2.5 完整环境快照（MEM-5）

`save_state` / `load_state` 已覆盖变量面（P6 落地）。MEM-5 要求扩展到
**world/mode/话语状态**。当前评估：
- 现有 `save_state` 保存 = 全局变量（含 memory 实例——因为 memory 是一等值）
- 扩展面 = 引擎状态（注册表/模块表/LLM 配置）——**远期**，与 P7 进程隔离
  的"完整进程状态快照"交叠（当前不实施，登记为远期项）

**B3 裁定**：MEM-5 在 Phase B 范围内 = "memory 实例完整序列化/水化"（已自然满足
——memory 是一等值类型，`to_native`/`serialize` 完整覆盖）。引擎级完整快照归远期。

### 2.6 语言面（IBCI 用户代码视角）

```ibci
# 构造
memory mem = memory.new()

# 分层登记
mem.encode("fact_1", "地球是圆的", "knowledge")
mem.encode("note_1", "用户偏好简洁回复", "session")

# 查询
str val = mem.retrieve("fact_1")

# 层级操作
mem.promote("note_1", "knowledge")
str t = mem.tier("note_1")  # → "knowledge"

# 容量
mem.set_capacity("working_set", 10)
int n = mem.tier_size("working_set")

# 生命周期
mem.consolidate({"from_tier": "session", "to_tier": "knowledge", "min_age_events": 5})
mem.prune({"tier": "long_term", "max_age_events": 100})

# 完整性
str h = mem.content_hash("fact_1")
bool ok = mem.verify("fact_1")
```

### 2.7 公理层（MemoryAxiom）

- 方法面：encode / retrieve / promote / demote / tier / tier_size / tier_keys /
  set_capacity / consolidate / prune / content_hash / verify / keys / len / export
- 运算符面：无（操作 = 显式方法调用，同 knowledge）
- 转换：memory → str（repr）/ memory → any（透传）
- 值语义：容器可变（引用），条目值冻结（深克隆快照）

---

## 三、REC —— `recall` 操作设计

### 3.1 定位

`recall` = **任务感知地从 memory 组装 LLM 上下文**——非仅向量 top-k，而是
"给定任务/目标/预算/instruction → 从分层记忆中选出最相关片段 → 返回排序+
成本标注的工作集"。

**与 `ai.retrieve` 的关系**：
- `ai.retrieve` = 底层原语（给定 query vector + corpus vectors → top-k）
- `recall` = 高层操作（给定 task goal → 内部决定从哪层取、用什么 instruction、
  多少预算 → 调用 embedding + retrieve → 返回结构化结果）

### 3.2 语言面

```ibci
# 基本召回（从 memory 中按目标选取最相关片段）
recall_result r = mem.recall("查找关于 Python 性能优化的知识",
    scope = "knowledge",
    budget = 4096,          # token 预算
    k = 5)                  # 最大片段数

# 指令条件化召回（REC-1 + REC-6：instruction 仅 query 侧）
recall_result r2 = mem.recall("查找关于用户投诉处理策略",
    scope = "session",
    budget = 2048,
    k = 3,
    instruct = "retrieve passages that describe customer complaint handling strategies")

# 层级召回（REC-2：coarse-to-fine）
recall_result r3 = mem.recall("查找关于分布式系统的设计模式",
    scope = "all",           # 跨层
    budget = 8192,
    k = 10,
    hierarchical = True)     # 启用层级下钻
```

### 3.3 `recall_result` 值类型

```ibci
# recall_result 字段：
#   fragments: list[recall_fragment]  —— 排序后的召回片段
#   cost_tokens: int                    —— 本次召回总 token 成本
#   instruction: str                    —— 所用 instruction（审计面）
#   scope: str                          —— 实际搜索范围
#   dim: int                            —— 嵌入维度（MRL）

# recall_fragment 字段：
#   key: str            —— memory 条目键
#   value: any          —— 片段内容
#   score: float        —— 相似度分数
#   tier: str           —— 来源层
#   relevance: float    —— relevance-per-token（成本效率）
```

### 3.4 REC-6：query/doc 不对称内核保证 + MRL 维度轴

**设计**（需求单 §2b day-0 锚点）：

| 面 | 语义 | 实现 |
|----|------|------|
| `instruct` 参数 | **仅应用于 query 嵌入**（document 侧裸嵌入且缓存） | `memory.encode` 时 doc 侧嵌入 = 裸文本 → 缓存向量；`recall` 时 query 侧 = `Instruct: {instruct}\nQuery:{query}` → 调 embedding |
| 不对称保证 | **内核保证**（非调用方记忆） | `EmbeddingService.embed(texts, side="query"|"doc", instruct=..., dim=...)`：side 决定 instruction 是否前置 + 是否命中 doc 缓存 |
| MRL 维度 | 输出维度 32-1024 可自定义 | `dim` 参数控制截断维度（粗召回 = 小维省成本，精召回 = 大维） |

**`ai.embed` 扩展**（新参数面）：
```python
def embed(self, text, side="doc", instruct=None, dim=None):
    """
    side="doc"：裸嵌入（可缓存）
    side="query"：instruct 前置（`Instruct: {instruct}\nQuery:{text}`）
    dim：MRL 截断维度（None = 全维度）
    """
```

**缓存策略**：
- doc 侧向量缓存在 memory 条目内（`entry.vector`）——encode 时一次性计算
- query 侧不缓存（每次 recall 重新计算，因为 instruction 可能不同）

### 3.5 层级召回（REC-2）

`hierarchical=True` 时：
1. 粗召回（低维 dim=64，从 long_term/knowledge 层取 top-2k）
2. 精召回（高维 dim=512，从粗召回结果中取 top-k）
3. 每层预算分配（按层容量比例）

### 3.6 经验证召回（REC-3）

`verify=True` 时（recall 参数）：
- 每个召回片段过确定性校验（出处/provenance 非空 + 一致性）
- 未过校验的片段标记 `verified=False`（不丢弃，调用方可决策）

### 3.7 成本模型（REC-4）

每次 recall 返回 `cost_tokens`（= fragments 总 token 估计）+ `relevance`（per-fragment
relevance-per-token = score / token_count）。

---

## 四、实施批次规划

| 批次 | 内容 | 依赖 | 预估复杂度 |
|------|------|------|-----------|
| **B4**（最先落地） | REC-6 基础：`ai.embed` 扩展 side/instruct/dim 参数 + doc 缓存 | 无（现有 embedding 通道直接扩展） | 低 |
| **B2a** | memory 值类型基础：`IbMemory` + `MemoryAxiom` + 注册 + encode/retrieve/keys/len | B4（memory 条目用 vector 索引） | 中 |
| **B2b** | 分层模型：promote/demote/tier/set_capacity/tier_size | B2a | 中 |
| **B2c** | 生命周期：consolidate/prune + 完整性 content_hash/verify | B2b | 中 |
| **B5a** | recall 基础：`mem.recall` 方法（线性 top-k 从 memory 中选取） | B2a | 中 |
| **B5b** | recall 进阶：hierarchical + verify + cost model + recall_result 值类型 | B5a | 高 |
| **B3** | MEM-5：save_state 覆盖验证（memory 实例序列化/水化） | B2c | 低 |
| **B6** | OBS-1..3：recall 决策审计（自动入 journal）+ memory 快照 | B5b | 低 |

---

## 五、设计哲学对照

| 原则 | 对照 |
|------|------|
| 单一权威源 | memory 状态单一权威 = 值对象内部；recall 结果 = recall_result；不双写 |
| 统一设计语言 | memory 方法面 = 值对象方法（同 knowledge/dict 约定）；recall 是 memory 方法（非独立模块）|
| 设计思路统一 | 深克隆快照 / 事件序号 / 层级容量管理 = 同 knowledge 先例机制同构 |
| 机制同构 | 注册模式 = knowledge/vector 先例；模块面 = ai 模块先例（embed 扩展）|
| 配合模式统一 | memory ↔ vector（条目索引）/ memory ↔ ai.embedding（向量生成）/ recall ↔ journal（审计）|
| 一致性先于便利 | 不引入独立"memory 模块"——memory 是值类型，recall 是其方法（非 ai 模块面）|
| 命名粒度统一 | 一个概念一个名字：`memory`（类型）/ `recall`（操作）/ `recall_result`（返回值）|

---

## 六、硬约束对照

- **9 项 VM 不变量**：memory 是纯值类型（无 LLM 调用/无阻塞/无调度器交互）→ 不变量
  ④⑧⑨ 不涉及；recall 内部调 embedding（经 LLM 通道 ④）→ 走既有 `ai.embedding` 面
- **工作模式定论**：无 compat shim（knowledge 保留独立，不合并进 memory）；无胶水
  （recall 是 memory 方法，非跨模块字符串拼接）；无 tricky（层级操作是显式方法调用）
- **每批全量零回归门**：是

---

## 七、开放问题（Phase B 设计确认）

1. **memory 的 vector 索引是必需还是可选？**
   推荐 = 可选（`encode` 第 4 参 `vector` 可选）。无向量的 memory 条目仍可
   retrieve（按 key），但 recall 需要向量才能做相似度排序。
2. **recall 是 memory 方法还是 ai 模块面？**
   推荐 = memory 方法（`mem.recall`）——单一权威源（记忆状态在 memory 内）；
   ai 模块只提供底层 embed + 向量生成。
3. **consolidate/prune 策略的"时间"基准是什么？**
   推荐 = 事件序号（memory 内部单调计数器），非墙钟——确定性可复现（同 knowledge seq）。
4. **memory 条目值类型限制？**
   推荐 = 可深克隆值类型（同 knowledge：str/int/float/list/dict/knowledge 等；
   函数/behavior = 拒绝，fail-fast）。
5. **recall 的 LLM 调用是否需要？**
   当前设计 = 不需要（recall 是纯向量检索 + 确定性排序，不调 LLM）。
   未来可扩展为"LLM 辅助 reranking"（Phase C SELF-1 域），非当前范围。
