# _p2_world_model_kb_design — P2 R-B 世界模型 KB（演化 knowledge 为一等三元组知识图谱）机制设计

> **性质**：临时任务控制文档（设计阶段），P2 批次的**设计单点真理**。落地后删除，
> 最终内容按治理收敛入 `docs/`（16_knowledge_system 主文档 + KNOWN_LIMITS）。
> 上游需求权威源 = `_world_model_db_design.md`（§6 P2 + §7 决策点 #1/#6）+
> 试用方 v2 需求单 §3 规格 + R-B 节（`ibci-trial/docs/REQ_IBCI_WORLD_MODEL_INTEGRATION.md`，
> D-ISO 只读）。

---

## 0. 一句话设计论点

> **P2 = 把 `knowledge` 值就地演化为世界模型 KB：一个值、一个审计序号、三个正交数据面
> ——entries（通用知识登记面，既有契约零改动）/ facts（append-only 事实日志，KB 单一
> 权威源）/ vocab（治理词表：words/relations/worlds allowlist）；8 倒排索引全部**派生**
> （增量维护 + 水化重建，永不独立存储/序列化）；事实准入 = 内建确定性治理门（词表
> allowlist，零 LLM——knowledge check 门纪律的图平面落法）；27 个图/词表/审计方法面
> 全确定性（D1），fact_id = KB 单调序号（字节可复现）。**

**为什么"就地演化 knowledge"而非新类型**（决策点 #1 裁定）：
① 单点真理——KB = IBCI 的 D 纸带，knowledge 公理文档明写"语言自动机的知识层/D 纸带"，
另立 `world_model` 平行类型 = 同一概念两处权威（design-philosophy §一 碎片化）；
② 消费面轻（本批实证审计：core 消费方 = 语义层 check 纯度检查 1 处 + serializer +
deep_clone + 类型注册；无重用户面——entries 平面契约保持不变则零破坏）；
③ 机制同构——append-only/审计序号/值冻结/验证门/序列化双面 knowledge 全部现成，
facts/vocab 平面复用同一序号与序列化通道（不发明新机制）。

---

## 1. 现状盘点（实证，2026-09-10 本批审计）

| 子件 | 现状 | 对 P2 的结论 |
|------|------|-------------|
| `knowledge` 值对象（IbKnowledge） | payload = {entries: {key: {value, check, check_name, provenance, events}}, seq}；store/get/amend/history/keys/len/export；条目值冻结（深克隆快照）；事件序号 = 引擎单调序号（确定性可复现） | **entries 平面原样保留**（通用登记契约）；**seq 复用为 KB 单一审计序号**（facts/vocab 事件同序——一个 KB 一条审计链） |
| `knowledge` 公理（KnowledgeAxiom） | 方法面 = store/get/amend/history/export/keys/len/cast_to；无运算符面 | **方法面扩展 27 个**（词表/事实/查找/对比/展开/审计——get_method_specs 单一来源，spec 自动绑定） |
| check 门（SEM_KNW_*） | store 的 check 须本模块显式函数引用 + 函数体零 LLM（编译期纯度门） | **entries 平面 check 契约不变**；facts 平面准入 = **内建治理门**（词表 allowlist，确定性零 LLM——同纪律不同机制面：entries 门 = 调用方谓词，facts 门 = KB 内建治理，两门各辖一面，非双通道） |
| serializer | _collect_knowledge 持久 entries+seq（值经实例池）；水化重建（check=None 边界 fail-fast） | **扩展持久 facts+vocab**（全原生结构直存）；**indexes 不入快照**（派生面，水化重建——单点真理：日志是权威，索引是视图） |
| deep_clone | knowledge 专分支（entries 值/事件递归克隆；check 引用共享边界） | **扩展克隆 facts/vocab**（原生结构深拷贝——防两个克隆共享事实日志被单方变异） |
| v30 真实数据 | axioms=451 条 {world,s,r,o}（无 id/source/status）；words=99；relation_types=51 裸名（governed_vocab 59 带语义）；word.relations×axioms 双写（34 条 only_in_axioms） | **facts 平面 = axioms 的权威落点**（补 id/source/status 目标态）；**word.relations 不再独立存储**（= by_subject 派生，根治双写）；治理词表元数据（semantics/transitive/multi_valued）= vocab 平面（决策点 #5：以 governed_vocab 为元数据权威） |

