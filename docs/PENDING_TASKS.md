# PENDING_TASKS — 阻塞 / 待前置任务

> 本文档**只**记录有明确前置条件、暂不能开工的事项；其余非阻塞低优先级想法不在此处维护。
> 当前最紧要项见 `docs/NEXT_STEPS.md`；已完成事项见 `docs/COMPLETED.md`。
>
> **最后更新**：2026-05-12

---

## 一、llmexcept 相关后续（PT-1.x）— 已完成

> 历史 PT-1.1（llmexcept 快照恢复 merge vs 替换语义）已随 NS-2c 落地；PT-1.2 / PT-1.3 已于 2026-05-12 一并完成，详见 `docs/COMPLETED.md` 同日锚点。

## 二、NS-2（intent OOP 化收口）相关 — 已全部完成

> PT-2.1（intent_context 高级 OOP 场景）与 PT-2.2（IbIntentContext 序列化/反序列化）已于 2026-05-12 一并落地，详见 `docs/COMPLETED.md` 同日锚点。

---

## 三、待 VM 信号 / 中断 / 异步机制（L3 协程）成熟后才能继续

### PT-3.1　host.run_isolated() 返回值改进 [VISION]
### PT-3.2　ReceiveMode 枚举演进 [VISION]
### ~~PT-3.3　ibci_idbg.protection_map() 完整实现 [P3]~~ ✅ 已完成（2026-05-12）

---

## 四、明确排除的方向

- 不引入静态类型检查器作为解释器前置强依赖。
- 不以牺牲运行时可观测性换取短期性能优化。
- 不为优化同一程序内独立 LLM 调用而创建多 Interpreter（这是 L1 流水线的职责）。
