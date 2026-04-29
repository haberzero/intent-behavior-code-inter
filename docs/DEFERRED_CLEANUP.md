# 延迟清理任务清单

> **建立时间**：2026-04-28  
> **更新**：2026-04-29（轻量债务清理 PR 落地：L1/L2/C1/C2/C3/C4/C10/C13 标记为 ✅ DONE；剩余条目延后到 M6 后统一处理）  
> **来源**：从 `URGENT_ISSUES.md` 转入的低优先级维护性条目 + 2026-04-28/29 文档/代码一致性审查识别的"可彻底清理的兼容性回退"  
> **属性**：以下任务均不影响正确性，目标是工程美观与可维护性  
> **触发方式**：作为下一个独立的"代码债务清理 PR"一次性处理；不混入 M3b/M5a 等主线特性 PR

> **测试基线**：本文件中所有任务必须保持 `python3 -m pytest tests/ -q` 测试基线不退化（**当前基线 949 passed**）。

---

## 一、URGENT_ISSUES 转入的维护性改善（L1–L4）

### [L1] `IbLambdaExpr.returns` 兼容字段彻底删除 ✅ DONE（2026-04-29）
**文件**：`core/kernel/ast.py`，`core/compiler/semantic/passes/semantic_analyzer.py`，`core/compiler/semantic/passes/resolver.py`  
**落地内容**：删除 `IbLambdaExpr.returns` 字段；删除 `visit_IbLambdaExpr`（Pass 3）中 `node.returns` elif 回退分支；删除 `visit_IbLambdaExpr`（Pass 2 Resolver）中 `node.returns is not None` 类型决议分支；同步更新 docstring。声明侧返回类型完全经由 `_pending_fn_return_type` 隐式通道传递；表达式侧 `lambda -> TYPE: EXPR` 在解析期产生 PAR_005（既有约束）。

---

### [L2] `get_vars()` 硬编码内置函数过滤名单 ✅ DONE（2026-04-29）
**文件**：`core/runtime/interpreter/runtime_context.py`，`core/runtime/interpreter/intrinsics/__init__.py`，`core/runtime/interfaces.py`  
**落地内容**：`RuntimeSymbolImpl` 新增 `is_builtin: bool` 字段；`Scope.define()` / `RuntimeContext.define_variable()` Protocol 与 impl 增加 `is_builtin` 参数；`IntrinsicManager.rebind()` 在注入 intrinsic 时传 `is_builtin=True`；`get_vars()` 改为按属性过滤（`if symbol.is_builtin: continue`），不再硬编码 `("len", "print", "range", "input", "get_self_source")`。

---

### [L3] `_pending_fn_return_type` 隐式上下文通道注释 ✅ DONE（2026-04-29）
**文件**：`core/compiler/semantic/passes/semantic_analyzer.py`  
**落地内容**：在 `_pending_fn_return_type` 字段声明处补充设计决策注释，明确说明：(1) 这是经过审慎选择的隐式通道（替代方案"节点字段"已在 L1 删除，"参数化访问者"会污染分发签名）；(2) 嵌套安全性由 `visit_IbAssign` 的 `try/finally save/restore` 保证。无代码改动。

---

### [L4] `_collect_free_refs` 启发式子节点遍历注释 ✅ DONE（2026-04-29）
**文件**：`core/runtime/interpreter/handlers/expr_handler.py`  
**落地内容**：在 `_collect_free_refs` 通用展开循环处补充注释，说明启发式策略（"字段值是字符串且存在于 ``node_pool``" 即视作子节点 UID）以及为什么 UID 编码（前 16 hex 字节内容哈希 + ``node_`` 前缀）下碰撞概率极低（< 2^-64）。如果未来 UID 编码改用更短或非随机的格式，需改用显式 AST 字段 schema。无代码改动。

---

## 二、兼容性回退彻底清理（2026-04-28 审查识别）

### [C1] `LLMExceptFrame._is_serializable()` 死代码删除 ✅ DONE（2026-04-29）
**文件**：`core/runtime/interpreter/llm_except_frame.py`  
**落地内容**：方法已删除；全仓库零调用点（已通过 grep 确认）。

---

