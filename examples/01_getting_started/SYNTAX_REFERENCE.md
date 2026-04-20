# IBC-Inter 基础语法参考手册

本手册被放置于examples文件夹下，用于阐述一些作者不希望凌乱散落在具体示例代码里的细节语法。

---

## 基础概念

### AI 模块

IBC-Inter 使用 `ai` 配置运行过程中的 LLM 提供者。
任何行为描述交互或者 llm 函数调用交互等涉及到模型调用的操作之前，都必须先配置 LLM 提供者，否则IBC-Inter 无法顺利继续运行。

#### 基本配置

使用 `ai.set_config()` 配置 LLM 提供者：

```ibci
import ai
import json
import file

dict config = json.parse(file.read("./api_config.json"))
dict default_model = (dict)config["default_model"]

ai.set_config(
    (str)default_model["base_url"],
    (str)default_model["api_key"],
    (str)default_model["model"]
)
```

注：IBC-Inter目前的demo设计中，类型系统设计上存在已知局限性，需要利用强制类型转换来处理Dict这种容器类型。

---

### 行为描述语句

**行为描述语句**是 IBC-Inter 的核心机制之一，使用 `@~ ... ~` 语法直接调用 LLM：

```ibci
# 行为描述：使用 AI 生成回复
str greeting = "你好，请打个招呼"
str result = @~ 请根据要求进行回复： $greeting ~
print(result)

# 变量赋值的 LHS 类型自动成为 LLM 输出格式约束
int a = 10
int b = 20
int sum = @~ 请计算 $a 和 $b 之和，只输出数字 ~
print((str)sum)
```

> **重要**：`(Type)@~...~` 的转型语法已废弃，会产生编译错误。请直接将类型声明在变量赋值的左侧，解释器会自动将其作为 LLM 输出格式的提示上下文。

#### 行为描述中引用变量

在 `@~ ... ~` 中使用 `$变量名` 插值引用当前作用域的变量：

```ibci
str topic = "量子计算"
str style = "通俗易懂"
str article = @~ 请写一篇关于 $topic 的文章，风格要 $style ~
```

---

### LLM 函数

使用 `llm` 关键字定义 LLM 函数，`llmend` 标记结束：

```ibci
llm 翻译(str 文本, str 目标语言):
__sys__
你是一个翻译助手，只返回翻译结果。不输出任何额外内容
__user__
请将以下内容翻译成 $目标语言： $文本
llmend
```

#### 特点

1. **无需缩进** - LLM 函数内容不需要缩进，确保所有空格都能作为提示词的一部分，这能减轻阅读负担。因此llm函数必须以独占一行的 `llmend` 来标记结束。
2. **系统提示词** - 使用 `__sys__` 分隔符定义系统提示词。 `__sys__` 必须独占一行单独书写，用来指示系统提示词的开始。
3. **用户提示词** - 使用 `__user__` 分隔符定义用户提示词。 `__user__` 必须独占一行单独书写，用来指示用户提示词的开始。
4. **参数插值** - 使用 `$参数名` 在提示词中引用函数参数。在参数列表之外的 `$纯文本` 会被视作普通文本，可自由书写。

#### 调用 LLM 函数

```ibci
str chinese_text = "编程让世界更美好"
str english_text = 翻译(chinese_text, "English")
print("翻译: " + english_text)
```

---

### 意图注释

使用 `@` 语法添加意图注释，动态向提示词注入额外约束：

```ibci
# 意图注释 - 为下一次 LLM 调用注入约束（一次性，调用后自动清除）
@ 用客观无感情且最简洁的方式回复用户
str result = @~ 打个招呼 ~
print(result)
```

#### 意图注释的作用

意图注释用于动态地向 LLM 提示词注入额外约束：

1. **场景控制** - 控制 AI 回复的语气、风格
2. **额外提示词** - 为后续 AI 调用添加额外约束
3. **上下文增强** - 为特定代码块添加上下文

#### 与 LLM 函数配合

```ibci
@ 所有英文回复都采用大写字母
str text = 翻译("你好", "English")
```

#### 意图修饰符

