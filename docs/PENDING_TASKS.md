# IBC-Inter 待实现任务清单

> 记录中长期未来工作。近期任务见 `docs/NEXT_STEPS.md`，已完成工作见 `docs/COMPLETED.md`。
>
> **最后更新**：2026-04-28（M1 完成；758 个测试通过；fn/lambda/snapshot 全新语法落地，旧语法彻底移除）

---

## 一、动态宿主（DynamicHost）相关

### 1.1 子解释器插件注册 [PENDING]
**任务**：允许子解释器独立注册自己的插件。

**搁置原因**：当前阶段不允许子解释器独立注册插件，所有插件应从主解释器继承。

**未来方案**：定义插件注册接口、实现运行时插件加载机制、添加隔离策略配置项。

---

### 1.2 HOST 插件 breakpoint 接口 [PENDING]
**任务**：为 HOST 插件添加 breakpoint 相关接口（现场保存/恢复/回溯，非 GDB 式断点）。

**搁置原因**：DynamicHost 当前最小目标不含断点功能，需先完成内核稳定工作。

---

## 二、公理化相关

### 2.1 Intent 完整公理化 [✅ COMPLETED — 2026-04-19]

**完成内容**：
- 新建 `core/kernel/axioms/intent.py`：`IntentAxiom`（`is_class()=True`，完整 vtable 声明）
- `IbIntent` 添加 `@register_ib_type("Intent")` 装饰器及三个公共方法：`get_content()`、`get_tag()`、`get_mode()`
- `register_core_axioms()` 注册 `IntentAxiom()`
- `INTENT_SPEC = ClassSpec(name="Intent", ...)` 加入 `specs.py` 并注册到 `create_default_spec_registry()`，使 `_bootstrap_axiom_methods()` 在 `SpecRegistry` 初始化阶段即填充 `Intent` 成员表
- `builtin_initializer.py` 显式导入 `IbIntent`，确保 `@register_ib_type("Intent")` 在公理自动化绑定循环之前执行
- 517 个测试全部通过

---

### 2.2 Intent Stack 不可变性约束 [PENDING]
**任务**：实现 Intent Stack 不可变性约束。

**搁置原因**：依赖 Intent 公理化完成；Intent Stack 语义尚有待澄清的设计要点。

---

### 2.3 符号同步深拷贝 [PENDING]
**任务**：修复 `_sync_variables_from()` 直接传递 symbol 引用的问题。

**搁置原因**：变量继承已禁用（`inherit_variables=False`），当前不触发。**位置**：`interpreter.py:93-99`

---

### 2.4 ParserCapability LLM 提示词片段扩展 [PENDING]
**任务**：扩展 `ParserCapability` 接口，添加 `get_llm_prompt_fragment()` 方法，替代 `ibci_ai` 中硬编码的 `_return_type_prompts`，使每个 Axiom 能自主声明其对应的 LLM 输出格式提示词。

**涉及文件**：`core/kernel/axioms/protocols.py`、`core/kernel/axioms/primitives.py`、`core/runtime/interpreter/llm_executor.py`

---

### 2.5 Axiom Capability 内部委托对象模式重构 [FUTURE / INDEPENDENT]

**任务**：将 `primitives.py` 中所有 Axiom 类从"自身实现 Capability Protocol"的多继承模式，改为"持有内部 Capability 委托对象"的委托模式（`DeferredCallCapability` / `BehaviorCallCapability` 已采用此独立类模式）。

**目标模式**：
```python
class _IntOperatorCapability:           # 独立私有类
    def resolve_operation_type_name(self, op, other): ...

class IntAxiom(BaseAxiom):              # 只继承 BaseAxiom，无 Protocol 多继承
    _op_cap = _IntOperatorCapability()
    def get_operator_capability(self): return self._op_cap
```

**完成效果**：所有 14 个 Axiom 类 MRO 退化为单继承；`primitives.py` 中 48 处 Protocol 多继承链条全部消除；对外 API 零破坏（调用方通过 `get_xxx_capability()` 访问）。

