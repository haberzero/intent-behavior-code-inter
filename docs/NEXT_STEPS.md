# IBC-Inter 近期优先任务

> 本文档只记录"接下来可以直接开工的任务"。  
> 中长期任务见 `docs/PENDING_TASKS.md`，已完成工作见 `docs/COMPLETED.md`，VM 架构长期设想见 `docs/PENDING_TASKS_VM.md`。
>
> **最后更新**：2026-05-06（用户自定义异常落地；except 类型窄化完成；LLMCallError 接入；is_uncertain 从用户 API 移除；**当前测试基线：1056 个测试通过**；TypeRef 重构（选项3）为高优先级近期主线）

---

## 当前状态摘要

核心公理化路径 + VM 主路径切换 + 多解释器并发 + LLM 流水线 + 跨实现合规 + 编译器深度清洁 + fn 类型系统重设计 + LLM 异常层次 + 用户自定义异常 + try/except 完整机制 **全部完成**。详细记录见 `docs/COMPLETED.md`。

代码层面的关键事实：
- VM 主路径：模块顶层 + `IbUserFunction.call()` 函数体均通过 `VMExecutor.run()` / `run_body()` 执行（CPS 调度）。
- CPS dispatch 覆盖 43 节点；handlers 中无显式 `fallback_visit()` 调用。
- 控制流：`Signal(kind, value)` 数据对象沿生成器栈传播；只在 VM 顶层未消费时包装为 `UnhandledSignal` 抛出。
- 闭包：lambda 自由变量经共享 `IbCell` 捕获；`free_vars` 编译期填充 + `cell_captured_symbols` 侧表防止 LLMFuture 写入 IbCell。
- 多 Interpreter 并发：`ihost.spawn_isolated/collect`。
- LLM 流水线：DDG 编译期分析 + LLMScheduler/Future + dispatch-before-use。
- 跨实现合规：`docs/VM_SPEC.md` 正式规范 + `tests/compliance/` 32 测试。
- **异常体系完整**：`try/except/raise/finally` 全路径可用；LLMError/LLMParseError/LLMRetryExhaustedError/LLMCallError 层次完整；用户可以 `class MyError(Exception):` 自定义并 raise/catch。

---

## 下一里程碑选项（按建议优先级）

技术债已全部清零；**fn/lambda/snapshot 类型系统重设计 + LLM 异常层次 + 用户自定义异常 + try/except 机制均已完成（1056 测试通过）**；
可在以下方向中选择主线推进：

### 选项 1：Semantic 用户面其他问题修复

直接影响用户写 IBCI 代码的体验。涉及：

- ~~**`except X as e:` 类型窄化**（近期可交付）~~ ✅ **已完成（2026-05-06）**：`visit_IbExceptHandler` 现在正确捕获 `self.visit(node.type)` 返回值，单一 ClassSpec 异常类型直接用于窄化捕获变量类型。
- **泛型类型推断进一步改进**：详见 `docs/KNOWN_LIMITS.md §十六`（剩余约 2 项：`tuple` 元素类型标注 §16.5、`dict` value 类型推断完善）。
- **OI-1 `str + llm_uncertain` 隐式拼接清理**：在 `llmexcept` + dispatch-before-use 路径确认不再触发后，可收紧为类型错误。详见 `docs/OPEN_ISSUES.md OI-1`。

### 选项 2：目标语言后端 【低优先级】

在 VM_SPEC 与 32 compliance 测试基础上，以另一宿主语言（Rust 或 Go）做最小子集 VM 参考实现。这是 IBC-Inter "标准语言"愿景的关键一步，但工程量大、门槛高，**当前优先级低**，待类型系统和 VM 进一步稳定后再规划。

### 选项 3：TypeRef 重构 【高优先级——近期主线】

`docs/PENDING_TASKS.md §13`（类型系统长期演进）— 用 `TypeRef` 统一所有"类型内容"表示，消除 `IbSpec.name` 同时承担注册键 + 语义分类标签的二义性。这是 VM 完善和类型系统深化的基础性工程，与用户声明的近期主线（VM 完善 + 类型系统完善）直接对齐。详细分析见本文档末尾"TypeRef 重构分析"节。

### 选项 4：插件系统待实现部分

`docs/PENDING_TASKS.md`（插件显式引入）：明确"方法模块"vs"类型模块"语义；Scheduler 符号注入逻辑标记外部模块符号。

### ~~选项 5：LLMCallError 触发路径决策~~ ✅ **已完成（2026-05-06）**

`_call_llm()` 中所有 provider 层异常现已 `raise ThrownException(LLMCallError)`，跳过 llmexcept retry。
用户使用 `try except LLMCallError` 处理网络/鉴权问题。详见 `PENDING_TASKS.md §10.2`、`OPEN_ISSUES.md OI-7`。

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

### ~~选项 7：Semantic 代码健康三件套~~ ✅ **全部完成（2026-05-02）**

以下三项均已完成：

