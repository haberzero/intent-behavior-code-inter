# IBCI inherit_variables 配置分析

**文档版本**: 1.0
**生成时间**: 2026-04-06

---

## 一、当前默认值状态

### 1.1 IsolationPolicy 默认值

**结论: 默认值已经是 `inherit_variables: False` ✅**

```python
# core/runtime/host/isolation_policy.py:17-21
@dataclass
class IsolationPolicy:
    level: str = "PARTIAL"
    inherit_plugins: Optional[List[str]] = None
    inherit_intents: bool = False
    inherit_variables: bool = False  # ← 默认已经是 False
    inherit_classes: bool = True
```

### 1.2 预设策略

| 预设 | `inherit_variables` | 说明 |
|------|---------------------|------|
| `full()` | `True` | 完全隔离模式，继承所有内容 |
| `partial()` | `False` | 部分隔离模式（默认） |
| `plugin_only()` | `False` | 仅插件隔离 |
| `minimal()` | `False` | 最小隔离 |

---

## 二、会被继承的变量

### 2.1 继承逻辑

```python
# core/runtime/host/service.py:132-142
if policy.get("inherit_variables", False):
    # 提取父环境的全局变量 (排除内部变量)
    global_symbols = self.execution_context.runtime_context.global_scope.get_all_symbols()
    initial_vars = {}
    for name, sym in global_symbols.items():
        if not name.startswith("__") and not sym.metadata.get("is_builtin", False):
            val = self.execution_context.runtime_context.global_scope.resolve(name)
            if hasattr(val, 'get_value'):
                initial_vars[name] = val.get_value()
```

### 2.2 排除的变量

| 条件 | 示例 | 说明 |
|------|------|------|
| 以 `__` 开头 | `__internal_cache` | 内部变量 |
| `is_builtin=True` | `print`, `len`, `str` | 内置函数/类型 |

### 2.3 会继承的变量

**用户定义的变量**：

| 类型 | 示例 | 说明 |
|------|------|------|
| 配置字典 | `cfg = {"model": "gpt-4"}` | 用户配置 |
| 计算结果 | `count = 100` | 中间计算结果 |
| 导入模块 | `import file` | 模块引用 |

---

## 三、设计背景

### 3.1 为什么 `full()` 预设有 `inherit_variables: True`

`full()` 预设的目的是**完全隔离但共享状态**：

```
FULL 隔离级别:
├── Registry: 独立克隆 ✅
├── Plugins: 全部继承 ✅
├── Intents: 全部继承 ✅
├── Variables: 全部继承 ← 需要共享配置
├── CallStack: 全部继承 ✅
```

**使用场景**：
- 子环境需要使用父环境的配置
- 例如：AI API 密钥、数据库连接等

### 3.2 为什么 PARTIAL (默认) 有 `inherit_variables: False`

**设计决策**: 默认情况下不继承变量，确保子环境是**完全独立**的运行环境。

---

## 四、当前状态评估

### 4.1 用户示例分析

```ibci
# parent.ibci
dict policy = {
    "isolated": true,
    "registry_isolation": true,
    "inherit_variables": false  # ← 显式设置，但与默认值一致
}
```

**评估**: 用户显式设置了 `inherit_variables: false`，这与默认值一致，无需修改。

### 4.2 是否需要修改

| 问题 | 答案 | 说明 |
|------|------|------|
| 默认值需要改为 false 吗？ | **不需要** | 默认已经是 false ✅ |
| 示例代码需要修改吗？ | **不需要** | 示例已经正确 ✅ |
| `full()` 预设需要修改吗？ | **不需要** | 这是可选模式 ✅ |

---

## 五、结论

### 5.1 分析结果

1. **默认值已经是 `inherit_variables: False`** ✅
2. **用户示例已经使用正确的配置** ✅
3. **不需要任何修改** ✅

### 5.2 架构评估

| 维度 | 评估 | 说明 |
|------|------|------|
| 隔离正确性 | ✅ 良好 | 默认不继承变量 |
| 示例正确性 | ✅ 良好 | 显式设置 false |
| 灵活性 | ✅ 良好 | `full()` 提供可选项 |

### 5.3 建议

**无需修改任何代码。**

当前设计已经满足"子环境完全独立"的要求：
- 默认 `inherit_variables: False`
- `full()` 预设提供可选的变量共享模式

---

**文档结束**