**工程量**：需新增约 40-50 个私有 Capability 类，约为 Impl 类 Protocol 清理工作的 3-4 倍。需同步拆分 `primitives.py`（届时约 2000+ 行）。

**搁置原因**：无对应 Bug；Capability Protocol 均无 `@runtime_checkable` 修饰，不存在 Python 3.12 isinstance 风险；为纯架构美观性改进，现阶段无触发必要性。

**建议触发时机**：`primitives.py` 因内容增加需强制拆分文件时，或 Capability 逻辑出现跨 Axiom 复用需求时。

**涉及文件**：`core/kernel/axioms/primitives.py`

---

## 三、类型系统

### 3.1 禁止 auto 向明确类型隐式赋值 [PENDING]
**任务**：实现 auto 类型约束机制，禁止 auto 向明确类型隐式赋值。

**搁置原因**：最低优先级，允许当前瑕疵存在。**方向**：在语义分析器的类型检查阶段加强约束。

---

### 3.2 ib_type_mapping 完善 [PENDING]
**任务**：完善 `runtime/objects/ib_type_mapping.py` 的类型映射实现（当前 `_IB_TYPE_TO_CLASS` 为空字典）。

**搁置原因**：不影响核心功能，优先级低。

---

### 3.3 BooleanCapability 接口 [PENDING]
**任务**：在语义分析器的条件驱动 for 循环类型校验中（`semantic_analyzer.py` 约第 853 行），引入 `BooleanCapability` 接口，替代现有的 `is_dynamic() or is_behavior() or iter_type.name == "bool"` 特例判断。

**当前状态**：该分支逻辑直接 `pass`，无实质约束；现有条件足以覆盖已知场景。

**搁置原因**：不影响当前功能正确性；需要在 `core/kernel/axioms/protocols.py` 中新增 `BooleanCapability` 协议并在所有布尔类型 Axiom 中实现。

---

## 四、语法功能

### 4.1 (str n) @~ ... ~ 语法完善 [PENDING]
**任务**：验证并完善 callable 闭包参数传递语法，明确其设计语义。

**搁置原因**：手册描述的语法需确认完整实现，闭包参数传递机制需更明确的设计。

---

### 4.2 llmretry 后缀语法澄清 [PENDING]
**任务**：明确 llmretry 后缀的当前实现状态与文档描述是否一致。

**搁置原因**：当前实现为声明式 llmexcept + retry，手册描述的单行后缀语法已被重构。

---

### 4.3 lambda/snapshot 语法重构与语义完整化 [REDESIGNED ⏳ — 2026-04-27]

> **状态**：本任务已升级为完整的语法重构任务。新语法方案已于 2026-04-27 确认，完整规范见 `docs/NEXT_STEPS.md` Step 12.5。

**旧语法（将废弃）**：`TYPE lambda NAME = EXPR` / `TYPE snapshot NAME = EXPR`  
**新语法（计划）**：`fn [TYPE] NAME = lambda([PARAMS])(BODY)` / `fn [TYPE] NAME = snapshot([PARAMS])(BODY)`

**已实现（2026-04-19，现行旧语法下）**：
- `lambda` 延迟对象不允许作为函数参数传递（运行时 `RUN_CALL_ERROR`，见 `kernel.py` `IbUserFunction.call()`）
- `snapshot` 捕获定义位置的意图栈快照，可被作为参数传递和跨作用域传递
- `IbBehavior(deferred_mode='snapshot')` 在 `captured_intents` 字段存储意图快照

**已明确的语义规范（2026-04-27，待新语法实现后落地）**：
- 参见 `docs/INTENT_SYSTEM_DESIGN.md` §9（意图栈交互规则 IT-1 至 IT-4）
- 参见 `docs/PENDING_TASKS_VM.md` §10.2—10.3（Cell 变量模型 + 生命周期模型）