---

## 2. 设计决策（self-grill 全部分支已消解，无待用户项）

| # | 决策 | 裁定 | 依据 |
|---|------|------|------|
| D1 | **演化形态** | 就地演化 `knowledge`：一个值、一个 seq、三正交数据面（entries/facts/vocab）+ 派生索引 | 决策点 #1（不另立平行类型）+ design-philosophy §一（单一权威源）；三平面 = 三个不同概念（通用登记/事实日志/治理词表），各辖一面，非碎片化 |
| D2 | **facts 准入门** | **内建确定性治理门**：world/relation/s/o 全部须已注册（词表 allowlist）——add_fact 时机器强制，fail-fast；entries 平面 check 契约不变 | 治理 = KB 自身的元规则（放调用方写谓词 = 治理碎片化 + 每调用方重复造门）；零 LLM 确定性 = D1 铁律 + check 门纪律同构（登记门须确定性验证） |
| D3 | **索引** | 8 索引**派生**（增量维护于 add/retract/amend；水化时从 facts 重建；**永不序列化/独立存储**）：6 图索引（by_subject/by_object/by_relation/by_pair/by_triple/by_world = **active 视图**）+ 2 审计索引（by_source/by_status = **全日志视图**） | 设计 §3.1（单一权威源 + 全派生）；活跃/审计视图切分 = 墓碑语义的结构性保证（retracted 事实退出图平面、保留在日志平面） |
| D4 | **fact_id/UID** | = str(KB seq)（add 时刻的 KB 单调序号） | 确定性可复现（同操作序列 → 同 id → 字节一致）；全局唯一；可排序（序 = 登记序）；引擎单调序号先例（knowledge 审计序号） |
| D5 | **值域约束** | s/o = **str 且须为已注册词**（governed lexeme）；r = str 且须为已注册关系；world = str 且须为已注册世界；source/status = 自由 str（status 惯例 "active"/"retracted"） | v30 数据形态（s/o 全是词）+ 治理词表 allowlist 纪律；**边界**：结构化 o / R-E 自指事实（fact 指向语言自身构造）= 后续扩展面（届时裁定 o 值域放宽 + 词表自指条目），P2 不预置 |
| D6 | **墓碑/版本化** | retract(fact_id, reason) = status→"retracted" 事件（append-only，reason 强制）；amend_fact(fact_id, new_o, reason) = o 版本切换事件（原 o 留事件链）；图平面索引即时移除/更新，日志保留全史 | 试用方规格（删除=墓碑/版本化，保证可追溯）+ knowledge amend 纪律同构（reason 强制 + append-only + 审计链） |
| D7 | **方法面** | 27 方法（§3 面表）；**事实平面操作一律收 fact_id（str）、返回 KB 权威数据**（不接受调用方自持的 fact dict——防陈旧副本双真相）；命名与既有面零冲突（get≠get_fact / amend≠amend_fact / history≠history_fact / len≠fact_len） | design-philosophy §八（一个概念一个名字）+ §一（KB 是唯一权威读取口——数据不离开 KB 值） |
| D8 | **expand/compare = 纯派生** | expand(fact_id) = 事实 + 词结构(s/o) + 关系语义 + 世界上下文，按需推导**不存展开态**（多次调用逐字节一致）；compare(a,b) = {exact, contradiction, scale, same_word}（1/2/3/5 层；4 层语义相似归 P6 向量面） | 设计 §0（存定理不存证明）+ D1 确定性（展开态必须逐字节可复现——派生即复现） |
| D9 | **序列化/克隆** | 持久 entries+facts+vocab+seq（facts/vocab 全原生结构直存，同 quoted/run_result 纪律）；indexes 丢弃（水化重建）；deep_clone 克隆 facts/vocab 原生结构（深拷贝防共享变异） | 单点真理（快照 = 日志 + 词表 + 序号，可完整重建）+ 克隆独立性（可变容器值 = 引用语义，克隆须独立） |
| D10 | **诊断码** | 新增 KNW_VOCAB_UNREGISTERED（治理门：world/relation/word 未注册）/ KNW_FACT_DUPLICATE（同 (world,s,r,o) active 事实重复 add）/ KNW_FACT_NOT_FOUND（未知 fact_id 操作）/ KNW_FACT_RETRACTED（对 retracted 事实 retract/amend）；reason 空**复用 KNW_REASON_EMPTY**（同一概念"审计链须 reason"，单名） | 诊断码 = 精确触发面（catalog 登记 title+fix）；复用 = 单点真理（不新造同义码） |
| D11 | **transitive(s, r)** | 沿 active by_pair 链展开 r 关系传递闭包：返回**可达集**（含直接 length-1）list[dict]{s, r, o, via:[中间对象]}；仅对 transitive=True 的关系有效（非传递关系 = fail-fast KNW_VOCAB_UNREGISTERED? 不——新语义：**transitive 面仅接受已注册关系，非传递关系返回空 list**（无传递闭包 = 空，非错误——诚实语义）；小图链式 + visited 防环 | 试用方 §3.3-6；"小图链式即可，格式预留 Datalog 定点"（设计 §4）；空闭包 = 空 list 非 fail-fast（无传递性 ≠ 错误状态） |
| D12 | **P2 范围** | = KB 值 + 词表面 + 事实面 + 8 索引 + 7 查找 + 对比/展开 + 审计面 + 序列化/克隆 + 诊断码 + 测试。**不含**：load_kb 磁盘加载（P3）/ 确定性模式断言（P4）/ 工件加载（P5）/ 向量面/embed_search（P6）/ to_ibci 投影（P7） | 试用方 M1 = P2+P3+P4 联合达成；P2 独立可验收 = IBCI 脚本内注册词表 + add_fact + 7 查找 + 对比/展开 全确定性 |
| D13 | **批次划分（灵活规划）** | B1 地基（payload 三面 + 词表面 + add_fact/get_fact/facts/fact_len + 治理门 + 索引 + 序列化/克隆/to_native + 单测）→ B2 查询面（7 查找 + contradicts/transitive + expand/compare/same_word + 单测）→ B3 审计面（retract/amend_fact/source/history_fact + 墓碑/版本化 + e2e + harness 语料）→ B4 文档同步（16_knowledge_system 主文档 + catalog + KNOWN_LIMITS）+ 全量放行门 + 收尾 | 每批 = 受影响子集 + smoke 零回归 + commit + 落账；B1 独立可验证（地基稳了再上层） |

