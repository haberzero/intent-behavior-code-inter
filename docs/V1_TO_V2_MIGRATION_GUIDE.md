# V1→V2 语义分析器迁移指南

> **状态**: ✅ V2已成为默认（2026-05-13）
> **V1状态**: 🟡 已废弃，保留作为回退选项
> **移除计划**: 待V2稳定运行1个月后完全移除V1

---

## 📋 迁移概述

### 什么改变了？

semantic_v2 现在是 IBCI 的**默认语义分析器**。所有新代码编译默认使用 V2。

| 方面 | V1 | V2 |
|------|----|----|
| 架构 | 单一2,192行文件 | 6个独立Pass，共2,026行 |
| 状态管理 | 13+可变实例变量 | 不可变Context |
| 错误处理 | 边分析边报错 | Error-as-Data，收集所有错误 |
| 元数据 | Python object引用 | UID-based，可序列化 |
| 代码量 | 3,386行（8文件） | 2,026行（6文件） |
| 默认状态 | ❌ 已废弃 | ✅ 默认启用 |

---

## 🚀 如何使用V2（默认）

### 自动启用（推荐）

```python
from core.engine import IBCIEngine

# V2自动启用，无需任何改动
engine = IBCIEngine()
result = engine.compile_string("int x = 42")
```

### 显式启用

```python
# 显式指定V2（与默认行为相同）
engine = IBCIEngine(use_semantic_v2=True)
```

---

## 🔄 如何回退到V1（不推荐）

如果遇到V2问题需要紧急回退：

```python
from core.engine import IBCIEngine

# 临时回退到V1
engine = IBCIEngine(use_semantic_v2=False)
```

⚠️ **警告**: V1将在未来版本中移除，请尽快报告V2问题。

---

## 🏗️ V2架构改进

### 1. Pipeline-Filter架构

V2采用6个独立Pass，清晰分离职责：

```
┌──────────────────────────────────────────┐
│  Pass 1: Symbol Collection              │
│  收集所有符号定义                          │
└──────────────────────────────────────────┘
                  ↓
┌──────────────────────────────────────────┐
│  Pass 2: Symbol Resolution               │
│  解析符号引用                              │
└──────────────────────────────────────────┘
                  ↓
┌──────────────────────────────────────────┐
│  Pass 3: Type Checking                   │
│  类型检查和推断                            │
└──────────────────────────────────────────┘
                  ↓
┌──────────────────────────────────────────┐
│  Pass 4: Binding Analysis                │
│  LLMExcept/Intent/Lambda绑定分析          │
└──────────────────────────────────────────┘
                  ↓
┌──────────────────────────────────────────┐
│  Pass 5: Behavior Dependency             │
│  行为依赖分析                              │
└──────────────────────────────────────────┘
                  ↓
┌──────────────────────────────────────────┐
│  Pass 6: Integrity Check                 │
│  完整性验证                                │
└──────────────────────────────────────────┘
```

### 2. 不可变Context

V1的13+可变变量 → V2的不可变Context：

```python
# V1（不好）
class SemanticAnalyzer:
    def __init__(self):
        self.symbol_table = SymbolTable()
        self.current_return_type = None
        self.current_class = None
        self.in_behavior_expr = False
        # ...还有9个以上的可变状态

# V2（好）
@dataclass(frozen=True)
class SemanticContext:
    ast: IbASTNode
    registry: Any
    symbol_table: SymbolTableContext
    type_environment: TypeEnvironment
    metadata: MetadataStore
    # 所有状态显式且不可变
```

### 3. Error-as-Data

V1边分析边报错 → V2收集所有错误：

```python
# V1: 遇到错误立即停止
if error:
    self.issue_tracker.error(...)
    return  # 停止分析

# V2: 收集所有错误，继续分析
diagnostics.append(Diagnostic(...))
# 继续分析，发现更多错误
```

### 4. UID-based Metadata

V1使用Python对象引用 → V2使用UID：

```python
# V1（不可序列化）
side_table.node_to_type[node_obj] = type_spec

# V2（可序列化）
metadata.type_bindings[node.uid] = type_spec
```

---

## 🔧 API兼容性

### CompilationResult结构保持不变

V2通过adapter完全兼容V1接口：

