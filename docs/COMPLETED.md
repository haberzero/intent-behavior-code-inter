# COMPLETED — 极简时间线归档

> 本文档以**极简时间线**记录主线工作的完成节点。
> 设计与实现细节见对应正式文档：`docs/TYPE_SYSTEM_DESIGN.md`、`docs/VM_AND_INTERPRETER_DESIGN.md`、`docs/VM_SPEC.md`、`docs/ARCH_DETAILS.md`。
> 当前最紧要项见 `docs/NEXT_STEPS.md`；阻塞项见 `docs/PENDING_TASKS.md`。
>
> **最后更新**：2026-05-11

---

## 2026-05-11 锚点：NS-1 LLM 调用路径合并入 CPS 调度循环

将 `IbBehavior.call()` / `IbLLMFunction.call()` 与 `vm_handle_IbExprStmt` 中的 behavior 同步旁路合并入 VMExecutor 的 CPS 主循环；所有 LLM 调用（行为表达式 / 命名 LLM 函数）触发时，对应 VMTask 都在帧栈上，使 LLM 帧受 VM 调度管理（快照、并发、调试可观察性）。

- **新增 CPS 生成器助手**（`core/runtime/vm/handlers.py`）：
  - `_vm_invoke_behavior(executor, behavior, args)`：镜像 `IbBehavior.call` 的 scope/closure/参数绑定簿记，在调用 LLM 之前 `yield None` 一次以保证当前 VMTask 留在帧栈上，然后委托给 `executor.invoke_behavior(...)`。
  - `_vm_invoke_llm_function(executor, func, receiver, args)`：镜像 `IbLLMFunction.call` 的意图栈 fork / 模块切换 / `push_stack` / `enter_scope` / 参数自动绑定（含 `intent_context` 形参 `use_intent_context`）/ `call_intent` 解析簿记，`yield None` 后委托给 `executor.invoke_llm_function(...)`。
- **handler 改写**：
  - `vm_handle_IbCall`：当 `func` 是 `IbBehavior` 或 `IbLLMFunction` 时改用 `yield from` 助手；其他 callable 维持 `func.call(...)`。
  - `vm_handle_IbExprStmt`：behavior 分支由 `res.call(...)` 改为 `yield from _vm_invoke_behavior(executor, res, [])`。
- **VMExecutor 可观察性**：`VMExecutor` 新增 `frame_stack_depth` 属性（暴露主循环当前栈深度），供调试器 / NS-1 回归测试观察 CPS 帧层级。
- **`IbBehavior.call()` / `IbLLMFunction.call()` 保留为 Python-可调用后备**（host/用户直接调用场景），外部契约未变。
- **回归覆盖**：新增 `tests/runtime/test_vm_llm_cps_dispatch.py`（2 个测试）验证 `execute_behavior_object` / `execute_llm_function` 进入时 `vm.frame_stack_depth >= 2` 且 `step_count` 已推进。
- **范围外（已记为后续）**：`LLMExecutorImpl._evaluate_segments` 的 CPS 化转换未本批纳入。`_evaluate_segments` 通过 `vm.run(segment)` 对 prompt 片段做嵌套求值；改造为 yield-based 形式需要把它本身改为生成器、并让 `_call_llm`/`execute_behavior_expression` 调用方也变成 yield，扩散面较大且收益弱于 NS-1 主路径，因此留作 follow-up。
- 代码：`core/runtime/vm/handlers.py`、`core/runtime/vm/vm_executor.py`。文档：`docs/NEXT_STEPS.md`、`docs/VM_AND_INTERPRETER_DESIGN.md`。
- 回归结果：`python -m pytest tests/ -q --tb=short` 通过（1197 passed = 1195 历史 + 2 新增）。

NS-3（lambda/snapshot 跨帧 `_execution_context` 边界）由于 `vm_handle_IbCall` 现在对 IbBehavior 走 CPS 助手，**捕获时刻的 `_execution_context`** 已和**调用时刻的执行器** 通过 VMTask 帧栈对齐；但 `IbBehavior` 字段中仍持有定义期 `execution_context` 引用，跨线程时仍可能出现历史绑定问题（与 `core/runtime/objects/builtins.py:930` 一致）。因此 NS-3 不算被本次合并完全吃掉，保留待后续单独评估。

---

## 2026-05-11 锚点：NS-2 intent 系统 OOP 化完整收口（NS-2a/b/c/d 全部完成）

NS-2 全四步合龙——意图注释体系语法路径（`@`/`@+`/`@-`/`@!`）与 OOP 路径（`intent_context` 实例方法）打通为同一底层 `IbIntentContext`，双轨断裂彻底消除。

