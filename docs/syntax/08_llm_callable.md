## 8. LLM 可调用类

> 本章描述 LLM 可调用类的定义与使用。面向已阅读行为描述语句章节的开发者。覆盖 `__llm_call__` 协议方法、装配配置字典（`user_prompt` / `prompt_slots` / `expected_type`）、实例直接调用与统一消费入口（`run_batch` / `stream`）。
>
> `llm ... llmend` 函数语法已废除：命名 LLM 调用统一由 **LLMCallable 可调用类实例** 承载——定义一次、任意调用，经统一装配入口消费。

### 8.1 定义

```ibci
class 翻译:
    func __llm_call__(self, any 文本, any 目标语言) -> dict:
        return {"user_prompt": "请将 \"" + str(文本) + "\" 翻译为 " + str(目标语言) + "。", "prompt_slots": [{"kind": "user_sys", "text": "你是一个专业翻译，直接输出翻译结果，不加任何解释。"}]}
```

- 类实现 **`LLMCallable`** 协议：定义 `__llm_call__` 方法即满足（`satisfies_protocol(..., "llm_callable")` 唯一判定）。
- `__llm_call__` 返回**装配配置字典**，键：
  - `user_prompt`：用户提示文本（**必需**）
  - `prompt_slots`：自定义语义槽列表 `[{"kind": str, "text": str}]`（如角色设定；任意 kind，统一呈现）
  - `expected_type`：返回解析目标类型名（如 `int` / `list[int]` / 用户类名）；缺省按字符串解析
  - `output_hint`：输出格式约束提示
  - `model`：具名模型路由标识

### 8.2 调用

```ibci
翻译 t = 翻译()
str result = t("Hello World", "中文")
print(result)
```

- **实例直接调用** `t(args)`：参数按位绑定到 `__llm_call__` 的非 `self` 参数；未声明参数时无参调用。调用即一次 LLM 调用（经统一装配入口 + 统一 worker 执行）。
- 同一类可实例化多次，各实例独立装配。
- 调用表达式静态类型为动态 `any`——LLM 结果类型由运行时 `expected_type` 决定（渐进类型语义），按声明目标类型赋值即可（如 `int v = t(...)`）。

### 8.3 统一消费入口

| 入口 | 语义 |
|------|------|
| `ai.run_batch(target, items)` | 批量调用：行为值（items 逐项绑参）或 llm 可调用类实例（每 item 一次调用，`__llm_call__(self, any item)` 声明 item 参时逐项参数化） |
| `ai.stream_call(target)` | 流式调用：返回 Waitable，`await` 后得到完整文本 |
| `ai.stream_channel(target)` | 流式调用：返回 stream Channel，逐块 `recv` 增量消费 |
| 行为语句 `@~ ... ~` | 匿名 LLM 调用语法糖（行为表达式，独立语法） |

### 8.4 可选协议方法

- **`__intent__`**（可选）：`func __intent__(self, dict intents) -> dict` —— 装配时改写进入本次调用的意图三层（`active` / `global` / `merged`）。入参为三层 dict；返回 dict 的键为三层任意子集——存在的键替换对应层（消解/增删/重排），缺失的键保持原层；显式空列表清空该层。未声明时意图原样透传。
- **`__retry__`**（可选）：`func __retry__(self) -> dict` —— 声明**调用级默认重试策略**（高阶化 retry）。返回策略字典：
  - `max_retry`（`int` ≥ 1，缺省 3）：本次调用最多执行的轮数；
  - `hint`（`str`）：每轮失败后注入下一轮调用的补充要求（经标准多轮对话的 `message_history` 回喂，不拼入系统提示词——承接旧 `__llmretry__` 段语义）。
  
  调用失败（LLM 结果不确定）时按策略自动重试：失败响应与解析错误随 `hint` 自动回喂；达到 `max_retry` 仍不确定，结果交语句层（`llmexcept` 接管 / 无保护时抛解析错误）。未声明该方法时不自动重试（一次调用即交语句层）。声明空字典（`return {}`）启用默认 `max_retry=3`。该策略与语句级 `llmexcept` 的 `retry` 指令互补（见 `docs/syntax/10_robustness.md` §10.5）。

### 8.5 返回类型解析

- **标量**：`int` / `float` / `str` / `bool` 经内建解析器从模型输出提取（`bool` 识别 `True/False` / `true/false` 等形态）。
- **容器**：`list[T]` / `dict[K,V]` 等容器类型按容器解析——模型输出按元素类型逐个解析进容器（如 `list[int]` 解析数字列表、`dict[str,int]` 解析键值对）。
- **用户类**：经 `__from_prompt__` 解析（契约见 `docs/syntax/06_oop.md` §6.7），可配合 `__validate_prompt__` 校验。
- **void 边界**：`expected_type` 不声明可解析目标时按字符串解析；需要纯副作用调用时使用行为表达式（`@~ ... ~`）。

---

## 深入指引

- LLM 可调用类装配与统一消费：`docs/architecture/` LLM 执行章节