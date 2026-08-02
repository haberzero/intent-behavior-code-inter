# 反射规避架构缺陷修复 — 组 6：orchestrator 注入收敛（临时任务文档）

> 临时任务文档，Phase 5 完成后经用户确认删除。
> **状态**：全部完成，全量 pytest 1263 passed / 4 skipped。

## 方案 A（用户裁决）：收敛 orchestrator 单一注入路径

### 问题（既有缺陷，非本次引入）
生产路径的 orchestrator 构造注入链恒失效（双通道）：
- `HostService`/`Interpreter`/`ServiceContextImpl` 构造的 orchestrator 参数恒收 None（spawn 时 sc 未 hydrate）
- 真实注入完全依赖 `set_orchestrator` 事后同步（功能必需，曾被误判为死代码）

### 修改单元

| # | 文件 | 改动 |
|---|---|---|
| A1 | `rt_scheduler.py` | 删 line 77 Interpreter 构造的 orchestrator 参数（死值 getattr）；删 line 92 HostService 构造的 orchestrator 参数 |
| A2 | `interpreter.py` | `__init__` 删 orchestrator 参数；删传给 ServiceContextImpl 的行 |
| A3 | `service_context.py` | `__init__` 删 orchestrator 参数 + 赋值行；`set_orchestrator` docstring 更新为"唯一注入点" |
| A4 | `host/service.py` | `__init__` 删 orchestrator 参数，`_orchestrator = None` 初始；property 保留 setter |
| A5 | `test_runtime_host_collect.py` | `_make_service` 改 property setter 注入（与生产路径一致） |
| A6 | `test_host_save_state.py` | 删 orchestrator=None 构造参数 |

### 注入闭环（方案 A 后）
```
_prepare_interpreter:
  A. rt_scheduler.spawn()
     ├ Interpreter(...)          # 无 orchestrator 参数
     ├ HostService(...)          # 无 orchestrator 参数，_orchestrator = None
     └ sub_sc.set_host_service(host_service)
  B. set_orchestrator(self)      # ★唯一注入点
     ├ sub_sc._orchestrator = engine
     └ host_service.orchestrator = engine   # 同步（功能必需）
```

## 验证
- 全量 `python -m pytest tests/`：1263 passed / 4 skipped
- 相关测试：test_e2e_multi_interpreter + host_collect + host_save_state = 29 passed
- 残留扫描：无构造传 orchestrator、无 getattr(sc,'orchestrator') 残留
