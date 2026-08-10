# PT-DEBT-17 `ai.run_batch` 同步阻塞根治（独立分支 exp/run-batch-cps）

## 背景（三层不一致，2026-08-10 彻查确认）
`ai.run_batch`（`ibci_ai/core.py:311` → `executor.run_batch`，`_behavior.py:339`）是语言级并发批量
行为执行原语，但走**同步阻塞路径**：
1. **①** 主线程 `fut.result()`（`:383`）同步阻塞等全部 LLM 完成（实测 main_thread=True，多任务并发
   拖住调度线程，违反"阻塞即挂起"）。
2. **②** 同步 `_prepare_behavior_call`（`:369` → `_evaluate_segments` `_prompt.py:153`）`vm.run` 重入
   主线程调度循环（任务内同步重入调度器，与 A2 同款、独立位置）。
3. **③** 同模块 `stream_call`/`stream_channel` 返回 Waitable（auto-yield 协作挂起）而 `run_batch`
   返回 `List`（主线程硬阻塞）——并发范式割裂（design-philosophy §三/§四）。

## 设计（对照工作模式定论 + self-grill + design-philosophy）
**方案**：`run_batch` 返回 **`CPSDrivable` Waitable**（与 `stream_call` 返回 `IbStreamHandle`、
A3 `_SlotUpdateWaitable.cps_drive` 同构），VM `vm_handle_IbCall` 兜底分支 `yield from
result.cps_drive(executor)` 帧内 CPS 驱动。

- **①③ 修复**：cps_drive → `_run_batch_cps` 内把多 LLM Future 聚合为 `LLMBatchFuture`（新聚合
  Waitable，全部完成才就绪、一次保序取回），`yield` 它由调度器 `try_result` 非阻塞轮询——
  主线程不再硬阻塞，与 stream_call 范式一致。
- **② 修复**：`_run_batch_cps` 用 `_prepare_behavior_call_cps`（段求值经 `_evaluate_segments_cps`
  yield、意图消解经 `resolve_cps`、hint 经 `_get_llmoutput_hint_cps` 均嵌入当前 VM 帧栈），
  消除 `vm.run` 同步重入。
- **vtable 契约评估**：`ai.run_batch` return_type 保持 `"list"`——auto-yield 完成后语言层仍收到
  boxed IbList，契约不破坏。
- **宿主/线程体兜底**：保留 `_run_batch_sync`（旧 body，vm.run 重入）作为 `try_result`/`result`
  的 `_drive` 同步路径（与 `_SlotUpdateWaitable._drive` 同构；run_batch 需 EC，正常仅 VM 路径，
  cps_drive 为权威）。
- **死代码清理（顺带）**：同步 `LLMExecutorImpl.resolve()`（`_scheduler.py:78`）与
  `LLMFuture.get()`（`llm_result.py:129`）零真实调用（仅 docstring 示例，VM 全走 CPS
  `resolve_future_cps`）——登记清理（涉及 IILLMExecutor 协议声明，独立小窗核查后删）。

## 落地（Phase 3）
- `core/runtime/shared/llm_result.py`：新增 `LLMBatchFuture` 聚合 Waitable；**移除死代码** `LLMFuture.get()`（生产零调用，VM 全走 `resolve_future_cps`/`try_result`）。
- `core/runtime/interpreter/llm_executor/_behavior.py`：
  - `run_batch` 改为返回 `_RunBatchDrive(self, behavior, items, ec)`。
  - 旧 body 更名 `_run_batch_sync`（宿主兜底）。
  - 新增 `_run_batch_cps`（CPS 权威路径）。
  - 新增 `_RunBatchDrive`（Waitable + CPSDrivable：is_done/try_result/result/register_wake/cps_drive）。
  - **统一聚合**：单一 `_aggregate_batch_results(ec, llm_results)` 返回 raw `List[IbObject]`（任一项不确定即抛），CPS 路径 `registry.box` 装箱（消除双路径重复/返回类型分叉）。
- `core/runtime/interpreter/llm_executor/_scheduler.py`：**移除死代码** `resolve()`（生产零调用，VM 走 `resolve_future_cps`）+ 死 import IbObject + docstring 对齐。
- `core/runtime/interfaces.py` / `core/base/interfaces.py`：`run_batch` 返回类型改 `Any`（Waitable）声明；`LLMExecutor` 协议移除死 `resolve()`。
- `tests/e2e/test_ai_batch.py`：新增 `TestRunBatchWaitableContract`（判别性：旧实现返回 List 必失败）+ 并发线程共存集成测试。
- `tests/runtime/test_llm_result_future.py`：移除锁定死方法 `get()` 的 5 个测试（保留活契约 `is_done`）。

## 验证（Phase 4）
- 全量 pytest 零回归：基线 2138/1 → **2135 passed / 1 skipped**（+2 新增 run_batch 测试，-5 移除死 `get()` 测试；剩余全绿）。
- general 复核：3 项建议级全部整改（PT 编号入生产 docstring 清除 / 死 import 删除 / 双路径聚合统一）。
- `run_batch` 返回 `Waitable`+`CPSDrivable`、懒构造即时返回（判别性断言通过）。

## 死代码清理（随 PT-DEBT-17 完成）
- `LLMExecutorImpl.resolve()`（`_scheduler.py`）：移除（零真实调用，VM 全走 `resolve_future_cps`）。
- `LLMFuture.get()`（`llm_result.py`）：移除（零真实调用，仅测试锁定）+ 删除其 5 个死测试。
- `LLMExecutor` 协议声明同步（`core/runtime/interfaces.py`）。
