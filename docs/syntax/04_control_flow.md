## 4. 控制流

> 本章描述 IBCI 的控制流语句。面向已阅读运算符章节的开发者。覆盖 if/while/for/switch 条件分支与循环、try/except/raise 异常处理、pass 空语句。

### 4.1 条件语句

```ibci
int x = 10

if x > 5:
    print("大于 5")
elif x == 5:
    print("等于 5")
else:
    print("小于 5")
```

三元表达式（C 风格 `?:`）：

```ibci
int result = x > 5 ? 1 : 0
```

也支持 Python 风格的三元表达式：

```ibci
int result = 1 if x > 5 else 0
```

### 4.2 while 循环

```ibci
int i = 0
while i < 5:
    print((str)i)
    i = i + 1
```

### 4.3 for 循环

遍历列表：

```ibci
list[str] names = ["Alice", "Bob", "Charlie"]
for str name in names:
    print(name)
```

遍历范围（整数序列）：

```ibci
for int i in range(5):         # 0,1,2,3,4
    print((str)i)

for int i in range(2, 6):      # 2,3,4,5
    print((str)i)

for int i in range(0, 10, 2):  # 0,2,4,6,8（步长为 2）
    print((str)i)
```

遍历字典（使用 `items()`）：

```ibci
dict[str,int] d = {"a": 1, "b": 2}
for any pair in d.items():
    # pair 是 [key, value] 列表
    print((str)pair)
```

支持 `__iter__` 协议的自定义类实例也可以直接用于 `for` 循环。

### 4.4 break / continue

```ibci
for int i in range(10):
    if i == 5:
        break
    if i % 2 == 0:
        continue
    print((str)i)   # 输出 1, 3
```

### 4.5 pass 空语句

`pass` 是空操作语句，用于空函数体、空类体等占位场景：

```ibci
func placeholder() -> void:
    pass
```

### 4.6 switch / case

```ibci
str status = "ok"

switch status:
    case "ok":
        print("成功")
    case "error":
        print("失败")
    default:
        print("未知")
```

配合 Enum：

```ibci
class Color(Enum):
    str RED   = "RED"
    str GREEN = "GREEN"
    str BLUE  = "BLUE"

Color c = Color.BLUE

switch c:
    case Color.RED:
        print("红")
    case Color.BLUE:
        print("蓝")
    default:
        print("其它")
```

### 4.7 try / except / raise / finally

IBCI 提供与传统命令式语言一致的 `try` / `except` / `raise` / `finally` 异常机制，用于处理"显式抛出的语言级异常"。
处理 LLM 调用的不确定性请使用 `llmexcept`（见第 10 节）—— 二者**互补**而非竞争：

| 场景 | 推荐机制 |
|------|----------|
| LLM 输出无法解析、需要重试调整提示词 | `llmexcept` / `retry` |
| 业务逻辑显式 `raise` 出来的错误 | `try` / `except` |
| LLM 重试耗尽后的兜底处理 | `try except LLMRetryExhaustedError` |
| 在没有 `llmexcept` 保护时的 LLM 失败兜底 | `try except LLMParseError` |

#### 4.7.1 基本语法

```ibci
try:
    int x = (int)"not a number"        # 强转失败会抛出运行时异常
except Exception as e:
    print("捕获到异常")
    print(e.message)
finally:
    print("总是执行")
```

#### 4.7.2 显式 raise

```ibci
func divide(int a, int b) -> int:
    if b == 0:
        raise Exception("division by zero")
    return a / b

try:
    int q = divide(10, 0)
except Exception as e:
    print(e.message)
```

#### 4.7.3 内置异常类型层次

IBCI 内置以下异常类型（字段明细见 §4.7.4）：

```
Exception
  └── LLMError
        ├── LLMParseError            # LLM 输出无法解析为目标类型
        ├── LLMRetryExhaustedError   # llmexcept 重试次数耗尽
        └── LLMCallError             # LLM provider 层硬失败（网络/鉴权等；VM 自动抛出，跳过 llmexcept retry）
```

`except` 按继承链匹配：`except Exception` 可捕获其下所有派生异常；`except LLMError` 可同时捕获三个具体 LLM 错误。

```ibci
# 精确匹配
try:
    str x = @~ MOCK:FAIL bad_parse ~
    print(x)
except LLMParseError as e:
    print("解析失败：" + e.message)

# 基类匹配
try:
    str result = @~ MOCK:FAIL exhausted ~
    llmexcept:
        retry "只返回数字"
except LLMError as e:
    print("LLM 出问题：" + e.message)

# 顶层兜底
try:
    str x = @~ MOCK:FAIL anything ~
except Exception as e:
    print("意外失败：" + e.message)
```

#### 4.7.4 内置异常类型字段

| 类型 | 字段 | 含义 |
|------|------|------|
| `Exception` | `message: str` | 错误描述文本 |
| `LLMError` | `message: str`, `raw_response: str` | LLM 失败时返回的原始内容（如有） |
| `LLMParseError` | `message: str`, `raw_response: str`, `type_name: str` | 内容字段同 `LLMError`；`type_name` 为解析失败的目标类型名；语义为"LLM 输出无法解析为目标类型" |
| `LLMRetryExhaustedError` | `message: str`, `raw_response: str`, `max_retry: int` | 内容字段同 `LLMError`；`max_retry` 为重试次数上限；`message` 含 `retry` 关键字 |
| `LLMCallError` | `message: str`, `raw_response: str`, `provider_error: str` | 比 `LLMError` 多 `provider_error`（HTTP 状态、网络错误等）；VM 在 provider 层失败时自动抛出，直接跳过 llmexcept retry；用户也可手动 `raise LLMCallError(...)` |

#### 4.7.5 用户自定义异常

继承 `Exception` 或任意内置 LLM 异常类型即可定义自定义异常：

```ibci
class AppError(Exception):
    func __init__(self, str msg) -> auto:
        self.message = msg

class NetworkError(AppError):
    int code
    func __init__(self, str msg, int code) -> auto:
        self.message = msg
        self.code = code

try:
    raise NetworkError("connection refused", 503)
except AppError as e:
    print(e.message)        # 能由父类 except 捕获
```

> **类型窄化**：`except X as e:` 中 `e` 的编译期类型正确窄化为 `X`，
> 可直接访问子类专属字段，无需 `(X)e` 强转：
>
> ```ibci
> try:
>     raise NetworkError("conn refused", 503)
> except NetworkError as e:
>     print((str)e.code)   # ✅ 直接访问 .code
> ```
>
> 直接访问基类字段（如 `e.message`）不受此限制影响。
---

## 深入指引

- 控制流实现与异常模型：docs/architecture/04_vm_interpreter.md
