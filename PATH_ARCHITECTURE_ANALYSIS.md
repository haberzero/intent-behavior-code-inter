# IBCI 路径管理体系架构分析与重构指南

**文档版本**: 1.0
**生成时间**: 2026-04-06
**状态**: 待重构

---

## 执行摘要

经过系统性代码验证和多个独立分析确认，**IBCI 当前路径管理体系存在架构级缺陷**，所有设计假设均不成立。本文档记录问题分析、验证结论和重构方案，作为接下来工作的指导参考。

---

## 一、问题总览

| 问题 | 严重程度 | 影响范围 |
|------|----------|----------|
| 相对路径基准混乱 | 🔴 严重 | 全部 IBCI 程序 |
| 入口文件未追踪 | 🔴 严重 | 路径解析 |
| sys/ibci_sys 职责混杂 | 🟡 中等 | 模块设计 |
| FileLib 时序问题 | 🔴 严重 | 文件操作 |

---

## 二、详细问题分析

### 2.1 问题1: 相对路径基准混乱

**问题描述**: `./` 和 `../` 路径的解析基准是**调用栈最近帧**，而非**入口文件**。

**验证结论**: ✅ 确认

**关键代码**:

```python
# core/runtime/interpreter/execution_context.py:191-203
def get_current_script_path(self) -> Optional[str]:
    if self._logical_stack and self._logical_stack.frames:
        # 遍历调用栈，从栈顶向栈底
        for frame in reversed(self._logical_stack.frames):
            if frame.location and frame.location.file_path:
                ib_path = IbPath.from_native(frame.location.file_path)
                return ib_path.resolve_dot_segments().to_native()
    return None
```

**问题**:
- 使用 `reversed(self._logical_stack.frames)` 从栈顶（最近）向栈底遍历
- 返回**第一个**有 `file_path` 的帧的路径
- 这返回的是**当前执行位置**，而非入口文件

**影响**:
```ibci
# main.ibci 调用 utils.ibci
# 在 utils.ibci 中执行 file.read("./config.json")

# 期望: /project/config.json
# 实际: /project/utils/config.json  ← 错误
```

---

### 2.2 问题2: 入口文件未追踪

**问题描述**: IBCIEngine 和 ExecutionContext 都没有保存入口文件的绝对路径。

**验证结论**: ✅ 确认

**关键代码**:

```python
# core/engine.py:246-248
def run(self, entry_file: str, ...):
    abs_entry = os.path.abspath(entry_file)
    # abs_entry 仅作为局部变量使用，没有保存到 self

# core/engine.py:281-285
def compile(self, entry_file: str, ...):
    abs_entry = os.path.abspath(entry_file)
    # abs_entry 仅作为局部变量使用，没有保存到 self
```

**问题**:
- 入口文件路径仅在 `run()` 和 `compile()` 方法内作为局部变量使用
- 没有存储到任何实例属性
- `ExecutionContext` 没有 `_entry_file` 或类似属性

---

### 2.3 问题3: FileLib 时序问题

**问题描述**: `FileLib.setup()` 在模块加载阶段被调用，此时 `_logical_stack` 为空，导致 `script_dir` 为 `None`。

**验证结论**: ✅ 确认

**关键代码**:

```python
# ibci_modules/ibci_file/core.py:22-34
def setup(self, capabilities):
    self.capabilities = capabilities
    self.permission_manager = capabilities.service_context.permission_manager

    # 问题: setup() 在模块加载时调用，此时 _logical_stack 为空
    script_dir = capabilities.stack_inspector.get_current_script_dir()

    # 如果 _logical_stack 为空，这里会返回 None
    script_dir_ib = IbPath.from_native(script_dir) if script_dir else None

    project_root_ib = IbPath.from_native(
        capabilities.service_context.permission_manager.root_dir
    )

    self._path_resolver = PathResolver(project_root_ib, script_dir_ib)
```

**时序问题**:

| 阶段 | `_logical_stack.frames` | `script_dir` | 说明 |
|------|------------------------|--------------|------|
| 模块加载 | **空列表** | `None` | `setup()` 被调用 |
| 程序执行 | **有内容** | 应该是脚本目录 | `run()` 执行 |

