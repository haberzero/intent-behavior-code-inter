# IBC-Inter 工程演进记录（已完成工作归档）

> 精炼记录各阶段已完成的代码与架构演进，时间线从早期向当前推进。
> **最后更新**：2026-04-18

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
| `(Type) @~...~` 废弃 | PAR_010 硬错误；LHS 类型自动成为提示词上下文 |
| 彻底重构原则 | 禁止渐进式补丁；完成则完整，不留旁路 |
| `LLMExecutorImpl` 不可替换 | 它是语言语义的一部分，provider 可配置，执行接口不可替换 |
