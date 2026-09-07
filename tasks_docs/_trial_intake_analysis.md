# 外部试用工程（ibci-trial）回接分析 —— 需求/缺陷核验、使用流程审视、语言自动机使命下的适配与发展方向

> **裁定状态（2026-09-06，用户）**：本文件 §四 Q1-Q4 裁决建议 + §五 5.2 发展队列
>（P0 三线：诊断面打包 → PT-FEAT-16 四批 → N2 已验证答案注册表设计；P1×2 / P2×4 / 挂起×1）
> + §五 5.3 排除项——**全部认可**。Q1-Q4 转"已裁定"，PT-FEAT-16 批① 实施解锁；
> N2 方向认可（设计文档先行，文档内四个开放问题二次裁决）。任务入口 =
> `tasks_docs/_free_explore_handoff.md` §六（下一 session 接手）。

> 日期：2026-09-06（free-explore 分支）。性质：设计阶段任务控制文档（回接分析）。
> 输入源：`/home/dsh/proj/ibci-trial/`（外部试用智能体工作区，只读；其全部 IBCI 相关产出：
> 需求文档 P1-P11/N1-N4/A1-E2、上游交接汇总、K1-K3 参考实现 33/33、PT-FEAT-16 使用证据、
> 172 个自主轮记录、e01-e58 实验脚本与输出存档）。
> 本文件是回接的**单点记录**：试用方文档的要点摘要 + 我方逐条核验结论 + 适配/发展方向分析
> + 下一任务队列建议。试用方原文以其工作区为准（不复制全文，只引要点与编号）。

---

## 一、试用工程概览

### 1.1 使命与定位

试用智能体用 IBCI 构建并验证**灰盒自然语言自动机**（三纸带：D 数据/I 指令/M 元指令）。
用户 2026-09-06 定位（经试用方文档转述，与本仓 AGENTS.md 使命一致）：
**"ibci 一切为了稳定可靠的语言自动机服务，不是翻版 Python、不是通用编程语言"**。

核心架构（试用方实证成立的部分）：

- **结构层（确定性）**：类型/验证/路由/世界 register/重读/延迟 denotation——可审计、可重算；
- **内容层（神经）**：词汇语义/世界知识/相似性/语用推理——从数据学习；
- **铁律**（试用方 2026-09-05 后精化为三类操作）：
  - **judgment**（提示模型判断/评分/排序）= **禁止**（自偏好/冗长/位置偏差，文献证实）；
  - **measurement**（采样模型自身分布统计量：cloze 频率/logprob）= **允许**（可复算可审计）；
  - **proposal**（生成内容/提案，结构由确定性层验证）= **允许**。
- **数独式验证闭环**：LLM 提案 → 确定性裁判（类型兼容/论元饱和/真值，100% 确定性）→
  PASS/FAIL/AMBIGUOUS + error_trace → 训练信号。
- **已验证答案注册表**（试用方黑话原称“结晶”，用户 2026-09-07 裁定废除此名；第二轮新增 P0 机制，N2）：验证过的答案存起来，下次不再问模型
  （"用得越久越确定"）。

### 1.2 工作规模与产出

| 阶段 | 内容 | 规模 |
|------|------|------|
| 第一轮 e01-e17 | IBCI 内逐机制原型（世界模型/验证闭环/认知作用域/同像性/场景标注/三纸带/λ-核心/自修改/词典/LLM 类型裁判/批量训练/world register/确定性路由/重读索引/延迟 denotation） | 17 组 25 脚本，全部亲验跑通 |
| 第二轮 e18-e29（本地小模型） | Phase 0-4 补全（VSA 向量/延迟 denotation/三纸带主循环/RSA 意图推断/模式语义/闭环深化）+ e24-e29（语篇引擎/结晶/surprisal 测量/确定性优先/修订置信度/LLM 结构提案） | 17 脚本（IBCI）+ 6 脚本（Python 侧） |
| 自主轮 R1-R172 | trial2 新端点重验 + e30-e58 机制栈（30 个中文语篇 360 句语域标定：终态 81TP/10FP/29FN，P=0.8901 R=0.7364）+ K1-K3 kernel_overlay（PT-FEAT-16 批①③参考实现，33/33 契约测试）+ **44 轮上游只读监测**（监测到本仓 STREAM-1 在途修复并做只读分析） | 172 轮逐轮记录（docs/AUTONOMOUS_LOG.md 6474 行） |

关键实证结论（对我方有直接价值的）：

1. **IBCI 是三纸带自动机的理想原型台**：三原创思想（意图栈=认知作用域、__to_prompt__、
   场景标注=不确定性操作静态类型）在 e05/e07/e02b 逐一实证；三纸带各组件在 IBCI 原生承载
   （D 池=平铺 dict+append-only、M 纸带=intent 栈、I 纸带=类型驱动归约纯代码、
   quote/eval=ihost+字符串存储、确定性沉底=宿主绑定、类型论 ISA=协议注册表）。
2. **embedding 粒度分工（e32q 实证）**：结构层（词边界/标记族）= 单句级权威判定；
   向量侧（句向量相似度）= 语料级/语域级**辅助相对测量**——互补不替代。
3. **检索最小闭包足够（e32r 实证）**：候选召回（list + 线性 cosine top-k）满足
   语料级使用场景；句级语义判定不成立（特异性证伪）。
4. **结晶通道收益路径（e31/e31b 实证）**：fast path（0 调用）+ 模式匹配 few-shot
   （正贡献）+ 裸 few-shot（负贡献）——结晶必须带结构签名存储、按结构键检索。

### 1.3 试用方对我方的观察（上游监测）

44 轮只读监测（R41-R171，HEAD b89fdc39 冻结期）：
- 在途 STREAM-1 修复做了根因链三层分析 + cancel() 协作式设计认可（R45 记录）；
  **该修复已于 2026-09-06 由本分支落地（commit 751ddb5d）**——试用方观察与我的实施一致。
