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
    - **HostInterface 集成**: 静态分析阶段会通过 `HostInterface` 自动发现外部注册的模块元数据。
6.  **Interpreter (解释器)**:
    - 接收经过校验的 AST，使用 **Visitor 模式** 递归执行。
    - 结果：程序执行输出或运行时错误。

---

## 2. 宿主接口与扩展架构 (Host Interface & Plugins)

这是 IBC-Inter 实现零硬编码和高度可扩展性的核心。

### 2.1 HostInterface (宿主接口)
`HostInterface` 是连接 Python 宿主环境与 IBCI 虚拟环境的桥梁。它统一管理：
- **静态元数据**: 模块的类型定义（ModuleType），供静态分析器使用。
- **运行时实现**: 模块的具体 Python 实现对象，供解释器调用。

### 2.2 自动推断与反射 (Reflection)
为了降低扩展门槛，`HostInterface` 支持自动推断：
- 当注册一个 Python 对象但未提供元数据时，系统通过 `dir()` 反射扫描其公共属性。
- 自动识别函数、类、变量，并将其影子映射到 IBCI 环境中。

### 2.3 插件系统与嗅探机制
- **IBCIEngine**: 封装了调度、编译、解释的完整生命周期。
- **自动嗅探**: 引擎启动时会自动扫描项目根目录下的 `plugins/` 文件夹。
- **setup() 钩子**: 允许插件开发者通过定义 `setup(engine)` 函数进行深度集成（如自定义注册名称、预注入变量等）。

---

## 3. 解释器深度剖析 (Interpreter Internals)

解释器是系统的核心，其设计目标是“高度解耦”与“原生互操作”。

### 3.1 ServiceContext 依赖注入
为了避免循环依赖并实现组件间协作，系统使用 `ServiceContext` 容器。
- `Interpreter` 持有 `ServiceContext`。
- 子组件（Evaluator, LLMExecutor, ModuleManager）通过 `ServiceContext` 访问彼此。

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
- **维修提示 (Retry Hint)**: 支持 `ai.set_retry_hint()` 注入。当 `llmexcept` 中调用 `retry` 时，执行器会自动将该 Hint 加入系统提示词。

---

## 4. 关键设计细节与逻辑妥协

1.  **双重类型检查**: 语义分析执行严格静态检查，解释器执行运行时兼容性检查。
2.  **错误捕获与 AI 容错**:
    - **llmexcept 冒泡机制**: 当 `LLMUncertaintyError` 发生时，解释器会向上寻找最近的 `llm_fallback` 块。
    - **retry 机制**: 通过 `RetryException` 实现闭环修复。
3.  **零硬编码标准库**:
    - 所有内置模块（ai, math, json）均通过 `stdlib_provider.py` 以插件形式注入，编译器核心不感知具体模块名称。

---

## 5. 对后续开发的指导建议

### 5.1 如何扩展功能？
- **极简扩展**: 在 `plugins/` 放入 `.py` 文件。
- **深度集成**: 实现 `setup(engine)` 钩子，调用 `engine.register_plugin()`。
- **语法扩展**: 需修改 `Lexer`, `Parser` 和 `Interpreter` 的对应组件。

### 5.2 注意事项
- **根目录依赖**: 引擎通过 `root_dir` 决定搜索路径，务必确保入口文件位置正确。
- **Mock 性能**: 在 `stdlib.py` 中已针对 `TESTONLY` 模式优化了 `OpenAI` 的延迟加载，新增插件时也应注意避免在全局作用域执行耗时操作。
