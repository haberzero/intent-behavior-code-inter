## 7. 行为描述语句（LLM 调用）

### 7.1 即时行为

```ibci
str joke = @~ 讲一个关于程序员的笑话 ~
int answer = @~ 1+1 等于几？只答数字 ~
bool ok = @~ 这句话包含负面情绪吗？只答 1 或 0 ~
```

行为表达式中可以内插变量（通过 `$变量名`）：

```ibci
str name = "Alice"
str greeting = @~ 用 $name 打个招呼，中文 ~
```

插值时调用变量的 `__to_prompt__()` 方法将其转换为提示词文本。

### 7.2 类型约束与输出格式

左值类型自动决定 LLM 的输出约束（通过 `__outputhint_prompt__`）和解析方式（通过 `__from_prompt__`）：

```ibci
int x     = @~ 1+1 是多少 ~       # 约束：只返回整数
float f   = @~ pi 约等于多少 ~    # 约束：只返回浮点数
bool b    = @~ 今天是晴天吗 ~      # 约束：只返回 0 或 1
list[str] tags = @~ 给这段文字打3个标签，JSON数组格式 ~
```

### 7.3 行为表达式在控制流中

AI 可以直接驱动条件判断：

```ibci
str input = "我今天很难过"

if @~ $input 包含负面情绪吗？只答 1 或 0 ~:
    print("检测到负面情绪")
else:
    print("情绪正常")
```

AI 驱动循环条件（for 的 AI 版本）：

```ibci
int count = 0
for @~ $count 小于 3 吗？只回答 1 或 0 ~:
    count = count + 1
    print("计数: " + (str)count)
```

> **注意**：行为描述语句在条件上下文中会被隐式转换为 `bool` 类型，`bool` 的 `__from_prompt__` 要求 LLM 只输出 `0` 或 `1`。

### 7.4 延迟执行行为

延迟执行通过 `fn NAME = lambda: EXPR` / `fn NAME = snapshot: EXPR` 语法声明。`lambda` 在每次调用时求值；`snapshot` 在定义时捕获意图上下文快照，调用时与调用处意图完全隔离。

#### lambda

延迟执行，每次调用时使用**调用处**的当前意图上下文（调用处意图完全敏感）：

```ibci
# 无参 lambda（使用调用时意图栈），表达式侧返回类型标注（D2）
fn compute = lambda -> int: @~ 根据 $x 计算一个结果 ~
# 此时不会执行 LLM 调用

int x = 5
int result = compute()   # 调用时触发 LLM，使用当前 x 和意图栈
```

**带参数（lambda 是词法闭包 + 参数）**：

```ibci
fn translate = lambda(str text) -> str: @~ 翻译 $text ~
str r = translate("hello")

fn add = lambda(int a, int b) -> int: a + b
int s = add(3, 4)
```

**lambda 意图语义**（完整规则见 `docs/design/INTENT_SYSTEM_DESIGN.md` §9.4）：
- 定义时**不捕获**任何意图上下文
- 调用时使用调用处的持久意图栈（`@+` 累积）和一次性意图（`@` smear）
- 作为高阶函数参数传出后，调用时使用的仍是**调用点**的意图栈（不是定义处）
- `lambda` 延迟对象可以自由作为高阶函数参数传递（M2 落地后限制已移除）

#### snapshot

延迟执行，定义时对当前意图栈进行 `fork()` 快照（与 lambda 的区别在于意图冻结）：

```ibci
# 无参 snapshot（捕获定义时意图上下文），表达式侧返回类型标注（D2）
@+ 聚焦于正面回答
fn handler = snapshot -> str: @~ 根据 $context 生成回复 ~
@-   # 移除刚才添加的意图

# handler 持有定义时的意图栈快照，调用时绝对不受后续意图变化影响
str reply = handler()
```

**带参数**：

```ibci
fn translate = snapshot(str text) -> str: @~ 翻译 $text ~
str r = translate("hello")
```

**snapshot 意图语义**（完整规则见 `docs/design/INTENT_SYSTEM_DESIGN.md` §9.3）：
- 定义时 `fork()` 当时的完整意图上下文，存储为 `frozen_intent_ctx`
- 调用时**绝对忽略**调用处的所有意图（持久栈、`@` smear、`@!` 排他）
- `snapshot` 是 IBCI 中唯一"确定无状态、确定可重入"的延迟对象

#### 完整语法形式（8 种，lambda/snapshot 对称）

返回类型标注写在**表达式侧**（`fn f = lambda -> TYPE: EXPR`，D2）：

