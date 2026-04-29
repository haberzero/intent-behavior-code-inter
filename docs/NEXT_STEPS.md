# IBC-Inter 近期优先任务

> 记录接下来可以直接开工的具体任务，按优先级排列。  
> 中长期任务见 `docs/PENDING_TASKS.md`，已完成工作见 `docs/COMPLETED.md`。  
> VM 架构长期设想（含三层并发模型、llmexcept 危险悬案）见 `docs/PENDING_TASKS_VM.md`。
>
> **最后更新**：2026-04-29（轻量债务清理 PR 已合并：L1/L2/C1/C2/C3/C4/C10/C13；M3d/M5c 主线已纳入；949 个测试通过；下一里程碑：**M4 多 Interpreter 并发**）

---

## 当前整体状态评估

**核心公理化路径已全部完成**（Step 1 → Step 7）：

- ✅ 公理体系（Axiom）：`KernelRegistry` sealed 封印；primitive 类型已完成 Axiom 化
- ✅ vtable 分发：`IbObject.receive()` + `IbClass.lookup_method()` 消息传递模型
- ✅ LLM 执行路径统一：`LLMExecutorImpl` 通过 `capability_registry.get("llm_provider")` 唯一来源
- ✅ `IExecutionFrame` Protocol（Step 5）：`core/base/interfaces.py`，`ContextVar` 帧注册表
- ✅ `IbIntentContext` 公理化（Step 6）：独立意图上下文类型；`RuntimeContextImpl` 完整迁移（6c/6d）
- ✅ `LlmCallResultAxiom` + `IbLLMCallResult`（Step 7）：LLM 结果类型完整接入公理体系
- ✅ `IbLLMCallResult` 全链路接入：`set_last_llm_result()` 自动转换；所有读取点使用 `is_certain`
- ✅ vibe 代码债务清理：`interpreter.py:229` kwargs bug 修复；`engine.py` orchestrator 注入规范化
- ✅ **Step 8-pre（快照隔离完整落地）**：§9.2 SEM_052 编译期 read-only 约束 + §9.3 `_last_llm_result` per-snapshot 化；idbg `last_result()` / `last_llm()` 帧优先模式；`retry_stack()` 含帧私有 `last_result` 详情
- ✅ **`__prompt__` 协议 vtable 修复**：`_parse_result()` + `_get_llmoutput_hint()` 增加用户类 vtable 回退路径；`IbObject.__outputhint_prompt__()` 委托给 vtable 方法
- ✅ **`for...if` / `while...if` 过滤语法**：`visit_IbFilteredExpr` 实现（while 场景）；`visit_IbFor` 拆包 `IbFilteredExpr`，foreach 场景在目标赋值后求值 filter（`continue` 语义），条件驱动 for 场景 filter 失败终止循环（`break` 语义，与 `while...if` 一致）
- ✅ **llmexcept 快照深克隆（方案A）**：`LLMExceptFrame._save_vars_snapshot()` 使用 `_try_deep_clone()`，支持用户自定义 `IbObject` 实例的递归字段克隆；循环引用通过 `memo` dict 安全处理
- ✅ **llmexcept 用户协议快照（方案B）**：`saved_protocol_states` 字段；`_save_vars_snapshot()` 检测 `__snapshot__` vtable 并优先使用；`_restore_vars()` 调用 `__restore__(state)` 原地恢复；方案B优先于方案A，失败时自动降级；方案C（JSON 序列化）已作为 VM 任务记录在 `docs/PENDING_TASKS_VM.md`
- ✅ **函数调用意图隔离（§9.4）**：`IbUserFunction.call()` + `IbLLMFunction.call()` 统一 fork/restore；`@!` 语义恢复为只修饰 LLM 行为表达式（不修饰函数调用）；`intent_context.clear_inherited()`/`use(ctx)`/`get_current()` 三个显式作用域控制 API 在 `builtin_initializer.py` 注册
- ✅ **M1 fn/lambda/snapshot 全新语法落地**：758 → 780 个测试通过（M1 + M2 + fn declaration-side 三阶段）
- ✅ **M2 IbCell GC 根集合 + 词法作用域正式化**：lambda 自由变量通过共享 IbCell，lambda 可自由作为高阶函数参数传递；`ScopeImpl.promote_to_cell()`；`collect_gc_roots()`
- ✅ **fn 声明侧返回类型**：`TYPE fn NAME = lambda: EXPR`；表达式侧 `lambda -> TYPE:` 禁止（PAR_005）；`fn[TYPE]` 解析为 DeferredSpec
- ✅ **代码债务清理（H1/H2/H3/M1）**：删除 `_captured_scope` 僵尸字段（`IbDeferred` + factory/interfaces/expr_handler/stmt_handler 全链路）；修复 `DeferredAxiom.is_compatible` 文档/代码矛盾；移除 closure 解包死 `else` 分支（两处）；780 个测试通过
- ✅ **M3a：CPS 调度循环骨架**（`core/runtime/vm/`：VMExecutor + 21 节点 generator handler + VMTask/VMTaskResult/ControlSignal/ControlSignalException + IVMExecutor/IVMTask Protocol）；49 个 VM 单元测试新增；未实现节点回退到 `execution_context.visit(uid)`；829 个测试通过
- ✅ **M3b：控制信号数据化**（`Signal(kind, value)` frozen 数据对象；handler `return Signal(...)` 替代 `raise CSE`；while 消费 BREAK/CONTINUE，模块/if 透传；`StopIteration.value` 是 Signal 时通过 `gen.send` 沿栈传递；顶层未消费仍包装为 CSE 抛出，保持边界兼容）；22 个新增单元测试；829 → 851 个测试通过
- ✅ **M5a：DDG 编译期分析**（`IbBehaviorExpr.llm_deps` + `dispatch_eligible` 字段；`BehaviorDependencyAnalyzer` 作为 SemanticAnalyzer Pass 5 通过 Tarjan SCC 推导可调度性；`FlatSerializer` 自动序列化为 UID 列表）；16 个新增单元测试；851 → 867 个测试通过
- ✅ **M3c：IbLLMExceptionalStmt CPS 调度化**（`_resolve_stmt_uid` 保护重定向辅助；`vm_handle_IbLLMExceptionalStmt` CPS 生成器管理 retry 循环 + LLMExceptFrame；`IbModule`/`IbIf`/`IbWhile` 容器 handler 全部接入；`VMExecutor.service_context` property 暴露 capability_registry）；21 个新增单元测试；867 → 888 个测试通过
- ✅ **M5b：LLMScheduler / LLMFuture**（`LLMFuture(node_uid, future)` 包装 `concurrent.futures.Future`；`LLMExecutorImpl.dispatch_eager(node_uid, ec, intent_ctx)→LLMFuture`、`resolve(node_uid)→IbObject`、`__del__` 关闭线程池；`ThreadPoolExecutor` 惰性初始化；`_pending_futures` dict 单消费语义）；17 个新增单元测试；888 → 905 个测试通过
- ✅ **M3d-prep：扩展 CPS handler 覆盖（22→37 节点类型）**（新增 14 个 vm_handle_X：表达式 IbDict/IbSlice/IbCastExpr/IbFilteredExpr；语句 IbAugAssign/IbGlobalStmt/IbRaise/IbImport/IbImportFrom/IbSwitch/IbFunctionDef/IbLLMFunctionDef/IbClassDef/IbIntentAnnotation/IbIntentStackOperation；全部 1:1 镜像现存递归 visit_X 语义；不触碰 IbUserFunction.call() 内的 ReturnException 捕获——留待 M3d 整体处理）；21 个新增单元测试；905 → 926 个测试通过
- ✅ **URGENT_ISSUES 中等优先级清理（M2/M3/M4/M5）**：`define()` fallback UID 改 id+RuntimeWarning；snapshot 自由变量 `val is None` 不再静默；`IbDeferred/IbBehavior.to_native()` 未执行时抛 RuntimeError（不再静默 `return self`）；`iter_cells()` 上提至 Scope 协议
- ✅ **intent_context OOP MVP（§9.5）**：`IntentContextAxiom.is_class=True`；`INTENT_CONTEXT_SPEC = ClassSpec(...)`；实例方法 `__init__/push/pop/fork/resolve/merge/clear` + 作用域控制方法 `clear_inherited/use/get_current` 注册
- ✅ **`in` / `not in` 运算符**：`IbCompare` 支持成员检测；`str`/`list`/`dict` 均实现 `__contains__` vtable
- ✅ **标准库方法补全**：`str.{find_last, is_empty, replace, startswith, endswith, trim, to_upper, to_lower}`；`list.{insert, remove, index, count, contains}`；`dict.{pop, contains, remove}`；`Exception(msg)` 构造 + `e.message` 字段；`list + list` 拼接；610 测试通过
- ✅ **Step 8（架构边界文档化）**：`interpreter.py`/`engine.py`/`service.py` 头部添加边界说明注释
- ✅ **Bug #1 修复（IbBool(False) 假值）**：`result.value if result and result.value` 三处改为 `result is not None and result.value is not None`；修复 `bool b = @~ MOCK:FALSE ~` 报 `Type mismatch` 及 bool/int 零值被误替换为 None
- ✅ **Bug #2 修复（重复 `_stmt_contains_behavior`）**：删除 `semantic_analyzer.py` 中 AI Agent 遗留的残缺重复定义（只处理 `IbExprStmt`/`IbAssign`/`IbReturn`），恢复正确版本（含 `IbIf`/`IbWhile`/`IbFor`）；修复 `llmexcept` 跟在 `if/while/for @~...~:` 后始终报 SEM_050 的问题
- ✅ **Bug #3 修复（泛型专化崩溃）**：三处联合修复：`_resolve_type` 改调 `self.registry.resolve_specialization()`；`SpecRegistry.resolve_specialization` 修正 `hasattr` 检查名称 + 补全新注册 Spec 的方法成员；`list[str]`/`dict[str,int]`/`tuple[int]` 等泛型标注完全可用

