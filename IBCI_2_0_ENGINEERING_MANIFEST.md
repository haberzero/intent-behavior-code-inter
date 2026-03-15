# IBCI 2.0 工程技术宣言与深度审计清单 (2026-03-15)

## 1. 工程愿景与阶段性状态 (Engineering Vision & Current State)

IBCI 2.0 正处于从 **IES 1.0 (动态注入)** 向 **IES 2.0 (契约先行/物理隔离)** 演进的核心阶段。目前地基治理已基本完成，正在攻克多引擎隔离安全性与执行时序一致性。

### **1.1 已封印的核心特性 (Sealed Features)**
- **地基状态机**：`Registry` 实现 STAGE 1-6 严格单向状态跳转。
- **UTS 元数据系统**：统一描述符体系取代了原始 Python 类型映射。
- **两阶段插件加载**：实现元数据（STAGE 3）与实现（STAGE 4）的物理分离。
- **预水合机制**：用户类在 STAGE 5 完成实体创建，确保 STAGE 6 的不可变性。

### **1.2 核心设计哲学 (Philosophy)**
- **不可变执行环境**：READY 状态后禁止任何元数据篡改。
- **数据驱动分发**：解释器作为轻量级 Dispatcher，业务逻辑下沉至分片 Handler。
- **Fail-fast 契约**：任何违反 spec 的行为必须在加载期中断，严禁静默失效。

---

## 5. 上下文正规化专题：职责、层级与风险审计 (Context Regularization)

### **5.1 三大上下文的职责定义 (Clear Responsibilities)**
| 上下文类型 | 核心职责 | 物理层级 | 变动频率 |
| :--- | :--- | :--- | :--- |
| **`RuntimeContext`** | 存储变量、作用域、当前意图栈等**易变执行现场**。 | Runtime | 极高 (指令级) |
| **`IExecutionContext`** | 提供节点池、求值入口、栈内省等**执行资源网关**。 | Foundation | 低 (引擎级) |
| **`ServiceContext`** | 协调 LLM、模块管理、权限等**横向服务组件**。 | Runtime | 极低 (初始化级) |

### **5.2 核心架构风险 (Risk Audit)**
1. **[High] 层级定义错位 (Layer Violation)**: `ServiceContext` 协议目前定义在 `Foundation` 层，但其成员（如 `llm_executor`）属于高层 `Runtime` 逻辑。这导致了“下层知道上层”的架构污染。
2. **[Medium] 入口弥散 (Entry Point Smearing)**: 开发者可以从 `interpreter.runtime_context`、`service_context.runtime_context` 以及 `execution_context.runtime_context` 三个入口访问同一份现场。这种冗余代理增加了认知负担并掩盖了职责边界。
3. **[High] 间接上帝对象 (Indirect God Object)**: 许多 Manager 通过持有全量 `ServiceContext` 间接持有了 `Interpreter`。这种过度持有的传递链在物理上抵消了 `IExecutionContext` 所做的解耦努力。

### **5.3 治理方案 (Proposed Remediation)**
- **物理迁移**: 将 `ServiceContext` 协议定义下沉至 `core/runtime/interfaces.py`，从基座层剥离。
- **职责精简**: 移除 `ServiceContext` 中所有的 `runtime_context` 代理。规定：**“找服务找 ServiceContext，读现场读 IExecutionContext”**。
- **最小注入**: 重构 Manager 的构造函数，仅注入其所需的特定服务接口，而非全量上下文。

---

## 2. 深度审计：核心缺陷总结 (Core Defect Analysis)

### **2.1 [Critical] Item 12: 跨引擎元数据单例污染**
- **现象**：由于 Python 模块缓存，插件的 `ModuleMetadata` 在物理内存中是单例。
- **根因**：`TypeDescriptor` 包含 `_registry` 字段。多个引擎并行加载同一插件时，会竞争修改该引用。
- **后果**：先启动的引擎上下文会被篡改，导致符号解析跨引擎泄露，沙箱隔离彻底失效。
- **当前对策**：已初步引入 `clone()` 机制，但需在 `MetadataRegistry.register()` 时强制执行“注册即克隆”。

### **2.2 [High] 类字段初始化时序盲区 (Evaluation Gap)**
- **现象**：类字段如 `int x = 1 + 2` 在运行时变为 `None`。
- **根因**：`_hydrate_user_classes` 在 STAGE 5 执行，此时解释器环境（Context/Scopes）尚未闭合，不敢评估非字面量表达式。
- **后果**：破坏了 IBCI 类定义的完备语义。
- **对策**：重构实例化逻辑，在解释器环境就绪后的预评估阶段或实例化时按需求值。

### **2.3 [High] 继承链断裂静默失效**
- **现象**：父类缺失时仅打印 `Warning`。
- **后果**：子类带着错误的 MRO 进入 STAGE 6，导致执行期抛出难以追踪的 `AttributeError`。
- **对策**：升级错误等级，将加载期异常转化为致命错误（Linker Error）。

---

## 3. 专项审计清单：16 个技术债点 (16-Point Technical Audit)