- P9-P11 四微测试多轮复跑维持"未修复"（R41/R45 等）——本轮已逐条核验（见 §三）。
- PT-FEAT-16 无实施提交（监测期）——本轮起进入实施条件齐备状态（K1-K3 参考实现就位，见 §四）。

---

## 二、使用流程审视（试用方怎么实际用 IBCI）

### 2.1 典型实验工作流

```
建 .ibci 脚本（import ai/json/fs + ai.load_project_config() + set_mock_mode 兜底）
  → run（main.py run <case> --root <工程根>，api_config.json 单源）
  → 读 print 输出 + 输出存档（*.txt 两轮 live A/B）
  → 确定性断言（预注册 5/5 + 验收 5/5 双门）→ 迭代
```

### 2.2 IBCI 能力使用清单（按使用频率）

| 能力 | 用法 | 使用面 |
|------|------|--------|
| 行为表达式 `@~ ... ~` + 段插值 `$x` | LLM 提案（lambda 内 `fn f = lambda(x) -> str: @~ ... ~`） | 全部 e04-e13/e29/e31 |
| `ai.run_batch` | 并发批量提案（训练集生成） | e13/e31/e31c |
| llm 可调用类（`func __llm_call__(self, ...) -> dict`） | 结构化 LLM 提案 + 类型约束 | e04b/e12 |
| dict 程序化构建（`dict d = {}` + `d[k] = v`） | 词典/世界模型/真值池/register/结晶库 | 全部（D 纸带承载） |
| list/append | 话语状态（append-only）/error_trace/训练集 | 全部 |
| func + 显式返回注解 | 确定性裁判/查表/归约（类型论 ISA） | 全部（I 纸带承载） |
| intent（snapshot/lambda 稳定子集） | M 纸带（改写解释函数 F）/认知作用域 | e02b/e05/e14-e17 |
| ihost（脚本生成 + 隔离执行） | 自修改自动机/重读 | e06/e10 |
| json 模块 | LLM 结构化提案解析 | e04/e12/e13/e29 |
| fs 模块 | 训练集 JSONL 落盘/语料存档 | e13/e31 |
| ihost.save_state/load_state | 话语状态持久/重读环境 | e16 系 |
| mock 模式（ai.set_mock_mode） | 无 key 断言 | 全部（双轨：mock 断言 + live A/B） |

### 2.3 摩擦点 → 推出 IBCI 之外的边界（关键观察）

e24-e29 全部写成 **Python**（非 IBCI）的原因（经文件逐核）：
- **VSA 向量运算**（numpy 高维 binding/bundling）→ IBCI 无 vector 类型、无数值科学计算面；
- **RSA 贝叶斯**（log 域加法/归一化）→ 同上；
- **cloze/surprisal 测量**（logprob 采样统计）→ IBCI 无 logprob 通道（provider 不暴露）；
- **标定统计**（P/R/边际/A/B 计数）→ IBCI 可做但无聚合/统计面，Python 更顺。

即：**IBC 承载了全部"结构层 + 状态管理 + LLM I/O"，内容层的数值/统计面全部落到外部
Python 直连端点**。这正是 PT-FEAT-16（embedding 面）要收窄的边界；logprob 测量面（N3）
是同一边界的第二块（暂挂起，方向保留）。

### 2.4 迭代成本的主要去向

试用方 172 轮中大量轮次耗在：解析/运行错误定位（无源行号，P4/B1）、类型注解样板
（P3）、错误位置漂移（P2）、端点/模型细节（思考字段告警噪音、单 token 退化
raw="}"→n≥2 提案约定）。**诊断面（B1 源行号 + 编译期类型检查覆盖）是试用流程中
最高频的成本项**——这是"稳定可靠的语言自动机服务"使命下应优先收窄的。

---

## 三、缺陷/需求逐条核验（本轮实测，free-explore @ 1205a530）

### 3.1 已修复（本轮，commit 1205a530，pytest 3219/1 零回归）

| 编号 | 缺陷 | 根因 | 修复 |
|------|------|------|------|
| **P9a** | `len(dict)` 函数形态恒 0（`d.len()` 正确） | `IbDict` "payload 与 fields 同一映射" 不变量在 `_box_dict`/序列化水化两处被整体替换 `fields` 破坏（payload 滞留空壳）；IbList/IbTuple 的 `elements` property 早已防住同型问题，IbDict 是唯一例外 | `IbDict.fields` 经 property 落 `payload`（与 `elements` 同构的单点真理约定）——双写真相结构上不可能，两处破坏点零改动自洽 |
| **P9b** | 内联布尔子表达式比较反转：`(x.len()>0) == (y.len()>0)` 真==真→假 | 解析器 `binary()` 链式合并把**任意** IbCompare 左操作数当链续——括号包裹的独立比较被并入 `a > b == c > d` 链（左操作数错绑内层 comparator） | grouping 对括号内比较打 `_parenthesized` 标记（解析期消费，不入产物），链的语义边界以括号为界；无括号链式比较行为不变（四操作数链仍合并） |

判别测试：`tests/runtime/test_trial_feedback_fixes.py`（+10：P9a 字面量/增长/list 不变/
水化 round-trip；P9b 求值语义 3 组 + 解析结构 3 组含无括号链保持）。

### 3.2 已核验定性（未修，入队列）

