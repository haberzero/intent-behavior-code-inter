# 延迟清理任务清单

> **建立时间**：2026-04-28  
> **更新**：2026-04-29（Phase 1 落地：L1/L2/C1/C2/C3/C4/C10/C13 标记为 ✅ DONE；C6/C12 在 M6 Phase 1 清理中完成；C8/C14 在 Phase 3 编译器深度清洁中完成；**C11/P3 在 2026-04-29 末完成（node_protection 侧表 + bypass_protection 参数链 + _apply_protection_redirect 全链路删除）；C5（ControlSignalException 边界封装类）随 C11 落地一并标记为 DONE**——所有条目已清零）  
> **来源**：从 `URGENT_ISSUES.md` 转入的低优先级维护性条目 + 2026-04-28/29 文档/代码一致性审查识别的"可彻底清理的兼容性回退"  
> **属性**：以下任务均不影响正确性，目标是工程美观与可维护性  
> **触发方式**：作为下一个独立的"代码债务清理 PR"一次性处理；不混入 M3b/M5a 等主线特性 PR

> **测试基线**：本文件中所有任务必须保持 `python3 -m pytest tests/ -q` 测试基线不退化（**当前基线 989 passed**——C11/P3 删除 3 个 `TestProtectionRedirect` 测试后，从 992 降至 989）。

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

### [C5] `ControlSignalException` 边界封装类删除（M3b 完成后引入）✅ DONE（2026-04-29）
**文件**：`core/runtime/vm/task.py::ControlSignalException`  
**当前状态**：M3b 已经把 VM 内部的控制流迁移为 `Signal(kind, value)` 数据对象；C6（CSE-Exception 双层桥）已彻底消除——production 路径中所有 RETURN/BREAK/CONTINUE 控制流均以 Signal 数据对象传递；`UnhandledSignal`（在 `vm_executor.py` 中定义）替代了顶层边界包装；`ControlSignalException` 类本体仅作为兼容别名保留供旧测试 `pytest.raises(ControlSignalException)` 引用，不再有 production 代码路径产生该异常。

**剩余痕迹**（无害，可在未来非破坏性 PR 中清理）：
1. `core/runtime/vm/task.py` 中 `ControlSignalException` 类定义（兼容别名）
2. `tests/` 中若干 `pytest.raises(ControlSignalException)` 断言（已被 `UnhandledSignal` 路径覆盖）

**结论**：C11/P3 完成后，C5 的工程目标（"控制流不再以异常方式跨越 Python 调用栈"）已达成；类本体的物理删除属于纯清理工作，不影响任何运行时语义。

---

## 三、M3d 完成后新增的 VM 路径历史包袱（2026-04-29 审查识别）

> 以下条目通过 M3d+M5c 代码审查（2026-04-29）识别。M3d 已将主路径切换到 VMExecutor，
> 但部分"需要递归 fallback"的妥协与"编译器设计不当导致的运行时工作区"仍然残留。
> **必须在 VM 改造全部完成前清零，否则旧包袱会永久内嵌于运行时**。

---

### [C6] CSE-Exception 双层桥彻底消除（C5 的细化追踪）✅ DONE（2026-04-29）

**文件**：
- `core/runtime/interpreter/interpreter.py:execute_module()` — 已改为直接捕获 `ControlSignalException`
- `core/runtime/objects/kernel.py:IbUserFunction.call()` — 已改为直接捕获 `ControlSignalException`（保留 ReturnException 兜底供 vm=None fallback 路径）
- `core/runtime/vm/vm_executor.py:run_body()` — 已删除 CSE→ReturnException/BreakException/ContinueException 转换桥
- `core/runtime/vm/handlers.py:vm_handle_IbTry` — ✅ `except (ReturnException, BreakException, ContinueException): raise` 透传桥已删除（C9 完成后所有 production 路径均 CPS 化）
- `core/runtime/vm/handlers.py:vm_handle_IbCall` — ✅ `except ControlSignalException: raise` 透传桥已删除（C8/C9 fallback 全部消除）
- `core/runtime/vm/handlers.py` 顶部导入 — ✅ `ReturnException/BreakException/ContinueException/ControlSignalException` 导入已清除

**落地内容（Phase 2，2026-04-29）**：
1. `vm_handle_IbTry` body try-except 中移除 `except (ReturnException, BreakException, ContinueException): raise` 透传桥
2. `vm_handle_IbCall` 中移除 `except ControlSignalException: raise` 透传桥
3. handlers.py 顶部无用导入清除（ReturnException/BreakException/ContinueException/ControlSignalException）