**待实现（Step 12.5 任务）**：
- **新 fn 语法**：`fn int my_fn = lambda(int x)(x + n)` 有参形式；`fn my_fn = lambda(expr)` 无参形式
- **参数传递**：`IbDeferred.call()` / `IbBehavior.call()` 支持参数传入
- **IbCell 机制**：引入 Cell 堆对象实现词法闭包正确语义（SC-2 至 SC-4）
- **编译期约束**：lambda 存储约束（不允许赋给全局变量、类字段）提升到语义分析阶段
- **废弃旧语法**：新语法稳定后，旧语法先输出 `DEP_001` 警告，最终产生 `PAR_001` 错误

**搁置原因**：编译器 DDG 分析和 IbCell 机制需要系统性工程工作；旧语法测试已暂时注释（见 `tests/e2e/test_e2e_deferred.py`）。

---

## 五、intent_context 完整 OOP 化（已记录，待跟进）

> MVP 已落地（2026-04-19）：`intent_context` 可实例化，支持 `push/pop/fork/resolve/merge/clear` 方法。以下为用户明确要求的、尚未实现的完整功能。

### 5.1 将 intent_context 实例作为函数调用参数传递 [PARTIAL ✅ / PENDING]

**已实现（2026-04-19）**：用户可以将 `intent_context` 实例作为**普通参数**传递给函数，然后在函数内部调用 `intent_context.use(ctx)` 将其设置为当前作用域的意图上下文：

```ibci
func process_with_custom_ctx(intent_context ctx):
    intent_context.use(ctx)    # 用传入的上下文替换当前作用域（fork 拷贝，不共享引用）
    str r = @~ MOCK ~          # 只见 ctx 中的意图
    return r

intent_context my_ctx = intent_context()
my_ctx.push("简洁明了")
str result = process_with_custom_ctx(my_ctx)
```

**待实现（未来工作）**：
- **隐式绑定语法**：函数声明中以特殊方式声明 `intent_context` 参数，运行时自动将其绑定到当前帧的 `_intent_ctx`（而非用户手动调用 `use(ctx)`）
- **语法糖**：调用方 `my_func(@ctx my_ctx_var)` 使 `my_ctx_var` 自动成为函数作用域的意图上下文（无需函数体内显式 `use()`）
- **运行时绑定路径**：若有显式 `intent_context` 实参，则替换为该实参所包装的 `IbIntentContext`，而非 fork 调用者上下文

**搁置原因**：需要编译器和语义分析器支持意图上下文参数的自动绑定；当前通过 `intent_context.use(ctx)` 已可手动实现等效效果，此任务为语法层的简化。

---

### 5.2 函数内部屏蔽全局意图栈的精细控制 [✅ COMPLETED — 2026-04-19]

**已实现（2026-04-19）**：
- `intent_context.clear_inherited()` — 清空当前作用域从调用者继承的持久意图栈（✅ 已实现）
- `intent_context.use(ctx)` — 用指定 intent_context 实例替换当前作用域的意图上下文（✅ 已实现）
- `intent_context.get_current()` — 获取当前作用域意图上下文的快照副本（✅ 已实现）

**函数调用粒度的屏蔽**：
- 每次函数调用 fork 调用者意图上下文（拷贝传递），函数内操作不泄漏（✅ 已实现）
- 函数体内写 `intent_context.clear_inherited()` 清空继承的意图栈（✅ 已实现）
- **`@!` 不修饰函数调用**（明确的设计决策：`@!` 只修饰 LLM 行为表达式 `@~...~`）

**待实现（未来工作）**：
- **编译期 `@` 约束在函数调用时的静态检查**：目前 fork 是运行时行为；未来可在语义分析阶段对 `@` 作用域提前标注
- `@clear` 关键字语法糖（作为 `intent_context.clear_inherited()` 的简写，属于语法糖，非必需）

---

### 5.3 intent_context 作为函数参数类型 [PENDING]

**需求**：函数可以声明 `intent_context` 类型的参数，允许调用者传入自定义意图上下文对象，函数内直接操作该对象（push/pop/etc.），影响此次调用下的 LLM 行为。

```ibci
func generate_text(intent_context ctx, str prompt) -> str:
    ctx.push("保持简洁")
    str result = @~ $prompt ~
    return result
```

**搁置原因**：需要语义分析器对 intent_context 参数的特殊处理：绑定参数到当前帧的 `_intent_ctx`；与 5.1 协同设计。

