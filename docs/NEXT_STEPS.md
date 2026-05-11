# NEXT_STEPS — 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `docs/PENDING_TASKS.md`；历史归档见 `docs/COMPLETED.md`。
>
> **最后更新**：2026-05-11

---

## 主线

类型系统 M1–M5、VM CPS 主线、intent 系统 OOP 化（NS-2 全部 4 步），以及 LLM 调用路径合并入 CPS 调度循环（NS-1）均已完成，当前**无开放的 P0/P1 主线任务**。

下一阶段优先项（按优先级排序，任选其一开工）：

### NS-3 [P2]　lambda/snapshot 跨帧 `_execution_context` 边界
- 范围：`IbBehavior` 字段中仍持有定义期 `_execution_context` 引用，跨线程或多 Interpreter 场景下与"调用时刻执行器"不一致。
- 现状：NS-1 完成后，VM 主路径（CPS）下的 LLM 调用帧已对齐"调用时刻"语义；本项仅剩跨线程历史绑定的边界场景。
- 代码依据：`core/runtime/objects/builtins.py:724-751,928-934`。
- 建议：本项可与 PT-2.1 / PT-2.2 一起在 P2 排队中评估。

---

## 工作规则

- 同一时刻只主推一项 NS-x；其余项保留待选。
- 每项完成后，把摘要追加到 `docs/COMPLETED.md`（极简时间线），并把对应条目从本文件移除。
- 出现新的紧要项时，按"先评估优先级、再决定是否替换 NS-x"原则操作。

> **最后更新**：2026-05-11
