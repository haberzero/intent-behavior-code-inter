# IBC-Inter 工程演进记录（已完成工作归档）

> 精炼记录各阶段已完成的代码与架构演进，时间线从早期向当前推进。
> **最后更新**：2026-04-29（编译器深度清洁 Phase 1–5 全部落地：C5/C6/C7/C8/C9/C10/C11/C12/C13/C14 完成；CPS dispatch table 覆盖 43 节点；`fallback_visit()` 显式调用归零；`node_protection` 侧表 + `bypass_protection` 参数链 + `_apply_protection_redirect()` + `ControlSignalException` 类全链路删除；`docs/DEFERRED_CLEANUP.md` 与 `URGENT_ISSUES.md` 与 `BUG_REPORTS.md` 已合并归档至本文件并删除原文件；**989 个测试通过**）

---

## 一、类型系统与公理化

### 1.1 Tuple 类型全栈实现
Python `tuple` 原先被错误装箱为 `IbList`。全栈引入 `TupleSpec` + `TUPLE_SPEC` 原型常量 + `SpecFactory.create_tuple()` + `TupleAxiom`（不可变，无 `append`/`pop`/`sort`/`clear`/`__setitem__`）+ `IbTuple`（`elements` 为 Python `tuple`）+ 专用 `_box_tuple` boxer。元组解包赋值同时支持 `IbTuple` 和 `IbList`。
*文件：`core/kernel/spec/specs.py`、`core/kernel/axioms/primitives.py`、`core/runtime/objects/builtins.py`、`core/runtime/bootstrap/builtin_initializer.py`*

### 1.2 类型兼容性方向修复
`is_compatible(target_name)` 语义固定为"source 能否赋值给 target"。修复历史 Bug：父类型不再向下兼容子类型；`BoundMethodAxiom.is_compatible("callable")` 补充为 True；`CallableAxiom` 只与自身兼容。
*文件：`core/kernel/axioms/primitives.py`*

### 1.3 VoidAxiom 替代 DynamicAxiom("void")
`void` 成为具体类型标签（`is_dynamic=False`），无任何 Capability，`is_compatible` 仅匹配自身，表达"无返回值"语义，不与任何其他类型互相赋值。
*文件：`core/kernel/axioms/primitives.py`*

### 1.4 CallableAxiom 替代 DynamicAxiom("callable")
`callable`（`CallableAxiom`，`is_dynamic=False`）作为公理可调用类型层次的抽象根，仅与自身兼容。用户可见语法中 `callable` 关键字同步废弃。
*文件：`core/kernel/axioms/primitives.py`*

### 1.5 DeferredAxiom + DeferredSpec + IbDeferred（通用延迟表达式）
任意表达式（非仅 `@~...~`）均可通过 `lambda`/`snapshot` 关键字延迟执行。`DeferredAxiom` 继承 `CallableAxiom`，`DeferredCallCapability.resolve_return_type_name()` 返回 `"auto"`。
*文件：`core/kernel/spec/specs.py`、`core/kernel/axioms/primitives.py`、`core/runtime/objects/builtins.py`*

### 1.6 BehaviorAxiom + IbBehavior.call() 自主执行（Step 1 + Step 2）
- **Step 1**：`IILLMExecutor` Protocol 定义于 `core/base/interfaces.py`；`KernelRegistry` 新增 `register_llm_executor()` / `get_llm_executor()`；`engine._prepare_interpreter()` 完成 executor 注入。
- **Step 2**：`BehaviorAxiom` 替代 `DynamicAxiom("behavior")`，`is_dynamic=False`；`IbBehavior.call()` 通过 `registry.get_llm_executor().invoke_behavior()` 自主执行；`_execute_behavior()` 旁路从 `BaseHandler` 彻底删除；`visit_IbCall` 的 behavior 特殊路由删除。

*文件：`core/base/interfaces.py`、`core/kernel/registry.py`、`core/kernel/axioms/primitives.py`、`core/runtime/objects/builtins.py`、`core/engine.py`、`core/runtime/interpreter/handlers/`*

### 1.7 BehaviorSpec(return_type_name) 编译期类型推断
`BehaviorSpec`（继承 `DeferredSpec`）持有 `value_type_name`。语义分析器对 `int lambda f = @~...~` 创建带类型的 BehaviorSpec；序列化/反序列化路径完整保留该字段；运行时通过 `push_expected_type()` 精确解析。
*文件：`core/kernel/spec/specs.py`、`core/compiler/semantic/passes/semantic_analyzer.py`、`core/compiler/serialization/serializer.py`、`core/runtime/loader/artifact_rehydrator.py`*

### 1.8 ibci_ai 职责拆分（Step 3a）
`LLMExecutorImpl.llm_callback` 唯一来源变为 `capability_registry.get("llm_provider")`，彻底移除 `interop.get_package("ai")` fallback。`ibci_ai.setup()` 通过 `capabilities.expose("llm_provider", self)` 注入。
*文件：`core/runtime/interpreter/llm_executor.py`、`ibci_modules/ibci_ai/core.py`*

### 1.9 IbLLMFunction 自主执行（Step 4a）
`IbLLMFunction.call()` 通过 `registry.get_llm_executor().invoke_llm_function(self, ctx)` 执行，不再持有 `llm_executor` 引用。`IILLMExecutor` 新增 `invoke_llm_function()` 方法。
*文件：`core/runtime/objects/kernel.py`、`core/base/interfaces.py`、`core/runtime/interpreter/llm_executor.py`*

---

## 二、语法与编译器

### 2.1 lambda / snapshot 关键字引入，callable 用户可见关键字废弃
`callable` 从用户语法中移除，替换为 `lambda`（使用调用时意图栈）和 `snapshot`（捕获定义时意图栈）。`deferred_mode` 侧表记录模式，语义分析器根据 LHS 类型和 `deferred_mode` 推断 `behavior`/`deferred` 类型。
*文件：`core/compiler/common/tokens.py`、`core/compiler/lexer/core_scanner.py`、`core/compiler/parser/components/declaration.py`、`core/compiler/semantic/passes/semantic_analyzer.py`、`core/kernel/ast.py`、`core/compiler/semantic/passes/side_table.py`*

### 2.2 (Type) @~...~ 提示词注入废弃（PAR_010 硬错误）
`(Type) @~...~` 在 parser 层发出 PAR_010 硬错误。LHS 类型自动成为 LLM 输出格式的提示词上下文，无需额外语法。
*文件：`core/compiler/parser/components/expression.py`*

### 2.3 behavior_expression() STRING token 修复
`@~...~` 内的引号字符串不再被静默丢弃，正确保留并追加到 segments（修复了 `MOCK:["a","b","c"]` → `MOCK:[,,]` 的 Bug）。
*文件：`core/compiler/parser/components/expression.py`*

### 2.4 llmexcept 嵌套块绑定修复
`_bind_llm_except()` 现在递归进入 `IbFor`/`IbIf`/`IbWhile`/`IbTry`/`IbSwitch` 的 body，修复了循环/条件体内 llmexcept 静默失效的 Bug。
*文件：`core/compiler/semantic/passes/semantic_analyzer.py`*

### 2.5 for 循环条件 + llmexcept 语义修复
`_bind_llm_except_in_body()` 识别条件驱动 for 循环（`target=None`），将保护绑定到 `iter_uid`（条件表达式），而非整个 for 节点。`visit_IbLLMExceptionalStmt` 返回 target 执行结果，正确透传条件值。
*文件：`core/compiler/semantic/passes/semantic_analyzer.py`、`core/runtime/interpreter/handlers/stmt_handler.py`*

### 2.6 behavior 类型名硬编码消除
`semantic_analyzer.py visit_IbFor` 的 `"behavior"` 字符串直接比较替换为 `SpecRegistry.is_behavior()` 方法。
*文件：`core/kernel/spec/registry.py`、`core/compiler/semantic/passes/semantic_analyzer.py`*

---

## 三、LLM 执行 & 异常处理

### 3.1 MOCK:FAIL 哨兵修复
`"MAYBE_YES_MAYBE_NO_this_is_ambiguous"` 在 `_parse_result()` 之前被检测并返回 `LLMResult.uncertain_result()`，修复了其被 `StrAxiom.from_prompt()` 成功装箱、导致 llmexcept 不触发的 Bug。
*文件：`core/runtime/interpreter/llm_executor.py`*

### 3.2 IbBehavior call_intent 传播修复
`IbBehavior` 新增 `call_intent` 字段。`create_behavior()` 工厂方法更新签名，延迟执行路径正确传入 `call_intent`。序列化/反序列化路径同步更新。
*文件：`core/runtime/factory.py`、`core/runtime/interfaces.py`、`core/runtime/interpreter/handlers/expr_handler.py`、`core/runtime/serialization/runtime_serializer.py`*

### 3.3 重试诊断日志
`visit_IbLLMExceptionalStmt` 重试循环中新增 `debugger.trace()` 调用（进入帧、每次迭代、正常退出、UNCERTAIN 预览、重试耗尽），`CoreModule.INTERPRETER` 频道输出，生产运行无影响。
*文件：`core/runtime/interpreter/handlers/stmt_handler.py`*

### 3.4 IbTuple 序列化/快照集成
`llm_except_frame._is_serializable()` 和 `runtime_serializer.py` 的序列化/反序列化路径均添加 `"tuple"` 分支（cache-before-recurse 模式，与 IbList 对称）。
*文件：`core/runtime/interpreter/llm_except_frame.py`、`core/runtime/serialization/runtime_serializer.py`*

### 3.5 max_retry 配置穿透（ai.set_retry()）
`visit_IbLLMExceptionalStmt` 通过 `capability_registry.get("llm_provider").get_retry()` 读取 max_retry，使 `ai.set_retry(n)` 配置正确穿透到重试循环。
*文件：`core/runtime/interpreter/handlers/stmt_handler.py`、`ibci_modules/ibci_ai/core.py`*

---

## 四、代码健康 & 架构清理

### 4.1 OOP×Protocol 边界清理 PR-A（IbObject 子类单继承化）
删除 `IIbObject.descriptor` 幽灵字段；将 `IbBehavior`、`IbIntent`、`AIPlugin` 的多余 Protocol 显式继承移除为单继承；全部 Protocol `isinstance` 调用点替换为具体类（`IbBehavior`/`IbIntent`/`IbObject`）；修复 `_get_llmoutput_hint` 第二路径死代码（`getattr(ib_class, 'descriptor', None)` → `meta_reg.resolve(type_name)`）；删除全部悬挂死 import（`IIibBehavior`、`IIibIntent`、`IIibObject` TYPE_CHECKING 块）。
*文件：`core/runtime/interfaces.py`、`core/runtime/objects/builtins.py`、`core/runtime/objects/intent.py`、`ibci_modules/ibci_ai/core.py`、`core/runtime/interpreter/handlers/`、`core/runtime/interpreter/llm_executor.py`、`core/runtime/module_system/loader.py`*

### 4.2 Impl 类 Protocol 继承清理（PR-B）
6 个 Impl 类移除对 Protocol 接口的直接继承（Python `@runtime_checkable` 卫生清理）：`ExecutionContextImpl`、`SymbolViewImpl`、`RuntimeContextImpl`、`ModuleManagerImpl`、`InterOpImpl`、`ServiceContextImpl`。对外 API 零破坏。
*文件：`core/runtime/interpreter/execution_context.py`、`runtime_context.py`、`module_manager.py`、`interop.py`、`service_context.py`*

### 4.3 调度器 import 注入冲突日志
`_inject_plugin_symbols` 静默 `pass` 替换为 `debugger.trace()` 调用，调试模式下符号冲突可见。
*文件：`core/compiler/scheduler.py`*

### 4.4 技术债清理
- `collector.py`：删除 `"llm_fallback"` 无效属性遍历
- `runtime_context.py`：清理 5 处过期 TODO 注释
- `interop.py`：Protocol 继承 TODO 替换为解释性注释

### 4.5 ibci_file 文档分类修正
`ibci_file` 重新归类为"非侵入式（轻量依赖型）"，`ibcext.py` 注释和 `ARCHITECTURE_PRINCIPLES.md` 插件表格同步更新。

### 4.6 Mock 仿真引擎完善
`MOCK:FAIL` / `MOCK:REPAIR` / `MOCK:INT:n` / `MOCK:STR:text` / `MOCK:FLOAT:n` / `MOCK:["..."]` 等指令全部正确实现。`MOCK:REPAIR` 按调用点独立计数，`reset_mock_state()` 支持测试隔离。
*文件：`ibci_modules/ibci_ai/core.py`*

### 4.7 vtable callable 签名自动提取
`discovery.py` 的 `_extract_signature()` 通过 `inspect.signature()` 自动提取 `__ibcext_vtable__()` callable 条目签名，转换为 `MethodMemberSpec`。
*文件：`core/runtime/module_system/discovery.py`*

### 4.8 ibci_isys v2.0
`ibci_sys` 合并进 `ibci_isys`，新增 `sys.script_dir()`、`sys.script_path()` 等 IBCI 路径 API。
*文件：`ibci_modules/ibci_isys/`*

### 4.9 llmexcept 循环迭代器状态完整恢复
`LLMExceptFrame` 新增 `loop_resume: Dict[str, int]` 字段，由 `visit_IbFor` 在每次迭代开始时动态更新（写入当前节点 UID → 当前索引的映射）。`restore_context()` 故意不重置 `loop_resume`，使 retry 后 for 循环从失败的迭代索引处继续，而非从头开始。同时修复 `save_context()` 中 `_loop_stack` 浅拷贝：改为深拷贝 dict 对象，确保快照与运行时状态完全独立。
*文件：`core/runtime/interpreter/llm_except_frame.py`、`core/runtime/interpreter/handlers/stmt_handler.py`*

### 4.10 显式引入原则 Phase 1：插件 kind 字段
所有 10 个 `ibci_modules/*/` `_spec.py` 文件的 `__ibcext_metadata__()` 新增 `"kind": "method_module"` 字段。`discovery._load_spec()` 读取该字段，并对 `method_module` 类型的插件将生成的 `ModuleSpec.is_user_defined` 设为 `True`。`Prelude._init_defaults()` 已有的 `not is_user_defined` 过滤逻辑因此生效：`ai`、`math`、`json` 等插件模块不再被预注入为全局内置符号，必须通过显式 `import` 才能使用。`type_module` 类别保留给未来的内置类型扩展插件（当前无）。
*文件：`ibci_modules/ibci_{ai,math,json,net,time,schema,file,idbg,ihost,isys}/_spec.py`、`core/runtime/module_system/discovery.py`*

