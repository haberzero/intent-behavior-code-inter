# IBC-Inter 官方示例集 (Examples)

欢迎来到 IBC-Inter 的官方示例目录。这里的代码展示了 IBCI 语言的核心特性，分为三个主要部分：

1. `01_quick_start/`: 快速入门，包括基本的 AI 意图调用、标准库使用、以及意图驱动的控制流。
2. `02_advanced_ai/`: 高级 AI 模式，包括意图的叠加与覆盖 (Intent Stacking)、角色扮演、以及强制结构化输出。
3. `03_engineering/`: 工程化特性，包括配置加载与 Mock 测试、`llmexcept` 异常恢复机制、交互式调试 (`idbg`)、插件开发，以及动态宿主全隔离运行 (`DynamicHost`)。

## 运行示例

在运行示例前，请注意每个目录下都提供了一个 `api_config.json` 文件。
默认情况下，这些配置被设置为指向本地的 Mock LLM 服务 (`http://127.0.0.1:12234`)。
您可以将其修改为真实的 OpenAI 兼容 API：

```json
{
    "default_model": {
        "base_url": "https://api.openai.com/v1",
        "api_key": "sk-your-real-api-key",
        "model": "gpt-4o"
    }
}
```

运行方式（在项目根目录执行）：
```bash
python main.py run examples/01_quick_start/01_hello_ai.ibci
```
