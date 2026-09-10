# 知识注册表（knowledge）

> IBCI 的一等内置值类型 `knowledge` = 语言自动机的**知识层**（D 纸带）：
> 机器持有的已验证知识是**类型化、门控、可审计**的。本页描述其地位、
> 语义不变量、条目模型、**世界模型 KB 面**（事实日志 / 治理词表 / 派生
> 索引）、方法面与惯用法。

## 地位：知识层（in-language knowledge database）

IBC 结构 = 稳定可靠的语言自动机。"验证过的知识从非确定性层毕业到确定性
层"是该自动机的核心动力学：新对象经 LLM 提案与确定性裁判验证后提交为
知识，后续查询不再经过 LLM 调用。`knowledge` 类型让该机制成为**语言级
机制**，而非外部 Python 里的约定。

三个系统支柱的分工：

| 支柱 | 职责 | 载体 |
|------|------|------|
| 意图（intent 体系） | 认知作用域（改写解释） | 既有（intent_context 等） |
| 模型 I/O（ai 模块） | LLM 调用 / embedding 调用（纯模型交互） | 既有 `ai` |
| **知识（本类型）** | **已验证知识的持有/查询/更正/审计** | **`knowledge`（一等值类型）** |

## 语义不变量（硬约束）

1. **`@~...~` 行为描述语句 = LLM 调用**，语义不因本类型改变。本类型**不
   提供**任何"查表命中则跳过 LLM"的语句内隐式路由——一切知识操作都是
   **显式程序操作**（普通值方法调用，代码可见、可审计、可测试）。
2. "先查知识库再决定是否调 LLM"是**用户的控制流**（显式 if/else），不是
   引擎的隐式行为（见下方惯用法）。
3. 验证门（check）必须是**确定性验证**：谓词体内含 LLM 调用或不透明
   （编译器无法证明其确定性）在**编译期**即拒绝（`SEM_KNW_CHECK_LLM` /
   `SEM_KNW_CHECK_OPAQUE`）——不纯度不可证明即拒绝，不做运行期探测兜底。
4. KB 面（事实日志/治理词表/索引/查找/对比/展开/审计）**全路径确定性
   零 LLM**：事实准入 = 内建治理门（词表 allowlist 机器强制）；查询/对比/
   展开 = 纯内存派生（同输入同输出，逐字节可复现）。

## 类型形态

- **一等内置值类型**：可构造（`k = knowledge()`）、可多实例（程序持有多个
  知识库，如 dict）、可传参/可存变量/可进 `save_state`。
- **混合语义**（显式声明）：
  - 知识库对象本身 = **可变值对象**（引用语义，同 dict：共享、传参、
    save_state 值语义）；
  - 条目值 = **冻结快照**——store 入时深克隆 + get 出时深克隆
    （"知识库可变，知识不可变"：修改取回值或登记后的原值，均不污染
    知识库，审计链不被引用陷阱污染）。

## 条目模型

```
键（str，显式）→ 条目 {
  value:      深克隆冻结快照
  check:      登记时的验证谓词（审计"经谁验证"）
  provenance: 来源标记（store 第 4 参，可选；知识出处——模块/文件/采集轮次等）
  events:     append-only 事件流 [ {seq, kind: store|amend, value, reason} ]
             （seq = 引擎事件序号，单调，可复现——非墙钟）
}
```

## 世界模型 KB 面（facts / vocab / 派生索引）

`knowledge` 值承载三个正交数据面，共享**单一审计序号**（KB 级单调 `seq`，
非墙钟——确定性可复现）：

| 面 | 内容 | 纪律 |
|----|------|------|
| **entries**（通用登记面） | `key → 条目`（见上"条目模型"） | 调用方 check 谓词门（编译期纯度） |
| **facts**（世界模型事实日志） | `fact_id → {id, world, s, r, o, source, status, events}` 的三元组事实（`(world, s, r, o)`） | append-only；**内建治理门**（词表 allowlist）；`fact_id = str(seq)`（确定性） |
| **vocab**（治理词表） | `words`（`{lexeme, gloss, is_set, members, entries[world→{form,self_ref}]}`）/ `relations`（`{type, semantics, transitive, multi_valued}`）/ `worlds`（`{name, description, size_rank}`） | allowlist 元规则：关系 `transitive` 驱动传递闭包、`multi_valued` 驱动矛盾判定；词 `entries` 承载跨世界词形 + 跨尺度自指（`self_ref`） |
| **indexes**（8 倒排索引） | `by_subject / by_object / by_relation / by_pair(s,r) / by_triple(world,s,r,o) / by_world / by_source / by_status` | **派生面**——日志是权威、索引是视图：增量维护 + 构造/水化确定性重建，永不独立序列化 |

