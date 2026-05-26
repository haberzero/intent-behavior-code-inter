# PENDING_TASKS — 阻塞 / 待前置任务的未来规划

> 本文档记录**暂时搁置但经过验证仍有有效性的规划**——每项都有明确的阻塞原因或前置条件。
> 当前最紧要项见 `docs/NEXT_STEPS.md`；已完成事项见 `docs/COMPLETED.md`。
>
> **最后更新**：2026-05-26（深度核实原有条目有效性；恢复技术细节；修正 nonlocal 状态为"未实现"）
>
> **阅读指南**：
> - 标为 `[P1]` 的条目：前置条件已满足，可由 `NEXT_STEPS.md` 随时提升为当前任务
> - 标为 `[P2]`/`[P3]` 的条目：有明确前置链，需按序解锁
> - 标为 `[VISION]` 的条目：远期愿景，当前无明确用户需求推动
> - 标为 `[DESIGN-DEBT]` 的条目：已有部分基础设施但存在未解决的设计冲突

---

## 一、闭包写回语义 — `nonlocal` 关键字实现

**编号**: PT-CLOSURE-1  
**优先级**: P1（前置条件已满足，已被 `NEXT_STEPS.md` P0-C 提升为当前焦点）  
**状态**: 设计方案已确定，待实施

### 问题本质

IBCI 的闭包目前只支持**只读捕获**：内部函数/lambda 可以通过 `IbCell`（`core/runtime/objects/cell.py`）读取外部变量的最新值，但**不能写回**。原因是 `SymbolCollectionPass` 会为函数体内任何赋值目标创建本地符号，覆盖外部同名变量。

**代码验证**（2026-05-26）：
- Cell 基础设施已完备：`IbCell` 类、`ScopeImpl.promote_to_cell()`、`vm_handle_IbLambdaExpr` 的 lambda 共享分支均正常工作
- INV-LAMBDA-1/2（只读捕获）、INV-CONTEXT-1（返回 lambda 后 Cell 有效）测试全部通过
- INV-CONTEXT-2（闭包写回）失败 → 这就是本条目要解决的问题

### 推荐实现方案：`nonlocal` 关键字

用户通过 `nonlocal count` 显式声明"此变量来自外层作用域"，编译器据此跳过本地符号创建，改为建立到外部符号的 Cell 写入通道。

**全链路改动点**：

| 层 | 文件 | 改动 |
|----|------|------|
| Lexer | `core/compiler/lexer/core_scanner.py` | 在 KEYWORDS 表新增 `"nonlocal"` |
| Token | `core/compiler/common/tokens.py` | 新增 `TokenType.NONLOCAL` |
| AST | `core/kernel/ast.py` | 新增 `IbNonlocalStmt(names: List[str])` 节点 |
| Parser | `core/compiler/parser/components/statement.py` | 新增 `nonlocal_statement()` 解析规则 |
| SymbolCollectionPass | `core/compiler/semantic/passes/symbol_collection_pass.py` | `_prescan_body_locals` 跳过 nonlocal 声明的名称 |
| SymbolResolutionPass | `core/compiler/semantic/passes/symbol_resolution_pass.py` | `visit_IbNonlocalStmt` 验证外部绑定存在（否则 SEM_060/SEM_061） |
| BindingAnalysisPass | `core/compiler/semantic/passes/binding_analysis_pass.py` | 标记 nonlocal 变量为 Cell 提升（write-back 模式） |
| VM | `core/runtime/vm/handlers.py` | `vm_handle_IbFunctionDef` 对 free_vars 构建 Cell 闭包；`vm_handle_IbAssign` 对 nonlocal 变量写入 Cell |

**为什么不选其他方案**：
- 自动推断（Python 3 之前的行为）：违背 IBCI "显式优于隐式"设计原则，且在嵌套闭包中语义歧义风险高
- 无 nonlocal、仅保持只读捕获：满足 lambda 场景但无法覆盖"命名内部函数修改外部状态"的正当需求

**预估工作量**: 8-12 小时（词法/语法/语义/运行时全链路 + 回归测试）

---

## 二、Semantic Pipeline 后续演进

### PT-SEM-1　生产就绪化 [P2]

