# REGISTER — T13 意图一等值 + snapshot 冻结 + intent_context OOP（五大地基新特性）

> 分类/级别/编号规范：`_toolkit/CLASSIFICATION.md`。mock 层先行（确定性），LLM 层回归待运行。
> 参考规范版本：_toolkit 当前 HEAD。

## 一、总览

- **用例总数**：5 个（mock 层），全部经死循环保护（run_batch 默认 60s OS 级超时）。
- **PASS**：4 例；**GUARD**：1 例。
- **KERNEL_ISSUE**：0 项。**BOUNDARY**：1 项（观测缺口备注）。**DOC_ISSUE**：0 项。
- **LIMIT**：0 项。**LLM_BEHAVIOR / HARNESS**：0 项。

## 二、缺陷登记

### BOUNDARY-LLM-5（P3）— 进程内 mock 下 `get_current_call_info()` 无 `sys_prompt` 键

- **现象**：`ai.set_mock_mode()`（进程内 mock）下 `get_current_call_info()` 返回键集
  不含 `sys_prompt`（`[node_uid, target_model, thinking_mode, intents, output_contract,
  user_prompt, prompt_slots, has_message_history, message_history, response, raw_response]`）；
  真实 LLM 模式（T08 D3-05/D3-08）有 `sys_prompt` 键。进程内 mock 路径的 provider_meta
  sys_prompt 未回填 call_info。
- **证据**：T13 探针 + `cases/T13-I-M1-*.ibci` 初版（`KeyError: 'sys_prompt'`）。
- **分类定性**：**非缺陷**（观测设施缺口；意图三层 `intents.active/global/merged` 始终可用，
  T13 已改用它做断言面）；属可观测性备注，供阶段 C 文档复核评估（观测 API 对 mock 的覆盖）。
- **修复状态**：不修（阶段 C 只记录；如需 mock 观测 sys_prompt，独立窗口评估）。

### 语义确认备注（非缺陷，防止未来误解）

- **`intent_context.use(ctx)` 安装 fork 拷贝**：use 后对原 `ctx` 的 push/pop 不传播到已安装
  的帧上下文（`get_current()` 返回快照、`use()` 安装 `fork(ctx)`）。文档 §9.3 工作流
  （push→use→call→pop→push→re-use→call）依赖每次 re-use 重新安装——I-M4 按此验证通过。
  对"use 后修改 ctx 期望生效"的心智模型不成立，属设计语义（fork 隔离）。

## 三、LIMIT / 待修候选池

无。

## 四、逐例明细

| case_id | 目标 | 期望 | 实际 | 分类 | 级别 | 证据日志 |
|---------|------|------|------|------|------|----------|
| I-M1 | 意图一等值 eager 值 | has_A=True has_B=False | 同 | PASS | — | logs/B-T13-I-M1.log |
| I-M2 | 意图按值移除 | has_intent=False | 同 | PASS | — | logs/B-T13-I-M2.log |
| I-M3 | snapshot 冻结 vs lambda live | snap_frozen=True lam_live=True | 同 | PASS | — | logs/B-T13-I-M3.log |
| I-M4 | intent_context OOP 工作流 | r1_has_简洁 / r2_has_详细 / r2_no_简洁 | 同 | PASS | — | logs/B-T13-I-M4.log |
| I-G1 | push 缺参 fail-fast | RUN_GENERIC_ERROR ...requires a content argument | 同 | GUARD | P2 | logs/B-T13-I-G1.log |

## 五、结论

- **验证达成**：意图一等值（eager 值压栈/按值移除）、snapshot 冻结 vs lambda live、
  intent_context OOP 文档工作流（上下文切换）、push 缺参 fail-fast 全部 mock 层确定性通过。
- **发现**：BOUNDARY-LLM-5（进程内 mock 观测无 sys_prompt 键）登记；use= fork 拷贝语义确认。
- **下一步**：T13 LLM 层真实回归（真实意图约束服从 + snapshot 隔离）；其余新特性套件
  （fs/Optional、恶意边界）按 `tasks_docs/_phaseC_trials.md` 排布。
