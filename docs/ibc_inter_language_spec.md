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
from core.logger import Logger
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

LLM函数是一种特殊的函数，用于调用LLM模型执行自然语言任务。LLM函数支持多种返回值类型（int, float, bool, str, list, dict），默认为 str。参数支持所有基本类型与容器类型（int, float, str, bool, list, dict, ClassInstance）。

自然语言函数，无缩进，使用llmend结束。`__sys__`、`__user__`、`llmend` 只有在行首（忽略空格/制表符）书写时才作为关键字生效；如果出现在行中（非行首），会被视为提示词文本的一部分并原样发送。

> **注意**：虽然关键字通常独占一行，但 IBC-Inter 允许在 `__sys__` 或 `__user__` 同行后面直接书写提示词文本，解释器会自动将其识别为该段落的起始内容。

```ibc-inter
llm 函数名(类型 参数1, 类型 参数2, ...) -> 返回类型:
```

__sys__
系统提示词内容

__user__
用户提示词内容，包含 $__参数1__、$__表达式__ 等占位符。占位符使用 `$__` 和 `__` 包裹，中间支持任意合法的 IBC-Inter 表达式（如 `$__self.name__` 或 `$__list[0]__`）。

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

意图注释在 LLM 调用时动态注入系统提示词，作用于运行时而非定义时。IBC-Inter 2.0 引入了**层级化意图 (Layered Intent)** 机制，支持全局、块级和调用级的意图叠加。

**核心规则：**
1. **支持对象**：
    - **命名 LLM 函数调用**：`@ 意图内容` 直接作用于随后的 LLM 函数。
    - **行为描述行 (@~)**：前置的意图注释会自动注入到该行为行的执行上下文中。
2. **修饰符 (Modifiers)**：
    - `@+ "意图内容"` (默认): 显式声明叠加到当前所有层级之上。
    - `@! "意图内容"`: **唯一模式**。忽略所有全局 (Global) 和块级 (Block) 意图，仅使用此行定义的意图。
    - `@- "意图内容"`: **排除模式**。在本次调用中显式移除某条已存在的全局或块级意图。
3. **Lambda 化行为**：如果行为描述行被赋值给 `callable` 变量，意图注释会在该变量被**定义时**捕获，并在后续**调用时**生效。
4. **非 LLM 场景警告**：如果附加在无法消耗意图的语句上，解释器会报出 **Warning** 警告。

```ibc-inter
import ai
ai.set_global_intent("使用鲁迅的文风")

@! 请使用严谨的学术风格
str res = @~ 描述什么是 IBCI ~
# 输出将只遵循“学术风格”，忽略全局的“鲁迅文风”
```

### 5. 意图块 (intent)

意图块允许在特定的代码范围内应用一组意图。

```ibc-inter
intent "设定文本":
    # 该块内所有 LLM 调用都会自动合并此意图
    执行语句
```

**独占模式**：使用 `intent !` 可以创建一个屏蔽所有全局意图的区域。

```ibc-inter
intent ! "在此块内忽略全局设定":
    @~ 执行任务 ~
```

### 6. 行为描述行（@~ 包裹触发）

行为描述行使用 `@~` 开始，以 `~` 结束。支持在行首、表达式右值或控制流条件中使用。

**基本规则：**

1. **触发与结束**：以 `@~`（或带有标签的 `@tag~`）开始，以 `~` 结束。
2. **立即执行 vs 延迟执行**：
    - **立即执行**：直接作为右值或条件使用时，立即发起 LLM 调用。
    - **延迟执行 (Lambda)**：当赋值给 `callable` 类型变量时，封装为匿名函数，仅在被调用时执行。
3. **运行时类型转换**：当行为描述行被赋值给显式类型变量（如 `int`, `float`, `bool`, `list`, `dict`）时，内核会尝试自动解析 LLM 返回的字符串并转换为目标类型。
4. **内容书写**：行为描述内容被视为纯文本（Raw Text）。支持使用 `$变量名` 进行简单插值，也支持使用 `$对象.属性` 或 `$容器[索引]` 进行链式访问。支持使用 `\$` 和 `\~` 进行转义。

**示例：**

```ibc-inter
# 立即执行并自动转换为 int
int 数量 = @~ 数一下 $text 里的单词数 ~

# Lambda 化：定义时不执行
callable 动态分析 = @~ 分析 $data 的情感倾向 ~
# ... 稍后执行
str 结果 = 动态分析()
```

行为描述行仍需要解析外侧的行首关键字（如 if、for、var 或类型关键字），用于控制流与变量赋值。

### 7. 字符串字面量与 Raw String

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

### 8. 控制流语法

#### if 语句

```ibc-inter
if 条件:
    执行语句
elif 其他条件:
    其他执行语句
else:
    默认执行语句
```

**意图驱动分支 (llmexcept)：**
当 `if` 或 `elif` 的条件包含行为描述（`@~...~`）时，若 LLM 返回结果不明确，可使用 `llmexcept` 进行捕获处理。

