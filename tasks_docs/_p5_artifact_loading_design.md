# P5 R-D 工件加载（推理时窄模型）设计单点真理

> 状态：设计定稿（2026-09-10，P5 批次开工）。主线设计 = `_world_model_db_design.md`
> §3.3/§6-P5；试用方验收 = R-D（bind 已训练窄模型工件 → 推理时 score/topk，
> **纯推理零训练**；确定性同输入同输出）。本文 = P5 机制裁定（self-grill 全
> 分支消解记录）。P5 收束后删除。

## 1. 调研结论（试用方窄模型真实形态，D-ISO 实证）

- 试用方窄模型 = **KG 嵌入向量空间模型**（e30/e40）：主架构 **TransE**
  （实体嵌入 E∈R^{N×d} + 关系嵌入 R∈R^{M×d}；`f(s,r,o)=‖e_s + r_r − e_o‖`
  平移假设，距离**越小越优**）。推理面 = `predict_rank`（给定 (s,r)，对全部
  候选实体算距离升序排序）——**纯算术，零训练**（训练在试用方侧离线完成）。
- 多架构（TransE+DistMult）**consensus 是试用方侧离线交叉验证/质控**，非
  推理时 score 面——推理时模型 = TransE（实证：predict_rank 只用 TransE fdist）。
- **裁定：P5 实现 TransE 推理面**（忠实试用方实际推理模型）；DistMult/ComplEx
  不预置（离线质控面，非 R-D 推理契约；架构字段预留扩展位）。

## 2. 面定位（机制同构裁定）

**新值类型 `narrow_model`（不可变冻结工件值）+ `world_model` 模块加载面**
（与 P3 `knowledge` 值 + `world_model.load_kb` 同构——值类型承载数据，模块
函数承载磁盘装配）：

| 面 | 语义 | 静态面 |
|----|------|--------|
| `world_model.bind_artifact(path) -> narrow_model` | 加载 + 三级验证门 + 水化为**活窄模型值** | `(str) -> narrow_model` |
| `world_model.save_artifact(model, path) -> str` | 序列化落盘，返回 content_hash（钉扎/审计） | `(narrow_model, str) -> str` |
| `model.score(s, r, o) -> float` | TransE 距离 `‖e_s + r_r − e_o‖`（内容信号，**越小越优**） | `(str,str,str) -> float` |
| `model.topk(s, r, k) -> list` | 全部候选实体按距离升序取前 k，每项 `{o, score}`（确定性 tie-break） | `(str,str,int) -> list` |
| `model.name()/dim()/entities()/relations()/architecture()/content_hash()` | 工件元数据查询面 | 各自 |

**裁定（self-grill 消解）**：
- **D1 值类型不可变**（同 quoted/vector/run_result 纪律）：冻结工件无修改面；
  deep_clone = 引用复用；序列化 = 原生结构直存。`narrow_model()` 语言构造 =
  fail-fast（模型必经 `bind_artifact` 加载——良构由加载门成立，同 quoted 仅
  经 meta.quote 产出）。
- **D2 score 语义**：TransE **距离**（忠实试用方 predict_rank 升序语义），
  文档明示"越小越优"；topk = 距离升序前 k。（不反转为"越大越优"——忠实
  试用方实际指标，判定面归 D1 确定性路径，此处仅内容信号。）
- **D3 确定性**：候选序 = artifact entities 固定序；排序键 `(距离, 实体名)`
  升序（稳定 tie-break）；IEEE 浮点纯算术（同输入同输出）。
- **D4 参考未注册词 = fail-fast**（同 KB 治理门纪律）：score/topk 的 s/o 未
  注册实体 / r 未注册关系 = 显式错误（冻结模型词表固定，无静默默认）。
- **D5 架构扩展位**：artifact 载 `architecture` 字段；当前仅支持 `"transe"`
  （未知架构 = 结构门 fail-fast）。不预置 DistMult/ComplEx（离线质控面）。

