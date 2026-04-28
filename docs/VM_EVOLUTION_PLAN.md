# IBCI VM 演进总规划（Master Plan）

> **文档性质**：本文档是全部 VM 相关工作的总纲。每一个 Milestone 对应一个独立的 PR，执行前后均保持测试基线绿色。  
> **基准状态**（2026-04-28）：**780 个测试通过**；Step 1–8 全部完成；**M1 已完成**（fn/lambda/snapshot 全新语法落地）；**M2 已完成**（IbCell GC 根集合 + 词法作用域正式化，lambda 可自由传递）；**fn declaration-side 语法已完成**（`TYPE fn NAME = lambda: EXPR`，表达式侧 `-> TYPE` PAR_005 禁止）；Step 9–12 待推进。  
> **奠基进展**（M1 前置）：`IbCell` 原语已先行落地（`core/runtime/objects/cell.py`，纯容器、身份语义、`trace_refs()` GC 钩子就绪），单元测试 18 个，无现有路径行为变化。  
> **不阻塞规则**：每个 Milestone 在其前提 Milestone 合并后即可独立开工，不需要等待其他并行 Milestone。  
> **关联文档**：`docs/PENDING_TASKS_VM.md`（详细设计）、`docs/NEXT_STEPS.md`（近期任务）、`docs/COMPLETED.md`（已完成记录）。

---

## 一、当前架构现状（代码层事实）

### 1.1 解释器执行模型

`core/runtime/interpreter/interpreter.py` 的 `visit()` 方法（第 755 行）是一个纯 **Python 递归 tree-walker**：

```
visit(node_uid)
  └─ _visitor_cache[node_type](node_uid, node_data)   # 分发到 Handler
       └─ visit(child_uid)   # 递归
            └─ ...
```

控制流全部依赖 Python 异常机制：

| IBCI 控制流 | Python 实现 | 代码位置 |
|-------------|-------------|----------|
| `return v` | `raise ReturnException(v)` | `stmt_handler.py:709` |
| `break` | `raise BreakException()` | `stmt_handler.py:714` |
| `continue` | `raise ContinueException()` | `stmt_handler.py:717` |
| `raise e` | `raise ThrownException(e)` | `stmt_handler.py:720` |
| llmexcept retry | Python try/except + `LLMExceptFrame.restore_snapshot()` | `stmt_handler.py:555–648` |

`LogicalCallStack`（`call_stack.py`）只是 **调试影子栈**，真实调用栈是 Python 递归栈。注释自白（`interpreter.py` 第 14 行）：
> "每一层 IBCI 调用大约消耗 4 层 Python 栈帧；必须确保 max_call_stack * 4 < sys.getrecursionlimit()"

### 1.2 作用域与闭包现状

- `ScopeImpl._parent` 链已实现词法嵌套（公理 SC-1 ✅）
- `IbDeferred`/`IbBehavior` 的自由变量（M2 后）通过 `ScopeImpl.promote_to_cell()` 提升为共享 IbCell，lambda/snapshot 统一通过 `closure: Dict[sym_uid, (name, IbCell)]` 访问  
  → 公理 SC-3/SC-4 **已实现**（M2 ✅）
- `fn`/`lambda`/`snapshot` 支持参数传递（M1 ✅）；`TYPE fn NAME = lambda: EXPR` 声明侧返回类型标注已落地
- lambda 闭包对象可自由作为高阶函数参数传递（M2 ✅）

### 1.3 意图上下文现状

- `IbIntentContext` 已公理化，`fork()/restore()` 机制完整（Step 6 ✅）
- 函数调用时 fork（`kernel.py:767–769`），快照恢复时 restore（`llm_except_frame.py`）

### 1.4 测试基线

```
python3 -m pytest tests/ -q --tb=short   # 780 passed（2026-04-28，fn declaration-side 语法完成后）
```

每个 Milestone 完成后必须以此命令验证测试不退化。

---

## 二、总体演进路线图

