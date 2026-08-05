## 5. 函数

> 本章描述 IBCI 的函数声明与调用。面向已阅读控制流章节的开发者。覆盖函数声明、参数传递、递归、嵌套函数、fn 引用与高阶函数签名。

### 5.1 函数声明

```ibci
func greet(str name) -> str:
    return "Hello, " + name

str msg = greet("World")
print(msg)
```

**返回类型必须声明（2026-08-05 收紧）**：`func` / `llm` / lambda 缺失返回标注现在产生
`SEM_MISSING_RETURN_ANNOTATION` 编译错误（不再静默回填 `any` 击穿类型推断）。必须显式
声明 `-> TYPE`、`-> auto`（从 body 推断）或 `-> any`（显式逃生）：

```ibci
func double(int x) -> auto:      # auto：从 return 推断实际类型（此处 int）
    return x * 2

func say_hello(str name) -> void:    # void：无返回值
    print("Hello, " + name)

func identity(int x) -> auto:   # 显式 auto，与显式 TYPE 等价（推断结果）
    return x
```

> **`-> auto` 推断规则**：编译器从函数体内的 `return` 语句推断实际返回类型。若所有路径
> 均无 `return`，推断为 `void`；若有多条路径返回不同类型，报 `SEM_TYPE_MISMATCH` 错误。
> lambda 的 `-> auto` 从 body 表达式推断（行为体保持 behavior 动态语义）。

**`-> None` 与 `-> void` 的区别**

| 标注 | 语义 | 调用结果 |
|------|------|---------|
| `-> void` | 函数不产生任何值 | 不可赋值给变量 |
| `-> None` | 函数显式返回 `None` 值 | 可被赋值给 `any` 变量 |
| `-> auto` | 从 return/body 推断并锁定 | 取决于推断结果 |
| 省略 | **编译错误**（`SEM_MISSING_RETURN_ANNOTATION`） | — |

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

### 5.1.1 函数参数：默认值 / 具名 / 动态参数

函数参数支持默认值、具名调用、`*args`/`**kwargs` 动态参数与 keyword-only 参数（Python 语义对齐）。

**默认值**：`name = expr`，未传参时惰性求值；默认值表达式在定义包围作用域求值。

```ibci
func greet(str name, str punct = "!") -> str:
    return "hi " + name + punct

print(greet("x"))        # punct 取默认值 "!"，输出 "hi x!"
print(greet("x", "?"))   # 输出 "hi x?"
```

**具名调用**：实参以 `name = value` 传入，顺序任意；位置实参 + 具名实参可混用（位置先、具名后）。

```ibci
func add(int a, int b) -> int:
    return a + b

print((str)add(a=1, b=2))   # 3
print((str)add(b=2, a=1))   # 3（具名可乱序）
print((str)add(1, b=2))     # 3（混合）
```

**`*args` / `**kwargs`**：`*args` 收集多余位置实参为 `list`；`**kwargs` 收集未声明具名实参为 `dict`。`*args` 之后的参数为 **keyword-only**（只能具名传入）。

```ibci
func collect(str tag, *rest, int limit = 1, **kw) -> dict:
    return {"tag": tag, "rest": rest, "limit": limit, "kw": kw}

print((str)collect("t", 1, 2, limit=5, extra="x"))
# {"tag": "t", "rest": [1, 2], "limit": 5, "kw": {extra: "x"}}
```

**splat 调用**：`*expr` 展开序列为位置实参，`**expr` 展开 dict 为具名实参。

```ibci
list m = [1, 2]
dict kw = {"a": 1, "b": 2}
print((str)add(*m))      # 展开为 add(1, 2) → 3
print((str)add(**kw))    # 展开为 add(a=1, b=2) → 3
```

**约束**（编译期诊断）：
- 具名实参后不允许再出现位置实参（`PAR_POSITIONAL_AFTER_KEYWORD`）
- 重复具名 / 未知具名 / 缺失必填 / 位置超限（`SEM_DUPLICATE_KEYWORD` / `SEM_UNKNOWN_KEYWORD` / `SEM_MISSING_REQUIRED_ARG` / `SEM_TOO_MANY_POSITIONAL`）
- 默认值类型与参数标注不匹配（`SEM_DEFAULT_TYPE_MISMATCH`，定义处校验）
- 参数顺序：`*args` 前不能有默认值后接无默认值普通参数；`**kwargs` 必须居末（`PAR_UNEXPECTED_TOKEN`）

**原生模块函数**：`_spec.py` 中声明 `params: [{"name", "type", "default", "kind"}]` 后，模块函数同样支持具名调用与默认值填充（如 `file.write(target="a.txt", data="x")`）。

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

fn g = lambda -> auto: 42   # 持有无参 lambda（-> auto 推断为 int）
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