---

### 5.4 intent_context 显式作为函数作用域默认上下文 [PENDING]

**需求**：在函数体内可以显式声明一个 `intent_context` 变量作为"本函数的意图上下文"，所有 `@+`/`@-` 操作作用在该变量上，而非隐式的 `rt_context._intent_ctx`。

```ibci
func process():
    intent_context my_ctx = intent_context()
    # 以下 @+ 操作作用在 my_ctx 上（而非隐式上下文）
    @+ "格式要求"  # → my_ctx.push(...)
    str r = @~ MOCK:test ~
```

**搁置原因**：这需要对意图操作的作用目标（隐式 vs 显式）进行语法区分，属于较大的语言设计变更。

---

### 5.5 更复杂的意图上下文操作 [VISION]

**需求（远期）**：
- intent_context 实例之间的合并策略（`merge_with_priority()`, `intersect()`, `diff()`）
- intent_context 的序列化 / 反序列化（JSON 快照，用于跨进程/持久化场景）
- intent_context 的"冻结"（freeze）模式：创建后不可修改，适合在多个函数间共享

---

## 六、其他功能

### 6.1 LLM 输出持久化 [PENDING]
**任务**：AI 插件支持将 LLM 输出保存到文件。

**搁置原因**：与 IssueTracker 持久化机制配合，属于扩展性功能。

---

### 6.2 子解释器变量深拷贝隔离 [PENDING]
**任务**：实现 `RuntimeContext.inject_variable()` 方法（变量继承已禁用，当前不触发）。

---

## 七、明确排除的设计

| 排除项 | 理由 |
|--------|------|
| 进程级隔离 | 实例级隔离已足够 |
| 核心级 IPC | 通过外部 file 插件实现 |
| GDB 式断点 | DynamicHost 断点是现场保存/恢复/回溯 |
| hot_reload_pools | 违反解释器不修改代码原则 |
| generate_and_run | 动态生成 IBCI 应由显式 IBCI 生成器完成 |
| `LLMExecutorImpl` 作为可替换插件 | 它是语言语义的一部分；provider 可配置，执行接口不可替换 |

---

## 八、架构与基础设施

### 8.1 ImmutableArtifact `__deepcopy__` [PENDING]
**任务**：添加 `__deepcopy__` 方法（不可变对象，深拷贝返回自身）。

**搁置原因**：当前行为可接受，不影响核心功能。

---

### 8.2 MetadataRegistry 双轨统一 [PENDING]
**任务**：解决 `Engine.__init__()` 初始化的 MetadataRegistry（轨 A，内置类型公理）与 `HostInterface` 各自创建的实例（轨 B，插件元数据）并行问题。

**搁置原因**：两轨各有各的查询路径，当前不影响功能。

---

## 九、插件系统

### 9.1 显式引入原则完整实现 [Phase 1 ✅ / Phase 2 ✅ / Phase 3-4 PENDING]
**任务**：严格实现"必须显式 import 才能使用"原则，彻底消除 `discover_all()` 无条件全局注册。

**Phase 1 ✅ 已完成**：`__ibcext_metadata__()` 的 `"kind"` 字段区分 `"method_module"`（工具插件，需显式 import）与 `"type_module"`（内置类型扩展）；`Prelude._init_defaults()` 按 `is_user_defined` 过滤，所有方法插件（`ai`、`math`、`json` 等）不预注入为全局内置符号——用户代码中使用 `ai.xxx` 而未 `import ai` 时，语义分析器会报 "undefined variable" 错误。

**Phase 2 ✅ 已完成（最小实现）**：`discover_all()` 不再在 `Engine.__init__()` 无条件调用。改由 `Engine._ensure_plugins_discovered()` 懒加载：仅在首次 `compile()` / `check()` 调用时执行一次。`Engine.__init__()` 阶段只创建空 `HostInterface()`，不触发任何插件发现。

**Phase 3 PENDING**：明确区分"方法模块"（提供函数调用）和"类型模块"（提供原生类型），完善 `kind` 字段语义。

