# 如何自定义 LLM Provider（供应商、请求/响应、配置格式）

> 面向需要自定义 IBCI 的 LLM 底层（供应商、请求/响应格式、api_config.json 书写
> 格式、思考参数映射）的开发者。解决"在不改语言内核的前提下换掉 LLM 调用实现"的
> 具体问题。前置知识：`docs/subsystems/04_plugin_system.md`（内置模块机制）、
> `docs/architecture/01_principles.md` §3.7（供应商无关中间层）、Python 基础、
> `docs/howto/extend_with_host_binding.md`（宿主绑定）。

## 总览：provider 自定义经宿主绑定统一（F4）

IBCI 的 LLM 调用经 **`llm_provider` 能力** 接入：内核 LLM 执行器每次调用都从能力
注册表读取当前激活的 provider，再调 `provider.call(request)` / `provider.stream(request)`。
内置默认 provider 是 `ibci_modules/ibci_ai/provider_impl.py` 的
`RecommendedProvider`（无自定义时生效）。

**自定义 LLM 底层（正式通道）** = 写一个实现 `LLMProvider` 契约的 Python 类，经
**宿主绑定**声明，并 `ai.set_provider(...)` 注册为激活 provider。无需修改任何内核/内置
文件。

## 三步自定义 provider

### 1. 写 provider 模块

在项目里建一个 Python 模块（如 `my_provider.py`），实现 `LLMProvider` 契约并导出
一个实例：

```python
# my_provider.py
from core.base.llm_protocol.llm_call import LLMCallResult
from core.base.llm_protocol import LLMCallRequest

class MyProvider:
    def call(self, request: LLMCallRequest) -> LLMCallResult:
        # 组装您的供应商请求并解析为供应商无关结果
        return LLMCallResult(content="...")          # content 是最终答案文本

    def stream(self, request):
        yield "增量文本..."                           # 流式增量

    def get_retry(self) -> int:
        return 3                                    # llmexcept 重试次数

    def is_auto_intent_injection_enabled(self) -> bool:
        return True                                  # 自动意图注入开关

    def get_current_call_info(self) -> dict:
        return {}                                    # 最近一次调用诊断

provider = MyProvider()                              # 导出实例供绑定
```

契约方法（签名固定）与职责：

| 方法 | 职责 |
|------|------|
| `call(request) -> LLMCallResult` | 执行一次 LLM 调用并解析为供应商无关结果 |
| `stream(request)` | 流式调用，返回逐步产出 `str` 增量的迭代器 |
| `get_retry() -> int` | 最大 LLM 重试次数（llmexcept 重试循环读取） |
| `is_auto_intent_injection_enabled() -> bool` | 自动意图注入开关（prompt 拼装前读取） |
| `get_current_call_info() -> dict` | 最近一次调用的诊断信息 |

`probe()` 是**可选**方法（供应商感知的能力探测）；不实现时内核按保守策略处理。

### 2. 宿主绑定声明 + 注册

在 IBCI 脚本里绑定 provider 实例并注册：

```ibci
import python "my_provider" as lib:
    bind provider -> any

import ai
ai.set_provider(lib.provider)
```

`ai.set_provider` 校验 provider 具备全部契约方法（缺失即报错，不静默降级），然后
以 HIGH 优先级把它注册为激活的 `llm_provider`——此后内核 LLM 调用走您的实现。

### 3. 验证

1. 全量回归：`conda activate ibci && python -m pytest tests/`——零回归后再提交。
2. 真实 LLM 试用：按 `docs/howto/run_trials.md` 跑一套真实调用，确认新 provider
   的响应解析与探测路径符合预期。
3. 契约自检：provider 类具备全部五个契约方法（缺任一则 `set_provider` 拒绝）。

## 常见修改点

### 换一个 OpenAI 兼容端点

无需自定义 provider——在 `api_config.json` 的 `providers` / `models` 里改端点即可
（内置默认 provider 已按 OpenAI 兼容格式组装 payload）。仅当端点无法以该格式接入
时才自写 provider。

### 调整思考参数映射

`LLMCallRequest` 的 `thinking_mode` 是供应商无关声明（"auto"/"on"/"off"）；各供应商
自身的思考字段由您的 provider 实现映射。内置默认实现面向开发基线（LM Studio + Qwen
非思考模式）固定发送 `enable_thinking=false`；换供应商时在自写 provider 的 `call()` /
`stream()` / `probe()` 里按该供应商字段映射 `thinking_mode`。**不要改动契约层**
（`core.base.llm_protocol`）。

### 改变 api_config.json 书写格式

配置读取经 `ConfigSourceAdapter` 抽象（`core.base.llm_protocol.config`）。默认适配器
`ProjectApiConfigAdapter`（`ibci_modules/ibci_ai/config_source_adapter.py`）识别推荐
schema。想用自己的格式：自写 `ConfigSourceAdapter` 实现并替换默认适配器（整文件替换
`config_source_adapter.py`，保持类名 `ProjectApiConfigAdapter`），或经 F4 provider
接入自定义配置读取。

## 注意事项

- **MOCK 测试模式**：`set_mock_mode()` / `api_config.json` 的 `defaults.mock` 显式进入；
  MOCK 指令语言由 `ibci_modules/ibci_ai/mock_scenario.py` 实现（线程安全），自写
  provider 可复用，勿改哨兵常量（位于 `core.base.llm_protocol.llm_call`）。
- **不改胶水**：`core.py` 里 `run_batch` / `stream_call` / `stream_channel` / 意图
  方法依赖内核执行器与 capabilities，误改会破坏 `ai` 模块运行面。
- **`provider_impl.py` 不手动改**：它只是内置默认实现；自定义走宿主绑定 + `set_provider`。
- **能力单一 primary**：`set_provider` 后自定义 provider 为激活 provider；未注册时
  内置默认 provider 生效。二者经优先级单选，不并存双通道。

## 深入指引

- 供应商无关契约全文：`docs/architecture/01_principles.md` §3.7
- 宿主绑定（用户扩展唯一通道）：`docs/howto/extend_with_host_binding.md`
- 内置模块系统：`docs/subsystems/04_plugin_system.md`
- 调试 LLM 调用：`docs/howto/debug_llm_calls.md`
