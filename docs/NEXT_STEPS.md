# IBC-Inter 近期优先任务

> 本文档只记录"接下来可以直接开工的任务"。  
> 中长期任务见 `docs/PENDING_TASKS.md`，已完成工作见 `docs/COMPLETED.md`，VM 架构长期设想见 `docs/PENDING_TASKS_VM.md`。
>
> **最后更新**：2026-04-29（编译器深度清洁全部落地；CPS dispatch table 覆盖 43 节点；`fallback_visit()` 归零；`node_protection` 侧表全链路删除；fn/lambda/snapshot 类型系统重设计全部完成（`fn[(int,str)->bool]` callable 签名标注）；历史工作文件已归档至本文件；**1011 个测试通过**；**剩余技术债：无**）

---

## 当前状态摘要

核心公理化路径 + VM 主路径切换 + 多解释器并发 + LLM 流水线 + 跨实现合规 + 编译器深度清洁 + fn 类型系统重设计 **全部完成**。详细记录见 `docs/COMPLETED.md`。

代码层面的关键事实：
- VM 主路径：模块顶层 + `IbUserFunction.call()` 函数体均通过 `VMExecutor.run()` / `run_body()` 执行（CPS 调度）。
- CPS dispatch 覆盖 43 节点；handlers 中无显式 `fallback_visit()` 调用。
- 控制流：`Signal(kind, value)` 数据对象沿生成器栈传播；只在 VM 顶层未消费时包装为 `UnhandledSignal` 抛出。
- 闭包：lambda 自由变量经共享 `IbCell` 捕获；`free_vars` 编译期填充 + `cell_captured_symbols` 侧表防止 LLMFuture 写入 IbCell。
- 多 Interpreter 并发：`ihost.spawn_isolated/collect`。
- LLM 流水线：DDG 编译期分析 + LLMScheduler/Future + dispatch-before-use。
- 跨实现合规：`docs/VM_SPEC.md` 正式规范 + `tests/compliance/` 32 测试。

---

## 下一里程碑选项（按建议优先级）

技术债已全部清零；**fn/lambda/snapshot 类型系统重设计均已完成（1011 测试通过）**；
可在以下方向中选择主线推进：

### 选项 1：Semantic 用户面其他问题修复

直接影响用户写 IBCI 代码的体验。涉及：

- **`try/except` 与 IBCI 错误模型对齐**：当前 `try/except/finally` 词法/语法接受但运行时不真正捕获非语言级异常（详见 `docs/KNOWN_LIMITS.md` 二）。需与 `llmexcept` 体系融合或重新设计。
  - 关联交付项：`core/runtime/objects/builtins.py:326` 和 `core/kernel/axioms/primitives.py:400` 中对 `str + llm_uncertain` 的显式放行 `# TODO(future)` 注释——这两处过渡期妥协在 try/except 修复落地后应一并收紧。
- **泛型类型推断改进**：详见 `docs/KNOWN_LIMITS.md §十六`（下标访问不传播泛型参数、特化 axiom 方法引导不全、嵌套泛型推断缺失等 6 项，改进方向见 `docs/PENDING_TASKS.md §3.4`）。

### 选项 2：目标语言后端

在 VM_SPEC 与 32 compliance 测试基础上，以另一宿主语言（Rust 或 Go）做最小子集 VM 参考实现。这是 IBC-Inter "标准语言"愿景的关键一步。

### 选项 3：TypeRef 重构

`docs/PENDING_TASKS.md`（类型系统长期演进）— 用 `TypeRef` 统一所有"类型内容"表示，消除 `IbSpec.name` 同时承担注册键 + 语义分类标签的二义性。工程量大、需与下一代 VM 架构升级配合。

### 选项 4：插件系统待实现部分

`docs/PENDING_TASKS.md`（插件显式引入）：明确"方法模块"vs"类型模块"语义；Scheduler 符号注入逻辑标记外部模块符号。

### 选项 5：LLMPermanentFailureError 传播语义

`docs/PENDING_TASKS_VM.md`（失败传播） — 当前 LLM 重试耗尽后产生 `Uncertain`，但 permanent failure 与可恢复错误的语义边界、跨函数传播、与 `try/except` 的协同尚未完整规范。

---

## 任务依赖图

```
✅ 核心公理化 + VM 主路径 + 多解释器并发 + LLM 流水线 + 编译器深度清洁 + fn 类型系统重设计（1011 测试）
    │
    ├── 用户面语义修复（try/except、泛型）
    ├── 目标语言后端（Rust/Go 参考实现）
    ├── 类型引用重构（TypeRef，与下一代 VM 升级配合）
    ├── 插件系统完善（方法/类型模块语义、Scheduler 符号注入）
    └── LLM 永久失败传播语义
```

---

*本文档记录近期可执行任务。详细历史见 `docs/COMPLETED.md`；VM 长期架构见 `docs/PENDING_TASKS_VM.md`。*
