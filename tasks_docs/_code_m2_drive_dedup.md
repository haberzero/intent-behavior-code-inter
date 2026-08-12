# _code_m2_drive_dedup — M2 驱动去重（PT-DEBT-15 剩余）

> **性质**：临时任务文档（实施完删除）。独立分支 exp/async-m1m2 实验。
> **背景**：`_ASYNC_UNIFY.md` M2——线程体独立驱动循环与主 VM 重复实现，
> trampoline/GeneratorYield 语义需双维护。成功判据：单一驱动循环。

## 现状（Phase 1 理解）

- **主 VM** `VMExecutor._drive_loop_gen`（vm_executor.py:204）——VMTask 栈调度循环，
  统一处理：Waitable 挂起（yield 向外）、str child uid（`_make_task` 压栈）、
  `UserFunctionCall`（`is_generator` → `make_generator_driver` / 否则 `_make_user_function_task`）、
  `GeneratorYield`（语言产出 yield 向外）、`Signal` / `UnhandledSignal` / `None` 规范化、协作取消。
  是**单一权威驱动循环**（run/run_many 共用）。
- **线程体** `coordinator._drive_generator`（coordinator.py:307）——独立手写驱动：
  原始生成器栈 + 每节点 `task_vm.run(yielded)`（**嵌套调度器**）+ `UserFunctionCall`
  直接 `_vm_call_user_function` 压原始生成器（**缺 is_generator 分派**）+ **缺 GeneratorYield
  处理** + **缺 None/Signal 规范化**。

## 问题（去重动机）

两套驱动逻辑双维护：
1. 线程体 `task_vm.run(yielded)` 每次新建调度器（嵌套调度器），与主 VM `_make_task` 压栈同栈不一致。
2. 线程体缺 `is_generator` 分派（spawn 生成器函数会损坏）。
3. trampoline / GeneratorYield / Signal / None 规范化双写，语义漂移风险。

## 方案（已实现）

线程体 `_drive_generator` 改为复用主 VM 的 `_drive_loop_gen` + `TaskScheduler`：

- 根生成器包装为 `VMTask` 压栈，经 `task_vm._drive_loop_gen([task])`（**单一权威驱动
  循环**）驱动到完成。
- `TaskScheduler` 提供统一协作调度：Waitable 经 `try_result` 非阻塞消费 + `register_wake`
  通知式唤醒 + park；**协作取消（cancel_event）在 park 期取消等待任务**（D5 闭合）。
- 结果转译：`TaskScheduler` 返回 `[TaskCancelled]` 表示协作取消 → 转 `ThreadCancelled`。

### 实现中修正（自我质询 + 实测）
- **初版用"阻塞泵"（手写循环对 Waitable `.result()` 阻塞）→ 死锁**：旧代码线程体
  cancel 中断 recv 的来源是**嵌套 `task_vm.run` → TaskScheduler 的 park 期 cancel 机制**，
  而手写泵对 recv Waitable 调 `buffer.recv()`（永久阻塞）、cancel 无法中断。改为直接用
  `TaskScheduler` 驱动 `_drive_loop_gen`，由 TaskScheduler 承担取消——正确复用统一调度。
- **移除死参数 `send_first`**：原签名保留但新实现未使用、且无任何调用方传值。

### 边界
- 生成器函数被 spawn（根是生成器）：`_drive_loop_gen` 遇 `GeneratorYield` yield 向外，
  TaskScheduler 对非 Waitable yield fail-fast（与既有"生成器不可直接 spawn 为任务"语义一致）。

## 验证
- 全量 pytest 2128 passed / 1 skipped 零回归（含线程体递归 depth=300 / 阻塞 recv /
  cancel / await t / slot.update CAS 既有测试全过）。
- 移除 `_drive_generator` 原独立驱动循环（trampoline/GeneratorYield/Signal/None 规范化/
  协作取消）双写——现在唯一权威为 `_drive_loop_gen`。
