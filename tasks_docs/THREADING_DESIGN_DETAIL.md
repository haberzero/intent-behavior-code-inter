# IBCI 运行时多线程 + 统一通信机制 + 内省/控制 — 详细设计文档（PT-MT-1）

> **状态**：PT-MT-1 详细设计（待用户审阅）。
> **上一级决策**：`tasks_docs/THREADING_DESIGN.md`（用户裁定 + 设计空间分析）。
> **最后更新**：2026-08-03
>
> 本文档是下一主线（IBCI 运行时多线程 + 统一通信机制 Channel/Signal/Slot + 内省 + 控制 + 多 VM 实例 + 编译器改造）的**落地级详细设计**，覆盖：架构总览、AST/编译器变更、通信内核、内省层、控制层、流式/并行、多 VM 实例、用户代码多线程、并发正确性、测试策略、实施顺序。设计落地前先经用户审阅；落地后按 `docs/` 治理纪律择机写入技术手册。

---

## 〇、设计前置约束（不可违反）

1. **工作模式定论**（`NEXT_STEPS.md`）：
   - 禁止 compat shim / 胶水 / tricky / 过程式硬编码分发（同一决策只通过协议驱动）。
   - 禁止双通道 / 双写真相（同一事实只在单点维护）。
   - 质量优先于速度；原则优先于行为维持；可推翻 IBCI 自身设计缺陷。
2. **架构边界**（`docs/architecture/01_principles.md` §四）：依赖方向禁止穿透。
3. **AST/侧表边界**（`docs/architecture/02_metadata_ast.md`）：静态分析结果写 AST 节点；编译期临时数据写侧表；类型级属性写 `IbSpec`。
4. **并发正确性基线**（Stage 1 三项核验）：executor 共享状态去共享化、`_pending_futures` 清理、主线程单写槽 `_current_call_info` 只主线程写、意图 fork 隔离完整。
5. **明确排除**：跨进程/CPU 并行；跨引擎通信（隔离运行保持文件/序列化机制）；media Phase 4 多模态；完整通用异步（async 函数/生成器，本主线不含）。
6. **GIL 现实**：IBCI 运行于 Python，受 GIL 限制。多线程**只为服务 LLM IO 调用**（IO 密集，等待期间释放 GIL）与**用户可见的实时 UI/输出刷新**；不追求 CPU 并行，不优化为通用并发框架。

---

## 一、架构总览

### 1.1 目标架构

```
                    ┌─────────────────────────────────────────────────────┐
                    │              Runtime Kernel (统一通信内核)           │
                    │  ┌──────────┐  ┌──────────┐  ┌──────────┐          │
                    │  │ Channel  │  │ Signal   │  │ Slot     │          │
                    │  │(数据流)   │  │(控制流)   │  │(共享状态) │          │
                    │  └────┬─────┘  └────┬─────┘  └────┬─────┘          │
                    │       └──────────────┼────────────┘                 │
                    │        ┌─────────────┴─────────────┐                │
                    │        │ 线程安全 bounded buffer     │                │
                    │        │ 可寻址注册表(name→对象)      │                │
                    │        │ 内省/控制钩子                │                │
                    │        └───────────────────────────┘                │
                    └─────────────────────────────────────────────────────┘
         ▲                       ▲                       ▲
         │ 语言层一等公民          │ 内省/控制               │ 运行时协调
         │ (chan/signal/slot)    │ (runtime.snapshot/     │ (多 VM 实例)
         │                        │  subscribe/configure)   │
         │                        │                        │
┌────────┴────────┐   ┌──────────┴──────────┐   ┌─────────┴─────────┐
│   VMExecutor    │   │ RuntimeCoordinator  │   │ 轻量 VM 实例池     │
│ (CPS 帧栈调度)   │   │ (快照/订阅/配置)     │   │ (spawn/join/cancel)│
└────────┬────────┘   └────────────────────┘   └───────────────────┘
         │
         │  TaskScheduler（Stage 2 已落地） / run_many
         │  Worker 线程池（LLM IO 边界）→ Channel → 渲染线程
         ▼
    LLMExecutor / LLMFuture / Waitable / HostAwaitable
```

### 1.2 分层职责

| 层 | 归属 | 职责 |
|----|------|------|
| **通信内核** | `core/runtime/shared/comm/`（叶子模块） | Channel/Signal/Slot 三抽象的线程安全实现 + 可寻址注册表 |
| **语言层暴露** | 新模块 `core/runtime/modules/runtime_comm.py`（或并入 kernel-native 模块 `runtime`） | 把三抽象以 `IbObject` 形式暴露给 IBCI 代码 |
| **内省层** | `core/runtime/observability/` | `runtime.snapshot()` / `runtime.subscribe()` |
| **控制层** | 同内省层或独立 | `runtime.configure(...)` 统一启停 |
| **VM 集成** | `core/runtime/vm/` | 新 AST 节点 handler、spawn/join/cancel 任务句柄 |
| **多 VM 实例** | `core/engine.py` + `core/runtime/rt_scheduler.py` | 每并发路径一个轻量 VM 实例，协调器管理生命周期 |
| **编译器** | `core/compiler/` | 新 AST 节点 + parser + 4 阶段语义 + dispatch + 序列化 |

### 1.3 关键设计决策（承上启下）

| 决策点 | 本设计结论 | 依据 |
|--------|-----------|------|
| 三抽象关系 | Channel（数据流）+ Signal（控制流）+ Slot（共享状态）三协调抽象，**共享**线程安全内核 | 用户裁定 §三（三个正交通信域，不能用一个超抽象覆盖） |
| 语言层暴露 | 一等公民：`chan`/`signal`/`slot` 关键字 + 类型 | 用户裁定 §二（语言层全部暴露为一等公民） |
| 内省形态 | 快照式 + 事件流**两者都提供** | 用户裁定 §二 |
| 控制接口 | 统一"启停"设计，非"关闭接口" | 用户裁定 §二 |
| 多 VM | 每并发路径一个轻量 VM（完全隔离 + 全局只读数据） | 用户裁定 §二 |
| 并发任务持久化 | **运行时瞬态**，不进入 save_state/load_state | 用户裁定 §八 |
| 流式 vs 并行 | 两个独立概念，都默认开启 | 用户裁定 §二 |

