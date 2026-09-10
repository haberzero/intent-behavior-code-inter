# P3 磁盘格式（KB artifact）设计单点真理

> 状态：设计定稿（2026-09-10，P3 批次开工）。主线设计 = `_world_model_db_design.md`
> §3.4/§6-P3；试用方验收 = R-B B1（`load_kb(path)` 后活查询 + 增量 100 事实可用，
> 无需重编译）。本文 = P3 机制裁定（self-grill 全分支消解记录）。P3 收束后删除。

## 1. 面定位（机制同构裁定）

**磁盘面 = kernel-native 模块 `world_model`**（同 `fs` 注册模式），两个自由函数：

| 函数 | 语义 | 静态面 |
|------|------|--------|
| `world_model.load_kb(path) -> knowledge` | 加载 artifact → 验证 → 水化为**活 KB 值**（可查询 + 可增量 add_fact） | `(str) -> knowledge` |
| `world_model.save_kb(kb, path) -> str` | 序列化 KB 面 → 计规范哈希 → 写 artifact；返回 `content_hash`（审计/钉扎面） | `(knowledge, str) -> str` |

**为何是模块而非值方法**（Q1 消解）：
- `load_kb` 产生值——值方法面无法承载（无接收者）；`knowledge.load_kb` 类级静态调用
  面 IBCI 值类型不存在（构造器仅零参 `_create_blank` 机制）。
- 磁盘 I/O = 外部效应面，沙箱校验（`resolve_path` + `PermissionManager.validate_path`）
  归模块域（`fs` 先例）；值方法（unbox=False 绑定）无 `capabilities` 注入面，做不了
  沙箱校验。
- 试用方验收字面 = `load_kb(path)` 自由函数（模块函数经 `world_model.load_kb(path)`
  调用——IBCI 模块调用惯例）。

## 2. artifact 格式（共享契约 = 试用方按此重新导出 v30）

单 JSON 文件（传输格式；**不是运行时模型**——运行时模型 = 活 KB 值）：

```json
{
  "schema_version": 1,
  "content_hash": "<sha256 64-hex>",
  "facts": [ {"id","world","s","r","o","source","status","events"}, ... ],  // seq 序
  "vocab": {
    "words":     {lexeme: {lexeme, gloss, is_set, members, entries}},
    "relations": {type: {type, semantics, transitive, multi_valued}},
    "worlds":    {name: {name, description, size_rank}}
  },
  "seq": <int>
}
```

**裁定（Q2-Q4）**：
- **D1 条目面不入 artifact**：artifact = KB 面（facts/vocab/seq）的磁盘形态；
  entries 面（通用登记）持久化走 `ihost.save_state` 全状态通道（其 check 谓词引用
  本就不入值快照——两通道各辖其面，非双通道：不同概念不同载体）。
- **D2 content_hash**：= sha256 全摘要（64-hex）作用于 **canonical 载荷**
  `{"facts", "vocab", "seq"}`（排除 schema_version/content_hash 封套字段）；
  canonical = `json.dumps(payload, sort_keys=True, separators=(",",":"),
  ensure_ascii=False).encode("utf-8")`（dict 键排序 + 紧凑分隔 + UTF-8 字面；
  list 序保持 = seq 序）。文件布局（缩进/排版）是传输，身份是 canonical——
  同内容不同排版 = 同 hash。完整 64-hex（非 UID 家族 16-hex 前缀——数据完整性
  契约，非进程内标识符；uid.py 不扩）。
- **D3 schema_version 策略**：= 1；未知版本 = fail-fast（无自动迁移——兼容层
  红线）。v30 对齐：facts 记录含 id（试用方导出时按 seq 分配）/source/status
  （试用方配合项 ② 补元数据）；loader 只验结构 + 哈希，不假设试用方特定
  元数据取值。

## 3. 加载语义（fail-fast 三级门）

1. **结构门**：文件文本 = 合法 JSON + 顶层 dict + 必需键齐备（schema_version/
   content_hash/facts/vocab/seq）+ facts = list[dict] 必填字段 str 形态 + vocab
   三面 dict 形态 → 违例 `KNW_KB_ARTIFACT_MALFORMED`。