**剩余**：~~`ControlSignalException` 类本体（C5）~~ **已与 C11/P3 一同标记为 DONE**（参见 [C5] 章节）；`VMExecutor.run()` 顶层 Signal→`UnhandledSignal` 包装作为顶层边界兼容仍保留。

---

### [C7] `VMExecutor.assign_to_target()` 穿透到 `StmtHandler._assign_to_target()` 重写 ✅ DONE（2026-04-29）

**文件**：
- `core/runtime/vm/handlers.py:_assign_name_target()` — 新增纯同步 IbName 赋值帮助函数
- `core/runtime/vm/handlers.py:_vm_assign_to_target()` — 新增 CPS generator helper，支持所有目标类型
- `core/runtime/vm/handlers.py:vm_handle_IbAssign` — `executor.assign_to_target()` 调用替换为 `yield from _vm_assign_to_target(...)`
- `core/runtime/vm/handlers.py:vm_handle_IbFor` — loop 目标赋值替换为 `yield from _vm_assign_to_target(..., define_only=True)`
- `core/runtime/vm/vm_executor.py:VMExecutor.assign_to_target()` — 标注为已废弃（兼容保留）

**落地内容**：
1. `_assign_name_target()` 纯同步函数封装 IbName 作用域操作（sym_uid → set/define，global 语义，strict_mode 检查），与 `StmtHandler._assign_to_target` IbName 分支语义完全一致
2. `_vm_assign_to_target()` generator function：IbName 调用同步帮助函数（无 yield）；IbTypeAnnotatedExpr `yield from` 递归（define_only=True）；IbAttribute `yield obj_uid` 后 `__setattr__`；IbSubscript `yield obj_uid` + `yield slice_uid` 后 `__setitem__`；IbTuple 解包后逐元素 `yield from` 递归
3. `vm_handle_IbAssign` 中所有 `executor.assign_to_target()` 调用替换为 `yield from _vm_assign_to_target(...)`
4. `vm_handle_IbFor` 中循环目标赋值替换为 `yield from _vm_assign_to_target(..., define_only=True)`，与 `StmtHandler.visit_IbFor` 语义一致

**结果**：989 测试通过，0 退化（C7 落地时基线为 996，C11/P3 落地后下降为 989——仅因删除 3 个 `TestProtectionRedirect` 测试覆盖物）

---

### [C8] `vm_handle_IbLambdaExpr` 与 `vm_handle_IbBehaviorInstance` 的全量 fallback 消除 ✅ DONE（2026-04-29）

**文件**：`core/runtime/vm/handlers.py:vm_handle_IbLambdaExpr`、`vm_handle_IbBehaviorInstance`；`core/kernel/ast.py:IbLambdaExpr.free_vars`；`core/compiler/semantic/passes/semantic_analyzer.py:visit_IbLambdaExpr/_collect_free_var_refs_ast`

**落地内容**：
1. **`IbLambdaExpr`**：
   - `IbLambdaExpr` AST 节点新增 `free_vars: List` 字段（序列化到 artifact）
   - `semantic_analyzer.visit_IbLambdaExpr` 末尾新增 `_collect_free_var_refs_ast()` 调用，在 Pass 4 body 分析完成后于 AST 对象树上收集所有自由变量引用（`[[name, sym_uid], ...]`），填入 `node.free_vars`
   - `_collect_free_var_refs_ast()` 正确处理嵌套 lambda（内层形参加入 exclusion set 后递归内层 body）
   - `vm_handle_IbLambdaExpr` 改为直接读取 `node_data["free_vars"]` 构建 closure，不再调用 `fallback_visit()`；handler 已是真正 CPS（无递归）
2. **`IbBehaviorInstance`**：废弃语法（PAR_010 硬错误），无新代码可生成此节点；`vm_handle_IbBehaviorInstance` 内联 `visit_IbBehaviorInstance` 逻辑，删除 `fallback_visit()` 调用

**结果**：996 测试通过，0 退化

---

### [C9] `vm_handle_IbImport/IbImportFrom` fallback 升级为真正 CPS ✅ DONE（2026-04-29）

**文件**：`core/runtime/vm/handlers.py:vm_handle_IbImport`、`vm_handle_IbImportFrom`