---

## 二、编译器改造（PT-MT-2 核心）

### 2.1 新 AST 节点（`core/kernel/ast.py`）

新增以下节点（均在既有 `IbStmt` / `IbExpr` 体系内，遵循 `@dataclass(kw_only=True, eq=False)` 约定）：

```python
# --- 语句级：并发任务 ---

@dataclass(kw_only=True, eq=False)
class IbSpawnStmt(IbStmt):
    """``task t = spawn fn(...)`` / ``task t = spawn(fn, args)`` / fire-and-forget ``spawn fn(...)``。

    注意：``task`` 是保留关键字（类型名），spawn 的目标变量名**不能**叫 ``task``
    （见 §2.2）。变量命名用 ``t``/``handle`` 等普通标识符。
    """
    target: Optional[IbExpr]          # 赋值目标（IbName / IbTypeAnnotatedExpr），None 表示 fire-and-forget
    func: IbExpr                      # 被 spawn 的可调用表达式（函数名 / fn 变量 / lambda）
    args: List[IbExpr] = field(default_factory=list)    # 位置实参
    keywords: List['IbKeyword'] = field(default_factory=list)  # 具名实参

@dataclass(kw_only=True, eq=False)
class IbJoinStmt(IbStmt):
    """``join t`` 或 ``task t = join t2``（join 出现在声明右侧，表达式位置）。"""
    task: IbExpr                      # 任务句柄表达式
    target: Optional[IbExpr] = None   # 结果赋值目标

@dataclass(kw_only=True, eq=False)
class IbCancelStmt(IbStmt):
    """``cancel t``：请求取消任务（协作式取消）。"""
    task: IbExpr
```

> **IbTaskRef 已移除（self-grill/审查修正）**：任务句柄是 spawn **运行时返回**的 `IbObject` 值（`IbTask`），不是 AST 表达式节点；`task t = spawn ...` 的 `spawn ...` 在表达式位置经 **SPAWN 前缀规则**解析为 `IbSpawnStmt`（带 target 的语句），句柄值由运行时产生，无需独立的 `IbTaskRef` AST 节点。§2.1 不再定义该节点，与 §2.3/§2.6 的 6 节点收敛一致。


# --- 表达式级：通信原语 ---

@dataclass(kw_only=True, eq=False)
class IbChannelExpr(IbExpr):
    """``chan T(...)`` 或 ``chan(T, ...)``：创建 Channel。"""
    type_name: Optional[str] = None   # Channel 元素类型名
    mode: str = "message"             # stream | message | pubsub
    buffer: int = 0                   # 有界缓冲大小（0 = 无界）
    name: Optional[str] = None        # 具名 Channel（可选，用于跨作用域寻址）

@dataclass(kw_only=True, eq=False)
class IbSignalExpr(IbExpr):
    """``signal(...)``：创建/发送 Signal（控制流，抢占式）。"""
    kind: str = "cancel"              # cancel | pause | resume | config_change
    target: Optional[IbExpr] = None   # 定向目标（None = 广播）
    payload: Optional[IbExpr] = None  # 附加数据

@dataclass(kw_only=True, eq=False)
class IbSlotExpr(IbExpr):
    """``slot T(name)`` 或 ``slot(name, value)``：创建/访问 Slot。"""
    name: str
    type_name: Optional[str] = None
    value: Optional[IbExpr] = None    # 初始值


# --- 语句级：Channel/Signal/Slot 操作 ---

@dataclass(kw_only=True, eq=False)
class IbChanSend(IbStmt):
    """``chan.send(value)``：向 Channel 发送数据。"""
    chan: IbExpr
    value: IbExpr
    blocking: bool = False            # send_blocking 语义

@dataclass(kw_only=True, eq=False)
class IbChanRecv(IbStmt):
    """``x = chan.recv()``：从 Channel 接收数据。"""
    chan: IbExpr
    target: Optional[IbExpr] = None   # 结果赋值目标
    blocking: bool = True             # recv 阻塞语义；recv_nonblocking = False

@dataclass(kw_only=True, eq=False)
class IbSlotRead(IbExpr):
    """``slot.value``：读取 Slot 当前值。"""
    slot: IbExpr

@dataclass(kw_only=True, eq=False)
class IbSlotWrite(IbStmt):
    """``slot.value = x`` 或 ``slot.update(x)``：原子写/读改写 Slot。"""
    slot: IbExpr
    value: IbExpr
