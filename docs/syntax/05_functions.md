## 5. 函数

> 本章描述 IBCI 的函数声明与调用。面向已阅读控制流章节的开发者。覆盖函数声明、参数传递、递归、嵌套函数、fn 引用与高阶函数签名。

### 5.1 函数声明

```ibci
func greet(str name) -> str:
    return "Hello, " + name

str msg = greet("World")
print(msg)
```

返回类型可以省略，编译器会自动推断（`auto` 语义）：

```ibci
func double(int x):          # 省略返回类型，自动推断为 int
    return x * 2

func say_hello(str name):    # 无 return 语句，推断为 void
    print("Hello, " + name)
```

> **注意**：省略 `-> type` 标注等同于 `-> auto`，编译器从函数体内的 `return` 语句推断实际返回类型。若所有路径均无 `return`，推断为 `void`；若有多条路径返回不同类型，报 `SEM_TYPE_MISMATCH` 错误。

显式返回类型标注：

```ibci
func add(int a, int b) -> int:
    return a + b

func log(str msg) -> void:
    print(msg)

func identity(int x) -> auto:   # 显式 auto，与省略等价
    return x
```

**`-> None` 与 `-> void` 的区别**

| 标注 | 语义 | 调用结果 |
|------|------|---------|
| `-> void` | 函数不产生任何值 | 不可赋值给变量 |
| `-> None` | 函数显式返回 `None` 值 | 可被赋值给 `any` 变量 |
| 省略 | 编译器自动推断（`auto`） | 取决于推断结果 |

```ibci
func cleanup(str path) -> None:
    # 处理清理逻辑
    print("cleaned: " + path)
    # 不需要显式 return —— 隐式 None 返回合法

func maybe_get(bool flag) -> None:
    if flag:
        return None   # ✅ 显式
    return            # ✅ 裸 return 在 -> None 函数中合法
```

### 5.2 行为表达式与 return 的约束

> **Known Limit (docs/KNOWN_LIMITS.md §四)**：`return @~ ... ~` 是**禁止写法**，会产生 `SEM_TYPE_MISMATCH` 编译错误。

```ibci
# 错误：不允许在 return 中直接使用行为表达式
func get_reply() -> str:
    return @~ 给我一句话 ~

# 正确：先赋值给有类型的局部变量
func get_reply() -> str:
    str reply = @~ 给我一句话 ~
    return reply
```

### 5.3 递归函数

```ibci
func factorial(int n) -> int:
    if n <= 1:
        return 1
    return n * factorial(n - 1)

int result = factorial(5)
print((str)result)   # 120
```

### 5.4 嵌套函数

```ibci
func outer(int x) -> int:
    func inner(int y) -> int:
        return y * 2
    return inner(x) + 1
```

### 5.5 `fn` 函数引用与延迟对象

`fn` 用于持有任何可调用值：函数引用、lambda 闭包、snapshot 延迟对象。

```ibci
func double(int x) -> int:
    return x * 2

fn f = double           # 持有函数引用
int r = f(5)            # 10

fn g = lambda: 42       # 持有无参 lambda
auto v = g()            # 42

fn h = lambda(int x) -> int: x * 2   # 带表达式侧返回类型标注，带参 lambda
int w = h(3)                          # 6
```

延迟执行的完整语法见 §7.4。

### 5.6 `fn[(...)->(...)]` 高阶函数 callable 签名标注

裸 `fn` 用于变量声明位置时表示"推导任意可调用类型，不约束签名"；当需要在**类型标注位置**对 callable 进行结构签名约束时（如高阶函数参数、返回类型、`auto`/`fn` 覆盖类型），使用 `fn[(<input_types>) -> (<output_types>)]` 形式。

```ibci
# 接受 (int, str) -> bool 的 callable 作为参数
func apply(fn[(int, str) -> bool] predicate, int x, str s) -> bool:
    return predicate(x, s)

# 无参 callable
func run_callable(fn[() -> int] task) -> int:
    return task()

# 返回值也可以是带签名的 fn
func make_adder(int n) -> fn[(int) -> int]:
    fn adder = lambda(int x) -> int: x + n
    return adder

# 接受任意可调用（不约束签名）—— 裸 fn
func call_any(fn f) -> auto:
    return f()
```

**裸 `fn` vs `fn[...]`**：

| 形式 | 出现位置 | 含义 |
|------|---------|------|
| `fn NAME = EXPR` | 变量声明 | 推导任意可调用类型；不约束签名 |
| `fn[(...)->(...)]` | 类型标注位置（参数 / 返回类型 / `auto`/`fn` 覆盖类型） | 结构签名约束（参数数量 + 各位置类型 + 返回类型） |

**匹配规则**：
- 参数数量必须严格相等
- 各位置参数类型必须 assignable（含子类型协变）
- 返回类型必须 assignable
- 实参可以是普通函数引用、lambda 闭包、snapshot 延迟对象、可调用类实例

---
