# IBC-Inter 变更日志

> 本文档记录 IBC-Inter 项目已完成的任务和工作，以精简的条目形式呈现。
> 保留了关键的操作记录和版本演进信息。
>
> **生成日期**：2026-03-21
> **版本**：V1.0

---

## 一、架构重构完成项

### 1.1 P0 级别任务（已完成）

| 日期 | 任务 | 描述 | 涉及文件 |
|------|------|------|----------|
| 2026-03-20 | P0-A | 重命名 `kernel/types/hydrator.py` → `axiom_hydrator.py`，类名 `TypeHydrator` → `AxiomHydrator` | kernel/types/axiom_hydrator.py |
| 2026-03-20 | P0-B | 重命名 `runtime/loader/type_hydrator.py` → `artifact_rehydrator.py`，类名 `TypeHydrator` → `ArtifactRehydrator` | runtime/loader/artifact_rehydrator.py |
| 2026-03-20 | P0-C | 更新所有导入：registry.py, artifact_loader.py, __init__.py | registry.py, artifact_loader.py |
| 2026-03-20 | P0-D | 修复 `builtin_initializer.py` 对 `uts.` 的依赖 | runtime/bootstrap/builtin_initializer.py |
| 2026-03-20 | P0-E | 修复 `Registry.clone()` 的 `_metadata_registry` 共享bug | kernel/registry.py |
| 2026-03-20 | P0-F | 添加 `MetadataRegistry.clone()` 方法的临时桩 | kernel/types/registry.py |

---

### 1.2 P1 级别任务（已完成）

| 日期 | 任务 | 描述 | 涉及文件 |
|------|------|------|----------|
| 2026-03-20 | P1-A | 重命名 `foundation/` → `base/`，`diagnostics/core_debugger.py` → `diagnostics/debugger.py` | base/ |
| 2026-03-20 | P1-B | 重命名 `domain/` → `kernel/` | kernel/ |
| 2026-03-20 | P1-C | `kernel/registry.py`（原 `base/registry.py`），类名 `Registry` → `KernelRegistry` | kernel/registry.py |
| 2026-03-20 | P1-D | `runtime/objects/type_registry.py` → `ib_type_mapping.py` | runtime/objects/type_registry.py |
| 2026-03-20 | P1-E | `base/host_interface.py` 中的 `RuntimeRegistry` → `HostModuleRegistry` | base/host_interface.py |
| 2026-03-20 | P1-F | 实现完整的 `MetadataRegistry.clone()` 方法（深克隆） | kernel/types/registry.py |
| 2026-03-20 | P1-G | 更新 `KernelRegistry.clone()` 使用完整的 `MetadataRegistry.clone()` | kernel/registry.py |

---

### 1.3 P2 级别任务（已完成）

| 日期 | 任务 | 描述 | 涉及文件 |
|------|------|------|----------|
| 2026-03-20 | P2-A | `run_isolated()` 序列化 artifact - 调用 FlatSerializer | runtime/host/service.py |
| 2026-03-20 | P2-B | Interpreter 构造函数中对 artifact_dict 做深拷贝 | engine.py |
| 2026-03-20 | P2-B.1 | IssueTracker实例隔离：每个子环境创建独立IssueTracker实例 | engine.py |
| 2026-03-20 | P2-C | 删除 `hot_reload_pools()` - 违反隔离原则 | runtime/interpreter/interpreter.py |
| 2026-03-20 | P2-D | 实现 `ImmutableArtifact` 包装器 | runtime/serialization/immutable_artifact.py |
| 2026-03-20 | P2-A.1 | registry.clone() 移至 HostService：隔离策略的决定权在调用者 | runtime/host/service.py, engine.py |
| 2026-03-20 | P2-A.2 | IInterpreterFactory 添加 isolated 参数 | runtime/interfaces.py |
| 2026-03-20 | P2-E | IExecutionContext 拆分：将 `IExecutionContext` 移至 `kernel/interfaces.py` | kernel/interfaces.py（新建）, runtime/interfaces.py |
| 2026-03-20 | P2-EXT-A | 删除 `register_conversion` 死代码 | intrinsics/conversion.py（已删除） |

