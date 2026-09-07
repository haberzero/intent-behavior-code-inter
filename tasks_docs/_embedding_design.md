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

---

## 九、批 ① 实施定案（2026-09-07，free-explore）

> Q1-Q4 已裁定（`_trial_intake_analysis.md` §4.1）；K1-K3 参考实现审查
> （§4.2）= 批 ①/批 ③ 实施底本。本节记录批 ① 落地定案。

### 9.1 范围

- **做**：契约包 `core/base/embedding_protocol/`（EmbeddingRequest/Result +
  EmbeddingProvider 协议 + RecommendedEmbeddingProvider（OpenAI 兼容
  /v1/embeddings + MOCK:VEC 确定性 mock）+ retrieval 最小闭包（cosine + 线性
  top-k）+ MOCK:VEC 指令引擎）+ `EMB_` 诊断码域（Q4 裁定，6 码）+ 契约测试
  （K1-K3 33 用例改写为 pytest 判别测试）。
- **不做（属后续批次）**：`vector` 值类型（批 ② 公理层）；`ai.embed` 模块面 +
  用户面 MOCK:VEC 接线 + api_config embedding 条目 schema 形态（批 ③）；
  SiliconFlow 真实试用（批 ④）。

### 9.2 合入处理项（K1-K3 已知瑕疵处置，`_trial_intake_analysis.md` §4.2）

1. **mock 向量派生文档漂移**：docstring 与实现对齐——派生键 = `{seed}|{text}`
   （`mock_vector` 对传入 text 派生）；场景引擎按批对齐时自行前缀
   （`default:{i}` / `vec:{i}`）——两层职责分离是设计而非漂移，修正表述。
2. **零范数兜底改 fail-fast**：`norm == 0.0` 的 e_0 兜底（防御性边界，
   sha256 派生实际不可能触发）违反 fail-fast 纪律——改为显式契约违约
   （`EMB_ZERO_NORM`）。与 retrieval `cosine` 零范数 fail-fast 同纪律。
3. **测试 runner → pytest**：33 用例改写为 pytest 断言（判别性保留，
   自包含 runner 面删除——上游 pytest 基建完备，C4 裁决）。

### 9.3 EMB_ 码面（Q4 裁定：embedding 是一等 I/O 面，错误面独立可定位）

| 码 | 语义 | 发射点（批 ①） |
|----|------|---------------|
| `EMB_CONFIG_MISSING` | embedding 配置缺失（base_url/api_key/model 必填空） | `set_config` / live 路径未配置 |
| `EMB_BATCH_ORDER` | 批量保序契约违约（响应长度 ≠ 请求长度 / 项缺序且乱序不可恢复） | `RecommendedEmbeddingProvider._embed_live` |
| `EMB_DIMENSION_MISMATCH` | 维度失配（批内不一致 / 查询×语料 / mock SEQ 向量维度） | provider / retrieval / mock 引擎 |
| `EMB_SERVICE_ERROR` | embedding 服务调用失败（网络/供应商错误） | `_embed_live` |
| `EMB_ZERO_NORM` | 零范数向量（余弦未定义 / 派生退化） | retrieval / mock 派生 |
| `EMB_INVALID_INPUT` | 检索/契约非法输入（空批 / 空语料 / k≤0 / 非有限值 / 序列长度不符） | provider / retrieval / mock 引擎 |

**码 × 异常映射**：`EmbeddingProviderError` / `RetrievalError` 携带 `code`
属性（失败语义 → 码 单点权威源）——批 ③ 语言层接线时同码复用
（用户可见错误 = EMB_*，不另设 RUN_ 面）。

### 9.4 配置面定案（批 ① 边界）

- 批 ① 配置经**显式 `set_config`** 承载（K1-K3 形态，"配置单源由调用方
  保证"）；**api_config.json schema 形态不定案**（`models.<name>.kind` vs
  独立段）——属批 ③ 模块面接线点（`ai.load_project_config` 消费处），
  批 ① 不动 api_config schema（避免 CFG_ 码面扩大）。
- 机制同构基准（§一）五层：契约包（本批）/ provider 实现（本批）/
  模块面（批 ③）/ 配置单源（批 ③ 接线）/ 执行路径（批 ③——embedding
  无意图/重试语义，最小重试 DEFAULT_RETRY=2 保留）。

### 9.5 验收基线

- K1-K3 33 用例全绿（pytest 形态，判别性保留）；
- 全量 pytest 零回归（基线 3289）；
- EMB_ 6 码 catalog 1:1 覆盖（test_diagnostic_catalog 强制）；
- 合入处理项 ② 实证：零范数输入 → `EMB_ZERO_NORM` fail-fast（非静默 e_0）。

### 9.6 批 ② 裁决项确认（2026-09-07）

- **Q4 诊断域**（已裁定 = `EMB_` 域）：批 ② vector 方法面 dim 不一致 fail-fast
  错误码 = `EMB_DIMENSION_MISMATCH`（C4/T3）；NaN/Inf 构造违约 = `EMB_INVALID_INPUT`
  （C7）——复用批 ① 码面，不新设码。
