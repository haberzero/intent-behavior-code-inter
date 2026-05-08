# IBCI 审计发现记录（2026-05-08）

> 本文档记录 2026-05-08 对 IBCI 核心代码进行深度交叉审计后确认的问题。  
> 所有结论均通过代码直接核实，标注了具体文件和行号。  
> 随着代码演进，本文档中的条目应被逐步解决，并在相应任务文档中打勾。

---

## 问题一：LLM 行为调用路径逃逸 CPS 调度循环

**状态**：已确认，待解决  
**优先级**：P1

### 描述

IBCI 的 VM 采用 CPS（Continuation-Passing Style）调度循环（`VMExecutor._drive_loop`），所有 AST 节点的执行通过 `yield` 协议接受调度。但 LLM 调用的三条核心路径均绕过了这个机制，走同步 Python 调用链：

**路径 A**：`IbBehavior.call()`（`core/runtime/objects/builtins.py:971`）  
→ `executor.invoke_behavior(self, self._execution_context)`  
→ `execute_behavior_object` → `execute_behavior_expression` → `_call_llm`  
全程直接 Python 调用，不 yield 给 VMExecutor。

**路径 B**：`vm_handle_IbExprStmt`（`core/runtime/vm/handlers.py:372-374`）  
```python
if isinstance(res, IbValue) and res.ib_class.name == "behavior":
    return res.call(executor.registry.get_none(), [])  # 同步调用
```
对 behavior 对象的直接调用同样不在 CPS 循环内。

**路径 C**：`IbLLMFunction.call()`（`core/runtime/objects/kernel.py:985`）  
整个 LLM 函数调用（参数绑定、作用域管理、`invoke_llm_function`）都是直接 Python 调用。

### 影响

LLM 调用时的"执行帧"不受 VMExecutor 管理；快照机制（generator 挂起语义）对这条链路不适用；调试工具对 LLM 调用帧的可观测性不完整。

### 核实依据

- `core/runtime/objects/builtins.py:971-1032`（IbBehavior.call）
- `core/runtime/vm/handlers.py:372-374`（IbExprStmt behavior 路径）
- `core/runtime/objects/kernel.py:985-1074`（IbLLMFunction.call）

---

## 问题二：lambda/snapshot 捕获语义——代码已正确实现，但部分路径需要澄清

**状态**：语义澄清已确认正确；实现存在一处边界情况需关注  
**优先级**：P1（边界情况）

### 已确认正确的语义

**lambda 模式**（`core/runtime/vm/handlers.py:1332-1335`）：
- 通过 `current_scope.promote_to_cell(sym_uid)` 共享 IbCell 引用
- 调用时 `cell.get()` 返回**调用时刻的最新值**（引用语义、词法作用域）
- `captured_intents = None`，执行时走 `context.get_resolved_prompt_intents()`（调用时意图栈）

**snapshot 模式**（`core/runtime/vm/handlers.py:1323-1330`）：
- `IbCell(val)` 在定义时刻深拷贝值到独立 IbCell（冻结语义）
- `captured_intents = executor.runtime_context.fork_intent_snapshot()`（定义时刻意图栈快照）

### 需要关注的边界情况

`IbDeferred` 和 `IbBehavior` 在被作为 callable 对象调用时（非直接 CPS 执行路径），持有的是**定义时刻**的 `_execution_context` 引用（`builtins.py:730,930`）。若 lambda 在**跨帧**（不同函数调用层级）或**跨线程**（LLMFuture 后台线程）的场景中被调用，`_execution_context.runtime_context` 是定义时刻的上下文，不是调用时刻的——这与"lambda 在被调用时获取当时生效的意图栈"的语义要求存在潜在偏差。

CPS 路径（`vm_handle_IbCall` → `_vm_call_deferred`）中直接使用 `executor.runtime_context`（调用时上下文），是正确的。问题仅存在于通过 `.call()` 方法调用的非 CPS 路径。

### 核实依据

- `core/runtime/vm/handlers.py:1294-1360`（vm_handle_IbLambdaExpr）
- `core/runtime/vm/handlers.py:232-300`（_vm_call_deferred，CPS 路径）
- `core/runtime/objects/builtins.py:724-751,928-934`（_execution_context 持有方式）

---

## 问题三：`deferred` 概念未被根除，与设计原则存在语义摩擦

**状态**：已确认，详见 `docs/DEFERRED_REMOVAL_PLAN.md`  
**优先级**：P0（主要演进目标）

### 描述

IBCI 的设计原则是"行为描述表达式在 ibci 中的地位应当和其它平常的编程表达式完全平等"，`lambda`/`snapshot` 产生的可调用实例本质上是函数，不应被称为"延迟执行"机制。但 `deferred` 这个概念仍渗透在多个层次：

- **类型系统层**：`DEFERRED_SPEC`（`specs.py:41`），独立的 `TypeDef`，name="deferred"
- **公理层**：`DeferredAxiom`（`primitives.py`），独立公理，`is_compatible` 写有 `"deferred"` 字符串
- **运行时对象层**：`IbDeferred` 类（`builtins.py:694`），`@register_ib_type("deferred")`
- **工厂层**：`RuntimeObjectFactory.create_deferred()`（`factory.py:44`）
- **VM 层**：`vm_handle_IbCall` 中 `func.ib_class.name == "deferred"` 特判（`handlers.py:313`）
- **启动层**：`builtin_initializer.py` 中 "deferred" 在核心公理列表中
- **序列化层**：`runtime_serializer.py` 中 `_type = "deferred"` 标记
- **编译器层**：`semantic_analyzer.py` 中 `_deferred_desc`、`create_deferred()` 调用