### [C2] `LLMExecutor.execute_behavior_expression` 中 `captured_intents` 旧路径分支删除 ✅ DONE（2026-04-29）
**文件**：`core/runtime/interpreter/llm_executor.py`，`core/runtime/interfaces.py`，`core/runtime/objects/builtins.py`，`core/runtime/serialization/runtime_serializer.py`，`core/runtime/interpreter/interpreter.py`  
**落地内容**：删除 `IntentNode.to_list()` else 分支；改为对非 `IbIntentContext` 的 `captured_intents` 抛 `TypeError`（明确契约违反）；收紧 `IIbBehavior.captured_intents` 注解为 `Optional[Any]`（注释为 `Optional[IbIntentContext]`，保持避免循环导入的 `Any` 形态）；同步收紧 `IbBehavior.__init__`、`IbBehavior.serialize_for_debug`、`Interpreter.get_captured_intents`、`runtime_serializer` 中读取 `captured_intents` 的代码以适应 `None | IbIntentContext` 形态（之前假设可迭代）。

---

### [C3] `ScopeImpl.define()` fallback UID 路径升级为断言 ✅ DONE（2026-04-29）
**文件**：`core/runtime/interpreter/runtime_context.py`  
**落地内容**：经 `-W error::RuntimeWarning` 全套测试验证（949 passed）确认 fallback 不被合法路径触发；删除 `RuntimeWarning`；保留 `id(sym)` 派生 UID 兼容内核引导期 / 跨上下文同步路径（`RuntimeContextImpl.sync_state`、`HostService` plugin 恢复），并增加 `assert name` 防御性断言；移除现已不需要的 `import warnings`。

---

### [C4] `IbDeferred.body_uid is None` 空值兼容路径审计 ✅ DONE（2026-04-29）
**文件**：`core/runtime/objects/builtins.py`  
**审计结论**：经审查，`body_uid is None` 分支在 M1 之后理论上仅由 `stmt_handler.visit_IbAssign` 中"`is_deferred=True` 且 `value_node_type != IbBehaviorExpr`"分支构造，而 `node_is_deferred` 侧表的唯一写入点（`expression_analyzer.visit_IbBehaviorExpr`）限定写入 IbBehaviorExpr 节点；两个条件互斥，故该分支在合法编译路径下不可达。决定保留 `or self.node_uid` 作为防御性回退（不抛异常），以兼容潜在的程序化构造路径（artifact 反序列化、测试 harness 等）；在调用点添加详细审计注释固化结论。

---

### [C5] `ControlSignalException` 边界封装类删除（M3b 完成后引入）
**文件**：`core/runtime/vm/task.py::ControlSignalException`  
**当前状态**：M3b 已经把 VM 内部的控制流迁移为 `Signal(kind, value)` 数据对象；但 `ControlSignalException` 作为**边界封装**保留：
1. `VMExecutor.run()` 在顶层栈空仍持有 Signal 时包装为 CSE 抛给调用者
2. `fallback_visit()` 路径中递归解释器抛出的 `ReturnException`/`BreakException`/`ContinueException` 仍会被捕获并转 CSE 沿帧栈传播
3. 现有外部测试 `pytest.raises(ControlSignalException)` 依赖该类型

**目标**：M3d 完成（全部节点 CPS 化、`Interpreter.visit()` 主路径切换到 VMExecutor）后：
1. 删除 `fallback_visit` 中的 `ReturnException`/`BreakException`/`ContinueException` → CSE 转换路径
2. 删除 `VMExecutor.run()` 顶层 Signal → CSE 包装路径，调用方直接处理 Signal
3. 把 `ControlSignalException` 类彻底删除；`from_signal()` 也一并移除
4. 调整使用 `pytest.raises(ControlSignalException)` 的测试为检查 `Signal` 数据对象

**风险**：M3d 之前删除会破坏现有 `IbCall` / `IbFunctionDef` 的 RETURN 语义，因为这两个节点尚未 CPS 化。

---

## 三、M3d 完成后新增的 VM 路径历史包袱（2026-04-29 审查识别）

