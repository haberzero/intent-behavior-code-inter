# IBC-Inter 基础语法参考手册

本手册被放置于examples文件夹下，用于阐述一些作者不希望凌乱散落在具体示例代码里的细节语法。

---

## 基础概念

### AI 模块

IBC-Inter 使用 `ai` 配置运行过程中的 LLM 提供者。
任何行为描述交互或者 llm 函数调用交互等涉及到模型调用的操作之前，都必须先配置 LLM 提供者，否则IBC-Inter 无法顺利继续运行

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

### 行为描述语句

**行为描述语句**是 IBC-Inter 的核心机制之一。

使用 `@~ ... ~` 语法直接调用 LLM：

```ibci
# 行为描述：使用 AI 生成回复
str greeting = "你好，请打个招呼"
str result = @~ 请根据要求进行回复： $greeting ~
print(result)

# 带有类型约束的行为描述
int a = 10
int b = 20
int sum = (int)@~ 请计算 $a 和 $b 之和 ~
print((str)sum)
```

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

### 意图注释

使用 `@` 语法添加意图注释，动态向提示词注入额外约束：

```ibci
# 意图注释 - 为下一行代码注入约束
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

| 修饰符 | 说明 | 示例 |
| -------- | ------ | ------ |
| `@` | 单行意图注入 | `@ 用简洁的方式回复` |
| `@+` | 增量注入（追加） | `@+ 添加更多约束` |
| `@-` | 意图移除（按内容/标签） | `@- 取消之前的某个意图` 或 `@-#tag` |
| `@-` | 栈顶移除（无参数） | `@-` 直接移除栈顶最新意图 |
| `@!` | 排他注入（覆盖） | `@! 屏蔽栈并仅应用此意图` |

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

### 类型转换

```ibci
str num_str = (str)42        # int → str
int parsed = (int)"123"       # str → int
float f = (float)10           # int → float
```

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
nums[::-1]      # [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]  - 反向
nums[7:2:-1]     # [7, 6, 5, 4, 3]  - 反向切片
```

---

### 字符串

#### 创建字符串

```ibci
str s1 = "Hello"
str s2 = 'World'
str s3 = """多行
字符串"""
```

#### 字符串方法

```ibci
str s = "  Hello, IBCI!  "

s.trim()         # "Hello, IBCI!"
s.to_upper()    # "  HELLO, IBCI!  "
s.to_lower()    # "  hello, ibci!  "
s.len()         # 16
s.is_empty()    # false
s.contains("IBCI")  # true
```

#### 字符串查找

```ibci
str text = "Hello, IBCI World!"

# 查找子串位置
int pos = text.find("IBCI")      # 7 (首次出现)
int last = text.find_last("o")   # 17 (最后一次出现)
int not_found = text.find("xyz")  # -1 (未找到)

# 查找的实用示例
str filename = "document.pdf"
int dot_pos = filename.find_last(".")
if dot_pos >= 0:
    str name = filename[0:dot_pos]  # "document"
    str ext = filename[dot_pos + 1:]  # "pdf"
```

#### 字符串切片

```ibci
str text = "Hello, World!"

text[0:5]       # "Hello"
text[7:]        # "World!"
text[::2]       # "Hlo ol!"
text[::-1]       # "!dlroW ,olleH"
```

#### 字符串操作

```ibci
str email = "user@example.com"

email.contains("@")        # true
email.find("example")      # 5
email.replace("example", "test")  # "user@test.com"
email.split("@")          # ["user", "example.com"]
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

config.keys()           # 获取所有键
config.values()         # 获取所有值
config.contains("debug")  # 检查键是否存在
config.remove("debug")  # 移除键值对
```

---

## 运算符

### 算术运算符

```ibci
int a = 10
int b = 3

a + b    # 加法: 13
a - b    # 减法: 7
a * b    # 乘法: 30
a / b    # 除法: 3
a % b    # 取余: 1
a ^ b    # 幂运算: 1000
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

```ibci
bool p = true
bool q = false

p && q    # 逻辑与: false
p || q    # 逻辑或: true
!p        # 逻辑非: false
```

### 三元运算符

```ibci
bool condition = true
str result = condition ? "真" : "假"
```

---

## 控制流

### if 语句

```ibci
int score = 85

if score >= 90:
    print("优秀")
else if score >= 80:
    print("良好")
else:
    print("继续努力")
```

### while 循环

```ibci
int i = 1
while i <= 5:
    print("计数: " + (str)i)
    i = i + 1
```

### for 循环（通过 while 实现）

```ibci
list items = ["a", "b", "c"]
int idx = 0
while idx < items.len():
    print((str)items[idx])
    idx = idx + 1
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

---

## 函数

### 定义函数

```ibci
def greet(name: str):
    print("你好，" + name + "！")

def add(a: int, b: int) -> int:
    return a + b
```

### 函数调用

```ibci
greet("Alice")           # 输出: 你好，Alice！
int sum = add(10, 20)    # sum = 30
```

### 递归函数

```ibci
def factorial(n: int) -> int:
    if n <= 1:
        return 1
    return n * factorial(n - 1)

int result = factorial(5)  # result = 120
```

### 嵌套函数

```ibci
def outer(x: int):
    def inner(y: int) -> int:
        return x + y
    return inner(x * 2)
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

# 类型转换
(str)42, (int)"123", (float)10

# 条件判断
if condition:
    # 代码
else if other:
    # 代码
else:
    # 代码

# 循环
while condition:
    # 代码

# 函数
def my_func(arg: Type) -> ReturnType:
    return value

# 行为描述语句（AI 调用）
str result = @~ 请打个招呼 ~

# LLM 函数
llm 翻译(str 文本, str 目标语言):
__sys__
你是一个翻译助手
__user__
请翻译：$文本
llmend

# 意图注释
@ 用简洁的方式回复
str text = @~ 说点什么 ~
```