- **NS-2a**（已收录于本日条目）：`intent_context` 参数自动激活；`use(ctx)` 与函数自动绑定统一复用 `RuntimeContextImpl.use_intent_context(...)`。
- **NS-2b**：帧级活跃 `intent_context` IBCI 实例指针 `RuntimeContextImpl._active_intent_ibobj`，与帧 `_intent_ctx` 共享底层引用。`use()` / `clear_inherited()` / 函数入口 / NS-2a 自动绑定均同步重建此指针，使语法路径的 `@+`/`@-` 修改能通过 OOP `get_current()` 实时观察到（调试器亦获得用户命名身份）。
- **NS-2c**：`LLMExceptFrame.restore_context()` 由 `intent_context.merge(saved)` 改为 `_intent_ctx = saved.fork()` 干净替换，并同步重建活跃实例指针；retry 前后意图状态完全一致，与 vars / loop_context 的恢复语义对齐。
- **NS-2d**：新增 11 项测试覆盖（7 个 `tests/runtime/test_intent_context.py` 单元测试 + 4 个 `tests/e2e/test_e2e_ai_mock.py` 端到端测试），覆盖共享引用不变量、`use()` fork 语义、`clear_inherited()` 重建、`@+` × `get_current()` 同源观察、`llmexcept` retry 干净还原。
- 代码：`core/runtime/interpreter/runtime_context.py`，`core/runtime/objects/kernel.py`，`core/runtime/bootstrap/builtin_initializer.py`，`core/runtime/interpreter/llm_except_frame.py`。
- 回归结果：`python -m pytest tests/ -q --tb=short` 通过（1195 passed）。

历史 PT-1.1（llmexcept merge vs 替换语义对齐）随 NS-2c 一并落地，已从 `docs/PENDING_TASKS.md` 移除。PT-2.1 / PT-2.2 解除阻塞（依赖 NS-2b 的活跃实例指针），可作为 P2 排队。

---

## 2026-05-11 锚点：NS-2a（intent_context 参数自动激活）完成

- 在 `IbUserFunction.call()` 与 `IbLLMFunction.call()` 参数绑定阶段，`intent_context` 形参会自动激活为当前帧意图上下文（等价 `use(arg)` 语义）。
- 新增统一运行时入口 `RuntimeContextImpl.use_intent_context(...)`，并让 `intent_context.use(ctx)` 复用该入口，消除双轨分叉。
- 新增 e2e 覆盖：验证自动绑定生效、以及函数内 `@+` 修改不泄漏回调用方/实参上下文。
- 回归结果：`python -m pytest tests/ -q --tb=short` 通过（1182 passed）。

---

## 2026-05-08 锚点：类型系统主线收口 + VM CPS 全链路

### 类型系统五件套（M1–M5）

| 里程碑 | 完成日 | 摘要 |
|--------|--------|------|
| **M1**　TypeRef 引入 | 2026-05-07 | `core/kernel/spec/type_ref.py`：不可变 / 递归 / 工厂入口；编译器 / 解释器双端可读取 |
| **M2**　Optional[T] 与空安全 | 2026-05-07 | `OptionalSpec` + `OptionalAxiom` + 赋值规则；`is_nullable` 退役为兼容字段 |
| **M3**　TypeDef 单一化 | 2026-05-08 | 旧 `*Spec` 子类全部归并入统一 `TypeDef`，按 `kind` 分派；扁平 `*_name`/`*_module` 字段全面 TypeRef 化 |
| **M3→M5**　callable-instance 路线 | 2026-05-08 | `TypeKind.DEFERRED` + `BEHAVIOR` 合并为 `CALLABLE_INSTANCE`；`deferred_mode` → `capture_mode` |
| **M4**　运行时值模型单一化 | 2026-05-08 | `IbValue(type_ref, payload, fields, meta)` 成为运行时值公共承载层 |
| **M5**　Axiom 接口统一化 | 2026-05-08 | 单一 `TypeAxiom` 取代 9 个 Capability 子协议；`has_*_cap` 类属性声明能力 |

### 命名规范化（deferred → fn_callable，2026-05-08）

`IbDeferred` → `IbFnCallable`；`DeferredAxiom` → `FnCallableAxiom`；`DEFERRED_SPEC` → `FN_CALLABLE_SPEC`；`create_deferred()` → `create_fn_callable()`；`IbDeferredField` → `IbClassField`。无后向兼容 shim。

### VM CPS 全链路（M3a–M3d / M5a–M5c / M6 / Phase 1–5 编译器深度清洁）

