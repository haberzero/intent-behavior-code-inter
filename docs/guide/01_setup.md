# 01 · 配置 LLM 提供者

> 本章是 IBCI 入门教程的第一章。面向首次使用 IBCI 的开发者。覆盖 LLM 提供者配置、API 密钥获取、模型路由设置与连接验证。

## 你将会学到

- 创建和填写 `api_config.json`
- 配置默认模型与命名模型路由
- 验证 API 连接可用性
- 调整超时与重试参数

## api_config.json 的结构

IBCI 通过项目根目录下的 `api_config.json` 读取 LLM 提供者配置。文件需放置在 `.ibci` 工程文件的同级目录中。

最简配置——仅声明默认模型：

```json
{
    "default_model": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxx",
        "model": "qwen3-30b-a3b"
    }
}
```

三个字段均为必填：`base_url` 是 LLM 提供者的 API 端点地址，`api_key` 是鉴权密钥，`model` 是要调用的模型名称。

## 获取 API 密钥

以阿里云百炼为例：

1. 访问 [阿里云百炼平台](https://bailian.console.aliyun.com/) 并登录。
2. 在左侧菜单进入 **"模型广场"**，选择一个模型。
3. 在 **"API-KEY"** 菜单中创建新密钥并复制。
4. 阿里云百炼的 `base_url` 通常为 `https://dashscope.aliyuncs.com/compatible-mode/v1`。

其他 LLM 提供者的配置方式相同——只需替换 `base_url`、`api_key` 和 `model` 三个字段即可。IBCI 兼容 OpenAI 兼容 API 协议。

## 命名模型路由

当项目需要多个不同模型（例如文本模型 + 语音识别模型）时，可在 `api_config.json` 中添加 `named_models` 段：

```json
{
    "default_model": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxx",
        "model": "qwen3-30b-a3b"
    },
    "named_models": {
        "WHISPER": {
            "base_url": "https://api.openai.com/v1",
            "api_key": "sk-yyyyyyyyyyyyyyyyyyyyyyyy",
            "model": "whisper-1"
        }
    }
}
```

每个命名模型同样需要 `base_url`、`api_key` 和 `model` 三个字段。模型名称区分大小写——`WHISPER` 和 `whisper` 是不同的路由。

有关行为表达式中使用命名模型的语法，见 `docs/syntax/07_behavior_expressions.md §7.5`。

## 验证连接

IBCI 提供了两个内置探测函数。首先，在代码文件顶部导入 `ai` 模块：

> **import 约束**：`import` 语句必须出现在文件最顶部，任何非 import 语句之前。不允许在函数、类或条件块内部使用 `import`。完整规则见 `docs/syntax/11_modules.md §11.1`。

```ibci
import ai

ai.set_config("https://dashscope.aliyuncs.com/compatible-mode/v1",
              "sk-xxxxxxxxxxxxxxxxxxxxxxxx",
              "qwen3-30b-a3b")
```

检查 API 密钥是否已配置：

```ibci
if ai.has_api_key():
    print("API 密钥已配置")
else:
    print("请先在 api_config.json 或 set_config() 中配置 API 密钥")
```

发起一次真实的模型探测调用：

```ibci
str status = ai.probe_model()
print(status)   # STANDARD_MODEL / REASONING_MODEL / PROBE_FAILED_FALLBACK_REASONING
```

`ai.has_api_key()` 仅检查密钥是否已填入，不发起网络请求。`ai.probe_model()` 发起一次轻量级真实调用，返回模型能力状态字符串（MOCK 模式返回 `MOCK_PROBE_SUCCESS`）。

## 超时与重试配置

IBCI 允许按项目调整 LLM 调用的超时和重试次数：

```ibci
import ai

ai.set_config("https://dashscope.aliyuncs.com/compatible-mode/v1",
              "sk-xxxxxxxxxxxxxxxxxxxxxxxx",
              "qwen3-30b-a3b")
ai.set_timeout(30)    # 单次 LLM 调用超时（秒），默认 30
ai.set_retry(3)       # 失败后最大重试次数，默认 3
```

`ai.set_timeout()` 控制单次 HTTP 请求的超时上限。`ai.set_retry()` 控制 `llmexcept` 或 `llmretry` 保护块中的最大重试次数。

## 你现在能做什么

你已完成 LLM 提供者的配置，模型连接就绪。接下来可以编写第一个行为表达式调用，让 LLM 真正工作起来。

**下一步**：[02 · 第一个 @~ 调用][]——开始编写第一个行为表达式调用。

[02 · 第一个 @~ 调用]: ./02_first_call.md
[syntax-07]: ../syntax/07_behavior_expressions.md
[syntax-11]: ../syntax/11_modules.md
