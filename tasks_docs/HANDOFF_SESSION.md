# HANDOFF_SESSION — 会话交接文档（一次性，下一 session 核验后并入 HANDOFF.md）

> **性质**：本文件是一次**会话边界交接文档**。内容自包含，下一 session 开工前读本文件 +
> `tasks_docs/NEXT_STEPS.md` + `tasks_docs/WORKLOG.md` + `tasks_docs/HANDOFF.md`。
> **核验并接手后**：把本文件要点收敛进 `HANDOFF.md` §二，然后删除本文件（git 承载历史）。
>
> **本 session 主线**：五大地基改造（用户 2026-08-18 定方向 + 6 项决策）的无人值守推进——
> 接手上 session 交接（HANDOFF_SESSION 收敛删除）→ P4b-3a/3b → **P4c 全链路完成**
> （llm 函数语法与旧机制彻底删除 + 全量迁移），按用户"推进到 P4c 结束 + 书写交接"指示暂停。

---

## 一、总览（一句话）

本 session 完成 **P4b-3（`__intent__` 可选协议方法 + 流式消费面统一）+ P4c（`llm ... llmend`
语法与旧机制全链路删除 + 测试/示例/试用/文档全量迁移）**，每步全量 pytest 零回归 + 本地
commit + 文档同步。当前 `unsafe-vibe-dev` HEAD=`9a3ab867`，基线 **3035 passed / 1 skipped**
（以实跑为准），worktree 干净，**未 push、未触碰 main**。Goal `goal-a7656866-...`（max 7 轮，
roundsStarted 1）已由用户接管 disarmed；**goal 不跨会话**——下 session 按 HANDOFF §1.2.1
习惯新建 goal（max_auto_turns=7，用户 2026-08-19 将模板从 10 改为 7）。

---

## 二、仓库状态（权威）

| 项 | 值 |
|----|----|
| 当前分支 | `unsafe-vibe-dev`（HEAD=`9a3ab867`，领先 origin **222** 提交，未 push） |
| 其它分支 | `main`（未触碰，`eb4a7d10`）；无其它本地分支（短期分支合并即删） |
| 测试基线 | `~/miniconda3/envs/ibci/bin/python -m pytest tests/` → **3035 passed / 1 skipped**（以实跑为准，不冻结） |
| 工作树 | 干净 |
| push | **一律禁止**（除非用户显式授权硬原则） |
| Goal | `goal-a7656866-af24-4939-8412-84aeb7b8374c` revision 2 disarmed（max 7 轮，roundsStarted 1）；跨会话不可 resume，下 session 新建 |

---

## 三、本 session 提交序列（unsafe-vibe-dev，旧→新）

| 提交 | 内容 | 基线 |
|------|------|------|
| `89f7ee36` | 交接收尾：上 session HANDOFF_SESSION 要点收敛入 HANDOFF §二 + 删除临时交接文件；**goal 配置习惯 max_auto_turns 10→7**（用户指示） | 3030 |
| `37801407` | **P4b-3a `__intent__` 可选协议方法运行时发现**（契约见 §六·1） | 3035 |
| `41fd710a` | **P4b-3b 流式消费面统一**（契约见 §六·2） | 3036 |
| `f5527e88` | **P4c-1 特性地基**：llm 可调用类实例直接调用 + 动态 any + prompt_slots 键 + call_args（契约见 §六·3） | 3035 |
| `61486deb` | **P4c-2a 测试迁移**：10 个 e2e/contracts/runtime 测试文件 → llm 可调用类 | 3035 |
| `5657dcee` | **P4c-2b 内核删除**（净删 656 行）：llm 函数机制全链路删除（§六·4） | 3035 |
| `9cf15e9f` | **P4c-2c 迁移收尾**：examples + trials 12 case + docs 全面同步（§六·5） | 3035 |
| `b12ef22c` | 任务文档收尾：NEXT_STEPS 候选 #1 前移 P4d + P4c 完成条目；HANDOFF 状态/检查单；WORKLOG 重大决策 | — |
| `9a3ab867` | 删除已完成 P4b 的临时设计文档 `_code_p4b_assembly.md`（git 承载）；NEXT_STEPS 备注同步 | — |

---

## 四、待验证清单（下一 session 首步，按序）

- [ ] `git status` → 干净；`git branch -vv` → 当前 = unsafe-vibe-dev、main 未动、未 push。
- [ ] `git log --oneline 9a3ab867~9..HEAD` 对齐 §三 提交序列（9 笔）。
- [ ] 全量 pytest 实跑 → 记录实跑 passed/skipped（预期 3035 量级，**以实跑为准**）。
- [ ] 读 `tasks_docs/NEXT_STEPS.md`（当前状态 ✅ 条目 + 候选 #1 = P4d retry 高阶化）与 `tasks_docs/HANDOFF.md` §2.2 检查单。
- [ ] 核验 §六 各契约落地文件存在（`core/runtime/interpreter/llm_executor/_llm_callable.py`
  / `core/runtime/objects/kernel/ib_class.py` `_LLMCallableCallDrive` / `core/runtime/objects/
  kernel/base.py` `_dispatch_call` / `core/compiler/semantic/passes/_expression_visitors.py`
  llm_callable 静态 any / `docs/syntax/08_llm_callable.md`、`docs/guide/05_llm_callable.md`）。