---

## 3. 方法面契约（27 方法；全确定性 D1 零 LLM）

> 类型签名按 IBCI spec 面（`_m(name, params, ret)`）；事实平面操作收 **fact_id**，
> 返回 KB 权威数据（dict/list 为 IBCI 值）。`null` = 未命中合法态（非错误）。

### 3.1 词表面（9）——治理 allowlist（KB 元规则）

| 方法 | 签名 | 语义 |
|------|------|------|
| `register_word` | (lexeme: str, gloss: str, is_set: bool, members: list, entries: dict) → void | 注册词（gloss 释义 / is_set 集合词 / members 成员 / entries = {world: {form, self_ref}} 跨世界词形 + 跨尺度自指）；已注册 = fail-fast（KNW_VOCAB_UNREGISTERED? 不——**已注册重复 = 语义错误，复用 KNW_FACT_DUPLICATE? 不——词表重复登记是新概念：fail-fast 消息 + KNW_VOCAB_UNREGISTERED 语义不符。裁定：词表重复 register = 幂等拒绝 fail-fast，诊断码 = 新增 KNW_VOCAB_EXISTS**（见 D10 补正） |
| `register_relation` | (type: str, semantics: str, transitive: bool, multi_valued: bool) → void | 注册关系类型（语义描述 / 传递性 / 多值性——矛盾判定与传递闭包的元数据） |
| `register_world` | (name: str, description: str, size_rank: int) → void | 注册世界（描述 / 尺度秩——跨尺度自指与对比层 3 的元数据） |
| `word` / `relation` / `world` | (str) → dict\|null | 词表查询（未注册 = null 合法态） |
| `words` / `relations` / `worlds` | () → list | 已注册名枚举（list[str]，确定性序 = 插入序） |

