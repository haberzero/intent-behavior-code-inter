# IBCI VM 与解释器架构设计说明（当前正式版）

> 本文档是 **当前代码状态** 下的 VM 与解释器架构权威设计参考。  
> VM 正式规范层（含合规测试套件）：`docs/VM_SPEC.md`  
> VM 演进路线历史（各 Milestone 设计规范）：`docs/VM_EVOLUTION_PLAN.md`  
> 架构细节备份（llmexcept/MOCK/IbBehavior/MetadataRegistry 等具体实现细节）：`docs/ARCH_DETAILS.md`  
> 演进落地记录：`docs/COMPLETED.md §六–§二十二`  
>
> **最后更新**：2026-05-08（VM 主路径全部 CPS 化，M1–M6 + 编译器深度清洁全部完成；测试基线 1180 passed）

---

## 一、执行模型

### 1.1 VMExecutor CPS 调度循环（M3a–M3d 完成）

IBCI 主执行路径是**显式帧栈 + CPS（Continuation-Passing Style）调度循环**：

```
VMExecutor._drive_loop()
    while frame_stack:
        task = frame_stack.top()
        child_uid = task.generator.send(pending_value)
        if isinstance(child_uid, str):
            frame_stack.push(make_task(child_uid))   # 子节点压栈
        elif isinstance(child_uid, Signal):
            bubble up or handle
        # StopIteration → pop，把值交给父任务
```

核心特性：
- **公理 EXEC-1（无 Python 递归）**：主执行路径不使用 Python 递归栈，IBCI 调用深度不受 `sys.setrecursionlimit` 限制。
- **公理 EXEC-2（控制流数据化）**：`return`/`break`/`continue`/`throw` 全部以 `Signal(kind, value)` 数据对象传播，不使用 Python 异常跨帧传递。`ControlSignalException` 类已彻底从代码库删除（仅余 `UnhandledSignal` 作为 VM 顶层未消费 Signal 的边界异常）。

**代码位置**：`core/runtime/vm/vm_executor.py`、`core/runtime/vm/task.py`（Signal 定义）

### 1.2 CPS Handler 覆盖

编译器深度清洁（Phase 1–5，C5–C14）完成后，**43 个 AST 节点类型全部覆盖 CPS handler**，所有显式 `fallback_visit()` 调用归零。节点分类：

| 分类 | 节点类型 | 状态 |
|------|---------|------|
| 语句 | `IbModule`、`IbIf`、`IbWhile`、`IbFor`、`IbReturn`、`IbBreak`、`IbContinue`、`IbRaise`、`IbAssign`、`IbAugAssign`、`IbDelete`、`IbPass`、`IbTry`、`IbExceptHandler`、`IbRetry`、`IbCase`、`IbLLMExceptionalStmt` | ✅ CPS |
| 表达式 | `IbName`、`IbConst`、`IbBinOp`、`IbUnaryOp`、`IbCompare`、`IbBoolOp`、`IbCall`、`IbAttribute`、`IbSubscript`、`IbTuple`、`IbList`、`IbDict`、`IbSlice`、`IbFString`、`IbBehaviorExpr`、`IbTypeAnnotatedExpr`、`IbIntentInfo` | ✅ CPS |
| 表达式 | `IbLambdaExpr`、`IbBehaviorInstance` | ✅ CPS（C8 清理）|
| 声明 | `IbFunctionDef`、`IbLLMFunctionDef`、`IbClassDef`、`IbImport`、`IbImportFrom` | ✅ CPS |

### 1.3 组件分工

```
core/runtime/
├── interpreter/
│   ├── interpreter.py         # 装配层：上下文、模块、作用域、服务注入
│   ├── execution_context.py   # 执行上下文状态容器（持有所有池和回调）
│   └── runtime_context.py     # 运行时上下文（意图栈、LLM结果、循环上下文）
├── vm/
│   ├── vm_executor.py         # CPS 调度主循环（VMExecutor）
│   ├── task.py                # VMTask + Signal 数据类
│   └── handlers.py            # 各 AST 节点的 CPS handler 实现
└── objects/
    ├── kernel.py              # IbValue 基类 + IbClass + IbNone 等核心对象
    └── builtins.py            # IbInteger/IbList/IbDeferred/IbBehavior 等实现
```

