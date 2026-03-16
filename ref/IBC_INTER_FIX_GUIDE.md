# IBC-Inter 核心 Bug 诊断与架构维修指南 (2026-03-16 完整增补版)

> 本文档汇集了对 IBC-Inter 内核的深度审计结论，旨在为后续的维修和闭环开发提供精准的技术指引。本文档保留了 subagent 探测到的所有批判性判定与演化逻辑。

---

## 一、 核心 Bug 定位与底层故障分析 (Deep Diagnosis)

### 1. 字符串拼接与类型转换瘫痪 (Identity Mismatch)
- **判定**: **演化阵痛**。
- **微观表现**: 在执行 `(str)10` 时，`converters.py` 接收到描述符副本。执行 `if target_desc is STR_DESCRIPTOR` 时，由于内存地址不一致，判定走入 `else` 分支，返回原始 `int`。随后触发 `RuntimeContext` 类型检查，抛出 `Type mismatch`。
- **架构根源**: **IES 2.0 隔离机制先行，公理化覆盖不全**。为了支持多引擎隔离，所有类型描述符在注册时被强制深度克隆。目前的转换层仍在使用陈旧的“指针相等”判定（Identity-based），而没有切换到 UTS 规范建议的“契约判定”（Contract-based）。
- **演化路径**: 随着 UTS 向“契约一致性”演化（即改用 `is_assignable_to`），此问题将通过统一描述符判定逻辑自动闭环。
- **修复方案**: 弃用 `is` 比较，改用 `name` 匹配（如 `other.descriptor.name != "str"`）或调用 `is_assignable_to()`。

