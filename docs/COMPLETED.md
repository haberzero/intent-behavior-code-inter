# IBC-Inter 工程演进记录（已完成工作归档）

> 精炼记录各阶段已完成的代码与架构演进，时间线从早期向当前推进。
> **最后更新**：2026-04-20（Step 8 架构边界文档化；Bug 修复：IbBool(False) 假值判断、duplicate `_stmt_contains_behavior`、list[str]/dict[K,V] 泛型专化；610 个测试通过）

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
| `lambda` 不允许作为参数传递 | `deferred_mode='lambda'` 的延迟对象不可作为函数实参；`snapshot` 不受此限制 |
| `snapshot` 捕获意图快照 | `snapshot` 在定义位置调用 `fork_intent_snapshot()` 捕获当前意图栈的不可变副本 |
| `intent_context` is_class=True | `intent_context` 可实例化为 OOP 对象；用户可显式管理意图上下文（§9.5） |