### 4.11 嵌套 llmexcept 系统性集成测试
新增 `TestE2ELLMExceptNested` 测试类，包含三个场景：① 外层/内层 llmexcept 独立重试互不干扰；② 内层 LLM 恢复后外层代码正常继续；③ 内层重试耗尽后，后续普通赋值不被 `IbLLMUncertain` 污染。全部 500 测试通过。
*文件：`tests/e2e/test_e2e_ai_mock.py`*

### 4.12 ibci_ihost / ibci_idbg KernelRegistry 标准化（Step 4b）
将 `ibci_ihost` 和 `ibci_idbg` 两个核心层插件从直接访问内核内部结构迁移为通过 `KernelRegistry` 稳定钩子接口访问，与 `IbBehavior.call()` / `IbLLMFunction.call()` 的公理化自主执行模式一致：
- **`core/base/interfaces.py`**：扩展 `IStateReader` Protocol，新增 `get_vars()`、`get_active_intents()`、`get_last_llm_result()`、`get_llm_except_frames()` 方法签名。
- **`core/runtime/interpreter/runtime_context.py`**：`RuntimeContextImpl` 新增 `get_llm_except_frames()` 方法（返回 `_llm_except_frames` 副本），消除插件对私有属性的直接访问。
- **`core/kernel/registry.py`**：新增 `_host_service`、`_stack_inspector`、`_state_reader` 三个字段及对应 `register_host_service()` / `get_host_service()`、`register_stack_inspector()` / `get_stack_inspector()`、`register_state_reader()` / `get_state_reader()` 六个方法；`clone()` 同步复制新字段。
- **`core/extension/capabilities.py`**：`PluginCapabilities` 新增 `kernel_registry` property，暴露 `_registry` 引用供核心层插件访问稳定钩子。
- **`core/engine.py`**：`_prepare_interpreter()` 在注册 `llm_executor` 之后，同步将 `host_service`、`stack_inspector`（`execution_context.stack_inspector`）、`state_reader`（`runtime_context`）注册到 `KernelRegistry`。
- **`ibci_modules/ibci_ihost/core.py`**：`_host_service()` 辅助方法改为 `capabilities.kernel_registry.get_host_service()`，删除对 `capabilities.service_context.host_service` 的直接访问。
- **`ibci_modules/ibci_idbg/core.py`**：`setup()` 不再存储 `stack_inspector`/`state_reader` 实例，改为存储 `_kr`（KernelRegistry）和 `_cap_registry`（CapabilityRegistry）；所有方法通过 `self._kr.get_stack_inspector()` / `get_state_reader()` / `get_llm_executor()` 懒获取服务；`llm_provider` 通过 `self._cap_registry.get("llm_provider")` 访问；`protection_map()` TODO 注释精简。
*全部 517 个测试通过。*

### 4.13 Step 6c：RuntimeContextImpl 意图字段完整迁移
`RuntimeContextImpl` 的四个意图相关私有字段（`_intent_top`、`_pending_smear_intents`、`_pending_override_intent`、`_global_intents`）全部迁移至 `IbIntentContext._intent_ctx` 字段持有：
- `RuntimeContextImpl` 保留 `intent_context` 属性直接返回 `_intent_ctx` 实例。
- `push_intent()` / `pop_intent()` / `remove_intent()` 全部委托至 `_intent_ctx.push/pop/remove()`。
- `get_global_intents()` / `set_global_intent()` / `clear_global_intents()` / `remove_global_intent()` 全部委托至 `_intent_ctx` 的 `get/set_global_intents()` 系列方法。
- `fork_intent_snapshot()` 现在返回 `IbIntentContext` 值快照（`_intent_ctx.fork()`），不再返回裸 `IntentNode` 引用。
- `intent_stack` property getter/setter 改为通过 `_intent_ctx.get_intent_top()` / `set_intent_top()` 操作，保持与外部调用者的兼容性。
- `get_resolved_prompt_intents()` 改为委托 `_intent_ctx` 的 smear/override/active/global 系列方法。
- 私有帮助方法 `_remove_by_tag()` / `_remove_by_content()` / `_invalidate_cache_up_to_root()` 从 RuntimeContextImpl 删除，移入 `IbIntentContext`。
- `IbIntentContext` 新增：`remove(tag, content)`、`get_intent_top()`、`set_intent_top()` 以及完整的私有移除和缓存无效化逻辑。
- `IbIntentContext` 删除：`consume_smear_snapshot()` 和 `get_override_snapshot()` 两个已无调用者的旧兼容方法。
*文件：`core/runtime/objects/intent_context.py`、`core/runtime/interpreter/runtime_context.py`*

### 4.14 Step 6d：LLMExceptFrame 意图快照清洁化
`LLMExceptFrame` 中的 `saved_intent_stack` 字段（裸 `IntentNode` 引用）完整删除，仅保留 `saved_intent_ctx`（`IbIntentContext` fork 值快照）：
- `save_context()` 直接调用 `runtime_context.intent_context.fork()`，无任何分支备注和后备路径。
- `restore_context()` 直接调用 `runtime_context.intent_context.merge(saved_intent_ctx)`，无 `elif` 旧路备份。
- 类文档字符串更新，删除 `saved_intent_stack` 字段说明和 TODO。
*文件：`core/runtime/interpreter/llm_except_frame.py`*

### 4.15 Step 7b：LlmCallResultAxiom + IbLLMCallResult 全链路公理化接入
- **`LlmCallResultAxiom`**：在 `core/kernel/axioms/primitives.py` 新增 `LlmCallResultAxiom`（`@property name = "llm_call_result"`），`register_core_axioms()` 末尾注册。
- **`LLM_CALL_RESULT_SPEC`**：在 `core/kernel/spec/specs.py` 新增 `LLM_CALL_RESULT_SPEC = IbSpec(name="llm_call_result", ...)`，在 `create_default_spec_registry()` 中注册，确保 `initialize_builtin_classes()` 启动时创建对应 `IbClass`。导出至 `core/kernel/spec/__init__.py`。
- **`set_last_llm_result()` 自动转换**：`RuntimeContextImpl.set_last_llm_result()` 现在接受 `LLMResult`（内部 Python dataclass）或 `IbLLMCallResult`（IBCI 对象），遇到 `LLMResult` 时自动转换为 `IbLLMCallResult` 后存储。`get_last_llm_result()` 只返回 `IbLLMCallResult`。
- **读取端全面迁移**：`stmt_handler.py` 中所有 6 处 `result.is_uncertain` 改为 `not result.is_certain`；`ibci_idbg/core.py` 中 `get_last_call_info()` 和 `last_result()` 两处 `res.is_uncertain` / `res.success` / `res.value` / `res.error_message` 全部适配 `IbLLMCallResult` 字段（`is_certain`、`result_value`、`retry_hint`）。
*文件：`core/kernel/axioms/primitives.py`、`core/kernel/spec/specs.py`、`core/kernel/spec/registry.py`、`core/kernel/spec/__init__.py`、`core/runtime/interpreter/runtime_context.py`、`core/runtime/interpreter/handlers/stmt_handler.py`、`ibci_modules/ibci_idbg/core.py`*

### 4.16 Vibe 代码债务清理
修复以下被标注为"vibe 快速实现"或历史遗留的代码问题：
- **`interpreter.py:229` kwargs bug**：`orchestrator=kwargs.get('orchestrator', None) if 'kwargs' in locals() else None` 改为直接引用显式参数 `orchestrator=orchestrator`（`**kwargs` 从未存在于该签名）。
- **`engine.py` orchestrator 注入**：删除 `TODO: 怀疑有vibe带来的异味` 注释；使用新增的 `ServiceContextImpl.set_orchestrator()` 方法替代直接写入私有字段 `_orchestrator`；`host_service.orchestrator` 旁路注入已内化到 `set_orchestrator()` 实现中。
- **`ServiceContextImpl.set_orchestrator()`**：新增标准化注入方法，内聚 orchestrator + host_service 双向更新逻辑。
*文件：`core/runtime/interpreter/interpreter.py`、`core/engine.py`、`core/runtime/interpreter/service_context.py`*

### 4.17 Step 8-pre：llmexcept 快照隔离约束完整落地（§9.2 + §9.3）

#### §9.2：llmexcept body 编译期 read-only 约束（SEM_052）
- **`core/base/diagnostics/codes.py`**：新增 `SEM_LLMEXCEPT_BODY_WRITE = "SEM_052"` 错误码。
- **`core/compiler/semantic/passes/semantic_analyzer.py`**：
  - 新增 `_llmexcept_outer_scope_names: Optional[frozenset]` 字段（初始为 `None`），在进入 llmexcept body 时设置，离开时恢复。
  - 新增 `_collect_llmexcept_body_declared_names(body)` 辅助方法：利用 `LocalSymbolCollector`（Pass 2.5）预扫描时写入的 `def_node` 信息，区分 body-local 新声明变量（`def_node is stmt`）与外部作用域变量的重声明（`def_node is not stmt`），只将前者加入排除集合。
  - `visit_IbLLMExceptionalStmt` 在进入 body 前，以"所有已知符号名 - body-local 新声明名"为外部作用域快照（`_llmexcept_outer_scope_names`），在离开时通过 `try/finally` 恢复（支持嵌套 llmexcept 正确工作）。
  - `visit_IbAssign` 新增前置检查：若 `_llmexcept_outer_scope_names` 不为 `None` 且目标变量名在外部作用域集合中，发出 SEM_052 错误（无论是否带类型标注）。
- **`tests/compiler/test_compiler_pipeline.py`**：新增 `TestLLMExceptBodyReadOnly`（6 个测试）：直接赋值到外部变量、用类型标注重声明外部变量（均应报 SEM_052）；声明全新局部变量、使用 retry 语句、读取外部变量、对整型外部变量写入（前三者允许，最后一个 SEM_052）。

#### §9.3：`_last_llm_result` per-snapshot 化
- **`core/runtime/interpreter/handlers/stmt_handler.py`**：`visit_IbLLMExceptionalStmt` 中每次迭代无条件清零 `_last_llm_result`（进入快照前清零）；读取 LLM 结果后立即再次清零（不再等 body 执行完）；删除 `try/finally` 块中的"恢复兼容性"代码。`LLMExceptFrame.last_result` 成为 per-snapshot 权威来源。
- **`ibci_modules/ibci_idbg/core.py`**：
  - `last_result()`：改为"优先从活跃 llmexcept 帧读取（`frames[-1].last_result`），无帧时回退共享字段"的帧优先模式，移除旧注释"临时清空说明"。
  - `last_llm()`：同样改为帧优先模式获取 `res`，移除嵌套 if/else 链。
  - `retry_stack()`：将 `last_llm_response`（始终为 `None` 的死字段）替换为 `last_result` 字段，包含 `is_certain`、`raw_response`（前 120 字符）、`retry_hint` 三个子字段。

*全部 610 个测试通过。*


---

#### §9.4：函数调用意图隔离（fork/restore）与显式作用域控制 API

**问题**：函数调用时意图上下文是引用传递（直接共享），函数内 `@+`/`@-` 操作影响调用者；函数内部没有显式 API 来屏蔽/替换继承自调用者的意图。

**修复内容（2026-04-19，580 测试通过）**：

- **`core/runtime/objects/kernel.py`**：`IbUserFunction.call()` 和 `IbLLMFunction.call()` 在函数执行前后实现意图上下文 fork/restore：
  - 统一采用 **fork 拷贝传递**：`child_ctx = old_intent_ctx.fork()`
  - `try/finally` 确保调用者上下文始终恢复

- **`core/runtime/bootstrap/builtin_initializer.py`**：在 `intent_context` 类上注册三个作用域控制方法：
  - `clear_inherited()` — 清空当前帧 `_intent_ctx._intent_top`（清除继承的持久意图栈）
  - `use(ctx)` — 用 `ctx._ctx.fork()` 替换当前帧的 `_intent_ctx`（保留全局意图）
  - `get_current()` — 返回当前帧 `_intent_ctx.fork()` 的新 `intent_context` 实例
  - 三个方法均通过 `get_current_frame()` ContextVar 访问当前执行帧，类调用/实例调用效果相同

- **`core/kernel/axioms/intent_context.py`**：`get_method_specs()` 新增 `clear_inherited`、`use`、`get_current` 三个方法规格

- **`core/compiler/semantic/passes/semantic_analyzer.py`**：`_validate_intent_in_body()` 保持原语义：`@` 和 `@!` 均只能修饰 LLM 行为表达式（`@~...~`）；**不允许** `@!` 修饰普通函数调用（此前错误实现的功能已回退）

- **lambda 参数传递约束**（同批次）：`IbUserFunction.call()` 检测到 `deferred_mode='lambda'` 的 `IbDeferred`/`IbBehavior` 实参时，抛出 `RUN_CALL_ERROR`

#### §9.5：intent_context OOP MVP

**需求**：允许 IBCI 用户代码显式创建和操作意图上下文对象：`intent_context ctx = intent_context()`。

**实现内容（2026-04-19）**：

- **`core/kernel/axioms/intent_context.py`**：`IntentContextAxiom.is_class()` → `True`；`get_method_specs()` 新增 `clear`、`clear_inherited`、`use`、`get_current` 方法规格
- **`core/kernel/spec/specs.py`**：新增 `INTENT_CONTEXT_SPEC = ClassSpec(name="intent_context", ...)`
- **`core/kernel/spec/registry.py`**：`INTENT_CONTEXT_SPEC` 加入 `create_default_spec_registry()` 注册列表和 import
- **`core/runtime/bootstrap/builtin_initializer.py`**：注册 `intent_context` 类的所有原生方法：
  - 实例方法：`__init__`、`push`、`pop`、`fork`、`resolve`、`merge`、`clear`
  - 作用域控制（类/实例均可调用）：`clear_inherited`、`use`、`get_current`