> 以下条目通过 M3d+M5c 代码审查（2026-04-29）识别。M3d 已将主路径切换到 VMExecutor，
> 但部分"需要递归 fallback"的妥协与"编译器设计不当导致的运行时工作区"仍然残留。
> **必须在 VM 改造全部完成前清零，否则旧包袱会永久内嵌于运行时**。

---

### [C6] CSE-Exception 双层桥彻底消除（C5 的细化追踪）

**文件**：
- `core/runtime/interpreter/interpreter.py:execute_module()` L591–L600（CSE → ReturnException/BreakException/ContinueException 还原桥）
- `core/runtime/objects/kernel.py:IbUserFunction.call()` L851–L858（同上）
- `core/runtime/vm/handlers.py:vm_handle_IbTry` L1301–L1303（`except (ReturnException, BreakException, ContinueException): raise` 透传桥）
- `core/runtime/vm/handlers.py:vm_handle_IbCall` L260–L261（`except ControlSignalException: raise` 透传桥）
- `core/runtime/vm/handlers.py` 顶部 imports（仍引入 `ReturnException/BreakException/ContinueException`）

**问题**：M3d 已通过 VMExecutor 完全驱动函数体，内部 `return` 语句产生 `Signal(RETURN, value)`，经由 `ControlSignalException.from_signal()` 包装后抛给 `execute_module` / `IbUserFunction.call`，再转回 `ReturnException`，最后在 `IbUserFunction.call()` 外层 `except ReturnException` 消费。这是一个三层翻译：`Signal → CSE → ReturnException → return value`。完全可以直接捕获 `Signal`。

**目标**：
1. `IbUserFunction.call()` 捕获 `ControlSignalException`，若 `kind==RETURN` 直接返回 `cse.value`，删除 CSE→ReturnException→except 三层转换
2. `execute_module()` 同理：直接捕获 CSE，`kind==RETURN/BREAK/CONTINUE` 分别处理，删除转换桥
3. `vm_handle_IbTry` 的 `except (ReturnException, BreakException, ContinueException): raise` 在 fallback 路径完全消除后删除
4. `vm_handle_IbCall` 的 `except ControlSignalException: raise` 也只在 fallback 中有意义；fallback 消除后删除
5. 最终目标与 C5 对齐：`ControlSignalException` 在整个代码库只剩顶层边界一个产生点和一个消费点，之后可整体删除

**前提**：C6 = C5 的细化；在 C5 完成时一并处理。

---

### [C7] `VMExecutor.assign_to_target()` 穿透到 `StmtHandler._assign_to_target()` 重写

**文件**：
- `core/runtime/vm/vm_executor.py:VMExecutor.assign_to_target()` L107–L122
- `core/runtime/vm/handlers.py:vm_handle_IbAssign` / `vm_handle_IbFor` / `vm_handle_IbAugAssign` 等中的 `executor.assign_to_target()` 调用

**问题**：凡是遇到非简单 IbName 的赋值目标（`IbAttribute`、`IbSubscript`、`IbTuple` 解包），CPS handler 都委托给 `executor.assign_to_target()`，其内部通过 `interpreter.stmt_handler._assign_to_target()` 调用，后者对 attribute/subscript 使用 `self.visit(...)` **重新进入递归解释器**。这意味着：

```python
obj.x = value       # IbAttribute 目标 → 递归调用 visit(obj_uid)
items[0] = value    # IbSubscript 目标 → 递归调用 visit(obj_uid) + visit(slice_uid)
a, b = pair         # IbTuple 解包 → 递归 visit
```

表达式已通过 CPS 求值，写回却回退递归——双层路径混用。

**目标**：
1. 把 `_assign_to_target` 中的 `IbAttribute`/`IbSubscript`/`IbTuple` 分支重写为 CPS 友好形式：由调用方提供已求值的 `obj`（通过 `yield`），handler 只做 `receive` 调用，不再通过 `visit()` 二次求值
2. 具体地，把 `vm_handle_IbAssign` 中对复杂目标的处理从"委托给 `assign_to_target()`"升级为在 handler 内部 `yield` 目标表达式并自己完成写回
3. 最终可以删除 `VMExecutor.assign_to_target()` 以及对 `interpreter.stmt_handler` 的反向耦合

