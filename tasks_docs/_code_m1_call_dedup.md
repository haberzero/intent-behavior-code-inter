# _code_m1_call_dedup — M1 `.call` 双写收敛（PT-DEBT-15 剩余）

> **性质**：临时任务文档（实施完删除）。独立分支 exp/async-m1m2 实验。
> **背景**：`_ASYNC_UNIFY.md` M1——各 CPS 路径保留同步 `.call()` 孪生（作用域/实参绑定
> 双写）。收敛为单一 CPS 权威路径；`.call` 变薄宿主包装（驱动 CPS 生成器），消双写。

## 现状（Phase 1 理解）

VM 主路径（leaf.py:347-404）已全部走 CPS：
- `fn_callable` → `_vm_call_fn_callable`、`behavior` → `_vm_invoke_behavior`、
  `llm_function` → `_vm_invoke_llm_function`、`user_function` → `UserFunctionCall`（trampoline）。
- 剩余走 `receive('__call__')` → `.call()` 同步后备的仅 native/bound method（合法，非任务内路径）。

`.call()` 同步后备用于**宿主/线程/反序列化**场景（非 VM 主路径），每个携带完整绑定逻辑：
- `IbUserFunction.call`（user_functions.py:41）——模块切换/意图 fork/scope/closure/self+super/实参绑定/栈 + `vm.run_body`
- `IbFnCallable.call`（callables.py:87）——scope/closure/snapshot 深克隆/实参绑定 + `vm.run`
- `IbBehavior.call`（callables.py:355）、`IbLLMFunction.call`（user_functions.py:191）

**双写**：这些 `.call()` 的绑定逻辑与 `_vm_call_*` CPS 版本重复。

## 方案（已实现）

`.call()` 变薄宿主包装：委托对应 `_vm_call_*` CPS 生成器 + `_drive_generator`
（M2 已统一为 TaskScheduler 驱动 `_drive_loop_gen`）驱动到完成，消绑定双写。

**已完成 4/4 对象**：
- `IbFnCallable.call` → `_vm_call_fn_callable` + `_drive_generator`
- `IbUserFunction.call` → `_vm_call_user_function` + `_drive_generator`
- `IbLLMFunction.call` → `_vm_invoke_llm_function` + `_drive_generator`
- `IbBehavior.call` → `_vm_invoke_behavior` + `_drive_generator`

### 实现中修正（自我质询 + 实测）
- **返回值语义核对**：`IbUserFunction.call` 旧实现无 RETURN 返回 `ib_none`，
  CPS `_vm_call_user_function` 返回末语句结果——用探针实测 void/none/ret 三例，
  两者返回一致（IbNone/IbNone/42），收敛安全。
- **rt_context 解析差异**：旧 `.call()` 用 `_get_frame()`（调用现场 ContextVar），
  CPS 用 `executor.runtime_context`——实测收敛后宿主/反序列化路径语义一致。
- **清理死 import**：user_functions.py 移除 `_get_frame`/`IbSuperProxy`/`Location`/
  `IntentRole`/`_is_intent_context_param`/`_should_activate_intent_context_arg`/
  `InterpreterError`/`RUN_CALL_ERROR`。
- **保留合法原生**：`IbNativeFunction.call`/`IbBoundMethod.call`（functions.py）
  是真同步原生调用，无 CPS 孪生，**不属于 M1 范围**（保持）。
- **保留绑定 helper**：`bind_behavior_closure`/`bind_behavior_call_args` 仍被
  `_shared.py`/`_behavior.py` 使用，保留于 callables.py。

### 边界
- `.call()` 在无 vm_executor（反序列化/纯宿主无 VM）时保持 fail-fast（原语义一致）。
- receiver 语义：user_function/llm_function 经 CPS `receiver` 槽注入（self/super），
  与旧 `.call()` 绑定等价。

## 验证
- 全量 pytest 2128 passed / 1 skipped 零回归（宿主直调 / 反序列化 / vtable /
  LLM 解析 / behavior / slot.update 既有路径全过）。
- **M1 成功判据达成**：单一 CPS 权威路径 + 薄宿主包装，消绑定双写。
  M3（prompt 单源）已收敛（`_evaluate_segments` 已是 `_evaluate_segments_cps` 宿主包装）。
