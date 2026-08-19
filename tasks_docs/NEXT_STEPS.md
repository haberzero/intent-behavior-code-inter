# NEXT_STEPS — 当前最紧要项

> 本文件**只**记录当前最紧要、可立即开工的下一步与强制工作约束；长期规划见
> `tasks_docs/PENDING_TASKS.md`。本文件不承载历史完成记录（git 承载）；任务控制
> 治理见 `tasks_docs/GOVERNANCE.md`。
>
> **书写要求**：更新本文档必须按尾部「书写模式」模板与格式书写，保持一致。

---

## ⛔ 工作模式定论（强制，凌驾于本文件一切任务之上）

> **扎实推进，禁止任何形式的快速实现 / 兼容层 / 胶水实现 / tricky 实现。**

1. 禁止 compat shim / 兼容层：新设计就是真设计，旧代码要么真合并、要么真删除。
2. 禁止胶水实现：不在两个不统一的子系统之间塞字符串拼接 / 魔法哨兵 / 隐式约定。
3. 禁止 tricky 实现：不靠隐式字符串变换承载语义；不靠"凑巧相等"；不靠书写顺序掩盖数据依赖。
4. 禁止过程式硬编码分发：同一决策只通过协议驱动（`receive()` / vtable），不写 `if 能力标志位`。
5. 质量优先于速度：技术债必须先清；潜伏 bug 不允许过渡修复。
6. 原则优先于行为维持：既有行为违反一般工程/架构原则时，以原则为准，不以"保持已有行为"为主。
7. 可推翻 IBCI 自身设计缺陷：即使设计思路已在文档记录，也可按更普适、实践更合理的方案重建。
8. 破坏性重构授权：符合一般工程经验且经分析优于现有体系时默认已授权自主推进，详记决策。
9. 大范围破坏性重构分支政策：无法确认边界/危害程度的重构 100% 授权在独立分支实验；
   独立分支禁止直接合并到 unsafe-vibe-dev 或 main；永远不触碰 main。

---

## 🔴 当前状态

**主线：远期原生宿主绑定（F0-F5）已全部完成并合入 `unsafe-vibe-dev`**（路线图
`tasks_docs/ROADMAP_NATIVE_BINDING.md` §三 F0-F5）：宿主导入一等语法 + 宿主类型绑定
（F1-F2）、插件体系重构（F3, 废弃 _spec.py、内置 11 模块 `builtin_modules.py` 构造期
注册）、Provider 自定义经宿主绑定统一（F4, `ai.set_provider`）、架构统一/文档收敛
（F5, 档 A/内核自举/档 B/隔离/反射=远期 pending）。测试基线以实跑为准（不冻结数字，见下）。

**🔴 新主线：「llm 机制重构为可调用 llm 类 + LLM 相关体系彻底协议化（总统一性）」**（用户
2026-08-18 定方向，两时点补充）：用户决定**彻底抛弃"llm 函数"概念**，重构为**可调用的 llm 类**
（面向对象形态承载 LLM 调用/意图/llmexcept 等语义）。**第二轮补充**（同 session）：提出**总统一性
主线**——行为描述/意图注释/retry/prompt 协议族/lambda/snapshot/llm 函数全部收敛为"可调用实例 +
协议（类型类）"机制：lambda/snapshot 统一为 llm 匿名可调用类的两种捕获模式语法糖；`impl` 目标
扩展至内置类型（可改写 `int` 等的 `__prompt__` 系列）；retry 高阶化（行为实例也可经 impl 包装
retry）。

