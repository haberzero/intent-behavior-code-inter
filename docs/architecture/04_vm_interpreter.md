# IBCI VM 与解释器架构

> 本文档是 IBCI 运行时（VM + 解释器）的架构设计文档，覆盖 CPS 调度循环、执行帧、LLM 流水线、llmexcept 机制、意图上下文、多 Interpreter 隔离、内存模型。
> 公理化可验证规范见 `docs/architecture/05_vm_specification.md`。
>
> **路径说明**：以下模块已重构为包（目录），正文中 `*.py` 路径请以实际目录为准：
> `runtime/vm/handlers/`（CPS handler 包）、`runtime/objects/{primitives,kernel}/`、`runtime/interpreter/llm_executor/`。

---

## §1 总览：层级与职责

```
┌──────────────────────────────────────────────────────────────────────┐
│ IBCI Engine (core/engine.py)                                          │
│   ├─ KernelRegistry  ───── SpecRegistry · AxiomRegistry · llm_executor │
│   ├─ Compiler ──── 输出不可变 CompilationResult（artifact + side tables）│
│   └─ Interpreter ── 解释器外壳                                         │
│        ├─ ServiceContext  — capability_registry / llm_executor / ...   │
│        ├─ ExecutionContextImpl — node 池、侧表、对象工厂、registry 引用 │
│        ├─ RuntimeContextImpl — 当前执行帧（scope / intent / llm_except_frames）│
│        └─ VMExecutor ── CPS 调度循环（运行时唯一执行入口）              │
│             ├─ build_dispatch_table() — 45 个 AST 节点 handler         │
│             ├─ Frame stack (List[VMTask])                              │
│             └─ Signal / UnhandledSignal — 控制流数据化                  │
└──────────────────────────────────────────────────────────────────────┘
```

执行任意 IBCI 代码的唯一路径：**`Interpreter.execute_module()` / `IbUserFunction.call()` → `VMExecutor.run_body(body)` → CPS 调度循环**。

---

## §2 CPS 调度循环

### 2.1 数据对象

`core/runtime/vm/task.py`：

| 类型 | 作用 |
|------|------|
| `VMTask(node_uid, generator, locals)` | 一个执行帧；包装节点求值的 Python 生成器协程 |
| `VMTaskResult(kind, value)` | 标记类型 `done` / `suspend` / `signal`（部分场景代用） |
| `Signal(kind: ControlSignal, value)` | 控制流数据对象（`return` / `break` / `continue` / `throw`） |
| `UnhandledSignal(signal)` | VM 顶层未消费 Signal 的边界异常 |

### 2.2 主循环协议

`core/runtime/vm/vm_executor.py:VMExecutor`：

```text
while frame_stack:
    task = frame_stack.top()
    res = task.generator.send(pending_value)   # 或首次 send(None)
    if isinstance(res, str):                   # yield child_uid
        frame_stack.push(make_task(res))
    elif StopIteration(value):                 # 协程结束
        if isinstance(value, Signal):          # 控制信号沿生成器返回值传播
            propagate_signal_to_parent(value)
        else:
            send_to_parent(value)
    elif raise:                                # Python 异常
        throw_to_parent_generator(exc)
```

### 2.3 公理（与 `05_vm_specification.md` §1 对齐）

| 公理 | 内容 |
|------|------|
| **EXEC-1 无 Python 递归** | 主路径不使用 Python 递归栈；IBCI 调用深度不受 `sys.setrecursionlimit` 限制 |
| **EXEC-2 控制流数据化** | `return` / `break` / `continue` / `throw` 通过 `Signal(kind, value)` 沿生成器返回值传播；不使用跨帧异常 |
| **EXEC-3 llmexcept 显式驱动** | llmexcept 关联通过 AST 字段 `llmexcept_handler` 统一挂载到被保护语句；各语句 handler 检查返回值 `IbLLMCallResult(is_certain=False)`，内联创建 `LLMExceptFrame` + retry 循环（无 handler 时抛 `LLMParseError`） |

### 2.4 Handler 表

`core/runtime/vm/handlers/dispatch.py:build_dispatch_table()` 注册 45 个 `vm_handle_IbXxx(executor, node_uid, node_data)` 生成器函数：