**D10 补正**：新增 5 码 = KNW_VOCAB_UNREGISTERED（事实/词表操作引用未注册项）/
KNW_VOCAB_EXISTS（词表重复注册）/ KNW_FACT_DUPLICATE / KNW_FACT_NOT_FOUND /
KNW_FACT_RETRACTED。

### 3.2 事实面（8）——append-only 日志（KB 单一权威源）

| 方法 | 签名 | 语义 |
|------|------|------|
| `add_fact` | (world, s, r, o, source, status: 全 str) → str（fact_id） | 登记事实（内建治理门：world/r/s/o 已注册 + 非重复 active；source/status 缺省 ""/"active"——store 先例"编译期声明最大参数列、运行期接受更少"） |
| `get_fact` | (fact_id: str) → dict\|null | 事实记录（{id, world, s, r, o, source, status, events}——权威形态含全事件链；未知 id = null） |
| `facts` | () → list[dict] | 全日志（含 retracted，status 字段自辨；确定性序 = seq 序） |
| `fact_len` | () → int | 事实计数（全日志） |
| `retract` | (fact_id, reason: str) → void | 墓碑（status→retracted；reason 强制非空；已 retracted = fail-fast KNW_FACT_RETRACTED；图索引即时移除） |
| `amend_fact` | (fact_id, new_o, reason: str) → void | o 版本化（new_o 须已注册词；reason 强制；原 o 留事件链 {seq, kind="amend", reason, new_o}；索引更新 by_object/by_triple/by_pair） |
| `source` | (fact_id: str) → str | 来源标记（审计"事实从哪来"；未知 id fail-fast KNW_FACT_NOT_FOUND） |
| `history_fact` | (fact_id: str) → list[dict] | 事件链（{seq, kind: "add"/"amend"/"retract", reason, new_o?}——append-only 全史） |

### 3.3 查找面（7）——图平面（active 视图，全确定性）

| 方法 | 签名 | 语义（试用方 §3.3 七查找） |
|------|------|------|
| `lookup_pair` | (s, r: str) → list[dict] | "s 经 r 指向什么"——by_pair[(s,r)] 全部 active 事实记录 |
| `exists` | (world, s, r, o: str) → bool | 事实存在吗（去重）——by_triple 成员检查（active） |
| `all_in_world` | (world: str) → list[dict] | 某 world 的全部 active 事实 |
| `by_source` | (source: str) → list[dict] | 某来源的全部事实（审计——全日志视图） |
| `by_subject` | (s: str) → list[dict] | 关于某词的全部 active 事实（**word.relations 的派生替代——根治双写**） |
| `contradicts` | (s, r, o: str) → bool | 矛盾检查：by_pair[(s,r)] 已有 active o'≠o 且关系非 multi_valued ⇒ 矛盾 |
| `transitive` | (s, r: str) → list[dict] | 传递闭包（仅 r 已注册且 transitive；返回可达集含直接，{s, r, o, via}；非传递关系 = 空 list） |

