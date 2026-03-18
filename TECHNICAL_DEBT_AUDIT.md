# IBC-Inter 架构审计：深度技术债与逻辑断层汇总 (IES 2.1)

本文件详细记录了针对 IBC-Inter 项目进行的多次深度架构审计结果。作为 IES 2.1 演进的指导性文件，它记录了所有探测到的技术债、逻辑断层以及架构缺陷，包括精确的行号、根因分析及重构路径建议。

---

## 1. 名称依赖残留与泛型特化陷阱 (Subagent 1 深度审计报告) - **[FIXED]**
**核心问题：** 虽核心路径已采用 `resolve_specialization`，但在水化重建、诊断提示及结构判定中仍存在严重的字符串名称依赖。

### 1.1 诊断层硬编码 - **[FIXED]**
- **[DONE]** `get_diff_hint` 已下沉至 Axiom 协议，移除了 `descriptors.py` 中的字符串前缀比对。
- **[DONE]** 语义分析器错误消息已尽可能基于公理驱动。

### 1.2 结构化标识与兼容性依赖 - **[FIXED]**
- **[DONE]** `TypeDescriptor.__eq__` 和 `_is_structurally_compatible` 已重构为基于 `get_references()` 的多态判定。

### 1.3 泛型处理“双轨制” - **[FIXED]**
- **[DONE]** `type_hydrator.py` 已重构为映射驱动模式，并确保通过 `registry.register` 维持公理绑定一致性。
- **[DONE]** `descriptors.py` 与 `serializer.py` 已通过 `get_references()` 彻底移除了对 `ListMetadata`/`DictMetadata` 的 `isinstance` 依赖。

---

## 2. 元数据更新与结构性操作残留 (Subagent 2 深度审计报告) - **[FIXED]**
**核心问题：** `WritableTrait` 覆盖不全，导致结构性操作（Clone/Hydrate）依然强依赖于类身份判定。

### 2.1 隐秘的 'isinstance(..., FunctionMetadata)' - **[FIXED]**
- **[DONE]** 引入了 `walk_references(callback)` 模式，并在 `TypeDescriptor` 基类中实现了成员符号遍历。
- **[DONE]** `symbols.py`、`resolver.py`、`scheduler.py` 和 `hydrator.py` 中所有残留的 `isinstance(..., Metadata)` 检查已全部清除，改用 `is_class()`、`is_module()` 等抽象接口。
- **[DONE]** `SymbolFactory` 已重构为多态能力探测模式。

### 2.2 越权直接属性赋值 - **[FIXED]**
- **[DONE]** 通过 `walk_references` 统一了属性更新路径，并实现了 `deep_hydrate` 的多态化。

### 2.3 WritableTrait 局限性 - **[FIXED]**
- **[DONE]** `walk_references` 弥补了 `WritableTrait` 的结构递归缺失问题。

---

## 3. 编译器前端 (Parser) 隐秘假设 (Subagent 3 深度审计报告) - **[FIXED]**
**核心问题：** 除 `var`/`callable` 外，前端对特定标识符和语法结构仍有硬编码假设。

### 3.1 标识符硬编码 - **[FIXED]**
- **[DONE]** 移除了布尔值的字符串硬编码判断。
- **[DONE]** 修复了 `ExpressionComponent.grouping` 中的 `AttributeError` (self.parser -> self.context)。

### 3.2 语法结构局限 - **[FIXED]**
- **[DONE]** `IbCastExpr` 已重构为支持完整类型标注，支持泛型投射（如 `(list[int]) x`），且在语义分析阶段正确记录 `node_to_type`。

---

## 4. 产物完备性与 STAGE 7 验证盲区 (Subagent 4 深度审计报告) - **[FIXED]**
**核心问题：** 状态机流转存在健壮性风险，审计覆盖率不足。

### 4.1 审计盲区 - **[FIXED]**
- **[DONE]** `ContractValidator` 已补全对全局函数描述符的水合完整性审计。

### 4.2 状态机风险 (RegistrationState) - **[FIXED]**
- **[DONE]** `engine.py` 已增加 STAGE 6 状态强制检查，确保校验前环境就绪。
- **[DONE]** 解释器增加了对内核令牌缺失的诊断预警。

---

## 5. 攻坚任务清单 (Next Stage) - **[ALL FIXED]**
1. **[Foundation]** 引入 `TypeDescriptor.walk_references(callback)` 模式，消除所有结构操作中的 `isinstance`。 - **[DONE]**
2. **[Axiom]** 将诊断提示（Diff Hint）公理化，移除 `descriptors.py` 中的字符串比对。 - **[DONE]**
3. **[Refactor]** 统一 `type_hydrator.py` 的特化逻辑，使其遵循 `resolve_specialization`。 - **[DONE]**
4. **[Parser]** 移除 `self` 和布尔值硬编码，支持泛型 Cast 语法。 - **[DONE]**
5. **[Security]** 强化状态机，补全全局函数审计逻辑。 - **[DONE]**

---