| 类别 | 节点 |
|------|------|
| 字面量 / 名字 / 算子 | `IbConstant` `IbName` `IbBinOp` `IbUnaryOp` `IbBoolOp` `IbCompare` `IbIfExp` `IbAwaitExpr` |
| 表达式 | `IbCall` `IbAttribute` `IbSubscript` `IbTuple` `IbListExpr` `IbDict` `IbSlice` `IbCastExpr` `IbFilteredExpr` |
| 语句 | `IbExprStmt` `IbAssign` `IbAugAssign` `IbIf` `IbWhile` `IbFor` `IbReturn` `IbBreak` `IbContinue` `IbPass` `IbRaise` `IbSwitch` `IbTry` `IbRetry` `IbGlobalStmt` `IbNonlocalStmt` |
| 模块 / 引入 | `IbModule` `IbImport` `IbImportFrom` |
| 声明 | `IbFunctionDef` `IbLLMFunctionDef` `IbClassDef` |
| 意图 | `IbIntentAnnotation` `IbIntentStackOperation` |
| Behavior / 闭包 | `IbBehaviorExpr` `IbLambdaExpr` |
| 并发 / 通信 | `IbChannelExpr` `IbSlotExpr` |
| llmexcept | `IbLLMExceptionalStmt`（挂载载体，不入 body；经 `llmexcept_handler` 字段驱动） |

每个 handler 是 `def vm_handle_*(...) -> Generator`：通过 `yield child_uid` 发起子求值，`return value` 完成本帧；`return Signal(...)` 触发控制流。

### 2.5 Handler 编写约束

- 不允许递归 `executor.run(...)`；子求值通过 `yield child_uid`。
- 不允许 `raise ControlSignalException`；用 `return Signal(kind, value)`。
- 拦截 `Signal`：父 handler 用 `isinstance(res, Signal)` 判断后决定 **拦截**（循环 handler 拦截 `BREAK`/`CONTINUE`，函数帧拦截 `RETURN`，`Try` handler 拦截 `THROW` 并匹配 `except`）或 **透传**（`return res`）。

### 2.6 调用实参绑定（统一绑定器）

`vm_handle_IbCall` 是所有可调用形式（用户函数、类方法、fn-lambda、behavior、LLM 函数、原生模块函数）的统一调用点。它先 CPS 求值函数对象与实参，再经统一绑定器解析：位置实参（`*expr` 序列解包展开）与具名实参（`**expr` 字典解包合并）收集后，按**声明序**执行「位置 → 具名 → 默认填充 → varargs/varkw」绑定，产出最终实参列表。

| 输入 | 处理 |
|------|------|
| 位置实参 | 依序填入普通参数槽位；溢出进入 `*args`，无 `*args` 则报错 |
| 具名实参 | 命中声明参数即绑定（重复绑定报错）；未声明且有 `**kwargs` 则归入 `**kwargs`，否则报未知具名 |
| 缺省参数 | 未绑定的普通 / keyword-only 参数取默认值：用户级默认表达式经 `yield` 惰性求值，原生默认值直接使用字面值 |
| `*args` / `**kwargs` | 打包为 `list` / `dict`（装箱为 IbObject） |

绑定算法与语义层同源，收敛于 `core/kernel/arg_binding.py:resolve_call_binding`（共享纯核心，见 `docs/architecture/03_type_system.md` §3.6）；运行时适配层 `core/runtime/vm/handlers/_shared.py:_resolve_call_arguments_runtime` 把中性绑定计划映射为按声明序的最终实参列表。调用体参数签名由 `_get_callee_param_specs` 按 callee 种类取得：用户/LLM 函数读自身 AST 的 `IbArg` 节点；fn_callable / behavior 读 `params_uids`；原生模块函数读 `IbNativeFunction.param_meta` 字段（loader 构建的声明元数据）；bound method 解包到内层方法。无静态签名（内置构造器 / axiom-backed）时保持位置直传、忽略具名实参，与语义层动态策略一致。

原生模块函数声明 `**kwargs`（VAR_KEYWORD）时，绑定器把归集的具名实参 dict 装箱为声明序末位的位置实参；loader 代理（`create_proxy`）识别声明并把它分传为 `**kwargs` 交给原生实现。声明 VAR_KEYWORD 但实现不接受 `**kwargs` 在加载阶段即失败。

