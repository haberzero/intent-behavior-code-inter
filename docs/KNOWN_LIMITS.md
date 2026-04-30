# IBC-Inter 已知限制（语言级）

> 本文档记录当前版本中**正式承认的语言设计限制**：偏向"用法约束 + 设计取向 + 根源说明"。
> 历史 Bug 修复记录已归档至 `docs/COMPLETED.md` §二十一。
> **最后更新**：2026-04-29（合并 `BUG_REPORTS.md` 中的语言级限制条目：链式下标语法、类字段调用表达式默认值、子类 auto-init、引用语义、auto/fn/any 对比、容器多类型、已废弃语法；989 个测试通过）

---

## 一、函数返回类型注释：不支持 `-> None`

**限制说明**

函数声明中的返回类型注释（`-> <type>`）目前**不支持** `None` 作为返回类型。

**根源**

`None` 是词法层面的保留关键字（`TokenType.NONE`），类型注释解析器（`TypeComponent.parse_type_annotation`）只接受标识符（IDENTIFIER）、`auto` 和 `fn` 三种形式，无法识别 `None` 关键字作为类型名。要支持 `-> None` 需在 type annotation 解析路径中显式接受 `NONE` token。

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

**根源**

`try`/`except` 是早期为兼容传统语言习惯而保留的关键字，但 IBCI 的核心健壮性叙事是
"LLM 不确定性 → `llmexcept` 快照隔离"。`try`/`except` 自身的异常类型层级、`raise` 语义、
`finally` 资源释放路径在当前解释器实现中并未与 `LLMExceptFrame` / `IbLLMCallResult` 对齐——
词法 / 解析层接受 `try`/`except`/`raise`/`finally`，运行时按顺序执行各分支，但**不会真正捕获**
非语言级的运行时异常。后续会与"unification with `llmexcept`"或"完整 try/except 重构"一并落地。

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

## 三、可调用类实例（`__call__` 协议）

**限制说明**

可调用类实例（即实现了 `__call__` 方法的用户自定义类的实例）在调用方式上存在设计问题，**不建议使用**。

**根源**

`fn` 类型推断对 `__call__` 协议与闭包捕获、意图栈副作用的若干交叉路径存在不一致——尤其是当可调用类实例内部触发 `@~...~` 或意图栈相关副作用时，类型推断与运行时分发之间的错位可能产生静默错误。

> **注**：`fn` 变量搭配 `lambda`/`snapshot` 的语法已在 D1/D2（2026-04-29）完成清洁化：  
> 返回类型标注已从声明侧（`TYPE fn f = lambda: EXPR`，已废弃）迁移至表达式侧  
> （`fn f = lambda -> TYPE: EXPR`）。可调用类实例问题独立于此，不受影响。

```ibci
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

## 八、`str + Uncertain` 拼接：过渡期允许，未来将禁止

**当前行为（过渡期）**

`str` 类型变量在运行时持有 `Uncertain`（例如 `llmretry` 重试耗尽后）时，与字符串的 `+` 拼接被允许，且 `Uncertain` 被视作字符串 `"uncertain"` 参与拼接。这是为了避免 `print("结果: " + r)` 这类常见调试模式在 LLM 失败后立刻 RUNTIME_ERROR 的"安静崩溃"路径。

```ibci
# ✅ 当前过渡期允许
str r = @~ MOCK:FAIL ~ llmretry "..."
print("结果: " + r)    # 输出："结果: uncertain"
```

**未来计划**

后续解释器架构升级（引入更完善的 except / 不确定性异常机制）后，本行为将被禁止：`str + Uncertain`
将不再隐式 coerce，相关错误路径将由统一的 `try/except`（或与之等价的不确定性异常处理器）接管。
届时 `Uncertain` 必须由 `is_uncertain(r)` 显式判断后再处理。

**根源**

`IbString.__add__` 与 `StrAxiom.resolve_operation_type_name` 当前对 `llm_uncertain` 操作数做了
显式放行（参见 `core/runtime/objects/builtins.py` / `core/kernel/axioms/primitives.py` 中的 TODO 注释）。

---

## 九、链式下标 `(expr)[index]` 语法不支持

**严重级别**：低（可用临时变量规避）

**根源**：解析器将 `(nested[0])` 中的括号识别为强制类型转换语法 `(TypeName)`，而非分组表达式，导致 `[1]` 无法正确解析。

```ibci
# ❌ PAR_001：Expect type name
tuple nested = ((1, 2), (3, 4))
print((str)(nested[0])[1])

# ✅ 规避方案：用临时变量承接
tuple inner = (tuple)nested[0]
print((str)inner[1])
```

---

## 十、类字段不支持调用表达式作为默认值

类字段初始化表达式中，只有字面量常量（`int` / `str` / `bool` / `list[]` / `dict{}`）可靠工作。函数调用、构造器调用等动态表达式作为字段默认值均不可靠。

**规避方案**：始终通过 `__init__` 构造函数进行动态字段初始化。

---

## 十一、子类 auto-init 不含父类字段

**严重级别**：低（符合 Python 语义，但与 C++/Java 使用者直觉不符）

当子类没有显式 `__init__`，编译器会自动生成一个 `__init__`，**仅接受当前类自身声明的字段**，不包含父类字段。

```ibci
class Animal:
    str name

class Dog(Animal):
    str breed       # Dog 的 auto-init 只接受 breed，不接受 name