**本轮已产出**：
- 调研基准 `tasks_docs/_llm_callable_redesign.md`（可行性 + 规划，P0）；
- **交接清单 6 项补充调研全部完成 + 五大地基现状评估 + 总路线设计**
  （`tasks_docs/_five_foundation_redesign.md`，临时）：内置类型协议方法表机制形态（三选一落点）、
  lambda/snapshot 捕获策略参数化落点（值层已参数化，运行时闭包机制是主改造面）、retry 协议化
  边界（帧机制保留 + 语法/策略高阶化）、行为语句 vs llm 可调用类统一点（统一 LLMCallable
  消费路径）、能力公理 → 协议满足关系收敛（三层划分）、prompt 协议族类型类化（双注册表收敛 +
  to_prompt 死条目激活）；五大地基评分（函数式 3 / 类型类 3 / 类型理论 3 / 高阶函数 3.5 / 协议化
  3.5）；总路线 P1-P9。
- **6 项关键决策已用户拍板**（2026-08-18，落 `_five_foundation_redesign.md` §五）：
  ① 内置类型协议方法表选 B（per-IbClass 协议方法表，系统化重构）；② 内置类型行为改写 = 临时
  覆层机制（默认不生效、flag 启用、作用域化，最关键新设计约束）；③ snapshot 意图冻结按文档
  补齐（纯 snapshot lambda 也冻结意图）；④ `llm ... llmend` 语法**彻底删除**（非语法糖，全量
  迁移）；⑤ retry 帧机制保留 + 语法/策略高阶化；⑥ P1-P6 本主线，P7/P8 远期。

**下一 session 开工 = P1 设计定稿**（决策输入已收敛，见
`_five_foundation_redesign.md` §六 交接清单）——详见下一步候选 #1。

> **P1 设计定稿已完成（上一 session）**：用户明确 `llm ... llmend` 语法**彻底删除**且
> **关联旧机制一并彻底删除**（`__sys__/__user__/__llmretry__` 段、`IbLLMFunctionDef`、
> `callable_kind="llm_function"`、`_LLMFunctionMixin`、provider `user_sys` 槽等；不保留、
> 不兼容、不包袱）。P1 定稿已产出 `tasks_docs/_five_foundation_P1_design.md`（§一-§九，
> 7 项开工输入全部定稿）。