---

## ✅ COMPLETED：__prompt__ 系列协议对用户自定义类的局限性

~~**问题描述（已修复）**：~~

已完成修复（2026-04-19）：

| 协议 | 用户 IBCI 自定义类 | Python Axiom 内置类型 |
|------|-------------------|----------------------|
| `__to_prompt__` | ✅ 有效（vtable 消息传递路由） | ✅ 有效 |
| `__from_prompt__` | ✅ **已修复**（vtable 回退路径） | ✅ 有效 |
| `__outputhint_prompt__` | ✅ **已修复**（vtable 回退路径） | ✅ 有效 |

**修复内容**：
1. `_parse_result()`（`llm_executor.py`）：Axiom 路径无匹配时，通过 `registry.get_class(type_name).lookup_method('__from_prompt__')` 调用用户 vtable 方法（以 `IbClass` 为 receiver，类方法语义）。返回值约定为 `(bool, any)` 元组（成功标志 + 解析值）。
2. `_get_llmoutput_hint()`（`llm_executor.py`）：Axiom 路径无匹配时，通过 vtable 查找 `__outputhint_prompt__`（以 `IbClass` 为 receiver）。
3. `IbObject.__outputhint_prompt__()`（`kernel.py`）：委托给 vtable `receive('__outputhint_prompt__', [])`，vtable 缺失时退回默认字符串。