- **Q3 `expected_type: vector`**（已裁定 = 否）：批 ② 不触 LLM 协议面
  （C13 负面检查 = diff 范围核对）。
- **JSON 表征**（pre-study 阻塞项 4 裁决）：vector 的 JSON 类型标签 =
  `{"_vector": [...elements...]}`（与 `ibci_json` 既有 `{"_list"}`/`{"_value"}`
  包装纪律同型——类型标签化保证 round-trip 保真）；**实现接线属批 ③**
  （json 模块面），批 ② 只锁表征语义。
- **字面量语法**（暂缓）：起步 = 内置 `vec(list) -> vector` 构造函数
  （C15）；list 不得隐式转 vector（显式 vec() 调用）。
- **PT-DEBT-30/33 先例核对**：类型边界闭合全链路（序列化/深克隆/快照/克隆）
  按既有 checklist 逐项核销（C8-C10）。

### 9.7 批 ② 交叉核验裁定（2026-09-07，侦察蓝图 × 实测对照）

批 ② 实施经 fork subagent 机制面侦察蓝图 + 逐项实测对照，7 个决策项裁定：

- **D1 vec 静态签名（实测推翻侦察推荐）**：侦察结论"vec 静态 = any（无编译期
  函数签名先例）"**不成立**——`register_function` 元数据经 metadata registry
  同步 + `resolve_call_return` Layer 6 return_type 直读生效。实证：
  `list xs = vec([1.0])` → `SEM_TYPE_MISMATCH: Cannot assign 'vector' to 'list'`；
  `vector v = vec([...])` 编译通过。**裁定：保留元数据注册（强静态返回类型
  = vector，优于 any）**。
- **D2 JSON 表征（拒绝侦察推荐，维持 9.6 裁定）**：侦察推荐"现状直接数组
  （to_native）"——**拒绝**：to_native 降格 vector → list = 类型身份静默丢失
  （P11 类型漂移教训的内核侧对应物）+ JSON round-trip 类型回退 list。
  **裁定：`IbVector.to_native()` = 显式违约（EMB_INVALID_INPUT）**——vector
  类型身份永不降格；JSON 面正式通道 = 9.6 裁定的 `{"_vector": [...]}` 类型
  标签包装（批 ③ json 模块接线，json 模块自持 vector 分支，不经 to_native）。
- **D3 dict 键排除显式度**：to_native 显式违约（D2）使 dict 键/set/原生
  边界经 unbox 单一边界统一 fail-fast（消息含 vector 类型名）+
  `__hash__ = None` 双保险——**优于侦察"现状 + 文档化"推荐**（消息 =
  "vector 是值语义一等类型，不可拆箱为原生值"，非 Python 原生
  "unhashable type: 'list'" 的无类型名形态）。
- **D4 __to_prompt__ 截断（采纳）**：`__to_prompt__` = dim + 前 8 维摘要
  （与 idbg serialize_for_debug 同风格；1024 维全量进提示词 = 污染风险）。
- **D5 空 vector（采纳）**：dim=0 构造合法（维度固定含 0）；方法面
  cosine 零范数 fail-fast（EMB_ZERO_NORM）；norm() = 0.0（范数定义域含
  零向量，不违约）；to_bool = dim > 0（与 list/str/dict `len > 0` 先例同型，
  primitive_initializer 手动绑定——`bool b = v` 直接赋值不开（任何值型均
  不开，bool 化面 = if/while 条件协议 to_bool，实证对齐））。
- **D6 错误码域（拒绝侦察推荐，维持 EMB_）**：侦察推荐"RUN_ 域（值层通用）"
  ——**拒绝**：与 9.3 已落文裁定矛盾（"语言层接线时同码复用，不另设 RUN_
  面"）；值层 vector 契约违约（dim 失配/零范数/非法输入）与服务面维度契约
  违约**同一失败语义**（维度一致性），同码合理。C4 错误码 =
  EMB_DIMENSION_MISMATCH；构造违约 = EMB_INVALID_INPUT。
- **D7 对象文件位置（采纳）**：`core/runtime/objects/primitives/vector.py`
  （IbValue 子类统一目录；侦察指出的检查单"与 stream.py 同位"表述修正——
  值类全在 primitives/）。

**额外修正项（交叉核验识别）**：`==`/`!=` 运算符经 vtable receive 派发
（OP_MAPPING），非 Python __eq__ 魔法路径——VectorAxiom 声明
`get_operators() = {"==": "__eq__", "!=": "__ne__"}` 触发 `_auto_bind_operators`
自动绑定 + IbVector 显式 `__ne__`（object 继承的自动推导非实例方法，
`_is_impl_method` 不识别）；`__to_prompt__` 方法 spec 声明（协议豁免但
契约可见，ExceptionAxiom 先例）；cast_to 无法转换 fail-fast（批 ③ 纪律，
非静默 return self）；deep_clone 不可变原语分支（vector 与 int/str 同纪律
引用复用——不可变 = 克隆语义等价，C9"修改 clone 不影响原"空真成立）。
