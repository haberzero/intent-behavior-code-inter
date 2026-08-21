# REGISTER — T11 stream 流式 + run_batch 批量（五大地基新特性）

> 分类/级别/编号规范：`_toolkit/CLASSIFICATION.md`。mock 层先行（确定性），LLM 层回归待运行。
> 参考规范版本：_toolkit 当前 HEAD。

## 一、总览

- **用例总数**：5 个（mock 层），全部经死循环保护（run_batch 默认 60s OS 级超时）。
- **PASS**：5 例；**GUARD**：0 例。
- **KERNEL_ISSUE**：0 项。**BOUNDARY**：0 项（含 1 项已修工具缺口，见 §二）。**DOC_ISSUE**：1 项（指针修正）。
- **LIMIT**：0 项。**LLM_BEHAVIOR / HARNESS**：0 项。

## 二、缺陷登记

### 已修复：进程内 mock 流式分块保真缺口（HARNESS 处置 = 修工具）

- **现象**：`ai.set_mock_mode()`（进程内 mock）下 `ai.stream_channel` 逐块 `recv` 报
  `communication object is closed`——`provider_impl.py::RecommendedProvider.stream()` 的
  test_mode 分支返回 `iter([result.content])`，**丢弃 `MOCK:STREAM` 解析出的 `chunks`**，
  通道只收到 1 块整文本后关闭（第 2 次 recv 即空+关闭报错）。HTTP mock 路径
  （`mock_service.py`）已正确处理 chunks，两路径不一致。
- **证据**：`T11-M3-stream-channel-recv.ibci` 修复前日志（`communication object is closed`）。
- **根因**：`ibci_modules/ibci_ai/provider_impl.py` stream() test_mode 分支未用 `result.chunks`。
- **修复**：`return iter(result.chunks if result.chunks else [result.content])`（与 HTTP mock
  路径同构；无分块时保持整块迭代，stream_call 语义不变）。回归测试
  `tests/runtime/test_streaming.py::test_stream_channel_incremental_recv_inprocess_mock`（+1）。
- **状态**：已修复（本 session）；全量 pytest 零回归（以实跑为准）。

### 迁移记录（非缺陷）

- T08/T01 4 个旧字符串形态 stream 用例（`stream_call(sys, user)` / `stream_channel(sys, user)`，
  已随旧 llm 函数机制删除）迁移到新 llm 可调用实例形态：`D5-01-stream-call.ibci` /
  `D5-02-stream-channel.ibci` / `D5-08-stream-call-info.ibci` / `D2-35-stream.ibci`。
- `docs/syntax/11_modules.md:112` 陈旧指针 `09_llm.md → 08_llm_callable.md` 已修正。

## 三、LIMIT / 待修候选池

无。

## 四、逐例明细

| case_id | 目标 | 期望 | 实际 | 分类 | 级别 | 证据日志 |
|---------|------|------|------|------|------|----------|
| M1 | stream_call await 完整文本 | full=Hello World! | 同 | PASS | — | logs/B-T11-M1.log |
| M2 | stream_call 赋值自动等待 | got=Hello World! | 同 | PASS | — | logs/B-T11-M2.log |
| M3 | stream_channel 逐块 recv | a=Hello b= World c=! | 同 | PASS | — | logs/B-T11-M3.log |
| M4 | run_batch 行为逐项绑参 | r0=1 r1=2 | 同 | PASS | — | logs/B-T11-M4.log |
| M5 | run_batch llm 实例逐项参数化 | total=12 | 同 | PASS | — | logs/B-T11-M5.log |

## 五、结论

- **验证达成**：stream 流式消费面（stream_call await / 赋值自动等待 / stream_channel 逐块
  recv）与 run_batch 批量消费（行为逐项绑参 / llm 实例逐项参数化）在 mock 层确定性全过。
- **发现并修复**：进程内 mock 流式分块保真缺口（provider test_mode 分支丢 chunks）——
  已修复 + 回归测试 +1，两 mock 路径（进程内 / HTTP）对齐。
- **迁移**：4 个旧字符串形态 stream 用例迁移到新实例形态（D5-* / D2-35）。
- **下一步**：T11 LLM 层真实回归（含流式错误/llmexcept 恶意边界）；其余新特性套件
  （覆层/协议族、意图一等值、fs、Optional、恶意边界）按 `tasks_docs/_phaseC_trials.md` 排布。
