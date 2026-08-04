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

### C2 设计裁定：join 返回容器 + Rust 风格直接取值方法（2026-08-04）

**用户裁定**：`t.join()` 返回 `thread_result[T]` 容器（非 T）。§2.3 例 `int r = t.join()` 需改为 `thread_result[int] r = t.join()` 再取 value。

**易用方法**（用户要求：参考 Rust 的直接返回 value 方法，设计历史已归档无此记录，自主设计）：
- §2.5 已有：`unwrap()`→Optional[T]（失败返回 Optional 空，不抛）、`unwrap_or(default)`→T、`is_error()`/`is_success()`、`.value`（失败抛错）、`.error`（不抛）。
- **新增 `expect()`**（Rust 对齐）：直接返回 T，失败抛 IBCI 异常（fail-fast）。`expect()` 是"明确直接返回 value"的方法，弥补 `unwrap()` 返回 Optional 不直接取 T 的缺口。
- **`status`**：容器持有状态（done/cancelled/failed），经内省方法暴露。

**容器成员**：`value()`、`error()`、`status()`、`is_error()`、`is_success()`、`unwrap()`、`unwrap_or(default)`、`expect()`。
- **value/error/status 为方法**（`r.value()` 等），符合疏漏 4"内省方法取代裸属性"裁决（非裸属性）。

**join 语义**：`join()` 返回容器。成功 → `status=done`、`value=T`、`error=null`；失败/取消 → `status=failed/cancelled`、`error=err`、`value=null`。成功值经 `expect()`/`.value()`/`.unwrap()` 取。

## 五、验证

- 新增 `tests/runtime/test_thread_model.py`（构造/状态机/join/cancel/is_done/线程隔离）。
- 新增 `tests/runtime/test_thread_result.py`（容器方法 + join 返回容器）。
- 全量 `python -m pytest tests/` 零回归。

## 六、待办（按序）

- [x] C0：`_get_callee_param_specs` 支持 IbClass + `_auto_init` 补 param_meta（+ 测试）—— **已完成 2026-08-04**（commit 35b0691，4 用例，全量 1443+4 零回归）
- [x] C1：`IbThread` 值对象 + 状态机—— **已完成 2026-08-04**（thread.py + primitive_initializer 注册 __init__ + ThreadAxiom has_call_cap + resolve_return_type_name；5 用例，全量 1447 passed 零回归）
- [x] C2：`thread_result[T]` 容器—— **已完成 2026-08-04**（TypeKind.THREAD_RESULT + THREAD_RESULT_SPEC + create_thread_result + GenericTypeRegistry + ThreadResultAxiom + IbThreadResult + join 返回容器 + value/error/status/is_error/is_success/unwrap/unwrap_or/expect；9 用例（thread_model 5 + thread_result 4），全量 1457 passed 零回归）
- [x] C5：序列化—— **已完成 2026-08-04**（serializer thread_result value_type 持久化 + rehydrator THREAD_RESULT shell + runtime_serializer thread_result 值序列化/反序列化；全量 1457 passed 零回归）
- [x] C6：测试 + 全量验证—— **已完成 2026-08-04**（新增 cancel/线程隔离用例；全量 1459 passed / 4 skipped 零回归）

## 任务 C 完成小结

任务 C（线程对象模型）**已完成 2026-08-04**：
- C0 前置：类构造关键字参数支持（commit 35b0691）
- C1：IbThread 值对象 + 生命周期状态机（commit 5ebbcfd）
- C2：thread_result[T] 容器 + join 返回容器 + expect()（commit e30487c）
- C5：序列化（commit 21b3ce6）
- C6：测试验证（11 用例，全量 1459 passed / 4 skipped 零回归）

**待办**：任务 D（err 类型统一）、任务 E（线程相关清理，含 save_state 未完成线程检测）、任务 F（关键字精简 + 废除旧测试）。见 `NEXT_STEPS.md` 主线。

## 任务 D：err 类型统一（已完成 2026-08-04）

按 THREAD_DESIGN_REVISION §2.6 实施：

- **`TaskError` 层次**：`TaskError`（parent Exception）→ `TaskCancelled`/`TaskFailed`（parent TaskError），均为 IBCI CLASS spec + axiom。用户可见、可继承（`class MyTaskError(TaskError)` 验证通过）、`except TaskError`/`except Exception` 按继承链捕获。
- **`make_task_cancelled`/`make_task_failed`**：kernel registry 运行时工厂（与 make_llm_parse_error 模式一致）。
- **`cancel()` 返回 err**：成功发出取消请求 → `TaskCancelled` err（含 message）；未启动/已结束 → None。
- **`join()` 错误值化**：线程失败/取消时把底层异常映射为 IBCI err 对象存入容器（用户 raise → 原 IBCI 异常对象；协调器 TaskCancelled → IBCI TaskCancelled；其他 → TaskFailed）。
- **`expect()` 抛容器内 err**：经 `ThrownException` 抛出，语言层 try/except 按类型捕获。
- **`IbThreadResult.error()`** 返回 IBCI 错误对象（如 `<Instance of LLMParseError>`）。

测试：新增 `tests/runtime/test_thread_err.py`（5 用例）。全量 pytest **1464 passed / 4 skipped** 零回归。

## 任务 E：线程相关清理（已完成 2026-08-04）

按 THREAD_DESIGN_REVISION VP-1~VP-6 + F-1~F-8 处理：

