# DESIGN — T12 覆层机制 + prompt 协议族（五大地基新特性试用地基）

> **目标**：对五大地基重构后 **覆层机制**（overlay，既有套件零覆盖，重点）与 **prompt 协议族
> 五成员**（`__to_prompt__`/`__from_prompt__`/`__outputhint_prompt__`/`__payload_prompt__`/
> `__validate_prompt__`）全面试用。mock 层确定性 + 真实 LLM 层回归。
> 参考规范：`_toolkit/CLASSIFICATION.md` / `_toolkit/CONTRACT_FORMAT.md`。

## 覆盖矩阵（mock 层已建）

| 维度 | 覆盖特性 | 语法章节 | 用例组 | 覆盖状态 |
|------|----------|----------|--------|----------|
| O-M1 | 覆层端到端：impl overlay 覆层 __to_prompt__，with overlay 块内生效/块外原生（行为插值观测） | 06_oop 覆层章节 | O-M1 | ✅ PASS |
| O-M2 | 覆层默认不生效（声明无引用 → 原生）；SEM_OVERLAY_UNUSED 为编译层诊断 | 06_oop + 15_diagnostics | O-M2 | ✅ PASS |
| O-M3 | 覆层嵌套作用域恢复顺序 | 06_oop 覆层章节 | O-M3 | ✅ PASS |
| O-G1 | with overlay 引用未声明覆层 → SEM_TYPE_MISMATCH | 06_oop 覆层章节 | O-G1 | ✅ GUARD |
| O-G2 | 覆层方法非协议消息 → 水化期 fail-fast | 06_oop 覆层章节 | O-G2 | ✅ GUARD |
| P-M1 | __to_prompt__ 自定义渲染（mock 回显观测） | 06 §6.7 | P-M1 | ✅ PASS |
| P-M2 | __from_prompt__ 解析 mock 输出为用户类实例 | 06 §6.7 | P-M2 | ✅ PASS |
| P-M4 | __outputhint_prompt__ 注入系统提示词（idbg 观测）+ __from_prompt__ 解析 | 06 §6.7 | P-M4 | ✅ PASS |
| P-G1 | __from_prompt__ 返回非 (bool,instance) 元组 → LLMParseError（诊断+uncertain） | 06 §6.7 | P-G1 | ✅ GUARD |

> 协议族 __validate_prompt__ / __payload_prompt__ 的真实/确定性用例已由 T08 覆盖
> （D2-02 validate+retry / D2-05 payload），本套件不重复，聚焦 overlay（零覆盖）与
> 协议族确定性守卫。

## 硬约束

- 每用例 `--timeout` 必填（run_batch 默认 60s，OS 级 SIGKILL 死循环保护）。
- mock 用例 `# expect-llm: false` + `ai.set_mock_mode()`（确定性）。
- 用例头部断言必填；注释只保留功能说明 + `# doc:` 引用。

## 真实 LLM 层（LLM 回归，待运行）

- L1 真实 overlay __to_prompt__ 影响行为插值（块内/块外对照）
- L2 真实协议族 __to_prompt__/__from_prompt__/__outputhint_prompt__ 全链路（复用 T08 D2-01 精神）

## 分类与记录

- 分类规范：PASS / GUARD / KERNEL_ISSUE / BOUNDARY / DOC_ISSUE / LLM_BEHAVIOR / LIMIT / HARNESS。
- 缺陷登记：`trials/INDEX.md` 生命周期状态机 + REGISTER.md。
- 只记录不修复优先；不为规避缺陷改套件。
