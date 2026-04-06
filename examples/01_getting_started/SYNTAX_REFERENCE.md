# IBCI 语法参考手册

IBCI (Intent-Behavior Code Interoperation) 是一门专注于**行为描述**的编程语言，深度集成 AI 能力。

## 目录

1. [基础概念](#基础概念)
2. [类型系统](#类型系统)
3. [运算符](#运算符)
4. [控制流](#控制流)
5. [函数](#函数)
6. [列表](#列表)
7. [字符串](#字符串)
8. [字典](#字典)
9. [意图注释](#意图注释)

---

## 基础概念

### 行为描述语句

IBCI 的核心是**行为描述语句**，用于描述"做什么"而非"怎么做"：

```ibci
# 行为描述：获取用户输入并打印
str name = input("请输入你的名字：")
print("你好，" + name)
```

### 注释

```ibci
# 单行注释

# 多行注释可以通过多个单行注释实现
# 注释1
# 注释2
```

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

### 负数

```ibci
int negative = -50            # 支持负数常量
float temp = -5.5             # 支持负浮点数
int x = -100 + 50             # 表达式中的负数
int y = 100 - 50              # 减法运算
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

## 列表

### 创建列表

```ibci
list empty = []
list numbers = [1, 2, 3, 4, 5]
list mixed = ["a", 1, true, 3.14]
```

### 访问元素

```ibci
list items = [10, 20, 30]
items[0]          # 第一个元素: 10
items[1]          # 第二个元素: 20
items.len()       # 长度: 3
```

### 列表操作

```ibci
list fruits = ["apple", "banana"]

fruits.append("cherry")       # 添加元素
fruits.insert(1, "orange")   # 插入元素
fruits.remove("banana")       # 移除元素
str removed = fruits.pop()     # 弹出元素

bool has_apple = fruits.contains("apple")  # 检查包含
int idx = fruits.index_of("cherry")       # 查找索引
```

### 列表切片

```ibci
list nums = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]

nums[0:3]      # [0, 1, 2]     - 前三个
nums[3:6]      # [3, 4, 5]     - 中间三个
nums[::2]      # [0, 2, 4, 6, 8]  - 偶数位
nums[::-1]      # [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]  - 反向
nums[7:2:-1]     # [7, 6, 5, 4, 3]  - 反向切片
```

---

## 字符串

### 创建字符串

```ibci
str s1 = "Hello"
str s2 = 'World'
str s3 = """多行
字符串"""
```

### 字符串方法

```ibci
str s = "  Hello, IBCI!  "

s.trim()         # "Hello, IBCI!"
s.to_upper()    # "  HELLO, IBCI!  "
s.to_lower()    # "  hello, ibci!  "
s.len()         # 16
```

### 字符串切片

```ibci
str text = "Hello, World!"

text[0:5]       # "Hello"
text[7:]        # "World!"
text[::2]       # "Hlo ol!"
text[::-1]       # "!dlroW ,olleH"
```

### 字符串操作

```ibci
str email = "user@example.com"

email.contains("@")        # true
email.find("example")      # 5
email.replace("example", "test")  # "user@test.com"
email.split("@")          # ["user", "example.com"]
```

---

## 字典

### 创建字典

```ibci
dict person = {
    "name": "Alice",
    "age": 25,
    "city": "Beijing"
}
```

### 访问字典

```ibci
person["name"]           # "Alice"
person["age"]            # 25

# 添加/修改
person["email"] = "alice@example.com"
person["age"] = 26
```

### 字典方法

```ibci
dict config = {"debug": true, "timeout": 30}

config.keys()           # 获取所有键
config.values()         # 获取所有值
config.contains("debug")  # 检查键是否存在
config.remove("debug")  # 移除键值对
```

---

## 意图注释

### 基本语法

使用 `#@` 语法添加意图注释：

```ibci
#@ 用户问候
str greeting = "早上好"

#@ 计算总价
int total = price * quantity
```

### 意图注释的作用

1. **代码可读性** - 帮助理解代码意图
2. **AI 理解** - 让 AI 更好地理解代码逻辑
3. **文档生成** - 自动生成代码文档
4. **代码审查** - 帮助代码审查流程

### 常见意图类型

```ibci
#@ 数据验证
if user_age >= 0 && user_age <= 150:
    print("年龄有效")

#@ 错误处理
if operation_success:
    print("操作成功")
else:
    print("操作失败")

#@ 业务逻辑
int discount = original_price * discount_rate / 100
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

# AI 调用
str response = ai.chat("你好")
```
