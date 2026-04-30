# IBCI VM 规范（VM_SPEC.md）

> **文档性质**：本文档是 IBCI 虚拟机的**正式规范层定义**，与 Python 宿主实现隔离。  
> 规范目标：使本文档连同 `tests/compliance/` 合规测试套件成为跨宿主实现（Python/Rust/Go/C++ 等）的合规标准。  
> **基准状态**（2026-04-29）：Python 宿主实现（`core/`）全部符合本规范；1011 测试通过（D1/D2/D3 fn/lambda callable 签名标注全链路落地后）。  
> **关联文档**：`docs/VM_EVOLUTION_PLAN.md`（里程碑演进规划）、`docs/PENDING_TASKS_VM.md`（详细设计与任务清单）。

---

## §1 执行模型（Execution Model）

### §1.1 CPS 调度循环

IBCI VM 使用**显式帧栈 + CPS（Continuation-Passing Style）调度循环**执行 AST（`core/runtime/vm/vm_executor.py`）：

```
while frame_stack:
    task = frame_stack.top()
    child_uid = task.generator.send(pending_value)
    if isinstance(child_uid, str):
        frame_stack.push(make_task(child_uid))
    # or:
    # StopIteration → pop, deliver value to parent
    # Exception     → pop, throw to parent
```

**公理 EXEC-1（无 Python 递归）**：主执行路径（`VMExecutor._drive_loop`）不使用 Python 递归栈；IBCI 调用深度不受 `sys.setrecursionlimit` 限制。

**公理 EXEC-2（控制流数据化）**：控制流信号（`return`/`break`/`continue`/`throw`）以数据对象 `Signal(kind, value)` 在帧栈间传播，不使用 Python 异常跨帧传递（C6 完成后）。外部边界（帧栈空仍持有 Signal）以 `UnhandledSignal` 透传给调用方处理。

**公理 EXEC-3（llmexcept 显式驱动）**：llmexcept 关联通过 AST 字段在编译期建立——正则情形通过 `IbLLMExceptionalStmt.target` 字段引用前一语句节点，并在 body 中**替换**该节点；条件驱动 for 循环情形通过 `IbFor.llmexcept_handler` 字段直接引用 handler。运行时 `vm_handle_IbLLMExceptionalStmt` 显式 yield target_uid 驱动 target 求值并管理 retry 循环；`vm_handle_IbFor` 在条件求值返回 uncertain 时内联执行 handler body。**不存在**侧表驱动的隐式重定向机制（旧 `node_protection` + `_apply_protection_redirect` 已在 C11/P3 彻底删除）。

**已知限制**：无——所有节点类型均已 CPS 化（编译器深度清洁 Phase 1–5 完成）。`IbLambdaExpr` 和 `IbBehaviorInstance` 在 Phase 3（C8）已彻底消除 fallback 路径。

---

### §1.2 节点类型分类

| 分类 | 节点类型 | CPS 状态 |
|------|---------|---------|
| 语句 | `IbModule` `IbIf` `IbWhile` `IbFor` `IbReturn` `IbBreak` `IbContinue` `IbRaise` `IbAssign` `IbAugAssign` `IbDelete` `IbPass` `IbTry` `IbExceptHandler` `IbRetry` `IbCase` | ✅ CPS handler |
| 语句 | `IbLLMExceptionalStmt` | ✅ CPS handler（M3c） |
| 表达式 | `IbName` `IbConst` `IbBinOp` `IbUnaryOp` `IbCompare` `IbBoolOp` `IbCall` `IbAttribute` `IbSubscript` `IbTuple` `IbList` `IbDict` `IbSlice` `IbFString` | ✅ CPS handler |
| 表达式 | `IbBehaviorExpr` | ✅ CPS handler（M5c） |
| 表达式 | `IbTypeAnnotatedExpr` `IbIntentInfo` | ✅ CPS handler |
| 表达式 | `IbLambdaExpr` `IbBehaviorInstance` | ✅ CPS handler（C8 已清理） |
| 声明 | `IbFunctionDef` `IbLLMFunctionDef` `IbClassDef` `IbImport` `IbImportFrom` | ✅ CPS handler |

---

## §2 内存模型（Memory Model）

### §2.1 对象模型公理

**公理 OM-1（对象存在性）**：IBCI 程序中的一切运行时值都是"IBCI 对象"（IbObject），由 `(类型标签, 有效载荷, 元数据)` 三元组构成。

