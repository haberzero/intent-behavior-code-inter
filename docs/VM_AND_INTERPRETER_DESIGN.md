# IBCI VM 与解释器架构（代码对齐版）

> 本文档是 IBCI 运行时（VM + 解释器）的**正式架构设计文档**，与当前代码（`core/runtime/vm/`、`core/runtime/interpreter/`、`core/runtime/objects/`）严格对齐。
> 公理化的可验证规范见 `docs/VM_SPEC.md`；实现细节备份见 `docs/ARCH_DETAILS.md`；历史演进时间线见 `docs/COMPLETED.md`。

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
│        ├─ RuntimeContextImpl — 当前执行帧（scope / intent / last_llm）  │
│        └─ VMExecutor ── CPS 调度循环（运行时唯一执行入口）              │
│             ├─ build_dispatch_table() — 43 个 AST 节点 handler         │
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
| `UnhandledSignal(signal)` | VM 顶层未消费 Signal 的边界异常（C5）|

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

### 2.3 公理（与 `VM_SPEC.md §1` 对齐）

| 公理 | 内容 |
|------|------|
| **EXEC-1 无 Python 递归** | 主路径不使用 Python 递归栈；IBCI 调用深度不受 `sys.setrecursionlimit` 限制 |
| **EXEC-2 控制流数据化** | `return` / `break` / `continue` / `throw` 通过 `Signal(kind, value)` 沿生成器返回值传播；不使用跨帧异常 |
| **EXEC-3 llmexcept 显式驱动** | llmexcept 关联通过 AST 字段建立（`IbLLMExceptionalStmt.target` / `IbFor.llmexcept_handler`）；CPS handler 内显式 yield + retry 循环 |

### 2.4 Handler 表

`core/runtime/vm/handlers.py:build_dispatch_table()` 注册 43 个 `vm_handle_IbXxx(executor, node_uid, node_data)` 生成器函数，覆盖全部 AST 节点：

| 类别 | 节点 |
|------|------|
| 字面量 / 名字 / 算子 | `IbConstant` `IbName` `IbBinOp` `IbUnaryOp` `IbBoolOp` `IbCompare` `IbIfExp` |
| 表达式 | `IbCall` `IbAttribute` `IbSubscript` `IbTuple` `IbListExpr` `IbDict` `IbSlice` `IbCastExpr` `IbFilteredExpr` |
| 语句 | `IbExprStmt` `IbAssign` `IbAugAssign` `IbIf` `IbWhile` `IbFor` `IbReturn` `IbBreak` `IbContinue` `IbPass` `IbRaise` `IbSwitch` `IbTry` `IbRetry` `IbGlobalStmt` |
| 模块 / 引入 | `IbModule` `IbImport` `IbImportFrom` |
| 声明 | `IbFunctionDef` `IbLLMFunctionDef` `IbClassDef` |
| 意图 | `IbIntentAnnotation` `IbIntentStackOperation` |
| Behavior / 闭包 | `IbBehaviorExpr` `IbBehaviorInstance` `IbLambdaExpr` |
| llmexcept | `IbLLMExceptionalStmt` |

每个 handler 是 `def vm_handle_*(...) -> Generator`：通过 `yield child_uid` 发起子求值，`return value` 完成本帧；`return Signal(...)` 触发控制流。

### 2.5 Handler 编写约束

- 不允许递归 `executor.run(...)`；子求值通过 `yield child_uid`。
- 不允许 `raise ControlSignalException`（已删除）；用 `return Signal(kind, value)`。
- 拦截 `Signal`：父 handler 用 `isinstance(res, Signal)` 判断后决定 **拦截**（循环 handler 拦截 `BREAK`/`CONTINUE`，函数帧拦截 `RETURN`，`Try` handler 拦截 `THROW` 并匹配 `except`）或 **透传**（`return res`）。

---

## §3 执行帧与上下文

