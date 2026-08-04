# 临时任务文档 — 任务 C 线程对象模型（含前置机制完善）

> 按 `code-workflow` 建立的临时任务文档。Phase 5 汇报后经用户确认删除。
> 状态：**调研完成，进入方案设计**。唯一决策依据：`tasks_docs/THREAD_DESIGN_REVISION.md`。

## 一、任务范围

实施线程对象模型方向修正任务 C：`thread[T]` 类型 + 构造函数 + 句柄方法（start/join/cancel/is_done）+ 生命周期状态机。

**任务 C 前置机制缺口（用户侧机制不完善，阻碍任务 C 推进）**：
类构造的关键字参数支持缺失——`_get_callee_param_specs` 不处理 `IbClass`，导致 `thread(fn=..., args=...)` 的关键字参数无法传递。此缺口同时影响用户类构造（`Dog(name=..., age=...)` 当前报错）。须先完善此机制，再实现 thread 构造。**此机制完善已纳入本任务规划（C0 前置），任务路径相应调整。**

## 二、调研结论（已确认代码事实）

| 项 | 位置 | 事实 |
|----|------|------|
| thread 类型已就绪 | `comm.py:37-59` / `specs.py:85` / `factory.py:258` / `generic.py` | `ThreadAxiom` + `THREAD_SPEC` + `create_thread` + `GenericTypeRegistry`；`thread[T]` 解析成功 |
| join 返回类型特化 | `_members.py:121-127` | `thread[T].join()`/`result()` → T |
| 内核机制可复用 | `coordinator.py` | `RuntimeCoordinator` + `SpawnedTask`（后台线程 + 任务本地上下文） |
| 现有 IbTask 是 spawn 句柄 | `task.py:22-84` | 需改造为 thread 对象 + 句柄方法 |
| spawn/join/cancel/task 是关键字 | `core_scanner.py:40-46` + parser | 任务 F 删除 |
| thread 不是关键字 | `core_scanner.py` KEYWORDS 无 thread | `thread(...)` 走普通 `IbCall`，func 是 `IbName("thread")` |
| **类构造关键字参数缺口** | `_shared.py:91-111` | `_get_callee_param_specs` 不处理 `IbClass` → 关键字参数被忽略 |
| `_auto_init` 生成的 `__init__` 无 param_meta | `interpreter.py:674-696` | 需补 param_meta 支持关键字构造 |
| 用户显式 `__init__` 是 IbUserFunction | `interpreter.py:642` | 有 AST 参数，`_get_callee_param_specs` 已处理 |

## 三、C0 前置：类构造关键字参数支持（机制完善）

**目标**：`thread(func=..., args=...)` 及用户类 `Dog(name=..., age=...)` 的关键字构造可用。

**设计裁决（关键字碰撞原则，2026-08-04）**：设计文档 §2.3 示例 `thread(fn=compute, ...)` 中的 `fn` 是保留关键字（`TokenType.FN`），与"内部接口设计不违反关键字碰撞"架构原则冲突。按"架构原则优先"裁定，thread 构造参数名**不使用 `fn`**，改用不与关键字碰撞的 `callable`（`callable` 非关键字，`args` 亦非关键字）。设计文档措辞相应调整（`fn`→`callable`）。

**设计**：
1. `_get_callee_param_specs`（`_shared.py`）增加 `IbClass` 分支：返回其 `__init__` 方法的参数签名。
   - `__init__` 是 `IbUserFunction`（显式定义）→ 走 `_build_runtime_param_specs`（AST 参数）。
   - `__init__` 是 `IbNativeFunction`（`_auto_init` 生成）→ 需其 `param_meta` 已填充。
2. `_auto_init`（`interpreter.py:674-696`）生成 `__init__` 时设置 `param_meta`（字段名 → `(name, POSITIONAL_OR_KEYWORD, None)`）。
3. 验证：`_resolve_call_arguments_runtime` 把关键字解析为位置序，`instantiate` 按序调用 `__init__`。

## 四、任务 C：线程对象模型

**设计**（按 THREAD_DESIGN_REVISION §八，自主决策并记录）：
1. **`IbThread` 值对象**（`core/runtime/objects/thread.py`，`@register_ib_type("thread")`）：改造 `IbTask`，继承 `IbObject`，持有 `_coordinator`/`_spawned`/`_callable`/`_args`/`_value_type` + 生命周期状态机 + `thread_result[T]` 容器。
2. **生命周期状态机**：idle → running → done / cancelled / failed。`start()` 启动；`join()` 等待返回 T；`cancel()` 返回 err；`is_done()` 查询。
3. **`thread_result[T]` 容器**（`core/runtime/objects/thread_result.py`，`@register_ib_type("thread_result")`）：`value`/`error`/`status` + `is_error`/`is_success`/`unwrap`/`unwrap_or`。禁止 any。
4. **构造**：`thread(callable=..., args=...)` 走普通 `IbCall` + C0 机制。thread 类需注册 `__init__` 原生方法接收 callable/args，创建 `IbThread`。
   - **参数名**：`callable`（非关键字）。设计文档原 `fn`/`func` 均与关键字（`TokenType.FN`/`FUNC`）碰撞，按"内部接口设计不违反关键字碰撞"架构原则裁定弃用，改用 `callable`（`args` 本身非关键字，保留）。
5. **`ThreadAxiom` 方法表面修正**：`join` → T、`cancel` → err（任务 D 细化，此处先对齐）。
6. **序列化**：thread/thread_result 值类型持久化。

## 五、验证

- 新增 `tests/runtime/test_thread_model.py`（构造/状态机/join/cancel/is_done/线程隔离）。
- 全量 `python -m pytest tests/` 零回归。

## 六、待办（按序）

- [x] C0：`_get_callee_param_specs` 支持 IbClass + `_auto_init` 补 param_meta（+ 测试）—— **已完成 2026-08-04**（commit 35b0691，4 用例，全量 1443+4 零回归）
- [x] C1：`IbThread` 值对象 + 状态机—— **已完成 2026-08-04**（thread.py + primitive_initializer 注册 __init__ + ThreadAxiom has_call_cap + resolve_return_type_name；5 用例，全量 1447 passed 零回归）
- [ ] C2：`thread_result[T]` 容器
- [ ] C3：thread 构造函数注册 + 绑定（已完成 C1 内：`thread(callable=..., args=...)` 关键字构造可用）
- [ ] C4：ThreadAxiom 方法表面对齐（join → T、cancel → err，任务 D 细化）
- [ ] C5：序列化
- [ ] C6：测试 + 全量验证

### C1 实现细节记录（2026-08-04）

- **构造参数名**：`callable`（非关键字）。设计文档原 `fn`/`func` 均与关键字碰撞，按"内部接口设计不违反关键字碰撞"原则裁定弃用。
- **`IbThread` 值对象**（`core/runtime/objects/thread.py`，`@register_ib_type("thread")`）：实例状态存于 `self.fields`（与 `intent_context` 模式一致）。句柄方法 `start`/`join`/`cancel`/`is_done` 自包含操作 fields，不依赖实例私有 helper（实例是普通 `IbObject`）。
- **构造**：`primitive_initializer` 注册 thread 类 `__init__` 原生方法（param_meta 声明 callable/args），经 `_init_fields` 初始化状态并 eager 启动。
- **`ThreadAxiom`**：`has_call_cap = True`（允许 `thread(...)` 构造调用）+ `resolve_return_type_name` 返回 "thread"（具体泛型由声明上下文确定）。
- **eager 语义**：构造即启动后台线程（与既有 spawn 语义一致）。