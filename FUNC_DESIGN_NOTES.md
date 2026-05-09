# IBCI 高阶函数 / 可调用类型 设计思考笔记

> **更新（2026-04-23）**：§1 记录已实现的 `fn` + `__call__` 可调用类支持。

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

没有定义 `__call__` 的类实例不能被 `fn` 承载（SEM_003 编译错误）。

### 设计决策：不引入统一 callable 基类

`fn` 是类似 `auto` 的**类型推断哨兵**，而非一个内置类型。  
所有实现了公理层 `__call__` 的类型都可由 `fn` 承载，无需继承任何公共基类。  
这与 IBCI 的"鸭子类型 + 能力协议"设计哲学一致。

> ⚠️ **已知限制**：`fn` 变量存在若干设计问题，暂不建议在复杂场景使用。详见 [`docs/KNOWN_LIMITS.md §三`](docs/KNOWN_LIMITS.md)。

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
