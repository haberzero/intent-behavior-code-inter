# IBC-Inter (Intent-Behavior-Code Interaction)

IBC-Inter 是一种实验性的**意图驱动型混合编程语言**。它旨在将确定性的结构化代码（Python-style）与不确定性的自然语言推理（LLM）深度融合，通过原生的“意图机制”和“AI 容错控制流”解决 LLM 在复杂逻辑编排中的落地难题。

## 🚀 核心特性

- **🧠 意图驱动 (Intent-Driven)**: 使用 `@` 意图注释动态增强上下文，让 AI 真正“读懂”代码意图。
- **🎭 混合执行 (Hybrid Execution)**: 原生支持行为描述行 (`~~...~~`) 和 LLM 函数，像调用普通函数一样驱动 AI。
- **🛡️ AI 容错控制流 (LLM-Except)**: 专为解决 AI 逻辑判断模糊性设计的 `llmexcept` 与 `retry` 机制，实现逻辑的自我修复。
- **🧩 插件化扩展 (Plugin-Ready)**: 零配置的 Python 插件自动嗅探机制，轻松扩展语言能力。
- **🔒 安全沙箱**: 内置文件访问控制与权限管理，确保 AI 行为在受控范围内。

## 📦 快速开始

### 1. 安装依赖
```bash
pip install openai
```

### 2. 运行示例
你可以直接运行 `examples` 目录下的示例：

```bash
# 运行基础 AI 交互示例
python main.py run examples/01_basic_ai.ibci

# 运行带插件的示例
python main.py run examples/03_plugins/main.ibci
```

### 3. 命令行工具
```text
usage: main.py [-h] {run,check} ...

positional arguments:
  {run,check}  Commands
    run        Run an IBCI file
    check      Static check an IBCI project

optional arguments:
  --config     LLM API 配置文件 (json)
  --plugin     加载额外的 Python 插件 (.py)
  --var        注入全局变量 (key=value)
  --no-sniff   禁用 plugins/ 目录自动嗅探
```

## 💡 代码示例

```ibc-inter
import ai

# 1. 意图驱动
@ 你现在是一个冷酷的逻辑专家
str greeting = ~~请向我打个招呼~~
print(greeting)

# 2. AI 容错控制流
if ~~检查 $greeting 是否包含情感词汇~~:
    print("AI 违背了设定")
llmexcept:
    print("判断模糊，正在重试...")
    ai.set_retry_hint("请只返回 1 或 0")
    retry
```

## 🛠️ 架构概览

IBC-Inter 采用高度解耦的编译器架构：
- **Lexer/Parser**: 支持缩进敏感语法与特殊 AI 语法标记。
- **Semantic Analyzer**: 强类型检查与作用域绑定。
- **HostInterface**: 统一的宿主互操作层。
- **IBCIEngine**: 工业级全链路执行引擎。

更多详情请参阅：
- [使用指南](docs/prototype_usage_guide.md)
- [架构设计指南](docs/architecture_design_guide.md)

## 📄 开源协议
MIT License
