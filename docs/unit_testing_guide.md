# IBC-Inter 单元测试指南 (Unit Testing Guide)

本指南旨在说明如何运行和编写 IBC-Inter 项目的单元测试，特别强调了如何利用内核调试器 (Core Debugger) 在测试过程中进行深度追踪。

---

## 1. 测试框架概览

IBC-Inter 采用 Python 标准库 `unittest` 作为基础测试框架。为了更好地支持 IBCI 解释器的特性（如插件加载、LLM 模拟、内核调试），项目引入了 `IBCTestCase` 增强型测试基类。

### 1.1 IBCTestCase 基类

`IBCTestCase` 位于 `tests/ibc_test_case.py`。它封装了以下核心功能：
- **自动化引擎创建**：提供 `create_engine()` 方法，自动根据当前测试的调试配置初始化 `IBCIEngine`。
- **调试状态隔离**：在每个测试用例运行前后自动重置内核调试器状态，确保每个测试用例拥有独立的、干净的调试环境。
- **静默执行接口**：提供 `run_silent()` 方法，专门用于测试“预期会报错”的场景，抑制冗余的错误堆栈输出。
- **配置优先级**：自动处理类级别配置与环境变量配置的合并。

---

## 2. 运行测试

### 2.1 运行所有测试
在项目根目录下运行：
```bash
python -m unittest discover tests
```

### 2.2 运行特定模块的测试
```bash
python -m unittest tests/test_class_system.py
```

---

## 3. 在测试中使用内核调试器 (Core Debugger)

内核调试器允许你在测试运行期间观测词法分析、语法分析、语义检查以及解释器执行的内部细节。

### 3.1 环境变量控制 (推荐方式)

通过设置 `IBC_TEST_CORE_DEBUG` 环境变量，你可以为**任何**现有的测试用例开启调试输出，而无需修改源代码。

**语法格式：** `MODULE:LEVEL,MODULE:LEVEL...` 或标准 JSON 字符串。

**示例：**
```bash
# 查看所有测试的解释器执行细节和 LLM 交互详情
export IBC_TEST_CORE_DEBUG="INTERPRETER:DETAIL,LLM:DATA"
python -m unittest tests/test_llm_integration.py

# 在 Windows PowerShell 中：
$env:IBC_TEST_CORE_DEBUG="INTERPRETER:DETAIL,LLM:DATA"
python -m unittest tests/test_llm_integration.py
```

### 3.2 类属性控制 (静态配置)

如果你正在开发一个新的核心功能，并希望在运行其对应的测试脚本时默认开启某些调试信息，可以在测试类中显式声明：

```python
from tests.ibc_test_case import IBCTestCase

class TestMyFeature(IBCTestCase):
    # 默认开启语义分析基础追踪和解释器详情追踪
    core_debug_config = {
        "SEMANTIC": "BASIC",
        "INTERPRETER": "DETAIL"
    }
    ```python
    def test_logic(self):
        # 这里的 self.engine 将自动携带上述调试配置
        self.engine.run_string("...")
```

---

## 4. 静默测试模式 (Silent Mode)

在编写负面测试（即验证程序是否能正确报错）时，默认的错误输出（如堆栈追踪、编译错误详情）会污染测试控制台。

### 4.1 使用 run_silent

`IBCTestCase` 提供的 `run_silent()` 方法通过底层引擎的 `silent=True` 选项，实现了：
1.  **抑制标准输出**：不再打印“Compilation Errors”或“Runtime Error”横幅。
2.  **异常透传**：直接将异常向上抛出，以便配合 `assertRaises` 进行断言。

**推荐用法：**
```python
def test_division_by_zero(self):
    code = "int x = 1 / 0"
    # 使用 run_silent 确保控制台整洁
    with self.assertRaises(InterpreterError):
        self.run_silent(code)
```

---

## 5. 编写新测试的最佳实践

为了确保测试的可维护性和调试友好性，请遵循以下原则：

1.  **继承 IBCTestCase**：所有涉及解释器运行的测试都应继承自 `IBCTestCase`。
2.  **使用 self.engine**：尽量使用 `self.engine` 或通过 `self.create_engine()` 创建实例，而不是直接实例化 `IBCIEngine`。
3.  **调用 super().setUp()**：如果你覆盖了 `setUp` 方法，请务必在方法开头调用 `super().setUp()` 以确保基础环境正确初始化。
4.  **关注数据流**：当测试失败且原因不明时，优先开启 `LLM:DATA` 或 `INTERPRETER:DATA` 以观察原始 Prompt 和变量赋值。

---

## 5. 常见调试模块建议

| 调试场景 | 推荐配置 |
| :--- | :--- |
| **语法报错定位** | `{"LEXER": "BASIC", "PARSER": "DETAIL"}` |
| **类型检查异常** | `{"SEMANTIC": "DETAIL"}` |
| **逻辑执行流异常** | `{"INTERPRETER": "DETAIL"}` |
| **AI 返回结果不符合预期** | `{"LLM": "DATA"}` |
| **多文件导入失败** | `{"SCHEDULER": "BASIC"}` |
