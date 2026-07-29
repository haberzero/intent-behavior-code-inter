## 1. 类型系统

> 本章描述 IBCI 的基础类型系统。面向所有 IBCI 开发者。覆盖基础类型、泛型容器、Optional[T] 空安全与类型转换规则。

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

`None` 在布尔上下文中为假。`(str)None` 返回 `"None"`。LLM 调用失败处理请使用 `llmexcept` / `try except LLMCallError` / `try except LLMRetryExhaustedError`。

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

**转换规则**（按优先级）：

1. **同类型**：目标类型与源类型相同 → 直接返回原值
2. **向上转型**：目标类型是源类型的父类 → 直接返回原值（安全且语义正确）
3. **字符串化**：目标类型为 `str` 或 `any` 时，调用源对象的 `__to_prompt__` 协议获取字符串表示
4. **失败**：以上均不满足 → 运行时抛出类型转换错误

内置类型（int/float/str/list/dict/tuple 等）有专用的转换实现。用户类可定义自己的 `cast_to` 方法覆盖默认行为：

```ibci
class Temperature:
    float value

    func cast_to(self, target) -> any:
        if target == str:
            return (str)self.value + "°C"
        return self
```

**编译期提示**：对于声明了转换规则的类型，编译器会在转换明显不合法时发出 `SEM_CAST_NO_CONVERTER` 警告（如 `(int)file_handle`）。未声明转换规则的类型不做编译期校验，由运行时裁定。

---
