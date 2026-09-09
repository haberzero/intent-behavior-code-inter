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

### 1.1.1 字符串字面量

四种形态（引号定界 + raw 前缀正交）：

| 形态 | 示例 | 说明 |
|------|------|------|
| 单行 | `"hello"` / `'hello'` | 不可跨行；行内换行报 `LEX_UNTERMINATED_STRING` |
| raw 单行 | `r"\n"` | 保留反斜杠（`\n` = 字面反斜杠+n）；反斜杠+引号不闭合字符串 |
| 三引号多行 | `"""..."""` / `'''...'''` | 换行保留为真实换行（含开定界符后首个换行，无 docstring 式剥离）；缩进保留 |
| raw 三引号 | `r"""..."""` / `r'''...'''` | 三引号 + raw 语义组合 |

**三引号多行字符串**（提示词、模板、多行文本的主力形态）：

```ibci
str prompt = """你是一名审稿人。
请检查以下文本：
    <原文保留缩进>"""
```

- **闭合** = 连续三个同类引号；孤立引号与转义引号（`\"`）不闭合；
- **转义** 与单行字符串同一规则表（`\n` `\t` `\\` `\"` `\'` 等；未知转义保留双字符）；
- **反斜杠+换行** = 行拼接（结果不含换行，下一行缩进保留）；
- 空串 = `""""""`（六个引号）或 `""`。

### 1.2 泛型容器类型

```ibci
list[int]          # 整数列表
list[str]          # 字符串列表
list[any]          # 异构列表（元素访问返回 any；不支持 list[int,str] 多类型声明）
dict[str,int]      # string→int 字典
dict[str,str]      # string→string 字典
```

### 1.3 特殊值

```ibci
None        # 空值（首字母大写）
```

`None` 在布尔上下文中为假。`(str)None` 返回 `"None"`。

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

    func cast_to(self, any target) -> any:
        if type(target) == "str":
            return (str)self.value + "°C"
        return self

Temperature t = Temperature(25.0)
str s = (str)t          # "25.0°C"
```

**编译期检查**：对于声明了转换规则的类型，编译器会在转换明显不合法时报 `SEM_CAST_NO_CONVERTER` 错误（如 `(int)file_handle`）。未声明转换规则的类型不做编译期校验，由运行时裁定。
### 1.5 vector（内置值类型）

词嵌入向量：固定维度、创建后不可变的**纯值类型**（值语义——逐元素精确相等/不等，
可作 dict key / set 成员）：

- **产生面**：经 `ai.embed` embedding 服务产生（见 `docs/syntax/11_modules.md` §11.3）；
  无字面量语法、不经 LLM 输出解析。
- **方法面**（修改操作走方法、返回新 vector；无算术运算符面）：

  | 方法 | 签名 | 说明 |
  |------|------|------|
  | `dim` | `dim() -> int` | 维度 |
  | `dot` | `dot(other: vector) -> float` | 点积 |
  | `norm` | `norm() -> float` | 模长 |
  | `cosine` | `cosine(other: vector) -> float` | 余弦相似度（尺度不变） |
  | `scale` | `scale(k: float) -> vector` | 标量缩放 |
  | `add` | `add(other: vector) -> vector` | 逐元素加 |
  | `sub` | `sub(other: vector) -> vector` | 逐元素减 |
  | `cast_to` | `cast_to(target) -> auto` | 类型转换 |

- **元素访问**：只读下标 `v[0] -> float`（越界 fail-fast）。
- **相等与相似**：`==`/`!=` = 逐元素精确相等（维度不同 = 不等）；相似度判定经
  `cosine` 显式表达，无隐式容差、无隐式归一化。
- **序列化**：snapshot / save_state / deep_clone 全链路支持。

---

## 深入指引

- 类型系统设计与原理：docs/architecture/03_type_system.md
- 语言级类型限制：docs/KNOWN_LIMITS.md
