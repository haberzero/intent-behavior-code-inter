# 线程对象模型方向修正 — 完整决策记录（2026-08-04）

> **状态**：设计决策已定，**用户已授权实现（2026-08-04）**。本文档完整记录本轮讨论的所有细节与用户裁定，作为实施（统一泛型模型 + 线程对象模型 + thread_result 容器 + err 类型 + Optional 配套）的唯一决策依据。
> **授权记录**：2026-08-04 用户授权实现（含 Optional 配套的完整实现）；"授权实现。完善相关决策文档。"
> **前置设计**：PT-MT-1~8 主线设计（原 `THREADING_DESIGN.md` / `THREADING_DESIGN_DETAIL.md` 已删除归档，作为历史完成记录）。
> **性质**：本轮是**大范围方向修正**——推翻 PT-MT-1~8 已实现的 spawn/join/cancel 关键字语法，改为"thread 对象 + 句柄方法"模型。用户已授权（疏漏 3 裁决）。
> **最后更新**：2026-08-04

---

## 一、背景与动机

PT-MT-1~8 主线实现完成后，对 spawn/join/cancel/task 关键字设计进行深度质询，发现**设计缺陷**：

1. **领域混淆**：`await`（异步）与 `join`（线程等待）概念混用——`IbTask` 满足 `Waitable` 协议导致 `await t` 可等待线程句柄，混淆异步/线程两个领域。
2. **关键字冗余**：`spawn`/`join`/`cancel` 三个关键字中，`cancel` 应由句柄方法承担；`join` 与既有 `await` 功能重叠；`spawn` 与 `fn`（可调用）本质重合。
3. **类型精度不足**：`join` 返回类型保守为 `any`（`_statement_visitors.py:474`），违反用户"禁止 any 兜底"的裁定。
4. **系统碎片化**：内省双数据源、资源生命周期缺口、事件语义扭曲、`task` 命名冲突等（F-1~F-8）。

**用户裁定方向**：线程 = 一等对象（`thread` 类型 + 句柄方法），与异步彻底分离；返回值用泛型容器 `thread_result[T]`；err 类型统一接入 IBCI 异常体系。

---

## 二、用户裁定（完整逐条记录）

### 2.1 领域分离（最高原则）

> **async 与 thread 是必须彻底分离的两个领域。** 从概念、用户使用方式、机制设计、内核设计各层面全面区分，永远不让用户或内核内部逻辑产生混淆。

| 层面 | 异步 async | 线程 thread |
|------|-----------|-------------|
| 本质 | 非阻塞 I/O 等待 | 独立执行单元 |
| 解决 | 等待 I/O 不浪费 CPU | 多执行路径并行推进 |
| 资源 | 轻量（任务/协程） | 重量（线程 + 独立上下文） |
| 等待 | `await`（协作式让出） | `t.join()`（句柄方法） |
| 心智 | "等一个异步操作的值" | "管理一个执行单元的生命周期" |

**核心推论**：
- `IbTask` **不得**满足 `Waitable` 协议（杜绝 `await t` 等待线程）。
- `await` 只服务真正的异步操作（LLM Future / HostAwaitable）。
- 线程生命周期管理走句柄方法（`start`/`join`/`cancel`/`is_done` 等）。

### 2.2 关键字精简

| 关键字 | 处置 | 依据 |
|--------|------|------|
| `spawn` | **删除** | 与 `fn` 本质重合；线程创建改构造函数 |
| `join` | **删除** | 与既有 `await` 重叠；改句柄方法 `t.join()` |
| `cancel` | **删除** | 改句柄方法 `t.cancel()` |
| `task` | **删除/更名** | 改用 `thread` 类型名（语义清晰，与 async 区分） |
| `chan`/`signal`/`slot` | **保留（暂缓完善）** | 通信三域，下阶段处理（疏漏 2） |

> **疏漏 1 裁决（用户）**：无用关键字直接删除，不保留。

### 2.3 线程类型与返回类型标注

- **`thread[T]` 泛型标注是必须语法**（非"类型作参数传递进括号"）。
- 线程**允许且要求**携带返回值类型，用户书写时必须显式标注。
- 例：`thread[int] t = thread(callable=compute, args=["x"])`，`thread_result[int] r = t.join()`。
- 无返回值线程：`thread[void]`（join 返回 None 容器）。