## 6. 最终加固与接口纯化 (Subagent 联合终审报告) - **[FIXED]**
**核心问题：** 彻底清除历史兼容包袱，强化底层多态能力。

### 6.1 兼容性接口大清洗 - **[FIXED]**
- **[DONE]** 从 `HostInterface` 中彻底移除了 `# --- 兼容性接口 ---` 整个代码块（包括 `is_external_module`, `get_module_type` 等）。
- **[DONE]** `Engine.register_plugin` 已更名为 `register_native_module`，并移除了“兼容旧模式”的架构妥协标记。
- **[DONE]** `Scheduler`, `HostService`, `ModuleLoader` 等核心组件已迁移至直接使用 `MetadataRegistry` 的官方查询接口。

### 6.2 多态遍历补全 - **[FIXED]**
- **[DONE]** 为 `LazyDescriptor` 实现了 `walk_references`，解决了延迟加载描述符在克隆/水合时的递归断层。
- **[DONE]** `TypeHydrator.deep_hydrate` 已彻底消除对 `TypeDescriptor` 子类的 `isinstance` 依赖，完全转向多态遍历。

### 6.3 注册表官方查询增强 - **[FIXED]**
- **[DONE]** 在 `MetadataRegistry` 中引入了 `get_all_modules()`, `get_all_functions()`, `get_all_classes()` 等官方查询接口，替代了原有的 facade 包装。

---

## 9. 核心特性重构：LLM Fallback 体系解耦与纯态化 (Final Refactor) - **[FIXED]**
**核心问题：** 解决 `llm fallback` 导致的逻辑膨胀、代码冗余及状态耦合隐患。

### 9.1 AST 与解析链路纯化 - **[FIXED]**
- **[DONE]** `llm_fallback` 属性已从所有语句子类中移除，统一上移至 `IbStmt` 基类，消除了 AST 层的结构冗余。
- **[DONE]** `StatementComponent` 已重构。所有语句的 `llm except` 容错块现在通过 `parse_statement` 统一入口进行拦截解析。
- **[DONE]** **去硬编码化**：引入了 `IbStmt.supports_llm_fallback` 属性，通过 AST 节点的能力探测替代了原有的 `isinstance` 类型硬编码判定。

### 9.2 调度与执行解耦 - **[FIXED]**
- **[DONE]** 移除了 `BaseHandler` 中重复的 `_with_llm_fallback` 包装。
- **[DONE]** 在 `Interpreter.visit` 中实现了**全局统一容错调度**。现在所有的语句级重试和 Fallback 逻辑均在分发层闭环，避免了处理器（Handlers）层面的逻辑膨胀。
- **[DONE]** **指数级膨胀风险消除**：通过在分发层统一控制重试计数和上下文隔离，阻断了嵌套语句导致的冗余重试链条。

### 9.3 状态与提示词去中心化 - **[FIXED]**
- **[DONE]** `LLMExecutorImpl` 现已实现完全**无状态化**。原本私有的 `retry_hint` 已迁移至 `RuntimeContext` 统一管理，确保了执行服务的纯净性。
- **[DONE]** **提示词解耦**：所有针对特定语法节点（如 `if`, `while`）的专业化重试提示词已从内核代码中剥离，迁移至 `ai` 模块的 `get_retry_prompt` 接口中，实现了“内核逻辑”与“模型引导策略”的物理隔离。

### 8.1 彻底去 `isinstance` 化 - **[FIXED]**
- **[DONE]** `prelude.py` 已重构，使用 `get_call_trait()` 和 `is_module()` 替代对 `FunctionMetadata` 和 `ModuleMetadata` 的类身份判定。
- **[DONE]** `loader.py` 和 `module_spec_builder.py` 补全了能力探测逻辑，不再依赖 `isinstance` 分类描述符。

### 8.2 语法常量与枚举化 - **[FIXED]**
- **[DONE]** 意图模式（Intent Mode）在 `statement.py` 中已全面切换为 `IntentMode` 枚举值（`+`, `!`, `-`），消除了 `"normal"`, `"append"` 等硬编码字符串。
- **[DONE]** 公理层 `primitives.py` 的诊断提示已重构为基于 `_axiom` 类型的多态判定，消除了对 `.name == "int"` 的依赖。
- **[DONE]** `Parser` 中的逻辑运算符和复合赋值运算符已全部通过 `OP_MAP` 和 `COMPOUND_OP_MAP` 统一管理。

### 8.3 运行时补丁大清理 - **[FIXED]**
- **[DONE]** `llm_executor.py` 移除了关于 `retry_hint` 存储位置的兼容性注释，将其确认为标准字段。
- **[DONE]** `runtime_context.py` 彻底删除了“从列表重建链表”的兼容模式，强制要求基于 `IntentNode` 的原子化状态恢复。

### 8.4 描述符完备性增强 - **[FIXED]**
- **[DONE]** 为 `ClassMetadata` 和 `ModuleMetadata` 补全了 `get_references()` 实现，确保了结构化比对（`__eq__`）在复杂继承和模块场景下的客观性。
