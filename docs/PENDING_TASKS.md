# PENDING_TASKS — 阻塞 / 待前置任务

> 本文档**只**记录有明确前置条件、暂不能开工的事项；其余非阻塞低优先级想法不在此处维护。
> 当前最紧要项见 `docs/NEXT_STEPS.md`；已完成事项见 `docs/COMPLETED.md`。
>
> **最后更新**：2026-05-09

---

## 一、待 NS-1（LLM 调用路径合并入 CPS）落地后才能继续

### PT-1.1　llmexcept 快照恢复 `merge()` vs 直接替换语义对齐 [P2]
- 现状：`llm_except_frame.py:270` 调用 `intent_context.merge(saved_intent_ctx)`；
  `INTENT_SYSTEM_DESIGN.md §4.6` 描述为 `runtime_context._intent_ctx = saved.fork()`（替换）。
- 阻塞原因：在 NS-1 把 LLM 路径合并入 CPS 后，意图栈 fork/restore 的实现位置可能整体下沉，届时一并对齐更安全。

### PT-1.2　LLMExceptFrame 重试历史追踪 [P2]
- 现状：`reset_for_retry()` 清除 `last_error`，重试历史不保留。
- 阻塞原因：先稳定 NS-1 的 LLM 帧管理路径，再决定 retry 历史的承载位置（运行时 vs 调试器侧）。

### PT-1.3　LLMExceptFrameStack 最大嵌套深度限制 [P3]
- 现状：无最大嵌套深度检查。
- 阻塞原因：与 PT-1.2 一并设计。

---

## 二、待 NS-2（intent OOP 化收口）落地后才能继续

### PT-2.1　intent_context 在更复杂场景的 OOP 操作 [VISION]
- 例：把 `IbIntentContext` 实例作为运行时参数传入 behavior 表达式注入路径。
- 阻塞原因：必须先把 intent_context 实例作为函数参数 / 函数参数类型走通。

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
