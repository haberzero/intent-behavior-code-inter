# IBCI 基石架构深度审计清单 (2026-03-09)

## **1. 架构层级倒置 (Layer Inversion) - 致命风险**
*   **[Kernel 依赖 Runtime]**：[kernel.py](file:///c:/myself/proj/intent-behavior-code-inter/core/foundation/kernel.py) 中的 `IbUserFunction.call` 直接持有并调用了 `Interpreter` 及其 `visit` 方法。
    - **后果**：作为系统最底层的 Foundation 层，强行依赖了最上层的执行引擎。这导致无法在不拉起整个解释器的情况下独立测试或使用基础对象模型。
*   **[耦合执行逻辑]**：`IbObject`、`IbFunction`、`IbLLMFunction` 等带有重度运行时执行逻辑（作用域管理、消息分发、LLM 调用）的类被放置在 Foundation 层。
    - **建议**：Foundation 应仅包含“对象的定义”和“接口协议”，具体的“执行实现”必须迁移至 `core/runtime`。

## **2. 类型系统 (UTS) 的分裂与冗余 - 逻辑隐患**
*   **[真理源冲突]**：系统目前并存两套类型描述逻辑：
    - `core/domain/types/descriptors.py` 中的 `TypeDescriptor` 体系。
    - `core/foundation/kernel.py` 中的 `Type` 类族（`ListType`, `FunctionType` 等）。
*   **[兼容性逻辑重复]**：两套体系各自实现了 `is_assignable_to` 逻辑。
    - **后果**：编译期的类型检查逻辑与运行期的类型校验逻辑可能产生歧义，导致“编译通过但运行崩溃”或“运行合法但编译报错”。
*   **[建议]**：彻底合并两套体系，将 `TypeDescriptor` 升级为全系统唯一的类型真理源。

## **3. Domain 层的被动性与安全性缺失 - 插件风险**
*   **[缺乏防御性 Facade]**：Domain 层（如 `IbASTNode`, `Symbol`）目前是裸露的 dataclass。
    - **现状**：外部代码（特别是未来的插件）可以不受限制地直接读写这些核心数据结构。
    - **后果**：任何插件的逻辑错误都可能直接污染全局 AST 或符号表，导致系统发生不可预测的灾难性崩溃。
*   **[协议不完备]**：虽然引入了 `Locatable` 协议，但 Domain 层缺乏一套标准化的“主动暴露”接口（如 `to_view()`, `as_readonly()`），无法支持安全的数据存取机制。

## **4. 依赖管理与循环引用 - 维护风险**
*   **[注册表依赖症]**：[registry.py](file:///c:/myself/proj/intent-behavior-code-inter/core/foundation/registry.py) 作为全局单例 Service Locator，被用来强行打破 `Kernel`、`Builtins` 和 `Bootstrapper` 之间的循环引用。
    - **后果**：这是一种典型的“架构胶带”。它掩盖了对象模型设计上的职责不清，使得依赖关系变得隐晦且难以追踪。
*   **[Runtime 协议泄漏]**：[interfaces.py](file:///c:/myself/proj/intent-behavior-code-inter/core/foundation/interfaces.py) 中定义了大量仅与运行时相关的协议（如 `LLMExecutor`, `ModuleManager`）。
    - **后果**：Foundation 层承担了过多的“运行时契约管理”职责，变成了运行时的附属品。

## **5. 诊断系统的物理隔离残余 - 耦合风险**
*   **[SourceManager 倒置引用]**：[DiagnosticFormatter](file:///c:/myself/proj/intent-behavior-code-inter/core/compiler/diagnostics/formatter.py) 仍需感知 `SourceManager` 的具体实现。
    - **现状**：虽然已将 `SourceManager` 下沉至 Foundation，但格式化逻辑对它的依赖应进一步抽象为“源码提供者协议”，以支持未来从内存、网络或缓存中读取源码的动态场景。

---
**审计结论**：IBCI 的“基石”目前处于**功能性过度负载**状态。Foundation 层混杂了过多的执行逻辑和运行时契约。如果不进行“脱敏”和“减负”，系统在引入插件体系或复杂动态宿主时将面临极高的崩溃风险。