**前置条件**: Semantic 4-Phase pipeline 已稳定运行 ✅（`create_semantic_pipeline()` 在 `core/compiler/semantic/pipeline.py:115-139`）

**现状核查**（2026-05-26）：
- Pipeline 作为唯一编译期分析路径已稳定运行，无回退开关
- 4 个 Phase（SymbolPhase → TypePhase → BindingPhase → IntegrityPhase）均有对应 Pass 子步骤
- `PassOutput` frozen dataclass + `MetadataStore.from_outputs()` 合并产物路径已就绪

**具体待做**：
1. **错误信息优化**：当前 `SEM_xxx` 错误码附带的消息偏技术化（"symbol not found in scope"），需转化为用户友好表述（"变量 'x' 在此位置尚未声明"）
2. **诊断工具**：为符号表、类型绑定、行为依赖图提供可视化导出（JSON/dot 格式），便于开发者调试复杂脚本
3. **性能基准**：建立编译时间基准测试（针对 100+ 行脚本），确保后续改动不引入回归
4. **CI/CD 集成**：语义分析测试套件纳入 CI 流水线自动运行

**预估工作量**: 15-20 小时

---

### PT-SEM-2　CompilationResult 字段精简 [P3]

**前置条件**: PT-SEM-1 完成 + pipeline 稳定运行 ≥ 1 个月

**现状核查**（2026-05-26）：
- `CompilationResult`（`core/kernel/blueprint.py`）仍携带若干历史字段
- `MetadataStore` 三张核心绑定（symbol_bindings / type_bindings / loc_bindings）是下游（序列化器/VM）唯一真实消费方
- `core/compiler/semantic/adapter.py` 做 PipelineResult → CompilationResult 转换时可能搬运冗余数据

**具体待做**：
1. 审计 `CompilationResult` 中哪些字段被下游（`core/runtime/vm/`、序列化器）实际读取
2. 将未消费字段降级为 debug-only 或直接移除
3. 确认 `MetadataStore` 的三张绑定表是否可直接作为 CompilationResult 的唯一载荷

---

### PT-SEM-3　二层 IR 路线评估 [VISION]

**前置条件**: PT-SEM-2 完成 + 单 IR 路径稳定 ≥ 1 个月

**设计问题**：当前 semantic pipeline 既做"AST 结构变换"（llmexcept body 重排、intent 注解附着）又做"语义分析"（类型推断、符号解析）。随着行为依赖图/intent 调度优化等功能扩展，可能需要分离为：
- **结构 IR**：AST 规整化产物（可序列化、可独立验证）
- **执行 IR**：VM 直接消费的扁平化指令序列

**为什么搁置**：当前 IBCI 脚本规模（通常 < 200 行）下，单 IR 性能足够；只有当 LLM 调用计费/调度优化等高级功能需要跨过程分析时才会成为瓶颈。

---

## 三、VM 异步/协程层（L3）— 多项子任务共同阻塞

### 阻塞原因

L3 协程层需要 VM 从"单任务调度器"升级为"多任务挂起/恢复"架构。这牵涉三个独立维度的协同变更：
1. **调度器架构**：当前 `VMExecutor` 是单根任务（`vm.run(uid)` 一次执行完毕）；需要多任务队列 + `Signal.YIELD` 挂起语义
2. **语言层关键字**：`async`/`await`/`yield` 均不在现有 KEYWORDS 表中；需设计语法与类型
3. **快照协议对齐**：协程挂起时如何保存 intent_context 栈 + llmexcept 帧栈（当前 `try_deep_clone` 仅服务 llmexcept retry，不覆盖协程 yield 点）

### 现有基础设施（已验证可复用）

- CPS 风格 yield 调度循环（`vm_executor.py` / `handlers.py`）：所有语句执行已转为 VM 帧栈驱动，递归 visit 已消除 → 这是协程化的必要前置
- `ControlSignal` enum（`core/runtime/vm/task.py:34`）：已定义 break/continue/return/llm_uncertain 信号类型；可扩展 YIELD
- `dispatch_eager` + `LLMFuture`（`handlers.py:691-754`）：后台 LLM 请求 + 使用点阻塞解引用，已验证"异步提交 → 延迟解析"模式可行

### 被阻塞的子项

