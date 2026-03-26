# IBC-Inter LLM 配置与 Mock 示例

本目录展示了 IBC-Inter 引擎中关于 LLM 配置的多种实践方案，以及如何利用内置的 Mock 机制进行高效调试。

## 1. 配置文件说明 (`api_config.json`)
建议的配置文件格式如下：
```json
{
    "url": "API 基础地址",
    "key": "API 密钥",
    "model": "模型名称"
}
```

## 2. 配置方案演示

### 方案 A：命令行注入 (推荐)
- **文件**: `01_cli_config.ibci`
- **运行**: `python main.py run examples/05_llm_config/01_cli_config.ibci --config examples/05_llm_config/api_config.json`
- **优点**: 敏感信息不进入代码，支持环境隔离。

### 方案 B：显式代码读取
- **文件**: `02_file_config.ibci`
- **运行**: `python main.py run examples/05_llm_config/02_file_config.ibci`
- **优点**: 流程清晰，不依赖外部命令行参数。

### 方案 C：硬编码配置 (不推荐)
- **文件**: `03_hardcoded_config.ibci`
- **运行**: `python main.py run examples/05_llm_config/03_hardcoded_config.ibci`
- **优点**: 极其快速的单文件测试。

## 3. 高级 Mock 功能说明
IBC-Inter 专门为 LLM 交互设计了“魔法指令”，在 `ai.set_config("TESTONLY", ...)` 模式下生效：

| 指令前缀 | 效果描述 |
| :--- | :--- |
| `MOCK:TRUE` | 强制分支/循环判定为 **真 (1)** |
| `MOCK:FALSE` | 强制分支/循环判定为 **假 (0)** |
| `MOCK:FAIL` | 强制触发 `llmexcept` 块 (返回无法解析的模糊结果) |
| `MOCK:REPAIR` | 初始判定为模糊，若存在 `retry_hint` 则在 `retry` 后判定为真 |

**调试联动方法：**
- `ai.set_retry(n)`: 设置 AI 判定的重试上限。
- `ai.set_retry_hint(msg)`: 在重试时注入额外的“维修提示词”，用于修正 AI 的判定逻辑。
- `llmexcept` + `retry`: 语言原生的错误恢复流。
