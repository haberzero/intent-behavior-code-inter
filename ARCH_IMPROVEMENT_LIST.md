# IBC-Inter 2.0 架构优化与改进清单 (ARCH_IMPROVEMENT_LIST)

## 1. 核心架构哲学：定义权收归与单源真理 (Single Source of Truth)

经过深度核查，IBCI 2.0 的核心矛盾在于“语言定义权”的错位。目前定义权散落在编译器（手工模拟）和运行时（动态注入）。

### 1.1 职责重新划分 (Responsibility Re-evaluation)
- **Foundation (基础设施层)**：仅作为**纯粹的容器与协议定义**。`Registry` 和 `HostInterface` 负责存储元数据与实现，但不应包含任何具体的内置类逻辑（如 `int` 有哪些方法）。
- **Domain (领域/真理层)**：作为**语言定义的唯一来源**。定义“什么是 IBCI”，产出描述符（Schema）。
- **Compiler (编译器/检查层)**：作为**Schema 的消费者**。负责验证逻辑合法性，不应硬编码任何类型行为。
- **Runtime (运行时/执行层)**：作为**Schema 的填充者**。负责将描述符关联到具体的 Python 实现逻辑。

### 1.2 声明式 Schema 机制
- **现状**：命令式注册。运行时调用 `create_subclass` 并手动注入方法，导致编译器不可见。
- **目标**：引入 `core/domain/builtin_schema.py`。所有内置类型的 `TypeDescriptor`（方法签名、运算符行为）在此统一声明。编译器和运行时均通过此文件获取真理。

### 1.3 物理依赖解耦：结果中立化策略 (Result Neutralization) [COMPLETED]
- **核心原则**：UTS 层 (Domain/Types) 严禁引用 Symbol 层 (Domain/Symbols)。
- **实现机制**：`TypeDescriptor.resolve_member` 仅返回“元数据描述符” (TypeDescriptor)，而不返回符号 (Symbol)。由符号层负责将元数据包装为对应的 `FunctionSymbol` 或 `VariableSymbol`。
- **收益**：彻底杜绝了物理层面的循环导入，确保 UTS 作为纯粹的数据基座可被多方复用。

---

## 2. IBCI 2.0 核心架构演进计划 (EVOLUTION_PLAN_2.0)

### 阶段一：元数据基座与 UTS (统一类型系统) 升级 [COMPLETED]
**核心目标**：将 `TypeDescriptor` 从单纯的数据容器升级为具备“自描述行为”协议中心，并攻克循环依赖死锁。

1.  **增强 `TypeDescriptor` 协议**：已在 [descriptors.py](file:///c:/myself/proj/intent-behavior-code-inter/core/domain/types/descriptors.py) 中实现 `get_member_signature(name)`、`is_callable`、`get_operator_result` 等协议。
2.  **攻克循环依赖 (Two-Pass Analysis & Lazy Binding)**：实现了 `LazyDescriptor` 占位机制，支持编译器双遍解析（Collection & Resolution），完美解决循环引用死锁。
3.  **建立 `builtin_schema.py`**：已创建 [builtin_schema.py](file:///c:/myself/proj/intent-behavior-code-inter/core/domain/builtin_schema.py)，作为内置类型的“单源真理”。
4.  **符号系统重构**：[symbols.py](file:///c:/myself/proj/intent-behavior-code-inter/core/domain/symbols.py) 已完成“去硬编码”改造，所有类型行为均代理至对应的描述符。

### 阶段二：注册表服务化 (Foundation 层重构) [IN_PROGRESS]
**核心目标**：将 `Registry` 转型为“类型系统服务”。

1.  **`Registry` 接口扩展**：
    - 修改 [registry.py](file:///c:/myself/proj/intent-behavior-code-inter/core/foundation/registry.py)，要求 `register_class` 时必须强制关联 `TypeDescriptor`。
    - 增加 `export_manifest()` 接口，生成用于编译器的类型快照。
2.  **权限与安全加固**：
    - 完善令牌机制，区分“内核级注册”与“扩展级注册”，防止插件篡改核心行为。

### 阶段三：编译器“去逻辑化” (Domain 层重构)
**核心目标**：剥离 [symbols.py](file:///c:/myself/proj/intent-behavior-code-inter/core/domain/symbols.py) 中的硬编码模拟。

1.  **重构 `StaticType` 基类**：
    - 彻底废弃具体的 `IntType`, `StringType` 等子类。
    - 引入通用 `DescriptorType`，其行为完全代理至关联的 `TypeDescriptor`。
2.  **统一运算符决议**：
    - 将所有运算符（+、-、not 等）的决议逻辑从符号表移交给描述符系统，实现“行为随对象走”。

### 阶段四：引导程序与文件位置重组织 (Runtime 层合龙)
**核心目标**：理顺文件职责，实现“定义与实现”的分离。

1.  **文件位置迁移**：
    - 将 `initialization.py` 迁移至 `core/runtime/bootstrap/`，更名为 `builtin_initializer.py`。
    - 剥离其中的 Schema 定义代码，使其仅负责“根据 Schema 注入 Python 实现逻辑”。
2.  **IES 2.0 插件协议**：
    - 插件的 `setup()` 必须提交 `ModuleMetadata`，由引擎在编译前自动同步至 `Registry`。

---

## 3. 改造风险与代价评估

| 维度 | 评估结果 | 风险点/代价备注 |
| :--- | :--- | :--- |
| **涉及文件数** | **15+ 个** | 几乎触及所有核心模块，尤其是跨层引用部分 |
| **架构风险** | **极高 (Critical)** | 初始化顺序敏感：若 `int` 等基础描述符未就绪，编译器会发生不可调试的崩溃 |
| **循环依赖风险** | **高 (High)** | UTS 与 Symbol 之间的引用需要通过接口或基类解耦 |
| **改造代价** | **高 (High)** | 需要分 5 个阶段进行，每个阶段均需全量回测 24 个基础测试项 |

---

**汇报总结**：
本次改造不仅是代码的搬迁，更是 **“定义权”从运行时向领域层（Domain）的收拢**。通过“声明式 Schema”替代“命令式注入”，我们将彻底消除“二元对齐”风险，使 IBCI 2.0 真正具备成熟的面向对象底座。
