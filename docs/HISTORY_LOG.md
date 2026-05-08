# IBC-Inter 项目演进历史记录

> 本文档按时间线记录 IBC-Inter 项目的核心演进节点，供未来维护者了解项目如何一步一步演进到当前状态。
>
> **详细的阶段性落地记录**：`docs/COMPLETED.md`（按演进顺序，含具体文件变更和测试基线）  
> **当前正式设计文档**：`docs/TYPE_SYSTEM_DESIGN.md`、`docs/VM_INTERPRETER_DESIGN.md`  
> **最后更新**：2026-05-08

---

## 阶段一：基础语言核心（2026-04 初期，测试基线约 610–750 passed）

### 早期架构现状

- 类型系统：`core/kernel/types/` 目录（`descriptors.py`、`registry.py`）是旧体系，`Symbol.descriptor` 属性和 `TypeDescriptor`/`FunctionMetadata`/`ListMetadata` 等类是当时的核心。
- 解释器：基于 Python 递归调用栈，控制流通过 `LLMUncertaintyError` 异常传播，llmexcept 处理分散在各 `visit_*` 方法中，`_with_unified_fallback` 包装器提供统一 fallback，但架构混乱。
- callable（延迟求值）：`lambda`/`snapshot` 被称为"延迟求值（deferred）"，`DeferredSpec` 是独立 Spec 子类，`TypeKind.DEFERRED` 与 `TypeKind.BEHAVIOR` 是两条分开的路线。

### 主要完成工作（详见 COMPLETED.md §一–§五）

**类型系统与公理化（约610 tests时期）**：
- Tuple 类型全栈实现（`IbList` 错误装箱 Python tuple 的 Bug 修复）
- 类型兼容性方向修复（`is_compatible` 语义统一为"source 能否赋值给 target"）
- `VoidAxiom` 替代 `DynamicAxiom("void")`，`void` 成为具体无返回值类型
- `CallableAxiom` 替代 `DynamicAxiom("callable")`，成为可调用抽象根
- `DeferredAxiom` + `DeferredSpec` + `IbDeferred`：任意表达式（非仅 `@~...~`）可通过 lambda/snapshot 包装成可调用实例——这是当时的设计，"延迟求值"是当时的命名
- `BehaviorAxiom` + `BehaviorSpec`：`@~...~` 行为表达式体系落地
- `IntentContextAxiom`：意图上下文正式成为 IBCI 公理化类型
- LLM 执行路径重构：废弃 Python 异常驱动，改为 `LLMResult.is_uncertain` 标志位；`visit_IbAssign` 检测 uncertain 后赋值 `IbLLMUncertain` 哨兵（而非跳过）；`visit_IbIf/While/For` 检测 uncertain 后返回空，外层 `visit_IbLLMExceptionalStmt` 统一管理 retry 循环。

**代码健康（约 610 tests 时期）**：
- 删除 `core/kernel/types/` 旧体系，迁移到 `core/kernel/spec/`
- 旧 `SpecRegistry` → 新 `SpecRegistry`（基于 `core/kernel/spec/registry.py`）
- 插件可见性修复：`Prelude._init_defaults()` 不再把插件全局注入，`import ai` 才使 `ai` 可见
- `IbStatefulPlugin` 状态快照机制落地（`ibci_ai` 保存/恢复配置）
- `ibci_idbg` 调试模块上线（`last_llm()`/`show_last_prompt()`/`show_intents()` 等）

---

## 阶段二：fn/lambda/snapshot 语法重设计（2026-04-28 前后，基线约 750–900 passed）

### 背景问题

旧语法 `int fn f = lambda: EXPR` 存在严重设计耦合：`fn` 承担了本不属于它的"携带输出类型"职责，通过编译器内部 `_pending_fn_return_type` 侧通道传递给 `visit_IbLambdaExpr`。表达式侧不允许写 `lambda -> TYPE: EXPR`，且 `fn` 无法表达 callable 签名约束（无法写 `fn[(int)->int]`）。

### 设计决策 D1/D2（2026-04-28）：`fn` 与类型标注解耦

- **D1**：`fn` 完全等同于 `auto`，在变量声明侧只做可调用类型推导，不承载任何输出类型。旧的 `int fn f = lambda: EXPR` 产生 PAR_003 编译错误。
- **D2**：返回类型标注迁移至表达式侧：`lambda(int x) -> int: EXPR`，`fn` 与之彻底解耦。
- 同步删除 `_pending_fn_return_type` 编译器侧通道。

### IbCell + 词法作用域正式化（M1/M2，2026-04-28）

