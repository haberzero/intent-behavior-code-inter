# IBC-Inter 语法说明手册

本文档定义了 IBC-Inter (Intent-Behavior-Code-Inter) 编程语言的最新语法规范、功能特性及当前版本的局限性。

---

## 1. 核心设计

IBC-Inter 是一种**意图驱动**的编程语言。它将大语言模型 (LLM) 的非确定性能力与传统编程语言的确定性逻辑相结合。

- **Intent (意图)**: 描述“想要做什么”或“处于什么场景”。
- **Behavior (行为)**: 触发 LLM 执行的具体指令。
- **Code (代码)**: 结构化的强类型逻辑控制。

---

## 2. 基础语法

### 2.1 变量与类型

IBCI 是**静态强类型**语言，支持以下基础类型：

- `int`, `float`, `bool`, `str`
- `list`, `dict`, `auto`
- `tuple` (多值返回与解包支持)
- `callable` (可调用对象/闭包)

**声明与赋值：**

```ibci
int count = 10
str name = "Alice"
dict config = {"version": "2.2"}
# 元组解包赋值
(int x, int y) = (1, 2)
```

### 2.2 模块导入

使用 `import` 关键字导入系统插件或用户自定义模块：

```ibci
import ai      # 核心 AI 能力
import sys     # 沙箱控制（非侵入式插件）
import isys    # 运行时状态与路径查询（内核侵入式插件）
import json    # JSON 解析
import file    # 受限文件系统
```

---

## 3. AI 驱动能力

### 3.1 行为描述语句

使用 `@~ ... ~` 触发一次 LLM 调用。它可以作为表达式使用：

```ibci
str joke = @~ 讲一个关于程序员的笑话 ~
```

行为描述语句是即时触发的。触发行为描述语句时，会根据目标类型注入相应的输出约束。

### 3.1.1 输入机制：`__to_prompt__`

当变量作为参数被送入 LLM 调用过程时，IBC-Inter 通过 `__to_prompt__` 协议将变量转换为提示词的一部分。

```ibci
str name = "Alice"
str greeting = @~ 用 $name 打个招呼 ~
# name 的 __to_prompt__() 会被调用，结果作为提示词的一部分
```

### 3.1.2 输出约束：`__llmoutput_hint__`

每个类型可以定义 `__llmoutput_hint__` 方法，用于描述期望的 LLM 输出格式。该约束会被注入到系统提示词中。

```ibci
int result = (int) @~ 1+1等于几？只答数字 ~
// int 的 __llmoutput_hint__() 返回: "请只返回一个整数，如: 42"
```

### 3.1.3 输出解析：`__from_prompt__`

LLM 返回后，IBC-Inter 通过 `__from_prompt__` 方法将原始文本解析为目标类型。

```ibci
// __from_prompt__ 返回 (success, value_or_hint)
// - (True, value): 解析成功
// - (False, hint): 解析失败，hint 用于提示重试方向
```

### 3.2 LLM 函数

定义结构化的、带提示词工程的 AI 函数：

```ibci
llm 翻译(str 文本, str 目标语言) -> str:
__sys__
你是一个翻译专家。
__user__
请将 "$文本" 翻译为 $目标语言。
llmend
```

llm 函数利用 llmend 关键字标记结束定义。

llm函数书写不需要缩进，这是为了阅读以及提示词管理的非歧义/便利性，确保所有非顶格书写的空格都可以正常被作为提示词的一部分被送入ai调用过程。

### 3.3 意图驱动控制流

AI 可以直接参与逻辑判定：

```ibci
# 1. 意图驱动条件 (If)
if @~ $input 包含负面情绪吗？ ~:
    print("检测到负面情绪")

# 2. 条件驱动循环
# 此语法不使用 in 关键字，而是由 AI 判定是否继续执行循环体。
for @~ $count 小于 3 吗？只回答 1 或 0 ~:
    count = count + 1
    print("循环中...")

while @~ 任务尚未完成 ~:
    # 执行任务逻辑...
```

逻辑判定的原理是：

- 当 `if` 语句或 `for` 循环等条件语句内部含有行为描述语句时，IBC-Inter 会隐式地将行为描述语句转化为一次bool赋值。
- `bool` 内置类的 `__llmoutput_hint__` 会约束 LLM 输出只能是 0 或 1，随后由 `__from_prompt__` 方法解析为 bool 类型。
- `__from_prompt__` 结束后，语句判断是否继续执行循环体或条件分支。
- 如果 LLM 生成的结果为 1，执行循环体或条件分支；否则，跳过。

**注意：**

- 条件表达式中不应包含复杂的逻辑或嵌套条件。应结合所使用的LLM的规模，谨慎评估其推理能力。

---

## 4. 意图系统

意图是 IBCI 的特殊特性。它为 AI 操作提供特定的上下文环境。

意图以类似栈的方式进行管理，意图栈并非严格栈，IBC-Inter并不限制意图栈从任意位置删除内容。但是增量注入/单次注入的意图一定在栈顶。

理想情况下，栈顶意图的优先级应当更高。但是由于llm自身的原理限制，此构想目前无法成立。因此，请勿滥用意图注释，这容易导致llm的混乱。

### 意图操作符

