# IBC-Inter 近期优先任务

> 记录接下来可以直接开工的具体任务，按优先级排列。  
> 中长期任务见 `docs/PENDING_TASKS.md`，已完成工作见 `docs/COMPLETED.md`。  
> VM 架构长期设想（含三层并发模型、llmexcept 危险悬案）见 `docs/PENDING_TASKS_VM.md`。
>
> **最后更新**：2026-04-19（意图上下文隔离 + @! 函数屏蔽 + intent_context OOP MVP + lambda 参数约束落地；551 个测试通过）

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
- ✅ **函数调用意图隔离（§9.4）**：`IbUserFunction.call()` + `IbLLMFunction.call()` 实现 fork/restore；`@!` 修饰函数调用创建隔离子上下文；`@` 修饰限制仍为 LLM 行为表达式
- ✅ **lambda 参数传递约束**：`deferred_mode='lambda'` 的延迟对象作为函数实参时运行时报错；`snapshot` 不受限
- ✅ **intent_context OOP MVP（§9.5）**：`IntentContextAxiom.is_class=True`；`INTENT_CONTEXT_SPEC = ClassSpec(...)`；原生方法 `__init__/push/pop/fork/resolve/merge/clear` 注册；551 测试通过

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
        # 解析 raw，返回 (true, parsed_value) 或 (false, "错误提示")
        return (true, raw)

    func __outputhint_prompt__(self) -> str:
        return "请返回一个 JSON 格式的 MyType 对象"
```

---

## Step 8：概念边界文档化 [P3 - 可随时推进]

在完成 Step 5-7 后，用代码注释强化已明确的架构边界：

- `core/runtime/interpreter/interpreter.py` 头部：明确 Interpreter = 执行隔离单元，不是 LLM 并发单元
- `core/engine.py` 头部：明确 Engine = 组装者，不参与执行
- `core/runtime/host/service.py` 头部：明确 DynamicHost = 编排者，不亲自执行 IBCI 代码

---

## Step 8-pre：llmexcept 快照隔离约束完整落地 [✅ COMPLETED — 2026-04-19]

快照隔离模型已在代码层面完全自洽：

1. **§9.2 编译期 read-only 约束**（SEM_052）✅：llmexcept body 内向外部作用域变量的任何赋值（含类型标注重声明）产生 `SEM_052` 编译期错误；body-local 新声明变量和 `retry` 语句不受限制。新增 `TestLLMExceptBodyReadOnly` 覆盖 6 个测试场景。
2. **§9.3 `_last_llm_result` per-snapshot 化** ✅：读取后立即清零共享字段（不再依赖 `finally` 块恢复）；`LLMExceptFrame.last_result` 是 per-snapshot 权威来源；idbg `last_result()` / `last_llm()` 改为帧优先模式；`retry_stack()` 含帧私有 `last_result` 详情（替代始终为 None 的 `last_llm_response`）。
3. **§9.4 用户自定义对象深克隆快照** ✅：`LLMExceptFrame._try_deep_clone()` 递归克隆用户 IBCI 对象实例，字段回滚在 retry 时生效；函数/行为/原生对象不参与快照（跳过，不影响正确性）。
4. **§9.5 用户协议快照（方案B）** ✅：`LLMExceptFrame` 新增 `saved_protocol_states`；`_save_vars_snapshot()` 检测 vtable 中的 `__snapshot__` 方法，优先调用（方案B）；`_restore_vars()` 对方案B对象调用 `__restore__(state)` 原地恢复，方案A对象替换变量绑定；`__snapshot__` 调用失败时自动降级到方案A。

---

## Step 9：VM CPS 调度循环 [P2 - IExecutionFrame 接口完整后可推进]

**前提**：Step 5 IExecutionFrame 接口已完整（✅ 已具备）

**本质**：消除当前解释器的 Python 递归调用栈，改用 CPS（Continuation-Passing Style）调度循环，支持：
- 解释器不再受 Python 调用栈深度限制
- 为 Layer 2 多 Interpreter 并发（`DynamicHost.spawn` 线程化）铺路

详见 `docs/PENDING_TASKS_VM.md`。

---

## Step 10：Layer 1 LLM 流水线 [P2 - Step 6 意图 fork 完成后可推进]

**前提**：Step 6 `IbIntentContext.fork()` 已完整（✅ 已具备）

**本质**：DDG 编译器 + `LLMScheduler` 实现 dispatch 时刻意图绑定，支持 LLM 调用并行化。

详见 `docs/PENDING_TASKS_VM.md`。

---

## Step 11：Layer 2 多 Interpreter 并发 [P3 - Step 5 ContextVar 完整后]

**前提**：Step 5 ContextVar（多线程下帧状态隔离）已完整（✅ 已具备）

**本质**：`DynamicHost.spawn` 线程化，每个 Interpreter 实例持有独立 ContextVar 槽位。

详见 `docs/PENDING_TASKS_VM.md`。

---

## 任务依赖图（历史完成路径）

```
Step 4b（完成）
    │
    ├──→ Step 5a（IExecutionFrame Protocol 定义）[✅ 完成]
    │        │
    │        └──→ Step 5b（ContextVar，IbUserFunction 去除 context 参数）[✅ 完成]
    │                    │
    │                    └──→ Step 6a（IntentContextAxiom）[✅ 完成]
    │                                 │
    │                                 ├──→ Step 6b（IbIntentContext 运行时对象）[✅ 完成]
    │                                 │            │
    │                                 │            └──→ Step 6c（RuntimeContextImpl 迁移）[✅ 完成]
    │                                 │                         │
    │                                 │                         └──→ Step 6d（LLMExceptFrame 修复）[✅ 完成]
    │                                 │
    │                                 └──→ Step 7（LlmCallResultAxiom + IbLLMCallResult 接入）[✅ 完成]
    │
    └──→ Step 8（文档化，随时可做）
```

**下一优先路径**：Step 8（架构边界文档化，随时可做）→ Step 9（CPS 调度循环）→ Step 10（LLM 流水线）→ Step 11（多解释器并发）

---

*本文档记录近期可执行任务。VM 架构长期设想（三层并发/llmexcept危险悬案）见 `docs/PENDING_TASKS_VM.md`。*