| 修饰符 | 说明 | 特性 |
| -------- | ------ | ------ |
| `@` | 一次性涂抹意图 | 只对紧跟的下一次 LLM 调用有效，调用后**自动清除** |
| `@+` | 压入意图栈（持久） | 持续有效，直到被显式移除 |
| `@-` | 从栈中移除意图 | 按内容匹配：`@- 某意图内容`；按标签匹配：`@-#tag`；无参数则移除栈顶：`@-` |
| `@!` | 排他意图（单次覆盖） | 只对当前 LLM 调用有效，**同时屏蔽**涂抹意图和持久栈，调用后自动清除 |

**语法规则**：
- `@`（一次性）和 `@!`（排他）是**前置意图**，语义上紧跟后面的 LLM 调用
- `@+`（压栈）和 `@-`（移除）可以**独立存在**，不需要后跟 LLM 调用
- `@` 与修饰符之间**不能有空格**（如 `@-#tag` 正确，`@ - #tag` 错误）

```ibci
# 意图优先级：@!（排他）> @（涂抹）> @+（持久栈）
@+ 用英文回复
@+ 每句话不超过10个单词
str r1 = @~ 打个招呼 ~           # 受 @+ 意图影响

@ 这次用中文                      # 一次性涂抹，仅影响下一次调用
str r2 = @~ 打个招呼 ~           # 受"用中文"涂抹意图 + @+ 意图影响

str r3 = @~ 打个招呼 ~           # 涂抹意图已消费，只受 @+ 持久意图影响

@! 无视所有约束，自由发挥
str r4 = @~ 打个招呼 ~           # 只受 @! 影响，@+ 意图被屏蔽

@- 每句话不超过10个单词           # 按内容移除
@-                                # 再移除栈顶（此时为"用英文回复"）
```

---

### llmexcept / retry（LLM 异常处理）

`llmexcept` 是 IBC-Inter 的 LLM 不确定性处理机制，基于**快照隔离模型**。当 LLM 调用结果不确定时（如格式错误、语义不符），可以在 `llmexcept` 块中检查原因并决定是否重试。

```ibci
str result = @~ 请返回一个 JSON 格式的对象，包含 name 和 age 字段 ~
llmexcept:
    retry "请严格按 JSON 格式返回，不要包含任何额外文字"
```

#### 使用 ai.set_retry() 配置最大重试次数

```ibci
import ai
ai.set_retry(3)   # 最多重试 3 次（默认值）
```

#### llmexcept 的语义约束（快照隔离）

`llmexcept` body 在**只读快照**中执行：
- ✅ **允许**：读取外部变量（读取快照进入时的值）
- ✅ **允许**：调用 `retry "hint"` 提供重试提示词
- ❌ **禁止**：向外部变量赋值（编译期 SEM_052 错误）

```ibci
str context = "一篇关于 AI 的文章"
str summary = @~ 请总结以下内容：$context ~
llmexcept:
    # context 可以读取（只读）
    retry "请用一句话总结，不超过30字"
    # summary = "错误" ← 编译期错误 SEM_052：不能在 llmexcept body 内写入外部变量
```

#### 与循环配合

```ibci
list items = ["苹果", "香蕉", "橙子"]
for str item in items:
    str desc = @~ 用一句话描述 $item 的营养价值 ~
    llmexcept:
        retry "请直接给出一句话描述，不要加序号或额外格式"
    print(desc)
```

---

### 延迟行为（lambda / snapshot）

使用 `lambda` 或 `snapshot` 关键字声明**延迟执行**的行为或表达式：

| 关键字 | 语义 | 意图栈时机 |
|--------|------|-----------|
| `lambda` | 调用时执行 | 使用**调用时刻**的意图栈 |
| `snapshot` | 定义时捕获，调用时执行 | 使用**定义时刻**的意图栈快照 |

#### 语法

```ibci
# 变量声明语法：<type> lambda <name> = <expr>
int lambda compute = @~ 计算一个随机数 ~

# 也可以使用 auto
auto lambda lazy_sum = a + b

# snapshot 变体
int snapshot cached = @~ 生成一个偶数 ~
```

#### 意图栈时机

`lambda` 和 `snapshot` 的核心区别在于**意图（`@+`/`@-`）何时绑定**：