```
已完成（Step 1–8 + M1 + M2 + fn declaration-side 语法）
  └─── 当前状态（基准：780 tests）
         │
         ├─── ✅ M1：fn 新语法 + IbCell（Step 12.5）                  [已完成 2026-04-28]
         │      │
         │      └─── ✅ M2：IbCell GC 根集合 + 词法作用域正式化（Step 13）[已完成 2026-04-28]
         │
         ├─── M3a：CPS 调度循环骨架（Step 9a）                      [独立入口，M2 完成后可进]
         │      │
         │      ├─── M3b：return/break/continue 迁移到 Signal（Step 9b）
         │      │      │
         │      │      └─── M3c：llmexcept retry + intent fork 调度化（Step 9c）
         │      │
         │      └─── M4：Layer 2 多 Interpreter 并发（Step 11）     [依赖 M3a]
         │
         └─── M5：LLM 流水线（Step 10a/10b/10c）                    [依赖 Step 6 ✅，可独立]
                └─── M6：可移植性参考实现 + 并发行为测试套件（Step 12）[依赖 M3c + M4 + M5]
```

**推荐执行顺序**：M1 → M2 → M3a → M3b → M3c → M4 → M5 → M6  
（M5 可在 M3a 之前并行推进，但 M5 的 dispatch-before-use 集成需要 M3c 完成后才能完整）

---

## 三、Milestone 详细规范

---

### M1：fn 参数化 lambda/snapshot 新语法 + IbCell 基础（Step 12.5）✅ COMPLETED — 2026-04-28

**目标**：用新的统一 `fn` 声明语法替代旧语法，引入参数传递能力；引入 `IbCell` 堆对象实现公理 SC-3/SC-4。

**前提**：Step 8 完成（✅ 已具备）

**完成状态**：✅ 全部落地，758 个测试通过（M1 本体）；随后 fn declaration-side 语法进一步演进至 780 个测试通过。详见 `docs/COMPLETED.md §五/§七b`。

**已落地的最终语法规范**（M1 基础 + 后续 fn declaration-side 语法演进）：

```ibci
# 无参形式（冒号语法）
fn f = lambda: EXPR
TYPE fn f = lambda: EXPR        # 带返回类型标注（声明侧）
fn f = snapshot: EXPR
TYPE fn f = snapshot: EXPR      # 带返回类型标注（声明侧）

# 带参形式
fn f = lambda(PARAMS): EXPR
TYPE fn f = lambda(PARAMS): EXPR
fn f = snapshot(PARAMS): EXPR
TYPE fn f = snapshot(PARAMS): EXPR
```

其中 TYPE 可为 `int`、`str`、`tuple[int,str]`、用户类名等任意类型。  
`fn[TYPE]` 通过 `registry.resolve_specialization` 解析为 `DeferredSpec(value_type_name=TYPE)`。  
表达式侧 `lambda -> TYPE: EXPR` 形式已被 **PAR_005** 错误禁止。

**已移除的旧语法**（现产生 parse error）：
```ibci
# 以下形式已废弃，解析器拒绝：
int lambda f = expr          # ❌ 旧声明语法
auto snapshot g = expr       # ❌ 旧声明语法
fn lambda h = expr           # ❌ 旧声明语法
lambda(EXPR)                 # ❌ 旧括号体语法
lambda(PARAMS)(EXPR)         # ❌ 旧括号体语法
```

**实际落地的文件**：

| 文件 | 改动性质 |
|------|---------|
| `core/compiler/parser/components/declaration.py` | 移除所有 `deferred_mode` 检测分支（auto/fn/TYPE 三处），`IbAssign` 不再携带 `deferred_mode` |
| `core/compiler/parser/components/expression.py` | `lambda_expr`/`snapshot_expr` 强制冒号 body-start；移除旧括号体形式；更新废弃错误消息 |
| `core/compiler/semantic/passes/semantic_analyzer.py` | 移除 `visit_IbAssign` 中所有 `deferred_mode` 相关分支；`visit_IbLambdaExpr` 处理参数、自由变量、返回类型绑定；IbCell 闭包接线 |
| `core/runtime/objects/builtins.py` | `IbDeferred`/`IbBehavior` 支持参数列表；M2 后 lambda/snapshot 统一通过 `closure` + IbCell 捕获自由变量（`captured_scope` 路径已删除） |
| `core/runtime/interpreter/handlers/expr_handler.py` | `visit_IbLambdaExpr` 构建 IbDeferred/IbBehavior；`_collect_free_refs` 自由变量扫描 |
| `core/runtime/objects/cell.py` | ✅ 已奠基，M1 接线使用 |
| `tests/e2e/test_e2e_fn_lambda_syntax.py` | 80+ 个测试；旧语法测试改为断言 parse error |
| `tests/e2e/test_e2e_deferred.py` | 更新为新语法 |
| `tests/e2e/test_e2e_ai_mock.py` | 更新为新语法 |
| `tests/compiler/test_compiler_pipeline.py` | 更新为新语法 |