---

## 二、命名冲突解决

### 2.1 同名文件冲突（已解决）

| 原冲突 | 解决方案 |
|--------|----------|
| 同名文件 "registry.py": 3个 | → kernel/registry.py + kernel/types/registry.py + kernel/axioms/registry.py |
| 同名类 "TypeHydrator": 2个 | → AxiomHydrator + ArtifactRehydrator |
| 同名文件 "interfaces.py": 2个 | 保持现状（base/interfaces.py + runtime/interfaces.py） |
| 同名概念 "Registry": 5处 | → KernelRegistry + MetadataRegistry + AxiomRegistry + HostModuleRegistry |

### 2.2 重命名完成清单

| 原路径 | 新路径/类名 |
|--------|-------------|
| `core/domain/types/hydrator.py` | `kernel/types/axiom_hydrator.py` → `AxiomHydrator` |
| `core/runtime/loader/type_hydrator.py` | `runtime/loader/artifact_rehydrator.py` → `ArtifactRehydrator` |
| `core/foundation/registry.py` | `kernel/registry.py` → `KernelRegistry` |
| `core/runtime/objects/type_registry.py` | `runtime/objects/ib_type_mapping.py` |
| `core/foundation/host_interface.py` 中的 `RuntimeRegistry` | `HostModuleRegistry` |

---

## 三、issue_tracker 诊断系统

### 3.1 系统定位

issue_tracker 是 IBC-Inter 的**集中化编译器诊断系统**，对应 Python 的编译检查和异常体系：

| 文件 | 职责 | 层级归属 |
|------|------|----------|
| `base/source_atomics.py` | `Severity` (Enum), `Location` (dataclass) | base (最底层) |
| `kernel/issue.py` | `Diagnostic`, `Locatable` (Protocol), 各种 Error 类 | kernel (核心层) |
| `compiler/diagnostics/issue_tracker.py` | `IssueTracker` - 诊断收集和管理 | compiler (编译器专用) |
| `compiler/diagnostics/formatter.py` | `DiagnosticFormatter` - 诊断格式化输出 | compiler (编译器专用) |
| `base/diagnostics/debugger.py` | `CoreDebugger` - 内核调试追踪 | base (基础设施) |

### 3.2 DynamicHost 下的 IssueTracker 设计原则

- 每个解释器实例（包括子环境）创建**独立的IssueTracker实例**
- IssueTracker诊断信息应**主动持久化到硬盘**
- 通过外部文件机制允许主环境查阅子环境的debug信息
- DynamicHost应提供启动参数控制IssueTracker的持久化行为

---

## 四、编译器-解释器隔离修复

### 4.1 已修复的问题

| 问题 | 位置 | 说明 |
|------|------|------|
| run_isolated调用compiler | service.py:136 | 应先序列化再传递 |
| hot_reload_pools可替换pools | interpreter.py:423-437 | 允许替换整个artifact字典 |
| artifact_dict引用传递 | engine.py | 直接引用，无深拷贝 |
| IssueTracker实例共享 | engine.py:103 | 子环境共享父环境IssueTracker |

### 4.2 扁平序列化输出结构

```json
{
    "entry_module": "模块名",
    "modules": {...},
    "global_symbols": {...},
    "pools": {
        "nodes": {...},
        "symbols": {...},
        "scopes": {...},
        "types": {...},
        "assets": {...}
    }
}
```

---

## 五、插件系统状态

### 5.1 三大插件职责

| 插件 | 状态 | 说明 |
|------|------|------|
| **AI** | ✅ 基本完整 | LLM调用接口，支持 set_config/call/retry 等 |
| **IDBG** | ✅ 完整 | vars()/last_llm()/env()/fields() - spec与实现一致 |
| **HOST** | ⚠️ 部分 | save_state/load_state/run_isolated - spec需更新 |

### 5.2 已注册的 IBC 模块

