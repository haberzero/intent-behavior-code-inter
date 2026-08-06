# 如何调试 LLM 调用失败

> 面向已能运行 `@~ ... ~` 调用的开发者。解决"LLM 调用报错或返回不符合预期"的具体问题。
> 前置知识：`docs/syntax/07_behavior_expressions.md`（行为表达式）、`docs/syntax/10_robustness.md`（异常与重试）。

## 先判定失败类型

LLM 调用失败分三类，处理方式完全不同：

| 现象 | 类型 | 根因 |
|------|------|------|
| `LLMCallError` | 基础设施失败 | 网络、鉴权、超时、服务不可达 |
| `LLMParseError` | 内容解析失败 | LLM 返回无法解析为目标类型 |
| `LLMRetryExhaustedError` | 重试耗尽 | 上述任一失败在 `ai.set_retry(n)` 次内未恢复 |

## 查看最近一次调用的详情

在失败点后插入调试代码，用 `idbg` 探查：

```ibci
import idbg

@~ 计算 1+1，只返回数字 ~
idbg.current_result()        # 最近一次调用结果对象
idbg.current_llm()           # 调用详情（模型、提示词、原始响应）
idbg.show_target_prompt()    # 打印注入意图后的完整提示词
idbg.retry_stack()           # 若在 llmexcept 中：当前重试帧详情
```

- `current_llm()` 返回 dict，含 `raw_response` 与 `reasoning`（如可用）。
- `show_target_prompt()` 显示 LLM 实际收到的提示词，用于核对意图/插值是否正确注入。

## 处理内容解析失败

`LLMParseError` 说明 LLM 返回的文本无法解析为声明类型。先确认解析约束：

```ibci
# ❌ 目标类型未声明，LLM 返回任意文本
result = @~ 计算 1+1 ~

# ✅ 声明 int，LLM 收到"只返回数字"的输出约束
int result = @~ 计算 1+1 ~
```

若已声明类型仍失败，在行为表达式后加 `llmexcept` 提供修正指引：

```ibci
int result = @~ 计算 1+1 ~
llmexcept:
    retry "请只返回一个数字，不要任何其他文字"
```

## 定位提示词层面的问题

输出不符合预期（而非报错）时，检查三处：

1. **意图泄漏**：函数内未清除继承意图，`show_intents()` 查看当前意图栈。
2. **插值未生效**：`$var` 引用拼写或作用域错误，`show_target_prompt()` 核对。
3. **解析类型不匹配**：声明类型与行为语义不一致，改用 `-> str` 取原始文本核对。

## 用 MOCK 隔离环境问题

在不连真实 API 的情况下复现，排除网络/服务因素：

```ibci
import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")

str r = @~ MOCK:STR:hello ~    # 确定返回 "hello"
```

MOCK 指令语法见 `docs/syntax/13_mock_testing.md`。需要验证传输层行为（超时、并发）时用 MOCK HTTP 服务。

## 深入指引

- 异常体系与重试：`docs/syntax/10_robustness.md`
- MOCK 测试：`docs/syntax/13_mock_testing.md`
- 行为输出解析限制：`docs/KNOWN_LIMITS.md` §四