**已完成（coordinator / observability / serializer / save_state）**：
- **VP-2**：`_drive_generator` 死 `_task_handle` 引用 → 改为显式传入 `handle`（`_run`→`_run_task_body`→`_drive_generator` 全链透传）。
- **F-2**：`RuntimeCoordinator._tasks` 只增不减 → `spawn` 注册 `add_done_callback` 自动清理（防泄漏）。
- **F-1**：快照双数据源 → `snapshot.py` 补充从 `RuntimeCoordinator` 收集线程任务（单数据源）。
- **疏漏 4（save_state 未完成线程检测）**：`save_state` 在 `unfinished_handles()` 非空时抛异常 fail。
- **save_state 磁盘型误判修复**：`_contains_disk_backed_instance` 把类对象（IbClass）误判为 disk-backed 实例（file_handle/audio/image/video 类常驻 prelude，导致 save_state 永久拒绝）→ 跳过 IbClass。
- **序列化瞬态线程**：thread 值序列化为存根（`thread_transient`，读 fields 状态），不递归 coordinator（否则经 `_interpreter → EC → scope → t` 引用环无限递归）；修正 `IbThread.to_native` 返回原生 bool。

**随任务 F 删除（旧 spawn/join/cancel 关键字路径）**：
- VP-1（join 阻塞式）、VP-4（except:pass 兜底）、VP-5（TaskAxiom 无方法表面）——位于旧 comm.py handler / TaskAxiom，任务 F 删除关键字时一并清除。
- VP-3（cancel 覆盖用户函数路径缺失）、VP-6（完成后 cancel 覆盖结果）——经复核，VP-6 已有 `not self._future.done()` 守卫；VP-3 属协作式取消设计边界（纯 CPU 用户函数无可挂起点），记录为设计取舍，随任务 F 清理评估。

测试：新增 `tests/runtime/test_thread_cleanup.py`（4 用例）。全量 pytest **1468 passed / 4 skipped** 零回归。

## 任务 F：关键字精简（已完成 2026-08-04）

按 THREAD_DESIGN_REVISION §2.2 + 任务 F：删除 spawn/join/cancel/task 关键字全链 + 废除旧测试 + 新测试。

**删除（全链）**：
- **lexer**：`core_scanner.py` KEYWORDS 移除 'spawn'/'join'/'cancel'/'task'；`tokens.py` 移除 SPAWN/JOIN/CANCEL/TASK TokenType。
- **parser**：`statement.py` 移除 spawn_statement/join_statement/cancel_statement/_parse_spawn_call + 语句起始匹配；`expression.py` 移除 spawn_expr/join_expr + 前缀注册；`type_def.py` 移除 TASK 类型注解；`recognizer.py` 移除 TASK 声明起始。
- **AST**：`ast.py` 移除 IbSpawnStmt/IbJoinStmt/IbCancelStmt。
- **semantic**：`_statement_visitors.py` 移除 visit_IbSpawnStmt/visit_IbJoinStmt/visit_IbCancelStmt + 死 `_is_task_type`。
- **VM**：`comm.py` 移除 vm_handle_IbSpawnStmt/IbJoinStmt/IbCancelStmt；`dispatch.py` 移除注册。
- **spec**：`specs.py` 移除 TASK_SPEC；`_runtime.py` 移除 TASK_SPEC；`comm.py` 移除 TaskAxiom；`registry.py` 移除注册。
- **runtime 对象**：删除 `objects/task.py`（IbTask，死代码）。

**废除旧测试 + 重写**：
- `test_concurrency_syntax.py`：移除 spawn/join/cancel/task 语法/语义/序列化测试，保留 chan/signal/slot。
- `test_vm_comm.py`：移除 TestSpawnJoinE2E。
- `test_vm_instance.py`：重写为 thread 对象模型语法（函数/多线程/隔离/cancel/实时输出）。

**修复（实现中发现）**：
- `_thread_init` 实参传递 bug：`args_obj.to_native()` 使 IbList 内 chan/slot 值对象退化为原生快照丢失身份 → 改为 IbList 元素直接取出（保持 IbObject 身份）。

**验证**：旧 spawn/join/cancel/task 语法全部编译失败（已验证）；新 thread 对象模型测试覆盖。全量 pytest **1453 passed / 4 skipped** 零回归（净减 15：废除旧 spawn/join/cancel/task 测试，新 thread 测试已计入）。

### C1 实现细节记录（2026-08-04）

- **构造参数名**：`callable`（非关键字）。设计文档原 `fn`/`func` 均与关键字碰撞，按"内部接口设计不违反关键字碰撞"原则裁定弃用。
- **`IbThread` 值对象**（`core/runtime/objects/thread.py`，`@register_ib_type("thread")`）：实例状态存于 `self.fields`（与 `intent_context` 模式一致）。句柄方法 `start`/`join`/`cancel`/`is_done` 自包含操作 fields，不依赖实例私有 helper（实例是普通 `IbObject`）。
- **构造**：`primitive_initializer` 注册 thread 类 `__init__` 原生方法（param_meta 声明 callable/args），经 `_init_fields` 初始化状态并 eager 启动。
- **`ThreadAxiom`**：`has_call_cap = True`（允许 `thread(...)` 构造调用）+ `resolve_return_type_name` 返回 "thread"（具体泛型由声明上下文确定）。
- **eager 语义**：构造即启动后台线程（与既有 spawn 语义一致）。