2. **版本门**：`schema_version == 1` → 否则 `KNW_KB_SCHEMA_VERSION`。
3. **完整性门**：canonical 重算 hash == `content_hash` → 否则
   `KNW_KB_HASH_MISMATCH`（篡改/损坏——内容寻址的"寻址"即验证）。

三门过后水化：`IbKnowledge(registry.get_class("knowledge"),
payload={"entries": {}, "seq", "facts", "vocab"})`——构造入口统一重建派生
索引（P2 不变量：索引永不跨构造存活）。**加载 = 活 KB**（可变，可 add_fact
增量——B1 验收；artifact 文件本身只读不被 load 改写）。

## 4. 保存语义

`save_kb(kb, path)`：kb 参数经模块默认 `unbox_args=True` 到达 = `kb.to_native()`
原生快照 `{entries, seq, facts, vocab}`（P2 to_native 三面对外快照——save 只取
KB 面三键 `facts/vocab/seq`，entries 面丢弃（D1））。canonical 计 hash → 封套
`{schema_version: 1, content_hash, ...}` → pretty JSON（`indent=2,
ensure_ascii=False`——传输面人类可读）→ 沙箱校验（`resolve_path` +
`validate_path(native, "write")`，同 `fs.write` new 模式）→ 写文件 → 返回
`content_hash` str（钉扎/审计：调用方可 hash 比对验证落盘内容）。

## 5. 诊断码（+3，KNW_ 域）

| 码 | 语义 |
|----|------|
| `KNW_KB_ARTIFACT_MALFORMED` | artifact 结构非法（非 JSON / 缺键 / 形态错——加载与保存共用） |
| `KNW_KB_SCHEMA_VERSION` | schema_version 未知（≠ 1；无自动迁移） |
| `KNW_KB_HASH_MISMATCH` | content_hash 验证失败（篡改/损坏） |

（文件不存在/沙箱拒绝 = 复用 `fs` 面既有诊断——load_kb 内部同路
`resolve_path`/`validate_path`，错误原样穿透，不另造码。）

## 6. 测试面

- **runtime**（`tests/runtime/test_world_model_kb_disk.py`）：save→load round-trip
  保真（facts/vocab/seq + 索引水化等价）；hash 篡改 → KNW_KB_HASH_MISMATCH；
  结构损坏 → KNW_KB_ARTIFACT_MALFORMED；版本错 → KNW_KB_SCHEMA_VERSION；
  加载后活增量（add_fact 100 条 → 查询面反映）；排版无关性（同内容不同缩进
  = 同 hash 可 load）；canonical 函数确定性（同载荷同 hash）。
- **e2e**（B1 验收形态）：`import world_model` → save_kb → load_kb → 活查询
  （lookup_pair/exists/expand）→ 追加 100 事实 → 增量可用（全程无重编译——
  活 KB 值语义）。
- **差分 harness 语料不做磁盘 I/O**（语料纪律 = 自包含脚本无外部文件依赖；
  磁盘面由 pytest 覆盖——P9 差分面如需文件语料再显式扩 temp root 机制，
  不预置）。

## 7. 文档同步面（C2）

- `docs/syntax/16_knowledge_system.md`：磁盘面节（artifact 契约 + load/save +
  三级验证门 + 排版无关性）。
- `docs/syntax/07_kernel_native_modules.md`（或对应内核模块表）：+world_model
  （kernel-native 9）。
- `docs/syntax/15_diagnostics.md`：+3 码（catalog 对账）。
- 不涉 `KNOWN_LIMITS`（无新语言边界——fs 沙箱边界既有时）。

## 8. 批次

- **C1**：WorldModelLib 实现 + spec/注册 + 3 码 + catalog + 15_diagnostics +
  runtime 测试 + 受影响子集+smoke + commit。
- **C2**：e2e（B1 验收形态）+ 文档同步 + 全量放行门（模块注册面变更——
  保守按公理层同档评估）+ WORKLOG/NEXT_STEPS/HANDOFF + commit。
