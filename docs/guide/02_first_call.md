# 02 · 第一个 @~ 调用

> 本章是 IBCI 入门教程的第二章。面向已完成 LLM 提供者配置的开发者。覆盖行为表达式的基本语法、变量插值、类型约束与一个完整的端到端示例。
>
> 前置阅读：`docs/guide/01_setup.md`。

## 你将会学到

- 使用 `@~ ... ~` 发起一次 LLM 调用
- 在提示词中插入变量
- 理解左值类型如何约束 LLM 输出格式
- 编写并运行一个完整的 IBCI 程序

## 最简行为表达式

`@~ ... ~` 是 IBCI 中触发 LLM 调用的语法结构。`@~` 和 `~` 之间的自然语言文本会作为提示词发送给 LLM，LLM 的返回值被赋给左侧变量：

```ibci
str joke = @~ 讲一个关于程序员的笑话 ~
print(joke)
```

左值的类型决定了 LLM 输出如何被解析。完整类型约束与输出格式规则见 `docs/syntax/07_behavior_expressions.md §7.2`。

## 在提示词中插入变量

使用 `$变量名` 语法可将变量值嵌入提示词：

```ibci
str topic = "Python"
str joke = @~ 讲一个关于 $topic 的笑话 ~
print(joke)
```

插值时，IBCI 调用变量的 `__to_prompt__()` 方法将其转换为提示词文本。所有内置类型（`str`、`int`、`float` 等）都实现该方法。

## 左值类型决定输出格式

不同左值类型对 LLM 施加不同的输出约束：

| 左值类型 | 约束 | 示例 |
|----------|------|------|
| `str` | 任意文本 | `str reply = @~ 介绍一下 IBCI ~` |
| `int` | 仅整数 | `int answer = @~ 1+1 等于几 ~` |
| `float` | 小数点数值 | `float pi = @~ pi 前三位小数 ~` |
| `bool` | 仅 0 或 1 | `bool neg = @~ "我很难过" 是负面情绪吗 ~` |
| `list[str]` | JSON 数组格式 | `list[str] tags = @~ 给这段文字打 3 个标签，JSON 数组格式 ~` |

如果 LLM 返回的内容与左值类型不匹配，解析阶段会抛出 `LLMParseError`。错误处理机制将在下一章详细讨论。

## 第一个完整程序

将以下内容保存为 `01_hello.ibci`：

```ibci
import ai

ai.set_config("https://dashscope.aliyuncs.com/compatible-mode/v1",
              "sk-xxxxxxxxxxxxxxxxxxxxxxxx",
              "qwen3-30b-a3b")

str name = "IBCI"
str greeting = @~ 用一句话介绍 $name，用中文 ~
print(greeting)

int answer = @~ 1+1 等于几？只回答数字 ~
print(answer)
```

运行：

```bash
python main.py run 01_hello.ibci
```

输出将包含 LLM 生成的中文介绍和数字 `2`。

在条件判断中使用行为表达式同样可行：

```ibci
str input = "今天心情不错"
if @~ $input 包含正面情绪吗？只答 1 或 0 ~:
    print("正面情绪")
else:
    print("非正面情绪")
```

行为表达式在条件上下文中被隐式转换为 `bool` 类型——编译器要求 LLM 仅输出 `0` 或 `1`。

## 不依赖 api_config.json 的纯代码配置

如果尚未创建 `api_config.json`，也可以在代码中直接调用 `ai.set_config()` 配置默认模型。两种方式的效果相同。若已通过 `ai.load_project_config()` 加载文件配置，后续 `set_config()` 调用会覆盖之。

## 你现在能做什么

你已掌握 `@~` 行为表达式的基本用法，可以发起 LLM 调用并处理不同输出格式。下一步需要处理真实场景中不可避免的 LLM 调用失败。

**下一步**：[03 · 处理 LLM 调用失败][]——处理真实场景中不可避免的 LLM 调用失败。

[03 · 处理 LLM 调用失败]: ./03_handling_errors.md
