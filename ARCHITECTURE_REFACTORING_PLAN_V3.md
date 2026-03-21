# IBC-Inter 底层架构重构计划 V3.0

> 本文档整合 ARCHITECTURE_REFACTORING_PLAN 和 CIRCULAR_IMPORT_ANALYSIS_PLAN_C 的分析结果，
> 基于用户最新的设计意图澄清、全量代码扫描、以及issue_tracker系统专项分析，提供完整的底层架构重构方案。
>
> **核心理念**：公理化基底、编译器-解释器分离、插件系统暴露、多实例安全
> **设计原则**：无历史包袱、无妥协、直观清晰、职责分明、命名精确

---

## 一、设计意图澄清（基于用户最新描述）

### 1.1 层级架构理念

| 层级 | 设计意图 | 当前实现 | 问题 |
|------|----------|----------|------|
| **公理化基底** | 独立于Python的概念层，可迁移到任何语言 | `domain/axioms/` + `foundation/source_atomic/` | 层级边界不清晰，axioms被domain嵌套掩盖基础性 |
| **Domain** | 包含AST、类型系统、符号系统、公理 | `core/domain/` | 命名与DDD混淆，实际是"核心语言概念" |
| **Foundation** | 调试基础设施、源码管理 | `core/foundation/` | 与Domain关系模糊，但确实是更底层 |
| **Compiler** | 输出不可变JSON，包含完整UID/类型/依赖关系 | 部分实现 | 隔离原则被违反（run_isolated调用compiler） |
| **Interpreter** | 通过hydrator还原运行时状态 | 部分实现 | JSON可被hot_reload_pools替换 |
| **Plugin System** | 暴露内部运行细节，支持外部插件 | 部分实现 | HOST插件缺少breakpoint语义 |

### 1.2 关键设计原则

1. **公理化基底独立于Python**
   - `core/domain/axioms/` 定义 IBC-Inter 类型行为规范
   - `core/foundation/source_atomic.py` 定义位置/严重级别等原子概念
   - 这些概念应该可以迁移到 C++ 或任何其他语言

2. **编译器-解释器严格分离**
   - 编译器输出**不可变扁平JSON** + 侧表
   - 解释器只能读取JSON，通过hydrator还原运行时
   - 解释器**禁止修改**原始JSON结构

3. **DynamicHost断点机制**
   - 依赖不可变JSON + 确定性侧表结构
   - 支持保存/跳出/回溯断点

4. **插件系统暴露内部细节**
   - AI插件：LLM调用接口
   - IDBG插件：给IBCI开发者的运行时调试
   - HOST插件：断点保存/恢复/回溯（当前缺少breakpoint语义）
   - core_debug：给内核开发者的调试（与IDBG互补）

---

## 二、全量扫描发现的关键问题

### 2.1 P0任务状态：**P0-1和P0-4已被修复**

**重要发现**：`symbols.py` 的问题已经被修复：
- ✅ 不再存在 `from .types import descriptors as uts` 顶层导入
- ✅ `FunctionSymbol.return_type` 已经返回 `None`（不再返回 `uts.VOID_DESCRIPTOR`）

**仍存在的 `uts.` 耦合问题**：
- `core/runtime/bootstrap/builtin_initializer.py:L8` - 仍使用 `from core.domain.types import descriptors as uts`
- `core/runtime/objects/builtins.py:L8` - 导入但未使用

### 2.2 命名冲突清单（高优先级）

**同类文件冲突统计**：
```
同名文件 "registry.py":  3 个
    - core/foundation/registry.py → Registry
    - core/domain/types/registry.py → MetadataRegistry, TypeFactory
    - core/domain/axioms/registry.py → AxiomRegistry

同名类 "TypeHydrator":  2 个
    - core/domain/types/hydrator.py → UTS类型水合器
    - core/runtime/loader/type_hydrator.py → JSON反序列化器

同名文件 "interfaces.py":  2 个
    - core/foundation/interfaces.py
    - core/runtime/interfaces.py

同名概念 "Registry":  5 处
    - Registry, MetadataRegistry, AxiomRegistry, CapabilityRegistry, RuntimeRegistry
```

**必须重命名的高优先级文件**：