**注意**：`IbAugAssign` 中对 `IbAttribute` 的读-修改-写已有 CPS 实现（`old_val = yield target_uid` + `obj.receive("__setattr__", ...)`），可作为样本。

---

### [C8] `vm_handle_IbLambdaExpr` 与 `vm_handle_IbBehaviorInstance` 的全量 fallback 消除

**文件**：`core/runtime/vm/handlers.py:vm_handle_IbLambdaExpr` L1102–L1111、`vm_handle_IbBehaviorInstance` L1091–L1099

**问题**：这两个 handler 目前是 "CPS 注册壳 + 立即 fallback"，实际执行路径与没有 CPS handler 完全相同：

```python
def vm_handle_IbLambdaExpr(executor, node_uid, node_data):
    if False: yield
    return executor.fallback_visit(node_uid)  # ← 完全递归

def vm_handle_IbBehaviorInstance(executor, node_uid, node_data):
    if False: yield
    return executor.fallback_visit(node_uid)  # ← 完全递归
```

根本原因：
- `IbLambdaExpr`：自由变量分析 + IbCell 提升逻辑全部在 `ExprHandler.visit_IbLambdaExpr` 的递归路径中，且 lambda body 在调用时才执行。CPS 化需要把自由变量扫描拆分为编译期侧表（`free_vars` 侧表），运行时只做 `IbCell` 分配与 `IbDeferred` 构造。
- `IbBehaviorInstance`：`segments` 由 `LLMExecutor._evaluate_segments()` 递归求值，未暴露为单独 UID 供 CPS yield。

**目标**：
1. **`IbLambdaExpr`**：在语义分析阶段生成 `free_vars` 侧表（变量 UID 列表），运行时 handler 只需根据侧表分配 IbCell + 构造 IbDeferred，不再遍历 AST；删除 fallback，handler 升级为真正 CPS。
2. **`IbBehaviorInstance`**：把 `_evaluate_segments()` 的子节点 UID 提升为 `IbBehaviorInstance` 节点的 `segment_uids` 字段，运行时 handler 逐一 `yield` 各段求值，再把结果传入同步的 LLM 调用；删除 fallback。
3. 这两项都需要**编译器改动**（语义分析 pass 或序列化字段扩展），属于"编译器设计欠债导致运行时无法简化"的典型案例。

---

### [C9] `vm_handle_IbImport/IbImportFrom` fallback 升级为真正 CPS

**文件**：`core/runtime/vm/handlers.py:vm_handle_IbImport` L806–L813、`vm_handle_IbImportFrom` L816–L821

**问题**：两个 handler 目前是"注册壳 + 完全 fallback"，不比直接从 dispatch 表移除有任何 CPS 价值：

```python
def vm_handle_IbImport(executor, node_uid, node_data):
    if False: yield
    return executor.fallback_visit(node_uid)
```

根本原因：`ModuleManager.import_module()` 本身是同步调用，理论上不需要 yield；但 `ImportHandler.visit_IbImport` 内部调用了 `self.execution_context.visit()` 来处理 `as` 别名、`__init__` 模块初始化等，这些调用目前还是递归的。

**目标**：
1. 把 `ImportHandler.visit_IbImport()` 的逻辑剥离为不依赖递归 visit 的纯函数，直接操作 `module_manager` + `runtime_context.define_variable()`；
2. `vm_handle_IbImport` 改为内联这段逻辑；删除 fallback；
3. 使 import 语句在 VM 执行统计（`step_count`）和调度追踪中可见。

---

### [C10] `execute_module()` 和 `IbUserFunction.call()` 中重复的 `IbLLMExceptionalStmt` 跳过逻辑 ✅ DONE（2026-04-29）

**文件**：
- `core/runtime/vm/vm_executor.py`（新增 `VMExecutor.run_body()` 共享实现）
- `core/runtime/interpreter/interpreter.py:execute_module()`
- `core/runtime/objects/kernel.py:IbUserFunction.call()`

