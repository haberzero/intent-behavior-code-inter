# IBCI 隔离架构与配置管理审计报告 (IES 2.2)

**日期**：2026-03-30
**版本**：V2.0
**状态**：审计通过，待实施重构（取代 V1.0 路径审计）

## 1. 核心审计结论 (Audit Conclusions)

### 1.1 隔离语义缺陷
- **现状**：子解释器（通过 `DynamicHost` 启动）在 `RuntimeScheduler.dispatch` 中错误地继承了主解释器的 `root_dir`。
- **风险**：子解释器沦为主解释器的“附庸”，无法实现真正的环境独立。这导致插件搜索路径（`plugins/`）和文件操作基准被主环境污染。
- **目标**：实现父子解释器的“完全平等”。子解释器必须拥有独立的 `target_proj_root`，由其自身的入口文件位置决定。

### 1.2 配置注入隐患
- **现状**：`main.py --config` 机制存在隐式侧向加载（Side-loading）。它将 JSON 字段自动炸开为全局变量，导致脚本逻辑不透明，且在隔离运行环境下变量传递链路脆弱。
- **风险**：违背了 IBCI “显式、手动管理”的设计理念。
- **目标**：彻底废除 `--config` 机制。

## 2. 架构设计原则 (Design Principles)

1. **显式配置 (Explicit Configuration)**：任何一个可运行的 `.ibci` 脚本必须自己负责查找和加载其依赖的 `api_config.json`。
2. **完全隔离 (Total Isolation)**：
    - 每个解释器实例（无论主次）拥有独立的 `target_proj_root`。
    - 每个实例拥有独立的 `Registry`（默认克隆）和 `HostInterface`（基于自身 root 重新发现插件）。
3. **位置无关 (Location Independence)**：利用 `__dir__` 内置变量，脚本应使用 `file.read(__dir__ + "/api_config.json")` 进行显式加载。

## 3. 重构实施方案 (Implementation Plan)

### 3.1 编译器与入口层 (main.py)
- **动作**：删除 `--config` 参数定义及相关 JSON 解析、变量注入代码。
- **Root 逻辑**：保持 `root_dir` 默认为入口脚本所在目录，但明确该目录仅作为该实例的 `target_proj_root`。

### 3.2 运行时调度层 (rt_scheduler.py)
- **动作**：修改 `dispatch` 方法，**严禁继承** `main_interpreter.root_dir`。
- **实现**：根据 `ExecutionRequest.node_uid`（如果是物理路径）重新计算子环境的 `root_dir`。

### 3.3 宿主服务层 (service.py)
- **动作**：在 `run_isolated` 中强制执行 `registry.clone()` 和 `HostInterface` 重新发现。
- **目标**：确保子解释器跳转后，可以开启自己的子解释器并无限深跳，而不受主环境限制。

### 3.4 测试集对齐 (Test Assets)
- **动作**：
    - 在每个 `test_target_proj` 目录下放置 `api_config.json` 副本。
    - 更新所有 `.ibci` 测试脚本，将原本依赖隐式注入的变量引用改为显式读取和 `ai.set_config` 调用。

## 4. 最终验证标准 (Verification)
- **验证 1**：在不带任何 CLI 变量的情况下运行子目录脚本，脚本应能自行找到同目录配置并运行。
- **验证 2**：在 `DynamicHost` 隔离运行测试中，子脚本应能成功加载其自身的插件目录（`plugins/`），而非主环境的插件。