### 2. 意图修饰符的语义断层 (Mode Literal Mismatch)
- **判定**: **同步机制失效**。
- **底层成因**: 
    - **Parser 层**: [statement.py](file:///d:/Proj/intent-behavior-code-inter-master/core/compiler/parser/components/statement.py) 在处理简写 `@!` 时写入魔术字符串 `"override"`。
    - **AST 层**: [ast.py](file:///d:/Proj/intent-behavior-code-inter-master/core/domain/ast.py) 属性硬编码为 `self.mode == "!"`。
- **风险**: 运行时虽通过 `from_str` 补丁“自愈”，但**编译期属性已损坏**。这暗示了 Parser 与 Domain 层之间缺乏共享“事实来源”（Source of Truth）。
- **修复方案**: 统一 Parser 映射，使 `mode` 字段与 `IntentMode` 枚举强绑定，消除魔术字符串。

### 3. 集合类型转换接口缺失 (Missing cast_to)
- **判定**: **实现补全任务**。
- **原因**: 属于“基座类公理化”过程中的遗漏。只需在 [builtin_initializer.py](file:///d:/Proj/intent-behavior-code-inter-master/core/runtime/bootstrap/builtin_initializer.py#L247) 中补全 `list_class` 和 `dict_class` 的 `__call__` 与 `cast_to` 公理注册即可，不涉及架构调整。

---

## 二、 游离于演化之外的“孤立底层 Bug” (The Rogue Bugs)

这些 Bug 属于纯粹的底层代码实现缺陷，即使 UTS 和公理体系演化完成，它们依然会存在，必须专项清理：

### 1. `IbBehavior` 的内省屏障与“黑盒”奇异点 (The Intro-barrier Singularity)
- **判定**: **孤立底层 Bug / 架构权责模糊**。
- **逻辑链路剖析**:
    - **待机态 (Standby)**: `IbBehavior` 对象（延迟执行的行为 `@~...~`）在 `LLMExecutor` 调度前，内部 `_cache` 为 `None`。
    - **消息分发链**: 容器类（如 `IbList`/`IbDict`）在序列化（`__to_prompt__` 协议）或调试内省时，会遍历成员并递归分发 `receive` 消息。
    - **强制拦截**: [builtins.py](file:///d:/Proj/intent-behavior-code-inter-master/core/runtime/objects/builtins.py#L297-300) 的 `receive` 实现为“全有或全无”的强一致性代理：`if not self._cache: raise RuntimeError(...)`。
- **架构影响**: **严重破坏了“一切皆对象”的一致性**。在 UTS 理想架构中，任何对象（无论是否就绪）都应具备基本的“元数据响应能力”（Meta-responsiveness）。目前的 `IbBehavior` 在未执行前是一个不可触碰的“奇异点”，任何对其进行非侵入式观察（如 `print` 包含它的字典）的行为都会导致系统性崩溃。这直接阻碍了 AGI 时代的内核 Core Dump 和回溯调试（Time-travel Debugging）特性的实现。
- **融合 UTS/对象基座的方案**:
    1. **消息路由分流 (Protocol Splitting)**: 在 `IbObject` 基类中明确区分 **业务消息 (Business Protocol)** 与 **元数据消息 (Meta Protocol)**。`IbBehavior` 应在未执行时拦截业务请求，但必须自主响应元数据请求（如 `__repr__`, `__type__`）。
    2. **补全 BehaviorAxiom**: 在 `builtin_initializer` 中为 `IbBehavior` 注册专属公理，实现 `ParserCapability`，使其在被要求转换为 Prompt 字符串时能返回安全的描述性占位符而非抛出异常。
- **评估**: 
    - **难度**: 容易。仅涉及 `receive` 逻辑重构与公理注册，不涉及编译器大改。
    - **风险**: 极低。此项工作是对象基座走向成熟的标志，能显著增强 `idbg` 等调试工具的扫描安全性。

### 2. IES 2.0 插件系统的“注入断层”与隔离冲突 (Capability Injection & Isolation Gap)
- **判定**: **隔离机制先行与资源分发模型不匹配**。
- **逻辑链路剖析**:
    - **发现与蓝图**: [ModuleDiscoveryService](file:///d:/Proj/intent-behavior-code-inter-master/core/runtime/module_system/discovery.py) 通过 `_spec.py` 构建插件的“数字孪生”蓝图。
    - **隔离加载**: [ModuleLoader](file:///d:/Proj/intent-behavior-code-inter-master/core/runtime/module_system/loader.py) 强制执行多引擎实例隔离，每个插件对象都是独立的克隆副本。
    - **脆弱注入**: 系统通过 `setup(capabilities)` 方法进行依赖注入。以 `idbg` 为例，[idbg/core.py](file:///d:/Proj/intent-behavior-code-inter-master/ibc_modules/idbg/core.py) 仅手动提取了部分工具，未持久化 `capabilities` 对象，导致运行时访问 `self._capabilities` 触发 `AttributeError`。
- **架构影响**: 暴露了 IES 2.0 在模块注入契约上的实现疏漏。此外，由于隔离机制强制克隆了类型描述符，插件内部如果使用 `is STR_DESCRIPTOR` 判定类型，会因为内存地址不匹配而完全瘫痪。这导致插件系统目前处于“逻辑孤岛”状态，无法利用内核的类型转换能力。
- **融合 UTS/对象基座的方案**:
    1. **基于公理的依赖注入 (Axiom-based DI)**: 将 `setup` 过程重构为声明式注入。插件通过 `TypeAxiom` 声明其对内核能力（如 `InspectorAxiom`）的需求，由加载器在 STAGE 6 自动完成双向绑定。
    2. **统一装箱/拆箱公理 (Universal Boxing Axiom)**: 将 VTable 包装层（Proxy VTable）的类型转换逻辑迁移至各类型的 `ParserCapability` 公理中，使用契约判定（`is_assignable_to`）代替身份判定。
    3. **静态 Spec 校验**: 在编译阶段利用 UTS 类型格（Type Lattice）对插件定义的签名进行预校验。
- **评估**: 
    - **难度**: 中等 (3-5个工作日)。涉及 `loader.py` 重构与公理化迁移。
    - **风险**: 中等偏低。重构后能显著提升插件系统的工业级稳定性，支持 Core Dump 等高级特性。

### 3. 词法作用域 Shadowing（遮蔽）限制与“扁平池”逻辑断层 (Scope Shadowing & Flat-Pool Discontinuity)
- **判定**: **严重的 DSL 设计缺陷 / 闭包简化代价**。
- **逻辑链路剖析**:
    - **编译期 (Semantic Analyzer)**: [semantic_analyzer.py](file:///d:/Proj/intent-behavior-code-inter-master/core/compiler/semantic/passes/semantic_analyzer.py) 在定义新变量时，若发现外层已存在同名局部变量，会直接**复用 (Reuse)** 该符号实例，以简化闭包捕获逻辑。
    - **序列化期 (Flat Pooling)**: UID 生成绑定符号对象的内存地址。由于符号被复用，内层变量与外层变量被赋予了**完全相同的 UID**。
    - **运行时 (RuntimeContext)**: [runtime_context.py](file:///d:/Proj/intent-behavior-code-inter-master/core/runtime/interpreter/runtime_context.py) 采用扁平化的 `_uid_to_symbol` 映射。当执行赋值时，解释器通过相同的 UID 直接命中了父作用域的存储空间，造成了破坏性覆盖。
- **架构影响**: 导致系统在底层缺乏真正的“栈帧”概念，强行将分层的词法作用域拍扁。这不仅增加了编程心智负担（必须保证变量名全局唯一），也阻碍了多线程、协程及复杂模块化递归调用的实现，是 IBCI 走向工业级语言的最大瓶颈。
- **融合 UTS/对象基座的方案**:
    1. **编译器层重构**: 禁止符号复用。每个定义动作必须产生唯一 Symbol。引入显式的 `CaptureSymbol` 处理闭包捕获，而非物理复用。
    2. **运行时层栈帧化**: 将扁平变量池重构为真正的 **作用域栈 (Scope Stack)**。`define` 操作强制作用于栈顶，`get/set` 操作执行递归向外查找。
    3. **UTS 类型遮蔽校验**: 利用类型格（Type Lattice）在编译期增加遮蔽合法性及常量保护检查。
- **评估**: 
    - **难度**: 中等偏高 (5-7个工作日)。涉及语义分析与执行环境的同步重构，尤其是闭包逻辑的重新闭合。
    - **风险**: 中等 (局部架构震荡)。会打破现有的闭包实现，但这是补全执行环境一致性的最后一块拼图。

---

## 三、 架构健壮性审计与地基评价 (Base Integrity Audit)

### 1. 存储层：稳固 (Flat Pooling & Side-Tabling)
- **结论**: 成功实现了 AST 与语义侧表的物理分离。侧表索引逻辑正确。
- **建议**: 将 UID 生成由 `id()` 升级为基于内容的 `Hash` 以支持持久化。

### 2. 语义层：稳固 (Semantic Gateway)
- **结论**: 闭包捕获“意图栈快照”的设计非常优雅。采用不可变链表结构支持结构共享（Structural Sharing）。

### 3. 协议层：存在裂缝 (Penetration Violation)
- **缺陷**: `IbBehavior` 的“代理穿透”导致类型状态不一致。此外，审计发现 [scheduler.py](file:///d:/Proj/intent-behavior-code-inter-master/core/compiler/scheduler.py) 等组件存在对 `context.interpreter` 的穿透调用，这反映了**组合解耦模型的架构坍塌**。

---

## 四、 终极维修行动路线 (Action Roadmap)

1.  **[P0] 恢复语言生命力**:
    - 统一描述符匹配逻辑（由 `is` 改为 `name` 匹配）。
    - 强化 `unwrap()` 调用，确保 `LazyDescriptor` 正确解包。
2.  **[P1] 闭合公理体系**:
    - 补全 `list/dict` 的转换与构造公理。
    - 将 `converters.py` 中的硬编码逻辑迁移至各类型的 `ParserCapability` 公理实现中。
3. **[P2] 重构底层设施与插件基座**:
    - 升级变量池为支持变量遮蔽的栈帧结构。
    - 重构 `loader.py` 中的 VTable 构建逻辑，引入基于公理的依赖注入 (DI)。
    - 修复 `idbg` 模块的属性持久化逻辑，使其正确保留 `capabilities`。
    - 统一模块发现机制，修正 `_spec.py` 与 `spec.py` 的命名冲突。
4.  **[P3] 安全化内省协议**:
    - 修改 `IbBehavior` 路由逻辑，支持安全序列化，打通 Core Dump 链路。
