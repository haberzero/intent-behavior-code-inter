# IBCI 高阶函数 / 可调用类型 设计思考笔记

> **更新（2026-04-23）**：§5 记录已实现的 `fn` + `__call__` 可调用类支持。

---

## 1. 已实现：`fn` 关键字 + 用户自定义 `__call__` 协议

IBCI 当前支持以下所有"可被调用"的类型通过 `fn` 关键字统一承载：

| 类型 | 示例 | 备注 |
|---|---|---|
| 普通函数引用 | `fn f = myFunc` | 持有函数对象引用 |
| 类构造器引用 | `fn f = Dog` | 构造 Dog 实例 |
| lambda 延迟对象 | `fn lambda f = expr` | 每次调用重新求值 |
| snapshot 延迟对象 | `fn snapshot f = expr` | 首次调用后缓存 |
| 用户自定义可调用类实例 | `fn f = my_adder` | 类须定义 `__call__` 方法 |

### 用户自定义可调用类（`__call__` 协议）

定义 `func __call__(self, ...)` 的类，其实例可通过 `fn` 承载并被调用：

```ibci
class Adder:
    int base

    func __init__(self, int b):
        self.base = b

    func __call__(self, int x) -> int:
        return self.base + x

Adder adder = Adder(10)
fn my_fn = adder        # ✅ 推断为 Adder 类型（有 __call__）
int result = my_fn(5)   # ✅ 调用 adder.__call__(5)，result = 15
```

没有定义 `__call__` 的类实例不能被 `fn` 承载（SEM_003 编译错误）：

```ibci
class Plain:
    str name

Plain p = Plain("hi")
fn f = p    # ❌ SEM_003：Plain 没有 __call__
```

### 设计决策：不引入统一 callable 基类

`fn` 是类似 `auto` 的**类型推断哨兵**，而非一个内置类型。  
所有实现了公理层 `__call__` 的类型都可由 `fn` 承载，无需继承任何公共基类。  
这与 IBCI 的"鸭子类型 + 能力协议"设计哲学一致。

---

## 2. 待实现设计方向（历史存档）

以下内容为早期讨论方向，供日后决策参考。

### 2.1 `func[sig]` 泛型类型标注（P2）

支持带签名约束的 `func` 类型，使参数签名可在编译期验证：

```ibci
func apply_typed(func[int -> int] fn, int x) -> int:
    return fn(x)
```

### 2.2 lambda/snapshot 支持参数列表（P3）

允许 `func[int -> int] lambda f = ...`，带参数调用 `f(3)`。

### 2.3 轻量泛型 `<T>`（P4）

支持泛型高阶函数类型传播。

---

*最后更新：2026-04-23*

---

## 1. 核心问题：缺失统一的"可调用"内置类型

IBCI 目前有三种"可以被调用一次"的对象形态：

| 形态 | 创建方式 | 典型用途 |
|---|---|---|
| `lambda` 延迟对象 | `int lambda f = @~ ... ~` | 每次调用重新求值 |
| `snapshot` 延迟对象 | `int snapshot f = @~ ... ~` | 首次调用后缓存 |
| 函数工厂返回的闭包 | `func make_adder(int n) -> ???` | 返回一个闭包函数 |

问题：IBCI 没有一个统一的内置类型/关键字来表达 **"可接受零或多个参数、能被调用一次并返回值"** 的一等公民对象。  
也就是说，当我们想把 **一个函数** 作为参数传递或者作为函数返回值时，目前缺少一个对齐 Python `Callable` / Haskell 函数类型的语法和类型系统支持。

---

## 2. 建议引入 `func` 作为一等公民内置类型关键字

### 2.1 设计意图

`func` 既是声明普通函数的关键字，也应成为一个**内置类型名**，代表"任意可调用函数对象"。  
类似于：
- Python 的 `Callable` (typing)
- TypeScript 的 `(...args: any[]) => any`
- Rust 的 `Fn` / `FnMut` / `FnOnce`

### 2.2 基本语法构想

```ibci
# 函数作为参数
func apply(func fn, int x) -> int:
    return fn(x)

# 函数作为返回值
func make_adder(int n) -> func:
    func adder(int x) -> int:
        return x + n
    return adder

# 带签名约束的 func 类型（更精确）
func apply_typed(func[int -> int] fn, int x) -> int:
    return fn(x)
```

### 2.3 与 lambda / snapshot 的关系

- `lambda` / `snapshot` 是**值语义**的延迟求值容器，适合包装 `@~ ... ~` 行为表达式。
- `func` 类型是**函数对象**的类型，更通用，可以接受 `lambda`、`snapshot`、普通 `func` 定义的函数、以及从函数工厂返回的闭包。
- 未来 `lambda` 和 `snapshot` 的 `to_bool` / `call` 等行为应当通过 `func` 协议统一。

---

## 3. 缺失的关键机制

### 3.1 闭包的捕获语义

IBCI 的 `snapshot` 目前通过 `IbDeferred.call()` 重新执行 AST 节点，但没有**显式的变量捕获声明**。  
Python 通过 `nonlocal` 声明实现闭包变量捕获；IBCI 可以考虑：
- 隐式捕获（Python 风格）：自动捕获外部作用域的引用
- 显式捕获列表（C++ Lambda 风格）：`[capture_list] func f(...):`  
建议：优先保持 Python 风格（隐式捕获），但需要在编译期静态分析中明确捕获点，避免悬空引用。

### 3.2 函数对象的类型签名表达

目前 `func` 作为类型名时无法携带签名信息（参数类型 / 返回类型）。  
建议支持泛型化的 `func` 类型：
```
func[int, str -> bool]   # 接收 int 和 str，返回 bool
func[-> int]             # 无参，返回 int
func                     # 完全不约束（兜底）
```
这与 `list[int]` / `dict[str, int]` 的泛型语法保持一致。

### 3.3 高阶函数的编译期类型推断

当 `auto` 作为函数返回类型时（已在当前 PR 实现推断），对于高阶函数中通过 `func` 类型参数调用：
```ibci
func apply(func fn, int x) -> auto:
    return fn(x)   # 编译期无法确定 fn 的返回类型，auto 退化为 any
```
需要引入**泛型参数**（类似 TypeScript 的 `<T>`）才能实现真正的类型传递。这是未来工作。

### 3.4 lambda / snapshot 的已知缺陷

1. **多参数支持缺失**：当前 `lambda` / `snapshot` 内嵌 `@~ ... ~` 时，只支持无参调用。将 `lambda` 作为带参函数传递时，调用语义不完整。
2. **类型签名丢失**：`int lambda f = @~ ... ~` 只记录了返回类型 `int`，但调用 `f(x, y)` 时参数数量和类型无法在编译期验证。
3. **`snapshot` 的线程安全**：`snapshot` 首次调用后缓存，但在并发场景（如果 IBCI 未来支持并发）存在竞态条件。
4. **递归 lambda**：`lambda` 无法引用自身（无自我引用语法）。

---

## 4. 建议实现路径（优先级排序）

1. **[P1] 将 `func` 注册为内置类型名**，使 `func f = some_function` 语法合法，并在编译期进行 callable 类型检查。
2. **[P2] 支持 `func[sig]` 泛型类型标注**，使参数签名可以在编译期验证。
3. **[P3] lambda/snapshot 支持参数列表**，如 `func[int -> int] lambda f = ...`，允许 `f(3)` 等带参调用。
4. **[P4] 引入轻量泛型** (`<T>`) 以支持泛型高阶函数的类型传播。

---

*最后更新：2026-04-21*
