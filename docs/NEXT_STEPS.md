# NEXT_STEPS — 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `docs/PENDING_TASKS.md`；历史归档见 `docs/COMPLETED.md`。
>
> **最后更新**：2026-05-11

---

## 主线

类型系统 M1–M5、VM CPS 主线与 intent 系统 OOP 化（NS-2 全部 4 步）已全部完成，当前**无开放的 P0 主线任务**。

交叉核验结论：真正的下一步仍是 **NS-1**（先把 `IbBehavior.call()` / `IbLLMFunction.call()` / `IbExprStmt` 的同步旁路并入 CPS），**NS-3** 继续作为与 NS-1 强耦合的后续收口项。

下一阶段优先项（按优先级排序，任选其一开工）：

### NS-1 [P1]　LLM 调用路径合并入 CPS 调度循环
- 范围：`IbBehavior.call()` / `IbLLMFunction.call()` / `vm_handle_IbExprStmt` 中的 behavior 同步分支。
- 目标：所有 LLM 调用通过 VMExecutor yield 协议进入主循环，使 LLM 帧受 VM 调度管理（快照、并发、调试可观察性）。
- 代码依据：
  - `core/runtime/objects/builtins.py:971`（`IbBehavior.call`）
  - `core/runtime/objects/kernel.py:985`（`IbLLMFunction.call`）
  - `core/runtime/vm/handlers.py:372-374`（`IbExprStmt` 同步分支）

### NS-3 [P1]　lambda/snapshot 跨帧 `_execution_context` 边界
- 范围：通过 `.call()` 方法走非 CPS 路径调用闭包时，`_execution_context.runtime_context` 是定义时刻而非调用时刻。
- 目标：与"调用时刻意图栈"语义对齐；通常通过 NS-1 的合并方案一并消除。
- 代码依据：`core/runtime/objects/builtins.py:724-751,928-934`

> 建议沿 NS-1 → NS-3 顺序推进。NS-2 完整收口后，`PT-2.1` / `PT-2.2` 的阻塞前置条件已解除，可作为 P2 排队。

---

## 工作规则

- 同一时刻只主推一项 NS-x；其余项保留待选。
- 每项完成后，把摘要追加到 `docs/COMPLETED.md`（极简时间线），并把对应条目从本文件移除。
- 出现新的紧要项时，按"先评估优先级、再决定是否替换 NS-x"原则操作。

> **最后更新**：2026-05-11
