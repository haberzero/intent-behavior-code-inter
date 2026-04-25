# IBC-Inter 已知限制

> 本文档记录当前版本中已知的语言设计限制和注意事项。
>
> **最后更新**：2026-04-24

---

## 一、函数返回类型注释：不支持 `-> None`

**限制说明**

函数声明中的返回类型注释（`-> <type>`）目前**不支持** `None` 作为返回类型。
原因是 `None` 是词法层面的保留关键字（`TokenType.NONE`），类型注释解析器（`TypeComponent.parse_type_annotation`）只接受标识符（IDENTIFIER）、`auto` 和 `fn` 三种形式，无法识别 `None` 关键字作为类型名。

**行为**

```ibci
# ❌ 当前会引发解析错误 (PAR_001)
func my_func() -> None:
    print("hello")
```

**建议替代方案**

使用 `void` 作为"无返回值"的显式类型注释：

```ibci
# ✅ 正确用法 —— 显式声明无返回值
func my_func() -> void:
    print("hello")

# ✅ 也可以省略返回类型注释（省略时默认使用 auto，编译器自动推断）
func my_func():
    print("hello")
```

---

## 二、`try` / `except` 语法

**限制说明**

当前 `try` / `except` / `finally` 语法自身存在设计问题，**强烈不建议使用**，将在未来版本中完善。

```ibci
# ⚠️ 强烈不建议使用——存在设计问题，行为可能不符合预期
try:
    ...
except SomeException as e:
    ...
finally:
    ...
```

如需处理 LLM 不确定性结果，请优先使用专为此场景设计的 `llmexcept` 语法。

---

## 三、`fn` 变量与可调用类实例

**限制说明**

当前 `fn` 变量语法以及所有的可调用类实例（即实现了 `__call__` 方法的用户自定义类的实例）自身存在设计问题，**强烈不建议使用**，将在未来版本中完善。

```ibci
# ⚠️ 强烈不建议使用——存在设计问题，行为可能不符合预期
fn f = some_function

class MyCallable:
    func __call__():
        ...

MyCallable obj = MyCallable()
obj()  # ⚠️ 可调用类实例的调用方式存在设计问题
```

---

## 四、`Enum` 语法

**支持状态**：当前版本已提供基础 `Enum` 支持，但存在以下使用约束需要注意。

### 4.1 声明方式

`Enum` 通过继承内置 `Enum` 类实现，成员字段必须显式声明类型（当前版本仅支持 `str` 类型的枚举成员）：

```ibci
class Color(Enum):
    str RED   = "RED"
    str GREEN = "GREEN"
    str BLUE  = "BLUE"
```

### 4.2 访问与比较

枚举成员通过类名访问（`Color.RED`），支持 `==` / `!=` 比较：

```ibci
Color c = Color.BLUE

# 访问
print((str)Color.RED)    # 输出: RED

# 比较
if c == Color.BLUE:
    print("blue")

# switch/case（枚举的推荐控制流形式）
switch c:
    case Color.RED:
        print("red")
    case Color.BLUE:
        print("blue")
    default:
        print("other")
```

### 4.3 当前限制

- **仅支持 `str` 类型成员**：枚举成员的底层值目前只能声明为 `str` 类型。`int` 等其他类型成员在未来版本中支持。
- **不支持枚举迭代**：当前无法对枚举类的所有成员进行遍历（如 `for v in Color:`）。
- **不支持枚举数量/序数查询**：`len(Color)`、成员序号等功能暂不支持。
- **LLM 集成**：`Enum` 类型已具备 `IlmoutputHintCapability`，LLM 函数可以直接输出枚举成员名称并自动解析为对应枚举值。

---

## 五、`Uncertain` 字面量与 `is_uncertain()` 函数

### 5.1 `Uncertain` 字面量

`Uncertain` 是全局可见的特殊字面量（与 `None` 保持命名一致），表示 LLM 调用因重试耗尽而无法得到确定结果时产生的特殊值。

