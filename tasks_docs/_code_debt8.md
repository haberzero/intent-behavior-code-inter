# _code_debt8 — 值层分派收敛审计（PT-DEBT-8 重定义）

> 临时任务文档（Phase 5 汇报后删除）。
> 依据：用户系统层面审视——折叠为单一 IbValue 是伪目标（收益已通过 name/vtable 分派兑现），
> 真正价值 = 收敛残留精确 isinstance 分派 + 固化"类角色分工"设计决策。

## 任务定义（替代原"折叠 IbXxx→IbValue"）

1. **审计**：全量定位运行时值层的精确 isinstance 分派点，分类为"合理保留"vs"该收敛"。
2. **收敛**：把该统一的精确 isinstance（具体值类名作分派依据）改为 name/协议分派。
3. **文档化**：在 architecture 固化"值层具体类 = 领域方法实现载体，IbValue = 统一值载体"。
4. **更新**：PENDING_TASKS 重定义 PT-DEBT-8，注明折叠为伪目标的决策依据。

## 审计基线（已核实）

- 运行时精确 isinstance 值层分派点：`numbers.py`(2)、`leaf.py`(IbNone/IbLLMUncertain)、
  `runtime_context.py`(IbOptional/IbNone/IbLLMUncertain)、`seq.py`/`control_flow.py`(IbList/IbTuple)、
  `runtime_serializer.py`(IbValue 守卫，name 分派)、`_shared.py`/`control_flow.py`/`_behavior.py`(IbValue+name)。
- `isinstance(x, IbValue)` 作为"值对象 vs 内核对象"守卫：**合理保留**（二分语义，非值层内分派）。
- 待收敛核心：具体值类名（IbNone/IbLLMUncertain/IbOptional/IbList/IbTuple）作分派依据的点。
