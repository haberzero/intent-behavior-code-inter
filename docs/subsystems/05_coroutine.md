# 协程与迭代器设计

> 本文档记录 IBCI 协程/迭代器相关的架构分析。**状态变更（2026-08-02）**：用户裁定 **LLM 真正可用的并行化 + 同步异步** 为当前主线，本方向由搁置升为主线（架构定案 Option A 混合模型，见 `tasks_docs/NEXT_STEPS.md`）。完整语言级 async/await 为演进目标，暂缓至 VM 多任务化稳定后。当前实现状态以代码为准。

---

## 一、搁置原因（历史）

协程相关功能（L3 协程层、async/await/yield）曾暂缓。主要原因：

1. `dispatch_eager` + `LLMFuture` 覆盖最主要的异步 LLM 需求，用户无需显式写 async/await
2. 协程层需要 VM 从"单任务调度器"升级为"多任务挂起/恢复"架构，跨五层改动（lexer/parser/semantic/vm/runtime）
3. 缺乏明确的用户需求来源——当前 IBCI 用户脚本都是线性流程 + LLM 调用
4. 当时优先级：多模态功能的完善和定义

**2026-08-02 重新评估**：多模态无限期搁置（条件 4 不再成立）；用户裁定并行化 + 同步异步为主线（条件 3 由"等待需求"转为"明确需求"）；条件 1 的"隐式 async 足够"判断被推翻——`dispatch_eager`+`resolve` 的隐式阻塞是魔法（违反显式优于隐式），且共享状态存在并行竞争（"能用但不真正可用"）。故解封升为主线。

---

## 二、现有基础设施分析（可复用）

### 2.1 CPS 风格调度循环

- `VMExecutor`（`core/runtime/vm/vm_executor.py`）：所有语句执行已转为 VM 帧栈驱动，递归 visit 已消除
- 这是协程化的**必要前置**——无 CPS 帧栈则无法实现 yield 点保存/恢复

### 2.2 ControlSignal 枚举

- 位置：`core/runtime/vm/task.py` 的 `ControlSignal` 枚举
- 包含 `break` / `continue` / `return` / `llm_uncertain` 信号类型
- 可扩展：新增 `YIELD` 信号类型用于协程挂起

### 2.3 dispatch_eager + LLMFuture

- 位置：`core/runtime/vm/handlers/` 包中的赋值上下文调度逻辑
- "异步提交 → 延迟解析"模式可行
- 后台 LLM 请求 + 使用点阻塞解引用

---

## 三、协程层（L3）设计维度

> **架构定案（2026-08-02，Option A 混合模型）**：LLM IO 保持线程池（仅纯 IO 边界，不触碰共享状态）；VM 多任务协作调度（单线程、无锁）；语言级 async/await 为 Stage 3 演进目标。**核心洞察**：executor 共享状态去共享化（per-task 所有权）既是并行可靠性根因修复，也是多任务调度器的地基——两者是同一重构。

### 3.1 调度器架构

- **当前**：`VMExecutor` 是单根任务（`vm.run(uid)` 一次执行完毕）
- **需要**：多任务队列 + `Signal.YIELD` 挂起语义
- **挑战**：如何在 yield 点保存完整的执行上下文（帧栈 + 局部变量 + intent context）
- **方向**：任务句柄持有自己的状态栈；per-task 状态所有权（对应共享状态去共享化）

### 3.2 语言层关键字

- `async` / `await` / `yield` 均不在现有 KEYWORDS 表中
- 需设计语法与对应的类型系统支持
- 涉及 lexer token 新增 + parser 语法规则 + semantic pass 处理 + VM handler

### 3.3 快照协议对齐

- **问题**：协程挂起时如何保存 intent_context 栈 + llmexcept 帧栈
- **现状**：`try_deep_clone` 仅服务 llmexcept retry，不覆盖协程 yield 点
- **需要**：设计"协程帧快照"协议，与现有 llmexcept snapshot 兼容

---

## 四、被阻塞的子项

| 编号 | 标题 | 依赖 L3 的原因 |
|------|------|---------------|
| 1 | `host.run_isolated()` 返回值改进 | 当前返回 `IbObject`/`bool`，需要协程句柄才能实现"异步等待子脚本完成" |
| 2 | `ReceiveMode` 枚举演进 | 需要 yield/resume 语义支持流式接收模式 |

---

## 五、迭代器协议扩展方向

### 5.1 当前迭代器实现

- `for x in collection:` 通过 `__iter__` / `__next__` 协议实现
- 内置类型（list、dict、str）通过 axiom 提供迭代能力
- 用户类尚无自定义迭代器支持

### 5.2 未来方向

- **用户类 `__iter__` / `__next__`**：允许用户类实例参与 `for ... in ...` 循环
- **生成器函数（generator function）**：`yield` 关键字使函数变为生成器
- **与协程的关系**：生成器是协程的子集；如果实现了协程，生成器自然可行

### 5.3 与多模态的关系

- 流式多模态响应（如逐帧视频处理）需要 iterator/generator 模式
- 当前决策：多模态采用同步执行语义（完整获取后返回），不依赖流式
- 流式处理属于 L3 协程层功能，搁置

---

## 六、恢复条件（历史）

> 该条件清单原为"何时恢复协程层"而设；**2026-08-02 已由用户裁定直接升为主线**，条件不再适用。保留作为历史记录。

1. 多模态子系统稳定实现并通过充分测试 —— 多模态已无限期搁置
2. 出现明确的用户需求场景（如需要同时等待多个独立 LLM 调用）—— 用户已裁定并行化+同步异步为主线
3. `dispatch_eager` + `LLMFuture` 模式被证明不足以覆盖需求 —— 已判定隐式阻塞是魔法（显式优于隐式）
4. 团队有足够带宽做跨五层（lexer → runtime）的大规模改动 —— 主线立项即带宽承诺