```ibci
# Uncertain 字面量用法
auto x = Uncertain

# 布尔上下文中为假
if x:
    print("不会执行")
else:
    print("Uncertain 是假值")

# 强制转换为字符串得到 "uncertain"
print((str)x)    # 输出: uncertain
```

### 5.2 `is_uncertain(r)` 内置函数

提供专用内置函数 `is_uncertain(r)` 用于检测一个值是否为 `Uncertain`：

```ibci
auto result = Uncertain
if is_uncertain(result):
    print("结果不确定")

# 与 None 的区别
auto n = None
print(is_uncertain(n))       # False —— None 不是 Uncertain
print(is_uncertain(Uncertain)) # True
```

### 5.3 与 `None` 的区别

| 特性 | `None` | `Uncertain` |
|------|--------|-------------|
| 语义 | 空值/无值 | LLM 调用结果不确定 |
| 布尔值 | 假 | 假 |
| `(str)` 强转 | `"None"` | `"uncertain"` |
| 检测函数 | 无专用函数（用 `== None` 比较） | `is_uncertain(r)` |
| 来源 | 手动赋值或函数无返回 | LLM 调用重试耗尽后自动赋值 |

### 5.4 暂不支持的用法

当前版本**不提供** `r.is_uncertain()` 实例方法形式，请统一使用全局函数 `is_uncertain(r)`。

---

## 六、字符串比较运算符

**支持状态**：当前版本已支持字符串的 `<`、`<=`、`>`、`>=` 词法顺序比较。

```ibci
bool r1 = "apple" < "banana"    # True（词法顺序）
bool r2 = "zebra" > "alpha"     # True
bool r3 = "abc" <= "abc"        # True
bool r4 = "xyz" >= "abc"        # True
```

比较语义遵循 Unicode 码点顺序（等同于 Python `str` 的比较语义）。

---

## 七、行为表达式不可直接用于 `return` 语句

**限制说明**

行为表达式（`@~ ... ~`）的输出类型和提示词约束由左值类型驱动（即赋值目标的类型）。
在 `return` 语句中直接书写行为表达式时，由于无法从函数返回类型标注中以静态明确的方式推导出提示词约束，编译器**禁止**此写法，报 `SEM_003` 错误。

**行为**

```ibci
# ❌ SEM_003：不允许在 return 中直接使用行为表达式
func get_reply() -> str:
    return @~ 给我一句话 ~
```

**正确用法**

先将行为表达式赋值给有类型的局部变量，再 `return` 该变量：

```ibci
# ✅ 正确：通过有类型的局部变量明确输出约束
func get_reply() -> str:
    str reply = @~ 给我一句话 ~
    return reply
```

**设计原因**

行为表达式的目标类型同时决定了注入给 LLM 的输出格式约束（通过 `__outputhint_prompt__`）以及 LLM 返回值的解析方式（通过 `__from_prompt__`）。将其绑定到明确的左值类型可以保证语义清晰、无歧义，而不是将执行语义与函数签名隐式耦合。


---

## 二、`try` / `except` 语法

**限制说明**

当前 `try` / `except` / `finally` 语法自身存在设计问题，**强烈不建议使用**，将在未来版本中完善。

```ibci
# ⚠️ 强烈不建议使用——存在设计问题，行为可能不符合预期
try:
    ...
except SomeException as e:
    ...
finally:
    ...
```

如需处理 LLM 不确定性结果，请优先使用专为此场景设计的 `llmexcept` 语法。

---

## 三、`fn` 变量与可调用类实例

**限制说明**

当前 `fn` 变量语法以及所有的可调用类实例（即实现了 `__call__` 方法的用户自定义类的实例）自身存在设计问题，**强烈不建议使用**，将在未来版本中完善。