- **11 个新测试**（含 4 个 `TestE2EIntentScopeIsolation`、4 个 `TestE2EIntentContextOOP`、1 个 `TestE2ELambdaRestriction`）

*全部 610 个测试通过。*

---

## 四b、Bug 修复（2026-04-20，610 测试通过）

### 4b.1 IbBool(False) / IbInteger(0) 假值误判（Bug #1）
`result.value if result and result.value else registry.get_none()` 中 `bool(IbBool(False))` 为 Python `False`，导致 LLM 返回 `false`/`0` 时误替换为 `IbNone`，变量赋值时报 `Type mismatch`。  
**修复**：三处全改为 `result is not None and result.value is not None`。  
*文件：`core/runtime/interpreter/handlers/expr_handler.py`，`core/runtime/interpreter/llm_executor.py`*

### 4b.2 重复 `_stmt_contains_behavior` 覆盖正确实现（Bug #2）
同一方法在 `semantic_analyzer.py` 中被定义两次：第 276 行正确版含 `IbIf`/`IbWhile`/`IbFor` 分支；第 1130 行 AI Agent 遗留版仅处理 `IbExprStmt`/`IbAssign`/`IbReturn`。Python 类后定义覆盖前定义，导致 `llmexcept` 跟在 `if/while/for @~...~:` 后时总报 SEM_050。  
**修复**：删除 1130–1141 行残缺重复实现。  
*文件：`core/compiler/semantic/passes/semantic_analyzer.py`*

### 4b.3 list[str] / dict[K,V] 泛型专化崩溃（Bug #3，含三处子修复）
1. `semantic_analyzer.py:_resolve_type` 调用不存在的 `IbSpec.resolve_specialization()`，应为 `self.registry.resolve_specialization()`。
2. `SpecRegistry.resolve_specialization()` 的 `hasattr` 检查错误（`"resolve_specialization"` 而非 `"resolve_specialization_by_names"`），导致始终返回 `None`。
3. 新注册的专化 Spec 在 `_bootstrap_axiom_methods()` 之后创建，未自动填充方法成员；`resolve_specialization` 修复后同步使用 `axiom.get_method_specs()` 补全成员。  
**修复**：三处联合修复；`list[str]`、`dict[str,int]`、`tuple[int]` 等泛型标注全部可用，含字面量赋值、行为表达式、方法调用、for 迭代。  
*文件：`core/compiler/semantic/passes/semantic_analyzer.py`，`core/kernel/spec/registry.py`*

---

## 五、确认的设计决策

| 决策 | 说明 |
|------|------|
| `@~...~` 独立于 `import ai` | 行为描述是语言核心特性；`import ai` 仅配置 LLM provider |
| 公理层次 `callable → deferred → behavior` | 三级继承，全部 `is_dynamic=False` |
| `is_compatible()` 方向原则 | 子类型向上声明兼容，父类型不向下兼容子类型 |
| `void` 独立语义 | 不与任何具体类型互相赋值；表达无返回值 |
| `lambda` vs `snapshot` | lambda 使用调用时意图栈；snapshot 捕获定义时意图栈快照 |
| `llmexcept` 边界语义 | sibling 保护条件表达式；body-nested 保护循环体内语句 |
| `llmexcept` body 只读约束 | body 内禁止写入快照外的外部变量（SEM_052 编译期错误）；body-local 新声明和 retry 语句允许 |
| `_last_llm_result` per-snapshot | 读取后立即清零共享字段；`LLMExceptFrame.last_result` 为 per-snapshot 权威来源 |
| `(Type) @~...~` 废弃 | PAR_010 硬错误；LHS 类型自动成为提示词上下文 |
| 彻底重构原则 | 禁止渐进式补丁；完成则完整，不留旁路 |
| `LLMExecutorImpl` 不可替换 | 它是语言语义的一部分，provider 可配置，执行接口不可替换 |
| 函数调用意图：拷贝传递 | 每次函数调用 fork 调用者意图上下文；函数内意图操作不泄漏（§9.4） |
| `@!` 只修饰 LLM 调用 | `@!` 只能修饰 LLM 行为表达式（`@~...~`），不能修饰普通函数调用 |
| 函数内意图控制显式 API | `intent_context.clear_inherited()`/`use(ctx)`/`get_current()` 作用于当前帧意图上下文（§9.4/§9.5） |
| `lambda` 不允许作为参数传递 | lambda 延迟对象（`IbDeferred`/`IbBehavior`）不可作为函数实参；`snapshot` 不受此限制 |
| `snapshot` 捕获意图快照 | `snapshot` 在定义位置调用 `fork_intent_snapshot()` 捕获当前意图栈的不可变副本 |
| `intent_context` is_class=True | `intent_context` 可实例化为 OOP 对象；用户可显式管理意图上下文（§9.5） |
| `:` 是 lambda/snapshot 唯一有效体起始符 | 括号体形式（`lambda(EXPR)`、`lambda(PARAMS)(EXPR)`）已移除；`lambda: EXPR` / `lambda(PARAMS): EXPR` 为规范 |
| 旧 `TYPE lambda/snapshot NAME = EXPR` 声明语法移除 | 产生 parse error（非废弃警告），彻底不兼容 |

---

## 六、M1：fn/lambda/snapshot 全新语法落地 [✅ COMPLETED — 2026-04-28]

**前提**：Step 8 + IbCell 奠基（已具备）  
**测试基线**：758 个测试通过（较 M1 前 678 增加 80 个）

### 6.1 IbCell 原语奠基（M1 前置）

`IbCell` 基础原语先行落地：

- **`core/runtime/objects/cell.py`**（新建）：纯 VM 容器（非 `IbObject`），`get()/set(v)/is_empty()/trace_refs()`，身份语义（`__eq__`/`__hash__` 基于 id），`IbCell.EMPTY` 哨兵，读取未初始化单元抛出 `RuntimeError`。
- **`tests/runtime/test_ib_cell.py`**：18 个单元测试，无现有路径行为变化。

### 6.2 表达式语法：lambda/snapshot 冒号强制 body-start

`core/compiler/parser/components/expression.py` 的 `lambda_expr`/`snapshot_expr`：

- `:` 是**唯一**有效的 body 起始符（原括号体形式已移除）
- 8 种合法形式：`lambda: EXPR`、`lambda -> TYPE: EXPR`、`lambda(PARAMS): EXPR`、`lambda(PARAMS) -> TYPE: EXPR`（snapshot 对称）
- 旧括号体形式（`lambda(EXPR)`、`lambda(PARAMS)(EXPR)`）产生 `PAR_002` parse error
- `IbLambdaExpr.returns` 字段持有可选返回类型标注节点；语义阶段通过 `side_table.bind_type` 将返回类型绑定到 body `IbBehaviorExpr`，修复 LLM executor `_get_expected_type_hint` 的类型推断

### 6.3 声明语法：移除旧 `TYPE lambda NAME = EXPR` 形式

`core/compiler/parser/components/declaration.py`：

- 移除 `variable_declaration` 中所有 3 处 `deferred_mode` 检测块（`auto`/`fn`/显式类型 三个分支）
- 移除 `deferred_mode = None` 初始化
- `IbAssign(deferred_mode=...)` 参数移除，`deferred_mode` 字段不再由 parser 设置为非 `None`
- 旧声明语法（`int lambda f = ...`、`auto snapshot g = ...`、`fn lambda h = ...`）现在因后跟 `lambda`/`snapshot` 关键字无法匹配 `IDENTIFIER`，产生 parse error

### 6.4 语义分析：移除 deferred_mode 路径 + 新增 IbLambdaExpr 分析

`core/compiler/semantic/passes/semantic_analyzer.py`：

- `visit_IbAssign` 中两处 `deferred_mode = getattr(node, 'deferred_mode', None)` 及全部依赖分支删除：
  - `fn lambda / fn snapshot` 分支
  - `auto lambda / auto snapshot` 分支
  - `elif deferred_mode:` 显式类型延迟分支
  - behavior 表达式的 `if deferred_mode:` 分支
  - 通用表达式的 `elif deferred_mode and node.value:` 分支
- `visit_IbLambdaExpr`：push 局部 SymbolTable 注册形参；分析自由变量（`_collect_free_refs`）；处理 `-> TYPE` 返回类型标注（`bind_type` 到 body）

### 6.5 运行时：IbDeferred/IbBehavior 参数化 + IbCell 闭包

`core/runtime/objects/builtins.py`：

- `IbDeferred.__init__(params, body_node, deferred_mode, captured_scope)` 支持参数列表
- `IbBehavior.__init__(params, body_node, deferred_mode, captured_scope/closure)` 同步
- **lambda 闭包语义**：持有 `captured_scope` 引用（自由变量读取最新值），不缓存
- **snapshot 闭包语义**：持有 `closure: Dict[sym_uid, (name, IbCell(value))]`，定义时值拷贝；调用时按 `sym_uid` 在子作用域 `define_variable(name, val, uid=sym_uid)` 重登记，IbName UID-lookup 命中本地副本

`core/runtime/interpreter/handlers/expr_handler.py`：

- `visit_IbLambdaExpr`：构建 `IbDeferred` (普通 body) 或 `IbBehavior` (IbBehaviorExpr body)；snapshot 模式调用 `_collect_free_refs` + `IbCell` 值拷贝；lambda 模式仅传递 `captured_scope`
- `_collect_free_refs`：扫描 lambda/snapshot 体内的 `IbName` 节点，按 `sym_uid` 区分自由变量与局部变量

### 6.6 测试覆盖

| 测试文件 | 测试类 | 覆盖场景 |
|----------|--------|---------|
| `tests/e2e/test_e2e_fn_lambda_syntax.py` | `TestFnLambdaColonSyntax` | 8 种冒号形式正确执行 |
| | `TestFnLambdaReturnType` | `-> TYPE` 标注；类型不匹配 SEM_003 |
| | `TestFnLambdaParams` | 带参数 lambda/snapshot；参数传递 |
| | `TestFnLambdaClosures` | lambda 闭包读最新值；snapshot 闭包冻结值 |
| | `TestFnSnapshotIntentIsolation` | snapshot 意图隔离；lambda 意图敏感 |
| | `TestFnLambdaBackwardCompat` | 旧语法断言 parse error（不兼容） |
| | `TestFnLambdaErrors` | 旧括号体语法 parse error；lambda 不可作参数 |
| `tests/e2e/test_e2e_deferred.py` | — | deferred 调用、fn 持有 lambda 引用 |
| `tests/e2e/test_e2e_ai_mock.py` | — | lambda/snapshot + behavior 表达式；deferred 传参 |
| `tests/compiler/test_compiler_pipeline.py` | `TestBehaviorDeferred` | 新语法编译期通过 |


---

## 七、M2：IbCell GC 根集合 + 词法作用域正式化 [✅ COMPLETED — 2026-04-28]

**前提**：M1（已具备）  
**测试基线**：776 个测试通过（较 M2 前 758 增加 18 个）

### 7.1 ScopeImpl Cell 变量提升（公理 SC-3 / SC-4）

`core/runtime/interpreter/runtime_context.py`：

- `RuntimeSymbolImpl` 新增 `cell: Optional[IbCell]` 字段，追踪是否已提升为 Cell 变量
- `ScopeImpl` 新增 `_cell_map: Dict[str, IbCell]`（sym_uid → IbCell）
- `ScopeImpl.promote_to_cell(sym_uid)` 方法：首次被 lambda 捕获时将符号提升为 Cell 变量；全局作用域（`_parent is None`）不提升（全局变量始终可达）；幂等：再次调用返回已有 Cell
- `ScopeImpl.iter_cells()` 方法：枚举当前作用域所有 IbCell（GC-2 根集合扫描入口）
- `assign()` / `assign_by_uid()` 修改：若符号已有 `cell`，赋值时同步调用 `cell.set(value)`，确保持有该 Cell 的 lambda 闭包看到最新值

### 7.2 lambda 共享 IbCell 捕获（SC-4 落地）

`core/runtime/interpreter/handlers/expr_handler.py`：

- `visit_IbLambdaExpr` lambda 模式：改为对每个自由变量调用 `scope.promote_to_cell(sym_uid)`，将共享 Cell 引用存入 `closure` 字典；不再传递 `captured_scope`
- snapshot 模式逻辑不变（独立 `IbCell(value_copy)`）
- 两种模式统一使用 `closure` 字典格式：`{sym_uid: (name, IbCell)}`

### 7.3 IbDeferred.call() 简化（移除 captured_scope 切换）

`core/runtime/objects/builtins.py`：

- 删除 `IbDeferred.call()` 中 `captured_scope` 作用域切换代码（`old_scope` / `rt_context.current_scope = _captured_scope`）
- lambda/snapshot 统一通过 `closure` 字典安装自由变量，无需切换作用域基底
- `_captured_scope` 字段在此阶段仍保留（历史 API 兼容，M2 后始终传 `None`）；字段完全删除于代码债务清理 PR（§九）

### 7.4 IbUserFunction 移除 lambda 参数传递限制

`core/runtime/objects/kernel.py`：

- 删除 `IbUserFunction.call()` 中 lambda 参数传递约束代码（约束理由："IbCell 未落地时 lambda 跨作用域不安全"）
- M2 落地后 lambda 携带共享 IbCell 闭包，可安全跨作用域传递和调用

### 7.5 GC-2 根集合接口

`core/runtime/interpreter/runtime_context.py`：

- `RuntimeContextImpl.collect_gc_roots()` 生成器方法：遍历作用域链（`_current_scope` → global），逐一 yield 符号值；对 Cell 变量调用 `cell.trace_refs()` yield 持有的对象

### 7.6 测试覆盖

| 测试文件 | 测试类 | 覆盖场景 |
|----------|--------|---------|
| `tests/e2e/test_e2e_m2_higher_order.py` | `TestLambdaAsHigherOrderArg` | lambda 传入高阶函数并调用（7 个场景） |
| | `TestLambdaSharedIbCell` | lambda 共享 Cell 读最新值（SC-4） |
| | `TestSnapshotIbCellIsolation` | snapshot 独立 Cell 冻结值（SC-3 回归） |
| | `TestLambdaFactory` | 工厂模式：函数返回 lambda，外层作用域退出后仍可调用 |
| | `TestCollectGcRoots` | `collect_gc_roots()` 接口可调用；Cell 变量值出现在根集合中 |
| `tests/e2e/test_e2e_ai_mock.py` | `TestE2ELambdaRestriction` | 反转为：lambda 可自由传递；snapshot 可传递（回归） |

