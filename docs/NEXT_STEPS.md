# NEXT_STEPS — 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `docs/PENDING_TASKS.md`；历史归档见 `docs/COMPLETED.md`。
>
> **最后更新**：2026-05-12

---

## 主线

类型系统 M1–M5、VM CPS 主线、intent 系统 OOP 化（NS-2 全部 4 步）、LLM 调用路径合并入 CPS 调度循环（NS-1）、lambda/snapshot/behavior 跨帧 EC 边界（NS-3）、intent_context 高级 OOP 场景（PT-2.1）、IbIntentContext 序列化/反序列化（PT-2.2）以及 `_evaluate_segments` CPS 化均已完成，当前**无开放的 P0/P1/P2 主线任务**。

下一阶段优先项（按优先级排序，任选其一开工）：

- **PT-1.2 [P2]** `LLMExceptFrame` 重试历史追踪（`reset_for_retry()` 会清空 `last_error`，不保留历史；详见 `docs/PENDING_TASKS.md`）。
- **PT-1.3 [P3]** `LLMExceptFrameStack` 最大嵌套深度限制（与 PT-1.2 一并设计）。

---

## 工作规则

- 同一时刻只主推一项 NS-x；其余项保留待选。
- 每项完成后，把摘要追加到 `docs/COMPLETED.md`（极简时间线），并把对应条目从本文件移除。
- 出现新的紧要项时，按"先评估优先级、再决定是否替换 NS-x"原则操作。

> **最后更新**：2026-05-12