```ibci
# lambda：每次调用时才执行，使用调用时的意图栈
int lambda compute = @~ 计算一个随机数 ~

@+ 结果必须是正数
int result1 = compute()    # 受 @+ 意图影响

@- 结果必须是正数
int result2 = compute()    # @+ 已移除，意图栈已改变

# snapshot：定义时捕获意图栈快照
@+ 结果必须是偶数
int snapshot cached = @~ 生成一个偶数 ~
@- 结果必须是偶数            # 移除意图
int result3 = cached()     # 仍使用定义时的快照意图（"结果必须是偶数"）
```

#### 延迟任意表达式

`lambda`/`snapshot` 不局限于行为描述，任意表达式均可延迟：

```ibci
int a = 3
int b = 4
auto lambda lazy_add = a + b      # 定义时不求值
int val = lazy_add()              # 调用时才真正计算 a + b
```

#### 调用语法

延迟变量通过 `()` 调用，**不接受参数**：

```ibci
int lambda f = @~ 返回一个整数 ~
int x = f()    # 正确
# int y = f(1) # 错误：延迟表达式不接受参数
```

#### 类型

延迟变量的底层类型为 `deferred`（延迟执行），其中行为描述（`@~...~`）的类型为 `behavior`（`deferred` 的子类型）：

```
callable  →  deferred  →  behavior
（可调用）   （延迟执行）  （LLM 行为）
```

变量声明时的类型标注（如 `int lambda f = ...`）表示**调用时返回值的期望类型**，不影响变量本身的 `deferred` 类型。

---

## 类型系统

### 基本类型

| 类型 | 说明 | 示例 |
|------|------|------|
| `int` | 整数 | `int age = 25` |
| `float` | 浮点数 | `float pi = 3.14` |
| `str` | 字符串 | `str name = "Alice"` |
| `bool` | 布尔值 | `bool flag = true` |
| `list` | 列表 | `list items = ["a", "b"]` |
| `dict` | 字典 | `dict data = {"key": "value"}` |

### 自动类型推断

使用 `auto` 让解释器自动推断类型：

```ibci
auto x = 42          # 推断为 int
auto name = "Alice"  # 推断为 str
auto flag = true     # 推断为 bool
```

### 类型转换

```ibci
str num_str = (str)42        # int → str
int parsed = (int)"123"       # str → int
float f = (float)10           # int → float
```

### 可调用类型层次

IBC-Inter 有三层可调用类型，从抽象到具体：

```
callable  →  deferred  →  behavior
（可调用）   （延迟执行）  （LLM 行为，延迟执行）
```

- `callable`：所有可调用对象的抽象基类
- `deferred`：用 `lambda`/`snapshot` 声明的延迟表达式，调用时求值
- `behavior`：`@~...~` 行为描述，是带 LLM 调用语义的特殊 `deferred`

---

### 列表

#### 创建列表

```ibci
list empty = []
list numbers = [1, 2, 3, 4, 5]
list mixed = ["a", 1, true, 3.14]
```

#### 访问元素

```ibci
list items = [10, 20, 30]
items[0]          # 第一个元素: 10
items[1]          # 第二个元素: 20
items.len()       # 长度: 3
```

#### 列表操作

```ibci
list fruits = ["apple", "banana"]

fruits.append("cherry")       # 添加元素
fruits.insert(1, "orange")   # 插入元素
fruits.remove("banana")       # 移除元素
str removed = fruits.pop()     # 弹出元素

bool has_apple = fruits.contains("apple")  # 检查包含
int idx = fruits.index_of("cherry")       # 查找索引
```

#### 列表切片

```ibci
list nums = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

nums[0:3]      # [0, 1, 2]     - 前三个
nums[3:6]      # [3, 4, 5]     - 中间三个
nums[::2]      # [0, 2, 4, 6, 8]  - 偶数位
nums[::-1]     # [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]  - 反向
nums[7:2:-1]   # [7, 6, 5, 4, 3]  - 反向切片
```

---

### 字符串

#### 创建字符串

```ibci
str s1 = "Hello"
str s2 = 'World'
```

#### 字符串方法

