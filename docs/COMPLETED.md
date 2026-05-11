# COMPLETED — 极简时间线归档

> 本文档以**极简时间线**记录主线工作的完成节点。
> 设计与实现细节见对应正式文档：`docs/TYPE_SYSTEM_DESIGN.md`、`docs/VM_AND_INTERPRETER_DESIGN.md`、`docs/VM_SPEC.md`、`docs/ARCH_DETAILS.md`。
> 当前最紧要项见 `docs/NEXT_STEPS.md`；阻塞项见 `docs/PENDING_TASKS.md`。
>
> **最后更新**：2026-05-11

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
