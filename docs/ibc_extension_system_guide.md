# IBC-Inter 扩展系统 (IES) 开发者指南 (v1.0 - 全面实战版)

本手册是为希望深度定制 IBC-Inter 功能的开发者准备的“保姆级”教程。通过阅读本手册，你将能够从零开始编写出像 `ai` 或 `idbg` 这样与内核深度交互的高级扩展模块。

---

## 1. 模块目录结构

一个标准的 IBC-Inter 扩展模块是一个标准的 Python 包，位于 `ibc_modules/` 目录下：

```text
ibc_modules/
└── my_module/            # 模块名 (ibci 中 import 的名称)
    ├── __init__.py       # 逻辑实现层 (Implementation)
    └── spec.py           # 接口定义层 (Specification)
```

---

## 2. 接口定义层 (`spec.py`)

`spec.py` 决定了 `.ibci` 代码能看到哪些函数、参数类型和返回值。它必须导出一个名为 `spec` 的对象。

### 2.1 使用 `SpecBuilder`
```python
from core.support.module_spec_builder import SpecBuilder

spec = (SpecBuilder("my_module")
    # 定义一个带参数和返回值的函数
    .func("calculate", params=["int", "float"], returns="float")
    # 定义一个不带返回值的函数
    .func("log_event", params=["str"])
    # 定义一个返回字典的函数
    .func("get_status", returns="dict")
    .build())
```

### 2.2 类型对应关系
在 `params` 和 `returns` 中使用的字符串必须符合 `ibci` 的类型系统：
-   `"int"`, `"float"`, `"str"`, `"bool"`: 基础类型。
-   `"list"`, `"dict"`: 容器类型。
-   `"var"`: 动态类型。
-   `None`: 表示无返回值。

---

## 3. 逻辑实现层 (`__init__.py`)

实现层负责具体的 Python 逻辑，并通过 **能力注入 (Capability Injection)** 与解释器内核交互。

### 3.1 核心样板代码
每个模块必须包含以下结构：

```python
from typing import Dict, Any, Optional
from core.runtime.ext.capabilities import ExtensionCapabilities

class MyModuleImpl:
    def __init__(self):
        # 用于存储内核注入的能力
        self._caps: Optional[ExtensionCapabilities] = None

    def setup(self, capabilities: ExtensionCapabilities):
        """
        [核心] 内核在加载模块后会自动调用此方法。
        capabilities 容器包含了内核主动暴露的所有只读能力。
        """
        self._caps = capabilities

    # 实现 spec.py 中定义的函数
    def calculate(self, a: int, b: float) -> float:
        return a + b

def create_implementation():
    """[必须] 导出此工厂函数，供加载器实例化模块"""
    return MyModuleImpl()
```

---

## 4. 深度交互：利用内核能力 (Capabilities)

这是 IES 架构的精髓。你的模块可以通过 `self._caps` 访问以下标准接口：

### 4.1 IStateReader (只读状态)
**用途**：像 `idbg.vars()` 一样获取当前程序的变量快照。
-   **方法**: `get_vars_snapshot() -> Dict[str, Dict[str, Any]]`
-   **返回结构**:
    ```python
    {
        "var_name": {
            "value": 42,
            "type": "int",
            "is_const": False
        }
    }
    ```

### 4.2 IStackInspector (运行时内省)
**用途**：获取解释器的性能和位置信息。
-   **`get_instruction_count() -> int`**: 获取已执行的 AST 节点总数。
-   **`get_call_stack_depth() -> int`**: 获取当前递归嵌套深度。
-   **`get_active_intents() -> List[str]`**: 获取当前生效的所有意图装饰器内容。

### 4.3 ILLMProvider (接管 LLM 流量)
**用途**：像 `ai` 模块一样，让自己成为语言的 LLM 引擎。
-   **注册方式**: 在 `setup` 中执行 `capabilities.llm_provider = self`。
-   **必须实现的方法**:
    -   `__call__(sys_prompt: str, user_prompt: str, scene: str) -> str`: 处理请求。
    -   `get_last_call_info() -> Dict[str, Any]`: 供 `idbg` 调用。
    -   `set_retry_hint(hint: str)`: 接收内核的修复建议。

---

## 5. 手把手：从零编写一个 `Logger` 扩展

假设我们要写一个能看到当前意图栈的智能日志模块。

### 第一步：编写 `ibc_modules/smart_log/spec.py`
```python
from core.support.module_spec_builder import SpecBuilder

spec = (SpecBuilder("smart_log")
    .func("info", params=["str"])
    .build())
```

### 第二步：编写 `ibc_modules/smart_log/__init__.py`
```python
from core.runtime.ext.capabilities import ExtensionCapabilities

class SmartLogImpl:
    def __init__(self):
        self._caps = None

    def setup(self, capabilities: ExtensionCapabilities):
        self._caps = capabilities

    def info(self, msg: str):
        # 1. 利用 StackInspector 获取当前意图上下文
        intents = self._caps.stack_inspector.get_active_intents()
        prefix = f"[{' -> '.join(intents)}]" if intents else "[GENERAL]"
        
        # 2. 打印带上下文的日志
        print(f"{prefix} {msg}")

def create_implementation():
    return SmartLogImpl()
```

### 第三步：在 `.ibci` 中使用
```ibc-inter
import smart_log

@ 正在处理用户订单
smart_log.info("开始校验库存") 
# 输出: [正在处理用户订单] 开始校验库存
```

---

## 6. 高级技巧与注意事项

### 6.1 跨语言边界的数据安全
-   **过滤**: 始终在导出数据前检查类型。不要尝试将 Python 的 `Class`、`Module` 或 `Lambda` 直接作为 `dict` 的值返回给 `ibci`。
-   **None 处理**: `ibci` 中的 `None` 对应 Python 的 `None`。

### 6.2 错误处理
在扩展中抛出 `core.types.exception_types.InterpreterError` 可以让错误带有行号信息并被 `ibci` 的 `try...except` 捕获。

### 6.3 单元测试
建议为你的扩展编写专门的测试文件，参考 `tests/test_idbg_core.py`，手动模拟 `ExtensionCapabilities` 注入。

---
*IBC-Inter 团队 - 赋予代码意图，赋予开发者力量。*
