# COMPLETED（精简里程碑）

> 只保留关键里程碑与阶段结论。
> 详细历史过程与旧日志已归档到 `docs/HISTORY_LOG.md`。
>
> 最后更新：2026-05-08

---

## 1) 类型系统主线（M1–M5）

- M1：TypeRef 引入（跨模块/泛型引用统一）
- M2：Optional[T] 空安全落地
- M3：TypeDef 单一化（字段统一为 TypeRef）
- M4：运行时值承载统一到 `IbValue(type_ref, payload, fields, meta)`
- M5：Axiom 接口统一（`TypeAxiom` + `has_*_cap`）

状态：✅ 已完成（主线收口）

---

## 2) callable-instance 路线收敛

- `TypeKind.DEFERRED` / `TypeKind.BEHAVIOR` 已统一为 `TypeKind.CALLABLE_INSTANCE`
- 类型层不再承载 `capture_mode`；`capture_mode` 保留在 AST/运行时值层
- `lambda` / `snapshot` 作为右值关键字构造 callable-instance

状态：✅ 已完成（基础收敛）

---

## 3) VM / 解释器主路径

- 主执行路径为 VMExecutor CPS 调度循环
- 控制流信号通过 `Signal` 数据对象传播
- llmexcept 采用快照隔离与显式重试帧

状态：✅ 已完成（主路径稳定）

---

## 4) 意图系统阶段结论

- `IbIntentContext` 已成为运行时核心状态对象
- `intent_context` 内置类型可实例化并具备基础对象 API
- 函数调用意图上下文采用 fork 隔离

状态：✅ MVP 已完成；完整对象化收敛进入后续主线

---

## 5) 当前测试基线

- `python -m pytest tests/ -q --tb=short`
- 当前结果：`1180 passed`（2026-05-08 本仓实测）
