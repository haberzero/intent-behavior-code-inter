# IBC-Inter 核心架构审计与深度分析报告

## 1. 当前探查到的核心问题记录 (Findings)

### A. 意图系统 (Intent System) 的协议碎片化
*   **现象**：`llm_executor.py` 在处理意图合并时，需要兼容 `IntentNode`、`SimpleNamespace`、`dict` 等多种数据结构，并对 `mode` 字段（如 `override`, `!`, `+`, `append`）进行多重映射判断。
*   **深层成因**：
    *   **编译器端**：`ast.IbIntentInfo` 定义了原始符号（如 `!`, `+`, `-`）。
    *   **解释器端**：`visit_IbIntentStmt` 为了方便访问，在运行时临时构造了 `SimpleNamespace`。
    *   **执行器端**：`LLMExecutor` 处于链路末端，被迫承担了所有的“格式转换”和“语义对齐”工作。
*   **潜在风险**：缺乏统一的 `RuntimeIntent` 领域模型，导致意图在跨作用域（尤其是 Lambda 化的 Behavior）传递时，状态一致性难以保障。

### B. 统一类型系统 (UTS) 的内部术语泄露
*   **现象**：AI 收到 `预期返回类型：behavior` 的提示，导致逻辑理解混乱。
*   **深层成因**：
    *   `core.domain.symbols.BehaviorType` 将其内部名称定为 `"behavior"`。
    *   解释器在推导预期类型时，直接透传了该名称。
*   **架构冲突**：编译器内部的“控制流辅助类型”不应等同于面向 AI 的“语义交互类型”。这违反了 **“一切皆对象”** 中对象对外表现应具有一致语义的原则。

### C. LLM 执行生命周期的不完整性
*   **现象**：`BehaviorExpr` 的执行路径（`execute_behavior_expression`）与 `LLMFunction` 的执行路径在可观测性（`last_call_info`）上存在差异，导致 `idbg` 调试工具在特定语法下失效。
*   **成因**：`LLMExecutor` 的核心方法设计过于离散，没有形成统一的 `Prompt -> Call -> Record -> Parse` 原子事务。

---

## 2. 与底层架构设计的冲突评估 (Architectural Conflict Audit)

### 设计思想：一切皆对象 (Everything is an Object)
*   **当前做法**：意图在某些地方是对象，某些地方是字典或命名空间。
*   **冲突点**：意图本身也应是一个遵循特定协议的对象，而非散落在各处的临时元数据。

### 设计思想：编译器与解释器解耦
*   **当前做法**：解释器直接处理 AST 节点中的原始 `mode` 字符串。
*   **冲突点**：解释器应依赖于经过语义化的中间表示（IR）或领域符号（Symbols），而非直接操作语法层面的 Token 字符串（如 `!` 或 `+`）。

---

## 3. Domain 与 Foundation 基底检查 (Base Layer Inspection)

### Domain 层观察
*   **`ast.IbIntentInfo` 与运行时脱节**：AST 定义了意图的静态结构，但 `domain` 层缺乏对应的 `RuntimeIntent` 模型。这导致解释器在 `interpreter.py` 中不得不手动构造 `SimpleNamespace` 或 `dict` 来模拟对象行为。
*   **`StaticType` 语义单一**：`StaticType` 目前仅通过 `name` 属性与外部交互。对于像 `BehaviorType` 这种具有“内部/外部双重身份”的类型，缺乏语义映射机制（如 `alias_for_prompt`）。
*   **`CompilationResult` 侧表精度不足**：`node_to_type` 侧表目前仅存储 `type_name` (string)，丢弃了 `StaticType` 对象携带的丰富元数据。这导致解释器在执行时只能看到一个字符串，失去了进一步查询类型属性的能力。

### Foundation 层观察
*   **`Registry` 的对象工厂职责不明确**：`Registry` 擅长管理“类”，但不擅长管理“具有特定行为的系统级对象”（如 Intent）。目前 Intent 的创建逻辑散落在 `interpreter.py` 和 `llm_executor.py` 中。
*   **接口协议 (`interfaces.py`) 的模糊性**：`IIntentManager` 等接口大量使用 `Any` 或 `str`，没有在底层强制执行类型安全的领域对象契约。

---

## 4. 深度重构建议 (Proposed Structural Optimization)

### A. 引入 `IbIntent` 领域对象
*   在 `core.runtime.objects` 中定义正式的 `IbIntent` 类，继承自 `IbObject`。
*   将意图的模式转换（如 `!` -> `override`）和内容解析逻辑封装在 `IbIntent` 内部。
*   重构 `RuntimeContext`，使其意图栈强制存储 `IbIntent` 实例。

### B. 增强 `StaticType` 的语义映射
*   在 `core.domain.symbols.StaticType` 中增加 `get_prompt_name()` 方法。
*   `BehaviorType` 覆盖此方法，返回 `"str"` 或空，从而在不修改编译器逻辑的前提下，优雅地解决 AI 提示词污染问题。

### C. 提升侧表数据精度
*   修改 `SemanticAnalyzer`，让 `node_to_type` 侧表存储完整的 `StaticType` 对象。
*   更新 `FlatSerializer`，支持将 `node_to_type` 中的对象引用序列化到 `type_pool`。
*   这允许解释器通过 `registry.get_type(uid)` 获取完整的类型元数据，实现更智能的运行时推断。

---

## 5. 最终结论 (Final Conclusion)

目前的架构缺陷并非由于设计方向错误，而是由于 **“IES 2.0 演进过程中，部分运行时数据结构未能及时完成从『原始数据』到『领域对象』的蜕变』”**。

**结论**：
1.  **编译器缺陷**：侧表存储精度不足（Lossy Side-tables）。
2.  **解释器缺陷**：领域模型缺失导致的“逻辑堆叠”（Missing Runtime Domain Model）。
3.  **修复合理性**：通过在 `domain` 和 `objects` 层引入正式的意图对象和类型映射机制，可以从根源上消除 `llm_executor` 中的兼容性判断，这完全符合 **“一切皆对象”** 和 **“语义解耦”** 的设计思想。

**建议**：在确认上述分析后，启动针对 IES 2.0 的“领域对象规范化”重构，而非继续打补丁。
