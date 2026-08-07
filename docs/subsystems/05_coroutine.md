# 协程与迭代器设计

> **状态**：Stage 2 调度器多任务化与语言级 `await` 表达式已落地；语言级生成器（`yield`）为演进方向（列为阶段 5 实现项，设计见 `tasks_docs/EXEC_FOUNDATION_DESIGN.md` §5.2）。**无 async 函数关键字**：任意函数均可 `await`（透明 async），`yield` 使函数成为惰性生成器。当前实现状态以代码为准。

## 定位

面向需要理解 IBCI 异步模型边界或评估协程方向的架构读者。本文记录该方向的**状态**；已实现的并发语言面见 `docs/syntax/14_concurrency.md`，并发语言语义限制见 `docs/KNOWN_LIMITS.md` §二十二。

## 当前状态

- **已落地**：调度器多任务化（`core/runtime/vm/task_scheduler.py`）、语言级 `await` 表达式（AST `IbAwaitExpr`）、宿主异步统一 `Waitable` 协议。
- **规划中**：语言级生成器（`yield` 使函数成为惰性生成器），依赖调度器多任务挂起恢复与快照协议覆盖 yield 点，尚未实现。

## 深入指引

- 并发与通信语言面：`docs/syntax/14_concurrency.md`
- 通信原语限制：`docs/KNOWN_LIMITS.md` §二十二
- VM 调度与执行模型：`docs/architecture/04_vm_interpreter.md`、`docs/architecture/05_vm_specification.md`