| 编号 | 试用方描述 | 本轮核验结论 |
|------|-----------|-------------|
| **P9c** | 无 dict 键枚举 | **部分过期**：`d.keys()/values()/items()` 已可用（实测 keys_len=2）；真实缺口 = **dict 不可 `for` 迭代**（无 `to_list`，for=to_list 物化协议不覆盖 dict）——能力缺口，低成本 |
| **P11** | 内联 @~ 结果类型漂移 str/dict | **LHS 标注形态正常**（实测 `dict d = @~...~` → d_type=dict；`str s = @~...~` → s_type=str）；试用方微测试（`experiments/e32x_p9p11_recheck/p11_cast.ibci`）实际暴露的是**比较运算符编译期类型检查缺失**：`str >= int` 静态已知失配漏到运行期 `RUN_GENERIC_ERROR`（无 ibci 源行、无诊断码定位）——**新登记 `KERNEL_ISSUE-SEM-1`**（INDEX），与 P2/B1 同域（诊断面） |
| **P2** | 解析错误位置漂移 | 维持（与 SEM-1/B1 同域：诊断面核心缺口） |
| **P3** | 强制返回类型注解（`-> auto` 样板） | 维持（语言决定，易用性项；不改——显式类型是 IBCI 类型论 ISA 的承载，试用方自身机制依赖它） |
| **P4/B1** | 运行错误无 ibci 源行号 | 维持（诊断面 P0 候选） |
| **P10** | dict/list 引用传递陷阱 | 标准语义（设计非缺陷）；文档 + `copy()/deepcopy()` 已备——试用方建议 = 文档面，入 C4/文档队列 |
| **P7/P8** | 顶层行为表达式 DDG 异步派发语义 | 既有设计（lazy resolve）；试用方已适应（lambda 包一层同步）；文档面 |
| **P1/P5/P6** | 多行容器尾逗号/其他语法严格性 | A3 尾逗号 = 语法易用性项（入队列，低成本）；其余维持 |

### 3.3 需求侧（N1-N4 + A1-E2 表）核验与立场

| 需求 | 核验 | 立场（按语言自动机使命 + design-philosophy 审查） |
|------|------|-----------|
| **N1 思考模型支持**（extra_body 透传 + 空 content 确定性处理 + max_tokens 预算） | SiliconFlow `Qwen/Qwen3.6-35B-A3B` 已实证：双字段抑制有效（`reasoning_content` 兼容已验证）；空 content 处理/max_tokens 键仍缺。**2026-09-06 追加实证（overlay 配置面评估）**：provider 当前把双字段抑制 dict **硬编码**进每个请求的 `extra_body`（3 个调用点：非流/流/probe，`provider_impl.py` call/stream/probe 路径）且**无条件发送**——`reasoning: true`（思考模型模式）在请求层实际不可表达（抑制仍发出）；vendor 参数（机器事实）滞留 tracked 代码层 = 与 named-model 端点泄漏同源的"机器事实未收敛配置单源"问题 | **做**（P1，**重定性为根因项并前置**）：per-model `extra_body` 配置字段（dict，fail-fast 类型校验，CFG_ 码族，与 T4 max_tokens 同型）+ 代码默认 = 不发送（对 vendor 零意见）+ 本机抑制 dict 迁入 `api_config.json`（机器事实归位）；空 content 确定性处理同批（现状 = 静默以 reasoning 替代 content，违反可审计纪律）。**脚本层"整 schema 覆写"形态评估结论 = 不做**（单一权威源/密钥卫生/双通道/可审计性四重违反；真实需求 = ihost 子环境配置隔离，归 ref E1 设计，scoping 形态而非覆写形态；详见本文件 §五 5.4） |
| **N2 已验证答案注册表**（试用方建议 API `ai.crystallize/lookup/correct/crystal_log` 为审查输入，黑话名已废除；引擎内路由：registry 命中→跳过 LLM；铁律：原始 LLM 输出不可直接登记，必须过确定性谓词；append-only 事件流） | 试用方 e25/e31 机制实证收益路径（fast path + 模式匹配 few-shot）；存储面与 IBCI 平铺池+UID 侧表同构 | **做**（P0 候选，语言自动机使命核心机制——"用得越久越确定"的机器承载）：设计阶段文档先行（§五 3.1） |
| **N3 measure_freq**（logprob 测量通道） | 试用方自我质疑后建议**挂起**；e26-e28 为现成验收基线 | **挂起、方向保留**：measurement 是铁律允许的第三类操作；logprob 通道是"测量"能力的机器承载，但当前语料/探针设计全部手工，内化时机未到 |
| **N4 finish_reason 暴露 + max_tokens 键** | provider 未暴露 | **做**（P1，与 N1 同批：批量管线运行细节） |
| **C1 embedding/vector 一等面**（PT-FEAT-16） | 设计文档就位 + K1-K3 参考实现 33/33 + Q1-Q4 证据齐备（§四） | **做**（P0，实施条件齐备——本轮起从"设计冻结"转"可实施"） |
| **C2 结构化 LLM 输出契约显式化** | llm 可调用类/expected_type 已可用（试用方主力模式）；契约违约面已 fail-fast（RUN_LLM_CALLABLE，BOUNDARY-LLM-4 处置） | **收窄为文档+边缘补齐**（不是新机制：机制已存在，缺的是试用方遇到的边缘——如内联行为表达式 LHS 标注与容器返回的交互说明） |
| **C3 用户模块路径解析** | KERNEL_ISSUE-IMPORT-2 已定位（project_root 锚定语义未定案） | **做**（P2：锚点语义定案+文档化，与多文件用例形态联动） |
| **C4 ibci-内部测试面** | 试用方自包含 runner（kernel_overlay tests 零 pytest 依赖）是其零改动纪律的产物 | **维持现状**（外部工程纪律合理；我方 pytest 基建完备——不适用） |
| **B1 源行号** | 诊断面核心缺口（§二 2.4 迭代成本主去向） | **做**（P0 候选，与 SEM-1/P2 同域打包设计） |
| **A3 尾逗号** | 语法易用性 | **做**（P2，低成本解析器项） |

### 3.4 端点切换记录（本轮已完成并验证）

