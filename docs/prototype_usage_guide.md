# IBC-Inter 原型机使用指南

本文档旨在描述 IBC-Inter（Interactive/Interpreted Intent Behavior Code）语言原型机现阶段的核心能力、内置组件以及具体使用方法。

## 1. 核心语言特性

### 1.1 意图驱动编程
- **意图注释 (`@`)**：通过在代码行上方添加 `@ 意图描述`，动态增强后续 LLM 调用（LLM 函数或行为描述行）的系统提示词。
- **行为描述行 (`~~...~~`)**：使用双波浪号包裹自然语言，直接触发即时的 LLM 推理。支持插值变量，如 `~~分析 $data 的趋势~~`。

### 1.2 混合执行模型
- **传统函数 (`func`)**：支持强类型的结构化逻辑编写。
- **LLM 函数 (`llm`)**：专门用于自然语言处理任务，支持 `__sys__` 和 `__user__` 分段提示词。
- **确定性 AI 容错 (`llmexcept`)**：专门用于处理 LLM 在 `if/while/for` 条件判断中的不确定性。当 LLM 返回模糊结果（非 0/1）时，自动触发该块。支持冒泡搜索。
- **重试指令 (`retry`)**：在 `llmexcept` 块中使用，可立即让当前的控制流节点重新发起 LLM 请求。
- **异常处理 (`try-except-finally`)**：支持对运行时错误（如文件 IO 错误）进行捕获和恢复。

## 2. 运行与工程化工具

### 2.1 命令行入口 (`main.py`)
IBC-Inter 提供了一个统一的命令行工具来管理执行与检查：

- **运行代码**:
  ```bash
  python main.py run entry.ibci
  ```
  *注意：默认会将 `entry.ibci` 所在的目录作为项目根目录 (root)，并自动加载该目录下的插件。*

- **静态检查**:
  ```bash
  python main.py check entry.ibci
  ```

- **常用参数**:
  - `--config path/to/config.json`: 注入 LLM 配置（url, key, model）。
  - `--plugin path/to/plugin.py`: 手动加载额外的 Python 插件。
  - `--var key=value`: 注入全局变量。
  - `--no-sniff`: 关闭自动嗅探 `plugins/` 目录的功能。

### 2.2 自动插件嗅探机制
IBC-Inter 支持“约定优于配置”的插件扩展：
1. 在项目根目录下创建 `plugins/` 文件夹。
2. 将 Python 脚本（如 `tools.py`）放入其中。
3. 在 `.ibci` 代码中直接使用 `import tools` 即可调用其成员。
4. **高级扩展**: 如果 Python 脚本包含 `def setup(engine):` 函数，它将被优先调用以进行自定义注册。

## 3. 全局内置函数与类型

在 IBC-Inter 中，以下函数和类型无需导入即可直接使用。

### 3.1 基础函数
- `print(*args)`：输出内容到控制台。
- `len(container)`：返回 list、dict 或 str 的长度。
- `input(prompt)`：接收用户输入。

### 3.2 类型转换与构造
- `int(value)`, `float(value)`, `str(value)`, `bool(value)`
- `list()`, `dict()`

## 4. 内置第一方组件 (需显式导入)

### 4.1 ai (LLM 配置与管理)
- `ai.set_config(url, key, model)`：配置 API 访问参数。
- `ai.set_retry(count)`：设置 LLM 重试次数。
- `ai.set_retry_hint(hint)`：设置维修提示词。

### 4.2 json, file, sys, math, time
- `json.parse(s)`, `json.stringify(obj)`
- `file.read(path)`, `file.write(path, content)`, `file.exists(path)`
- `sys.request_external_access()`, `sys.is_sandboxed()`
- `math.*` (映射 Python math 库)
- `time.now()`, `time.sleep(s)`

## 5. 快速原型开发 (TESTONLY 模式)

开启模拟模式以进行脱机测试：
```ibc-inter
import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")

if ~~MOCK:FAIL 执行可能失败的任务~~:
    print("Success")
llmexcept:
    print("Caught simulated failure")
    ai.set_retry_hint("Please try again with MOCK:TRUE")
    retry
```

## 6. 完整示例项目结构

```text
my_project/
├── main.ibci          # 入口文件
├── lib.ibci           # IBCI 库文件
├── plugins/           # 自动嗅探插件目录
│   └── helper.py      # Python 扩展
└── data/              # 数据目录
    └── input.json
```

运行方式：`python main.py run my_project/main.ibci`
