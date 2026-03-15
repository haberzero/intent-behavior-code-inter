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

### **4.1 核心矛盾：非法越级持有**
目前的 `Interpreter` 实例同时承载了 **执行逻辑 (Visitor)** 与 **运行时数据 (State)**。
- `Foundation (Registry)` 为了记录求值引用而持有它。
- `Kernel (IbObject)` 为了调用 `.visit()` 进行求值而持有它。

### **4.2 终极解决方案：状态分离 (ExecutionContext)**
- **抽象**：定义 `ExecutionContext` 纯数据结构，包含 `node_pool`, `logical_stack`, `instruction_count` 等。
- **下沉**：将 `ExecutionContext` 定义放置在 `Foundation` 或 `Common` 层。
- **解耦**：`IbObject` 仅持有 `ExecutionContext`。解释器在执行时，将自身持有的数据包传递给对象系统。
- **结论**：这是消除物理循环依赖、实现真正沙箱化运行的唯一路径。

---

## 5. 后续行动路线图 (Action Roadmap)

### **阶段 4.4: 审计修复与物理隔离加固 (Completed)**
1. [x] **Fix Item 4**: 修正 `artifact_loader.py` 的导入 Bug。
2. [x] **Item 12 Enforcement**: 在 `MetadataRegistry.register` 中强制执行克隆策略。
3. [x] **Linker Enforcement**: 将 `ArtifactLoader` 的警告升级为抛出致命错误。
4. [x] **Security Cleanup**: 移除 `visit_IbClassDef` 中的动态回退逻辑 (Item 15/16)。

### **阶段 4.5: 架构深度解耦 (Completed)**
1. [x] 设计并实现 `IExecutionContext` 纯数据协议。
2. [x] 重构 `Registry` 与 `IbObject`, `IbUserFunction`, `IbLLMFunction`，彻底移除对 `Interpreter` 实例的直接持有。
3. [ ] 将 `builtin_initializer.py` 中的硬编码逻辑迁移至 Axiom 公理层。

---
*版本：v1.0 (2026-03-15) - 终极整合版*
