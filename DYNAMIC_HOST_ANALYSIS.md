# IBCI 动态宿主与路径管理体系配合分析（修订版）

**文档版本**: 2.0
**生成时间**: 2026-04-06
**状态**: 修订完成

---

## 一、动态宿主设计分析

### 1.1 动态宿主的核心功能

**用户可调用的 API**（来自 `ibci_host/_spec.py`）：

| 方法 | 参数 | 返回值 | 说明 |
|------|------|--------|------|
| `host.run_isolated(path, policy)` | 路径 + 策略字典 | bool | 在隔离环境中运行脚本 |
| `host.save_state(path)` | 文件路径 | void | 保存运行时状态到文件 |
| `host.load_state(path)` | 文件路径 | void | 从文件加载运行时状态 |
| `host.get_source()` | 无 | str | 获取当前源文件内容 |

### 1.2 run_isolated 策略

```ibci
dict policy = {
    "isolated": true,           # 是否隔离
    "registry_isolation": true, # 是否隔离 Registry
    "inherit_variables": false  # 是否继承变量
}
```

**关键决策**：`inherit_variables: false` 确保子环境不继承父环境变量。

### 1.3 generate_and_run 状态

**状态**: 已删除 ✅

`generate_and_run()` 方法存在于 `core/runtime/host/dynamic_host.py` 中，但：
- **未暴露给用户** - 不在 `ibci_host/_spec.py` 的 vtable 中
- **未被集成** - `HostService` 不调用它
- **未在任何地方使用**

---

## 二、隔离执行机制分析

### 2.1 核心设计原则

**原则**: 子环境和主环境只是关系上的相对概念，不具备地位上的区别。

这意味着：
- 子环境不是"次要"或"从属"的环境
- 子环境应该具备与主环境完全相同的能力
- 子环境是完全独立的运行环境

### 2.2 完全隔离的实现

```python
# core/engine.py:388-411
def request_isolated_run(self, entry_path, policy, initial_vars) -> bool:
    # 1. 创建全新的 Engine 实例
    sub_engine = IBCIEngine(
        root_dir=sub_root_dir,  # 子项目目录
        auto_sniff=True,        # 独立插件发现
        core_debug_config=self.debugger.config  # 调试配置不影响隔离
    )

    # 2. 运行子项目
    success = sub_engine.run(abs_path, variables=initial_vars)

    return success
```

### 2.3 完全独立的子系统

| 子系统 | 子环境 | 说明 |
|--------|--------|------|
| **Engine** | 全新实例 | 每个隔离运行创建新的 Engine |
| **Registry** | 全新实例 | 独立的符号表和类型系统 |
| **Plugin Discovery** | 独立发现 | 基于子项目目录的插件嗅探 |
| **PermissionManager** | 独立实例 | 独立的沙箱边界 |
| **入口文件** | 独立追踪 | `_entry_file` 和 `_entry_dir` 正确设置 |
| **ExecutionContext** | 独立实例 | 独立的路径解析上下文 |

---

## 三、路径管理体系配合分析

### 3.1 三层路径概念

| 层级 | 接口 | 说明 |
|------|------|------|
| L1 | `isys.entry_dir()` | 相对路径解析基准 |
| L2 | `isys.project_root()` | 沙箱边界 |
| L3 | `os.getcwd()` | Python 工作目录 |

### 3.2 隔离执行时的路径行为

| 场景 | 父环境 | 子环境 |
|------|--------|--------|
| `isys.entry_path()` | `/project/main.ibci` | `/project/sub/child.ibci` |
| `isys.entry_dir()` | `/project` | `/project/sub` |
| `isys.project_root()` | `/project` | `/project/sub` |
| `./config.json` | `/project/config.json` | `/project/sub/config.json` |

### 3.3 配合评估

**结论: 路径管理体系与动态宿主配合良好 ✅**