**落地内容**：新增 `VMExecutor.run_body(stmt_uids)` 方法，统一封装 (1) `IbLLMExceptionalStmt` 直接子节点跳过、(2) `node_protection` 重定向（由 `run()` 入口承担）、(3) `Signal → ReturnException/BreakException/ContinueException` 的边界恢复。`execute_module()` 与 `IbUserFunction.call()` 的内联 body 循环现在共用一行 `vm.run_body(body)`。注：本次未把 body 循环移入 `IbModule` / `IbFunctionDef` handler 内部（C10 描述中的方案 1/2），因 `IbUserFunction.call()` 同时需要参数绑定与作用域 push/pop 的精细控制——共享 `run_body` 是更安全的渐进式重构。修复了原 `IbUserFunction.call()` 中 `cse.kind` 的 dormant 错误（属性名应为 `cse.signal`），由此首次让函数体真正经由 VM 路径执行（之前 `getattr(self.context, "vm_executor", None)` 永远是 None，函数体走的是递归 fallback）。

---

### [C11] `node_protection` 侧表驱动的保护机制重定向设计改造

**文件**：
- `core/runtime/vm/vm_executor.py:_apply_protection_redirect()` L239–L262
- `core/compiler/semantic/passes/semantic_analyzer.py:_bind_llm_except`（生产方）
- `core/runtime/interpreter/interpreter.py:visit()` L804–L810（旧递归消费方）

**问题**：`node_protection` 侧表是为旧递归解释器设计的——`visit()` 每次调用时检查侧表，若存在则跳转到 handler_uid。这个设计的缺陷：

1. **无状态**：侧表只知道"目标 → handler"的映射，不知道"是否已在被保护中"，导致 VM 必须额外维护 `LLMExceptFrame.target_uid` 反查来避免无限重定向。
2. **散射**：每一个处理调度节点（容器 handler 的 `_resolve_stmt_uid`、`execute_module` body 循环、`IbUserFunction.call` body 循环、`VMExecutor._apply_protection_redirect`）都必须各自实现一遍保护过滤，否则 `IbLLMExceptionalStmt` 会被重复执行或被意外跳过。
3. **条件驱动 for 循环的特殊化**：`for @~...~:` 的 `node_protection` 挂在 `IbBehaviorExpr`（iter 内部子节点）而非 `IbFor` 本身，导致 `_apply_protection_redirect` 必须在每次 `yield child_uid` 时都执行（不只是根节点），增加了每个调度步骤的开销。

**目标**：
1. 在编译器中把 `IbLLMExceptionalStmt` 节点设计为对其 `target` 的**显式包装**（类似 `IbIf` 包含 `body`）：handler_node 直接包含 target_uid，不再依赖侧表间接关联
2. 在 AST 层面，`IbLLMExceptionalStmt` 节点在其所在 body 中**替换**原 target_uid 而不是**紧随**其后——消除"body 中同时有 target 和 handler，容器需过滤其一"的问题
3. 相应地，编译器 body 序列化时只写入 handler_uid（不写入裸 target_uid），运行时容器 handler 只需正常遍历 body，不需要 `_resolve_stmt_uid` 过滤；handler 本身 yield 其包含的 target
4. `_apply_protection_redirect()` 和 `bypass_protection` 参数可以完全删除
5. **高优先级**：这项改动触及编译器 + 序列化 + 运行时三层，建议作为单独的"重构 PR"执行

---

### [C12] `_assign_future_to_name_target()` 直接操作 `ScopeImpl` 私有属性

**文件**：`core/runtime/vm/handlers.py:_assign_future_to_name_target()` L541–L596

**问题**：M5c 的 dispatch-before-use 路径必须绕过 `ScopeImpl.define/assign` 的类型检查，直接把非 `IbObject` 的 `LLMFuture` 写入符号表。当前实现直接操作：

```python
target_scope._symbols[name] = new_sym      # 私有字段
target_scope._uid_to_symbol[sym_uid] = new_sym  # 私有字段
sym.value = future           # 绕过 _check_type
sym.current_type = type(future)  # 写入非 IbObject 的类型
```

根本原因：`RuntimeContext` / `ScopeImpl` 接口的 `define_variable` / `set_variable_by_uid` 假定传入值是合法的 `IbObject`，没有"跳过类型检查的低级写入"操作。

