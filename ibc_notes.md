
## 架构重构：意图与类型系统 (Architecture Refactoring: Intent & Type System)

为了解决“兼容性补丁”带来的架构隐患，我们对核心系统进行了深度的重构（Refactoring），旨在消除技术债务并建立更健壮的领域模型。

### 1. 意图系统重构 (Intent System)
**问题**：意图对象在运行时表现为散乱的字典、`SimpleNamespace` 或元组，导致 `llm_executor` 中充斥着大量的类型检查和兼容性代码。
**重构**：
- 引入了 `core.runtime.objects.intent.IbIntent` 领域对象，统一封装意图的内容、模式（Mode）、来源（Source）和类型（Type）。
- **对象模型对齐**：将 `IbIntent` 实现为 `IbObject` 的子类，并在 `Bootstrapper` 中注册了 `Intent` 类型，使其成为运行时的一等公民。
- 更新了解释器（`Interpreter`）和上下文（`RuntimeContext`），在全链路中使用 `IbIntent` 对象传递意图。
- 移除了 `llm_executor` 中针对不同意图格式的 hack 代码，逻辑更加清晰。

### 2. 类型系统优化 (Type System)
**问题**：`BehaviorType`（行为描述行类型）在编译器中被命名为 "behavior"，这导致 LLM 提示词中出现 "Expected return type: behavior"，让 AI 产生困惑。
**重构**：
- 在 `StaticType` 基类中引入 `prompt_name` 属性，允许类型定义其在 Prompt 中的显示名称。
- `BehaviorType` 覆盖 `prompt_name` 为 "str"，明确告知 AI 行为描述行的结果是字符串。
- 更新了语义分析器（`SemanticAnalyzer`），在生成 `node_to_type` 侧表时使用 `prompt_name`，从而在根本上解决了类型名称污染问题。

### 3. 执行器净化 (Executor Cleanup)
**成果**：得益于上述重构，`llm_executor.py` 中的 `_merge_intents` 和 `execute_behavior_expression` 方法变得更加简洁和安全，不再包含针对特定类型名称（如 "behavior"）的硬编码过滤逻辑。

### 4. 调试发现：编译器与运行时不一致性 (Debug Findings: Compiler-Runtime Mismatch)
**问题背景**：在对高级意图特性（覆盖 `@!`、删除 `@-`）进行单元测试时，暴露出了编译器层面的解析缺陷。

**详细分析**：
1.  **Lexer 模式切换的副作用 (@- 简写失效)**：
    *   **现象**：`@- "Global Intent"` 被解析为包含引号的字符串 `'"Global Intent"'`，导致运行时字符串匹配失败。
    *   **成因**：Lexer 在遇到 `@` 开头的简写时，会进入 `IN_INTENT` 模式。在此模式下，为了支持自然语言提示词，Lexer 贪婪地将后续字符（包括引号）都视为 `RAW_TEXT`，而没有将其作为字符串字面量处理。
    *   **影响**：导致 `remove` 操作无法准确命中目标意图。
    *   **修复**：修改了 `core_scanner.py` 中的 `_scan_intent_char`，增加了对引号的检测。如果遇到引号，暂时切换回 `STRING` 模式进行标准字符串解析，从而正确分离出 `STRING` token。

2.  **Parser 优先级问题 (intent ! 失效)**：
    *   **现象**：`intent ! "Override Intent": ...` 语法在运行时被识别为普通意图（`mode` 为空），导致排他逻辑失效。
    *   **成因**：`Parser._parse_intent_info` 方法在尝试匹配 `TokenType.NOT` (`!`) 时失败。这可能与 Token 流的预读机制或关键字解析优先级有关。
    *   **影响**：排他性意图退化为普通意图，破坏了意图控制流。
    *   **调试状态**：通过 `debug_parser.py` 验证了 Token 流的正确性 (`INTENT_STMT` -> `NOT` -> `STRING`)，但 Parser 依然未能正确匹配 `NOT`。目前推测问题可能在于 `stream.match` 的状态管理或 `intent_statement` 调用前的 token 消耗逻辑。

3.  **运行时逻辑缺失 (LLMExecutor)**：
    *   **现象**：`LLMExecutor` 的意图合并逻辑中，完全忽略了 `remove` (`-`) 模式的处理分支。
    *   **修复状态**：已在 `_merge_intents` 中引入了黑名单机制（`blacklist`）来处理 `is_remove` 标记，但由于上述编译器问题，目前该修复尚未在集成测试中完全生效。

4.  **临时性修复代码 (Temporary Fixes)**：
    *   **现象**：`LLMExecutorImpl._merge_intents` 中仍存在一行 `call_intent = IbIntent(...)` 的临时构造代码。
    *   **成因**：函数调用时的 `Call Intent`（如 `func(intent="...")`）目前仍以原始字典形式传递，未在调用栈早期被对象化。
    *   **风险**：这是架构上的不一致，虽然能工作，但使得 `Call Intent` 成为“二等公民”。

**结论**：
*   **基础功能可用性**：核心的解释运行机制是健全的。普通的意图注释（单次生效、无叠加/覆盖/删除）完全可用，且通过了回归测试。
*   **问题集中点**：问题主要集中在**高级意图控制流**（Override/Remove）的**编译器解析层**。这属于“高级特性”的实现缺陷，不影响基础功能的稳定性。

### 5. 待办事项 (Pending Tasks)
1.  **Parser 修复**：深入调试 `_parse_intent_info` 中的 `match` 逻辑，确保 `intent !` 能被正确解析。
2.  **集成测试**：在 Parser 修复后，重新运行 `test_intent_system.py`，验证 Lexer 和 Runtime 的修复是否共同生效。
3.  **架构优化**：考虑将 `Call Intent` 的对象化逻辑上移至 `IbLLMFunction.call` 或参数绑定阶段，消除 `LLMExecutor` 中的临时代码。