> **决策理由**：`t.join()` 的返回类型必须在编译期与线程类型绑定（泛型正解）；与 `list[int]`/`Optional[int]`/`fn[...]` 语法统一；避免类型与值混淆。
>
> **实施修正（2026-08-04，任务 C2）**：用户裁定 `join()` 返回 `thread_result[T]` 容器（非 T）。构造参数名 `fn`（原 §2.3 例）与保留关键字碰撞，按"内部接口设计不违反关键字碰撞"原则改用 `callable`（`callable` 非关键字）。例更新为 `thread(callable=compute, args=["x"])`。

### 2.4 返回值容器 `thread_result[T]`

- 所有线程返回一种**专用容器**（IBCI 数据类型类）。
- **必须泛型**：`thread_result[T]`，保留类型参数精度，**禁止 any 兜底**。
- 用户可见、**可继承、可改写**。
- 异常/取消/失败**值化**进容器成员（不靠抛异常打断控制流）。
- 容器成员至少含：成功值、错误对象、状态（done/cancelled/failed）。

### 2.5 容器配套方法（Rust 对齐）

| 方法 | 语义 |
|------|------|
| `r.unwrap()` | 返回 `Optional[T]`——失败返回 Optional 空（**非裸 None**，避免类型撒谎；对齐 `OptionalAxiom` 先例） |
| `r.unwrap_or(default)` | 失败返回默认值（**最常用，推荐**） |
| `r.is_error()` / `r.is_success()` | 内省检查 |
| `r.value()` | 直接取值，**失败时抛错**（fail-fast，防静默空值） |
| `r.error()` | 取错误对象（不抛，内省友好） |
| `r.expect()` | **实施新增（任务 C2）**：直接返回 T，失败抛 IBCI 异常（Rust `unwrap`/`expect` 对齐）——"明确直接返回 value"的易用方法，弥补 `unwrap()` 返回 Optional 不直接取 T 的缺口 |

> **用户裁定**：同意 `unwrap_or(default)` + `is_error()` 模式（Rust `unwrap_or` 模式）。
> **疏漏 4 裁决（用户）**：用更明确的**内省方法**（获取完整状态）配合 result 模型，取代裸属性暴露。
> **实施细化（任务 C2）**：`value`/`error`/`status` 均实现为**方法**（`r.value()`/`r.error()`/`r.status()`），符合疏漏 4"内省方法取代裸属性"。

### 2.6 err 类型统一设计

- err 类型**统一接入既有 IBCI `Exception` 类体系**（`Exception` → `LLMError` → `LLM*Error`，`specs.py:45-57`）。
- `TaskCancelled`/`TaskFailed` 映射为 **IBCI Exception 子类**（当前是 Python 异常，`coordinator.py:37`）。
- **用户可见、可继承、完整开放**（`class MyError(Exception)` 已支持）。
- `t.cancel()` **返回 err**（操作状态：成功取消 / 无效 / 已结束）。
- 区分两个 err 语义：**cancel 操作状态** vs **线程结果内的错误**。

### 2.7 挂起/恢复

> **挂起机制设计直接取消，未来也不做。**

- **无损挂起/恢复**（保存现场 + resume）本质是**生成器/协程帧保存**——与 async 层机制本质相同，与"线程/异步分离"原则冲突，且高难度（VM 帧序列化）。
- 不做时间片调度 / 任务管理块 / 内存寄存器模型 / 中断机制（误解排除：Python 线程由 OS 调度，协作式非抢占）。
- 记录为未来独立协程设计的前置，不在线程层单独做。

### 2.8 统一泛型模型

> **必须立即启动**，作为接下来任务的一部分，与线程工作直接关联。

- 范围：**内置类型泛型化的正式统一机制**（list/dict/tuple/Optional/fn/thread 统一为"内置泛型类型声明"）。
- **不包含**：用户级泛型类（PT-4.4，VISION）、Hindley-Milner 约束求解（已明确排除）。
- `thread[T]` 作为该模型的第一个正式消费者。

