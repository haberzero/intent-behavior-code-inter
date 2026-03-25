# IBC-Inter 变更日志

> 本文档记录 IBC-Inter 项目的已完成变更，以精简的条目形式呈现。
>
> **生成日期**：2026-03-25
> **版本**：V1.1

---

## 2026-03-25 代码审计修正

### P0 级别问题修复记录

| 日期 | 任务 | 描述 | 状态 |
|------|------|------|------|
| 2026-03-25 | AUDIT-P0-1 | 审计发现 `llmexcept` 机制设计缺陷 - 异常捕获路径断裂 | 🔴 未修复 |
| 2026-03-25 | AUDIT-P0-2 | 审计发现 `intent_stack` 类型不匹配 - setter期望IntentNode但传入list | 🔴 未修复 |
| 2026-03-25 | AUDIT-P0-3 | 审计发现 `MOCK:FAIL/REPAIR` 前缀完全未实现 | 🔴 未修复 |
| 2026-03-25 | AUDIT-P0-4 | 审计发现意图标签 (`#1`, `#2`) 解析完全缺失 | 🔴 未修复 |

### P1 级别问题修复记录

| 日期 | 任务 | 描述 | 状态 |
|------|------|------|------|
| 2026-03-25 | AUDIT-P1-1 | `Symbol.Kind` typo - 应为 `SymbolKind` | 🔴 未修复 |
| 2026-03-25 | AUDIT-P1-2 | `FunctionMetadata.resolve_return` 协变错误 | 🔴 未修复 |
| 2026-03-25 | AUDIT-P1-3 | `int // int` 返回 `float` 而非 `int` | 🔴 未修复 |
| 2026-03-25 | AUDIT-P1-4 | `ai.set_retry()` 无效 - 硬编码为3 | 🔴 未修复 |
| 2026-03-25 | AUDIT-P1-5 | `@!` OVERRIDE 意图内容丢失 | 🔴 未修复 |

---

## 架构重构记录 (2026-03-20)

### P0 重构完成

| 日期 | 任务 | 涉及文件 |
|------|------|----------|
| 2026-03-20 | 重命名 `hydrator.py` → `axiom_hydrator.py` | kernel/types/axiom_hydrator.py |
| 2026-03-20 | 重命名 `type_hydrator.py` → `artifact_rehydrator.py` | runtime/loader/artifact_rehydrator.py |
| 2026-03-20 | 修复 `Registry.clone()` 的 `_metadata_registry` 共享bug | kernel/registry.py |
| 2026-03-20 | 添加 `MetadataRegistry.clone()` 方法 | kernel/types/registry.py |

### P1 重构完成

| 日期 | 任务 | 涉及文件 |
|------|------|----------|
| 2026-03-20 | 重命名 `foundation/` → `base/` | base/ |
| 2026-03-20 | 重命名 `domain/` → `kernel/` | kernel/ |
| 2026-03-20 | `KernelRegistry` 类名更新 | kernel/registry.py |
| 2026-03-20 | 实现完整的 `MetadataRegistry.clone()` | kernel/types/registry.py |

### P2 重构完成

| 日期 | 任务 | 涉及文件 |
|------|------|----------|
| 2026-03-20 | `run_isolated()` 序列化 artifact | runtime/host/service.py |
| 2026-03-20 | Interpreter 构造函数深拷贝 artifact_dict | engine.py |
| 2026-03-20 | 删除 `hot_reload_pools()` | runtime/interpreter/interpreter.py |
| 2026-03-20 | 实现 `ImmutableArtifact` 包装器 | runtime/serialization/immutable_artifact.py |

---

## 命名冲突解决记录

| 原冲突 | 解决方案 |
|--------|----------|
| 同名文件 "registry.py": 3个 | → kernel/registry.py + kernel/types/registry.py + kernel/axioms/registry.py |
| 同名类 "TypeHydrator": 2个 | → AxiomHydrator + ArtifactRehydrator |
| 同名概念 "Registry": 5处 | → KernelRegistry + MetadataRegistry + AxiomRegistry + HostModuleRegistry |

---

## 内置函数记录

| 函数 | 文件 | 状态 |
|------|------|------|
| `len()`, `range()` | intrinsics/collection.py | ✅ |
| `print()`, `input()` | intrinsics/io.py | ✅ |
| `get_self_source()` | intrinsics/meta.py | ✅ |
| `register_conversion` | intrinsics/conversion.py | ✅ 已删除 |

---

## 公理实现状态

| 公理类 | Operators | Converter | Parser | Iter | Subscript | Call | 状态 |
|--------|-----------|-----------|--------|------|-----------|------|------|
| IntAxiom | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | 完整 |
| FloatAxiom | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | 完整 |
| BoolAxiom | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | 完整 |
| StrAxiom | ✅ | ❌ | ✅ | ✅ | ✅ | ❌ | 需扩展 |
| ListAxiom | ❌ | ❌ | ✅ | ✅ | ✅ | ❌ | 完整 |
| DictAxiom | ❌ | ❌ | ✅ | ✅ | ✅ | ❌ | 完整 |
| DynamicAxiom | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | 仅Any/var完整 |

**占位符确认**：
- `DynamicAxiom("behavior")` - Behavior公理只是占位符
- `DynamicAxiom("callable")` - Callable公理只是占位符

---

## 测试文件记录

> 以下测试文件存在于 tests/ 目录

| 测试目录 | 文件数 |
|---------|--------|
| tests/base/ | 6 |
| tests/kernel/ | 10 |
| tests/compiler/lexer/ | 4 |
| tests/compiler/parser/ | 2 |
| tests/compiler/semantic/ | 1 |
| **总计** | **25** |

---

## 已排除的设计

| 排除项 | 理由 |
|--------|------|
| 进程级隔离 | 实例级隔离已足够 |
| 核心级 IPC | 通过外部 file 插件实现 |
| GDB 式断点 | DynamicHost 断点是现场保存/恢复/回溯 |
| hot_reload_pools | 违反解释器不修改代码原则 |
| generate_and_run | 动态生成IBCI应由显式的IBCI生成器进行 |

---

*本文档为 IBC-Inter 变更日志，最后更新：2026-03-25*