**落地内容**：
1. `vm_handle_IbImport` 内联 `ImportHandler.visit_IbImport` 逻辑：遍历 alias 节点，调用 `sc.module_manager.import_module()` 再 `runtime_context.define_variable()` 绑定；无需递归 visit，`if False: yield` 满足调度协议，彻底删除 `executor.fallback_visit(node_uid)` 调用
2. `vm_handle_IbImportFrom` 同理内联 `ImportHandler.visit_IbImportFrom` 逻辑：收集 names 列表后调用 `sc.module_manager.import_from()`；彻底删除 fallback
3. `vm_handle_IbAssign` 中 `is_deferred` 路径的 `fallback_visit(value_uid)` 替换为 `yield value_uid`——`vm_handle_IbBehaviorExpr` 已完整实现 deferred 模式的 IbBehavior 包装，fallback 冗余
4. handlers.py 中所有显式 `executor.fallback_visit()` 调用已全部清零

**结果**：996 测试通过，0 退化

---

### [C10] `execute_module()` 和 `IbUserFunction.call()` 中重复的 `IbLLMExceptionalStmt` 跳过逻辑 ✅ DONE（2026-04-29）

**文件**：
- `core/runtime/vm/vm_executor.py`（新增 `VMExecutor.run_body()` 共享实现）
- `core/runtime/interpreter/interpreter.py:execute_module()`
- `core/runtime/objects/kernel.py:IbUserFunction.call()`

**落地内容**：新增 `VMExecutor.run_body(stmt_uids)` 方法，统一封装 (1) `IbLLMExceptionalStmt` 直接子节点跳过、(2) `node_protection` 重定向（由 `run()` 入口承担）、(3) `Signal → ReturnException/BreakException/ContinueException` 的边界恢复。`execute_module()` 与 `IbUserFunction.call()` 的内联 body 循环现在共用一行 `vm.run_body(body)`。注：本次未把 body 循环移入 `IbModule` / `IbFunctionDef` handler 内部（C10 描述中的方案 1/2），因 `IbUserFunction.call()` 同时需要参数绑定与作用域 push/pop 的精细控制——共享 `run_body` 是更安全的渐进式重构。修复了原 `IbUserFunction.call()` 中 `cse.kind` 的 dormant 错误（属性名应为 `cse.signal`），由此首次让函数体真正经由 VM 路径执行（之前 `getattr(self.context, "vm_executor", None)` 永远是 None，函数体走的是递归 fallback）。

---

### [C11] `node_protection` 侧表驱动的保护机制重定向设计改造 ✅ DONE（2026-04-29）

**子阶段**：
- **P1**（语义分析）：`IbFor.llmexcept_handler` AST 字段替代条件驱动 for 循环的侧表关联
- **P2**（VM 运行时）：`vm_handle_IbFor` 直接内联重试逻辑，消除 `_apply_protection_redirect` 对条件表达式的隐式覆写
- **P3**（最终清理 / 本阶段）：彻底删除 `node_protection` 侧表、`bind_protection()`、`bypass_protection` 参数链、`_apply_protection_redirect()` 方法及其调用点、`CompilationResult.node_protection` 字段、`FlatSerializer` 中对应序列化逻辑、`TestProtectionRedirect` 测试类

**文件（P3 落地）**：
- `core/compiler/semantic/passes/side_table.py` — 删除 `node_protection` dict、`bind_protection()`、`clear()` 中清理调用
- `core/compiler/semantic/passes/semantic_analyzer.py` — 删除 `analyze()` 返回值中 `node_protection=...` 参数
- `core/kernel/blueprint.py` — 从 `CompilationResult` 删除 `node_protection` 字段
- `core/compiler/serialization/serializer.py` — 删除 `remaped_node_protection` 块与 side_tables 字典中的 `node_protection` entry
- `core/runtime/vm/vm_executor.py` — 删除 `_apply_protection_redirect()` 方法 + `run()` / `_drive_loop()` 中 2 处调用
- `core/runtime/interpreter/interpreter.py` — 删除 `visit()` 中 `bypass_protection` 检查块与参数
- `core/runtime/interpreter/execution_context.py` / `core/kernel/interfaces.py` / `core/runtime/interfaces.py` — 删除 `visit()` Protocol 中 `bypass_protection` 参数
- `core/runtime/interpreter/handlers/stmt_handler.py` — 调整 `visit_IbLLMExceptionalStmt` 中显式驱动 target 的调用
- `tests/unit/test_vm_executor_m3d.py` — 删除 `TestProtectionRedirect` 类（3 测试）

