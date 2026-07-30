# retry_hint / last_call_info 子系统彻查报告（临时文档）

> **状态**：彻查产出（`code-review` Phase 0-3）。修复方向待用户决断后转入 `code-workflow`。
> **范围**：验证"双存储 + 两条 llmexcept 路径行为不一致"是否为真 bug，并盘点相关架构缺陷。
> **方法**：源代码直接取证（file:line 引用），不依赖二手报告。
> **关联**：`tasks_docs/_phase0_research.md`（决策分析暂存）、`tasks_docs/_mock_concurrency.md`（主线）、PT-4.7。

---

## 一、彻查结论速览

| 编号 | 问题 | 分类 | 严重性 |
|---|---|---|---|
| Bug-1 | 两条 llmexcept 路径对 `retry "hint"` 行为不一致（restore 清除 vs 不清除） | **真 bug** | 高 |
| Bug-2 | `_call_llm` 的 `set_retry_hint` 是死代码（调用前已清零 context 侧） | **死代码** | 中 |
| Bug-3 | retry_hint 回退策略在 behavior 与 llm_function 间不一致 | **真 bug** | 中 |
| 缺陷-4 | `provider._retry_hint` 持久存储语义与"一次性重试提示"冲突 | **半接通/设计限制** | 中 |
| 缺陷-5 | `last_call_info` 双存储回退链是死路径 | **死代码** | 低 |
| 缺陷-6 | retry_hint 子系统语义碎片化（三来源/两存储/两注入路径/单向回传） | **架构缺陷** | 高 |
| 违规-7 | MOCK 哨兵字符串比对（`__MOCK_REPAIR__` 等） | **工作模式定论违规** | 中（已在 Phase 0.1 清理范围） |

**核心结论**：retry_hint / last_call_info 子系统存在确凿的真 bug（Bug-1、Bug-3）与架构缺陷（缺陷-6），且这些**直接阻塞 PT-4.7 线程安全方案决断**--在状态语义未重设计清楚前，"保护什么、正确语义是什么"未定义，线程安全方案（thread-local/锁/future 去共享）无从决断。

---

## 二、retry_hint 完整数据流（取证）

### 2.1 三条来源

| 来源 | 写入点 | 存储位置 | 生命周期 |
|---|---|---|---|
| `retry "hint"` 语句 | `vm_handle_IbRetry` `core/runtime/vm/handlers/llm_behavior.py:394` `executor.runtime_context.retry_hint = hint_val` | **context 侧** `RuntimeContextImpl._retry_hint` (`runtime_context.py:309`) | 一次性（读后清零）；**参与 llmexcept 快照** |
| `ai.set_retry_hint()` 用户 API | `ibci_modules/ibci_ai/core.py:313-314` `self._retry_hint = hint` | **provider 侧** `AIPlugin._retry_hint` (`ibci_ai/core.py:16`) | 持久（不清零）；**不参与 llmexcept 快照** |
| 函数定义 `__llmretry__` | 编译期 `core/compiler/parser/components/declaration.py:261` `llm_node.retry_hint = retry_hint` | node_data（AST 元数据） | 静态；仅 llm 函数回退用 |

### 2.2 两个存储的快照行为

- `context._retry_hint`：`LLMExceptFrame.save_context`（`llm_except_frame.py:168-169`）保存为 `saved_retry_hint`；`restore_context`（`:256-257`）恢复为 `saved_retry_hint`。
- `provider._retry_hint`：**save/restore 均不覆盖**（`LLMExceptFrame` 只操作 `runtime_context.retry_hint`，不触达 provider）。

### 2.3 消费逻辑（两处不一致）

**behavior 表达式**（`core/runtime/interpreter/llm_executor/_behavior.py:104-111`，CPS 版 `:272-278` 同构）：
```python
current_retry_hint = context.retry_hint          # :105 读 context 侧
context.retry_hint = None                         # :106 清零 context 侧
if provider and not current_retry_hint and hasattr(provider, "_retry_hint"):
    current_retry_hint = provider._retry_hint     # :107-108 回退读 provider 侧（不清零）
if current_retry_hint:
    sys_prompt += f"...{current_retry_hint}"      # :110-111 注入 sys_prompt
```