### 2.9 Optional 配套设计

> 用户裁定：**如果有能力设计 Optional 相关配套，则直接完整实现。**

**现状查证（2026-08-04）**：
- ✅ 编译期：`Optional[T]` 特化完整（spec 层，`resolve_member` 返回 int，`test_type_annotations.py` 已验证）。
- ❌ 运行时：**无 `IbOptional` 对象**。`Optional[int] x = None` 是裸 None，`x.is_some()` **运行时失败**（"Object of type 'None' has no method '__call__'"）。
- 方法表面在 `OptionalAxiom` 声明（unwrap/or_else/is_some），但**运行时实现不存在**。

**结论**：Optional 配套设计 = 补齐运行时 `IbOptional` 对象 + `is_some`/`unwrap`/`or_else` 运行时实现。**有能力做**，复用既有 spec/axiom/factory 基础设施。

---

## 三、疏漏裁决（用户逐条）

| # | 疏漏 | 用户裁决 |
|---|------|---------|
| 1 | spawn/join/cancel 关键字的去留 | **无用关键字直接删除，不保留** |
| 2 | chan/signal/slot 通信三域去留 | **通信领域设计完善与统一化检查是下阶段任务，暂缓** |
| 3 | 既有已实现代码（PT-MT-1~8 spawn/join/cancel + chan/signal/slot）处置范围 | **大范围重构直接开始**；允许推翻已有代码，允许删除确认无用或待改造的代码 |
| 4 | `is_done` 裸属性 + 线程对象/容器持久化 | **用明确内省方法获取完整状态**（配合 result 模型），取代裸属性；线程对象和容器**是瞬态**，save_state 时用户自保；**检测到未完成线程时 save_state 直接抛异常 fail** |
| 6 | 相关测试项去留 | **废除相关测试项**，新机制测试单独制作 |

---

## 四、系统碎片化记录（F-1~F-8，推进中自然修复）

| # | 碎片化 | 现状 |
|---|--------|------|
| F-1 | 内省双数据源 | `observability/snapshot.py:35-46` 只从 TaskScheduler 收集；spawn 线程在 RuntimeCoordinator，快照看不到 |
| F-2 | 任务资源生命周期缺口 | `coordinator._tasks` 只增不减；`cleanup` 无调用点 → 内存泄漏 |
| F-3 | `task_done` 事件语义扭曲 | join 时刻 emit（非任务完成时刻），payload 无结果值 |
| F-4 | 无资源参数监控 | 无线程上限/超时/取消后回收/异常上报渠道 |
| F-5 | 协调器 kind 枚举未实现 | 设计承诺 `TaskHandle.kind` 区分隔离/轻量任务——未实现 |
| F-6 | `task` 命名冲突 | 语言级 task vs TaskScheduler.Task vs SpawnedTask |
| F-7 | 执行域与通信域无一等衔接 | 设计说"经 Channel 协调"但无语言级语法 |
| F-8 | 双内省模块 | `idbg` vs `iruntime` 职责未明确划分 |

> **用户裁定**：推进中自然修复；若无法以设计/架构原则确认方案，先汇报。

---

## 五、违规点记录（VP-1~VP-6，后续触碰即修）

| # | 违规点 | 位置 | 性质 |
|---|--------|------|------|
| VP-1 | join 阻塞式（非 yield 挂起），文档/实现脱节 | `comm.py:185-206` | 半修复 |
| VP-2 | `_task_handle` 死引用 | `coordinator.py:272` | tricky 残留 |
| VP-3 | cancel 覆盖用户函数路径缺失 | `coordinator.py:114-126` | 半修复 |
| VP-4 | `except: pass` 兜底 | `comm.py:53-67` | fail-fast 违背 |
| VP-5 | TaskAxiom 无方法表面 | `comm.py:22-34` | 类型系统缺口 |
| VP-6 | 任务完成后 cancel 覆盖已有结果 | `coordinator.py:123-126` | 真实 bug |

---

## 六、后续任务清单（已授权实现，2026-08-04）

> **实施顺序**：依赖驱动（泛型/容器地基在前，对象模型/清理在后）。每步全量 pytest 零回归 + 本地 commit。

