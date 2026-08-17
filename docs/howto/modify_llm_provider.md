# 如何修改 LLM Provider（自定义底层与供应商）

> 面向需要自定义 IBCI 的 LLM 底层（供应商、请求/响应格式、api_config.json 书写
> 格式、思考参数映射）的开发者。解决"在不改语言内核的前提下换掉 LLM 调用实现"的
> 具体问题。前置知识：`docs/subsystems/04_plugin_system.md`（内置模块机制）、
> `docs/architecture/01_principles.md` §3.7（供应商无关中间层）、Python 基础。

## 修改哪个文件

IBCI 的内置 `ai` 模块由两个文件组成，职责不同、修改权限不同：

| 文件 | 职责 | 是否可改 |
|------|------|----------|
| `ibci_modules/ibci_ai/provider_impl.py` | **推荐 provider**：纯 provider 逻辑（请求组装 / 响应解析 / 思考抑制 / 探测），实现 `LLMProvider` 契约 | **可改**（本指南对象） |
| `ibci_modules/ibci_ai/core.py` | **模块宿主**：IBCI 胶水（`setup` / 配置加载入口 / `run_batch` / `stream_*` / 意图管理） | **不改**（改它破坏 `ai` 模块的 IBCI 集成） |

- `provider_impl.py` 是 kernel-free 的单一可替换单元：不导入 `core.kernel` /
  `core.runtime` / `core.extension`，只依赖 `core.base.llm_protocol`（最底层契约）
  与同目录 kernel-free 模块。
- 自定义 LLM 底层 = 修改 `provider_impl.py`，或把整个文件替换为自写
  `LLMProvider` 实现（保持宿主依赖的契约面，见下）。

## LLMProvider 契约方法

宿主 `AIPlugin` 继承本类并经 `LLMProvider` 契约向内核暴露；替换实现时以下
**抽象方法**必须保留（签名不变）：

| 方法 | 职责 |
|------|------|
| `call(request) -> LLMCallResult` | 执行一次 LLM 调用并解析为供应商无关结果 |
| `stream(request)` | 流式调用，返回逐步产出 `str` 增量的迭代器 |
| `get_retry() -> int` | 最大 LLM 重试次数（llmexcept 重试循环读取） |
| `is_auto_intent_injection_enabled() -> bool` | 自动意图注入开关（prompt 拼装前读取） |
| `get_current_call_info() -> dict` | 最近一次调用的诊断信息 |

`probe()` 是**可选**方法（探测发送方式与判定逻辑是供应商专属适配）：需要模型
能力探测时实现它；不实现时按保守策略处理。

宿主依赖的配置应用面同样不能丢：`apply_config` / `set_config` / `set_mock_mode` /
`register_model` / `has_api_key` / `probe_model` / `set_retry` / `set_timeout` /
`set_return_type_prompt` / `get_return_type_prompt` / `save_plugin_state` /
`restore_plugin_state`（这些是 `ai` 模块的 vtable 用户 API 与插件状态协议）。

## 常见修改点

### 换一个 OpenAI 兼容端点

推荐 provider 已按 OpenAI 兼容格式组装 payload，通常只需在
`ai.load_project_config()` 的 `api_config.json` 中改 `providers` / `models`，
无需改代码。仅当端点无法以该格式接入时才修改本文件。

### 调整思考参数映射

`LLMCallRequest` 的 `thinking_mode` 字段是供应商无关声明（"auto"/"on"/"off"）；
各供应商自身的思考字段（LM Studio / llama.cpp `enable_thinking`、OpenAI
`reasoning.effort`、Anthropic `thinking.budget_tokens` 等）由 provider 实现映射。

- 推荐实现面向开发基线（LM Studio + Qwen 非思考模式），payload 固定发送
  `extra_body={"enable_thinking": False, ...}`。
- 换供应商时修改 `call()` / `stream()` / `probe()` 中的 payload 组装，按该
  供应商字段映射 `thinking_mode`；不要改动契约层（`core.base.llm_protocol`）。

### 改变 api_config.json 书写格式

配置读取经 `ConfigSourceAdapter` 抽象（`core.base.llm_protocol.config`）。默认
适配器 `ProjectApiConfigAdapter`（`ibci_modules/ibci_ai/config_source_adapter.py`）
识别推荐 schema（`defaults` / `providers` / `models` / `default_model`）。

- 想用自己的格式：替换 `config_source_adapter.py` 整文件，实现
  `can_load` / `load` / `load_raw_dict`（保持类名 `ProjectApiConfigAdapter`），
  输出 `LLMConnectionConfig` 即可——内核与语言层不感知文件 schema。
- 逻辑配置归一（旧式 dict → `LLMConnectionConfig`）在
  `ibci_modules/ibci_ai/config_normalize.py`（kernel-free 叶子），一般不改。

### 返回类型提示

`set_return_type_prompt(type_name, prompt)` 注册某类型的系统提示词注入；
`apply_config` / `load_project_config` 载入后自动生效。类型提示表在
`provider_impl.py` 内维护。

## 注意事项

- **思考抑制失败是已知边界**：请求已带抑制参数但模型仍输出思考时，推荐 provider
  只告警一次（提示提交 issue），不引导改配置绕开。该边界属供应商感知的思考禁用
  覆盖缺口。
- **MOCK 测试模式**：`set_mock_mode()` / `api_config.json` 的 `defaults.mock` 显式
  进入；MOCK 指令语言由 `ibci_modules/ibci_ai/mock_scenario.py` 实现（线程安全），
  替换 provider 时可直接复用，勿改哨兵常量（位于 `core.base.llm_protocol.llm_call`）。
- **不改胶水**：`core.py` 里 `run_batch` / `stream_call` / `stream_channel` / 意图
  方法依赖内核执行器与 capabilities，误改会破坏 `ai` 模块运行面。

## 改动后验证

1. 全量回归：`conda activate ibci && python -m pytest tests/`——零回归后再提交。
2. 真实 LLM 试用：按 `docs/howto/run_trials.md` 跑一套真实调用，确认新 provider
   的响应解析与探测路径符合预期。
3. 提交前自检：`provider_impl.py` 保持 kernel-free（无 `core.kernel` /
   `core.runtime` / `core.extension` 导入）；vtable 用户 API 齐全；无新旧路径并存。

## 深入指引

- 供应商无关契约全文：`docs/architecture/01_principles.md` §3.7
- 内置模块系统：`docs/subsystems/04_plugin_system.md`
- 调试 LLM 调用：`docs/howto/debug_llm_calls.md`