### 3.1 三层"上下文"

| 名称 | 文件 | 责任 |
|------|------|------|
| `ServiceContext` | `core/runtime/interpreter/service_context.py` | 进程级服务：`llm_executor` / `capability_registry` / `host_service` / 调试器 |
| `ExecutionContextImpl` | `core/runtime/interpreter/execution_context.py` | 解释器静态部分：节点池、侧表、`registry`、`object_factory`、`runtime_context` 引用 |
| `RuntimeContextImpl` | `core/runtime/interpreter/runtime_context.py` | 当前执行帧：scope / intent_context / last_llm_result / loop_stack / retry_hint |

### 3.2 IExecutionFrame 协议

`core/base/interfaces.py:IExecutionFrame`（Step 5a 落地）：

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
    @property
    def last_llm_result(self) -> Any: ...
    def visit(self, node_uid, **kwargs): ...
```

`RuntimeContextImpl` 即此协议的实现。多 Interpreter 隔离（M4）通过为每个子解释器创建独立 `RuntimeContextImpl` 实现。

### 3.3 ContextVar 当前帧

`core/runtime/frame.py` 暴露 `get_current_frame()` / `set_current_frame()` / `reset_current_frame()`（基于 `contextvars.ContextVar`）。`Interpreter.execute_module()` 与 `IbUserFunction.call()` 入口设置当前帧；asyncio Task / 多 Interpreter 线程间天然隔离。

---

## §4 作用域与闭包

### 4.1 公理（与 `VM_SPEC.md §2.2` 对齐）

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
- **snapshot**（值捕获）：定义时刻深拷贝到独立 `IbCell`（冻结值）；`captured_intents = runtime_context.fork_intent_snapshot()`（定义时刻意图栈快照）。

### 4.4 cell 捕获 × dispatch_eligible

为保证 `IbCell` 只持有合法 `IbObject`（不持 `LLMFuture` 占位符），编译期 `BehaviorDependencyAnalyzer` 把 cell 捕获变量的 behavior 赋值强制 `dispatch_eligible=False`（`core/compiler/semantic/passes/behavior_dependency_analyzer.py`）。VM 在 `vm_handle_IbAssign` 检查此标志，cell 变量赋值不走 dispatch_eager。

---

## §5 LLM 流水线（dispatch-before-use）

### 5.1 三层并发模型

| 层 | 粒度 | 状态 |
|----|------|------|
| **L1: LLM 调用流水线** | 单个 LLM 调用 | ✅ 已实现（M5a/M5b/M5c） |
| **L2: 多 Interpreter 隔离** | 整段程序 | ✅ 已实现（M4） |
| **L3: 语言级协程 / yield** | 单个 yield 点 | ⏳ 远期愿景 |

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

### 5.4 公理（与 `VM_SPEC.md §3` 对齐）

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
           → LLMResult(success/value/is_uncertain/raw_response/retry_hint)
           → runtime_context.set_last_llm_result(result)
```

> 当前已知局限：`IbBehavior.call()` / `IbLLMFunction.call()` 通过 `executor.invoke_behavior` / `invoke_llm_function` 走的是同步 Python 调用，不在 CPS 循环内。这是 P1 项，详见 `docs/NEXT_STEPS.md` NS-1。

---

## §6 llmexcept：影子执行驱动模式

### 6.1 模型概述

llmexcept 不再用 Python 异常实现，改用**快照隔离 + 影子执行驱动 + 标志位轮询**：

```text
visit_IbLLMExceptionalStmt
  ├─ save_llm_except_state()                 — 创建 LLMExceptFrame，保存变量/意图/loop 快照
  └─ while frame.should_continue_retrying():
       ├─ frame.restore_snapshot()
       ├─ runtime_context.set_last_llm_result(None)
       ├─ execution_context.visit(target_uid)
       │     └─ 内部 LLM 调用 → LLMResult.is_uncertain
       │     └─ runtime_context.set_last_llm_result(result)
       ├─ if not last_llm_result.is_uncertain: break
       └─ else: 执行 body 块（可含 IbRetry）→ frame.increment_retry()
```

