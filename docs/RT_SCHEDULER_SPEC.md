# IBC-Inter RuntimeScheduler (rt_scheduler) 架构设计规范

## 1. 原始构思与核心驱动力 (Origin & Drivers)

本架构提议源于对 IBC-Inter 运行时“宏观-微观”职责不分、组件耦合过深及动态宿主实现不规范的深度反思。

### 1.1 核心痛点
- **解释器职责过载**：[Interpreter](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/interpreter/interpreter.py) 承担了不属于其范畴的宿主服务管理、子环境生成及状态同步逻辑。
- **组件形态不一致**：动态宿主 (Dynamic Host) 游离于标准插件协议之外，存在 `ai_server` 式的硬编码依赖。
- **引用权越界**：[RuntimeSerializer](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/serialization/runtime_serializer.py) 和 [DynamicHost](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/host/dynamic_host.py) 直接或间接持有对解释器具体实现类的引用，违反了物理隔离与接口化原则。

### 1.2 顶层设计意图
- **引入 `rt_scheduler` 层**：在 `core/runtime` 根目录下建立与编译器 `scheduler` 对等的运行时调度层。
- **层级重定义**：`Engine` 作为与 `main.py` 交互的承接层；`rt_scheduler` 负责宏观生命周期、多实例调度与状态同步；`Interpreter` 回归为纯粹的微观 AST 执行引擎。
- **单向持有原则**：`rt_scheduler` 持有 `Interpreter`，而其它外部组件仅通过“通知/上下文/回调”与解释器交互。

---

## 2. 专项审计子代理 (Sub-Agent) 交叉审计结论

我启动了四个独立审计子代理，分别从不同维度对上述想法进行了压力测试与评估：

### 2.1 架构可行性与层级关系评估 (Agent 1)
- **结论**：**高度可行且必要**。
- **收敛要点**：
    - **宏观执行 (Macro-Execution)**：管理解释器池、资源配额、任务挂起/恢复、隔离策略。
    - **微观执行 (Micro-Execution)**：纯粹的 AST 步进器，只关心当前作用域和意图栈。
    - **调用流重塑**：`Engine` -> `rt_scheduler` -> `Interpreter`。隔离请求通过 `ServiceContext` 向 `rt_scheduler` 发起 `dispatch`，而非直接由宿主服务创建。

### 2.2 解耦机制与引用权限制审计 (Agent 2)
- **结论**：**支持，但需建立“状态采集协议”**。
- **收敛要点**：
    - **数据 vs 实例**：[RuntimeSerializer](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/serialization/runtime_serializer.py) 必须改用 `IStateProvider` 接口，严禁访问 `_` 私有属性。
    - **通知机制**：引入 `IInterpreterListener`，让解释器在安全点主动通知调度器。
    - **跳转信号标准化**：传统的 Python 异常捕获无法跨实例传递，必须封装为 `ExecutionSignal` 结构体进行显式回传。

### 2.3 动态宿主标准化与插件演进审计 (Agent 3)
- **结论**：**必须消除 `xx_server` 式硬编码**。
- **收敛要点**：
    - **插件化归位**：将 `DynamicHost` 逻辑移至 `ibci_modules/ibci_host/`。
    - **能力自推销**：利用 `CapabilityRegistry` 进行能力注册，内核不再通过 `get_package("ai")` 查找，而是请求 `llm_provider` 能力。
    - **接口对齐**：将 `set_config` 等操作下沉到标准的 `ILLMProvider` 协议。

### 2.4 架构风险、性能与复杂性交叉审计 (Agent 4)
- **结论**：**中立警示，关注性能与 God Object 风险**。
- **收敛要点**：
    - **性能瓶颈**：频繁创建实例开销巨大，**必须实现“写时复制 (CoW) 注册表”**。
    - **God Object 风险**：`rt_scheduler` 必须保持无状态化，将策略 (Policy) 与执行 (Execution) 分离。
    - **状态同步复杂性**：处理隔离环境的状态“部分同步”极易出错，需定义严格的 `IsolationLevel`。

---

## 3. 最终分析结论与架构实现 (Current Implementation)

基于以上收敛结论，已完成架构实现：

### 3.1 RuntimeScheduler 核心实现
- **位置**: `core/runtime/rt_scheduler.py`
- **角色**: 作为运行时环境的“指挥中心”，负责解释器实例的生命周期管理、资源隔离与状态同步。
- **核心能力**:
    - **spawn()**: 根据指定的 `IsolationLevel` 创建并初始化新的解释器实例。
    - **execute()**: 启动指定实例的执行流，并处理宏观退出信号。
    - **hydrate()**: 在运行时将调度器自身注入 `ServiceContext`，建立系统调用通道。

### 3.2 关键机制落地
1.  **隔离级别 (IsolationLevel)**: 
    - 统一使用 `NONE`, `SCOPE`, `REGISTRY` 三级隔离模型。
    - `REGISTRY` 级别触发 **写时复制 (CoW) 注册表** 克隆，确保类型系统完全隔离。
2.  **Kernel Gateway 模式**: 
    - 解释器不再直接持有 `HostService`，而是通过 `IKernelOrchestrator` (由 `Engine` 实现) 向调度器发起请求。
3.  **拓扑序列化支持**: 
    - 调度器配合 `RuntimeSerializer` 实现了 `IntentStack` 的拓扑保持，确保实例快照恢复后的结构共享特性。

---

## 4. 当前运行状态 (Status Report)

目前 `RuntimeScheduler` 已正式接管执行权：
- **[Engine.py](file:///c:/myself/proj/intent-behavior-code-inter/core/engine.py)** 已完成装配，所有 `run()` 请求均委派给 `rt_scheduler`。
- **隔离运行**: `host.run_isolated` 已通过调度器实现真正的内核级隔离。
- **状态一致性**: 修复了 `intent_stack` 的类型崩溃问题，支持从列表或节点直接恢复。
