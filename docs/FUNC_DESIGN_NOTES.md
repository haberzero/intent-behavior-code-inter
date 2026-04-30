# IBCI 高阶函数 / 可调用类型 设计笔记

> **最后更新（2026-04-29）**：清理早期设计讨论；当前内容反映 M1/M2/D1/D2/D3 落地后的事实。

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

后续改进方向（`func[sig]` 泛型标注、轻量泛型 `<T>`、高阶函数类型推断、lambda 剩余缺陷）详见 `docs/PENDING_TASKS.md §4.4`。

---

*历史多版本设计讨论已合并到上述精简版。详细演化记录见 `docs/COMPLETED.md` §六（M1）/ §七（M2）/ §八（fn declaration-side 语法）。*