- 旧端点 `vllm.haberzero.cn` 35B **已下线**（用户 2026-09-06 明确）→ 弃用注记已落
  `TEMP-35B-LLM-GUIDE.md` 头部。
- 新端点 **SiliconFlow** `https://api.siliconflow.cn/v1`（key 已入 `api_config.json`，gitignored）：
  - chat `Qwen/Qwen3.6-35B-A3B`：probe 通过（~166ms）；**思考抑制双字段实证有效**
    （`enable_thinking=false` + `chat_template_kwargs.enable_thinking=false` →
    `reasoning_content=None`、content 纯答案 2 tokens）；思考字段名 = `reasoning_content`
    （provider `_extract_reasoning` 兼容 `reasoning`/`reasoning_content` 两者，已核代码）。
  - embedding `Qwen/Qwen3-Embedding-0.6B`：`POST /v1/embeddings` 直连验证通过（~1024 维）。
    **IBCI provider 尚无 embeddings 通道**——该面 = C1/PT-FEAT-16 实施范围（本轮未动）。
  - 记录落点：`AGENTS.local.md`（本机事实）+ `api_config.json`（default/qwen35 两模型
    `reasoning:false` timeout 180）+ TEMP 指南作废注记。

---

## 四、PT-FEAT-16 实施条件评估（Q1-Q4 裁决输入 + K1-K3 可用性）

### 4.1 Q1-Q4 裁决（试用方证据 + 我方 design-philosophy 审查）

| 问题 | 设计文档位置 | 试用方证据 | 我方裁决建议 |
|------|-------------|-----------|-------------|
| **Q1 载体模块**：并入 `ai`（`ai.embed`）vs 独立模块 | §四 | Q1 使用证据：embedding 面与 LLM 面无调用时序耦合（K1-K3 零依赖 llm_protocol；33/33 独立测试）；但**配置/密钥/端点是同一 api_config 单源**（SiliconFlow 一个端点供两个面） | **并入 `ai` 的模块面（`ai.embed`），协议层独立（`core/base/embedding_protocol`）**：协议包独立 = 机制同构基准（与 llm_protocol 对等）；模块面并入 = 配置单源 + 用户认知单入口（"ai 模块 = 模型 I/O 面"），避免第二套 load_project_config。K1-K3 的独立包形态恰是协议层的正确形态，平移零冲突 |
| **Q2 相似度/检索归属**：vector 方法面 vs 检索库 | §四 | e32r 实证：使用场景 = 语料级候选召回（list + 线性 cosine top-k 足够）；句级判定不成立 | **最小闭包起步（线性 top-k 内置，无索引结构）**：K3 retrieval.py 即该形态（fail-fast 五类 + 并列按索引升序 + k>n 显式钳制）；索引结构按需求演进（不预建） |
| **Q3 `expected_type: vector`**：LLM 能否产出向量 | §四 | Q3 证据：向量从不经过 LLM 路径产生（LLM 产出文本 → 确定性层调 embedding） | **否**：`expected_type: vector` 不开放（铁律：内容层产出经契约层——LLM 输出永远是文本/JSON，向量化是确定性调用）。这一裁决把 vector 类型的产生面收窄为 embedding provider 单源，序列化/克隆语义随之简单 |
| **Q4 诊断码域**：新 `EMB_` 域 vs 归入 `RUN_` | §四 | K1-K3 契约违约五类 fail-fast 面：配置缺失/模型不可用（CFG 面）+ 调用/维度/保序违约（EMB 面）+ 运行（RUN 面） | **新 `EMB_` 域**（与 15_diagnostics 域语义一致：embedding 调用是一等 I/O 面，错误面独立可定位；CFG_ 面复用既有配置域）。K1-K3 的 `EmbeddingProviderError`/`RetrievalError` 即该域异常形态 |

### 4.2 K1-K3 参考实现审查结论（本轮亲自核查代码）

- **质量**：契约层纯数据（frozen dataclass，零副作用）；provider 抽象与 LLMProvider
  机制同构（embed↔call/get_retry/get_current_call_info/可选 probe）；recommended 实现
  fail-fast 纪律完整（配置缺失不静默回退、批量保序、维度/长度违约显式抛错）；
  mock 向量 = sha256 派生 L2 单位向量（确定性可复现、零网络零 key）；retrieval 零依赖纯 Python。
- **可平移性**：`core/base/embedding_protocol/` 新包，与既有文件零冲突（平移指引在
  试用方 `docs/ibci_kernel_changes.md` §上游应用）；测试为自包含 runner（33/33）——
  合入时改写为 pytest（判别性测试保留，冒烟测试并入既有套件）。
- **已知瑕疵（合入时处理）**：① mock 向量派生文档（`{seed}|{i}|{text}`）与实现
  （`{seed}|{text}`，i 由调用方拼入 key）的表述漂移；② `norm==0.0` 的 e_0 兜底为
  防御性边界（sha256 派生实际不可能触发）——按 fail-fast 纪律应改为显式违约而非兜底；
  ③ 测试 runner 的 `print` 断言面需迁移为 pytest 断言。
- **结论**：**批①/批③参考实现可直接作为实施底本**（不是照抄——按上表 Q1 裁决调整
  模块面归属 + 按 fail-fast 纪律处理 ②）。

### 4.3 批②（vector 值类型）pre-study 就绪度

试用方 C1-C15（合入检查面）/ T1-T10（判别测试）检查单已备（`docs/pt_feat16_batch2_prestudy.md`）。
关键判别点（C5 值语义）：vector = **值语义**（不可变、比较/哈希按内容）——与 P10
（dict/list 引用语义）的区分是类型设计的核心；Q3 裁决（产生面单源）进一步收窄其
序列化/克隆面。**批② 是四批中唯一触及公理层（值类型注册 + 克隆 + 序列化）的批次**，
需按语义错误集变更纪律走全量 pytest 评估。

---

## 五、主动适配点与发展方向（回应用户两问）

