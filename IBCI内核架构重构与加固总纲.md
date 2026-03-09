# IBCI 内核架构重构与加固总纲 (Master Roadmap) - V2.0

## **1. 核心架构哲学 (Architectural Philosophy)**
*   **Domain (契约层)**：系统的“宪法”。仅定义数据结构与静态逻辑，无副作用。
*   **Foundation (基础设施层)**：系统的“内核”。提供环境无关的通用工具、协议与 API 网关（外交部）。
*   **Compiler (分析层)**：系统的“智库”。执行静态语义分析，生成 Compilation Artifact。
*   **Runtime (执行层)**：系统的“动力室”。负责对象的具体内存布局、执行流控制与 LLM 交互。

---

## **2. 现阶段现状深度审计 (Status Audit)**

### **已巩固的阵地 (Consolidated)**
*   **[物理隔离]**：`Runtime` 与 `Foundation` 的物理循环依赖已切断。`kernel.py` 成功从 Foundation 迁出。
*   **[真理源归一化]**：UTS (Unified Type System) 已在 Domain 层统一，消除了类型判定的双重标准。
*   **[编译器诊断系统]**：V2 版诊断系统已完工，支持精准的范围标注与错误码化。

### **暴露的隐患 (Identified Risks)**
*   **[内核肥胖症]**：`Interpreter` 承担了过多的内置函数实现逻辑，导致内核难以单独测试。
*   **[内置类逻辑过载]**：`Builtins.py` 混杂了对象定义、UTS 注册、原生代理三重职责。
*   **[权限控制真空]**：`HostInterface` 缺乏权限审计，存在被恶意插件篡改核心实现的风险。
*   **[双向引用与 Context 同步]**：`ServiceContext` 目前持有静态的 `RuntimeContext` 引用，在模块切换（Context Switch）时存在同步滞后，导致作用域泄漏或访问错误。
*   **[静态/动态错误不匹配]**：重构后的编译器能捕获更多静态错误，导致旧有的运行时测试（期望 InterpreterError）出现不匹配。

---

## **3. 细化执行清单 (Detailed Execution Plan)**

### **第零阶段：Foundation 协议收拢 (Protocol Consolidation) - [COMPLETED]**
*   **[P0] 契约归口管理**：已迁移所有 Protocol 至 `core/foundation/interfaces.py`。
*   **[P0] 定义 IIbObject 协议**：已实装，`idbg` 已脱离对 `runtime.objects` 的物理依赖。

### **第一阶段：运行时 API 对齐与内核“瘦身” (Kernel Dismantling) - [IN PROGRESS]**
*   **[P0] 修复 ServiceContext 动态 Context 机制**：
    - 修改 `ServiceContextImpl`，使其通过 `interpreter.context` 动态获取当前活跃的 `RuntimeContext`。
    - **目标**：解决 `ModuleManager` 和 `LLMExecutor` 在跨模块调用时，仍在使用旧作用域的严重 Bug。
*   **[P1] 内置函数（Intrinsics）插件化重构**：
    - 创建 `core/runtime/interpreter/intrinsics/` 目录。
    - 将 `Interpreter` 中的 `_builtin_print`, `_builtin_len` 等方法剥离为独立的“内核扩展 (Kernel Extensions)”。
    - **设计方案**：采用“特权插件”模式，通过 `Foundation.Registry` 统一注册与注入。
*   **[P1] 模块加载鲁棒性加固**：
    - 完善 `ModuleManager` 的循环引用处理逻辑，防止访问半初始化状态的模块成员。
    - 针对新编译器的静态分析能力，更新并对齐 `tests/test_interpreter_module.py` 的断言。
*   **[P1] Builtins 职责拆分**：
    - 将 `IbInteger` 等对象的“内存布局定义”与“原生方法代理实现”在物理文件上分离。

### **第二阶段：Domain 主动防御与安全视图 (The Facade Layer)**
*   **[P1] 引入 IbASTView & SymbolView**：
    - 实现基于代理模式的只读视图。
    - **目标**：确保外部插件通过 `Foundation` 获取 AST 时，只能读取信息，严禁通过引用修改内部状态。
*   **[P2] 符号表访问权限控制**：
    - 在 `SymbolTable` 中增加作用域锁定机制，防止非预期的符号注入。

### **第三阶段：Foundation 外交网关加固 (Diplomatic Gateway)**
*   **[P1] Registry 权限审计**：
    - 为 `Registry` 的关键操作（如 `register_class`）增加调用栈来源校验，确保只有核心 Runtime 能注册内置类。
*   **[P2] SourceProvider 协议化**：
    - 彻底解耦 `DiagnosticFormatter` 对物理文件系统的依赖，实现“无盘化”诊断输出。

### **第四阶段：全局架构大清理 (The Final Polish)**
*   **[P2] 彻底消灭局部导入 (Local Import)**：
    - 在确保循环依赖物理消除的前提下，将全工程剩余的局部导入（原本为了绕过循环引用）全部移至文件顶部。
*   **[P2] 依赖图合法性自动化测试**：
    - 编写 `test_dependency_graph.py`，利用静态分析工具确保 `core/domain` 不会反向依赖任何其它目录。

---

## **4. 涉及的代码改动预估 (Scope of Change)**
*   **core/runtime/interpreter/**：重灾区。需要进行大量的逻辑拆分与接口对齐。
*   **core/runtime/objects/**：需要将 `Builtins` 拆分为 `definitions` 与 `proxies`。
*   **core/domain/ast.py & symbols.py**：增加大量的 `View` 类定义。
*   **core/foundation/registry.py**：增加权限校验装饰器。

---

## **5. 工作目标 (Definition of Success)**
1.  **物理隔离 100%**：无局部导入，无双向物理依赖。
2.  **职责内聚**：`Interpreter` 仅负责 Visit，不负责实现具体的内置逻辑。
3.  **插件安全**：插件在不读取 `core/runtime` 源码的前提下，通过 `Foundation` 即可完成 90% 的扩展工作。
4.  **测试全通**：所有解释器与编译器的单元测试回归通过。
