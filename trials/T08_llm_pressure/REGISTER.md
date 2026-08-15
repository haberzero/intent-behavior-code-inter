# T08_llm_pressure REGISTER — 第一轮压力试用记录

> 2026-08-15。基线 unsafe-vibe-dev ad764191；全量 pytest 修复后实跑零回归。
> 41 例：**32 PASS + 2 GUARD + 4 LLM_BEHAVIOR + 2 BOUNDARY + 1 LIMIT**。

## 一、结果总览

| 分类 | 数量 | 说明 |
|------|------|------|
| PASS | 32 | 内联/容器/协议/批量/流式/路由/线程/生成器/配置等 |
| GUARD | 2 | D5-04 未注册命名模型；D6-02 缺失配置 fail-fast |
| LLM_BEHAVIOR | 4 | run_batch 持久/排他意图的模型服从性（注入正确性已由观测用例 PASS） |
| BOUNDARY | 2 | LLM 函数 `-> void`；stream_call 后 `get_current_call_info` 为空 |
| LIMIT | 1 | 未读取的 LLM 赋值在 provider 失败时静默通过（KNOWN_LIMITS §十五） |
| KERNEL_ISSUE | 2（已修复） | LLM 函数容器返回解析；`set_retry(0)` 重试耗尽 |

## 二、缺陷登记

### KERNEL_ISSUE-LLM-2（P1，已修复）— LLM 函数返回 `list[int]` / `dict[str,int]` 未按容器解析

- **现象**：`llm f() -> list[int]` 真实调用后赋值给 `list[int]` 报 `RUN_TYPE_MISMATCH: Cannot assign 'str' to 'list[int]'`。
- **证据**：`cases/D4-01-llmfunc-typed.ibci` + `logs/B-D4-01-llmfunc-typed.log`
- **根因**：`_get_expected_type_hint` 只处理 returns `IbName`，对 `IbSubscript`（`list[int]`/`dict[str,int]`）返回 `None` → LLM 函数默认按 `str` 解析；用户类 `IbName` 路径正常。
- **修复**：`core/runtime/interpreter/llm_executor/_prompt.py` 在 returns 节点优先读取 `node_to_type`（覆盖 `IbSubscript`）；`Optional[...]` 保持旧路径（避免破坏 Optional 包装链路）。
- **回归**：`tests/e2e/test_llm_basic.py::TestE2ELLMFunctionContainerReturn`（list + dict 两个用例）。
- **状态**：已修复，T08 触发用例转 PASS。

### KERNEL_ISSUE-LLM-3（P1，已修复）— `ai.set_retry(0)` + `llmexcept` 不抛 `LLMRetryExhaustedError`

- **现象**：`set_retry(0)` 后 `MOCK:FAIL` 在 llmexcept 保护下不抛重试耗尽，而是把不确定容器赋给 `int` 报 `RUN_TYPE_MISMATCH`。
- **证据**：`cases/D6-04-retry-edge.ibci` + `logs/B-D6-04-retry-edge.log`
- **根因**：`_retry_llm_uncertain` 的重试循环只在 `while frame.should_continue_retrying()` 内检查耗尽；`max_retry=0` 时循环一次都不进，直接返回 uncertain。
- **修复**：`core/runtime/vm/handlers/_shared.py` 在 `max_retry <= 0` 时立即构造并抛出 `LLMRetryExhaustedError`。
- **回归**：`tests/e2e/test_llmexcept.py::TestE2ELLMExceptZeroRetry`。
- **状态**：已修复，T08 触发用例转 PASS。

### DOC_ISSUE-30（P2）— `@!` + `ai.run_batch` 文档与实现不一致

- **现象**：`docs/syntax/09_intent_system.md` 称 `@!` 在 run_batch 中只作用于首个 LLM 调用；当前实现（commit 28540336 起）为每条 run_batch 调用独立 fork 意图快照，`@!`/`@` 会注入批内每个调用。
- **证据**：`cases/D3-08-runbatch-oneshot-obs.ibci` 证明 `sys_prompt` 含 `FIRST_ONLY`（last call 也有）。
- **处置**：**已同步（2026-08-15）**：`docs/syntax/09_intent_system.md` 已改为“当前实现为批内每个调用独立 fork 意图快照，因此语句级 `@!` / `@` one-shot 意图会注入批内每一个 LLM 调用”。

### BOUNDARY-LLM-2（P3）— LLM 函数 `-> void` 编译通过但运行期 `LLMParseError`

- **现象**：`llm 报告() -> void` 可编译，调用作为表达式语句时运行期 `LLMParseError`。
- **证据**：`cases/D4-04-llmfunc-void.ibci`
- **处置**：文档未声明支持 `void`；建议要么支持（丢弃输出）要么编译期报清晰错误。记录待评估。

### BOUNDARY-LLM-3（P3）— `stream_call` / `stream_channel` 不写入 `ai.get_current_call_info()`

- **现象**：`await ai.stream_call(...)` 后 `ai.get_current_call_info()` 仍为空 dict。
- **证据**：`cases/D5-08-stream-call-info.ibci`
- **处置**：若 `get_current_call_info` 承诺覆盖所有 LLM 调用，需为流式路径补记录；否则文档明确排除。记录待评估。

### LIMIT 复现 — 未读取的 LLM 赋值在 provider 失败时静默通过

- **现象**：`str s = @~ ... ~` 后不使用 `s`，即使 provider 不可达程序也正常结束。
- **证据**：`cases/D6-06-unread-provider-failure.ibci`
- **对应**：`docs/KNOWN_LIMITS.md §十五` 已记录“未读取的 dispatched 变量残留”。

## 三、LLM_BEHAVIOR 明细

| 用例 | 观察 |
|------|------|
| D3-03 / D3-06 | `@+ 只输出 BANANA` 注入成功，但模型对第 3 项输出 ORANGE（服从性非内核） |
| D3-04 / D3-07 | `@! 只输出 FIRST_ONLY` 注入成功（D3-08 观测 sys_prompt），但模型未服从输出 FIRST_ONLY |

## 四、逐例明细

见 `logs/register.jsonl`（机械字段由 harness 写入）与各 `logs/B-*.log`。

## 五、结论

第一轮压力试用覆盖了直接/间接 LLM 主要能力，真实调用整体稳定；发现并修复 2 个内核缺陷，
另记录 1 个文档不一致、2 个边界和 1 个已知限制复现。后续可继续扩展长提示、超时、并发压测、
多模态真实文件等压力维度。
