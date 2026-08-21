# REGISTER — T12 覆层机制 + prompt 协议族（五大地基新特性）

> 分类/级别/编号规范：`_toolkit/CLASSIFICATION.md`。mock 层先行（确定性），LLM 层回归待运行。
> 参考规范版本：_toolkit 当前 HEAD。

## 一、总览

- **用例总数**：9 个（mock 层），全部经死循环保护（run_batch 默认 60s OS 级超时）。
- **PASS**：6 例；**GUARD**：3 例。
- **KERNEL_ISSUE**：0 项。**BOUNDARY**：0 项。**DOC_ISSUE**：0 项。
- **LIMIT**：0 项。**LLM_BEHAVIOR / HARNESS**：0 项。

## 二、缺陷登记

无新缺陷。关键契约确认：

- **O-G1**：`with overlay` 引用未声明覆层 → 编译期 `SEM_TYPE_MISMATCH`（守卫生效，实测）。
- **O-G2**：覆层方法非协议消息 → 水化期 fail-fast（守卫生效，实测）。
- **P-G1**：`__from_prompt__` 返回非 `(bool, instance)` 元组 → `LLMParseError`（诊断+uncertain），
  与 PT-DECIDE-3 ① 单向契约定案一致（实测 exit 1）。
- **O-M2 备注**：`SEM_OVERLAY_UNUSED` 为**编译层诊断**（engine.compile_string 的
  issue_tracker 告警，内核判别测试 `test_overlay_mechanism.py::test_unused_overlay_warns`
  承载）；`main.py run` 运行输出不可见——O-M2 仅断言"声明未引用 → 原生行为"，告警由内核
  测试锁定，不误判。

## 三、LIMIT / 待修候选池

无。

## 四、逐例明细

| case_id | 目标 | 期望 | 实际 | 分类 | 级别 | 证据日志 |
|---------|------|------|------|------|------|----------|
| O-M1 | 覆层端到端（块内生效/块外原生） | [MOCK] report: overlayed-int / 5 | 同 | PASS | — | logs/B-T12-O-M1.log |
| O-M2 | 覆层默认不生效 | [MOCK] report: 5 | 同 | PASS | — | logs/B-T12-O-M2.log |
| O-M3 | 覆层嵌套恢复顺序 | 3×overlayed-int + 5 | 同 | PASS | — | logs/B-T12-O-M3.log |
| O-G1 | with 未声明覆层 | SEM_TYPE_MISMATCH | 同 | GUARD | P2 | logs/B-T12-O-G1.log |
| O-G2 | 覆层非协议方法 | 水化期 fail-fast | 同 | GUARD | P2 | logs/B-T12-O-G2.log |
| P-M1 | __to_prompt__ 回显 | [MOCK] 输出: TOKEN_XYZ | 同 | PASS | — | logs/B-T12-P-M1.log |
| P-M2 | __from_prompt__ 解析 | got=开心 | 同 | PASS | — | logs/B-T12-P-M2.log |
| P-M4 | __outputhint_prompt__ 注入 + 解析 | val=你好 | 同 | PASS | — | logs/B-T12-P-M4.log |
| P-G1 | __from_prompt__ 形状违约 | LLMParseError（uncertain） | 同 | GUARD | P2 | logs/B-T12-P-G1.log |

## 五、结论

- **验证达成**：覆层机制四语义面（块内生效/块外原生/嵌套恢复/默认不生效）mock 层确定性全过；
  两个覆层守卫（未声明引用/非协议方法）fail-fast 生效；prompt 协议族 `__to_prompt__`/
  `__from_prompt__`/`__outputhint_prompt__` 确定性全过 + `__from_prompt__` 形状违约守卫
  （LLMParseError）与单向契约定案一致。**overlay 完成从零覆盖到基本覆盖**。
- **下一步**：T12 LLM 层真实回归（overlay 影响真实渲染 + 协议族全链路复用 T08 精神）；
  其余新特性套件（意图一等值/fs/Optional、恶意边界）按 `trials/INDEX.md` 排布。