### 5.1 我们有什么能够主动去适配的（从使用流程 + 工程目的出发）

**第一性观察**：试用方的灰盒自动机**已经在 IBCI 上跑起来了**（172 轮、30 语篇 360 句、
全部机制原型 e01-e17 成立）——IBC I 对语言自动机使命的承载是**正向实证**，不是
"需要大改才能用"。适配点 = 收窄"IBC I 承载面"与"外部 Python 内容面"的边界，
把已验证在 IBCI 内可做的、以及已验证该由语言层承载的，收进来：

1. **embedding/检索面（C1/PT-FEAT-16）**——边界收窄第一块：向量内容层 I/O
   （embedding 调用 + 候选召回）从"外部 Python 直连端点"收进 IBCI 语言层。
   试用方 e30-e32 的 172 轮中，凡涉及"取向量/算相似度/召回候选"的段全部在 Python 侧；
   收进 IBCI 后，结构层（标记族/词边界/判定）与内容层（向量测量）在**同一语言内**
   组合——这是灰盒架构在机器层的完整承载。实施条件已齐备（§四）。
2. **已验证答案注册表（N2，试用方黑话原称"结晶"，已按用户 2026-09-07 裁定废除该名）**——"用得越久越确定"的机器承载：验证过的答案（LLM 提案 +
   确定性谓词通过）沉淀为确定性 fast path，后续同类输入 0 次 LLM 调用。
   语言层适配 = 引擎内路由（registry 命中跳过 LLM）+ 存储（平铺池+UID，同构）+
   铁律语言化（原始 LLM 输出不可直接登记——验证门必须是确定性函数）。
3. **诊断面（B1 源行号 + P2 错误位置 + KERNEL_ISSUE-SEM-1 编译期比较类型检查）**——
   试用流程中最高频迭代成本的直接消解。对"稳定可靠的语言自动机服务"，可定位的
   错误面是服务契约的一部分（试用方 172 轮中多次为"错误定位不到 ibci 源行"付出
   整轮成本）。
4. **思考模型运行面（N1+N4）**——云端共享思考模型成为常态端点后的运行必需
   （空 content 确定性处理/max_tokens 预算/finish_reason 暴露）。
5. **dict 可迭代（P9c 真实缺口）+ 尾逗号（A3）**——语言面低成本适配，
   试用方 D 纸带承载（dict 程序化构建）的直接受益。

### 5.2 如果要实现这种自然语言分析，IBCI 接下来应如何发展（工具/功能/机制）

按"语言自动机使命"分层（结构层机器承载 / 内容层 I/O 契约 / 运行细节 / 易用性）：

**P0（使命核心机制，材料齐备）**

1. **PT-FEAT-16 实施**（§四 Q1-Q4 裁决落定后开工）：
   - 批① 契约包 + provider + 配置（K1-K3 平移 + Q1 模块面归属调整）；
   - 批② `vector` 值类型（公理层，值语义 C5 判别，全量 pytest 评估）；
   - 批③ `ai.embed` 模块面 + MOCK:VEC + 检索最小闭包（K3 平移）；
   - 批④ 真实服务试用（SiliconFlow embedding 端点已验证可用）。
2. **N2 已验证答案注册表设计**：设计文档已产出（`tasks_docs/_n2_answer_registry.md`，平实展开 + 11 项设计问题逐问推荐，**待用户确认**）——
   API 形态（试用方建议的 `ai.crystallize(name, value, predicate)` 等四方法为输入，
   最终以 design-philosophy 审查为准：谓词类型（确定性 fn）、存储形态（平铺池+UID
   侧表 vs 独立 registry 对象）、检索键（结构签名——e31b 实证的模式匹配键）、
   生命周期（append-only 事件流 + correct 修订语义）、与 intent/snapshot 的交互
   （答案注册表是否进 snapshot？——裁定：不进，注册表 = 引擎级状态，随 save_state 持久；见 _n2_answer_registry Q7）。
3. **诊断面打包设计**（B1 源行号 + SEM-1 编译期比较类型检查 + P2 错误位置漂移）：
   三同域缺口一次设计（错误定位链：编译期 SEM 检查覆盖 → 运行期诊断码 →
   ibci 源行/列渲染）。

**P1（运行面必需，云端思考模型常态化的直接后果）**

4. **N1 思考模型支持**（**2026-09-06 重定性为根因项**：per-model `extra_body` 配置字段
   + 代码默认不发送 + 本机硬编码抑制 dict 迁入 api_config.json 归位 + 空 content
   确定性处理同批——详见 §五 5.4 形态 A）：落地后 `reasoning: true` 思考模型模式
   请求层可表达；max_tokens 预算键已随 T4 落地。**2026-09-06 追加合并**：生成参数面
   （temperature/top_p/top_k/seed 命名字段 + register_model 变体参数面 + `**kwargs`
   静默吞参改 fail-fast + call_info 采样姿态审计闭环 + model 条目未知字段严格性）
   并入本批（同一机制链，单设计 pass 覆盖六项——§五 5.5）。
5. **N4 finish_reason 暴露**：call_info 观测面补 `finish_reason`（截断检测是
   批量管线的运行细节：截断 ≠ 解析失败）。

**P2（易用性/能力缺口，低成本顺带）**

6. **dict 可迭代**（for k in d → to_list 协议覆盖 dict；P9c 真实缺口）。
7. **尾逗号（A3）**：多行容器字面量尾逗号接受（解析器项）。
8. **named-model 端点泄漏修复**（`IBCI_TRIAL_LLM_URL` 环境变量通道，取代两用例
   硬编码旧端点）+ T06 子目录复跑缺口 + 恶意边界 #15/#17/#19/#33（handoff §三 队列）。
9. **P10 引用语义文档**（dict/list 引用传递 + copy/deepcopy 语义，语言手册面）。

**挂起（方向保留）**