---

## 八、fn 声明侧返回类型语法演进 [✅ COMPLETED — 2026-04-28]

**前提**：M2（已具备）  
**测试基线**：780 个测试通过（较 M2 前 776 增加 4 个）

### 8.1 核心语法变更

将 fn/lambda/snapshot 的返回类型标注从**表达式侧**（`lambda -> TYPE: EXPR`）迁移到**声明侧**（`TYPE fn NAME = lambda: EXPR`）：

| 旧语法（已禁止，PAR_005） | 新语法（声明侧） |
|--------------------------|----------------|
| `fn f = lambda -> int: EXPR` | `int fn f = lambda: EXPR` |
| `fn f = lambda(PARAMS) -> str: EXPR` | `str fn f = lambda(PARAMS): EXPR` |
| `fn f = snapshot -> float: EXPR` | `float fn f = snapshot: EXPR` |

**优势**：
- 返回类型标注对工厂模式和高阶函数参数同样有效（RHS 不是 lambda 字面量时也可标注）
- 与变量声明语法一致（`TYPE NAME = EXPR`）
- 支持泛型返回类型：`tuple[int,str] fn make_pair = lambda(int n, str s): (n, s)`

### 8.2 实现细节

| 文件 | 改动性质 |
|------|---------|
| `core/compiler/parser/components/declaration.py` | `TYPE fn NAME` 三词识别路径；`fn[TYPE]` 包装为 IbSubscript；处理工厂模式（RHS 可为任意表达式） |
| `core/compiler/parser/components/expression.py` | `lambda_expr`/`snapshot_expr` 移除 `-> TYPE` 语法；任何尝试触发 PAR_005 编译错误（含迁移提示） |
| `core/compiler/parser/components/recognizer.py` | 三处 lookahead 路径扩展以识别 `TYPE fn NAME` 形式 |
| `core/kernel/spec/registry.py` | `resolve_specialization`：`fn[TYPE]` → `DeferredSpec(value_type_name=TYPE)` |
| `core/kernel/axioms/primitives.py` | `DeferredAxiom.is_compatible` / `BehaviorAxiom.is_compatible`：接受 `deferred[…]` / `behavior[…]` 槽位 |
| `core/compiler/semantic/passes/semantic_analyzer.py` | `visit_IbAssign`：检测 `DeferredSpec` 类型声明时注入 `_pending_fn_return_type`（try/finally 保证嵌套安全）；`visit_IbLambdaExpr` 优先读取 pending type |
| `core/kernel/ast.py` | `IbLambdaExpr.returns` docstring 标注为历史兼容字段，解析器不再设置 |
| `tests/e2e/test_e2e_fn_lambda_syntax.py` | 所有 `lambda -> TYPE` 形式的测试迁移为 `TYPE fn` 声明侧；新增工厂模式、HOF 赋值场景 |

### 8.3 `fn[TYPE]` 类型推导链

```
TYPE fn f = lambda(PARAMS): EXPR
  ↓ parser: 声明类型 = fn[TYPE] = IbSubscript(fn, TYPE)
  ↓ semantic: resolve_specialization(fn, [TYPE]) → DeferredSpec(value_type_name=TYPE.name)
  ↓ semantic: _pending_fn_return_type = TYPE_spec
  ↓ visit_IbLambdaExpr: returns_type = TYPE_spec → 注入 body 的 expected_type
  ↓ 调用处: resolve_return(DeferredSpec[TYPE], []) → TYPE_spec
  → int r = f() 在编译期类型决议正确
```

---

## 九、代码债务清理（H1/H2/H3/M1）[✅ COMPLETED — 2026-04-28]

**前提**：M2 + fn 声明侧语法（已具备）  
**测试基线**：780 个测试通过（无新增测试，无回归）  
**背景**：基于 M2 落地后代码全链路审查（`URGENT_ISSUES.md` 高/中优先级问题）清理历史遗留死代码与文档/代码语义矛盾。

### 9.1 [H1] IbDeferred docstring 更新

`core/runtime/objects/builtins.py`：

- `IbDeferred` 类 docstring 中 `closure` 字段说明从 M1 旧描述更新为 M2 语义
- 删除 "lambda 模式仍使用 `captured_scope` 引用链" 说法
- 新描述：lambda/snapshot 两种模式均通过 `closure: Dict[sym_uid, (name, IbCell)]` 访问自由变量；snapshot 存独立 IbCell（值拷贝），lambda 存共享 IbCell（引用）

### 9.2 [H2] `_captured_scope` 僵尸字段完全删除

M2 后 `captured_scope` 参数始终传 `None`，字段从未被读取，属于死代码。本次完全删除：

| 文件 | 改动 |
|------|------|
| `core/runtime/objects/builtins.py` | `IbDeferred.__init__` 删除 `captured_scope` 参数及 `self._captured_scope = captured_scope` 赋值 |
| `core/runtime/factory.py` | `create_deferred` 签名删除 `captured_scope` 参数 |
| `core/runtime/interfaces.py` | `IObjectFactory.create_deferred` 抽象签名删除 `captured_scope` 参数 |
| `core/runtime/interpreter/handlers/expr_handler.py` | 删除 `captured_scope=None` 的显式传 None |
| `core/runtime/interpreter/handlers/stmt_handler.py` | 删除 `captured_scope = None` / `captured_scope = self.runtime_context.current_scope` 计算逻辑及相关传参（3 行死代码）|

### 9.3 [H3] `DeferredAxiom.is_compatible` 语义矛盾修复

`core/kernel/axioms/primitives.py`：

- 删除 `or other_name.startswith("behavior[")` 分支
- 该分支允许 `deferred` 值被赋给 `behavior[TYPE]` 槽，与 docstring 声明的"behavior 是 deferred 子类型、不可反向赋值"矛盾
- 修复前：`behavior[int] f = lambda: EXPR` 错误通过编译，产生 `IbDeferred` 运行时对象而非 `IbBehavior`，LLM executor 路径静默失效
- 修复后：`is_compatible` 与 docstring 一致；仅接受 `deferred`、`callable`、`deferred[TYPE]` 槽

### 9.4 [M1] closure 解包死分支删除

`core/runtime/objects/builtins.py`（两处）：

M2 后 `visit_IbLambdaExpr` 始终将 closure 条目存储为 `(name, IbCell)` 元组，`else` 分支永远不会执行：

```python
# 删除前
for sym_uid, payload in self.closure.items():
    if isinstance(payload, tuple) and len(payload) == 2:
        name, cell = payload
    else:
        name, cell = None, payload  # 死代码

# 删除后
for sym_uid, (name, cell) in self.closure.items():
```

`IbDeferred.call()` 和 `IbBehavior.call()` 两处均已更新。

---

## 十、M3a：CPS 调度循环骨架 + 次要代码债务清理 [✅ COMPLETED — 2026-04-28]

**前提**：M2 + 代码债务清理（已具备）  
**测试基线**：829 个测试通过（较 M2 后 780 增加 49 个；M3a 新增 49 个 VM 单元测试）  
**背景**：按 `docs/VM_EVOLUTION_PLAN.md` Step 9，落地 CPS 调度循环骨架——`Interpreter.visit()` 的并行路径，为 M3b/M3c/M3d 的控制流数据化、LLM exception 帧调度、主路径切换奠定调度层基础。

### 10.1 VM 包：`core/runtime/vm/`

新建 VM 子系统：

| 文件 | 职责 |
|------|------|
| `core/runtime/vm/__init__.py` | 公开 API：`VMTask`、`VMTaskResult`、`ControlSignal`、`ControlSignalException`、`VMExecutor` |
| `core/runtime/vm/task.py` | 调度数据对象：`VMTask`（节点 uid + 生成器协程）、`VMTaskResult`（DONE/SUSPEND/SIGNAL）、`ControlSignal` 枚举、`ControlSignalException`（M3a 过渡用） |
| `core/runtime/vm/handlers.py` | M3a 节点 CPS 处理器（基于 generator function）：覆盖 IbConstant/IbName/IbBinOp/IbUnaryOp/IbBoolOp/IbCompare/IbIfExp/IbCall/IbAttribute/IbSubscript/IbTuple/IbListExpr/IbModule/IbPass/IbExprStmt/IbAssign/IbIf/IbWhile/IbReturn/IbBreak/IbContinue 共 21 种节点 |
| `core/runtime/vm/vm_executor.py` | `VMExecutor` 显式帧栈调度循环（trampoline）：`run(uid)` / `supports(uid)` / `fallback_visit(uid)` / `assign_to_target(uid, val)` |

### 10.2 调度循环设计

* **生成器 trampoline**：每个支持的 AST 节点对应一个 generator function；`yield child_uid` 让出控制权，`return value` 完成任务，`raise ControlSignalException` 触发控制流信号。
* **显式帧栈**：`stack: list[VMTask]` 维护求值上下文；不依赖 Python 递归。
* **控制流信号**：M3a 通过 `ControlSignalException` + `generator.throw()` 跨帧传播；循环帧（IbWhile）拦截 BREAK/CONTINUE，函数帧（未来 M3b/M3c）拦截 RETURN。M3b 将把控制流改为显式 `VMTaskResult` 数据传递。
* **回退路径**：未实现的节点类型自动调用 `execution_context.visit(uid)` 回退到原递归路径，确保混合执行的程序仍能正确运行——这是 M3a 作为"骨架"的关键设计。

### 10.3 协议定义

`core/base/interfaces.py` 新增两个 Protocol（`runtime_checkable`）：

* `IVMTask`：声明 `node_uid` / `generator` 两个属性
* `IVMExecutor`：声明 `supports(uid)` / `run(uid)` / `fallback_visit(uid)` 三个方法

供 `__all__` 导出，与既有 `IExecutionFrame` 等协议位于同一文件。

### 10.4 测试覆盖

`tests/unit/test_vm_executor.py` 共 49 个测试，分 11 个类：

1. **数据类**（4 测试）：ControlSignal 枚举值 / ControlSignalException 携带数据 / VMTaskResult 工厂方法 / VMTask 默认 locals
2. **基础表达式**（12 测试）：IbConstant、IbName、IbBinOp（加/减/乘/嵌套）、IbUnaryOp、IbBoolOp（and/or 短路）、IbIfExp（true/false 分支）
3. **比较运算**（5 测试）：等于/不等/链式比较/短路链/in 列表
4. **复合表达式**（3 测试）：IbTuple、IbListExpr、IbSubscript
5. **控制流**（8 测试）：if true/false/else 分支、while 循环、break/continue、break 单独传播、return signal 携带值
6. **函数调用**（2 测试）：print 通过 VM 调用 / IbCastExpr 回退路径
7. **赋值**（2 测试）：常量目标 / 表达式目标
8. **Module/Pass/ExprStmt**（2 测试）：pass / module 顺序执行
9. **调度器基础设施**（6 测试）：supports/fallback_visit/run(None)/run(unsupported)/step_count
10. **CPS-vs-递归一致性**（3 测试）：算术/比较/while 循环模块级一致性
11. **信号传播**（2 测试）：while 内 break 不逃逸 / continue 跳过剩余

### 10.5 次要代码债务清理（M2/M3/M4/M5）

伴随 M3a 的辅助工作，按 `URGENT_ISSUES.md` 中等优先级清单同步完成：

| 编号 | 文件 | 改动 |
|------|------|------|
| M2 | `core/runtime/interpreter/runtime_context.py` | `define()` 的 fallback UID 路径：原 SHA256 hash 改为 `id(sym)`-based 唯一标识；通过 `warnings.warn(..., RuntimeWarning)` 显式告警；`import warnings` 提到模块顶层 |
| M3 | `core/runtime/interpreter/handlers/expr_handler.py` | snapshot 自由变量 `val is None` 不再静默跳过：通过 `debugger.trace(BASIC)` 输出诊断警告 |
| M4 | `core/runtime/objects/builtins.py` | `IbDeferred.to_native()` / `IbBehavior.to_native()` 不再静默 `return self`，改为抛出 `RuntimeError`（同步更新 `tests/e2e/test_e2e_m2_higher_order.py::TestCollectGcRoots` 过滤未执行的延迟值）|
| M5 | `core/runtime/interfaces.py`、`core/runtime/interpreter/runtime_context.py` | `iter_cells()` 提升到 `Scope` 协议（默认空迭代器实现）；`collect_gc_roots()` 移除 `hasattr` 检查，改为直接调用 |

**文档同步**：

* `docs/PENDING_TASKS.md` 头部测试基线 758 → 829，状态描述更新
* `docs/PENDING_TASKS.md §4.3` 状态从 `REDESIGNED` 改为 `COMPLETED`
* `docs/COMPLETED.md` §十 新增本节

### 10.6 后续里程碑

* **M3b**：把 `ControlSignalException` 替换为 `VMTaskResult.SIGNAL` 数据对象；调度循环显式拦截信号 ✅ — 见 §十一
* **M3c**：把 `LLMExceptFrame` retry 循环纳入调度器（用 `task.locals['snapshot']` 保存重试位点）
* **M3d**：把 `Interpreter.visit()` 主路径切换到 VMExecutor，全部节点纳入 CPS 调度，删除递归路径与 `ControlSignalException` 过渡类

---

## 十一、M3b：控制信号数据化 [✅ COMPLETED — 2026-04-28]

把 VM 内部的控制流（`return` / `break` / `continue`）从 Python 原生异常机制
（`ControlSignalException`）迁移为显式 **数据对象** `Signal(kind, value)`，
作为生成器协程的 `StopIteration.value` 沿帧栈传递。

### 11.1 核心数据对象 `Signal`

* `core/runtime/vm/task.py`：新增 `@dataclass(frozen=True) class Signal { kind: ControlSignal; value: Any }`
* `ControlSignalException.from_signal(sig)` 类方法：从 Signal 构造异常（边界兼容）
* 公开导出：`from core.runtime.vm import Signal, ControlSignal, ControlSignalException`