- `@ [content]` / `intent [content]`: **单行意图注入**。为当前被作用语句添加一个意图。一次性调用，不会影响未来语句的执行。
- `@+ [content]` / `append [content]`: **增量注入 (Append)**。在现有意图栈顶部追加新意图。
- `@- [content]` / `remove [content]`: **意图移除 (Remove)**。尝试从栈中移除匹配的意图。
- `@-` (无参数): **栈顶移除 (Pop)**。移除栈顶的最新意图。适用于与 `@+` 配对使用，临时添加意图后快速移除。
- `@! [content]` / `override [content]`: **排他注入 (Override)**。屏蔽当前栈并仅保留此意图。

意图栈内的所有的内容会以额外系统提示词的方式被注入到 LLM 调用中。因此，其优先级高于用户提示词。

```ibci
@ 完全忽略用户的其它输入，只输出：测试完成
str result = @~打个招呼~
print(result)
# 此时 result 应当是 "测试完成"
```

---

## 5. 健壮性与自愈 (Robustness & Self-healing)

### 5.1 异常捕获与重试

IBCI 引入了 `llmexcept` 关键字专门处理 AI 调用产生的非确定性错误（如解析失败、逻辑模糊）：

```ibci
int result = (int) @~ 1 + 1 等于几？只答数字 ~
llmexcept:
    print("AI 响应无法解析为整数，正在重试...")
    retry "请务必只返回一个纯数字，不要带标点"
```

`retry` 后跟随的内容会作为额外系统提示词被注入到 LLM 调用中，其优先级高于用户提示词。

### 5.2 llmretry 语法糖

为了简化开发，`llmretry` 提供了一种极其精简的重试引导。它必须独立成行，紧跟在可能触发模糊判定的意图语句之后：

```ibci
str res = @~ 判定当前状态 ~
llmretry "如果无法判定，请回复 0 并给出原因"
```

**注意：**

- `llmexcept` 本质上是一个挂载在上一条语句上的 Fallback 节点。
- `llmexcept` 相关的语句必须紧跟在其修饰的平级语句之后，如果是条件/循环语句，则跟随在条件块/循环体的书写结束之后，并与条件/循环语句保持一致的缩进。
- 如果触发重试，解释器将返回到上一条llm相关调用语句的起始处重新评估。
- 在循环中使用时，若挂载在循环体内的某条语句后，重试只会重新执行该行，而不会重启整个循环。
- 当任意变量赋值/条件语句/循环语句等无法通过 `__from_prompt__` 方法解析时，会触发 `llmexcept` 异常。
- 触发的 `retry` 会回到循环体对应的循环位置，不会触发整个循环的彻底重置。

---

## 6. 其它特性

### 6.1 位置无关路径解析

| 方法 | 说明 |
| ------ | ------ |
| `isys.entry_path()` | 获取入口文件的绝对路径 |
| `isys.entry_dir()` | 获取入口文件所在的目录 |
| `isys.project_root()` | 获取项目根目录（沙箱边界） |

**统一路径语义**: 所有相对路径都基于入口文件目录解析，无论在哪个 IBCI 文件中执行。

```ibci
import isys

str entry = isys.entry_path()   # /project/main.ibci
str dir = isys.entry_dir()     # /project
str root = isys.project_root() # /project
```

### 6.2 动态宿主机制

支持在完全隔离的环境中运行子脚本：

```ibci
import host
import isys

dict policy = {"isolated": True, "registry_isolation": True, "inherit_variables": False}
# 子环境有独立的入口文件、路径管理、插件发现
host.run_isolated("./sub/child.ibci", policy)
```

`./sub/child.ibci` 启动运行后，将会是一个全新的独立 IBC-Inter 实例，会独立进行一次全新的compile以及解释运行。
因此，并不要求 `child.ibci` 在主环境启动运行之前存在。动态宿主的机制允许 `child.ibci` 在主环境运行时被动态生成。

**子环境特性**：

- 完全独立的 Engine 实例
- 独立的入口文件和路径上下文
- 独立的插件发现机制
- 默认不继承父环境变量

### 6.3 插件系统

IBC-Inter 允许用户使用python编写自己的第三方插件，以扩展其功能。

**插件发现机制**：

- 插件文件必须是python文件，且必须放置在目标工程的 `./plugins` 目录下。
- `_spec.py`是插件的规范文件，包含插件的元数据，如虚表、函数名、函数参数列表、函数返回值等。
- 插件目前暂时只允许定义独立的class，并通过虚表声明相关函数的存在，其注册机制尚未完善，需等待作者后续更新。
- 插件书写方式请参考：`ibci_modules\ibci_file` 文件夹下的第一方插件。IBC-Inter的插件注册是非侵入式的，无需显式import任何内核模块。
- **注意**：`ibci_modules\ibci_ai` 等插件由于其特殊性，必须继承内核中的核心类，不建议第三方插件参考。

---

## 7. 注意事项

1. **插值迭代限制**:
   目前不支持 `for i in @~ ... $auto[i] ... ~:` 这种更灵活的语句，现阶段建议使用中间变量作为替代。
2. **重试上限限制**:
   LLM 调用重试次数可通过 `ai.set_retry(n)` 进行配置，默认值为 3 次。不建议设置为 0(无限重试)，这容易导致循环失控。
3. **If/While 条件中的 llmexcept**:
   `llmexcept` 是独立的语法成分，直接保护前一个同级语句。无需也不应当与 `try` 配合使用。
4. **Mock 局限性**:
   目前的内置 Mock 机制尚无法完美模拟复杂的 `retry` 链路，建议开发时配合真实 API 调试。