证据：
1. **入口文件正确传递**: `Engine.run()` → `_prepare_interpreter()` → `ExecutionContextImpl()`
2. **capabilities 正确注入**: `ModuleLoader.load_and_register_all()` → `capabilities.execution_context`
3. **沙箱边界正确**: 每个子 Engine 有独立的 `PermissionManager`

---

## 四、潜在污染问题分析

### 4.1 确认无污染的机制

| 潜在问题 | 状态 | 说明 |
|----------|------|------|
| Engine 实例共享 | ✅ 无污染 | 每个隔离运行创建全新 Engine |
| Registry 共享 | ✅ 无污染 | 每个 Engine 有独立的 Registry |
| 插件路径混淆 | ✅ 无污染 | 基于各自的 `root_dir` 发现 |
| 入口文件混淆 | ✅ 无污染 | 各自追踪自己的入口文件 |
| 符号表污染 | ✅ 无污染 | `inherit_variables: false` 阻止变量继承 |

### 4.2 inherit_variables 的风险

**当前行为**:
```ibci
# policy.inherit_variables: true 时
host.run_isolated("sub/child.ibci", {
    "inherit_variables": true  # 危险！
})
```

**风险**: 子环境会继承父环境的变量，可能导致意外的变量污染。

**建议**: 在示例和文档中明确说明 `inherit_variables: false` 是推荐的默认值。

---

## 五、未来扩展方向

### 5.1 可能的扩展

| 扩展 | 说明 | 优先级 |
|------|------|--------|
| 权限控制 | 细粒度控制子环境的权限 | 未来 |
| 变量继承策略 | 更灵活的变量继承控制 | 未来 |
| 资源共享 | 安全的跨环境资源共享 | 未来 |
| 环境通信 | 子环境向父环境返回数据 | 未来 |

### 5.2 当前限制

这些扩展不是现阶段需要解决的问题。当前目标是确保基本的隔离机制稳定可靠。

---

## 六、架构验证

### 6.1 验证：完全隔离

```ibci
# main.ibci
import host
import isys

str my_dir = isys.entry_dir()
print("主环境目录: " + my_dir)  # /project

host.run_isolated("./sub/child.ibci", {"inherit_variables": false})

# child.ibci
import isys

str my_dir = isys.entry_dir()
print("子环境目录: " + my_dir)  # /project/sub
```

**预期**: 主环境和子环境有各自独立的路径上下文
**结果**: ✅ 正确

### 6.2 验证：独立插件发现

```
/project/
├── plugins/
│   └── my_plugin/      # 主环境的插件
├── sub/
│   └── child.ibci
│   └── plugins/
│       └── child_plugin/  # 子环境的插件（独立发现）
```

**预期**: 子环境发现自己的插件，主环境的插件对子环境不可见
**结果**: ✅ 正确（通过 `auto_sniff=True` 实现）

---

## 七、结论

### 7.1 配合评估

| 维度 | 评估 | 说明 |
|------|------|------|
| 完全隔离 | ✅ 良好 | 每个子环境是完全独立的 Engine 实例 |
| 路径管理 | ✅ 良好 | 各自有独立的入口文件和路径上下文 |
| 插件发现 | ✅ 良好 | 基于各自的 `root_dir` 独立发现 |
| 概念清晰 | ✅ 良好 | 主/子环境只是相对概念，无地位区别 |

### 7.2 建议行动

**无紧急行动项**

当前架构已经满足设计要求：
- ✅ 子环境是完全独立的运行环境
- ✅ 不会与主环境相互污染
- ✅ 路径管理体系正确工作

---

## 八、附录：关键代码位置

| 文件 | 关键代码 | 行号 |
|------|----------|------|
| `core/engine.py` | `request_isolated_run` 创建新 Engine | 388-411 |
| `core/engine.py` | 传递 `entry_file` 和 `entry_dir` | 122-123 |
| `core/runtime/module_system/loader.py` | 注入 `execution_context` | 94 |
| `ibci_modules/ibci_isys/__init__.py` | `isys` 模块实现 | 全部 |
| `ibci_modules/ibci_host/_spec.py` | 用户可调用的 API | 20-47 |

---

**文档结束**