**完成后的出口契约**（均已验证）：
- ✅ 新语法 `fn f = lambda: EXPR` / `fn f = lambda(PARAMS) -> TYPE: EXPR` 8 种形式全部可用
- ✅ `IbDeferred.call(args)` / `IbBehavior.call(args)` 支持参数列表
- ✅ lambda 闭包语义（M2 后）：自由变量通过共享 IbCell 间接访问（不再直接持有 ScopeImpl）
- ✅ snapshot 闭包语义：自由变量通过 `IbCell` 值拷贝，调用时与外部隔离
- ✅ 旧语法（`int lambda f = ...`、`auto snapshot g = ...`、括号体形式、`lambda -> TYPE: EXPR` 表达式侧返回类型）产生 parse error（非警告）
- ✅ 758 个测试全部通过（新增 ≥30 个 fn/lambda/snapshot 相关测试）

---

### M2：IbCell GC 根集合 + 词法作用域正式化（Step 13）✅ COMPLETED — 2026-04-28

**目标**：IbCell 机制落地公理 SC-3/SC-4/LT-2/LT-3；更新 GC 根集合扫描路径；移除 lambda 参数传递限制。

**前提**：M1 完成

**实际落地的文件**：

| 文件 | 改动性质 |
|------|---------|
| `core/runtime/interpreter/runtime_context.py` | `RuntimeSymbolImpl` 添加 `cell` 字段；`ScopeImpl` 添加 `_cell_map`、`promote_to_cell()`、`iter_cells()`；`assign`/`assign_by_uid` 同步写入 IbCell；`RuntimeContextImpl` 新增 `collect_gc_roots()` |
| `core/runtime/interpreter/handlers/expr_handler.py` | `visit_IbLambdaExpr` lambda 模式改为共享 IbCell 引用（`promote_to_cell()`），不再传递 `captured_scope` |
| `core/runtime/objects/builtins.py` | `IbDeferred.call()` 移除 `captured_scope` 作用域切换逻辑；lambda/snapshot 统一通过 `closure` 字典安装自由变量（注：`_captured_scope` 字段本身在后续代码债务清理 PR 中完全删除，见 `docs/COMPLETED.md §九`）|
| `core/runtime/objects/kernel.py` | `IbUserFunction.call()` 删除 lambda 参数传递限制 |
| `tests/e2e/test_e2e_m2_higher_order.py` | 新增 17 个 M2 专项测试（HOF、IbCell 语义、GC 根集合） |
| `tests/e2e/test_e2e_ai_mock.py` | `TestE2ELambdaRestriction` 反转：改为验证 lambda 可自由传递 |

**出口契约（均已验证）**：
- ✅ lambda 闭包的自由变量通过共享 `IbCell` 间接访问（不再直接持有 ScopeImpl 引用）
- ✅ snapshot 对象的自由变量在定义时复制 Cell 值，之后与外部 ScopeImpl 完全解耦
- ✅ `ScopeImpl.promote_to_cell()` 在变量首次被 lambda 捕获时将其提升为 Cell 变量
- ✅ `assign`/`assign_by_uid` 对 Cell 变量同步更新 IbCell，lambda 下次调用读到最新值
- ✅ `RuntimeContextImpl.collect_gc_roots()` 枚举作用域链中所有符号值与 Cell 持有对象
- ✅ lambda 对象可以自由作为高阶函数参数传递
- ✅ 776 个测试全部通过（758 基线 + 18 新增）

---

### M3a：CPS 调度循环骨架（Step 9a）

**目标**：在现有 `interpreter.py` 旁新增一个 `vm_executor.py`，实现基于显式帧栈（而非 Python 递归）的 `visit_cps()` 方法。**本阶段不替换 `visit()`**，而是作为独立的并行实现路径验证正确性。

**前提**：Step 7 完成（✅ 已具备）；M1 完成后更安全（但不强依赖）

**核心设计**：

