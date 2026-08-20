## 2. 变量声明与赋值

> 本章描述 IBCI 的变量声明与赋值语法，以及变量共享数据的**值语义**（引用/拷贝/赋值/传递契约）。面向已阅读类型系统章节的开发者。覆盖有类型声明、auto/any 推导、元组解包、global/nonlocal 作用域与值语义模型。

### 2.1 有类型声明（推荐）

```ibci
int count = 10
str name = "Alice"
bool flag = True
float price = 9.99
list[int] nums = [1, 2, 3]
dict[str,int] scores = {"Alice": 95}
```

### 2.2 auto 推断

```ibci
auto x = 42          # 推断为 int，x 的类型被锁定为 int
auto s = "hello"     # 推断为 str
auto nums = [1, 2]   # 推断为 list[int]
```

`auto` 会在首次赋值时推断并锁定类型，后续赋值必须兼容该类型。

### 2.3 any 类型（唯一动态逃生阀）与裸赋值

```ibci
any val = "hello"    # 显式 any：真正的动态类型，可重新赋值为任何类型
x = 42               # 裸赋值：等同 auto——从首次赋值推断并锁定（不隐式 any）
x = "s"              # ❌ SEM_TYPE_MISMATCH：裸赋值已锁定为 int
```

> **裸赋值语义**：无类型标注的裸赋值（`x = 42`）采用 `auto` 语义——
> 编译期从首次赋值推断实际类型并锁定，不隐式退化为动态 `any`。需要真正的动态语义时
> **必须显式声明 `any`**。
>
> **any 逃生后的重处理**：`any` 值用于有类型检查的上下文（赋给 `int y` 等）时，运行时
> 强制类型校验（不匹配抛 `RUN_TYPE_MISMATCH`），必须先用强制类型转换 `(int)x`。

### 2.4 元组解包

```ibci
(int a, int b) = (10, 20)
(str x, str y, str z) = ("p", "q", "r")
```

### 2.5 多重赋值

```ibci
int a = 1
int b = 2
(a, b) = (b, a)    # 交换
```

### 2.6 全局变量

`global` 语句与 Python 语义一致：在函数内声明 `global x` 后，函数内对 `x` 的所有读写均操作全局作用域中的 `x`，而非创建局部变量。

```ibci
int counter = 0

func increment() -> void:
    global counter
    counter = counter + 1

increment()
print((str)counter)    # 1
```

**说明：**
- `global` 用于声明对模块级全局变量的写访问；在模块级使用 `global` 无额外效果（全局作用域本就是最外层）。
- 可以在 `global` 声明之后才定义全局变量（函数调用时变量已存在即可）。
- `global x, y` 支持一次声明多个全局变量。

### 2.7 nonlocal 变量

`nonlocal` 语句用于在嵌套函数中**写回**外层函数作用域的变量。不使用 `nonlocal` 时，内部函数的赋值目标会被视为局部变量声明。

```ibci
func make_counter() -> fn:
    int count = 0
    func inc() -> int:
        nonlocal count
        count = count + 1
        return count
    return inc

fn counter = make_counter()
print(counter())    # 1
print(counter())    # 2
print(counter())    # 3
```

**说明：**
- `nonlocal` 只能在嵌套函数内部使用，在模块级使用会产生 SEM_INTENT_PLACEMENT 编译错误。
- 声明的变量必须在外层作用域中已存在，否则产生 SEM_NONLOCAL_NOT_FOUND 编译错误。
- `nonlocal a, b` 支持一次声明多个外部变量。
- nonlocal 变量通过闭包共享机制实现：多个闭包可以共享同一个外部变量，实现状态共享。

**只读捕获（自动）**：嵌套函数体内**读取**外层变量无需 `nonlocal`——引用自动捕获为共享 cell（读捕获自动、写需 `nonlocal`）。

```ibci
func make_adder() -> fn:
    int base = 10
    func add(int x) -> int:
        return base + x    # 读 base：自动捕获，无需 nonlocal
    return add

fn adder = make_adder()
print(adder(5))    # 15
```
---

## 2.8 值语义：引用、拷贝、赋值与传递

值语义决定变量之间如何共享数据：赋值与传参何时共享同一对象、何时产生独立副本。本节是 IBCI 值语义的**权威契约**，传参、闭包捕获与快照各章均以此为准。

### 两类值：不可变原语与可变复合对象

| 类别 | 类型 | 赋值行为 |
|------|------|---------|
| 不可变原语 | `int` / `float` / `bool` / `str` / `None` | 赋值即复制（值语义等价，无就地修改） |
| 可变复合对象 | `list` / `dict` / 用户类实例 | 赋值 = 引用复制（别名，共享同一对象） |

### 赋值是引用复制（复合对象）

`b = a` 让 `b` 与 `a` 指向同一个对象。通过任一名就地修改该对象，另一名立即可见：

```ibci
list a = [1, 2, 3]
list b = a            # b 与 a 共享同一列表
b.append(4)
print((str)a.len())   # 4 —— a 看到 b 的修改
```

需要独立副本时使用显式拷贝：`copy` 浅拷贝（容器独立、元素共享）、`deepcopy` 深拷贝（嵌套容器与用户对象字段独立）。使用细节见 `docs/syntax/12_builtins.md`。

### 不可变原语赋值互不影响

原语值不可就地修改，重绑定一个变量不影响另一变量：

```ibci
int a = 1
int b = a
b = 2
print((str)a)   # 1 —— int 不可变，b 重赋值不影响 a
```

### `is`（身份）与 `==`（比较）

`is` 恒为身份比较：两个变量是否指向同一对象（不可覆写）。`==` 的语义分两类：

- **不可变原语**（`int`/`float`/`bool`/`str`/`None`）：值比较——内容相等即真，与对象身份无关。
- **容器与用户类**（`list`/`dict`/用户类实例）：默认**身份比较**——仅同一对象为真（未覆写 `__eq__` 时；用户类可覆写 `__eq__` 实现值比较）。

共享别名的对象 `is` 与 `==` 均为真；`copy`/`deepcopy` 得到的独立副本 `is` 为假，容器的 `==` 默认亦为假。运算符语法与 `is None` 语义见 `docs/syntax/03_operators.md`。

### 参数传递是共享引用

函数实参按**共享引用**传入：函数内就地修改可变参数会影响调用方变量；重绑定参数名不影响调用方。完整语义与示例见 `docs/syntax/05_functions.md` §5.10。

### 闭包捕获与快照

- **lambda**：捕获外层变量为共享 cell（引用语义），调用时读最新值。
- **snapshot**：定义时深克隆冻结（值语义），调用不污染外部变量。

意图冻结与捕获细节见 `docs/syntax/07_behavior_expressions.md`。

### 快照与序列化交互

snapshot 延迟对象与 llmexcept 快照在捕获点深克隆冻结现场；序列化按值 round-trip 恢复独立副本。见 `docs/syntax/10_robustness.md`。

---

## 深入指引

- 作用域与存储模型：docs/architecture/08_storage_model.md
- 语言级变量限制：docs/KNOWN_LIMITS.md