| 当前路径 | 问题 | 建议新名称 |
|----------|------|------------|
| `core/domain/types/hydrator.py` | 与runtime/hydrator重名，职责是"公理注入" | `domain/types/axiom_hydrator.py` → `AxiomHydrator` |
| `core/runtime/loader/type_hydrator.py` | 与domain/hydrator重名，职责是"JSON反序列化" | `runtime/loader/artifact_rehydrator.py` → `ArtifactRehydrator` |
| `core/foundation/registry.py` | "Registry"太通用 | `foundation/kernel_registry.py` → `KernelRegistry` |
| `core/runtime/objects/type_registry.py` | 与MetadataRegistry名称混淆 | `runtime/objects/ib_type_mapping.py` |
| `core/foundation/host_interface.py`中的`RuntimeRegistry` | 与Registry类名混淆 | `HostModuleRegistry` |

### 2.3 编译器-解释器隔离违反（严重问题）

**发现的问题**：

| 问题 | 位置 | 说明 |
|------|------|------|
| **run_isolated调用compiler** | `service.py:136` | `self.compiler.compile_file()` 违反隔离原则 |
| **hot_reload_pools可替换pools** | `interpreter.py:423-437` | 允许替换整个artifact字典 |
| **artifact_dict引用传递** | `interpreter.py:173` | 直接引用，无深拷贝 |
| **JSON无不可变性保护** | `serializer.py` | FlatSerializer产出可变的dict |

### 2.4 多实例支持问题（Registry.clone bug）

**严重Bug**：`Registry.clone()` 第291行：
```python
new_registry._metadata_registry = self._metadata_registry  # 共享引用!
```

这导致 `isolated=True` 的 `spawn_interpreter` 无法真正隔离。

### 2.5 HOST插件能力不足

**当前问题**：
- spec.py仅定义save_state、load_state、run、get_source
- **没有breakpoint相关接口**（breakpoint_set/breakpoint_clear/breakpoint_list）
- backtrack只能通过save+load间接实现

---

## 三、issue_tracker 诊断系统专项分析

### 3.1 系统定位

issue_tracker 是 IBC-Inter 的**集中化编译器诊断系统**，对应 Python 的编译检查和异常体系：

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      compiler/diagnostics/                              │
│  ┌─────────────────────┐   ┌─────────────────────┐                  │
│  │  issue_tracker.py    │   │    formatter.py      │                  │
│  │                     │   │                     │                  │
│  │  IssueTracker 类     │   │  DiagnosticFormatter │                  │
│  │  - 收集诊断          │   │  - 格式化输出        │                  │
│  │  - 报告诊断          │   │  - ANSI颜色支持      │                  │
│  │  - 错误聚合          │   │  - 源码上下文显示    │                  │
│  └─────────────────────┘   └─────────────────────┘                  │
└─────────────────────────────────────────────────────────────────────────┘
```

### 3.2 组件关系

| 文件 | 职责 | 层级归属 |
|------|------|----------|
| `foundation/source_atomic.py` | `Severity` (Enum), `Location` (dataclass) - 物理位置信息 | **foundation** (最底层) |
| `domain/issue.py` | `Diagnostic`, `Locatable` (Protocol), 各种 Error 类 | **domain** (领域层) |
| `compiler/diagnostics/issue_tracker.py` | `IssueTracker` - 诊断收集和管理 | **compiler** (编译器专用) |
| `compiler/diagnostics/formatter.py` | `DiagnosticFormatter` - 诊断格式化输出 | **compiler** (编译器专用) |
| `foundation/diagnostics/core_debugger.py` | `CoreDebugger` - 内核调试追踪（与issue_tracker互补） | **foundation** (基础设施) |

### 3.3 关键设计："无盘化"诊断

IssueTracker 实现"无盘化"诊断，自动注入源码上下文：
```python
# issue_tracker.py L111-112
if resolved_loc and not resolved_loc.context_line and self.source_provider:
    resolved_loc.context_line = self.source_provider.get_line(resolved_loc.file_path, resolved_loc.line)
```

### 3.4 与插件系统的交互

```
IbPlugin 错误
    → PluginError 异常 (domain/issue.py)
    → IssueTracker.report() 捕获
    → 记录为 severity=ERROR, code="PLUGIN_ERROR", plugin_name 标识
    → DiagnosticFormatter 格式化输出
