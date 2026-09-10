# P7 R-F 投影派生视图（kb.to_ibci()）设计单点真理

> 状态：设计定稿（2026-09-10，P7 批次开工）。主线设计 = `_world_model_db_design.md`
> §2.2/§3.1/§3.3/§6-P7；试用方验收 = R-F（`project_kb(kb)` 产物与活 KB 查询结果
> 一致[对拍]；定位 = **派生/便利特性，非数据层本身**）。本文 = P7 机制裁定。
> P7 收束后删除。

## 1. 调研结论（stopgap 实证 + IBCI 代码面实证）

- **stopgap（`schema_to_ibci.py`）缺陷**（主线 §2.2 实证）：每词生成 IBCI class，
  `form(world)` 用**硬编码 if 字符串分支**；关系编码 `"target:relation_type"`
  单字符串；**根本不存 axioms**（只读派生 word.relations）→ **静默丢 34 条事实
  （lossy）**；`return "unknown"`/`return ""` 魔法默认（红线）；无查询/索引；KB
  增长需全量重编译。
- **IBCI 代码面实证**：IBCI 支持 dict/list/bool 字面量 + 字符串转义（`"it\'s"`）
  + 末尾裸值（`kb`）合法可执行 + 执行后经 `runtime_context.get_variable("kb")`
  取回重建值 → **投影代码可确定性生成 + 可执行重建 + 可对拍**。
- **裁定：`kb.to_ibci()` = 活 KB 当前态的确定性 IBCI 代码投影**（派生视图，
  非存储层；替代 lossy stopgap——全词汇 + 全事实[active+retracted]，无魔法默认，
  无全量重编译——按需派生）。

## 2. 面定位（机制同构裁定）

**`to_ibci()` 挂 `knowledge` 值类型**（设计 §3.3 `kb.to_ibci()` 权威形态；与 P6
嵌入面同纪律——KB 值的方法面；只读导出，无修改面，同 `export()`）：

| 面 | 语义 | 静态面 |
|----|------|--------|
| `kb.to_ibci()` | 导出 KB 当前态的确定性 IBCI 代码（派生视图） | `() -> str` |

**裁定（self-grill 全分支消解）**：
- **D1 派生视图非存储层**：投影 = KB 当前态的 IBCI 代码（值），单一权威源 = 活
  KB / artifact；投影可经执行重建等价 KB，但**不是**存储层（§3.1：代码投影从
  日志派生，绝不独立存储）。
- **D2 当前态投影（非全史回放）**：投影重建 KB 的**当前态**（全词汇 + 全事实
  当前 o/source/status，active+retracted 均含）。**不回放 amend/retract 事件史**
  ——因 amend 的原始 o 不可恢复（事件链只存 new_o，原 o 被覆盖丢失）→ 全史回放
  不可能；投影 = 当前态视图（历史归 fact 日志权威面 + artifact）。
- **D3 确定性**：词汇序 = KB 自身序（worlds()/relations()/words() 插入序，
  确定性）；事实序 = fact_id（= str(seq)）序；字面量序列化规范化（dict 键排序
  + str 转义）→ **同 KB = 逐字节一致**（两次调用/两引擎）。
- **D4 治理门顺序**：投影代码先注册全词汇（worlds→relations→words），再 add_fact
  （全事实）——满足 add_fact 治理门（world/relation/s/o 须已注册）。
- **D5 无新诊断码**：to_ibci 只读导出（读 KB 当前态生成字符串），无治理违约
  面——不新造码（语义错误集不变）。
- **D6 fact_id 边界**：投影重建的 fact_id = 回放 seq（add-only KB = 与原一致；
  含 amend/retract 历史的 KB = id 可能偏移[历史事件也增 seq]——当前态 o/status
  仍一致，id 是回放派生量）。对拍按**语义查询结果**（world/s/r/o/source/status），
  非 fact_id 本身。

## 3. 投影代码形态（确定性 IBCI 源码）

```
# knowledge.to_ibci() 确定性导出（派生视图——KB 当前态的 IBCI 代码投影；非存储层）
kb = knowledge()
kb.register_world("<name>", "<description>", <size_rank>)          # 每世界（KB 序）
kb.register_relation("<type>", "<semantics>", <transitive>, <multi_valued>)  # 每关系（KB 序）
kb.register_word("<lexeme>", "<gloss>", <is_set>, [<members>], {<entries>})  # 每词（KB 序）
kb.add_fact("<world>", "<s>", "<r>", "<o>", "<source>", "<status>")          # 每事实（fact_id 序，当前态）
kb
```

- **字面量序列化**（`_ibci_literal`）：str（转义 `\"`/`\\`/`\n`/`\t`，UTF-8 原样）/
  bool（`True`/`False`，先于 int 判）/ int / float / list（`[lit,...]`）/ dict
  （键**排序**后 `{lit: lit, ...}`，确定性）。
- **末尾裸 `kb`**：代码可求值 = 重建 KB（执行后 `get_variable("kb")` / 末值）。
- **确定性保证**：同 KB → 同词汇序 + 同事实序 + 同字面量 → **逐字节一致**。

## 4. 对拍（R-F 验收面）

投影代码经**新引擎**执行重建 KB，与原 KB **语义查询结果对拍**（一致性）：
`lookup_pair(s,r)` / `exists(world,s,r,o)` / `by_subject(s)` / `contradicts(s,r,o)` /
`transitive(s,r)` / `facts()`（语义字段 world/s/r/o/source/status）全一致（add-only
KB 的 fact_id 亦一致）。

## 5. 测试面

- **G1 runtime**（`tests/runtime/test_knowledge_to_ibci.py`）：
  - 确定性：同 KB 两次 to_ibci 逐字节一致；
  - 有效性：投影代码编译 + 执行无错；
  - **对拍**：新引擎执行投影代码 → 取回重建 KB → 语义查询结果与原 KB 一致
    （lookup_pair/exists/by_subject/contradicts/transitive/facts）；
  - 全词汇/全事实投影（active+retracted 均含，无 lossy）；
  - retracted 事实投影（status="retracted" 保真）。
- **G2 e2e**（R-F 验收形态）：to_ibci 导出投影代码 → 写盘 → 两次独立 CLI run
  执行投影代码 → 数据面（查询结果）逐字节一致 + 零 LLM。
- **文档**（G2）：knowledge 参考节 to_ibci + 主设计/11_modules（若需）。

## 6. 批次

- **G1**：knowledge.to_ibci()（确定性 IBCI 代码发射器：词汇 + 当前态事实 +
  字面量序列化）+ 公理 KnowledgeAxiom 加 to_ibci + runtime 对拍测试 +
  受影响子集 + smoke + commit。
- **G2**：e2e（R-F 验收：投影代码独立 CLI run 对拍一致 + 零 LLM）+ 文档同步 +
  全量放行门（公理层变更——knowledge 新面）+ WORKLOG/NEXT_STEPS/HANDOFF + commit。
