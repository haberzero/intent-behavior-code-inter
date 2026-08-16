# T09_protocol_kernel_impact — 协议化内核大重构影响确认（真实 LLM 试用）

> 承接主线：协议化大重构（内核协议注册表化 + 架构级重构）。
> 目标：以真实 LLM 确认重构影响——既有套件回归 + 新能力端到端可用。
> 运行结果与缺陷登记见本套 `logs/`、`REGISTER.md` 与 `trials/INDEX.md`。

## 一、工作模式与硬约束

| 约束 | 内容 |
|------|------|
| 死循环保护 | 每例经 harness 硬超时 SIGKILL 进程组兜底 |
| 真实为主 | 真实 LLM（本地 qwen3.6-35b-a3b 非思考模式 @ 127.0.0.1:1234），mock 仅对照 |
| 记录优先 | logs/ + register.jsonl + batch_result.jsonl 确定性记录 |
| 修复纪律 | 根因修复 + tests/ 回归；禁 compat shim / 胶水 / tricky |
| 禁 push | 全程本地 commit |

## 二、Phase 1：既有套件真实 LLM 回归（重构影响确认）

对 T01/T02/T05(D3)/T06/T07/T08 的全部真实 LLM 用例在最新代码重跑，逐类对照
既有登记（`trials/INDEX.md` / 各套 `REGISTER.md`）确认无分类漂移。

## 三、Phase 2：新能力真实 LLM 试用（N1-N8）

| 用例 | 覆盖 |
|------|------|
| N1-impl-llm-method | impl 块内 LLM 方法（协议方法由 LLM 实现） |
| N2-impl-generic-bound | impl 补方法 + 泛型协议 bound + LLM 输出实参 |
| N3-llm-fn-firstclass | LLM 函数第一等函数值（fn 变量持有并调用） |
| N4-long-prompt | 长 prompt 压力（内联行为表达式） |
| N5-concurrent-dispatch | 并发 dispatch 压测（dispatch_eager CPS 化路径） |
| N6-llmexcept-real-retry | llmexcept 自动错误回喂 + retry 收敛（统一 CPS 路径） |
| N7-llm-class-method | 类内 LLM 方法真实调用 |
| N8-fromprompt-class | 用户类 `__from_prompt__` LLM 输出解析 |

覆盖的协议化新能力：retroactive 方法补充 / 协议 bound / LLM 函数统一 / dispatch CPS 化。

## 四、后续压力维度（T08 待扩展项延续）

- 更长 prompt（>4k token）、多轮长对话、批量并发上限、多模态真实媒体文件（media 封存除外）。
