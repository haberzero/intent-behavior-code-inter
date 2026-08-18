# HANDOFF_SESSION — 会话交接文档（一次性，下一 session 核验后并入 HANDOFF.md）

> **性质**：本文件是一次**会话边界交接文档**（用户因上下文不足要求书写）。内容自包含，
> 下一 session 开工前读本文件 + `tasks_docs/NEXT_STEPS.md` + `tasks_docs/WORKLOG.md` +
> `tasks_docs/HANDOFF.md`。**核验并接手后**：把本文件要点收敛进 `HANDOFF.md` §二，然后删除
> 本文件（git 承载历史）。
>
> **本 session 主线**：五大地基改造（用户 2026-08-18 定方向 + 6 项决策）——承接原
> `exp/protocol-vtable` 未提交增量 → 低风险合并 → P2③/P5 → P3 → P4 自主推进 8 轮，按用户
> "本轮完成停下汇报 + 书写交接"指示暂停。

---

## 一、总览（一句话）

本 session 把 **P2/P6 地基**（protocol_vtable 数据结构 + P2-② 覆层机制）低风险合并入
`unsafe-vibe-dev`，随后无人值守推进 **P2③/P5 D1+D2 → P3 D8/G5/G2 → P4a → P4b 设计 →
P4b-2a/2b/2c**（LLMCallable 协议 + 统一装配 + run_batch 统一消费），每步全量 pytest 零回归 +
本地 commit + 文档同步。当前 `unsafe-vibe-dev` HEAD=`bf7df634`，基线 **3030 passed / 1 skipped**
（以实跑为准），worktree 干净，**未 push、未触碰 main**。Goal `goal-60b14b27...`（max 10 轮）已
pause（roundsStarted 7），可 resume 续接。

---

## 二、仓库状态（权威）

| 项 | 值 |
|----|----|
| 当前分支 | `unsafe-vibe-dev`（HEAD=`bf7df634`，领先 origin **212** 提交，未 push） |
| 其它分支 | `main`（未触碰，`eb4a7d10`）；`exp/protocol-vtable` 已合并即删（仅剩 main + unsafe-vibe-dev） |
| 测试基线 | `~/miniconda3/envs/ibci/bin/python -m pytest tests/` → **3030 passed / 1 skipped**（以实跑为准，不冻结；docs 中历史基线数字均已过期勿引用） |
| 工作树 | 干净 |
| push | **一律禁止**（除非用户显式授权硬原则） |
| Goal | `goal-60b14b27-92fe-4cfc-81cf-bf4369dfda32` revision 2 paused（resume 可续） |

## 三、本 session 提交序列（unsafe-vibe-dev，旧→新）

| 提交 | 内容 | 基线 |
|------|------|------|
| `1d3fc74a` | P2-② 临时覆层机制（`overlay`/`with` 新关键字 + `impl overlay` + `with overlay(...)` 作用域块全链路）；复核补充端到端判别测试 + `_OverlayRegistry.declared_items()` | 2997 |
| `b7479497` | 删除临时文档 `_code_overlay.md`/`_code_protocol_vtable.md`（git 承载）+ WORKLOG 指针清理 | — |
| `978f0409` | P2/P6 地基**低风险 fast-forward 合并** unsafe-vibe-dev（用户授权）；post-merge 文档同步 | 2997 |
| `e7e92d2a` | **P2③/P5 D1+D2**（见 §六·契约1） | 3003 |
| `be138ca3` | **P3 D8** snapshot 意图冻结（见 §六·契约2） | 3011 |
| `aa078cfb` | **P3 G5/G2** 可调用值有意义契约嵌入（见 §六·契约3） | 3019 |
| `ee6ad807` | **P4a** LLMCallable 协议地基（见 §六·契约4） | 3020 |
| `eda28937` | **P4b 设计定稿**（`_code_p4b_assembly.md` 临时设计文档） | — |
| `f2db9aa6` | **P4b-2a** 统一装配路径（见 §六·契约5） | 3028 |
| `354738af` | **P4b-2b** run_batch 统一消费 LLMCallable 实例（见 §六·契约5） | 3029 |
| `bf7df634` | **P4b-2c** llm 类 run_batch 逐项参数化（`__llm_call__(self, any item)` 可选 item 参 + 批量） | 3030 |