**公理 OM-2（类型二分）**：
- **值类型（Value）**：`int`, `float`, `bool`, `str`, `None`, `Uncertain`。赋值语义等价于深拷贝，不具有可变身份。
- **引用类型（Ref）**：`list`, `dict`, 用户类实例, `fn`, `behavior`。赋值语义为引用复制，具有对象身份。

### §2.2 作用域与变量分类

**公理 SC-1（词法嵌套）**：每个作用域有词法父作用域，构成树；全局作用域是树根。

**公理 SC-2（变量分类）**：
- **本地变量（Local）**：函数体内声明且未被内层函数引用。
- **Cell 变量（Cell）**：函数体内声明且被至少一个内层 lambda/snapshot 引用；通过 `IbCell` 间接存储。
- **自由变量（Free）**：在函数体内引用但未在此函数体内声明。

**公理 SC-3（Cell 语义）**：Cell 变量通过 `IbCell` 间接存储。`IbCell` 是独立于任何 `ScopeImpl` 的堆对象，包含字段 `value`。对 Cell 变量的读写是对 `IbCell.value` 的读写。

**公理 SC-4（自由变量捕获）**：嵌套函数/lambda 被创建时，所有自由变量的 `IbCell` 引用写入该函数对象的 `closure` 字典；此后函数对象持有 Cell 引用，与外层 ScopeImpl 生命周期解耦。

### §2.3 生命周期公理

**公理 LT-1（作用域生命周期）**：ScopeImpl 的设计生命周期为对应函数调用持续时间。

**公理 LT-2（Cell 延长生命周期）**：Cell 变量的 `IbCell` 生命周期由 closure 字典决定；只要有 fn 对象持有 Cell 引用，Cell 即活跃。

**公理 LT-3（snapshot 自包含性）**：`snapshot` 类型的 fn 对象完全自包含，不依赖外部作用域或意图上下文的生命周期。

**公理 LT-4（IntentContext 生命周期）**：`IbIntentContext` 通过 `fork()` 在函数调用时隔离，函数返回时恢复调用者的 context。

### §2.4 GC 模型

**公理 GC-1（追踪式 GC）**：IBCI 规定使用追踪式 GC（Tracing GC），不依赖引用计数；允许循环引用。

**公理 GC-2（根集合）**：GC 根集合 = 全局作用域符号值 ∪ 活跃调用栈帧局部变量 ∪ 所有活跃 fn 对象的 `closure` 字典中的 Cell 值 ∪ 所有活跃 snapshot 对象持有的 `frozen_intent_ctx`。

**公理 GC-3（回收条件）**：对象当且仅当从根集合不可达时可被回收，不依赖 Python 的引用计数机制。

---

## §3 LLM 数据流模型（LLM Dataflow Model）

### §3.1 DDG 编译期分析（M5a）

编译阶段（`BehaviorDependencyAnalyzer` Pass 5）分析 `IbBehaviorExpr` 节点之间的数据依赖：

- `llm_deps: List[IbBehaviorExpr]`：此 behavior 直接依赖的其他 behavior 节点列表。
- `dispatch_eligible: bool`：若依赖图为 DAG（无环且无未知依赖），标注为 True（可并发 dispatch）；否则 False（串行同步路径）。

**规则**：以下情况强制 `dispatch_eligible = False`：
- 目标变量是插值依赖（前序 behavior 的输出是当前 behavior 的 $var 输入）
- 赋值目标是 Cell 变量（IbCell 不允许持有 LLMFuture 占位符，见 `docs/COMPLETED.md` §二十一 C14 条目）
- 节点处于 llmexcept 保护下（snapshot 隔离约束）

### §3.2 LLMScheduler + LLMFuture（M5b）

**公理 LLM-1（dispatch_eager）**：`dispatch_eligible=True` 时，VM 在赋值点立即调用 `LLMScheduler.dispatch_eager()`，提交 LLM HTTP 调用到 `ThreadPoolExecutor`，返回 `LLMFuture` 占位符写入符号表（`ScopeImpl.define_raw()`）。

**公理 LLM-2（lazy resolve）**：读取点（`vm_handle_IbName`）检测到 `LLMFuture` 时，调用 `resolve()` 阻塞等待 LLM 完成，将真实 `IbObject` 写回符号表，后续读取直接命中 IbObject（O(1)）。

