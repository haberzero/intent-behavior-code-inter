# IBC-Inter 下一步（当前最高优先级）

> 仅保留**当前可直接开工**且需要优先推进的事项。
> 已完成事项请见 `docs/COMPLETED.md`；历史细节见 `docs/HISTORY_LOG.md`。
>
> 最后更新：2026-05-08

---

## P0：Intent / Behavior / VM 收敛主线

### 1) 意图注释体系与 `intent_context` 体系收敛
- 明确 `@ / @! / @+ / @-` 与 `intent_context` 对象 API 的最终分工。
- 评估并推进“语法糖 -> 对象 API”可收敛路径，减少双轨语义维护成本。
- 清理 `IntentStack` 遗留接口的定位与生命周期（保留/下线/仅兼容层）。

### 2) callable-instance 语义统一与术语收敛
- 继续收敛“延迟求值（deferred）”历史术语，统一到 callable-instance 语义。
- 对齐 `lambda` / `snapshot`：
  - `lambda`：调用时读取当前生效上下文（含意图栈）
  - `snapshot`：创建时冻结上下文快照（含意图栈）
- 审查核心代码中的历史命名与注释，避免旧路线词汇误导。

### 3) `fn` 关键字在高阶函数场景的类型表达增强
- 评估并增强 `fn[(...)->(...)]` 在泛型与高阶函数中的表达与推导稳定性。
- 优先覆盖“参数/返回均为 callable-instance”的组合路径与边界错误提示。

### 4) `llm_uncertain` 与字符串真值/拼接策略收敛
- 审查运行时与公理层中 `str + llm_uncertain` 过渡兼容策略。
- 明确从“过渡期兼容”迁移到“异常/显式处理”路径的落地条件与步骤。

---

## 说明
- 类型系统 M1–M5 主线已完成，不再作为当前 P0 主线。
- 当前 P0 聚焦：Intent / Behavior / VM / callable-instance 语义收敛。