**Interpreter 与 VMExecutor 的分工**：
- `Interpreter`：负责初始化、装配，将所有必要的依赖注入到 `ExecutionContextImpl`
- `VMExecutor`：负责驱动 CPS 调度循环，不直接持有业务依赖
- `handlers.py`：各节点的 CPS 语义实现，通过 `execution_context` 访问注册表/作用域等

---

## 二、作用域与闭包

### 2.1 词法作用域实现

`ScopeImpl._parent` 链实现词法嵌套（公理 SC-1）：
- 每个作用域有词法父作用域，构成树形结构，全局作用域是树根
- 变量查找从当前作用域向上游历父链

### 2.2 变量分类

| 类别 | 说明 | 存储 |
|------|------|------|
| 本地变量（Local） | 函数体内声明且未被内层函数引用 | 直接存于 ScopeImpl 符号表 |
| Cell 变量（Cell） | 函数体内声明且被至少一个内层 lambda/snapshot 引用 | 通过 `IbCell` 间接存储 |
| 自由变量（Free） | 在函数体内引用但未在此函数体内声明 | 通过 closure 字典中的 IbCell 访问 |

### 2.3 IbCell 原语

**位置**：`core/runtime/objects/cell.py`

`IbCell` 是独立于任何 `ScopeImpl` 的堆对象：
- 纯 VM 容器（非 `IbObject`）
- 接口：`get()`/`set(v)`/`is_empty()`/`trace_refs()`
- 身份语义：`__eq__`/`__hash__` 基于 `id()`
- `IbCell.EMPTY` 哨兵：读取未初始化单元时抛 `RuntimeError`

**Cell 提升时机**：编译器语义分析阶段，发现被内层 lambda/snapshot 引用的变量时，通过 `ScopeImpl.promote_to_cell()` 将其提升为 Cell 变量。

### 2.4 fn/lambda/snapshot 闭包语义

- 内层 lambda/snapshot 创建时，所有自由变量的 `IbCell` 引用写入该函数对象的 `closure: Dict[sym_uid, (name, IbCell)]` 字典
- 此后函数对象持有 Cell 引用，与外层 ScopeImpl 生命周期解耦
- `lambda`（引用捕获）和 `snapshot`（值拷贝捕获）在闭包语义上的区别：
  - `lambda`：通过 Cell 共享，读最新值
  - `snapshot`：创建时拷贝当前值，完全自包含
- 两者在**意图栈**上的差异详见 `docs/INTENT_SYSTEM_DESIGN.md §4.7`

---

## 三、LLM 数据流模型

### 3.1 DDG 编译期分析（M5a）

编译阶段，`BehaviorDependencyAnalyzer`（Pass 5）分析 `IbBehaviorExpr` 节点间的数据依赖关系：

- `llm_deps: List[IbBehaviorExpr]`：此 behavior 直接依赖的其他 behavior 节点
- `dispatch_eligible: bool`：若依赖图为 DAG（无环且无未知依赖），可并发 dispatch

**强制 `dispatch_eligible = False` 的情况**：
- 赋值目标是 Cell 变量（`IbCell` 不允许持有 `LLMFuture` 占位符）
- 节点处于 llmexcept 保护下
- 目标变量是前序 behavior 输出的插值依赖

### 3.2 LLMScheduler + LLMFuture（M5b/M5c）

**公理 LLM-1（dispatch eager）**：`dispatch_eligible=True` 时，VM 在赋值点立即提交 LLM HTTP 调用到 `ThreadPoolExecutor`，返回 `LLMFuture` 占位符写入符号表。

**公理 LLM-2（lazy resolve）**：读取点（`vm_handle_IbName`）检测到 `LLMFuture` 时，调用 `resolve()` 阻塞等待并将真实值写回符号表。

**公理 LLM-3（确定性输出）**：并发 dispatch 不改变程序输出顺序——`print` 调用顺序遵从语句语义顺序，而非 dispatch 完成顺序。

**代码位置**：`core/runtime/interpreter/llm_executor.py`

### 3.3 LLMResult 不确定性信号

LLM 调用结果通过 `LLMResult` 传递（`core/runtime/interpreter/llm_result.py`）：

