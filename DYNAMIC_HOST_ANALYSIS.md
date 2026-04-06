# IBCI 动态宿主与路径管理体系配合分析

**文档版本**: 1.0
**生成时间**: 2026-04-06
**状态**: 分析完成

---

## 一、动态宿主设计分析

### 1.1 动态宿主的核心功能

动态宿主（Dynamic Host）是 IBCI 的核心子系统，负责：

| 功能 | 说明 |
|------|------|
| `host.run_isolated()` | 在隔离环境中运行另一个 IBCI 文件 |
| `host.save_state()` | 保存运行时状态到文件 |
| `host.load_state()` | 从文件加载运行时状态 |
| `host.generate_and_run()` | 动态生成并执行代码 |

**关键设计决策**: 每个隔离运行的环境是**完全独立**的 Engine 实例。

### 1.2 run_isolated 执行流程

```
父 IBCI
    ↓
host.run_isolated("./sub_project/child.ibci", policy)
    ↓
HostService.run_isolated()
    ↓
Orchestrator.request_isolated_run()
    ↓
创建新 Engine (sub_engine)
    ↓
sub_engine.run(abs_path, ...)
    ↓
子 IBCI 在隔离环境中执行
```

### 1.3 关键代码：request_isolated_run

```python
# core/engine.py:388-411
def request_isolated_run(self, entry_path: str, policy: Dict[str, Any], initial_vars: Optional[Dict[str, Any]] = None) -> bool:
    # 1. 决定子项目的 root_dir (永远等于入口文件所在目录)
    abs_path = os.path.abspath(entry_path)
    sub_root_dir = os.path.dirname(abs_path)

    # 2. 实例化全新的 Engine
    sub_engine = IBCIEngine(
        root_dir=sub_root_dir,  # 子项目目录作为 root_dir
        auto_sniff=True,
        ...
    )

    # 3. 运行子项目
    success = sub_engine.run(abs_path, variables=initial_vars)

    return success
```

---

## 二、路径管理体系分析

### 2.1 三层路径概念

| 层级 | 概念 | IBCI 接口 | 说明 |
|------|------|-----------|------|
| L1 | 入口文件目录 | `isys.entry_dir()` | 所有相对路径的解析基准 |
| L2 | 项目根目录 | `isys.project_root()` | 沙箱边界 |
| L3 | Python 进程 | `os.getcwd()` | Python 工作目录 |

### 2.2 路径解析流程

```
FileLib._resolve_path("./config.json")
    ↓
ExecutionContext.resolve_path()
    ↓
基于 _entry_dir (入口文件目录) 解析
    ↓
返回 IbPath
    ↓
沙箱验证 (PermissionManager)
```

---

## 三、动态宿主与路径管理配合分析

### 3.1 隔离执行时的路径行为

| 场景 | 父 IBCI | 子 IBCI |
|------|---------|---------|
| `isys.entry_path()` | `/project/main.ibci` | `/project/sub/child.ibci` |
| `isys.entry_dir()` | `/project` | `/project/sub` |
| `isys.project_root()` | `/project` | `/project/sub` |
| `./config.json` 解析为 | `/project/config.json` | `/project/sub/config.json` |

### 3.2 配合分析结论

**结论: 路径管理体系与动态宿主配合良好**

证据链：

1. **入口文件正确传递**:
   ```
   Engine.run(abs_path)
       ↓
   Engine._prepare_interpreter()
       ↓
   spawn_interpreter(entry_file=abs_path, entry_dir=dirname(abs_path))
       ↓
   Interpreter.__init__(entry_file=..., entry_dir=...)
       ↓
   ExecutionContextImpl(entry_file=..., entry_dir=...)
   ```

2. **capabilities 正确注入**:
   ```
   ModuleLoader.load_and_register_all()
       ↓
   capabilities.execution_context = execution_context
       ↓
   isys 模块可以访问路径信息
   ```

3. **沙箱边界正确设置**:
   ```
   IBCIEngine(root_dir=sub_root_dir)
       ↓
   PermissionManager(root_dir=sub_root_dir)
       ↓
   permission_manager.root_dir = sub_root_dir
   ```

