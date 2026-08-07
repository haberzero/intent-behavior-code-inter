# _code: PT-FEAT-9 内核结构化诊断机制重建（B-E 阶段）

> 临时任务文档（Phase 5 汇报后删除）。设计权威源：`tasks_docs/DIAGNOSTIC_DESIGN.md`（冻结）。

## 修改单元

### B 机制落地
- [x] ① codes.py 增 `=== 内核诊断 (KDIAG_) ===` 节（10 码）
- [ ] ② 新建 `core/runtime/observability/diagnostics.py`（kernel_diagnostic helper）
- [x] ③ events.py docstring 对账 —— 已在 P4 完成（如实清单）；新增 kernel_diagnostic 后补入清单
- [ ] ④ helper 单测（警告触发/事件门控/rc 缺省/stacklevel 归属）

### C 站点迁移（12 处，逐批文案逐字）
| 码 | 文件:行 | context |
|----|---------|---------|
| KDIAG_PROTOCOL_TO_PROMPT_FALLBACK | intent.py:74 | intent_resolution |
| KDIAG_PROTOCOL_TO_PROMPT_FALLBACK | kernel/base.py:103 | cast |
| KDIAG_PROTOCOL_FROM_PROMPT_FALLBACK | kernel/base.py:138 | parse |
| KDIAG_PROTOCOL_FROM_PROMPT_FALLBACK | llm_parsing_strategy.py:245 | vtable |
| KDIAG_PROTOCOL_PAYLOAD_PROMPT_FALLBACK | _prompt.py:91 | - |
| KDIAG_PROTOCOL_VALIDATE_FALLBACK | llm_parsing_strategy.py:204 | - |
| KDIAG_PROTOCOL_SNAPSHOT_FALLBACK | llm_except_frame.py:183 | - |
| KDIAG_PROTOCOL_RESTORE_FALLBACK | llm_except_frame.py:267 | - |
| KDIAG_POLICY_MODULE_OVERRIDE | host_interface.py:67 | kernel 层惰性 import（先例 registry.py:283） |
| KDIAG_POLICY_MODULE_NO_EXPORT | loader.py:330 | - |
| KDIAG_RUNTIME_COLLECT_SKIP | engine.py:867 | - |
| KDIAG_RUNTIME_STAGE_SKIP | interpreter.py:273 | - |

边界：scheduler.py:364 保持 warnings（D5 编译期）。

### D 事件投影测试
- [ ] 协议回退事件测试（如 __from_prompt__ 失败站点）
- [ ] 策略忽略事件测试（kernel-native 覆盖）
- [ ] 运行时跳过事件测试
- [ ] 门控测试（observability 关 → 事件不发射、警告保留）

### E docs 治理
- [ ] docs/architecture/ 章节（诊断面职责/事件形态/代码表）
- [ ] WORKLOG 记录
- [ ] NEXT_STEPS/PENDING_TASKS 收敛

## 决策记录
- B③ 复用既有完成态；events.py docstring 增补 kernel_diagnostic 入如实清单。
- host_interface（kernel 层）站点：惰性 import kernel_diagnostic（先例 registry.py:283 惰性 import EventBus）。
- 事件订阅测试走 `runtime.subscribe()`（IBCI 面）或 `rc.get_event_bus().subscribe()`（Python 面）。
