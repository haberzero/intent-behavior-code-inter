# 06 · 构建多步骤 LLM 工作流

> 本章是 IBCI 多步骤 LLM 工作流的入门教程。面向已掌握 LLM 函数定义和意图系统的 IBCI 用户。覆盖如何串联多个 LLM 调用、用 `for @~` 实现 AI 驱动循环、以及结合 `file` 模块和 `llmexcept` 构建健壮的处理管道。

---

## 你将会学到

- 将 LLM 调用串联为分步骤的处理管道
- 用 `file` 模块持久化中间结果
- 用 `fn` + `lambda` 创建可复用的延迟行为表达式
- 用 `for @~ ... ~` 让 AI 决定循环终止条件
- 用 `llmexcept` 为每个步骤加上容错保护

前提：你已完成 [05 · 定义和使用 LLM 函数][] 的学习，能封装和调用 LLM 函数。

---

## 场景：文本情感分析与重写

假设你需要构建一个内容处理管道：

1. 分析输入文本的情感（正面 / 负面 / 中性）
2. 根据分析结果走不同的 LLM 重写分支
3. 将最终结果保存到文件

每一步都可能出现 LLM 解析失败，需要容错处理。我们将逐步构建这个管道。

---

## 步骤一：定义 LLM 函数

首先封装两个 LLM 函数——一个做情感判断，一个做重写：

```ibci
import ai
ai.set_config("https://api.example.com", "YOUR_KEY", "gpt-4o")

llm 分析情感(str 文本) -> str:
__sys__
你是一个情感分析专家。
__user__
分析以下文本的情感，只返回一个词：正面、负面 或 中性。

$文本
__llmretry__
请只返回 "正面"、"负面" 或 "中性" 中的一个词。
llmend
```

```ibci
llm 重写文本(str 原文, str 目标风格) -> str:
__sys__
你是一个专业文案，善于按指定风格改写内容。
__user__
请将以下文本改写为"$目标风格"风格：

$原文
__llmretry__
请务必输出改写后的文本，不要附带注释。
llmend
```

---

## 步骤二：串联调用与分支

核心逻辑：分析 → 判断 → 分支重写。每一步用 `llmexcept` 保护：

```ibci
func 处理文本(str 输入) -> str:
    str 情感 = 分析情感(输入)
    llmexcept:
        retry "请只返回 正面、负面 或 中性"

    str 输出
    if 情感 == "正面":
        输出 = 重写文本(输入, "更热情的宣传")
        llmexcept:
            retry "请输出改写后的完整文本"
    elif 情感 == "负面":
        输出 = 重写文本(输入, "委婉中立的表达")
        llmexcept:
            retry "请输出改写后的完整文本"
    else:
        输出 = 输入

    return 输出
```

---

## 步骤三：持久化中间结果

`file` 模块可以将每个阶段的输出写入文件，方便调试和复查：

```ibci
import file

str 原始 = "这个产品的功能其实还可以，但是价格实在太贵了"
str 情感 = 分析情感(原始)
llmexcept:
    retry "请只返回 正面、负面 或 中性"

file_handle fh = file.write_new("pipeline_output.txt",
    "原始文本: " + 原始 + "\n情感判断: " + 情感)

str 原文内容 = fh.read()
print(原文内容)
```

`file.write_new` 创建新文件，返回只读的 `file_handle`。`write_copy` 和 `write_new` 不污染已有数据，适合在 LLM 重试场景中使用——即使在 `llmexcept` retry body 中也可以安全调用（详见 [语法参考 / 模块][syntax-11]）。

---

## 步骤四：用 `fn` + `lambda` 复用行为

需要多次调用同一个 LLM 但根据不同上下文切换参数时，`lambda` 可以封装为可复用对象：

```ibci
fn 改写 = lambda(str 文本, str 风格) -> str:
    @+ 不要添加任何额外解释
    str r = 重写文本(文本, 风格)
    return r

str v1 = 改写("产品不错", "小红书种草风格")
str v2 = 改写("产品不错", "知乎技术评测风格")
```

`lambda` 在每次调用时求值，使用调用处的意图栈——上述例子中通过 `@+` 在调用处追加了"不要额外解释"的约束。如果需要冻结意图上下文，改用 `snapshot`（详见 [语法参考 / 行为表达式][syntax-07]）。

---

## 步骤五：AI 驱动循环

当循环的终止条件需要 AI 判断时，用 `for @~ ... ~`：

```ibci
int 迭代次数 = 0
str 文本 = "这个产品还不错"

for @~ $文本 已经很精炼了吗？只回答 1 或 0 ~:
    迭代次数 = 迭代次数 + 1
    if 迭代次数 >= 5:
        break
    文本 = 重写文本(文本, "精炼简洁")
    llmexcept:
        retry "请输出更精炼的改写文本"

print("最终文本: " + 文本)
print("迭代次数: " + (str)迭代次数)
```

`for @~` 的条件表达式会被隐式转换为 `bool`：LLM 返回 `1` 时继续循环，返回 `0` 时退出。`break` 提供硬上限保护，防止循环失控。

完整工作流可选的健壮性方案（`llmexcept` 快照隔离、retry 约束）详见 [语法参考 / 健壮性][syntax-10]。

---

## 你现在能做什么

- 设计并实现包含多个 LLM 调用的分步骤管道
- 用 `file` 模块在步骤间持久化中间结果
- 用 `fn` + `lambda` 创建可复用的延迟行为表达式
- 用 `for @~` 让 AI 决定循环终止，搭配 `break` 做硬上限保护
- 用 `llmexcept` 为每个 LLM 调用添加容错兜底

**下一步**：[07 · MOCK 测试与调试][]——在不连接真实 API 的情况下测试你的 LLM 工作流。

[05 · 定义和使用 LLM 函数]: ./05_llm_functions.md
[07 · MOCK 测试与调试]: ./07_testing.md
[syntax-07]: ../syntax/07_behavior_expressions.md
[syntax-10]: ../syntax/10_robustness.md
[syntax-11]: ../syntax/11_modules.md
