# IBC-Inter (Intent Behavior Code - Interactive)

**请注意！！当前项目仍然处在实验性示例阶段，请谨慎参考并且不要直接用于生产环境！！**

**Attention!! This repository remains in the EXPERIMENTAL DEMO phase, Please refer with caution and Do not use in production!!**

IBC-Inter 是一种实验性的**意图驱动型混合编程语言**。它旨在将确定性的结构化代码（Python-style）与不确定性的自然语言推理（LLM）深度融合，通过原生的"意图机制"和"AI 容错控制流"解决 LLM 在复杂逻辑编排中的落地难题。

## 核心特性

- **混合执行**: 即时执行的行为描述行 (`@~...~`) ，像书写普通表达式一样调用调用 LLM 
- **LLM函数定义**: 用设计函数的思路设计LLM调用，把LLM的提示词书写为类似函数的形式，允许参数传递
- **提示词协议`__to_prompt__`**: 允许类对象定义自身在LLM调用过程中的表现形式，实现 AI 视角、数据结构与代码逻辑的解耦
- **AI 容错控制流 (LLM-Except)**: 专为解决 AI 逻辑判断模糊性设计的 `llmexcept` 与 `retry` 机制，实现逻辑的自我修复
- **插件化扩展**: 零配置的 Python 插件自动嗅探机制，轻松扩展语言能力。
- **动态宿主**: 允许一段IBC-Inter代码主动开启一个新脚本的独立编译执行且完全不干扰主环境，允许IBC-Inter脚本生成新的IBC-Inter脚本并实时动态地切换至全新的编译-解释运行的环境。

## 快速开始

### 第一步：获取代码

你可以通过以下任一方式获取本项目：

- **方式 A (推荐)**: 如果你安装了 Git，直接克隆：
  ```bash
  git clone https://github.com/haberzero/intent-behavior-code-inter.git
  cd intent-behavior-code-inter
  ```

- **方式 B**: 在 GitHub 页面点击绿色的 **"Code"** 按钮，选择 **"Download ZIP"**。下载后解压并进入文件夹。

### 第二步：安装 Python 与运行依赖

确保你的电脑安装了 **Python 3.10** 或更高版本。然后在终端运行：

```bash
# 安装连接 AI 所需的官方库
pip install openai
```

### 第三步：获取你的 AI API Key (以阿里云百炼为例)

1. 访问 [阿里云百炼平台](https://bailian.console.aliyun.com/)。
2. 登录后，点击左侧菜单的 **"模型广场"**，选择一个模型（如 `qwen3-30b-a3b`）。
3. 点击 **"API-KEY"** 菜单，创建一个新的 API-KEY 并复制。
4. **记住你的地址**: 阿里云百炼的默认base_url通常是 `https://dashscope.aliyuncs.com/compatible-mode/v1`。

### 第四步：配置并运行示例

创建一个独立的目标文件夹，例如`test_target_proj`

在目标文件夹下创建一个 `api_config.json`，填写信息：

```json
{
    "default_model": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": "这里填你刚才复制的 API-KEY",
        "model": "qwen3-30b-a3b"
    }
}
```

复制`examples\01_quick_start\01_hello_ai.ibci`到`test_target_proj`

尝试运行示例代码:

```bash
python main.py run test_target_proj/01_hello_ai.ibci
```

## 代码特性示例

### 1. 意图驱动 (Intent-Driven)

使用 `@` 意图注释动态增强上下文。

```ibc-inter
@ 用冷酷的口吻进行回复
str greeting = @~请向我打个招呼~
print(greeting) # 此时输出的招呼语会受到"冷酷"意图的约束
```

<!-- 在这一句之前首先要解释ibc-inter实现if判断的机制，要说清楚怎么书写if和for循环· -->
### 2. AI 容错控制流 (LLM-Except)

专为解决 AI 逻辑判断模糊性设计的 `llmexcept` 与 `retry` 机制。

```ibc-inter
if @~检查 $greeting 是否包含情感词汇~:
    print("AI 违背了设定")
llmexcept:
    print("判断模糊，正在重试...")
    ai.set_retry_hint("请严格返回 1 (包含) 或 0 (不包含)")
    retry
```

<!-- 示例有问题，判断内容这一句完全无意义无价值，没有变量引用，根本不会被送入llm -->
### 3. 意图驱动循环 (Intent-Driven Loop)

支持根据语义状态持续进行任务迭代。

```ibc-inter
for @~判定当前内容是否足够热情？如果不够请返回 1 继续优化~:
    current_content = @~优化这段文字：$current_content~
    if @~判断内容是否已包含笑脸表情~:
        break
```

<!-- 这个不要放在readme.md，应该单独书写一个说明书 -->
### 4. 插件化扩展 (Plugin-Ready)

零配置的 Python 插件自动嗅探机制：

1. 在项目根目录下创建 `plugins/` 文件夹。
2. 将 Python 脚本（如 `tools.py`）放入其中。
3. 在 `.ibci` 代码中直接使用 `import tools` 即可调用。

<!-- 后面还要展示一些项目场景，明天给公司写一个循环迭代分析示波器代码的脚本，用那个脚本做advanced演示 -->

## 其它

更多详情请参阅：

- [IBC-Inter语法说明手册](docs/IBC-Inter语法说明手册.md) (语法与类型系统)
- [架构原则](docs/ARCHITECTURE_PRINCIPLES.md) (核心设计思路)

***