该绑定语义与语义层实参解析（`docs/architecture/03_type_system.md` §3.6、§5.1）一致。运行期各 callee 路径保持按索引绑定不变，参数解析的改动收敛在 `vm_handle_IbCall` 单一入口。

---

## §3 执行帧与上下文

### 3.1 三层"上下文"

| 名称 | 文件 | 责任 |
|------|------|------|
| `ServiceContext` | `core/runtime/interpreter/service_context.py` | 进程级服务：`llm_executor` / `capability_registry` / `host_service` / 调试器 |
| `ExecutionContextImpl` | `core/runtime/interpreter/execution_context.py` | 解释器静态部分：节点池、侧表、`registry`、`object_factory`、`runtime_context` 引用 |
| `RuntimeContextImpl` | `core/runtime/interpreter/runtime_context.py` | 当前执行帧：scope / intent_context / llm_except_frames / loop_stack / retry_hint |

### 3.2 IExecutionFrame 协议

`core/base/interfaces.py:IExecutionFrame`：

```python
class IExecutionFrame(Protocol):
    @property
    def pc(self) -> str: ...                       # 当前 node_uid
    @property
    def scope(self) -> Scope: ...                  # 局部变量 / 闭包 cell 引用
    @property
    def intent_context(self) -> IbIntentContext: ...
    @property
    def llm_except_stack(self) -> List: ...
    def visit(self, node_uid, **kwargs): ...
```

`RuntimeContextImpl` 即此协议的实现。多 Interpreter 隔离通过为每个子解释器创建独立 `RuntimeContextImpl` 实现。

### 3.3 ContextVar 当前帧

`core/runtime/frame.py` 暴露 `get_current_frame()` / `set_current_frame()` / `reset_current_frame()`（基于 `contextvars.ContextVar`）。`Interpreter.execute_module()` 与 `IbUserFunction.call()` 入口设置当前帧；asyncio Task / 多 Interpreter 线程间天然隔离。

---

## §4 作用域与闭包

### 4.1 公理（与 `05_vm_specification.md` §2.2 对齐）

| 公理 | 内容 |
|------|------|
| **SC-1 词法嵌套** | `ScopeImpl._parent` 链构成树；全局 scope 是树根 |
| **SC-2 变量分类** | Local（本地） / Cell（被内层 lambda/snapshot 引用） / Free（外层引用） |
| **SC-3 Cell 语义** | `IbCell` 是独立堆对象；Cell 变量的读写就是 `IbCell.value` 的读写 |
| **SC-4 自由变量捕获** | 嵌套 fn 创建时把 `IbCell` 引用写入对象 `closure` 字典；之后函数对象与外层 scope 生命周期解耦 |

### 4.2 IbCell 与 promote_to_cell

`core/runtime/objects/cell.py:IbCell` 是纯容器（`value` 字段 + GC 钩子 `trace_refs()`）。`ScopeImpl.promote_to_cell(sym_uid)` 把已有局部变量升级为 cell（首次 lambda/snapshot 捕获时由 VM 调用）。

### 4.3 lambda vs snapshot

- **lambda**（引用捕获）：通过 `current_scope.promote_to_cell(sym_uid)` 共享 `IbCell`；调用时 `cell.get()` 读最新值；`captured_intents=None`，运行时取调用方意图栈。
- **snapshot**（值捕获，无状态可重入）：定义时刻对所有自由变量做深克隆（`try_deep_clone`）形成只读种子；每次调用前再次对种子深克隆注入子作用域；`captured_intents = runtime_context.fork_intent_snapshot()`（定义时刻意图栈快照）。snapshot 不缓存任何结果——除调用时实参以外的所有内容都按值冻结，每次调用都是独立的求值。

### 4.4 cell 捕获 × dispatch_eligible

为保证 `IbCell` 只持有合法 `IbObject`（不持 `LLMFuture` 占位符），编译期 `BehaviorDependencyAnalyzer` 把 cell 捕获变量的 behavior 赋值强制 `dispatch_eligible=False`（`core/compiler/semantic/passes/behavior_dependency_analyzer.py`）。VM 在 `vm_handle_IbAssign` 检查此标志，cell 变量赋值不走 dispatch_eager。