10. **N3 measure_freq（logprob 通道）**：measurement 类能力的机器承载；
    当前语料/探针设计全部手工（e26-e28 为验收基线），内化时机未到——
    待 embedding/答案注册表面落地后重估（铁律三类操作中唯一尚无机器承载的一类）。

### 5.3 不做什么（审查后的排除项）

- **不做通用化数值科学计算面**（VSA/numpy 形态）：内容层的重数值面留在外部——
  IBCI 承载"语言自动机的结构 + 模型 I/O 契约"，不承载"数值计算平台"
  （使命定位：稳定可靠的语言自动机服务，不是通用语言）。
- **不开放 `expected_type: vector`**（Q3 裁决）：向量产生面 = embedding provider 单源。
- **不把 judgment 类操作（LLM 评分）做成语言内建**（铁律：禁止）。
- **不改 P3（显式返回注解）**：类型论 ISA 的承载，试用方自身机制依赖。
- **不复制试用方的自包含测试 runner**（C4）：其零改动纪律的产物，不适用我方。

### 5.4 脚本层"覆写 LLM 配置面"评估（extra_body / 整 api_config schema overlay，2026-09-06 用户质询）

> 来源：更早试用者提出"直接允许 ibci 层书写 overlay，比如直接覆盖 extra_body 甚至直接覆盖
> 整个 api_config.json 的 schema"。该表述混合了三种不同形态，逐形态评估：

**形态 A · 配置级 `extra_body` 透传（N1 项 1）——✅ 合理且可行，前置到 P1 首位**

- 内容：`api_config.json` per-model 增加 `extra_body` 字段（dict），原样合并进请求体
  （如 `{"chat_template_kwargs": {"enable_thinking": false}}`）。
- **追加实证（本轮）**：provider 现有 `extra_body=` 参数接线点已齐备（3 处调用点：
  非流/流/probe）；且**双字段抑制 dict 当前硬编码在 tracked 代码层并随每个请求无条件发送**
  （`provider_impl.py` call/stream/probe 路径）——`reasoning: true` 声明的思考模型模式在
  请求层实际不可表达（抑制仍发出）；vendor 参数滞留代码层 = 与 named-model 端点泄漏同源
  的"机器事实未收敛配置单源"问题（AGENTS.local 纪律：机器事实归 gitignored 配置层）。
- 设计形态：per-model `extra_body`（fail-fast 类型校验，CFG_ 码族，与 T4 max_tokens 同型）；
  **代码默认 = 不发送**（对 vendor 零意见）；本机（SiliconFlow/qwen3.6）抑制 dict 迁入
  `api_config.json` = 机器事实归位。ibci 校验形状（dict）、vendor 解释语义——职责边界清晰
  （透传口子 ≠ 兜底：不是"未知参数静默吞掉"，是显式声明的 vendor 原生参数面）。
- 原则对照：单一权威源（vendor 参数从代码层回到配置单源）/ 字面量散落治理
  （code-quality 十查 #3：硬编码 vendor 魔法值提炼单点）/ 行业同构（OpenAI SDK 自身
  `extra_body` 即此形态——"一个透传口子比 n 个专用开关更可维护"成立）。

**形态 B · 语言层窄运行时开关（`ai.set_extra_body` 类 set_* 族）——⏸ 挂起**

- 现有运行时面设计语言 = "配置来自文件单源 + 运行时窄开关（set_retry/set_timeout/
  set_mock_mode/set_config/register_model）+ 命名路由（@NAME~）"。per-call 参数变化
  已被命名模型路由覆盖（register_model 每模型 timeout/max_tokens）。形态 A 落地后，
  若出现真实 per-script override 需求，按同型加窄开关（`set_*` 族），**不新开面**。

**形态 C · 脚本层整 schema 覆写（覆写整个 api_config.json 逻辑配置面）——❌ 不做**

- 技术可行（`apply_config` 已接受逻辑配置）但架构不合理，四重原则违反：
  1. **单一权威源**（design-philosophy §一）："生效的 LLM 配置"现有单一答案点
     （仓库根 api_config.json + 显式窄开关）。脚本级整 schema 第二入口 = 同一系统级概念
     两处可写 → T1 刚清场的 61 份副本双写真相问题以语言层形态复生；
  2. **密钥卫生回归**：schema 含 providers api_key。脚本内联整配置面诱导密钥进
     `.ibci` 源文件（tracked!）——直接回退 "{env:VAR} + tracked 不落密钥"纪律；
  3. **双通道**（code-quality 红线）：vendor 特定行为的既有原则性扩展点 = 宿主绑定
     自写 provider 实现（可实现任意请求组装）；整 schema 覆写是同一需求的第二、更弱
     扩展口（能力上做不到自定义 provider 的事）→ 同一决策两条通道；
  4. **可审计性**（使命）：生效配置可从单一文件回答 = 可审计；file + script overlay +
     set_* 调用栈三层叠加 = LLM 调用时的生效配置只能靠重建脚本内容推知。
- **背后的真实需求 ≠ 覆写，= 作用域**：唯一真实场景是 ihost 子环境需要不同 LLM 配置
  （ref E1：子环境 LLM 配置继承/隔离）。正确形态 = **scoping**（spawn API 接受配置引用，
  子环境独立配置作用域，父环境不受影响），非全局面覆写 → 归 ref E1 设计（批次表 P1-P2）。

### 5.5 生成参数面（temperature/top_p/top_k/seed）"脚本内实时临时修改"评估（2026-09-06 用户质询）

> 来源：更早试用者提出模型温度、top_k 等参数是否可在 ibci 脚本中"实时临时修改"。

**现状实证（本轮核查，五点事实链）**：

