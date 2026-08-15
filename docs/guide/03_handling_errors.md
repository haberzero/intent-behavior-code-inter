# 03 · 处理 LLM 调用失败

> 本章是 IBCI 入门教程的第三章。面向已能发起 LLM 调用的开发者。覆盖三种 LLM 异常类型、`llmexcept` 重试机制、`llmretry` 快捷写法与快照隔离模型。
>
> 前置阅读：`docs/guide/02_first_call.md`。完整健壮性机制参考见 `docs/syntax/10_robustness.md`。

## 你将会学到

- 识别三种 LLM 异常类型及其触发场景
- 使用 `llmexcept` + `retry` 保护行为表达式赋值
- 使用 `llmretry` 简化单重试场景
- 理解快照隔离保证重试一致性
- 使用 `try/except` 作为最终兜底

## LLM 调用可能失败的方式

LLM 调用的失败分为三个层次：

| 异常类型 | 触发场景 |
|----------|---------|
| `LLMCallError` | 网络故障、API 密钥无效、提供者返回 4xx/5xx |
| `LLMParseError` | LLM 回应内容无法按左值类型解析（例如 `int` 变量收到一段散文） |
| `LLMRetryExhaustedError` | `llmexcept` 保护块中所有重试次数耗尽，最后一次尝试仍然失败 |

`LLMCallError` 和 `LLMParseError` 由 IBCI 运行时在调用失败时自动抛出。`LLMRetryExhaustedError` 仅在 `llmexcept` 或 `llmretry` 保护下重试耗尽时抛出。

## llmexcept：保护赋值语句

`llmexcept` 紧跟在被保护的语句之后，缩进级别必须一致。当被保护语句中的 LLM 调用失败时，`llmexcept` 体被执行：

```ibci
int result = @~ 1+1 等于几？只答数字 ~
llmexcept:
    print("AI 响应无法解析为整数，正在重试……")
    retry "请务必只返回一个纯数字，不要任何其他内容"
```

执行流程：
1. 执行 `@~ ... ~` 赋值。
2. 成功 → 跳过 `llmexcept`，继续执行后续代码。
3. 失败 → 进入 `llmexcept` 体，执行 `print`，然后 `retry` 重新发起 LLM 调用。
4. `retry` 后的字符串会作为额外系统提示词注入到重试调用中；同时运行时自动把上一次失败响应与解析错误以标准多轮对话形式回喂给模型。
5. 重试成功 → `result` 被赋值，退出 `llmexcept`。
6. 所有重试耗尽 → 抛出 `LLMRetryExhaustedError`。

重试次数由 `ai.set_retry(n)` 配置，默认为 3。

## llmexcept：保护 if 条件

行为表达式可以直接出现在 `if` 条件中。此时 `llmexcept` 跟在条件块末尾：

```ibci
str text = "今天的会议很高效"
if @~ $text 是正面情绪吗？只答 1 或 0 ~:
    print("正面")
llmexcept:
    retry "只返回 0 或 1"
```

条件中的行为表达式被隐式转换为 `bool` 类型。若 LLM 返回的内容既不是 `0` 也不是 `1`，解析失败触发 `llmexcept`，重试后再次求值 `if` 条件。

## llmretry：纯重试快捷写法

当重试逻辑仅需要注入提示词、不需要额外副作用（如打印日志）时，`llmretry` 是更简洁的写法：

```ibci
str res = @~ 判断当前状态，只回答正常或异常 ~
llmretry "如果无法判断，请回复 0 并说明原因"
```

`llmretry` 等价于一个只包含 `retry` 语句的 `llmexcept` 块。两者语义完全相同，仅是语法糖。

## 快照隔离：重试不会污染其他变量

`llmexcept` 的重试由**快照隔离**保证一致性：

1. 进入被保护的 LLM 语句时，运行时创建当前变量状态、意图上下文和循环状态的完整快照。
2. LLM 调用成功 → 结果提交到目标变量，快照被丢弃。
3. LLM 调用失败 → 先执行 `llmexcept` 体（打印日志等），然后从快照恢复全部状态，再重新发起调用。
4. `llmexcept` 体中对变量的非关键修改不会泄漏到重试后的调用中。

这意味着即使 `llmexcept` 体内修改了参与 LLM 调用的变量，重试时也会恢复到快照中的原始值：

```ibci
int counter = 0
str result = @~ 翻译 "Hello" ~
llmexcept:
    counter = counter + 1    # 这个修改不会影响后续重试
    retry "请翻译成中文"
```

**限制**：`llmexcept` 体内禁止修改参与 `$` 插值的变量和 LLM 赋值目标变量（编译器会报告 `SEM_LLMEXCEPT_BODY_WRITE` 错误）。非参与变量的修改允许。

## try/except：最终兜底

当所有重试耗尽后，`LLMRetryExhaustedError` 可被外层 `try/except` 捕获，实现最终降级逻辑：

```ibci
import ai

ai.set_config("https://dashscope.aliyuncs.com/compatible-mode/v1",
              "sk-xxxxxxxxxxxxxxxxxxxxxxxx",
              "qwen3-30b-a3b")
ai.set_retry(2)

try:
    int score = @~ 给以下产品打分 1-10 ~
    llmexcept:
        retry "请只返回 1 到 10 之间的整数"
    print("分数：" + (str)score)
except LLMRetryExhaustedError:
    print("LLM 服务暂时不可用，请稍后重试")
```

## 你现在能做什么

你已掌握 IBCI 的三层异常处理：解析失败时的带提示重试、网络/鉴权失败时的自动捕获、以及重试耗尽后的最终降级。这套机制允许你在 LLM 不确定性与工程可靠性之间取得平衡。

**下一步**：[04 · 用意图控制 LLM 行为][]——用意图注释精准控制 LLM 的输出风格和格式。

[04 · 用意图控制 LLM 行为]: ./04_intents.md