```python
# core/runtime/vm/vm_executor.py（新建）
class VMExecutor:
    """
    CPS 调度循环执行器。
    替代 interpreter.py 中的 Python 递归 visit() 方法。
    
    执行模型：
      while work_queue:
          task = work_queue.pop()
          result = task.step()
          if result is DONE:
              task.continuation(result.value)
          elif result is SUSPEND:
              work_queue.push(result.resume_task)
    """
    def __init__(self, execution_context: IExecutionContext):
        self._ec = execution_context
        self._work_queue: List[VMTask] = []
    
    def run(self, node_uid: str) -> IbObject:
        """入口：将根节点包装为 VMTask，启动调度循环"""
        ...
```

**VMTask 类型（新建 `core/runtime/vm/task.py`）**：

```python
@dataclass
class VMTask:
    node_uid: str
    scope_snapshot: Scope          # 执行时的作用域
    intent_ctx_snapshot: IbIntentContext
    continuation: Callable[[IbObject], None]  # 结果回调
    
    def step(self) -> 'VMTaskResult': ...
```

**文件级修改清单**：

| 文件 | 改动性质 |
|------|---------|
| `core/runtime/vm/` （新建目录） | 新建 VM 子包 |
| `core/runtime/vm/__init__.py` | 包初始化 |
| `core/runtime/vm/task.py` | `VMTask`、`VMTaskResult`（`DONE`/`SUSPEND`）、`ControlSignal`（`RETURN`/`BREAK`/`CONTINUE`/`THROW`）数据类定义 |
| `core/runtime/vm/vm_executor.py` | `VMExecutor` 主类；`_dispatch_table: Dict[str, Callable]`；`run()` 驱动循环 |
| `core/runtime/vm/handlers/` | 每类 AST 节点的 CPS handler（对应现有 `stmt_handler.py`/`expr_handler.py` 但不使用 Python 递归） |
| `core/base/interfaces.py` | 新增 `IVMExecutor` Protocol；`IVMTask` Protocol |
| `tests/unit/test_vm_executor.py` | 单元测试：常量求值、算术、函数调用、while 循环的 CPS 路径 |

**关键设计决策（防止 M3a 失控）**：
1. M3a **不删除** `interpreter.py` 的 `visit()` 方法；两者并存
2. M3a 通过 `VMExecutor` 运行 `tests/unit/test_vm_executor.py` 的专属测试集（可以是现有 E2E 测试的子集）
3. M3a 结束时 678 个现有测试仍由旧 `visit()` 驱动，**保证不退化**
4. M3a 中控制流信号（return/break/continue）暂时**仍可使用 Python 异常**，在 M3b 中迁移

**出口契约（完成后）**：  
- `VMExecutor` 能正确执行：常量/变量/算术/比较/if/while/函数定义/函数调用/return（使用 Python 异常 OK）  
- 678 个原有测试不退化  
- 新增 ≥30 个 CPS 路径专属测试

---

### M3b：return/break/continue/throw 迁移到 ControlSignal（Step 9b）

**目标**：在 `VMExecutor` 中彻底消除 `ReturnException`/`BreakException`/`ContinueException`/`ThrownException`，改为显式 `ControlSignal` 数据对象在调度器循环中传播。

**前提**：M3a 完成

**核心改动**：

旧实现（Python 异常）：
```python
# stmt_handler.py:709
def visit_IbReturn(self, node_uid, node_data):
    value = self.visit(node_data.get("value"))
    raise ReturnException(value)
```

新实现（ControlSignal）：
```python
# vm/handlers/control_handler.py
def handle_IbReturn(task: VMTask, node_data: dict) -> VMTaskResult:
    value_task = VMTask(node_data["value"], ...)
    def on_value(v: IbObject):
        task.signal(ControlSignal.RETURN, v)
    value_task.continuation = on_value
    return VMTaskResult.SUSPEND(value_task)
```

调度器循环中拦截 `ControlSignal`，沿帧栈向上传播直到找到对应的处理帧（函数帧拦截 `RETURN`，循环帧拦截 `BREAK`/`CONTINUE`，try 帧拦截 `THROW`）。

**文件级修改清单**：

| 文件 | 改动性质 |
|------|---------|
| `core/runtime/vm/task.py` | 添加 `ControlSignal` 枚举和 `task.signal()` 方法 |
| `core/runtime/vm/vm_executor.py` | 在调度循环中添加 `ControlSignal` 传播逻辑；`FunctionCallFrame` 拦截 `RETURN`；`LoopFrame` 拦截 `BREAK`/`CONTINUE` |
| `core/runtime/vm/handlers/control_handler.py` | 重写 `handle_IbReturn`/`handle_IbBreak`/`handle_IbContinue`/`handle_IbRaise` |
| `core/runtime/exceptions.py` | 标注旧异常类为 `@deprecated("Use VMExecutor ControlSignal instead")`（不删除，旧 visit() 仍需要） |

