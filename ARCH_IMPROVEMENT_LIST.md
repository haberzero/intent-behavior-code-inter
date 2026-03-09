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

### 阶段二：注册表服务化与隔离加固 (Foundation 层重构) [COMPLETED]
**核心目标**：将 `Registry` 转型为“类型系统服务”，并实现多引擎实例的物理隔离与权限审计。

1.  **多引擎实例隔离**：已在 [descriptors.py](file:///c:/myself/proj/intent-behavior-code-inter/core/domain/types/descriptors.py) 中通过原型深拷贝机制实现描述符的物理隔离。
2.  **权限审计机制**：已在 [registry.py](file:///c:/myself/proj/intent-behavior-code-inter/core/foundation/registry.py) 实现 `PrivilegeLevel` 与令牌双轨制（KERNEL/EXTENSION），保护内核工厂函数不被篡改。
3.  **编译器上下文对齐**：编译器前端（Prelude/Analyzer）已改为从引擎 `Registry` 实例动态获取类型符号，确保静态检查与运行时环境完全同步。

### 阶段三：编译器“去逻辑化” (Domain 层重构) [COMPLETED]
**核心目标**：剥离 [symbols.py](file:///c:/myself/proj/intent-behavior-code-inter/core/domain/symbols.py) 中的硬编码模拟，将行为协议彻底委托给描述符。

1.  **重构 `StaticType` 基类**：已完成。`is_callable`、`is_iterable`、`is_subscriptable` 等行为协议已彻底代理至 UTS 描述符。
2.  **统一运算符决议**：已将数值、字符串、列表等运算符决议逻辑收拢至 [descriptors.py](file:///c:/myself/proj/intent-behavior-code-inter/core/domain/types/descriptors.py) 的 `get_operator_result` 中。
3.  **简化符号层级**：废弃了冗余的 `IntType`、`StringType` 子类，实现了符号层对元数据的“中立包装”。

### 阶段四：引导程序与文件位置重组织 (Runtime 层合龙) [COMPLETED]
**核心目标**：理顺文件职责，实现“定义与实现”的分离。

1.  **文件位置迁移**：已将 `initialization.py` 迁移至 `core/runtime/bootstrap/builtin_initializer.py`。
2.  **职责剥离**：`builtin_initializer.py` 现在仅负责“根据 Schema 注入 Python 实现逻辑”，而具体的 Schema 定义已完全下沉到 `core/domain/builtin_schema.py`。
3.  **IES 2.0 插件协议准备**：Registry 已支持扩展令牌注册类与元数据，为插件系统的平滑接入打下了基础。

### 阶段五：验证、合龙与清理 (Finalization) [COMPLETED]
**核心目标**：解除屏蔽，全量跑通，优化结构。

1.  **全量测试跑通**：已解除所有 `unittest.skip`，24 项基础测试全部 Passed。
2.  **运行时查找优化**：已在 [interpreter.py](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/interpreter/interpreter.py) 实现 IbName 查找失败时向 Registry 类对象的回退，解决了 `int(x)` 等内置构造行为。
3.  **命名空间冲突修复**：清除了 `conversion.py` 中的全局冗余函数，统一了内置类与全局转换函数的语义。

### 阶段六：IES 2.0 插件系统 (Developer Experience & Contract Alignment) [IN_PROGRESS]
**核心目标**：建立“契约对齐”的插件开发协议，解决 `spec.py` 与实现层脱节的问题。

1.  **建立 `ibci-sdk`**：引入 [@ibci.method](file:///c:/myself/proj/intent-behavior-code-inter/core/extension/sdk.py) 装饰器，显式绑定实现函数与 UTS 契约符号。
2.  **启动时签名校验**：在 [loader.py](file:///c:/myself/proj/intent-behavior-code-inter/core/runtime/module_system/loader.py) 加载插件时，强制对比 Spec 与 Python 函数签名，确保“定义即实现”。
3.  **自动化数据转换 (Marshaling)**：基于 UTS 描述符实现入参自动解箱（Unboxing）与出参自动装箱（Boxing），降低插件开发心智负担。

---

**汇报总结**：
本次改造不仅是代码的搬迁，更是 **“定义权”从运行时向领域层（Domain）的收拢**。通过“声明式 Schema”替代“命令式注入”，我们将彻底消除“二元对齐”风险，使 IBCI 2.0 真正具备成熟的面向对象底座。
