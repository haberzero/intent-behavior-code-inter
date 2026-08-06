## 2. 变量声明与赋值

> 本章描述 IBCI 的变量声明与赋值语法。面向已阅读类型系统章节的开发者。覆盖有类型声明、auto/any 推导、元组解包与 global/nonlocal 作用域。

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
auto nums = [1, 2]   # 推断为 list
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

func increment():
    global counter
    counter = counter + 1

increment()
print((str)counter)    # 1
```

**说明：**
- `global` 只能在函数内部使用，在全局作用域中使用会产生 SEM_INVALID_SCOPE 编译错误。
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
---

## 深入指引

- 作用域与存储模型：docs/architecture/08_storage_model.md
- 语言级变量限制：docs/KNOWN_LIMITS.md