**出口契约（完成后）**：  
- `VMExecutor` 中 return/break/continue/throw 不再依赖 Python 异常  
- 678 个原有测试仍由旧 `visit()` 驱动，不退化  
- `VMExecutor` 测试新增 ≥20 个控制流相关案例（包括嵌套 return、带 finally 的 throw 等）

---

### M3c：llmexcept retry + intent fork/restore 调度化（Step 9c）

**目标**：将 `LLMExceptFrame` 的 retry 循环和意图 fork/restore 迁移到 `VMExecutor` 的调度循环中管理，消除对 Python try/except + `LLMExceptFrame.restore_snapshot()` 的直接依赖。

**前提**：M3b 完成

**当前问题**（`stmt_handler.py:555–648`）：
```python
def visit_IbLLMExceptionalStmt(self, node_uid, node_data):
    for attempt in range(max_retries):
        try:
            result = self.visit(target_uid)   # Python 递归
            if result.is_certain:
                break
        except ...:
            frame.restore_snapshot()
            # retry
```

目标实现（调度循环中）：
```python
# LLMExceptTask 是一个自管理的 VMTask 子类
class LLMExceptTask(VMTask):
    def step(self) -> VMTaskResult:
        if self.attempt < self.max_retries:
            child = VMTask(self.target_uid, self.snapshot_scope, self.snapshot_intent_ctx, ...)
            child.continuation = self._on_llm_result
            return VMTaskResult.SUSPEND(child)
        else:
            return VMTaskResult.SIGNAL(ControlSignal.THROW, LLMPermanentFailureError(...))
    
    def _on_llm_result(self, result: IbObject):
        if result.is_certain:
            self.continuation(result)
        else:
            self.attempt += 1
            self._work_queue.push(self)  # 重新入队：retry
```

意图 fork/restore 在 `LLMExceptTask.__init__` 时调用 `intent_ctx.fork()`，在 `_on_llm_result` 中自动恢复（不再依赖 Python finally 块）。

**文件级修改清单**：

| 文件 | 改动性质 |
|------|---------|
| `core/runtime/vm/tasks/llm_except_task.py`（新建） | `LLMExceptTask` 类；snapshot 保存/恢复逻辑 |
| `core/runtime/vm/vm_executor.py` | 注册 `IbLLMExceptionalStmt` → `LLMExceptTask` 的映射 |
| `core/runtime/interpreter/llm_except_frame.py` | 标注为 `@deprecated_for_vm`；保留供旧 `visit()` 使用 |

**出口契约（完成后）**：  
- `VMExecutor` 中 llmexcept retry 不依赖 Python 异常或 Python finally  
- 678 个原有测试不退化  
- M3a/M3b/M3c 合并后，开始逐步将 `Interpreter.run()` 切换到使用 `VMExecutor`（可作为单独小 PR）

---

### M3d（附属）：Interpreter.visit() 切换到 VMExecutor

**目标**：让主执行路径（`Interpreter.run()` → `execute_module()` → `visit()`）使用 `VMExecutor` 而非 Python 递归。

**前提**：M3c 完成

**文件级修改清单**：

| 文件 | 改动性质 |
|------|---------|
| `core/runtime/interpreter/interpreter.py:755–843` | `visit()` 委托到 `self._vm_executor.visit(node_uid)` |
| `core/runtime/interpreter/interpreter.py:507–567` | `execute_module()` 使用 `VMExecutor.run()` |
| `core/runtime/exceptions.py` | 删除 `ReturnException`/`BreakException`/`ContinueException` 的实际使用（旧 `visit()` 路径移除） |

**出口契约（完成后）**：  
- 678 个测试全部由新 `VMExecutor` 路径驱动通过  
- `interpreter.py:149` 注释（"每层 IBCI 调用消耗 4 层 Python 栈帧"）删除  
- Python `sys.setrecursionlimit` 不再是 IBCI 运行时的限制因素

---

### M4：Layer 2 多 Interpreter 并发（Step 11）

**目标**：`DynamicHost.spawn()` 线程化——每个子 Interpreter 在独立线程中运行，持有独立 `ContextVar` 槽位；`collect()` 等待所有子 Interpreter 完成并提取结果。