## 3. artifact 格式（共享契约 = 试用方按此导出窄模型工件）

IBCI 内容寻址 artifact（同 P3 KB artifact 纪律：单 JSON 文件，JSON 降传输
格式，身份 = canonical）：

```json
{
  "schema_version": 1,
  "content_hash": "<sha256 64-hex>",
  "model_name": "...",
  "architecture": "transe",
  "dim": 16,
  "entities": ["atom", "proton", "..."],              // 候选空间（固定序）
  "entity_embeddings": { "atom": [0.1, -0.2, ...] },  // 名 -> dim 维向量
  "relations": ["composed_of", "..."],
  "relation_embeddings": { "composed_of": [0.05, ...] }
}
```

- **content_hash** = canonical 载荷（model_name/architecture/dim/entities/
  entity_embeddings/relations/relation_embeddings）sha256 全摘要（同 P3：
  sort_keys + 紧凑分隔 + UTF-8；同内容不同排版 = 同 hash）。
- **三级验证门**（fail-fast，同 load_kb）：结构门（合法 JSON + 封套键 + 向量
  维度一致 + 名/嵌入键匹配 + architecture ∈ {transe}）→ `NAR_ARTIFACT_
  MALFORMED`；版本门（schema_version ≠ 1）→ `NAR_SCHEMA_VERSION`；完整性门
  （canonical 重算 ≠ content_hash）→ `NAR_HASH_MISMATCH`。文件缺失/沙箱拒绝
  复用 fs 面诊断（同 P3）。

## 4. 诊断码（+6，NAR_ 域 = narrow model）

| 码 | 语义 |
|----|------|
| `NAR_ARTIFACT_MALFORMED` | artifact 结构非法（非 JSON / 缺键 / 向量维度错 / 名-嵌入键不匹配 / 未知架构） |
| `NAR_SCHEMA_VERSION` | schema_version 未知（≠ 1；无自动迁移） |
| `NAR_HASH_MISMATCH` | content_hash 验证失败（篡改/损坏） |
| `NAR_ENTITY_UNREGISTERED` | score/topk 的 s/o 未注册实体 |
| `NAR_RELATION_UNREGISTERED` | score/topk 的 r 未注册关系 |
| `NAR_TOPK_INVALID` | topk 的 k 非正整数 |

## 5. 测试面

- **runtime**（`tests/runtime/test_narrow_model_type.py`）：score 算术正确性
  （对照手工 TransE 距离）/ topk 排序 + tie-break 确定性 / 同输入同输出
  （确定性）/ 未注册实体/关系 fail-fast / k 非法 fail-fast / 元数据查询面 /
  不可变（无修改面）/ to_native 快照独立。
- **runtime 磁盘面**（`tests/runtime/test_narrow_model_artifact.py`）：
  save→bind round-trip 保真 / 三级门各判别 / 排版无关性 / 空工件合法。
- **e2e**（R-D 验收形态）：bind_artifact → score/topk 可调用 + 确定性
  （两次独立 CLI run 逐字节一致）+ **全程无训练调用**（纯推理——无 optimizer/
  反向传播；确定性模式凭证 llm_calls=0 佐证零 LLM）。
- **文档**（E2）：narrow_model 参考节 + world_model 模块 §（bind_artifact）+
  15_diagnostics +6 码 + KNOWN_LIMITS（若需）。

## 6. 批次

- **E1**：narrow_model 值类型（primitive + axiom + 注册）+ 序列化/克隆接线 +
  6 诊断码 + catalog + 15_diagnostics + runtime 值类型测试 + 受影响子集+smoke
  + commit。
- **E2**：bind_artifact/save_artifact（world_model 模块扩展）+ artifact 格式 +
  三级门 + runtime 磁盘面测试 + e2e（R-D 验收）+ 文档同步 + 全量放行门
  （公理层变更——新值类型）+ WORKLOG/NEXT_STEPS/HANDOFF + commit。