```

### 3.5 与core_debugger的互补关系

| 维度 | CoreDebugger | IssueTracker |
|------|-------------|-------------|
| **职责** | 内部执行追踪 | 诊断信息收集 |
| **输出** | 调试 trace 信息 | 编译/运行时错误 |
| **层级** | foundation/diagnostics/ | compiler/diagnostics/ |
| **触发** | DebugLevel 配置 | Severity 配置 |
| **异常** | 不抛出异常 | FATAL 抛出异常 |
| **目标用户** | 内核开发者 | 所有用户 |

**结论**：CoreDebugger 和 IssueTracker 各司其职，当前划分合理。

---

## 四、目标架构

### 4.1 推荐的目录结构

```
core/
├── base/                              # ★ 重命名：基础设施层（最底层 - 可迁移到任何语言）
│   ├── source/
│   │   └── source_atomics.py         # Location, Severity（原子概念）
│   ├── diagnostics/
│   │   ├── codes.py                   # 错误码常量 (LEX_*, PAR_*, SEM_*)
│   │   └── debugger.py                # ★ 重命名：CoreDebugger, DebugLevel
│   ├── enums.py                       # PrivilegeLevel, RegistrationState
│   ├── interfaces.py                  # 纯协议定义 (IExecutionContext等)
│   └── kernel_registry.py             # ★ 重命名：Registry → KernelRegistry
│
├── kernel/                            # ★ 重命名：原domain层（IBC-Inter核心概念）
│   ├── axioms/                        # 公理系统（类型行为规范）
│   │   ├── protocols.py              # TypeAxiom, CallCapability...
│   │   ├── primitives.py             # IntAxiom, StrAxiom, ListAxiom...
│   │   └── registry.py               # AxiomRegistry
│   ├── types/                         # 类型系统
│   │   ├── descriptors.py            # TypeDescriptor, FunctionMetadata...
│   │   ├── registry.py               # MetadataRegistry, TypeFactory
│   │   └── axiom_hydrator.py         # ★ 重命名：TypeHydrator → AxiomHydrator
│   ├── symbols.py                    # Symbol, SymbolTable, FunctionSymbol...
│   ├── blueprint.py                   # CompilationArtifact
│   ├── ast.py                        # AST节点定义
│   ├── factory.py                    # create_default_registry()
│   └── issue.py                      # ★ 移动：Diagnostic, LexerError等异常
│
├── compiler/                          # 编译器层（输出不可变JSON）
│   ├── lexer/
│   ├── parser/
│   ├── semantic/
│   ├── diagnostics/                   # ★ 诊断系统（编译器专用）
│   │   ├── issue_tracker.py          # IssueTracker - 诊断收集
│   │   └── formatter.py              # DiagnosticFormatter - 格式化输出
│   └── serialization/
│       └── serializer.py              # FlatSerializer - 输出扁平JSON
│
├── runtime/                           # 运行时层（通过hydrator还原）
│   ├── interpreter/
│   ├── loader/
│   │   ├── artifact_loader.py        # 加载JSON
│   │   └── artifact_rehydrator.py    # ★ 重命名：TypeHydrator → ArtifactRehydrator
│   ├── host/
│   │   ├── dynamic_host.py           # DynamicHost（支持断点）
│   │   └── isolation_policy.py      # 隔离级别
│   └── objects/
│
└── extension/                          # 插件系统（SDK层）
    ├── ibcext.py                     # IbPlugin基类
    ├── capabilities.py               # PluginCapabilities
    ├── exceptions.py                 # SDK异常
    └── spec_builder.py               # SpecBuilder
```

### 4.2 层级依赖关系（重构后）

```
base/ (最底层 - 原子概念，可迁移到任何语言)
    │
    ├── source/source_atomics.py     → Location, Severity
    ├── diagnostics/codes.py         → 错误码常量
    └── diagnostics/debugger.py      → CoreDebugger, DebugLevel
    │
    │  依赖
    ▼
kernel/ (核心层 - IBC-Inter核心语言概念)
    │
    ├── axioms/                     → 公理系统（类型行为规范）
    ├── types/registry.py            → MetadataRegistry（UTS元数据）
    ├── types/descriptors.py         → TypeDescriptor等
    ├── symbols.py                   → 符号系统
    └── issue.py                     → Diagnostic, 各种Error类
    │
    │  依赖
    ▼
compiler/ (只上不下，输出不可变JSON)
    │
    ├── diagnostics/issue_tracker.py → 诊断收集（使用 kernel/issue.py 的异常）
    └── serialization/serializer.py  → 输出扁平JSON
    │
    │  输出
    ▼
runtime/ (只下不上，通过artifact_rehydrator还原)
    │
    │  依赖
    ▼
