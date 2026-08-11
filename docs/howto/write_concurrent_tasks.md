# 如何编写并发任务

> 面向已能运行单任务 IBCI 脚本的开发者。解决"如何让多个任务并行、如何在任务间通信、如何等待异步结果"的具体问题。
> 前置知识：`docs/syntax/14_concurrency.md`（并发与通信原语）、`docs/syntax/05_functions.md`（函数）。

## 何时需要并发

任务间存在独立工作且希望整体更快、或天然需要跨任务数据流时使用。IBCI 的并发模型：

- **线程**：后台任务，`thread[T]` 声明，`t.join()` / `await t` 等待结果。
- **通道（chan）**：任务间消息传递（生产-消费 / 发布-订阅）。
- **槽（slot）**：跨任务共享状态（读改写）。
- **协作挂起**：阻塞操作在 VM 任务内让出 CPU，不阻塞线程。

## 启动一个后台线程

```ibci
func fetch(int x) -> int:
    return x * 2

thread[int] t = thread(callable=fetch, args=[21])
thread_result[int] r = t.join()      # 等待完成 → 结果容器
print((str)r.value)                  # 42
```

- `T` 为返回类型（`void` 亦可）。
- `t.join()` 在 VM 任务内是**协作挂起**：等待期间调度器运行其它任务，不阻塞线程。

## 用 await 等待线程

`await t` 等价于 `t.join()`，且 `await thread[T]` 编译期收敛为 `thread_result[T]`：

```ibci
thread[int] t = thread(callable=fetch, args=[21])
thread_result[int] r = await t       # 同 t.join()
```

## 线程间用通道传递数据

生产-消费（`stream` 模式）：

```ibci
chan c = chan(str, "stream")

func producer():
    c.send("第一")
    c.send("第二")

func consumer() -> str:
    str acc = c.recv()             # 阻塞接收第一个
    str second = c.recv()          # 阻塞接收第二个
    return acc + " " + second

thread[void] p = thread(callable=producer, args=[])
thread[str] cons = thread(callable=consumer, args=[])
str out = cons.join().value         # "第一 第二"
```

> 精确的消费结束信号（如通道关闭检测）以 `docs/syntax/14_concurrency.md` 当前语义为准；需要非阻塞轮询用 `recv_nowait()`（空缓冲返回 `None`）。

发布-订阅（`pubsub` 模式）：`c.subscribe()` 创建独立端点，`send` 广播给全部订阅者：

```ibci
chan c = chan(int, "pubsub")
subscriber a = c.subscribe()
subscriber b = c.subscribe()

c.send(7)
int va = a.recv()   # 7
int vb = b.recv()   # 7
```

## 共享状态用 slot

跨任务共享可变值：

```ibci
slot counter = slot("counter", 0)

func bump(int n):
    int i = 0
    while i < n:
        counter.update(lambda(int v) -> auto: (v + 1))   # CAS 读改写
        i = i + 1
```

`slot.update` 传可调用对象时做原子读改写，避免读-改-写竞态。

## 非阻塞投递与接收

缓冲满/空时不想阻塞用 `*_nowait` 变体：

```ibci
bool ok = c.send_nowait(x)   # 队列满 → False，不阻塞
any v = c.recv_nowait()      # 空缓冲 → None，不阻塞
```

## 常见陷阱

- **任务不写主环境作用域**：跨任务数据必须经 `chan` / `slot` 显式传递（见 `14_concurrency.md` §14.1）。
- **类构造例外**：`thread(...)` 的 `__init__` 是原生函数，返回的 `IbThread` 是句柄，**不自动挂起**——等待须显式 `t.join()` / `await t`。
- **`collect` 自动挂起**：调用返回 Waitable 的方法（如 `ihost.collect`）会自动挂起等待，无需显式 `await`。
- **超时/死锁**：有界通道 + 双端阻塞可能死锁；用 `recv_nowait` / 充足缓冲 / 明确关闭信号规避。

## 深入指引

- 并发原语完整参考：`docs/syntax/14_concurrency.md`
- 批量并发 LLM 调用（`ai.run_batch`）：`docs/syntax/08_llm_functions.md`
- 通信原语限制：`docs/KNOWN_LIMITS.md` §二十二
- 后台调试：`docs/howto/debug_llm_calls.md`
