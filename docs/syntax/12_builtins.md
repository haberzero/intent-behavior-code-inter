## 12. 内置函数与方法

> 本章描述 IBCI 的内置函数与内置类型方法。面向已阅读模块章节的开发者。覆盖 print/range/len 等全局函数与 str/list/dict/tuple 等内置类型的方法。

### 12.1 全局内置函数

| 函数 | 说明 |
|------|------|
| `print(value)` | 输出值（支持任意类型） |
| `range(n)` | 生成 `[0, n)` 整数序列 |
| `range(start, end)` | 生成 `[start, end)` 整数序列 |
| `len(container)` | 获取容器长度（列表/字符串/字典） |

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
s.find_last("l")            # 9
s.is_empty()                # False

# 别名方法
s.trim()                    # 等同于 strip()
s.to_upper()                # 等同于 upper()
s.to_lower()                # 等同于 lower()

# 字符串拼接与重复
str a = "ab" + "cd"    # "abcd"
str b = "ab" * 3       # "ababab"

# 下标访问
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
