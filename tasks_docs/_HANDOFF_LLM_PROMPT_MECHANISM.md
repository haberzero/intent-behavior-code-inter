# 交接：IBCI LLM 调用机制改进（T5 枚举解析失败暴露的机制弱点）

> 2026-08-14 编制。触发：完整试用核查中 T02 T5-enum-value-ne-name 真实 LLM 间歇失败
> （枚举成员名→值映射，LLMParseError），用户要求严肃评估 IBCI LLM 调用机制（prompt
> 协议 / 提示词设计 / llmretry 反馈 / vs OpenAI 标准对话机制），并交接下一 session 改进。

## 〇、交接结论（先行）

**T5 间歇失败不是单纯模型非确定性——实证为 IBCI 机制设计弱点**，其中**一个可直接
复现的机制 bug**（枚举输出格式约束未注入提示词）+ **三个结构性弱点**（程序化调用
纪律缺失 / 期望类型不注入 prompt / retry 无自动错误回喂）。

---

## 一、实证：失败时的真实 LLM 响应（已捕获）

失败响应（模型完全滑入"对话助手"模式，反问/拒绝/安全幻觉）：
```
"请提供需要解析的状态值。"
"无法提供不存在的系统内部状态信息。作为人工智能助手，我遵循安全、合规的原则运行..."
"请提供需要解析的状态字符串。"
```
成功响应：`"ACTIVE"`（成员名）。成功率高度随机（前期 2/3 败，后 12/12 过）——模型
服从性不稳定，且**提示词框架给了它"滑回对话"的空间**。

## 二、可直接复现的机制 bug：枚举输出格式约束未注入提示词

### 实际发送的 prompt（插桩实证）
```
[SYS_PROMPT]  '你是一个意图行为代码执行器。'        ← 无 [输出格式要求] 段！
[USER_PROMPT] '你是状态枚举解析器。只输出一个成员名：ACTIVE 或 INACTIVE...'
[TYPE_HINT]   '__string_exec__.Status'              ← 仅用于解析，不注入
```

### 根因链（逐环实证）
1. 枚举 `Status` 按 module 限定名注册（S2/S5 类身份 module 化后）：
   `resolve("Status")` = **None**，`resolve("Status", module="__string_exec__")` = **found**
   （kind=class，axiom=enum，`__outputhint_prompt__` = "Reply with exactly one of: ACTIVE, INACTIVE."）。
2. `_get_llmoutput_hint`（`llm_executor/_prompt.py:259`）node_to_type 分支：
   `type_name = node_to_type.name`（裸名 `"Status"`）→ `_try_axiom_output_hint("Status")`
   → `meta_reg.resolve("Status")` = **None** → hint = None。
3. `_try_vtable_hint("Status", module)` 也失败：枚举 `__outputhint_prompt__` 在 **EnumAxiom**
   上（axiom 级），不在用户类 vtable 上 → `lookup_method('__outputhint_prompt__')` = None。
4. 结果：sys_prompt 无 `[输出格式要求]`，模型只收到通用系统提示 + 用户中文 prompt →
   服从性脆弱 → 失败。

### 不对称
- **解析端 module 感知**：`_get_expected_type_hint` 返回 qualified 名（`__string_exec__.Status`），
  `from_prompt` 解析正常（成员名大小写不敏感映射）。
- **注入端非 module 感知**：`_try_axiom_output_hint` 用裸名 resolve，找不到枚举 →
  hint 不注入。**S2/S5 module 化后注入端未同步升级**（与 create_func/resolve_member
  断层同族：早期按裸名设计，module 化后未跟随）。

## 三、三个结构性机制弱点（严肃评估）

1. **系统提示词过弱、过于通用**：`_prepare_behavior_call`（`_behavior.py:163`）
   `sys_prompt = "你是一个意图行为代码执行器。"`——未建立"程序化调用、只输出原始数据、
   禁止问候/提问/解释/拒绝"的输出纪律。模型易滑回对话助手模式（正是失败形态）。
2. **期望输出类型不注入 prompt**：`type_hint` 只传 `BehaviorCallSpec` 供解析（`_behavior.py:178`），
   不注入 sys_prompt。模型从未被告知"必须返回一个 {type}"。`__outputhint_prompt__` 协议是
   补偿机制，但依赖类型实现者（enum 有但注入断链；普通用户类需自定义）。