extension/ (SDK层 - 只出不进)
```

### 4.3 层命名建议

| 当前名称 | 问题 | 建议名称 | 理由 |
|----------|------|----------|------|
| `foundation/` | 与DDD的Foundation混淆，且"底层"命名但实际是工具层 | `base/` | 更准确表示"通用基础设施" |
| `domain/` | 与DDD的Domain混淆，实际是"核心语言概念" | `kernel/` | 更准确表示"IBC-Inter语言内核" |

---

## 五、重构任务清单

### 5.1 P0级别（立即执行）

| 任务 | 描述 | 涉及文件 | 风险 | 状态 |
|------|------|----------|------|------|
| **P0-A** | 重命名 `domain/types/hydrator.py` → `axiom_hydrator.py`，类名 `TypeHydrator` → `AxiomHydrator` | domain/types/hydrator.py | 中 | 待执行 |
| **P0-B** | 重命名 `runtime/loader/type_hydrator.py` → `artifact_rehydrator.py`，类名 `TypeHydrator` → `ArtifactRehydrator` | runtime/loader/type_hydrator.py | 低 | 待执行 |
| **P0-C** | 更新所有导入：registry.py, artifact_loader.py, __init__.py | registry.py, artifact_loader.py | 低 | 待执行 |
| **P0-D** | 修复 `builtin_initializer.py` 对 `uts.` 的依赖 | runtime/bootstrap/builtin_initializer.py | 中 | 待执行 |
| **P0-E** | 修复 `Registry.clone()` 的 `_metadata_registry` 共享bug（临时修复：hasattr fallback） | foundation/registry.py | 中 | 待执行 |
| **P0-F** | 添加 `MetadataRegistry.clone()` 方法的临时桩（支持 P0-E 的 fallback） | domain/types/registry.py | 低 | 待执行 |

### 5.2 P1级别（目录重命名 + MetadataRegistry 完整克隆）

| 任务 | 描述 | 涉及文件 | 风险 | 依赖 |
|------|------|----------|------|------|
| **P1-A** | 重命名 `foundation/` → `base/`，`diagnostics/core_debugger.py` → `diagnostics/debugger.py` | foundation/ | 高 | P0 |
| **P1-B** | 重命名 `domain/` → `kernel/` | domain/ | 高 | P1-A |
| **P1-C** | `foundation/registry.py` → `kernel/registry.py`，类名 `Registry` → `KernelRegistry` | registry.py | 中 | P1-A |
| **P1-D** | `runtime/objects/type_registry.py` → `ib_type_mapping.py` | runtime/objects/type_registry.py | 低 | P1-B |
| **P1-E** | `foundation/host_interface.py` 中的 `RuntimeRegistry` → `HostModuleRegistry` | foundation/host_interface.py | 低 | P1-A |
| **P1-F** | 实现完整的 `MetadataRegistry.clone()` 方法（深克隆），替代 P0-F 的临时桩 | domain/types/registry.py | 高 | P1-B |
| **P1-G** | 更新 `Registry.clone()` 使用完整的 `MetadataRegistry.clone()` | foundation/registry.py | 中 | P1-F |

### 5.3 P2级别（编译器-解释器隔离修复）

| 任务 | 描述 | 涉及文件 | 风险 | 依赖 |
|------|------|----------|------|------|
| **P2-A** | 修复 `run_isolated()` 直接调用 compiler：在 `service.py` 中 `compile_file()` 后立即调用 `FlatSerializer` 将 `CompilationArtifact` 转为不可变 dict | runtime/host/service.py | 高 | P1-B |
| **P2-B** | Interpreter 构造函数中对 artifact 做深拷贝 | runtime/interpreter/interpreter.py | 中 | P2-A |
| **P2-C** | 移除或限制 `hot_reload_pools()`：加强校验+深拷贝 | runtime/interpreter/interpreter.py | 中 | P2-B |
| **P2-D** | 可选：实现 `ImmutableArtifact` 包装器 | runtime/loader/ | 中 | P2-C |

### 5.4 P3级别（HOST插件增强）

| 任务 | 描述 | 涉及文件 | 风险 | 依赖 |
|------|------|----------|------|------|
| **P3-A** | 为 HOST 插件添加 breakpoint 接口 | ibc_modules/host/spec.py | 中 | P2-A |
| **P3-B** | 实现 DynamicHost 的断点管理器 | runtime/host/dynamic_host.py | 高 | P3-A |
| **P3-C** | 实现 backtrack 调用栈快照机制 | runtime/interpreter/call_stack.py | 高 | P3-B |

---

## 六、issue_tracker诊断系统的改进建议

### 6.1 当前评估

issue_tracker 系统的层级划分**是合理的**：

| 组件 | 当前归属 | 评估 |
|------|----------|------|
| `Severity`, `Location` | foundation/source_atomic.py | ✅ 正确 - 最底层原子概念 |
| `Diagnostic`, Error类 | domain/issue.py | ✅ 正确 - 领域实体 |
| `IssueTracker` | compiler/diagnostics/ | ✅ 正确 - 编译器专用服务 |
| `DiagnosticFormatter` | compiler/diagnostics/ | ✅ 正确 - 编译器专用格式化 |

### 6.2 潜在的改进方向

1. **增强 CoreDebugger 与 IssueTracker 的联动**
   - 当 `DebugLevel >= DATA` 时，可将诊断信息同时写入 IssueTracker
   - 需要在 `base/diagnostics/debugger.py` 中添加配置选项

2. **IDBG 调试接口**
   - 当前没有暴露统一的调试接口供 IDE 集成
   - 可考虑添加 `IDebugAdapter` 接口，接收诊断事件

3. **插件错误来源标识**
   - `PluginError` 支持 `plugin_name`，但 IssueTracker 报告中无特殊处理
   - 可在 Diagnostic 中添加 `origin_module` 字段标识来源

---

## 七、架构原则总结

| 原则 | 说明 |
|------|------|
| **base/是最底层** | 只包含Location, Severity, DebugLevel等原子概念，可迁移到任何语言 |
| **kernel/是核心语言层** | 包含IBC-Inter特定抽象（AST, TypeDescriptor, Symbol, Axiom, Issue/异常） |
| **Compiler输出不可变JSON** | 编译器产生的JSON必须是不可变的，解释器禁止修改 |
| **Hydrator职责分明** | `AxiomHydrator`（类型-符号-公理桥接）+ `ArtifactRehydrator`（JSON反序列化） |
| **Plugin通过ibcext暴露** | 所有插件（AI, IDBG, HOST）通过统一SDK暴露能力 |
| **core_debug定位清晰** | 给内核开发者用的非侵入式调试工具，与IDBG互补 |
| **issue_tracker独立** | 诊断系统各司其职：base提供原子，kernel提供异常，compiler使用tracker |
| **命名精确** | 每个文件/类的名称必须明确标识其所属层级和职责 |

---

## 八、不再关注的问题（基于用户反馈）

以下问题在之前的分析中被过度关注，但实际不是核心问题：

| 问题 | 之前状态 | 用户反馈 | 结论 |
|------|----------|----------|------|
| **循环导入** | 高优先级 | "真正的循环依赖不存在" | 实际是TYPE_CHECKING保护的假问题 |
| **is_assignable_to的s is o** | 高优先级 | "跨实例比较是伪需求" | 同一实例内的interning优化，不是问题 |
| **Factory/DI模式滥用** | 高优先级 | "不要设计模式滥用" | 移除不必要的factory.py, axiom_injector.py，但保留必要的factory |
| **`from __future__ import annotations`** | - | "未告知使用" | 移除，只在必要时使用TYPE_CHECKING |

---

## 九、命名前缀规范

为避免将来继续出现同名冲突，建议采用以下命名规范：

| 层级 | 建议前缀 | 示例 |
|------|----------|------|
| base | 直接用描述性名称 | `source_atomics.py`, `debugger.py` |
| kernel | 无需前缀（kernel已经是限定词） | `axiom_hydrator.py`, `issue.py` |
| runtime | `rt_` 或 `runtime_` | `rt_artifact_rehydrator.py` |
| compiler | 无需前缀（compiler已经是限定词） | `issue_tracker.py`, `formatter.py` |
| extension | `ext_` 或 `extension_` | `extension_ibcext.py` |

---

*文档生成时间：2026-03-20*
*版本：V3.1（基于P0-E修复方案分析更新）*
*更新内容：
  - P0-E 修复方案更新：采用临时 hasattr fallback + P0-F 临时桩
  - 新增 P1-F：实现完整的 MetadataRegistry.clone() 深克隆方法
  - 新增 P1-G：更新 Registry.clone() 使用完整克隆
  - 调整任务分类：P0 保持紧急修复，P1 包含完整克隆实现
*