- [ ] 确认 goal 状态：跨会话不可 resume → 按 HANDOFF §1.2.1 新建 goal（max_auto_turns=7）。

---

## 五、继续工作路线（NEXT_STEPS 候选 #1 已前移）

**P4d（下一主线）：retry 高阶化（决策 5：帧机制保留 + 语法/策略高阶化）**：
- `__retry__` 可选协议方法落地（P1 §2.2 契约 `(retry 策略参数) -> 策略声明`：声明快照策略 +
  重试策略 + hint；**satisfies 非强制**，存在则经 `lookup_method` 发现——与 `__intent__`
  P4b-3a 同一通道 `_discover_optional_protocol_method`）+ 装配消费；
- llm 可调用类自定 retry（实现 `__retry__` 覆盖默认帧策略）；行为语句默认 retry 由帧机制
  提供（用户不写时走默认）；
- **承接 P4c 记录项**：`__llmretry__` 旧段语义（重试 hint 注入）在此落地装配；
  **output_hint 自动推导评估**（P4b-2a 记录：现为显式声明，自动推导归 P4d/P5 评估）。

**P5**：validate_prompt 死条目激活（G7 能力公理收尾）+ prompt 类型类化剩余 +
**required/optional 协议条目形式化**（`ProtocolDef` methods 分两组，`__intent__`/`__retry__`
正式入 llm_callable 协议条目）。
**P6**：per-IbClass 协议方法表最终收尾。

**待 P4 对齐项（债务）**：G5 意图值栈全量重构（栈存原始值/按值匹配）；
`has_llm_call_cap` → LLMCallable 协议；行为值深程统一装配入口收敛（run_batch/invoke 行为
路径当前经各自入口，`assemble_stream_request_cps` 已有桥接先例）。

---

## 六、关键设计与契约（下一 session 必须知道）

1. **P4b-3a `__intent__` 可选协议方法**（`37801407`，`_llm_callable.py`）：契约
   `func __intent__(self, dict intents) -> dict`——入参三层 `active`/`global`/`merged`
   （与 `LLMCallRequest.intents` 对齐）；返回 dict 键为三层任意子集：**存在键替换对应层
   （消解/增删/重排）、缺失键保持原层、显式空列表清空该层**。发现 = `ib_class.lookup_method`
   （receive 同源虚表，非 getattr 探测）经 `_discover_optional_protocol_method`；调用 =
   `UserFunctionCall` CPS（`_apply_intent_rewrite_cps`）。契约违约（参数数≠1/返回非 dict/
   层值非 str 列表）fail-fast。run_batch 共用装配入口自动继承；行为值路径零变化。
2. **P4b-3b 流式统一**（`41fd710a`）：`assemble_stream_request_cps`（行为值 → 语义槽装配/
   用户 llm 类 → 统一装配入口含 `__intent__`）+ `_StreamCallableDrive`（帧内 CPS → 
   IbStreamHandle；**stream_call yield 句柄取完整文本**（与旧调用点 auto-yield 语义一致，
   `await`/赋值得全文）、**stream_channel 返回 IbChannel** 逐块 recv）。`ai` 模块
   `_require_llm_executor` 收敛 run_batch/stream。字符串形态（sys_prompt, user_prompt）
   已真删除。
3. **P4c-1 llm 类直接调用**（`f5527e88`）：`IbObject._dispatch_call` 增路由——类无确定性
   `__call__` 且 `satisfies_protocol('llm_callable')` → `_LLMCallableCallDrive`（
   `ib_class.py`）：`f(args)` 按位绑定 `__llm_call__` 非 self 参数（默认值惰性填充经
   `_resolve_call_arguments_runtime`），结果经 `_finalize_invoke_result`（不确定 → 
   `IbLLMCallResult` 容器由语句层处理）。调用表达式静态类型 = **动态 any**（
   `_expression_visitors.py`，LLM 结果类型由运行时 `expected_type` 决定）。装配 dict 键：
   `user_prompt`（必需）/`prompt_slots`（可选 `[{kind,text}]`→PromptSlot，`__sys__` 迁移
   载体）/`expected_type`/`output_hint`/`model`；`call_args` 位置参数化（invoke/assemble
   透传）。
