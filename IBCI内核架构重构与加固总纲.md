# IBCI 内核架构重构与加固总纲 (Master Roadmap) - V2.8

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
*   **[内核瘦身]**：内置函数已插件化剥离；解释器流控异常已迁出 Domain 层。
*   **[多实例就绪]**：`Registry` 已实例化，`ServiceContext` 已实现动态同步。
*   **[绝对隔离]**：`IbInteger` 驻留池已实例隔离，全局单例注册表彻底移除。
*   **[职责纯化]**：`LLMExecutor` 职责解耦，运算符映射表迁出主类。
*   **[主动防御]**：引入 `IbASTView` (只读 AST 门面) 与 `SymbolView` (受限符号接口)。
*   **[协议对齐]**：全链路诊断信息（ErrorCode/Location）已标准化对齐。

---

## **3. 细化执行清单 (Detailed Execution Plan)**

### **第一阶段：解释器架构抛光与隔离加固 - [COMPLETED]**
*   **[P0] 内存残留清理 (Memory Isolation Polishing)**：已完成。
*   **[P0] 职责边界划定 (Responsibility Boundary)**：已完成。
*   **[P1] 移除 Fallback 兼容层 (Removing Legacy Callbacks)**：已完成。

### **第二阶段：Domain 主动防御与安全视图 (The Facade Layer) - [COMPLETED]**
*   **[P0] 引入 IbASTView (只读 AST 门面)**：已完成。
*   **[P1] 符号表安全视图 (SymbolView)**：已完成。
*   **[P1] 诊断信息标准化 (Diagnostic Alignment)**：已完成。

### **第三阶段：Foundation 外交网关加固 (Diplomatic Gateway) - [IN PROGRESS]**
*   **[P1] Registry 权限审计 (Access Control)**：
    - **目标**：为 `Registry` 增加来源校验。
    - **实现**：引入 `privileged_access` 令牌机制，确保只有内核初始化流程（如 `initialization.py`）能注册内置核心类。
*   **[P2] SourceProvider 协议化 (Diskless Diagnostics)**：
    - **目标**：实现诊断输出的“无盘化”。
    - **实现**：重构 `IssueTracker` 使其支持从 `SourceProvider` (内存缓冲区) 获取代码片段进行标注，而非强制读取磁盘文件。

---

## **4. 工作目标 (Definition of Success)**
1.  **受控的内核扩展**：任何非特权代码（外部插件）严禁污染内核 `Registry`。
2.  **无盘化诊断**：解释器与编译器支持在内存中直接生成带有上下文的高质量错误报告。
3.  **多引擎完美共存**：在同一进程内运行 N 个引擎，其内存足迹、常量缓存与类定义互不干涉。