```

**设计说明**：
- `spawn`/`join`/`cancel` 为**语句**（有副作用、改变控制流），不伪装成纯表达式。
- `chan`/`signal`/`slot` 构造为**表达式**（可赋值、可传参）。
- Channel/Signal/Slot 的**运行时对象**为 `IbChannel`/`IbSignal`/`IbSlot`（`IbObject` 子类，见 §三），语言层操作（send/recv）经**对象方法协议**（`IbChannel.send(...)` 经方法分发）而非新 AST 节点，保持"协议驱动"而非"过程式硬编码"。上述 `IbChanSend`/`IbChanRecv`/`IbSlotRead`/`IbSlotWrite` 为**对象方法的 AST 形态**（对应 `chan.send(...)` 方法调用在 AST 中表现为 `IbCall` 走方法分发）——实际落地时优先复用 `IbCall` + 方法分发，**不新增** send/recv 专用节点，避免与既有 `IbCall` 双通道。**此决策在 §2.3 确认。**

### 2.2 Lexer/Token 变更（`core/compiler/common/tokens.py` + `core/compiler/lexer/core_scanner.py`）

新增关键字：

| 关键字 | TokenType | 位置角色 |
|--------|-----------|----------|
| `spawn` | `SPAWN` | 语句起始 + **表达式前缀**（`task t = spawn fn(...)`，见 §2.3） |
| `join` | `JOIN` | 语句起始 + **表达式前缀**（`task t = join t2`，见 §2.3） |
| `cancel` | `CANCEL` | 语句起始 |
| `chan` | `CHAN` | 表达式起始（构造函数）+ **类型注解位置** |
| `signal` | `SIGNAL` | 表达式起始 + **类型注解位置** |
| `slot` | `SLOT` | 表达式起始 + **类型注解位置** |
| `task` | `TASK` | **类型注解位置**（任务句柄类型；**保留字，禁止作变量名**） |

`core_scanner.py` 的 `KEYWORDS` dict（参考 `'await': TokenType.AWAIT`，`core_scanner.py:39`）添加对应条目。

**类型注解集成（关键，self-grill 修正）**：`core/compiler/parser/components/type_def.py` 的 `parse_type_annotation()` 目前仅接受 `IDENTIFIER`/`AUTO`/`FN`/`NONE` 作为类型基元（`type_def.py:18-53`）。若 `task`/`chan`/`signal`/`slot` 是 lexer 关键字，则 `task t = spawn...`、`chan[str] c = ...` 会在类型解析处失败。**必须**在 `parse_type_annotation()` 中新增对 `TASK`/`CHAN`/`SIGNAL`/`SLOT` 关键字的匹配分支（产出 `IbName(id="task")` / `IbName(id="chan")` 等），并保持泛型 `chan[T]`/`slot[T]` 走既有 `LBRACKET` 泛型路径（`type_def.py:56-70`）。此模式遵循既有 `fn`/`auto`/`None` 关键字作类型的前例，不引入新机制。

**保留字限制（关键，审查修正）**：`task` 作为保留关键字后**不能再作变量名**。`task t = spawn ...` 中 `task` 是类型注解（走 TASK 类型分支），变量名 `t` 是普通标识符。禁止 `task = ...`（task 作变量名）的写法——词法层 `task` 固定产出 `TASK` token 而非 `IDENTIFIER`。此限制与 `fn`/`lambda`/`auto` 等既有保留字一致。

### 2.3 Parser 变更（`core/compiler/parser/components/`）

- **StatementComponent**（`statement.py`）新增：
  - `spawn_statement()`：`spawn <expr>`（fire-and-forget）或 `spawn(<expr>, args)`
  - `join_statement()`：`join <expr>`
  - `cancel_statement()`：`cancel <expr>`
  - 在 `_parse_statement_core()` 的 **if 分派链**（非 Python `match` 语句，`statement.py:36-101`）注册（参考 `TokenType.RETURN` 等既有分支）
- **ExpressionComponent**（`expression.py`）新增**前缀规则**（`register(TokenType.X, prefix_fn, None, precedence)`，参考 `:74` AWAIT 模式）：
  - `spawn_expr()`：`spawn fn(...)` —— **表达式位置**（`task t = spawn ...`、`join(t)` 场景），产出 `IbSpawnStmt(target=...或 None, ...)` 经语义阶段判别；`precedence=UNARY`
  - `join_expr()`：`join t` —— **表达式位置**（`task t = join t2`、`x = join t`），产出 `IbJoinStmt(target=...或 None, ...)`；`precedence=UNARY`
  - `chan_expr()` / `signal_expr()` / `slot_expr()` 前缀规则
  - `signal_expr()` 以 `signal(...)` 函数形态解析（`kind` 从首参提取）

  > **spawn/join 表达式前缀（审查修正，落地级必选）**：`task t = spawn compute(...)` 中 `spawn` 出现在声明 `=` 右侧（表达式位置）。`task t = ...` 走 `parse_declaration()`→`variable_declaration()`→`self.expression.parse_expression()`，若无 SPAWN/JOIN 前缀规则会触发 "Expect expression. Got SPAWN"。**必须**为 SPAWN/JOIN 注册表达式前缀规则（同 AWAIT 模式）。`spawn_expr`/`join_expr` 产出带 `target` 的语句节点，由语义阶段/VM 判别"是否带赋值目标"（带 → 语句；无 → 表达式值返回句柄）。

- **Channel 构造语法（D2 机制确认）**：`chan` 前缀规则解析 `chan(T, mode=..., buffer=...)` 函数形态为主（`T` 为元素类型名，首参经 `parse_type_annotation` 解析为类型引用）；`chan T(...)` 声明式形态为可选糖——`chan_expr` 先看下一 token：`(` → 函数形态；`IDENTIFIER`/泛型类型名 → 解析类型后接 `(...)`。两种形态产出同一 `IbChannelExpr`，无双通道。
  > **首参类型解析（审查补充）**：`chan(str, "stream")` 中 `str` 在表达式位置——由于 `str` 是注册类型名（非关键字），`chan_expr` 对**首参显式调用 `parse_type_annotation()`**（接受 IDENTIFIER 类型名如 `str`/`int`），而非走通用表达式解析（那会把 `str` 当变量引用）。`mode`/`buffer`/`name` 等其余参数走通用表达式解析。此机制在落地时须在 `chan_expr` 内显式区分首参与其余参数。
- **Channel 方法分发**：`chan.send(x)` / `chan.recv()` / `chan.recv_nonblocking()` / `chan.close()` 经既有 `IbCall` + 方法分发，不新增节点（见 §2.1 设计说明）。

**关键决策（自我裁定）**：`chan.send`/`chan.recv` 复用 `IbCall` 方法分发，**不新增** `IbChanSend`/`IbChanRecv`/`IbSlotRead`/`IbSlotWrite` 专用 AST 节点。理由：
1. Channel 是运行时对象，send/recv 是对象行为，天然走方法分发（`IbAttribute` + `IbCall`），与既有 `str.replace(...)`、`list.append(...)` 同构。
2. 避免为语言特性引入"过程式硬编码分发"（工作模式定论第 4 条）。
3. `IbChannel` 类在注册表注册方法成员（vtable），语义阶段对 `chan.send(...)` 做类型检查即可。
> 此决策意味着 §2.1 中的 `IbChanSend`/`IbChanRecv`/`IbSlotRead`/`IbSlotWrite` **不落地**；落地的是 `spawn`/`join`/`cancel` 语句节点 + `chan`/`signal`/`slot` 表达式节点。序列化/语义/VM 均按此收敛，无双通道。

### 2.4 语义阶段（4-Phase）变更

| Phase | 变更 |
|-------|------|
| **SymbolPhase** | 新节点无新符号收集需求（`spawn` 的目标是既有可调用符号；`chan/signal/slot` 构造无新符号）。`task` 类型关键字注册为类型名。 |
| **TypePhase** | `IbSpawnStmt` 返回 `task` 类型；`IbJoinStmt` 返回被 join 函数的返回类型；`IbChannelExpr` 元素类型 = `type_name` 解析；`IbSignalExpr`/`IbSlotExpr` 类型检查。新增 **`task` / `chan` / `signal` / `slot` 类型**到 `IbSpec` 体系（见 §2.5）。 |
| **BindingPhase** | `spawn` 的实参绑定与函数调用同构（复用 `resolve_call` 逻辑）；`join` 结果类型 = 函数返回类型；行为依赖分析（`llm_deps`/`dispatch_eligible`）**不覆盖** spawn 内部——spawn 的函数体是独立执行单元，其内部行为依赖在 spawn 语义下按"新根"处理（运行时经 `run_many` 风格独立驱动）。 |
| **IntegrityPhase** | `chan`/`signal`/`slot` 类型存在性校验；`spawn` 目标必须可调用；`join`/`cancel` 目标必须 `task` 类型。 |

### 2.5 类型系统扩展（`core/kernel/spec/` + `IbSpec`）

新增内置类型（注册到 primitive/prelude）：

| 类型 | 本质 | 说明 |
|------|------|------|
| `task` | `TypeKind.TASK` | 任务句柄；`join`/`cancel` 的载体 |
| `chan[T]` | `TypeKind.CHANNEL`（泛型） | 数据流通道；`T` 为元素类型 |
| `signal` | `TypeKind.SIGNAL` | 控制流信号 |
| `slot[T]` | `TypeKind.SLOT`（泛型） | 共享状态槽 |

- `task`/`chan`/`signal`/`slot` 均为运行时 `IbObject` 类，注册到 Registry（`_prepare_interpreter` 阶段），定义见 §三。
- `chan[T]`/`slot[T]` 的泛型参数在 TypePhase 解析为 `TypeRef`，运行时经注册表类型化 `IbObject` 承载。
- **序列化**：`chan`/`signal`/`slot` 对象在 `save_state` 中作为**运行时状态**序列化（若保存时存活）；`task`（并发任务）**不进入持久化状态**（用户裁定 §八：并发任务为运行时瞬态）。

### 2.6 Dispatch / VM Handler（`core/runtime/vm/handlers/`）

| 节点 | Handler 归属 | 行为 |
|------|-------------|------|
| `IbSpawnStmt` | 新 `vm_handle_IbSpawnStmt` | 解析 func + args → 构造轻量 VM 任务（见 §7）→ 注册到协调器 → 返回 task 句柄 |
| `IbJoinStmt` | 新 `vm_handle_IbJoinStmt` | 对 task 句柄 yield 等待（复用 `Waitable` 协议）→ 取回结果 |
| `IbCancelStmt` | 新 `vm_handle_IbCancelStmt` | 请求协作式取消（经 Signal 机制） |
| `IbChannelExpr` | 新 `vm_handle_IbChannelExpr` | 构造 `IbChannel` 对象 |
| `IbSignalExpr` | 新 `vm_handle_IbSignalExpr` | 构造 `IbSignal` 对象 + 投递 |
| `IbSlotExpr` | 新 `vm_handle_IbSlotExpr` | 构造 `IbSlot` 对象 |

**Dispatch 注册**：`core/runtime/vm/handlers/dispatch.py` 的 `build_dispatch_table()` 添加 6 个新节点（参考 `"IbAwaitExpr": vm_handle_IbAwaitExpr`）。

### 2.7 序列化（`core/compiler/serialization/serializer.py`）

- 新节点经 `vars(node)` 通用序列化自动覆盖（`_collect_node` 对 `vars()` 迭代，新字段自动持久化）。
- `chan`/`signal`/`slot` 构造表达式的 `type_name`/`mode`/`buffer`/`name` 为纯标量字段，直接序列化。
- **并发任务不序列化**：`task` 句柄不写入 artifact；`IbSpawnStmt` 作为 AST 节点序列化（描述"程序要 spawn 什么"），但运行时产生的 task 实例是瞬态。

---

## 三、统一通信内核（PT-MT-3 核心）

### 3.1 模块布局

```
core/runtime/shared/comm/
├── __init__.py
├── channel.py       # IbChannel（数据流）
├── signal.py        # IbSignal（控制流）
├── slot.py          # IbSlot（共享状态）
├── registry.py      # 可寻址注册表（name → 对象）
└── buffer.py        # 线程安全 bounded buffer（共享内核）
```

> 位于 `core/runtime/shared/` 下：与 `waitable.py`/`signals.py`/`llm_result.py` 同级，为运行时各子包（vm/host/interpreter/objects）共享的叶子模块，避免循环导入。不依赖 `objects`（`IbObject` 在 object 层），`channel.py` 等定义**纯通信原语**（线程安全容器），语言层 `IbChannel`（`IbObject` 子类）在 `core/runtime/objects/` 定义并引用共享原语。

### 3.2 线程安全 bounded buffer（`buffer.py`）

```python
class CommBuffer:
    """线程安全有界缓冲（统一内核）。

    - 多生产者/多消费者安全（threading.Condition 保护）。
    - 有界（maxsize）：满时 send 阻塞或返回 False（nonblocking）。
    - 空时 recv 阻塞或返回 (False, None)（nonblocking）。
    - close() 后：send 抛 ClosedError；recv 排空剩余后抛 ClosedError。
    """
    def __init__(self, maxsize: int = 0): ...          # 0 = 无界
    def send(self, item) -> None: ...
    def send_nowait(self, item) -> bool: ...           # False = 满/已关闭
    def recv(self): ...
    def recv_nowait(self): ...
    def close(self) -> None: ...
    @property
    def closed(self) -> bool: ...
    def qsize(self) -> int: ...
```

**正确性要点**：
- `Condition` 单一锁保护 `_queue` + `_closed` + `_size`，读改写原子。
- `close()` 置 `_closed=True` 并 `notify_all()`（唤醒所有阻塞 recv）。
- send 后 `notify()`（至少唤醒一个等待 recv）；recv 后 `notify()`（唤醒等待 send 的）。
- **fail-fast**：已关闭后 send/recv 抛明确异常，不静默返回。

### 3.3 Channel（数据流，`channel.py`）

```python
class ChannelCore:
    """Channel 数据流核心（纯通信原语，线程安全）。

    mode:
      - stream:  有序 FIFO 流（与 buffer 一致），生产-消费
      - message: 离散消息队列（与 buffer 一致），点对点排队
      - pubsub:  扇出（同一消息投递所有订阅者）；内部每个订阅者一个队列
    """
    def __init__(self, mode: str = "message", buffer: int = 0, name: Optional[str] = None): ...
    # 生产者
    def send(self, item): ...
    def send_nowait(self, item) -> bool: ...
    # 消费者
    def recv(self): ...
    def recv_nowait(self): ...
    # pubsub
    def subscribe(self) -> "ChannelCore": ...   # 返回订阅者专属队列视图（fan-out）
    # 生命周期
    def close(self) -> None: ...
    @property
    def closed(self) -> bool: ...
    def snapshot(self) -> dict: ...             # 内省：qsize/closed/订阅者数
```

**语言层 `IbChannel`**（`core/runtime/objects/`）：

```python
class IbChannel(IbObject):
    """IBCI 语言层的 Channel 值对象。"""
    def __init__(self, ib_class, core: ChannelCore): ...
    def send(self, value): ...          # 经对象方法分发调用
    def recv(self): ...
    def recv_nonblocking(self): ...
    def close(self): ...
    def snapshot(self): ...
```

### 3.4 Signal（控制流，`signal.py`）

```python
class SignalCore:
    """Signal 控制流核心（抢占式、一次性）。

    - target: None = 广播；具体 = 定向（寻址到指定 handle/Channel/Slot）
    - kind:   cancel / pause / resume / config_change
    - 语义：一次性投递，抢占式（投递即生效，由接收方决定如何响应）
    """
    def __init__(self, kind: str, target=None, payload=None): ...
    @property
    def kind(self): ...
    @property
    def target(self): ...
    @property
    def payload(self): ...
    def to_dict(self) -> dict: ...
```

**语言层 `IbSignal`**：包装 `SignalCore`；投递行为经 `Registry`/`CommRegistry` 分发到目标（任务句柄 / VM 实例 / Channel）。

### 3.5 Slot（共享状态，`slot.py`）

```python
class SlotCore:
    """Slot 共享状态核心（具名、可反复读写、原子读改写）。

    - name: 具名标识
    - value: 当前值（初值可设）
    - update(fn): 原子读改写（读当前值 → fn 计算 → 写回，整段持锁）
    """
    def __init__(self, name: str, initial_value=None): ...
    @property
    def name(self): ...
    def get(self): ...
    def set(self, value): ...
    def update(self, fn) -> None: ...   # 原子读改写
    def snapshot(self) -> dict: ...
```

**语言层 `IbSlot`**：包装 `SlotCore`；`slot.value` 属性经 `__getattr__`/属性协议映射 `get`/`set`（或经方法 `slot.get()`/`slot.set()`）。

### 3.6 可寻址注册表（`registry.py`）

```python
class CommRegistry:
    """通信对象可寻址注册表（供广播枚举 + 定向查找 + 内省）。

    - name → 对象（Channel/Slot 可具名注册）
    - handle → 对象（spawn 任务句柄）
    - 广播：遍历某类所有对象（signal 广播）
    - 线程安全（锁保护）
    """
    def __init__(self): ...
    def register(self, name: str, obj) -> None: ...
    def unregister(self, name: str) -> None: ...
    def lookup(self, name: str): ...
    def all(self, kind=None) -> list: ...
    def snapshot(self) -> dict: ...       # 内省：全部注册对象
```

### 3.7 与既有机制的关系（单点真理，不双通道）

| 既有机制 | 关系 |
|---------|------|
| `TaskScheduler`/`Waitable`（Stage 2） | Channel 的 `recv` 语义可包装为 `Waitable`（未就绪则挂起），供 VM 调度器协作等待；**不替换** TaskScheduler，是它的数据源。 |
| `LLMFuture` | Channel 可承载 Worker 的增量结果（流式），但**不替换** LLMFuture（那是 LLM 调用句柄）；流式是"另一个通道"，见 §6。 |
| `output_callback` / `call_info` | 本主线不删除（对外契约）；但为流式/内省提供**新的一等通道**。`output_callback` 仍是 print 输出的回调；流式 LLM 增量经 Channel。 |
| `Signal`（`core/runtime/shared/signals.py`） | 既有 `Signal`（RETURN/BREAK/CONTINUE/THROW）是 **VM 控制流信号**（帧间传递）；新 `IbSignal`（cancel/pause/resume/config_change）是**运行时协调信号**（任务/VM 实例级）。两者命名域不同、职责不同，**不合并**（合并会造成语义混乱）。新 `IbSignal` 复用 `SignalCore` 数据结构，`kind` 为字符串枚举。 |

---

## 四、内省层（PT-MT-4 核心）

### 4.1 快照式：`runtime.snapshot()`

返回当前运行时全部可观测状态的**结构化 dict**：

```python
# IBCI 侧
dict s = runtime.snapshot()
# {
#   "tasks": [{"handle": "...", "status": "running|done|waiting|cancelled",
#               "node_uid": "...", "started_at": ...}],
#   "channels": [{"name": "...", "mode": "message", "qsize": 3, "closed": false}],
#   "slots": [{"name": "score", "value": 42}],
#   "vms": [{"instance_id": "...", "status": "running", "active_intents": [...]}],
#   "llm": {"pending_futures": 2, "last_call_info": {...}},
#   "vars": {"<module>:<name>": value}
# }
```

实现：`core/runtime/observability/snapshot.py`——协调器/VM/CommRegistry/TaskScheduler/executor 各自暴露 `snapshot()`，快照器聚合。**快照必须无锁一致性**（每子快照持锁取一致切片；整体不强求跨对象一致性快照，文档注明）。

### 4.2 事件流：`runtime.subscribe()`

返回一个 `Channel`（mode=stream），运行时状态变更事件推入：

```python
chan events = runtime.subscribe()
while not events.closed:
    dict ev = events.recv()   # {"type": "task_started"|"task_done"|"chan_send"|...,
                               #  "data": {...}}
```

实现：
- 各可观测源（协调器/VM/CommRegistry）实现 `EventSource` 协议：`attach(sink_channel)` / `detach()`。
- 订阅即建一个 `ChannelCore(mode="stream")`，事件产生方 `send(事件 dict)`。
- 事件类型：`task_started` / `task_done` / `task_cancelled` / `chan_created` / `chan_closed` / `slot_updated` / `llm_dispatched` / `llm_resolved` / `vm_spawned` / `vm_terminated` / `configured`。
- **协议驱动**：事件源统一走 `EventSource` 协议，禁止在运行流程里写 `if 事件类型` 硬编码分发。

### 4.3 内省的可观测性目标

> 对标 Python `sys.settrace`/`inspect`、`asyncio.all_tasks()`、OpenTelemetry spans——通用、可复用、不过时，非 LLM 专有伪设计（用户裁定 §五）。

---

## 五、控制层（PT-MT-5 核心）

### 5.1 `runtime.configure(...)`

统一"启停"接口，每能力有开启/关闭两侧，默认值不同：

```python
runtime.configure(parallel=True, stream=True, observability=True, debug=False)
```

| 能力 | 默认 | 说明 |
|------|------|------|
| `parallel` | **开** | 并发 dispatch（`dispatch_eager` / run_many） |
| `stream` | **开** | 流式 LLM 增量（provider 支持时） |
| `observability` | **开** | 内省（snapshot/subscribe 记录） |
| `debug` | **关** | 调试细节（调用信息记录、call_info 保留） |

### 5.2 粒度链式覆盖

`全局 → 单调用 → 单实例`（链式覆盖，后者优先）：

- **全局**：`runtime.configure(...)` 设置运行时默认。
- **单调用**：`runtime.configure(task=handle, stream=False)` 覆盖某次调用/某任务。
- **单实例**：`runtime.configure(instance="child", observability=False)` 覆盖某 VM 实例。

实现：`ConfigStore`（`core/runtime/observability/config.py`），键 = `(scope, key)`，查询按 单实例 → 单调用 → 全局 顺序解析（**单点真理**：只有一个 ConfigStore）。

### 5.3 控制机制实现

- `configure` 变更经 `IbSignal(kind="config_change", payload=diff)` 广播到所有 VM 实例（协议驱动）。
- 每 VM 实例的 executor/调度器读取生效配置（读时解析，不缓存陈旧值）。

---

## 六、流式 + 并行（PT-MT-6 核心）

### 6.1 两个独立概念（不混淆）

| 概念 | 本质 | 默认 |
|------|------|------|
| **并行** | 多个 LLM 调用并发推进（`dispatch_eager`/`run_many`，Stage 1/2 已落地） | 开 |
| **流式** | 单个 LLM 响应的增量逐步到达（provider 流式接口 → Worker 增量 → Channel → 渲染线程） | 开 |

### 6.2 流式 provider 接口

`ibci_ai` 的 `AIPlugin.__call__` 增加流式能力（协议化，非硬编码分支）：

```python
class ILLMProvider(Protocol):
    def __call__(self, sys_prompt, user_prompt, *, target_model="") -> str: ...
    def stream(self, sys_prompt, user_prompt, *, target_model="") -> Any:
        """返回增量迭代器（逐步产出 str 增量）；非流式 provider 可抛 NotImplementedError。"""
        ...
```

- `IbStreamHandle`（`Waitable` 协议）：持有 `ChannelCore(mode="stream")`，`is_done` = provider 增量结束；`result()` = 完整拼接文本。
- Worker 线程（LLM IO 边界）以流式接口接收增量 → `send` 到 Channel → 渲染线程 `recv` 逐块渲染（实时 UI/输出刷新）。

### 6.3 流式管线

```
LLM provider.stream() → Worker 线程逐块 yield → ChannelCore(stream) → 渲染线程 recv → 逐块输出/UI 刷新
```

- `stream=False`（configure 关）或 provider 不支持流式 → 走既有非流式路径（`__call__`），**不是**双通道——是同一调用的能力降级（单点实现，按能力探测决定）。
- MOCK 验证：`mock_service.py` 的 MockServer 增加流式端点支持（chunked 响应），`MockScenarioEngine` 增加流式指令（如 `STREAM:块1|块2|块3`）。

### 6.4 与并行共存

- 并行 = 多个行为并发 dispatch（既有）；流式 = 每个行为内部增量到达（新增）。两者正交。
- `run_many` + 流式：每个根的行为若 provider 支持流式，则增量经各自 Channel 传出，同时多个根并发推进。

---

## 七、多 VM 实例 + 用户代码多线程（PT-MT-7/8 核心）

### 7.1 轻量 VM 实例

**定义**：每个并发路径（`spawn` 的任务）一个轻量 VM 实例。

- **复用**既有 `spawn_isolated` 多引擎机制（`engine.py` `request_spawn_isolated`：后台线程 + 独立子 Engine），升级为"同进程多线程多 VM"。
- **轻量**：与 `spawn_isolated`（完整隔离引擎，独立注册表/插件/编译）不同，`spawn(fn)` 的任务是**同进程、共享 artifact/node_pool（只读）、共享注册表/类体系**的轻量执行——只在**执行上下文/作用域/意图栈**上隔离。
- **执行模型（关键）**：参考 `IbUserFunction.call()`（`user_functions.py`）——函数体经 `vm.run_body(body)` 驱动。spawn 任务在此基础上**新建独立轻量执行上下文**（自有 runtime_context + 独立 VM 驱动循环），而非复用主线程的 runtime_context：
  - 任务作用域栈、意图上下文（fork 种子）、llmexcept 帧栈、loop 上下文**完全独立**（per-task 所有权，对应 Stage 1 去共享化原则）。
  - artifact/node_pool 只读共享（CPS handler 的节点数据是编译产物，只读）。
  - **executor 独立性（D6 定案）**：每个轻量 VM 实例持有**自己的 `LLMExecutorImpl`**（自有 `_current_call_info` 主线程单写槽、`_pending_futures`、线程池），避免多任务共享 executor 的写竞争——这正延续 Stage 1 去共享化设计，符合用户裁定"每并发路径一个轻量 VM 实例（完全隔离）"。
- **全局只读数据**：任务可读主环境的全局只读数据（常量、类型、已注册模块），不可写污染（写入经 Channel/Slot 显式通信）。

### 7.2 任务生命周期（spawn/join/cancel）

```
spawn fn(args) → 新轻量 VM 实例（后台线程 + 独立执行上下文 + 独立 executor）
              → 注册到协调器 → 返回 task 句柄
join task      → 对 task 的完成 Waitable yield 挂起 → 就绪后取回结果
cancel task    → 经 IbSignal(kind="cancel", target=handle) 协作式取消
```

- **后台线程 vs TaskScheduler 根（定案）**：`spawn` 任务是**后台线程**（真并行，供实时 UI/输出刷新——用户裁定"用户可见多线程"）；`TaskScheduler`/`run_many` 保留为**内部 LLM 并发**（单线程协作式，服务 IO 密集）。两者分工不同，不混用（单点真理：spawn=线程，run_many=协作式并发）。
- **join 返回结果**：`join` 返回值 = spawn 的函数返回类型（语义阶段确定）。
- **cancel 语义**：协作式——任务在下一个可挂起点（yield Waitable / Channel recv / 循环边界）检查取消标志，自行退出。Python 无法强杀线程，故 cancel 是**请求**而非强杀（文档注明，与 `collect_timeout` 孤儿线程语义一致）。
- **fire-and-forget**：`spawn fn(...)` 无赋值目标 → 后台运行，结果丢弃（或进内省事件）。

### 7.3 内核协调器（RuntimeCoordinator）

`core/runtime/coordinator.py`：

```python
class RuntimeCoordinator:
    """多任务/多 VM 生命周期协调器。

    - spawn(fn, args) → task handle
    - join(handle) → 结果（Waitable）
    - cancel(handle)
    - is_done(handle)
    - snapshot() / subscribe(events_channel)
    - configure(...) 分发
    """
    def __init__(self, engine, config_store): ...
    def spawn(self, fn, args, keywords=None, instance=None): ...
    def join(self, handle): ...
    def cancel(self, handle): ...
    def is_done(self, handle) -> bool: ...
```

- 与既有 `engine._spawned_tasks`（隔离引擎）**共存不合并**：隔离引擎任务是"子 Engine"（独立注册表/编译）；`spawn(fn)` 任务是"同 VM 轻量任务"（共享注册表）。两者都经协调器管理，但生命周期语义不同（隔离 = 完整子引擎；轻量 = 同进程任务）。**此决策为单点真理**：协调器统一暴露任务 API，内部区分两种任务类型（经 `TaskHandle.kind` 枚举，非过程式 if）。

### 7.4 用户代码多线程（语言面）

```ibci
fn compute(str x) -> int:
    return @~ 计算 $x 的答案 ~

task t = spawn compute("问题A")     # 新任务
task t2 = spawn(lambda: @~ 另一个问题 ~)  # spawn lambda

int r1 = join t                    # 等待并取回结果
str r2 = join t2

# 实时 UI/输出刷新场景：
chan events = chan(str, "stream")
task renderer = spawn(lambda:
    while True:
        str chunk = events.recv()
        print(chunk)
        if chunk == "": break
)
```

---

## 八、并发正确性（贯穿全主线）

### 8.1 线程安全不变量（必须守住）

| # | 不变量 | 实现 |
|---|--------|------|
| C1 | 通信内核（buffer/channel/slot/registry）所有读改写原子 | `threading.Condition`/`Lock` 单一锁 |
| C2 | 主线程单写槽 `_current_call_info` 只主线程写 | 既有（Stage 1 已落地）；流式路径也不破坏 |
| C3 | `_pending_futures` 每 Future 恰被 resolve 一次 | 既有（dispatch/resolve 配对）；spawn 任务内部独立 executor 上下文 |
| C4 | 每个轻量 VM 任务独占自己的 runtime_context/意图/llmexcept 帧栈 | per-task 所有权 |
| C5 | 全局只读数据多任务只读 | 只读引用（不加锁）；写必须经 Channel/Slot |
| C6 | 广播/定向寻址在注册表锁内一致 | CommRegistry 锁 |
| C7 | configure 读时解析不缓存陈旧 | ConfigStore 查询链 |
| C8 | 每个后台线程/轻量 VM 只写自己 executor 的单写槽 | 每轻量 VM 实例独立 `LLMExecutorImpl`（D6 定案），其 `_current_call_info` 是"该任务线程的单写槽"，不跨任务竞争 |

### 8.2 协作式取消的正确性

- cancel 经 `IbSignal(kind="cancel", target=handle)` 投递 → 任务在**可挂起点**检查。
- 挂起点定义：`yield Waitable` / `Channel.recv` 阻塞 / 循环边界 / 函数边界。每个挂起点检查 `TaskState.cancel_requested`。
- 取消后任务以 `CancelledError` 或规范值退出；`join` 收到取消结果。

### 8.3 共享状态隔离

- 轻量任务不写主环境作用域（写会报错或经 Slot/Channel）。
- 意图上下文 fork（Stage 1 已验隔离）；spawn 的任务 fork 当前意图快照为种子（与 snapshot lambda 语义一致）。
- llmexcept 帧栈、loop 上下文 per-task。

### 8.4 死锁避免

- 通信内核单锁（不持锁调用外部代码——send/recv 只操作内部队列，不回调用户代码）。
- `update(fn)` 的原子读改写：`fn` 在锁内执行有风险（若 fn 内部再进通信会死锁）→ **设计约束**：`SlotCore.update` 的 `fn` 必须在锁内执行，文档禁止 fn 内嵌通信操作；或改为"读-算-写"非锁内（见 §10 待决项）。
- 测试含死锁看门狗（conftest 已有 90s 强制退出）。

---

## 九、测试策略（PT-MT-1 → PT-MT-8 全程）

### 9.1 测试分层

| 层 | 文件 | 覆盖 |
|----|------|------|
| 通信内核单元 | `tests/runtime/test_comm_channel.py` / `test_comm_signal.py` / `test_comm_slot.py` / `test_comm_buffer.py` | 线程安全 send/recv、有界阻塞/非阻塞、close 语义、pubsub 扇出、slot 原子读改写、signal 定向/广播 |
| 编译器 | `tests/compiler/` | 新节点 parser 正/负样本、语义类型检查（task/chan/signal/slot）、序列化 round-trip |
| VM | `tests/runtime/test_vm_spawn_join.py` / `test_vm_cancel.py` | spawn/join/cancel 的 VM 驱动 |
| 内省 | `tests/runtime/test_observability.py` | snapshot 结构、subscribe 事件流 |
| 控制 | `tests/runtime/test_runtime_configure.py` | configure 粒度链式覆盖、配置生效 |
| 流式 | `tests/runtime/test_streaming.py` | 流式 provider（mock chunked）、Worker→Channel→渲染 |
| 多 VM | `tests/runtime/test_vm_instance_pool.py` | 轻量 VM 隔离、全局只读、join 结果 |
| e2e | `tests/e2e/` | IBCI 代码端到端（spawn/join/chan/slot/signal 全链路） |

### 9.2 并发正确性测试（复用既有模式）

- `test_concurrent_dispatch_integrity.py` 思路（mock_server 真并发）扩展到 Channel/Slot。
- **真实并发重叠断言**：两个任务各等不同 waitable，总时近似 max 而非 sum（`test_task_scheduler.py` 模式）。
- **时序断言**：流式块顺序、pubsub 扇出顺序。
- **死锁防护**：conftest 90s 看门狗已覆盖。

### 9.3 回归门槛

每批改动全量 `python -m pytest tests/` 零回归。基线以实跑为准，不冻结数字（AGENTS.md 纪律）。

### 9.4 破坏面评估

- 新增 TokenType/AST 节点/dispatch handler → 全量 pytest 评估（编译器管道所有消费者需覆盖新节点）。
- 新增类型（task/chan/signal/slot）注册 → 检查 prelude 过滤器、类型解析器、序列化器类型处理。
- 不改变既有 `__call__`/`run_batch`/`resolve` 语义（流式为新增协议，非替换）。

---

## 十、待决项（self-grill 归零前保留）

以下为设计阶段待决，多数可自主裁定，仅用户强相关项标注：

| # | 待决项 | 分析 | 推荐（自主裁定） |
|---|--------|------|-----------------|
| D1 | `spawn` 语法形态 | `task t = spawn fn(...)` vs `task t = spawn(fn, args)` | 两形态都支持（`spawn <expr>` 表达式/语句形态，复用函数调用语法），Parser 兼容 |
| D2 | `chan` 语法 | `chan T(...)` vs `chan(T, ...)` | 都支持；`chan T(mode=..., buffer=...)` 声明式为主 |
| D3 | `slot.value` 属性 vs `slot.get()/set()` | 属性语法更 IBCI 化，但实现需属性协议 | **属性语法**（`slot.value = x` / `x = slot.value`），经对象属性协议；保留 `get/set` 方法兜底（协议驱动） |
| D4 | `SlotCore.update(fn)` 锁内 vs 锁外 | 锁内执行 fn 有死锁风险 | **锁外读改写**（get → fn 计算 → CAS set），避免持锁回调；若需严格原子性再评估 CAS 循环 |
| D5 | pubsub 订阅者队列边界 | 无界订阅者队列内存风险 | 订阅者队列用有界 buffer（默认配置），满则丢最旧或阻塞（文档化） |
| D6 | 轻量 VM 是否独立 executor | 每任务独立 `LLMExecutorImpl` vs 共享 | **每轻量 VM 实例独立 `LLMExecutorImpl`**（自有 `_current_call_info` 单写槽 / `_pending_futures` / 线程池）——延续 Stage 1 去共享化，避免多任务共享 executor 的写竞争；符合用户裁定"每并发路径完全隔离" |
| D7 | 流式 provider 探测 | 如何探测 provider 是否支持流式 | `IbStreamHandle` 构造时探测：provider 有 `stream` 方法即流式；无则降级非流式（能力探测，非双通道） |
| D8 | `task` 句柄序列化 | save_state 时 task 存活 | **不序列化**（用户裁定：并发任务为运行时瞬态）；save_state 时未 join 的 task 记作 cancelled |
| D9 | 广播 Signal 目标集合 | 广播给谁 | 广播给注册表全部任务 + 全部 VM 实例；定向给指定 handle |

> 以上 D1-D9 均可在设计阶段自主裁定（已有推荐）。若用户审阅时对某项有异议，按用户指示调整。

---

## 十一、实施顺序（对应 PT-MT-* 阶段）

| 阶段 | 任务 | 交付物 | 依赖 |
|------|------|--------|------|
| **PT-MT-2** | 编译器地基 | 新 AST 节点 + lexer token + parser + 语义 + dispatch + 序列化（spawn/join/cancel/chan/signal/slot 全落地，可编译运行但暂无线程） | 本设计文档 |
| **PT-MT-3** | 统一通信内核 | CommBuffer/Channel/Signal/Slot/Registry + `IbChannel`/`IbSignal`/`IbSlot` 语言层对象 | PT-MT-2 |
| **PT-MT-4** | 内省层 | snapshot + subscribe（协调器/VM/CommRegistry 事件源） | PT-MT-2/3 |
| **PT-MT-5** | 控制层 | ConfigStore + `runtime.configure` + config_change 信号 | PT-MT-3/4 |
| **PT-MT-6** | 流式 + 并行 | 流式 provider 接口 + MockServer 流式端点 + Worker→Channel→渲染 | PT-MT-3 |
| **PT-MT-7** | 多 VM 实例 | 轻量 VM 任务 + RuntimeCoordinator + 隔离/只读数据 | PT-MT-2/3 |
| **PT-MT-8** | 用户代码多线程 | `task t = spawn(fn)`/`join`/`cancel` 语言面完整可用 + 实时 UI 刷新 | PT-MT-7 |

**阶段门禁**：每阶段完成 → 全量 pytest 零回归 → 描述性 commit → 更新 NEXT_STEPS/PENDING_TASKS → 接续下一阶段。

---

## 十二、非目标（明确不做）

- 跨进程 / CPU 并行（性能瓶颈在 IBCI 包装，非 CPU 并发）。
- 跨引擎通信（隔离运行是自我进化窗口，保持文件/序列化机制）。
- media Phase 4 多模态。
- 完整通用异步（async 函数/生成器）——本主线只做 spawn/join/chan 等具体形态，`async def`/`yield` 生成器不在此范围（后续独立评估）。
- 不删除/破坏既有 `output_callback`/`call_info`/`run_batch`/`Waitable` 对外契约（本主线为新增一等机制 + 演进，非替换）。

---

> 本设计文档为 PT-MT-1 交付物，待用户审阅通过后落地实现（PT-MT-2+）。
