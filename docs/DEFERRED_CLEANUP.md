# 延迟清理任务清单

> **建立时间**：2026-04-28  
> **来源**：从 `URGENT_ISSUES.md` 转入的低优先级维护性条目 + 2026-04-28 文档/代码一致性审查识别的"可彻底清理的兼容性回退"  
> **属性**：以下任务均不影响正确性，目标是工程美观与可维护性  
> **触发方式**：作为下一个独立的"代码债务清理 PR"一次性处理；不混入 M3b/M5a 等主线特性 PR

> **测试基线**：本文件中所有任务必须保持 `python3 -m pytest tests/ -q` 测试基线不退化。

---

## 一、URGENT_ISSUES 转入的维护性改善（L1–L4）

### [L1] `IbLambdaExpr.returns` 兼容字段彻底删除
**文件**：`core/kernel/ast.py:444`，`core/compiler/semantic/passes/semantic_analyzer.py:1749-1755`  
**当前状态**：`IbLambdaExpr.returns` 字段已标注"解析器不再设置"，但 `visit_IbLambdaExpr` 内仍有 `elif node.returns is not None: returns_type = self._resolve_type(node.returns)` 回退路径。  
**根因**：fn declaration-side 语法落地后，`_pending_fn_return_type` 完全替代了表达式侧返回类型；旧字段成为僵尸字段，elif 永不命中。  
**目标**：
1. 删除 `IbLambdaExpr.returns: Optional[IbASTNode]` 字段
2. 删除 `visit_IbLambdaExpr` 中的 elif 回退分支
3. 同步更新 docstring 与 `core/compiler/serialization/serializer.py`/`core/runtime/loader/artifact_rehydrator.py` 中可能涉及的字段读写（应已无依赖，但需确认）

**风险**：若某些缓存的 artifact 还携带 `returns` 字段，反序列化时会忽略；建议同时清理 artifact 缓存目录。

---

### [L2] `get_vars()` 硬编码内置函数过滤名单
**文件**：`core/runtime/interpreter/runtime_context.py:481`  
**当前**：
```python
if symbol.is_const and name in ("len", "print", "range", "input", "get_self_source"):
    continue
```
**目标**：在 `RuntimeSymbolImpl` 上添加 `is_builtin: bool` 标志位，由 `builtin_initializer.py` 在注册内置函数时设置；`get_vars()` 通过标志过滤而非硬编码名单。

---

### [L3] `_pending_fn_return_type` 隐式上下文通道注释
**文件**：`core/compiler/semantic/passes/semantic_analyzer.py`  
**目标**：仅在注释/docstring 中明确说明 visit_IbAssign → visit_IbLambdaExpr 隐式通道的嵌套安全性保证，并注明这是刻意的设计决策（避免后续维护者误以为"未完成的临时方案"而擅自重构）。无代码改动。

---

### [L4] `_collect_free_refs` 启发式子节点遍历注释
**文件**：`core/runtime/interpreter/handlers/expr_handler.py`  
**目标**：在 `_collect_free_refs` 内部展开逻辑处加注释，说明"字段值是字符串且存在于 node_pool"是启发式遍历，并解释为什么 UID 格式（UUID/哈希前缀）使碰撞概率极低。无代码改动。

---

## 二、兼容性回退彻底清理（2026-04-28 审查识别）

### [C1] `LLMExceptFrame._is_serializable()` 死代码删除
**文件**：`core/runtime/interpreter/llm_except_frame.py:258-262`  
**当前**：
```python
def _is_serializable(self, val: IbObject) -> bool:
    """判断值是否可序列化（兼容旧接口，内部委托给 _try_deep_clone）。"""
    return self._try_deep_clone(val) is not None
```
**事实**：全仓库 `grep _is_serializable` 仅此一处定义，零调用点。完全死代码。  
**目标**：直接删除该方法。同步把 `docs/COMPLETED.md §四`、`docs/ARCH_DETAILS.md` 中描述该方法的段落改写为"已删除"备注或直接删除该段。

---

### [C2] `LLMExecutor.execute_behavior_expression` 中 `captured_intents` 旧路径分支删除
**文件**：`core/runtime/interpreter/llm_executor.py:486-494`  
**当前**：
```python
else:
    # 兼容旧路径：IntentNode 链表（to_list）或已展平的列表
    active_list = captured_intents.to_list() if hasattr(captured_intents, 'to_list') else captured_intents
    ...
```
**事实**：自 Step 6c/6d 完成后，所有生产者只产出 `None` 或 `IbIntentContext` 实例（见 `expr_handler.visit_IbBehaviorExpr` 中 `fork_intent_snapshot()` 调用）。`IntentNode.to_list()` 路径无产生方。  
**目标**：
1. 把 else 分支替换为 `raise TypeError(f"Unexpected captured_intents type: {type(captured_intents)}")`
2. 收紧 `core/runtime/interfaces.py` `IBehavior.captured_intents` 注解为 `Optional[IbIntentContext]`（去掉 `Union[List[Any], Any]`）
3. 同步收紧 `core/runtime/objects/builtins.py` `IbBehavior.__init__` 注解
4. 检查 `core/runtime/serialization/runtime_serializer.py` 序列化路径是否依赖 list 形态（如有需要保留 list↔IbIntentContext 互转）

