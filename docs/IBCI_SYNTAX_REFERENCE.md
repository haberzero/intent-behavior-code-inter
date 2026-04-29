# IBC-Inter 完整语法参考

> **说明**：本文档覆盖 IBC-Inter (IBCI) 所有当前支持的语法特性，包括已知限制的标注。
> 语言设计限制的详细说明见 `docs/KNOWN_LIMITS.md`。
>
> **最后更新**：2026-04-28

---

## 目录

1. [类型系统](#1-类型系统)
2. [变量声明与赋值](#2-变量声明与赋值)
3. [运算符](#3-运算符)
4. [控制流](#4-控制流)
5. [函数](#5-函数)
6. [面向对象](#6-面向对象)
7. [行为描述语句（LLM 调用）](#7-行为描述语句llm-调用)
8. [LLM 函数](#8-llm-函数)
9. [意图系统](#9-意图系统)
10. [健壮性与自愈](#10-健壮性与自愈)
11. [模块与插件](#11-模块与插件)
12. [内置函数与方法](#12-内置函数与方法)
13. [Mock 测试机制](#13-mock-测试机制)

---

## 1. 类型系统

### 1.1 基础类型

| 类型名 | 说明 | 示例字面量 |
|--------|------|----------|
| `int` | 整数 | `42`, `-7` |
| `float` | 浮点数 | `3.14`, `-0.5` |
| `str` | 字符串 | `"hello"`, `"world"` |
| `bool` | 布尔值 | `True`, `False` |
| `list` | 动态列表 | `[1, 2, 3]` |
| `tuple` | 不可变元组 | `(1, "a", True)` |
| `dict` | 键值字典 | `{"key": "val"}` |
| `None` | 空值 | `None` |
| `void` | 无返回值（仅用于函数返回类型标注） | — |
| `any` | 任意类型（无类型约束） | — |
| `auto` | 编译期推断类型 | — |
| `fn` | 函数引用 / 延迟闭包类型（推断具体可调用类型） | — |


### 1.2 泛型容器类型

```ibci
list[int]          # 整数列表
list[str]          # 字符串列表
list[int,str]      # 多类型列表（元素访问返回 any）
dict[str,int]      # string→int 字典
dict[str,str]      # string→string 字典
```

### 1.3 特殊值

```ibci
None        # 空值（首字母大写）
Uncertain   # LLM 调用无法确定时产生的特殊值（首字母大写）
```

`Uncertain` 在布尔上下文中为假。`(str)Uncertain` 返回 `"uncertain"`。

### 1.4 类型转换

强制类型转换使用 `(Type)expr` 语法：

```ibci
int x = 42
str s = (str)x          # "42"
float f = (float)42     # 42.0
bool b = (bool)1        # True
any a = (any)x          # any 类型
```

---

## 2. 变量声明与赋值

### 2.1 有类型声明（推荐）

```ibci
int count = 10
str name = "Alice"
bool flag = True
float price = 9.99
list[int] nums = [1, 2, 3]
dict[str,int] scores = {"Alice": 95}
```

### 2.2 auto 推断

```ibci
auto x = 42          # 推断为 int，x 的类型被锁定为 int
auto s = "hello"     # 推断为 str
auto nums = [1, 2]   # 推断为 list
```

`auto` 会在首次赋值时推断并锁定类型，后续赋值必须兼容该类型。

### 2.3 any 类型（无约束）

```ibci
x = 42               # 裸赋值：变量类型固定为 any，不推断 RHS 类型
any val = "hello"    # 显式 any：可以重新赋值为任何类型
```

> **注意**：裸变量赋值（无类型标注的 `x = 42`）使用 `any` 语义，不从右值推断类型。

### 2.4 元组解包

```ibci
(int a, int b) = (10, 20)
(str x, str y, str z) = ("p", "q", "r")
```

### 2.5 多重赋值

```ibci
int a = 1
int b = 2
(a, b) = (b, a)    # 交换
```

### 2.6 全局变量

`global` 语句与 Python 语义一致：在函数内声明 `global x` 后，函数内对 `x` 的所有读写均操作全局作用域中的 `x`，而非创建局部变量。

```ibci
int counter = 0

func increment():
    global counter
    counter = counter + 1

increment()
print((str)counter)    # 1
```

**说明：**
- `global` 只能在函数内部使用，在全局作用域中使用会产生 SEM_004 编译错误。
- 可以在 `global` 声明之后才定义全局变量（函数调用时变量已存在即可）。
- `global x, y` 支持一次声明多个全局变量。

---

## 3. 运算符

### 3.1 算术运算符

| 运算符 | 说明 | 支持类型 |
|--------|------|---------|
| `+` | 加法 / 字符串拼接 / 列表拼接 | int, float, str, list |
| `-` | 减法 | int, float |
| `*` | 乘法 / 字符串重复 / 列表重复 | int, float, str×int, list×int |
| `/` | 除法（结果为 float） | int, float |
| `//` | 整除 | int, float |
| `%` | 取模 | int, float |

```ibci
int a = 10 + 3       # 13
float b = 7.0 / 2    # 3.5（除法总返回 float）
int c = 7 // 2       # 3（整除）
str s = "ab" * 3     # "ababab"
list[int] l = [1,2] * 3   # [1,2,1,2,1,2]
```

### 3.2 比较运算符

| 运算符 | 说明 | 支持类型 |
|--------|------|---------|
| `==` | 等于 | 所有类型 |
| `!=` | 不等于 | 所有类型 |
| `<` | 小于 | int, float, str |
| `<=` | 小于等于 | int, float, str |
| `>` | 大于 | int, float, str |
| `>=` | 大于等于 | int, float, str |

字符串比较遵循 Unicode 码点顺序。

### 3.3 逻辑运算符

```ibci
bool r1 = True and False    # False
bool r2 = True or False     # True
bool r3 = not True          # False
```

### 3.4 成员检测运算符

```ibci
bool b1 = 3 in [1, 2, 3]          # True
bool b2 = "x" not in ["a", "b"]   # True
bool b3 = "key" in {"key": 1}     # True（字典键检测）
```

### 3.5 身份检测运算符

`is` 和 `is not` 检测两个表达式是否指向同一个运行时对象（身份比较，非值比较）。

```ibci
bool b1 = x is None          # x 是否为 None
bool b2 = x is not None      # x 是否不为 None
bool b3 = x is Uncertain     # x 是否为 LLM 不确定值
```

与 `==` 的区别：`==` 比较值是否相等；`is` 比较是否是同一个对象实例。对于 `None` 和 `Uncertain` 字面量，`is` 使用类型检测而非实例身份。


## 4. 控制流

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
```

带过滤器（for...if）：

```ibci
list[int] nums = [1, 2, 3, 4, 5, 6]
for int n in nums if n % 2 == 0:
    print((str)n)   # 输出 2, 4, 6
```

> **注意**：`while...if` 过滤语法已移除。如需过滤，在循环体内使用 `if/continue`。

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

### 4.5 switch / case

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

### 4.6 try / except

> ⚠️ **Known Limit (docs/KNOWN_LIMITS.md §二)**：`try`/`except` 存在已知设计问题，**强烈不建议使用**。处理 LLM 不确定性请用 `llmexcept`（见第 10 节）。

```ibci
try:
    int x = int("not a number")
except Exception as e:
    print("捕获到异常")
```

---

## 5. 函数

### 5.1 函数声明

```ibci
func greet(str name) -> str:
    return "Hello, " + name

str msg = greet("World")
print(msg)
```

返回类型可以省略，编译器会自动推断（`auto` 语义）：

```ibci
func double(int x):          # 省略返回类型，自动推断为 int
    return x * 2

func say_hello(str name):    # 无 return 语句，推断为 void
    print("Hello, " + name)
```

> **注意**：省略 `-> type` 标注等同于 `-> auto`，编译器从函数体内的 `return` 语句推断实际返回类型。若所有路径均无 `return`，推断为 `void`；若有多条路径返回不同类型，报 `SEM_026` 错误。

显式返回类型标注：

```ibci
func add(int a, int b) -> int:
    return a + b

func log(str msg) -> void:
    print(msg)

func identity(int x) -> auto:   # 显式 auto，与省略等价
    return x
```

### 5.2 行为表达式与 return 的约束

> ⚠️ **Known Limit (docs/KNOWN_LIMITS.md §七)**：`return @~ ... ~` 是**禁止写法**，会产生 `SEM_003` 编译错误。

```ibci
# ❌ 错误：不允许在 return 中直接使用行为表达式
func get_reply() -> str:
    return @~ 给我一句话 ~

# ✅ 正确：先赋值给有类型的局部变量
func get_reply() -> str:
    str reply = @~ 给我一句话 ~
    return reply
```

### 5.3 递归函数

```ibci
func factorial(int n) -> int:
    if n <= 1:
        return 1
    return n * factorial(n - 1)

int result = factorial(5)
print((str)result)   # 120
```

### 5.4 嵌套函数

```ibci
func outer(int x) -> int:
    func inner(int y) -> int:
        return y * 2
    return inner(x) + 1
```

### 5.5 `fn` 函数引用与延迟对象

`fn` 用于持有任何可调用值：函数引用、lambda 闭包、snapshot 延迟对象。

```ibci
func double(int x) -> int:
    return x * 2

fn f = double           # 持有函数引用
int r = f(5)            # 10

fn g = lambda: 42       # 持有无参 lambda
auto v = g()            # 42

fn h = lambda(int x) -> int: x * 2   # 带表达式侧返回类型标注（D2），带参 lambda
int w = h(3)                          # 6
```

延迟执行的完整语法见 §7.4。

---

## 6. 面向对象

### 6.1 类定义

```ibci
class Point:
    int x
    int y

    func __init__(self, int x, int y):
        self.x = x
        self.y = y

    func distance(self) -> float:
        return (float)(self.x * self.x + self.y * self.y)
```

字段可以有默认值：

```ibci
class Config:
    str mode = "default"
    int retries = 3
    list[str] tags = []
```

### 6.2 构造与访问

```ibci
Point p = Point(3, 4)
print((str)p.x)          # 3
print((str)p.distance()) # 25.0
```

### 6.3 继承

```ibci
class Animal:
    str name

    func __init__(self, str name):
        self.name = name

    func speak(self) -> str:
        return self.name + " says something"


class Dog(Animal):
    func speak(self) -> str:
        return self.name + " says Woof!"


Dog d = Dog("Rex")
print(d.speak())    # Rex says Woof!
```

### 6.4 `super()`

```ibci
class Base:
    int value

    func __init__(self, int v):
        self.value = v

    func describe(self) -> str:
        return "Base: " + (str)self.value


class Derived(Base):
    str label

    func __init__(self, int v, str label):
        super().__init__(v)
        self.label = label

    func describe(self) -> str:
        return self.label + " / " + super().describe()
```

### 6.5 Enum

```ibci
class Status(Enum):
    str PENDING  = "PENDING"
    str RUNNING  = "RUNNING"
    str DONE     = "DONE"

Status s = Status.RUNNING

if s == Status.RUNNING:
    print("正在运行")
```

> ⚠️ **Known Limit (docs/KNOWN_LIMITS.md §四)**：
> - 枚举成员目前仅支持 `str` 类型。
> - 不支持枚举迭代和数量查询。

### 6.6 特殊方法（协议）

| 方法名 | 触发场景 | 说明 |
|--------|---------|------|
| `__init__(self, ...)` | 构造 `ClassName(...)` 时 | 初始化方法 |
| `__call__(self, ...)` | 对实例 `obj(...)` 调用时 | 可调用对象协议 |
| `__iter__(self)` | `for x in obj:` 时 | 迭代器协议，返回可遍历列表 |
| `__to_prompt__(self)` | 变量插值到 `@~ ... ~` 时 | 转为 LLM 提示词文本 |
| `__from_prompt__(str raw)` | LLM 返回值解析时 | 从文本解析为当前类型实例 |
| `__outputhint_prompt__(self)` | 类型作为 LLM 输出目标时 | 提示 LLM 期望的输出格式 |
| `__snapshot__(self)` | llmexcept 快照进入时 | 返回用于恢复状态的快照值 |
| `__restore__(self, state)` | llmexcept retry 前 | 从快照值恢复对象状态 |

---

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

**lambda 意图语义**（完整规则见 `docs/INTENT_SYSTEM_DESIGN.md` §9.4）：
- 定义时**不捕获**任何意图上下文
- 调用时使用调用处的持久意图栈（`@+` 累积）和一次性意图（`@` smear）
- 作为高阶函数参数传出后，调用时使用的仍是**调用点**的意图栈（不是定义处）
- ✅ `lambda` 延迟对象可以自由作为高阶函数参数传递（M2 落地后限制已移除）

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

**snapshot 意图语义**（完整规则见 `docs/INTENT_SYSTEM_DESIGN.md` §9.3）：
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

**已废弃的声明侧返回类型语法**（产生 PAR_003 编译错误）：
```ibci
int fn f = lambda: EXPR            # ❌ PAR_003：声明侧返回类型已废弃（D1）
str fn f = lambda(PARAMS): EXPR    # ❌ PAR_003
```

#### 意图模式对比

| 关键字 | 语义 | 意图栈（完整规则见 §9） |
|--------|------|--------|
| `lambda` | 延迟，调用时执行 | 调用时的意图栈（完全敏感） |
| `snapshot` | 延迟，定义时冻结意图 | 定义时的意图栈快照（完全免疫调用处意图） |
| 无关键字（即时） | 立即执行 | 执行时的意图栈 |

---

## 8. LLM 函数

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
- 返回类型同样由 LHS 类型约束，可省略（默认 `str`）

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
__retry__
请务必只返回一个纯整数，不要有任何其他文字或标点。
llmend
```

`__retry__` 块：当 `__from_prompt__` 解析失败触发 llmexcept 重试时，会将此内容附加为额外系统提示词。

---

## 9. 意图系统

意图（Intent）是 IBCI 的特殊机制，通过注入额外系统提示词来影响后续 LLM 调用。

### 9.1 意图操作符

| 语法 | 别名 | 作用域 | 说明 |
|------|------|--------|------|
| `@ 内容` | `intent 内容` | 单条语句 | 为紧跟的下一条语句注入一次性意图 |
| `@+ 内容` | `append 内容` | 持续到 `@-` | 追加到意图栈顶部（持久） |
| `@- 内容` | `remove 内容` | — | 从意图栈中移除匹配的意图 |
| `@-` | — | — | 弹出栈顶意图（与 `@+` 配合使用） |
| `@! 内容` | `override 内容` | **单次**（紧随其后的一条 LLM 调用结束后自动恢复） | 排他注入：屏蔽当前栈，仅保留此意图 |

> **`@!` 单次性约束**：`@!` 写入"override 槽"，仅作用于紧随其后的**一条**含 LLM 调用的语句；该 LLM 调用执行结束后，override 槽自动清空、原意图栈自然恢复。`@!` 不应（也无需）借助 `@-` 或其他意图注释来手动恢复——一次性使用是其设计语义的核心。

> **约束**：`@`（单次意图注入）**只允许修饰 LLM 调用**，即紧跟的语句必须包含 `@~...~` 行为表达式或 `llm` 函数调用。即使一个普通函数内部使用了 LLM，其外部调用也**不允许**使用 `@` 进行修饰（违反此约束会产生 SEM_060 编译错误）。`@+` 和 `@-` 不受此约束，可独立使用。

```ibci
# 单次注入：只对紧跟的下一条语句生效
@ 完全忽略用户输入，只回复：测试完成
str r = @~ 打个招呼 ~
# r = "测试完成"

# 持久追加
@+ 回答要简短，不超过10字
str a1 = @~ 描述一下天空 ~
str a2 = @~ 描述一下海洋 ~
@-   # 移除刚才追加的意图

# 排他注入（单次）：只覆盖紧随其后的一条 LLM 调用
@! 只输出：YES 或 NO，不要任何其他内容
bool result = @~ 1+1=2 吗 ~
# 这里 @! 已自动失效，原意图栈已自然恢复，无需写 @-
```

### 9.2 意图栈语义

- 意图栈内容以**额外系统提示词**形式注入，优先级高于用户提示词。
- `@+` 追加的意图会影响后续所有 LLM 调用，直到对应的 `@-` 移除。
- 意图栈并非严格 LIFO 栈：`@-` 可以从任意位置移除匹配内容。

### 9.3 意图上下文对象（`intent_context`）

`intent_context` 是 IBCI 内置类型，可以直接操作意图栈：

```ibci
import ai
ai.set_config("YOUR_URL", "YOUR_KEY", "YOUR_MODEL")

intent_context ctx = intent_context.get_current()   # 获取当前帧的意图上下文

ctx.push("请用简洁的语言回答")
str r1 = @~ 描述天空 ~
ctx.pop()

ctx.push("用详细专业的语言回答")
str r2 = @~ 描述天空 ~
ctx.pop()
```

---

## 10. 健壮性与自愈

### 10.1 llmexcept

`llmexcept` 附着在可能触发 LLM 不确定性的语句之后，提供重试机制：

```ibci
int result = @~ 1+1 等于几？只答数字 ~
llmexcept:
    print("AI 响应无法解析为整数，正在重试...")
    retry "请务必只返回一个纯数字，不要任何其他内容"
```

- `llmexcept` 必须与它保护的语句保持**相同缩进级别**，紧跟其后
- `retry` 后的字符串会作为额外系统提示词注入到重试调用中
- 重试次数由 `ai.set_retry(n)` 配置（默认 3 次）

保护条件语句时，`llmexcept` 跟在条件块末尾：

```ibci
if @~ $text 是正面的吗？只答 1 或 0 ~:
    print("正面")
llmexcept:
    retry "只返回 0 或 1"
```

保护循环体内的行：

```ibci
for str item in items:
    int score = @~ 给 $item 打分 1-10 ~
    llmexcept:
        retry "请只返回一个 1 到 10 的整数"
    print("分数: " + (str)score)
```

### 10.2 llmretry 语法糖

```ibci
str res = @~ 判断当前状态，只回答正常或异常 ~
llmretry "如果无法判断，请回复 0 并说明原因"
```

`llmretry` 等价于只有 `retry` 语句的 `llmexcept`，是其精简写法。

### 10.3 快照隔离模型

`llmexcept` 使用**快照隔离**保证 retry 的一致性：

- 进入 LLM 语句执行时，创建当前变量/意图上下文/循环状态的快照
- LLM 调用成功 → 结果 commit 到目标变量，退出快照
- LLM 调用失败 → 执行 `llmexcept` 体，然后从快照恢复状态并 retry
- 重试耗尽 → 目标变量设为 `Uncertain`

`llmexcept` 体内**禁止写入外部变量**（编译期 `SEM_052` 错误）：

```ibci
int x = 1
int result = @~ 计算结果 ~
llmexcept:
    x = 2            # ❌ SEM_052：禁止在 llmexcept 中写入外部变量
    retry "重试"
```

### 10.4 用户自定义快照协议

对于复杂对象，可以通过 `__snapshot__` / `__restore__` 协议控制快照粒度：

```ibci
class Config:
    str mode
    int attempts

    func __snapshot__(self) -> int:
        return self.attempts    # 只快照关键字段

    func __restore__(self, int saved):
        self.attempts = saved   # 恢复关键字段
```

---

## 11. 模块与插件

### 11.1 import 位置约束

**`import` 语句必须出现在模块文件的顶部**，在任何非 import 语句之前。不允许在函数、类、条件块或循环体内部使用 `import`。

```ibci
# ✅ 正确：import 在文件顶部
import ai
import json

int x = 10
func main():
    ...
```

```ibci
# ❌ 错误：import 不能出现在函数内或其他语句后面
int x = 10
import ai    # PAR_002 编译错误

func main():
    import json  # PAR_002 编译错误
```

此约束使调度器（Scheduler）能够高效地在不执行代码的前提下进行无副作用的依赖扫描。

### 11.2 内置模块

```ibci
import ai      # LLM provider 配置（API key、model、retry 等）
import isys    # 运行时路径查询（entry_path / entry_dir / project_root）
import idbg    # 调试探查工具
import ihost   # 动态宿主（隔离子环境运行）
import json    # JSON 解析
import file    # 受限文件系统操作
```

> **注意**：`@~ ... ~` 行为描述语句是语言核心特性，**不依赖 `import ai`**。`ai` 模块仅负责配置 LLM provider。

### 11.3 ai 模块

```ibci
import ai

ai.set_config("https://api.example.com", "API_KEY", "model-name")
ai.set_retry(3)           # 设置重试次数（默认 3）
ai.set_timeout(30)        # 设置超时（秒）
```

TESTONLY 模式（结合 MOCK 指令使用）：

```ibci
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
```

### 11.4 isys 模块

```ibci
import isys

str entry  = isys.entry_path()    # 入口文件绝对路径
str dir    = isys.entry_dir()     # 入口文件所在目录
str root   = isys.project_root()  # 项目根目录
```

### 11.5 idbg 模块

```ibci
import idbg

int x = 42
idbg.vars()              # 打印当前作用域所有变量及其值
idbg.print_vars()        # 同 vars()，别名
idbg.last_llm()          # 返回最后一次 LLM 调用的详细信息（dict）
idbg.last_result()       # 返回最后一次 LLM 调用的结果对象
idbg.show_last_prompt()  # 打印最后一次 LLM 调用的提示词
idbg.show_last_result()  # 打印最后一次 LLM 调用的结果
idbg.show_all()          # 打印变量、最后结果等全部调试信息
idbg.retry_stack()       # 返回当前 llmexcept 重试栈
idbg.intents()           # 返回当前意图栈列表
idbg.show_intents()      # 打印当前意图栈
idbg.env()               # 返回当前运行环境信息
idbg.fields(obj)         # 返回对象所有字段
```

> **⚠️ 已知限制**：`idbg.inspect(x)` 和 `idbg.dump_intent_stack()` 在当前版本中**未实现**，调用会产生运行时错误。
> 请使用 `idbg.vars()` 代替 `idbg.inspect()`，使用 `idbg.show_intents()` 代替 `idbg.dump_intent_stack()`。

### 11.6 ihost 动态宿主

```ibci
import ihost
import isys

dict policy = {"isolated": True}
ihost.run_isolated("./sub/child.ibci", policy)
```

子环境完全独立（独立 Engine 实例、独立插件发现、默认不继承父环境变量）。

### 11.7 file 模块

```ibci
import file

str content = file.read("./data.txt")
file.write("./output.txt", "hello world")
bool exists = file.exists("./data.txt")
```

### 11.8 json 模块

```ibci
import json

str raw = '{"name": "Alice", "age": 30}'
dict parsed = json.parse(raw)
str serialized = json.stringify(parsed)
```

### 11.9 用户插件

插件文件须放置于工程的 `./plugins` 目录，以 Python 编写，通过 `_spec.py` 声明元数据。参考 `ibci_modules/ibci_file` 的一方插件写法。

---

## 12. 内置函数与方法

### 12.1 全局内置函数

| 函数 | 说明 |
|------|------|
| `print(value)` | 输出值（支持任意类型） |
| `range(n)` | 生成 `[0, n)` 整数序列 |
| `range(start, end)` | 生成 `[start, end)` 整数序列 |
| `is_uncertain(value)` | 检测值是否为 `Uncertain` |
| `len(container)` | 获取容器长度（列表/字符串/字典） |

### 12.2 str 方法

```ibci
str s = "  Hello World  "
s.len()              # 15
s.strip()            # "Hello World"（等同于 trim()）
s.upper()            # "  HELLO WORLD  "
s.lower()            # "  hello world  "
s.split(" ")         # ["", "", "Hello", "World", "", ""]
s.replace("Hello", "Hi")    # "  Hi World  "
s.startswith("  Hello")     # True
s.endswith("  ")            # True
s.contains("World")         # True
s.find("World")             # 8
s.find_last("l")            # 9
s.is_empty()                # False

# 字符串拼接与重复
str a = "ab" + "cd"    # "abcd"
str b = "ab" * 3       # "ababab"

# 下标访问
str ch = s[0]          # " "
```

### 12.3 list 方法

```ibci
list[int] l = [3, 1, 2]
l.append(4)            # [3, 1, 2, 4]
l.insert(0, 99)        # [99, 3, 1, 2, 4]
l.remove(99)           # [3, 1, 2, 4]
l.sort()               # [1, 2, 3, 4]
l.reverse()            # [4, 3, 2, 1]
int v = l.pop()        # v=1, l=[4, 3, 2]
l.clear()              # []
int idx = l.index(3)   # 找到 3 的索引
int cnt = l.count(2)   # 统计 2 出现次数
bool has = l.contains(3)   # True / False
int n = l.len()        # 长度

# 列表拼接与重复
list[int] a = [1, 2] + [3, 4]     # [1, 2, 3, 4]
list[int] b = [1, 2] * 3          # [1, 2, 1, 2, 1, 2]

# 下标访问与赋值
int first = l[0]
l[0] = 99
```

### 12.4 dict 方法

```ibci
dict[str,int] d = {"a": 1, "b": 2}
d["c"] = 3                  # 新增/更新
int v = d["a"]              # 取值
bool has = "a" in d         # 键存在检测
list pairs = d.items()      # [[key, value], ...] 列表
d.update({"d": 4, "a": 99}) # 合并/更新

# 删除键
d.remove("a")
```

### 12.5 tuple

```ibci
tuple t = (1, "hello", True)
auto first = t[0]     # 1（下标访问）
int n = t.len()       # 3
```

---

## 13. Mock 测试机制

在没有真实 LLM API 的环境中，可以通过 MOCK 指令模拟 LLM 返回。

### 13.1 启用 MOCK 模式

```ibci
import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")
```

### 13.2 MOCK 指令格式

MOCK 指令写在行为表达式（`@~...~`）或 LLM 函数的 `__user__` 块中：

| 指令 | 说明 | 示例 |
|------|------|------|
| `MOCK:STR:value` | 返回指定字符串 | `MOCK:STR:hello` |
| `MOCK:INT:value` | 返回指定整数字符串 | `MOCK:INT:42` |
| `MOCK:FLOAT:value` | 返回指定浮点字符串 | `MOCK:FLOAT:3.14` |
| `MOCK:BOOL:value` | 返回 `1`（True）或 `0`（False） | `MOCK:BOOL:True` |
| `MOCK:LIST:value` | 返回 JSON 数组字符串 | `MOCK:LIST:[1,2,3]` |
| `MOCK:DICT:value` | 返回 JSON 对象字符串 | `MOCK:DICT:{"a":1}` |
| `MOCK:TRUE` | 返回 `"1"` | — |
| `MOCK:FALSE` | 返回 `"0"` | — |
| `MOCK:FAIL` | 返回模糊内容（触发 llmexcept） | — |
| `MOCK:REPAIR` | 下一次 FAIL 后 repair 到 str 空值 | — |
| `MOCK:REPAIR:STR:v` | 下一次 FAIL 后 repair 到指定字符串 | `MOCK:REPAIR:STR:fallback` |
| `MOCK:REPAIR:INT:v` | 下一次 FAIL 后 repair 到指定整数 | `MOCK:REPAIR:INT:0` |
| `MOCK:SEQ:[v1,v2,...] key` | 按序返回值，支持哨兵 FAIL/TRUE/FALSE | `MOCK:SEQ:[a,b,c] my_key` |

> ⚠️ **MOCK:SEQ 强制使用方括号格式**：必须写成 `MOCK:SEQ:[v1,v2,...] key`，**不允许**省略方括号（`MOCK:SEQ:a,b,c` 会产生 `UserWarning` 并返回空字符串）。

### 13.3 示例

```ibci
import ai
ai.set_config("TESTONLY", "TESTONLY", "TESTONLY")

str reply = @~ MOCK:STR:hello world ~
print(reply)    # hello world

int n = @~ MOCK:INT:42 ~
print((str)n)   # 42

# SEQ：依序返回
str s1 = @~ MOCK:SEQ:[first,second,third] mykey ~   # first
str s2 = @~ MOCK:SEQ:[first,second,third] mykey ~   # second
str s3 = @~ MOCK:SEQ:[first,second,third] mykey ~   # third

# FAIL + llmexcept + REPAIR：首次 ambiguous 触发 llmexcept，
# retry 后由 REPAIR 提供 fallback 值。
# 注意：retry "..." 的字符串是**追加给 LLM 的系统提示词**，
# 不是 MOCK 指令覆盖，因此用 `MOCK:REPAIR:INT:99` 表达
# "失败一次后回退到 99"，而不是 retry "MOCK:INT:99"。
int result = @~ MOCK:REPAIR:INT:99 ~
llmexcept:
    retry "请只返回一个整数"
print((str)result)   # 99
```

### 13.4 LLM 函数 MOCK

LLM 函数 MOCK 时，`__user__` 块必须**只包含** MOCK 指令（不能混入其他文本）：

```ibci
llm 测试函数(str input) -> str:
__sys__
任何系统提示词
__user__
MOCK:STR:mock_result
llmend

str r = 测试函数("anything")
print(r)   # mock_result
```
