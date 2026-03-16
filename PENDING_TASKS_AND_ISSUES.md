# IBC-Inter 2.0 未完成任务与深度审计发现 (Pending Tasks & Issues)

本文件是 IBC-Inter 项目当前所有已知缺陷、架构风险、技术债以及后续演进方向的**唯一权威清单**。本文件内容不允许进行精简或总结，所有条目必须保留原始审计细节。

## 1. 架构违规与“不可容忍”项 (Critical)

### **1.1 局部 Import 规避循环引用 (Architecture Compromise)**
在核心逻辑路径中发现多处局部 `import`，这表明架构尚未完全闭合：
- **[stmt_handler.py:L167]**: `from core.runtime.objects.builtins import IbList` (用于 `visit_IbFor`)。
- **[kernel.py:L543-544]**: `from core.runtime.objects.intent import IbIntent, IntentRole` (用于 `_invoke_function`)。
- **[runtime_context.py:L382]**: `from core.domain.intent_resolver import IntentResolver` (用于 `get_resolved_prompt_intents`)。
- **[declaration.py:L265-266]**: `from core.compiler.lexer.lexer import Lexer` (用于解析内嵌表达式)。
- **[service.py:L103]**: `from core.runtime.objects.kernel import IbObject, IbNativeObject` (用于环境重绑定)。

### **1.2 穿透禁令审计 (Penetration Audit)**
- **任务**: 进行全量 Grep 检查，严禁出现 `context.interpreter` 或 `context.runtime_context.registry` 等违规链条。
- **风险**: 穿透调用会破坏组合解耦的物理隔离。

### **1.3 层级定义错位 (Layer Violation)**
- **问题**: `ServiceContext` 协议目前定义在 `Foundation` 层，但其成员（如 `llm_executor`）属于高层 `Runtime` 逻辑。
- **对策**: 将 `ServiceContext` 协议定义下沉至 `core/runtime/interfaces.py`，从基座层剥离。

### **1.4 插件系统符号化正规化 (Plugin Symbolization Regularization)**
- **问题**: 当前 `SemanticAnalyzer` 中存在针对旧版插件 Spec 的动态包装补丁。这些插件在 `ModuleMetadata.members` 中直接存储 `TypeDescriptor` 而非 `Symbol`，违反了 IES 2.1 架构规范。
- **正规化方案**: 
    1. 修改 `core/runtime/module_system/loader.py` 或 `ModuleMetadata.__post_init__`。
    2. 在插件元数据加载完成后，统一调用 `SymbolFactory` 将其成员转换为 `Symbol` 对象。
    3. 更新 `ibc_modules/` 下的所有插件 `_spec.py`，使用正规的符号定义方式。
    4. 完成后移除 `semantic_analyzer.py` 中的 `[TEMP PATCH]`。
- **风险**: 延迟处理会导致编译器逻辑中充满防御性代码。

### **2.1 类字段初始化求值盲区 (Evaluation Gap)**
- **问题**: `_hydrate_user_classes` 在 STAGE 5 执行，此时环境尚未闭合，无法评估非字面量表达式（如 `int x = a + b`），导致类字段变为 `None`。
- **任务**: 重构实例化逻辑，在解释器环境就绪后的预评估阶段或实例化时按需求值。

### **2.2 STAGE 6 深度契约校验 (Verification)**
- **任务**: 实现方法签名、参数数量及类型的静态一致性验证。
- **风险**: 缺乏深度校验会导致执行期抛出难以追踪的 `AttributeError` 或类型错误。

### **2.3 内置符号冲突校验 (Symbols)**
- **任务**: 在 `SymbolTable.define` 中增加对内置符号覆盖时的类型一致性检查。
- **风险**: 同名但不同类型的内置符号冲突会导致不可预知的解析结果。

## 3. 技术债清理与硬编码移除 (Medium)

### **3.1 元数据公理化下沉 (Metadata Axiomatization)**
- **问题**: `_is_scope_defining` 中的节点类型列表仍属于硬编码。
- **对策**: 将该属性下沉至 AST 定义或 `TypeDescriptor` 中，通过标记 `_is_scope: true` 来驱动压栈。

### **3.2 运行时不可变性加固 (Immutability)**
- **任务**: 在 `IbClass.register_method` 接口中增加显式的状态检查，禁止在封印后修改。

### **3.3 引导层去硬编码 (Bootstrap)**
- **任务**: 将 `builtin_initializer.py` 中的硬编码 Axiom 映射表完全迁移至公理定义层。

### **3.4 调试逻辑与池化校验下沉 (Clean)**
- **任务**: 将 `interpreter.py` 中的池化校验（L592-607）迁移至 `ReadOnlyNodePool`。
- **任务**: 移除 `interpreter.py` 中的硬编码压栈节点白名单（L627-639），改为元数据驱动。

### **3.5 Legacy 模式与伪装层移除 (Clean)**
- **任务**: 清理 `discovery.py` 中对无 spec 模块的冗余兼容逻辑。
- **任务**: 在 UTS 完全接管后，移除描述符中的 `type_info` 兼容属性（`descriptors.py#L73-78`）。

## 4. 深度审计清单遗留项 (Audit Findings)

- **[Audit Item 13]**: `discovery.py#L48-50` 违规操作。契约加载失败仅 print 跳过，违反了“Fail-fast”原则。
- **[Audit Item 14]**: `stmt_handler.py#L321-324` STAGE 6 模式下缺乏深度契约校验。
- **[Audit Item 15]**: `stmt_handler.py#L324-333` 保留动态回退逻辑，属于为“绕过封印非法执行”留下的技术后门。
- **[Audit Item 11]**: `registry.py#L143-148` 严重架构违规。`Foundation` 层直接持有 `Runtime` 层的解释器实例。

