# T09_protocol_kernel_impact — 协议化内核大重构影响确认（真实 LLM 试用）

> 2026-08-16。承接主线：exp/protocol-kernel 协议化大重构（批次 1-3 + 架构级重构）。
> 目标：在最新代码上以真实 LLM 确认重构影响——既有套件零回归 + 新能力端到端可用。

## 一、工作模式与硬约束

| 约束 | 内容 |
|------|------|
| 死循环保护 | 每例经 harness 硬超时 SIGKILL 进程组兜底 |
| 真实为主 | 真实 LLM（qwen3.6-35b-a3b @ 127.0.0.1:1234），mock 仅对照 |
| 记录优先 | logs/ + register.jsonl + batch_result.jsonl 确定性记录 |
| 修复纪律 | 根因修复 + tests/ 回归；禁 compat shim / 胶水 / tricky |
| 禁 push | 全程本地 commit |

## 二、Phase 1：既有套件真实 LLM 回归（重构影响确认）

对 T01/T02/T05(D3)/T06/T07/T08 的全部真实 LLM 用例在协议化分支最新代码重跑：

| 套件 | 用例数 | 结果 | 基线对照（重构前） |
|------|--------|------|------|
| T01 | 57 | 54 PASS + 2 GUARD + 1 LLM_BEHAVIOR | 与 2026-08-14/15 基线逐类一致 |
| T02 | 3 | 3 PASS | T5-enum-value-ne-name 由 LLM_BEHAVIOR 转 PASS（模型非确定性） |
| T05 cases_D3 | 8 | 8 PASS | 一致 |
| T06 | 7 | 7 PASS | 一致 |
| T07 | 7 | 7 PASS | 一致 |
| T08 | 37 | 29 PASS + 4 LLM_BEHAVIOR + 2 BOUNDARY + 1 GUARD + 1 LIMIT | 与第一轮同维度分类一致 |

**结论：108 例真实 LLM 回归，分类与重构前基线完全一致——协议化大重构零回归。**

## 三、Phase 2：新能力真实 LLM 试用（8 例全 PASS）

| 用例 | 覆盖 | 结果 |
|------|------|------|
| N1-impl-llm-method | impl 块内 LLM 方法（协议方法由 LLM 实现） | PASS |
| N2-impl-generic-bound | impl 补方法 + 泛型协议 bound + LLM 输出实参 | PASS |
| N3-llm-fn-firstclass | LLM 函数第一等函数值（fn 变量持有并调用） | PASS |
| N4-long-prompt | 长 prompt 压力（内联行为表达式） | PASS |
| N5-concurrent-dispatch | 并发 dispatch 压测（dispatch_eager CPS 化路径） | PASS |
| N6-llmexcept-real-retry | llmexcept 自动错误回喂 + retry 收敛（统一 CPS 路径） | PASS |
| N7-llm-class-method | 类内 LLM 方法真实调用 | PASS |
| N8-fromprompt-class | 用户类 `__from_prompt__` LLM 输出解析 | PASS |

**结论：协议化新能力（retroactive 方法补充 / 协议 bound / LLM 函数统一 / dispatch CPS 化）
经真实 LLM 端到端验证全部可用。**

## 四、发现

- **无新增 KERNEL_ISSUE / BOUNDARY / DOC_ISSUE**（既有 2 BOUNDARY + 1 LIMIT 为 T08 第一轮
  已登记项复现：BOUNDARY-LLM-2/3、未读赋值静默 LIMIT）。
- 用例修正 2 处（试用代码问题，非内核）：N7 未初始化变量、N8 `__from_prompt__` 签名
  （类方法无 self，契约返回 tuple——与既有 D3-70 约定一致）。

## 五、后续压力维度（T08 待扩展项延续）

- 更长 prompt（>4k token）、多轮长对话、批量并发上限、多模态真实媒体文件（media 封存除外）。