---

## §5 LLM 流水线（dispatch-before-use）

### 5.1 三层并发模型

| 层 | 粒度 | 状态 |
|----|------|------|
| **L1: LLM 调用流水线** | 单个 LLM 调用 | 当前支持 |
| **L2: 多 Interpreter 隔离** | 整段程序 | 当前支持 |
| **L3: 语言级生成器（yield）** | 单个 yield 点 | 规划中（阶段 5 实现项，见 `docs/subsystems/05_coroutine.md`） |

### 5.2 编译期：依赖图（DDG）

`core/compiler/semantic/passes/behavior_dependency_analyzer.py`（Pass 5）为每个 `IbBehaviorExpr` 标注：

| 字段 | 含义 |
|------|------|
| `llm_deps: List[IbBehaviorExpr]` | 依赖的前序 behavior 节点 |
| `dispatch_eligible: bool` | 是否可提前 dispatch（DAG + 无 cell 捕获 + 无 llmexcept 保护） |

强制 `dispatch_eligible=False` 的场景：
- 模板 `$var` 插值依赖前序 behavior 输出；
- 赋值目标是 cell 变量（cell 不能持 `LLMFuture`）；
- 节点处于 llmexcept 保护下（snapshot 隔离）。

### 5.3 运行期：LLMScheduler / LLMFuture

`core/runtime/interpreter/llm_scheduler.py`：

| 入口 | 行为 |
|------|------|
| `dispatch_eager(node_uid, prompt_args, intent_ctx) -> LLMFuture` | 立即提交 `ThreadPoolExecutor`，返回 Future（不阻塞） |
| `LLMFuture.resolve()` | 阻塞等待 LLM HTTP 完成，返回真实 `IbObject` |

VM 行为：
- `vm_handle_IbAssign`：`rhs` 是 behavior 且 `dispatch_eligible=True` → `LLMScheduler.dispatch_eager()`，把 `LLMFuture` 写入 scope（`define_raw`）。
- `vm_handle_IbName`：读取时若拿到 `LLMFuture` → `resolve()` 阻塞 → 真实 `IbObject` 写回 scope，后续读取 O(1)。

### 5.4 公理（与 `05_vm_specification.md` §3 对齐）

| 公理 | 内容 |
|------|------|
| **LLM-1** | dispatch_eligible=True 时立即 dispatch_eager，写入 LLMFuture |
| **LLM-2** | 读取点 lazy resolve，O(1) 命中后续读取 |
| **LLM-3** | 并发 dispatch 不改变输出顺序，按语句语义顺序提交 |

### 5.5 LLM 调用路径（当前实现）

```text
表达式：x = @~ ... ~
   ├── dispatch_eligible=True：
   │     vm_handle_IbAssign → LLMScheduler.dispatch_eager()
   │       → ThreadPoolExecutor.submit(_call_llm)
   │       → IbLLMFuture 写入 scope
   │     使用点 vm_handle_IbName → future.resolve()
   │
   └── dispatch_eligible=False：
         vm_handle_IbAssign → LLMExecutorImpl.execute_behavior_expression(...)
           → _call_llm() → axiom.from_prompt(raw, spec)
           → LLMResult(success/value/is_uncertain/raw_response/retry_hint/call_info)
           → 确定：返回 result.value；不确定：返回 IbLLMCallResult(is_certain=False) 容器
```

> LLM 调用路径：`IbBehavior.call()` / `IbLLMFunction.call()` 在 VM CPS 主路径下由 `core/runtime/vm/handlers/` 包中的 `_vm_invoke_behavior` / `_vm_invoke_llm_function` 助手通过 `yield from` 接管，调用时 VMTask 留在帧栈上；两者保留为 Python 可调用后备（host/直接调用场景），外部契约不变。

---

## §6 llmexcept：消费者内联驱动模式

### 6.1 模型概述

llmexcept 使用快照隔离 + 消费者内联驱动 + 返回值传递实现。certainty 经
`IbLLMCallResult` 返回值传递（产生者不写 frame / 全局槽），各被保护语句
handler 从返回值检查不确定并创建帧执行重试：

