# IBC-Inter 近期优先任务

> 记录接下来可以直接开工的具体任务，按优先级排列。
> 中长期任务见 `docs/PENDING_TASKS.md`，已完成工作见 `docs/COMPLETED.md`。
>
> **最后更新**：2026-04-18（Step 4b ibci_ihost/idbg KernelRegistry 重构完成；下一重点：Step 5 IbFunction.call() 去除 context 依赖）

---

## 1. Step 5：IbFunction.call() 去除 context 参数依赖 [P2]

**任务**：`IbUserFunction.call(self, receiver, args)` / `IbNativeFunction.call()` 当前仍通过外部传入 `execution_context` 执行。目标是让函数对象在创建时捕获执行上下文引用（类比 `IbBehavior` 的 `_execution_context` 模式），使 call() 真正自主执行，彻底消除对外部 context 参数的依赖。

**注意**：此重构涉及调用栈、递归、闭包捕获等复杂并发场景，需要先仔细讨论并发模型再动工。

**文件**：`core/runtime/objects/kernel.py`（IbUserFunction/IbNativeFunction）、`core/runtime/interpreter/handlers/expr_handler.py`、`core/runtime/interpreter/interpreter.py`

---

*本文档记录近期可执行任务。中长期任务见 `docs/PENDING_TASKS.md`。*