| 编号 | 标题 | 依赖 L3 的原因 |
|------|------|---------------|
| PT-3.1 | `host.run_isolated()` 返回值改进 | 当前返回 `IbObject`/`bool`，需要协程句柄才能实现"异步等待子脚本完成" |
| PT-3.2 | `ReceiveMode` 枚举演进 | 需要 yield/resume 语义支持流式接收模式 |

### 为什么搁置

- `dispatch_eager` + `LLMFuture` 已覆盖最主要的异步 LLM 需求，用户无需显式写 async/await
- 缺乏明确的用户需求来源——当前 IBCI 用户脚本都是线性流程 + LLM 调用
- 单次 PR 无法收口（最少跨 lexer/parser/semantic/vm/runtime 五层改动 + 快照协议升级）

---

## 四、语言级能力扩展（暂搁置，经事实核查确认有效）

### PT-4.1　Enum 非 str 成员 + 迭代能力 [VISION]

**已验证的现状**（2026-05-26 代码核查）：
- `EnumAxiom`（`core/kernel/axioms/primitives.py:1076+`）：`has_from_prompt_cap = True` / `has_output_hint_cap = True`
- `_get_enum_index_map(spec)` 遍历 `spec.members`，建立 `{name → name}` 映射——**不携带成员声明类型**，一律把成员"名字本身"当字符串值返回给 LLM
- `from_prompt(...)` 把 LLM 返回值大写化后查表；`__outputhint_prompt__` 仅列出成员名
- 运行时 `IbEnumValue` / `IbEnum`（`core/runtime/objects/enum.py`）所有比较退化到 `name` 字符串等价
- 写 `int RED = 1` 时 `from_prompt` 仍按名字匹配，与底层值 `1` 不一致

**扩展方向**：
- 支持 `int` / `float` 成员：`_get_enum_index_map` 升级为携带类型信息，`from_prompt` 同时接受名字或字面值
- 支持 `for v in Color:` 迭代：为 Enum 基类注册 `__iter__` / `__len__` 方法
- 统一 `Color.RED` 返回 `IbEnumAdapter` 而非原始 `IbString`

**为什么搁置**：现有 str 枚举 + LLM 名字匹配已覆盖 95% 用例；非 str 成员涉及 prompt 输出约定变更（"reply with RED" vs "reply with 1"），需用户反馈驱动。

---

### PT-4.2　`__call__` 协议类型推断一致性 [VISION]

**已验证的现状**（2026-05-26 代码核查）：
- 编译期：`TypeCheckingPass.visit_IbCall`（`type_checking_pass.py:388-396, 991-1003`）识别 `__call__` 成员并通过 `registry.resolve_callable_instance_return()` 推断返回类型
- 运行时：`vm_handle_IbCall`（`handlers.py:512`）对任意 `func` 派发 `func.receive("__call__", args)` — 语法层可用
- **已知灰区**（同步登记在 `KNOWN_LIMITS.md §三`）：
  1. `__call__` 内部 `@~...~` 的 intent_context 合并规则未显式规定
  2. `fn f = obj`（obj 是带 `__call__` 的类实例）的兼容性未被类型系统覆盖（`TypeKind.CLASS` 与 `fn_callable` 不在同一兼容轴）
  3. `__call__` 省略返回类型时回落到 `auto`，未与调用站左值类型协商

**扩展方向**：
- 在 `MethodMemberSpec` 上为 `__call__` 增设"is_callable_proxy"标记
- 显式规定 `__call__` 内 intent_context 合并规则
- 评估是否要求 `__call__` 的返回类型必须显式声明

**为什么搁置**：触及类型系统兼容性轴（class ↔ callable），跨 axiom/spec/semantic/vm 四层；用户可用"普通方法 + lambda 包装"作为零成本替代。

---

### PT-4.3　语言级协程 [VISION]

见 §三（L3 协程层）—— 本条是其语言层面表现形式。

---

### PT-4.4　用户类泛型类型参数 [VISION]

**已验证的现状**（2026-05-26 代码核查）：
- `core/compiler/lexer/core_scanner.py` KEYWORDS 无泛型 token
- `core/kernel/ast.py:IbClassDef` 无 `type_params` 字段
- `SpecRegistry.resolve_specialization()`（`registry.py:966+`）仅响应 axiom 内置类型（list/dict/Optional/tuple）；用户 class 的 spec 不参与泛型特化