```text
vm_handle_IbIf / IbWhile / IbFor / IbSwitch / IbAssign / IbExprStmt
  ├─ cond/value = yield 被保护表达式
  │     └─ 内部 LLM 调用不确定 → 返回 IbLLMCallResult(is_certain=False) 容器
  ├─ if _is_llm_uncertain_value(cond/value)（或 is_truthy 返回容器）:
  │     ├─ 无 llmexcept_handler → 抛 LLMParseError
  │     └─ _retry_llm_uncertain()：
  │           ├─ save_llm_except_state()       — 创建 LLMExceptFrame，保存变量/意图/loop 快照
  │           ├─ frame.target_result = 容器
  │           └─ while frame.should_continue_retrying()：  （单帧计数内收敛）
  │                ├─ frame.restore_snapshot()
  │                ├─ 重新求值被保护表达式（yield re_eval_uid）
  │                ├─ 确定/可接受 → 返回最终值
  │                ├─ 否则执行 llmexcept body（可含 IbRetry）→ frame.increment_retry()
  │                └─ 耗尽 → 抛 LLMRetryExhaustedError
  └─ 确定：按分支/赋值/循环语义继续
```

### 6.2 关键组件

| 组件 | 文件 | 责任 |
|------|------|------|
| `LLMExceptFrame` | `core/runtime/interpreter/llm_except_frame.py` | 现场快照（变量、意图栈、loop 栈、retry hint）+ 快照完整性校验 |
| `LLMExceptFrameStack` | 同上 | 嵌套 llmexcept 块栈管理 |
| `IbLLMUncertain` | `core/runtime/objects/kernel/sentinels.py` | 不确定结果哨兵对象（赋值占位符，重试轮内标记目标变量） |
| `IbLLMCallResult` | `core/runtime/objects/kernel/sentinels.py` | certainty 信号载体（内部传递容器，`is_certain=False` 触发重试） |
| `LLMResult` | `core/runtime/shared/llm_result.py` | LLM 调用结果数据对象（`is_uncertain` 旗标 + `call_info`） |

### 6.3 快照内容

- 可序列化变量（IbNone / IbInteger / IbFloat / IbString / IbList / IbTuple / IbDict）深克隆；
- `intent_context.fork()` 产生独立意图上下文快照；
- `_loop_stack` 深拷贝；
- `loop_resume`（for 循环断点恢复映射）**不重置**（设计决定）；
- 函数 / behavior / NativeObject 等引用类型显式排除。

### 6.4 完整规范

详见 `docs/architecture/05_vm_specification.md` §5（意图上下文模型公理）。

### 6.5 Body 保护机制（编译期 + 运行期双层防御）

llmexcept handler body 对**参与 LLM 调用的变量**实施只读保护。保护集为：`$` 插值引用的变量、意图注解引用的变量、接收 LLM 结果的赋值目标。非 LLM 参与变量的修改默认允许。

**编译期**（BindingPhase，`binding_analysis_pass.py`）：

| 检查 | 诊断码 | 触发条件 |
|------|--------|----------|
| 赋值/属性变异/下标变异 | `SEM_LLMEXCEPT_BODY_WRITE` | 赋值目标的根变量 ∈ 保护集 |
| mutating 方法调用 | `SEM_LLMEXCEPT_MUTATING_CALL` | 接收者 ∈ 保护集 且方法 `MethodMemberSpec.mutating=True` |
| 间接 mutating 函数调用 | `SEM_LLMEXCEPT_MUTATING_CALL` | 参数含保护集变量 且函数体被推断为 mutating |

mutating 推断从公理层 `mutating=True` 标注出发，沿用户函数调用链向上传播（保守过近似）。

**运行期**（`LLMExceptFrame.verify_snapshot_integrity()`）：

body 执行后、retry 前，比对被保护变量当前值与黄金快照。若检测到篡改（编译期未捕获的间接路径），发出 `RUN_LLMEXCEPT_SNAPSHOT_VIOLATION` 警告并强制恢复快照后继续 retry。

---

## §7 意图上下文（IbIntentContext）

### 7.1 公理（与 `05_vm_specification.md` §5 对齐）

