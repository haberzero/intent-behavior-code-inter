# HANDOFF_SESSION — 会话交接文档（一次性，下一 session 核验后并入 HANDOFF.md）

> **性质**：本文件是一次**会话边界交接文档**。内容自包含，下一 session 开工前读本文件 +
> `tasks_docs/NEXT_STEPS.md` + `tasks_docs/WORKLOG.md` + `tasks_docs/HANDOFF.md`。
> **核验并接手后**：把本文件要点收敛进 `HANDOFF.md` §二，然后删除本文件（git 承载历史）。

> **本 session 主线**：五大地基改造 P4d/P5/P6 无人值守推进（P1-P6 全链路收官）+ 超大型
> 重构专项审计（只检测不修改，用户 2026-08-19 指示）。P4d/P5/P6 每步全量 pytest 零回归 +
> 本地 commit + 文档同步。

---

## 一、总览（一句话）

本 session 完成 **P4d retry 高阶化 + P5 prompt 类型类化收尾 + P6 per-IbClass 协议方法表
最终收尾**（五大地基改造 P1-P6 **全链路完成**，每步零回归 + commit + 文档同步），并以
**专项审计**（基线 `e8c7944b`..HEAD，130 文件 +4592/-1627）产出本次超大型重构的技术债
清单（A-G，**均未修**，见 §七/§八）。当前 `unsafe-vibe-dev` HEAD=`764d7ca6`，基线
**3059 passed / 1 skipped**（以实跑为准），worktree 仅剩未跟踪临时文档
`tasks_docs/_code_p4d_retry.md`，**未 push、未触碰 main**。

## 二、仓库状态（权威）

| 项 | 值 |
|----|----|
| 当前分支 | `unsafe-vibe-dev`（HEAD=`764d7ca6`，领先 origin **228** 提交，未 push） |
| 其它分支 | `main`（未触碰，`eb4a7d10`）；无其它本地分支（短期分支合并即删） |
| 测试基线 | `~/miniconda3/envs/ibci/bin/python -m pytest tests/` → **3059 passed / 1 skipped**（以实跑为准，不冻结） |
| 工作树 | 仅未跟踪 `tasks_docs/_code_p4d_retry.md`（P4d 临时设计文档，汇报经用户确认后删除） |
| push | **一律禁止**（除非用户显式授权硬原则） |
| Goal | `goal-2dcb9124`（P4d: complete）、`goal-239eb807`（P6: complete）；跨会话不可 resume，下 session 新建 |
| 主线状态 | **五大地基 P1-P6 全链路完成**（NEXT_STEPS 当前状态段 + 候选 #1） |

## 三、本 session 提交序列（unsafe-vibe-dev，旧→新）

| 提交 | 内容 | 基线 |
|------|------|------|
| `0febf487` | **P4d retry 高阶化**：`__retry__` 可选协议方法 + 装配三元组 + 调用级策略重试循环（决策 5；契约见 §五.1） | 3047 |
| `bafa62c6` | **P5 prompt 类型类化收尾**：validate_prompt 死条目激活（axiom_cap + 消费前置门）+ required/optional 形式化（optional_methods + all_methods + llm_callable 登记）（契约见 §五.2） | 3055 |
| `71ac4ba8` | 任务文档：P5 完成条目 + P6 候选前移 + **output_hint 自动推导评估定论 = 保持显式不落地** | — |
| `5ccd4eb0` | **P6 最终收尾**：双表收敛实证锁定（判别测试 +4）+ `TypeAxiom` 接口补 has_validate_prompt_cap + docs 漂移修正（03 §4.0/§4.1、04 §2）（契约见 §五.3） | 3059 |
| `764d7ca6` | 剩余对齐债务评估记录（has_llm_call_cap 编译期 DDG 层实证） | — |

**专项审计**（本 session 末，只检测不修改）：无提交，产出技术债清单 §七/§八。

## 四、待验证清单（下一 session 首步，按序）

- [ ] `git status` → 仅 `_code_p4d_retry.md` 未跟踪；`git branch -vv` → unsafe-vibe-dev、main 未动、未 push。
- [ ] `git log --oneline 25846bd5..HEAD` 对齐 §三 提交序列（5 笔）。
- [ ] 全量 pytest 实跑 → 记录 passed/skipped（预期 3059 量级，**以实跑为准**）。
- [ ] 读 `tasks_docs/NEXT_STEPS.md`（当前状态 ✅ 条目 + 候选 #1）与 `tasks_docs/HANDOFF.md` §2.2 检查单。
- [ ] **读本文件 §五-§八**（P4d/P5/P6 契约 + 审计技术债清单——下 session 处置候选）。
- [ ] 确认 goal：跨会话不可 resume → 按 HANDOFF §1.2.1 新建 goal（max_auto_turns=7）。