> **P2/P6 地基已完成并合入 `unsafe-vibe-dev`（本 session，用户确认零风险后纯 fast-forward 合并）**：
> 当前分支 = `unsafe-vibe-dev`（`exp/protocol-vtable` 实验分支已按"合并即删"政策删除）。已完成的零回归增量：
> - P2-① retroactive impl 目标扩展到内置类型（`impl P for int` 编译/运行/协议满足三环闭环，
>   合成 owned_scope 复用 F2 机制；commit `6c3f6c94`）；
> - D4 str 补齐 output_hint（`has_output_hint_cap` + `__outputhint_prompt__`，与 int/list/dict
>   一致；commit `eb8ecd30`）；
> - D9 死字段 `is_callable_instance` 清理（实证编译期不赋 True，删死分支；commit `6fd2cefc`）。
> 另有地基增量：收敛 receive 6 份重复分派骨架为单一 `_dispatch_protocol_message`（D5 机制
> 同构；commit `6d933080`）。当前 exp 分支全量基线以实跑为准：**2997 passed / 1 skipped**（含下述
> P2-② 覆层增量与复核补充的判别性测试）。
> **自主重排序（用户认可自主决定，2026-08-18）**：P2 剩余的②覆层机制/③to_prompt 激活/④
> `_dispatch` 查表与 P5 prompt 类型类化、P6 protocol_vtable 数据结构**深度纠缠**（D2 to_prompt
> 零消费者、D1 payload_prompt 双注册表均实证属 P5；协议方法表是共享地基）——为免半接通/
> 双通道（质量红线），**protocol_vtable 数据结构（P6 核心）优先**，作为 P2-②/P2③/P5 的落点。
> **protocol_vtable 数据结构已落地并提交（本 session）**：`ProtocolSlot`（消息名槽，native 按值
> Python 类解析 + 覆层影子条目默认不参与分派）+ `IbClass.protocol_vtable`（消息名键，惰性
> 建槽）+ `_dispatch_protocol_message` 查表分派（D5 消除）；全量 2985 零回归 + 判别性测试；
> commit `cd60ea6d`。
>
> **✅ P2-② 临时覆层机制已提交（本 session，commit 见 git log）**：`overlay`/`with` 新关键字 +
> `impl overlay for <T>:` 声明 + `with overlay(<T>.<协议方法>):` 作用域块全链路闭环（AST/parser/
> 语义/`_overlay_registry`/SEM_OVERLAY_UNUSED/水化影子条目/`vm_handle_IbWithOverlay` save-restore/
> `_dispatch_protocol_message` 覆层 IbFunction `.call()` 执行）。复核补充两处：① 新增端到端判别
> 测试（真实 `with overlay` 语句驱动 + 行为 `$x` prompt 渲染经 PromptRenderer receive 走覆层 /
> 块外恢复原生，mock 回显判别）；② `_OverlayRegistry.declared_items()` 公开遍历 API（收敛私有
> 字段跨模块访问）。e2e 6 项；全量 pytest **2997 passed / 1 skipped** 零回归；临时文档
> `_code_overlay.md`/`_code_protocol_vtable.md` 已随收尾删除（git 承载）。
>
> **✅ P2③/P5 prompt 协议族类型类化 D1+D2 已落地（本 session，unsafe-vibe-dev）**：D1 双注册表
> 收敛——`PROMPT_PROTOCOL_SPECS` 补第 5 成员 `__payload_prompt__`（用户契约 `(self)->dict|list|str`，
> runtime 零参数分派；trial D2-05 声明零伪警告、2 参声明出 SEM_PROTOCOL_SIGNATURE）；
> D2 to_prompt 死条目激活——`BaseAxiom.has_to_prompt_cap` 默认 True（通用渲染路径，单一真理）+
> to_prompt 协议条目接 `axiom_cap` + `PromptRenderer.to_prompt_str` 前置门（镜像 to_payload）+ 判别
> 测试；行为保持实证（内置/用户类/覆层端到端一致）；P1 §五 protocol_vtable 形状已订正为消息名键。
> 全量 pytest **3003 passed / 1 skipped** 零回归。G7 三层划分定位：has_llm_call_cap → LLMCallable
> 协议属 P4；**validate_prompt 死条目激活 = P5 剩余项**。
>
> **✅ P3 D8 snapshot 意图冻结补齐已落地（本 session，unsafe-vibe-dev）**：意图 fork 移出
> body_is_behavior 特判 → 按 capture_mode 统一（snapshot 恒 fork / lambda 恒 None）；`IbFnCallable`
> 增 `captured_intents`（与 IbBehavior 同构）+ 工厂/序列化补齐；`_vm_call_fn_callable` 增意图
> 生命周期（enter_intent_scope：lambda 得 IT-3 调用点 fork + snapshot 安装冻结快照，
> replace_intent_context(fork)，IT-4 隔离）。判别测试 `tests/e2e/test_snapshot_intent_freeze.py`
> （自定义 provider 记录 intents.merged）：快照=定义意图忽略调用处 smear、lambda=调用处 smear。
> 顺带清理死字段 `IbAssign.capture_mode`。全量 pytest **3011 passed / 1 skipped** 零回归。
>
> **✅ P3 G5/G2 意图一等值切片·可调用值有意契约嵌入已落地（本 session，unsafe-vibe-dev）**：意图段
> 求值渲染大面已工作（int/str 值经 segments→PromptRenderer 正确）；G2 缺口 = 函数/可调用/行为值
> 渲染为 Python repr → `IbUserFunction.__to_prompt__` 改 `func <name>(<参数>) -> <ret>`（取 spec
> 值层自持签名）+ `IbFnCallable`/`IbBehavior` 的 `__to_prompt__`/`_dispatch_to_prompt` 统一
> `signature_name()`；判别测试 `tests/e2e/test_intent_callable_embedding.py`；既有断言 `<Function>`
> 语义演进为契约形式。全量 pytest **3019 passed / 1 skipped** 零回归。G5"值栈全量重构"剩余面
> （栈存原始值/按值匹配）与 P4 (LLMCallable) 对齐评估。
>
> **✅ P4a LLMCallable 协议地基已落地（本 session，unsafe-vibe-dev）**：`BUILTIN_PROTOCOLS` 增
> `llm_callable`（`__llm_call__` 必需方法 = "能否被 LLM 消费"唯一判定，P1 §2.1；required/optional
> 形式化归 P5/P6）；判别测试（用户类实现→满足/不实现→不满足）。P4 为巨型阶段，拆子增量轮次推进
> （勿半接通）：P4a（本轮，纯增量零破坏）→ P4b 装配路径 → P4c llm 语法+旧机制删除+全量迁移
> （摸底 36 测试 + 66 示例/试用文件面）→ P4d retry 高阶化。全量 pytest **3020 passed / 1 skipped**
> 零回归。
>
> **✅ P4b LLMCallable 装配路径设计定稿（本 session，设计轮）**：装配上下文 `IbLLMCallAssemblyCtx`
> （IBCI 一等对象，可写槽 + 只读意图/输出契约）+ 用户 `__llm_call__` 契约 + 统一装配入口
> `assemble_llm_callable_request_cps`（CPS 生成器，差异经协议方法承载）+ 落地顺序。
> 设计文档 `tasks_docs/_code_p4b_assembly.md`（临时，实现后删除）。
>
> **✅ P4b-2a LLMCallable 统一装配路径实现已落地（本 session）**：`_LLMCallableMixin`
> （`_llm_callable.py`，组合进 LLMExecutorImpl）——`assemble_llm_callable_request_cps`（协议门 →
> CPS 调用户 `__llm_call__` → 装配 dict→LLMCallRequest）+ `invoke_llm_callable_cps`（装配 →
> 统一 worker）。契约定稿：用户 `__llm_call__(self) -> dict` 返回装配配置 dict（ctx 对象降级
> P4b-2b 扩展）。判别测试 `tests/e2e/test_llm_callable_unified.py`（用户 llm 类端到端 mock +
> fail-fast）。全量 pytest **3028 passed / 1 skipped** 零回归。
>
> **✅ P4b-2b run_batch 统一消费 LLMCallable 实例已落地（本 session）**：`run_batch` 移除"仅
> behavior"窄拒——行为（items 逐项绑参保留）+ 用户 llm 可调用实例（`_RunLLMCallableDrive`
> Waitable 经统一装配入口单次执行；items 参数化归 P4b-2c）+ fail-fast；`builtin_modules.py`
> run_batch 首参型宽化为 any。判别（新增 run_batch-llm-callable）+ 行为 run_batch 零破坏。全量
> pytest **3029 passed / 1 skipped** 零回归。
>
> **✅ P4b-2c llm 类 run_batch 逐项参数化契约已落地（本 session）**：`__llm_call__(self, any item)`
> 可选 item 参（经 method.spec.param_types 检测）→ assemble/invoke 按需传项；`_RunLLMCallableDrive`
> 批量化（每 item 一次 LLM 调用，boxed 结果列表；并发优化留待后续）。run_batch 语义收敛为
> **每 item 一次调用**。判别：无参→单次固定装配；声明 item 参→逐项装配（"欢迎1"/"欢迎2"）。
> 全量 pytest **3030 passed / 1 skipped** 零回归。