- `IbCell` 原语落地（`core/runtime/objects/cell.py`）：纯容器、身份语义，`trace_refs()` GC 钩子。
- `ScopeImpl.promote_to_cell()` 实现变量到 Cell 的提升。
- lambda/snapshot 闭包通过 `closure: Dict[sym_uid, (name, IbCell)]` 统一访问自由变量。
- GC 根集合正式化：全局作用域 ∪ 活跃帧局部变量 ∪ fn 对象 closure 字典中的 Cell 值。

### 设计决策 D3（2026-04-29）：`fn[(...)->(...)]` 高阶函数签名标注

- 引入 `IbCallableType` AST 节点 + `CallableSigSpec(FuncSpec)`
- 解析器支持 `fn[(int, str) -> bool] predicate` 语法
- 语义分析阶段结构匹配：实际传入的 callable 签名与 `fn[...]` 约束对比
- 20 个 D3 专项测试

---

## 阶段三：VM CPS 化（M3/M5/M4/M6，2026-04-28~29，基线 867→1011 passed）

### 问题根因

旧解释器基于 Python 递归调用栈：IBCI 调用深度受 `sys.setrecursionlimit` 限制，控制流信号（return/break/continue）通过 Python 异常传播（`ControlSignalException`），性能差且难以调试。多 Interpreter 并发（Layer 2）无法在 Python 递归栈模型下安全实现。

### M3a：CPS 调度循环骨架（2026-04-28）

- `VMExecutor._drive_loop()` 引入显式帧栈，首批覆盖 `IbAssign`/`IbReturn`/`IbName`/`IbConst`/`IbBinOp`。
- CPS handler 通过 `yield child_uid` 挂起，帧栈弹/压子节点，`StopIteration` 向父帧交付值。

### M3b：控制流数据化（2026-04-28）

- `Signal(kind, value)` 数据类替代 `ControlSignalException`。
- `return`/`break`/`continue`/`throw` 均通过 Signal 在帧栈间传播。
- `ControlSignalException` 类彻底从代码库删除（仅余 `UnhandledSignal` 作为边界异常）。

### M5a：DDG 编译期分析（2026-04-28）

- `BehaviorDependencyAnalyzer`（Pass 5）分析 behavior 间数据依赖，标注 `dispatch_eligible`。
- Cell 变量、llmexcept 保护节点强制 `dispatch_eligible=False`（IbCell 不可持有 LLMFuture 占位符）。

### M3c：llmexcept CPS 调度化（2026-04-28）

- `vm_handle_IbLLMExceptionalStmt` 成为主控外壳，主动 yield target_uid 驱动目标节点执行。
- `LLMExceptFrame.restore_snapshot()` 在每次 retry 前恢复变量/意图/循环上下文完整快照。

### M5b：LLMScheduler + LLMFuture（2026-04-28）

- `LLMScheduler.dispatch_eager()`：提交 LLM 调用到 `ThreadPoolExecutor`，返回 `LLMFuture` 占位符。
- `LLMFuture.resolve()`：读取点阻塞等待，将真实值写回符号表（O(1) 后续访问）。

### M3d + M5c：主路径切换 + dispatch-before-use（2026-04-29）

- **C13（M3d 前置）**：`ExecutionContextImpl.vm_executor` 属性注入，`IbUserFunction.call()` 直接走 VM 路径（旧三级查找链发现函数体始终走 `context.visit()` fallback，C13 是首次真正使函数体经由 VM 执行）。
- `Interpreter.execute_module()` 和 `IbUserFunction.call()` 均通过 `VMExecutor.run_body()` 驱动，主执行路径正式切换。
- M5c：`dispatch_eligible=True` 的 behavior 表达式在 VMExecutor 中直接调用 `dispatch_eager()`，读取点 lazy resolve。

### M4：Layer 2 多 Interpreter 并发（2026-04-29）

- `DynamicHost.spawn_isolated()` 在独立线程中运行子 Interpreter，共享只读 KernelRegistry。
- `collect(handle)` 阻塞等待，返回可序列化值字典。
- 基线：949 → 964（+15 M4 专项测试）。

### M6：VM 规范层 + 合规测试套件（2026-04-29）

- `docs/VM_SPEC.md` 正式发布，公理化定义执行模型/内存模型/LLM 数据流/多 Interpreter 并发。
- `tests/compliance/` 套件建立（46 个合规测试，覆盖内存模型/LLM 并发/执行隔离）。
- 基线：964 → 996。

### 编译器深度清洁 Phase 1–5（C5–C14，2026-04-29）