### 核实依据

参见 `docs/DEFERRED_REMOVAL_PLAN.md` 的完整影响清单。

---

## 问题四：intent 体系 OOP 化存在双轨并行的逻辑断裂

**状态**：已确认，已记录于 `docs/PENDING_TASKS.md §四`  
**优先级**：P1

### 描述

`IbIntentContext` 运行时对象已存在，`IntentContextAxiom` 也已注册，但意图注释的**语法节点路径**与 `intent_context` 的 **OOP 接口路径**并行存在，互不相交：

**语法路径**（`@+`/`@-`/`@`/`@!`）：
- `vm_handle_IbIntentAnnotation`（`handlers.py:1130`）→ `executor.runtime_context.add_smear_intent()` / `set_pending_override_intent()`
- `vm_handle_IbIntentStackOperation`（`handlers.py:1150`）→ `executor.runtime_context.push_intent()` / `pop_intent()`
- 直接操作 `RuntimeContextImpl._intent_ctx` 内部字段

**OOP 路径**（`intent_context` 对象）：
- `ctx = intent_context.get_current()` / `ctx.push(...)` / `ctx.pop()` / `ctx.fork()`
- 通过 `IbIntentContext` 公开 API 操作

两条路径操作的是同一个底层 `_intent_ctx`，但代码逻辑完全独立，未来维护时容易引入不一致。

### 额外缺口

以下 OOP 化功能尚未实现（已记录在 `PENDING_TASKS.md §四`）：
- `intent_context` 实例作为函数调用参数（类型检查路径未打通）
- `intent_context` 实例作为函数参数类型声明
- `intent_context` 作为函数作用域默认上下文

### 核实依据

- `core/runtime/vm/handlers.py:1128-1172`（语法路径）
- `core/runtime/objects/intent_context.py`（OOP 路径）
- `docs/PENDING_TASKS.md:48-54`

---

## 问题五：llmexcept 快照恢复语义——`merge()` vs 直接替换未对齐

**状态**：已确认，需要深入确认与文档对齐  
**优先级**：P2

### 描述

`ARCH_DETAILS.md §1.4` 和 `INTENT_SYSTEM_DESIGN.md §4.6` 对 llmexcept 快照恢复中意图上下文的恢复方式描述不一致：

- 文档 A（`INTENT_SYSTEM_DESIGN.md §4.6`）描述为：`runtime_context._intent_ctx = frame.saved_intent_ctx.fork()`（直接替换引用）
- 实际代码（`llm_except_frame.py:270`）：`runtime_context.intent_context.merge(self.saved_intent_ctx)`（in-place 合并）

两者语义是否等价，取决于 `IbIntentContext.merge()` 的实现是**完全状态覆写**还是**增量合并**。

### 已确认的其他快照规则（正确实现）

- `save_context` 保存：变量快照（方案A深克隆 / 方案B `__snapshot__` 协议）、`fork()` 意图快照、循环上下文、retry_hint
- `loop_resume` 字段故意不重置（for 循环断点恢复）
- 函数对象、behavior 对象、NativeObject 被显式排除在变量快照之外

### 核实依据

- `core/runtime/interpreter/llm_except_frame.py:257-280`（restore_context）
- `docs/ARCH_DETAILS.md §1.4`
- `docs/INTENT_SYSTEM_DESIGN.md §4.6`

---

## 问题六：LLMFuture 对 cell 捕获变量的限制——已正确实现

**状态**：已确认正确，无需修改  
**优先级**：N/A（已完成）

### 描述

LLMFuture（dispatch-before-use 并发调度）对 cell 捕获变量的限制已通过编译期静态分析正确实现，链路完整：

1. `semantic_analyzer.py:1957-1959`：lambda 捕获变量的 UID 写入 `side_table.cell_captured_symbols`
2. `behavior_dependency_analyzer.py:109-114`：赋值目标若在 `cell_captured_symbols` 中，强制 `rhs.dispatch_eligible = False`
3. `vm_handle_IbAssign`（`handlers.py:508-510`）：运行时检查 `dispatch_eligible`，cell 变量的 behavior 赋值不走 dispatch_eager 路径

**原因**：IbCell 只能持有合法 IbObject，不能持有 LLMFuture 占位符。限制通过编译期分析实现，无运行时开销。

### 核实依据

- `core/compiler/semantic/passes/semantic_analyzer.py:1957-1959`
- `core/compiler/semantic/passes/behavior_dependency_analyzer.py:96-114`
- `core/runtime/vm/handlers.py:504-520`

---

## 参考：近期完成的主线工作（状态确认）

以下工作已核实与代码及文档完全一致：

| 里程碑 | 状态 | 核实时间 |
|--------|------|----------|
| M1 TypeRef 引入 | ✅ 完成 | 2026-05-08 |
| M2 Optional[T] | ✅ 完成 | 2026-05-08 |
| M3 TypeDef 单一化 | ✅ 完成 | 2026-05-08 |
| M4 IbValue 运行时值统一 | ✅ 完成 | 2026-05-08 |
| M5 Axiom 接口统一化 | ✅ 完成 | 2026-05-08 |
| VM CPS 重构（全 43 节点） | ✅ 完成 | 2026-05-08 |
| llmexcept 影子执行驱动模式 | ✅ 完成 | 2026-05-08 |
| cell 捕获变量 dispatch_eligible 限制 | ✅ 完成 | 2026-05-08 |
| lambda/snapshot 词法闭包语义 | ✅ 完成 | 2026-05-08 |