> 另有 `exp/protocol-vtable` 上既有提交（`6d933080` receive 骨架收敛 / `6c3f6c94` impl 内置目标 /
> `eb8ecd30` D4 str output_hint / `6fd2cefc` D9 死字段清理 / `cd60ea6d` protocol_vtable 数据结构）
> 随合并一并进入 unsafe-vibe-dev 历史。

## 四、待验证清单（下一 session 首步，按序）

- [ ] `git status` → 干净；`git branch -vv` → 当前 = unsafe-vibe-dev、main 未动、未 push。
- [ ] `git log --oneline e8c7944b..HEAD` 对齐 §三 提交序列。
- [ ] 全量 pytest 实跑 → 记录实跑 passed/skipped（预期 3030 量级，**以实跑为准**）。
- [ ] 读 `tasks_docs/NEXT_STEPS.md`（当前状态 ✅ 条目 + 候选 #1 = P4b-3）与 `tasks_docs/HANDOFF.md` §2.2 检查单。
- [ ] 核验 §六 各契约落地文件存在 + 判别测试绿（`tests/e2e/test_overlay_mechanism.py` /
  `test_snapshot_intent_freeze.py` / `test_intent_callable_embedding.py` /
  `test_llm_callable_unified.py` / `tests/kernel/test_protocol_registry.py`）。
- [ ] 确认 goal 状态（`get_goal`）；如需续接 → `update_goal resume`。

## 五、继续工作路线（NEXT_STEPS 候选 #1 已前移）

**P4b-3（下一主线）**：LLMCallable **可选协议方法运行时发现**（P1 §2.2）——
`__intent__`（装配时改写本次调用意图）/ `__retry__`（重试策略声明，决策 5 输入）经 `receive`
发现；装配上下文 `IbLLMCallAssemblyCtx`（只读意图入参）按需引入；剩余消费面（`stream_call`/
`stream_channel` 统一消费 LLMCallable——当前仍吃字符串，需设计 llm 类流式装配语义；
行为值经统一装配入口路由——sync/CPS 张力见 `_code_p4b_assembly.md` §2.3 已定 CPS 装配入口承载）。

**P4c（最大破坏性阶段，用户定裁）**：`llm ... llmend` 语法及旧机制**彻底删除** + 全量迁移。
删除面与语义迁移映射见 `tasks_docs/_five_foundation_P1_design.md` §三；迁移面摸底：
**36 个测试文件 + 66 个示例/试用文件** 使用 llm 函数机制。载体清单：lexer token
（`LLM_DEF/LLM_END/LLM_SYS/LLM_USER/LLM_RETRY/LLM_RETRY_HINT`）、`core/compiler/lexer/llm_scanner.py`
整块、parser `llm_function_declaration` + 顶层 `llmretry` 语法糖、AST `IbLLMFunctionDef`、
semantic 各 pass `is_llm` 分支、`callable_kind="llm_function"`、`_LLMFunctionMixin`
（`llm_executor/_llm_function.py` 整文件）、provider `user_sys` 槽。测试迁移原则：语义随修复
演进重构为新语义（非规避缺陷，user-principles §三唯一底线保留缺陷复现用例）。

**P4d**：retry 高阶化（决策 5：帧机制保留 + 语法/策略高阶化，`__retry__` 协议装配）。

**P5**：validate_prompt 死条目激活（G7 能力公理收尾）+ prompt 类型类化剩余。
**P6**：per-IbClass 协议方法表最终落地收尾。

**待 P4 对齐项**：G5 意图值栈全量重构（栈存原始值/按值匹配）；`has_llm_call_cap` → LLMCallable
协议。

## 六、关键设计与契约（下一 session 必须知道）

1. **P2③/P5 D1+D2**（`e7e92d2a`）：`PROMPT_PROTOCOL_SPECS` 补第 5 成员 `__payload_prompt__`
   （用户契约 = `(self) -> dict|list|str`，runtime 零参数分派；公理层 `(self,value,spec=None)`
   是内置委托内部签名不经校验）；`BaseAxiom.has_to_prompt_cap` 默认 **True**（to_prompt 是通用
   渲染路径）+ `BUILTIN_PROTOCOLS.to_prompt` 接 `axiom_cap` + `PromptRenderer.to_prompt_str`
   增 `satisfies_protocol` 前置门（镜像 to_payload）。P1 §五 protocol_vtable 形状已订正为
   **消息名 → ProtocolSlot**（native 按值类惰性解析 + overlay + overlay_enabled，非协议名键）。