**公理 LLM-3（确定性输出）**：并发 dispatch 不改变程序的输出确定性——程序输出顺序遵从语句语义顺序（print 调用顺序），而非 dispatch 完成顺序。

### §3.3 合规测试

`tests/compliance/test_concurrent_llm.py` 验证以上公理的可观察行为，以 MOCK LLM driver 作为后端，不依赖外部网络。

---

## §4 多 Interpreter 并发（Layer 2 Execution Isolation）

### §4.1 执行隔离公理

**公理 ISO-1（独立 RuntimeContext）**：每个子 Interpreter 拥有独立的 `RuntimeContextImpl` 实例，不与主 Interpreter 或其他子 Interpreter 共享任何可变状态。

**公理 ISO-2（只读共享 Registry）**：子 Interpreter 与主 Interpreter 共享 `KernelRegistry`（只读），不共享运行时对象实例。

**公理 ISO-3（线程安全）**：子 Interpreter 在独立线程（`threading.Thread`）中运行；`ContextVar` 在线程中独立，不发生竞争。

### §4.2 spawn/collect 契约

**公理 SC-1（spawn 非阻塞）**：`spawn_isolated(path, policy)` 立即返回字符串 handle，不等待子 Interpreter 完成。

**公理 SC-2（collect 提取）**：`collect(handle)` 阻塞等待子 Interpreter 完成并返回其用户变量字典 `Dict[str, native_value]`。

**公理 SC-3（collect 幂等保护）**：对同一 handle 重复调用 `collect()` 抛出 `RuntimeError`。

**公理 SC-4（collect 类型过滤）**：collect 仅返回可序列化的值类型（str/int/float/bool/list/dict）；函数对象、behavior 对象、内置符号不包含在结果中。

**公理 SC-5（错误传播）**：子 Interpreter 运行期或编译期抛出的异常，在 `collect()` 时传播为 `RuntimeError`。

### §4.3 合规测试

`tests/compliance/test_execution_isolation.py` 验证以上公理的可观察行为，独立可运行。

---

## §5 意图上下文模型（IbIntentContext Model）

### §5.1 公理

**公理 IC-1（fork 隔离）**：每次函数调用时 `IbIntentContext.fork()` 创建子 context；子 context 从父 context 继承意图栈快照，后续修改互不影响。

**公理 IC-2（restore 还原）**：函数返回时恢复调用者的 context，不论函数体内对意图栈的任何修改。

**公理 IC-3（llmexcept snapshot）**：`llmexcept` 框架在执行前对 context 进行完整快照（scope + intent + last_result），retry 时恢复该快照，使重试语义完整隔离。

---

## §6 合规测试套件（Compliance Test Suite）

```
tests/compliance/
├── __init__.py              — 套件说明文档
├── test_execution_isolation.py  — §4 多 Interpreter 隔离（19 测试）
├── test_concurrent_llm.py       — §3 LLM dispatch-before-use（9 测试）
└── test_memory_model.py         — §2 内存模型（18 测试）
```

**运行方式**（独立验证）：
```bash
python3 -m pytest tests/compliance/ -v
```

**使用限制**：所有合规测试仅依赖 `core.engine.IBCIEngine` 公开 API 与标准 Python 库（`os`, `tempfile`, `pytest`）。不依赖任何以 `_` 开头的私有属性（此约束确保跨实现可移植性）。

---

## §7 与现有文档的对应关系

| 本文档章节 | `VM_EVOLUTION_PLAN.md` Milestone | `PENDING_TASKS_VM.md` 章节 |
|-----------|----------------------------------|--------------------------|
| §1 执行模型 | M3a/b/c/d | §一（执行模型）、§三 层次 2 |
| §2.1 对象模型 | — | §十（OM 公理） |
| §2.2 作用域 | M1/M2 | §十（SC 公理）、§十.2/3 |
| §2.3 生命周期 | M1/M2 | §十（LT 公理）、§十.3 |
| §2.4 GC | M2 | §十（GC 公理）、§十.4 |
| §3 LLM 数据流 | M5a/b/c | §五（LLM 流水线）、§五.5–5.6 |
| §4 多 Interpreter | M4 | §五（执行隔离）、§七 7.2 |
| §5 意图上下文 | Step 6 | §一（意图上下文）|
| §6 合规测试 | M6 | — |

---

*本文档与 `tests/compliance/` 构成 IBCI VM 的可验证规范。每次合规测试套件全部通过即代表当前 Python 宿主实现符合本规范。*