**前提**：M3a 完成（ContextVar 多线程安全性依赖帧不在 Python 递归栈上；M3a 完成后帧已独立）

**文件级修改清单**：

| 文件 | 改动性质 |
|------|---------|
| `core/runtime/host/service.py` | `spawn()` 使用 `ThreadPoolExecutor` 提交子 Interpreter；`collect()` 调用 `Future.result()` |
| `core/runtime/async/` | 新建 `async_runner.py`：`spawn_interpreter_thread()` 工具函数 |
| `core/runtime/frame.py` | 确认 `ContextVar[IExecutionFrame]` 在 `threading.Thread` 中安全（标准库保证，验证即可） |
| `tests/e2e/test_e2e_multiinterp.py`（新建） | 并发 spawn + collect 的 E2E 测试 |

**出口契约（完成后）**：  
- `host.spawn()` + `host.collect()` 支持至少 4 个并发子 Interpreter  
- 子 Interpreter 不共享 RuntimeContext，结果通过 collect 接口提取  
- 678 + 之前 Milestone 新增 的测试全部通过

---

### M5：Layer 1 LLM 流水线（Step 10a / 10b / 10c）

**目标**：数据无关的 behavior 表达式并发发起 HTTP 调用，总耗时 ≈ max(T_a, T_b, T_c)。

**前提**：Step 6（IbIntentContext.fork()）✅ 已具备；可以在 M3a 之前独立推进 10a+10b，但 10c 的 dispatch-before-use 集成需要 M3c 完成后才能完整

#### Step 10a：DDG 编译器分析

**文件级修改清单**：

| 文件 | 改动性质 |
|------|---------|
| `core/compiler/semantic/passes/expression_analyzer.py` | 新增 `BehaviorDependencyAnalyzer`：分析 `IbBehaviorExpr` 模板中引用的变量，向上追溯定义来源是否为另一个 behavior |
| `core/compiler/serialization/serializer.py` | `IbBehaviorExpr` 节点新增 `llm_deps: List[str]` 和 `dispatch_eligible: bool` 字段 |
| `tests/unit/test_ddg_analysis.py`（新建） | DDG 提取的单元测试 |

#### Step 10b：LLMScheduler

**文件级修改清单**：

| 文件 | 改动性质 |
|------|---------|
| `core/runtime/interpreter/llm_executor.py`（重构） | `LLMExecutorImpl` 演进为 `LLMScheduler`：添加 `dispatch_eager(node_uid, prompt_args, intent_ctx) -> LLMFuture` 和 `resolve(node_uid) -> IbObject` 入口；内部持有 `ThreadPoolExecutor` |
| `core/runtime/interpreter/llm_result.py` | 新增 `LLMFuture` 类型（包装 `concurrent.futures.Future`）；`LLMFuture.get() -> IbObject` 阻塞等待结果 |

#### Step 10c：VM dispatch-before-use 集成

**文件级修改清单**：

| 文件 | 改动性质 |
|------|---------|
| `core/runtime/vm/vm_executor.py`（或 `interpreter.py` 的 `visit_IbBehaviorExpr`） | `dispatch_eligible=True` 时调用 `dispatch_eager()`；变量使用点检测到 `LLMFuture` 时调用 `resolve()` |
| `core/runtime/interpreter/handlers/expr_handler.py:218–278` | 现有 `visit_IbBehaviorExpr`：添加 `dispatch_eligible` 检查 |
| `tests/e2e/test_e2e_llm_pipeline.py`（新建） | 并发 LLM 调用时序验证（MOCK 驱动，验证三个 behavior 并发 dispatch 后乱序完成仍然结果正确） |

---

### M6：可移植性参考实现 + 并发行为测试套件（Step 12）

**目标**：使现有 E2E 测试套件成为 IBCI VM 规范的跨实现合规测试集；补充并发行为覆盖。

**前提**：M3c + M4 + M5 完成

**文件级修改清单**：

| 文件 | 改动性质 |
|------|---------|
| `docs/VM_SPEC.md`（新建） | IBCI VM 正式规范：执行模型、数据流模型、IbIntentContext 规范、IbObject 内存模型、三层并发接口规范 |
| `tests/compliance/`（新建目录） | 将现有 E2E 测试中适合跨实现验证的测试子集复制/重组为 Compliance Test Suite |
| `tests/compliance/test_concurrent_llm.py` | 乱序 LLM 结果的确定性验证；并发 spawn 的隔离性验证 |
| `tests/compliance/test_memory_model.py` | IbCell 生命周期验证；snapshot 自包含性验证；值类型赋值深拷贝等价验证 |