**影响**: `./` 和 `../` 路径被错误地解析为项目相对路径。

---

### 2.4 问题4: sys/ibci_sys 职责混杂

**问题描述**: `ibci_sys` 模块同时包含路径查询和沙箱控制功能，职责不清晰。

**验证结论**: ✅ 确认

**关键代码**:

```python
# ibci_modules/ibci_sys/__init__.py

class SysLib:
    # === 路径查询方法 (应该是 isys 的职责) ===
    def script_dir(self) -> str:
        return self.capabilities.stack_inspector.get_current_script_dir() or ""

    def script_path(self) -> str:
        return self.capabilities.stack_inspector.get_current_script_path() or ""

    def project_root(self) -> str:
        return self.permission_manager.root_dir

    # === 沙箱控制方法 (应该是 sys 的职责) ===
    def request_external_access(self) -> None:
        self.permission_manager.enable_external_access()

    def is_sandboxed(self) -> bool:
        return not self.permission_manager.is_external_access_enabled()
```

**问题**: 一个模块混杂了两种不同职责的功能。

---

## 三、重构方案

### 3.1 架构设计目标

```
┌─────────────────────────────────────────────────────────────┐
│                    IBCI 运行时                              │
│                                                             │
│  入口文件路径 (Entry Point)                                │
│       ↓                                                     │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  EntryAnchor: 入口文件锚点（运行时只读）              │ │
│  └─────────────────────────────────────────────────────┘ │
│       ↓                                                     │
│  PathResolver: 所有相对路径解析的单一入口                    │
│       ↓                                                     │
│  ibci_file: 文件操作                                       │
└─────────────────────────────────────────────────────────────┘
```

### 3.2 核心修改

#### 3.2.1 修改 Engine

```python
# core/engine.py

class IBCIEngine:
    def __init__(self, root_dir: str = None, ...):
        # ... 其他初始化 ...

    def run(self, entry_file: str, ...):
        self._entry_file = os.path.abspath(entry_file)  # 保存入口文件
        self._entry_dir = os.path.dirname(self._entry_file)  # 提取入口目录

        context = ExecutionContext(
            entry_file=self._entry_file,
            entry_dir=self._entry_dir,
            # ... 其他参数 ...
        )
```

#### 3.2.2 修改 ExecutionContext

```python
# core/runtime/interpreter/execution_context.py

class ExecutionContextImpl:
    def __init__(
        self,
        entry_file: str,
        entry_dir: str,
        # ... 其他参数 ...
    ):
        self._entry_file = entry_file
        self._entry_dir = entry_dir
        # ... 其他初始化 ...

    def resolve_path(self, path: str) -> IbPath:
        """所有相对路径的统一解析入口"""
        ib_path = IbPath.from_native(path)

        if ib_path.is_absolute:
            return ib_path

        # 所有相对路径基于入口文件目录
        return (IbPath.from_native(self._entry_dir) / ib_path).resolve_dot_segments()

    def get_entry_path(self) -> str:
        """获取入口文件路径"""
        return self._entry_file

    def get_entry_dir(self) -> str:
        """获取入口文件目录"""
        return self._entry_dir
```

#### 3.2.3 修改 FileLib

```python
# ibci_modules/ibci_file/core.py

class FileLib:
    def setup(self, capabilities):
        self.capabilities = capabilities
        self.permission_manager = capabilities.service_context.permission_manager
        # 不再获取 script_dir

    def _resolve_path(self, path: str) -> str:
        """使用 ExecutionContext 的统一路径解析"""
        ib_path = self.capabilities.execution_context.resolve_path(path)
        native_path = ib_path.to_native()
        self.permission_manager.validate_path(native_path)
        return native_path
```

#### 3.2.4 分离 sys 和 isys

