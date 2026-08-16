# T06_class_identity — 统一类身份模型回归 + 真实试用

> **试用与记录任务，不是修复任务**。目标：对统一类身份模型
> （入口类 qualified / 单类表 / 线程侧表统一 /
> is_truthy 任务本地化）后的最新内核做**回归 + 对抗 + 真实 LLM** 全方位
> 试用，确认宏观重构的健康与边界，并复验遗留边界触发用例。
>

## 一、工作模式与硬约束

| 约束 | 内容 |
|------|------|
| 死循环保护 | 每例经 harness 硬超时 SIGKILL 进程组兜底；无超时不运行 |
| 记录优先 | 只记录登记，不改内核；logs/ + register.jsonl + REGISTER.md 确定性记录 |
| 分层 | mock 用例（快）+ 真实 LLM 用例（qwen3.6-35b-a3b @ 127.0.0.1:1234，先探测） |
| 分类 | PASS | KERNEL_ISSUE | BOUNDARY | LIMIT | DOC_ISSUE | LLM_BEHAVIOR | GUARD | HARNESS |
| 禁 push | 全程本地 commit |

## 二、检测矩阵

### D1 — 统一类身份模型回归（mock）

| 用例 | 目标 |
|------|------|
| D1-01 | 入口模块类 qualified：`type()` 裸名显示 + 类表 qualified 键（run_string 与文件入口双路径） |
| D1-02 | 入口类与导入同名类彻底隔离（main.Box vs geo.Box 方法表/字段不串扰） |
| D1-03 | run_string 入口模块名稳定（`__string_exec__`，跨运行可复现） |
| D1-04 | get_class 裸名回落仅命中内置（`get_class("Box")` 不再命中入口类） |
| D1-05 | 单类表：Bootstrapper 委托 KernelRegistry（Enum 无 [Enum Hook] 仍正确） |

### D2 — 类身份边界/对抗（mock）

| 用例 | 目标 |
|------|------|
| D2-01 | 入口类泛型特化 qualified（main.Box[int]）运行/序列化 |
| D2-02 | 入口类非泛型继承链（is_assignable 父 module 补全） |
| D2-03 | 入口类 LLM 输出类型解析（`-> Point` __from_prompt__ module 感知） |
| D2-04 | 线程 worker 内入口类 + 导入类双路径（KI-1 核销） |
| D2-05 | 跨模块类 LLM 输出 hint（node_to_type module 感知） |
| D2-06 | 三模块同名类（geo/graph/data）+ 入口类共存 |
| D2-07 | 入口类序列化 round-trip（qualified 名保真） |
| D2-08 | 入口类作内置泛型实参（list[入口类]） |

### D3 — 真实 LLM（qwen3.6-35b-a3b）

| 用例 | 目标 |
|------|------|
| D3-01 | 入口类 `-> Point` __from_prompt__ 真实解析（module 感知） |
| D3-02 | 跨模块类 `-> geo.Box` 真实 LLM 输出 |
| D3-03 | 意图 @/@! + 入口类组合 |
| D3-04 | 线程 + LLM 组合（worker 内 LLM 调用 module 上下文） |
| D3-05 | mock↔真实切换 + 入口类（回归） |

### D4 — T05 关键用例核销回归（mock）

| 用例 | 目标 |
|------|------|
| D4-01 | 线程 worker 内 geo.Box(5).get() = 405（跨模块类身份） |
| D4-02 | T05 D1-12 入口遮蔽回归 |

## 三、运行

```bash
# 服务探测
curl -s -m 5 http://127.0.0.1:1234/v1/models   # 期望含 qwen3.6-35b-a3b
# 全量（mock 先 + llm 后）
python _toolkit/run_batch.py T06_class_identity --timeout 40 --parallel 4 --repo-root <repo>
```

## 四、产出

- `logs/` + `register.jsonl` + `REGISTER.md`
- KI-1 核销记录 + 新缺陷登记（如有）
- 收尾同步 NEXT_STEPS/HANDOFF/WORKLOG。全程本地 commit、禁 push。