| 形式 | 语法 |
|------|------|
| 无参，无返回类型标注 | `fn f = lambda: EXPR` |
| 无参，有返回类型标注 | `fn f = lambda -> TYPE: EXPR` |
| 带参，无返回类型标注 | `fn f = lambda(PARAMS): EXPR` |
| 带参，有返回类型标注 | `fn f = lambda(PARAMS) -> TYPE: EXPR` |
| 无参 snapshot | `fn f = snapshot: EXPR` |
| 无参 snapshot，有返回类型 | `fn f = snapshot -> TYPE: EXPR` |
| 带参 snapshot | `fn f = snapshot(PARAMS): EXPR` |
| 带参 snapshot，有返回类型 | `fn f = snapshot(PARAMS) -> TYPE: EXPR` |

其中 `TYPE` 可以是任意类型（包括泛型如 `tuple[int,str]`、`list[str]`，以及用户自定义类名）：

```ibci
fn add = lambda(int a, int b) -> int: a + b
fn greet = lambda(str name) -> str: "Hello, " + name
fn make_pair = lambda(int n, str s) -> tuple[int,str]: (n, s)
```

**已废弃的声明侧返回类型语法**（产生 PAR_INVALID_SYNTAX 编译错误）：
```ibci
int fn f = lambda: EXPR            # PAR_INVALID_SYNTAX：声明侧返回类型已废弃（D1）
str fn f = lambda(PARAMS): EXPR    # PAR_INVALID_SYNTAX
```

#### 意图模式对比

| 关键字 | 语义 | 意图栈（完整规则见 §9） |
|--------|------|--------|
| `lambda` | 延迟，调用时执行 | 调用时的意图栈（完全敏感） |
| `snapshot` | 延迟，定义时冻结意图 | 定义时的意图栈快照（完全免疫调用处意图） |
| 无关键字（即时） | 立即执行 | 执行时的意图栈 |

### 7.5 命名模型路由（`@NAME~`）

通过 `@` 后跟模型名称前缀，可以将行为表达式路由到指定的命名模型：

```ibci
import ai

# 注册命名模型
ai.register_model("WHISPER", "https://api.openai.com/v1", env("KEY"), "whisper-1")

# 路由到命名模型
str transcript = @WHISPER~ 识别这段音频的内容 ~

# 无前缀的 @~ 使用默认模型
str greeting = @~ 打个招呼 ~
```

**规则**：

| 语法 | 行为 |
|------|------|
| `@~ ... ~` | 使用 `ai.set_config()` 配置的默认模型 |
| `@NAME~ ... ~` | 使用 `ai.register_model("NAME", ...)` 注册的命名模型 |
| 未注册的 `NAME` | 运行时错误（真实 LLM 模式下） |

- 模型名称**区分大小写**（`@GPT4o~` 与 `@gpt4o~` 是不同的模型）
- 模型名称支持字母+数字（如 `@GPT4o~`、`@WHISPER~`）
- MOCK/TESTONLY 模式下，未注册的模型名称不会报错（MOCK 拦截在路由之前）

### 7.6 多模态 payload 协议（`__payload_prompt__`）

`__payload_prompt__` 是 `__to_prompt__` 的多模态增强版本，允许类返回结构化 content block 而非纯文本。IBCI 内置的 `audio`/`image`/`video` 类型已实现该协议，可直接插值到 `@~ ... ~` 中：

```ibci
import file

image photo = image.from_file("cat.png")
str caption = @~ 请描述这张图片：$photo ~
```

**内置 media 类型（G6 之后）**：

| 类型 | 构造方式 | field | I/O method |
|------|---------|-------|-----------|
| `audio` | `audio.from_file(path)` | `format` | `data()` |
| `image` | `image.from_file(path)` | `format` | `data()` |
| `video` | `video.from_file(path)` | `format` | `data()` |

```ibci
import file

audio rec = audio.from_file("interview.wav")
str fmt = rec.format     # field，只内省，无 I/O
str b64 = rec.data()     # method，惰性读取字节并按需 base64 物化
```

用户自定义类型如需实现 `__payload_prompt__`，需自己负责字节物化与格式化；`file` 模块不再提供 `read_base64`，可用 `file.read_bytes(path)` 读取原始字节后自行编码。

**协议优先级**：当变量插值到行为表达式时，运行时优先调用 `__payload_prompt__`；若未定义则回退到 `__to_prompt__`。纯文本路径完全不受影响——只有当 content 中包含结构化 block 时才会切换为多模态 payload 模式。

**向后兼容**：仅实现了 `__to_prompt__` 的类型行为不变；`__payload_prompt__` 是可选扩展，不替代现有协议。

---