## 五、关键设计与契约（下一 session 必须知道）

1. **P4d `__retry__` 协议**（`0febf487`，`_llm_callable.py`）：`func __retry__(self) -> dict`
   （无参）返回 `{"max_retry": int>=1(缺省 3), "hint": str}`；发现走
   `_discover_optional_protocol_method`（与 `__intent__` P4b-3a 同一虚表通道）；违约
   fail-fast（带参/非 dict/max_retry 非法/hint 非 str）。装配入口返回三元组
   `(request, type_hint, retry_policy)`；`invoke_llm_callable_cps` 有策略时走
   `_invoke_llm_callable_retry_cps` 调用级重试循环（失败轮经 `_prompt_assembly` 单一消息
   构造累积 `message_history` 回喂，max_retry 耗尽返回最后不确定结果交语句层
   llmexcept/LLMParseError）；直接调用 `f(args)` 与 run_batch 逐项自动继承。
   **设计边界裁定**（用户质询的答复）：帧机制 = 执行窗口重求值 ⊕ LLM 重试信息装配两正交
   职责，高阶化只作用于后者（CPS 状态机不进协议）；`__llmretry__` 旧语义由 `hint` 承接；
   行为语句默认 retry 帧机制零改动。`stream` 路径不消费重试循环（与行为值流式一致）。
2. **P5 prompt 类型类化收尾**（`bafa62c6`）：validate_prompt 激活（`BaseAxiom.has_validate_prompt_cap`
   默认 False + 协议条目 axiom_cap/structural_methods + `llm_parsing_strategy` 消费前置门，
   advisory：实际分派仍走虚表）；`ProtocolDef.optional_methods` + `all_methods()`；
   `llm_callable` 登记 `optional_methods=("__intent__","__retry__")`（methods 保持必需权威，
   satisfies 判定不变）。
3. **P6 协议方法表收尾**（`5ccd4eb0`）：P6 主体 P2-② 已落地（protocol_vtable/ProtocolSlot/
   `_dispatch_protocol_message`），本步 = 判别测试 +4（`TestSatisfactionDispatchConvergence`：
   satisfies↔receive 一致 / 未声明不误分派（消费前置门以 satisfies 为准）/ 惰性建槽 /
   optional 不建协议槽）+ `TypeAxiom` 接口补 has_validate_prompt_cap + docs 三处修正。
   **据实评估**：剩余面边界清晰、非架构级，**未独立分支**（P1 §8.3 分支政策前提已不成立）。
4. **output_hint 自动推导 = 不落地**（显式优于隐式裁定，WORKLOG 记录）：llm 类装配 dict
   显式声明；行为路径自动取 hint 是行为值节点语义，不扩及 llm 类。
5. **语义演进（防误解）**：llm 类实例渲染 `<Instance of T>`；`fn` 只收 lambda；llm 类
   run_batch 每 item 一次调用；行为 run_batch 语义保留。

## 六、语义演进验证要点（本 session 判别测试成果）

- `tests/e2e/test_llm_retry_callable.py`（6 项）：`__retry__` hint 注入 message_history /
  耗尽交语句层 / 未声明单次 / 空 dict 默认 3 / run_batch 继承 / 契约 fail-fast。
- `tests/runtime/test_protocol_dispatch_contract.py::TestSatisfactionDispatchConvergence`（4 项）。
- `tests/kernel/test_prompt_protocol.py`（P5 +8 项）。

## 七、专项审计发现：技术债/遗留问题清单（均未修，处置候选）⚠️

> 审计基线 `e8c7944b`..HEAD（130 文件 +4592/-1627），只检测未修改。详细结论见上次
> 审计汇报；下 session 处置建议顺序 **A+B 机械批 → C 债务评估 → D 独立窗口设计**。

**A. 注释/文档任务代号污染（合规违规，工作量最大）**：AGENTS.md 硬规则禁代码注释任务
代号/章节指针、docs/ 面向人类禁任务代号（docs/README.md §三"删代号标签，留功能说明"）。
- core/ 12 文件：`_llm_callable.py`（新建 570 行注释遍布 P4b/P4c/P4d）、`_behavior.py`、
  `_expression_visitors.py`（P4c L540）、`tokens.py`（P2-② L63）、`ib_class.py`/`base.py`
  （"决策 1 B"）、`kernel/protocol.py`（P5）、`_shared.py`/`llm_behavior.py`/
  `runtime_serializer.py`（D8）、`runtime_context.py`（P3）、`llm_executor/__init__.py`；
  基线仅 `vm_executor.py` R2-D5 一处历史遗留。
- tests/ 19 文件（test_llm_callable_unified / test_llm_retry_callable /
  test_retroactive_impl_builtin / test_streaming 等的 docstring "P4b/P4c 迁移"）。