Dog d = Dog("Husky")    # 只设置 breed；d.name = None
```

**规避方案**：在子类中显式定义 `__init__` 手动初始化父类字段，或在构造后赋值。

**根源**：auto-init 生成逻辑（`interpreter.py:_hydrate_user_classes`）仅遍历当前类 `body` 中声明的字段。父类字段通过 `default_fields` 继承，但不加入构造函数参数。此设计与 Python 行为一致（子类不自动调用 `super().__init__`）。

---

## 十二、引用语义局限性

IBCI 对所有复合对象（`list` / `dict` / 用户类实例）使用**共享引用**语义——与 Python 一致。

### 12.1 赋值是引用复制

```ibci
list a = [1, 2, 3]
list b = a          # b 与 a 指向同一个列表
b.append(4)
print((str)a.len()) # 输出 4
```

**规避方案**：手动构造副本（IBCI 暂未提供 `copy` / `deepcopy` 内建）：

```ibci
list b = []
for int x in a:
    b.append(x)
```

### 12.2 类实例字段的默认引用陷阱

若多个实例共享同一个"默认"列表字段，修改一个实例的字段会影响其他实例。**始终在构造函数中初始化列表 / 字典字段**：

```ibci
class Stack:
    list items
    func __init__(self):
        self.items = []  # 每个实例独立创建
```

### 12.3 `llmexcept` 快照不影响容器内容

`llmexcept` 的方案A 深克隆 + 方案B `__snapshot__` 协议目前只快照"标量变量绑定 / 用户对象字段"。若快照前的变量持有列表，LLM 调用体内对该列表的 `append`/`remove` 等**就地修改**在 `retry` 后不会被还原。

**规避方案**：不要在 `llmexcept` 保护块的 LLM 调用路径中就地修改容器；如需可回滚的容器状态，在 `llmexcept` 之前先做深复制（或为类实现 `__snapshot__` / `__restore__` 协议自行决定快照粒度）。

### 12.4 `fn` 变量的可调用引用语义

```ibci
fn f = add          # f 持有 add 函数的引用
fn g = f            # g 也引用同一个函数
```

函数本身是不可变的，因此 `fn` 变量的引用语义不会导致副作用问题。

---

## 十三、`auto` / `fn` / `any` 对比

| 关键字 | 用途 | 类型推导时机 | 后续赋值限制 |
|--------|------|------------|------------|
| `auto x = expr` | 通用类型推导，锁定为首次赋值的实际类型 | 编译期 | 只能赋相同类型 |
| `fn f = callable` | 可调用类型推导，RHS 必须是可调用的 | 编译期 | 保持可调用约束 |
| `any x = expr` | 真正的动态类型，不锁定 | 运行时 | 任意类型 |
| `x = expr`（裸赋值）| 隐式 `any` 语义（不推荐） | 运行时 | 任意类型 |

> **注意**：没有类型标注的裸赋值（`x = expr`）编译器会将变量视为 `any` 类型。
> 若需要将此变量用于有类型检查的上下文（如赋给 `int y`），**必须使用强制类型转换**：
> ```ibci
> x = 42
> int y = (int)x    # 必须显式转换，不能直接赋值
> ```

---

## 十四、容器多类型声明

`list[int, str, list]` 语法允许声明一个可持有多种类型元素的列表。编译器规则：

- **元素读取**（下标访问 / for 迭代）返回 `any` 类型。若需明确类型，必须显式转换：
  ```ibci
  list[int, str] mixed = [1, "hello"]
  any val = mixed[0]
  int n = (int)val      # 必须先取到 any，再强制转换
  ```
- **不允许** 通过 `auto` 直接承载容器元素取值赋值（编译期推断会失败）：
  ```ibci
  auto x = mixed[0]    # ❌ 不推荐
  any x = mixed[0]     # ✅ 建议始终用 any 中转
  int n = (int)x        # ✅ 再强制转换到目标类型
  ```

详细泛型容器问题见 [`GENERICS_CONTAINER_ISSUES.md`](../GENERICS_CONTAINER_ISSUES.md)。

---

## 十五、已废弃语法（产生硬编译错误）

### `(Type) @~...~` 强制类型转换语法（PAR_010）

```ibci
# ❌ 已废弃，产生 PAR_010 编译错误
int sum = (int) @~ 请计算 $a 和 $b 之和 ~

# ✅ 正确写法：LHS 类型自动成为 LLM 输出格式约束
int sum = @~ 请计算 $a 和 $b 之和 ~
str mood = @~ 请判断颜色，回复颜色单词 ~
```

LHS 的变量声明类型会自动被传递给 LLM 作为输出格式提示，无需额外的类型转换语法。

### 旧 fn / lambda 声明语法（PAR_003 / D1/D2 废弃）

```ibci
# ❌ 全部产生 parse error
int lambda f = expr           # 旧声明语法（PAR_001）
auto snapshot g = expr        # 旧声明语法（PAR_001）
fn lambda h = expr            # 旧括号体形式（PAR_001）
lambda(EXPR)                  # 旧括号体形式（PAR_001）
lambda(PARAMS)(EXPR)          # 旧括号体形式（PAR_001）
int fn f = lambda: EXPR       # 声明侧返回类型（PAR_003，D1 废弃）
int fn f = snapshot(int a, int b): EXPR  # 声明侧返回类型（PAR_003，D1 废弃）

# ✅ 正确写法（D1/D2：返回类型标注写在表达式侧）
fn f = lambda: EXPR                          # 无参，返回类型推导
fn f = lambda -> int: EXPR                   # 无参，显式返回类型（D2）
fn f = lambda(int x): EXPR                  # 有参，返回类型推导
fn f = lambda(int x) -> int: EXPR           # 有参，显式返回类型（D2）
fn f = snapshot -> int: EXPR                # snapshot，显式返回类型（D2）
fn f = snapshot(int a, int b) -> str: EXPR  # snapshot 有参（D2）
```

`D1`（2026-04-29）废弃了声明侧返回类型 `TYPE fn NAME = lambda: EXPR` 形式（产生 PAR_003），
改为在表达式侧通过 `-> TYPE` 标注（`D2`）。

