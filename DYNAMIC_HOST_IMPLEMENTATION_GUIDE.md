# IBCI 2.0 “动态宿主”与运行时持久化机制实现规划指导书 (架构重构版)

## 1. 概述与设计目标
本指导书旨在为 IBCI 2.0 引入基于“协调器模式”的动态宿主机制。该机制要求逻辑与物理实现完全解耦，消除循环依赖，并支持极致的运行现场持久化。

---

## 2. 顶级架构：协调器模式 (Orchestrator Pattern)

为了实现真正的物理隔离，系统引入 `IBCIEngine` 作为顶层协调器，负责管理所有解释器实例的生命周期。

### 2.1 解释器工厂接口 (IInterpreterFactory)
- **定义**：定义在 `core/runtime/interfaces.py` 中的抽象协议。
- **职责**：屏蔽 `Interpreter` 类的物理细节。`HostService` 仅通过此接口请求创建新的执行环境。

### 2.2 宿主服务 (HostService) 的角色转变
- **定位**：由内核插件转变为 **“内核中介者”**。
- **解耦要求**：禁止在 `HostService` 中直接 `import Interpreter`。所有创建操作必须通过注入的 `IInterpreterFactory` 完成。
- **接口封装**：保留 `ibc_modules/host` 作为一个极简的包装层。内核提供能力（Capability），模块提供接口（Interface），确保安全性与 API 稳定性。

---

## 3. 核心机制：安全点与特权恢复

### 3.1 安全点同步协议 (Safe Point Sync)
- **显式同步**：在持久化前，由 `host.sync()` 强制所有资源进入稳定态。
- **资源清理**：物理句柄（文件、网络）在同步点被强制释放，仅保留元数据。

### 3.2 特权路径恢复
- **内核特权接口**：在 `Scope` 层面提供受限的 `force_define` 接口，允许 `RuntimeDeserializer` 在恢复现场时覆盖常量（如内置函数）。
- **环境重绑定 (Re-binding)**：恢复后的“空壳”对象由 `HostService` 通过 `Engine` 提供的真实实现进行动态链接。

---

## 4. 深度持久化协议：针对未来并发 LLM 交互

### 4.1 逻辑与物理分离原则
- **逻辑状态**：包括变量、意图栈、作用域，必须 100% 深度持久化。
- **物理状态**：包括 LLM 网络连接、文件句柄，禁止持久化。恢复时走“探测-重连”流程。

### 4.2 事务模型：Snapshot-Try-Restore
- 在 `host.run` 之前自动生成逻辑快照。
- 若子解释器崩溃，协调器负责将主解释器的 `RuntimeContext` 还原至快照点。

---

## 5. 实施阶段规划 (无妥协版)

### 第 0 阶段：架构拓扑重构
- **任务**：在 `interfaces.py` 定义 `IInterpreterFactory`。
- **任务**：重构 `core/engine.py` (IBCIEngine)，使其实现工厂接口。
- **任务**：彻底切断 `HostService` 对 `Interpreter` 类的物理引用。

### 第 1 阶段：工厂级对象实例化 (Unified Factory)
- **任务**：实现 `Registry.create_instance` 模式，确保所有对象从诞生起就绑定正确的内核上下文。

### 第 2 阶段：深度持久化引擎
- **任务**：完成支持循环引用的 `RuntimeSerializer`，实现特权符号恢复路径。

### 第 3 阶段：全链路验证与同步原语
- **任务**：实现 `host.sync` 及其对 AI/File 插件的清理协议。
- **任务**：通过 `verify_host.py` 进行包含“跨环境迁移模拟”的压力测试。

---

## 6. 验收标准
1. **物理隔离**：`HostService` 与 `Interpreter` 之间不存在直接或循环的 `import` 关系。
2. **逻辑完备**：持久化快照能够跨进程、跨环境恢复，且内置功能自动重绑定。
3. **架构优雅**：所有系统级操作均通过 `Orchestrator` 协调，而非组件间私下通信。