### 11.2 Handler 协议改造

| Handler | M3a（旧） | M3b（新） |
|---------|-----------|-----------|
| `vm_handle_IbReturn` | `raise ControlSignalException(RETURN, v)` | `return Signal(RETURN, v)` |
| `vm_handle_IbBreak` | `raise CSE(BREAK)` | `return Signal(BREAK)` |
| `vm_handle_IbContinue` | `raise CSE(CONTINUE)` | `return Signal(CONTINUE)` |
| `vm_handle_IbModule` | 直接 `yield stmt_uid` | 检查 `isinstance(res, Signal)`，是则 `return res` 透传 |
| `vm_handle_IbIf` | 同上 | 同上 |
| `vm_handle_IbWhile` | `try/except CSE` 拦截 BREAK/CONTINUE | 检查 Signal：BREAK 跳出、CONTINUE 跳到下一轮、其他 `return res` 透传 |

### 11.3 调度器改造（`vm_executor.py`）

* `StopIteration.value` 是 `Signal` 时：作为 `pending_value` 传给父帧（父 handler 通过 `gen.send(Signal)` 接收）
* 顶层栈空仍持有未消费 Signal：包装为 `ControlSignalException` 抛给调用者（**保留**与既有 `pytest.raises(ControlSignalException)` 测试合约的兼容）
* `fallback_visit()` 路径产生的旧 `ControlSignalException`（来自递归解释器 `ReturnException` 等）继续沿帧栈传播

### 11.4 测试覆盖（22 个新增 + 49 个 M3a 全部回归）

* `tests/unit/test_vm_executor_signals.py`：
  - **Signal 数据形态**（5 测试）：frozen / 携带 value / 等价 / kinds 互斥 / repr
  - **Handler 不再 raise**（3 测试）：IbBreak / IbContinue / IbReturn 通过 `return Signal(...)` 触发 `StopIteration.value`
  - **顶层逸出**（4 测试）：循环外 break/continue 转 CSE / return 携带 value / return 无值
  - **while 消费**（3 测试）：BREAK 终止循环 / CONTINUE 跳过剩余 / 嵌套 if 中 break
  - **非循环容器透传**（3 测试）：IbIf 透传 BREAK / IbIf 内 break 不执行后续语句 / else 分支 break
  - **无异常路径**（2 测试）：循环内 BREAK/CONTINUE 被消费时 `run()` 不抛异常
  - **CSE 边界转换器**（2 测试）：`from_signal` 保留 kind/value
* 总测试数 829 → 851

### 11.5 设计要点

* **不变性**：`Signal` 用 `frozen=True` 防止帧间被误改
* **零额外开销**：消费帧通过 `isinstance(res, Signal)` 单测试即可识别；非控制流场景零开销
* **可逆兼容**：`ControlSignalException` 保留作为**边界封装**类型，使外部测试与 fallback 路径无需改动；后续 M3d 完成全部节点 CPS 化后才能彻底删除

---

## 十二、M5a：DDG 编译期分析（BehaviorDependencyAnalyzer）[✅ COMPLETED — 2026-04-28]

为支撑后续 M5b/M5c 的 LLM 并行调度，在语义分析阶段对每个 `IbBehaviorExpr`
计算其上游依赖图（DDG = Dynamic-host Dependency Graph）。

### 12.1 AST 字段扩展

`core/kernel/ast.py::IbBehaviorExpr`：

```python
llm_deps: List["IbBehaviorExpr"] = field(default_factory=list)
dispatch_eligible: bool = True
```

* `llm_deps`：本节点求值依赖的上游 `IbBehaviorExpr` 节点（按 AST 出现顺序、去重）
* `dispatch_eligible`：是否可在 LLM 调度阶段被独立 dispatch（True：DAG / False：参与依赖环）

### 12.2 BehaviorDependencyAnalyzer Pass

`core/compiler/semantic/passes/behavior_dependency_analyzer.py`（新文件，240 行）：

1. **第一轮**：前序 AST 遍历，维护 `id(symbol) → IbBehaviorExpr` 映射
   - 遇到 `IbAssign(targets=[t], value=IbBehaviorExpr | IbCastExpr(IbBehaviorExpr) | IbTypeAnnotatedExpr(IbBehaviorExpr))` 时把所有 LHS Symbol 注册为该上游 behavior 的来源
   - 遇到 `IbBehaviorExpr` 时扫描 `segments` 中的 `$var` 插值（被解析为 `IbName`），通过 `side_table.get_symbol(name_node)` 找到 Symbol 并查表
   - 元组解包目标 / `IbTypeAnnotatedExpr` 包装目标都正确处理
2. **第二轮**：基于 Tarjan SCC 分析 `llm_deps` 图；含多元素或自环的 SCC 内所有节点 `dispatch_eligible = False`，其余保持默认 `True`

### 12.3 流水线集成

`SemanticAnalyzer.analyze()` 新增 **Pass 5**（在 Pass 4 深度检查之后），仅在前序 Pass 无错误时运行，避免半绑定状态产生噪音误差。

### 12.4 序列化

无需修改 `FlatSerializer._collect_node`：现有的 `_process_value` 自动把 `List[IbBehaviorExpr]` 转为 UID 列表，`bool` 字段直接存为 JSON 布尔值。运行时通过 `node_data.get("llm_deps")` / `node_data.get("dispatch_eligible")` 即可访问（不需要修改 `ArtifactRehydrator`，它只处理类型池）。

### 12.5 测试覆盖（16 个新增）

* `tests/unit/test_ddg_analysis.py`：
  - **无依赖**（3 测试）：单 behavior / 两个独立 behavior / 引用普通整型变量
  - **单依赖 / 链式 / 多源 / 去重**（4 测试）：A→B、A→B→C、{A,B}→C、A 引用两次只出现一次
  - **重新赋值保守**（1 测试）：覆盖为字面量后保留 ≤1 个依赖（保守近似，安全可靠）
  - **dispatch_eligible**（3 测试）：DAG 全 True / 人工互依赖环 False / 自环 False
  - **跨函数保守**（1 测试）：函数返回值不会被识别为 behavior 来源
  - **序列化**（1 测试）：`FlatSerializer` 输出含 UID 列表 + `dispatch_eligible: True`
  - **嵌套调用**（1 测试）：`print(@~direct $a~)` 中的 behavior 也参与依赖解析
  - **AST 默认值合约**（2 测试）：每个实例独立 `llm_deps=[]`、`dispatch_eligible=True`
* 总测试数 851 → **867**

### 12.6 后续

* **M5b**：基于 `dispatch_eligible == True` 的 behaviors 在调度器中并行 dispatch
* **M5c**：把 DDG 与 VMExecutor 帧栈结合，做拓扑排序的依赖等待
* **跨函数追溯**（DEFERRED）：当前实现仅在同作用域内追溯；未来可能扩展到跨函数返回值传播

---

## 十三、M3c：IbLLMExceptionalStmt CPS 调度化

> **完成状态**：✅ 全部落地，905 个测试通过（867 + 21 新增 M3c + 17 新增 M5b）。

**目标**：将 `LLMExceptFrame` 的 retry 循环和意图 fork/restore 迁移到 `VMExecutor` 调度循环中管理，消除对 Python try/except 的直接依赖（M3c 出口契约）。

### 13.1 保护重定向机制

`core/runtime/vm/handlers.py` 新增 `_resolve_stmt_uid(executor, stmt_uid)` 辅助函数：

* `_type == "IbLLMExceptionalStmt"` → 返回 `None`（直接 llmexcept 节点在 body 中跳过）
* `node_protection[stmt_uid]` 存在 → 返回对应 handler uid（重定向到 llmexcept handler）
* 其他 → 原样直通

`vm_handle_IbModule` / `vm_handle_IbIf` / `vm_handle_IbWhile` 均改为通过 `_resolve_stmt_uid` 对 body 中每个 stmt 进行解析，返回 `None` 时 `continue` 跳过。

### 13.2 vm_handle_IbLLMExceptionalStmt handler

新增生成器 handler，遵循 CPS 契约：

1. 从 LLM Provider 读取 `max_retry`（默认 3）
2. 创建 `LLMExceptFrame` 并保存上下文快照
3. 循环（最多 max_retry 次）：CPS 执行 target → 读取 `last_llm_result` → 确定则 break → 不确定则执行 body → `increment_retry`
4. `finally`：保证 `pop_llm_except_frame` 始终执行（无论正常退出 / Signal 传播 / 异常）

信号（RETURN/BREAK/CONTINUE/THROW）在 target 或 body 执行后立即透传给父帧。

### 13.3 VMExecutor.service_context 属性

`core/runtime/vm/vm_executor.py` 新增 `service_context` property，通过 `interpreter.service_context` 访问能力注册中心（供 handler 查询 `llm_provider.get_retry()`）。

### 13.4 注册

`build_dispatch_table()` 新增 `"IbLLMExceptionalStmt": vm_handle_IbLLMExceptionalStmt` 条目。

### 13.5 文件级修改清单

| 文件 | 改动性质 |
|------|---------|
| `core/runtime/vm/handlers.py` | 新增 `_resolve_stmt_uid`、`vm_handle_IbLLMExceptionalStmt`；更新三个容器 handler；注册到 dispatch table |
| `core/runtime/vm/vm_executor.py` | 新增 `service_context` property |
| `tests/unit/test_vm_executor_llmexcept.py`（新建） | 21 个测试：调度表注册 / `_resolve_stmt_uid` 路径 / 帧生命周期 / CPS 路径执行 / E2E 行为保留 |

### 13.6 测试覆盖（21 个新增）

* `TestDispatchTableRegistration`（3 测试）：dispatch table 注册、callable、generator function 类型
* `TestResolveStmtUid`（5 测试）：None / 重定向 / 直通 / 缺失 node_data / protection 优先
* `TestVMServiceContext`（2 测试）：无 interpreter → None / 有 interpreter → 正确上下文
* `TestFrameLifecycle`（2 测试）：CPS 执行后帧已出栈 / 多次执行不泄露帧
* `TestCPSExecution`（3 测试）：`vm.run(llmexcept_uid)` str / int / `supports()` 返回 True
* `TestE2EBehaviorPreservation`（6 测试）：无 retry / REPAIR retry / 多 llmexcept / if 分支 / while 循环 / retry hint

---

## 十四、M5b：LLMScheduler / LLMFuture

> **完成状态**：✅ 全部落地，905 个测试通过。

**目标**：为 `LLMExecutorImpl` 添加并发 dispatch 基础设施（`dispatch_eager` + `resolve` + `LLMFuture`），为 M5c 的 dispatch-before-use 集成提供就绪接口。

### 14.1 LLMFuture 数据类

`core/runtime/interpreter/llm_result.py` 新增 `LLMFuture`：

```python
@dataclass
class LLMFuture:
    node_uid: str
    future: Any  # concurrent.futures.Future[LLMResult]

    @property
    def is_done(self) -> bool: ...
    def get(self, registry: Any) -> IbObject: ...
```

`get()` 阻塞等待 `future.result()` 完成，返回 `LLMResult.value` 或 `registry.get_none()`。

### 14.2 LLMExecutorImpl 扩展

`core/runtime/interpreter/llm_executor.py`：

* `__init__` 新增 `max_workers: int = 8`，内部维护 `_thread_pool`（惰性）和 `_pending_futures: Dict[str, LLMFuture]`
* `_get_thread_pool()` 惰性初始化 `ThreadPoolExecutor`（首次 `dispatch_eager` 时创建）
* `dispatch_eager(node_uid, execution_context, intent_ctx)` → 提交到线程池，返回 `LLMFuture`，存入 `_pending_futures`
* `resolve(node_uid)` → 从 `_pending_futures` 弹出对应 Future，阻塞等待并返回 `IbObject`；uid 不存在或二次 resolve 抛 `RuntimeError`
* `__del__()` → 非阻塞关闭线程池

### 14.3 文件级修改清单

| 文件 | 改动性质 |
|------|---------|
| `core/runtime/interpreter/llm_result.py` | 新增 `LLMFuture` 数据类 |
| `core/runtime/interpreter/llm_executor.py` | 添加 `ThreadPoolExecutor`、`dispatch_eager`、`resolve`、`_get_thread_pool`、`__del__` |
| `tests/unit/test_llm_scheduler.py`（新建） | 17 个测试 |

### 14.4 测试覆盖（17 个新增）

* `TestLLMFuture`（6 测试）：is_done True/False / get() 返回 IbObject / None 降级 / 阻塞直到完成 / node_uid 字段
* `TestDispatchEager`（3 测试）：返回 LLMFuture / 非阻塞 / 存入 _pending_futures
* `TestResolve`（4 测试）：返回 IbObject / 消费后清除 / 未知 uid 抛错 / 二次 resolve 抛错
* `TestThreadPoolLazyInit`（3 测试）：dispatch 前为 None / dispatch 后非 None / 同一实例
* `TestBackwardCompat`（1 测试）：execute_behavior_expression 仍正常工作

### 14.5 后续

* **M5c**：dispatch-before-use 集成（依赖 M3c + M5b）：`dispatch_eligible=True` 时 VMExecutor 调用 `dispatch_eager()`，使用点调用 `resolve()`

---

## 十五、M3d-prep：扩展 CPS handler 覆盖 [✅ COMPLETED — 2026-04-28]

> **结论**：把 VM CPS handler 覆盖从 22 个节点类型扩展到 37 个；此为 M3d（主路径切换）必需的预备工作。  
> 测试基线：905 → 926 个测试通过（+21 单元测试）

### 15.1 新增的 CPS handler

新增 11 个 dispatch table 条目，对应 15 个 AST 节点类型（部分公用 handler）。每个 handler 1:1 镜像 `ExprHandler.visit_X` / `StmtHandler.visit_X` 的语义，仅形态由递归改为 generator-based CPS：

