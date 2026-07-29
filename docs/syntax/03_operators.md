## 3. 运算符

> 本章描述 IBCI 的运算符系统。面向已阅读变量章节的开发者。覆盖算术、比较、逻辑、成员与身份运算符的语法与优先级。

### 3.1 算术运算符

| 运算符 | 说明 | 支持类型 |
|--------|------|---------|
| `+` | 加法 / 字符串拼接 / 列表拼接 | int, float, str, list |
| `-` | 减法 | int, float |
| `*` | 乘法 / 字符串重复 / 列表重复 | int, float, str×int, list×int |
| `/` | 除法：**在 IBCI 中，`int/int` 也执行地板除**；若任一操作数为 `float`，则执行浮点除法 | int, float |
| `//` | 显式整除（与 `int/int` 的 `/` 一致，但在源码中更直观） | int, float |
| `%` | 取模 | int, float |
| `**` | 幂运算 | int, float |
| `&` | 按位与 | int |
| `\|` | 按位或 | int |
| `^` | 按位异或 | int |
| `~` | 按位取反（一元） | int |
| `<<` | 左移 | int |
| `>>` | 右移 | int |

```ibci
int a = 10 + 3       # 13
int b = 7 / 2        # 3（int/int 按地板除处理）
float c = 7.0 / 2    # 3.5（涉及 float 时为浮点除法）
int d = 7 // 2       # 3（显式整除）
int e = 2 ** 3       # 8（幂运算）
int f = 6 & 3        # 2（按位与）
int g = 6 | 1        # 7（按位或）
int h = 1 << 3       # 8（左移）
str s = "ab" * 3     # "ababab"
list[int] l = [1,2] * 3   # [1,2,1,2,1,2]
```

### 3.2 比较运算符

| 运算符 | 说明 | 支持类型 |
|--------|------|---------|
| `==` | 等于 | 所有类型 |
| `!=` | 不等于 | 所有类型 |
| `<` | 小于 | int, float, str |
| `<=` | 小于等于 | int, float, str |
| `>` | 大于 | int, float, str |
| `>=` | 大于等于 | int, float, str |

字符串比较遵循 Unicode 码点顺序。

### 3.3 逻辑运算符

```ibci
bool r1 = True and False    # False
bool r2 = True or False     # True
bool r3 = not True          # False
```

### 3.4 成员检测运算符

```ibci
bool b1 = 3 in [1, 2, 3]          # True
bool b2 = "x" not in ["a", "b"]   # True
bool b3 = "key" in {"key": 1}     # True（字典键检测）
```

### 3.5 身份检测运算符

`is` 和 `is not` 检测两个表达式是否指向同一个运行时对象（身份比较，非值比较）。

```ibci
bool b1 = x is None          # x 是否为 None
bool b2 = x is not None      # x 是否不为 None
```

与 `==` 的区别：`==` 比较值是否相等；`is` 比较是否是同一个对象实例。对于 `None` 字面量，`is` 使用类型检测而非实例身份。