1. temperature/top_p/top_k/seed **全仓零存在**（ai 模块 / llm_protocol / provider 均无）；
   请求组装只发 model/messages/max_tokens/extra_body → **采样姿态 = 不透明的 vendor 默认**
   （"这个模型用什么采样"无法从任何单点回答 = 可审计性缺口）；
2. 配置校验器 model 条目**静默丢弃未知字段**（写 `temperature` 进 api_config 今天 =
   静默 no-op，无报错无记录——fail-fast 违反）；
3. `ai.register_model(name, url, key, model, **kwargs)` **`**kwargs` 静默吞未知参数**
   （语言面同型红旗：试用者今天若试图按此做参数变体，会被静默忽略）；
4. call_info 观测面不记录生成参数（采样姿态不可审计）；
5. 硬编码 extra_body 抑制 dict（§5.4 形态 A 已述，同域）。

**"实时临时修改"的四种形态逐评**：

| 形态 | 可行性 | 合理性 | 裁决 |
|------|--------|--------|------|
| **F1 配置 schema 一等化**（per-model 命名字段：temperature/top_p/top_k/seed，fail-fast 类型+范围校验，CFG_ 码族） | 高（与 T4 max_tokens / 形态 A extra_body 同链：schema→校验→ModelSpec→provider 解析→请求组装→call_info） | **合理且是补审计缺口**：采样姿态从"不透明 vendor 默认"变为"声明式单点"；字段集按使命取——temperature（铁律三操作的确定性旋钮：提案通道可多样性、测量通道要确定）/ seed（A/B 双轮一致纪律的原则性可复现旋钮）/ top_p·top_k（标准完备，防被挤进 extra_body 的范畴错误——标准参数走命名类型化面，extra_body 只走 vendor 特定）；缺省 = 不发送（文档化 vendor 默认）+ **call_info 记录有效值**（"未指定(vendor 默认)"也是可记录的答案） | ✅ 做（并入 N1 批） |
| **F2 命名模型按变体改参**（register_model 参数面扩展同套参数；注册即声明变体，@NAME~ 逐调用路由） | 高（命名路由本就是"按调用变化"的既有通道——endpoint/model/timeout/max_tokens 已按变体不同；纯参数变体甚至无需不同 model_id，同模型注册两个名字即可） | **这就是"实时临时修改"的合理形态**：变化 = 声明的数据（注册点可见、单源、不可变），非隐藏状态；无全局态、无实验泄漏；机制同构（同一通道补参数面，不新开面） | ✅ 做（并入 N1 批）；**前置必改**：`**kwargs` 静默吞参 → 显式参数 + 未知参数 fail-fast |
| **F3 逐调用内联语法**（`@~...~` 带参数后缀 / llm 调用函数带 kwargs 等语言语法） | 可行但代价大（全 LLM 表达式形态承载：内联行为/llm 可调用类/run_batch/流式/snapshot 捕获语义） | **不合理**：需求已被 F2 同构覆盖——同一决策（这次调用用什么采样姿态）两条表达 = 双通道；使命无"逐调用内联调参"的真实场景（172 轮实证：变化以"实验/通道"为单位，非以调用为单位） | ❌ 不做 |
| **F4 会话级全局 setter**（`ai.set_temperature(...)`） | 可行 | **不合理（仅生成参数；既有 set_retry/set_timeout 运行参数维持不动）**：① 可变全局态 + 每次调用须记录当前值（审计负担）；② **实验泄漏危害**——试用方 172 轮测量纪律依赖"姿态按实验声明"，全局温度槽跨实验泄漏正是破坏 A/B 一致的状态类；③ 同参数在不同模型上合法性不同（思考模型可能拒绝 temperature——o1 类先例），per-model 声明天然处理，全局 setter 无法表达 | ❌ 不做（F2 严格优于：声明数据 > 隐藏状态） |

**思考模型特殊注记**：采样参数支持随模型而异（OpenAI o1 类不接受 temperature；部分思考
模型受限）——per-model 命名声明天然适配（模型条目只声明该模型接受的参数；vendor 400 =
fail-fast 诊断，不静默丢弃）。这也是 F1/F2 正确而 F4 错误的技术注脚。

**批次归置**：F1+F2 与 N1（extra_body 形态 A）+ T4（max_tokens 先例）= **同一"生成参数面"
机制**（一条链：配置 schema → 校验 → 解析 → 请求组装 → call_info 审计闭环），并入 N1 批
（P1，P0 三线之后开工），单设计 pass 覆盖：① 标准参数命名字段 ② extra_body 逃生口
③ 硬编码抑制 dict 迁出归位 ④ `**kwargs` 静默吞参 → fail-fast ⑤ call_info 采样姿态审计
闭环 ⑥ 配置 model 条目未知字段严格性检查（静默丢弃 → fail-fast）。

### 5.6 配置格式生态对齐评估（api_config vs OpenCode/DSH；YAML 问题，2026-09-06 用户质询）

**证据**：OpenCode 官方配置文档（opencode.ai/docs/config/，2026-09-07 核查）+ DSH 本机
配置（`~/.dsh/settings.yaml` + `.credentials.yaml`）+ IBCI 现状（config_loader/provider_impl）。

| 维度 | IBCI api_config.json | OpenCode opencode.json[c] | DSH settings.yaml |
|------|---------------------|---------------------------|-------------------|
| 格式 | JSON（严格） | JSON + JSONC | YAML + 独立凭据文件（.credentials.yaml，600） |
| 连接层 | providers: base_url + api_key | provider: options.baseURL + apiKey | provider: baseURL + **apiKeyEnv（仅 env 变量名）** |
| 协议 | openai SDK 直连（OpenAI 兼容） | provider 按 OpenAI 兼容/各家 | `api: openai-completions` 显式标注 |
| 模型选择 | models: 命名 → {provider, model, 每模型参数} | model: "provider/model-id" 字符串引用 + models 段 | provider.models[]: id/name/contextWindow/input |
| 默认模型 | default_model（字符串引用或对象） | 顶层 "model" | agent-default-model: {provider, model} |
| 密钥通道 | {env:VAR} 插值（内联亦可） | env 变量 / auth 文件 | 仅 env 变量名（配置永不含 key） |
| 发现 | 仓库根单源 + 向上发现（.git 边界） | 多层合并（global→project[向上到 git]→inline→managed） | DSH_HOME 单点 |
| 校验 | 内建 fail-fast（12 CFG_ 码） | 发布公开 JSON Schema（编辑器校验） | 内建 |

