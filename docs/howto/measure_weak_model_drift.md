# 如何测量弱模型输出漂移

> 本文档解决"如何观测弱模型（小参数 / 低温度不可控）输出的漂移与截断"的问题。
> 面向需要批量运行 LLM 用例、评估模型输出稳定性的开发者。漂移测量依赖两个
> 观测面：`call_info`（两次形态：活面 + journal 持久面）与 `finish_reason`
> （截断检测）。阅读前需了解 run 级可观测子系统（journal 见 `docs/syntax/15_diagnostics.md`
> run 命令可观测面节 + `docs/howto/run_trials.md`）。

## 一、什么是输出漂移

弱模型在**相同 prompt** 下多次运行，输出内容/结构可能不一致（措辞漂移、
字段缺失、答案长度波动）。漂移测量的目标：用机器可判定的信号定位"哪次运行
偏离了"，而非人工逐条比对。两个核心信号：

- **`finish_reason`**：`stop` = 正常完成；`length` = **达到 `max_tokens` 被截断**
  （弱模型"没说完"）。重复出现 `length` = 输出预算不足的漂移信号。
- **输出内容/长度**：`raw_response` / `content` 的跨运行差异（需 journal 跨运行
  语料，见 `measure_proposal_stability.md`）。

## 二、call_info 的两形态

`call_info` 是"最近一次 LLM 调用的诊断信息"，有两形态：

### 形态 1：活面（进程内即时）

`ai.get_current_call_info()` 返回**最近一次调用**的诊断 dict（内核 LLM 执行器
主线程单写槽，取最近值）。适合**单次运行内的即时检查**（运行结束前读取）。

```ibci
import ai

str ans = @~回答：1+1=?~
dict ci = ai.get_current_call_info()
print(ci["target_model"])     # 本次调用的目标模型
print(ci["user_prompt"])      # 本次 user prompt
if ci.has("finish_reason"):
    print(ci["finish_reason"])  # stop / length（截断检测面）
print(ci["raw_response"])     # 原始响应文本
```

> 活面只保留**最近一次**调用（单写槽覆盖）。要跨多次调用/跨运行比对，用
> 形态 2（journal 持久面）。

### 形态 2：journal 持久面（跨调用 / 跨运行）

CLI `run` 默认开启 LLM journal（append-only JSONL，`llm_journal/<run-id>.jsonl`；
`--no-journal` 关闭）。每次 LLM 调用（成功/失败两面）记一行，字段：

```
v / type / seq / ts / ts_mono / node_uid / target_model / sys_prompt /
user_prompt / content / raw_response / finish_reason / generation / usage / error
```

journal 是**跨运行语料源**——批量运行 N 次后，解析 journal 逐行取得每次调用的
`finish_reason` / `raw_response` / `usage`，做跨运行漂移统计。

```bash
# 批量运行 + 收集 journal（run 命令默认开 journal；--result-json 收尾 trailer
# 的 "journal" 字段给出 run-id，据此定位 journal 文件）
python -m ibci run my_case.ibci --result-json
# 解析 journal（每行一个 JSON 调用记录）
python -c "import json,sys
for line in open(sys.argv[1]):
    r = json.loads(line)
    if r['type']=='call':
        print(r['seq'], r['finish_reason'], len(r['raw_response']))" <run-id>.jsonl
```

## 三、finish_reason 最小用法

`finish_reason` 是弱模型漂移的**第一信号**（截断检测）：

- **`length`**：输出达到 `max_tokens` 上限被截断——弱模型"没说完"，答案可能
  不完整。批量出现 `length` = `max_tokens` 预算对弱模型不足（调大 `max_tokens`
  或缩短 prompt）。
- **`stop`**：模型正常停止（答案完整）。

最小用法（活面即时判）：

```ibci
import ai

str ans = @~用一句话解释量子纠缠~
dict ci = ai.get_current_call_info()
if ci.has("finish_reason") and ci["finish_reason"] == "length":
    print("警告：输出被 max_tokens 截断（finish_reason=length），答案可能不完整")
```

最小用法（journal 批量判）：对一批 run 的 journal，统计 `finish_reason == "length"`
的调用占比——占比升高 = 该模型在该任务上的截断漂移。

## 四、漂移测量流程

1. **固定 prompt 与 `max_tokens`**（控制变量；`max_tokens` 经 api_config model 条目声明）。
2. **批量运行 N 次**（`run_batch` 或循环 `run`），每次产出 journal。
3. **收集 journal**（`--result-json` trailer 的 `journal` 字段定位 run-id → journal 文件）。
4. **跨运行统计**：`finish_reason` 分布（length 占比）+ `raw_response` 长度/内容
   离散度（见 `measure_proposal_stability.md` 的提案稳定性测量）。
5. **判定**：length 占比高 = 截断漂移（调 `max_tokens`）；内容离散度高 = 措辞漂移
   （弱模型固有，需接受或用确定性验证门约束）。

## 相关文档

- `measure_proposal_stability.md`：弱模型**提案稳定性**测量（journal 跨运行语料的
  提案一致性/离散度统计）——本文的漂移信号是其输入。
- `run_trials.md`：试用套件运行（批量 run + journal 收集的工程面）。
- `docs/syntax/15_diagnostics.md` run 命令可观测面节：journal / `--replay` /
  预算 / `--result-json` 的机制面。
