# IBC-Inter 近期优先任务

> 记录接下来可以直接开工的具体任务，按优先级排列。
> 中长期任务见 `docs/PENDING_TASKS.md`，已完成工作见 `docs/COMPLETED.md`。
>
> **最后更新**：2026-04-18（P1 三项任务（循环迭代器恢复、显式引入原则 Phase 1、嵌套 llmexcept 测试）全部完成；下一重点：Step 4b ibci_ihost/idbg 重构）

---

## 1. Step 4b：ibci_ihost / ibci_idbg 标准化重构 [P1]

**任务**：将 `ibci_ihost` 和 `ibci_idbg` 两个核心层插件从直接访问 `capabilities.service_context.host_service` / `capabilities.stack_inspector` / `capabilities.llm_executor` 等内部接口，迁移为通过 `KernelRegistry` 注册的稳定钩子接口（类比 `get_llm_executor()` 的模式）访问服务。

**设计方向**：
- `KernelRegistry` 新增 `register_host_service()` / `get_host_service()` 钩子
- `KernelRegistry` 新增 `register_stack_inspector()` / `get_stack_inspector()` 钩子，接口类型为 `IStackInspector` / `IStateReader`
- `ibci_ihost` / `ibci_idbg` 通过上述稳定接口替换对 `capabilities.service_context.*` 的直接访问

**文件**：`core/kernel/registry.py`、`core/base/interfaces.py`、`ibci_modules/ibci_ihost/`、`ibci_modules/ibci_idbg/`

---

*本文档记录近期可执行任务。中长期任务见 `docs/PENDING_TASKS.md`。*

