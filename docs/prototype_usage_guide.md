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

## 2. 全局内置函数与类型

在 IBC-Inter 中，以下函数和类型无需导入即可直接使用。

### 2.1 基础函数
- `print(*args)`：输出内容到控制台或回调接口。
- `len(container)`：返回 list、dict 或 str 的长度。
- `input(prompt)`：接收用户输入。

### 2.2 类型转换与构造
- `int(value)`：转换为整数。
- `float(value)`：转换为浮点数。
- `str(value)`：转换为字符串。
- `list()`：创建空列表。
- `dict()`：创建空字典。
- `bool(value)`：转换为布尔值。

## 3. 内置第一方组件 (需显式导入)

### 3.1 ai (LLM 配置与管理)
用于控制语言模型的核心行为，支持场景化（Scene）配置。
- `ai.set_config(url, key, model)`：配置 API 访问参数。使用 "TESTONLY" 可进入模拟模式。
- `ai.set_retry(count)`：设置 LLM 调用失败后的重试次数。
- `ai.set_retry_hint(hint)`：设置维修提示词，在下一次 `retry` 时注入，引导 LLM 修正行为。
- `ai.set_branch_prompt(prompt)`：设置 `if` 分支场景下的系统提示词。
- `ai.set_loop_prompt(prompt)`：设置 `while/for` 循环场景下的系统提示词。
- `ai.set_scene_config(scene, config_dict)`：专家模式配置，如 `ai.set_scene_config("branch", {"prompt": "..."})`。

### 3.2 json (数据解析)
- `json.parse(string)`：将 JSON 字符串转换为 dict 或 list。
- `json.stringify(object)`：将对象序列化为 JSON 字符串。

### 3.3 file (受限文件访问)
- `file.read(path)`：读取文件内容。
- `file.write(path, content)`：写入文件。
- `file.exists(path)`：检查文件是否存在。
*注意：受沙箱权限限制，默认仅允许访问工作目录内文件。*

### 3.4 sys (系统与权限)
- `sys.request_external_access()`：请求开启跨目录访问权限。
- `sys.is_sandboxed()`：检查当前是否处于沙箱限制中。

### 3.5 math & time (基础工具)
- `math`：映射 Python 原生 math 库的所有数学函数。
- `time.now()`：获取当前时间戳。
- `time.sleep(seconds)`：阻塞执行。

## 4. 快速原型开发 (TESTONLY 模式)

为了支持脱离真实 API 的快速迭代，IBC-Inter 提供了强大的 `TESTONLY` 模拟模式。

### 4.1 开启模拟
```ibc-inter
import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
```

### 4.2 模拟指令 (MOCK Directives)
在行为描述行 (`~~...~~`) 中嵌入以下特定指令，可以精确操控模拟块的行为：
- `MOCK:FAIL`: 强制模拟 LLM 返回模糊结果，触发 `llmexcept` 流程。
- `MOCK:TRUE` / `MOCK:1`: 在逻辑场景下强制模拟返回 `1`。
- `MOCK:FALSE` / `MOCK:0`: 在逻辑场景下强制模拟返回 `0`。
- `MOCK:REPAIR`: 模拟“维修-重试”闭环。第一次调用触发失败，设置 `retry_hint` 后执行 `retry` 将返回成功。

## 5. 建议示例

下面的示例展示了如何读取外部配置文件（JSON 格式），提取关键字段，并通过 LLM 函数进行智能化处理。

```ibc-inter
import ai
import json
import file

# 环境配置：从本地安全配置文件读取，严禁在代码中硬编码敏感信息
# 假设 secrets.json 内容为: {"url": "https://api.example.com", "key": "sk-xxx", "model": "gpt-4"}
try:
    str secrets_raw = file.read("secrets.json")
    dict secrets = (dict)json.parse(secrets_raw)
    ai.set_config((str)secrets["url"], (str)secrets["key"], (str)secrets["model"])
except str as e:
    print("安全配置加载失败，请检查 secrets.json 文件: " + e)

ai.set_retry(3)

# 1. 定义 LLM 逻辑：总结用户意图。实际代码中建议llm函数单独放置或放在代码文件最末尾
llm 总结报告(str 用户名, str 内容):
__sys__
你是一个专业的数据分析助理。
__user__
请为用户 $__用户名__ 总结以下报告内容的核心要点：
$__内容__
llmend

# 2. 定义处理流程
func 执行自动化分析(str config_path):
    try:
        # 读取配置文件
        # 假设 config.json 内容为: {"user": "张三", "data_path": "report.txt"}
        str config_raw = file.read(config_path)
        dict config = (dict)json.parse(config_raw)
        
        str user_name = (str)config["user"]
        str data_path = (str)config["data_path"]
        
        # 读取报告正文
        str report_content = file.read(data_path)
        
        # 调用 LLM 函数进行总结
        @ 总结要求：简洁明了，不超过 100 字
        str summary = 总结报告(user_name, report_content)
        
        # 使用行为描述行进行后续处理
        if ~~MOCK:REPAIR 检查分析内容 $summary 是否包含敏感词~~:
            print("分析完成：")
            print(summary)
        llmexcept:
            print("LLM 判断不明确，正在尝试修复并重试...")
            ai.set_retry_hint("请务必只返回 1 或 0，不要有废话")
            retry
        
    except str as e:
        print("流程执行出错: " + e)

# 执行入口
执行自动化分析("config.json")
```
