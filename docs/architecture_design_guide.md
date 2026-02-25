# IBC-Inter 原型机架构设计指南 (深度版)

本文档旨在为后续开发者及 AI 协作智能体提供 IBC-Inter 系统的全方位技术视图。通过阅读本指南，你应当能够理解系统的数据流转、关键逻辑实现及架构设计决策，从而实现对底层的“黑盒化”调用并专注于功能扩展。

---

## 1. 系统全链路数据流转 (Data Flow)

IBC-Inter 的执行过程是一个标准的流水线模型，数据在不同阶段之间以特定的结构进行传递：

1.  **Source (源码)**: 用户编写的 `.ibci` 文件。
2.  **Scheduler (调度中心)**: 
    - 启动 `DependencyScanner` 识别所有 `import`。
    - 构建 `DependencyGraph` 并通过**拓扑排序**确定编译顺序。
    - 为每个文件启动编译链。
3.  **Lexer (词法分析)**: 
    - 产生 `Token` 流。
    - 特色：处理 `INDENT`/`DEDENT`（缩进敏感）及 `~~` (行为描述行) 的特殊解析模式。
4.  **Parser (语法分析)**:
    - 将 `Token` 流转化为 `AST (抽象语法树)`。
    - 使用组件化架构（Declaration, Statement, Expression 等组件）。
    - **场景自动标记**: 在解析 `if/while/for` 时，Parser 会自动为相关的行为描述表达式注入 `Scene` 标签（BRANCH/LOOP），用于后续 LLM 结果的强制校验。
5.  **Semantic Analyzer (语义分析)**:
    - 遍历 AST，填充 `SymbolTable`。
    - 执行静态类型检查，并为 AST 节点绑定作用域信息 (`ScopeNode`)。
6.  **Interpreter (解释器)**:
    - 接收经过校验的 AST，使用 **Visitor 模式** 递归执行。
    - 结果：程序执行输出或运行时错误。

---

## 2. 核心数据结构 (Core Typedefs)

理解以下数据结构是理解系统的关键，它们定义在 `typedef/` 目录下：

### 2.1 ASTNode (parser_types.py)
所有语法实体的基类。包含 `lineno`, `col_offset` 以及关联的 `scope`。
- **Stmt (语句)**: 如 `If`, `For`, `Try`, `Assign`, `FunctionDef`。
- **Expr (表达式)**: 如 `BinOp`, `Call`, `BehaviorExpr`, `Attribute`。
- **BehaviorExpr**: 特有的表达式，包含文本段和插值表达式列表。

### 2.2 Symbol & ScopeNode (symbol_types.py / scope_types.py)
- **Symbol**: 存储变量/函数的元数据，包括 `type_info` (语义类型) 和 `declared_type_node` (原始定义)。
- **ScopeNode**: 树状结构，维护父子作用域关系，支持符号解析 (`resolve`)。

### 2.3 Type System (utils/semantic/types.py)
- 采用 **PrimitiveType** (int, float, str) 和 **ContainerType** (list, dict)。
- **AnyType**: 对应 `var` 关键字，表示动态类型。
- **FunctionType**: 存储参数类型列表及返回值类型。

---

## 3. 解释器深度剖析 (Interpreter Internals)

解释器是系统的核心，其设计目标是“高度解耦”与“原生互操作”。

### 3.1 ServiceContext 依赖注入
为了避免循环依赖并实现组件间协作，系统使用 `ServiceContext` 容器。
- `Interpreter` 持有 `ServiceContext`。
- 子组件（Evaluator, LLMExecutor, ModuleManager）通过 `ServiceContext` 访问彼此，例如：`Evaluator` 在遇到复杂调用时会通过 context 回调 `Interpreter.visit()`。

### 3.2 Evaluator 与类型路由 (Type Routing)
`EvaluatorImpl` 负责所有算术和逻辑运算。
- **技术细节**: 维护 `_bin_handlers` 映射表，键为 `(op, type_left, type_right)`。
- **互操作性**: 当访问 `Attribute` 或调用方法时，直接利用 Python 的 `getattr`。如果对象是原生 Python 容器，则直接暴露其方法（如 `append`）。

