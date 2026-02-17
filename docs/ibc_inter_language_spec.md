# IBC-Inter 语言规范

IBC-Inter（Interactive/Interpreted Intent Behavior Code）是一种面向过程、流程化执行的交互式意图行为代码语言。IBC-Inter专注于直接逐行运行，利用LLM进行自然语言代码执行。

IBC-Inter 中，绝大多数保留关键字是以位置敏感的方式进行作用。绝大多数关键字只允许在行首使用，从而避免关键字干扰自然语言表达。

## 语法规则

### 1. 模块导入 (import)

```ibc-inter
import module_name
from module_name import specific_function
from module_name import specific_function as alias
import module_name as alias
from module_name import *
```

示例：

```ibc-inter
import json
from utils.logger import Logger
from config.settings import load_config as load_cfg
import requests as http
from math import *
```

### 2. 函数定义 (func)

函数必须为每个参数显式声明类型，采用类型在前的写法。支持显式返回值类型标注，使用 `-> 类型`，目前只允许单一返回值：

```ibc-inter
func 函数名(类型 参数1, 类型 参数2, ...) -> 类型:
    函数体
    返回 结果
```

示例：

```ibc-inter
func 计算总价(list 商品列表, float 税率) -> float:
    int 总价 = 0
    for 商品 in 商品列表:
        总价 = 总价 + 商品.价格
    返回 总价 * (1 + 税率)
```

### 3. LLM函数 (llm)

LLM函数是一种特殊的函数，用于调用LLM模型执行自然语言任务。LLM函数的返回值固定为str。参数仅支持 int 与 str 类型，不支持容器类型。

自然语言函数，无缩进，使用llmend结束。`__sys__`、`__user__`、`llmend` 只有单独一行书写时才作为关键字生效；如果出现在行内，会被视为提示词文本的一部分并原样发送，不会起到特殊作用：

```ibc-inter
llm 函数名(int 参数1, str 参数2, ...):

__sys__
系统提示词内容

__user__
用户提示词内容，包含 $__参数1__、$__参数2__ 等占位符，占位符前后需使用空格与其他文本分割，llmend在此不作为关键字进行作用

llmend
```

示例：

```ibc-inter
llm 生成欢迎消息(str 用户名, str 产品名称):

__sys__
你是一个友好的客服助手，需要生成个性化的欢迎消息

__user__
请为用户名 $__用户名__ 生成一个关于产品 $__产品名称__ 的欢迎消息，要求温暖亲切

llmend
```

### 4. 运行时意图注释 (@)

意图注释在LLM函数调用时动态注入系统提示词，作用于运行时而非定义时：

```ibc-inter
llm 分析用户反馈(str 反馈文本):

__sys__
你是用户反馈分析专家

__user__
请分析以下用户反馈：__反馈文本__

llmend

@ 需要特别关注用户隐私保护
str 结果 = 分析用户反馈(用户输入)

# 调用时的系统提示词会被动态增强为：
# 你是用户反馈分析专家
# 你需要特别额外注意的是：需要特别关注用户隐私保护
```

意图注释也可以作用于行为描述行：

```ibc-inter
@ 对于用户的负面评价需要进行特别标注
str 分析结果 = ~~分析文本情感 $用户评论 ~~
```

### 5. 行为描述行（双波浪号包裹触发）

行为描述行使用双波浪号 `~~` 包裹，支持在行首、表达式右值或控制流条件中使用。

基本规则：

1. **触发与结束**：以 `~~` 开始，以 `~~` 结束。
2. **内容书写**：行为描述内容被视为纯文本（Raw Text）。如果需要在行为描述行中书写 `~~` 或 `$`，请使用反斜杠转义：
    - `\$`：表示美元符号 `$`（作为普通文本，而非变量引用）。
    - `\~`：表示单波浪号 `~`（作为普通文本）。
    - `\~~`：表示双波浪号 `~~`（作为普通文本，而非结束符）。
    - 其他字符前的反斜杠 `\` 将保持原样，不做转义处理。这意味着可以直接书写包含 `\` 的路径或文本（除非恰好是 `\~` 或 `\$`，此时需双写 `\\` 来表示反斜杠）。

**示例：**

```ibc-inter
# 单行基础用法
str 分析结果 = ~~分析用户情绪 $用户评论内容~~

# 包含特殊字符的转义
str 特殊文本 = ~~包含 \~\~ 和 100\$ 的文本~~

