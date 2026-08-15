# _code_llm_retry_multiturn — LLM 提示词精简 + retry 标准多轮对话改造

> 2026-08-15 编制。触发：用户指出 behavior 系统提示中
> "你是一个被 IBCI 程序调用的函数。" 等多处注入对模型无信息量，
> 应改为只描述任务要求；并追问 retry 是否利用 OpenAI 标准多轮对话。

## 一、问题确认

1. 原 `BEHAVIOR_SYSTEM_PROMPT` 向模型介绍 "IBCI 程序调用" 身份，模型不知道
   IBCI；意图标题 "当前上下文意图（必须严格遵守）" 也是元信息。提示词应
   只描述本次调用必须遵守的规则。
2. retry 之前**没有**利用标准多轮对话：`_call_llm` → `ILLMProvider.__call__`
   只接收 sys/user 单轮输入，`AIPlugin` 每次 `chat.completions.create` 都新建
   `[system, user]`；重试反馈被拼进 sys_prompt，而不是以 `assistant/user`
   轮次回喂。代码实证见 `ibci_modules/ibci_ai/core.py` `__call__`（旧）。

## 二、方案

- **提示词精简**：删除身份句；behavior 基础纪律改为
  "只输出任务要求的结果数据本身。禁止输出任何解释、问候、提问、拒绝、
  安全声明或其他与结果无关的文字。"；意图标题改为 "必须遵守以下要求："；
  通用类型声明去掉多余 `[期望输出类型]` 标题。
- **标准多轮 retry**：
  - `ILLMProvider.__call__` 协议增加 `message_history: Optional[List[Dict]]`
    关键字参数，追加在 `[system, user]` 之后。
  - `LLMExceptFrame` 增加 `attempt_history` 失败尝试历史，每轮 handler body
    执行后由 `_retry_llm_uncertain` 记录（含 raw_response / parse_error /
    下一轮 user_hint）。
  - `_BehaviorMixin` / `_LLMFunctionMixin` 从 `attempt_history` 构造
    `assistant → user → ...` 消息历史，通过 `BehaviorCallSpec.message_history`
    / `LLMFunctionCallSpec.message_history` 传给 `_call_llm`。
  - `AIPlugin` 把 `message_history` 追加到 OpenAI messages，形成
    `system → user(原任务) → assistant(失败输出) → user(纠错)` 标准多轮。
  - Mock HTTP 服务 `_extract_user_prompt` 改为取首个 user 消息（原始任务），
    否则 MOCK 指令会被末轮纠错 user 消息覆盖。

## 三、测试

- 更新 `tests/e2e/test_llm_prompt_mechanism.py`：断言 sys_prompt 不含
  "IBCI"/"意图行为代码执行器"；retry 测试改为断言 `message_history`
  的 `assistant/user` 角色与内容；新增 `__llmretry__` 首次调用不注入测试。
- 全量 pytest：2788 passed / 1 skipped（零回归）。
