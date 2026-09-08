# N3 measure_freq（logprob 测量通道）设计

> 状态：**待决（挂起，方向保留）**。本文 = R3-⑬"设计优先"交付物——探针实证 + 面设计 +
> 重估触发条件。实施未启动。单点记录：发展方向裁定见 `_trial_intake_analysis.md` §1.6 /
> `_free_explore_handoff.md` N3 行。

## 一、定位

`measure_freq` = 采样模型自身分布的统计量测量（cloze 频率 / logprob / surprisal）——
铁律允许的**第三类操作**（measurement：可复算、可审计，区别于 judgment 主观裁决）。
试用方 e26-e28（cloze/surprisal 测量）为现成验收基线，当前全部落外部 Python
直连端点（IBC 无 logprob 通道）。N3 = 该测量面的机器承载（收窄"内容层数值/统计
面全落外部 Python"边界的第二块，第一块 = PT-FEAT-16 embedding 面）。

## 二、探针实证（SiliconFlow，2026-09-08，真实端点 `api.siliconflow.cn/v1`）

模型 `Qwen/Qwen3.6-35B-A3B`，openai SDK 3.8.0 直连实测：

| 通道 | 请求 | 结果 |
|------|------|------|
| **chat completions**（IBCI provider 现用通道） | `logprobs=True, top_logprobs=5` | **400 校验错**（`top_logprobs` 需 `logprobs=true`，但 chat 面 logprobs 无效） |
| **chat completions** | 仅 `logprobs=True` | 接受但**静默忽略**——响应**无 `logprobs` 字段**（不报错、无数据） |
| **legacy completions** | `logprobs=N`（top-N） | **完整支持**——返回 `tokens` / `token_logprobs` / `top_logprobs`（逐 token top 候选） |

legacy completions 样例（`prompt="The capital of France is", logprobs=3`）：

```
tokens         = [" Paris", ",", " a", " city"]
token_logprobs = [-0.547, -0.716, -0.741, -0.322]
top_logprobs[0]= {" Paris": -0.547, " a": -2.172, " the": -3.047}
top_logprobs[1]= {",": -0.716, ".": -0.841, "\n": -4.029}
```

**结论**：logprob 能力在 SiliconFlow 后端**存在**，但仅经 **legacy completions**
端点暴露；IBCI provider 的 **chat completions** 通道**不暴露**（静默忽略）。

## 三、设计影响

- IBCI 的 LLM 调用通道 = **chat completions**（provider `call()`/`stream()` 用
  `client.chat.completions.create`）。故**现有 provider 路径无法暴露 logprobs**——
  非 IBCI 缺陷，是通道形态约束（chat 面 vs completions 面）。
- 要落地 measure_freq，须**新增一条 completions 形态的 logprob 通道**：
  - 面定位：`ai` 模块内建方法（如 `ai.measure_logprob(prompt, top_n?) -> dict`
    返回 `{tokens, logprobs, top_logprobs}`）或独立 `measure` 面；
  - 机制：provider 新增方法走 `client.completions.create`（**非** chat），
    与现有 chat 通道并存（双通道不同端点形态，非双写真相——chat 做对话、
    completions 做 logprob 测量，语义分工明确）；
  - 约束：completions 端点为 OpenAI legacy 形态（部分供应商已弃用）——端点
    可用性是**供应商机器事实**，须探针前置（如 PT-FEAT-16 的 embedding 探针）。

## 四、裁定：待决（挂起，方向保留）

1. **与试用方自我裁定一致**：corpus/probe 设计当前**全部手工**（Python 直连），
   内化时机未到——e26-e28 为现成验收基线，无需 IBCI 承载即可跑通。
2. **通道约束**：现有 chat 通道不暴露 logprobs，落地须新增 completions 通道
   （§三）——属新面设计，非小改。
3. **重估触发条件**（满足其一即重估启动）：
   - provider 支持 completions/logprob 通道（或 embedding 面 PT-FEAT-16 落地时
     同批评估——二者同属"收窄内容层数值面落外部 Python"边界）；
   - corpus/probe 测量设计从手工内化为 IBCI 可承载（有稳定语料/探针形态）。
4. **不做什么**：不在 chat 通道上强行探测 logprobs（静默忽略 = 无数据，探测
   无意义）；不为此新增独立数值科学计算面（同 PT-FEAT-16 排除项）。

## 五、验收基线（重估后实施参照）

- 试用方 e26-e28（cloze/surprisal 测量，Python 直连）= 行为基线；
- 本探针样例（§二）= 端点能力基线（completions 面 logprobs 形态）。