| 审计项 | 涉及代码位置 | 深度审计结论与逻辑链条 | 风险等级 |
| :--- | :--- | :--- | :--- |
| **1** | `descriptors.py#L73-78` | **兼容性妥协**：UTS 描述符通过 `type_info` 属性伪装成旧版 `Symbol` 以维持旧语义分析器运行。UTS 完全接管后必须移除。 | Medium |
| **2** | `symbols.py#L42-53` | **兼容性妥协**：同上。属于 Symbol 系统向 UTS 迁移期间的过渡补丁。 | Medium |
| **3** | `symbols.py#L105-106` | **逻辑隐患**：内置符号覆盖逻辑缺乏类型签名的一致性校验。同名但不同类型的内置符号冲突会导致不可预知的解析结果。 | Medium |
| **4** | `artifact_loader.py#L4-6` | **确认为 BUG**：导入路径错误。试图从不存在的 `core.foundation.exceptions` 导入。 | **CRITICAL** |
| **5** | `interpreter.py#L192-202` | **预留设计**：构造函数中的 `or` 逻辑属于标准的依赖注入（DI），为未来动态宿主切换和断点注入预留了插槽。 | Low |
| **6** | `interpreter.py#L592-607` | **设计不洁**：过度防御的池化检查。此类调试逻辑应下沉至数据池层（`ReadOnlyNodePool`），不应污染 Dispatcher。 | Low |
| **7** | `interpreter.py#L627-639` | **硬编码债务**：压栈节点列表硬编码在逻辑中。应改为基于 AST 节点的元数据标记驱动。 | Medium |
| **8** | `kernel.py#L172-199` | **历史残留**：消息传递中的尝试性 `pass` 查找。IES 2.0 下应改为基于契约的显式分发。 | Low |
| **9** | `kernel.py#L247-271` | **架构违规**：`IbClass` 内部持有顶层 `Interpreter` 实例以支持求值。严重违反分层依赖。 | **HIGH** |
| **10** | `kernel.py#L417-418` | **架构违规**：`IbUserFunction`/`IbLLMFunction` 深度耦合解释器逻辑。 | **HIGH** |
| **11** | `registry.py#L143-148` | **严重架构违规**：`Foundation` 层直接持有 `Runtime` 层的解释器实例。属于最高优先级的解耦项。 | **CRITICAL** |
| **12** | `interpreter.py#L160-164` | **临时补丁**：为了解决 Item 2.2 的实例化求值问题而进行的临时注入。 | Medium |
| **13** | `discovery.py#L48-50` | **违规操作**：契约加载失败仅 print 跳过。违反了“Fail-fast”原则，属于对坏数据的容忍。 | Medium |
| **14** | `stmt_handler.py#L321-324` | **功能缺失**：STAGE 6 模式下缺乏深度契约校验（方法签名、参数一致性验证）。 | Medium |
| **15** | `stmt_handler.py#L324-333` | **逻辑风险**：保留 STAGE 5 之前的动态回退逻辑。这实际上是为“绕过封印非法执行”留下的技术后门。 | **HIGH** |
| **16** | `stmt_handler.py#L329-331` | **元数据不洁**：允许运行时临时创建 descriptor。背离了“静态契约先行”原则。 | Medium |

---

## 4. 架构治理专题：解释器“上帝对象”解耦 (God Object Decoupling)

### **4.1 核心矛盾：非法越级持有与“假解耦”继承**
目前的 `Interpreter` 实例同时承载了 **执行逻辑 (Visitor)** 与 **运行时数据 (State)**，且采取了“协议继承”的捷径。
- `Interpreter` 继承了 `IStackInspector` 和 `IExecutionContext`。
- **缺陷**：虽然底层组件看到的是协议，但物理上持有的依然是庞大的解释器实例。
- **栈管理矛盾**：栈的推进（Push/Pop）是解释器的逻辑行为，而栈的内容是执行数据。目前的继承关系导致逻辑与数据在物理内存地址上完全重合，无法实现真正的数据隔离或状态快照。

### **4.2 终极解决方案：状态分离 (ExecutionContext & Stack Isolation)**
- **数据容器化**：定义 `ExecutionContextImpl` 和 `StackState` 纯数据类。
- **组合代替继承**：
    - `Interpreter` 内部持有这些数据实例。
    - `Interpreter` 不再继承协议，而是作为逻辑驱动器，在初始化时将自身的方法（作为回调）注入到数据上下文中。
- **收益**：底层组件持有的将是纯粹的、轻量级的状态包，解释器实例可以被随时销毁、热替换或序列化，而不会影响底层的对象引用。

---

## 6. 上下文正规化：深度规格说明书 (Context Regularization Specification)

### **6.1 核心定义与职责分离 (The Three Contexts)**

#### **I. `RuntimeContext` (易变执行现场)**
- **职责定位**：负责管理单一执行流中的**易变状态**。它是解释器运行时的“记忆”。
- **物理位置**：
    - 协议：`core/runtime/interfaces.py`
    - 实现：`core/runtime/interpreter/runtime_context.py`
