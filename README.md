# IBC-Inter (Intent Behavior Code - Interactive)

**请注意！！当前项目仍然处在实验性示例阶段，请谨慎参考并且不要直接用于生产环境！！**

**Attention!! This repository remains in the EXPERIMENTAL DEMO phase, Please refer with caution and Do not use in production!!**

IBC-Inter 是一种实验性的**意图驱动型混合编程语言**。它旨在将确定性的结构化代码（Python-style）与不确定性的自然语言推理（LLM）深度融合，通过原生的"意图机制"和"AI 容错控制流"解决 LLM 在复杂逻辑编排中的落地难题。

## 核心特性

- **混合执行**: 即时执行的行为描述行 (`@~...~`) ，像书写普通表达式一样调用调用 LLM 
- **LLM可调用类**: 用设计类的思路设计 LLM 调用，把提示词书写为 `__llm_call__` 装配配置，支持参数化、意图改写与重试策略
- **提示词协议`__to_prompt__`**: 允许类对象定义自身在LLM调用过程中的表现形式，实现 AI 视角、数据结构与代码逻辑的解耦
- **AI 容错控制流 (LLM-Except)**: 专为解决 AI 逻辑判断模糊性设计的 `llmexcept` 与 `retry` 机制，实现逻辑的自我修复
- **宿主绑定扩展**: 在 .ibci 内用 `import python "..." as lib: bind ...` 显式绑定任意 Python 模块/类/函数，声明式扩展语言能力。
- **动态宿主**: 允许一段IBC-Inter代码主动开启一个新脚本的独立编译执行且完全不干扰主环境，允许IBC-Inter脚本生成新的IBC-Inter脚本并实时动态地切换至全新的编译-解释运行的环境。

## 项目亮点

### 1. 行为描述语句与 LLM 可调用类

使用简单易读的语法，在单行内调用 LLM，这被称为行为描述语句

`@~ ... ~` 会触发一次 LLM 调用。它可以作为表达式使用：

```ibci
str result = @~ 打个招呼 ~
print(result)
# 此时会得到被配置的语言模型的回复
```

需要复用带提示词工程的 LLM 调用时，用 **LLM 可调用类**（实现 `__llm_call__` 协议）：

```ibci
class 翻译:
    func __llm_call__(self, str 文本, str 目标语言) -> dict:
        return {
            "user_prompt": "请将 \"" + str(文本) + "\" 翻译为 " + str(目标语言) + "。",
            "prompt_slots": [{"kind": "user_sys", "text": "你是一个专业翻译，直接输出翻译结果。"}],
            "expected_type": "str"
        }

翻译 t = 翻译()
str result = t("你好", "英语")
print(result)
```

实例直接调用 `t(args)` 即触发一次 LLM 调用（经统一装配入口，含 `__intent__` 改写与 `__retry__` 重试策略）。完整契约见 `docs/syntax/08_llm_callable.md`。

提示词协议族：`__to_prompt__` 定义类对象在 LLM 调用中的表现形式（如 class str 保持原字符串、class float 转数字字符串）；`__from_prompt__` 将模型返回字符串转换为类对象；`__outputhint_prompt__` 注入并约束模型返回的字符串格式；`__payload_prompt__`/`__validate_prompt__` 提供结构化载荷与输出校验。

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

llmexcept 机制与 IBC-Inter 的 `__to_prompt__` 以及 `__from_prompt__` 协议紧密相关，详情请见 [IBCI 语法手册](docs/SYNTAX_REFERENCE.md)

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

import ihost

dict policy = {
    "isolated": True,
    "registry_isolation": True,
    "inherit_variables": False
}

ihost.run_isolated("child.ibci", policy)
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

使用 Python 标准库 `venv` 创建独立虚拟环境并安装全部依赖（依赖分组与完整步骤见 `docs/guide/00_environment.md`）：

```bash
# 从项目根目录
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
source .venv/bin/activate   # Windows: .venv\Scripts\activate
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
        "model": "qwen3-30b-a3b",
        "reasoning": false
    }
}
```

> 配置支持 `providers`/`models`/`defaults` 分层、`{env:VAR}` 环境变量引用、`mock:true` 显式 MOCK 模式等。完整 schema 见 `docs/guide/01_setup.md`。

复制`examples/01_getting_started/01_hello_world.ibci`到`test_target_proj`

尝试运行示例代码:

```bash
python main.py run test_target_proj/01_hello_world.ibci
```

*注意！！！ 现阶段不推荐使用任何思考模型接入 IBC-Inter，思考模型在当前 IBCI 版本的提示词约束下，无法合理工作并收敛思考结论，容易陷入思考死循环。特别是本地小尺寸的思考模型，更容易陷入无穷无尽的“等一等，我应该更深入思考”之类的反思中。请务必使用非思考模式。

## 本地 LLM 快速开始（真实 LLM 驱动）

除上述云端 API 外，IBCI 支持本地 LLM 服务（Ollama / LM Studio / vLLM 等 OpenAI 兼容端点）。

1. 起一个 OpenAI 兼容的本地端点（如 LM Studio 打开 Server，默认 `http://localhost:1234/v1`）。
2. 在目标文件夹下创建 `api_config.json`：

```json
{
    "providers": {
        "local": { "base_url": "http://localhost:1234/v1", "api_key": "lm-studio" }
    },
    "models": {
        "default": { "provider": "local", "model": "qwen3.6-35b-a3b", "reasoning": false }
    },
    "default_model": "default"
}
```

3. 运行示例（脚本内 `ai.load_project_config()` 显式加载配置；配置加载为显式动作，引擎不再自动加载）：

```bash
python main.py run test_target_proj/01_hello_world.ibci
```

> `reasoning:false` 声明非思考模型（跳过 probe，直接标准模式），防反思死循环。
> 完整配置 schema 见 `docs/guide/01_setup.md`。

## 进一步阅读

更多详情请参阅：

- [入门指南](GETTING_STARTED.md)（**新加入者先读**：安装与环境准备）
- [文档中心导航与治理](docs/README.md)（**新加入者先读**：目录结构、阅读路径、治理纪律）
- [IBC-Inter 语法手册](docs/SYNTAX_REFERENCE.md) (语法与类型系统的完整参考，含诊断码参考 `docs/syntax/15_diagnostics.md`)
- [架构原则](docs/ARCHITECTURE.md) (核心设计思路，含观测体系 `docs/architecture/09_observability.md`)
- [子系统设计](docs/SUBSYSTEM_DESIGN.md)（意图 / 文件容器 / 可调用 / 模块系统 / 协程内部设计）
- [操作指南](docs/howto/)（按问题查阅：调试 LLM 调用、宿主绑定扩展）
- [已知限制](docs/KNOWN_LIMITS.md) (当前版本的语言级约束)

### 运行测试

```bash
python -m pytest tests/
```

测试基线以当次 pytest 输出为准。

***