---

### [C3] `ScopeImpl.define()` fallback UID 路径升级为断言
**文件**：`core/runtime/interpreter/runtime_context.py:101-115`  
**当前**：M3a PR 修复为 `id(sym)`-based fallback + `RuntimeWarning`；但目前合法编译路径下 warning 应**永远不触发**。  
**目标**：
1. 先把 warning 提升为 `error`-level 跑一轮 829 测试，确认 0 触发
2. 若 0 触发，把 fallback 分支替换为 `assert uid is not None, "ScopeImpl.define(): caller must provide UID; bootstrapper bug?"`
3. 删除 fallback UID 生成代码

**风险**：如果发现某条引导路径仍依赖 fallback，需先修该引导路径再删除 fallback。

---

### [C4] `IbDeferred.body_uid is None` 空值兼容路径审计
**文件**：`core/runtime/objects/builtins.py:791-792`  
**当前**：
```python
# 2) 评估目标节点：M1 参数化路径走 body_uid，否则走 node_uid（与历史一致）
target_uid = self.body_uid if self.body_uid else self.node_uid
```
**事实**：M1 之后所有 `visit_IbLambdaExpr` 路径均会设置 `body_uid`；遗留的"`body_uid is None` → 用 `node_uid`"分支可能仅服务于已废弃的 IbAssign deferred_mode 直接构造路径。  
**目标**：审计是否仍有路径产出 `body_uid=None` 的 IbDeferred；若无，则添加断言 `assert self.body_uid is not None`，并把表达式简化为 `target_uid = self.body_uid`。

---

### [C5] `ControlSignalException` 边界封装类删除（M3b 完成后引入）
**文件**：`core/runtime/vm/task.py::ControlSignalException`  
**当前状态**：M3b 已经把 VM 内部的控制流迁移为 `Signal(kind, value)` 数据对象；但 `ControlSignalException` 作为**边界封装**保留：
1. `VMExecutor.run()` 在顶层栈空仍持有 Signal 时包装为 CSE 抛给调用者
2. `fallback_visit()` 路径中递归解释器抛出的 `ReturnException`/`BreakException`/`ContinueException` 仍会被捕获并转 CSE 沿帧栈传播
3. 现有外部测试 `pytest.raises(ControlSignalException)` 依赖该类型

**目标**：M3d 完成（全部节点 CPS 化、`Interpreter.visit()` 主路径切换到 VMExecutor）后：
1. 删除 `fallback_visit` 中的 `ReturnException`/`BreakException`/`ContinueException` → CSE 转换路径
2. 删除 `VMExecutor.run()` 顶层 Signal → CSE 包装路径，调用方直接处理 Signal
3. 把 `ControlSignalException` 类彻底删除；`from_signal()` 也一并移除
4. 调整使用 `pytest.raises(ControlSignalException)` 的测试为检查 `Signal` 数据对象

**风险**：M3d 之前删除会破坏现有 `IbCall` / `IbFunctionDef` 的 RETURN 语义，因为这两个节点尚未 CPS 化。

---

## 三、PR 操作建议

1. **顺序**：建议在 M3b + M5a 主线 PR 合并之后，把 L1–L4 + C1–C4 集中到一个独立的 **"chore: deferred cleanup (L1–L4 + C1–C4)"** PR。**C5 必须等 M3d 完成后**作为后续 PR 处理。
2. **分阶段验证**：每完成一个条目立即跑 `python3 -m pytest tests/ -q --tb=short` 确认 0 退化。
3. **测试基线**：以 M3b/M5a 完成后的最新基线（**867 个测试**）为准；若中间 M3c/M3d 已合并，以那时基线为准。
4. **参考资料**：`URGENT_ISSUES.md`（修复历史归档）、`docs/COMPLETED.md`（每条变更对应的章节）。

---

## 四、本文件维护

* 完成某条目后，把对应小节标记为 `✅ DONE — YYYY-MM-DD` 并简述实际改动。
* 若执行过程中识别新的可清理回退，追加到第二节末尾并编号 C5/C6/...
* 若某条目执行过程中暴露出更深的设计问题（应转为高优 issue），把它升级到 `URGENT_ISSUES.md` 而非留在本文件。