**llm 函数**（`core/runtime/interpreter/llm_executor/_llm_function.py:55-75`，CPS 版 `:192-205` 同构）：
```python
current_retry_hint = context.retry_hint           # :60 读 context 侧
if current_retry_hint:
    retry_hint_segments = [current_retry_hint]
else:
    retry_hint_segments = node_data.get("retry_hint")  # :65 回退到函数定义 __llmretry__（不读 provider！）
# 注入后...
context.retry_hint = None                          # :75 清零（在注入之后、_call_llm 之前）
```

### 2.4 `_call_llm` 的死代码（`_core.py:146-191`）

```python
context = execution_context.runtime_context if execution_context else None
retry_hint = context.retry_hint if context else None   # :169 再次读 context 侧
if self.llm_callback:
    if retry_hint:
        self.llm_callback.set_retry_hint(retry_hint)   # :175 写 provider 侧
    response = self.llm_callback(sys_prompt, ...)       # :177 调 provider
```

`_call_llm` 全部 4 个调用点（`_behavior.py:119,284`、`_llm_function.py:92,219`）均经 `execute_behavior_expression`/`execute_llm_function`，二者在调用前已清零 `context.retry_hint`（`_behavior.py:106,273`、`_llm_function.py:75,205`）。故 `:169` 恒读 None，`:173-175` 几乎永不执行。

### 2.5 `LLMResult.retry_hint` 单向回传（`core/runtime/shared/llm_result.py:36`）

uncertain 结果携带 `retry_hint`（如 `"MOCK:REPAIR - 模拟..."`，`_behavior.py:134,150`）。消费点（grep 全量）：
- `assignment.py:116`、`control_flow.py:261`、`_shared.py:316`：作 `LLMParseError` 消息文本。
- `runtime_context.py:408`：存入 `IbLLMCallResult`（IBCI 用户面对象）`retry_hint` 字段，供用户代码/调试器读取。
- `ibci_idbg/core.py:108,109,246,248,272`：调试器显示。

**从不被写回 `context._retry_hint` 或 `provider._retry_hint`**。即 uncertain 结果携带的 hint 不会自动成为下次重试的注入 hint。

---

## 三、Bug-1 详解：两条 llmexcept 路径行为不一致（真 bug）

### 3.1 路径 A：`vm_handle_IbLLMExceptionalStmt`（保护 if/assign/while 等的 llmexcept）

`core/runtime/vm/handlers/llm_behavior.py:64-130` 时序：
1. `:57-61` `save_llm_except_state` -> `save_context` 保存 `saved_retry_hint = context.retry_hint`（通常 None）。
2. `:65` `first_iteration=True`。
3. `:66` `while frame.should_continue_retrying():`
4. 第 1 轮：`:69` `first_iteration=True` 跳过 restore；`:74` 清 `last_llm_result`；`:77` `yield target_uid` 执行 target LLM 调用。
   - target 调 `execute_behavior_expression`：`:105` 读 `context.retry_hint`(None)，`:106` 清零，注入（无 hint）。返回 uncertain。
5. `:84-93` 读 `last_llm_result`，uncertain -> `frame.should_retry=False`。
6. `:97-100` 执行 body。body 中 `retry "hint"`（`llm_behavior.py:394`）写 `context.retry_hint = "某hint"`。
7. body 结束。`:117` `increment_retry`。回到 `:66`。
8. 第 2 轮：`:69` `first_iteration=False` -> **`:70` `frame.restore_snapshot(runtime_context)`**。
   - `restore_context`（`llm_except_frame.py:256-257`）：`runtime_context.retry_hint = self.saved_retry_hint`（None）。
   - **`retry "hint"` 写入的 hint 被清除！**
9. `:77` 重新执行 target：`:105` 读 `context.retry_hint`(None)，**hint 未注入**。
   - 回退读 `provider._retry_hint`：第 1 轮 target 时 `_call_llm:169` 读 context 侧为 None（已清零），`:175` 未调 `set_retry_hint`，故 provider 侧也无值。
   - **hint 完全丢失。**

### 3.2 路径 B：`vm_handle_IbFor` 条件驱动 llmexcept

