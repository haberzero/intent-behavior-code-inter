## 6. 面向对象

> 本章描述 IBCI 的面向对象编程支持。面向已阅读函数章节的开发者。覆盖类定义、继承、super()、Enum 枚举与协议方法。

### 6.1 类定义

```ibci
class Point:
    int x
    int y

    func __init__(self, int x, int y) -> auto:
        self.x = x
        self.y = y

    func distance(self) -> float:
        return (float)(self.x * self.x + self.y * self.y)
```

字段可以有默认值：

```ibci
class Config:
    str mode = "default"
    int retries = 3
    list[str] tags = []
```

### 6.2 构造与访问

```ibci
Point p = Point(3, 4)
print((str)p.x)          # 3
print((str)p.distance()) # 25.0
```

### 6.3 继承

```ibci
class Animal:
    str name

    func __init__(self, str name) -> auto:
        self.name = name

    func speak(self) -> str:
        return self.name + " says something"


class Dog(Animal):
    func speak(self) -> str:
        return self.name + " says Woof!"


Dog d = Dog("Rex")
print(d.speak())    # Rex says Woof!
```

### 6.4 `super()`

> `super()` 对所有 IBCI 用户类均有效——所有用户类隐式继承自 `Object` 基类（类似 Python 3）。即使没有显式写 `class Foo(Bar):`，`super()` 也可在方法内使用，此时它指向 `Object`。

```ibci
class Base:
    int value

    func __init__(self, int v) -> auto:
        self.value = v

    func describe(self) -> str:
        return "Base: " + (str)self.value


class Derived(Base):
    str label

    func __init__(self, int v, str label) -> auto:
        super().__init__(v)
        self.label = label

    func describe(self) -> str:
        return self.label + " / " + super().describe()
```

### 6.5 Enum

```ibci
class Status(Enum):
    str PENDING  = "PENDING"
    str RUNNING  = "RUNNING"
    str DONE     = "DONE"

Status s = Status.RUNNING

if s == Status.RUNNING:
    print("正在运行")
```

> **Known Limit (docs/KNOWN_LIMITS.md §二)**：枚举成员值是其声明类型的底层值（非枚举实例），
> 因此枚举自定义方法不可在成员值上调用。枚举支持任意底层类型（`str`/`int`/`float`/`bool`）、
> 迭代（`for v in Color:`）与数量（`len(Color)`）。

### 6.6 特殊方法（协议）

| 方法名 | 触发场景 | 说明 |
|--------|---------|------|
| `__init__(self, ...)` | 构造 `ClassName(...)` 时 | 初始化方法 |
| `__call__(self, ...)` | 对实例 `obj(...)` 调用时 | 可调用对象协议 |
| `__iter__(self)` | `for x in obj:` 时 | 迭代器协议，返回可遍历列表 |
| `__to_prompt__(self)` | 变量插值到 `@~ ... ~` 时 | 转为 LLM 提示词文本 |
| `__from_prompt__(str raw)` | LLM 返回值解析时 | 从文本解析为当前类型实例。**必须返回 `(bool, 实例)` 元组**——首元素为成功标志，次元素为解析出的实例（返回裸实例会被当作不确定失败） |
| `__outputhint_prompt__(self)` | 类型作为 LLM 输出目标时 | 提示 LLM 期望的输出格式 |
| `__payload_prompt__(self)` | 变量插值到多模态 `@~ ... ~` 时 | 返回结构化 content block（图像/音频等） |
| `__snapshot__(self)` | llmexcept 快照进入时 | 返回用于恢复状态的快照值 |
| `__restore__(self, state)` | llmexcept retry 前 | 从快照值恢复对象状态 |
---

## 深入指引

- 用户类能力差距：docs/KNOWN_LIMITS.md §十四
- Enum 语法限制：docs/KNOWN_LIMITS.md §二