```python
@dataclass
class LLMResult:
    success: bool
    value: Optional[IbObject]   # 成功时的结果对象
    is_uncertain: bool           # True 表示应触发 llmexcept
    raw_response: str            # LLM 原始响应
    retry_hint: Optional[str]   # 重试提示词
```

`is_uncertain=True` 触发场景：
1. MOCK 哨兵（`MOCK:FAIL`/`MOCK:REPAIR`）被检测
2. 公理层 `from_prompt()` 解析失败（返回 `(False, retry_hint_str)`）
3. LLM 调用底层失败

---

## 四、llmexcept 与快照隔离

### 4.1 影子执行驱动模式

llmexcept 经历三个演进阶段（详见 `docs/ARCH_DETAILS.md §一`），当前为第三阶段**影子执行驱动模式**：

```
vm_handle_IbLLMExceptionalStmt
  │
  ├── 创建 LLMExceptFrame，保存变量/意图/循环上下文快照
  │
  └── while frame.should_continue_retrying():
        ├── frame.restore_snapshot()    # 恢复快照（保证重试输入一致）
        ├── 执行 target_uid（目标语句）  # 内部 LLM 调用 → LLMResult
        │
        ├── [is_uncertain=False] → break，正常退出
        │
        └── [is_uncertain=True] → 执行 llmexcept body 块
              └── visit_IbRetry → 设置 retry_hint + restore_snapshot
```

- **不存在**旧的 `LLMUncertaintyError` 异常捕获
- **不存在**旧的 `_with_unified_fallback` 包装器
- **不存在**旧的 `node_protection` 侧表重定向（C11/P3 已彻底删除）

### 4.2 LLMExceptFrame 快照内容

`LLMExceptFrame`（`core/runtime/interpreter/llm_except_frame.py`）保存：

| 字段 | 内容 |
|------|------|
| `saved_vars` | 可序列化类型变量快照（基础值类型 + list/tuple/dict）|
| `saved_intent_ctx` | `IbIntentContext.fork()` 产生的意图上下文独立快照 |
| `saved_loop_context` | 循环上下文列表（`_loop_stack` 的深拷贝）|
| `saved_retry_hint` | 上次保存的重试提示词 |
| `max_retry` | 最大重试次数（`llm_provider.get_retry()`）|
| `last_result` | 最后一次 LLM 调用的 `LLMResult` |

### 4.3 快照隔离的设计理念

快照隔离的概念框架类比数据库 SI（Snapshot Isolation）：

```
数据库 SI:                         llmexcept 快照:
BEGIN TRANSACTION                  LLM 语句进入执行
  read from snapshot                 从快照读取变量/意图栈
  on success: COMMIT                 成功：commit 到目标变量
  on failure: ROLLBACK               失败：restore_snapshot + 向外传播
```

此设计使 llmexcept 与 LLM 并发无关——每个 LLM 语句独立快照，多个快照同时运行不产生竞争条件。

---

## 五、意图上下文在执行模型中的角色

详细设计见 `docs/INTENT_SYSTEM_DESIGN.md`，这里记录执行模型视角的关键集成点：

### 5.1 意图上下文的存储位置

```
RuntimeContextImpl
└── _intent_ctx: IbIntentContext   # 统一持有四类意图状态
    ├── 持久意图栈（@+ / @-）
    ├── 一次性涂抹意图（@）
    ├── 排他意图槽（@!）
    └── 全局意图（Engine 级）
```

### 5.2 函数调用时的意图上下文传递

每次函数调用（`IbUserFunction.call()` / `IbLLMFunction.call()`）执行 `fork()`：
- 被调用函数在独立的意图上下文副本上操作
- 函数内对意图系统的操作**不泄漏**给调用者（拷贝传递语义）
- 函数返回后，副本被丢弃，调用者上下文不变

### 5.3 lambda vs snapshot 的意图栈差异

```python
# handlers.py / runtime factory
capture_mode = self.get_side_table("node_capture_mode", node_uid)
captured_intents = (
    None                               # lambda：不捕获意图，调用时使用当前生效意图
    if capture_mode == "lambda"
    else self.runtime_context.fork_intent_snapshot()  # snapshot：冻结当前意图快照
)
```

