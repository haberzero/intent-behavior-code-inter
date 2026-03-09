# IBCI 内核架构重构与加固总纲 (Master Roadmap) - V2.5

## **1. 核心架构哲学 (Architectural Philosophy)**
*   **Domain (契约层)**：系统的“宪法”。仅定义数据结构、静态逻辑与语法契约，**严禁包含运行时副作用及流控异常**。
*   **Foundation (基础设施层)**：系统的“内核”。提供环境无关的通用工具、协议与 API 网关。**支持多实例并行，无全局状态污染**。
*   **Compiler (分析层)**：系统的“智库”。执行静态语义分析，生成具有完整元数据的 Compilation Artifact。
*   **Runtime (执行层)**：系统的“动力室”。负责对象内存布局、执行流控制与 LLM 交互。**解释器仅作为 AST 调度器存在**。

---

## **2. 现阶段现状深度审计 (Status Audit)**

### **已巩固的阵地 (Consolidated)**
*   **[物理隔离]**：`Runtime` 与 `Foundation` 的物理循环依赖已切断。
*   **[契约收拢]**：插件通信协议（Protocol）已统一归口至 `core/foundation/interfaces.py`。
*   **[内核瘦身]**：内置函数（print, len 等）已成功插件化剥离至 `intrinsics` 目录。
*   **[动态上下文]**：`ServiceContext` 已实现动态 Context 同步，消除了多模块加载的作用域滞后。

### **暴露的隐患 (Identified Risks)**
*   **[单例污染 (Singleton Pollution)]**：`Registry` 和 `IntrinsicManager` 目前使用类级别静态变量。这阻碍了“动态宿主”愿景（多引擎实例隔离、运行时快照与恢复）的实现。
*   **[异常层级穿透 (Exception Contamination)]**：`ReturnException` 等流控信号目前物理存放在 `core/domain/issue.py` 中，污染了纯净的领域层。
*   **[诊断契约不一致]**：解释器的错误报告机制（Issue 报告）尚未与编译器诊断系统（Diagnostic/Severity）完全标准化对齐。

---

## **3. 细化执行清单 (Detailed Execution Plan)**

### **第零阶段：Foundation 协议收拢 (Protocol Consolidation) - [COMPLETED]**
*   **[P0] 契约归口管理**：已迁移所有 Protocol 至 `core/foundation/interfaces.py`。
*   **[P0] 定义 IIbObject 协议**：已实装，`idbg` 插件物理脱敏完成。

### **第一阶段：运行时 API 对齐与内核隔离 - [COMPLETED]**
*   **[P0] 修复 ServiceContext 动态 Context 机制**：已完成，解决跨模块作用域泄漏。
*   **[P1] 内置函数（Intrinsics）插件化重构**：已完成，`Interpreter` 成功瘦身。
*   **[P1] Builtins 职责拆分**：已完成，对象定义与引导逻辑分离。

### **第一阶段（续）：运行时隔离与领域纯净化 - [NEW - HIGH PRIORITY]**
*   **[P0] 注册表去单例化 (Registry De-singleton)**：
    - 将 `core/foundation/registry.py` 重构为实例模式。
    - **目标**：支持“动态宿主”，允许在同一进程中运行多个完全内存隔离的 IBCI 引擎。
*   **[P0] 领域层物理纯化 (Domain Purity)**：
    - 创建 `core/runtime/exceptions.py`。
    - 将所有运行时专用流控异常（Return, Break, Continue, Retry）从 Domain 层迁出。
*   **[P1] 解释器 Issue 机制标准化**：
    - 重写解释器错误报告入口，强制要求通过 `ServiceContext.issue_tracker` 报告 `Diagnostic` 对象。
    - 实现解释器与编译器在“外交网关”层面的错误协议对齐。

### **第二阶段：Domain 主动防御与安全视图 (The Facade Layer)**
*   **[P1] 引入 IbASTView & SymbolView**：
    - 实现基于代理模式的只读视图，确保插件严禁通过引用修改 AST 内部状态。
*   **[P2] 符号表作用域锁定**：
    - 在 `SymbolTable` 中增加锁定机制，防止非预期的动态符号注入。

### **第三阶段：Foundation 外交网关加固 (Diplomatic Gateway)**
*   **[P1] Registry 权限审计**：
    - 为实例化的 `Registry` 增加来源校验，确保只有持有特权的内核组件能注册内置类。
*   **[P2] SourceProvider 协议化**：
    - 实现诊断输出的“无盘化”，支持从内存缓冲区直接生成错误标注。

---

## **4. 工作目标 (Definition of Success)**
1.  **多引擎实例隔离**：在同一 Python 进程中启动两个引擎，修改其中一个的 Registry 不会影响另一个。
2.  **领域层 0 运行时污染**：`core/domain` 目录下不包含任何 `Exception` 派生类。
3.  **动态宿主就绪**：解释器现场（Context + Scope + Registry）可被完整序列化并跨实例恢复。
4.  **外交协议统一**：所有内核 Issue（编译器或解释器）通过 Foundation 暴露时，均遵循统一的 `Diagnostic` 契约。
