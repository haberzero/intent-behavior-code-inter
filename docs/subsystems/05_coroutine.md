# 协程与迭代器设计（SHELVED）

> **状态**：Stage 2 调度器多任务化与语言级 `await` 表达式已落地；语言级 async 函数 / 生成器（`yield`）为演进目标，**SHELVED**——保持规划不主动推进。当前实现状态以代码为准。

## 定位

面向需要理解 IBCI 异步模型边界或评估协程方向的架构读者。本文记录该方向的**状态**；已实现的并发语言面见 `docs/syntax/14_concurrency.md`，并发语言语义限制见 `docs/KNOWN_LIMITS.md` §二十四。

## 当前状态

- **已落地**：调度器多任务化（`core/runtime/vm/task_scheduler.py`）、语言级 `await` 表达式（AST `IbAwaitExpr`）、宿主异步统一 `Waitable` 协议。
- **SHELVED**：语言级 async 函数 / 生成器（`yield` 使函数成为生成器）。依赖调度器多任务挂起恢复与快照协议覆盖 yield 点，尚未实现。

## 深入指引

- 并发与通信语言面：`docs/syntax/14_concurrency.md`
- 通信原语限制：`docs/KNOWN_LIMITS.md` §二十四
- VM 调度与执行模型：`docs/architecture/04_vm_interpreter.md`、`docs/architecture/05_vm_specification.md`
