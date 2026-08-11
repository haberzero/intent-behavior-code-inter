# 如何使用惰性生成器

> 面向已能定义函数与循环的开发者。解决"如何逐值产生序列、节省内存、或按需驱动复杂计算"的具体问题。
> 前置知识：`docs/syntax/05_functions.md` §5.8/5.9（惰性生成器语法）、`docs/syntax/04_control_flow.md`（`for` 循环）。

## 何时用生成器

需要**按需产生一组值**且不想一次性构造整个序列时使用。典型场景：

- 计算规模大（逐项产出，避免一次全量分配）
- 序列依赖运行期状态（每次迭代才推进）
- 与 LLM 组合（每次迭代触发一次行为，逐个消费）

```ibci
func countdown(int n) -> int:      # 含 yield → 惰性生成器
    int i = n
    while i > 0:
        yield i
        i = i - 1
```

## 迭代一个生成器

`for` 循环自动推进生成器并逐值恢复其帧状态：

```ibci
for int x in countdown(3):
    print((str)x)
# 输出 3 2 1
```

生成器体在 `yield` 点保留整个帧（循环位置、局部变量），下次迭代从挂起点继续。

## 一次性转为列表

需要多次遍历或随机访问时，用 `to_list()` 物化：

```ibci
func naturals(int n) -> int:
    int i = 0
    while i < n:
        yield i
        i = i + 1

list[int] xs = naturals(4).to_list()   # [0, 1, 2, 3]
```

## 逐次取下一个值

`next(gen)` 推进一次并返回产出；耗尽后抛可捕获异常：

```ibci
import idbg

func gen(int n) -> int:
    int i = 0
    while i < n:
        yield i
        i = i + 1

any g = gen(2)
print((str)next(g))   # 0
print((str)next(g))   # 1
try:
    next(g)           # 已耗尽 → 抛异常
except Exception as e:
    print("耗尽：" + e.message)
```

## 委托给子迭代（yield from）

`yield from <expr>` 把子迭代对象的每个产出透传为当前生成器的产出。子迭代可以是嵌套生成器、序列或有迭代协议的对象：

```ibci
func prefix() -> int:
    yield 0
    yield 1

func combined() -> int:
    yield from prefix()      # 透传 0, 1
    yield 9                  # 再产出 9

for int x in combined():
    print((str)x)            # 0 1 9
```

外层 `break` 提前终止时，子迭代不再继续（惰性）。

## 与 LLM 组合

生成器体可含行为表达式，每次迭代触发一次 LLM 调用：

```ibci
func greet(int n) -> str:
    int i = 0
    while i < n:
        yield @~ 说一句第 $i 次问候 ~
        i = i + 1

for str msg in greet(2):
    print(msg)
```

`yield` 的操作数是行为时，产出 LLM 解析结果；生成器驱动与 LLM 协作挂起正交（见 `docs/syntax/14_concurrency.md`）。

## 常见陷阱

- **`yield` 只在函数体内**：模块顶层 `yield` 报 `SEM_YIELD_OUTSIDE_FUNCTION`。
- **不要期望提前返回**：`return` 结束生成器（耗尽），不产出额外值。
- **只消费一次**：生成器是惰性单次迭代；需复用请 `to_list()` 物化。

## 深入指引

- 生成器语法与委托：`docs/syntax/05_functions.md` §5.8/5.9
- 迭代与 `next()` 内建：`docs/syntax/12_builtins.md`
- 并发协作：`docs/syntax/14_concurrency.md`