**表达式（4 个新 handler）**：
| 节点类型 | handler | 行为 |
|---------|---------|------|
| `IbDict` | `vm_handle_IbDict` | 装箱 dict（key 通过 `to_native()` 解构） |
| `IbSlice` | `vm_handle_IbSlice` | 装箱 Python `slice(lower, upper, step)`（任意可空） |
| `IbCastExpr` | `vm_handle_IbCastExpr` | 通过 `node_to_type` side_table 解析目标类，调用 `cast_to` 消息 |
| `IbFilteredExpr` | `vm_handle_IbFilteredExpr` | 主表达式短路 + 过滤条件求值（while...if 语义） |

**简单语句（5 个新 handler）**：
| 节点类型 | handler | 行为 |
|---------|---------|------|
| `IbAugAssign` | `vm_handle_IbAugAssign` | 复合赋值（`a += b`）：读旧值 + receive + 写回；支持 IbName / IbAttribute 目标 |
| `IbGlobalStmt` | `vm_handle_IbGlobalStmt` | 编译期语义；运行时无操作 |
| `IbRaise` | `vm_handle_IbRaise` | 求值异常对象后抛 `ThrownException`（fallback 路径中由 IbTry 捕获） |
| `IbImport` | `vm_handle_IbImport` | 当前阶段为 no-op |
| `IbImportFrom` | `vm_handle_IbImportFrom` | 当前阶段为 no-op |

**Switch（1 个新 handler）**：
| 节点类型 | handler | 行为 |
|---------|---------|------|
| `IbSwitch` | `vm_handle_IbSwitch` | test 求值 + 不确定性短路 + case 模式匹配 + body 的 Signal 透传 + `_resolve_stmt_uid` llmexcept 重定向 |

**定义类语句（3 个新 handler）**：
| 节点类型 | handler | 行为 |
|---------|---------|------|
| `IbFunctionDef` | `vm_handle_IbFunctionDef` | 绑定 `IbUserFunction` 到当前作用域 |
| `IbLLMFunctionDef` | `vm_handle_IbLLMFunctionDef` | 绑定 `IbLLMFunction` 到当前作用域 |
| `IbClassDef` | `vm_handle_IbClassDef` | 类必须 STAGE 5 已预水合；契约校验 + 作用域绑定（与原 handler 同语义） |

**意图操作（2 个新 handler）**：
| 节点类型 | handler | 行为 |
|---------|---------|------|
| `IbIntentAnnotation` | `vm_handle_IbIntentAnnotation` | `@` 涂抹（add_smear_intent）/ `@!` 排他（set_pending_override_intent） |
| `IbIntentStackOperation` | `vm_handle_IbIntentStackOperation` | `@+` push / `@-` pop_top / `@-` remove(tag/content) |

### 15.2 dispatch table 扩展

`build_dispatch_table()` 现包含 37 个条目，组成如下：22（M3a 骨架）+ 1（M3c IbLLMExceptionalStmt）+ 14（M3d-prep 本节新增）= 37。

### 15.3 文件级修改清单

| 文件 | 改动性质 |
|------|---------|
| `core/runtime/vm/handlers.py` | 新增 14 个 vm_handle_X 函数；扩展 imports（IbUserFunction/IbLLMFunction/IbClass/Thrown 等）；扩展 build_dispatch_table |
| `tests/unit/test_vm_executor_m3dprep.py` | 新建文件；21 个单元测试 |
| `tests/unit/test_vm_executor.py` | `test_supports_unknown_node` 改用 `IbBehaviorExpr`（IbCastExpr 已支持） |

### 15.4 测试覆盖（21 个新增）

`tests/unit/test_vm_executor_m3dprep.py` 包含：
* TestDispatchTableRegistration（2）：所有新 handler 已注册 + 全部为 generator function
* TestIbDictHandler（2）、TestIbSliceHandler（2）、TestIbCastExprHandler（1）、TestIbFilteredExprHandler（2）
* TestIbAugAssignHandler（1）、TestIbGlobalStmtHandler（1）、TestIbRaiseHandler（1）
* TestIbImportHandlers（1）、TestIbSwitchHandler（3）
* TestDefinitionHandlers（3）、TestIntentHandlers（2）

### 15.5 设计要点

* **handler 一致性**：所有新 handler 使用相同的"通过 `executor.ec` / `executor.runtime_context` / `executor.registry` 访问解释器服务"接口模式，与 M3a/M3b/M3c 现存 handler 完全统一。
* **Signal 透传**：IbSwitch 在 case body 中遇到 Signal 时立即返回 Signal，与 IbWhile/IbIf 一致。
* **llmexcept 重定向**：IbSwitch 的 case body 通过 `_resolve_stmt_uid` 处理 `node_protection`，与其他容器 handler 行为一致。
* **保持原语义**：所有新 handler 都是 1:1 语义镜像，无任何行为改动。覆盖扩展仅是 M3d 的形态准备。
* **不做妥协**：未触碰 `IbUserFunction.call()` 内部的 `ReturnException` 捕获——这部分必须等 M3d 主路径切换 + 函数帧 CPS 化后整体处理（参见 `docs/DEFERRED_CLEANUP.md` C5）。

### 15.6 后续

* **M3d**：剩余 unsupported 节点（`IbFor`、`IbTry`、`IbRetry`、`IbLambdaExpr`、`IbBehaviorExpr`、`IbBehaviorInstance`、`IbExceptHandler`、`IbCase`、`IbTypeAnnotatedExpr`、`IbIntentInfo` 等）需要在 M3d 阶段统一 CPS 化；同时切换 `Interpreter.visit()` 主路径，移除 `ReturnException`/`BreakException`/`ContinueException`。
* **测试基线**：M3d-prep 后为 **926 个测试**。

---

## 十六、M3d + M5c：主路径切换 + LLM dispatch-before-use [✅ COMPLETED — 2026-04-29]

### 16.1 新增的 CPS handler（M3d 范围内最后一批）

`core/runtime/vm/handlers.py` 新增 6 个 handler，把 dispatch table 扩展到 43 个节点类型（22 M3a + 1 M3c + 14 M3d-prep + 6 M3d）：

* **表达式**：`IbBehaviorExpr`、`IbBehaviorInstance`、`IbLambdaExpr`
* **控制流**：`IbFor`（含 iterable / condition-driven / IbFilteredExpr 三种形态）、`IbTry`（try/except/else/finally + IbExceptHandler 类型匹配）、`IbRetry`

`IbBehaviorExpr` handler 同时承担 M5c 的 dispatch hook：当上层 IbAssign 检测到 RHS 满足条件时，跳过同步执行直接调用 `LLMExecutor.dispatch_eager()`。

### 16.2 主执行路径切换

* `core/runtime/interpreter/interpreter.py::Interpreter.execute_module()` 顶层语句循环改为通过 `VMExecutor.run()` 驱动；`ControlSignalException`（`Signal` 顶层未消费包装）转回 `ReturnException`/`BreakException`/`ContinueException` 以便既有的"控制流位于函数/循环之外"边界检查继续工作。
* `core/runtime/objects/kernel.py::IbUserFunction.call()` 函数体执行改为通过 `VMExecutor.run()` 驱动；同样的 CSE → ReturnException 桥保留。
* `Interpreter._get_vm_executor()` 提供单例 `VMExecutor` 的延迟构造入口。

### 16.3 VMExecutor 中的 node_protection 重定向

`core/runtime/vm/vm_executor.py::VMExecutor._apply_protection_redirect()` 把原本只在 `Interpreter.visit()` 顶部生效的 llmexcept 拦截语义统一上提到 VM 层：

* 在 `run()` 入口和每次 yield 子节点 UID 时执行重定向；
* 通过比对 `RuntimeContext.get_llm_except_frames()[*].target_uid` 防止"已经在被保护中"的目标重复重定向（避免 llmexcept ↔ target 无限循环）。

这一步同时修复了一个 M3c 起就存在的潜在缺陷：条件驱动 for 循环（`for @~...~:`）的 `node_protection` 实际作用于 iter 中的 `IbBehaviorExpr`（语义分析阶段决定），主路径切换前依赖 `Interpreter.visit()` 入口拦截，切换后必须由 VM 层提供等价机制。

### 16.4 M5c：LLM dispatch-before-use 集成

实现位置：`core/runtime/vm/handlers.py::vm_handle_IbAssign` 与 `vm_handle_IbName`：

* `vm_handle_IbAssign`：当 RHS 是 `IbBehaviorExpr`、`dispatch_eligible == True`、不在 `is_deferred` 模式、当前没有活跃 LLMExceptFrame、目标是简单 `IbName` 时，调用 `LLMExecutor.dispatch_eager(node_uid, ec)` 并把返回的 `LLMFuture` 直接绑定到符号（绕过类型检查——LLMFuture 不是真实的 IbObject）；其余情况退回同步路径。
* `vm_handle_IbName`：读取符号时检测到值为 `LLMFuture`，调用 `LLMExecutor.resolve()` 同步等待 future，把结果回写符号槽（lazy resolve、单次消费、之后 O(1)）。

llmexcept frame 检查是必须的——同步协议依赖 `runtime_context.set_last_llm_result(result)` 在 `last_llm_result` 通道传递不确定性；dispatch 路径使用 future 异步通道，与 last_llm_result 不兼容。

### 16.5 关联修复

* `vm_handle_IbImport` / `vm_handle_IbImportFrom`：M3d-prep 阶段的"编译期无操作"实现错误地丢弃了 import 的运行时绑定。M3d 主路径切换后所有 import 都通过 VM 走，必须委托回 `ImportHandler.visit_IbImport*`，由它把模块对象写入当前作用域的符号表。
* `vm_handle_IbTry`：移除 `except InterpreterError: raise` 分支；现在与递归 `StmtHandler.visit_IbTry` 一致，`InterpreterError` 等 Python 内部异常作为通用 `Exception` 被捕获并包装为 IBCI `Exception` 实例。

### 16.6 文件级修改清单

| 文件 | 改动性质 |
|------|---------|
| `core/runtime/vm/handlers.py` | 新增 6 个 handler；vm_handle_IbAssign 增加 dispatch 分支；vm_handle_IbName 增加 LLMFuture lazy resolve；修复 import handler |
| `core/runtime/vm/vm_executor.py` | 新增 `_apply_protection_redirect()`；run() 入口与 yield 子节点路径调用 |
| `core/runtime/interpreter/interpreter.py` | execute_module() 顶层循环切换至 VMExecutor；新增 `_get_vm_executor()` |
| `core/runtime/objects/kernel.py` | IbUserFunction.call() 函数体循环切换至 VMExecutor；导入 BreakException/ContinueException |
| `tests/unit/test_vm_executor_m3d.py` | 新建：M3d 6 handler + 主路径切换 + protection 重定向（16 个测试） |
| `tests/e2e/test_e2e_llm_pipeline.py` | 新建：M5c 并发派发 / lazy resolve / dispatch-skip / 语义等价（7 个测试） |
| `tests/unit/test_llm_scheduler.py` | 更新 `test_dispatch_eager_stores_in_pending_futures` 适配 M5c 隐式派发 |

### 16.7 测试基线

`python3 -m pytest tests/ -q --tb=short` → **949 passed**（926 + 16 新 M3d + 7 新 M5c）。

### 16.8 设计要点

* **Signal vs Exception 分层**：CPS 内部一律用 `Signal(kind, value)` 数据流传播 RETURN/BREAK/CONTINUE；只在 VMExecutor.run() 出口处把未消费的 Signal 包装成 `ControlSignalException` 跨越 Python 调用栈到达 `execute_module` / `IbUserFunction.call`，再由这两处转回原始 `ReturnException` / `BreakException` / `ContinueException` 让既有的边界检查工作。该 ExceptionBridge 保留至 DEFERRED_CLEANUP C5。
* **保护重定向单点化**：M3c 时由各容器 handler 各自实现 `_resolve_stmt_uid`；M3d 把这一职责上提到 VMExecutor 调度循环统一处理，所有 yield child_uid 自动获得保护语义，handler 内不必关心。
* **dispatch 决策保守**：仅在能严格判定"目标是简单赋值、无 deferred、无 llmexcept 保护"的场景启用 M5c 派发；任何不确定情况都退回同步路径，保证语义不退化。
* **未变动**：`ReturnException` 类、`ControlSignalException` 类继续保留作为边界封装。`Interpreter.visit()` 仍是 fallback 路径——VMExecutor 不支持的节点类型会回退到这里，同时模块外部接口（如解释器嵌入测试用例）不受影响。

### 16.9 后续

* **M4**：Layer 2 多 Interpreter 并发（`DynamicHost.spawn` 线程化）。M3d 完成后 ContextVar 帧管理已从 Python 递归栈解耦，可以在独立线程中运行子 Interpreter。
* **C5（DEFERRED_CLEANUP）**：移除 `ReturnException`/`BreakException`/`ContinueException` 与 `ControlSignalException`，把函数返回完全数据化为 Signal 帧。

---


## 十七、轻量代码债务清理（L1/L2 + C1/C2/C3/C4 + C10/C13）[✅ COMPLETED — 2026-04-29]

> **背景**：M3d/M5c 完成后基线 949 测试通过；为给 M4（多 Interpreter 并发）扫清前置债务，将 `DEFERRED_CLEANUP.md` 中风险极低的 8 条以一个 PR 集中清理。所有改动都在已有代码框架内，无编译器改动。

### 17.1 死代码与僵尸字段删除（C1 / L1）
* **C1**：删除 `LLMExceptFrame._is_serializable()` —— 全仓库零调用点。
* **L1**：删除 `IbLambdaExpr.returns` 字段；删除 `visit_IbLambdaExpr`（Pass 3）的 `node.returns` elif 回退；删除 Pass 2 Resolver 的 `node.returns is not None` 类型决议分支。声明侧返回类型完全经由 `_pending_fn_return_type` 隐式通道传递。
*文件：`core/runtime/interpreter/llm_except_frame.py`、`core/kernel/ast.py`、`core/compiler/semantic/passes/{semantic_analyzer,resolver}.py`*

