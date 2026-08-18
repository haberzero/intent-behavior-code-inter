## 6. 面向对象

> 本章描述 IBCI 的面向对象编程支持。面向已阅读函数章节的开发者。覆盖类定义、继承、super()、Enum 枚举与协议方法。

### 6.1 类定义

```ibci
class Point:
    int x
    int y

    func __init__(self, int x, int y) -> auto:
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

    func __init__(self, str name) -> auto:
        self.name = name

    func speak(self) -> str:
        return self.name + " says something"


class Dog(Animal):
    func speak(self) -> str:
        return self.name + " says Woof!"


Dog d = Dog("Rex")
print(d.speak())    # Rex says Woof!
```

### 6.4 泛型类

用户类可声明泛型类型参数，用 `[T]` 语法：

```ibci
class Box[T]:
    T value

    func get(self) -> T:
        return self.value

    func set(self, T v) -> void:
        self.value = v
```

实例化/声明时提供类型实参（特化），`T` 被替换为实参类型：

```ibci
Box[int] bi = Box[int](42)
Box[str] bs = Box[str]("hi")

int v = bi.get()    # get() 返回类型特化为 int
str s = bs.get()    # get() 返回类型特化为 str
```

要点：

- **多特化并存**：`Box[int]` 与 `Box[str]` 是独立类型，互不干扰。
- **嵌套泛型**：`list[Box[int]]` 合法——类型实参自身可为泛型特化。
- **使用面**：类型参数可用于字段类型、方法参数/返回类型、局部变量注解。
- **裸用拦截**：泛型类必须特化使用（`Box b = ...` 报 `SEM_GENERIC_TYPE_NEEDS_ARGS`）；
  实参数量须与声明一致（`Box[int, str]` 报 `SEM_GENERIC_TYPE_ARG_COUNT`）。

泛型继承——子类继承父类类型参数：

```ibci
class SpecialBox[T](Box[T]):
    str label

    func __init__(self, T v, str l) -> void:
        self.value = v
        self.label = l

    func describe(self) -> str:
        return self.label + ":" + (str)self.get()

SpecialBox[int] sb = SpecialBox[int](7, "SB")
print(sb.describe())    # SB:7
```

> **自动构造器（无显式 `__init__` 时）**：参数 = 当前类 + 继承链全部无默认值字段
> （父类优先、子类同名覆盖）——继承特化场景下 `Linked[int](data, tag)` 一并绑定
> 父类字段。需要自定义构造逻辑（如字段变换、祖先 `__init__` 副作用）时显式写
> `__init__` + `super`（见 §6.5）。

### 6.5 `super()`

> `super()` 用于调用**显式父类**的方法——`class Derived(Base)` 中 `Derived` 的方法
> 内可用 `super()` 访问 `Base` 的同名方法。无显式父类的类使用 `super()` 会抛运行时
> 错误（隐式基类 `Object` 不提供用户可调用的方法）。

```ibci
class Base:
    int value

    func __init__(self, int v) -> auto:
        self.value = v

    func describe(self) -> str:
        return "Base: " + (str)self.value


class Derived(Base):
    str label

    func __init__(self, int v, str label) -> auto:
        super().__init__(v)
        self.label = label

    func describe(self) -> str:
        return self.label + " / " + super().describe()
```

### 6.6 Enum

```ibci
class Status(Enum):
    str PENDING  = "PENDING"
    str RUNNING  = "RUNNING"
    str DONE     = "DONE"

Status s = Status.RUNNING

if s == Status.RUNNING:
    print("正在运行")
```

> **Known Limit (docs/KNOWN_LIMITS.md §二)**：枚举成员值是其声明类型的底层值（非枚举实例），
> 因此枚举自定义方法不可在成员值上调用。枚举支持任意底层类型（`str`/`int`/`float`/`bool`）、
> 迭代（`for v in Color:`）与数量（`len(Color)`）。

### 6.7 特殊方法（协议）

