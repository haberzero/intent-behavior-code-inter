## 8. LLM 函数

> 本章描述 LLM 函数的定义与使用。面向已阅读行为描述语句章节的开发者。覆盖 `llm ... llmend` 语法、`__sys__`/`__user__` 提示词段、参数替换与 `__llmretry__` 重试块。

### 8.1 定义

```ibci
llm 翻译(str 文本, str 目标语言) -> str:
__sys__
你是一个专业翻译，直接输出翻译结果，不加任何解释。
__user__
请将 "$文本" 翻译为 $目标语言。
llmend
```

- 关键字 `llm` 开头，用 `llmend` 结束
- `__sys__` 块：系统提示词
- `__user__` 块：用户提示词（支持 `$变量名` 插值）
- 函数体**不需要缩进**（顶格书写），避免空格被作为提示词内容传入
- 返回类型**必须显式声明**（`-> TYPE` / `-> auto`）；缺失产生 `SEM_MISSING_RETURN_ANNOTATION` 编译错误

### 8.2 调用

```ibci
str result = 翻译("Hello World", "中文")
print(result)
```

### 8.3 带重试提示词

```ibci
llm 解析数字(str 文本) -> int:
__sys__
你是一个数字提取专家。
__user__
从 "$文本" 中提取一个整数，只返回数字本身。
__llmretry__
请务必只返回一个纯整数，不要有任何其他文字或标点。
llmend
```

`__llmretry__` 块：当 `__from_prompt__` 解析失败触发 llmexcept 重试时，会将此内容附加为额外系统提示词。

### 8.4 返回类型解析

- **标量返回**：`int` / `float` / `str` / `bool` 经内建解析器从模型输出提取（`bool` 识别 `True/False` / `true/false` 等形态）。
- **容器返回**：`list[T]` / `dict[K,V]` 等容器类型按容器解析——模型输出按元素类型逐个解析进容器（如 `-> list[int]` 解析数字列表、`-> dict[str,int]` 解析键值对）。**`auto` 返回**走旧路径按字符串处理。
- **用户类返回**：经 `__from_prompt__` 解析（契约见 `docs/syntax/06_oop.md` §6.7），可配合 `__validate_prompt__` 校验。
- **`-> void` 边界**：返回类型声明为 `void` 时编译通过，但运行期解析无目标类型会抛 `LLMParseError`——当前**未声明支持**（待评估：编译期拦截或正式支持）；生产代码应避免 `llm ... -> void`。

---

## 深入指引

- LLM 函数实现：docs/architecture/04_vm_interpreter.md
