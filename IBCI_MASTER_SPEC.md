# IBC-Inter 2.0 核心演进说明书 (Master Specification)

## 1. 项目愿景与哲学 (Vision & Philosophy)

IBC-Inter (Intent-Behavior-Code Interaction) 旨在构建一种**意图驱动的混合编程语言**。它通过“确定性代码”与“非确定性 AI 推理”的物理分离，解决 LLM 在复杂逻辑编排中的落地难题。

### **1.1 核心设计哲学**
- **不可变执行环境 (Immutable Registry)**：进入 STAGE 6 (READY) 后，内核注册表封印，禁止任何动态类注册或契约修改。
- **动态宿主机制 (Dynamic Host)**：解决“动态性”不应依赖运行时修改内核，而应通过“上下文快照 + 全新环境重启”实现零污染的逻辑演进。
- **数据驱动与侧表化 (Data-Driven & Side-Tabling)**：AST 保持只读，所有分析结论存储在侧表中，实现编译器与解释器的物理去耦。

---

## 2. IES 2.0 插件系统规范 (Plugin & SDK Spec)

IES 2.0 确立了插件与内置函数在技术实现上的完全平权。

### **2.1 物理分离架构**
插件必须遵循三层分离结构：
- `_spec.py`：[静态契约] UTS 描述符定义，编译器专属。
- `core.py`：[逻辑实现] 纯净的 Python 实现。
- `__init__.py`：[加载门面] 仅负责导出实现实例或工厂。

### **2.2 显式契约与 Proxy VTable**
- **元数据先行**：编译器仅通过 `_spec.py` 识别能力，不加载实现。
- **职责下放 (Boxing)**：插件通过 `setup(capabilities)` 接收特权。`ModuleLoader` 负责 `Proxy VTable` 包装，自动拦截返回值并应用 `box()`。
- **禁止猜测**：内核严禁使用 `getattr` 兜底，所有调用必须符合显式虚表映射。

---

## 3. 解释器架构演进 (Interpreter Evolution)

为了解决 `Interpreter.py` 职责过重（God Class）的问题，架构向“模块化与可观测性”演进。

### **3.1 解释器分片 (Sharding)**
- **职责剥离**：将 `Interpreter` 拆分为 `Dispatcher` (调度) + `StmtVisitor` (语句处理) + `ExprVisitor` (表达式处理)。
- **中介者容器**：`ServiceContext` 作为唯一组件交换中心，严禁在解释器内部重新实例化组件。

### **3.2 逻辑调用栈 (Logical CallStack)**
- **目的**：不直接替换 Python 递归，但引入显式的 `CallStack` 记录每一层函数调用的局部变量、意图栈和执行位置。
- **价值**：为“动态宿主”提供可序列化的执行快照，同时消除对 Python 递归深度的极限依赖。

---

## 4. 观测性与调试演进 (Observability & Debugging 2.0 - 远景演进)

基于 **Logical CallStack** 的引入，调试系统将从简单的日志打印向成熟的代码观测器进化。

### **4.1 核心演进方向 (非即时任务)**
- **idbg 2.0 (交互式调试器)**：实现类 GDB 的 `backtrace` (回溯)、帧选择 (Frame Selection) 以及 IBCI 特有的 **意图感知调试 (Intent-Aware Debugging)**。
- **内核 Core Dump**：当解释器崩溃或触发异常时，自动导出 `.ibdump` 文件，包含 `CallStack` + `Registry` + `VariablePool` 的完整快照，支持离线环境下的现场恢复。
- **issue_tracker 2.0 (上下文诊断)**：运行时错误报告将自动关联源码片段、局部变量快照以及当前的“语义意图链条”。

### **4.2 架构预留与风险评估**
- **性能平衡**：必须设计显式的“调试/追踪”开关，确保在生产模式下栈信息收集的开销降至最低。
- **实施优先级**：**此类功能严禁在 Phase 4 重构期间启动**。其演进必须建立在解释器分片化 (Phase 4.3) 彻底完成、主框架逻辑达到 100% 稳定性、且单元测试全绿通过之后。
- **职责边界**：调试器专注于“观测”与“回溯”，**严禁具备运行时动态修改 Registry 或类结构的能力**，以维持 STAGE 6 的封印原则。

---

## 5. 注册生命周期状态机 (Registration State Machine)

| 阶段 | 状态 | 职责 |
| :--- | :--- | :--- |
| **STAGE 1** | `BOOTSTRAP` | 注册基础原生类。 |
| **STAGE 2** | `CORE_TYPES` | 注入内置公理契约 (Axioms)。 |
| **STAGE 3** | `PLUGIN_METADATA` | 仅加载插件 `_spec.py` 元数据。 |
| **STAGE 4** | `PLUGIN_IMPL` | 加载插件实现并执行 `setup()` 注入。 |
| **STAGE 5** | `HYDRATION` | 执行产物重水合，**在此阶段完成用户类的预实例化**。 |
| **STAGE 6** | `READY` | **彻底封印**，开始执行。 |

---

## 6. 下阶段重构路线图 (Roadmap)

### **Phase 4.2: 运行时同步与引导修复 (已完成/修复中)**
- [x] **组件链路修复**：重构 `Interpreter.__init__`，强制使用 `Engine` 注入的 `ServiceContext`。
- [x] **用户类预水合**：修改 `ArtifactLoader`，在 STAGE 5 完成脚本定义类的实例化。
- [x] **测试基座隔离**：确保每个单元测试拥有独立的 `Registry` 实例。

### **Phase 4.3: 解释器分片化 (Architectural Sharding - 已完成)**
- [x] 将 `visit_` 逻辑从 `interpreter.py` 剥离到独立的 Handler 模块。
- [x] 引入 `LogicalCallStack` 增强可观测性。
- [x] 重构 `Interpreter` 为轻量级 `Dispatcher`。

### **Phase 4.4: 审计修复与物理隔离加固 (Ongoing)**
- [ ] **物理隔离闭环**：强制执行描述符“注册即克隆”，彻底封锁 Item 12 风险。
- [ ] **架构深度解耦**：引入 `ExecutionContext` 数据包，消除 Foundation/Kernel 对 Interpreter 的非法持有。
- [ ] **语义完备性修复**：解决类字段初始化求值时序问题。
- [ ] **引导层去硬编码**：将 Axiom 映射下沉至定义层。

---

## 7. 验证检查清单 (Verification Checklist)

### **7.1 开发禁令 (Strict Constraints)**
- **禁止**：在运行时使用字符串名称进行类型校验，必须使用 `TypeDescriptor` 标识。
- **禁止**：在 `core/runtime` 之外手动构造描述符。
- **禁止**：在 STAGE 6 之后尝试修改任何 `Registry` 结构。

### **7.2 单元测试准则**
- 测试必须覆盖：**公理方法绑定、意图栈叠加、Proxy VTable 自动装箱、跨引擎实例隔离**。
- 任何 `DeprecationWarning` 或局部导入均视为验证失败。

---
*版本控制：v2.5.0 (2026-03-15) - 核心架构终极对齐版*