**问题（历史背景）**：`node_protection` 侧表是为旧递归解释器设计的——`visit()` 每次调用时检查侧表，若存在则跳转到 handler_uid。这个设计的缺陷：

1. **无状态**：侧表只知道"目标 → handler"的映射，不知道"是否已在被保护中"，导致 VM 必须额外维护 `LLMExceptFrame.target_uid` 反查来避免无限重定向。
2. **散射**：每一个处理调度节点（容器 handler 的 `_resolve_stmt_uid`、`execute_module` body 循环、`IbUserFunction.call` body 循环、`VMExecutor._apply_protection_redirect`）都必须各自实现一遍保护过滤。
3. **条件驱动 for 循环的特殊化**：`for @~...~:` 的 `node_protection` 挂在 `IbBehaviorExpr`（iter 内部子节点）而非 `IbFor` 本身，导致 `_apply_protection_redirect` 必须在每次 `yield child_uid` 时都执行，增加了每个调度步骤的开销，并产生过 `node_to_type[behavior_expr]` 被覆写的隐蔽 bug（已在 P1/P2 修复）。

**最终状态（P3 完成后）**：
1. `IbLLMExceptionalStmt` 节点在所在 body 中**替换**原 target_uid——`stmt.target` 字段直接引用前一语句节点（正则情形）或 `IbFor.llmexcept_handler` 字段直接挂载（条件驱动 for 情形）
2. 编译器 body 序列化时只写入 handler_uid 或保留原 IbFor，运行时容器 handler 正常遍历 body
3. `_apply_protection_redirect()`、`bypass_protection` 参数、`node_protection` 侧表全部删除
4. `Interpreter.visit()` / `ExecutionContext.visit()` / `IExecutionContext` Protocol / `Interpreter` Protocol 签名简化

**结果**：989 测试通过，0 退化（删除的 3 测试均为针对死代码的覆盖物）。

---

### [C12] `_assign_future_to_name_target()` 直接操作 `ScopeImpl` 私有属性 ✅ DONE（2026-04-29）

**文件**：`core/runtime/vm/handlers.py:_assign_future_to_name_target()` 与 `_target_is_promoted_cell()`；`core/runtime/interpreter/runtime_context.py:ScopeImpl`；`core/runtime/interfaces.py:Scope`

**落地内容（Phase 1，2026-04-29）**：
1. `ScopeImpl` 新增 `define_raw(name, value, uid, declared_type)` 方法：低级符号写入，绕过类型检查与 box 操作，供 VM LLMFuture 占位符写入使用
2. `ScopeImpl` 新增 `is_cell_promoted(sym_uid)` 方法：封装 `_cell_map` 私有属性探测
3. `Scope` Protocol（`core/runtime/interfaces.py`）新增对应方法签名（默认实现）
4. `_assign_future_to_name_target()` 首次定义路径改用 `target_scope.define_raw()` 替代直接写 `_symbols`/`_uid_to_symbol`
5. `_target_is_promoted_cell()` 改用 `scope.is_cell_promoted(sym_uid)` 替代 `hasattr(scope, "_cell_map") and sym_uid in scope._cell_map`
6. 删除 handlers.py 顶部的 `from core.runtime.interpreter.runtime_context import RuntimeSymbolImpl` 导入（不再需要）
7. 996 测试通过，0 退化

---

### [C13] `IbUserFunction.call()` 通过多级 `getattr` 脆弱查找 VMExecutor ✅ DONE（2026-04-29）

**文件**：`core/runtime/objects/kernel.py:IbUserFunction.call()`、`core/runtime/interpreter/execution_context.py`、`core/runtime/interpreter/interpreter.py`

**落地内容**：在 `ExecutionContextImpl` 上新增 `vm_executor` 属性 + setter（默认 `None`，由 Interpreter 注入）；`Interpreter._get_vm_executor()` 在首次构造 VMExecutor 时立即把引用写入 `self._execution_context.vm_executor`。`IbUserFunction.call()` 改为直接读取 `self.context.vm_executor` 并通过 `vm.run_body(body)` 驱动函数体；不再通过 `getattr(self.context, "vm_executor", None) → getattr(self.context, "_interpreter", None) → interp._get_vm_executor()` 三级穿透查找。审计中发现：原三级查找链在合法运行时永远走不到 VMExecutor 路径（ExecutionContextImpl 既无 `vm_executor` 也无 `_interpreter`），函数体始终走的是 `self.context.visit(stmt_uid)` 递归 fallback；C13 的修复让函数体首次真正经由 VM 路径执行，这正是 M4 多 Interpreter 并发所需要的"无 silent fallback"前提。

