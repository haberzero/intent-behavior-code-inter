# IBC-Inter 近期优先任务

> 本文档只记录当前可直接开工且必须优先执行的任务进度。  
> 低优先级事项统一转入 `docs/PENDING_TASKS.md`。

> **最后更新**：2026-05-08（M4 `IbValue` 运行时值模型已落地；M5 成为当前唯一未完成的类型系统主线）

---

## 当前唯一最高优先级主线

### 类型系统演进与重构（立即执行）【P0】

- 架构原文（完整）：`docs/IBCI_TYPE_SYSTEM_FROM_ZERO_ARCHITECTURE.md`
- 专项任务清单：`docs/TYPE_SYSTEM_TASKS.md`

#### 进度管控

- [x] M1：TypeRef 引入（兼容阶段）— 完成（2026-05-07，+103 tests，总 1159 passed）
- [x] M2：Optional[T] 与空安全落地（完成 2026-05-07：OptionalSpec + assignability + artifact rehydration + Optional 方法语义收口；全量 1179 passed）
- [x] M3：TypeDef 单一化（完成 2026-05-08：所有扁平 `*_name`/`*_module` 字段全面 TypeRef 化，无残留；测试基线 1182 passed）
- [x] M3→M5 补充：fn/lambda/snapshot 统一为 callable-instance 路线 — 完成（2026-05-08：`TypeKind.DEFERRED` + `TypeKind.BEHAVIOR` 合并为 `TypeKind.CALLABLE_INSTANCE`，`deferred_mode` 概念彻底删除并重命名为 `capture_mode`，全栈一致）
- [x] M4：运行时值模型单一化（IbValue）— 完成（2026-05-08：`IbValue(type_ref, payload, fields, meta)` 已成为运行时值公共承载层；现有 `IbInteger/IbList/IbBehavior/...` 退化为兼容包装层，装箱与运行时对象结构统一）
- [ ] M5：Axiom 接口统一化

#### 当前执行要求

- [ ] 每个里程碑完成后同步更新本文件进度。
- [ ] 每个里程碑完成后同步测试基线与风险状态。
- [ ] 低优先级事项不进入本文件，只在 pending 跟踪。
- [x] callable-instance 路线落地后，相关 `fn` 失败用例已收口；当前测试基线为 **1184 passed**。

---

## 低优先级任务处理规则

- 所有非类型系统任务统一视为低优先级。
- 低优先级任务统一维护在 `docs/PENDING_TASKS.md`。
- 本文件不再展开低优先级任务细节。