**问题**：尽管主路径切换完成，CPS handler 覆盖不全（仍有 `fallback_visit()` 兜底），`node_protection` 侧表与 `bypass_protection` 参数链残留，AST 节点自由变量和 Cell 侧表未在编译期正确填充。

**清洁内容**：
- **C5/C6**：将所有剩余节点类型迁移到 CPS handler，消除所有 `fallback_visit()` 调用
- **C7**：`_vm_assign_to_target()` CPS generator helper 替代 assign_to_target 递归穿透
- **C8**：`IbLambdaExpr`/`IbBehaviorInstance` 的 CPS handler 彻底消除 fallback 路径
- **C11/P3**：`node_protection` 侧表与 `bypass_protection` 参数链彻底删除
- **C14**：`IbLambdaExpr.free_vars` 与 `cell_captured_symbols` 侧表在编译期正确填充
- 基线：996 → 1011（完成后 43 个 AST 节点类型全部 CPS 化）

---

## 阶段四：代码健康三件套 + 用户异常体系（2026-05-02 ~ 05-06，基线约 1011→1100 passed）

### H5–H7 代码健康（2026-05-02）

对 HEALTH_AUDIT_2026_04_29.md 审计发现的历史妥协点进行清理：
- `engine.py`/`service.py` 历史妥协点继续清理
- 意图标签解析迁移到 Lexer（原来在 Parser 层，违反分层原则）
- 泛型推断 G3 改进：嵌套泛型场景的类型推断能力增强
- `LLMExceptFrame` 重试历史追踪完善

### 用户自定义异常体系（2026-05-06）

- `IbException` 类型落地，`try/except` 完整可用
- 用户可以 `raise MyException("msg")` 并在 `except (MyException e)` 中捕获
- 异常继承链、多 except 分支、finally 块全链路实现

---

## 阶段五：类型系统五大里程碑（M1–M5，2026-05-07~08，基线 1056→1184 passed）

这是类型系统的一次彻底重构，将分散的多 Spec 结构统一为单一 TypeDef，消除所有字符串类型引用，建立统一的公理接口。

### M1：TypeRef 引入（2026-05-07，+103 tests）

旧类型系统中，类型引用全靠字符串名称（`param_type_names`、`return_type_name` 等），无法表达泛型结构。M1 引入 `TypeRef(head, args, module)` 作为结构化类型引用：
- `core/kernel/spec/type_ref.py` 新建
- 所有 Spec 的关系字段新增 TypeRef 版本（`IbSpec.type_ref`、`FuncSpec.return_type_ref` 等，与旧字符串字段并存）
- `SpecRegistry.resolve_typeref()` 支持按 TypeRef 查找，含跨模块与泛型特化
- 103 个新测试（`tests/kernel/test_typeref.py`）
- 基线：1056 → 1159

### M2：Optional[T] 与空安全（2026-05-07）

- `OptionalSpec` + `OptionalAxiom` 落地
- `SpecRegistry.is_assignable()` 改为 Optional[T] 语义：非 Optional 类型禁止接收 None；`Optional[T]` 接受 `T` / `None` / `Optional[T]`
- `Optional.unwrap()` / `or_else()` 返回类型收口到 T
- 旧 `is_nullable` 布尔语义字段冻结（不再参与可空判定）
- 基线：1159 → 1179

### M3：TypeDef 单一化 + callable-instance 路线（2026-05-08）

**旧多 Spec 体系的问题**：`FuncSpec`、`ClassSpec`、`ListSpec`、`TupleSpec`、`DictSpec`、`DeferredSpec`、`BehaviorSpec`、`OptionalSpec` 等各有独立 Python 类，代码中大量 `isinstance(spec, FuncSpec)` 分支，维护成本高。

**M3 做了什么**：
- 设计 `TypeDef(kind, ...)` 统一结构，以 `TypeKind` 枚举区分语义类别
- 将所有旧 Spec 子类迁移到 TypeDef，旧类名别名全部删除（无任何兼容 shim）
- 所有关系字段全面 TypeRef 化：`param_types`、`return_type`、`parent_type`、`element_type`、`key_type`、`value_type`、`wrapped_type`、`receiver_type`、`allowed_element_types`
- 旧标量便利 property 全部删除：`return_type_name`/`_module`、`element_type_name`/`_module` 等 47+ 处读取点全部迁移到 `.X.head` / `.X.module`
- **callable-instance 统一**：`TypeKind.DEFERRED` + `TypeKind.BEHAVIOR` 合并为 `TypeKind.CALLABLE_INSTANCE`；`deferred_mode` 字段从 TypeDef 删除，全局重命名：`deferred_mode → capture_mode`、`is_deferred → is_callable_instance`、`node_deferred_mode → node_capture_mode` 等