**用户 IBCI 类实现约定**：
```ibci
class MyType:
    str field

    func __from_prompt__(str raw) -> tuple:
        # 解析 raw，返回 (True, parsed_value) 或 (False, "错误提示")
        return (True, raw)

    func __outputhint_prompt__(self) -> str:
        return "请返回一个 JSON 格式的 MyType 对象"
```

---

## Step 8：概念边界文档化 [✅ COMPLETED — 2026-04-20]

三个核心文件头部已添加架构边界说明注释：

- `core/runtime/interpreter/interpreter.py` 头部：明确 Interpreter = 执行隔离单元，不是 LLM 并发单元
- `core/engine.py` 头部：明确 Engine = 组装者，不参与执行
- `core/runtime/host/service.py` 头部：明确 DynamicHost（HostService）= 编排者，不亲自执行 IBCI 代码

---

## Step 8-pre：llmexcept 快照隔离约束完整落地 [✅ COMPLETED — 2026-04-19]

快照隔离模型已在代码层面完全自洽：

1. **§9.2 编译期 read-only 约束**（SEM_052）✅：llmexcept body 内向外部作用域变量的任何赋值（含类型标注重声明）产生 `SEM_052` 编译期错误；body-local 新声明变量和 `retry` 语句不受限制。新增 `TestLLMExceptBodyReadOnly` 覆盖 6 个测试场景。
2. **§9.3 `_last_llm_result` per-snapshot 化** ✅：读取后立即清零共享字段（不再依赖 `finally` 块恢复）；`LLMExceptFrame.last_result` 是 per-snapshot 权威来源；idbg `last_result()` / `last_llm()` 改为帧优先模式；`retry_stack()` 含帧私有 `last_result` 详情（替代始终为 None 的 `last_llm_response`）。
3. **§9.4 用户自定义对象深克隆快照** ✅：`LLMExceptFrame._try_deep_clone()` 递归克隆用户 IBCI 对象实例，字段回滚在 retry 时生效；函数/行为/原生对象不参与快照（跳过，不影响正确性）。
4. **§9.5 用户协议快照（方案B）** ✅：`LLMExceptFrame` 新增 `saved_protocol_states`；`_save_vars_snapshot()` 检测 vtable 中的 `__snapshot__` 方法，优先调用（方案B）；`_restore_vars()` 对方案B对象调用 `__restore__(state)` 原地恢复，方案A对象替换变量绑定；`__snapshot__` 调用失败时自动降级到方案A。

