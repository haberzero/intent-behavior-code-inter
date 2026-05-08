# 当前任务控制文档（最新）

> 本文档用于追踪当前阶段的主线任务控制。
> 以当前代码状态为准。
>
> 最后更新：2026-05-08

---

## 一、主线目标

围绕以下系统做下一步收敛：
- 意图注释系统（`@ / @! / @+ / @-`）
- 行为描述语句（`@~...~`）
- VM 与解释器调度系统
- callable-instance 语义统一（`lambda` / `snapshot` / `fn`）

---

## 二、当前共识与审计结论

### 1) deferred 概念定位（重点）
- 当前类型层已统一为 `TypeKind.CALLABLE_INSTANCE`。
- 历史“deferred 作为类型分叉”已完成收口；`capture_mode` 位于 AST/运行时值层。
- 但代码中仍保留 `IbDeferred` 类名与部分历史术语，存在认知噪音，需继续命名与注释收敛。

### 2) lambda / snapshot 的当前语义
- 两者都是右值关键字，构造 callable-instance。
- `lambda`：调用时读取当前生效上下文（含意图栈）。
- `snapshot`：创建时冻结上下文快照（含意图栈），调用时忽略调用处上下文变化。
- 语义本质更接近“函数实例化语义差异”，不应继续被描述为旧路线中的“延迟调用特例”。

### 3) fn 关键字的双角色
- 变量侧：可调用实例推导入口（类似 auto，但针对 callable）。
- 类型标注侧：高阶函数签名约束（`fn[(...)->(...)]`）。
- 在类型系统更新后，应继续推进 fn 在泛型/HOF 场景下的表达与诊断能力。

---

## 三、专项检查：字符串真值与 llm_uncertain

### 现状审计
- 真值判断主入口：`is_truthy(value) -> value.receive('to_bool', [])`。
- `IbLLMUncertain.to_bool()` 返回 false（0），参与条件判断为假。
- 仍保留过渡兼容：`str + llm_uncertain` 被允许并拼接为 `"uncertain"`。
  - 编译期：`StrAxiom.resolve_operation_type_name` 允许 `str + llm_uncertain -> str`
  - 运行时：`IbString.__add__` 对 `llm_uncertain` 特判拼接

### 风险与下一步
- 该兼容路径可能掩盖不确定性来源，建议纳入主线收敛：
  - 明确退出条件（何时改为错误/异常路径）
  - 明确与 llmexcept / LLM 错误体系的协同策略

---

## 四、下一步任务清单（执行顺序）

1. 明确意图注释语法与 `intent_context` 对象 API 的最终边界规范。
2. 清理 callable-instance 相关历史术语与变量命名（deferred 噪音清理）。
3. 形成 fn/HOF 泛型表达增强的专项设计与测试矩阵。
4. 收敛 `llm_uncertain` 字符串拼接过渡策略，补齐迁移方案与兼容窗口说明。
5. 在 VM/解释器文档与代码注释中统一上述术语与边界，确保新贡献者认知一致。