> **✅ P4b-3a `__intent__` 可选协议方法运行时发现已落地（本 session，unsafe-vibe-dev）**：
> 装配入口 `assemble_llm_callable_request_cps` 经 `lookup_method`（receive 同源虚表）
> 发现 `__intent__`，存在则经 `UserFunctionCall` CPS 调用用户 `func __intent__(self, dict
> intents) -> dict`——入参三层（active/global/merged，与 `LLMCallRequest.intents` 对齐）；
> 返回 dict 键为三层任意子集：存在键替换对应层（消解/增删/重排）、缺失键透传、显式空列表
> 清空层；结果合并回装配（单调用与 run_batch 共用装配入口自动继承）。契约违约（参数数≠1 /
> 返回非 dict / 层值非 str 列表）fail-fast。判别测试 +5（改写 merged + 读入 global 层 /
> 透传 active+global / 空列表清空层 / 批量继承 / 违约 fail-fast）；行为值路径零变化。
> **`__retry__` 装配消费归 P4d**（避免零消费者半接通；发现机制与 `__intent__` 同一通道）；
> **装配上下文按需引入（当前无消费者，不引入）**。全量 pytest **3035 passed / 1 skipped** 零回归。

> **✅ P4b-3b 流式消费面统一已落地（本 session，unsafe-vibe-dev）**：
> `stream_call`/`stream_channel` 统一消费 LLMCallable——`assemble_stream_request_cps`
> （统一流式装配：行为值 → 语义槽装配 / 用户 llm 类 → 统一装配入口含 `__intent__`
> 改写）+ `_StreamCallableDrive`（帧内 CPS：装配 → IbStreamHandle；stream_call yield
> 句柄取完整文本（与旧调用点 auto-yield 语义一致），stream_channel 返回 IbChannel
> 逐块消费）；字符串形态（sys_prompt, user_prompt）**真删除**（3 语言测试迁移 + 行为值
> 判别测试 + `docs/syntax/11_modules.md` 同步）；ai 模块 `_require_llm_executor` 收敛
> run_batch/stream 共用。试用 T01/T08 4 个 case 字符串形态残留 = **P4c 66 文件迁移面
> 登记**。全量 pytest **3036 passed / 1 skipped** 零回归。