### 3.4 对比/展开面（3）——5 层对比的确定性 4 层 + 按需展开

| 方法 | 签名 | 语义 |
|------|------|------|
| `expand` | (fact_id: str) → dict | 按需确定性展开：{事实字段, subject: 词记录, object: 词记录, relation: 关系记录, world_ctx: 世界记录}——纯派生不存展开态，逐字节一致 |
| `same_word` | (a, b: str) → bool | 词同一性（层 5）：a == b 且均为已注册词（未注册 = false 非错误） |
| `compare` | (a, b: str（fact_id）) → dict | 对比（层 1/2/3/5）：{exact: (world,s,r,o) 全等, contradiction: 同 (s,r) 不同 o 且非 multi_valued, scale: "same"/"cross"（两事实 world 同/异——异 world = 不直接可比，由 size_rank 语境判定）, same_word: s 词同一性}；任一 id 未注册 = fail-fast KNW_FACT_NOT_FOUND |

> **层 4（语义相似）= P6 向量面**（`embed_search`——内容信号非判定，D1：判定仍走
> 1/2/3/5 确定性路径）。P2 的 compare 不含层 4 字段（不预置半成品）。

---

## 4. 数据形态（payload 与记录）

```
IbKnowledge payload = {
  "entries": {key: {value, check, check_name, provenance, events}},  # 既有通用登记面（零改动）
  "seq": int,                                                        # KB 单一审计序号（既有，facts/vocab 事件同序）
  "facts": {fact_id: {id, world, s, r, o, source, status,
                       events: [{seq, kind, reason, new_o?}]}},     # append-only 事实日志（权威）
  "vocab": {                                                         # 治理词表（权威）
    "words":    {lexeme: {lexeme, gloss, is_set, members, entries}},
    "relations":{type:   {type, semantics, transitive, multi_valued}},
    "worlds":   {name:   {name, description, size_rank}}},
  "indexes": {...},                                                  # 派生（8 索引；不序列化；水化重建）
}
```

**索引结构（派生，active 视图除非注明）**：
`by_subject {s: [id]}` / `by_object {o: [id]}` / `by_relation {r: [id]}` /
`by_pair {s: {r: [id]}}` / `by_triple {world: {s: {r: {o: [id]}}}}` / `by_world {world: [id]}` /
`by_source {source: [id]}`（全日志）/ `by_status {status: [id]}`（全日志）

**确定性不变量**：同注册/登记序列 → 同 fact_id（seq 派生）→ 同事实日志 → 同索引 →
同查询结果（逐字节可复现；零 LLM 全路径）。

---

## 5. 改动面清单

| # | 文件 | 改动 |
|---|------|------|
| 1 | `core/runtime/objects/primitives/knowledge.py` | payload 三面扩展 + 27 方法 + 索引维护辅助（_index_add/_index_remove/_rebuild_indexes）+ 治理门辅助 + to_native/serialize_for_debug 扩展 |
| 2 | `core/kernel/axioms/primitives/knowledge.py` | get_method_specs +27（单一方法面来源） |
| 3 | `core/base/diagnostics/codes.py` | +5 KNW_ 码 |
| 4 | `core/base/diagnostics/catalog.py` | +5 CodeInfo（title/fix） |
| 5 | `core/runtime/serialization/runtime_serializer.py` | _collect_knowledge 扩展（facts/vocab 直存，indexes 丢弃）+ hydration 扩展（重建 + 索引重建） |
| 6 | `core/runtime/objects/deep_clone.py` | knowledge 克隆分支扩展（facts/vocab 原生深拷贝） |
| 7 | 测试 | `tests/runtime/test_world_model_kb.py`（词表/事实/索引/门/序列化/克隆）+ `tests/e2e/test_world_model_kb_e2e.py`（用户面：注册 + 登记 + 7 查找 + 对比/展开 + 墓碑/版本化）+ 差分 harness 语料 +2（KB 事实 + 确定性查询面） |
| 8 | 文档 | `docs/syntax/16_knowledge_system.md` 主文档扩展（KB 三面 + 27 方法 + 墓碑/版本化 + 序列化/克隆边界）+ KNOWN_LIMITS（治理门边界：s/o 须注册词；非传递关系 transitive = 空） |

