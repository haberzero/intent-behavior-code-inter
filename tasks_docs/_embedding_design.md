# _embedding_design — 词嵌入一等能力系统级架构设计（PT-FEAT-16 · 阶段 E 批 1）

> **定位**：设计阶段文档（临时，实现落地后按治理删除、决策收敛进 `docs/architecture/`）。
> **设计纪律（用户 2026-09-05 明确）**：embedding 不是"一种数据结构或一个库函数"——
> 与 LLM 同等严肃对待：语言级表现形态、职责边界、承载的数据结构、系统级角色、
> ibci 其它全部元素与新成员的交互协议，须系统级架构设计先行。
> **裁决基准**：`design-philosophy` 全清单（单一权威源 / 设计语言统一 / 设计思路统一 /
> 机制同构 / 配合模式统一 / 一致性先于便利 / 宏观反思 / 命名粒度统一）。
> **范围基线**（ref C1）：vector 类型 + 相似度（cosine）+ 向量检索 + 与 LLM 协同 +
> OpenAI 兼容 embeddings 服务接入。愿景锚点：灰盒自动机"内容层"在 ibci 内闭合，不寄生 Python。

## 一、先例剖析：LLM 集成的机制骨架（机制同构基准）

embedding 的集成必须复用 LLM 已验证的分层骨架，而非另起炉灶：

| 层 | LLM 侧既有机制 | embedding 侧对应（候选） |
|----|----------------|--------------------------|
| 契约包 | `core.base.llm_protocol`（`core/base` 只出不进）：`LLMCallRequest/LLMCallResult`（供应商无关数据契约）、`ModelSpec/ConfigSourceAdapter`（配置）、`LLMProvider`（抽象动作协议） | `core.base.embedding_protocol`（同位）：`EmbeddingRequest/EmbeddingResult`、embedding 模型配置（并入或并列 ModelSpec）、`EmbeddingProvider` 协议 |
| 推荐实现 | `ibci_modules/ibci_ai/provider_impl.RecommendedProvider`（OpenAI 兼容 payload、思考抑制、call_info、重试面） | OpenAI 兼容 `/v1/embeddings` 默认实现（`input` 批量、`dimensions`?、维度/归一化适配） |
| 模块面 | `ai` 模块（`set_config/load_project_config/register_model/probe_model/set_mock_mode/run_batch/stream_call/...` 经 spec 元数据供 IBCI 调用） | `ai.embed(...)` / provider 注册入口；或独立 `iembed` 模块（命名粒度权衡见 §四） |
| 配置 | api_config.json（单源向上发现 + `{env:}` 密钥通道） | embedding 模型条目（provider/model/dims）——复用同一单源机制，不新造配置通道 |
| mock | mock_scenario 指令语言（`MOCK:STR/SEQ/FAIL/STREAM/ERROR`，线程安全） | `MOCK:VEC` 指令语言（确定性向量生成：哈希派生/种子向量，保证断言可判定） |
| 观测 | call_info / get_call_trace / idbg.current_llm | embed 调用观测面（最近一次嵌入的输入数/维度/时延） |
| 诊断 | LEX/PAR/SEM/DEP/INT/RUN/KDIAG/CFG 域 | 新能力配套诊断码（ref D3）：契约违约/维度不匹配/服务失败归属域待定 |

**机制同构结论（初判）**：embedding 走"契约包 + 推荐实现 + 模块面 + 配置单源 + mock 指令"
五层同构，`EmbeddingProvider` 契约形态对齐 `LLMProvider`（call/批量/探测/供应商字段映射
在各自实现内，`thinking_mode` 式供应商无关声明位预留为 `normalize`/`dimensions` 语义位）。

## 二、系统级角色定位

- embedding 是**语义内容缝的基础能力**（检索/候选生成/相对排序），不是媒体、不是 LLM 的附属。
- 服务对象：灰盒自动机的内容层——知识条目嵌入、查询嵌入、候选召回、相似度评分、
  与 LLM 协同（少样本召回、意图上下文检索、验证闭环的候选生成）。
- 明确非目标（本批）：VSA 离散层（trial2 e18 实证需求，属远期语义代数层）、模型训练、
  大规模持久化索引（磁盘型 storage model 交互为后续窗口）、rerank 模型。

## 三、数据结构：vector 值类型（承载什么）