```python
# ibci_sys/isys.py (新文件 - 内核 provider)

class IBCISysLib:
    """IBCI 运行时核心模块"""

    def setup(self, capabilities):
        self._execution_context = capabilities.execution_context

    def entry_path(self) -> str:
        """获取入口文件路径"""
        return self._execution_context.get_entry_path()

    def entry_dir(self) -> str:
        """获取入口文件目录"""
        return self._execution_context.get_entry_dir()

# ibci_sys/__init__.py (重构 - 普通插件)

class SysLib:
    """系统能力模块 - 沙箱控制"""

    def request_external_access(self) -> None:
        self.permission_manager.enable_external_access()

    def is_sandboxed(self) -> bool:
        return not self.permission_manager.is_external_access_enabled()
```

---

## 四、实施计划

### 阶段1: 核心路径重构 (高优先级)

| 步骤 | 修改文件 | 说明 |
|------|----------|------|
| 1.1 | `core/engine.py` | 保存入口文件到实例属性 |
| 1.2 | `core/execution_context.py` | 添加 `entry_file`/`entry_dir` 参数和 `resolve_path()` 方法 |
| 1.3 | `ibci_modules/ibci_file/core.py` | 使用 `resolve_path()` 替代手动解析 |
| 1.4 | `core/runner.py` | 传递入口文件到 Context |

### 阶段2: 模块职责分离 (中优先级)

| 步骤 | 修改文件 | 说明 |
|------|----------|------|
| 2.1 | `ibci_modules/ibci_sys/__init__.py` | 重命名为 SysLib，只保留沙箱控制 |
| 2.2 | `ibci_modules/ibci_sys/isys.py` | 新建 IBCISysLib，负责运行时状态 |

### 阶段3: 示例修正 (低优先级)

| 步骤 | 修改文件 | 说明 |
|------|----------|------|
| 3.1 | `examples/01_getting_started/01_hello_ai.ibci` | 移除显式 `sys.script_dir()` 调用 |
| 3.2 | `examples/01_getting_started/03_path_management.ibci` | 更新路径说明 |

---

## 五、验证方法

### 5.1 单元测试

```ibci
# test_path_anchor.ibci
import file
import sys

str entry_dir = sys.entry_dir()
print("入口目录: " + entry_dir)

file.write("./test_anchor.txt", "测试")
bool exists = file.exists("./test_anchor.txt")

if exists:
    print("✓ 路径锚点正确")
    file.remove("./test_anchor.txt")
```

### 5.2 多级 import 测试

```ibci
# main.ibci
file.write("./main.txt", "main")
import "sub/lib.ibci"

# sub/lib.ibci
file.write("./lib.txt", "lib")
# 应该创建在 /project/lib.txt，不是 /project/sub/lib.txt
```

---

## 六、风险评估

| 风险 | 可能性 | 影响 | 缓解措施 |
|------|--------|------|----------|
| 破坏现有程序 | 中 | 高 | 添加版本检查，提示用户 |
| import 路径失效 | 低 | 中 | 更新示例代码 |
| 性能下降 | 极低 | 低 | 缓存入口目录 |

---

## 七、决策记录

| 日期 | 决策 | 理由 |
|------|------|------|
| 2026-04-06 | 所有相对路径基于入口文件目录 | 符合用户预期，更容易理解 |
| 2026-04-06 | 分离 isys 和 sys | 职责清晰，模块化良好 |

---

## 八、附录

### A. 相关文件清单

| 文件 | 作用 | 状态 |
|------|------|------|
| `core/engine.py` | 引擎入口 | 待修改 |
| `core/runtime/interpreter/execution_context.py` | 执行上下文 | 待修改 |
| `core/runtime/path/resolver.py` | 路径解析 | 已就绪 |
| `ibci_modules/ibci_file/core.py` | 文件操作 | 待修改 |
| `ibci_modules/ibci_sys/__init__.py` | 系统模块 | 待修改 |

### B. 术语表

| 术语 | 定义 |
|------|------|
| 入口文件 | `python main.py run script.ibci` 中的 `script.ibci` |
| 入口目录 | 入口文件所在的目录 |
| 项目根目录 | 包含 `plugins/` 或 `ibci_modules/` 的目录 |
| 脚本目录 | 当前正在执行的 IBCI 脚本所在目录 |

---

**文档结束**