**目标**：
1. 在 `ScopeImpl` / `RuntimeContext` 接口中增加 `define_raw(name, value, uid)` 方法（或 `define_variable(..., skip_type_check=True)`），供 VM 特殊路径使用
2. `_assign_future_to_name_target` 改用该方法，不再直接操作 `_symbols` / `_uid_to_symbol` 私有字段
3. 对 `_cell_map` 私有属性的 `hasattr` 探测（`_target_is_promoted_cell()`）同理：在 `ScopeImpl` 上增加 `is_cell_promoted(sym_uid: str) -> bool` 方法，把私有知识封装在 scope 内部

---

### [C13] `IbUserFunction.call()` 通过多级 `getattr` 脆弱查找 VMExecutor ✅ DONE（2026-04-29）

**文件**：`core/runtime/objects/kernel.py:IbUserFunction.call()`、`core/runtime/interpreter/execution_context.py`、`core/runtime/interpreter/interpreter.py`

**落地内容**：在 `ExecutionContextImpl` 上新增 `vm_executor` 属性 + setter（默认 `None`，由 Interpreter 注入）；`Interpreter._get_vm_executor()` 在首次构造 VMExecutor 时立即把引用写入 `self._execution_context.vm_executor`。`IbUserFunction.call()` 改为直接读取 `self.context.vm_executor` 并通过 `vm.run_body(body)` 驱动函数体；不再通过 `getattr(self.context, "vm_executor", None) → getattr(self.context, "_interpreter", None) → interp._get_vm_executor()` 三级穿透查找。审计中发现：原三级查找链在合法运行时永远走不到 VMExecutor 路径（ExecutionContextImpl 既无 `vm_executor` 也无 `_interpreter`），函数体始终走的是 `self.context.visit(stmt_uid)` 递归 fallback；C13 的修复让函数体首次真正经由 VM 路径执行，这正是 M4 多 Interpreter 并发所需要的"无 silent fallback"前提。

---

### [C14] `BehaviorDependencyAnalyzer` 不感知 IbCell 提升导致运行时扫描

**文件**：`core/runtime/vm/handlers.py:_target_is_promoted_cell()` L511–L538

**问题**：M5c 的 dispatch 决策必须在运行时通过 `hasattr(scope, "_cell_map")` 私有探测判断变量是否被 lambda 捕获。根本原因：`BehaviorDependencyAnalyzer`（M5a）在 Pass 5 中只做数据依赖图分析，不感知 Pass 4 中 lambda 捕获分析产生的 IbCell 提升信息。

**目标**：
1. 在语义分析 Pass 4（lambda 捕获分析）完成后，把"被提升为 IbCell 的符号 UID"列表写入侧表 `cell_captured_symbols: Set[str]`
2. Pass 5（`BehaviorDependencyAnalyzer`）利用该侧表：若 `IbBehaviorExpr` 的 target 符号 UID 在 `cell_captured_symbols` 中，则强制 `dispatch_eligible = False`
3. 运行时 `_target_is_promoted_cell()` 可以改为简单侧表查询，删除作用域链扫描与私有属性探测

---

## 四、PR 操作建议

1. **第一阶段：轻量债务清理 PR（L1-L4 + C1-C4 + C10 + C13）** ✅ DONE（2026-04-29）— 详见上面各条 ✅ 标记。基线 949 → 949（0 退化）。
2. **暂缓**：C5、C6、C7、C8、C9、C11、C12、C14——其中 C5/C6 等待 M3d 完整切换、ControlSignalException 被彻底移除后处理；C7/C8/C11/C14 需要编译器改动或较大重构，按计划在 M6 后统一处理。
3. **分阶段验证**：每完成一个条目立即跑 `python3 -m pytest tests/ -q --tb=short` 确认 0 退化。
4. **测试基线**：M3d+M5c+轻量清理后基线 **949**。
5. **参考资料**：`URGENT_ISSUES.md`（修复历史归档）、`docs/COMPLETED.md`（每条变更对应的章节）。

---

## 五、本文件维护

* 完成某条目后，把对应小节标记为 `✅ DONE — YYYY-MM-DD` 并简述实际改动。
* 若执行过程中识别新的可清理回退，追加到第三节末尾并编号 C15/C16/...
* 若某条目执行过程中暴露出更深的设计问题（应转为高优 issue），把它升级到 `URGENT_ISSUES.md` 而非留在本文件。