- ✅ **H5（P1）：ExpressionAnalyzer ghost class 清理** — `expression_analyzer.py` 及所有无效引用已删除（2026-05-02）。
- ✅ **H6（P2）：`_pending_intents` 动态属性信道形式化** — `_pending_intents` 幽灵管道（旧意图涂抹模型残留）已完全删除（2026-05-02）。
- ✅ **H7（P2）：`visit_IbAssign` 复杂度降低** — `visit_IbAssign` 已拆分为 10+ 职责单一的私有子函数（`_check_void_assign`、`_resolve_target_name_and_type`、`_handle_attr_subscript_target`、`_handle_tuple_unpack_target`、`_check_llmexcept_readonly`、`_bind_global_ref`、`_infer_and_define_symbol`、`_infer_target_type_from_declared`、`_infer_fn_type`、`_bind_symbol_to_side_table` 等），主方法约 32 行（2026-05-02）。

---

## 任务依赖图

```
✅ 核心公理化 + VM 主路径 + 多解释器并发 + LLM 流水线 + 编译器深度清洁 + fn 类型系统重设计（1028 测试）
✅ P1（_pre_evaluate → VMExecutor）+ P4（IbLLMExceptionalStmt fallback 删除）+ H2（free_vars 迁移）
✅ P2（IbDeferred CPS 化）+ P3（提示词 segment 内联）
✅ P4b（dispatch loop fallback 删除）→ P5（旧 handler 类删除，−1400 行）→ P6（Python 异常控制流类删除）→ P7（目录重组）
✅ E1-E5：LLM 异常层次（LLMError/LLMParseError/LLMRetryExhaustedError/LLMCallError）
✅ H5-H7：Semantic 代码健康三件套（ExpressionAnalyzer 清理、_pending_intents 删除、visit_IbAssign 拆分）
✅ 插件系统（§9）：OI-3 修复（显式引入已执行，SEM_009 import 冲突 WARNING 新增）
✅ 泛型推断 G3：resolve_member 特化（list[T].__getitem__→T，dict[K,V].get/values/keys 特化，嵌套泛型 list[list[T]] 修复）
✅ 用户自定义异常 + try/except 完整落地（EXCEPTION_SPEC→ClassSpec，vm_handle_IbTry，TestE2EUserDefinedException ×7）
    │
    ├── 【高优先级主线】TypeRef 重构（§13，类型系统深化基础，VM 完善配合）
    │       └── → 进一步泛型改进（嵌套泛型链式推断、函数返回类型精确传播）
    ├── except 类型窄化（§3.9，小改动，用户体验修复）
    ├── OI-1 str+uncertain 清理（待 dispatch-before-use 路径分析后决策）
    ├── OI-7 LLMCallError 触发路径决策（§10.2）
    └── 【低优先级】目标语言后端（Rust/Go 参考实现）
```

---

## TypeRef 重构分析（选项 3 详述）

### 现状问题

`IbSpec.name` 字段身兼二职：

1. **注册表键**（`"list[int]"`、`"dict[str,int]"`）
2. **语义分类标签**（`"list"`、`"dict"`）

泛型出现后两职冲突。补丁方案（`get_base_name()` + `get_base_spec()`）已消除大部分 `.name` 直比问题，但**字符串类型引用**（`FuncSpec.return_type_name: str`、`ListSpec.element_type_name: str`、`MemberSpec.type_name: str` 等）的本质缺陷仍在：

| 当前问题 | 具体表现 |
|---------|---------|
| 嵌套泛型表达力不足 | `list[list[int]]` 的元素类型 `list[int]` 存储为字符串，无法通过类型引用做结构操作 |
| 跨模块类型丢失 | `FuncSpec.return_type_name` 仅存 `"MyClass"` 而非 `"module.MyClass"`，跨模块符号解析需额外 `return_type_module` 字段补救 |
| 函数返回类型不能传播泛型参数 | `func -> list[int]` 的返回类型只能表达为字符串，调用处类型推断退化为 `list` |
| TypeRef 重构时接触面极广 | 每个 spec 字段都是 `str`，改动涉及 spec 层、compiler 层、runtime 层、序列化层全栈 |

### TypeRef 设计（PENDING_TASKS.md §13.2 已记录）

```python
@dataclass(frozen=True)
class TypeRef:
    base_name: str                          # "list", "dict", "int"
    args: Tuple["TypeRef", ...] = ()        # 泛型参数，递归
    module: Optional[str] = None
    nullable: bool = False
```

### 推荐实施路线（分阶段）

| 阶段 | 范围 | 改动量 |
|------|------|--------|
| Phase 1 | 定义 TypeRef；`FuncSpec.return_type` 迁移；`SpecRegistry.resolve_return` 接受 TypeRef | 小（约 200 行）|
| Phase 2 | `ListSpec.element_type`、`DictSpec.key_type/value_type`、`TupleSpec.element_type` 迁移 | 中（约 400 行）|
| Phase 3 | `MemberSpec.type_ref` 迁移；compiler resolver 产出 TypeRef | 大（约 600 行，跨 compiler/runtime）|
| Phase 4 | 序列化层迁移；VM 侧表类型 `node_to_type: TypeRef` | 大（跨多文件）|

**Phase 1 可独立交付**，不破坏现有行为，但立即解决跨模块函数返回类型丢失模块信息的问题。

---
*本文档记录近期可执行任务。详细历史见 `docs/COMPLETED.md`；VM 长期架构见 `docs/PENDING_TASKS_VM.md`。*