```ibci
str s = "  Hello, IBCI!  "

s.trim()              # "Hello, IBCI!"
s.to_upper()         # "  HELLO, IBCI!  "
s.to_lower()         # "  hello, ibci!  "
s.len()              # 16
s.is_empty()         # false
s.contains("IBCI")   # true
```

#### 字符串查找

```ibci
str text = "Hello, IBCI World!"

int pos = text.find("IBCI")       # 7 (首次出现)
int last = text.find_last("o")    # 17 (最后一次出现)
int not_found = text.find("xyz")  # -1 (未找到)

str filename = "document.pdf"
int dot_pos = filename.find_last(".")
if dot_pos >= 0:
    str name = filename[0:dot_pos]       # "document"
    str ext = filename[dot_pos + 1:]     # "pdf"
```

#### 字符串切片

```ibci
str text = "Hello, World!"

text[0:5]    # "Hello"
text[7:]     # "World!"
text[::2]    # "Hlo ol!"
text[::-1]   # "!dlroW ,olleH"
```

#### 字符串操作

```ibci
str email = "user@example.com"

email.contains("@")                    # true
email.find("example")                  # 5
email.replace("example", "test")       # "user@test.com"
email.split("@")                       # ["user", "example.com"]
```

---

### 字典

#### 创建字典

```ibci
dict person = {
    "name": "Alice",
    "age": 25,
    "city": "Beijing"
}
```

#### 访问字典

```ibci
person["name"]           # "Alice"
person["age"]            # 25

# 添加/修改
person["email"] = "alice@example.com"
person["age"] = 26
```

#### 字典方法

```ibci
dict config = {"debug": true, "timeout": 30}

config.keys()              # 获取所有键
config.values()            # 获取所有值
config.contains("debug")   # 检查键是否存在
config.remove("debug")     # 移除键值对
```

---

## 运算符

### 算术运算符

```ibci
int a = 10
int b = 3

a + b     # 加法: 13
a - b     # 减法: 7
a * b     # 乘法: 30
a / b     # 除法（浮点）: 3.333...
a // b    # 整除（向下取整）: 3
a % b     # 取余: 1
a ** b    # 幂运算: 1000（右结合：2 ** 3 ** 2 = 2 ** (3**2) = 512）
```

### 比较运算符

```ibci
a == b    # 相等
a != b    # 不等
a < b     # 小于
a > b     # 大于
a <= b    # 小于等于
a >= b    # 大于等于
```

### 逻辑运算符

IBC-Inter 使用**关键字**作为逻辑运算符，不支持 `&&`/`||` 等符号：

```ibci
bool p = true
bool q = false

p and q    # 逻辑与: false
p or q     # 逻辑或: true
not p      # 逻辑非: false
```

### 位运算符

```ibci
int a = 0b1010    # 10
int b = 0b0110    # 6

a & b     # 按位与:  0b0010 = 2
a | b     # 按位或:  0b1110 = 14
a ^ b     # 按位异或: 0b1100 = 12  （注意：^ 是位异或，不是幂运算）
~a        # 按位取反
a << 1    # 左移:    0b10100 = 20
a >> 1    # 右移:    0b0101 = 5
```

### 三元运算符

```ibci
bool condition = true
str result = condition ? "真" : "假"   # result = "真"

# 可嵌套（右结合）
int x = 5
str label = x > 10 ? "大" : (x > 3 ? "中" : "小")   # label = "中"

# 可与逻辑运算符组合：逻辑运算优先于三元
bool a = true
bool b = false
str r = a or b ? "有" : "无"    # 等价于 (a or b) ? "有" : "无"
```

> **语义**：`cond ? body : orelse` 当 `cond` 为真时返回 `body` 的值，否则返回 `orelse` 的值。  
> 三元运算符优先级低于所有逻辑运算符（`and`/`or`/`not`）和比较运算符，高于赋值。

### 复合赋值运算符

```ibci
int x = 10
x += 5    # x = 15
x -= 3    # x = 12
x *= 2    # x = 24
x /= 4    # x = 6
x //= 2   # x = 3（整除赋值）
x %= 4    # x = 3
x **= 3   # x = 27（幂赋值）
```

