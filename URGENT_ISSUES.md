# 紧急问题清单（Code Review 2026-04-28）

> 来源：代码全链路审查（IbCell / 闭包 / fn / 语义分析器 / 类型系统）  
> 优先级：**高** = 正确性风险或严重误导；**中** = 代码健康度；**低** = 维护性改善  
> 状态：⚠️ 待修复 / ✅ 已修复
>
> **当前状态（2026-04-28，M3b/M5a 完成后）**：高优 H1/H2/H3 ✅ + 中优 M1/M2/M3/M4/M5 ✅ 全部修复。L1–L4 维护性改善 + 兼容性回退清理已搬到 [`docs/DEFERRED_CLEANUP.md`](docs/DEFERRED_CLEANUP.md)（M3b 完成后新增 1 项：彻底删除 `ControlSignalException` 边界封装类，等 M3d 主路径切换后处理）。本文件保留作为修复历史归档。

---

## 高优先级（正确性风险 / 严重文档误导）

### [H1] ✅ FIXED (2026-04-28) `IbDeferred` docstring 严重落后于 M2 实现
**文件**：`core/runtime/objects/builtins.py:703-707`  
**修复**：docstring 更新为 M2 语义（`closure` 字段说明覆盖 lambda/snapshot 两种模式；`captured_scope` 路径说明已删除）。

---

### [H2] ✅ FIXED (2026-04-28) `_captured_scope` 僵尸字段存活
**文件**：`core/runtime/objects/builtins.py`，`core/runtime/factory.py`，`core/runtime/interfaces.py`，`core/runtime/interpreter/handlers/expr_handler.py`，`core/runtime/interpreter/handlers/stmt_handler.py`  
**修复**：删除 `IbDeferred.__init__` 的 `captured_scope` 参数及 `self._captured_scope` 赋值；同步清理 `factory.py`、`interfaces.py` 中的签名，以及 `expr_handler.py`、`stmt_handler.py` 中的死参传递。

---

### [H3] ✅ FIXED (2026-04-28) `DeferredAxiom.is_compatible` 与自身文档语义矛盾
**文件**：`core/kernel/axioms/primitives.py`  
**修复**：移除 `or other_name.startswith("behavior[")` 这行，使 `is_compatible` 与 docstring 一致。

---

## 中优先级（代码健康度）

### [M1] ✅ FIXED (2026-04-28) IbDeferred.call() 和 IbBehavior.call() 中的"兼容历史"死分支
**文件**：`core/runtime/objects/builtins.py`  
**修复**：两处均改为直接解包 `for sym_uid, (name, cell) in self.closure.items()`，删除 `else` 分支。

---

### [M2] ✅ FIXED (2026-04-28，M3a PR 同步修复) `define()` 的 fallback UID hash 生成
**文件**：`core/runtime/interpreter/runtime_context.py:100-115`  
**修复**：fallback UID 改为 `id(sym)`-based 唯一标识，避免相同 (name, type, value) 的不同变量产生相同 UID 而静默覆盖；新增 `warnings.warn(..., RuntimeWarning)` 显式告警；`import warnings` 提到模块顶层。
**残留任务**：合法路径都已注入 UID，未来可把 warning 升级为 `assert`，彻底删除 fallback 分支（已转入 `DEFERRED_CLEANUP.md`）。

---

### [M3] ✅ FIXED (2026-04-28，M3a PR 同步修复) snapshot 模式自由变量捕获静默失败
**文件**：`core/runtime/interpreter/handlers/expr_handler.py`（`_collect_free_refs` 附近）  
**修复**：`val is None` 不再静默跳过，改为通过 `debugger.trace(BASIC)` 输出诊断警告。

---

### [M4] ✅ FIXED (2026-04-28，M3a PR 同步修复) `IbDeferred.to_native()` / `IbBehavior.to_native()` 静默返回 self
**文件**：`core/runtime/objects/builtins.py`  
**修复**：未执行时抛出 `RuntimeError`，不再静默返回 self；同步更新 `tests/e2e/test_e2e_m2_higher_order.py::TestCollectGcRoots` 过滤未执行的延迟值。

---

### [M5] ✅ FIXED (2026-04-28，M3a PR 同步修复) `collect_gc_roots()` 用 `hasattr` 做接口检查
**文件**：`core/runtime/interfaces.py`、`core/runtime/interpreter/runtime_context.py`  
**修复**：`iter_cells()` 提升到 `Scope` 协议（默认空迭代器实现）；`collect_gc_roots()` 移除 `hasattr` 检查，改为直接调用。

---

## 低优先级（维护性改善）

> **L1–L4 已搬到 [`docs/DEFERRED_CLEANUP.md`](DEFERRED_CLEANUP.md)，等待下一个独立 PR 处理。**

---

## 汇总统计（最终）

| 优先级 | 问题数 | 已修复 | 剩余 |
|--------|--------|--------|------|
| 高 | 3 | **3** ✅ | 0 |
| 中 | 5 | **5** ✅ | 0 |
| 低 | 4 | 0 | 4（已转入 `DEFERRED_CLEANUP.md`）|
| **合计** | **12** | **8** | 4（低优维护性）|

> H1/H2/H3/M1 于 2026-04-28 修复（780 测试通过）；M2/M3/M4/M5 于 2026-04-28 M3a PR 同步修复（829 测试通过）。L1/L2/L3/L4 维护性改善已转入 [`docs/DEFERRED_CLEANUP.md`](DEFERRED_CLEANUP.md)，并在该文件中追加了 4 个已识别的兼容性回退清理条目。