**索引视图切分**：6 图索引（`by_subject`…`by_world`）= **active 视图**
（仅 `status == "active"` 事实；`by_pair`/`by_subject` 按三元组规格为
**world 无关**键——world 维经 `all_in_world` / `exists`（`by_triple`）表达）；
`by_source` / `by_status` = **全日志视图**（含墓碑）。

**事实记录形态**（`get_fact` / `facts` / 各查找返回的权威记录）：

```
{ id, world, s, r, o, source, status,
  events: [ {seq, kind: add|amend|retract, reason, new_o?} ] }   # append-only 全史
```

## 方法面

**通用登记面**（entries）：

| 方法 | 语义 | 纪律 |
|------|------|------|
| `k.store(key, value, check, provenance?)` | 登记（首次写入） | 引擎求值 `check(value)`：假 = 运行期错误 `KNW_CHECK_REJECTED`；键已存在 = `KNW_KEY_EXISTS`（"登记"与"更正"机器强制区分）；`provenance`（可选，来源标记）入条目，经 export/history 可观测 |
| `k.get(key)` | 查询当前值 | 未登记 → `null`（合法状态非错误）；返回深克隆快照 |
| `k.amend(key, new_value, reason)` | 更正 | `reason` 强制非空（`KNW_REASON_EMPTY`）；新值再过 check 门；append-only（原值保留于事件流，当前值指针切换） |
| `k.history(key, kind?)` | 审计 | 事件序列 `list`（元素为 `{seq, kind, value, reason}` dict）；未登记 → 空 list；`kind`（可选，"store"/"amend"）过滤事件类型，缺省 = 全事件 |
| `k.export()` | 整库导出 | 返回 `dict`：键 → `{value, check_name, provenance, events}`（审计链全量）；值 = 快照深克隆（防导出引用污染活库）；供整库序列化/检视/迁移 |
| `k.keys()` / `k.len()` | 枚举键 / 计数 | `list[str]` / `int`（容器约定与 dict 同构） |

**词表面**（治理 allowlist——KB 元规则；全确定性零 LLM）：

| 方法 | 语义 | 纪律 |
|------|------|------|
| `k.register_word(lexeme, gloss, is_set, members?, entries?)` | 注册词 | `members`（缺省 `[]`）= 集合词成员；`entries`（缺省 `{}`）= 跨世界词形 `{world: {form, self_ref}}`；重复注册 = `KNW_VOCAB_EXISTS`；参数形态非法 = `KNW_VOCAB_MALFORMED` |
| `k.register_relation(type, semantics, transitive, multi_valued)` | 注册关系类型 | `transitive` / `multi_valued` = 传递闭包 / 矛盾判定的元数据；重复 = `KNW_VOCAB_EXISTS` |
| `k.register_world(name, description, size_rank)` | 注册世界 | `size_rank`（int）= 尺度秩（跨尺度对比/自指元数据）；重复 = `KNW_VOCAB_EXISTS` |
| `k.word(lexeme)` / `k.relation(type)` / `k.world(name)` | 词表查询 | 未注册 → `null`（合法态非错误） |
| `k.words()` / `k.relations()` / `k.worlds()` | 词表枚举 | `list[str]`（确定性序 = 插入序） |

**事实面**（append-only 事实日志——KB 单一权威源）：