**扩展方向**：
- `IbClassDef` 扩展 `type_params: List[str]`；语法层支持 `class Box[T]:` 形态
- 语义层对类成员中的 `T` 做延迟绑定；运行时走 erasure（不建立完整 HM 推断）

**为什么搁置**：`any` 兜底 + axiom 内置泛型已覆盖绝大多数 LLM 集成脚本需求；引入用户级泛型会撑大类型系统兼容性轴。

---

### PT-4.5　用户类运算符重载 [VISION]

**已验证的现状**（2026-05-26 代码核查）：
- 内置 axiom 通过 `resolve_operation_type_name(op, other_name)` 处理 `+ - * / < == !=` 等运算符
- 用户类 `IbClass` **无** dunder 运算符注册位；`==` 在用户类实例上退化为 `id()` 比较
- 现有 dunder 协议仅覆盖：`__init__` / `__call__` / `__to_prompt__` / `__from_prompt__` / `__outputhint_prompt__` / `__snapshot__` / `__restore__`

**扩展方向**：
- `IbClass.receive(op, [other])` 中增加"先查自身 dunder，再 fallback 到 axiom"分发
- `TypeCheckingPass.visit_IbBinOp` 增加用户类操作数分支：查找 `__add__` 等 → 推断返回类型

**为什么搁置**：IBCI 业务脚本主要使用 LLM + 容器操作，运算符重载不是核心需求；且涉及类型系统兼容性轴 + 编译期方法分派两个维度。

---

### PT-4.7　DDG 并行调度真正接入 VM [DESIGN-DEBT]

**已验证的现状**（2026-05-26 代码核查）：
- **编译期已就绪**：`BehaviorDependencyAnalyzer`（`core/compiler/semantic/passes/behavior_dependency_pass.py:37+`）为每个 `IbBehaviorExpr` 计算 `llm_deps` / `dispatch_eligible` 字段
- **运行时有部分通路**：`vm_handle_IbBehaviorExpr`（`handlers.py:691-754`）在 `dispatch_eligible=True` 时调用 `LLMScheduler.dispatch_eager()` 提交后台 LLM 请求，得到 `LLMFuture` 占位符；`vm_handle_IbName`（`handlers.py:90-117`）在读取 `LLMFuture` 时阻塞解引用
- **限制**：Cell 变量被标记为 `dispatch_eligible=False`（`handlers.py:744`），避免 Cell 同步问题；但更深层的设计冲突是 **llmexcept 快照与 future 解引用的交互**——若 retry 发生时 future 尚未完成，`try_deep_clone` 无法正确快照一个"未完成的 future"

**为什么搁置**：收益高（非依赖 LLM 调用可真正并行）但风险高——快照 / future 解引用顺序的错配会破坏 retry 隔离语义。建议在 llmexcept 快照协议有专门的 "future-aware snapshot" 策略后再推进。

---

## 五、设计原则与明确排除方向

> 以下原则经项目主要贡献者确认，作为架构决策的长期约束。

### 坚持的设计原则

1. **显式优于隐式**：所有语义行为必须在代码中可见（如 `nonlocal` 而非自动推断、显式 `(Type)cast` 而非隐式转换）
2. **单点真理**：同一份语义事实只能存在于一处可序列化位置——AST 字段 ∨ 侧表 ∨ MetadataStore，不允许双写（详见 `docs/METADATA_ARCHITECTURE.md`）
3. **公理调度 + 单次锁定**：类型系统不引入完整约束求解/HM 风格推断，但允许从中汲取受控设计思路（如 `TypeSlot` 单次锁定延迟绑定）
4. **运行时可观测性优先**：不以牺牲调试/内省能力换取短期性能优化

### 明确排除的方向

- ❌ 静态类型检查器作为解释器前置强依赖
- ❌ 为优化同一程序内独立 LLM 调用而创建多 Interpreter（这是 L1 流水线职责）
- ❌ 完整的 HM 风格类型推断（但 TypeSlot 延迟绑定等受控借鉴是允许的）
- ❌ AST 字段 + 侧表 + MetadataStore 三处同时存储同一语义事实（"双写真相"禁令）
