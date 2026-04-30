# IBCI 高阶函数 / 可调用类型 设计笔记

> **最后更新（2026-04-29）**：清理早期设计讨论；当前内容反映 M1/M2 落地后的事实。

---

## 1. 当前状态：`fn` 关键字 + 用户自定义 `__call__` 协议

IBCI 当前支持以下"可被调用"的类型通过 `fn` 关键字统一承载：

| 类型 | 示例 | 备注 |
|---|---|---|
| 普通函数引用 | `fn f = myFunc` | 持有函数对象引用 |
| 类构造器引用 | `fn f = Dog` | 构造 Dog 实例 |
| lambda 延迟对象 | `fn f = lambda(int x): x + 1` | 调用时使用调用方意图栈 |
| snapshot 延迟对象 | `fn f = snapshot(int x): @~ ... ~` | 创建时冻结意图栈 |
| 用户自定义可调用类实例 | `fn f = my_adder` | 类须定义 `__call__` 方法 |

### 用户自定义可调用类（`__call__` 协议）

```ibci
class Adder:
    int base
    func __init__(self, int b):
        self.base = b
    func __call__(self, int x) -> int:
        return self.base + x

Adder adder = Adder(10)
fn my_fn = adder        # ✅ 推断为 Adder 类型（具备 __call__）
int result = my_fn(5)   # ✅ 调用 adder.__call__(5)
```

没有定义 `__call__` 的类实例不能被 `fn` 承载（SEM_003 编译错误）。

### 设计决策：不引入统一 callable 基类

`fn` 是类似 `auto` 的**类型推断哨兵**，而非一个内置类型。所有实现了公理层 `__call__` 的类型都可由 `fn` 承载，无需继承任何公共基类。这与 IBCI 的"鸭子类型 + 能力协议"设计哲学一致。

### 已知 `fn` 限制

详见 `docs/KNOWN_LIMITS.md` 三 —— `fn` 在跨场景调用、与 OOP `__call__` 协议解析、闭包捕获、与 lambda/snapshot 互通的若干路径上仍存在一致性不足，需要等待整体重设计。这是 `docs/NEXT_STEPS.md` 选项 1（Semantic 用户面修复）的核心议题。

---

## 2. 未来设计方向

### 2.1 `func[sig]` 泛型类型标注（P2）

支持带签名约束的 `func` 类型，使参数签名可在编译期验证：

```ibci
func apply_typed(func[int -> int] fn, int x) -> int:
    return fn(x)
```

### 2.2 轻量泛型 `<T>`（P3）

支持泛型高阶函数类型传播。

### 2.3 高阶函数的编译期类型推断

当 `auto` 作为函数返回类型时，对于通过 `func` 类型参数调用：

```ibci
func apply(func fn, int x) -> auto:
    return fn(x)   # 编译期无法确定 fn 的返回类型，auto 退化为 any
```

需要引入泛型参数（类似 TypeScript 的 `<T>`）才能实现真正的类型传递。

### 2.4 lambda / snapshot 的剩余缺陷

1. **类型签名丢失**：`int fn f = lambda(int x): EXPR` 调用 `f(x)` 时参数数量在编译期可被验证，但参数类型至今仍较弱（`fn` 类型推断不传播签名）。
2. **递归 lambda**：lambda 无法引用自身（无自我引用语法）。
3. **`snapshot` 的线程安全**：snapshot 首次调用后缓存；M4 引入并发后存在潜在竞态，目前未有专门保护，依赖"snapshot 通常无副作用"的使用约定。

---

*历史多版本设计讨论已合并到上述精简版。详细演化记录见 `docs/COMPLETED.md` §六（M1）/ §七（M2）/ §八（fn declaration-side 语法）。*