**Phase 4 PENDING**：Scheduler 符号注入逻辑，标记外部模块符号（区分内置符号与 import 注入符号）。

**文件**：`core/engine.py`（`_ensure_plugins_discovered`）、`core/compiler/semantic/passes/prelude.py`、所有插件 `_spec.py`

---

### 9.2 模块符号去重机制 [PENDING]
**任务**：解决外部模块符号（`import ai` 注入 MODULE 符号 `"ai"`）与用户定义符号（`class ai`）的命名冲突问题。

**根因**：`import ai` 在 Pass 1 之前注入 MODULE 符号，与用户 `class ai` 在 Pass 1 中收集的 CLASS 符号冲突。

---

## 十、llmexcept / retry 机制后续

### 10.1 重试策略配置扩展 [PENDING]
**任务**：在固定次数重试（`ai.set_retry(n)`）基础上，支持指数退避（Exponential Backoff）和条件重试（基于错误类型）。

**文件**：`ibci_modules/ibci_ai/core.py`、`core/runtime/interpreter/handlers/stmt_handler.py`

---

### 10.2 llmexcept body 内外部变量写入约束（SEM_052）[✅ COMPLETED — 2026-04-19]

**完成内容**：
- `core/base/diagnostics/codes.py`：新增 `SEM_LLMEXCEPT_BODY_WRITE = "SEM_052"`
- `semantic_analyzer.py`：添加 `_llmexcept_outer_scope_names: Optional[frozenset]` 字段；
  `visit_IbLLMExceptionalStmt` 进入 body 前通过 `_collect_llmexcept_body_declared_names()` 区分
  body-local 新声明变量与外部作用域变量，并设置外部作用域快照；`visit_IbAssign` 在检测到对外部作用域变量的任何赋值时发出 SEM_052。
- `tests/compiler/test_compiler_pipeline.py`：新增 `TestLLMExceptBodyReadOnly`（6 个测试）覆盖各场景。
- 610 个测试全部通过。

---

### 10.3 `_last_llm_result` 从 RuntimeContext 迁移到 LLMExceptFrame [✅ COMPLETED — 2026-04-19]

**完成内容**：
- `stmt_handler.py`：`visit_IbLLMExceptionalStmt` 中读取 `result` 后立即清零共享字段，并将 `frame.last_result = result` 作为 per-snapshot 权威存储；去除了依赖 `frame.should_retry` 的条件性清零（改为无条件清零）；删除了 `finally` 块中"将 result 恢复回 `_last_llm_result`"的兼容性代码。
- `ibci_idbg/core.py`：`last_result()` 和 `last_llm()` 均改为"优先从活跃帧读取，无帧时回退共享字段"的帧优先模式；`retry_stack()` 替换 `last_llm_response`（始终为 None）为 `last_result` 帧私有字段详情。
- 610 个测试全部通过。

---

## 十一、代码健康（审计遗留）

### 11.1 意图标签解析迁移到 Lexer [P2 / PENDING]
**问题**：`statement.py:278` 的 `#tag` 解析使用 inline `import re` + 正则表达式在 parser 层处理，属于词法层职责被推后到语法层。未来对 tag 做语义分析（如检查 `@- #tag` 中 tag 是否已定义）时会比较困难。

**文件**：`core/compiler/parser/components/statement.py`（约第 278-289 行）

---

### 10.2 engine.py / service.py "vibe" 妥协标注 [P3 - 部分已修复]
**问题**：多处被标注为"智能体快速 vibe 实现，未经严格审查"：
- ~~`engine.py:136`：强制向 service_context 回写 orchestrator（双向引用注入）~~ **[已修复]**：改用 `ServiceContextImpl.set_orchestrator()` 标准注入方法（见 COMPLETED.md §4.16）
- ~~`interpreter.py:229`：`kwargs.get('orchestrator', ...)` 却没有 `**kwargs` 参数~~ **[已修复]**（见 COMPLETED.md §4.16）
- `service.py:173`：`host_run()` 返回值简化为布尔值，隐藏实际结果（等待多返回值语法完善后修复，见 §11.3）
- `rt_scheduler.py:40-44`：`_resolve_builtin_path()` 使用 `ibci_modules.__file__` 动态发现路径（合理但可用常量替代，低优先级）
- `scheduler.py:81`：`compile_to_artifact_dict()` 方法设计合理性存疑

