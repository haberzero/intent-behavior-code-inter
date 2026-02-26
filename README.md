# IBC-Inter (Intent-Behavior-Code Interaction)

IBC-Inter 是一种实验性的**意图驱动型混合编程语言**。它旨在将确定性的结构化代码（Python-style）与不确定性的自然语言推理（LLM）深度融合，通过原生的“意图机制”和“AI 容错控制流”解决 LLM 在复杂逻辑编排中的落地难题。

## 🚀 核心特性

- **🧠 意图驱动 (Intent-Driven)**: 使用 `@` 意图注释动态增强上下文，让 AI 真正“读懂”代码意图。
- **🎭 混合执行 (Hybrid Execution)**: 原生支持行为描述行 (`~~...~~`) 和 LLM 函数，像调用普通函数一样驱动 AI。
- **🛡️ AI 容错控制流 (LLM-Except)**: 专为解决 AI 逻辑判断模糊性设计的 `llmexcept` 与 `retry` 机制，实现逻辑的自我修复。
- **🧩 插件化扩展 (Plugin-Ready)**: 零配置的 Python 插件自动嗅探机制，轻松扩展语言能力。
- **🔒 安全沙箱**: 内置文件访问控制与权限管理，确保 AI 行为在受控范围内。

## 📦 快速开始 (初学者友好指南)

### 第一步：获取代码
你可以通过以下任一方式获取本项目：
- **方式 A (推荐)**: 如果你安装了 Git，直接克隆：
  ```bash
  git clone https://github.com/your-repo/ibc-inter.git
  cd ibc-inter
  ```
- **方式 B**: 在 GitHub 页面点击绿色的 **"Code"** 按钮，选择 **"Download ZIP"**。下载后解压并进入文件夹。

### 第二步：安装 Python 与运行依赖
确保你的电脑安装了 **Python 3.10** 或更高版本。然后在终端（Windows 是 PowerShell 或 CMD，Mac 是 Terminal）运行：
```bash
# 安装连接 AI 所需的官方库
pip install openai
```

### 第三步：获取你的 AI API Key (以阿里云百炼为例)
1. 访问 [阿里云百炼平台](https://bailian.console.aliyun.com/)。
2. 登录后，点击左侧菜单的 **“模型广场”**，选择一个模型（如 `qwen-plus` 或 `qwen-turbo`）。
3. 点击 **“API-KEY”** 菜单，创建一个新的 API-KEY 并复制。
4. **记住你的地址**: 阿里云百炼的默认地址（base_url）通常是 `https://dashscope.aliyuncs.com/compatible-mode/v1`。

### 第四步：配置并运行
最简单的方法是直接创建一个 `api_config.json`：
1. 打开 `api_config.json`，把你的信息填进去：
   ```json
   {
       "default_model": {
           "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
           "api_key": "这里填你刚才复制的 API-KEY",
           "model": "qwen-plus"
       }
   }
   ```
2. **运行示例代码**:
   ```bash
   python main.py run examples/01_basics/basic_ai.ibci --config api_config.json
   ```

---

### 调试组件 Mock模式(模拟模式)

如果你暂时没有 API Key，可以使用 IBC-Inter 解释器中内置的Mock块，对代码流进行调试

1. 创建一个 `test.ibci` 文件，粘贴以下内容：
   ```ibc-inter
   import ai
   # 开启模拟模式，不需要真实的 Key
   ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")

   print("正在测试模拟模式...")
   str res = ~~向我打个招呼~~
   print("AI 回复: " + res)

   if ~~MOCK:TRUE 这是一个必中的判断~~:
       print("逻辑分支验证成功！")
   ```
2. 运行它：
   ```bash
   python main.py run test.ibci
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
