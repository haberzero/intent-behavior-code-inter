# IBC-Inter 待实现任务清单

> 记录中长期未来工作。近期任务见 `docs/NEXT_STEPS.md`，已完成工作见 `docs/COMPLETED.md`。
>
> **最后更新**：2026-04-18（Steps 1-4b 全部落地；517 个测试通过；11.1 Step 4b [COMPLETED]）

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

### 2.1 Intent 完整公理化 [VISION / FUTURE]
**任务**：创建 `IntentAxiom`，将 Intent 的行为约束纳入公理体系（`is_class()=True`，完整的 vtable）。

**当前状态**：Intent 通过 `Bootstrapper.initialize()` 注册为内置 `ClassSpec`；`IbIntent` 是真正的 `IbObject` 子类；`IntentStack` 已有完整的原生方法注册（`push`/`pop`/`remove`/`clear`）。专用 `IntentAxiom` 是长期目标，不阻塞当前功能。

**工程量**：预估 3-5 人天。

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

## 四、语法功能

### 4.1 (str n) @~ ... ~ 语法完善 [PENDING]
**任务**：验证并完善 callable 闭包参数传递语法，明确其设计语义。

**搁置原因**：手册描述的语法需确认完整实现，闭包参数传递机制需更明确的设计。

---

### 4.2 llmretry 后缀语法澄清 [PENDING]
**任务**：明确 llmretry 后缀的当前实现状态与文档描述是否一致。

**搁置原因**：当前实现为声明式 llmexcept + retry，手册描述的单行后缀语法已被重构。

---

### 4.3 lambda 闭包跨作用域传递语义 [VISION]
**任务**：明确 lambda 作为回调函数跨作用域传递时，参数引用的捕获规则（调用位置变量 vs 定义位置变量）。

**当前策略**：暂不设计跨作用域传递语义，lambda 限制在定义作用域内使用。

---

## 五、其他功能

### 5.1 LLM 输出持久化 [PENDING]
**任务**：AI 插件支持将 LLM 输出保存到文件。

**搁置原因**：与 IssueTracker 持久化机制配合，属于扩展性功能。

---

### 5.2 子解释器变量深拷贝隔离 [PENDING]
**任务**：实现 `RuntimeContext.inject_variable()` 方法（变量继承已禁用，当前不触发）。

---

## 六、明确排除的设计

| 排除项 | 理由 |
|--------|------|
| 进程级隔离 | 实例级隔离已足够 |
| 核心级 IPC | 通过外部 file 插件实现 |
| GDB 式断点 | DynamicHost 断点是现场保存/恢复/回溯 |
| hot_reload_pools | 违反解释器不修改代码原则 |
| generate_and_run | 动态生成 IBCI 应由显式 IBCI 生成器完成 |
| `LLMExecutorImpl` 作为可替换插件 | 它是语言语义的一部分；provider 可配置，执行接口不可替换 |

---

## 七、架构与基础设施

### 7.1 ImmutableArtifact `__deepcopy__` [PENDING]
**任务**：添加 `__deepcopy__` 方法（不可变对象，深拷贝返回自身）。

**搁置原因**：当前行为可接受，不影响核心功能。

---

### 7.2 MetadataRegistry 双轨统一 [PENDING]
**任务**：解决 `Engine.__init__()` 初始化的 MetadataRegistry（轨 A，内置类型公理）与 `HostInterface` 各自创建的实例（轨 B，插件元数据）并行问题。

**搁置原因**：两轨各有各的查询路径，当前不影响功能。

---

## 八、插件系统

### 8.1 显式引入原则完整实现 [PENDING]
**任务**：严格实现"必须显式 import 才能使用"原则，彻底消除 `discover_all()` 无条件全局注册。

**当前问题**：`discover_all()` 在 `Engine.__init__()` 时无条件调用，所有插件元数据被注册到全局 MetadataRegistry，导致 `import ai` 前 `ai` 已是内置符号。

**长期方案**（演进步骤）：
1. **Phase 1**：在 `__ibcext_metadata__()` 返回值中添加 `"kind"` 字段；`Prelude._init_defaults()` 根据 kind 过滤，仅加载真正的内置类型模块（*近期任务，见 `NEXT_STEPS.md`*）
2. **Phase 2**：延迟 `discover_all()` 调用到首次 `import` 时触发
3. **Phase 3**：明确区分"方法模块"（提供函数调用）和"类型模块"（提供原生类型）
4. **Phase 4**：Scheduler 符号注入逻辑，标记外部模块符号

