# DESIGN — T13 意图一等值 + snapshot 冻结 + intent_context OOP（五大地基新特性试用地基）

> **目标**：对五大地基重构后 **意图一等值嵌入**（`@+ $x` eager 值压栈 / `@-` 按值匹配）、
> **snapshot 意图冻结 vs lambda 调用点 live**、**intent_context OOP 方法族**
> （get_current/use/push/pop/fork/merge/combine/clear + 缺参 fail-fast）全面试用。
> mock 层确定性 + 真实 LLM 层回归。
> 参考规范：`_toolkit/CLASSIFICATION.md` / `_toolkit/CONTRACT_FORMAT.md`。

## 覆盖矩阵（mock 层已建）

| 维度 | 覆盖特性 | 语法章节 | 用例组 | 覆盖状态 |
|------|----------|----------|--------|----------|
| I-M1 | 意图一等值：@+ $x eager 压入当时值，重赋值不影响 | 09 §9.2 | I-M1 | ✅ PASS |
| I-M2 | 意图按值移除：@+ 后 @- 同值字面量 | 09 §9.2 | I-M2 | ✅ PASS |
| I-M3 | snapshot 冻结定义时意图 vs lambda 调用点 live | 09 §9.2 + 07 §7.4 | I-M3 | ✅ PASS |
| I-M4 | intent_context OOP 文档工作流（push/use/pop/push/re-use 上下文切换） | 09 §9.3 | I-M4 | ✅ PASS |
| I-G1 | intent_context.push 缺参 fail-fast（B3 定案） | 09 §9.3 | I-G1 | ✅ GUARD |

> **观测手段**：`ai.get_current_call_info()["intents"]["merged"]` 断言实际注入意图（mock 下
> call_info 无 `sys_prompt` 键——见 REGISTER BOUNDARY 备注；intents 三层是最干净断言面）。

## 硬约束

- 每用例 `--timeout` 必填（run_batch 默认 60s，OS 级 SIGKILL 死循环保护）。
- mock 用例 `# expect-llm: false` + `ai.set_mock_mode()`（确定性）。
- 用例头部断言必填；注释只保留功能说明 + `# doc:` 引用。

## 真实 LLM 层（LLM 回归，待运行）

- L1 真实意图一等值注入影响模型输出（@+ $x 风格约束服从）
- L2 真实 snapshot vs lambda 意图隔离（调用点意图不泄漏进 snapshot）

## 分类与记录

- 分类规范：PASS / GUARD / KERNEL_ISSUE / BOUNDARY / DOC_ISSUE / LLM_BEHAVIOR / LIMIT / HARNESS。
- 缺陷登记：`trials/INDEX.md` 生命周期状态机 + REGISTER.md。
- 只记录不修复优先；不为规避缺陷改套件。