| 里程碑 | 完成日 | 摘要 |
|--------|--------|------|
| **M3a**　CPS 调度循环骨架 | 2026-04-28 | `VMExecutor` + `VMTask` + dispatch table |
| **M3b**　控制信号数据化 | 2026-04-28 | `Signal(kind, value)` 替代 `ControlSignalException`（类已删除） |
| **M5a**　DDG 编译期分析 | 2026-04-28 | `BehaviorDependencyAnalyzer` 写入 `llm_deps` / `dispatch_eligible` |
| **M3c**　llmexcept retry CPS 化 | 2026-04-28 | `vm_handle_IbLLMExceptionalStmt` + `LLMExceptFrame.restore_snapshot` |
| **M5b**　LLMScheduler / LLMFuture | 2026-04-28 | ThreadPoolExecutor + 占位符模式 |
| **M3d / M5c**　主路径切换 + dispatch-before-use | 2026-04-29 | `execute_module()` / `IbUserFunction.call()` 全部经 `VMExecutor.run_body()` |
| **M4**　多 Interpreter 隔离（Layer 2） | 2026-04-29 | `spawn_isolated` / `collect` 契约 + ContextVar 帧 |
| **M6**　合规测试套件 | 2026-04-29 | `tests/compliance/`（执行隔离 / 并发 LLM / 内存模型） |
| **Phase 1–5 编译器深度清洁** | 2026-04-29 | CPS dispatch 覆盖 43 节点；`fallback_visit()` 调用归零；`node_protection` 侧表与 `bypass_protection` 参数链彻底删除 |

### 语法系统重设计（D1–D6，2026-04-29）

- D1：`fn` 等同 `auto`，不携带返回类型；`int fn f = ...` 形式废弃为 PAR_003。
- D2：lambda / snapshot 返回类型标注迁移至表达式侧（`lambda(...) -> T: EXPR`）。
- D3：`fn[(in)->(out)]` 高阶函数签名标注全链路落地（含 `IbCallableType` / `CallableSigSpec`）。
- D4–D6：现状已满足语义，无代码变更需要。

### llmexcept 影子执行驱动模式（历次演进收口于 2026-05-08）

- 废弃旧 `LLMUncertaintyError` 异常 + `_with_unified_fallback` 包装器。
- 当前实现：`set_last_llm_result(...)` 旗标轮询 + `LLMExceptFrame` 快照隔离 + AST 字段绑定（无侧表）。
- 详见 `docs/ARCH_DETAILS.md §一` 与 `docs/VM_AND_INTERPRETER_DESIGN.md §6`。

### 公理化 / IILLMExecutor 通道（2026-04-17）

- `core/base/interfaces.py:IILLMExecutor` + `KernelRegistry.register_llm_executor()` 建立合法服务通道。
- `BehaviorAxiom` 替换 `DynamicAxiom("behavior")`，`behavior` 成为一等公民类型。
- 旧 `_execute_behavior()` 旁路彻底删除。

### 健康审计修复批次（2026-04-29 → 2026-04-30）

- K1（`KernelRegistry.clone()` 漏拷 `_builtin_instances`）—— 已修复。
- K2（`SpecRegistry.is_assignable()` 防环递归）—— 已修复。
- K3（`register_builtin_instance` token 形同虚设）—— 已修复（移除 token 参数）。
- A1–A5 / L1–L4 等条目全部归档清理。

### OPEN_ISSUES 已解决批次

- OI-3：外部模块符号预注入临时妥协（2026-05-02）。
- OI-4：`SpecRegistry.resolve_specialization()` 缓存（2026-05-02 G1/G3）。
- OI-7：`LLMCallError` 自动抛出（2026-05-06）。

### MetadataRegistry 双轨统一（2026-05-08）

主引擎路径（`discover_all(registry)` + `HostInterface(external_registry=...)`）统一为单一 SpecRegistry 实例。`HostInterface.metadata` 与 `KernelRegistry._metadata_registry` 同源。

---

## 远期归档

更早期（2026-04-17 之前 + 三十余项 C1–C14 / L1–L4 / S1–S4 等清理）的实现细节归档于 `git log` 与具体文件的"演进历程"小节。本文件不再展开，避免污染当前看板。

---

## 关联文档

- 类型系统正式设计：`docs/TYPE_SYSTEM_DESIGN.md`
- VM 与解释器正式设计：`docs/VM_AND_INTERPRETER_DESIGN.md`
- VM 公理化规范：`docs/VM_SPEC.md`
- 实现细节备份：`docs/ARCH_DETAILS.md`
- 意图系统：`docs/INTENT_SYSTEM_DESIGN.md`
- 架构原则：`docs/ARCHITECTURE_PRINCIPLES.md`
- 当前已知限制：`docs/KNOWN_LIMITS.md`
- 代码内 TODO 索引：`docs/OPEN_ISSUES.md`
