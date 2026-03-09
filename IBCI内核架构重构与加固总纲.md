# IBCI 内核架构重构与加固总纲 (Master Roadmap) - V2.7

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

---

## **3. 细化执行清单 (Detailed Execution Plan)**

### **第一阶段：解释器架构抛光与隔离加固 - [COMPLETED]**
*   **[P0] 内存残留清理 (Memory Isolation Polishing)**：已完成。
*   **[P0] 职责边界划定 (Responsibility Boundary)**：已完成。
*   **[P1] 移除 Fallback 兼容层 (Removing Legacy Callbacks)**：已完成。

### **第二阶段：Domain 主动防御与安全视图 (The Facade Layer) - [NEXT]**
*   **[P0] 引入 IbASTView (只读 AST 门面)**：
    - **目标**：防止外部插件（如 AI 模块或自定义 Intrinsic）通过引用直接修改已编译的 AST 节点。
    - **实现**：采用 Proxy 模式，为 `node_pool` 提供只读包装。
*   **[P1] 符号表安全视图 (SymbolView)**：
    - **目标**：在 `InterOp` 边界处，只暴露受限的符号查询接口。
    - **实现**：防止非预期的动态符号注入或全局作用域篡改。
*   **[P1] 诊断信息标准化 (Diagnostic Alignment)**：
    - 确保全链路（Lexer -> Parser -> Semantic -> Interpreter）的错误代码与位置信息完全遵循 UTS 契约。

### **第三阶段：Foundation 外交网关加固 (Diplomatic Gateway)**
*   **[P1] Registry 权限审计**：
    - 为实例化的 `Registry` 增加来源校验，确保只有持有特权的内核组件能注册内置类。
*   **[P2] SourceProvider 协议化**：
    - 实现诊断输出的“无盘化”，支持从内存缓冲区直接生成错误标注。

---

## **4. 工作目标 (Definition of Success)**
1.  **不可篡改的 AST**：外部插件严禁通过任何手段修改运行时载入的 AST 结构。
2.  **符号边界清晰**：解释器内部符号表与外部 Python 互操作层的边界由 `SymbolView` 严格把守。
3.  **多引擎完美共存**：在同一进程内运行 N 个引擎，其内存足迹、常量缓存与类定义互不干涉。