`core/runtime/vm/handlers/control_flow.py:212-248` 时序：
1. `:212` `while True:`；`:214` `condition = yield actual_iter_uid` 执行条件 LLM 调用。读 `context.retry_hint`(None)，返回 uncertain。
2. `:219` `if last_result and not last_result.is_certain:` + `:220` `if llmexcept_handler_uid is not None:`
3. `:226-230` `save_llm_except_state` 创建帧（保存 `saved_retry_hint`，此时 None）。
4. `:232` `frame.should_retry=False`。
5. `:234-244` 执行 handler body。body 中 `retry "hint"` 写 `context.retry_hint = "某hint"`。
   - `:243-244` `finally: pop_llm_except_frame()` -- **只 pop，不调 restore**。
6. `:247` `if frame.should_retry and frame.increment_retry(): continue`。
7. 回到 `:212` `while True` 顶部。`:213` 清 `last_llm_result`。`:214` 重新执行条件 LLM 调用。
   - `execute_behavior_expression`：`:105` 读 `context.retry_hint`("某hint"，**未被 restore**)，`:106` 清零，`:110-111` **注入 sys_prompt**。
   - **hint 生效。**

### 3.3 不一致结论

- 路径 A：`retry "hint"` 的 hint 在下一轮 target 前被 `restore_snapshot` 清除 -> **hint 丢失，不生效**。
- 路径 B：不调 restore -> **hint 存活，正确注入**。
- 同一 `retry "hint"` 语句，在 `if @~...~: ... llmexcept: retry "x"` 下失效，在 `for @~...~: ... llmexcept: retry "x"` 下生效。

### 3.4 测试盲区

`KNOWN_LIMITS §十七.6`：MOCK 无法验证提示词内容。grep `tests/` 中 `retry "..."` 出现 30+ 处（`test_llmexcept_guarantees.py`、`test_e2e_llmexcept.py`、`test_pipeline.py` 等），**全部验证控制流行为（retry 是否触发、变量隔离、计数），无一验证 hint 文本是否注入 sys_prompt**。故此 bug 被测试盲区掩盖。

---

## 四、其余问题详解

### Bug-2：`_call_llm` 的 `set_retry_hint` 死代码
- 见 §2.4。`_call_llm:169` 恒读 None（调用方已清零），`:173-175` 几乎永不执行。
- 影响：`provider._retry_hint` 的"同步 context 侧 hint 到 provider"路径失效，provider 侧几乎只由 `ai.set_retry_hint()` 写入。
- 分类倾向：死代码（但删除前需确认是否有未来 AsyncOpenAI 演进意图，按 code-review "死代码 vs 预留接口" 辨别法需查 git 历史与设计文档）。

### Bug-3：behavior 与 llm_function 回退策略不一致
- `_behavior.py:107-108` 回退读 `provider._retry_hint`；`_llm_function.py:64-65` 回退到函数定义 `__llmretry__`，**不读 `provider._retry_hint`**。
- 影响：`ai.set_retry_hint()` 对 behavior 表达式生效，对 llm 函数**不生效**。同一用户 API 在两种 LLM 调用形态下行为不一致。

### 缺陷-4：`provider._retry_hint` 持久语义冲突
- `ai.set_retry_hint()`（`ibci_ai/core.py:313-314`）写后不清零；`_behavior.py:107-108` 回退读也不清零。
- 后果：一旦设置，hint **持续注入所有后续 behavior 调用 sys_prompt**，重试成功后仍注入。与"针对上次失败的重试提示"语义冲突。

### 缺陷-5：`last_call_info` 双存储回退链死路径
- `get_last_call_info`（`_core.py:120-130`）优先 executor 侧，空才回退 provider 侧。
- executor 侧每次调用都被写入（`_behavior.py:154,123,139`、`_llm_function.py:127,96,112`），几乎总非空。
- provider 侧 `_last_call_info`（`ibci_ai/core.py:370,491`）几乎永不被读到。回退链是死代码，双存储无实际意义。

### 缺陷-6：retry_hint 子系统语义碎片化
- 三来源 + 两存储 + 两注入路径 + 一单向回传，缺乏统一来源优先级与生命周期定义（见 §2）。

### 违规-7：MOCK 哨兵字符串比对
- `_behavior.py:122,138`、`_llm_function.py:95,111` 用 `if response == "__MOCK_REPAIR__"` / `"MAYBE_YES_MAYBE_NO_this_is_ambiguous"` 字符串比对。
- 违反工作模式定论第 3 条（禁止靠凑巧相等/魔法哨兵）。
- 已在决策点 2 Phase 0.1 清理范围（报告 C 提议 6）。

---

## 五、严格分组（code-review Phase 2）

