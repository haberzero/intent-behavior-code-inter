# IBC-Inter 近期优先任务

> 本文档记录当前可直接开工且具有明确优先级的任务。  
> 低优先级挂起事项统一见 `docs/PENDING_TASKS.md`。  
> 完整任务背景与设计分析见 `docs/CURRENT_TASKS.md`。
>
> **最后更新**：2026-05-08（类型系统 M1–M5 全部收口；测试基线 1180 passed）

---

## 当前状态概览

类型系统五大里程碑（M1–M5）全部完成：

- [x] M1：TypeRef 引入（2026-05-07，+103 tests，基线 1159）
- [x] M2：Optional[T] 与空安全落地（2026-05-07，基线 1179）
- [x] M3：TypeDef 单一化 + callable-instance 路线收口（2026-05-08，基线 1182）
- [x] M4：运行时值模型单一化（IbValue）（2026-05-08，基线 1184）
- [x] M5：Axiom 接口统一化（单一 TypeAxiom Protocol）（2026-05-08，基线 1184→1180）

**当前无开放的类型系统 P0 主线。**

---

## 近期任务（按优先级）

### P1：callable-instance 术语代码清洗

**目标**：消除运行时层残留的旧"延迟求值（deferred）"术语误导性注释，与类型系统 M3 的术语统一对齐。

**范围**：
- `core/runtime/objects/builtins.py`：`IbDeferred` / `IbBehavior` 类注释
- `core/runtime/vm/handlers.py`：`_vm_call_deferred()` 及相关注释
- 评估 `factory.create_deferred()` 方法名是否需要添加 callable-instance 别名

**不属于此项工作的内容**：序列化格式字段名（`"deferred"` 作为线协议标识符，不改动）

**参考**：`docs/CURRENT_TASKS.md §一`

---

### P2：str + llm_uncertain 兼容拼接移除

**目标**：移除 `IbString.__add__()` 中对 `llm_uncertain` 的静默拼接兼容逻辑，改为显式类型错误。

**背景**：`builtins.py:322-330` 的 TODO 注释表明，这一兼容逻辑是在 try/except 机制完善之前的临时安全阀。try/except 已于 2026-05-06 完整落地，前置条件已满足，可以清理。

**改动**：
1. `IbString.__add__()` 中 `ib_class.name == "llm_uncertain"` 分支改为抛出 `InterpreterError`，错误消息提示使用 `llmexcept` 处理
2. 补充相关测试（确认 `str + uncertain_var` 报错，`llmexcept` 捕获路径完整）

**参考**：`docs/CURRENT_TASKS.md §三`

---

### P2：fn 高阶函数类型标注端到端测试

**目标**：通过测试确认 `fn[(...)->(...)]` 在复杂场景下的类型推导与结构匹配是否完整，发现并修复退化路径。

**测试场景**：
1. 嵌套签名：`fn[(fn[(int)->int]) -> int]`
2. 高阶函数返回 fn 类型的返回值类型传播
3. lambda/snapshot 传入 `fn[...]` 参数时的结构匹配

**参考**：`docs/CURRENT_TASKS.md §二`

---

## 低优先级任务处理规则

所有非 P1/P2 任务统一维护在 `docs/PENDING_TASKS.md`（通用挂起任务）和 `docs/PENDING_TASKS_VM.md`（VM 架构长期目标）中。

本文件不展开低优先级任务细节，以保持近期任务的清晰度。