---

## 控制流

### if / elif / else 语句

```ibci
int score = 85

if score >= 90:
    print("优秀")
elif score >= 80:
    print("良好")
elif score >= 60:
    print("及格")
else:
    print("继续努力")
```

> **注意**：IBC-Inter 使用 `elif` 关键字，不支持 `else if` 两词写法。

### while 循环

```ibci
int i = 1
while i <= 5:
    print("计数: " + (str)i)
    i = i + 1
```

#### while 过滤条件

```ibci
# while ... if ... 在每次迭代前额外检查过滤条件
while i < 100 if is_ready():
    # 只有在 is_ready() 为 true 时才执行循环体
    i = i + 1
```

### for 循环

#### 标准 for...in 循环

```ibci
list items = ["apple", "banana", "cherry"]

# 基本形式
for item in items:
    print(item)

# 带类型标注的循环变量
for str name in items:
    print("水果: " + name)
```

#### 带类型解包的 for 循环

```ibci
list coords = [(1, 2), (3, 4), (5, 6)]

for (int x, int y) in coords:
    print("坐标: " + (str)x + ", " + (str)y)
```

#### 带过滤条件的 for 循环

```ibci
list numbers = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

# 只处理偶数
for int n in numbers if n % 2 == 0:
    print((str)n)
```

#### 条件驱动 for 循环（IBCI 独有）

这是 IBC-Inter 最具特色的语法之一：以**条件表达式**而不是可迭代对象驱动循环。循环在条件为 `true` 时持续执行，常与 `@~...~` 行为表达式组合使用：

```ibci
# 让 LLM 决定是否继续循环
for @~ 请判断任务是否完成，返回 true 或 false ~:
    # 执行某些操作
    print("继续执行...")
```

```ibci
# 与普通条件表达式组合
int attempt = 0
for attempt < 5:
    attempt = attempt + 1
    print("第 " + (str)attempt + " 次尝试")
```

条件驱动 for 循环与 `llmexcept` 配合，可实现带重试的 LLM 判断循环：

```ibci
for @~ 判断数据处理是否应该继续 ~:
llmexcept:
    retry "请只回答 true 或 false"
    print("处理中...")
```

### break 和 continue

```ibci
int counter = 0
while counter < 100:
    counter = counter + 1
    if counter == 10:
        break                    # 退出循环
    if counter % 3 == 0:
        continue                 # 跳过本次迭代
    print((str)counter)
```

### switch / case

```ibci
str day = "Monday"

switch day:
    case "Monday":
        print("星期一")
    case "Tuesday":
        print("星期二")
    case "Saturday":
        print("周末")
    case "Sunday":
        print("周末")
    default:
        print("工作日")
```

---

## 函数

### 定义函数

使用 `func` 关键字定义函数，参数格式为 `类型 参数名`（类型在前，名称在后）：

```ibci
func greet(str name):
    print("你好，" + name + "！")

func add(int a, int b) -> int:
    return a + b
```

### 函数调用

```ibci
greet("Alice")            # 输出: 你好，Alice！
int sum = add(10, 20)     # sum = 30
```

### 带返回值的函数

```ibci
func max(int a, int b) -> int:
    if a > b:
        return a
    return b

int result = max(10, 20)  # result = 20
```

### 递归函数

```ibci
func factorial(int n) -> int:
    if n <= 1:
        return 1
    return n * factorial(n - 1)

int result = factorial(5)  # result = 120
```

### 嵌套函数

```ibci
func outer(int x) -> int:
    func inner(int y) -> int:
        return x + y
    return inner(x * 2)
```

### LLM 函数

在函数体内使用 `llm` 定义结构化 LLM 调用，适合作为类的方法：

```ibci
llm summarize(str text, str lang):
__sys__
You are a summarizer. Output only the summary, nothing else.
__user__
Summarize the following text in $lang:
$text
llmend

str zh_summary = summarize(long_text, "Chinese")
```

---

## 类与面向对象

### 定义类

IBCI 的构造函数名称为 `__init__`（注意双下划线），这与 Python 一致。