按"问题本质 + 修复方案 + 架构层级"三重标准：

### 组 1：retry_hint 语义重设计（Bug-1 + Bug-2 + Bug-3 + 缺陷-4 + 缺陷-6）
- **本质同源**：retry_hint 缺乏单一真相源、统一来源优先级、存储模型、生命周期、注入路径定义。
- **修复方案同构**：需整体重设计 retry_hint 语义（统一来源优先级、修复两条 llmexcept 路径 restore 一致性、厘清 provider._retry_hint 持久语义或废弃、清理 _call_llm 死代码）。
- **架构层级**：interpreter/llm_executor + vm/handlers + runtime_context + ibci_ai。
- **与 PT-4.7 强相关**：retry_hint 是线程安全方案核心对象，语义未清则线程安全无从决断。

### 组 2：last_call_info 双存储清理（缺陷-5）
- **本质**：executor 侧与 provider 侧双存储，回退链死路径。
- **修复方案**：合并为单一存储（保留 executor 侧富信息或 provider 侧精简信息之一）。
- **架构层级**：interpreter/llm_executor + ibci_ai。
- **与 PT-4.7 强相关**：last_call_info 是线程安全方案另一核心对象。

### 组 3：MOCK 哨兵常量化（违规-7）
- 已在 Phase 0.1 范围（报告 C 提议 6），独立分组（字符串常量化，与 retry_hint 语义无关）。

---

## 六、与主线（MOCK 服务化 + dispatch 修复）的关系

- **组 1 + 组 2 直接阻塞 PT-4.7 线程安全方案决断**：retry_hint 与 last_call_info 正是线程安全方案的两大核心对象。在它们的语义未重设计清楚前，"保护什么状态、状态的正确语义是什么"未定义，thread-local / 锁 / future 去共享三方案无从决断。
- **组 3 已在 Phase 0.1 范围**，与主线同步。
- **影响 Phase 0 范围**：建议将组 1 + 组 2 的语义重设计纳入 Phase 0 设计冻结，作为 PT-4.7 线程安全方案的前置依赖。这扩大 Phase 0 范围，但符合工作模式定论"质量优先、技术债先清、潜伏 bug 不允许过渡修复"--retry_hint 语义不清就做线程安全是沙滩建塔。

---

## 七、修复方向建议（非决策，供讨论）

> 仅列方向，不定方案。最终由用户决断后转 `code-workflow` 实现。

### 方向 A：retry_hint 统一到 context 侧一次性令牌
- 废弃 `provider._retry_hint` 持久存储（或重新定义为仅调试用）。
- `retry "hint"` 与 `ai.set_retry_hint()` 统一写 context 侧一次性令牌。
- 修复两条 llmexcept 路径 restore 一致性：要么都 restore（则需把 retry "hint" 写入不受快照管理的位置），要么都不 restore。
- `LLMResult.retry_hint` 回传接入：uncertain 结果的 retry_hint 在 llmexcept body 执行前写回 context 侧（作为默认 hint，可被 `retry "hint"` 覆盖）。

### 方向 B：retry_hint 经 future/LLMResult 显式传递（与方案 3 去共享对齐）
- retry_hint 不再存共享状态，而是作为 LLMResult/future 的属性显式传递。
- 主线程在 dispatch 时刻/resolve 时刻处理 hint，worker 不触达。
- 与决策点 1 方案 3（经 future 去共享）天然对齐。

### last_call_info 方向
- 合并双存储为单一真相源（建议保留 executor 侧富信息，废弃 provider 侧精简信息写入，或反之）。
- 重新定义并发下 `ai.get_last_call_info()` 的用户可见语义（见 `_phase0_research.md` §1.7 矛盾 3）。

### 前置确认事项（需用户输入或进一步调研）
1. `retry "hint"` 的预期语义：是否应注入下次 target 的 sys_prompt？（若是，Bug-1 确认为真 bug，需修复路径 A。）
2. `ai.set_retry_hint()` 的预期语义：一次性还是持久？对 llm 函数是否应生效？（决定 Bug-3、缺陷-4 修复方向。）
3. `LLMResult.retry_hint` 是否应自动注入下次重试？（决定是否新增回写链路。）
4. `_call_llm` 的 `set_retry_hint` 是否有未来 AsyncOpenAI 演进意图？（决定删除还是保留改造。）