```ibc-inter
if @~用户输入 $input 是否包含负面情绪~:
    print("处理负面情绪")
llmexcept:
    # 修复逻辑，例如提供更具体的提示或重试
    ai.set_retry_hint("请忽略语气词，只看核心诉求")
    retry
```

#### while 循环

```ibc-inter
while 条件:
    循环体
```

同样支持 `llmexcept` 用于处理意图判定的不确定性。

#### for 循环

```ibc-inter
# 1. 固定次数循环 (直接指定 int)
for 数字:
    循环体

# 2. 条件驱动循环 (通用布尔表达式或行为描述)
# 如果没有 'in' 且不是纯数值常量，则作为条件驱动模式运行
for @~行为描述表达~:
    循环体

for a > b:
    循环体
```

**意图/条件驱动循环模式：**
当 `for` 关键字后跟行为描述（`@~...~`）或任何布尔表达式，且没有 `in` 时，解释器进入“条件驱动”模式。该模式下：

- 每次迭代开始前，均会重新评估条件（如果是行为描述，则重新发起 LLM 调用）。
- 如果是 LLM 判定，返回值被严格解析为布尔值（1 表示继续，0 表示停止）。
- 支持 `llmexcept` 进行不确定性修复，支持 `retry` 重试当前判定的 LLM 请求。

# 3. 标准迭代模式 (遍历 list 或 range)
for i in list:
    循环体

#### 循环控制

支持 `break`（跳出循环）和 `continue`（跳过当前迭代）。

### 9. 变量声明与类型

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

### 10. 数据类型系统

IBC-Inter 仅支持以下类型：

#### 基本类型

- `int`: 整数 `42`, `-10`
- `float`: 浮点数 `3.14`, `-0.5`
- `str`: 字符串 `"hello"`, `'world'`
- `callable`: 可调用对象类型，用于存储函数、LLM 函数或 Lambda 化的行为描述行。

#### 容器类型

- `list`: 有序集合，允许存放任意类型 `[1, "a", 3.14]`
- `dict`: 键值对集合，key 只允许 int 或 str，value 允许任意类型 `{"name": "张三", "age": 25}`

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
- **None 比较**：允许与任意类型进行相等/不等比较
- int 与 float 之间允许在算术中混用，结果按语义产出 int 或 float
- str 仅支持加号连接与相等/不等比较
- list 和 dict 强烈不建议嵌套容器，容器嵌套机制的实现尚不完善
- dict 的 key 只允许 int 或 str
- **自动行为转换**：当行为描述行 `@~...~` 被赋值给显式类型变量时，内核会自动进行类型转换尝试（由 `ai` 模块配置支持）。

### 11. 运算符系统

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

### 12. 异常处理

IBC-Inter 支持标准异常处理机制，用于捕获运行时错误或主动抛出异常。

#### try...except 语句

```ibc-inter
try:
    # 可能产生错误的代码
    int 结果 = 10 / 0
except Exception as e:
    # 捕获所有异常
    print("发生错误: " + e)
finally:
    # 无论是否发生错误都会执行
    print("清理工作")
```

支持捕获特定类型的异常：

```ibc-inter
try:
    import non_existent_module
except "InterpreterError" as e:
    print("解释器错误: " + e)
```

#### raise 语句

使用 `raise` 主动抛出异常：

```ibc-inter
if 用户年龄 < 0:
    raise "年龄不能为负数"
```

### 13. 类系统 (class)

IBC-Inter 提供基础的面向对象支持，允许定义类、属性和方法。

#### 类定义与实例化

使用 `class` 关键字定义类。类体内可以包含带类型的属性声明（可选初始值）和方法定义。

```ibc-inter
class User:
    str name = "Guest"
    int age
    
    func __init__(str n, int a):
        self.name = n
        self.age = a
        
    func say_hello():
        print("Hello, I am " + self.name)

# 实例化
var u = User("Alice", 25)
u.say_hello()
```

#### 核心规则

1.  **构造函数**：`__init__` 方法在实例化时被调用。
2.  **self 引用**：类方法必须显式接收第一个参数 `self` 以访问实例属性。
3.  **属性访问**：支持使用 `.` 运算符读写实例属性（如 `u.name = "Bob"`）。
4.  **方法调用**：通过实例调用方法会自动注入 `self`。
5.  **LLM 方法支持**：类内可以定义 `llm` 方法，并能通过 `$__self.attr__` 访问实例状态。
6.  **提示词协议 (`__to_prompt__`)**：当类实例用于 LLM 插值时，如果定义了 `func __to_prompt__(self) -> str`，内核会调用它来获取该对象在 Prompt 中的表现形式，实现 AI 视角与代码逻辑的解耦。

```ibc-inter
class NPC:
    str name
    int secret_id = 999
    
    func __to_prompt__(self) -> str:
        return "NPC(Name: " + self.name + ")"

NPC n = NPC("小明")
@~ 你好 $n ~ # AI 看到的插值结果是 "你好 NPC(Name: 小明)"，而非包含 secret_id 的完整快照。
```

```ibc-inter
class Assistant:
    str role = "Helper"
    
    llm chat(str msg):
    __sys__
    You are a $__self.role__
    __user__
    $__msg__
    llmend
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
