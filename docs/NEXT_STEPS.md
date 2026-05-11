# NEXT_STEPS — 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `docs/PENDING_TASKS.md`；历史归档见 `docs/COMPLETED.md`。
>
> **最后更新**：2026-05-11

---

## 主线

类型系统 M1–M5 与 VM CPS 主线全部完成，当前**无开放的 P0 主线任务**。

下一阶段优先项（按优先级排序，任选其一开工）：

### NS-1 [P1]　LLM 调用路径合并入 CPS 调度循环
- 范围：`IbBehavior.call()` / `IbLLMFunction.call()` / `vm_handle_IbExprStmt` 中的 behavior 同步分支。
- 目标：所有 LLM 调用通过 VMExecutor yield 协议进入主循环，使 LLM 帧受 VM 调度管理（快照、并发、调试可观察性）。
- 代码依据：
  - `core/runtime/objects/builtins.py:971`（`IbBehavior.call`）
  - `core/runtime/objects/kernel.py:985`（`IbLLMFunction.call`）
  - `core/runtime/vm/handlers.py:372-374`（`IbExprStmt` 同步分支）

### NS-2 [P1]　intent 系统 OOP 化收口（当前进度：1/4，NS-2a 已完成）

**当前状态**：intent_context OOP MVP 已落地——用户可创建实例、调用 push/pop/fork/use/get_current/merge/clear_inherited（`core/runtime/bootstrap/builtin_initializer.py:410-568`）；`IbIntentContext` 持有持久栈、smear 队列、override 槽、global intents（`core/runtime/objects/intent_context.py`）。

**根本问题（双轨断裂）**：帧持有一个**匿名** `IbIntentContext` Python 对象（`runtime_context._intent_ctx`），用户创建的 `intent_context` IBCI 实例持有**另一个** `IbIntentContext`（`obj.fields['_ctx']`）。`use(ctx)` 仅做 fork-and-replace，fork 之后两者独立演化：OOP `ctx.push()` 不影响帧，语法 `@+/@-` 不影响用户对象。`get_current()` 返回的是快照（fork），不是帧的实时状态。

**收口路线图（剩余三步）**：

- **NS-2a（已完成，2026-05-11）** `intent_context` 参数类型化语义完整化
  - 落地：`IbUserFunction.call()` / `IbLLMFunction.call()` 参数绑定后自动激活 `intent_context` 实参；
    `intent_context.use(ctx)` 与函数自动绑定统一复用 `RuntimeContextImpl.use_intent_context(...)`。
  - 覆盖：新增 e2e 用例验证自动绑定生效与 fork 语义不泄漏。
  - 代码：`core/runtime/objects/kernel.py`，`core/runtime/interpreter/runtime_context.py`，`core/runtime/bootstrap/builtin_initializer.py`，`tests/e2e/test_e2e_ai_mock.py`

- **NS-2b** 帧级活跃 intent 实例化（建议在 NS-1 CPS 帧稳定后开工）
  - 问题：帧的意图状态是一个无身份的 Python 对象，`get_current()` 只能返回快照而无法追踪活跃状态；调试器无法直接观察"当前帧正在使用哪个意图策略对象"。
  - 目标：`RuntimeContextImpl` 额外持有 `_active_intent_ibobj: Optional[IbObject]`（指向当前帧"正在使用"的 `intent_context` IBCI 对象）；`use()` / `clear_inherited()` / NS-2a 的自动绑定均同步更新此指针；`get_current()` 改为返回该指针的 fork 而非裸 `_intent_ctx.fork()`，使调试器可观察到用户命名的对象身份。
  - 代码：`runtime_context.py`（新增字段）+ `builtin_initializer.py`（`_ic_use` / `_ic_get_current` 调整）

- **NS-2c** llmexcept 快照恢复语义对齐（依赖 NS-1，对应 PT-1.1）
  - 问题：`LLMExceptFrame.restore_context()` 调用 `intent_context.merge(saved_intent_ctx)`（`llm_except_frame.py:270`），但 `INTENT_SYSTEM_DESIGN.md §4.6` 规范描述为直接替换（`_intent_ctx = saved.fork()`）；merge 语义会将 llmexcept body 对意图栈的操作"叠加"进恢复结果，而非干净替换。
  - 目标：改为 `runtime_context._intent_ctx = saved_intent_ctx.fork()`，确保恢复后帧的意图状态与 llmexcept 触发前完全一致。
  - 代码：`core/runtime/interpreter/llm_except_frame.py:269-270`

- **NS-2d** IT 规则完整测试覆盖（收口验收）
  - 目标：针对 NS-2a–NS-2c 完成后的 intent OOP 全路径，新增端到端测试覆盖：
    - `func foo(intent_context ctx)` 参数自动绑定，`@+` 在函数内生效且不泄漏
    - `get_current()` 返回值在 NS-2b 后跟踪活跃对象状态
    - llmexcept 恢复后意图栈为 NS-2c 后的 fork 语义
    - snapshot × `intent_context` OOP 实例的意图冻结完整性（IT-2 规则）

**代码依据**：
  - 语法路径：`core/runtime/vm/handlers.py:1128-1172`
  - OOP 路径：`core/runtime/objects/intent_context.py`，`core/runtime/bootstrap/builtin_initializer.py:410-568`
  - 参数绑定入口：`core/runtime/objects/kernel.py:916-927`（`IbUserFunction.call`）
  - 帧意图状态：`core/runtime/interpreter/runtime_context.py:334,868-870,954`

### NS-3 [P1]　lambda/snapshot 跨帧 `_execution_context` 边界
- 范围：通过 `.call()` 方法走非 CPS 路径调用闭包时，`_execution_context.runtime_context` 是定义时刻而非调用时刻。
- 目标：与"调用时刻意图栈"语义对齐；通常通过 NS-1 的合并方案一并消除。
- 代码依据：`core/runtime/objects/builtins.py:724-751,928-934`

> NS-2 剩余项（NS-2b–NS-2d）均与 LLM/CPS 边界相关，建议沿 NS-1 → NS-3 → NS-2b → NS-2c → NS-2d 顺序推进。

---

## 工作规则

- 同一时刻只主推一项 NS-x；其余项保留待选。
- 每项完成后，把摘要追加到 `docs/COMPLETED.md`（极简时间线），并把对应条目从本文件移除。
- 出现新的紧要项时，按"先评估优先级、再决定是否替换 NS-x"原则操作。

> **最后更新**：2026-05-11
