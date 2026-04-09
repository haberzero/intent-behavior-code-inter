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

## 项目亮点

### 1. 行为描述语句与llm函数

使用简单易读的语法，在单行内调用llm，这被称为行为描述语句

`@~ ... ~` 会触发一次 LLM 调用。它可以作为表达式使用：

```ibci
str result = @~ 打个招呼 ~
print(result)
# 此时会得到被配置的语言模型的回复
```

定义结构化的、带提示词工程的 AI 函数：

```ibci
llm 翻译(str 文本, str 目标语言) -> str:
__sys__
你是一个翻译专家。
__user__
请将 "$文本" 翻译为 $目标语言。
llmend
```

llm 函数利用 llmend 关键字标记结束定义。

llm函数书写不需要缩进，这是为了阅读以及提示词管理的非歧义/便利性，确保所有非顶格书写的空格都可以正常被作为提示词的一部分被送入ai调用过程。

llm函数的参数传递需要配合 `__to_prompt__` 协议，确保参数能够被正确地转换为提示词中的变量。例如，class str 的 `__to_prompt__` 方法会将字符串保持为原始字符串，作为提示词的一部分；class float 的 `__to_prompt__` 方法会将浮点数转换为相对应的数字字符串，作为提示词的一部分。

与 `__to_prompt__` 协议相关的，还有 `__from_prompt__` 协议，用于将模型返回的字符串转换为类对象；以及 `__llmoutput_hint__` 协议，用于注入并约束模型返回的字符串的格式。

### 2. 意图注释

使用 `@` 意图注释动态增强上下文。意图注释会注入到llm的系统提示词上下文，作为额外的上下文信息。

```ibc-inter
@ 用冷酷的口吻进行回复
str greeting = @~请向我打个招呼~
print(greeting) # 此时输出的招呼语会受到"冷酷"意图的约束
```

### 3. AI 容错控制流 (LLM-Except)

专为解决 AI 逻辑判断模糊性设计的 `llmexcept` 与 `retry` 机制。

```ibc-inter
# 利用内在的提示词注入机制，IBC-Inter会强制要求模型返回 0 或 1
if @~检查 $greeting 是否包含情感词汇~:
    print("AI 违背了设定")
llmexcept:
    print("判断模糊，正在重试...")
    ai.set_retry_hint("请严格返回 1 (包含) 或 0 (不包含)")
    retry
```

如果模型没有遵循指令，没有返回 0 或 1，会触发 llmexcept 异常

ai.set_retry_hint 会增强提示词注入

retry 指令会使 ibci 代码回到 `if @~检查 $greeting 是否包含情感词汇~:` 语句

llmexcept 不仅仅可以保护if语句，事实上，llmexcept可以用来保护所有行为描述语句

llmexcept 机制与 IBC-Inter 的 `__to_prompt__` 以及 `__from_prompt__` 协议紧密相关，详情请见 [IBCI_SPEC.md](IBCI_SPEC.md)

### 4. 行为描述驱动循环

支持根据语义状态持续进行任务迭代。

```ibc-inter
for @~判定 $current_content 内容是否足够热情~:
    current_content = @~优化这段文字，使之更热情：$current_content~
# for 语句会不断调用行为描述语句，直到llm判断 $current_content 内容足够热情
```

### 5. 动态宿主 （重要）

```ibc-inter
# parent.ibci

import host

dict policy = {
    "isolated": true,
    "registry_isolation": true,
    "inherit_variables": false
}

host.run_isolated("child.ibci", policy)
```

上面的语句，会让 IBC-Inter 的整个运行流程从 `child.ibci` 重启。 `child.ibci` 是一个全新的独立 IBC-Inter 实例，会独立进行一次全新的编译以及解释运行。因此，并不要求 `child.ibci` 在主环境启动运行之前存在。动态宿主的机制允许 `child.ibci` 在主环境运行时被动态生成。

这也就意味着，理论上来说，你可以通过书写一个“用来生成IBC-Inter代码的.ibci脚本”，并且实时动态地切换至全新的编译-解释运行的环境。

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

复制`examples/01_getting_started/01_hello_world.ibci`到`test_target_proj`

尝试运行示例代码:

```bash
python main.py run test_target_proj/01_hello_world.ibci
```

## 其它

更多详情请参阅：

- [IBC-Inter语法说明手册](IBCI_SPEC.md) (语法与类型系统)
- [架构原则](docs/ARCHITECTURE_PRINCIPLES.md) (核心设计思路)

***