4. **P4c-2b 删除面（已完成）**：lexer token（`LLM_DEF/LLM_END/LLM_SYS/LLM_USER/
   LLM_RETRY_HINT/LLM_RETRY`）+ `lexer/llm_scanner.py` 整文件 + `LexerMode.LLM_BLOCK`/
   parser `llm_function_declaration`+`llm_body`+`parse_llm_section_content`+顶层 `llmretry`
   语法糖+impl 块 `llm func`/AST `IbLLMFunctionDef`/semantic 4 pass `is_llm` 分支+
   `SymbolKind.LLM_FUNCTION`+`llm_method` kind/运行时 `_vm_invoke_llm_function`+`callable_kind`
   字段+declarations+interpreter 水化分支/`_LLMFunctionMixin`（`_llm_function.py` 整文件）+
   `LLMFunctionCallSpec`+dispatch 分派/provider `user_sys` 槽特殊处理（自定义槽统一呈现）。
   **保留 `llmexcept`/`retry` 帧机制**（非 llm 函数语法，决策 5 载体）。`_vm_call_function`
   已简化为纯用户函数调用路径（`is_llm` 分支全删）。
5. **P4c-2c 文档/试用迁移**：`docs/syntax/08_llm_functions.md`→`08_llm_callable.md`（参考重写）、
   `docs/guide/05_llm_functions.md`→`05_llm_callable.md`（教程重写）；GETTING_STARTED/
   KNOWN_LIMITS/SYNTAX_REFERENCE/README/guide 01-07/howto 全部同步；examples 01/04 迁移；
   trials 12 case 迁移（T09 N1/N2 impl-llm-method→普通 func、N3/N7→类；T08 D4-01~05→类；
   T01 D1-08/D2-61/D3-C3e→类、D1-10 llmretry→llmexcept+retry）。
6. **语义演进记录（WORKLOG §二，防误解）**：llm 类实例渲染 `<Instance of T>`（非函数契约）；
   `fn` 变量只收 lambda/函数（类实例经 `ClassName inst = ClassName()` 类类型变量持有）；
   `__llmretry__` 段语义迁 `__retry__` 协议（P4d 落地）；output_hint 显式声明（自动推导
   评估归 P4d/P5）；Optional 返回由用户在装配 dict 表达 expected_type（剥离 Optional 前缀
   传内层类型）。
7. **迁移写法注意（P4c 实证）**：IBCI dict 字面量**不支持多行/尾逗号**——`return {...}`
   必须单行（parser 限制，`PAR_UNEXPECTED_TOKEN RBRACE`）；`fn x = ClassName()` 非法
   （`PAR_INVALID_SYNTAX`，fn 只收 lambda）；`@` 一次性意图必须紧跟 LLM 调用语句、`@+`
   持久意图可独立存在（stream/direct-call 判别测试曾用 `@+`）；JSON/MOCK 内容含 `"` 时
   IBCI 字符串用 `\\"` 转义（实测可用）。

---

## 七、遗留项 / 技术债（不阻塞主线）

- **P4b/P4c 记录待 P4d 评估**：output_hint 自动推导（现 llm 类显式声明）；`__llmretry__`
  旧语义装配；Optional 在 llm 类的表达（是否有更好的声明形式）。
- **契约/形式化待 P5**：`ProtocolDef` required/optional 分两组（`__intent__`/`__retry__`
  正式登记）；行为值深程统一装配入口收敛；`has_llm_call_cap` → LLMCallable。
- 历史遗留（此前登记）：`IbBehaviorInstance` 死类候选 + `binding_analysis_pass` getattr 探测
  （WORKLOG）；PT-DEBT-29/30/31、PT-DECIDE-2/3/4、PT-DEBT-4/5（PENDING_TASKS 支线）。
- 数字纪律：docs 中历史基线数字已过期，**一律以实跑为准**；`llm_handoff` 类历史提及（如
  REGISTER.md 历史实跑快照）保留为记录。

---

## 八、环境与纪律（勿忘）

- 测试唯一命令：`~/miniconda3/envs/ibci/bin/python -m pytest tests/`（conda env `ibci`）。
- 全程本地 `git commit`，**禁止 `git push`**（除非用户显式授权）；**永不触碰 `main`**。
- 每步：全量 pytest 零回归 + 描述性 commit + 同步 WORKLOG/NEXT_STEPS/HANDOFF；低风险增量
  可直接在 unsafe-vibe-dev 推进（合并即删短期分支），判定以"确认零风险"为准。
- 工作模式定论（NEXT_STEPS ⛔）：禁 compat shim / 胶水 / tricky / 过程式硬编码；质量优先；
  原则优先于行为维持；可推翻 IBCI 自身设计缺陷；"只记录，不断决"。
- 文档纪律：`docs/` 面向人类（无 agent 元信息、禁任务代号/日期戳）；任务控制文档单点真理、
  不冻结数字、不保留已完成历史（git 承载）。
- **goal 配置习惯（HANDOFF §1.2.1，已更新）**：`max_auto_turns` = **7**（非 10）。