这次 M3 重构彻底确立了"lambda/snapshot 不是延迟求值，而是 callable-instance"的语义定位。

### M4：IbValue 运行时值单一化（2026-05-08）

- `IbValue(type_ref, payload, fields, meta)` 作为统一运行时值基类落地
- 所有内置值类型（IbInteger/IbList/IbDeferred/IbBehavior 等）转入 IbValue 子体系
- 旧类名保留为兼容包装层（`__slots__=()` 确保无独立存储），`.value` property 访问 payload
- `isinstance(obj, IbXxx)` 分发全面替换为 `isinstance(obj, IbValue) and obj.ib_class.name == "..."` 模式
- 基线维持 1184（运行时行为不变，只是内部布局统一）

### M5：Axiom 接口统一化（2026-05-08）

旧 9 个 Capability 子协议（CallCapability/IterCapability 等）造成大量多重继承和样板代码，每次新增类型需要多处修改。

M5 以单一 `TypeAxiom` Protocol 替代，能力通过 `has_*_cap` 类属性声明（`BaseAxiom` 提供全 False 默认），`SpecRegistry.get_X_cap()` 统一入口。删除 `_FUNC_SPEC_CALL_CAP` 哨兵和 `WritableTrait` 不可达路径，净减约 400 行旧粘合代码。

**至此，五大里程碑全部完成，测试基线稳定在 1180 passed。**

---

## 技术决策记录（跨阶段）

| 决策 | 时间 | 说明 |
|------|------|------|
| 不引入静态类型检查器作为前置强依赖 | 早期 | IBCI 类型系统自给自足，不依赖外部类型检查工具 |
| 控制流信号数据化（M3b） | 2026-04-28 | 替代 Python 异常传播，使执行模型可迁移到非 Python 宿主 |
| fn/lambda 表达式侧返回类型（D1/D2） | 2026-04-29 | 解耦 fn 声明与类型标注，使 fn 成为纯 callable 推导关键字 |
| callable-instance 统一（M3） | 2026-05-08 | 废除"延迟求值"旧术语，lambda/snapshot/behavior 均视为 callable-instance |
| TypeDef 单一化（M3） | 2026-05-08 | 彻底删除多 Spec 体系和字符串类型字段，无兼容过渡层 |
| MetadataRegistry 双轨统一 | 2026-05-08 | Engine 路径单一 SpecRegistry 实例，discover_all 传入 registry 强制校验 |

---

## 测试基线时间线

| 时间 | 基线 | 主要里程碑 |
|------|------|----------|
| 2026-04-20 | ~610 | 旧类型系统初始状态，基础公理化 |
| 2026-04-28 | ~758 | fn/lambda/IbCell 新语法落地（M1/M2） |
| 2026-04-28 | ~867 | CPS 骨架 + Signal 数据化（M3a/M3b + M5a）|
| 2026-04-28 | ~905 | llmexcept CPS（M3c）+ LLMScheduler（M5b） |
| 2026-04-29 | ~926 | CPS handler 扩展（M3d-prep） |
| 2026-04-29 | ~949 | VM 主路径切换（M3d）+ dispatch-before-use（M5c） |
| 2026-04-29 | ~964 | 多 Interpreter 并发（M4） |
| 2026-04-29 | ~996 | VM 规范层 + 合规套件 + Phase 1 清洁（M6） |
| 2026-04-29 | ~989 | Phase 5 清洁（C11/P3，删除 3 个死代码测试） |
| 2026-04-29 | ~1011 | fn/lambda/snapshot D3 callable 签名标注全链路 |
| 2026-05-02 | ~1050 | H5–H7 健康清理 + 泛型推断 G3 |
| 2026-05-06 | ~1100 | 用户自定义异常 + try/except 完整可用 |
| 2026-05-07 | ~1159 | 类型系统 M1 TypeRef 引入（+103 测试）|
| 2026-05-07 | ~1179 | 类型系统 M2 Optional[T] |
| 2026-05-08 | ~1182 | 类型系统 M3 TypeDef 单一化 |
| 2026-05-08 | ~1184 | 类型系统 M4 IbValue 统一 |
| 2026-05-08 | ~1184 | 类型系统 M5 Axiom 接口统一化（完成全部里程碑）|
| 2026-05-08 | ~1180 | 稳定后（少量测试清理）|
