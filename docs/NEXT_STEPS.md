# IBC-Inter 近期优先任务

> 本文档只记录"接下来可以直接开工的任务"。  
> 中长期任务见 `docs/PENDING_TASKS.md`，已完成工作见 `docs/COMPLETED.md`，VM 架构长期设想见 `docs/PENDING_TASKS_VM.md`。
>
> **最后更新**：2026-05-02（双轨消除路线图 P1-P7 **全部完成**；LLM 异常层次 E1-E5 实现；**当前测试基线：1028 个测试通过**）

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

技术债已全部清零；**fn/lambda/snapshot 类型系统重设计均已完成（1028 测试通过）**；
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

### ~~选项 6：双轨制彻底消灭（P1-P7）~~ ✅ **全部完成（2026-04-30）**

**背景**：M3 CPS 迁移后存在两条执行路径——VM CPS Path（目标）和 Expression Eval Path（旧路径，待消灭）。旧路径依赖 `Interpreter.visit()` + Python 递归 + Python 异常控制流（`ReturnException`/`BreakException`/`ContinueException`），与 Python 底层深度耦合。完整路线图见 `docs/PENDING_TASKS_VM.md §十一`。

**全部完成（2026-04-30）**：
- ✅ **P1**：`_pre_evaluate_user_classes` → `_get_vm_executor().run()`
- ✅ **P4**：`vm_handle_IbLLMExceptionalStmt` else fallback → 直接 `yield target_uid`
- ✅ **H2**：`ExprHandler.visit_IbLambdaExpr` 迁移到编译期 `free_vars`（运行时 AST 遍历消除）
- ✅ **P2**：`IbDeferred.call()` CPS 化（`_execution_context` 字段删除）
- ✅ **P3**：提示词 segment 求值内联到 `vm_handle_IbBehaviorExpr`
- ✅ **P4b**：dispatch loop fallback 删除
- ✅ **P5**：旧 Handler 类删除（−1400 行）
- ✅ **P6**：`ReturnException`/`BreakException`/`ContinueException` 删除；`Signal` 是唯一控制流载体
- ✅ **P7**：文件结构重组；`handlers/` 目录删除

双轨彻底消灭：VMExecutor CPS 调度循环是唯一执行入口。

### 选项 7：Semantic 代码健康三件套

以下三项均独立可交付，与其他选项无前置依赖：

- **H5（P1）：ExpressionAnalyzer ghost class 清理**  
  `core/compiler/semantic/passes/expression_analyzer.py` 定义了 `ExpressionAnalyzer` 类，包含 `visit_IbBinOp`、`visit_IbName`、`visit_IbCall` 等方法，但全仓库无任何 import 或实例化。是一次未完成重构的遗留产物。可直接删除，或完成为 `SemanticAnalyzer` 的表达式类型推导委托类。详见 `docs/PENDING_TASKS.md §11.8`。

- **H6（P2）：`_pending_intents` 动态属性信道形式化**  
  `DeclarationComponent.parse_declaration()` 通过 `setattr(stmt, "_pending_intents", ...)` 将意图注释"涂抹"到 AST 节点，再由 `SemanticAnalyzer` 在 Pass 中读取。这是 parser→semantic 的隐式信道，与已删除的 `_pending_fn_return_type` 同类问题。可迁移为 AST 节点的显式字段或侧表。详见 `docs/PENDING_TASKS.md §11.9`。

- **H7（P2）：`visit_IbAssign` 复杂度降低**  
  `SemanticAnalyzer.visit_IbAssign` 是全文件中逻辑分支最多的单一方法（处理 fn 推导、auto 推导、global 作用域、llmexcept 只读约束、行为表达式特殊路径、元组解包等共 8+ 分支）。需拆分为职责单一的子函数以提高可维护性。详见 `docs/PENDING_TASKS.md §11.10`。

---

## 任务依赖图

```
✅ 核心公理化 + VM 主路径 + 多解释器并发 + LLM 流水线 + 编译器深度清洁 + fn 类型系统重设计（1028 测试）
✅ P1（_pre_evaluate → VMExecutor）+ P4（IbLLMExceptionalStmt fallback 删除）+ H2（free_vars 迁移）
✅ P2（IbDeferred CPS 化）+ P3（提示词 segment 内联）
✅ P4b（dispatch loop fallback 删除）→ P5（旧 handler 类删除，−1400 行）→ P6（Python 异常控制流类删除）→ P7（目录重组）
✅ E1-E5：LLM 异常层次（LLMError/LLMParseError/LLMRetryExhaustedError/LLMCallError）
    │
    ├── 用户面语义修复（try/except、泛型）
    ├── 目标语言后端（Rust/Go 参考实现）
    ├── 类型引用重构（TypeRef，与下一代 VM 升级配合）
    ├── 插件系统完善（方法/类型模块语义、Scheduler 符号注入）
    ├── LLM 永久失败传播语义
    └── Semantic 代码健康（选项 7，H5–H7，各自独立）
```

---

*本文档记录近期可执行任务。详细历史见 `docs/COMPLETED.md`；VM 长期架构见 `docs/PENDING_TASKS_VM.md`。*