- **持有数据 (Bottom Data)**：
    - `scopes`: `List[Scope]` - 变量解析栈。
    - `intent_stack`: `List[Intent]` - 活跃意图栈。
    - `registry`: `Registry` 实例 - 用于求值过程中的对象装箱 (Boxing)。
- **禁止项**：严禁持有任何横向服务（如 LLM）或解释器逻辑引用。

#### **II. `IExecutionContext` (资源与调度网关)**
- **职责定位**：作为 Foundation/Kernel 与 Runtime 之间的**物理隔离带**。它为底层对象提供“窄求值能力”。
- **物理位置**：
    - 协议：`core/foundation/interfaces.py` (下沉至基座)
    - 实现：`core/runtime/interpreter/execution_context.py`
- **持有数据 (Bottom Data)**：
    - `node_pool`: `Mapping[str, Any]` - AST 节点池的只读引用。
    - `registry`: `Registry` 实例 - 类型与公理系统的唯一真理源。
    - `runtime_context`: `RuntimeContext` 引用 - 当前执行现场。
- **交互协议**：通过 **回调函数 (Callbacks)** 代理 `visit`, `push_stack` 等逻辑，严禁持有 `Interpreter` 实例。

#### **III. `ServiceContext` (横向服务定位器)**
- **职责定位**：负责 Runtime 内部各独立组件之间的**横向发现与协作**。
- **物理位置**：
    - 协议：`core/runtime/interfaces.py` (严禁定义在 Foundation)
    - 实现：`core/runtime/interpreter/service_context.py` (独立文件)
- **持有数据 (Bottom Data)**：
    - 仅持有服务的协议接口：`ILLMExecutor`, `IModuleManager`, `IPermissionManager`, `IInterOp`, `IIssueTracker`。
- **禁止项**：
    - **严禁持有 `Interpreter` 实例**。
    - **严禁持有 `RuntimeContext`**。服务若需访问状态，必须通过调用栈显式传递 `IStateReader` 接口。

### **6.2 组件注入与传递规范 (Injection Policy)**

| 组件名称 | 注入内容 (Min-Privilege) | 传递入口 |
| :--- | :--- | :--- |
| **LLMExecutor** | `Registry`, `IIntentManager` | 构造函数注入 |
| **ModuleManager** | `InterOp`, `Registry`, `IObjectFactory` | 构造函数注入 |
| **Handlers** | `ServiceContext`, `IExecutionContext` | 构造函数注入 |
| **IbObject** | `IExecutionContext` | 实例化时注入 |

### **6.3 交互拓扑图 (Interaction Topology)**

1. **[Orchestrator] Interpreter**：作为逻辑中心，初始化所有组件。它创建 `ExecutionContextImpl` 并将自身的逻辑方法（如 `visit`）作为回调注入。
2. **[Data Holder] ExecutionContextImpl**：被传递给 `Registry` 和 `IbObject`。它不认识解释器，只知道如何通过回调触发求值。
3. **[Service Holder] ServiceContextImpl**：被传递给 `Handlers`。它不认识解释器，只知道如何找到 `LLMExecutor`。
4. **[No-Penetration] 穿透禁令**：严禁出现 `context.interpreter.xxx` 或 `context.runtime_context.registry` 这种跨层级引用链。

---

## 5. 后续行动路线图 (Action Roadmap)

### **阶段 4.4: 审计修复与物理隔离加固 (Completed)**
1. [x] **Fix Item 4**: 修正 `artifact_loader.py` 的导入 Bug。
2. [x] **Item 12 Enforcement**: 在 `MetadataRegistry.register` 中强制执行克隆策略。
3. [x] **Linker Enforcement**: 将 `ArtifactLoader` 的警告升级为抛出致命错误。
4. [x] **Security Cleanup**: 移除 `visit_IbClassDef` 中的动态回退逻辑 (Item 15/16)。

### **阶段 4.5: 架构深度解耦 (Completed)**
1. [x] 设计并实现 `IExecutionContext` 纯数据协议与 `ExecutionContextImpl` 组合容器。
2. [x] 重构 `Interpreter`，通过组合代替继承，彻底实现逻辑与数据的物理分离。
3. [x] 重构 `Registry` 与 `IbObject`, `IbUserFunction`, `IbLLMFunction`，确保它们仅持有轻量级的上下文容器而非整个解释器。
4. [ ] 将 `builtin_initializer.py` 中的硬编码逻辑迁移至 Axiom 公理层。

### **阶段 4.6: 上下文正规化与无穿透架构 (Completed)**
1. [x] 物理剥离 `ServiceContext` 定义至 Runtime 接口层。
2. [x] 实现非穿透式 `ServiceContextImpl`，彻底切断对 `Interpreter` 实例的物理持有。
3. [x] 重构 `LLMExecutor`、`ModuleManager` 和 `HostService`，实现基于“数据结构”的最小特权注入。
4. [x] 修复意图消解算法回归 Bug，确保冲突消解逻辑的正确性。

---
*版本：v1.0 (2026-03-15) - 终极整合版*