```ibci
class Person:
    str name
    int age

    func __init__(self, str name, int age):
        self.name = name
        self.age = age

    func greet() -> str:
        return "你好，我是 " + self.name

    llm describe():
    __sys__
    你是一个人物描述助手。
    __user__
    请描述这个人：姓名 $self.name，年龄 $self.age
    llmend
```

> **注意**：`func init(...)` 是一个普通方法（名为 `init`），**不是**构造函数。构造函数必须命名为 `func __init__(...)`。

### 自动生成构造函数

如果类体中声明了**无默认值的字段**（如 `str name`、`int age`），且未定义 `func __init__`，IBCI 运行时会自动生成一个按声明顺序接收位置参数的构造函数：

```ibci
class Point:
    int x
    int y
    # 无需手写 __init__，自动生成 __init__(self, int x, int y)

Point p = Point(3, 7)   # x=3, y=7
```

如果类中所有字段都有默认值，则构造函数自动生成为无参形式（`Point()`）。

### 创建实例

```ibci
Person alice = Person("Alice", 30)
print(alice.greet())       # "你好，我是 Alice"
str bio = alice.describe() # LLM 生成人物描述
```

### 继承

```ibci
class Animal:
    str name

    func __init__(self, str name):
        self.name = name

    func speak() -> str:
        return self.name + " 发出声音"

class Dog(Animal):
    func speak() -> str:
        return self.name + " 汪汪叫"

Dog d = Dog("旺财")
print(d.speak())   # "旺财 汪汪叫"
```

### 枚举

```ibci
class Status:
    PENDING, RUNNING, DONE, FAILED

Status s = Status.PENDING
switch s:
    case Status.DONE:
        print("完成")
    default:
        print("进行中")
```

---

## 异常处理

### try / except / finally

```ibci
try:
    int result = (int)"not_a_number"  # 触发异常
except Exception as e:
    print("捕获错误: " + e.message)
finally:
    print("总是执行")
```

### raise

```ibci
func divide(int a, int b) -> int:
    if b == 0:
        raise Exception("除数不能为零")
    return a / b
```

---

## 模块系统

### 导入模块

```ibci
import ai         # AI 配置模块
import math       # 数学函数
import json       # JSON 解析
import file       # 文件操作
```

### 使用模块

```ibci
import math
float result = math.sqrt(16.0)    # 4.0
float pi = math.pi()              # 3.14159...

import json
str text = '{"name": "Alice"}'
dict data = json.parse(text)

import file
str content = file.read("./data.txt")
file.write("./output.txt", content)
```

---

## 快速参考

```ibci
# 变量声明
int x = 10
str name = "Alice"
bool flag = true
list items = [1, 2, 3]
dict data = {"key": "value"}
auto inferred = 42           # 自动类型推断

# 类型转换
(str)42, (int)"123", (float)10

# 条件判断（注意：是 elif，不是 else if）
if condition:
    # 代码
elif other:
    # 代码
else:
    # 代码

# 循环
while condition:
    # 代码

for item in items:           # 标准 for...in
    # 代码

for str name in names:       # 带类型标注
    # 代码

for @~ LLM判断是否继续 ~:   # 条件驱动（IBCI 独有）
    # 代码

# 函数（func 关键字，参数格式：类型 名称）
func my_func(str arg, int count) -> str:
    return arg

# LLM 函数
llm 翻译(str 文本, str 目标语言):
__sys__
你是一个翻译助手
__user__
请翻译：$文本
llmend

# 行为描述语句（AI 调用）
str result = @~ 请打个招呼 ~

# 意图注释
@ 用简洁的方式回复             # 一次性（下次LLM调用后清除）
@+ 始终用英文                  # 持久压栈
@- 始终用英文                  # 按内容移除
@!  只回答 yes 或 no           # 排他覆盖（本次调用后清除）

# llmexcept 处理 LLM 不确定性
str answer = @~ 请回答 ~
llmexcept:
    retry "请提供更清晰的回答"

# 延迟行为
int lambda lazy = @~ 计算结果 ~   # 调用时执行，用调用时意图栈
int snapshot fixed = @~ 计算 ~    # 调用时执行，用定义时意图栈快照
int val = lazy()
```