| 方法 | 语义 | 纪律 |
|------|------|------|
| `k.add_fact(world, s, r, o, source?, status?)` | 登记事实，返回 `fact_id` | **内建治理门**：world/relation/s/o 须已注册（`KNW_VOCAB_UNREGISTERED`）；同 `(world,s,r,o)` 已有 active 事实 = `KNW_FACT_DUPLICATE`（去重机器强制）；`source`（缺省 `""`）/ `status`（缺省 `"active"`） |
| `k.get_fact(fact_id)` | 事实记录（权威形态含全事件链） | 未知 id → `null`（合法态） |
| `k.facts()` / `k.fact_len()` | 全日志 / 计数 | 含墓碑（`status` 自辨）；确定性序 = seq 序 |
| `k.retract(fact_id, reason)` | 墓碑（`status → "retracted"`） | `reason` 强制非空（`KNW_REASON_EMPTY`）；已墓碑再操作 = `KNW_FACT_RETRACTED`；图索引即时移除、日志保留全史；**恢复语义 = 登记新事实**（append-only：不复活的版本是新事实） |
| `k.amend_fact(fact_id, new_o, reason)` | o 版本化 | 新 o 须已注册词（治理门）；`reason` 强制；原 o 留事件链（`new_o` 字段可溯）；索引 `by_object`/`by_triple` 切换 |
| `k.source(fact_id)` | 来源标记（审计） | 未知 id = `KNW_FACT_NOT_FOUND` |
| `k.history_fact(fact_id)` | 事件链（append-only 全史） | 未知 id = `KNW_FACT_NOT_FOUND`（事实面严格语义——区别于 entries 面 `history` 的"未登记 = 空 list"） |

**查找面**（图平面，active 视图，全确定性零 LLM——七查找）：

| 方法 | 语义 |
|------|------|
| `k.lookup_pair(s, r)` | "s 经 r 指向什么"——`by_pair[(s,r)]` 全部 active 事实（确定性序 = seq 序；空 list 合法） |
| `k.exists(world, s, r, o)` | 事实存在吗（去重）——`by_triple` 成员检查（含 world 维） |
| `k.all_in_world(world)` | 某 world 的全部 active 事实（world 维视图） |
| `k.by_source(source)` | 某来源的全部事实（审计——全日志视图） |
| `k.by_subject(s)` | 关于某词的全部 active 事实（**词关系的派生替代**——词关系从不独立存储，根治双写真相） |
| `k.contradicts(s, r, o)` | 矛盾检查：同 `(s,r)` 已有 active `o'≠o` 且关系非 `multi_valued` ⇒ 矛盾；关系未注册 = `KNW_VOCAB_UNREGISTERED` |
| `k.transitive(s, r)` | 传递闭包：沿 active `by_pair` 链展开 `transitive` 关系的可达集（含直接；每项 `{s, r, o, via}`——`via` = 中间对象链；BFS 防环；确定性序 = BFS 发现序）；**非传递关系 = 空 list**（无传递闭包 = 空，非错误） |

**对比/展开面**（5 层对比的确定性 4 层 + 按需确定性展开）：

| 方法 | 语义 |
|------|------|
| `k.expand(fact_id)` | 按需确定性展开：`{事实字段, subject/object: 词记录, subject_form/object_form: 该事实世界的跨世界词形, relation: 关系记录（含 semantics/transitive/multi_valued）, world_ctx: 世界记录}`。**纯派生不存展开态**——多次调用逐字节一致（存定理不存证明；展开态 = 日志 + 词表的确定性函数） |
| `k.same_word(a, b)` | 词同一性（对比层 5）：`a == b` 且均为已注册词（未注册 = `false` 非错误） |
| `k.compare(a, b)`（fact_id 对） | 对比 4 层：`{exact: (world,s,r,o) 全等（层 1）, contradiction: 同 (s,r) 不同 o 且非 multi_valued（层 2）, scale: "same"/"cross"（层 3——异 world 不直接可比，`size_rank` 语境判定）, same_word: 主语词同一性（层 5）}`；未知 id = `KNW_FACT_NOT_FOUND`。**层 4（语义相似）归向量面**（内容信号非判定——判定恒走确定性路径） |

**向量面**（词嵌入——内容信号非判定；D1 判定恒走图平面确定性路径，与
`compare` 层 4 / `narrow_model.score` 同定位）：

