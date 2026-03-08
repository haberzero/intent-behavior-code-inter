# IBC-Inter 内核架构重构计划清单 (Refactoring Checklist)

此清单用于记录和追踪 IBC-Inter 内核依赖重构的进度，确保彻底根治循环依赖，建立纯净的组件化架构。

---

## 核心原则
1. **零妥协**：绝不使用局部导入 (Local Import) 来规避架构缺陷。
2. **依赖单向化**：Foundation (底层) -> Domain (模型层) -> Compiler/Interpreter (执行层)。
3. **Everything is an Object**：所有类型装箱与行为分发均通过对象总线 (Registry) 调度。

---

## 重构阶段与任务详情

### 第一阶段：底座加固 - 异常与诊断下沉 (Bedrock)
- [x] **创建核心异常库**：在 `core/foundation/errors.py` 中定义 `Severity` 和 `Location`。
- [x] **异常定义迁移**：将所有 IBCI 专用异常 (`IBCBaseException`, `LexerError`, `ParserError`, `InterpreterError`, `SemanticError`, `LLMUncertaintyError`) 及控制流异常 (`ReturnException`, `BreakException` 等) 从 `Domain` 层迁移至 `Foundation` 层。
- [x] **全工程路径更新**：更新所有文件（涉及 30+ 文件）的 `import` 路径，统一从 `core.foundation.errors` 导入。
- [x] **清理旧定义**：彻底删除 `core/domain/exceptions.py`。
- [x] **诊断解耦**：确保 `core/domain/diagnostics.py` 仅包含高层逻辑，基础位置信息引用自 `foundation.errors`。

### 第二阶段：对象总线 - Registry 动态解耦 (Bus)
- [x] **增强注册表功能**：在 `core/foundation/registry.py` 中实现 `register_boxer(py_type, boxer_func)` 接口。
- [x] **内置类型自注册**：修改 `core/foundation/builtins.py`，让 `IbInteger`, `IbString`, `IbList` 等具体类在模块加载时自动向 `Registry` 注册自己的装箱逻辑。
- [x] **消除物理引用**：确保 `Registry` 不再硬编码任何 `Ib` 类名，完全通过注册的函数指针进行调度。

### 第三阶段：Bootstrapper “空心化”与纯净加载 (Pure Loader)
- [ ] **重构装箱逻辑**：修改 `core/foundation/bootstrapper.py` 中的 `box` 方法，移除所有 `if isinstance(...)` 的硬编码判断。
- [ ] **彻底清理局部导入**：移除 `Bootstrapper` 内部所有的 `from .kernel import ...` 和 `from .builtins import ...`。
- [ ] **职责回归**：确保 `Bootstrapper` 仅负责管理初始化顺序 (Initialization Sequence)，不参与具体的对象构建实现。

### 第四阶段：统一类型系统 (UTS) 物理隔离 (Isolation)
- [x] **描述符迁移**：将 `core/foundation/types/` 下的描述符 (Metadata) 迁移至 `core/domain/types/`。
- [ ] **符号表安全性加固**：在 `core/domain/symbols.py` 中为 `StaticType` 增加安全访问接口（如 `element_type`），防止编译器崩溃。
- [ ] **物理导入循环消除**：重构 `Foundation` 与 `Domain` 的边界，确保物理层面的单向依赖。
- [ ] **编译器解耦验证**：验证编译器 (Compiler) 可以在不加载 `Foundation.kernel` 的情况下完成语法分析和语义检查。

---

## 当前架构问题深度分析 (2026-03-08)

### 1. 核心循环依赖 (Core Circularity)
- **现象**：`IbObject` (Kernel) 引用 `IbClass` (Kernel)，而 `IbClass` 继承 `IbObject`。
- **成因**：静态导入导致的物理闭环。目前通过 `Bootstrapper` 的局部导入强制切断，但这违背了“零妥协”原则。
- **对策**：计划通过动态绑定机制，在初始化阶段完成类对象的链接，而非通过顶层导入。

### 2. 编译器脆弱性 (Compiler Fragility)
- **现象**：`SemanticAnalyzer` 在处理 `for` 循环或下标访问时，直接访问 `element_type` 导致 `AttributeError`。
- **成因**：`StaticType` 缺乏统一的成员访问契约，`Any` 类型没有兜底处理。
- **对策**：在 `Domain` 层加固 `StaticType` 基类，提供安全的默认实现。

### 3. 序列化降级 (Serialization Degradation)
- **现象**：`FlatSerializer` 在处理 `IbClass` 等复杂对象时，由于缺乏专用序列化逻辑，导致对象被降级为字符串。
- **成因**：序列化器对 `IbObject` 系统支持不足。
- **对策**：在完成 `Domain` 层重构后，需专门修复序列化器的分发逻辑。

### 第五阶段：全局局部导入大清理 (Cleanup)
- [ ] **解释器清理**：将 `core/runtime/interpreter/interpreter.py` 中所有的局部 `import` 移至文件顶部。
- [ ] **语义分析器清理**：将 `core/compiler/semantic/passes/semantic_analyzer.py` 中所有的局部 `import` 移至文件顶部。
- [ ] **依赖图验证**：使用工具或手动走查，确保全工程不再存在任何物理层面的循环依赖 (Circular Dependency)。

### 第六阶段：稳定性与集成验证 (Verification)
- [ ] **模块边界测试**：运行循环引用专项测试，确保 `ModuleManager` 的缓存机制在重构后依然稳健。
- [ ] **错误回溯验证**：验证抛出的 `InterpreterError` 是否依然能通过 `Location` 准确还原到源码行号。
- [ ] **回归测试**：运行全量单元测试，确保装箱 (Boxing)、消息发送 (Dispatching) 等核心逻辑无损。