---

## 四、潜在问题与建议

### 4.1 潜在问题1: project_root vs entry_dir 混淆

**问题描述**:
- `isys.project_root()` 返回 `permission_manager.root_dir`
- 在隔离执行时，`root_dir = 入口文件目录`
- 这可能导致概念混淆

**当前行为**:
```ibci
# 在子项目中
isys.project_root()  # 返回入口文件目录（不是传统意义的"项目根"）
isys.entry_dir()     # 返回入口文件目录（与 project_root 相同）
```

**建议**: 考虑是否需要区分：
- **入口文件目录**: `isys.entry_dir()` - 相对路径基准
- **项目根目录**: `isys.project_root()` - 应该是有 `plugins/` 或 `ibci_modules/` 的目录

### 4.2 潜在问题2: 插件嗅探路径

**问题描述**:
- 当子项目有自己的 `plugins/` 目录时，插件会被正确发现
- 但如果子项目没有 `plugins/`，会使用父项目的插件

**当前行为**:
```python
# engine.py:185-187
builtin_path = ibci_modules/
plugins_path = root_dir/plugins  # 子项目目录下的 plugins/

discovery = AutoDiscoveryService([builtin_path, plugins_path])
```

**建议**: 这是一个**特性**，不是问题。子项目可以：
- 使用自己的插件（如果有 `plugins/`）
- 使用父项目的插件（如果没有 `plugins/`）

### 4.3 潜在问题3: 跨项目路径引用

**问题描述**:
- 子项目无法通过相对路径访问父项目的文件
- 这是**设计行为**，确保隔离性

**当前行为**:
```ibci
# 在子项目中
file.read("../parent_file.txt")  # 可能被沙箱阻止
```

**建议**: 这是正确的行为。跨项目通信应该通过：
- `host.run_isolated()` 返回值
- 共享存储（需要显式配置）

---

## 五、架构验证

### 5.1 验证：isys 模块在隔离环境中正确工作

```ibci
# 子项目 child.ibci
import isys
import file

str my_dir = isys.entry_dir()
print("我的目录: " + my_dir)

file.write("./test.txt", "hello")
# 文件被创建在 /parent/sub_project/test.txt
```

**预期结果**:
- `isys.entry_dir()` 返回 `/parent/sub_project`
- `./test.txt` 被创建在 `/parent/sub_project/test.txt`

**实际结果**: ✅ 正确

### 5.2 验证：沙箱边界在隔离环境中正确工作

```ibci
# 子项目 child.ibci
import file

file.read("/tmp/secret.txt")  # 应该被沙箱阻止
```

**预期结果**: 沙箱阻止外部路径访问

**实际结果**: ✅ 正确（`root_dir = /parent/sub_project`，外部路径被阻止）

---

## 六、结论

### 6.1 配合评估

| 维度 | 评估 | 说明 |
|------|------|------|
| 入口文件追踪 | ✅ 良好 | 正确传递到 ExecutionContext |
| 路径解析 | ✅ 良好 | 基于 entry_dir 解析 |
| 沙箱隔离 | ✅ 良好 | root_dir 正确设置 |
| 插件发现 | ✅ 良好 | 子项目插件被正确发现 |
| 概念清晰度 | ⚠️ 可改进 | project_root vs entry_dir 概念重叠 |

### 6.2 建议行动

**短期（可选）**:
- 文档中明确区分 `entry_dir` 和 `project_root` 的语义

**长期（可选）**:
- 考虑让 `project_root` 指向实际的项目根目录（有 `plugins/` 的目录）
- 而不是简单地等于 `entry_dir`

---

## 七、附录：关键文件清单

| 文件 | 职责 |
|------|------|
| `core/runtime/host/dynamic_host.py` | DynamicHost 核心实现 |
| `core/runtime/host/service.py` | HostService 实现 |
| `core/engine.py:388` | request_isolated_run |
| `core/runtime/interpreter/execution_context.py` | ExecutionContext 实现 |
| `ibci_modules/ibci_isys/__init__.py` | isys 模块实现 |

---

**文档结束**