### 6.2 关键组件

| 组件 | 文件 | 责任 |
|------|------|------|
| `LLMExceptFrame` | `core/runtime/interpreter/llm_except_frame.py` | 现场快照（变量、意图栈、loop 栈、retry hint） |
| `LLMExceptFrameStack` | 同上 | 嵌套 llmexcept 块栈管理 |
| `IbLLMUncertain` | `core/runtime/objects/kernel.py` | 不确定结果哨兵对象（赋值占位符） |
| `LLMResult` | `core/runtime/interpreter/llm_result.py` | LLM 调用结果数据对象（`is_uncertain` 旗标） |

### 6.3 快照内容

- 可序列化变量（IbNone / IbInteger / IbFloat / IbString / IbList / IbTuple / IbDict）深克隆；
- `intent_context.fork()` 产生独立意图上下文快照；
- `_loop_stack` 深拷贝；
- `loop_resume`（for 循环断点恢复映射）**不重置**（设计决定）；
- 函数 / behavior / NativeObject 等引用类型显式排除。

### 6.4 完整规范

详见 `docs/ARCH_DETAILS.md §一` 与 `docs/INTENT_SYSTEM_DESIGN.md §4.6`。

---

## §7 意图上下文（IbIntentContext）

### 7.1 公理（与 `VM_SPEC.md §5` 对齐）

| 公理 | 内容 |
|------|------|
| **IC-1 fork 隔离** | 每次函数调用 `fork()` 创建子 context；父子互不影响 |
| **IC-2 restore 还原** | 函数返回时恢复调用者 context |
| **IC-3 llmexcept snapshot** | retry 时通过 `LLMExceptFrame` 完整恢复意图栈快照 |

### 7.2 OOP 化与语法路径

意图系统提供**双路径**：
- 语法路径：`@`/`@!`/`@+`/`@-` → `vm_handle_IbIntentAnnotation` / `IbIntentStackOperation` → `runtime_context._intent_ctx`；
- OOP 路径：`intent_context.get_current()` / `.push()` / `.pop()` / `.fork()` → `IbIntentContext` 实例。

两路径操作同一底层 `_intent_ctx`，但代码逻辑独立。完整 OOP 化（实例作为参数、函数默认 ctx 等）尚未完成（见 `docs/PENDING_TASKS.md §四`）。

### 7.3 完整设计

详见 `docs/INTENT_SYSTEM_DESIGN.md`。

---

## §8 多 Interpreter 隔离（M4）

### 8.1 公理（与 `VM_SPEC.md §4` 对齐）

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

### 8.3 KernelRegistry.clone()

子解释器初始化路径若走 `clone()`（IsolationLevel != NONE 的旧路径），`_classes` / `_boxers` / `_metadata_registry` / `_builtin_instances` / `_llm_executor` 等字段均传播；`_int_cache` 故意不拷（性能缓存而非正确性）。M4 的 `spawn_isolated` 走新建独立 `IBCIEngine` 路径，不经 clone。

### 8.4 合规测试

`tests/compliance/test_execution_isolation.py` 验证可观察契约，仅依赖公开 API。

---

## §9 内存模型与 GC

### 9.1 对象模型公理（与 `VM_SPEC.md §2.1` 对齐）

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

实现侧目前使用 Python GC；`IbCell` / `IbBehavior` / `IbFnCallable` 暴露 `trace_refs()` 钩子供未来自管 GC。

---

## §10 边界与服务通道

### 10.1 IILLMExecutor

`core/base/interfaces.py:IILLMExecutor`（Protocol） + `KernelRegistry.register_llm_executor(executor, token)` 在 `Engine._prepare_interpreter()` 末尾注入。`IbBehavior.call()` / `IbLLMFunction` 通过 `registry.get_llm_executor()` 合法取得 LLM 服务，无架构穿透。

