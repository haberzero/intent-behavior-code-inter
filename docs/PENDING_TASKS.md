# PENDING_TASKS — 阻塞 / 待前置任务

> 本文档**只**记录有明确前置条件、暂不能开工的事项；其余非阻塞低优先级想法不在此处维护。
> 当前最紧要项见 `docs/NEXT_STEPS.md`；已完成事项见 `docs/COMPLETED.md`。
>
> **最后更新**：2026-05-11

---

## 一、待 NS-1（LLM 调用路径合并入 CPS）落地后才能继续

> 历史 PT-1.1（llmexcept 快照恢复 merge vs 替换语义）已随 NS-2c 一并落地（`core/runtime/interpreter/llm_except_frame.py`），不再阻塞。

### PT-1.2　LLMExceptFrame 重试历史追踪 [P2]
- 现状：`reset_for_retry()` 清除 `last_error`，重试历史不保留。
- 阻塞原因：先稳定 NS-1 的 LLM 帧管理路径，再决定 retry 历史的承载位置（运行时 vs 调试器侧）。

### PT-1.3　LLMExceptFrameStack 最大嵌套深度限制 [P3]
- 现状：无最大嵌套深度检查。
- 阻塞原因：与 PT-1.2 一并设计。

---

## 二、NS-2（intent OOP 化收口）已完成，以下项目阻塞解除，等待排期

### PT-2.1　intent_context 高级 OOP 场景 [P2]

**前置条件**：NS-2b（已完成，2026-05-11）。可开工。

**目标场景**：
- 把 `IbIntentContext` 实例注入 behavior 表达式的动态变量替换路径（`@~ $ctx_content ~` 中的 `ctx_content` 来自 `intent_context` 对象）。
- 多 `intent_context` 实例的组合合并：`ctx_a.merge(ctx_b)` 产生新上下文，传入 behavior 前作为 `use()` 参数。
- `intent_context` 作为类字段持久化（跨调用保存意图策略），配合 `__save__`/`__restore__` 协议参与 llmexcept 快照-恢复。

### PT-2.2　IbIntentContext 快照参与序列化/反序列化 [P3]

**前置条件**：NS-2b（已完成，2026-05-11）。可开工。

**目标**：在 `core/runtime/serialization/runtime_serializer.py` 中纳入 `IbIntentContext` 的序列化支持，使意图栈状态可随程序状态一并持久化，供调试器断点场景还原完整运行时（当前意图上下文对调试器不可见）。借助 NS-2b 的 `_active_intent_ibobj` 指针，调试器现已可观察"当前帧正在使用哪个用户命名的意图策略对象"，序列化时需把活跃指针与底层 `IbIntentContext` 一并落盘。

---

## 三、待 VM 信号 / 中断 / 异步机制（L3 协程）成熟后才能继续

### PT-3.1　host.run_isolated() 返回值改进 [VISION]
### PT-3.2　ReceiveMode 枚举演进 [VISION]
### PT-3.3　ibci_idbg.protection_map() 完整实现 [P3]
- 阻塞原因：要求 `IExecutionContext` 暴露 side_table 只读接口，与 VM 协程化设计一并落地。
- 当前位置：`ibci_modules/ibci_idbg/core.py:267`。

---

## 四、明确排除的方向

- 不引入静态类型检查器作为解释器前置强依赖。
- 不以牺牲运行时可观测性换取短期性能优化。
- 不为优化同一程序内独立 LLM 调用而创建多 Interpreter（这是 L1 流水线的职责）。