# 跨行书写（直接换行）
str 复杂指令 = ~~分析以下内容：
    第一部分：$content1
    第二部分：$content2~~

# 包含特殊字符（无需转义）
if ~~判断 $用户输入 是否包含 ~ 或 \ 符号~~:
    pass
```

行为描述行仍需要解析波浪号外侧的行首关键字（如 if、for、var 或类型关键字），用于控制流与变量赋值。

### 6. 字符串字面量与 Raw String

IBC-Inter 支持标准字符串和 Raw String（原始字符串）。

#### 标准字符串

使用双引号 `"` 或单引号 `'` 包裹。支持标准转义序列（如 `\n`, `\t`, `\"`, `\\` 等）。

```ibc-inter
str s1 = "Hello\nWorld"
str s2 = 'It\'s me'
```

#### Raw String (原始字符串)

使用 `r` 前缀，如 `r"..."` 或 `r'...'`。在 Raw String 中，反斜杠 `\` 不会被视为转义字符（除非用于转义引号本身，但反斜杠仍会保留）。

```ibc-inter
str path = r"C:\Windows\System32"
str regex = r"\d+\s+\w+"
```

### 7. 控制流语法

#### if语句

```ibc-inter
if 条件:
    执行语句
elif 其他条件:
    其他执行语句
else:
    默认执行语句
```

#### for循环

```ibc-inter
for 数字:
    循环体

for i in 数字:
    循环体

for i in list:
    循环体

for ~~行为描述表达~~:
    循环体
```

### 7. 变量声明与类型

IBC-Inter 使用显式类型关键字声明变量，同时提供 var 作为灵活性变量。可选使用显式类型并初始化，或先声明后赋值：

```ibc-inter
int 计数 = 0
float 税率 = 0.06
str 用户名 = "张三"
list 商品列表 = ["A", "B"]
dict 配置 = {"模式": "快速"}
int 未赋值
var 临时值 = 0
```

### 8. 数据类型系统

IBC-Inter 仅支持以下类型：

#### 基本类型

- `int`: 整数 `42`, `-10`
- `float`: 浮点数 `3.14`, `-0.5`
- `str`: 字符串 `"hello"`, `'world'`

#### 容器类型

- `list`: 有序集合，允许存放任意类型，但不允许容器嵌套 `[1, "a", 3.14]`
- `dict`: 键值对集合，key 只允许 int 或 str，value 允许任意类型，但不允许容器嵌套 `{"name": "张三", "age": 25}`

#### 空值

- `None`: 空值 `None`

#### 类型转换

```ibc-inter
str 数字字符串 = "123"
int 实际数字 = (int) 数字字符串
float 浮点数 = (float) "3.14"
str 文本 = (str) 42

# 未赋值变量默认值为 None
str 空值变量 
```

#### 运行时类型规则（最小可用）

- 明确代码行若出现语法错误或类型错误，直接报错并停止解释运行
- var 为动态类型，首次赋值决定当前类型；后续允许改变类型
- 显式类型变量仅允许同类型赋值，None 允许赋值给任意显式类型变量
- None 仅支持与自身进行相等/不等比较
- int 与 float 之间允许在算术中混用，结果按语义产出 int 或 float
- str 仅支持加号连接与相等/不等比较
- list 和 dict 不允许嵌套容器，若出现嵌套直接报错
- dict 的 key 只允许 int 或 str

### 9. 运算符系统

仅保留常用示例，完整说明见单独文件：docs/ibc_inter_type_operator_details.md

#### 数值运算（int/float）

```ibc-inter
int a = 10
int b = 3
int 加法 = a + b
float 除法 = a / b
```

#### 字符串运算（str）

```ibc-inter
str 欢迎 = "Hello" + " " + "World"
```

#### 比较与逻辑

```ibc-inter
if a > b:
    执行语句
if a == b:
    执行语句
if not (a > b):
    执行语句
```

## 独立示例

### 示例1

```ibc-inter
# 模块导入
import 模块名
from 模块名 import 函数名

# 传统函数定义
func 函数名(int 参数) -> int:
    int 变量 = 值
    返回 结果

# 主程序逻辑
int 结果 = 处理数据(输入数据)

# LLM函数定义（文件末尾）
llm 函数名(int 参数):

__sys__
系统提示词

__user__
处理 $__参数__ 并返回结果

llmend
```