**文件**：`core/engine.py`、`core/compiler/semantic/passes/prelude.py`、所有插件 `_spec.py`

---

### 8.2 模块符号去重机制 [PENDING]
**任务**：解决外部模块符号（`import ai` 注入 MODULE 符号 `"ai"`）与用户定义符号（`class ai`）的命名冲突问题。

**根因**：`import ai` 在 Pass 1 之前注入 MODULE 符号，与用户 `class ai` 在 Pass 1 中收集的 CLASS 符号冲突。

---

## 九、llmexcept / retry 机制后续

### 9.1 重试策略配置扩展 [PENDING]
**任务**：在固定次数重试（`ai.set_retry(n)`）基础上，支持指数退避（Exponential Backoff）和条件重试（基于错误类型）。

**文件**：`ibci_modules/ibci_ai/core.py`、`core/runtime/interpreter/handlers/stmt_handler.py`

---

## 十、代码健康（审计遗留）

### 10.1 意图标签解析迁移到 Lexer [P2 / PENDING]
**问题**：`statement.py:278` 的 `#tag` 解析使用 inline `import re` + 正则表达式在 parser 层处理，属于词法层职责被推后到语法层。未来对 tag 做语义分析（如检查 `@- #tag` 中 tag 是否已定义）时会比较困难。

**文件**：`core/compiler/parser/components/statement.py`（约第 278-289 行）

---

### 10.2 engine.py / service.py "vibe" 妥协标注 [P3 / PENDING]
**问题**：多处被标注为"智能体快速 vibe 实现，未经严格审查"：
- `engine.py:136`：强制向 service_context 回写 orchestrator（双向引用注入）
- `service.py:173`：`host_run()` 返回值简化为布尔值，隐藏实际结果
- `rt_scheduler.py:40-44`：`_resolve_builtin_path()` 使用 `ibci_modules.__file__` 动态发现路径
- `scheduler.py:81`：`compile_to_artifact_dict()` 方法设计合理性存疑

**文件**：`core/engine.py`、`core/runtime/host/service.py`、`core/runtime/rt_scheduler.py`、`core/compiler/scheduler.py`

---

### 10.3 instance_id 默认值碰撞风险 [P3 / PENDING]
**问题**：`interpreter.py:108` `instance_id: str = "main"` 默认值可能导致多解释器实例 ID 碰撞。当前有 `instance_id or f"inst_{id(self)}"` fallback 保护，但 `"main"` 作为默认值仍是潜在隐患。

**文件**：`core/runtime/interpreter/interpreter.py`

---

## 十一、远期架构目标

### 11.1 ibci_ihost / ibci_idbg 标准化重构（Step 4b）[COMPLETED]
**状态**：已完整落地（见 `docs/COMPLETED.md` § 4.12）。`ibci_ihost` 和 `ibci_idbg` 已改为通过 `KernelRegistry` 的稳定钩子接口（`get_host_service()`、`get_stack_inspector()`、`get_state_reader()`）访问服务。用户可见接口（`ihost.run_isolated()` 等）保持不变。517 个测试通过。

### 11.9 OOP × Protocol 边界清理 (P1) [COMPLETED]

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

### 11.9 OOP × Protocol 边界清理 (P1) [COMPLETED]

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

### 11.2 IbFunction.call() 去除 context 参数依赖（Step 5）
**任务**：`IbFunction.call(context, args)` 中的 `context` 外部传入与公理化"对象自洽执行"原则冲突。潜在方案：将"当前活跃 IExecutionContext"注入 KernelRegistry 作为线程本地状态。

**风险**：⚠️ 高风险。未来支持并发解释器或协程式执行时，线程本地存储会产生严重复杂度。**必须先明确解释器并发模型设计后才能推进。**

---

### 11.3 host.run_isolated() 返回值改进 [VISION]
**当前**：返回简化布尔值。**目标**：多返回值/元组解包语法完整实现后，改为 `tuple(exit_code: int, result: str|dict)`。

---

### 11.4 ReceiveMode 枚举演进 [VISION]
**当前**：`deferred_mode: str` 侧表（`'lambda'`/`'snapshot'`/`None`）。**目标**：迁移至 `ReceiveMode(IMMEDIATE / LAMBDA / SNAPSHOT)` 枚举，替代字符串，支持更严格的类型约束。

---

*本文档记录中长期未来工作。近期任务见 `docs/NEXT_STEPS.md`，已完成工作见 `docs/COMPLETED.md`。*
