# IBC-Inter VM 与解释器架构正式设计说明

> 本文档覆盖 IBC-Inter（IBCI）虚拟机与解释器的完整架构，包含执行模型、关键子系统、
> LLM 执行管道、llmexcept 快照隔离机制、意图系统，以及三层并发演进路径。
>
> **最后更新**：2026-05-09（文档首次正式化；Steps 1-8 全部完成；690 测试通过）

---

## 目录

1. [架构哲学与边界划分](#1-架构哲学与边界划分)
2. [核心组件概览](#2-核心组件概览)
3. [KernelRegistry：类型系统中枢](#3-kernelregistry类型系统中枢)
4. [Interpreter：执行隔离单元](#4-interpreter执行隔离单元)
5. [运行时对象模型：IbObject 与 vtable](#5-运行时对象模型ibobject-与-vtable)
6. [IExecutionFrame 与 ContextVar 帧注册表](#6-iexecutionframe-与-contextvar-帧注册表)
7. [LLM 执行管道](#7-llm-执行管道)
8. [llmexcept 快照隔离模型](#8-llmexcept-快照隔离模型)
9. [意图系统](#9-意图系统)
10. [Engine 与 HostService](#10-engine-与-hostservice)
11. [三层并发演进路径（PENDING）](#11-三层并发演进路径pending)

---

## 1. 架构哲学与边界划分

IBCI VM 的核心设计哲学是**职责最小化**：每个组件只做自己的事，不越界。

| 组件 | 职责 | 不做什么 |
|------|------|---------|
| **Engine** | 组装者：初始化 KernelRegistry、编译器、注入 Executor | 不执行任何 IBCI 代码 |
| **Interpreter** | 执行隔离单元：接受 Artifact，在独立上下文中执行并返回结果 | 不调度 LLM 并发，不管理子解释器 |
| **HostService（DynamicHost）** | 编排者：管理子解释器实例调度、Artifact 序列化 | 不亲自执行 IBCI 代码 |
| **KernelRegistry** | 类型系统中枢：sealed 后类型体系不可变 | 不执行任何逻辑 |
| **LLMExecutorImpl** | LLM 调用语义实现：解析、重试、格式约束 | 不可被替换（语义组件，非插件）|

**核心架构文件**：
- `core/engine.py`：Engine（组装者）
- `core/runtime/interpreter/interpreter.py`：Interpreter（执行隔离单元）
- `core/runtime/host/service.py`：HostService（编排者）
- `core/kernel/registry.py`：KernelRegistry（类型中枢）
- `core/runtime/interpreter/llm_executor.py`：LLMExecutorImpl（LLM 语义实现）

---

## 2. 核心组件概览

```
┌─────────────────────────────────────────────────────────────────┐
│  用户 IBCI 代码 (.ibci)                                           │
└─────────────────────────────┬───────────────────────────────────┘
                              │ compile()
┌─────────────────────────────▼───────────────────────────────────┐
│  Compiler Pipeline（编译器管道）                                   │
│  Lexer → Parser → Pass1（符号收集）→ Pass2/3（语义分析）           │
│  → Pass4（类型检查）→ ContractValidator → CompilationArtifact    │
└─────────────────────────────┬───────────────────────────────────┘
                              │ run(artifact)
┌─────────────────────────────▼───────────────────────────────────┐
│  Interpreter（执行隔离单元）                                        │
│  ├─ RuntimeContextImpl（变量绑定 / 意图栈 / LLM 帧栈）             │
│  ├─ 树遍历 VM（visit() AST 节点递归，核心 handlers 分派）           │
│  ├─ LLMExecutorImpl（@~...~ 语句的 LLM 调用语义）                 │
│  └─ LLMExceptFrame（快照隔离 / llmexcept 重试状态）               │
└────────────────┬────────────────────────────────────────────────┘
                 │ 使用
┌────────────────▼────────────────────────────────────────────────┐
│  KernelRegistry（sealed 类型中枢）                                 │
│  ├─ SpecRegistry（类型描述符注册表）                               │
│  ├─ AxiomRegistry（公理注册表）                                    │
│  ├─ IbClass 注册表（运行时类对象）                                  │
│  └─ 服务钩子：llm_executor / host_service / stack_inspector ...   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. KernelRegistry：类型系统中枢

### 3.1 职责与封印机制

`KernelRegistry`（`core/kernel/registry.py`）是 IBCI 运行环境的类型系统核心，管理：
- **SpecRegistry**：类型描述符注册表（IbSpec 对象）
- **AxiomRegistry**：公理注册表（TypeAxiom 对象）
- **IbClass 注册表**：运行时类对象（`IbClass`，vtable 持有者）
- **服务钩子**：`llm_executor`、`host_service`、`stack_inspector`、`state_reader`

封印（`seal_classes(token)`）后：
- 所有内置类型结构不可变（`is_sealed = True`）
- 用户自定义类仍可通过 `register_user_class()` 注册（编译时动态注册）
- 服务钩子注册仍可进行（运行时配置）

### 3.2 初始化阶段（RegistrationState）

```
STAGE_1_CORE_AXIOMS       — 核心公理注册（IntAxiom/StrAxiom 等）
STAGE_2_PRIMITIVES        — 内置 Spec 注册（INT_SPEC/LIST_SPEC 等）
STAGE_3_BOOTSTRAP         — builtin_initializer 绑定 vtable 方法
STAGE_4_PLUGIN_IMPL       — 插件实现注册（LLM Provider 等）
STAGE_5_HYDRATION         — 运行时类对象（IbClass）预水合
STAGE_6_PRE_EVAL          — 用户类字段预评估
STAGE_7_READY             — seal() 完成，类型系统冻结
```

### 3.3 元数据注册表（MetadataRegistry）

`KernelRegistry.get_metadata_registry()` 返回 `SpecRegistry`（元数据注册表），供编译器 Pass 和插件发现系统使用。Engine 在 `_ensure_plugins_discovered()` 时将其传递给 `DiscoveryService`，统一插件元数据注册轨道。

---

## 4. Interpreter：执行隔离单元

### 4.1 树遍历 VM（Tree-Walker VM）

IBCI 当前实现为**树遍历 VM**：`Interpreter.visit(node)` 递归遍历编译后的 AST 节点。核心分派通过 `_visitor_cache`（方法名→handler 缓存）路由到具体的 `visit_IbXxx()` 方法。

Handler 按关注点拆分为独立文件（`core/runtime/interpreter/handlers/`）：
- `stmt_handler.py`：语句执行（赋值、for、while、if、llmexcept）
- `expr_handler.py`：表达式求值（运算符、调用、下标访问）
- `base_handler.py`：内置操作（print、类型转换、内置函数）

### 4.2 当前限制（Python 递归调用栈）

当前实现受 Python 调用栈深度限制（约 1000 层）。深度嵌套的 IBCI 函数调用、递归函数可能触发 `RecursionError`。

**演进方向**：Step 9 CPS 调度循环（见 §11）将消除此限制。

### 4.3 CompilationArtifact

编译器输出 `CompilationArtifact`（`ImmutableArtifact`），包含：
- 编译后的 AST（`ReadOnlyNodePool`）
- 符号表（`VariableSymbol` 等）
- 类型信息（每个 AST 节点的 IbSpec）

`ImmutableArtifact` 是只读的，可被多个 Interpreter 实例安全共享（不可变性保证）。

---

## 5. 运行时对象模型：IbObject 与 vtable

### 5.1 IbObject

所有 IBCI 运行时值均继承自 `IbObject`（`core/runtime/objects/kernel.py`）：

```python
class IbObject:
    ib_class: IbClass      # 类型标识（内置或用户定义）
    _fields: Dict[str, IbObject]  # 实例字段
```

内置类型（`IbInteger`/`IbString`/`IbList`/`IbBehavior` 等）是 `IbObject` 的具体子类。

### 5.2 IbClass 与 vtable

`IbClass`（`core/runtime/objects/kernel.py`）是 IBCI 类对象的运行时表示：

```python
class IbClass:
    name: str
    vtable: Dict[str, Callable]   # 方法名 → Python 可调用
    parent: Optional[IbClass]      # 父类（继承链）
    fields: Dict[str, IbObject]    # 类级别字段
```

方法分派通过 `IbObject.receive(method_name, args)` 触发，`IbClass.lookup_method(name)` 沿继承链查找：

```
obj.receive("__to_prompt__", []) 
  → obj.ib_class.lookup_method("__to_prompt__")
  → 找到 vtable["__to_prompt__"]
  → 调用该 Python 可调用
```

### 5.3 内置类型实例

内置类型实例：

| 类 | 对应 IBCI 类型 | 值存储 |
|----|-------------|-------|
| `IbInteger` | `int` | `self._fields["value"]` |
| `IbFloat` | `float` | `self._fields["value"]` |
| `IbString` | `str` | `self._fields["value"]` |
| `IbBool` | `bool` | `self._fields["value"]` |
| `IbList` | `list` | `self._fields["elements"]` |
| `IbTuple` | `tuple` | `self._fields["elements"]` |
| `IbDict` | `dict` | `self._fields["pairs"]` |
| `IbBehavior` | `behavior` | `self._fields["node"]`（AST 节点引用）|
| `IbNone` | `None` | 无值（单例）|
| `IbLLMCallResult` | `llm_call_result` | `is_certain`, `result_value`, `retry_hint` 字段 |

### 5.4 用户自定义类实例

用户自定义类实例是普通 `IbObject`，`ib_class` 指向编译时注册的 `IbClass`，字段存储在 `_fields` 字典中。

### 5.5 RuntimeObjectFactory

`RuntimeObjectFactory`（`core/runtime/factory.py`）提供工厂方法，避免直接导入具体类名：

```python
factory.create_integer(42)
factory.create_string("hello")
factory.create_list([...])
factory.create_dict({...})
factory.create_tuple([...])
factory.create_fn_callable(spec, node, mode)
```

---

## 6. IExecutionFrame 与 ContextVar 帧注册表

### 6.1 IExecutionFrame Protocol

`IExecutionFrame`（`core/base/interfaces.py`）是执行帧的 Protocol 接口：

```python
class IExecutionFrame(Protocol):
    current_scope: Any            # 当前作用域（变量绑定）
    intent_stack: Any             # 意图栈顶节点
    def get_llm_except_frames() -> List[Any]   # LLM 帧栈（只读副本）
    def get_last_llm_result() -> Optional[Any]  # LLM 结果寄存器
    def fork_intent_snapshot() -> Any           # 意图快照（dispatch/retry 用）
```

`RuntimeContextImpl` 是 `IExecutionFrame` 的当前实现，同时也是 `RuntimeContext` Protocol 的实现。

### 6.2 ContextVar 帧注册表

IBCI 使用 Python `contextvars.ContextVar` 实现帧注册表（`core/runtime/frame.py`）：

```python
_current_frame: ContextVar[Optional[IExecutionFrame]] = ContextVar("_current_frame", default=None)

def get_current_frame() -> Optional[IExecutionFrame]:
    return _current_frame.get()

def set_current_frame(frame: IExecutionFrame) -> Token:
    return _current_frame.set(frame)
```

每次函数调用（`IbUserFunction.call()`、`IbLLMFunction.call()`）通过 `set_current_frame()` 更新当前帧，退出时通过 `Token` 恢复。这使得任何代码（包括公理层）都可以通过 `get_current_frame()` 安全地获取当前执行帧，无需传递 `context` 参数。

---

## 7. LLM 执行管道

### 7.1 整体流程

```
IBCI 行为表达式 @~ 请生成一段 $var 的摘要 ~
        │
        │ visit_IbExprStmt / visit_IbAssign
        ▼
  LLMExecutorImpl.execute(behavior, target_type, intent_ctx)
        │
        ├─ 1. 收集意图栈（_collect_intent_content）
        ├─ 2. 插值字符串（_expand_variables）
        ├─ 3. 构建提示词（包含格式提示：__outputhint_prompt__）
        ├─ 4. 调用 LLM Provider（capability_registry.get("llm_provider").call）
        │       ↑ 唯一 LLM 调用入口，provider 由 ibci_ai 注册
        ├─ 5. 解析返回值（_parse_result → FromPromptCapability.from_prompt）
        ├─ 6. 若解析失败（is_uncertain）→ 触发 llmexcept 机制
        └─ 7. 返回 LLMResult（success / is_uncertain / value / retry_hint）
```

### 7.2 @~...~ 语义

`@~...~`（行为表达式）是 IBCI 的 LLM 调用核心语法：
- **左值类型驱动**：赋值目标的类型（`IbSpec`）自动传递给 LLM 作为输出格式约束
- **意图上下文注入**：当前活跃的意图栈（`IbIntentContext`）注入为系统提示词
- **`$var` 插值**：行为字符串中的 `$var` 在执行时替换为变量值的字符串表示
- **`@+`/`@-`/`@!` 修饰符**：在行为表达式前的意图操作符，分别为推入持久意图、弹出意图、一次性排他意图

### 7.3 LLMResult

LLM 调用结果通过 `LLMResult` dataclass 传递（`core/runtime/interpreter/llm_result.py`）：

```python
@dataclass
class LLMResult:
    success: bool = False         # 调用是否成功完成
    is_uncertain: bool = False    # 结果是否不确定（解析失败）
    value: Optional[IbObject] = None  # 成功时的返回值
    error_message: Optional[str] = None
    raw_response: str = ""
    retry_hint: Optional[str] = None  # 供重试的提示词
```

### 7.4 用户协议：`__from_prompt__` 和 `__outputhint_prompt__`

用户自定义 IBCI 类可参与 LLM 解析管道：

```ibci
class MyType:
    str field

    func __from_prompt__(str raw) -> tuple:
        # 解析 raw，返回 (true, parsed_value) 或 (false, "错误提示")
        return (true, raw)

    func __outputhint_prompt__(self) -> str:
        return "请返回一个 JSON 格式的 MyType 对象，含 field 字段"
```

`LLMExecutorImpl._parse_result()` 在公理路径无法处理时，通过 vtable 路由到用户实现的 `__from_prompt__`。

---

## 8. llmexcept 快照隔离模型

### 8.1 快照隔离语义

`llmexcept` 机制基于**快照隔离（Snapshot Isolation）**概念，类比数据库事务：

```
BEGIN SNAPSHOT
  读取外部变量（快照时刻值）
  LLM 调用（含 retry 循环）
  成功：写入目标变量（唯一 COMMIT 点）
  失败：ROLLBACK 到快照 + 向外传播
END SNAPSHOT
```

### 8.2 已落地的快照基础设施

```
LLMExceptFrame（per-snapshot 权威状态）
├─ saved_vars: Dict[str, IbObject]      方案A：深克隆变量快照
├─ saved_protocol_states: Dict          方案B：用户 __snapshot__/restore__ 状态
├─ saved_intent_ctx: IbIntentContext    意图上下文快照（fork()）
├─ saved_loop_context                   循环上下文快照（for/while 状态）
├─ loop_resume: Dict[uid→int]           for 循环迭代断点恢复索引
├─ last_result: Optional[LLMResult]    per-snapshot LLM 结果（权威来源）
└─ retry_count / max_retry / should_retry
```

### 8.3 快照策略（优先级）

1. **方案B（用户协议，优先）**：若用户 IBCI 类定义了 `__snapshot__` 和 `__restore__`，进入帧时调用 `__snapshot__()`，每次 retry 前调用 `__restore__(state)` 原地恢复。用户对快照粒度有完全控制权。
2. **方案A（深克隆，兜底）**：对未实现 `__snapshot__` 的对象，使用 `_try_deep_clone()` 递归克隆用户 IBCI 实例的字段。函数/行为/原生对象不参与克隆（跳过）。
3. **方案C（JSON 序列化）**：未实现，列为 PENDING_TASKS_VM.md 中的 VM 任务。

### 8.4 编译期 read-only 约束（SEM_052）

`llmexcept` body 内向外部作用域变量的任何赋值（含类型标注重声明）在编译期产生 `SEM_052` 错误：

```ibci
int result = 0
llmexcept @~ ... ~:
    result = 42      # ❌ SEM_052：禁止在 llmexcept body 内写入外部变量
    int local = 99   # ✅ body-local 新声明，允许
    retry "重试提示"  # ✅ retry 语句，允许
```

实现：`SemanticAnalyzer._llmexcept_outer_scope_names`（frozenset）在进入 body 时设置，`visit_IbAssign` 检测外部变量写入。

### 8.5 `_last_llm_result` per-snapshot 化

`LLMExceptFrame.last_result` 是 per-snapshot 的权威 LLM 结果存储。读取结果后立即清零 `RuntimeContextImpl._last_llm_result` 共享字段，确保多个 llmexcept 帧之间不存在状态干扰。

---

## 9. 意图系统

### 9.1 核心数据结构

| 组件 | 位置 | 职责 |
|------|------|------|
| `IbIntent` | `core/runtime/objects/intent.py` | 单个意图对象（content, tag, mode）|
| `IbIntentContext` | `core/runtime/objects/intent_context.py` | 意图上下文容器（persistent stack + one-time intent）|
| `IntentContextAxiom` | `core/kernel/axioms/intent_context.py` | 公理声明（is_class=True）|
| `INTENT_CONTEXT_SPEC` | `core/kernel/spec/specs.py` | ClassSpec（可实例化）|

### 9.2 意图上下文的 fork 语义

每次函数调用（`IbUserFunction.call()`/`IbLLMFunction.call()`）在执行前 fork 调用者的意图上下文：

```python
old_intent_ctx = get_current_frame().intent_ctx
child_ctx = old_intent_ctx.fork()
set_intent_ctx(child_ctx)
try:
    # 执行函数体
finally:
    set_intent_ctx(old_intent_ctx)  # 恢复调用者上下文
```

Fork 是**拷贝传递**：函数内的 `@+`/`@-` 操作不泄漏到调用者。

### 9.3 显式作用域控制 API

用户 IBCI 代码可通过以下 API 显式管理意图作用域（在 `builtin_initializer.py` 注册）：

```ibci
intent_context.clear_inherited()   # 清空继承自调用者的持久意图栈
intent_context.use(ctx)            # 替换当前帧意图上下文为 ctx 的 fork
intent_context.get_current()       # 返回当前帧意图上下文的快照副本
```

### 9.4 意图操作符语义

| 操作符 | 语义 | 持续性 |
|--------|------|-------|
| `@+ "..."` | 推入持久意图（persistent push）| 直到 `@-` 或帧退出 |
| `@- "..."` | 弹出持久意图 | 即时生效 |
| `@! "..."` | 一次性排他意图（仅修饰 `@~...~`）| 单次 LLM 调用 |

`@!` 只能修饰 LLM 行为表达式（`@~ ... ~`），不能修饰普通函数调用（编译期约束）。

---

## 10. Engine 与 HostService

### 10.1 Engine（组装者）

`IBCIEngine`（`core/engine.py`）负责：
1. 创建 `KernelRegistry`
2. 调用 `initialize_builtin_classes()` 完成内置类型注册
3. 懒加载插件发现（`_ensure_plugins_discovered()` → `discover_all()`）
4. 提供 `compile_string()` / `run()` / `check()` 入口
5. 注入 LLM Executor（`register_llm_executor()`）和 HostService

### 10.2 HostService（DynamicHost 编排者）

`HostService`（`core/runtime/host/service.py`）负责：
- `run_isolated(artifact, variables)`：在独立 Interpreter 实例中执行，沙箱隔离
- `spawn(artifact)` / `collect()`：子解释器并发调度（Layer 2 PENDING）
- Artifact 序列化/反序列化（`RuntimeSerializer`/`RuntimeDeserializer`）

### 10.3 插件系统

插件通过 `ModuleDiscoveryService.discover_all()` 懒加载（首次 `compile()` 时触发），每个插件实现 `__ibcext_metadata__()` 返回元数据（含 `kind`：`"method_module"` 或 `"type_module"`）。方法插件必须显式 `import` 才能使用（Phase 1 显式引入原则）。

---

## 11. 三层并发演进路径（PENDING）

IBCI 的并发架构分三层，当前 Layer 0（单线程）已完成，Layer 1-2 为待实现路径。

### Layer 0（当前）：单线程树遍历

所有 LLM 调用串行执行，Python 调用栈承载函数递归，单 Interpreter 实例。

### Layer 1（Step 9 + Step 10）：LLM 流水线（DDG + LLMScheduler）

**前提**：`IExecutionFrame` 接口完整（✅ 已具备）

**Step 9 - CPS 调度循环**：  
将树遍历 VM 改为 CPS（Continuation-Passing Style）调度循环，消除 Python 递归栈限制，为协程化 LLM 调用打基础。

**Step 10 - LLM 流水线**：  
DDG（Data Dependency Graph）编译器分析 behavior 节点依赖关系，标注 `dispatch_eligible` 节点；`LLMScheduler`（`ThreadPoolExecutor`）在 dispatch-before-use 时刻并行发起多个 LLM 调用，`LLMFuture` 在求值点阻塞等待结果。

### Layer 2（Step 11）：多 Interpreter 并发

**前提**：ContextVar 帧注册表完整（✅ 已具备）

`DynamicHost.spawn()` 线程化：每个子解释器实例运行在独立线程中，通过 ContextVar 持有独立的帧状态，线程之间不共享运行时上下文。

详见 `docs/PENDING_TASKS_VM.md`。

---

*相关文档：`docs/ARCH_DETAILS.md`（已落地架构细节）；`docs/PENDING_TASKS_VM.md`（VM 并发演进路线）；`docs/TYPE_SYSTEM_DESIGN.md`（类型系统设计）*
