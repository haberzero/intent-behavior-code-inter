# DESIGN — T11 stream 流式 + run_batch 批量（五大地基新特性试用地基）

> **目标**：对五大地基重构后 **stream 流式消费面**（`ai.stream_call` / `ai.stream_channel`）
> 与 **run_batch 批量消费**（行为值逐项绑参 + llm 可调用实例逐项参数化）全面试用。
> mock 层确定性 + 真实 LLM 层回归。
> 参考规范：`_toolkit/CLASSIFICATION.md` / `_toolkit/CONTRACT_FORMAT.md`。

## 覆盖矩阵（mock 层已建）

| 维度 | 覆盖特性 | 语法章节 | 用例组 | 覆盖状态 |
|------|----------|----------|--------|----------|
| M1 | `ai.stream_call` await 取完整文本（MOCK:STREAM 分块拼接） | 11 §11.3 | M1 | ✅ PASS |
| M2 | `ai.stream_call` 赋值自动等待（auto-yield） | 11 §11.3 | M2 | ✅ PASS |
| M3 | `ai.stream_channel` 逐块 recv 增量消费 | 11 §11.3 | M3 | ✅ PASS |
| M4 | `ai.run_batch` 行为值批量（lambda 逐项绑参） | 07 §7.4 | M4 | ✅ PASS |
| M5 | `ai.run_batch` llm 可调用实例逐项参数化 | 08 §8.3 | M5 | ✅ PASS |

> 迁移备注：T08/T01 的 4 个旧字符串形态 stream 用例（D5-01/D5-02/D5-08/D2-35）已迁移到
> 新 llm 可调用实例形态（见 REGISTER 迁移记录）。

## 硬约束

- 每用例 `--timeout` 必填（run_batch 默认 60s，OS 级 SIGKILL 死循环保护）。
- mock 用例 `# expect-llm: false` + `ai.set_mock_mode()`（确定性）。
- 用例头部断言必填；注释只保留功能说明 + `# doc:` 引用。

## 真实 LLM 层（LLM 回归，待运行）

- L1 真实 `stream_call` await 完整文本（D5-01 迁移用例）
- L2 真实 `stream_channel` 逐块消费（D5-02 迁移用例）
- L3 流式错误传播 / llmexcept 组合（恶意边界面）
- L4 真实 run_batch 行为 + llm 实例批量

## 分类与记录

- 分类规范：PASS / GUARD / KERNEL_ISSUE / BOUNDARY / DOC_ISSUE / LLM_BEHAVIOR / LIMIT / HARNESS。
- 缺陷登记：`trials/INDEX.md` 生命周期状态机 + REGISTER.md。
- 只记录不修复优先；不为规避缺陷改套件。