3. **retry 反馈是人工手动的**：llmexcept/retry 只把 `ai.set_retry_hint()` 的用户文案追加到
   sys_prompt（`_behavior.py:171-172`，`_retry_llm_uncertain` 重求值）。**不自动回喂**
   ① 解析错误信息（`from_prompt` 已生成 "无法解析 'X'，请回复有效枚举值如: ..."）；
   ② 上一次的错误响应。标准做法是"把错误回喂模型再请求"。

## 四、vs OpenAI 标准对话机制（严肃评估）

| 维度 | OpenAI 标准（工具调用/结构化输出） | IBCI `@~...~` |
|---|---|---|
| 角色框架 | function/tool：模型知自己是"被调用函数" | 通用"意图行为代码执行器"，模型易滑回对话助手 |
| 输出约束 | 显式 schema/格式注入 system | `__outputhint_prompt__`（可选 + 本 bug 注入断链） |
| 期望类型 | prompt 中显式声明 | 仅用于解析，不注入 |
| 失败重试 | 把解析错误/前次输出回喂模型 | retry_hint 仅用户手写 |
| 调用方控制 | 调用方完全控制循环 | VM 控制，llmexcept 用户写 |

**协议方向正确（`__to_prompt__`/`__from_prompt__`/`__outputhint_prompt__` = 结构化输入输出），
但 prompt 组装层是最弱框架**——程序化调用纪律缺失、期望类型不注入、重试不回喂错误。

## 五、改进方向（下一 session，独立设计窗口）

### A. 修复机制 bug（明确，低风险）
- `_get_llmoutput_hint` 的 axiom 查找传入 module：`_try_axiom_output_hint(type_name, module)`
  → `meta_reg.resolve(type_name, module=module)`。node_to_type 分支已有 module_path。
- 或统一 `_get_llmoutput_hint` 与 `_get_expected_type_hint` 的 module 感知（单一权威）。
- 判别性回归：`Status c = @~...~` 实际 sys_prompt 含 `[输出格式要求] Reply with exactly
  one of: ACTIVE, INACTIVE.`；真实 LLM 多次运行成功率显著提升。

### B. 强化程序化调用纪律（中风险，机制改进）
- `@~...~` 用更强的系统提示框架（如"你是一个被 IBCI 程序调用的函数，只返回原始数据，
  禁止问候/提问/解释/拒绝/安全拒绝"）。
- 判别性回归：mock 断言系统提示包含输出纪律；真实 LLM 对"易滑回对话"的 prompt 稳定性。

### C. 期望类型注入 prompt（中风险）
- 把 `type_hint` 注入 sys_prompt（"必须返回一个 {type} 值"）。
- 与 `__outputhint_prompt__` 协同（类型级 hint 优先，通用 type 声明兜底）。

### D. retry 自动错误回喂（中风险，机制改进）
- llmexcept/retry 自动把"上次解析错误 + 上次响应"追加到重试提示（而非仅用户 retry_hint）。
- 判别性回归：构造 llmexcept + retry 用例，验证错误回喂后第二次调用收敛。

### E. 长期：对齐结构化输出
- 评估 OpenAI tool-call / structured-output 形态对 IBCI 的适配（封闭类型枚举/布尔等）。

## 六、验证基线

- 全量 pytest `~/miniconda3/envs/ibci/bin/python -m pytest tests/`（当前 2775 passed / 1 skipped）。
- 试用：T02 T5 真实 LLM 多次运行（目标：成功率显著提升或错误信息可回喂）。
- 判别性回归见各改进项。

## 七、交接纪律

- 全程本地 commit、禁 push、不触碰 main。
- 属语言级机制改进（LLM 调用面），建议独立分支实验 + 全量 pytest + 独立复核。
- 涉及对外行为（prompt 变化影响真实 LLM 输出），确认零风险后合并 unsafe-vibe-dev。
- 记录于 WORKLOG；本次仅记录+交接，未改内核（用户试用核查纪律）。

## 八、相关既有项（勿重复）

- `PENDING_TASKS §〇`：供应商感知模型思考禁用机制（LLM_SERVICE.md，P2 待设计）——与
  本交接正交（前者是模型后端参数形态，后者是 prompt 组装机制）。
- `KNOWN_LIMITS` / 协议文档：`__outputhint_prompt__` 触发条件待本交接落地后同步。
