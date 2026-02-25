# IBC-Inter (Intent-Behavior-Code Interaction)

IBC-Inter 是一种实验性的**意图驱动型混合编程语言**。它旨在将确定性的结构化代码（Python-style）与不确定性的自然语言推理（LLM）深度融合，通过原生的“意图机制”和“AI 容错控制流”解决 LLM 在复杂逻辑编排中的落地难题。

## 🚀 核心特性

- **🧠 意图驱动 (Intent-Driven)**: 使用 `@` 意图注释动态增强上下文，让 AI 真正“读懂”代码意图。
- **🎭 混合执行 (Hybrid Execution)**: 原生支持行为描述行 (`~~...~~`) 和 LLM 函数，像调用普通函数一样驱动 AI。
- **🛡️ AI 容错控制流 (LLM-Except)**: 专为解决 AI 逻辑判断模糊性设计的 `llmexcept` 与 `retry` 机制，实现逻辑的自我修复。
- **🧩 插件化扩展 (Plugin-Ready)**: 零配置的 Python 插件自动嗅探机制，轻松扩展语言能力。
- **🔒 安全沙箱**: 内置文件访问控制与权限管理，确保 AI 行为在受控范围内。

## 📦 快速开始

### 1. 准备环境
确保已安装 `openai` (用于连接 LLM) 和其他 Python 基础依赖：
```bash
pip install openai
```

### 2. 配置 LLM 服务
IBC-Inter 需要一个 API 配置文件来连接 LLM。你可以参考根目录下的 `api_config.json`：
```json
{
    "default_model": {
        "base_url": "http://你的API地址/v1",
        "api_key": "你的API密钥",
        "model": "模型名称"
    }
}
```

### 3. 编写并运行你的第一个 IBCI 程序
创建一个名为 `hello.ibci` 的文件：
```ibc-inter
import ai
# 自动使用 --config 注入的 url, key, model 变量进行初始化
ai.set_config(url, key, model)

@ 你是一个幽默的助手
str greeting = ~~请向我打个招呼~~
print(greeting)

if ~~判断 $greeting 是否包含笑话~~:
    print("AI 表现得很幽默！")
else:
    print("AI 似乎比较严肃。")
```

运行程序：
```bash
python main.py run hello.ibci --config api_config.json
```

### 4. 核心功能验证
你可以直接运行内置的验证脚本来确认环境是否就绪：
```bash
python main.py run verify.ibci --config api_config.json
```

## 💡 代码特性示例

### 1. 意图驱动 (Intent-Driven)
使用 `@` 意图注释动态增强上下文，让 AI 真正“读懂”代码意图。
```ibc-inter
@ 你现在是一个冷酷的逻辑专家
str greeting = ~~请向我打个招呼~~
print(greeting) # 此时输出的招呼语会受到“冷酷”意图的约束
```

### 2. AI 容错控制流 (LLM-Except)
专为解决 AI 逻辑判断模糊性设计的 `llmexcept` 与 `retry` 机制。
```ibc-inter
if ~~检查 $greeting 是否包含情感词汇~~:
    print("AI 违背了设定")
llmexcept:
    print("判断模糊，正在重试...")
    ai.set_retry_hint("请严格返回 1 (包含) 或 0 (不包含)")
    retry
```

### 3. 意图驱动循环 (Intent-Driven Loop)
支持根据语义状态持续进行任务迭代。
```ibc-inter
for ~~判定当前内容是否足够热情？如果不够请返回 1 继续优化~~:
    current_content = ~~优化这段文字：$current_content~~
    if ~~判断内容是否已包含笑脸表情~~:
        break
```

### 4. 插件化扩展 (Plugin-Ready)
零配置的 Python 插件自动嗅探机制：
1. 在项目根目录下创建 `plugins/` 文件夹。
2. 将 Python 脚本（如 `tools.py`）放入其中。
3. 在 `.ibci` 代码中直接使用 `import tools` 即可调用。

## 🛠️ 架构概览

IBC-Inter 采用高度解耦的编译器架构：
- **Scheduler ([scheduler.py](file:///c:/myself/proj/intent-behavior-code-inter/utils/scheduler.py))**: 负责多文件编译调度、依赖图构建及缓存管理。
- **Interpreter ([interpreter.py](file:///c:/myself/proj/intent-behavior-code-inter/utils/interpreter/interpreter.py))**: 核心执行引擎，采用 Visitor 模式遍历 AST，并支持意图栈管理。
- **LLM Executor ([llm_executor.py](file:///c:/myself/proj/intent-behavior-code-inter/utils/interpreter/llm_executor.py))**: 处理提示词构建、参数插值和结果的严格校验（BRANCH/LOOP 场景）。
- **Evaluator ([evaluator.py](file:///c:/myself/proj/intent-behavior-code-inter/utils/interpreter/evaluator.py))**: 处理所有算术、逻辑及类型转换运算。
- **HostInterface ([host_interface.py](file:///c:/myself/proj/intent-behavior-code-inter/utils/host_interface.py))**: 统一的宿主互操作层，支持 Python 插件与标准库元数据管理。

更多详情请参阅：
- [使用指南](docs/prototype_usage_guide.md)
- [语言规范](docs/ibc_inter_language_spec.md)
- [架构设计指南](docs/architecture_design_guide.md)

## 📄 开源协议
MIT License