2. **P3 D8**（`be138ca3`）：意图 fork 移出 `body_is_behavior` 特判 → 按 `capture_mode` 统一
   （snapshot 恒 fork / lambda 恒 None）；`IbFnCallable.captured_intents` + 工厂/序列化；
   `_vm_call_fn_callable` 意图生命周期（`enter_intent_scope` 给 lambda IT-3 fork +
   `replace_intent_context(captured_intents.fork())` 给 snapshot IT-2/IT-4）。
3. **P3 G5/G2**（`aa078cfb`）：`IbUserFunction.__to_prompt__` → `func <name>(<参数类型>) -> <ret>`
   （取 spec 值层自持签名）；`IbFnCallable`/`IbBehavior` 的 `__to_prompt__`/`_dispatch_to_prompt`
   统一 `signature_name()`（去 Python repr）。`test_callable_unification` 2 断言已按新契约更新。
4. **P4a**（`ee6ad807`）：`BUILTIN_PROTOCOLS.llm_callable` 注册，`__llm_call__` 为**必需方法**
   = "能否被 LLM 消费"唯一判定（`satisfies_protocol(..., 'llm_callable')`）；required/optional
   形式化归 P5/P6。
5. **P4b**（`eda28937`+`f2db9aa6`+`354738af`+`bf7df634`）：装配契约定为 **用户
   `__llm_call__(self[, any item]) -> dict` 返回装配配置 dict**（`user_prompt`/`output_hint`/
   `expected_type`/`model` 键）；统一装配入口 `assemble_llm_callable_request_cps`（协议门 →
   `UserFunctionCall` → dict→`LLMCallRequest`）+ 执行入口 `invoke_llm_callable_cps`（→ 统一
   worker `_call_and_parse`）；`run_batch` 已统一消费（行为 items 逐项绑参保留；llm 类 per-item
   参数化）。实现文件 `core/runtime/interpreter/llm_executor/_llm_callable.py`（`_LLMCallableMixin`
   组合进 `LLMExecutorImpl`）+ `_behavior.py` 的 `_RunLLMCallableDrive`。
   **重要**：`tasks_docs/_code_p4b_assembly.md` 是临时设计文档，**P4b 全部完成后删除**。

## 七、遗留项 / 技术债（不阻塞主线）

- **已知设计开放点**：`stream_call`/`stream_channel` llm 类流式语义、装配上下文 `IbLLMCallAssemblyCtx`
  （用户 `__llm_call__` 需读意图输入时引入）、行为经统一装配入口路由（sync/CPS 张力）。
- 历史遗留（此前登记）：`IbBehaviorInstance` 死类候选 + `binding_analysis_pass` getattr 探测
  （WORKLOG）；PT-DEBT-29/30/31、PT-DECIDE-2/3/4、PT-DEBT-4/5（PENDING_TASKS 支线）。
- 数字纪律：docs 中多处历史基线数字（2985/2997/3003...）已过期，**一律以实跑为准**。

## 八、环境与纪律（勿忘）

- 测试唯一命令：`~/miniconda3/envs/ibci/bin/python -m pytest tests/`（conda env `ibci`）。
- 全程本地 `git commit`，**禁止 `git push`**（除非用户显式授权）；**永不触碰 `main`**。
- 每步：全量 pytest 零回归 + 描述性 commit + 同步 WORKLOG/NEXT_STEPS/HANDOFF；低风险增量
  按已授权模式可直接 merge `unsafe-vibe-dev`（合并即删短期分支），判定以"确认零风险"为准。
- 工作模式定论（NEXT_STEPS ⛔）：禁 compat shim / 胶水 / tricky / 过程式硬编码；质量优先；
  原则优先于行为维持；可推翻 IBCI 自身设计缺陷；"只记录，不断决"。
- 文档纪律：`docs/` 面向人类（无 agent 元信息）；任务控制文档单向真理、不冻结数字、
  不保留已完成历史（git 承载）。