```ibci
# ⚠️ 强烈不建议使用——存在设计问题，行为可能不符合预期
fn f = some_function

class MyCallable:
    func __call__():
        ...

MyCallable obj = MyCallable()
obj()  # ⚠️ 可调用类实例的调用方式存在设计问题
```

---

## 四、`Enum` 语法

**支持状态**：当前版本已提供基础 `Enum` 支持，但存在以下使用约束需要注意。

### 4.1 声明方式

`Enum` 通过继承内置 `Enum` 类实现，成员字段必须显式声明类型（当前版本仅支持 `str` 类型的枚举成员）：

```ibci
class Color(Enum):
    str RED   = "RED"
    str GREEN = "GREEN"
    str BLUE  = "BLUE"
```

### 4.2 访问与比较

枚举成员通过类名访问（`Color.RED`），支持 `==` / `!=` 比较：

```ibci
Color c = Color.BLUE

# 访问
print((str)Color.RED)    # 输出: RED

# 比较
if c == Color.BLUE:
    print("blue")

# switch/case（枚举的推荐控制流形式）
switch c:
    case Color.RED:
        print("red")
    case Color.BLUE:
        print("blue")
    default:
        print("other")
```

### 4.3 当前限制

- **仅支持 `str` 类型成员**：枚举成员的底层值目前只能声明为 `str` 类型。`int` 等其他类型成员在未来版本中支持。
- **不支持枚举迭代**：当前无法对枚举类的所有成员进行遍历（如 `for v in Color:`）。
- **不支持枚举数量/序数查询**：`len(Color)`、成员序号等功能暂不支持。
- **LLM 集成**：`Enum` 类型已具备 `IlmoutputHintCapability`，LLM 函数可以直接输出枚举成员名称并自动解析为对应枚举值。

---

## 五、`Uncertain` 字面量与 `is_uncertain()` 函数

### 5.1 `Uncertain` 字面量

`Uncertain` 是全局可见的特殊字面量（与 `None` 保持命名一致），表示 LLM 调用因重试耗尽而无法得到确定结果时产生的特殊值。

```ibci
# Uncertain 字面量用法
auto x = Uncertain

# 布尔上下文中为假
if x:
    print("不会执行")
else:
    print("Uncertain 是假值")

# 强制转换为字符串得到 "uncertain"
print((str)x)    # 输出: uncertain
```

### 5.2 `is_uncertain(r)` 内置函数

提供专用内置函数 `is_uncertain(r)` 用于检测一个值是否为 `Uncertain`：

```ibci
auto result = Uncertain
if is_uncertain(result):
    print("结果不确定")

# 与 None 的区别
auto n = None
print(is_uncertain(n))       # False —— None 不是 Uncertain
print(is_uncertain(Uncertain)) # True
```

### 5.3 与 `None` 的区别

| 特性 | `None` | `Uncertain` |
|------|--------|-------------|
| 语义 | 空值/无值 | LLM 调用结果不确定 |
| 布尔值 | 假 | 假 |
| `(str)` 强转 | `"None"` | `"uncertain"` |
| 检测函数 | 无专用函数（用 `== None` 比较） | `is_uncertain(r)` |
| 来源 | 手动赋值或函数无返回 | LLM 调用重试耗尽后自动赋值 |

### 5.4 暂不支持的用法

当前版本**不提供** `r.is_uncertain()` 实例方法形式，请统一使用全局函数 `is_uncertain(r)`。

---

## 六、字符串比较运算符

**支持状态**：当前版本已支持字符串的 `<`、`<=`、`>`、`>=` 词法顺序比较。

```ibci
bool r1 = "apple" < "banana"    # True（词法顺序）
bool r2 = "zebra" > "alpha"     # True
bool r3 = "abc" <= "abc"        # True
bool r4 = "xyz" >= "abc"        # True
```

比较语义遵循 Unicode 码点顺序（等同于 Python `str` 的比较语义）。
