# IBC-Inter 近期优先任务

> 本文档只记录当前可直接开工且必须优先执行的任务进度。  
> 低优先级事项统一转入 `docs/PENDING_TASKS.md`。

> **最后更新**：2026-05-08（M5 Axiom 接口统一化已落地；类型系统主线全部里程碑完成；运行时值类型实现层彻底收口）

---

## `deferred` 概念全量清理（✅ 已完成 2026-05-08）

所有命名替换已落地。IBCI 核心代码中不再出现任何与"延迟求值/deferred"相关的命名、字符串或变量名。

**2026-05-08 二次复核结论**：
- `lambda` / `snapshot` 是 IBCI 的基础表达式包装机制，不是 behavior 专属；
- parser 在表达式位置统一构建 `IbLambdaExpr`，body 可为任意表达式；
- semantic pass 按 body 类型分流：普通表达式 → `fn_callable`，`IbBehaviorExpr` → `behavior`；
- VM 运行时按同一 `IbLambdaExpr` 路径构造 `IbFnCallable` 或 `IbBehavior`；
- e2e 覆盖了普通逻辑表达式的 lambda/snapshot（非 behavior 专属路径）。

**命名映射**（`deferred` → `fn_callable`）：

| 旧名称 | 新名称 |
|--------|--------|
| `deferred` 类型 | `fn_callable` |
| `IbDeferred` | `IbFnCallable` |
| `DeferredAxiom` | `FnCallableAxiom` |
| `DEFERRED_SPEC` | `FN_CALLABLE_SPEC` |
| `create_deferred()` | `create_fn_callable()` |
| `IbDeferredField` | `IbClassField` |

---



- 架构原文（完整）：`docs/IBCI_TYPE_SYSTEM_FROM_ZERO_ARCHITECTURE.md`
- 专项任务清单：`docs/TYPE_SYSTEM_TASKS.md`

#### 进度管控

- [x] M1：TypeRef 引入（兼容阶段）— 完成（2026-05-07，+103 tests，总 1159 passed）
- [x] M2：Optional[T] 与空安全落地（完成 2026-05-07：OptionalSpec + assignability + artifact rehydration + Optional 方法语义收口；全量 1179 passed）
- [x] M3：TypeDef 单一化（完成 2026-05-08：所有扁平 `*_name`/`*_module` 字段全面 TypeRef 化，无残留；测试基线 1182 passed）
- [x] M3→M5 补充：fn/lambda/snapshot 统一为 callable-instance 路线 — 完成（2026-05-08：`TypeKind.DEFERRED` + `TypeKind.BEHAVIOR` 合并为 `TypeKind.CALLABLE_INSTANCE`，`deferred_mode` 概念彻底删除并重命名为 `capture_mode`，全栈一致）
- [x] M4：运行时值模型单一化（IbValue）— 完成（2026-05-08：`IbValue(type_ref, payload, fields, meta)` 已成为运行时值公共承载层；现有 `IbInteger/IbList/IbBehavior/...` 退化为兼容包装层，装箱与运行时对象结构统一）
- [x] M5：Axiom 接口统一化 — 完成（2026-05-08：单一 `TypeAxiom` 协议替代旧 9 个 Capability 子协议；具体公理通过 `has_*_cap` 类属性声明能力；`SpecRegistry.get_X_cap()` 统一返回公理或 spec；删除 `_FUNC_SPEC_CALL_CAP` 哨兵与 `WritableTrait` 不可达路径；测试基线 1184 passed）

#### 类型系统主线状态

类型系统专项五大里程碑（M1–M5）全部完成，运行时值实现层亦已收口，无未结主线项。

- `SpecFactory` 方法（`create_func` / `create_class` 等）以 `*_name` / `*_module` 字符串为外部构造 API，内部统一将其转换为 TypeRef 后填入 TypeDef 字段；TypeDef 本身只持有 TypeRef 类型字段，不接受字符串 kwargs。

---

## 低优先级任务处理规则

- 所有非类型系统任务统一视为低优先级。
- 低优先级任务统一维护在 `docs/PENDING_TASKS.md`。
- 本文件不再展开低优先级任务细节。