---

## Step 9a：M3a CPS 调度循环骨架 [✅ COMPLETED — 2026-04-28]

详见 `docs/COMPLETED.md §十`。`core/runtime/vm/` 子包提供 VMExecutor + 21 节点 generator handler；与原 `Interpreter.visit()` 并存，未实现节点回退到 `execution_context.visit(uid)`；49 个 VM 单元测试新增。

---

## Step 9b：M3b 控制信号数据化 [✅ COMPLETED — 2026-04-28]

详见 `docs/COMPLETED.md §十一`。`vm/task.py` 新增 `Signal(kind, value)` frozen 数据对象；handler 改为 `return Signal(...)` 而非 `raise CSE`；`IbWhile` 直接消费 BREAK/CONTINUE，`IbModule`/`IbIf` 透传其他信号；调度器在 `StopIteration.value` 是 Signal 时通过 `gen.send` 数据化向上传递；顶层未消费仍包装为 `ControlSignalException` 抛给调用者（边界兼容）。22 个新增单元测试。

---

## Step 10a：M5a DDG 编译器分析 [✅ COMPLETED — 2026-04-28]

详见 `docs/COMPLETED.md §十二`。`IbBehaviorExpr` 扩展 `llm_deps: List[IbBehaviorExpr]` + `dispatch_eligible: bool` 字段；新建 `BehaviorDependencyAnalyzer` 作为 SemanticAnalyzer Pass 5，扫描 `$var` 插值并通过 Tarjan SCC 推导 dispatch_eligible；`FlatSerializer` 自动把依赖列表转为 UID 引用（无需修改）。16 个新增单元测试。

---

## Step 10/11/12：后续里程碑

