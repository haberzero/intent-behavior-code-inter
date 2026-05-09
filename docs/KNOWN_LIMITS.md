# IBC-Inter 已知限制

> 本文档记录当前版本中已知的语言设计限制和注意事项。
>
> **最后更新**：2026-04-27（验证代码与文档一致性；删除 KNOWN_LIMITS.md 重复章节；修正 `get_intent_context()` 幻觉 API → `intent_context.get_current()`；690 个测试通过）

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

## 八、链式下标 `(expr)[index]` 语法不支持

**限制说明**

不支持对括号分组表达式直接进行下标访问：

```ibci
tuple nested = ((1, 2), (3, 4))
print((str)(nested[0])[1])   # ❌ PAR_001：解析器将 (nested[0]) 识别为强制类型转换语法
```

**根因**：解析器将括号内的表达式优先识别为 `(TypeName)` 类型转换语法，导致后续 `[1]` 无法正确解析。

**规避方案**：引入临时变量：

```ibci
tuple inner = (tuple)nested[0]
print((str)inner[1])    # ✅ 正常工作
```

---

## 九、类字段仅字面量常量默认值可靠

**限制说明**

类字段初始化时，仅 `int`/`str`/`bool`/`float` 字面量常量和空字面量（`[]`、`{}`）作为默认值可靠工作。函数调用、构造器调用等动态表达式作为字段默认值的行为不可靠。

```ibci
class Config:
    int version = 1        # ✅ 正常
    str name = "IBCI"      # ✅ 正常
    list items = []        # ✅ 正常（已修复 Bug #1）
    int size = compute()   # ⚠️ 不可靠，建议在 __init__ 中初始化
```

**规避方案**：通过 `__init__` 构造函数进行动态字段初始化：

```ibci
class Stack:
    list items

    func __init__(self):
        self.items = []    # ✅ 每个实例独立创建
```

---

## 十、子类 auto-init 不含父类字段

**限制说明**

当子类没有显式 `__init__`，编译器自动生成的 `__init__`**仅接受当前类自身声明的字段**，不包含父类字段。父类字段在实例化时保持为 `None`（未初始化）。

```ibci
class Animal:
    str name

class Dog(Animal):
    str breed        # Dog 的 auto-init 只接受 breed，不接受 name

Dog d = Dog("Husky")    # 只设置 breed；d.name = None（未初始化）
print(d.name)           # 输出 None
```

**规避方案**：在子类中显式定义 `__init__`，手动初始化父类字段：

```ibci
class Dog(Animal):
    str breed

    func __init__(self, str dog_name, str dog_breed):
        self.name = dog_name
        self.breed = dog_breed
```

此行为与 Python 一致（子类不自动调用 `super().__init__`）。

---

## 十一、引用语义：复合对象共享引用

**说明**

IBCI 对所有复合对象（`list`、`dict`、用户类实例）使用**共享引用**语义（与 Python 一致）。

### 11.1 赋值是引用复制，不是值复制

```ibci
list a = [1, 2, 3]
list b = a          # b 与 a 指向同一个列表对象
b.append(4)
print((str)a.len()) # 输出 4，不是 3
```

**规避方案**：手动构造副本：

```ibci
list a = [1, 2, 3]
list b = []
for int x in a:
    b.append(x)
```

### 11.2 `llmexcept` 快照隔离不自动还原容器内容

`llmexcept` 的 `__snapshot__`/`__restore__` 协议快照并恢复变量绑定（变量名→对象的映射），但不自动还原容器的**内部元素**。若 LLM 调用体内对容器执行 `append`/`remove` 等就地修改，retry 后这些修改不会被还原。

**规避方案**：不要在 `llmexcept` 保护块的 LLM 调用路径中就地修改容器；若需可回滚的容器状态，可实现 `__snapshot__`/`__restore__` 用户协议（见 §九）。