**公理层变更**（类型方法面扩展 + 诊断码新增）→ **全量 pytest 放行门**（B4）。
entries 平面契约零改动 → 既有消费方（语义层 check 纯度门 / 既有测试）零回归预期。

---

## 6. 验证与验收

### 6.1 测试计划（按批次）

| 批 | 判别测试 |
|----|----------|
| B1 | 词表注册 + 重复 fail-fast；add_fact 治理门（未注册 world/r/s/o → KNW_VOCAB_UNREGISTERED）；重复 active fact → KNW_FACT_DUPLICATE；fact_id = seq 确定性；get_fact/facts/fact_len；序列化 round-trip（facts/vocab 保真 + 索引重建等价）；deep_clone 独立（克隆 A add_fact 不影响克隆 B）；既有 knowledge 测试全绿（entries 面零回归） |
| B2 | 7 查找各判别（lookup_pair 多 o / exists 去重 / all_in_world / by_source 全日志 / by_subject 派生 / contradicts multi_valued 反例 / transitive 链 + 非传递空 + 防环）；expand 逐字节一致（两次调用相等）+ 全字段；compare 四层各判别（exact/contradiction/scale/same_word）；same_word 未注册 = false |
| B3 | retract（reason 强制 / 已 retracted fail-fast / 图视图即时排除 / 日志保留 / by_status 全日志）；amend_fact（o 版本切换 + 索引更新 + 事件链 + 原 o 可溯）；e2e 用户面脚本（mini 世界模型：注册 3 世界/5 关系/4 词 + 5 事实 → 7 查找 + expand + compare + retract 全断言）；harness 语料（KB 确定性查询 = 差分面） |
| B4 | 全量 pytest 放行门（公理层变更）+ 文档同步 + 残留扫描 |

### 6.2 验收对照（试用方 R-B 面）

- B1 加载：**P3 联合达成**（本批 = 活 KB 值 + 方法面；磁盘加载 = P3）——IBCI 内
  `register_*` + `add_fact` 即活 KB 查询（B1 验收 = 进程内活操作）
- B2 索引/查找：8 索引 + 7 查找全确定性零 LLM ✅（本批）
- B3 对比：5 层中 1/2/3/5 确定性 ✅（本批）；4 层 = P6（内容信号，非判定）
- B4 展开：expand 按需确定性、逐字节一致、不预存 ✅（本批）
- **双写根治**：word.relations = by_subject 派生（无独立存储面）✅（结构性保证）

## 7. 硬约束对照

- 工作模式定论：新设计 = 真设计（KB 三面 = 真实数据面，非兼容层/胶水——既有 entries
  面原样保留是**消费方契约**，非双通道：facts/vocab 各有唯一登记口 + 唯一读取口）；
  派生索引 = 确定性重建（无隐式字符串编码键——组合键用嵌套 dict 非拼接串）；
  fail-fast（治理门/重复/未知 id/reason 空全显式上抛）。
- design-philosophy：单一权威（KB 值 = D 纸带唯一权威；索引派生非权威）；机制同构
  （审计序号复用 knowledge seq；墓碑/版本化同构 knowledge amend 纪律；序列化双面
  同构 quoted/run_result 直存纪律）；命名统一（事实面操作收 fact_id 返回权威数据——
  无 get_fact_fresh 类同物多名）。
- D1（零 LLM）：全 27 方法纯内存确定性操作；治理门 = 词表成员检查（无 LLM 面）。
- 公理层纪律：全量 pytest 放行门 + WORKLOG 详尽记录变化前后。