| 方法名 | 触发场景 | 说明 |
|--------|---------|------|
| `__init__(self, ...)` | 构造 `ClassName(...)` 时 | 初始化方法 |
| `__call__(self, ...)` | 对实例 `obj(...)` 调用时 | 可调用对象协议 |
| `__iter__(self)` | `for x in obj:` 时 | 迭代器协议，返回可遍历列表 |
| `__to_prompt__(self)` | 变量插值到 `@~ ... ~` 时 | 转为 LLM 提示词文本 |
| `__from_prompt__(str raw)` | LLM 返回值解析时 | 从文本解析为当前类型实例。**必须返回 `(bool, 实例)` 元组**——首元素为成功标志，次元素为解析出的实例（返回裸实例会被当作不确定失败） |
| `__validate_prompt__(self, str raw)` | LLM 输出解析校验时 | 校验原始输出。返回 `(bool, str)`——首元素为是否接受，次元素为拒绝原因（拒绝时经 `llmexcept` / retry 走纠错重试路径） |
| `__outputhint_prompt__(self)` | 类型作为 LLM 输出目标时 | 提示 LLM 期望的输出格式 |
| `__payload_prompt__(self)` | 变量插值到多模态 `@~ ... ~` 时 | 返回结构化 content block（图像/音频等） |
| `__snapshot__(self)` | llmexcept 快照进入时 | 返回用于恢复状态的快照值 |
| `__restore__(self, state)` | llmexcept retry 前 | 从快照值恢复对象状态 |

**运算符重载**：用户类可定义运算符 dunder 方法（`__add__` / `__sub__` / `__mul__` /
`__truediv__` / `__floordiv__` / `__mod__` / `__pow__` / `__and__` / `__or__` /
`__xor__` / `__lshift__` / `__rshift__` / `__eq__` / `__ne__` / `__lt__` / `__le__` /
`__gt__` / `__ge__` / `__neg__` / `__pos__` / `__invert__` / `__not__` /
`__contains__`）并经运算符分派调用；`is` 恒为身份比较，不可覆写。完整清单与
边界见 `docs/KNOWN_LIMITS.md` §十四。

---

### 6.8 用户协议与 retroactive implementation

**协议（protocol）** 是方法签名的命名集合，用作类型约束：

```ibci
protocol Greeter:
    func greet(self) -> str:
        pass

class Foo implements Greeter:
    func greet(self) -> str:
        return "hi"
```

- 协议支持继承：`protocol Child(Parent):`，子协议要求父协议的全部方法。
- 泛型协议：`protocol Container[T]:`，实现侧 `class Box implements Container[int]:`。
- 协议作为泛型约束：`class Box[T: Greeter]`（类型实参须满足协议）、
  `func call[T: Greeter](T x) -> str`（调用点从实参推断并检查约束）。
- 方法签名须与协议兼容：参数数量一致、参数类型可放宽、返回类型协变。
- `implements` 声明但缺失方法、或签名不兼容，均在编译期报错。

**retroactive implementation（`impl`）** 为既有类型声明协议满足关系：

```ibci
impl Greeter for Foo:

```

空 body 形式仅校验并记录：类型必须已提供协议全部方法。

`impl` 可携带方法定义体，为既有类型**补充缺失的协议方法**（不改原类定义）：

```ibci
protocol Renderable:
    func render(self) -> str:
        pass

class Box:
    str label

impl Renderable for Box:
    func render(self) -> str:
        return "[" + self.label + "]"

print(Box("a").render())   # [a]
```

- 补充的方法体可读 `self` 与字段；子类经继承链可见补充方法。
- 同一类型可写多个 `impl` 块（不同协议各自补充）。
- 协议满足检查在"类自身方法 + impl 补充方法"并集上进行。
- **限制**：目标须为本模块用户类、宿主绑定类（`bind class`）或内置具体值类型
  （`int`/`str`/`list` 等；`any`/`auto`/`void`/`module` 与泛型类不支持）；body 仅允许
  `func` 方法；与目标既有成员（含内置类型的公理声明方法与运算符）同名的方法报编译期错误；
  内置 `impl` 不得定义 `__init__`；内置类型的 `impl` 引擎全局生效。

---

## 深入指引

- 用户类能力差距：docs/KNOWN_LIMITS.md §十四
- Enum 语法限制：docs/KNOWN_LIMITS.md §二