> **✅ P4c `llm ... llmend` 语法与旧机制全链路删除 + 全量迁移已落地（本 session，unsafe-vibe-dev）**：
> ① **P4c-1 特性地基**（f5527e88）：LLMCallable 实例**直接调用** `f(args)`（`_dispatch_call` 路由 +
> `_LLMCallableCallDrive`，参数按位绑定含默认值惰性填充、`_finalize_invoke_result` 语义对齐）+ 调用
> 表达式静态类型 = 动态 any + 装配 dict 扩展 `prompt_slots` 键（`__sys__` 迁移载体）+ `call_args`
> 参数化；② **P4c-2a 测试迁移**（61486deb）：e2e/contracts/runtime 10 文件 llm 函数/llm 方法 →
> llm 可调用类（语义演进：实例渲染 `<Instance of T>`、fn 只收 lambda、`__llmretry__` 迁
> `__retry__`/P4d、output_hint 显式声明）；③ **P4c-2b 内核删除**（5657dcee，净删 656 行）：
> lexer token + `llm_scanner.py` + `LexerMode.LLM_BLOCK`/parser `llm_function_declaration` +
> 顶层 `llmretry` 语法糖 + AST `IbLLMFunctionDef` + semantic 4 pass `is_llm` 分支 +
> `SymbolKind.LLM_FUNCTION`/`llm_method` kind + `_vm_invoke_llm_function`/`callable_kind` 字段 +
> `_LLMFunctionMixin` 整文件 + provider `user_sys` 槽特殊处理（自定义槽统一呈现）；**保留
> `llmexcept`/`retry` 帧机制**；④ **P4c-2c 迁移收尾**（9cf15e9f）：examples + trials 12 case +
> docs 全面同步（`08_llm_functions`→`08_llm_callable` 参考重写、`guide/05_llm_functions`→
> `05_llm_callable` 教程重写、llmretry 文档合并删除、KNOWN_LIMITS/SYNTAX_REFERENCE 等更新）。
> 全仓 core 残留清零；全量 pytest **3035 passed / 1 skipped** 零回归。

## 下一步候选（当前主干按序；支线仅在不打断主线时介入）