- **第一方**: `ai`, `idbg`, `host`, `file`, `math`, `json`, `net`, `schema`, `sys`, `time`
- **第三方**: 通过 `plugins_path` 加载的模块

---

## 六、内置函数（当前状态）

| 函数 | 文件 | 状态 |
|------|------|------|
| `len()`, `range()` | intrinsics/collection.py | ✅ 存在 |
| `print()`, `input()` | intrinsics/io.py | ✅ 存在 |
| `get_self_source()` | intrinsics/meta.py | ✅ 存在 |
| `register_conversion` | intrinsics/conversion.py | ✅ 已删除（死代码） |

**注意**：内置函数库目前严重不足，仅5个函数。扩展方式有两种：
1. 通过第一方插件（math, file等）提供
2. 通过公理体系的方法扩展（str/list/dict方法等）

---

## 七、Intent/Behavior 公理化状态

### 7.1 公理实现完整度

| 公理类 | 类型 | Operators | Converter | Parser | Iter | Subscript | Call | 状态 |
|--------|------|-----------|-----------|--------|------|-----------|------|------|
| IntAxiom | int | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | 完整 |
| FloatAxiom | float | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | 完整 |
| BoolAxiom | bool | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | 完整 |
| StrAxiom | str | ✅ | ❌ | ✅ | ✅ | ✅ | ❌ | 需扩展方法 |
| ListAxiom | list | ❌ | ❌ | ✅ | ✅ | ✅ | ❌ | 完整 |
| DictAxiom | dict | ❌ | ❌ | ✅ | ✅ | ✅ | ❌ | 完整 |
| DynamicAxiom | Any/var/callable/None/void/behavior | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | 仅Any/var完整 |

### 7.2 占位符确认

- `DynamicAxiom("behavior")` - Behavior公理只是占位符
- `DynamicAxiom("callable")` - Callable公理只是占位符
- Intent相关类型 - 尚未公理化

---

## 八、核心语法完成度

| 类别 | 完成度 | 说明 |
|------|--------|------|
| 核心语法结构 | **95%** | 控制流、函数、类、异常处理基本完善 |
| LLM集成语法 | **90%** | llm函数、行为表达式、意图系统完善 |
| 内置函数 | **15%** | 严重不足，仅5个函数 |
| 类型系统 | **80%** | 基础类型完整，但泛型/高级类型支持有限 |
| 运行时对象模型 | **85%** | UTS协议、消息传递机制完善 |
| **综合完成度** | **~65%** | 语法框架基本完成，内置库严重不足 |

---

## 九、架构健康度评估

| 层级 | 健康度 | 主要问题 |
|------|--------|---------|
| base/ | 92% | 无严重问题 |
| kernel/ | 88% | MetadataRegistry双轨并行（轻微） |
| compiler/ | 90% | 遗留注释需清理 |
| runtime/ | 85% | Bootstrap双轨问题（轻微） |
| **总体** | **88%** | 核心架构健康 |

---

## 十、关键设计决策记录

### 10.1 已明确的决策

| 决策 | 内容 |
|------|------|
| Intent Stack继承 | 当前阶段**不继承任何意图栈** |
| 子解释器插件 | 子解释器**不允许独立注册插件**，默认继承所有主解释器插件 |
| 动态生成IBCI | **不使用** generate_and_run，由显式IBCI生成器进行 |
| 信息交互 | **显式file读写**，不做隐式内存交互 |
| LLM并发 | **最小实现**：AI组件提供非阻塞调用 + sync语句同步 |
| 返回值类型 | **只允许基本内置类型**：int/str/bool/float/none |

### 10.2 已排除的设计

| 排除项 | 理由 |
|--------|------|
| 进程级隔离 | 实例级隔离已足够 |
| 核心级 IPC | 通过外部 file 插件实现 |
| GDB 式断点 | DynamicHost 断点是现场保存/恢复/回溯 |
| hot_reload_pools | 违反解释器不修改代码原则 |

---

*本文档为 IBC-Inter 变更日志，记录已完成的工作和关键决策。*
