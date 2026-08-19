# 05 · 定义和使用 LLM 可调用类

> 本章是 IBCI LLM 可调用类的入门教程。面向已掌握行为表达式和意图系统的 IBCI 用户。覆盖 `__llm_call__` 协议方法、装配配置字典、参数绑定与统一消费入口。
>
> `llm ... llmend` 函数语法已废除，命名 LLM 调用统一由 **LLM 可调用类** 承载。

---

## 你将会学到

- 将提示词逻辑封装为可复用的 LLM 可调用类
- 用装配配置字典区分系统提示（`prompt_slots`）与用户提示（`user_prompt`）
- 在提示词中安全地插入变量
- 用 `expected_type` 控制 LLM 输出解析

前提：你已完成 [04 · 用意图控制 LLM 行为][] 的学习，能在 IBCI 中管理意图上下文。

---

## 为什么用 LLM 可调用类

直接在代码中写 `@~ ... ~` 行内行为表达式在简单场景中足够好用，但当你需要：

- 在多处用同一套提示词逻辑调用 LLM
- 接受参数定制每次调用的输入
- 明确定义系统提示词与用户提示词的边界
- 批量 / 流式消费同一套逻辑

就应该将提示词逻辑封装为 **LLM 可调用类**。

```ibci
# 行内方式：每次都要完整写提示词，无法复用
str r1 = @~ 请将 "hello" 翻译为中文 ~
str r2 = @~ 请将 "world" 翻译为中文 ~
# ...
```

```ibci
# LLM 可调用类：定义一次，任意调用
class 翻译:
    func __llm_call__(self, any 文本, any 目标语言) -> dict:
        return {"user_prompt": "请将 \"" + str(文本) + "\" 翻译为 " + str(目标语言) + "。"}

翻译 t = 翻译()
str r1 = t("hello", "中文")
str r2 = t("world", "中文")
```

---

## 基本语法

```ibci
class 翻译:
    func __llm_call__(self, any 文本, any 目标语言) -> dict:
        return {
            "user_prompt": "请将 \"" + str(文本) + "\" 翻译为 " + str(目标语言) + "。",
            "prompt_slots": [{"kind": "user_sys", "text": "你是一个专业翻译，直接输出翻译结果，不加任何解释。"}],
        }
```

关键规则：
- 类实现 `__llm_call__(self, ...) -> dict` 即满足 **LLMCallable** 协议
- 装配字典键 `user_prompt`（用户提示，必需）、`prompt_slots`（系统/角色设定）、`expected_type`（输出解析类型）
- 参数直接写在 `__llm_call__` 签名上，调用时按位绑定

LLM 可调用类的完整语法参考 [语法参考 / LLM 可调用类][syntax-08]。

---

## `prompt_slots` vs `user_prompt`

两者分工明确：

| 键 | 语义 | 放在里面的是 |
|----|------|-------------|
| `prompt_slots` | 系统提示（自定义语义槽） | 角色、能力边界、输出格式约定、回答风格 |
| `user_prompt` | 用户提示 | 具体任务描述、输入数据、参数化内容 |

```ibci
class 总结要点:
    func __llm_call__(self, any 文章) -> dict:
        return {
            "user_prompt": "请总结以下文章的核心要点：" + str(文章),
            "prompt_slots": [{"kind": "user_sys", "text": "你是一个专业编辑，善于提炼文章核心观点。\n只输出要点列表，每条一行，格式为 \"- 要点\"。"}],
        }
```

---

## 参数插值

`__llm_call__` 的参数经 `str(参数)` 显式拼入提示词。插值规则：

- 参数名**严格区分大小写**
- 每次调用时独立求值，不缓存
- 参数经 `str()` / `__to_prompt__()` 呈现（自定义类型调用其 `__to_prompt__()` 方法）

```ibci
class 打分:
    func __llm_call__(self, any 商品名, any 最高分) -> dict:
        return {"user_prompt": "请给 \"" + str(商品名) + "\" 打分，范围 1 到 " + str(最高分) + "，只返回整数。", "expected_type": "int"}

打分 s = 打分()
int score1 = s("机械键盘", 10)    # 评分范围 1-10
int score2 = s("无线耳机", 5)     # 评分范围 1-5
```

---

## `expected_type`：输出解析

LLM 输出不一定能成功解析为目标类型。`expected_type` 声明解析目标——`int` / `float` / `str` / `bool` / 容器（`list[T]` / `dict[K,V]`）/ 用户类（经 `__from_prompt__`）：

```ibci
class 提取年龄:
    func __llm_call__(self, any 文本) -> dict:
        return {"user_prompt": "从以下文本中提取年龄，只返回数字：" + str(文本), "expected_type": "int"}
```

当 `文本` 为 "我今年 25 岁" 时，LLM 应返回 `25`。解析失败触发重试机制（`llmexcept` 处理，见 [语法参考 / 健壮性][syntax-10]）。

---

## 调用 LLM 可调用类

```ibci
import ai
ai.set_config("https://api.example.com", "YOUR_KEY", "gpt-4o")

class 翻译:
    func __llm_call__(self, any 文本, any 目标语言) -> dict:
        return {"user_prompt": "将 \"" + str(文本) + "\" 翻译为 " + str(目标语言) + "。"}

翻译 t = 翻译()
str zh = t("Hello, how are you?", "中文")
str ja = t("Hello, how are you?", "日文")

print(zh)
print(ja)
```

LLM 可调用类实例可经统一消费入口批量 / 流式调用：`ai.run_batch(target, items)`、`ai.stream_call(target)` / `ai.stream_channel(target)`（见 [语法参考 / 模块 11][syntax-11]）。

---

## 你现在能做什么

- 用 LLM 可调用类封装可复用的提示词逻辑
- 通过参数绑定让每次 LLM 调用携带不同的输入数据
- 用 `expected_type` 控制输出解析
- 批量 / 流式消费同一套 LLM 逻辑

**下一步**：[06 · 构建多步骤 LLM 工作流][]——将多个 LLM 可调用类和行为表达式组合成完整的处理管道。

[04 · 用意图控制 LLM 行为]: ./04_intents.md
[06 · 构建多步骤 LLM 工作流]: ./06_multistep.md
[syntax-08]: ../syntax/08_llm_callable.md
[syntax-10]: ../syntax/10_robustness.md
[syntax-11]: ../syntax/11_modules.md