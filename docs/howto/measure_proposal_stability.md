# 如何测量弱模型提案稳定性

> 本文档解决"如何量化弱模型对同一任务多次运行所产**提案**（answer/proposal）的
> 稳定性"的问题。面向需要评估"模型答案跨运行是否一致"的开发者（如结晶注册表
> 候选答案的稳定性验收）。依赖 run 级 journal（跨运行语料源）与
> `measure_weak_model_drift.md` 的漂移信号。阅读前需了解 journal 机制
> （`docs/syntax/15_diagnostics.md` run 命令可观测面节）。

## 一、什么是提案稳定性

弱模型对**同一 prompt** 多次运行，产出的提案（最终答案文本）可能：
- **完全一致**（稳定）；
- **措辞不同但语义等价**（轻度漂移）；
- **结构/结论不同**（重度漂移 / 不稳定）；
- **被截断**（`finish_reason=length`，答案不完整）。

提案稳定性 = 跨运行提案的**一致性度量**。本 howto 给出机器可算的度量面
（经 journal 语料），供"候选答案是否稳定到可结晶"的判定。

## 二、语料源：journal 跨运行收集

每次 `run` 产出 journal（`llm_journal/<run-id>.jsonl`，CLI 默认开）。批量运行
N 次后，收集 N 个 journal 文件 = 跨运行提案语料。

```bash
# 同一用例跑 N 次，每次 --result-json（trailer 的 "journal" 字段定位 run-id）
for i in $(seq 1 20); do
    python -m ibci run my_case.ibci --result-json 2>/dev/null | \
        python -c "import json,sys; print(json.load(sys.stdin)['journal'])"
done > /tmp/journal_ids.txt
# 每个 journal-id → llm_journal/<id>.jsonl，取该用例对应调用的 raw_response
```

> 一个 journal 文件含该 run 的**全部** LLM 调用（多调用用例按 `seq` /
> `node_uid` 定位目标调用）。提案 = 目标调用的 `raw_response`（或 `content`）。

## 三、稳定性度量面

对 N 次运行的提案集合 `{p_1, ..., p_N}`，机器可算的度量：

| 度量 | 定义 | 稳定判据 |
|------|------|---------|
| **完全一致率** | 众数提案的频次 / N | 越高越稳定（1.0 = 完全一致） |
| **归一化一致率** | 归一化（去空白/大小写/标点）后众数频次 / N | 排除措辞噪声后的稳定性 |
| **长度离散度** | 提案长度的标准差 / 均值（CV） | 越低越稳定（长度波动小） |
| **截断占比** | `finish_reason == "length"` 的调用占比 | 0 = 无截断漂移 |
| **提案两两相似度** | 平均 token 重叠率（Jaccard） | 越高越稳定 |

## 四、最小度量脚本

```python
# stability.py：从 N 个 journal 提取目标调用提案并算稳定性度量
import json, re, sys
from collections import Counter

def extract_proposals(journal_paths, node_uid=None):
    """从 journal 提取目标调用的提案（raw_response）。node_uid 定位多调用用例。"""
    props = []
    for p in journal_paths:
        for line in open(p, encoding='utf-8'):
            r = json.loads(line)
            if r.get('type') != 'call':
                continue
            if node_uid and r.get('node_uid') != node_uid:
                continue
            if r.get('error'):      # 失败调用不计入提案
                continue
            props.append(r['raw_response'])
    return props

def normalize(s):
    s = s.lower().strip()
    return re.sub(r'[\s\W]+', ' ', s).strip()

def report(props):
    n = len(props)
    if n == 0:
        print("无有效提案"); return
    c = Counter(props)
    exact = c.most_common(1)[0][1] / n
    cn = Counter(normalize(p) for p in props)
    norm = cn.most_common(1)[0][1] / n
    lens = [len(p) for p in props]
    cv = (sum((l - sum(lens)/n)**2 for l in lens) / n) ** 0.5 / (sum(lens)/n)
    print(f"N={n}  完全一致率={exact:.2f}  归一化一致率={norm:.2f}  长度CV={cv:.2f}")

if __name__ == '__main__':
    report(extract_proposals(sys.argv[1:]))
```

用法：`python stability.py /path/to/journal1.jsonl journal2.jsonl ...`

## 五、稳定性判定（结晶门槛）

提案稳定性是"候选答案可否结晶入注册表"的验收信号（见
`docs/syntax/16_knowledge_system.md` 知识注册表）。判定惯例：

- **完全一致率高（如 ≥0.9）** + **截断占比 0**：提案稳定，可结晶（登记一次，
  查表命中 0 LLM 调用）。
- **归一化一致率高但完全一致率低**：措辞漂移但语义稳定——结晶前需归一化
  （或接受措辞差异，以语义等价验证门约束）。
- **截断占比 > 0**：先解决 `max_tokens` 预算（见 `measure_weak_model_drift.md`），
  再评估稳定性（截断提案不完整，不应结晶）。

## 六、与漂移测量的关系

- `measure_weak_model_drift.md`：**单信号**观测（finish_reason 截断 + 输出漂移
  的即时/journal 面）——回答"哪次偏离了"。
- 本文：**跨运行统计**（提案一致性/离散度）——回答"这个模型对该任务整体稳不稳"。
- 二者共享 journal 语料源；漂移信号（截断/长度）是提案稳定性的输入。

## 相关文档

- `measure_weak_model_drift.md`：输出漂移测量（finish_reason 最小用法 + call_info 两形态）。
- `run_trials.md`：试用套件运行（批量 run 工程面）。
- `docs/syntax/16_knowledge_system.md`：知识注册表（稳定提案的结晶归宿）。
