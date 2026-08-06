## 14. 并发与通信

> 本章描述 IBCI 的并发与通信原语：`chan`（通道）、`slot`（共享状态槽）、`subscriber`（订阅端点）、`thread`（后台线程）。面向已阅读控制流与函数章节的开发者。覆盖跨任务数据传递、共享状态读写、发布订阅与后台任务生命周期。

### 14.1 隔离模型

线程在**任务本地执行上下文**中运行：每个任务持有独立的意图栈与 llmexcept 保护帧，共享只读的类型与函数定义。任务**不写主环境作用域**；跨任务数据必须经 `chan` / `slot` 显式通信。

### 14.2 chan 通道

`chan(T, name, mode=..., buffer=...)` 构造通道；`T` 为消息元素类型，`name` 供注册表内省，`mode` 选择消息语义，`buffer` 为队列容量（0=无界，>0 有界）。

| 方法 | 语义 |
|------|------|
| `c.send(x)` | 阻塞投递（message/stream 排入队列；pubsub 广播给全部订阅者） |
| `c.send_nowait(x)` | 非阻塞投递 → `bool`；pubsub 无订阅者、或订阅者队列满时返回 False |
| `c.recv()` | 阻塞接收 → `T` |
| `c.recv_nonblocking()` | 非阻塞接收 → `T` 或 `None`（空缓冲） |
| `c.subscribe(buffer=0)` | 创建订阅端点 → `subscriber`（pubsub 模式） |

**模式（`mode=`）**：

| 模式 | 语义 |
|------|------|
| `stream` | 有序 FIFO 流，生产-消费 |
| `message` | 离散消息队列，点对点排队 |
| `pubsub` | 发布-订阅：`subscribe()` 创建独立端点，`send` 广播给全部端点 |

```ibci
chan c = chan(str, "stream")
c.send("hello")
str msg = c.recv()   # "hello"
```

### 14.3 subscriber 订阅端点

`subscriber sub = c.subscribe()` 为 pubsub 通道创建独立队列端点；`sub.recv()` 从**自己的**队列阻塞接收（端点互不影响）。

```ibci
chan c = chan(int, "pubsub")
subscriber a = c.subscribe()
subscriber b = c.subscribe()
c.send(7)            # 广播
int x = a.recv()     # 7
int y = b.recv()     # 7
```

pubsub 模式下无订阅者时 `send_nowait` 返回 False——消息未投递给任何端点。

### 14.4 slot 共享状态槽

`slot(name, value)` 构造共享状态槽（跨任务读写共享值）。

| 方法 | 语义 |
|------|------|
| `s.get()` | 读取当前值 |
| `s.set(x)` | 写入新值 |
| `s.update(x)` | 普通值 → 直接 set；可调用对象 → `fn(当前值) → 新值` 的原子 CAS 读改写 |

```ibci
slot st = slot("score", 0)
st.set(42)
int v = st.get()      # 42

slot s = slot("x", 10)
fn inc = lambda(int v) -> auto: (v + 1)
s.update(inc)         # CAS 读改写：11
```

### 14.5 thread 后台线程

`thread[T] t = thread(callable=fn, args=[...])` 在后台线程运行 `fn`，`T` 为返回值类型（`void` 亦可）。

| 方法 | 语义 |
|------|------|
| `t.join()` | 阻塞等待完成 → `thread_result[T]` |
| `t.is_done()` | 非破坏状态查询 → `bool` |
| `t.cancel()` | 协作式取消请求 → `ThreadCancelled` |

```ibci
func add(int a, int b) -> int:
    return a + b

thread[int] t = thread(callable=add, args=[1, 2])
thread_result[int] r = t.join()
int v = r.expect()     # 3
```

`cancel()` 为协作式：运行中的纯 CPU 任务无可挂起点时无法强制中断。

### 14.6 thread_result 结果容器

`thread_result[T]` 承载线程结果（成功 `value=T`；失败 `error=异常`，`status` 区分 `done`/`failed`/`cancelled`）。

| 成员 | 语义 |
|------|------|
| `r.expect()` | 成功值 `T`；失败抛 IBCI 异常（fail-fast） |
| `r.is_success()` / `r.is_error()` | `bool` 状态查询 |
| `r.value()` / `r.error()` / `r.status()` | 内省读取（失败时 `value()` 为 null 等） |

```ibci
func fail() -> int:
    raise Exception("boom")

thread[int] t = thread(callable=fail, args=[])
thread_result[int] r = t.join()
bool ok = r.is_error()   # True
```
---

## 深入指引

- 并发调度器设计：docs/architecture/04_vm_interpreter.md
- 通信原语限制：docs/KNOWN_LIMITS.md §二十二
