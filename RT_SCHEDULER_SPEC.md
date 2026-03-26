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

## 3. 最终分析结论与架构蓝图

基于以上收敛结论，确立以下实施准则：

### 3.1 RuntimeScheduler 核心接口 (Proposed)
```python
class IRuntimeScheduler(Protocol):
    def spawn(self, artifact: CompilationArtifact, isolation: IsolationLevel) -> str: ...
    def dispatch(self, request: ExecutionRequest) -> ExecutionSignal: ...
    def snapshot(self, instance_id: str) -> StateSnapshot: ...
    def restore(self, instance_id: str, snapshot: StateSnapshot) -> None: ...
```

### 3.2 关键机制变更
1.  **写时复制 (CoW) 注册表**：子环境默认共享父级 Registry 镜像，仅在写入新类型/符号时触发局部克隆，大幅降低调度开销。
2.  **信号驱动跳转**：隔离执行的退出必须携带信号，解释器在 `visit` 循环的每一轮检查调度器发出的外部指令。
3.  **能力导向 (Capability-Oriented)**：内核与插件的通信通道唯一化，彻底隔离物理实现。

---

## 4. 后续具体执行计划

计划分为三个阶段稳步推进，确保不破坏现有功能：

### 第一阶段：基础设施与接口定义 (Foundation)
- 在 `core/runtime/interfaces.py` 中定义 `IRuntimeScheduler`、`IStateProvider` 和 `ExecutionSignal` 协议。
- 在 `core/runtime/` 下创建 `rt_scheduler.py` 基础框架，但不接入逻辑。
- 重构 `CapabilityRegistry`，支持“能力自推销”模式。

### 第二阶段：组件剥离与重定向 (Decoupling)
- **Serializer 重构**：修改 [RuntimeSerializer](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/serialization/runtime_serializer.py)，使其仅依赖接口，删除对 `Interpreter` 具体类的导入。
- **DynamicHost 重构**：将 `HostService` 的隔离运行逻辑提取至 `rt_scheduler`。
- **Interpreter 纯净化**：删除 `Interpreter` 内部直接实例化 `HostService` 的逻辑，改为从 `ServiceContext` 获取调度器能力。

### 第三阶段：插件标准化与全链路切换 (Standardization)
- 将 `ibci_ai` 和 `ibci_host` 重构为符合 IES 2.2 规范的标准插件。
- 在 [Engine.py](file:///c:/myself/proj/intent-behavior-code-inter/core/engine.py) 中完成 `rt_scheduler` 的装配，将执行控制权正式移交。
- 运行全量回归测试，验证基于调度器的多实例跳转逻辑。