## 5. 发现的新问题 (New Findings)

- **llm_fallback 逻辑膨胀**: `BaseHandler` 中的 `_with_llm_fallback` 逻辑过于泛化，缺乏针对不同节点的差异化处理。
- **资产加载安全性**: 缺乏对外部 Prompt 资产的哈希指纹（SHA-256）校验。
- **TODO 标记**:
  - `interpreter.py:L66`: `# TODO: 适配新的意图捕获逻辑`
  - `builtin_initializer.py:L73`: `# TODO: 未来应将此映射下沉到 Axiom 或 Factory 中`
- **简化处理风险**: `primitives.py:L353`: `# 异常兼容性：... (这里简化处理)`。

## 6. 深度治理执行路线图 (Detailed Execution Roadmap)

### **Phase 1: 架构协议化与层级隔离 (Framework Level)**
*   **目标**: 彻底切断跨层级物理依赖，通过接口（Protocol）和依赖注入（DI）消除局部 `import`。
*   **1.1 核心实体协议化**:
    *   在 `core/runtime/interfaces.py` 中定义 `IIbObject`, `IIbClass`, `IIbFunction`, `IIbList`, `IIbIntent` 等协议。
    *   **技术细节**: 使用 `typing.Protocol` 描述这些对象的公共接口。
*   **1.2 引入对象工厂 (IObjectFactory)**:
    *   在 `IExecutionContext` 接口中增加 `factory: IObjectFactory` 属性。
    *   `IObjectFactory` 负责创建 `IbList`, `IbIntent` 等具体对象，解释器通过工厂获取实例，不再直接导入具体类。
    *   **代码位置**: `core/runtime/interpreter/factory.py` (实现), `core/runtime/interfaces.py` (协议)。
*   **1.3 ServiceContext 重定位与解耦**:
    *   将 `ServiceContext` 协议移至 `core/runtime/interfaces.py`。
    *   重构 `ServiceContextImpl` 构造函数，确保其不接收 `Interpreter` 实例。

### **Phase 2: 地基公理化与封印加固 (Foundation Level)**
*   **目标**: 提升 `Registry` 安全性，实现逻辑下沉。
*   **2.1 Axiom 映射表下沉**:
    *   重构 `core/domain/axioms/`，每个公理类（如 `IntAxiom`）自描述其对应的内置方法和转换逻辑。
    *   `builtin_initializer.py` 仅负责循环调用公理类的注册接口。
*   **2.2 Registry 封印强制化**:
    *   在 `IbClass` 的 `register_method` 和 `register_field` 中添加状态校验：`if self.registry.is_sealed: raise PermissionError(...)`。
*   **2.3 元数据驱动作用域判定**:
    *   在 `SemanticAnalyzer` 的语义分析阶段，根据节点类型在 `node_data` 中注入 `_is_scope: true` 标记。
    *   解释器 `_is_scope_defining` 方法仅检查此标记，不再硬编码类型列表。

### **Phase 3: 执行细节修复与技术债清理 (Execution Level)**
*   **目标**: 解决具体的功能性缺陷和时序问题。
*   **3.1 类字段延迟评估 (Late Evaluation)**:
    *   在 `Interpreter.run()` 启动前，增加 `STAGE 5.5: PRE_EVAL` 阶段。
    *   遍历所有用户类，对 `default_fields` 中非字面量节点进行求值并更新快照。
*   **3.2 深度契约校验实施**:
    *   在 `IbClassDef` 访问器中，对比 `node_data` 定义的方法与 `Registry` 中注册的描述符。
    *   校验参数个数、位置及默认值占位符。
*   **3.3 局部导入全面清理**:
    *   全量替换 `stmt_handler.py` 等文件中的局部 `import` 为 `execution_context.factory.create_xxx()`。

## 7. 后续演进方向 (Roadmap - Phase 4.4+)

### **7.1 核心演进方向 (非即时任务)**
- **idbg 2.0 (交互式调试器)**: 实现回溯、帧选择、意图感知调试。
- **内核 Core Dump**: 导出 `.ibdump` 文件（CallStack + Registry + VariablePool）。
- **issue_tracker 2.0 (上下文诊断)**: 错误报告关联源码片段和语义意图链。

---

## 附录：合并文档参考 (No Data Loss Reference)

### **A. 核心哲学与架构三层模型 (From architecture_design_guide.md)**
- **蓝图层 (Domain)**: AST (只读), Symbols, Types, Artifact (契约)。
- **生产层 (Compiler)**: Multi-Pass 语义分析 (Collector, Resolver, Analyzer), Side-Tabling (侧表化存储分析结论)。
- **消费层 (Runtime)**: Flat Pooling (UID 16位 Hex), UID-Based Walking, Rebinding Protocol (热替换)。

### **B. 语言规范关键点 (From ibc_inter_language_spec.md)**
- **变量系统**: 强类型声明 + `var` 推断。
- **行为描述行 (`@~ ... ~`)**: 立即执行 vs 延迟执行 (Lambda 化)。
- **意图系统**: 行级、块级意图；叠加 (`+`) 与 唯一 (`!`) 模式。
- **控制流**: `llmexcept` / `retry` / `for @~ ... ~`。
- **类系统**: `__init__`, `__to_prompt__` 协议。
- **物理限制**: 递归深度安全阈值 (4x Python 帧)；`max_instructions` 限制。

### **C. 插件系统规范 (From ibc_extension_system_guide.md)**
- **三层分离**: `_spec.py` (契约), `core.py` (逻辑), `__init__.py` (门面)。
- **Proxy VTable**: 自动拦截返回值并应用 `box()`。

---
*记录日期: 2026-03-16*
*状态: 深度治理期 (IES 2.1)*
