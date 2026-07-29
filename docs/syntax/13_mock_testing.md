# IBCI MOCK 测试机制

> 本文档详细说明 IBCI 的 MOCK 指令系统，用于在没有真实 LLM API 的环境中测试 LLM 相关功能。
>
> 语法参考见 `docs/syntax/07_behavior_expressions.md` 与 `docs/syntax/08_llm_functions.md`。

---

## 1. 启用 MOCK 模式

```ibci
import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
```

在 TESTONLY 模式下，所有 LLM 调用不会连接真实 API，而是解析行为表达式或 LLM 函数中的 MOCK 指令返回预设值。

---

## 2. MOCK 指令格式

MOCK 指令写在行为表达式（`@~...~`）或 LLM 函数的 `__user__` 块中。

### 2.1 基本类型指令

| 指令 | 说明 | 示例 |
|------|------|------|
| `MOCK:STR:value` | 返回指定字符串 | `MOCK:STR:hello world` |
| `MOCK:INT:value` | 返回指定整数字符串 | `MOCK:INT:42` |
| `MOCK:FLOAT:value` | 返回指定浮点字符串 | `MOCK:FLOAT:3.14` |
| `MOCK:BOOL:value` | 返回 `1`（True）或 `0`（False） | `MOCK:BOOL:True` |
| `MOCK:LIST:value` | 返回 JSON 数组字符串 | `MOCK:LIST:[1,2,3]` |
| `MOCK:DICT:value` | 返回 JSON 对象字符串 | `MOCK:DICT:{"a":1}` |

### 2.2 布尔快捷指令

| 指令 | 返回值 |
|------|--------|
| `MOCK:TRUE` | `"1"`（bool True） |
| `MOCK:FALSE` | `"0"`（bool False） |

### 2.3 失败与恢复指令

| 指令 | 说明 |
|------|------|
| `MOCK:FAIL` | 始终返回模糊值，触发 llmexcept；重试也无法成功，最终抛 `LLMRetryExhaustedError` |
| `MOCK:REPAIR` | 首次返回模糊值触发 llmexcept，第二次成功，默认返回 `"1"` |
| `MOCK:REPAIR:STR:v` | 首次失败，重试后返回指定字符串 |
| `MOCK:REPAIR:INT:v` | 首次失败，重试后返回指定整数 |
| `MOCK:REPAIR:BOOL:TRUE` | 首次失败，重试后返回 True |
| `MOCK:REPAIR:FLOAT:v` | 首次失败，重试后返回指定浮点数 |
| `MOCK:REPAIR:LIST:v` | 首次失败，重试后返回指定列表 |
| `MOCK:REPAIR:DICT:v` | 首次失败，重试后返回指定字典 |

> `MOCK:REPAIR:<FALLBACK>` 支持任意基本类型指令作为回退值。

### 2.4 序列指令

| 指令 | 说明 |
|------|------|
| `MOCK:SEQ:[v1,v2,...] key` | 按序返回值，`key` 为去重标识符 |

- 必须使用方括号格式 `MOCK:SEQ:[v1,v2,...] key`
- `FAIL`、`TRUE`、`FALSE` 可作为哨兵成员嵌入序列中
- 同一 `key` 的多次调用按序返回，超出序列长度后循环或返回空字符串

---

## 3. 使用示例

### 3.1 基本 MOCK

```ibci
import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")

str reply = @~ MOCK:STR:hello world ~
print(reply)    # hello world

int n = @~ MOCK:INT:42 ~
print((str)n)   # 42
```

### 3.2 MOCK + llmexcept

```ibci
import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")

# MOCK:FAIL 始终失败，需要 try/except 兜底
try:
    int result = @~ MOCK:FAIL 请提取数字 ~
    llmexcept:
        retry "请只返回一个整数"
except LLMRetryExhaustedError as e:
    print("重试耗尽: " + e.message)
```

### 3.3 MOCK:REPAIR 模拟恢复

```ibci
import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")

# 首次失败，重试后返回 99
int result = @~ MOCK:REPAIR:INT:99 ~
llmexcept:
    retry "请只返回一个整数"
print((str)result)   # 99
```

### 3.4 MOCK:SEQ 序列

```ibci
import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")

str s1 = @~ MOCK:SEQ:[first,second,third] mykey ~   # first
str s2 = @~ MOCK:SEQ:[first,second,third] mykey ~   # second
str s3 = @~ MOCK:SEQ:[first,second,third] mykey ~   # third
```

### 3.5 在控制流中使用 MOCK

```ibci
import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")

if @~ MOCK:TRUE 今天天气好吗？ ~:
    print("条件为真")

if @~ MOCK:FALSE 今天下雨吗？ ~:
    print("不会执行")
else:
    print("条件为假")
```

### 3.6 LLM 函数 MOCK

LLM 函数 MOCK 时，`__user__` 块必须**只包含** MOCK 指令：

```ibci
import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")

llm 测试函数(str input) -> str:
__sys__
任何系统提示词
__user__
MOCK:STR:mock_result
llmend

str r = 测试函数("anything")
print(r)   # mock_result
```

---

## 4. 命名模型路由的 MOCK

```ibci
import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
ai.register_model("WHISPER", "TESTONLY", "TESTONLY", "TESTONLY")

# 路由到命名模型
str transcript = @WHISPER~ MOCK:STR:named_result ~
print(transcript)   # named_result
```

在 MOCK 模式下，未注册的模型名称不会报错（MOCK 拦截在路由之前）。

---

## 5. 注意事项

1. **MOCK 模式不处理提示词内容**：意图注释、`__outputhint_prompt__` 等对 MOCK 返回值无影响。MOCK 只解析指令本身。
2. **`retry "hint"` 中的 hint 不会作为 MOCK 指令解析**：retry hint 是追加给 LLM 的系统提示词，不是 MOCK 指令覆盖。使用 `MOCK:REPAIR:<FALLBACK>` 表达"失败一次后回退到指定值"。
3. **MOCK 模式无法验证真实 LLM 行为**：`__to_prompt__`/`__from_prompt__`/`__outputhint_prompt__` 协议对真实 LLM 的影响需要连接真实 API 才能测试。
