# 07 · MOCK 测试与调试

> 本章是 IBCI MOCK 测试与调试机制的入门教程。面向需要在不连接真实 LLM API 的情况下测试 LLM 相关代码的 IBCI 用户。覆盖 MOCK 模式、MOCK 指令语法、序列 MOCK、以及 `idbg` 调试模块。

---

## 你将会学到

- 启用 MOCK 模式，用 MOCK 指令替代真实 LLM 调用
- 为不同数据类型编写对应的 MOCK 指令
- 用序列 MOCK 模拟多次调用的不同返回值
- 用 `idbg` 模块探查提示词、意图栈和调用结果
- 理解 MOCK 模式的边界——哪些场景需要真实 API 验证

前提：你已完成 [06 · 构建多步骤 LLM 工作流][] 的学习，能构建包含多个 LLM 调用的管道。

---

## 启用 MOCK 模式

IBCI 的 MOCK 模式让你无需 API key、无需网络即可测试 LLM 逻辑。只需一行配置：

```ibci
import ai
ai.set_mock_mode()
```

配置后，所有 `@~ ... ~` 行为表达式和 LLM 可调用类调用都不会连接真实 API，而是**在表达式或装配的用户提示中查找 MOCK 指令，直接返回预设值**。

---

## 基本 MOCK 指令

MOCK 指令写在行为表达式中，用 `MOCK:类型:值` 格式：

```ibci
import ai
ai.set_mock_mode()

str reply = @~ MOCK:STR:"hello world" ~
print(reply)          # hello world

int n = @~ MOCK:INT:42 ~
print((str)n)         # 42

bool yes = @~ MOCK:BOOL:TRUE ~
print((str)yes)       # True
```

布尔类型另有 `MOCK:TRUE` / `MOCK:FALSE` 快捷指令，直接返回真/假。完整指令表（含 `MOCK:FLOAT`、`MOCK:LIST`、`MOCK:DICT` 与含空格字符串的引号规则）见 [语法参考 / MOCK 测试][syntax-13]。

---

## LLM 可调用类 MOCK

测试 LLM 可调用类时，在装配配置字典的 `user_prompt` 中放置 MOCK 指令：

```ibci
import ai
ai.set_mock_mode()

class 翻译:
    func __llm_call__(self, any 文本, any 目标语言) -> dict:
        return {"user_prompt": "MOCK:STR:翻译结果", "prompt_slots": [{"kind": "user_sys", "text": "你是一个专业翻译。"}]}

翻译 t = 翻译()
str r = t("hello", "中文")
print(r)                     # 翻译结果
```

---

## 命名模型 MOCK

对使用 `@NAME~` 路由到特定模型的调用，MOCK 同样有效：

```ibci
import ai
ai.set_mock_mode()

# 无需真实注册，MOCK 模式直接截获
str result = @GPT4o~ MOCK:STR:"来自 GPT4o 的 mock 结果" ~
print(result)                   # 来自 GPT4o 的 mock 结果
```

MOCK 拦截发生在模型路由之前，MOCK 模式下未注册的模型名不报错（命名模型路由规则见 [语法参考 / 行为表达式][syntax-07]）。

---

## 测试容错：MOCK FAIL 与 REPAIR

`MOCK:FAIL` 始终失败（测试重试耗尽的路径），`MOCK:REPAIR` 首次失败后重试返回指定值（测试容错恢复）：

```ibci
import ai
ai.set_mock_mode()

try:
    int r = @~ MOCK:FAIL ~
    llmexcept:
        retry "请只返回一个整数"
except LLMRetryExhaustedError as e:
    print("重试耗尽: " + e.message)

int result = @~ MOCK:REPAIR:INT:99 ~
llmexcept:
    retry "请只返回一个整数"
print((str)result)                     # 99
```

`MOCK:REPAIR` 支持所有基本类型作回退值，完整语法见 [语法参考 / MOCK 测试][syntax-13]。

---

## 序列 MOCK：模拟多次调用

当同一 `key` 的 MOCK 被多次调用，需要每次返回不同值时，使用 `MOCK:SEQ`：

```ibci
import ai
ai.set_mock_mode()

# 第一次返回 "通过"，第二次返回 "优秀"，第三次返回 "不合格"
str s1 = @~ MOCK:SEQ:[通过,优秀,不合格] evaluation ~
str s2 = @~ MOCK:SEQ:[通过,优秀,不合格] evaluation ~
str s3 = @~ MOCK:SEQ:[通过,优秀,不合格] evaluation ~

print(s1)   # 通过
print(s2)   # 优秀
print(s3)   # 不合格
```

`MOCK:SEQ` 的 `key` 是去重标识符——同一个 `key` 共享序号计数器。

---

## 用 idbg 调试

`idbg` 模块让你探查每次 LLM 调用的内部状态：

```ibci
import ai
import idbg
ai.set_mock_mode()

@+ 用简洁的语言回答
str r = @~ MOCK:STR:hello ~

idbg.show_intents()          # 打印当前意图栈
idbg.show_target_prompt()    # 打印最近 LLM 调用的完整提示词
idbg.current_llm()           # 返回最近调用的完整信息（dict）
idbg.current_result()        # 返回最近调用的结果对象
idbg.vars()                 # 返回当前作用域所有变量（dict）
idbg.print_vars()           # 打印当前作用域所有变量
```

---

## MOCK 模式的边界

MOCK 模式验证指令解析与控制流逻辑，无法验证意图注入、提示词协议、多模态与 `llmexcept` retry hint 对真实 LLM 的行为影响——这些需要连接真实 API。完整列表见 [已知限制 / MOCK 模式下无法验证的 LLM 功能][known-17]。

---

## 推荐工作流

1. **快速迭代**：MOCK 模式 + `idbg` 调试，验证控制流和错误处理逻辑
2. **真实验证**：切换到真实 API key，验证 LLM 输出质量
3. **回归保护**：用 MOCK 指令固化已验证场景的预期行为，纳入测试套件
4. **真实 LLM 试用**：运行 `trials/` 下的试用地基，见 [如何运行试用套件][run-trials]

---

## 你现在能做什么

- 在 MOCK 模式下用 MOCK 指令为 `@~` 和 LLM 函数提供预设返回值
- 用 `MOCK:FAIL` / `MOCK:REPAIR` 验证容错逻辑
- 用 `MOCK:SEQ` 模拟多次调用的不同返回序列
- 用 `idbg.show_intents()` 和 `idbg.show_target_prompt()` 调试 LLM 交互
- 理解 MOCK 的边界，知道何时必须切换到真实 API

深入查阅：MOCK 指令的完整语法见 [语法参考 / MOCK 测试][syntax-13]，语言级限制见 [已知限制][known-17]。

[06 · 构建多步骤 LLM 工作流]: ./06_multistep.md
[run-trials]: ../howto/run_trials.md
[syntax-07]: ../syntax/07_behavior_expressions.md
[syntax-13]: ../syntax/13_mock_testing.md
[known-17]: ../KNOWN_LIMITS.md#十六mock-模式下无法验证的-llm-功能
