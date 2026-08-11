# 协程与迭代器设计

> 调度器多任务化与语言级 `await` 表达式、语言级惰性生成器（`yield`/`yield from`）构成 IBCI 的异步与迭代执行模型。**无 async 函数关键字**：任意函数均可 `await`（透明 async），`yield` 使函数成为惰性生成器。

## 定位

面向需要理解 IBCI 异步模型边界或评估协程方向的架构读者。本文概述协程与迭代方向的执行模型；并发与通信的语言面见 `docs/syntax/14_concurrency.md`，并发语言语义限制见 `docs/KNOWN_LIMITS.md` §二十二。

## 执行模型

- 调度器多任务化：`core/runtime/vm/task_scheduler.py` 承担任务调度与协作式挂起恢复。
- 语言级 `await` 表达式（AST `IbAwaitExpr`）：阻塞即挂起，由调度器通知式唤醒。
- 宿主异步统一 `Waitable` 协议：宿主等待原语经统一协议接入调度器。
- 语言级惰性生成器：`yield` 使函数自动成为惰性生成器（含 `yield from` 委托；语法与语义见 `docs/syntax/05_functions.md` §5.8/5.9）。

## 深入指引

- 并发与通信语言面：`docs/syntax/14_concurrency.md`
- 通信原语限制：`docs/KNOWN_LIMITS.md` §二十二
- VM 调度与执行模型：`docs/architecture/04_vm_interpreter.md`、`docs/architecture/05_vm_specification.md`
