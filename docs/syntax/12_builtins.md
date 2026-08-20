## 12. 内置函数与方法

> 本章描述 IBCI 的内置函数与内置类型方法。面向已阅读模块章节的开发者。覆盖 print/range/len 等全局函数与 str/list/dict/tuple 等内置类型的方法。

### 12.1 全局内置函数

| 函数 | 说明 |
|------|------|
| `print(value, ...)` | 输出值（支持任意类型与多参数） |
| `input(prompt)` | 读取一行输入（可选提示词） |
| `range(n)` | 生成 `[0, n)` 整数序列 |
| `range(start, end)` | 生成 `[start, end)` 整数序列 |
| `range(start, end, step)` | 生成 `[start, end)` 整数序列（步进） |
| `len(container)` | 获取容器长度（列表/字符串/字典） |
| `type(value)` | 返回值的规范类型名（`int`/`str`/`list[int]`/`Box[int]` 等）；内置泛型容器值保留特化实参（`list[int]` 值 → `list[int]`），对 fn_callable/behavior 返回含签名形态（如 `fn_callable[()->int]`，见 `05_functions.md` §5.7） |
| `int(value)` / `str(value)` / `float(value)` / `bool(value)` | 类型转换：`int("42")` → 42、`str(42)` → "42"、`float("3.5")` → 3.5、`bool(1)` → True（零参：`int()` → 0 等） |
| `enumerate(iterable)` | 生成 `[(索引, 值), ...]` 元组列表（与 `for (int i, str v) in ...` 搭配） |
| `zip(a, b, ...)` | 按位置组合多个序列为元组列表（按最短截断） |
| `sorted(iterable)` | 返回新排序列表（不改动原容器；区别于原地 `list.sort()`） |
| `reversed(iterable)` | 返回新逆序列表（不改动原容器；区别于原地 `list.reverse()`） |
| `sum(iterable)` | 数值元素之和（`list[int]`/`list[float]`） |
| `all(iterable)` | 全部元素为真 → `bool` |
| `min(a, b, ...)` / `min(iterable)` | 最小值（多参逐值比较，或单参集合） |
| `max(a, b, ...)` / `max(iterable)` | 最大值（同上） |
| `next(iterable)` | 惰性推进生成器至下一个产出值（生成器语义见 `05_functions.md`） |
| `copy(value)` | 浅拷贝：容器新建 + 元素引用共享（`copy(list)` 后修改副本不影响原容器；嵌套容器元素仍共享） |
| `deepcopy(value)` | 深拷贝：递归独立副本（嵌套容器/用户对象字段独立；不可克隆值如函数/行为回退原引用） |

> `copy` / `deepcopy` 在值语义模型中的角色见 `docs/syntax/02_variables.md` §2.8（赋值 = 引用复制，需要独立副本时用显式拷贝）。

> **内建函数名可被用户变量声明遮蔽**：`int len = 5` 会遮蔽内建 `len`，其后该名字指
> 用户变量（与 Python 一致）。内建**类型名**（`int`/`str`/`list` 等）不可遮蔽；对
> 内建名的直接赋值（`print = 5`）仍被拒绝。

```ibci
# 类型转换
int a = int("42")            # 42
str b = str(42)              # "42"
float c = float("3.5")       # 3.5
bool d = bool(1)             # True

# 序列辅助（与 for 元组解包搭配）
list[str] names = ["a", "b"]
for (int i, str name) in enumerate(names):
    print(i, name)           # "0 a" / "1 b"

list[int] l = [3, 1, 2]
list[int] s = sorted(l)      # [1, 2, 3]；l 仍为 [3, 1, 2]

# 聚合与最值
list[int] nums = [1, 2, 3]
int total = sum(nums)        # 6
int hi = max(nums)           # 3
int lo = min(nums)           # 1
int hi2 = max(3, 1, 2)       # 3
list[bool] flags = [True, False]
bool ok = all(flags)         # False
```

### 12.2 str 方法

```ibci
str s = "  Hello World  "
s.len()              # 15
s.strip()            # "Hello World"（等同于 trim()）
s.upper()            # "  HELLO WORLD  "
s.lower()            # "  hello world  "
s.split(" ")         # ["", "", "Hello", "World", "", ""]
s.replace("Hello", "Hi")    # "  Hi World  "
s.startswith("  Hello")     # True
s.endswith("  ")            # True
s.contains("World")         # True
s.find("World")             # 8
s.find_last("l")            # 11
s.is_empty()                # False

# 拼接、重复与下标访问
str a = "ab" + "cd"    # "abcd"
str b = "ab" * 3       # "ababab"
str ch = s[0]          # " "
```

### 12.3 list 方法

```ibci
list[int] l = [3, 1, 2]
l.append(4)            # [3, 1, 2, 4]
l.insert(0, 99)        # [99, 3, 1, 2, 4]
l.remove(99)           # [3, 1, 2, 4]
l.sort()               # [1, 2, 3, 4]
l.reverse()            # [4, 3, 2, 1]
int v = l.pop()        # v=1, l=[4, 3, 2]
l.clear()              # []
int idx = l.index(3)   # 找到 3 的索引
int cnt = l.count(2)   # 统计 2 出现次数
bool has = l.contains(3)   # True / False
int n = l.len()        # 长度

# 列表拼接与重复
list[int] a = [1, 2] + [3, 4]     # [1, 2, 3, 4]
list[int] b = [1, 2] * 3          # [1, 2, 1, 2, 1, 2]

# 下标访问与赋值
int first = l[0]
l[0] = 99
```

### 12.4 dict 方法

```ibci
dict[str,int] d = {"a": 1, "b": 2}
d["c"] = 3                  # 新增/更新
int v = d["a"]              # 取值
bool has = "a" in d         # 键存在检测
list pairs = d.items()      # [[key, value], ...] 列表
d.update({"d": 4, "a": 99}) # 合并/更新

# 删除键
d.remove("a")

# 其它常用方法
int val = d.get("e", 0)     # 取值，不存在时返回默认值 0
int popped = d.pop("a", 0)  # 取值并删除，不存在时返回默认值
list keys = d.keys()        # 所有键的列表
list vals = d.values()      # 所有值的列表
bool has_key = d.contains("a")  # 键存在检测（方法形式）
int size = d.len()          # 键值对数量
```

### 12.5 tuple

```ibci
tuple t = (1, "hello", True)
auto first = t[0]     # 1（下标访问）
int n = t.len()       # 3
```
---

## 深入指引

- 内建类型公理：docs/architecture/03_type_system.md §4
