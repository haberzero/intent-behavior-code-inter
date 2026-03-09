# IBC-Inter 2.0 架构优化与改进清单 (ARCH_IMPROVEMENT_LIST)

本清单旨在记录 IBC-Inter 解释器在单元测试加固过程中发现的架构缺陷、临时补丁及后续优化方向，确保系统符合 **Active Defense (主动防御)** 与 **Message Passing (消息传递)** 的核心哲学。

## 1. 静态语义系统 (Symbols & Static Analysis)

### 1.1 静态符号与动态注册的“二元对齐”风险 (NEW)
- **当前问题**：编译器符号表 (`symbols.py`) 与运行时类注册 (`initialization.py`) 处于手工同步状态。
- **缺陷分析**：编译器通过 Python 继承体系“模拟”IBCI 类型，这导致了“影子模型”问题：任何运行时的行为变更（如 IES 插件新增方法）都必须在前端手动复现。
- **深度隐患**：
    - **类型解析割裂**：`resolve_member` 的硬编码导致静态检查无法感知动态扩展。
    - **名称空间冲突**：`str`, `int` 等名称在“类型身份”（IbClass）与“转换身份”（Intrinsic Function）之间存在解析歧义。
- **重构预案**：
    1. **描述符化 (Descriptor-Driven)**：`StaticType` 彻底解耦具体逻辑，通过 `TypeDescriptor` 访问元数据。
    2. **元数据导出 (Manifest Generation)**：运行时 Registry 在启动阶段生成 `TypeManifest`，编译器基于此 Manifest 动态构建符号树，实现“单源真理”。

### 1.2 移除硬编码内置方法白名单
- **当前状态**：已重构为 `IntType`, `StringType` 等子类，但仍属于“前端模拟”。
- **后续目标**：将符号解析逻辑与 **UTS (统一类型系统)** 描述符彻底合龙，实现“一次注册，两端感知”。

### 1.2 强化内置方法类型签名
- **当前问题**：目前为了通过测试，将内置方法的返回类型简单设为 `Any`。
- **缺陷分析**：彻底削弱了编译器的静态检查能力，使得链式调用（如 `list.append(x).something()`）的错误无法在编译阶段被拦截。
- **改进方案**：为所有内置方法定义准确的 `FunctionType` 签名，例如 `list.append` 返回 `void`，`str.len` 返回 `int`。

### 1.3 统一行为协议属性
- **当前问题**：`StaticType` 基类与其子类（如 `ClassType`）之间，关于 `is_callable` 等属性的定义存在 `@property` 装饰器与普通方法混用的冲突。
- **缺陷分析**：导致编译器在访问这些属性时抛出 Python 层的 `TypeError`。
- **改进方案**：统一所有 `is_callable`, `is_iterable`, `is_subscriptable` 为 `@property` 只读属性。

## 2. 运行时核心 (Runtime & Initialization)

### 2.1 精简字符串拼接逻辑
- **当前问题**：`string_class.__add__` 实现中引入了隐式的 `__to_prompt__` 自动转换，试图让 `str + any` 均合法。
- **缺陷分析**：这种隐式“弱类型”转换会带来不可预测的副作用（如意外触发 LLM 推理），且破坏了语言的显式性。
- **改进方案**：退回到显式拼接。字符串加法仅支持 `str + str`。非字符串类型必须通过显式转换或提示词插值处理。

### 2.2 评估 None 单例注册逻辑 (Per-Registry)
- **当前问题**：`None` 单例被绑定到具体的 `Registry` 实例中，而非全局唯一。
- **架构确认**：这是为了支持多引擎隔离（Isolation）的必然设计，确保不同解释器实例之间的类型元数据不发生交叉污染。
- **改进方向**：保留此设计，但在 `Registry` 层面加强对 `none_class` 的保护，防止其被非内核令牌修改。

### 2.3 校验逻辑非协议 (`__not__`)
- **架构确认**：`bootstrapper.py` 中通过 `to_bool` 消息传递实现的 `_default_not` 是合理的。
- **结论**：它成功地将逻辑运算解耦为对象间的消息通信，符合 IBCI 核心哲学，应予以保留。

## 3. 语义分析逻辑调优 (Semantic Analyzer)

### 3.1 优化全局变量访问规则 (`SEM_004`)
- **当前问题**：编译器对全局变量的访问限制过于死板，导致在局部作用域读取顶层变量也必须声明 `global`。
- **改进方案**：对齐 Python/IBCI 惯例——**读取（Read）全局变量允许隐式引用，仅修改（Write/Assign）时强制要求 `global` 声明**。

## 4. 模块系统与测试同步 (Module System)

### 4.1 增强 Mock 模块的热插拔支持
- **当前问题**：单元测试中手动注册的 Mock AI 模块有时无法被内核 `LLMExecutor` 自动识别。
- **改进方案**：增强 `ModuleLoader` 的扫描逻辑，使其优先处理 `HostInterface` 中已手动挂载的实现层。

---
**核查状态**：待执行
**最后更新**：2026-03-09