**文件**：`core/runtime/host/service.py`、`core/runtime/rt_scheduler.py`、`core/compiler/scheduler.py`

---

### 11.3 instance_id 默认值碰撞风险 [P3 / PENDING]
**问题**：`interpreter.py:108` `instance_id: str = "main"` 默认值可能导致多解释器实例 ID 碰撞。当前有 `instance_id or f"inst_{id(self)}"` fallback 保护，但 `"main"` 作为默认值仍是潜在隐患。

**文件**：`core/runtime/interpreter/interpreter.py`

---

## 十二、远期架构目标

### 12.1 ibci_ihost / ibci_idbg 标准化重构（Step 4b）[COMPLETED]
**状态**：已完整落地（见 `docs/COMPLETED.md` § 4.12）。`ibci_ihost` 和 `ibci_idbg` 已改为通过 `KernelRegistry` 的稳定钩子接口（`get_host_service()`、`get_stack_inspector()`、`get_state_reader()`）访问服务。用户可见接口（`ihost.run_isolated()` 等）保持不变。517 个测试通过。

### 12.9 OOP × Protocol 边界清理 (P1) [COMPLETED]

**状态说明**：已完整修复（PR-A）。

根本问题：`IIbObject` Protocol 中存在 `@property def descriptor` 幽灵字段，在 Python 3.12 的 `@runtime_checkable` 机制下，该字段导致 `IbObject` 无法结构满足 `IIibObject`，进而引发 `IbBehavior`/`IbIntent`/`AIPlugin` 等被迫显式继承 Protocol 类的补丁链条，以及 5 处 Protocol isinstance 调用、2 处死代码/遗留兼容检查。

**全部修复内容**：
- `core/runtime/interfaces.py`：删除 `IIibObject.descriptor` 幽灵字段
- `core/runtime/objects/builtins.py`：`IbBehavior(IbObject, IIibBehavior)` → `IbBehavior(IbObject)`
- `core/runtime/objects/intent.py`：`IbIntent(IbObject, IntentProtocol)` → `IbIntent(IbObject)`
- `ibci_modules/ibci_ai/core.py`：`AIPlugin(ILLMProvider, IbStatefulPlugin)` → `AIPlugin(IbStatefulPlugin)`
- `stmt_handler.py`/`interpreter.py`/`service.py`/`llm_executor.py`：5 处 Protocol isinstance → 具体实现类 isinstance
- `llm_executor.py`：`_get_llmoutput_hint` 死代码路径修复为 `meta_reg.resolve(type_name)`
- `loader.py`：删除 `isinstance(context.llm_executor, ILLMExecutor)` 遗留兼容检查
- 6 处死 import 全部清理（`expr_handler.py`、`base_handler.py`、`runtime_context.py`、`ibci_idbg/core.py`）

---

### 12.2 IbFunction.call() 去除 context 参数依赖（Step 5）[COMPLETED]
**状态**：已完成（见 `docs/COMPLETED.md`，Step 5 完整路径：5a IExecutionFrame Protocol + 5b ContextVar 帧注册表）。`IbUserFunction.call()` 已通过 `get_current_frame()` 自主获取执行帧，不再依赖外部传入的 context 参数。

---

### 12.3 host.run_isolated() 返回值改进 [VISION]
**当前**：返回简化布尔值。**目标**：多返回值/元组解包语法完整实现后，改为 `tuple(exit_code: int, result: str|dict)`。

---

### 12.4 ReceiveMode 枚举演进 [VISION]
**当前**：`deferred_mode: str` 侧表（`'lambda'`/`'snapshot'`/`None`）。**目标**：迁移至 `ReceiveMode(IMMEDIATE / LAMBDA / SNAPSHOT)` 枚举，替代字符串，支持更严格的类型约束。

---

*本文档记录中长期未来工作。近期任务见 `docs/NEXT_STEPS.md`，已完成工作见 `docs/COMPLETED.md`。*

