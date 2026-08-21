# REGISTER — T10 llm 可调用类（五大地基新特性）

> 分类/级别/编号规范：`_toolkit/CLASSIFICATION.md`。mock 层先行（确定性），LLM 层回归待运行。
> 参考规范版本：_toolkit 当前 HEAD。

## 一、总览

- **用例总数**：13 个（mock 层），全部经死循环保护（run_batch 默认 60s OS 级超时）。
- **PASS**：9 例；**GUARD**：4 例。
- **KERNEL_ISSUE**：0 项。**BOUNDARY**：1 项。**DOC_ISSUE**：0 项。
- **LIMIT**：0 项。**LLM_BEHAVIOR / HARNESS**：0 项。

## 二、缺陷登记

### BOUNDARY-LLM-4（P3）— llm_callable 契约违约错误以原始 Python traceback 直漏、无诊断码

- **现象**：`__llm_call__`/`__intent__`/`__retry__` 契约违约（返回非 dict / 签名不符）时，
  用户侧呈现完整 Python 内部 traceback + `RuntimeError: VM: Call failed: ...`，
  **未发射 SEM_/RUN_/KDIAG 诊断码**（G1-G4 用例只能以整行错误文本断言，无法 expect-code）。
- **证据**：`cases/T10-G1-llmcall-non-dict.ibci` 等 + `logs/B-T10-G1-*.log`
- **根因分析起点**：`core/runtime/interpreter/llm_executor/_llm_callable.py` 契约校验
  `raise TypeError/RuntimeError`（L187/283/329/404）→ VM 以 `RuntimeError: VM: Call failed`
  包裹直漏。fail-fast 语义正确（契约未静默忽略），但错误呈现为 Python 层、无语言级诊断码。
- **分类定性**：**非缺陷**（fail-fast 契约按设计生效，判别测试断言消息文本）；属**可观测性/
  错误呈现 UX** 观察，登记供阶段 C 文档复核/诊断体系评估（用户友好化方向 PT-FEAT-5 语义
  错误用户友好化相关）。
- **修复状态**：不修（阶段 C 只记录；如需改诊断呈现，独立窗口评估）。

## 三、LIMIT / 待修候选池

无（本套件未命中已记录限制；若 BOUNDARY-LLM-4 经评估转为缺陷则在此登记）。

## 四、逐例明细

| case_id | 目标 | 期望 | 实际 | 分类 | 级别 | 证据日志 |
|---------|------|------|------|------|------|----------|
| M1 | 定义+直接调用+参数绑定+slots+str | echo=hello-world | 同 | PASS | — | logs/B-T10-M1.log |
| M2 | expected_type int | val=42 | 同 | PASS | — | logs/B-T10-M2.log |
| M3 | expected_type list[int] | len=3 sum=6 | 同 | PASS | — | logs/B-T10-M3.log |
| M4 | expected_type dict[str,int] | a=1 b=2 | 同 | PASS | — | logs/B-T10-M4.log |
| M5 | 无 expected_type 按 str | auto=hi | 同 | PASS | — | logs/B-T10-M5.log |
| M6 | __retry__+REPAIR 重试成功 | val=1 | 同 | PASS | — | logs/B-T10-M6.log |
| M7 | __retry__ 耗尽交语句层 | caught=True | 同 | PASS | — | logs/B-T10-M7.log |
| M8 | __intent__ 改写 merged（idbg 观测） | - 改写自:全局意图 | 同 | PASS | — | logs/B-T10-M8.log |
| M9 | run_batch 逐项参数化 | r0=1 r1=2 r2=3 | 同 | PASS | — | logs/B-T10-M9.log |
| G1 | __llm_call__ 非 dict fail-fast | RUN_LLM_CALLABLE | 同 | GUARD | P2 | logs/B-T10-G1.log |
| G2 | __intent__ 参数数非 1 fail-fast | RUN_LLM_CALLABLE | 同 | GUARD | P2 | logs/B-T10-G2.log |
| G3 | __retry__ 参数数非 0 fail-fast | RUN_LLM_CALLABLE | 同 | GUARD | P2 | logs/B-T10-G3.log |
| G4 | __intent__ 非 dict fail-fast | RUN_LLM_CALLABLE | 同 | GUARD | P2 | logs/B-T10-G4.log |

## 五、结论

- **验证达成**：llm 可调用类五大契约面（装配/解析/意图改写/重试高阶/批量消费）在 mock 层
  全部确定性通过；四个契约违约守卫全部 fail-fast 生效。
- **发现**：BOUNDARY-LLM-4（契约违约错误原始 traceback 呈现、无诊断码）——**已处置
  （2026-08-21）**：引入 RUN_LLM_CALLABLE 语言级诊断码（G1-G4 改 expect-code，呈现为
  `Runtime Error: [ERROR][RUN_LLM_CALLABLE]: ...`）。
- **下一步**：T10 LLM 层真实回归（真实翻译/意图改写服从/retry hint 回喂/run_batch）；
  其余新特性套件（stream/batch、覆层、协议族、意图一等值、fs、Optional）按
  `trials/INDEX.md` 排布推进。