候选决策（待深化论证）：
1. **内置值类型 `vector`**（公理层新增，独立于 list[float]）——语义上是一等数学对象：
   - 固定维度（创建时定，不可变）；元素为浮点；**值语义**（按元素相等/哈希一致）；
   - 经 `receive()`/vtable 方法面（与既有容器同构）：`dim()` / `dot(other)` / `norm()` /
     `cosine(other)` / `scale(k)` / `add(other)` / `sub(other)`（最小闭包，先内聚后扩展）；
   - 序列化/deep_clone/snapshot 全链路显式支持（类型边界闭合纪律——PT-DEBT-30/33 先例）；
   - 字面量语法**暂缓**（`vec([...])` 构造函数起步，字面量属语法面扩张，待使用证据）。
2. **相等与容差**：值语义相等 = 精确元素相等（浮点逐元素）；相似度判定走 `cosine` 显式
   表达，不做隐式容差（fail-fast/显式优于隐式纪律）。
3. **归一化**：不做隐式归一化；`cosine` 自带尺度不变性；`norm()` 显式可用。

## 四、语言形态与模块面（怎么用）

待决问题（下 session 以使用证据 + 命名粒度统一裁决）：
- Q1 载体模块：并入 `ai`（`ai.embed`）vs 独立 `iembed` 模块——LLM 能力在 `ai`，embedding
  是独立语义缝；独立模块更符合"一个概念一个权威入口"，但协同 API（检索+LLM 组合）跨模块。
- Q2 相似度/检索归属：vector 方法面（`cosine`）承载两两相似；**检索库**（多向量 + 查询 →
  top-k）是独立抽象（`vector_index`? 或 list[vector] + 内置检索函数）——最小闭包起步：
  先 `cosine` + list 线性扫描内置，索引结构按需求演进。
- Q3 `expected_type` 协同：LLM 行为能否声明 `expected_type: vector`（LLM 产出向量）？
  本批倾向**否**（LLM 产出经 `__from_prompt__` 文本解析，向量来自嵌入服务）——边界立牌。
- Q4 诊断码域：新 `EMB_` 域 vs 归入 `RUN_`——按 15_diagnostics 域语义裁决。

## 五、供应商无关契约（EmbeddingProvider，候选签名）

```python
class EmbeddingProvider:
    def embed(self, request: EmbeddingRequest) -> EmbeddingResult: ...   # 批量：texts -> vectors
    def get_retry(self) -> int: ...                                      # 与 LLMProvider 同构
    def is_auto_..._enabled(self) -> bool: ...                           # 语义位（预留）
    def get_current_call_info(self) -> dict: ...                         # 观测
    # probe()：可选，维度/服务探测（对齐 LLMProvider probe 可选形态）
```
OpenAI 兼容默认实现：`POST /v1/embeddings {model, input: [..]}` → `data[].embedding`；
批量保序；错误 fail-fast（CFG/RUN 域诊断码）。配置：api_config 增 embedding 模型条目
（`models.<name>.kind: "embedding"`? 或独立 `embedding_models` 段——单一权威 vs schema
一致性权衡，下 session 定）。

## 六、与既有元素交互协议清单（全元素审视）

| 交互面 | 语义要求 |
|--------|----------|
| 容器 | `list[vector]` 特化与遍历；vector 不作 dict 键（可哈希性 vs 浮点相等——立牌排除） |
| snapshot/lambda | 捕获按 deep_clone 既有协议（vector 深克隆 = 新实例同元素） |
| serialization / save_state | round-trip 保真（维度+元素） |
| LLM 协同 | 检索结果作为 prompt 槽内容经既有 `prompt_slots` 注入（不新增 LLM 侧机制） |
| mock | `MOCK:VEC[:seed]` 确定性向量，测试断言可判定 |
| idbg | fields/序列化视图含 vector 摘要（dim + 前 n 维） |
| 沙箱/fs | 无 I/O 面（纯内存值类型） |

## 七、批次与验收

1. 契约包 `core.base.embedding_protocol` + 默认 provider + 配置条目（契约测试）
2. 内置 `vector` 类型 + 方法面 + 序列化/深克隆/快照全链路（判别测试）
3. `ai`/`iembed` 模块面 + mock 指令 + 检索最小闭包（判别测试 + T16 试用套件骨架）
4. 真实服务试用（新端点 embeddings 可用性实测——服务端是否暴露 /v1/embeddings 待验证）

## 八、开放问题（下 session 输入）

- Q1~Q4（§四）；配置 schema 形态（§五）；`MOCK:VEC` 指令语法细节；
  `EmbeddingRequest` 字段面（texts/dimensions/user 归属）；内核执行器路径
  （llm_executor 同构 vs 独立轻路径——embedding 无意图/重试语义，或最小重试）；
  trial2 e18"短词坍缩"教训在默认实现层的体现（文档提示而非内核补偿）。