| 公理 | 内容 |
|------|------|
| **IC-1 fork 隔离** | 每次函数调用 `fork()` 创建子 context；父子互不影响 |
| **IC-2 restore 还原** | 函数返回时恢复调用者 context |
| **IC-3 llmexcept snapshot** | retry 时通过 `LLMExceptFrame` 完整恢复意图栈快照 |

### 7.2 OOP 化与语法路径

意图系统提供**双路径**，二者在帧级别打通为同一底层 `IbIntentContext`：

- **语法路径**：`@`/`@!`/`@+`/`@-` → `vm_handle_IbIntentAnnotation` / `IbIntentStackOperation` → `runtime_context._intent_ctx`
- **OOP 路径**：`intent_context.get_current()` / `.push()` / `.pop()` / `.fork()` / `.use()` → 当前帧活跃实例的 `IbIntentContext`

**核心不变量**：`_active_intent_ibobj.fields['_ctx'] is runtime_context._intent_ctx`——活跃 IBCI 实例与帧底层 Python 对象共享引用，因此两路径对当前帧的操作互可观察。

**关键 API**：

| 操作 | 维护点 |
|------|--------|
| `intent_context.use(ctx)` | fork 源对象 `_ctx`，重建活跃指针（共享引用） |
| `intent_context.clear_inherited()` | 清空持久栈，建立新的匿名活跃指针 |
| 函数调用进入 | 子帧 fork 调用者意图，建立匿名活跃指针；返回时恢复 |
| `intent_context` 参数自动激活 | 内部复用 `use_intent_context` 入口 |
| `LLMExceptFrame` retry | 以 `saved.fork()` 替换 `_intent_ctx`，同步重建活跃指针 |

### 7.3 完整设计

详见 `docs/subsystems/01_intent_system.md`。

---

## §8 多 Interpreter 隔离

### 8.1 公理（与 `05_vm_specification.md` §4 对齐）

| 公理 | 内容 |
|------|------|
| **ISO-1 独立 RuntimeContext** | 每个子 Interpreter 拥有独立 RuntimeContextImpl |
| **ISO-2 只读共享 Registry** | 共享 KernelRegistry（只读），不共享运行时实例 |
| **ISO-3 线程安全** | 子 Interpreter 在独立 `threading.Thread`；ContextVar 隔离 |

### 8.2 spawn / collect 契约

| API | 行为 |
|-----|------|
| `host.spawn_isolated(path, policy)` | 立即返回字符串 handle，不阻塞 |
| `host.collect(handle)` | 阻塞等待，返回 `Dict[str, native_value]`（仅可序列化值） |
| 二次 `collect(handle)` | 抛 `RuntimeError`（幂等保护） |
| 子 Interpreter 异常 | 在 `collect()` 时透传为 `RuntimeError` |
| `policy.collect_timeout` | `None`（默认）= 无界等待；正数（秒）= 墙钟上限，超时抛 `RuntimeError`，子线程作为 daemon 孤儿继续运行（Python 无法强杀线程） |

### 8.3 子解释器隔离路径

`spawn_isolated` 走新建独立 `IBCIEngine` 路径：子引擎持有自己的 `KernelRegistry`（类型隔离经 `SpecRegistry` 的克隆机制），与父引擎共享事件总线（观测全局）。主解释器与子解释器不共享 registry 实例。

### 8.4 合规测试

`tests/compliance/test_execution_isolation.py` 验证可观察契约，仅依赖公开 API。

### 8.5 插件可见性隔离（与 `05_vm_specification.md` §4.2 ISO-10 对齐）

插件层隔离落在 **IBCI 可见性层**，不落在 Python 模块代码层：

| 维度 | 隔离方式 | 层 |
|------|---------|-----|
| IBCI 脚本可见的插件 | 每 Engine 独立 `HostInterface`/`InterOp` 注册表，只能 `import` 本引擎登记的插件 | IBCI 层（隔离） |
| 插件 Python 实现代码 | `importlib` 进程级常规加载，`sys.modules` 全局缓存，同名"先加载者胜" | Python 层（共享） |
| 插件实例 | `create_implementation()` 每引擎新建实例，经 `BoundPlugin` 容器绑定引擎 registry 身份 | IBCI 层（隔离） |

