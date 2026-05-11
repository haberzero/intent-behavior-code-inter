# PENDING_TASKS — 阻塞 / 待前置任务

> 本文档**只**记录有明确前置条件、暂不能开工的事项；其余非阻塞低优先级想法不在此处维护。
> 当前最紧要项见 `docs/NEXT_STEPS.md`；已完成事项见 `docs/COMPLETED.md`。
>
> **最后更新**：2026-05-11

---

## 一、待 NS-1（LLM 调用路径合并入 CPS）落地后才能继续

### PT-1.1　llmexcept 快照恢复 `merge()` vs 直接替换语义对齐 [P2]
- 现状：`llm_except_frame.py:270` 调用 `intent_context.merge(saved_intent_ctx)`；
  `INTENT_SYSTEM_DESIGN.md §四（4.6 LLMExceptFrame 中的意图快照）` 描述为 `runtime_context._intent_ctx = saved.fork()`（替换）。
- 阻塞原因：在 NS-1 把 LLM 路径合并入 CPS 后，意图栈 fork/restore 的实现位置可能整体下沉，届时一并对齐更安全。
- 关联：NS-2c 的具体改动即为本项的代码落地；NS-1 稳定后可直接开工。

### PT-1.2　LLMExceptFrame 重试历史追踪 [P2]
- 现状：`reset_for_retry()` 清除 `last_error`，重试历史不保留。
- 阻塞原因：先稳定 NS-1 的 LLM 帧管理路径，再决定 retry 历史的承载位置（运行时 vs 调试器侧）。

### PT-1.3　LLMExceptFrameStack 最大嵌套深度限制 [P3]
- 现状：无最大嵌套深度检查。
- 阻塞原因：与 PT-1.2 一并设计。

---

## 二、待 NS-2（intent OOP 化收口）落地后才能继续

### PT-2.1　intent_context 高级 OOP 场景 [VISION → P2]

**依赖**：NS-2b（帧级活跃 intent 实例化）落地后开工。

**目标场景**：
- 把 `IbIntentContext` 实例注入 behavior 表达式的动态变量替换路径（`@~ $ctx_content ~` 中的 `ctx_content` 来自 `intent_context` 对象）。
- 多 `intent_context` 实例的组合合并：`ctx_a.merge(ctx_b)` 产生新上下文，传入 behavior 前作为 `use()` 参数。
- `intent_context` 作为类字段持久化（跨调用保存意图策略），配合 `__save__`/`__restore__` 协议参与 llmexcept 快照-恢复。

**为何阻塞**：必须先确保 NS-2b 的帧级活跃对象指针存在，才能在 behavior 注入路径里稳定解引用到"当前活跃 intent_context"。

### PT-2.2　IbIntentContext 快照参与序列化/反序列化 [P3]

**依赖**：NS-2b 完成后。

**目标**：在 `core/runtime/serialization/runtime_serializer.py` 中纳入 `IbIntentContext` 的序列化支持，使意图栈状态可随程序状态一并持久化，供调试器断点场景还原完整运行时（当前意图上下文对调试器不可见）。

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
