# REPORT — T06_class_identity 统一类身份模型回归 + 真实试用

> 2026-08-14。基线：unsafe-vibe-dev（Task1 后），全量 2616 passed / 1 skipped。
> 服务：qwen3.6-35b-a3b @ 127.0.0.1:1234（真实 LLM，响应 <1-2s，reasoning_tokens=0）。
> 套件：`tasks_docs/trials/T06_class_identity/`（20 用例，DESIGN/REGISTER 落档）。

## 一、结论摘要

| 项 | 结果 |
|----|------|
| 统一类身份模型回归 | **18 PASS / 2 KERNEL_ISSUE** |
| T05 KI-1 核销 | ✅（D4-01：线程 worker geo.Box(5).get()=405） |
| 新缺陷 | **1 项 pre-existing**（KERNEL_ISSUE-CROSSMOD-LLM-1） |
| 死循环/超时 | 0 |

## 二、统一类身份模型回归验证（Task1 S1-S4）

### 2.1 入口类 qualified（S2）
- D1-01：`type(b)` 仍显裸名 `Box`（用户语义不变）——**通过**。
- D1-02/D1-04：入口 `Box` 与 `geo.Box` 方法表独立（`5` vs `401`，`main-box` vs
  `geo-box`）——**通过**。
- D1-03：run_string 入口模块名稳定 `__string_exec__`——**通过**。
- D2-01：入口类泛型特化 `main.Box[int]` 运行 + type 显示 `Box[int]`——**通过**。
- D2-06：三模块（geo/graph/data）+ 入口类 4 路同名隔离——**通过**。

### 2.2 单类表（S3）
- D1-05：Enum（仅注册 KernelRegistry 权威表）无 [Enum Hook] 仍正确——**通过**。

### 2.3 KI-1 线程侧表 + is_truthy（S4）
- D4-01：**T05 D1-10 核销**——线程 worker 内 `geo.Box(5).get()` = 405（此前抛
  `Symbol UID missing`）——**通过**。
- D4-02：T05 D1-12 入口遮蔽回归（entry/geo/entry）——**通过**。
- D2-04：线程 worker 内入口类 + 导入类双路径（105/405/105/405）——**通过**。
- D3-04：线程 + LLM + geo 类组合（worker 内 LLM 调用 module 上下文正确）——
  **通过**。

### 2.4 LLM 链 module 感知（S2）
- D2-03/D3-01：入口类 `-> Point` `__from_prompt__` 真实 LLM 解析（type_hint 为
  qualified `main.Point`）——**通过**。
- D2-05/D3-02：跨模块类 `-> geo.Counter` —— **KERNEL_ISSUE**（见下）。

## 三、新暴露缺陷

### KERNEL_ISSUE-CROSSMOD-LLM-1（P1，pre-existing）

跨模块用户类作行为表达式 LLM 输出目标时，编译器未把目标类型（`geo.Counter`）绑定到
行为节点 node_to_type → type_hint='behavior' → LLM parse 链无法解析 → 运行时
`__call__ on None`。

- **触发**：`geo.Counter c = @~ 给一个数字 ~`（annotation 为 IbAttribute 点号限定）。
- **对照**：入口类 `Point p = @~...~`（annotation 为 IbName）正确（D2-03/D3-01 PASS）。
- **定性**：base 7ed9d274 同现——pre-existing，非 S2 引入。比 KNOWN_LIMITS §10.2 的
  "graceful 退化"更严重（运行时崩溃，非降级）。
- **根因**：`_statement_visitors.py` 行为表达式 bind_type 路径对 `IbAttribute` 点号
  限定注解未解析出目标 spec。
- **修复方向**：`_resolve_type` 支持 `IbAttribute` 点号限定注解解析（或在 behavior
  绑定路径补 module 限定），使 node_to_type = `geo.Counter`。待独立窗口。

## 四、批判性评价

1. **Task1 重构稳健**：统一类身份模型（入口类 qualified / 单类表 / KI-1 / is_truthy）
   在真实运行 + 真实 LLM + 并发组合下零回归，T05 KI-1 彻底核销。
2. **并发模块上下文隔离正确**：线程 worker 内入口类 + 导入类 + LLM 全正确（此前
   KI-1 是主要风险面，现已闭合）。
3. **遗留风险面**：跨模块用户类 LLM 输出目标（KERNEL_ISSUE-CROSSMOD-LLM-1）——编译器
   对点号限定类型注解的行为表达式类型传播缺口，需独立窗口修复（与 KNOWN_LIMITS
   §10.2 边界区分：这不是 graceful 退化，是运行时崩溃）。
4. **环境事实**：本机真实 LLM 响应 <1-2s、reasoning_tokens=0（思考已禁用），与
   LLM_SERVICE §二.1 记录的"强制思考 + 10-30s"不符——环境已变化（用户应用了禁用
   思考预设），LLM_SERVICE 文档需在 Task3 文档治理时更新。

## 五、后续

- KERNEL_ISSUE-CROSSMOD-LLM-1 登记 PENDING_TASKS（独立窗口）。
- KNOWN_LIMITS §10.2 更新（跨模块 LLM 输出目标 = 运行时崩溃而非 graceful 退化）。
- LLM_SERVICE 文档更新（思考已禁用环境事实）。
- 全部在 Task3 文档治理阶段处理。