设计立场：IBC-Inter **不插手 Python import 机制**（不装自定义 finder、不篡改 `sys.modules`）。插件模块级 Python 可变状态不被隔离--无状态是插件约定（服务于行为隔离/数据不污染/可重入），IBC-Inter 无强制力。详见 `docs/KNOWN_LIMITS.md` §十九。

---

## §9 内存模型与 GC

### 9.1 对象模型公理（与 `05_vm_specification.md` §2.1 对齐）

| 公理 | 内容 |
|------|------|
| **OM-1 对象存在性** | 一切运行时值均为 `IbObject` / `IbValue`，由 `(类型标签, payload, fields, meta)` 承载 |
| **OM-2 类型二分** | 值类型 `int/float/bool/str/None/Uncertain`（赋值=深拷贝）；引用类型 `list/dict/用户类/fn/behavior`（赋值=引用复制） |

### 9.2 GC 公理

| 公理 | 内容 |
|------|------|
| **GC-1** | 追踪式 GC，允许循环引用，不依赖引用计数 |
| **GC-2 根集合** | 全局 scope 符号 ∪ 调用栈帧局部 ∪ 所有活跃 fn 的 closure cell ∪ 所有活跃 snapshot 的 frozen_intent_ctx |
| **GC-3** | 对象不可达时方可回收，独立于 Python 引用计数 |

实现侧使用 Python GC；`IbCell` / `IbBehavior` / `IbFnCallable` 暴露 `trace_refs()` 钩子供未来自管 GC。

---

## §10 边界与服务通道

### 10.1 IILLMExecutor

`core/base/interfaces.py:IILLMExecutor`（Protocol） + `KernelRegistry.register_llm_executor(executor, token)` 在 `Engine._prepare_interpreter()` 末尾注入。`IbBehavior.call()` / `IbLLMFunction` 通过 `registry.get_llm_executor()` 合法取得 LLM 服务，无架构穿透。

### 10.2 HostService 与插件

- `HostService` 负责 spawn/collect 子 Interpreter；
- 插件通过 `IbStatefulPlugin` 协议参与状态快照（`save_plugin_state` / `restore_plugin_state`）；
- 详见 `docs/architecture/01_principles.md §三 / §七`。

### 10.3 LLM 边界（公理化通道）

公理层 `from_prompt(raw, spec)` / `__outputhint_prompt__(spec)` / `parse_value(raw)` 是 LLM 输出/输入的**唯一**通道；具体公理（`IntAxiom` / `StrAxiom` / `EnumAxiom` / `LlmCallResultAxiom` / 用户类 axiom）实现具体协议。

---

## §11 设计不变量

1. **VM 唯一执行入口**：所有 IBCI 代码执行必须经 `VMExecutor.run_body()`；handler 不可绕过调度循环递归调用。
2. **控制流数据化**：`Signal` 是控制流唯一表示；handler 内不允许 `raise ControlSignalException`。
3. **执行帧抽象**：`IExecutionFrame` 协议是帧的对外契约；不允许直接读 `RuntimeContextImpl` 内部字段实现新功能。
4. **LLM 服务通道唯一**：所有 LLM 调用必须经 `KernelRegistry.get_llm_executor()` 走 `IILLMExecutor`。
5. **公理层无运行时依赖**：`core/kernel/axioms/` 不导入 `core/runtime/`；运行时通过 `SpecRegistry.get_axiom()` 桥接。
6. **isinstance(IbXxx) 禁用**：分派一律 `isinstance(obj, IbValue) and obj.ib_class.name == "..."`；仅 `IbNone` 哨兵比较例外。
7. **快照隔离不变量**：`behavior` 表达式只读外部变量、不写外部状态；提示词组装在 dispatch 时刻完成。

---

## §12 关联文档

- VM 公理化规范（合规测试）：`docs/architecture/05_vm_specification.md`
- 类型系统设计：`docs/architecture/03_type_system.md`
- 架构原则：`docs/architecture/01_principles.md`
- 意图系统子系统设计：`docs/subsystems/01_intent_system.md`
- 已知语言限制：`docs/KNOWN_LIMITS.md`