**执行入口**：先核查 §二 基础设施现状（CPS 帧栈/ControlSignal/dispatch_eager），再从 Stage 1（共享状态去共享化）起步。

---

## 七、Stage 2 设计：调度器多任务化（当前推进）

> 本节是异步/协程主线的**当前设计要点**（2026-08-03）。目标：把 VM 从"单栈生成器调度"升级为"多任务协作调度"，作为语言级 async/await（Stage 3）与宿主异步（PT-3.1/3.2）的**共同地基**。设计面向最终语言级目标，不绕路。

> **设计约束（重要）**：IBCI 运行于 Python，受 **GIL 限制**——真正并行的 CPU 计算天然受限，性能和效率都不会高，**这不是本设计的目标**。本异步/并发设计**只为服务 LLM 调用**：LLM 调用是 IO 密集，等待期间释放 GIL，故多线程/协作式调度能让多个 LLM 调用并发推进而不阻塞解释器。因此：单线程协作式调度（VM 侧）+ 线程池做纯 LLM IO 边界（Option A）是正确模型；**不追求 CPU 并行，不优化为通用并发框架**。

### 7.1 现状与缺口

- **现状**：`VMExecutor._drive_loop_body`（`core/runtime/vm/vm_executor.py`）驱动**单个栈**（`VMTask` 列表，每个是一生成器），一次只服务一个逻辑计算。
- **缺口**：无"多任务队列"；`resolve`/`collect`/`run_isolated` 等 IO 等待为**阻塞整个 VM**（`future.result()`），无法并发。
- **关键洞察**：生成器本身就是**可挂起状态**（yield=挂起、send=恢复），帧保存被生成器模型天然解决，无需额外帧快照协议。

### 7.2 核心机制

1. **挂起信号**：`ControlSignal` 新增 `SUSPEND`（携带一个 waitable：`LLMFuture` 或宿主句柄）。生成器在等待 IO 时返回 `SUSPEND(waitable)`，而非阻塞。
2. **任务队列**：调度器从"单栈"升级为"任务队列"（多个独立根任务，各自是栈）。新增一个就绪队列 + 等待表。
3. **轮转**：调度器循环取一个就绪任务推进一步；若返回 `SUSPEND(waitable)`，移入等待表；当 waitable 完成，任务回到就绪队列。
4. **恢复**：对就绪任务的生成器 `send(完成值)` 继续。

### 7.3 关键设计点

- **waitable 抽象**：`LLMFuture`（已有 `is_done`/`get`）与宿主句柄（`spawn_isolated` 返回）统一为"可等待"协议，供调度器询问是否就绪。
- **`resolve` 改造**：从"阻塞 `future.result()`"改为"未就绪则返回 `SUSPEND(future)`，就绪后恢复"——把阻塞整个 VM 变为仅挂起当前任务。
- **`collect`/`run_isolated` 改造**：未就绪则挂起（PT-3.1 宿主异步依托）。
- **快照/状态**：per-task 状态所有权（对应 Stage 1 去共享化）；intent_context、llmexcept 帧栈随任务挂起持久化的方式在实现时确认。

### 7.4 与语言级 async 的关系

- Stage 2 提供"任务可挂起/恢复"机制（地基）。
- 语言级 `async`/`await`（Stage 3）是建立在此之上的**显式语法表面**：`await` 把对 waitable 的挂起表达为语句。
- 宿主异步（PT-3.1/3.2）是 Stage 2 之上的宿主级形态：`run_isolated`/`spawn_isolated` 返回可 await 句柄。

### 7.5 验证方式

- 多任务并发：两个独立任务各自等待不同的 SLEEP forever 的 mock future，断言总时近似 max 而非 sum（复用 `mock_server` 真并发思路）。
- 单任务行为不变：现有全量测试零回归（单栈语义保持，多任务只为并发生效）。

### 7.6 实现进度（2026-08-03）

Stage 2 地基已落地（见 `core/runtime/vm/task_scheduler.py`、`vm_executor.py`）：
- **`TaskScheduler`**：多任务协作调度器（纯 stdlib，`custom` 的 `Waitable` 协议），单线程轮转、Waitable 挂起/恢复。
- **`Waitable` 为 `runtime_checkable Protocol`**，`LLMFuture` 结构符合（`is_done` 属性 + `result()`），可直接被调度器 await。
- **`_drive_loop_body` → `_drive_loop_gen`（生成器）**：VM 调度循环改为可挂起（handler yield Waitable 时挂起），`run()` 单任务驱动（阻塞等待，保持既有语义）。
- **`run_many(roots)`**：多根并发入口，用 `TaskScheduler` 驱动多个独立 LLM 根，各自挂起在 LLM future 上。
- **结果序契约**：`TaskScheduler.run()` 返回各任务完成值**按提交序**（与 `submit` 顺序一致），而非完成序——完成序不可预测，按提交序才能让调用方按索引取回对应任务结果。实现：`Task` 携带 `index`，`submit` 预分配结果槽位，`_step` 完成时按索引写入。

测试：`test_task_scheduler.py`（9）、`test_vm_run_many.py`（1），全量 pytest 1311 passed/4 skipped 零回归。

**下一步**：宿主级异步（PT-3.1）——`run_isolated`/`spawn_isolated` 返回可 await 句柄、多返回值；`ReceiveMode`（PT-3.2）语义；以及 `leaf.py` 的 suspendable resolve 接线。