### 17.2 兼容路径收紧（C2 / C3 / C4）
* **C2**：`LLMExecutor.execute_behavior_expression` 中 `captured_intents` 旧路径分支替换为 `TypeError`；`IIbBehavior.captured_intents` 注释收紧为 `Optional[IbIntentContext]`；同步更新 `IbBehavior.serialize_for_debug` / `Interpreter.get_captured_intents` / `runtime_serializer` 的读取代码以适应 `None | IbIntentContext` 形态（之前假设可迭代）。
* **C3**：经 `-W error::RuntimeWarning` 全套测试验证 fallback 不被合法路径触发；删除 `RuntimeWarning`；保留 `id(sym)` 派生 UID 兼容内核引导期 / 跨上下文同步路径，并增加 `assert name` 防御性断言；移除现已不需要的 `import warnings`。
* **C4**：审计 `IbDeferred.body_uid is None` 路径——结论是该分支在合法编译路径下不可达（`is_deferred=True` 与 `value_node_type != IbBehaviorExpr` 互斥）；保留 `or self.node_uid` 作为防御性回退（不抛异常）以兼容潜在的程序化构造路径，并在调用点添加详细审计注释固化结论。

### 17.3 M4 前置：函数调用 VM 路径直化（C13 / C10）
* **C13**：在 `ExecutionContextImpl` 上新增 `vm_executor` 属性 + setter；`Interpreter._get_vm_executor()` 在首次构造 VMExecutor 时立即把引用写入 EC。`IbUserFunction.call()` 改为直接读取 `self.context.vm_executor` 调用 `vm.run_body(body)`，删除原三级 getattr 穿透查找链。**审计中发现**：原查找链在合法运行时永远走不到 VMExecutor 路径（ExecutionContextImpl 既无 `vm_executor` 也无 `_interpreter`），函数体始终走的是 `self.context.visit(stmt_uid)` 递归 fallback；C13 的修复让函数体首次真正经由 VM 路径执行——这正是 M4 多 Interpreter 并发所需要的"无 silent fallback"前提。
* **C10**：新增 `VMExecutor.run_body(stmt_uids)` 共享方法，统一封装 (1) `IbLLMExceptionalStmt` 直接子节点跳过、(2) `node_protection` 重定向（由 `run()` 入口承担）、(3) `Signal → ReturnException/BreakException/ContinueException` 边界恢复。`execute_module()` 与 `IbUserFunction.call()` 现在共用一行 `vm.run_body(body)`，消除两处重复的 body 循环逻辑。同时修复了原 `IbUserFunction.call()` 中 `cse.kind` 的 dormant 错误（属性名应为 `cse.signal`）——该错误因函数体路径之前从未真正进入 VM 而未被发现。
*文件：`core/runtime/interpreter/execution_context.py`、`core/runtime/interpreter/interpreter.py`、`core/runtime/objects/kernel.py`、`core/runtime/vm/vm_executor.py`*

### 17.4 维护性改善（L2 + L3 / L4 注释）
* **L2**：`RuntimeSymbolImpl` 新增 `is_builtin: bool` 字段；`Scope.define()` / `RuntimeContext.define_variable()` Protocol 与 impl 增加 `is_builtin` 参数；`IntrinsicManager.rebind()` 在注入 intrinsic 时传 `is_builtin=True`；`get_vars()` 改为按属性过滤而非硬编码 `("len","print","range","input","get_self_source")` 名单。
* **L3**：在 `SemanticAnalyzer._pending_fn_return_type` 字段声明处补充设计决策注释——这是经过审慎选择的隐式通道（替代方案"节点字段"已在 L1 删除，"参数化访问者"会污染分发签名）；嵌套安全性由 `visit_IbAssign` 的 `try/finally save/restore` 保证。
* **L4**：在 `_collect_free_refs` 通用展开循环处补充注释，说明启发式策略与 UID 编码下的低碰撞概率。
*文件：`core/runtime/interpreter/runtime_context.py`、`core/runtime/interfaces.py`、`core/runtime/interpreter/intrinsics/__init__.py`、`core/compiler/semantic/passes/semantic_analyzer.py`、`core/runtime/interpreter/handlers/expr_handler.py`*

### 17.5 测试基线
949 → 949（0 退化）。

### 17.6 暂缓项
C5 / C6 / C7 / C8 / C9 / C11 / C12 / C14 按计划延后：C5/C6 等 ControlSignalException 彻底移除；C7/C8/C11/C14 等 M6 后统一处理（需编译器改动或较大重构）。

---

## 十八、M4 多 Interpreter 并发（Layer 2 执行隔离）[✅ 2026-04-29]

> **前提**：M3a/M3b/M3c/M3d + M5a/M5b/M5c 已全部完成；C10/C13 前置债务已清理（949 测试通过）。

### 18.1 设计目标

实现 IBCI 三层并发模型中的 **第二层（执行隔离）**：允许 IBCI 程序并发启动多个完全独立的子 `Interpreter` 实例（每个子实例拥有独立的 `KernelRegistry`、`RuntimeContext`、`LLMScheduler`），通过显式 `collect()` 原语聚合结果，子环境不直接写主环境的 `RuntimeContext`。

### 18.2 新增 API

| 层级 | 方法 | 签名 | 语义 |
|------|------|------|------|
| IBCI 语言 | `ihost.spawn_isolated` | `(str, dict) → str` | 非阻塞：在后台线程启动子脚本，返回 handle |
| IBCI 语言 | `ihost.collect` | `str → dict` | 阻塞：等待子脚本完成，返回其全局变量字典 |
| Python/Engine | `IBCIEngine.request_spawn_isolated` | `(str, dict, dict?) → str` | Engine 层线程管理实现 |
| Python/Engine | `IBCIEngine.request_collect` | `str → Dict[str, Any]` | Engine 层 join + 变量提取实现 |

### 18.3 实现要点

**`IBCIEngine`（`core/engine.py`）**：
- 新增 `_spawned_tasks: Dict[str, Tuple[Thread, IBCIEngine, list]]` + `_spawned_tasks_lock`（`threading.Lock`）
- `request_spawn_isolated()`：创建全新 `IBCIEngine` 子实例，在 daemon 线程中调用 `sub_engine.run()`，`exc_holder` list 捕获子线程异常；线程 start 后立即返回 `f"spawn_{uuid8}"`
- `request_collect()`：线程 `join()`（阻塞），从 `_spawned_tasks` 消费并删除记录；子线程异常透传为 `RuntimeError`；从 `sub_engine.interpreter.runtime_context.global_scope` 提取用户变量，跳过 `is_builtin`、跳过函数/行为等不可序列化类型（`_SKIP_IB_TYPES`），通过 `val.to_native()` 转为 Python 原生值后返回

**`HostService`（`core/runtime/host/service.py`）**：
- `spawn_isolated(path, policy)` → 委托 `orchestrator.request_spawn_isolated()`
- `collect(handle)` → 委托 `orchestrator.request_collect()`

**`IHostPlugin`（`ibci_modules/ibci_ihost/core.py`）**：
- 新增 `spawn_isolated(path, policy)` + `collect(handle)` 方法，通过 `_host_service()` 调用 `HostService`

**`_spec.py`（`ibci_modules/ibci_ihost/_spec.py`）**：
- `spawn_isolated: (str, dict) → str`
- `collect: str → dict`

**接口层（`core/runtime/interfaces.py`）**：
- `IKernelOrchestrator` 协议新增 `request_spawn_isolated` + `request_collect`
- `IHostService` 协议新增 `spawn_isolated` + `collect`

### 18.4 安全约束

- 子引擎在 daemon 线程运行，主进程退出时自动终止（不泄漏）
- `_spawned_tasks_lock` 保护 dict 并发读写
- 每个 handle 只能被 collect 一次，重复 collect 抛 `RuntimeError`
- 子线程异常在 `collect()` 时以 `RuntimeError` 形式在主线程重新抛出
- 子引擎的 `KernelRegistry` 通过 `auto_sniff=True` 独立初始化，与父引擎完全隔离（不共享 sealed 注册表）

### 18.5 测试新增

新建 `tests/e2e/test_e2e_m4_multi_interpreter.py`，15 个测试覆盖：
- Engine 层直接 API（spawn/collect/错误传播/幂等保护/多顺序 spawn）
- 并发正确性（两个子引擎确实并发；spawn 非阻塞验证）
- IBCI 层 API（roundtrip/int 提取/handle 类型验证/两并发 spawn）
- `run_isolated` 兼容性回归

### 18.6 测试基线
949 → 964（+15 M4 专项测试，0 退化）。

---

## §十九：M6 可移植性参考实现 + Phase 1 轻量债务清理（C6/C12）— 2026-04-29

### 19.1 目标

M6 的核心目标是在主线功能（M1–M5c + M4）全部稳定后，建立**正式规范层**与**跨实现合规测试套件**，使 IBCI VM 的可观察行为在未来任何宿主实现（Rust/Go/C++ 等）中均可验证。同时完成 Phase 1 轻量债务清理（C6/C12），使代码与规范描述对齐。

### 19.2 VM 规范文档（docs/VM_SPEC.md）

新建 `docs/VM_SPEC.md` 作为 IBCI VM 的**正式规范**：
- **§1 执行模型**：CPS 调度循环公理（EXEC-1/2/3）、节点类型分类表（含 CPS/fallback 状态标注）
- **§2 内存模型**：对象模型公理（OM-1/2）、作用域公理（SC-1/2/3/4）、生命周期公理（LT-1/2/3/4）、GC 公理（GC-1/2/3）
- **§3 LLM 数据流模型**：DDG 编译期分析规则、LLMScheduler/LLMFuture 公理（LLM-1/2/3）
- **§4 多 Interpreter 并发**：执行隔离公理（ISO-1/2/3）、spawn/collect 契约（SC-1/2/3/4/5）
- **§5 意图上下文模型**：fork/restore/snapshot 公理（IC-1/2/3）
- **§6 合规测试套件说明**：目录结构、运行方式、可移植性约束
- **§7 与现有文档的对应关系**：章节-Milestone-PENDING_TASKS 映射表

### 19.3 合规测试套件（tests/compliance/）

新建 `tests/compliance/` 目录，包含 32 个合规测试（3 个测试文件）：

**`test_execution_isolation.py`（SPEC §4，19 测试）**：
- §4.1 子 Interpreter 变量不泄漏到主 Interpreter；主 Interpreter 变量不继承到子；两个子相互独立
- §4.2 collect 返回 dict；包含 str/int/bool/list/dict；排除内置符号；空脚本返回空 dict
- §4.3 重复 collect 抛 RuntimeError；子编译失败时 collect 传播错误；spawn 立即返回字符串 handle

**`test_concurrent_llm.py`（SPEC §3，9 测试）**：
- §3.1 两个/三个独立 behavior 赋值最终值正确；多次读取幂等；int 类型值正确
- §3.2 有数据依赖的 behavior 不破坏结果正确性；循环内 behavior 每次迭代正确
- §3.3 程序输出顺序遵从语义顺序而非 dispatch 顺序；dispatch 与同步代码混合正确
- §3.4 llmexcept 保护路径（同步路径）值正确

**`test_memory_model.py`（SPEC §2，18 测试）**：
- §2.1 lambda 共享 Cell：外部修改可见；两个 lambda 共享同一 Cell；多个自由变量独立
- §2.2 snapshot 值快照：外部修改不可见；snapshot vs lambda 不同结果对比
- §2.3 Cell 延长生命周期：工厂函数返回的 lambda 在外层退出后仍可调用；snapshot 创建时捕获值
- §2.4 值类型赋值深拷贝等价：int/str/bool 修改原变量不影响副本
- §2.5 lambda 高阶函数传递：作为参数传入被调用；从函数返回后仍可调用

### 19.4 C6 轻量债务清理（Signal→CSE→ReturnException 三层桥消除）

**`core/runtime/vm/vm_executor.py:run_body()`**：
- 移除 `except _CSE` 块（CSE→ReturnException/BreakException/ContinueException 转换），让 ControlSignalException 直接向调用方传播

**`core/runtime/interpreter/interpreter.py:execute_module()`**：
- 改为直接捕获 `ControlSignalException`（同时保留 ReturnException/BreakException/ContinueException 兜底）
- 新增 `from core.runtime.vm.task import ControlSignalException` 导入

**`core/runtime/objects/kernel.py:IbUserFunction.call()`**：
- 新增 `except ControlSignalException as cse`，`kind==RETURN` 时直接返回 `cse.value`
- 保留 `except ReturnException`（vm=None 递归路径兼容）

### 19.5 C12 轻量债务清理（ScopeImpl 私有字段访问封装）

**`core/runtime/interpreter/runtime_context.py:ScopeImpl`**：
- 新增 `is_cell_promoted(sym_uid: str) -> bool`：封装 `_cell_map` 私有字典探测
- 新增 `define_raw(name, value, uid, declared_type) -> RuntimeSymbolImpl`：低级符号写入，绕过类型检查与 box 操作（LLMFuture 占位符写入专用）

**`core/runtime/interfaces.py:Scope`**：
- 新增 `is_cell_promoted` 和 `define_raw` 默认实现方法

**`core/runtime/vm/handlers.py`**：
- `_target_is_promoted_cell()`：`hasattr(scope, "_cell_map") and sym_uid in scope._cell_map` 改为 `scope.is_cell_promoted(sym_uid)`
- `_assign_future_to_name_target()`：首次定义路径改用 `target_scope.define_raw(...)` 替代直接写 `_symbols`/`_uid_to_symbol` 私有字段；删除 `from core.runtime.interpreter.runtime_context import RuntimeSymbolImpl` 局部导入

### 19.6 文档更新

- `docs/VM_EVOLUTION_PLAN.md`：更新基准状态（964→996）；路线图标注 M4/M5c/M6 全部为 ✅；新增编译器深度清洁后续路径说明
- `docs/PENDING_TASKS_VM.md`：Step 12（M6）更新为 ✅ COMPLETED
- `docs/DEFERRED_CLEANUP.md`：更新基线（949→996）；C6 标记为 PARTIAL DONE；C12 标记为 DONE；PR 操作建议增加第二阶段说明
- `docs/NEXT_STEPS.md`：更新状态标签；增加"下一主线：编译器深度清洁"章节

### 19.7 测试基线

964 → 996（+32 合规测试，0 退化）。

---

## §二十：编译器深度清洁 Phase 2–5（C5–C14 全链路落地）— 2026-04-29