| 顺序 | 任务 | 内容 | 验收标准 |
|------|------|------|---------|
| 1 | **A. Optional 配套完整实现** | 运行时 `IbOptional` 对象 + `is_some`/`unwrap`/`or_else` 运行时实现；与 `thread_result[T]` 共用设计模式 | `Optional[int] x = None` 后 `x.is_some()`/`x.unwrap()` 可运行；全量 pytest 零回归 |
| 2 | **B. 统一泛型模型** | 内置泛型类型声明正式机制（list/dict/tuple/Optional/fn/thread 统一）；`thread[T]` 首个消费者 | 泛型 spec 经统一入口创建/解析/序列化/还原；不触碰用户级泛型类/约束求解 |
| 3 | **C. 线程对象模型** | `thread[T]` 类型 + 构造函数 + 句柄方法（start/join/cancel/is_done）+ 生命周期状态机 | `thread[int] t = thread(callable=compute, args=["x"])`；`t.join()` 返回 `thread_result[int]` 容器（用户裁定）；cancel 返回 err |
| 4 | **D. err 类型统一** | TaskCancelled/TaskFailed 映射 IBCI Exception 子类；`cancel()` 返回 err；err 用户可见可继承 | `class MyErr(Exception)` 可继承；取消后可从 err 取错误对象 |
| 5 | **E. 线程相关清理** | VP-1~VP-6 + F-1~F-8（join 阻塞、_task_handle 死引用、cancel 覆盖、except:pass、方法表面、内省统一、事件语义、资源生命周期） | 触碰到的问题全部修复；内省单数据源；task_done 事件语义正确 |
| 6 | **F. 关键字精简 + 测试** | 删除 spawn/join/cancel/task 关键字（AST/parser/语义/dispatch/序列化全链）；废除旧测试；新测试单独制作 | 旧 spawn/join/cancel 语法编译失败；新 thread 对象模型测试覆盖；全量 pytest 零回归 |

> **分工说明**：任务 A（Optional）与 B（泛型模型）为地基，先于 C（线程对象）；D（err）与 C 紧密关联；E（清理）随触碰随修；F（关键字删除）最后统一执行（避免实现期语法漂移）。

---

## 七、实施约束（用户裁定汇总）

1. **大范围重构直接开始**，允许推翻已有代码（疏漏 3）。
2. **无用关键字直接删除**（疏漏 1）。
3. **通信领域（chan/signal/slot）暂缓**，下阶段处理（疏漏 2）。
4. **线程对象与容器是瞬态**；save_state 时用户自保；**检测到未完成线程时 save_state 抛异常 fail**（疏漏 4）。
5. **废除旧测试**，新机制测试单独制作（疏漏 6）。
6. **挂起机制不做**（未来也不做）。
7. **禁止 any 兜底**：容器、unwrap、Optional 全部要求类型精度。
8. **err 类型统一**：接入既有 Exception 体系，用户可见可继承。
9. **await 与线程彻底解耦**：IbTask 不得满足 Waitable。

---

## 八、实施细节（已授权自主决策，按 WORKLOG 记录）

- **线程创建语法**：`thread t = thread(callable=..., args=...)`（构造函数）——签名按 IBCI 既有对象构造模式自主细化并记录。参数名 `callable`（原 `fn` 与关键字碰撞，实施修正）。
- **`thread_result[T]` 容器成员**：按本记录 2.5 细化（value/error/status/is_error/unwrap/unwrap_or）。
- **既有 `RuntimeCoordinator`/`SpawnedTask`**：保留内核机制，语言表面改造为 thread 对象 + 方法（用户已授权删除/改造，自主决定并记录）。
- **大范围重构分支政策**：本方向修正为**已确认边界**的破坏性改造（边界 = spawn/join/cancel/task 相关 + 线程对象模型 + Optional/err/泛型），用户明确授权在当前分支直接开始（疏漏 3），**不**走独立隔离分支。

---

> 本记录为线程对象模型方向修正的**唯一决策依据**。实施开始时按此执行；任何与本文档冲突的既有实现，以本文档为准（用户已授权推翻）。