| 方法 | 语义 | 纪律 |
|------|------|------|
| `k.set_embedding(word, vec)` | 给已注册词挂/换嵌入（可变面） | 词须已注册（`KNW_VOCAB_UNREGISTERED`）；维度须与既有嵌入一致（`KNW_EMB_DIM_MISMATCH`）；`vec` = `vector` 值 |
| `k.embedding(word)` | 取词嵌入（`vector` 值） | 词未注册 = `KNW_VOCAB_UNREGISTERED`；未挂 = `KNW_EMB_NOT_SET` |
| `k.has_embedding(word)` | 是否已挂嵌入（`bool`） | 未挂 = `false`（合法态非错误） |
| `k.embedding_dim()` | 嵌入维度（`int`） | 嵌入面空 = `KNW_EMB_NOT_SET`；维度全一致（set_embedding 门保证） |
| `k.embed_search(query, k)` | 全嵌入词暴力 cosine 取前 `k`（**内容信号**） | `query` = `vector` 值；返回 `list` 每项 `{word, score}`（score = cosine 越大越相似）；排序键 `(−score, word)` 升序（score 降序 + 平手按词名，确定性 tie-break）；`k` 非正整数 = `KNW_EMB_SEARCH_INVALID`，`k` 超嵌入词数 = 返回全部（截断非违约）；嵌入面空 = `KNW_EMB_NOT_SET` |

- **内容信号非判定**：`embed_search` 返回相似度 rank/分数（异常检测 / 语义对比
  用），从不做判定（判定走图平面 `contradicts`/`transitive`/`compare` 确定性
  路径）。嵌入只作**内容信号**（向量平面），与窄模型 `score` 同定位。
- **暴力 cosine**（小规模；无索引常驻服务——不可变工件加载，非常驻）；ANN/
  FAISS 派生加速 = 后置（磁盘格式预留）。
- **query 来源**：按词检索先 `k.embedding(word)` 取向量；任意文本经 `ai.embed`
  取向量（`ai.set_embedding_mock` 提供确定性 mock——零 LLM）。
- **持久化**：嵌入面入 KB artifact v2 `vector` 节（`{dim, embeddings}`，内容
  寻址；见 §11.12）；v1 artifact（无 vector 节）向后兼容加载（嵌入面空）。

**投影面**（`to_ibci`——KB 当前态的确定性 IBCI 代码派生视图；非存储层）：

| 方法 | 语义 | 纪律 |
|------|------|------|
| `k.to_ibci()` | 导出 KB 当前态的确定性 IBCI 源码（派生视图） | 只读导出（无修改面/无新诊断码）；返回 `str` |

- **派生视图非存储层**：投影 = 活 KB 当前态（全词汇 + 全事实当前 o/source/
  status，active+retracted 均含）的 IBCI 源码——可经执行重建等价 KB，替代
  lossy 静态投影器（全词汇/全事实无丢失、无魔法默认、按需派生免全量重编译）。
  单一权威源 = 活 KB / artifact；代码投影从日志派生，绝不独立存储。
- **确定性**：词汇序 = KB 自身插入序（worlds/relations/words）；事实序 =
  fact_id（str(seq)）序；字面量序列化规范化（dict 键排序 + str 转义）→
  **同 KB 逐字节一致**（派生视图可复现）。
- **当前态非全史**：不回放 amend/retract 事件史（amend 原始 o 不可恢复——事件
  链只存 new_o）；投影重建当前态，历史归 fact 日志权威面 + artifact。
- **对拍**：投影代码经执行重建 KB，其查询结果（lookup_pair/exists/by_subject/
  contradicts/transitive/facts 语义字段）与活 KB 一致（add-only KB 的 fact_id
  亦一致）。

## 惯用法（canonical idiom）

"先查知识库再决定是否调 LLM"——用户控制流的确定性验证门模式：

```python
knowledge kb = knowledge()

func verify(str x) -> bool:
    # 确定性验证（文本/格式/长度检查；不得含 LLM 调用）
    return x.len() > 0

key = "term:" + user_input
any known = kb.get(key)
if known == None:
    # 未命中：走 LLM 提案 + 确定性验证 + 登记
    str candidate = @~ 给出: user_input 的定义 ~
    if verify(candidate):
        kb.store(key, candidate, verify)
        answer = candidate
    else:
        answer = candidate   # 验证不过：不登记，直接答复
else:
    answer = (str)known      # 命中：0 次 LLM 调用（机器持有的知识）
```

要点：
- check 谓词 = **本模块显式定义的函数**（编译器遍历其函数体证明确定性）；
- 登记前验证与登记门是**同一个谓词**（提案先自证，过门才提交）；
- 命中路径完全不调用 LLM——这就是"用得越久越确定"的语言级落地。

## 状态恢复（save_state / load_state）

- 知识库经 `ihost.save_state` / `load_state` 持久化：条目值、审计事件流、
  事件序号保真；**KB 面**（facts 事实日志 + vocab 治理词表 + 单一审计序号）
  全保真；save 后的变更在 load 后丢弃（状态回退到快照）。