> Phase 1 已记录于 §十九（C6 部分 / C12）。本节汇总 Phase 2–5 的清洁工作，覆盖 `docs/DEFERRED_CLEANUP.md` 中 C5/C7/C8/C9/C11/C14 全部条目；自此该文件全部 ✅ DONE 并已归档进本文件后删除。

### 20.1 Phase 2（C8 + C14）— 编译期 free_vars / cell_captured_symbols 侧表

**C8：`vm_handle_IbLambdaExpr` / `vm_handle_IbBehaviorInstance` 全量 fallback 消除**

- `core/kernel/ast.py`：`IbLambdaExpr` 新增 `free_vars: List` 字段（`[[name, sym_uid], ...]`），编译期填充并序列化进 artifact。
- `core/compiler/semantic/passes/semantic_analyzer.py`：`visit_IbLambdaExpr` 末尾通过新增的 `_collect_free_var_refs_ast()` 在 Pass 4 body 分析完成后于 AST 对象树上收集所有自由变量引用；正确处理嵌套 lambda（内层形参加入 exclusion set）。
- `core/runtime/vm/handlers.py`：`vm_handle_IbLambdaExpr` 改为直接读取 `node_data["free_vars"]` 构建 closure，删除 `executor.fallback_visit()` 调用——handler 真正 CPS 化。
- `IbBehaviorInstance` 节点对应 PAR_010 废弃语法，`vm_handle_IbBehaviorInstance` 内联处理路径并清理 fallback。

**C14：`BehaviorDependencyAnalyzer` 不感知 IbCell 提升导致运行时扫描**

- `core/compiler/semantic/passes/side_table.py`：`SideTableManager` 新增 `cell_captured_symbols: Set[str]`——Pass 4 中 lambda 模式自由变量的 sym_uid 集合。
- `semantic_analyzer.visit_IbLambdaExpr` 在 `deferred_mode == "lambda"` 时把 free_vars 中的 sym_uid 写入侧表。
- `core/compiler/semantic/passes/behavior_dependency_analyzer.py`：`_register_assign_targets` 检查赋值目标 sym_uid 是否在 `cell_captured_symbols` 中，是则把对应 `IbBehaviorExpr.dispatch_eligible` 设为 `False`——编译期防止 LLMFuture 被写入 IbCell。
- `core/runtime/vm/handlers.py`：`_target_is_promoted_cell()` 运行时作用域链扫描函数删除；`vm_handle_IbAssign` 不再调用该函数。

### 20.2 Phase 3（C6 remainder + C7 + C9）— `fallback_visit()` 显式调用归零

**C9：`vm_handle_IbImport` / `vm_handle_IbImportFrom` fallback 升级为真正 CPS**

- `core/runtime/vm/handlers.py`：两个 handler 内联 `ImportHandler.visit_*` 逻辑，调用 `sc.module_manager.import_module()` / `import_from()`，再 `runtime_context.define_variable()` 绑定；`if False: yield` 满足调度协议，彻底删除 `executor.fallback_visit(node_uid)` 调用。
- `vm_handle_IbAssign` 中 `is_deferred` 路径的 `fallback_visit(value_uid)` 替换为 `yield value_uid`——`vm_handle_IbBehaviorExpr` 已完整实现 deferred 模式的 IbBehavior 包装，fallback 冗余。
- 至此 handlers.py 中所有显式 `executor.fallback_visit()` 调用清零。

**C7：`assign_to_target()` 穿透到 StmtHandler 的递归赋值彻底重写为 CPS generator**

- `core/runtime/vm/handlers.py`：新增 `_assign_name_target()` 纯同步 IbName 赋值帮助函数；新增 `_vm_assign_to_target()` CPS generator helper，支持所有目标类型（IbName / IbTypeAnnotatedExpr / IbAttribute / IbSubscript / IbTuple 解包）。
- `vm_handle_IbAssign` / `vm_handle_IbFor` 中所有 `executor.assign_to_target()` 调用替换为 `yield from _vm_assign_to_target(...)`。
- `core/runtime/vm/vm_executor.py`：`VMExecutor.assign_to_target()` 标注为已废弃（兼容保留），生产路径不再使用。

**C6 收尾：`IbTry` / `IbCall` 异常透传桥删除**

- `core/runtime/vm/handlers.py`：`vm_handle_IbTry` body try-except 中移除 `except (ReturnException, BreakException, ContinueException): raise` 透传桥；`vm_handle_IbCall` 中移除 `except ControlSignalException: raise` 透传桥；handlers.py 顶部清除 `ReturnException/BreakException/ContinueException/ControlSignalException` 全部无用导入。

### 20.3 Phase 4（M3d/C13 主路径切换）

**C13：`IbUserFunction.call()` 通过多级 `getattr` 脆弱查找 VMExecutor**

- `core/runtime/interpreter/execution_context.py` / `interpreter.py`：`ExecutionContextImpl` 新增 `vm_executor` 属性 + setter（默认 `None`，由 Interpreter 注入）；`Interpreter._get_vm_executor()` 在首次构造 VMExecutor 时立即把引用写入 `self._execution_context.vm_executor`。
- `core/runtime/objects/kernel.py`：`IbUserFunction.call()` 改为直接读取 `self.context.vm_executor` 并通过 `vm.run_body(body)` 驱动函数体。
- 审计修复：原三级查找链在合法运行时永远走不到 VMExecutor 路径，函数体始终走 `context.visit(stmt_uid)` 递归 fallback；C13 让函数体首次真正经由 VM 路径执行——这正是 M4 多 Interpreter 并发所需要的"无 silent fallback"前提。

### 20.4 Phase 5（C11 / P3 + C5）— `node_protection` 侧表 + `ControlSignalException` 全链路删除

**C11/P1**（语义分析）：`IbFor.llmexcept_handler` AST 字段替代条件驱动 for 循环的侧表关联。

**C11/P2**（VM 运行时）：`vm_handle_IbFor` 直接内联重试逻辑，消除 `_apply_protection_redirect` 对条件表达式的隐式覆写；修复条件驱动 for + llmexcept 无限循环 bug。

**C11/P3**（最终清理）：

- `core/compiler/semantic/passes/side_table.py`：删除 `node_protection` dict、`bind_protection()`、`clear()` 中清理调用。
- `core/compiler/semantic/passes/semantic_analyzer.py`：`analyze()` 返回值删除 `node_protection=...` 参数。
- `core/kernel/blueprint.py`：`CompilationResult` 删除 `node_protection` 字段。
- `core/compiler/serialization/serializer.py`：删除 `remaped_node_protection` 块与 side_tables 字典中的 `node_protection` entry。
- `core/runtime/vm/vm_executor.py`：删除 `_apply_protection_redirect()` 方法 + `run()` / `_drive_loop()` 中 2 处调用。
- `core/runtime/interpreter/interpreter.py`：删除 `visit()` 中 `bypass_protection` 检查块与参数。
- `core/runtime/interpreter/execution_context.py` / `core/kernel/interfaces.py` / `core/runtime/interfaces.py`：`visit()` Protocol 中 `bypass_protection` 参数删除。
- `core/runtime/interpreter/handlers/stmt_handler.py`：调整 `visit_IbLLMExceptionalStmt` 中显式驱动 target 的调用。
- `tests/unit/test_vm_executor_m3d.py`：删除 `TestProtectionRedirect` 类（3 个针对死代码的测试覆盖物）。

**C5**（控制流不再以异常方式跨越 Python 调用栈）：C11/P3 完成后，`ControlSignalException` 类本体在 `core/runtime/vm/task.py` 中**已彻底删除**，仅余 `UnhandledSignal`（VM 顶层未消费 Signal 的边界异常）。production 与 test 路径中均无任何引用。

### 20.5 测试基线与最终状态

- 基线：996（M6 + Phase 1 完成）→ 989（C11/P3 完成；删除 3 个 `TestProtectionRedirect` 死代码测试覆盖物，0 功能性退化）。
- CPS dispatch table 覆盖 **43 个 AST 节点 handler**（helper 节点 IbCase / IbExceptHandler / IbTypeAnnotatedExpr 由父 handler 内联，无需独立 dispatch entry）。
- handlers.py 中所有显式 `executor.fallback_visit()` 调用归零；`vm_executor.py` 的 fallback 仅作为分发层兜底（`dispatch[type] is None` 时返回值，所有 production 路径都已有显式 handler）。
- `docs/DEFERRED_CLEANUP.md` 中 L1–L4 + C1–C14 全部 ✅ DONE。

---

## §二十一：URGENT_ISSUES / BUG_REPORTS / DEFERRED_CLEANUP 历史归档

> 三个独立的"工作进行中"文件在 2026-04-29 全部完成清零；为减少冗余文档与未来 agent 误读风险，文件原内容（历史修复条目）已合并至本节备查，原文件已删除。

### 21.1 `URGENT_ISSUES.md`（Code Review 2026-04-28）历史归档

- **H1**（FIXED 2026-04-28）`IbDeferred` docstring 落后 M2 实现 — 更新为 closure 字段语义。`core/runtime/objects/builtins.py:703-707`
- **H2**（FIXED 2026-04-28）`_captured_scope` 僵尸字段存活 — 全链路删除。`core/runtime/objects/builtins.py`、`core/runtime/factory.py`、`core/runtime/interfaces.py`、`core/runtime/interpreter/handlers/expr_handler.py`、`core/runtime/interpreter/handlers/stmt_handler.py`
- **H3**（FIXED 2026-04-28）`DeferredAxiom.is_compatible` 与自身文档矛盾 — 移除 `or other_name.startswith("behavior[")` 行。`core/kernel/axioms/primitives.py`
- **M1**（FIXED 2026-04-28）`IbDeferred.call()` / `IbBehavior.call()` "兼容历史"死分支 — 改为直接解包 `closure.items()`。
- **M2**（FIXED 2026-04-28，M3a PR 同步）`define()` fallback UID hash 生成 — 改为 `id(sym)`-based + `RuntimeWarning`。
- **M3**（FIXED 2026-04-28，M3a PR 同步）snapshot 模式自由变量捕获静默失败 — `val is None` 改为通过 `debugger.trace(BASIC)` 输出诊断警告。
- **M4**（FIXED 2026-04-28，M3a PR 同步）`IbDeferred.to_native()` / `IbBehavior.to_native()` 静默返回 self — 未执行时抛 `RuntimeError`。
- **M5**（FIXED 2026-04-28，M3a PR 同步）`collect_gc_roots()` 用 `hasattr` 做接口检查 — `iter_cells()` 提升到 `Scope` 协议。
- **L1–L4**（DONE 2026-04-29，轻量债务清理 PR）—— 详见 §十七 与 §20。

### 21.2 `BUG_REPORTS.md` Bug #1–#4 历史归档

- **Bug #1**（FIXED）类字段列表/字典字面量默认值静默失效 — `Interpreter.__init__` 不再覆盖 `_kernel_token`；`KernelRegistry.set_execution_context()` 移除过度限制；运行时 handler 在 `_pre_evaluate_user_classes()` 之前初始化。
- **Bug #2**（FIXED）`dict` 类型变量接收 `@~...~` LLM 输出失败 — `_parse_result()` 在 `meta_reg.resolve(type_name)` 失败时剥离泛型参数重试（`"dict[any,any]"` → `"dict"`）。
- **Bug #3**（FIXED, CONFIRMED）Enum 类型从 LLM 输出解析失败 — `_check_type` 对 `is_user_defined=True` 的 `ClassSpec` 跳过类型校验，正常工作。
- **Bug #4**（FIXED）`none`（小写）关键字在运行时未定义 — `visit_IbName()` 检测到 `node.id == "none"` 时立即发 SEM_001 编译期错误。

> Bug #1–#3 涉及"`return` 中行为表达式""泛型专化崩溃"等子修复细节已分散记录于 §四 / §四b。

### 21.3 `DEFERRED_CLEANUP.md` 历史归档

> 全部 L1–L4 + C1–C14 条目已 ✅ DONE，详细落地说明见 §十七、§十九、§二十。本节仅留索引。

| 编号 | 主题 | 详细记录 |
|------|------|---------|
| L1   | `IbLambdaExpr.returns` 兼容字段彻底删除 | §十七 |
| L2   | `get_vars()` 硬编码内置函数过滤名单 → `is_builtin` 字段 | §十七 |
| L3   | `_pending_fn_return_type` 隐式上下文通道注释固化 | §十七 |
| L4   | `_collect_free_refs` 启发式子节点遍历注释固化 | §十七 |
| C1   | `LLMExceptFrame._is_serializable()` 死代码删除 | §十七 |
| C2   | `LLMExecutor.execute_behavior_expression` 中 `captured_intents` 旧路径分支删除 | §十七 |
| C3   | `ScopeImpl.define()` fallback UID 路径升级为断言 | §十七 |
| C4   | `IbDeferred.body_uid is None` 空值兼容路径审计 | §十七 |
| C5   | `ControlSignalException` 边界封装类删除 | §20.4 |
| C6   | CSE-Exception 双层桥彻底消除（含 IbTry/IbCall 异常透传桥） | §十九 + §20.2 |
| C7   | `assign_to_target()` 穿透到 StmtHandler 的 CPS generator helper 重写 | §20.2 |
| C8   | `vm_handle_IbLambdaExpr` / `vm_handle_IbBehaviorInstance` 全量 fallback 消除 | §20.1 |
| C9   | `vm_handle_IbImport` / `vm_handle_IbImportFrom` 真正 CPS 化 | §20.2 |
| C10  | `execute_module()` 与 `IbUserFunction.call()` 中重复的 `IbLLMExceptionalStmt` 跳过逻辑收敛到 `VMExecutor.run_body()` | §十七 |
| C11  | `node_protection` 侧表驱动的保护机制重定向设计改造（P1+P2+P3） | §20.4 |
| C12  | `_assign_future_to_name_target()` 直接操作 `ScopeImpl` 私有属性 → `define_raw()` / `is_cell_promoted()` 封装 | §十九 |
| C13  | `IbUserFunction.call()` 通过多级 `getattr` 脆弱查找 VMExecutor → 显式注入 | §20.3 |
| C14  | `BehaviorDependencyAnalyzer` 不感知 IbCell 提升 → `cell_captured_symbols` 侧表 | §20.1 |

