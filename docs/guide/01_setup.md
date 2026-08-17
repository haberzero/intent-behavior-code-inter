# 01 · 配置 LLM 提供者

> 本章是 IBCI 入门教程的第一章。面向首次使用 IBCI 的开发者。覆盖 LLM 提供者配置、API 密钥获取、模型路由设置与连接验证。

## 你将会学到

- 创建和填写 `api_config.json`
- 配置默认模型与命名模型路由
- 验证 API 连接可用性
- 调整超时与重试参数

## api_config.json 的结构

IBCI 的配置加载是**显式动作**：脚本在入口调用 `ai.load_project_config()`，引擎即加载项目根目录（`project_root`）下的 `api_config.json`。配置是原生一等机制，无需脚本手动 `file.read/json.parse`。引擎启动不自动加载配置，须显式调用 `ai.load_project_config()`。

**project_root 的确定**：`main.py run` 时，未显式 `--root` 则引擎自动从入口文件
所在目录**向上**查找项目标志（`ibci_modules/`、`plugins/`、`.ibci/`、`ibci.json`
等），命中即以其为 project_root；未命中则用入口文件所在目录。故：

- 独立项目目录（推荐，README 的 `test_target_proj` 方式）：目录内放
  `api_config.json`，脚本内 `ai.load_project_config()` 即加载。
- 在仓库内直接运行 `examples/`（仓库含 `ibci_modules/` 标志）：project_root 被
  探测为仓库根，`api_config.json` 须放仓库根，或用 `--root <example_dir>` 显式
  指定为示例目录。

最简配置--仅声明默认模型：

```json
{
    "default_model": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key": "sk-xxxxxxxxxxxxxxxxxxxxxxxx",
        "model": "qwen3-30b-a3b"
    }
}
```

完备配置--`providers`（连接层）+ `models`（命名模型）+ `defaults`（全局默认）+ `default_model`（默认引用）：

```json
{
    "defaults": {
        "timeout": 30.0,
        "retry": 3,
        "mock": false
    },
    "providers": {
        "dashscope": {
            "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            "api_key": "{env:DASHSCOPE_API_KEY}"
        }
    },
    "models": {
        "default": { "provider": "dashscope", "model": "qwen3-30b-a3b", "reasoning": false }
    },
    "default_model": "default"
}
```

字段说明：
- `providers`：连接层，声明 `base_url` + `api_key`（支持 `{env:VAR}` 环境变量引用）。
- `models`：命名模型，引用 `provider` + 模型名 + 每模型参数（`timeout`/`reasoning`）。
- `defaults`：全局默认（`timeout`/`retry`/`mock`/`auto_intent_injection`）。
- `default_model`：默认模型引用（字符串指向 `models` 的键，或对象形态直接声明）。

`api_key` 支持 `{env:VAR}` 引用环境变量，避免硬编码密钥。`reasoning:false` 声明非思考模型（跳过 `probe_model`，直接按标准指令模型处理）。`mock:true` 显式进入 MOCK 模式。

> **格式可插拔**：上述 schema 是 IBCI 默认配置源适配器（`ProjectApiConfigAdapter`，
> 供应商无关逻辑映射到 `core.base.llm_protocol`）识别的推荐写法。需要自定义
> `api_config.json` 书写格式（字段名 / 组织结构 / 环境变量解析规则）时，可实现
> `ConfigSourceAdapter`（`core.base.llm_protocol.config`）并替换默认适配器；嵌套在
> `ai.load_project_config()` 内的默认行为与文件格式本身都可被自定义实现覆盖。

## 获取 API 密钥

以阿里云百炼为例：

1. 访问 [阿里云百炼平台](https://bailian.console.aliyun.com/) 并登录。
2. 在左侧菜单进入 **"模型广场"**，选择一个模型。
3. 在 **"API-KEY"** 菜单中创建新密钥并复制。
4. 阿里云百炼的 `base_url` 通常为 `https://dashscope.aliyuncs.com/compatible-mode/v1`。

其他 LLM 提供者的配置方式相同--只需替换 `base_url`、`api_key` 和 `model` 三个字段即可。IBCI 兼容 OpenAI 兼容 API 协议。

## 命名模型路由

当项目需要多个不同模型（例如云端模型 + 本地模型）时，在 `models` 段声明命名模型，经 `@NAME~` 语法路由：

```json
{
    "providers": {
        "dashscope": { "base_url": "...", "api_key": "..." },
        "ollama":    { "base_url": "http://localhost:11434/v1", "api_key": "ollama" }
    },
    "models": {
        "default": { "provider": "dashscope", "model": "qwen3-30b-a3b" },
        "local":   { "provider": "ollama", "model": "qwen3-8b" }
    },
    "default_model": "default"
}
```

每个命名模型引用一个 `provider`（继承连接信息）+ 声明 `model` 名。模型名区分大小写--`local` 和 `Local` 是不同的路由。

有关行为表达式中使用命名模型的语法，见 `docs/syntax/07_behavior_expressions.md §7.5`。

## 验证连接

脚本入口显式加载 `api_config.json`，再经 `ai.has_api_key()` 检查是否已配置：

```ibci
import ai

ai.load_project_config()          # 显式加载 project_root/api_config.json（不存在则 no-op）
if not ai.has_api_key():
    print("未检测到 api_config.json，切换至 MOCK 模式。")
    ai.set_mock_mode()
```

`ai.has_api_key()` 在已配置（含 MOCK 模式）时返回 `True`。无配置时脚本可显式 `ai.set_mock_mode()` 进入 MOCK 模式（开箱即跑）。

发起一次真实的模型探测调用：

```ibci
str status = ai.probe_model()
print(status)   # STANDARD_MODEL / REASONING_MODEL / PROBE_FAILED_FALLBACK_REASONING
```

`ai.probe_model()` 发起一次轻量级真实调用，返回模型能力状态字符串（MOCK 模式返回 `MOCK_PROBE_SUCCESS`）。配置中声明 `reasoning:false` 可跳过探测，直接按标准指令模型处理。

## 超时与重试配置

超时与重试可在 `api_config.json` 的 `defaults` 段统一声明，或在单个 `models` 条目覆盖：

```json
{
    "defaults": { "timeout": 30.0, "retry": 3 },
    "models": {
        "default": { "provider": "...", "model": "...", "timeout": 60.0 }
    }
}
```

也可在代码中经 `ai.set_timeout(seconds)` / `ai.set_retry(count)` 动态调整。`ai.set_timeout()` 控制单次 HTTP 请求超时上限；`ai.set_retry()` 控制 `llmexcept`/`llmretry` 保护块的最大重试次数。

## 你现在能做什么

你已完成 LLM 提供者的配置，模型连接就绪。接下来可以编写第一个行为表达式调用，让 LLM 真正工作起来。

**下一步**：[02 · 第一个 @~ 调用][]--开始编写第一个行为表达式调用。

[02 · 第一个 @~ 调用]: ./02_first_call.md