- **派生索引不入值快照**（日志是权威、索引是视图）：水化时从事实日志
  确定性重建——同日志 → 同索引（可复现，无视图漂移面）。
- **边界**：`load_state` 为**同入口程序 / 同会话**的状态恢复机制（快照的
  变量身份绑定编译期符号表；跨入口文件的快照恢复不受支持）。
- **边界**：验证谓词引用**不入值快照**（函数非值快照）。恢复后条目仍可
  `get`/`history`，但 `amend` 因谓词引用丢失而 fail-fast
  （`KNW_CHECK_REJECTED`）——需重新 `store` 登记。KB 面不受此边界影响
  （治理门内建于 KB，不依赖调用方谓词）。

## 磁盘面（内容寻址 artifact，`world_model` 模块）

KB 面（facts/vocab/seq）可经 `world_model` 模块持久化为**内容寻址 artifact**
（单 JSON 文件；详见 §11 模块 `11.12`）：

```ibci
import world_model
str h = world_model.save_kb(kb, "./kb.json")   # 保存：返回 content_hash（钉扎基准）
kb2 = world_model.load_kb("./kb.json")         # 加载：水化为活 KB 值（可增量）
```

- **artifact 格式**（共享契约）：`{ schema_version, content_hash, facts[seq
  序], vocab{words,relations,worlds}, seq }`。JSON 是**传输格式**——运行时
  模型 = 加载后水化的活 KB 值，非文件本体。
- **内容即身份**：`content_hash` = canonical 载荷（facts/vocab/seq 键排序 +
  紧凑分隔规范形态）的 sha256 全摘要。同内容不同文件排版（缩进/键序）= 同
  hash；`save_kb` 返回值即钉扎/审计基准（调用方可 hash 比对验证落盘内容）。
- **加载三级验证门**（fail-fast 不静默降级）：结构门
  （`KNW_KB_ARTIFACT_MALFORMED`）→ 版本门（`KNW_KB_SCHEMA_VERSION`，无自动
  迁移）→ 完整性门（canonical 重算 hash ≠ 所载 `content_hash` =
  `KNW_KB_HASH_MISMATCH`，篡改/损坏）。文件缺失/沙箱拒绝复用 `fs` 面诊断。
- **加载 = 活 KB**：水化后可查询（全方法面）+ 可增量 `add_fact`（治理门/
  去重门照常生效；派生索引经构造入口从事实日志确定性重建）——**无需重
  编译**（对照静态投影 stopgap：KB 增长不再触发全量重编译）。
- **通道分工**：artifact 只辖 KB 面（entries 面不入——其持久化通道 =
  `save_state` 全状态面，两通道各辖其面）；加载的 KB 值 entries 面为空。

## 并发语义

知识库对象是值对象：同一实例可被多线程/多协程共享（引用语义，同 dict）。
**只读共享**（`get`/`history`/`keys`/`len`）可并发；**写操作**（`store`/
`amend`）的并发互斥由用户的控制流纪律保证（与 dict 等容器同纪律——语言
不提供内置锁面）。

## 不做什么（边界）

- 不做向量检索面（embedding 检索走 `ai.retrieve`；知识条目查询 = 显式键，
  无语义相似度隐式路由；KB 对比层 4 语义相似同属向量面——内容信号非判定）。
- 不做谓词引用跨快照恢复（见上；登记与快照是两个面）。
- 不做隐式路由/短路（语义不变量 1）。
- **KB 面值域边界**：事实的 `s` / `o` 为**已注册词的 lexeme**（str，治理
  allowlist）；结构化对象 / 自指事实（fact 指向语言自身构造）为后续扩展面，
  当前 `add_fact` 治理门拒绝未注册词（`KNW_VOCAB_UNREGISTERED`）。
- **KB 面不存展开态**（`expand` 纯派生）；**索引不独立存储**（派生视图，
  水化重建）；**词关系不独立存储**（`by_subject` 派生替代——无
  `word.relations` 双写面）。
- **展开/对比结果的字节对比**经 JSON 序列化路径（`json.stringify(a) ==
  json.stringify(b)`）或逐字段对比——容器 `==` 为恒等语义（见
  `docs/KNOWN_LIMITS.md` §10.5）。
