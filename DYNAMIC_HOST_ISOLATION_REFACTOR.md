# IBCI 动态宿主与全隔离架构重构指南 (IES 2.2)

**日期**：2026-03-30
**版本**：V3.0 (Final Architecture Blueprint)
**状态**：审计通过，进入实施阶段

## 1. 背景与核心问题 (Context & Critical Issues)

目前的 IBCI MVP 版本在处理“动态宿主 (DynamicHost)”和“子解释器运行”时，存在严重的架构设计缺陷，被定义为“架构穿透 (Architecture Leak)”和“逻辑异味”。

### 1.1 架构穿透：编译与运行边界模糊
- **现状**：`RuntimeScheduler` (运行时组件) 竟然持有了 `Compiler` (构建期组件) 的引用，并手动调用编译逻辑。
- **危害**：违反了层级隔离原则。运行时不应感知编译器的存在，更不应负责驱动复杂的项目级编译。

### 1.2 伪隔离：子解释器的“附庸”地位
- **现状**：子解释器通过主解释器的 `spawn` 接口产生，并共享/克隆部分父环境状态。
- **危害**：子环境无法实现真正的“全隔离编译”。子项目可能错误地复用了父项目的插件缓存、符号表或 root 路径，导致执行语义漂移。

### 1.3 隐式副作用：配置注入混乱
- **现状**：`main.py --config` 隐式地将变量“炸开”注入全局作用域。
- **危害**：脚本逻辑不透明，自包含性差，在跨宿主迁移时极易崩溃。

## 2. 架构设计原则 (The "Kernel Gateway" Principles)

为了实现真正的 **“全隔离、对等化、显式化”**，重构必须遵循以下红线：

1. **递归编排 (Recursive Orchestration)**：任何动态执行 `.ibci` 文件的请求，必须触发一个**全新的、完整的 `IBCIEngine` 实例化**过程。
2. **编译隔离 (Compilation Sandbox)**：每个隔离实例必须拥有独立的编译器实例，根据其自身的物理位置（`target_proj_root`）重新执行插件发现（`plugins/`）和语义分析。
3. **系统调用模式 (System Call Pattern)**：运行时向引擎发起隔离请求，应视为一种“内核调用”，通过定义的 `IKernelOrchestrator` 协议进行，而非物理层面的代码穿透。
4. **显式配置 (Explicit Config)**：废除所有隐式加载机制。脚本必须通过 `__dir__` 显式加载其依赖的 JSON 资产。

## 3. 目标架构模型 (Target Architecture Model)

### 3.1 内核协调协议 (IKernelOrchestrator)
- 定义在 `core/runtime/interfaces.py`。
- `IBCIEngine` 实现此协议，并作为 `ServiceContext` 中的一个只读服务提供。
- **职责**：接收 `(path, isolation_policy, initial_vars)` 请求，负责开启子 Engine 并在完成后返回信号。

### 3.2 解释器对等模型
- 每个解释器实例在逻辑地位上是平等的。
- 子 Engine 内部的 `orchestrator` 指向它自己产生的上下文，从而支持**无限深度的递归跳转**（父跳子，子跳孙...）。

### 3.3 注册表与插件空间
- **Registry**：不再通过脆弱的 `clone()`，而是由新 Engine 从头启动标准的 `initialize_builtin_classes` 流程，确保公理系统水合完整。
- **HostInterface**：基于子项目的 `root_dir/plugins` 重新扫描，确保插件空间的物理隔离。

## 4. 实施路径规划 (Execution Roadmap)

### 第一阶段：清理与脱钩 (Cleanup)
- [ ] 彻底移除 [main.py](file:///c:/myself/proj/intent-behavior-code-inter/main.py) 中的 `--config` 逻辑。
- [ ] 清理 [rt_scheduler.py](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/rt_scheduler.py)，移除所有对 `Compiler`、`Scheduler` 和 `FlatSerializer` 的引用。
- [ ] 移除 `rt_scheduler` 中的 `root_dir` 继承逻辑。

### 第二阶段：内核协议实现 (Kernel Gateway)
- [ ] 在 `core/runtime/interfaces.py` 中定义 `IKernelOrchestrator`。
- [ ] 让 `IBCIEngine` 实现该协议，并在 `_prepare_interpreter` 时将其注入 `ServiceContext`。
- [ ] 修改 `HostService.run_isolated`，将其实现从“手动孵化”改为“向 Orchestrator 发起请求”。

### 第三阶段：全隔离验证 (Isolation Verification)
- [ ] 为每个 `test_target_proj` 子目录放置独立的 `api_config.json`。
- [ ] 更新所有测试脚本，验证 `str cfg = file.read(__dir__ + "/api_config.json")` 的显式加载流。
- [ ] 编写“递归跳转”压力测试：主脚本运行子项目，子项目运行孙项目，验证每一层是否能正确加载属于自己的私有插件。

## 5. 灾难性遗忘防护 (Anti-Forget Measures)
- **严禁**：在 `core/runtime/` 下出现任何 `from core.compiler import ...`。
- **必须**：所有跨层级调用必须通过 `Protocol` 定义的接口进行。
- **注意**：子 Engine 的退出码必须被父环境捕获并映射为正确的 `ExecutionSignal`。
