# IBCI 高阶函数 / 可调用类型设计

> 本文档描述 IBCI 高阶函数与可调用类型的设计决策与当前实现。面向需要理解 `fn` 关键字和 `__call__` 协议机制的开发者。

---

## 一、`fn` 关键字与用户自定义 `__call__` 协议

IBCI 支持以下"可被调用"的类型通过 `fn` 关键字统一承载：

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
    func __init__(self, int b) -> auto:
        self.base = b
    func __call__(self, int x) -> int:
        return self.base + x

Adder adder = Adder(10)
fn my_fn = adder        # 推断为 Adder 类型（具备 __call__）
int result = my_fn(5)   # 调用 adder.__call__(5)
```

没有定义 `__call__` 的类实例不能被 `fn` 承载（SEM_TYPE_MISMATCH 编译错误）。

### 设计决策：不引入统一 callable 基类

`fn` 是类似 `auto` 的**类型推断哨兵**，而非一个内置类型。所有实现了公理层 `__call__` 的类型都可由 `fn` 承载，无需继承任何公共基类。这与 IBCI 的"鸭子类型 + 能力协议"设计哲学一致。

### `callable` 内部化：用户面统一 `fn` 族

- **`callable` 不作为用户可写类型**：`callable f` / `-> callable` / `list[callable]`
  编译期报 `SEM_UNRESOLVED_TYPE`（引导用 `fn`）。它保留为**内部概念**：运行期函数
  对象基类名（`type(make)`="callable"）、公理族根（fn_callable/behavior/bound_method
  的父公理）、`thread(callable=...)` 内置函数参数名。
- **`fn` 是唯一的用户面"可调用"抽象**，三种形态位置语义一致：
  - 声明推断：`fn f = add` ⇒ 推断 f 为具体 callable spec；RHS 必须是可调用。
  - 抽象槽（参数/返回/容器）：`fn` = "任意可调用（强制）"——`apply(42)`、
    `-> fn: return 42` 编译期拦截；动态实参/返回（any/auto）放行交运行期。
  - 签名约束：`fn[(args)->ret]` 结构匹配。
### 已知 `fn` 限制

详见 `docs/KNOWN_LIMITS.md` §一（`__call__` 协议）与 §七（`auto` / `fn` / `any`）——`fn` 在跨场景调用、OOP `__call__` 协议解析、闭包捕获、与 lambda/snapshot 互通的路径上仍存在一致性不足，待整体重设计。
---

## 深入指引

- fn 类型语义：docs/architecture/03_type_system.md §7
- 行为表达式语法层：docs/syntax/07_behavior_expressions.md