- **M3c**：llmexcept retry + intent fork/restore 调度化（依赖 M3b ✅）✅ COMPLETED
- **M3d**：Interpreter.visit() 主路径切换到 VMExecutor（依赖 M3c ✅）✅ COMPLETED（M3d-prep 扩展 CPS handler；C13 修复 `IbUserFunction.call()` 中 VMExecutor 查找路径，使函数体首次真正经由 VM 路径执行）
- **M4**：Layer 2 多 Interpreter 并发（DynamicHost.spawn 线程化，依赖 M3a ✅ + M3d ✅ + C10/C13 ✅）⏳ **当前主线下一步**
- **M5b**：LLMScheduler（ThreadPoolExecutor + LLMFuture，依赖 M5a ✅）✅ COMPLETED
- **M5c**：VM dispatch-before-use 集成（依赖 M5b ✅ + M3c ✅）✅ COMPLETED
- **M6**：可移植性参考实现 + 完整并发行为测试套件（依赖 M3d ✅ + M4 + M5c ✅）

详见 `docs/VM_EVOLUTION_PLAN.md` 与 `docs/PENDING_TASKS_VM.md`。

---

## 任务依赖图（精确版）

```
Step 1–8 + M1 + M2 + M3a + M3b + M3c + M3d + M5a + M5b + M5c + 轻量债务清理（已完成；949 测试通过）
    │
    └──→ M4（多 Interpreter 并发，依赖 M3a/M3d ✅，C10/C13 已清理）⏳ **当前主线**
            │
            └──→ M6（可移植性 + 合规测试套件）
```

**当前优先路径**：**M4（多 Interpreter 并发）** 为下一里程碑——其前置债务（C10 body 循环统一、C13 VMExecutor 查找直接化）已在 2026-04-29 的轻量债务清理 PR 中完成。其它较大重构债务（C7/C8/C11/C14）按计划延后到 M6 后统一处理。

---

## Step 12.5：fn 参数化 lambda/snapshot 新语法 [✅ COMPLETED — 2026-04-28]

> **完成总结**：M1 全部落地，旧语法已彻底移除（parse error）。详见 `docs/COMPLETED.md §六/§七/§八`。

### 实际落地的语法（最终形式：声明侧返回类型）

```ibci
int fn f = lambda: EXPR
int fn f = lambda(PARAMS): EXPR
str fn f = snapshot: EXPR
str fn f = snapshot(PARAMS): EXPR

# 无返回类型标注（不带 TYPE）
fn f = lambda: EXPR
fn f = lambda(PARAMS): EXPR
fn f = snapshot: EXPR
fn f = snapshot(PARAMS): EXPR
```

### 已移除的旧语法（现产生 parse error）

```ibci
int lambda f = expr          # ❌
auto snapshot g = expr       # ❌
fn lambda h = expr           # ❌
lambda(EXPR)                 # ❌ 旧括号体
lambda(PARAMS)(EXPR)         # ❌ 旧括号体
fn f = lambda -> int: EXPR   # ❌ PAR_005（表达式侧返回类型）
```

---

## 元组解包 / for-tuple 现状（2026-04-27 实测核实）

| 写法 | 行为 | 备注 |
|------|------|------|
| `int a, int b = t` | ✅ 已修复（裸列形式元组解包） | 与 Python `a, b = t` 对齐 |
| `(int a, int b) = t` | ✅ 正常 | 等价写法 |
| `(int a, int b) = (1, 2, 3)` | ❌ 运行期 `RUN_001: Unpack error` | 元数检查正确 |
| `(int a, str b) = (1, "x")` | ✅ 正常 | 混合类型 |
| `for (int x, int y) in list[tuple]` | ✅ 已修复 | 类型标注精确 |
| `tuple t = (1, 2); auto a = t[0]` | ✅ 正常 | 下标访问 |

---

*本文档记录近期可执行任务。VM 架构长期设想（三层并发/llmexcept危险悬案）见 `docs/PENDING_TASKS_VM.md`；低优维护性任务见 `docs/DEFERRED_CLEANUP.md`。*