1. **[主线·当前] P4d：retry 高阶化（决策 5）**：
   **当前分支 = `unsafe-vibe-dev`**（P2/P6 地基 + 覆层 + prompt 类型类化 D1+D2 + P3 D8/G2 +
   P4a + P4b 全量 + **P4c 语法/旧机制删除 + 全量迁移**（3035 零回归）已合入）。
   设计权威 `tasks_docs/_five_foundation_P1_design.md` §七（retry 高阶化）+ §2.2（`__retry__`
   可选协议方法契约），决策权威 `_five_foundation_redesign.md` §五（决策 5：帧机制保留 +
   语法/策略高阶化）。
   **本步 = P4d retry 高阶化**：
   - `__retry__` 可选协议方法落地（P1 §2.2：声明快照策略 + 重试策略 + hint；`satisfies`
     非强制，存在则经 `lookup_method` 发现——P4b-3a 同通道）+ 装配消费（决策 5）；
   - llm 可调用类自定 retry：实现 `__retry__` 覆盖默认帧策略；行为语句默认 retry 由帧机制
     提供（用户不写 `__retry__` 时行为实例走默认）；
   - 承接 P4c 记录项：`__llmretry__` 旧段语义（重试 hint 注入）在此落地；output_hint 自动
     推导评估（P4b 记录）。
   验证门：全量 pytest 零回归 + 本地 commit + 描述性提交。
   **后续子增量**：P5（validate_prompt 死条目激活 G7 收尾 + prompt 类型类化剩余 +
   required/optional 协议条目形式化）→ P6（per-IbClass 协议方法表最终收尾）。
   **待 P4 对齐项**：G5 意图值栈全量重构 + has_llm_call_cap → LLMCallable 协议 +
   行为值深程统一装配入口收敛（run_batch/invoke 行为路径，当前经各自入口）。
2. 支线：PT-DEBT-29/30/31、PT-DECIDE-2/3、PT-DEBT-4/5；
3. 支线：真实 LLM 压力试用扩展（VISION-3）；文档体系持续治理。

（最近完成与过程记录见 git log；长期裁定见 `tasks_docs/WORKLOG.md`。）

---

## 工作规则

- 同一时刻只主推一个 P0 阶段。
- 工作模式定论优先；改动公理层或语义错误集的任务需全量 pytest 评估破坏面。
- 重大架构决策直接写入 `docs/architecture/` 对应章节，不使用独立 ADR 文件。
- 测试基线以实跑为准，不冻结数字（唯一命令 `python -m pytest tests/`，见 AGENTS.md）。

---

## 附、书写模式（本文档专用模板，书写必须参照）

> 本节是本文档书写的**唯一权威模板**（模板归属 = 文档自身；`GOVERNANCE.md`
> §三 仅做索引）。更新本文档一律按下列结构与格式书写。

### 1. 文档结构

```
# NEXT_STEPS — 当前最紧要项
定位段（只记录当前最紧要、可立即开工的下一步与强制约束；不承载历史完成记录）
⛔ 工作模式定论（强制，凌驾于本文件一切任务之上；9 条硬约束）
🔴 当前状态（1 段：当前主线/任务 + 状态；无进行中主线时明确写出）
**下一步候选**（等待用户指示的候选项，按序编号）
工作规则（持续推进的硬规则）
（最近完成与过程记录由 git 承载，不在本文件登记）
```

### 2. 主线状态格式（有进行中主线时）

| 列 | 内容 |
|----|------|
| 阶段 | 阶段代号 + 一句话主题 |
| 状态 | 🔄 进行中 / ⏳ 待用户 / ❌ 阻塞（**不登记已完成阶段**——完成即从本文件移除） |
| 内容 | 本阶段正在做什么（2-4 项要点） |
| 验证 | 放行门（全量 pytest 实跑 + 复核，不冻结数字） |

### 3. 维护规则

- 主线变更时更新"当前状态"与"下一步候选"；**阶段完成即移除**（不保留完成登记）。
- **工作模式定论为最高约束**：修改其中条目属用户裁定级变更，须由用户拍板，不自主改写。
- 待用户确认项只在此标注；不建独立章节。
- 不出现日期戳、历史叙述、测试数字（基线以实跑为准）；引用其它任务控制文档用相对路径指针，不复制正文。