---

## 六、多 Interpreter 并发（M4 Layer 2）

### 6.1 执行隔离原则

- **公理 ISO-1**：每个子 Interpreter 拥有独立的 `RuntimeContextImpl`，不共享任何可变状态
- **公理 ISO-2**：子 Interpreter 与主 Interpreter 共享 `KernelRegistry`（只读）
- **公理 ISO-3**：子 Interpreter 在独立线程中运行，`ContextVar` 线程独立

### 6.2 spawn/collect 接口

- `spawn_isolated(path, policy)` → 立即返回 handle（非阻塞）
- `collect(handle)` → 阻塞等待，返回可序列化值的 Dict（幂等保护：同一 handle 重复调用抛 `RuntimeError`）

### 6.3 VMExecutor 注入策略（C13）

`ExecutionContextImpl.vm_executor` 属性由 `Interpreter` 在构造完成后注入，`IbUserFunction.call()` 直接读取此属性调用 `vm.run_body(body)`。这消除了旧的三级 `getattr` 查找链，也是 M4 多 Interpreter 并发的先决条件（无 silent fallback 保证）。

---

## 七、IbLLMUncertain 哨兵

`IbLLMUncertain`（继承 `IbValue`，`core/runtime/objects/kernel.py`）是 LLM 调用不确定时的变量赋值占位符：

- `visit_IbAssign` 检测到 `last_llm_result.is_uncertain=True` 时，将目标变量赋值为 `IbLLMUncertain`（保证变量已定义，不跳过赋值）
- 在布尔上下文中返回 `False`（`to_bool()` = 0）
- 支持 `(type) uncertain_val` 强制类型转换
- `str + llm_uncertain` 的拼接：当前保留过渡兼容（返回 `"..." + "uncertain"`），后续将收口为显式错误路径（见 `docs/CURRENT_TASKS.md §三`）

单例注册：`initialize_builtin_classes()` 中通过 `registry.register_llm_uncertain()` 注册，运行时通过 `registry.get_llm_uncertain()` 访问。

---

## 八、编译器架构简述

编译器采用**多 Pass 顺序分析**，每个 Pass 产出下一 Pass 的输入：

```
Pass 1: 模块级符号收集（保证向前引用）
Pass 2: 模块导入分析（ModuleScheduler）
Pass 3: 语义分析（类型检查、意图标注、作用域分析）
Pass 4: 符号解析完成
Pass 5: BehaviorDependencyAnalyzer（DDG 编译期分析）
输出: ImmutableArtifact（可序列化的 AST + 侧表）
```

**关键侧表**（side tables）：
- `node_to_loc`：节点 → 源码位置
- `node_capture_mode`：lambda/snapshot 节点的捕获模式
- `cell_captured_symbols`：每个函数的 Cell 符号集合
- `node_is_callable_instance`：可调用实例节点标记（原 `node_is_deferred` 已重命名）

---

## 九、合规测试套件

```
tests/compliance/
├── test_execution_isolation.py  # §4 多 Interpreter 隔离（19 测试）
├── test_concurrent_llm.py       # §3 LLM dispatch-before-use（9 测试）
└── test_memory_model.py         # §2 内存模型（18 测试）
```

运行：`python3 -m pytest tests/compliance/ -v`

所有合规测试仅依赖 `core.engine.IBCIEngine` 公开 API，不依赖私有属性，保证跨实现可移植性。

---

## 十、关联文档

| 文档 | 内容 |
|------|------|
| `docs/VM_SPEC.md` | VM 正式规范层（公理化定义 + 合规测试说明）|
| `docs/VM_EVOLUTION_PLAN.md` | VM 各 Milestone 演进规划与历史状态 |
| `docs/ARCH_DETAILS.md` | 具体实现细节（llmexcept/MOCK/IbBehavior 等）|
| `docs/INTENT_SYSTEM_DESIGN.md` | 意图注释系统完整设计说明 |
| `docs/FN_LAMBDA_SYNTAX_REDESIGN.md` | fn/lambda/snapshot 语法重设计决策 |
| `docs/COMPLETED.md §六–§二十二` | VM 各阶段落地记录 |