- docs/ 6 文件：08/10/guide-03/guide-05/KNOWN_LIMITS 的 "（P4c）" 字样 +
  **04_vm_interpreter §2 "（决策 1 B，P2-②/P6 落地）"（本 session P6 新引入）**。
- 处置：纯机械改写（注释/文档留功能说明去代号），零风险零回归。

**B. 死代码（零消费者）**：`_LLMCallableMixin._invoke_llm_callable_cps_boxed`（P4b-2b 早期
单元素版）+ `_invoke_llm_callable_sync`（P4b-2a 早期同步版），grep 全仓零引用 → 删除。

**C. 双实现/双通道（design-philosophy 单一权威）**：
- 意图三层解析**双写真相**：`_llm_callable.py::_resolve_llm_callable_intents_cps`（L93-112）
  与 `_behavior.py::_prepare_behavior_call_cps` 内联块（L288-306）近乎逐行相同；
- 行为/llm 类双装配入口（D11 残余，登记债务）：run_batch/invoke 行为走
  `_prepare_behavior_call_cps`、llm 类走 `assemble_llm_callable_request_cps`
  （`assemble_stream_request_cps` 已有桥接先例）。
- **与 NEXT_STEPS 候选 #1 "行为值深程统一装配入口收敛"同源，本次审计为其补精确代码定位。**

**D. 并发正确性风险**：`ProtocolSlot.overlay_enabled` 为 IbClass 级可变共享态
（`with overlay` save/restore 配对，`control_flow.py` L459-469）——`run_many` 多根并发
执行不同 `with overlay` 块时**跨根互相污染**，覆层"作用域化"设计（P1 §4.3）在多根下不成立，
无隔离/无同步。需设计（独立窗口），影响面待实测。

**E. 半接通边界（维持登记）**：stream 路径不消费 `__retry__` 循环（设计边界，与行为值流式
一致）；`_invoke_llm_callable_batch_cps` "并发优化留待后续"（llm 类 run_batch 逐项串行）。

**F. 登记债务核对（无新增）**：G5 意图值栈全量重构 / `has_llm_call_cap`（编译期 DDG 层，
已实证不可简单迁移 llm_callable）/ output_hint 显式定论——与 NEXT_STEPS/WORKLOG 一致。

**G. 工作过程遗留**：临时文档 `tasks_docs/_code_p4d_retry.md` 未删（待用户确认）；
"同步兜底"措辞（`_LLMCallableCallDrive._drive`/`_UserCallDrive`/`_ClassInstantiateDrive`）
经审问判定为**合法显式双驱动路径**（CPS 主路径 + 宿主同步路径，与 `_SlotUpdateWaitable._drive`
同构；无上下文时 fail-fast）——**非掩盖型兜底，保留**。

## 八、继续工作路线（下 session 候选，按序）

1. **审计清单处置**（§七）：A 代号污染清理（core 12 + tests 19 + docs 6，机械改写）+ B
   死代码删除 → 一批（零风险）；C 双实现收敛评估（与 NEXT_STEPS 候选 #1 行为统一装配同源，
   合入主线债务评估）；D overlay 并发隔离设计（独立窗口/独立分支）。
2. **主线剩余对齐债务评估**（NEXT_STEPS 候选 #1）：G5 意图值栈全量重构 / has_llm_call_cap
   / 行为值深程统一装配入口收敛。
3. 支线：PT-DEBT-29/30/31、PT-DECIDE-2/3、PT-DEBT-4/5；VISION-3；文档 P9 收尾
   （docs 治理纪律：**催生自 §七.A**——docs 代号污染 6 文件须在 P9 或审计批内清）。

## 九、环境与纪律（勿忘）

- 测试唯一命令：`~/miniconda3/envs/ibci/bin/python -m pytest tests/`（conda env `ibci`）。
- 全程本地 `git commit`，**禁止 `git push`**（除非用户显式授权）；**永不触碰 `main`**。
- 每步：全量 pytest 零回归 + 描述性 commit + 同步 WORKLOG/NEXT_STEPS/HANDOFF；低风险增量
  可直接 unsafe-vibe-dev（合并即删短期分支），判定以"确认零风险"为准。
- 工作模式定论（NEXT_STEPS ⛔）：禁 compat shim / 胶水 / tricky / 过程式硬编码；质量优先；
  原则优先于行为维持；可推翻 IBCI 自身设计缺陷；"只记录，不断决"。
- **注释纪律（本次审计血泪）**：代码注释禁任务代号（P4x/D#/G#/章节指针/历史叙述），只写
  功能设计与已知问题；docs/ 面向人类禁一切代号标签。新增注释即守此规；存量污染见 §七.A。
- **goal 配置习惯（HANDOFF §1.2.1）**：`max_auto_turns` = **7**；objective 按 §1.3 模板。