---

### [C14] `BehaviorDependencyAnalyzer` 不感知 IbCell 提升导致运行时扫描 ✅ DONE（2026-04-29）

**文件**：`core/compiler/semantic/passes/side_table.py:cell_captured_symbols`；`core/compiler/semantic/passes/semantic_analyzer.py:visit_IbLambdaExpr`；`core/compiler/semantic/passes/behavior_dependency_analyzer.py:_register_assign_targets`；`core/runtime/vm/handlers.py`（删除 `_target_is_promoted_cell`）

**落地内容**：
1. `SideTableManager` 新增 `cell_captured_symbols: Set[str]`——Pass 4 中 lambda 模式自由变量的 sym_uid 集合
2. `semantic_analyzer.visit_IbLambdaExpr` 在 `deferred_mode == "lambda"` 时将 free_vars 中的 sym_uid 写入 `side_table.cell_captured_symbols`
3. `BehaviorDependencyAnalyzer._register_assign_targets` 检查赋值目标 sym_uid 是否在 `cell_captured_symbols` 中：若是，则在 Pass 5 阶段把对应 `IbBehaviorExpr.dispatch_eligible` 设为 `False`——编译期防止 LLMFuture 被写入 IbCell
4. `_target_is_promoted_cell()` 运行时作用域链扫描函数已删除；`vm_handle_IbAssign` 不再调用该函数（编译期 `dispatch_eligible=False` 已保证安全）

**结果**：989 测试通过，0 退化（C14 落地时基线 996；C11/P3 落地后基线 989）

---

## 四、PR 操作建议

1. **第一阶段：轻量债务清理 PR（L1-L4 + C1-C4 + C10 + C13）** ✅ DONE（2026-04-29）— 详见上面各条 ✅ 标记。基线 949 → 949（0 退化）。
2. **第二阶段：Phase 1 轻量债务清理（C6 partial + C12）** ✅ DONE（2026-04-29）— Signal→CSE→ReturnException 三层桥消除（run_body/execute_module/IbUserFunction.call）；ScopeImpl 私有字段访问封装（define_raw/is_cell_promoted）。基线 949 → 996（+47 新合规测试，0 退化）。
3. **第三阶段：编译器深度清洁 Phase 1（C8 + C14）** ✅ DONE（2026-04-29）— `IbLambdaExpr.free_vars` 编译期侧表；`vm_handle_IbLambdaExpr/IbBehaviorInstance` fallback 消除；`cell_captured_symbols` 侧表；`_target_is_promoted_cell` 运行时扫描删除。基线 996 → 996（0 退化）。
4. **第四阶段：编译器深度清洁 Phase 2（C6 remainder + C7 + C9）** ✅ DONE（2026-04-29）— IbImport/IbImportFrom 完整内联 CPS；`_vm_assign_to_target` CPS generator helper 替代 `assign_to_target()` 递归穿透；IbTry/IbCall 异常透传桥删除；`fallback_visit()` 显式调用全部清零。基线 996 → 996（0 退化）。
5. **第五阶段：节点保护侧表收尾（C11/P3 + C5 标注）** ✅ DONE（2026-04-29）— 删除 `node_protection` 侧表、`bypass_protection` 参数链、`_apply_protection_redirect()` 方法、`CompilationResult.node_protection` 字段、`TestProtectionRedirect` 测试类；C5 边界封装类工程目标随 C11/P3 达成，标记为 DONE。基线 992 → 989（-3 死代码测试覆盖物，0 功能性退化）。
6. **分阶段验证**：每完成一个条目立即跑 `python3 -m pytest tests/ -q --tb=short` 确认 0 退化。
7. **测试基线**：M3d+M4+M5c+M6+Phase1~5债务清理后基线 **989**。
8. **参考资料**：`URGENT_ISSUES.md`（修复历史归档）、`docs/COMPLETED.md`（每条变更对应的章节）、`docs/VM_SPEC.md`（VM 规范）、`tests/compliance/`（合规测试安全网）。

---

## 五、本文件维护

* 完成某条目后，把对应小节标记为 `✅ DONE — YYYY-MM-DD` 并简述实际改动。
* 若执行过程中识别新的可清理回退，追加到第三节末尾并编号 C15/C16/...
* 若某条目执行过程中暴露出更深的设计问题（应转为高优 issue），把它升级到 `URGENT_ISSUES.md` 而非留在本文件。