**对齐度判断**：**设计思路对齐，差异是范围选择非设计分歧**——
① 三层结构（连接层 provider / 模型选择 models / 默认引用 default）三方同构；
② OpenAI 兼容为通用连接协议三方同构（DSH 显式标注 openai-completions）；
③ env 密钥通道三方同构（DSH 最严：仅变量名；IBCI {env:VAR} + 内联可选，项目范围下合理）；
④ 向上发现（.git 边界）与 OpenCode 项目配置发现同思路；IBCI 单源不合并 = T1 裁定
（项目级语言服务的范围选择，与 DSH 单点同形；OpenCode 多层合并是全局 CLI 工具 +
企业 managed 层的范围产物，不是更"先进"的设计）；
⑤ 字段命名随生态惯例（Python snake_case 对齐 openai SDK / JS camelCase 对齐 Node 生态），
语义一一对应。
**对齐缺口（记录，不紧迫）**：① 无公开 JSON Schema（OpenCode 发布 schema 供编辑器
校验/补全——N1 批 schema 生长[extra_body/采样参数]后可顺带发布，P2 可选）；② DSH
"contextWindow/input 能力元数据"对应 IBCI 的动态 `probe_model`（不同路线：静态声明 vs
动态探测，IBCI 路线适配试用场景，无需改）。

**YAML 评估（两问两答）**：

1. **api_config 支持 YAML？——❌ 不做，JSON 保持单格式**。依据：
   - 生态事实：LLM 工具配置主流 = JSON（OpenCode/VS Code/OpenAI SDK 生态）；YAML 主流在
     DevOps/k8s/CI 域（DSH 属之）。无"应跟随 YAML"的生态压力；
   - 语言数据面一致性：JSON 是 IBCI 一等数据面（json 模块 / dict↔native / LLM 结构化
     输出约定 = JSON——试用方 172 轮范式全部 JSON）；配置格式与语言数据面异构 = 同一
     "数据"概念两种形态（设计语言割裂）；
   - 语义纪律：YAML 隐式语义（类型推断/锚点/别名/`yes-no-on-off` 陷阱/性进制数字）与
     IBCI 显式 + fail-fast 纪律相悖——JSON 严格解析本身就是 fail-fast 面；
   - 成本：双格式 = 配置边界双通道（发现优先级/两套解析面）+ 新增 PyYAML 运行时依赖
     （现仅 openai 一个依赖）。
   - 若未来出现"配置注释"真实需求：对齐的扩展是 **JSONC**（OpenCode 同款，非 YAML），
     且当前不需要（api_config 是 gitignored 机器文件，非人工协作书写面）。
2. **IBCI 语言层支持 YAML（yaml 模块/值类型）？——❌ 不做**。依据：
   - 使命无消费者：试用方 172 轮结构化数据全部 JSON；LLM 结构化输出行业约定 = JSON
     （C2 契约建立在 JSON 上）；YAML 不是 LLM 输出形态；
   - 范围漂移：新增解析器依赖 + 值面 = 通用语言方向的扩张（违背使命定位）；
   - json 模块即语言数据格式面，与 LLM 提案/裁判范式（e04/e12/e13/e29 全部 json.parse）
     同构——这是 IBCI 对语言自动机使命的正确数据格式选择。

---

## 六、本轮工作记录（free-explore @ 2026-09-06）

| 项 | 状态 |
|----|------|
| 端点切换 SiliconFlow（chat + embedding 验证 + 弃用注记） | ✅ 完成（api_config.json / AGENTS.local.md / TEMP 指南） |
| 试用工程文档全量读取（14 docs + kernel_overlay + 实验脚本 + 172 轮记录抽样） | ✅ 完成 |
| P9a/P9b 根因定位 + 修复 + 10 判别测试 + 全量零回归 | ✅ commit `1205a530`（3219 passed / 1 skipped） |
| P9c/P11 核验定性（P9c = dict 不可迭代；P11 → 新发现 SEM-1 编译期比较类型检查缺失） | ✅ 登记 INDEX（KERNEL_ISSUE-SEM-1） |
| Q1-Q4 裁决建议 + K1-K3 可用性审查 | ✅ 本文件 §四 |
| 适配/发展方向分析 | ✅ 本文件 §五 |
| 残留队列 | 见 §五 5.2（P0×3 / P1×2 / P2×4 / 挂起×1）+ handoff §三（恶意边界 #15/#17/#19/#33、T06 缺口、named-model 泄漏、BOUNDARY-LLM-5 裁定） |

> 注：试用方文档中的 API 命名/签名均为**建议形态**（"最终以开发智能体的
> design-philosophy 审查为准"）。**状态（2026-09-06/07）**：用户已认可本文件全部建议
>（Q1-Q4 / 批次顺序 / P0 三线 / 排除项）；追加三组独立评估已落账——§五 5.4
> overlay 配置面（A 做 / B 挂起 / C 不做）、§五 5.5 生成参数面（F1/F2 做，并入 N1 批；
> F3/F4 不做）、§五 5.6 配置格式生态对齐 + YAML 评估（JSON 单格式维持；语言层不做
> YAML；公开 JSON Schema 可选随 N1 批）。设计阶段（`tasks_docs/_<task>.md`）与实施
> 按 handoff §五 队列推进（第一动作 = 线 1 诊断面设计文档）。