---

## 四、依赖图（精确版）

```
M1（fn 新语法 + IbCell）
  ├─────────────── M2（IbCell GC 根集合）
  │
  └───────────── M3a（CPS 骨架，独立路径）
                   └─── M3b（ControlSignal 迁移）
                          └─── M3c（llmexcept 调度化）
                                 ├─── M3d（切换主执行路径）
                                 └─── M4（多 Interpreter 并发）

M5a（DDG 编译器，独立）
  └─── M5b（LLMScheduler）
         └─── M5c（dispatch-before-use，需 M3c）

M3d + M4 + M5c
  └─── M6（可移植性规范 + 合规测试套件）
```

---

## 五、测试验收门（每个 Milestone 的 PR 合并条件）

| Milestone | 必须通过 | 必须新增 |
|-----------|---------|---------|
| M1 | 678 个基线测试 | ≥20 fn/lambda/Cell 测试 |
| M2 | M1 后全部测试 | ≥10 Cell 生命周期测试 |
| M3a | 678 个基线测试 | ≥30 VMExecutor 专属测试 |
| M3b | M3a 后全部测试 | ≥20 ControlSignal 控制流测试 |
| M3c | M3b 后全部测试 | ≥15 llmexcept/retry 调度化测试 |
| M3d | 678 + M3a/b/c 新增，全部由 VMExecutor 路径驱动 | 无新增要求，重点是不退化 |
| M4 | M3a 后全部测试 | ≥10 并发 spawn/collect 测试 |
| M5a | 基线测试 | ≥10 DDG 分析单元测试 |
| M5b | 基线测试 | ≥10 LLMScheduler/Future 单元测试 |
| M5c | M3c + M5b 后全部测试 | ≥10 并发 LLM 调用时序 E2E 测试 |
| M6 | 全部 | Compliance Test Suite 独立运行通过 |

---

## 六、风险与缓解措施

| 风险 | 影响 Milestone | 缓解措施 |
|------|---------------|---------|
| M3a 的 VMTask/ControlSignal 设计与现有 Handler 不兼容 | M3a | M3a 中新旧路径并存，旧路径作为 fallback；逐节点迁移，不一次性切换 |
| M3d 切换后某些 edge case（如 llmexcept 中的 for-loop retry resume）行为与旧路径不一致 | M3d | 在 M3c 完成后专门新增 llmexcept+for-loop+retry E2E 测试，M3d 前必须全部通过 |
| M5 的 LLMScheduler 线程池大小成为瓶颈 | M5b | 可配置的 `max_workers` 参数（默认 8）；文档明确"LLM 调用是 I/O bound，GIL 在 HTTP 期间释放" |
| M1 的 IbCell 机制引入后，旧 `captured_scope` 路径的测试全部失效 | M1 | M1 中旧语法输出 DEP_001 警告但不失效；旧路径测试在独立的"废弃移除" PR 中删除 |
| M4 的多线程 ContextVar 安全性 | M4 | Python 标准库保证 `ContextVar` 在 `threading.Thread` 中独立；单独编写 Thread 安全性验证测试 |

---

## 七、与现有文档的对应关系

| 本文档 Milestone | `PENDING_TASKS_VM.md` 对应章节 | `NEXT_STEPS.md` 对应 Step |
|-----------------|-------------------------------|--------------------------|
| M1 | §10.2 SC-3/SC-4、§10.3 LT-2/LT-3、§10.6 | Step 12.5 |
| M2 | §10.4 GC-2/GC-3、§10.5 | Step 13 |
| M3a/b/c/d | §二（双栈问题）、§三 层次 2 | Step 9 |
| M4 | §五 第二层执行隔离、§七 7.2 | Step 11 |
| M5a/b/c | §五 第一层 LLM 流水线、§五 5.5–5.6 | Step 10a/10b/10c |
| M6 | §八 可移植性路径 | Step 12 |

---

*本文档记录 VM 演进的全部分阶段规划。每个 Milestone 是独立的 PR，合并时保持测试基线绿色。详细设计参见 `docs/PENDING_TASKS_VM.md`。*
