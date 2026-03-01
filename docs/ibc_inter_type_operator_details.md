# IBC-Inter 类型与运算符详细说明

## 类型总览

### 基本类型

- int
- float
- str
- None

### 容器类型

- list
- dict：key 仅允许 int 或 str，value 允许任意类型

## 基本类型说明

### int

```ibc-inter
int 数量 = 42
int 结果 = 数量 * 2
```

### float

```ibc-inter
float 税率 = 0.05
float 总计 = 100.0 * (1 + 税率)
```

### str

```ibc-inter
str 名字 = "张三"
str 问候 = "你好，" + 名字
```

### None

```ibc-inter
str 为空 = None
```

## 容器类型说明

### list

```ibc-inter
list 事项 = [1, "A", 3.14]
```

### dict

```ibc-inter
dict 用户 = {"name": "张三", "age": 25}
```

## 运算符说明

### 算术运算（int/float）

```ibc-inter
int a = 10
int b = 3
int 加法 = a + b
float 除法 = a / b
int 取模 = a % b
```

### 比较运算

```ibc-inter
if a > b:
    执行语句
if a == b:
    执行语句
str 文本1 = "A"
str 文本2 = "B"
if 文本1 == 文本2:
    执行语句
```

### 逻辑运算

```ibc-inter
if (a > b and b > 0):
    执行语句
if (a > b or b > 0):
    执行语句
if not (a > b):
    执行语句
```

### 位运算（int）

```ibc-inter
int 位与 = a & b
int 位或 = a | b
int 位异或 = a ^ b
int 位非 = ~a
int 左移 = a << 2
int 右移 = a >> 1
```

### 行为描述（Behavior）

行为描述是一种特殊的表达式，使用 `@~...~` 包裹。支持在内容中使用 `$变量` 或 `$__表达式__` 进行动态插值。

**插值规则：**
1. **简单插值**：`$变量名`，直接将变量值转化为字符串。
2. **复杂插值**：`$__表达式__`（双下划线包裹），支持任意合法的 IBC-Inter 表达式，如 `$__user.name__` 或 `$__items[0].price__`。

```ibc-inter
str 结果 = @~分析数据 $data.id~
for @~等待条件满足 $__count > 10__~:
    pass
```

## LLM 返回值解析 (Parsing)

当 LLM 函数定义了非 `str` 的返回类型，或处于分支/循环判定场景时，解释器会自动进行鲁棒性解析：

| 目标类型 | 解析策略 |
| :--- | :--- |
| **int / float** | 提取文本中出现的第一个数字序列。 |
| **bool** | 识别 `1/0`, `true/false`, `yes/no` 等关键词。 |
| **list / dict** | 自动提取第一个 `[...]` 或 `{...}` 块，并自动剥离 Markdown 代码块标记（如 ` ```json `）。 |

这允许 LLM 在返回结果时包含一定的解释性文字（噪声），而不会破坏程序的逻辑执行。

### 赋值运算

```ibc-inter
int x = 10
x += 5
x -= 3
x *= 2
x /= 4
x %= 2
```

### 字符串运算（str）

```ibc-inter
str 连接 = "Hello" + " " + "World"
```

## 类型转换

```ibc-inter
str 数字字符串 = "123"
int 实际数字 = (int) 数字字符串
float 浮点数 = (float) "3.14"
str 文本 = (str) 42
```

## 运算符优先级

运算符优先级从高到低：

1. 括号：`()`
2. 函数调用、属性访问：`.`、`()`
3. 一元运算符：`+x`、`-x`、`not`、`~x` (位非)
4. 乘法、除法、取模：`*`、`/`、`%`
5. 加法、减法：`+`、`-`
6. 位运算：`<<`、`>>`、`&`、`|`、`^`
7. 比较运算：`<`、`<=`、`>`、`>=`、`==`、`!=`
8. 逻辑与：`and`
9. 逻辑或：`or`
10. 赋值：`=`, `+=`, `-=`, `*=`, `/=`, `%=`
11. 行为描述：`@~...~` (作为独立表达式解析)