### 10.2 HostService 与插件

- `HostService` 负责 spawn/collect 子 Interpreter（M4）；
- 插件通过 `IbStatefulPlugin` 协议参与状态快照（`save_plugin_state` / `restore_plugin_state`）；
- 详见 `docs/ARCHITECTURE_PRINCIPLES.md §三 / §七`。

### 10.3 LLM 边界（公理化通道）

公理层 `from_prompt(raw, spec)` / `__outputhint_prompt__(spec)` / `parse_value(raw)` 是 LLM 输出/输入的**唯一**通道；具体公理（`IntAxiom` / `StrAxiom` / `EnumAxiom` / `LlmCallResultAxiom` / 用户类 axiom）实现具体协议。

---

## §11 设计不变量

1. **VM 唯一执行入口**：所有 IBCI 代码执行必须经 `VMExecutor.run_body()`；handler 不可绕过调度循环递归调用。
2. **控制流数据化**：`Signal` 是控制流唯一表示；handler 内不允许 `raise ControlSignalException`（类已删除）。
3. **执行帧抽象**：`IExecutionFrame` 协议是帧的对外契约；不允许直接读 `RuntimeContextImpl` 内部字段实现新功能。
4. **LLM 服务通道唯一**：所有 LLM 调用必须经 `KernelRegistry.get_llm_executor()` 走 `IILLMExecutor`。
5. **公理层无运行时依赖**：`core/kernel/axioms/` 不导入 `core/runtime/`；运行时通过 `SpecRegistry.get_axiom()` 桥接。
6. **isinstance(IbXxx) 禁用**：分派一律 `isinstance(obj, IbValue) and obj.ib_class.name == "..."`；仅 `IbNone` 哨兵比较例外。
7. **快照隔离不变量**：`behavior` 表达式只读外部变量、不写外部状态；提示词组装在 dispatch 时刻完成。

---

## §12 当前状态（2026-05-08 锚点）

| 主线 | 状态 |
|------|------|
| M1–M5（类型系统） | ✅ 完成 |
| M3a–M3d（CPS 调度循环） | ✅ 完成 |
| M5a/M5b/M5c（DDG + LLMScheduler + dispatch-before-use） | ✅ 完成 |
| M4（多 Interpreter 隔离） | ✅ 完成 |
| M6（合规测试套件） | ✅ 完成 |
| Phase 1–5 编译器深度清洁（C5–C14） | ✅ 完成 |
| L3 语言级协程 / yield | ⏳ 远期愿景 |

**已知开放议题**（详见 `docs/NEXT_STEPS.md` 与 `docs/PENDING_TASKS.md`）：

- **P1**：`IbBehavior.call()` / `IbLLMFunction.call()` 走同步 Python 调用，未进入 CPS 循环；
- **P1**：`lambda`/`snapshot` 跨帧 / 跨线程 `_execution_context` 边界（`builtins.py:730,930`）；
- **P1**：意图系统语法路径与 OOP 路径双轨（共享底层但逻辑独立）；
- **P2**：llmexcept 快照恢复 `merge()` vs 直接替换语义对齐。

---

## §13 关联文档

- VM 正式规范（公理化、合规测试）：`docs/VM_SPEC.md`
- 类型系统设计（代码对齐版）：`docs/TYPE_SYSTEM_DESIGN.md`
- 架构原则：`docs/ARCHITECTURE_PRINCIPLES.md`
- 实现细节备份（llmexcept / MOCK / 类型系统迁移历史等）：`docs/ARCH_DETAILS.md`
- 意图系统设计：`docs/INTENT_SYSTEM_DESIGN.md`
- 已知语言限制：`docs/KNOWN_LIMITS.md`
- 历史时间线：`docs/COMPLETED.md`
