# DESIGN — T10 llm 可调用类（五大地基新特性试用地基）

> **目标**：对五大地基重构后 **llm 可调用类** 全面试用——直接调用、装配配置字典
> （`user_prompt` / `prompt_slots` / `expected_type`）、参数按位绑定、`__intent__` 三层改写、
> `__retry__` 调用级高阶化、run_batch 统一消费逐项参数化。mock 层确定性 + 真实 LLM 层回归。
> 参考规范：`_toolkit/CLASSIFICATION.md` / `_toolkit/CONTRACT_FORMAT.md`。

## 覆盖矩阵（mock 层已建）

| 维度 | 覆盖特性 | 语法章节 | 用例组 | 覆盖状态 |
|------|----------|----------|--------|----------|
| M1 | 定义 + 直接调用 + 参数按位绑定 + prompt_slots + expected_type str | 08 §8.1-8.2 | M1 | ✅ PASS |
| M2 | expected_type int 标量解析 | 08 §8.5 | M2 | ✅ PASS |
| M3 | expected_type list[int] 容器解析 | 08 §8.5 | M3 | ✅ PASS |
| M4 | expected_type dict[str,int] 容器解析 | 08 §8.5 | M4 | ✅ PASS |
| M5 | 未声明 expected_type 按字符串解析（auto 边界） | 08 §8.5 | M5 | ✅ PASS |
| M6 | `__retry__` 调用级策略 + MOCK:REPAIR 重试成功 | 08 §8.4 | M6 | ✅ PASS |
| M7 | `__retry__` 策略耗尽 + MOCK:FAIL 交语句层捕获 | 08 §8.4 | M7 | ✅ PASS |
| M8 | `__intent__` 三层改写（读 global 改写 merged，经 idbg 观测） | 08 §8.4 | M8 | ✅ PASS |
| M9 | run_batch 统一消费 llm 实例逐项参数化 | 08 §8.3 | M9 | ✅ PASS |
| G1 | `__llm_call__` 返回非 dict 契约违约 fail-fast | 08 §8.1 | G1 | ✅ GUARD |
| G2 | `__intent__` 参数数非 1 fail-fast | 08 §8.4 | G2 | ✅ GUARD |
| G3 | `__retry__` 参数数非 0 fail-fast | 08 §8.4 | G3 | ✅ GUARD |
| G4 | `__intent__` 返回非 dict fail-fast | 08 §8.4 | G4 | ✅ GUARD |

## 硬约束

- 每用例 `--timeout` 必填（run_batch 默认 60s，OS 级 SIGKILL 死循环保护）。
- mock 用例 `# expect-llm: false` + `ai.set_mock_mode()`（确定性）。
- 用例头部断言必填；注释只保留功能说明 + `# doc:` 引用。

## 真实 LLM 层（LLM 回归，待运行）

- L1 真实翻译调用（直接调用 + prompt_slots 角色 + 参数）
- L2 真实 `__intent__` 改写输出服从（意图改写影响模型输出）
- L3 真实 `__retry__` hint 回喂（首轮失败 hint 指导次轮）
- L4 真实 run_batch 逐项独立调用
- L5 实例多次调用独立装配

## 分类与记录

- 分类规范：PASS / GUARD / KERNEL_ISSUE / BOUNDARY / DOC_ISSUE / LLM_BEHAVIOR / LIMIT / HARNESS。
- 缺陷登记：`trials/INDEX.md` 生命周期状态机 + REGISTER.md。
- 只记录不修复优先；不为规避缺陷改套件。
