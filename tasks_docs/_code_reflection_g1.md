# 反射规避架构缺陷修复 — 组 1：LLM 协议并入（临时任务文档）

> 临时任务文档，Phase 5 完成后经用户确认删除。
> **状态**：全部完成（U1-U10），全量 pytest 1263 passed / 4 skipped。

## 修改单元清单

### U1：`ILLMProvider` 协议并入 `get_retry` ✅
- `core/base/interfaces.py` `ILLMProvider` 加 `def get_retry(self) -> int: ...`
- AIPlugin 已实现（`ibci_modules/ibci_ai/core.py:269`），零改动

### U2：`LLMExecutor`/`IILLMExecutor` 协议并入 4 方法 ✅
- `core/runtime/interfaces.py` `LLMExecutor` 加：`resolve(node_uid) -> Any`、`dispatch_eager(node_uid, execution_context, intent_ctx=None) -> Any`、`hydrate(service_context)`、`run_batch(behavior, items, execution_context) -> List[Any]`
- `core/base/interfaces.py` `IILLMExecutor` 同样并入（4 方法 + 保持协议一致性）
- LLMExecutorImpl 已实现（`_scheduler.py` resolve/dispatch_eager、`_core.py` hydrate、`_behavior.py` run_batch），零实现改动

### U3：`IHostService` 协议并入 `orchestrator` 属性 ✅
- `core/runtime/interfaces.py` `IHostService` 加 `orchestrator` property
- `core/runtime/interpreter/service_context.py:124` `set_orchestrator` 去 `hasattr`，改直用 `self._host_service.orchestrator = ...`
- **连带修复**：`HostService` 需显式实现 `orchestrator` property（带 setter）——因协议 property 会被继承为数据描述符，原先的实例属性赋值 `self.orchestrator = ...` 会触发 AttributeError。改为 `self._orchestrator` + property getter/setter。

### U4：`ServiceContext` 协议并入 `interpreter` 属性 ✅
- `core/runtime/interfaces.py` `ServiceContext` 加 `interpreter` property
- `core/runtime/rt_scheduler.py:117` `getattr(self.service_context, 'interpreter', None)` 改 `self.service_context.interpreter if self.service_context else None`
- ServiceContextImpl 已实现（`service_context.py:62`），零实现改动

### U5：`Scope` 协议并入 UID API 与 `registry` ✅
- `core/runtime/interfaces.py` `Scope` 加：`assign_by_uid(uid, value, skip_type_check=False) -> bool`、`get_symbol_by_uid(uid) -> Optional[RuntimeSymbol]`、`promote_to_cell(sym_uid) -> Optional[Any]`、`registry` property（带默认实现）
- `core/runtime/interpreter/runtime_context.py:157,191,236` 三处 `hasattr(self._parent, ...)` 改直用
- `core/runtime/interpreter/runtime_context.py:44` `hasattr(parent, '_registry')` 改 `parent.registry`
- **连带修复**：`ScopeImpl` 添加公开 `registry` property（委托 `_registry`），否则 `parent.registry` AttributeError

### U6：`_shared.py:443-452` `_get_max_retry` 协议化 ✅
- `cap_reg.get("llm_provider")` 直用（CapabilityRegistry.get 恒存在）
- `llm_provider.get_retry()` 直用（并入 ILLMProvider 后恒存在），None 守卫保留
- `getattr(sc, "capability_registry", None)` 保留（sc 可为 None，Optional 合理）

### U7：`leaf.py:76` / `assignment.py:68` / `interpreter.py:237` 去 hasattr ✅
- 三处 `hasattr(llm_executor, ...)` 改直接调用；保留 `if llm_executor is not None` 守卫

### U8：`ibci_ai/core.py:284-301` 去冗余探测 ✅
- `getattr(self._capabilities, "kernel_registry", None)` → capabilities dataclass 恒有，直用
- `hasattr(kr, "get_llm_executor")` → 恒有，直用
- `hasattr(executor, "get_current_call_info")` → 已并入协议，直用
- `hasattr(executor, "run_batch")` → 已并入协议，直用（保留 None 守卫 + fail-fast 语义）

### U9：`control_flow.py:277-292` elements 探测改 isinstance ✅
- 首分支 `hasattr(iterable_obj, "elements")` 改 `isinstance(iterable_obj, (IbList, IbTuple))`
- **注意**：不能用 `isinstance(x, IIbList)`——IbTuple 无 append/pop/len 不满足 IIbList，会漏掉 tuple 改变行为。用具体类元组 `(IbList, IbTuple)` 判定，行为等价。
- receive 路由（用户自定义类异构）保留

### U10：`engine.py:349-359` 机械性去冗余 ✅
- `getattr(self.interpreter.service_context, 'llm_executor'/'host_service', None)` → 公开属性直用
- `getattr(self.interpreter._execution_context, 'stack_inspector', None)` → `self.interpreter.execution_context.stack_inspector`（execution_context 有公开 property）

## 验证
- 全量 `python -m pytest tests/`：**1263 passed / 4 skipped**
- 组 1 LLM 目标命中点已清零（残留 `ibcext.py` `_capability_registry` 属组 2；`kernel_native_modules.py:99` hydrate 是外部 kernel-native 合法 C 类）