---

## 十三、类型系统长期演进（TypeRef 重构）

### 13.1 类型系统现状分析 [VISION]

**背景**：当前 `IbSpec.name` 字段同时承担了两个职责：
1. **注册表键**（唯一标识，含泛型参数），如 `"list[int]"`、`"dict[str,int]"`
2. **语义分类标签**（类型族归属），如 `"list"`、`"dict"`

泛型出现后这两个职责产生冲突：`"list[int]".name == "list[int]"` 而非 `"list"`，导致所有直接比较 `.name` 的语义检查对泛型失效（典型案例：`in`/`not in` 运算符的容器类型检查）。

**近期补丁方案（已实施，方案 A）**：
- 所有语义分类检查统一使用 `spec.get_base_name()` 而非 `spec.name`
- 新增 `SpecRegistry.get_base_spec(spec)` 工具方法，将泛型专化 spec 解析回基础 spec
- 约定：`.name` 仅用于 registry key 和 error message；`.get_base_name()` 用于能力查询和语义分类；`isinstance(spec, ListSpec/DictSpec/...)` 用于结构性能力判断

**需要被修复的散布调用点**（已知）：
- `visit_IbCompare`：`.name not in ("str","list","dict","tuple","any")` → 已修复 → `get_base_name()`
- `visit_IbFor`：`iter_type.name != "bool"` → 已修复 → `get_base_name()`
- 其他 `.name` 比较：仅用于 error message 显示，可保留

### 13.2 长期目标：引入 TypeRef 统一类型引用 [VISION]

**设计目标**：实现以下所有"类型内容"的逻辑正交性和设计统一性：

| 类型维度 | 当前表示 | TypeRef 目标表示 |
|---------|---------|----------------|
| 变量本身的类型 | `sym.spec: IbSpec` | `sym.type_ref: TypeRef` |
| 函数返回值类型 | `FuncSpec.return_type_name: str` | `FuncSpec.return_type: TypeRef` |
| 泛型容器自身类型 | `ListSpec.name = "list[int]"` | `TypeRef(base="list", args=[TypeRef("int")])` |
| 泛型容器元素类型 | `ListSpec.element_type_name: str` | `TypeRef.args[0]` |
| 泛型容器嵌套类型 | 无法表达 | `TypeRef(args=[TypeRef(args=[...])])` |
| 泛型下标成员类型 | `resolve_subscript()` 返回字符串 | `TypeRef.args[0]` |
| 类成员类型 | `MemberSpec.type_name: str` | `MemberSpec.type_ref: TypeRef` |
| 迭代器元素类型 | `resolve_iter_element()` 返回字符串 | `TypeRef.args[0]` |
| 表达式类型 | side_table `node_to_type: IbSpec` | side_table `node_to_type: TypeRef` |

**建议的 TypeRef 设计**：
```python
@dataclass(frozen=True)
class TypeRef:
    base_name: str                          # "list", "dict", "int"
    args: Tuple["TypeRef", ...] = ()        # 泛型参数
    module: Optional[str] = None
    nullable: bool = False

    @property
    def canonical_name(self) -> str:        # 注册表键，兼容 IbSpec.name
        if self.args:
            return f"{self.base_name}[{','.join(a.canonical_name for a in self.args)}]"
        return self.base_name

    @property
    def family_name(self) -> str:           # 语义分类，等价于 get_base_name()
        return self.base_name
```

**实施前提**：
- 需与 VM/CPS 调度循环重构一并规划（架构层二）
- 需要修改所有 spec 字段（`FuncSpec`, `ListSpec`, `DictSpec`, `MemberSpec` 等）和序列化层
- 成本极高，应在下一代架构升级时引入，不宜打补丁式渐进

**当前状态**：方案 A（`get_base_name()` + `get_base_spec()`）已落地，为 TypeRef 重构保留接口兼容性。TypeRef 本体在 VM 阶段一并处理。

---

*本文档记录中长期未来工作。近期任务见 `docs/NEXT_STEPS.md`，已完成工作见 `docs/COMPLETED.md`。*