### 3.3 LLMExecutor 与意图机制
这是 IBC-Inter 的灵魂所在。
- **意图栈 (Intent Stack)**: 存储在 `RuntimeContext` 中。解释器遇到 `@` 节点时执行 `push_intent()`，语句结束或函数退出时执行 `pop_intent()`。
- **提示词构建**: `LLMExecutor` 收集栈中所有字符串，拼接为增强约束。
- **场景化执行 (Scene-aware)**: 
    - 识别 AST 节点的 `scene_tag`。在 `BRANCH` 或 `LOOP` 场景下，执行器会切换至“确定性解析模式”，强制要求 LLM 返回 0 或 1。
    - **确定性校验**: 若 LLM 返回模糊结果，执行器会抛出 `LLMUncertaintyError`，这是触发 `llmexcept` 逻辑的开关。
- **维修提示 (Retry Hint)**: 支持 `ai.set_retry_hint()` 注入。当 `llmexcept` 中调用 `retry` 时，执行器会自动将该 Hint 加入系统提示词，引导 LLM 修正之前的错误。
- **占位符插值**: 使用正则表达式 `\$__(\w+)__` 在 `llm` 函数体中寻找并替换参数。

### 3.4 ModuleManager 与递归编译
- **加载逻辑**: 当遇到 `import` 时，`ModuleManager` 会调用 `Scheduler` 获取目标模块的 AST。
- **解释器工厂**: 它持有一个 `interpreter_factory`，用于为新模块创建独立的子解释器实例，执行完毕后将其全局作用域封装为 `ModuleInstance`。

---

## 4. 关键设计细节与逻辑妥协

1.  **双重类型检查**: 
    - 语义分析阶段执行严格的静态检查。
    - 解释器执行阶段执行运行时兼容性检查（`_check_type_compatibility`）。
    - **妥协原因**: 原型机需要同时支持强类型声明和 `var` 动态类型，双重检查能确保在 `var` 类型发生突变时仍能保持安全。
2.  **错误捕获与 AI 容错**:
    - 使用 Python 原生异常 `ReturnException`, `BreakException` 处理控制流跳转。
    - **llmexcept 冒泡机制**: 当 `LLMUncertaintyError` 发生时，解释器会寻找当前控制流节点关联的 `llm_fallback` 块。如果不存在，则向上冒泡至父级控制流节点的 `llmexcept`。
    - **retry 机制**: 在 `llm_fallback` 块中通过抛出 `RetryException` 触发。解释器捕获该异常后，会重新启动当前控制流节点的 `visit` 流程，从而实现闭环修复。
    - 用户级 `try-except` 捕获 `InterpreterError`。捕获后，异常消息会被提取为 `str` 供 IBCI 代码处理。
3.  **指令计数器**:
    - 解释器内置 `instruction_count` 和 `call_stack_depth` 限制，防止死循环和栈溢出。

---

## 5. 对后续开发的指导建议

### 5.1 如何扩展语法功能？
1.  在 `typedef/parser_types.py` 增加节点。
2.  在 `utils/lexer/core_scanner.py` 增加关键字。
3.  在 `utils/parser/components/` 对应的组件中增加 `parse_xxx` 逻辑。
4.  在 `Interpreter` 中增加 `visit_xxx` 方法。

### 5.2 如何增加新的内置库？
只需在 `utils/interpreter/modules/stdlib.py` 中编写一个 Python 类，定义静态方法，然后调用 `interop.register_package`。解释器会自动通过 `Attribute` 访问将其暴露给用户。

### 5.3 注意事项
- **黑盒边界**: 除非需要改变语言的基础解析逻辑，否则请保持 `Lexer` 和 `Parser` 目录不动。
- **类型安全**: 任何新的内置函数都应在 `utils/semantic/prelude.py` 中注册其 `FunctionType`，否则静态分析阶段会报错。
- **意图敏感**: 任何可能触发 AI 行为的新节点，都应确保在执行前正确合并了 `context.get_active_intents()`。
