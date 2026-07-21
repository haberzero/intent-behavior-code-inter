## 1. 类型系统

### 1.1 基础类型

| 类型名 | 说明 | 示例字面量 |
|--------|------|----------|
| `int` | 整数 | `42`, `-7` |
| `float` | 浮点数 | `3.14`, `-0.5` |
| `str` | 字符串 | `"hello"`, `"world"` |
| `bool` | 布尔值 | `True`, `False` |
| `list` | 动态列表 | `[1, 2, 3]` |
| `tuple` | 不可变元组 | `(1, "a", True)` |
| `dict` | 键值字典 | `{"key": "val"}` |
| `None` | 空值 | `None` |
| `void` | 无返回值（仅用于函数返回类型标注） | — |
| `any` | 任意类型（无类型约束） | — |
| `auto` | 编译期推断类型 | — |
| `fn` | 函数引用 / 延迟闭包类型（推断具体可调用类型） | — |


### 1.2 泛型容器类型

```ibci
list[int]          # 整数列表
list[str]          # 字符串列表
list[int,str]      # 多类型列表（元素访问返回 any）
dict[str,int]      # string→int 字典
dict[str,str]      # string→string 字典
```

### 1.3 特殊值

```ibci
None        # 空值（首字母大写）
```

`None` 在布尔上下文中为假。`(str)None` 返回 `"None"`。

> `Uncertain` 是 IBCI 内核内部的 LLM 不确定性哨兵，不是用户可编程的公开值。
> LLM 失败处理请使用 `llmexcept` / `try except LLMCallError` / `try except LLMRetryExhaustedError`。

### 1.3.1 Optional[T] 空安全

```ibci
Optional[int] maybe_a = None
Optional[int] maybe_b = 1
int a = maybe_a.or_else(0)     # 返回 int
int b = maybe_b.unwrap()       # 返回 int
bool ok = maybe_b.is_some()
```

- `Optional[T]` 接受 `T`、`None`、`Optional[T]`。
- 非 `Optional` 类型不接受 `None`。
- `or_else(default)` 的 `default` 与返回值类型均为 `T`。
- `unwrap()` 返回 `T`（若运行时值为 `None`，语义错误由运行时处理）。

### 1.4 类型转换

强制类型转换使用 `(Type)expr` 语法：

```ibci
int x = 42
str s = (str)x          # "42"
float f = (float)42     # 42.0
bool b = (bool)1        # True
any a = (any)x          # any 类型
```

---
