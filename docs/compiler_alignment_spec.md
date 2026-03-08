# IBC-Inter 编译器架构与解释器对齐规范 (Compiler Alignment Spec)

**版本：** 1.0 (Phase 6 架构清理后)
**状态：** 核心基建完备，支持平铺池化序列化与语义自检。

---

## **一、 编译器现状总结**

目前 IBC-Inter 编译器已经完成了从“实验性脚本”到“工业级解耦架构”的蜕变。其核心能力如下：

1.  **多轮深度语义分析 (Multi-Pass Analysis)**：
    -   **Pass 1 (Collector)**: 提取全局/局部定义，构建符号表骨架。
    -   **Pass 2 (Resolver)**: 解析类型引用（如变量标注、函数签名）。
    -   **Pass 3 (Analyzer)**: 执行类型推导、运算符重载校验、作用域检查及成员访问合法性验证。
2.  **侧表化架构 (Side-Tabling)**：
    -   AST 节点在分析阶段保持 **100% 纯净且只读**。
    -   所有的语义分析结论（符号绑定、推导类型、执行场景）均存储在独立的“侧表”中。
3.  **平铺池化序列化 (Flat Pooling Serialization)**：
    -   支持将复杂的、具有循环引用的内存对象图转换为扁平的、基于 UID 引用的 JSON 字典。
    -   消除了内存地址依赖，为分布式执行和跨进程通信奠定了基础。
4.  **语义完整性自检 (Integrity Checker)**：
    -   编译器在交付产物前会进行“闭环验证”，确保所有 Name/Attribute 节点均已正确绑定到符号池。

---

## **二、 核心目录架构**

编译器逻辑严格遵循“关注点分离”原则：

-   `core/domain/`: **共享契约层**。定义了 AST (`ast.py`)、Token (`tokens.py`)、Symbol (`symbols.py`) 和 StaticType (`static_types.py`) 的数据结构。它们是编译器和解释器的共同语言。
-   `core/compiler/`: **生产逻辑层**。
    -   `lexer/` & `parser/`: 源码 -> 纯净 AST。
    -   `semantic/passes/`: 纯净 AST -> 语义分析结论。
    -   `serialization/`: 语义结论 -> 扁平化池字典。
    -   `scheduler.py`: 负责多文件依赖调度。
-   `core/engine.py`: **门面 (Facade)**。提供一键式 `compile()` 和 `run()` 接口。

---

## **三、 编译器产物 (Compiler Output) 结构**

解释器应获取 `CompilationArtifact.to_dict()` 的输出，其结构如下：

### **1. 根引用**
-   `entry_module`: 入口模块名称。
-   `modules`: 模块字典，每个模块包含：
    -   `root_node_uid`: 该模块 AST 的起始节点。
    -   `root_scope_uid`: 该模块的顶层作用域。
    -   `side_tables`: 侧表集合（见下文）。

### **2. 四大全局池 (Pools)**
-   **Nodes Pool**: 存储 AST 节点。字段包含 `_type` (如 `If`, `Assign`) 和子节点 UID。
-   **Symbols Pool**: 存储符号定义。包含 `name`, `kind` (VARIABLE/FUNCTION/CLASS), `type_uid`, `owned_scope_uid`。
-   **Scopes Pool**: 存储作用域层级。包含 `parent_uid`, `symbols` (名称到 Symbol UID 的映射)。
-   **Types Pool**: 存储静态类型。包含 `_type` (如 `IntType`, `ClassType`), `key_type_uid` 等推导元数据。

### **3. 核心侧表 (Side Tables)**
-   `node_to_symbol`: **UID 映射**。解释器通过它将 `Name` 节点直接关联到符号池中的 UID。
-   `node_to_type`: **类型视图**。记录表达式节点的静态推导类型名，供解释器做动态分派参考。
-   `node_scenes`: **上下文标签**。标记节点处于 `BRANCH` (分支) 或 `LOOP` (循环) 场景，直接影响 LLM 意图的执行策略。

---

## **四、 解释器交互准则 (Interpreter Interaction)**

### **1. 解释器应该获取什么？**
-   **UID 引用**：解释器应养成“查表执行”的习惯。遇到 `Name` 节点，先去 `node_to_symbol` 查 UID，再去 `symbols` 池拿元数据。
-   **静态类型元数据**：在执行 `1 + 2.5` 时，解释器可以参考 `node_to_type` 里的 `float`，以决定调用哪个底层的运算符实现。
-   **Scene 标签**：在执行意图代码时，必须检查当前节点的 `Scene`。例如，`LOOP` 场景下的意图可能需要不同的 Prompt 策略。

### **2. 解释器不应该获取什么？**
-   **不应直接实例化 AST 类**：解释器应直接在字典池上工作。如果需要反射，应参考 `core/domain/ast.py` 作为 Schema 模板，而不是运行时的依赖。
-   **不应持有内存指针**：所有引用必须通过 UID 字符串进行。

### **3. 关键内部细节 (对实现解释器有益)**
-   **一切皆对象 (Everything is Object)**：编译器已经保证了即使是 `int` 或 `str` 在池中也有对应的 `TypeSymbol`。解释器可以统一处理成员访问。
-   **符号遮蔽 (Shadowing)**：编译器已处理完作用域遮蔽。同一个名字 `x` 在不同作用域下会映射到**不同的 Symbol UID**。解释器不需要再实现复杂的变量搜寻逻辑，直接信任侧表即可。
-   **局部作用域导出**：函数符号 (`FunctionSymbol`) 的 `owned_scope_uid` 指向了该函数内部的符号定义。解释器在进入函数时，应创建一个新的运行时 Frame，并加载该作用域。

---

## **五、 质量承诺**

-   **全量覆盖**：38 项单元测试覆盖了从简单语法到复杂 OOP 继承的所有路径。
-   **完整性保障**：自检校验器确保了所有交付的侧表均无断链风险。
-   **Schema 稳定**：`core/domain` 层的重组已完成，数据契约进入稳定期。

---
** IBCI 编译器团队 **
*2026-03-08*
