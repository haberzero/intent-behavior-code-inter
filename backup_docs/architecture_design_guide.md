# IBCI 2.0 架构设计指南

## 1. 核心哲学
IBCI 2.0 采用 **数据驱动 (Data-Driven)** 和 **侧表化 (Side-Tabling)** 的架构。核心目标是实现编译器分析逻辑与 AST 结构的完全解耦，并支持解释器在无内存依赖的环境下运行。

## 2. 三层解耦模型

### 2.1 蓝图层 (Domain Model - `core/domain/`)
作为“真理来源 (Source of Truth)”，蓝图层定义了 IBCI 语言的所有基本构成单元：
- **AST (`ast.py`)**：纯粹的数据结构，100% 只读。
- **Symbols (`symbols.py`)**：描述作用域和符号的语义。
- **Types (`static_types.py`)**：静态类型系统。
- **Artifact (`blueprint.py`)**：模块化的编译产出物契约。

### 2.2 生产层 (Compiler - `core/compiler/`)
负责将源码转换为蓝图。
- **Parser**: 采用中介者模式 (`ParserContext`) 处理复杂的组件依赖。
- **Semantic Analyzer**: 采用 **Multi-Pass** 机制：
  - **Pass 1 (Collector)**: 收集全局/局部符号。
  - **Pass 2 (Resolver)**: 决议继承链和类型引用。
  - **Pass 3 (Analyzer)**: 执行类型检查。
- **Side-Tabling**: 分析结果不写入 AST，而是存入 `node_to_symbol` 和 `node_to_type` 等映射表中。

### 2.3 消费层 (Runtime - `core/runtime/`)
执行编译器产出的扁平化蓝图。
- **Flat Pooling**: 解释器通过 `FlatSerializer` 获取扁平化的 JSON 字典池。UID 长度扩展至 **16 位 Hex** 以支持千万级规模的节点分布。
- **UID-Based Walking**: 解释器通过 UID 在池中游走，不再持有 Python 内存指针，实现了物理隔离。
- **Rebinding Protocol**: 解释器支持热替换 (Hot Reload)，允许在不破坏运行时变量现场的前提下更新底层逻辑实现。

## 3. 关键机制：语义网关 (TypeBridge)
IBCI 2.0 引入了 **TypeBridge** 作为编译器与运行时元数据之间的语义网关：
- **单源真理**：编译器不再硬编码内置类型，而是通过 `TypeBridge` 从引擎注册表 (`Registry`) 中动态同步元数据。
- **自动对齐**：当解释器注册新插件时，编译器通过网关自动识别插件定义的类和方法。

## 4. 意图系统与持久化优化
- **Immutable Intent Stack**: 管理层级化意图 (Global -> Block -> Call)。采用不可变链表 (`IntentNode`) 结构，支持 **结构共享 (Structural Sharing)**，极大降低了 Lambda 捕获时的内存开销。
- **Circular Reference Defense**: 在反序列化期间，采用 **“创建与填充分离 (Split Initialization)”** 模式，彻底解决了 `IbBoundMethod` 等复杂引用图在加载时可能导致的死循环问题。
- **Text Externalization**: 文本内容独立存储。将长文本、Prompts 与 JSON 元数据物理隔离，通过 `ext_ref` 进行软链接，确保了序列化系统的健壮性。
- **Scene Labels**: 编译器标记节点的执行场景 (BRANCH/LOOP)，解释器据此动态调整 Prompt 策略。