```python
@dataclass
class CompilationResult:
    module_ast: IbModule          # ✅ V2兼容
    symbol_table: SymbolTable     # ✅ V2兼容
    node_to_symbol: Dict          # ✅ V2通过adapter转换
    node_to_type: Dict            # ✅ V2通过adapter转换
    node_is_callable_instance: Dict  # ✅ V2兼容
    node_capture_mode: Dict       # ✅ V2兼容
    node_to_loc: Dict             # ✅ V2兼容
```

### 现有代码无需修改

所有依赖CompilationResult的代码**无需任何修改**：

```python
# 这段代码对V1和V2都有效
result = analyzer.analyze(ast_node)
symbol_table = result.symbol_table
type_spec = result.node_to_type[node]
```

---

## 🧪 测试迁移

### 测试自动使用V2

所有现有测试**自动使用V2**，无需修改：

```python
# 测试代码不需要改动
def test_my_feature():
    engine = IBCIEngine()  # 自动使用V2
    result = engine.compile_string("...")
    assert result.symbol_table.lookup("x") is not None
```

### 如果需要测试V1

```python
def test_v1_fallback():
    engine = IBCIEngine(use_semantic_v2=False)
    # 测试V1特定行为
```

---

## 🐛 已知差异与修复

### ✅ 已修复的问题

1. **CompilationResult结构不匹配** - ✅ 已修复
   - 问题：V2最初缺少node_to_symbol等字段
   - 修复：实现UID→object映射

2. **side_table访问** - ✅ 已修复
   - 问题：adapter缺少side_table属性
   - 修复：添加side_table属性，兼容V1接口

### ⚠️ 潜在差异

V2可能在以下场景表现不同（需要测试验证）：

1. **边界case处理** - 待测试
2. **错误消息格式** - 可能略有不同
3. **性能特征** - 可能更快或更慢

---

## 📊 性能影响

### 预期性能

| 维度 | V1 | V2 | 变化 |
|------|----|----|------|
| 内存使用 | 基准 | 预期相似 | ~0% |
| 编译速度 | 基准 | 待测量 | ? |
| 代码量 | 3,386行 | 2,026行 | -40% |

### 性能测试

运行性能对比：

```bash
python tools/validate_semantic_v2.py --verbose
```

---

## 🗺️ 迁移路线图

### ✅ Phase 1: 默认启用（已完成 2026-05-13）

- [x] V2设为默认
- [x] 修复CompilationResult兼容性
- [x] 标记V1为DEPRECATED

### ⏸️ Phase 2: 测试验证（进行中）

- [ ] 运行完整测试套件
- [ ] 修复发现的问题
- [ ] 性能对比报告

### 📅 Phase 3: V1完全移除（待定，~1个月后）

**前置条件**:
- V2稳定运行 > 1个月
- 所有测试通过
- 无严重bug报告
- 用户反馈正面

**行动**:
- 移除 `core/compiler/semantic/passes/semantic_analyzer.py`
- 移除 `core/compiler/semantic/passes/` 中V1相关文件
- 移除 Engine 的 `use_semantic_v2` 参数
- 更新所有文档

---

## 🆘 问题报告

### 如果遇到V2问题

1. **立即回退到V1**:
   ```python
   engine = IBCIEngine(use_semantic_v2=False)
   ```

2. **报告问题**:
   - 在GitHub Issue中描述问题
   - 提供最小可复现代码
   - 标记为 `semantic_v2` 标签

3. **帮助修复**:
   - 运行对比工具: `python tools/validate_semantic_v2.py`
   - 提供V1/V2差异报告

---

## 📚 相关文档

- `docs/SEMANTIC_REFACTORING_PLAN.md` - V2重构计划
- `docs/METADATA_ARCHITECTURE.md` - V2架构设计
- `docs/NEXT_STEPS.md` - 当前状态
- `docs/PENDING_TASKS.md` - 后续任务
- `tools/validate_semantic_v2.py` - V1/V2对比工具

---

## 🎉 总结

✅ **V2现在是默认** - 所有新代码自动使用V2
✅ **完全向后兼容** - 现有代码无需修改
✅ **V1可回退** - 遇到问题可临时回退
⏸️ **测试验证中** - 正在验证V2稳定性
📅 **V1将移除** - 稳定后将完全移除V1

**推荐**: 使用默认V2，遇到问题立即报告！
