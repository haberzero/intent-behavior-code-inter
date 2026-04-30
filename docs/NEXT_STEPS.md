# IBC-Inter 近期优先任务

> 本文档只记录"接下来可以直接开工的任务"。  
> 中长期任务见 `docs/PENDING_TASKS.md`，已完成工作见 `docs/COMPLETED.md`，VM 架构长期设想见 `docs/PENDING_TASKS_VM.md`。
>
> **最后更新**：2026-04-30（在编译器全清洁基础上，新增 Handler/VM 层双轨路径分析；识别 ExpressionAnalyzer ghost class、`_pending_intents` 隐式信道、`visit_IbAssign` 复杂度、ExprHandler 运行时 AST 遍历等技术债；新增选项 6/7；**当前测试基线：1011 个测试通过**）

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

### 选项 6：Handler 层 Expression Eval Path 整理

针对 Handler 层"双轨执行"（CPS Path + Expression Eval Path）残留的具体技术债，各子项独立可交付：

- **H1（P1）：VM_SPEC.md 正式定名双轨路径**  
  在 `docs/VM_SPEC.md` 中正式命名 `VM CPS Path` 和 `Expression Eval Path`，定义边界规则："哪类节点走哪条路径"。消除贡献者困惑，是所有 H2–H4 工作的架构前提。工程量：纯文档，1–2 小时。

- **H2（P1）：ExprHandler.visit_IbLambdaExpr 迁移到 `free_vars` 字段**  
  VM handler（`vm_handle_IbLambdaExpr`）已使用编译期 `free_vars` 字段，但 `ExprHandler.visit_IbLambdaExpr`（Expression Eval Path）仍在运行时调用 `_collect_free_refs()` 遍历 artifact dict。统一为读 `node_data["free_vars"]`，消除最后一处"运行时 AST 遍历"。详见 `docs/PENDING_TASKS_VM.md §十一.H2`。

- **H3（P1）：StmtHandler.visit_IbFor 与 C11 llmexcept_handler 语义对齐**  
  `vm_handle_IbFor` 已内联 `llmexcept_handler` 重试逻辑；`StmtHandler.visit_IbFor`（Expression Eval Path）缺失此逻辑。在类字段默认值预评估场景下若触发 for+llmexcept，旧路径会静默跳过重试语义。详见 `docs/PENDING_TASKS_VM.md §十一.H3`。

- **H4（P2）：to_native() 跨层契约正式界定**  
  `vm_handle_IbDict` / `vm_handle_IbSlice` 直接调用 `obj.to_native()`；这是 VM 层对"标量用作 Python 容器键或切片索引时必须可降解"的隐式契约。需在 VM_SPEC.md 中正式定义此"Object-to-native bridge contract"。

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
✅ 核心公理化 + VM 主路径 + 多解释器并发 + LLM 流水线 + 编译器深度清洁 + fn 类型系统重设计（1011 测试）
    │
    ├── 用户面语义修复（try/except、泛型）
    ├── 目标语言后端（Rust/Go 参考实现）
    ├── 类型引用重构（TypeRef，与下一代 VM 升级配合）
    ├── 插件系统完善（方法/类型模块语义、Scheduler 符号注入）
    ├── LLM 永久失败传播语义
    ├── Handler 层 Expression Eval Path 整理（H1–H4，选项 6，各自独立）
    └── Semantic 代码健康三件套（H5–H7，选项 7，各自独立）
```

---

*本文档记录近期可执行任务。详细历史见 `docs/COMPLETED.md`；VM 长期架构见 `docs/PENDING_TASKS_VM.md`。*
