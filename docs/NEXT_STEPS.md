# IBC-Inter 近期优先任务

> 本文档只记录"接下来可以直接开工的任务"。  
> 中长期任务见 `docs/PENDING_TASKS.md`，已完成工作见 `docs/COMPLETED.md`，VM 架构长期设想见 `docs/PENDING_TASKS_VM.md`。
>
> **最后更新**：2026-04-29（编译器深度清洁 Phase 1–5 全部完成；C5/C6/C7/C8/C9/C10/C11/C12/C13/C14 全部 ✅；CPS dispatch table 覆盖 43 节点；`fallback_visit()` 显式调用归零；`node_protection` 侧表 + `ControlSignalException` 类全链路删除；**989 个测试通过**；**剩余 C/L 类技术债：无**）

---

## 当前状态摘要

核心公理化路径（Step 1–8）+ M1/M2/M3a-d/M4/M5a-c/M6 + 编译器深度清洁 Phase 1–5 **全部完成**。详细记录见 `docs/COMPLETED.md` §一–§二十一。

代码层面的关键事实：
- VM 主路径：模块顶层 + `IbUserFunction.call()` 函数体均通过 `VMExecutor.run()` / `run_body()` 执行（CPS 调度）。
- CPS dispatch 覆盖 43 节点；handlers 中无显式 `fallback_visit()` 调用。
- 控制流：`Signal(kind, value)` 数据对象沿生成器栈传播；只在 VM 顶层未消费时包装为 `UnhandledSignal` 抛出。
- 闭包：lambda 自由变量经共享 `IbCell` 捕获；`free_vars` 编译期填充 + `cell_captured_symbols` 侧表防止 LLMFuture 写入 IbCell。
- 多 Interpreter 并发：`ihost.spawn_isolated/collect`（M4）。
- LLM 流水线：DDG 编译期分析 + LLMScheduler/Future + dispatch-before-use（M5a/b/c）。
- 跨实现合规：`docs/VM_SPEC.md` 正式规范 + `tests/compliance/` 32 测试（M6）。

---

## 下一里程碑选项（按建议优先级）

DEFERRED 类技术债已清零，可在以下方向中选择主线推进：

### 选项 1：Semantic 用户面问题修复（建议优先）

直接影响用户写 IBCI 代码的体验。涉及：

- **`fn` 类型系统重设计**：`fn` 当前在跨场景调用、`__call__` 协议解析、闭包捕获、与 lambda/snapshot 互通的若干路径上存在不一致（详见 `docs/KNOWN_LIMITS.md` 三）。
- **`try/except` 与 IBCI 错误模型对齐**：当前 `try/except/finally` 词法/语法接受但运行时不真正捕获非语言级异常（详见 `docs/KNOWN_LIMITS.md` 二）。需与 `llmexcept` 体系融合或重新设计。
- **泛型类型推断改进**：详见 `GENERICS_CONTAINER_ISSUES.md`（下标访问不传播泛型参数、特化 axiom 方法引导不全、嵌套泛型推断缺失等 6 项）。

### 选项 2：M7 可移植性目标语言后端

在 M6（VM_SPEC + 32 compliance 测试）基础上，以另一宿主语言（Rust 或 Go）做最小子集 VM 参考实现。这是 IBC-Inter "标准语言"愿景的关键一步。

### 选项 3：TypeRef 重构

`docs/PENDING_TASKS.md` §13 — 用 `TypeRef` 统一所有"类型内容"表示，消除 `IbSpec.name` 同时承担注册键 + 语义分类标签的二义性。工程量大、需与下一代 VM 架构升级配合。

### 选项 4：Plugin 系统 Phase 3/4

`docs/PENDING_TASKS.md` §9.1：明确"方法模块"vs"类型模块"语义；Scheduler 符号注入逻辑标记外部模块符号。

### 选项 5：LLMPermanentFailureError 传播语义

`docs/PENDING_TASKS_VM.md` 失败传播部分 — 当前 LLM 重试耗尽后产生 `Uncertain`，但 permanent failure 与可恢复错误的语义边界、跨函数传播、与 `try/except` 的协同尚未完整规范。

---

## 任务依赖图

```
✅ Step 1–8 + M1–M6 + Phase 1–5（989 测试）
    │
    ├── 选项 1：Semantic 用户面问题修复
    ├── 选项 2：M7 可移植性目标语言后端
    ├── 选项 3：TypeRef 重构（与下一代 VM 升级配合）
    ├── 选项 4：Plugin 系统 Phase 3/4
    └── 选项 5：LLMPermanentFailureError 传播语义
```

---

*本文档记录近期可执行任务。详细历史见 `docs/COMPLETED.md`；VM 长期架构见 `docs/PENDING_TASKS_VM.md`。*
