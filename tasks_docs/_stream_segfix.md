# _stream_segfix — 流式句柄退出段错误（KERNEL_ISSUE-STREAM-1）根因修复设计

> 临时任务文档（设计阶段）；实现落地后按治理删除，结论收敛入 WORKLOG / INDEX / 架构文档。

## 一、现象

阶段 C 真实 LLM 回归复跑（free-explore 分支，35B 共享端点）中 T08 `D5-02-stream-channel`
间歇性 SIGSEGV（harness 记 exit=-11，`timed_out=False`——进程自身段错误，非超时强杀）。

- 用例输出**完整**（`got_gt0=True | DONE` 全打印）→ 崩溃发生在**进程退出阶段**，非用例体。
- 复现矩阵（2026-09-06）：单发 15 次 0 崩；2 并发 12 轮 4 崩（崩溃率随并发/端点延迟上升）。
- faulthandler 崩溃栈：单线程 `<no Python frame>` → 线程死在 **C 扩展内部**
  （openai 流式解析链：jiter/h11/httpx Rust+C 层）。

## 二、根因链（三层叠加，缺一不崩或窗口更小）

1. **流句柄生命周期悬空**：`ai.stream_channel`（`_StreamCallableDrive` channel_mode）返回
   `IbChannel`（仅 `ChannelCore` 存活）；`IbStreamHandle` 及其 producer 生成器失去用户可达性，
   但 daemon 消费线程（`ibci-stream`）仍在消费**活的 HTTP 流**。脚本只 recv 一块即结束 →
   流被**放弃**，线程继续后台运行。
2. **退出竞态**：CPython 对 daemon 线程**不等待**——主线程退出后进入解释器终结
   （finalizer），daemon 线程被弃置。若该线程此刻在 C 扩展代码内（流式 JSON 解析 /
   socket 读），C 扩展状态随 finalizer 释放 → use-after-free → SIGSEGV。
3. **资源不闭环**：provider `_gen()`（`provider_impl.py` stream 路径）无 `finally` 清理——
   生成器被放弃时 HTTP 流（openai `Stream`）不关闭，连接在共享端点悬挂，线程有持续的
   C 层活动（扩大竞态窗口）。

`stream_call`（channel_mode=False）路径经调度器等待流耗尽（`result()` join 120s）→ 线程
已终结，无此风险——与实证一致（D5-01 stream-call 并发零崩溃）。

## 三、修复（单链三层，无双通道）

1. **`IbStreamHandle.cancel()`**（新公开生命周期方法，与 `SpawnedTask.cancel` 协作式同构）：
   - 幂等、线程安全（单一锁保护 `_cancelled` / `_done`）。
   - **cancel 只置标志，不触碰生成器**——CPython 禁止对运行中生成器跨线程
     `gen.close()`（`ValueError: generator already executing`，实测 2026-09-06）；
     **消费线程是生成器唯一操作者**（单写者）：每块检查 `_cancelled` → break →
     finally 内 **in-thread** `gen.close()`（此刻线程不在生成器体内，close 合法）→
     provider 生成器 finally 关闭 HTTP 流 → 资源闭环。
   - **producer 契约 = 生成器**：非生成器迭代器无 in-thread 关闭协议，阻塞型
     迭代器被放弃时悬挂 → 消费入口 fail-fast 校验（TypeError → 生产异常路径）。
     provider 真实路径（`_gen()`）与 mock 路径均生成器形态（mock 原 `iter([...])`
     同步改为生成器）。
   - **终态语义 = 协作式截断**：`is_done=True`、无 error、`result()` 返回截断前缀
     文本（语义明确、可预期；不引入"取消错误"新形态）。
   - cancel 生效时延 = 一个块 I/O（线程可能正阻塞在 `next(gen)` 的块读上，
     块读返回后经标志检查退出）——健康端点下单块毫秒级。
2. **provider `_gen()` 资源闭环**：`finally: stream_resp.close()`——HTTP 流释放是
   生成器自身职责（单一权威源）；谁放弃生成器谁负责关流。
3. **进程退出兜底**（`stream.py` 模块级）：live 句柄注册表 + `atexit` 钩子
   `_drain_live_streams()`——退出时（解释器仍存活）对每个 live 句柄 `cancel()` +
   `join(timeout=2s)` 有界等待，确保消费线程**在终结危险区之前干净退出**。
   - 超时仍退出（daemon 语义不变：**永不阻塞进程退出**）；超时残留 = LLM 挂死场景，
     与现状等价、不新增危害（记为已知角落，见 §五）。
   - 注册表用强引用 set（句柄被放弃后无用户引用，弱引用即失效——退出兜底必须
     能看见它们）；线程经 `self._consume` 闭包天然持有句柄，注册表条目不产生
     额外泄漏（流终结 / cancel 即移除）。

**非目标**（记后续评估，不随本修扩面）：
- 用户层显式截断 API（`chan` 面）：本修复后"放弃流即安全"已是默认语义；
  若未来需要显式 cancel 语言面，随 C6（流式编排完善，批 3）统一设计。
- coordinator `SpawnedTask` 的同型风险（阻塞外部 I/O 的用户任务）：无实证崩溃，
  且任务体取消事件已部分缓解；归入质量维护 Tier C 专项评估（记 WORKLOG）。

## 四、验证门

1. pytest 新增：cancel 语义（截断前缀 / finally 触发 / 线程终结 / 幂等）+
   atexit drain 路径（放弃流被 drain）——mock producer 确定性，无真实 LLM 依赖。
2. 并发复跑门：D5-02 2 并发 × 12+ 轮（修复前 4/12 崩）→ 零 SIGSEGV。
3. 全量 pytest 零回归。
4. T08 套件 `--llm-only` 复跑（D5-02 转 PASS，其余与修复前分类一致）。

## 五、已知角落（记录，不修）

atexit drain 的 join 超时时（LLM 流挂死 >2s），线程仍可能在 C 层被弃置——与修复前
同型风险、但窗口从"任意放弃时刻"收窄到"仅挂死 LLM"。彻底消除需 C 层协作取消
（如 socket 强制关闭由 cancel 直接执行），属 provider 层深化，待 C6 评估。
