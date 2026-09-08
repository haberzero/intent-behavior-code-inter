# HANDOFF — 常驻交接与固定化内容库

> 本文件**持久保留**（非临时交接）：为每个 session 提供**固定化模板 / 通用流程 / 工作原则**，
> 以及**当前任务状态**。
>
> **使用方式**（下一个 session 开始工作时）：
> 1. 根据当前任务分析：读 `NEXT_STEPS.md`（当前最紧要）+ `PENDING_TASKS.md`（长期规划）。
> 2. 从本文件 §一 获取**固定化内容**（goal 模板 / 工作流程 / 工作原则 / 约束）。
> 3. 按 §二 **动态状态** 接续当前工作。
>
> **维护规则**：§一 长期不变（新增用户裁定时补充）；§二 随任务更新。**不因任务完成删除本文件**。
> 工作流程权威源为 `AGENTS.md`，本文件只放指针与模板，不复制通用正文（单点真理）。
>
> **书写要求**：更新本文档必须按尾部「书写模式」模板与格式书写，保持一致。

---

## 一、固定化内容（长期不变）

### 1.1 工作流程（AGENTS.md 为权威源，此处只列指针）

- **自主工作循环**：理解 → 设计质询 → 自主决策 → 实现 → 自反馈验证 → 自主纠错 → 交付自查 → 收尾。
- **上报阈值**：穷尽自主手段仍无法决定才上报；破坏性重构默认已授权；分支政策见 AGENTS.md。
- **交付纪律**：全程本地 commit；**禁止 push**（硬原则，除非用户显式授权）。
- **工作日志**：自主决策/方案取舍/变化前后记录于 `WORKLOG.md`（"只记录，不断决"）。
- **测试**：`python -m pytest tests/`（唯一命令；环境规格权威源 = `pyproject.toml` + `docs/guide/00_environment.md` 规范 recipe；本机事实见 `AGENTS.local.md`）。
- **Skill 工作流**：code-workflow（实现）/ code-review（缺陷复核）/ code-quality（健康诊断）/
  code-odor（异味扫描）/ quality-maintenance（分层质量维护）/ doc-governance（文档治理）/
  self-grill（自我质询）/ design-philosophy（设计哲学）。

### 1.2 关键用户裁定与工作原则

| 原则 | 内容 |
|------|------|
| 碎片化判断基准 | 碎片化 = **设计语言（用户语义形态）统一**，非实现路径一致。同类内容内部路径差异有语义需求驱动且不改变用户语义形态，即非碎片 |
| "不删也不修" | 有缺陷/冗余的机制只能"**根本修复**"或"**彻底删除**"两档，禁止"废弃记录"中间态 |
| subagent 约束 | 所有 subagent 工作（含 review）**仅允许 general agent**，禁 explore/reviewer 特化 agent |
| 决策纪律 | 需拍板的决断项可大胆激进选方案；底线 = 架构原则/代码质量原则/非妥协/非 tricky/非临时兼容层/大方向主线 |
| 设计阶段文档 | 设计/决策先写 `tasks_docs/`，落地后按治理写入 `docs/`；`docs/` 只面向人类 |
| 工作模式定论 | 禁 compat shim/胶水/tricky/过程式硬编码；质量优先于速度；原则优先于行为维持；可推翻 IBCI 自身设计缺陷 |
| 破坏性重构授权 / 分支政策 / 禁 push | 见 AGENTS.md（权威源）。**分支合并细则（2026-08-18 更新，取消 cherry-pick）**：确认低风险/边界清晰（全量 pytest 零回归 + 复核放行）可直接 **merge** unsafe-vibe-dev；merge 无误即删无用分支（除 main 与 unsafe-vibe-dev 外不长期保留分支）；main 不更新不触碰；判定以"是否确认零风险"为准 |

### 1.2.1 goal 配置习惯（每个 session 新配置 goal 时自动采用，用户定案）

> 创建 goal（`create_goal` / `set_goal`）时按此默认参数，除非用户在本 session 显式覆盖：
>
> | 参数 | 值 | 说明 |
> |------|----|------|
> | `max_duration_seconds` | **14400（4 小时）** | 最晚结束时间 = 当前时刻 + 4h |
> | `max_auto_turns` | **7** | 允许 goal 自动续跑次数 |
> | `token_budget` | **null（无限制）** | 不设 token 预算上限（预算无限制；720K 为模型上下文窗口系统层硬限制，非 goal budget） |
>
> `objective` 正文仍按下方 §1.3 模板套用（无人值守 + 主线 + 交付纪律 + 工作流 + 停止条件 + 非目标）。

### 1.3 goal objective 模板（通用骨架，可直接套用）

```
【<任务名> · 无人值守】主任务：<按 NEXT_STEPS/PENDING_TASKS 定位的当前最紧要目标，
写明阶段/批次/具体项>。

一、主线任务（按序，依赖驱动，每步全量 pytest 零回归 + commit + 同步 NEXT_STEPS/WORKLOG）：
  <列出任务项；每完成一项用描述性 commit 提交并自动接续下一项>

二、自主推进偏好（最高优先）：总体偏向无人值守，允许较大限度自我裁定与自我质询分析并
尽可能推进。只有经过最大限度反思/质询/分析后仍确实无法彻底自主决定的内容才造成阻塞。
凡能自主决断的一律自主决断并详尽记录决策依据（工作日志）。上报阈值统一为"尽可能自主推进"。
决策纪律：可大胆激进选方案，底线=架构设计原则/代码质量原则/非妥协/非tricky/非临时兼容层/
大方向主线任务。不因需拍板而停滞。

三、交付纪律：全程本地 git commit；禁止 push 到 GitHub（硬原则）——除非用户明确指示允许
push，否则一律禁止 git push 到任何远程仓库。破坏性重构授权（硬原则）：符合一般工程经验/
普适性/合理架构设计且经分析确实优于现有体系时，哪怕设计已被文档记录也允许破坏性重构，
 默认已授权自主推进，仅需详尽记录决策依据与工作内容。大范围破坏性重构分支政策（硬原则，
 "零风险直接合并"细则；2026-08-18 更新合并流程，取消手动 cherry-pick）：无法确认边界/
 危害程度的破坏性重构 100% 授权在其独立分支实验，允许任意破坏性实验；永远不允许触碰主干
 分支（main）。**合并细则（2026-08-18 更新）**：确认低风险/边界清晰的改进（全量 pytest
 零回归 + 复核放行，无对外契约/架构级风险）可直接 **merge** 到 unsafe-vibe-dev；merge 无误后
 直接删除无用分支（除 main 与 unsafe-vibe-dev 外不长期保留分支，短期工作分支合并即删）。
 判定以"是否确认零风险"为准，非以改动规模。工作日志：所有自主决策/
 方案取舍/变化前后必须详尽记录于 WORKLOG，"只记录，不断决"。

四、工作流：每任务走 code-workflow Phase 0-5 + 质量门 + design-philosophy 对照 + self-grill
自我质询 + code-odor 自查 + 全量 pytest 零回归（python -m pytest tests/）。批量后 code-review
残留扫描。

五、主任务阻塞/暂停时的支线（按优先级，解阻立即回主线）：1) 质量维护/代码健康
（quality-maintenance Tier A/B）；2) PT-AUDIT-1/2 代码质量审计（独立分支）；
3) PT-FEAT-5 错误用户友好化（剩余 CI/CD 可靠化设计；PT-FEAT-2 已完成、已移除）；
4) 测试体系补测（PT-TEST-2 覆盖矩阵缺口；PT-TEST-1 已完成、已移除）。每条支线仍须全量 pytest 零回归、commit+留痕（仅本地）。

六、停止条件：先穷尽自主手段，仅当确实无法自主决定时（用户意图不明穷尽无解/公理层语义
错误集确需用户裁决/与工作模式定论冲突/破坏性重构无法确认边界且独立隔离分支也无法确定
技术路线）才 update_goal(status="unmet", blocker=具体卡点+建议)。

七、非目标：media Phase 4（PT-SEALED-1）、跨进程/CPU 并行、跨引擎通信、线程无损挂起/恢复、用户级泛型类（PT-FEAT-3）、Hindley-Milner 约束求解。`yield` 惰性生成器（PT-FEAT-1）是阶段 5 下一主线，非"非目标"；是否纳入本 goal 视主任务界定。
```

### 1.4 tasks_docs/ 文档结构指针

| 文档 | 用途 |
|------|------|
| `NEXT_STEPS.md` | 当前最紧要项 / 工作模式定论（强制约束）/ 工作规则 / 下一步候选 |
| `PENDING_TASKS.md` | 长期规划与搁置任务（任务代号按性质分域：PT-FEAT/PT-DEBT/PT-AUDIT/PT-DOC/PT-TEST/PT-DECIDE/PT-SEALED） |
| `HANDOFF.md` | 本文件：固定化内容 + 动态状态 |
| `WORKLOG.md` | 自主工作日志（关键裁定；设计决策收敛于 `PENDING_TASKS.md`） |
| `trials/` | 试用地基（T01-T07）与工具链 `trials/_toolkit/`（harness / batch / 用例即契约 / LLM_SERVICE）——测试资产，非任务控制文档 |

---

## 二、动态状态（随任务更新）

### 2.1 当前工程状态 / 下一阶段

> **接手起点**：读本节 + `tasks_docs/NEXT_STEPS.md`（当前最紧要 + ⛔ 工作模式定论）+
> `tasks_docs/PENDING_TASKS.md`（远期规划）+ `tasks_docs/GOVERNANCE.md`（任务控制治理）
> + `git log --oneline -30`（近期提交与工作动线）。

- **🔴 当前主线 = round3 试用需求整合队列（2026-09-08 intake，free-explore）**：
  试用方第三轮需求单 `ibci_feedback_round3.md`（v3 统一自动机 R185–R202 实证摩擦
  全集）intake 完成——单点记录 = `tasks_docs/_trial_round3_intake.md`（逐条核验 +
  耦合分析 + 新队列）；`trials/INDEX.md` 补登记 `KERNEL_ISSUE-VM-2`（试用方 R183
  上报的 D-1 fielded 类×LLM 调用 VM 缺陷，此前未入台账 = 流程缺口已修）。
  按恒高优先原则 round3 P0 插入现有阶段 E 队列之前：**~~R3-① D-1
  KERNEL_ISSUE-VM-2 修复~~ ✅ 已完成（2026-09-08：编译期构造器/零参方法静态
  绑定检查 + 运行期 auto-init 回退角落修正 + 显式内置父动态跳过；判别 25 项 +
  既有 4 项语义演进 + 全量 3563/1 零回归，git 承载）→ ~~R3-② D-2 三引号多行字符串~~ ✅ 已完成（2026-09-08：IN_TRIPLE_STRING
  态 + 转义共享 _apply_string_escape + 既有缺陷修复[字符串内置位
  continuation_mode 泄漏]；判别 36 项 + 全量 3605/1 零回归）
  → R3-③ D-3/D-4 str 原语四件套（当前项）[count/find(m,from)/rfind/
  原生切片 O(n)] → R3-④ D-5 stdout 行缓冲/--unbuffered → R3-⑤ R-1+R-3+R-4 run
  级可观测子系统[journal append-only + --replay 确定性重放 + run_summary 预算 +
  --result-json；单一设计文档一批批实施，对照原批 3 C7 消重防双通道]
  → R3-⑥ E1 重做 + R-2a run_file[ihost 子环境整合设计]**；P1 六项（诊断消息
  批[含原 B4] / D-7 裸声明语义 / D-10 json 鲁棒面 / F-2 思考抑制警告可配置 /
  R-7 429 退避 / R-8 knowledge 扩展面）+ P2 文档批两项按序；原批 2 剩余
  （A2/A5/B2）与批 3（A6/B5/C6/C7/D2/D3）整体顺延保留。长期登记不实施
  （架构安全/长期收益优先，用户 2026-09-08 指示）：R-2b meta.compile + R-6
  行为表达式作值（VISION-4/5 类型类/函数式方向耦合，不半接通）/ D-3.3 VM
  字符串扫描快速路径（VM 执行模型性能架构面，Tier C 候选）。F-2 真相核验
  （run 存档实证）：警告每进程一次性（去重机制正常）+ 试用方 4B 后端强制
  思考为事实（reasoning 隔离 `reasoning_content` 字段，content 干净）→ 处置
  = 可配置静默 + 语义澄清（非机制缺陷）。基线以实跑为准（intake 前实跑
  3534 passed / 1 skipped 零回归）。**E1 重做方案（R3-⑥ 前置，设计定案
  保留）**：spawn 时点快照继承——engine.run 增 on_ready 参数（prepare 后、
  execute 前触发；run 的 execute 调用点以 abs_entry 上下文精确定位）；子
  线程 run(on_ready=...) 钩子内应用父配置快照（to_llm_config 归一化
  apply_config）；失败 issue_tracker WARNING（HOST_ISOLATE_LLM_INHERIT_FAILED，
  不阻断）；验证 = mock 模式 + 继承断言 + 快照语义（spawn 后父变异子不变）；
  **防卡死：spawn 测试 request_collect 默认无界等待——判别测试须传有限
  collect 超时（IsolationPolicy collect_timeout）**。运行注记：测试套件
  双层防卡死已就位（pytest-timeout 每测试 60s 自动报告 + 看门狗 180s——
  无输出退出 124 = 框架层 hang，读完整 stderr 线程栈；用法见
  docs/howto/keep_tests_safe.md）。详见 `tasks_docs/NEXT_STEPS.md` +
  `tasks_docs/WORKLOG.md`（round3 整合条目）+ git log。
- **✅ 会话交接核验接手完成（2026-08-21）**：HANDOFF_SESSION 待验证清单全通过（git 干净 /
  main 未动 / 提交序列对齐 / 全量 pytest 实跑 **3182 passed / 1 skipped** / 契约 §五-§七 +
  规划已读）；**push 已获用户显式授权并执行**（本地 28 提交 `b2322214..e1a9b3d9` 推送
  origin/unsafe-vibe-dev，当前与 origin 同步；**push 授权不延续**，后续 push 需再获显式授权）；
  HANDOFF_SESSION.md 要点已收敛入本节并删除（git 承载）。阶段 B（B1-B6）全部完成，当前 P0 =
  阶段 C。
- **🔴 当前主线**：**远期原生宿主绑定（F0-F5）已全部完成**（路线图
  `tasks_docs/ROADMAP_NATIVE_BINDING.md` 已随完成删除，git 承载；远期工程项见
  `tasks_docs/PENDING_TASKS.md` VISION-6）。宿主导入一等语法 `import python "pkg" as lib:
  bind ...` + 宿主类型绑定 + 插件体系重构 + Provider 自定义经宿主绑定统一均已落地：
  - **F0-F2**：宿主导入/宿主类型一等绑定（EXTERNAL_MODULE CLASS + per-instance vtable）。
  - **F3**：废弃 Python `_spec.py` 磁盘发现/加载通道，用户侧扩展唯一边 = 宿主绑定
    `bind`；内置 11 模块（内核原生 5 + 工具 5 + file）TypeDef 字面量集中
    `core/runtime/bootstrap/builtin_modules.py` 构造期一次注册；插件搜索路径配置面/
    ibci_sdk/__ibcext_axiom__ 死协议等全铲除；Engine 签名简化 `IBCIEngine(root_dir=...)`。
  - **F4**：Provider 自定义经宿主绑定统一——用户写实现 `LLMProvider` 契约的 Python 类，
    经 `import python "my_provider" as lib: bind provider` + `ai.set_provider(lib.provider)`
    注册为激活 `llm_provider`（HIGH 优先级覆盖内置默认 RecommendedProvider）；R 期"改
    provider_impl.py"临时形态已拆除（provider_impl.py 降为内置默认实现）。
  - **F5**：架构统一/文档收敛——档 A 缓存/内核自举/档 B 真 JIT/隔离/反射评估为**远期
    pending 规划**（当前"引擎单次执行"模型下收益有限）；文档与代码一致。
- **当前代码状态**：
  - **当前分支 = `unsafe-vibe-dev`**（P2/P6 地基已并入：用户确认零风险后把 `exp/protocol-vtable`
    实验分支纯 fast-forward 合并，合并即删，仅剩 `main` + `unsafe-vibe-dev`）。本地领先 `origin`
    （**未 push**；禁 push 硬原则）。**main 不触碰**。
  - 用户侧扩展唯一边 = 宿主绑定 `bind`（`docs/howto/extend_with_host_binding.md`）；
    自定义 LLM provider = 宿主绑定 + `ai.set_provider`（`docs/howto/modify_llm_provider.md`）。
  - LLM 供应商无关中间层 `core/base/llm_protocol/`；MOCK 哨兵在该层 `llm_call.py`。
- **⏳ 下一步（新主线）**：**五大地基完整改造**（llm 可调用类 + LLM 体系彻底协议化（总统一性）
  + 函数式 / 类型类 / 类型理论 / 高阶函数 / 协议化）——用户 2026-08-18 定方向 + 6 项关键决策
  已拍板：① 内置类型协议方法表选 B（per-IbClass 协议方法表，系统化重构）；② 内置类型行为改写
  = **临时覆层机制**（默认不生效、flag 启用、作用域化，最关键新设计约束）；③ snapshot 意图冻结
  按文档补齐；④ `llm ... llmend` 语法**彻底删除**（非语法糖）；⑤ retry 帧机制保留 + 语法/策略
  高阶化；⑥ P1-P6 本主线、P7/P8 远期。
  **调研/可行性/规划/决策已全部产出**（临时文档 `_llm_callable_redesign.md` +
  `_five_foundation_redesign.md` + `_five_foundation_P1_design.md`——**已随 P1-P6 竣工删除，
  git 承载历史**；含交接清单 6 项补充调研 + 五大地基现状评估 + 总路线 P1-P9 + 决策 §五 +
  P1 开工输入 §六 + 用户追加裁定「`llm ... llmend` 语法彻底删除且旧机制一并删除、不兼容不包袱」）；
  **P2/P6 地基已完成并合入 `unsafe-vibe-dev`**（本 session 用户确认零风险后 fast-forward 合并）。
  **已合入增量**：protocol_vtable 数据结构（`ProtocolSlot` + `IbClass.protocol_vtable` 消息名键 +
  `_dispatch_protocol_message` 查表分派，`cd60ea6d`）+ 地基（receive 6 份骨架收敛 `6d933080`）+
  P2-①（impl 内置目标 `6c3f6c94`）+ D4（str output_hint `eb8ecd30`）+ D9（is_callable_instance
  清理 `6fd2cefc`）+ **P2-② 临时覆层机制（`1d3fc74a`）**。
  当前分支（`unsafe-vibe-dev`）全量基线以实跑为准：**2997 passed / 1 skipped**（零回归）。
  **✅ P2-② 临时覆层机制已提交（本 session）**：`overlay`/`with` 新关键字 + `impl overlay for <T>:`
  声明 + `with overlay(<T>.<协议方法>):` 作用域块 + 语义校验 + `_overlay_registry` + 未启用告警
  SEM_OVERLAY_UNUSED + 诊断目录/文档同步 + 水化影子条目 + `vm_handle_IbWithOverlay` save/restore +
  `_dispatch_protocol_message` 覆层 IbFunction `.call()` 执行 + e2e 判别性测试 6 项。复核实证：
  receive 分派块内覆层生效/块外恢复原生（端到端：真实 `with overlay` 语句 + 行为 `$x` prompt 渲染
  经 PromptRenderer receive 走覆层、mock 回显判别）、未启用告警、全量 2997 零回归。复核补充：
  `_OverlayRegistry.declared_items()` 公开遍历 API（收敛私有字段跨模块访问）。临时文档
  `_code_overlay.md`/`_code_protocol_vtable.md` 已删除（git 承载），决策要点沉 WORKLOG。
  **✅ P2③/P5 prompt 协议族类型类化 D1+D2 已落地（本 session，unsafe-vibe-dev）**：D1 双注册表
  收敛——`PROMPT_PROTOCOL_SPECS` 补第 5 成员 `__payload_prompt__`（用户契约 `(self)->dict|list|str`，
  runtime 零参数分派；trial D2-05 零伪警告、2 参声明出 SEM_PROTOCOL_SIGNATURE）；D2 to_prompt
  死条目激活——`BaseAxiom.has_to_prompt_cap` 默认 True（通用渲染路径）+ to_prompt 协议条目接
  `axiom_cap` + `PromptRenderer.to_prompt_str` 前置门（镜像 to_payload）+ 判别测试；行为保持实证
  （内置/用户类/覆层端到端一致）；P1 §五 protocol_vtable 形状订正为消息名键；G7 定位
  （has_llm_call_cap→P4；validate_prompt 激活 = P5 剩余项）。全量 pytest **3003 passed / 1 skipped** 零回归。
  **✅ P3 D8 snapshot 意图冻结补齐已落地（本 session，unsafe-vibe-dev）**：意图 fork 移出
  body_is_behavior 特判 → 按 capture_mode 统一（snapshot 恒 fork / lambda 恒 None）；`IbFnCallable`
  增 `captured_intents`（与 IbBehavior 同构）+ 工厂/序列化补齐；`_vm_call_fn_callable` 增意图
  生命周期（lambda 得 IT-3 调用点 fork + snapshot 安装冻结快照，IT-4 隔离）；判别测试
  `tests/e2e/test_snapshot_intent_freeze.py`；清理死字段 `IbAssign.capture_mode`。全量 pytest
  **3011 passed / 1 skipped** 零回归。
  **✅ P3 G5/G2 意图一等值切片·可调用值有意契约嵌入已落地（本 session，unsafe-vibe-dev）**：
  函数/可调用/行为值不再渲染 Python repr——`IbUserFunction.__to_prompt__` → `func <name>(<参数>) ->
  <ret>`（spec 值层自持签名）+ `IbFnCallable`/`IbBehavior` 的 `__to_prompt__`/`_dispatch_to_prompt`
  统一 `signature_name()`；判别测试 `tests/e2e/test_intent_callable_embedding.py`；既有 `<Function>`
  断言语义演进为契约形式。全量 pytest **3019 passed / 1 skipped** 零回归。G5"值栈全量重构"剩余面
  与 P4 (LLMCallable) 对齐评估。
  **✅ P4a LLMCallable 协议地基已落地（本 session，unsafe-vibe-dev）**：`BUILTIN_PROTOCOLS` 增
  `llm_callable`（`__llm_call__` 必需方法 = 能否被 LLM 消费唯一判定）+ 判别测试；纯增量零破坏。
  P4 为巨型阶段，拆子增量轮次推进（P4a→P4b 装配→P4c 语法删除+迁移→P4d retry 高阶化）。
  全量 pytest **3020 passed / 1 skipped** 零回归。
  **✅ P4b LLMCallable 装配路径设计定稿（本 session，设计轮）**：装配上下文 `IbLLMCallAssemblyCtx`
  （IBCI 一等对象）+ 用户 `__llm_call__` 契约 + 统一装配入口
  `assemble_llm_callable_request_cps`（CPS 生成器）+ 落地顺序；设计文档
  `tasks_docs/_code_p4b_assembly.md`（临时，实现后删除）。避免半接通——装配契约未钉死不强行实现。
  **✅ P4b-2a LLMCallable 统一装配路径实现已落地（本 session）**：`_LLMCallableMixin`
  （`llm_executor/_llm_callable.py`，组合进 LLMExecutorImpl）——`assemble_llm_callable_request_cps`
  （协议门 → CPS 调用户 `__llm_call__(self) -> dict` → 装配 dict→LLMCallRequest）+ 
  `invoke_llm_callable_cps`（装配 → 统一 worker `_call_and_parse`）。契约定稿：用户返回装配
  配置 dict（ctx 对象降级 P4b-2b 扩展）。判别测试 `tests/e2e/test_llm_callable_unified.py`
  （用户 llm 类端到端 mock + fail-fast）。全量 pytest **3028 passed / 1 skipped** 零回归。
  **✅ P4b-2b run_batch 统一消费 LLMCallable 实例已落地（本 session）**：`run_batch` 移除"仅
  behavior"窄拒——行为（items 逐项绑参保留）+ 用户 llm 可调用实例（`_RunLLMCallableDrive`
  Waitable 经统一装配入口单次执行）+ fail-fast；`builtin_modules.py` run_batch 首参型宽化为 any。
  判别新增 run_batch-llm-callable + 行为 run_batch 7 项零破坏。全量 pytest **3029 passed / 1
  skipped** 零回归。
  **✅ P4b-2c llm 类 run_batch 逐项参数化契约已落地（本 session）**：`__llm_call__(self, any item)`
  可选 item 参（method.spec.param_types 检测）→ assemble/invoke 按需传项；`_RunLLMCallableDrive`
  批量化（每 item 一次 LLM 调用）；run_batch 语义收敛为每 item 一次调用。全量 pytest
  **3030 passed / 1 skipped** 零回归。
  **✅ 交接核验与接手完成**：HANDOFF_SESSION.md 待验证清单全通过（git 干净 / 分支
  unsafe-vibe-dev / 提交序列对齐 / 契约文件 + 判别测试齐备 / 全量 pytest 实跑 3030 passed /
  1 skipped）；交接要点已收敛入本节并删除临时交接文件（git 承载）。
  **✅ P4b-3a `__intent__` 可选协议方法运行时发现已落地**：装配入口经 receive 同源虚表
  发现 `__intent__` → CPS 调用用户方法改写意图三层（存在键替换/缺失键透传/空列表清空层）
  → 合并回 `LLMCallRequest.intents`；契约违约 fail-fast；run_batch 共用装配入口自动继承；
  `__retry__` 装配消费归 P4d（免半接通）、装配上下文按需引入（当前无消费者）。全量
  pytest 3035 passed / 1 skipped 零回归。
  **✅ P4b-3b 流式消费面统一已落地**：`stream_call`/`stream_channel` 统一消费
  LLMCallable——`assemble_stream_request_cps`（行为值语义槽装配 / 用户 llm 类统一装配含
  `__intent__` 改写）+ `_StreamCallableDrive`（帧内 CPS → IbStreamHandle；stream_call
  yield 句柄取完整文本、stream_channel 返回 IbChannel）；字符串形态真删除（3 语言测试
  迁移 + 行为值判别 + 文档同步）；试用 T01/T08 4 case 残留 = P4c 迁移面登记。全量 pytest
  **3036 passed / 1 skipped** 零回归。
  **✅ P4c `llm ... llmend` 语法与旧机制全链路删除 + 全量迁移已落地**：P4c-1 特性地基
  （LLMCallable 实例直接调用 `f(args)` + 静态类型动态 any + `prompt_slots` 键 + `call_args`
  参数化）→ P4c-2a 测试迁移 10 文件（→ llm 可调用类；语义演进：实例渲染 <Instance of T>、
  fn 只收 lambda、`__llmretry__` 迁 `__retry__`/P4d、output_hint 显式声明）→ P4c-2b 内核
  删除（lexer/parser/AST/semantic/runtime/`_LLMFunctionMixin`/provider `user_sys` 槽，净删
  656 行；**保留 `llmexcept`/`retry` 帧机制**）→ P4c-2c 迁移收尾（examples + trials 12 case
  + docs 全面同步：08/05 重写为 llm 可调用类）。全仓 core 残留清零；全量 pytest **3035
  passed / 1 skipped** 零回归。
  **✅ P4d retry 高阶化已落地（决策 5）**：`__retry__` 可选协议方法（`func __retry__(self)
  -> dict`，无参返回 `{"max_retry": int>=1(缺省 3), "hint": str}`）——发现走
  `_discover_optional_protocol_method`（与 `__intent__` P4b-3a 同一虚表通道）+ 契约违约
  fail-fast；装配入口返回三元组 `(request, type_hint, retry_policy)`；invoke 路径有策略时
  驱动**调用级重试循环**（失败轮经 _prompt_assembly 单一消息构造累积 `message_history`
  回喂，max_retry 耗尽交语句层 llmexcept/LLMParseError）；直接调用与 run_batch 自动继承。
  边界裁定：帧机制 = 执行窗口重求值 ⊕ LLM 重试信息装配，高阶化只作用于后者（CPS 状态机
  不进协议）；`__llmretry__` 旧语义由 `hint` 承接；行为默认 retry 帧机制提供（零改动）。
  判别测试 6 项 + docs（08 §8.4 / 10 §10.5）同步；全量 pytest **3047 passed / 1 skipped**
  零回归。
  **✅ P5 prompt 类型类化收尾 + validate_prompt 激活 + required/optional 形式化已落地（G7
  收尾）**：P5a validate_prompt 死条目激活（D2 to_prompt 同构）——`BaseAxiom.has_validate_prompt_cap`
  （默认 False，内置预校验由内建解析器承担）+ validate_prompt 协议条目接 axiom_cap/structural_methods
  + llm_parsing_strategy 消费前置门（satisfies 统一判定，实际分派仍走虚表）。P5b required/optional
  形式化（P1 §2.2）——ProtocolDef 增 optional_methods + all_methods()；methods 保持必需权威
  （判定不变）；llm_callable 正式登记 optional_methods=("__intent__","__retry__")。P5c 评估即收尾
  （prompt 协议族五成员消费面前置门全部协议化）。判别测试 +8；全量 pytest **3055 passed /
  1 skipped** 零回归。
  **✅ P6 per-IbClass 协议方法表最终收尾已落地（决策 1 B）**：据实评估——P6 主体（protocol_vtable
  + receive 前置查表 + 覆层影子条目 + _dispatch_protocol_message 集中落点）已在 P2-② 落地，
  决策 1"一举解决 D3+D5"已达成（satisfies 判定与 receive 分派均以协议条目为单一权威）。剩余面
  = 双表收敛实证锁定 + 接口补齐 + 文档漂移修正（边界清晰、非架构级，不独立分支）：判别测试 +4
  （satisfies↔receive 一致 / 未声明不误分派（消费前置门以 satisfies 为准）/惰性建槽/optional
  不建协议槽）+ TypeAxiom 接口补 has_validate_prompt_cap + docs 三处修正。全量 pytest **3059
  passed / 1 skipped** 零回归。**五大地基主线 P1-P6 全链路完成**。
  **✅ 超大型重构专项审计完成（本 session 末，只检测未修）**：基线 `e8c7944b`..HEAD
  （130 文件 +4592/-1627）。发现技术债清单 A-G（详见会话交接 HANDOFF_SESSION.md §七）：
  **A 注释/文档任务代号污染**（core 12 + tests 19 + docs 6 文件，违注释纪律/docs 治理，
  含本 session P6 新引入的 04_vm_interpreter "P2-②/P6"）；**B 死代码 2 处**
  （`_invoke_llm_callable_cps_boxed` / `_invoke_llm_callable_sync` 零消费者）；
  **C 双实现**（意图三层解析双写真相 `_resolve_llm_callable_intents_cps` vs
  `_prepare_behavior_call_cps` 内联块 + 行为/llm 类双装配入口，与候选 #1 行为统一装配同源）；
  **D overlay_enabled 跨根并发污染风险**（IbClass 级共享态，需设计）；E 半接通边界（登记）；
  F 登记债务核对（无新增）；G 工作过程遗留（临时文档待删）。处置建议顺序 A+B → C → D。
  **当前推进 = 处置已完成，下一 session 开启主线后续**：① 审计清单 A+B ✅ / C ✅ / D ✅
  （本 session 落地，见下）；② 候选 #1 剩余债务评估定论 ✅（has_llm_call_cap 死字段删除 /
  G5 维持登记 / 行为装配评估）；③ 支线（PT-DEBT / VISION-3 / 文档 P9 收尾）。
  **✅ 审计处置 A+B 已落地（本 session，unsafe-vibe-dev `90e66a90`）**：A 注释/文档
  任务代号全仓清理——core 40+ 文件（P#/D#/G#/R#-D#/IT-#/决策 N/阶段 N/EXEC-FOUNDATION/
  DIAGNOSTIC_DESIGN 等去代号留功能说明）+ tests 45 文件 docstring + docs 7 文件 + examples 1
  + trials 18 文件 .ibci 头注释；保留 INV-*/LT-*/IT-* 规范/公理编号（正式引用标识）与
  trials 用例编号（试用地基身份）。**保留标准警示**：不变量编号 `INV-EXCEPT-\*` 等曾被
  subagent 误删过、已回退——遇到同类编号先判性质（任务代号 vs 规范标识）再动。B 死代码删除 `_invoke_llm_callable_cps_boxed` /
  `_invoke_llm_callable_sync`（零消费者）。全量 pytest 3059 passed / 1 skipped 零回归。
  **✅ 审计 C+D 已落地（本 session，unsafe-vibe-dev `ed4502ef`）**：C 意图三层解析双写真相
  收敛——行为路径 `_prepare_behavior_call_cps` 内联副本改为调用共享
  `_resolve_llm_callable_intents_cps`（补 IbIntentContext 校验 fail-fast），双写消除；
  双装配入口评估为值自身差异承载（非双通道）收窄登记。D overlay_enabled 跨根并发污染
  修复——覆层启用状态迁至 RuntimeContext 计数集合（enter_overlay/exit_overlay/
  is_overlay_enabled，嵌套计数成对），分派点经当前执行上下文查询（ContextVar 天然多根
  隔离）；探针实证修复前块外根误命中覆层、修复后隔离；判别测试 +3（tests/runtime/
  test_overlay_concurrency.py）。全量 pytest 3066 passed / 1 skipped（含 +7 判别）零回归。
  **✅ 候选 #1 剩余债务评估定论（本 session，unsafe-vibe-dev `033c9900`）**：
  has_llm_call_cap **实证为死字段**（无协议映射/无访问器/无任何消费者——上 session"编译期
  DDG 层"记录与代码不符，DDG 实际经 IbBehaviorExpr AST 类型识别），已删除（BaseAxiom/
  BehaviorAxiom/TypeAxiom + 03_type_system.md），P4 协议化真收尾；G5 意图值栈全量重构
  维持登记不推进（P3 核心切片已落地、勿半接通）；行为统一装配评估为值自身差异承载。
  全量 pytest 3066 passed / 1 skipped 零回归。
  **当前分支 = `unsafe-vibe-dev`**，HEAD=`a97773a6`（**已 push origin，与 origin 同步**——用户
  显式授权 push 并已执行，含收敛+排布提交；**后续 push 需再获显式授权，授权不自动延续**）、
  main 未动、worktree 干净；全量基线 **3069 passed / 1 skipped**（以实跑为准，接手复跑确认）。
  **✅ 技术债收敛 8 阶段全部完成**：任务控制文档收敛 / 注释代号清理（F# 残留清零含测试层）/
  死代码孤儿清理（inherit_plugins、IbBehaviorInstance）/ 质量红线修复（interpreter 双通道、私有
  穿透）/ PT-DEBT-4 file→fs 全量迁移 / PT-DECIDE-3 项①③ 语义裁定落地（__from_prompt__ 单向契约、
  SEM_PROTOCOL_SIGNATURE required=error）。全量 pytest **3069 passed / 1 skipped** 零回归
  （+3 判别测试）。详见 git 历史与 WORKLOG。
  **✅ 后续任务排布（用户 2026-08-19 指定健康度优先 + 真实 LLM 全面试用纳入）**：四阶段——
  **阶段 A · 代码/架构健康（当前 P0）**：A1 主线架构债务落地（G5 意图值栈全量重构 + 行为值深程
  统一装配入口收敛，先设计→评估→落地勿半接通）/ A2 PT-DEBT-29 生成器让出型消费 / A3 PT-DEBT-30+33
  类型边界闭合 / A4 Tier C 专项审计 / A5 PT-AUDIT-1/3 周期 + Tier B。**阶段 B · 功能稳健/对外能力**
  （PT-TEST-2 覆盖缺口、PT-DECIDE-3 项②④、PT-DOC-3P2 提前 B3、PT-FEAT-5 CI/CD）。**阶段 C ·
  真实 LLM 全面试用重启（VISION-3，阈值=A/B 稳定后；非最高优先但必做）**。**阶段 D · 远期演进**
  （P7 类型理论 / P8 函数式 / 二层 IR）。**排布微调（用户裁定）**：A3/A4 交换；**PT-DECIDE-2 封存**
  （短期不启动，解封条件=多供应商思考模式部署需求）；PT-DOC-3P2 提前至 B3；PT-FEAT-6/12 划远期。
  完整执行依据 = `tasks_docs/_planning_health_first.md`（临时规划文档，执行中逐项收敛进
  NEXT_STEPS/PENDING_TASKS，**已吸收并按治理删除，git 承载历史**）。
  **✅ 会话交接核验接手完成（本 session）**：HANDOFF_SESSION.md 待验证清单全通过（git 干净 /
  分支 unsafe-vibe-dev 与 origin 同步 / main 未动 / 提交序列对齐 / 全量 pytest 实跑 **3069 passed /
  1 skipped** / 契约与下一步已读）；本文件 §2.1/§2.2 收敛更新，临时交接文件已删除（git 承载）。
  **✅ 阶段 A1 主线架构债务落地完成（2026-08-20，unsafe-vibe-dev）**：① **G5 意图值栈全量重构**
  （`08c4b787`）——意图段 eager 求值为一等值列表（`IbIntent.values`，content/segments 双表示收敛
  为协议计算属性；`@-` 按值派生渲染文本匹配；意图消解链同步化收敛去死 CPS 包装；`@- "text"`/
  `@- $x` 解析修复）；② **行为值深程统一装配入口收敛**（`202c6ff3`）——`assemble_llm_call_request_cps`
  单一分派源，run_batch/invoke/stream 值路径收敛 + `_execute_behavior_spec_cps` 共享提交。判别
  +8；全量 pytest **3082 passed / 1 skipped 零回归**（基线 3069）。文档同步（09_intent_system /
  01_intent_system / LDE §1.3/§3.5）。详见 NEXT_STEPS/WORKLOG/git 历史。
  **🔴 PT-DEBT-34 变量语义建模技术债已登记 + 迅速评估定论（2026-08-20，用户裁定）**：用户判定变量
  **引用/拷贝/赋值/传递**值语义建模不显式不合理，为**巨大隐患**（语义地基级），排布置顶阶段 A
  （真实 LLM 全面试用之前）。迅速评估结论：**运行时值语义模型一致完整、非大重构**——复合对象共享
  引用（同 Python）/赋值=引用复制/传参共享引用/copy·deepcopy 内建正确/snapshot·llmexcept 深克隆/
  类静态字段每实例深克隆。"混乱不清晰"集中在**文档契约缺失**（02_variables 无赋值语义、05_functions
  无传参语义、共享引用只在 KNOWN_LIMITS §五、is vs == 无用户文档）+ **文档漂移**（KNOWN_LIMITS §五.2
  建议构造器初始化 vs 代码已每实例深克隆 ib_class.py:413）+ **判别测试缺口**。工作量中等（约 4-6 窗口）；
  修复四步：调研对照 → 文档权威契约 → 判别测试 → 运行时审计+小修（详见 PENDING PT-DEBT-34 / WORKLOG）。
  **✅ PT-DEBT-34 变量语义建模显式化已完成（2026-08-20）**：四步全落地——① 调研对照（与 Python
  完全对齐、运行时一致非大重构）；② 文档权威契约（02_variables §2.8 值语义权威章节 + 05_functions
  §5.10 传参语义 + KNOWN_LIMITS §五.2 漂移修复 + 03_operators/12_builtins is/== 精确化与互引闭环）；
  ③ 判别测试 test_value_semantics.py +11（赋值别名/传引用/不可变原语/is vs ==）；④ 运行时审计唯一
  发现 = 容器 `==` 默认身份比较（list/dict 未定义 `__eq__`，内部一致非缺陷，文档精确化不改行为；
  逐元素 `==` 若用户后续要属独立设计项），无代码小修。全量 3100 passed / 1 skipped 零回归（+17 =
  11 新测试 + 6 meta 按文件参数化）。真实试用（阶段 C）的 PT-DEBT-34 阈值解锁。详见
  PENDING/NEXT_STEPS/WORKLOG。
  **✅ PT-DEBT-29 生成器消费协作化已完成（2026-08-20）**：消除 `IbGenerator.generic_next` 对 Waitable
  的同步阻塞消费——全消费面（for / yield from / next() / to_list / generic_next / seq 内建）改为协作让出。
  机制：CPS 方法（`generic_next_cps`/`to_list_cps`）+ `_GeneratorConsumeDrive`/`_IterableComputeDrive`
  （Waitable+CPSDrivable 复用）+ `_GeneratorExhausted` 哨兵（规避 PEP 479）；判别测试 +6；KNOWN_LIMITS
  §二十四（同步阻塞边界）移除、25-27 重编号 24-26、引用同步。全量 pytest 3112 passed / 1 skipped
  零回归（+12 = 6 新判别 + 6 meta 参数化）。详见 PENDING/NEXT_STEPS/WORKLOG。
  **✅ 会话交接核验接手完成（2026-08-20，unsafe-vibe-dev HEAD=`b2322214` 已 push origin 与同步）**：
  HANDOFF_SESSION.md 待验证清单全通过（git 干净 / main 未动 / 提交序列对齐 / 全量 pytest 实跑
  **3112 passed / 1 skipped** / 契约 §五-§六 + 规划文档已读）；本文件 §2.1/§2.2 收敛更新，临时交接
  文件已删除（git 承载）。**push 授权不延续**：上一 session 已 push（用户显式授权，含上一 session 7
  个未 push 提交一并推送），后续 push 需再获显式授权。**KNOWN_LIMITS 编号已变**：原 §二十四（生成器
  同步阻塞）与 §二十四（`yield from` 序列委托，PT-DEBT-30 已收紧解决）均移除，现 §二十四=用户协议/
  impl、§二十五=LLM 可调用类返回类型。见下完成记录。
  **✅ PT-DEBT-30 + PT-DEBT-33 类型边界闭合完成（2026-08-20，unsafe-vibe-dev）**：① **PT-DEBT-30**
  `yield from` 序列委托编译期生成器/序列区分（`visit_IbYieldFromExpr` 按委托目标收紧：生成器=元素类型
  不变，序列/`__iter__`=None——`int r = yield from [seq]` 编译期 SEM_TYPE_MISMATCH）；② **PT-DEBT-33**
  三子边界——10.1 dict 键编译期校验 / 10.3 中置·前导星偏移修正 / 跨引擎封印优雅回落基类（与内置
  list[int]→list 同构，杜绝 ib_class=None 坏对象；封印不放松，决策见 WORKLOG）。判别测试 +11；
  KNOWN_LIMITS §二十四（序列委托）移除重编号 24-25 + §十.2/§十.3 更新。全量 pytest **3123 passed /
  1 skipped 零回归**。见下 Tier C 完成记录。
  **✅ Tier C 专项审计完成（2026-08-20，unsafe-vibe-dev）**：hasattr 全量分类（113 处：58 合法保留 /
  50 简单异味 / 4 真缺陷 / 4 深层次）+ 用户 6 决策 + 6 阶段全部落地零回归——Phase 1 机械清理
  （恒真/恒假死守卫 ~24 + 双轨残留 unbox 收敛 + 附带死代码）/ Phase 2 真缺陷 fail-fast（intent_context
  merge/combine 对齐 use()、__from_prompt__ 形状违约、binding_analysis 死兜底、serializer mode.value）/
  Phase 3 contract_validator:63 公理契约校验彻底根因修复（get_methods→get_method_specs + 移除死 kind 门，
  校验恢复生效零违约零误报）/ Phase 4 深层次（_helpers 补 isinstance、deep_clone 惰性 isinstance）/
  Phase 6 反序列化宽异常收窄 except PermissionError + KDIAG_RUNTIME_SPECIALIZATION_FALLBACK 诊断。
  判别测试 +10；KNOWN_LIMITS §十 契约不变；**PT-DEBT-35（_ctx 契约形式化）/ PT-DEBT-36（intent_context
  方法族结构重构 + axiom 能力契约校验）登记 PENDING 独立窗口**。全量 pytest **3133 passed /
  1 skipped 零回归**（基线 3123，+10 判别）。下一 session 起点 = **阶段 B（功能稳健/对外能力，当前 P0）**——B1 PT-TEST-2 / B2 PT-DECIDE-3 项②④ / **B3 PT-DEBT-36** / **B4 PT-DEBT-35**（2026-08-20 从推迟移入 B，不再推迟）/ B5 PT-DOC-3P2 / B6 PT-FEAT-5；周期质量维护（PT-AUDIT-1/3 + Tier B）按用户裁定推迟到真实试用（阶段 C）后。
  **✅ B1 PT-TEST-2 覆盖缺口补测完成（本 session，unsafe-vibe-dev `1eaefb12`）**：COVERAGE_MATRIX
  缺口全收敛——新增判别测试 17 项（INV-CAST-2 隐式转换 / INV-INTENT-PRIORITY-2 / INV-INTENT-FLOW-3 /
  INV-MOCK-3 / 模块缓存 / 循环 import / switch 内 return）+ 矩阵卫生（3 处陈旧 TRUE_GAP 收敛：
  INV-INTENT-SCOPE-3 已有 snapshot 冻结测试、INV-LLMEXCEPT-CATCH-4→5 重号、switch break/continue
  已有测试）+ §7 模块重载=设计排除（无热重载机制）。**B6 交付边界（用户 2026-08-20 裁定）**：
  CI/CD = 可靠化设计 + 本地配置（不 push、不启用 GitHub 侧），B6 完成标准=设计+配置就绪，远程
  启用待用户授权。全量 pytest **3156 passed / 1 skipped 零回归**（基线 3133）。
  **✅ B2 PT-DECIDE-3 项②④ 定案落地（本 session，unsafe-vibe-dev `9e326471`）**：② 评估定论 =
  不扩展 `__validate_prompt__` 至内置类型（内建解析器单一权威，扩展即双通道）+ 闭合半接通边缘
  （impl 内置类型定义 `__from_prompt__`/`__validate_prompt__` 编译期 SEM_TYPE_MISMATCH 拒绝）；
  ④ `PromptRenderer.to_prompt_str` AttributeError 静默吞并改 KDIAG_PROTOCOL_TO_PROMPT_FALLBACK
  可观测发射。判别测试 +4；全量 pytest **3160 passed / 1 skipped 零回归**（基线 3156）。
  **✅ B3 PT-DEBT-36 intent_context 方法族重构 + axiom 能力契约校验（本 session，unsafe-vibe-dev
  `6882f5b8`）**：① intent_context 方法族收敛（`_ic_get_ctx`/`_ic_frame` 单一权威，消除 10 处
  恒真死守卫/帧探测簇，缺参 fail-fast）；② `_is_impl_method` 排除元类伪影（修复 `bool | bool`
  误绑 `type.__or__` PEP 604 运算符）；③ `_verify_axiom_bindings` bootstrap 末契约校验（公理
  声明方法必须 vtable/协议分派/字段承载）。判别测试 +13；全量 pytest **3173 passed / 1 skipped
  零回归**（基线 3160）。
  **✅ B4 PT-DEBT-35 `_ctx` 契约单一权威形式化（本 session，unsafe-vibe-dev `a482dcb6`）**：
  `intent_context.get_intent_ctx`/`set_intent_ctx` 单一权威访问（isinstance 精确判别），全仓
  ~10 处 `_ctx` 字段探测双轨收敛（`_helpers`/use/merge/combine/get_current/序列化 collect+
  rehydrate）；判别测试 +9（fake `_ctx` 不误激活/round-trip/非对象 None/clear）；全量 pytest
  **3182 passed / 1 skipped 零回归**（基线 3173）。
  **✅ B5 PT-DOC-3P2 how-to 读者旅程补齐（本 session，unsafe-vibe-dev `00eaf873`）**：新增
  `use_isolation.md`（ihost 隔离）+ `orchestrate_llm_calls.md`（LLM 编排）2 篇操作指南 +
  交叉引用接线（debug→orchestrate、guide 03→orchestrate、syntax 11→use_isolation、README
  目录树）；纯文档变更。
  **✅ B6 PT-FEAT-5 CI/CD 可靠化设计 + 本地配置（本 session，unsafe-vibe-dev `46c5a18e`）**：
  四层可靠性设计（L1 fast/L2 全量跨平台/L3 真实 LLM 手动/L4 发布产物）+ ci.yml 分层就绪
  （保持 workflow_dispatch）+ `scripts/ci_local.sh` 本地分层复现；**远程启用待用户显式授权**
  （恢复 push/PR 触发并 push）。设计文档 `tasks_docs/_code_cicd.md`（已按治理删除，git 承载）。
  本地全量 pytest **3182
  passed / 1 skipped 零回归** + L1 909/1 + wheel 构建验证。
  **✅ 阶段 B（B1-B6）全部完成（2026-08-20）**：测试补测（PT-TEST-2）/ 协议定案（PT-DECIDE-3
  项②④）/ 技术债收敛（PT-DEBT-36/35）/ 文档补齐（PT-DOC-3P2）/ CI 设计（PT-FEAT-5，远程启用
  待授权）全部落地。当前 P0 前移 **阶段 C · 真实 LLM 全面试用重启（VISION-3）**——对五大地基
  重构后全部新特性重试用（llm 可调用类/stream/run_batch/覆层/prompt 协议族五成员/意图一等值/
  fs/Optional 等），真实 qwen3.6 非思考模式全量回归 + 压力维度扩展。

### 2.2 交接检查单（当前有效）

- [x] **✅ 发布准备线收官（本 session，2026-09-02，用户裁定）**：R4 重新定性并彻底删除
  （两遗留 IBCI 源文件全仓零消费者）+ `ci_local.sh` L4 发布产物层补齐 + 分支基准 =
  unsafe-vibe-dev（main 上 2 笔非核心提交 fast-forward 并入，push 已执行）+ 本机暂不跑
  真实 LLM（L3 / 阶段 C 真实 LLM 线搁置待 LLM 环境）+ NEXT_STEPS/WORKLOG/HANDOFF 同步；
  全量 pytest 实跑零回归确认安全
- [x] **✅ 阶段 C 收尾·临时文档收敛清理 + unsafe-vibe-dev→main 合并重建（2026-08-21 用户指示）**：
  临时文档 `_code_cicd`/`_planning_health_first`/`_trial_edge_catalog`/`_phaseC_trials` 已删
  （git 承载）；未完成项并入 NEXT_STEPS（文档复核登记项）+ trials/INDEX（恶意边界后续未测项 9 项）
  + PENDING_TASKS（PT-FEAT-5 远程启用待授权）；全量 pytest 实跑零回归确认安全；unsafe-vibe-dev
  快进合并入 main、分支删除重建，本地 + GitHub（origin/main 更新、远端 unsafe-vibe-dev 删除重建）
  同步完成
- [x] **✅ 会话交接核验接手完成（2026-08-21）**：git 干净 / 提交序列对齐 / 全量 pytest 实跑
  3182 passed / 1 skipped / push 获用户显式授权并执行（28 提交推送 origin 同步）；阶段 B
  （B1-B6）全部完成；当前 P0 = **阶段 C（VISION-3 真实 LLM 全面试用重启）**
- [x] **✅ B6 PT-FEAT-5 CI/CD 可靠化设计 + 本地配置（unsafe-vibe-dev `46c5a18e`）**：四层可靠性
  设计 + ci.yml 分层就绪（保持 workflow_dispatch）+ scripts/ci_local.sh 本地分层复现；远程启用
  待用户显式授权；本地全量 3182 零回归 + L1 909/1 + wheel 构建验证。**阶段 B（B1-B6）全部完成，
  当前 P0 前移阶段 C（VISION-3 真实 LLM 全面试用重启）**
- [x] **✅ B5 PT-DOC-3P2 how-to 读者旅程补齐（unsafe-vibe-dev `00eaf873`）**：新增 use_isolation
  + orchestrate_llm_calls 2 篇操作指南 + 交叉引用接线；纯文档变更；下一项 = B6 PT-FEAT-5
- [x] **✅ B4 PT-DEBT-35 `_ctx` 契约单一权威形式化（unsafe-vibe-dev `a482dcb6`）**：get_intent_ctx/
  set_intent_ctx 单一权威（isinstance 精确判别），全仓 _ctx 字段探测双轨收敛；判别 +9；全量
  pytest 3182 passed / 1 skipped 零回归；下一项 = B5 PT-DOC-3P2
- [x] **✅ B3 PT-DEBT-36 intent_context 方法族重构 + axiom 能力契约校验（unsafe-vibe-dev `6882f5b8`）**：
  方法族收敛（_ic_get_ctx/_ic_frame 单一权威，消除 10 处恒真死守卫/帧探测簇，缺参 fail-fast）+
  _is_impl_method 排除元类伪影（修复 bool|bool 误绑 type.__or__）+ _verify_axiom_bindings 契约校验；
  判别 +13；全量 pytest 3173 passed / 1 skipped 零回归；下一项 = B4 PT-DEBT-35
- [x] **✅ B2 PT-DECIDE-3 项②④ 定案落地（unsafe-vibe-dev `9e326471`）**：② 不扩展 validate_prompt
  至内置（内建解析器单一权威）+ impl 内置类型定义 __from_prompt__/__validate_prompt__ 编译期拒绝
  （闭合半接通）；④ to_prompt_str AttributeError 静默吞并改 KDIAG 可观测发射；判别 +4；全量
  pytest 3160 passed / 1 skipped 零回归；下一项 = B3 PT-DEBT-36
- [x] **✅ B1 PT-TEST-2 覆盖缺口补测完成（unsafe-vibe-dev `1eaefb12`）**：COVERAGE_MATRIX 缺口全收敛
  （新增判别测试 17 项：INV-CAST-2 隐式转换 / INV-INTENT-PRIORITY-2 / INV-INTENT-FLOW-3 / INV-MOCK-3 /
  模块缓存 / 循环 import / switch 内 return + 矩阵卫生 3 处陈旧 TRUE_GAP + §7 模块重载=设计排除）；
  全量 pytest 3156 passed / 1 skipped 零回归；下一项 = B2 PT-DECIDE-3 项②④；**B6 交付边界已定
  （可靠化设计+本地配置，不 push，远程启用待授权）**
- [x] **✅ Tier C 专项审计完成（本 session，unsafe-vibe-dev）**：hasattr 全量分类
  （113 处：58 合法/50 简单异味/4 真缺陷/4 深层次）+ 6 决策 + 6 阶段零回归（机械清理/
  真缺陷 fail-fast/contract_validator 恢复校验/深层次 isinstance/反序列化宽异常+KDIAG）；
  判别 +10；全量 pytest 3133 passed / 1 skipped 零回归；PT-DEBT-35/36 登记独立窗口。
  下一 session 起点 = 阶段 B（B1-B6 含 PT-DEBT-36/35 移入）；周期质量维护推迟到真实试用后
- [x] **✅ PT-DEBT-30 + PT-DEBT-33 类型边界闭合完成（本 session，unsafe-vibe-dev）**：yield from
  序列委托编译期收紧 + dict 键校验 + 中置·前导星偏移修正 + 跨引擎封印优雅回落基类；判别测试 +11；
  全量 pytest 3123 passed / 1 skipped 零回归；KNOWN_LIMITS 编号更新（二十四=用户协议/impl、
  二十五=LLM 可调用类）。下一 session 起点 = 阶段 A P0（Tier C 专项审计）
- [x] **✅ 会话交接核验接手完成（HEAD=`b2322214`，unsafe-vibe-dev 与 origin 同步（已 push））**：HANDOFF_SESSION.md 待验证清单全通过（git 干净 / main 未动 / 提交序列对齐 / 全量 pytest 实跑 3112 passed / 1 skipped / 契约 §五-§六 + 规划文档已读）；要点已收敛入 §2.1（含 PT-DEBT-34/29 完成、push 授权不延续、KNOWN_LIMITS 编号变更），临时交接文件已删除（git 承载）；下一 session 起点 = 阶段 A P0（PT-DEBT-30 + PT-DEBT-33 类型边界闭合）
- [x] **✅ 会话交接核验接手完成（HEAD=dcb7c4f2，unsafe-vibe-dev 领先 origin 7 未 push）**：HANDOFF_SESSION.md 待验证清单全通过（git 干净 / main 未动 / 提交序列对齐 / 全量 pytest 实跑 3083 passed / 1 skipped / 契约 §五-§六 + 规划文档已读）；要点已收敛入 §2.1（含 A1 完成、PT-DEBT-34 登记与迅速评估、push 授权不延续契约），临时交接文件已删除（git 承载）；下一 session 起点 = 阶段 A P0（PT-DEBT-34 变量语义建模显式化）
- [x] **✅ 会话交接核验接手完成（HEAD=a97773a6）**：HANDOFF_SESSION.md 待验证清单全通过（git 干净 / unsafe-vibe-dev 与 origin 同步（已 push）/ main 未动 / 提交序列对齐 / 全量 pytest 实跑 3069 passed / 1 skipped / 契约 §五-§六 + 规划文档已读）；要点已收敛入 §2.1（含 push 授权不延续契约与四阶段排布），临时交接文件已删除（git 承载）；下一 session 起点 = 阶段 A P0（A1）
- [x] **✅ 会话交接核验接手完成**：HANDOFF_SESSION.md 待验证清单全通过（git 干净 / 分支 unsafe-vibe-dev / main 未动 / 提交序列对齐 / 全量 pytest 实跑 3066 passed / 1 skipped）；契约要点已并入 §2.1（含 INV-EXCEPT-* 保留标准警示），临时交接文件已删除（git 承载）
- [x] **✅ 技术债收敛 8 阶段全部完成**：任务控制文档收敛 / 注释代号清理（F# 清零含测试层）/ 死代码孤儿清理（inherit_plugins、IbBehaviorInstance）/ 质量红线修复（interpreter 双通道、私有穿透）/ PT-DEBT-4 file→fs / PT-DECIDE-3 项①③ 语义裁定落地；全量 pytest 3069 零回归（+3 判别）；详见 git 历史
- [x] **✅ 审计 A+B 处置落地（`90e66a90`）**：注释/文档任务代号全仓清理（core+tests+docs+examples+trials）+ 死代码删除 `_invoke_llm_callable_cps_boxed`/`_sync`；保留 INV/LT/IT 规范编号与 trials 用例编号；全量 3059 零回归
- [x] **✅ 审计 C+D 处置落地（`ed4502ef`）**：C 意图三层解析双写收敛（行为路径调共享 `_resolve_llm_callable_intents_cps`）+ 双装配入口评估（值差异承载收窄登记）；D overlay 覆层启用状态迁 RuntimeContext（跨根并发隔离）+ 判别 +3；全量 3066 零回归
- [x] **✅ 候选 #1 剩余债务评估定论（`033c9900`）**：has_llm_call_cap 实证死字段删除（P4 真收尾）；G5 意图值栈维持登记不推进；行为装配评估值差异承载；全量 3066 零回归
- [x] **✅ 交接核验接收完成**：HANDOFF_SESSION.md 待验证清单全通过（git 干净 / 分支 unsafe-vibe-dev / main 未动 / 提交序列对齐 / 契约文件 + 判别测试齐备 / 全量 pytest 实跑 3030 passed / 1 skipped）；要点已收敛入 §二，临时交接文件已删除（git 承载）
- [x] **✅ P4b-3a `__intent__` 可选协议方法运行时发现落地**：装配入口发现 + CPS 调用 + 三层合并（存在键替换/缺失键透传/空列表清空）+ 契约 fail-fast + run_batch 继承；判别测试 +5；行为零变化；全量 3035 零回归
- [x] **✅ P4b-3b 流式消费面统一落地**：stream_call/stream_channel 统一消费 LLMCallable（_StreamCallableDrive 帧内 CPS + assemble_stream_request_cps 两路装配）；字符串形态真删除 + 3 语言测试迁移 + 行为值判别 + docs 同步；全量 3036 零回归
- [x] **✅ P4c 语法/旧机制全链路删除 + 全量迁移落地**：P4c-1 特性地基（实例直接调用 + prompt_slots + call_args）/ P4c-2a 测试迁移 10 文件 / P4c-2b 内核删除（净删 656 行，保留 llmexcept/retry 帧机制）/ P4c-2c examples + trials 12 + docs 全面同步；全仓 core 残留清零；全量 3035 零回归；下一步 = P4d retry 高阶化
- [x] **✅ P4d retry 高阶化落地**：`__retry__` 协议（`func __retry__(self) -> dict`：max_retry/hint；发现走 `_discover_optional_protocol_method` 同 `__intent__` 通道 + 违约 fail-fast）+ 装配三元组 + invoke 调用级重试循环（_prompt_assembly 单一消息构造累积 message_history 回喂，耗尽交语句层）+ 直接调用/run_batch 继承；边界裁定（帧机制=CPS 窗口重求值 ⊕ 信息装配，高阶化只作用于后者）；判别测试 6 项 + docs 同步；全量 3047 零回归
- [x] **✅ P5 prompt 类型类化收尾落地**：P5a validate_prompt 激活（BaseAxiom.has_validate_prompt_cap + 协议条目 axiom_cap/structural_methods + 消费前置门，D2 to_prompt 同构）/ P5b required/optional 形式化（ProtocolDef.optional_methods + all_methods()，llm_callable 登记 __intent__/__retry__）/ P5c 评估即收尾（prompt 协议族五成员消费面全协议化）；判别测试 +8；全量 3055 零回归
- [x] **✅ P6 per-IbClass 协议方法表最终收尾落地**：据实评估（P6 主体 P2-② 已落地，D3+D5 已达成——判定/分派以协议条目单一权威；剩余面边界清晰不独立分支）+ 判别测试 +4（satisfies↔receive 一致/未声明不误分派/惰性建槽/optional 不建协议槽）+ TypeAxiom 接口补 has_validate_prompt_cap + docs 三处修正（03 §4.0/§4.1 + 04 §2）；全量 3059 零回归；**五大地基 P1-P6 全链路完成**
- [x] **✅ 超大型重构专项审计完成（只检测未修）**：技术债清单 A-G——A 注释/文档代号污染（core 12 + tests 19 + docs 6，违注释纪律/docs 治理）/ B 死代码 2 处（_invoke_llm_callable_cps_boxed/_sync 零消费者）/ C 双实现（意图三层解析双写真相 + 行为双装配入口，与候选 #1 同源）/ D overlay_enabled 跨根并发污染 / E 半接通边界（登记）/ F 登记债务核对 / G 临时文档待删；处置建议 A+B 机械批 → C 评估 → D 独立窗口；详见 HANDOFF_SESSION.md §七
- [x] **读 `tasks_docs/ROADMAP_NATIVE_BINDING.md`（已完成主干任务总路线图，已随 F0-F5 完成删除，git 承载）**
- [x] **读 `tasks_docs/HANDOFF_SESSION.md`（本 session 会话交接：提交序列/待验证清单/继续路线/契约，接手后并入 §二 并删除）**
- [x] 读 `NEXT_STEPS.md`（当前状态 + ⛔ 工作模式定论 + 下一步候选）
- [x] 读 `PENDING_TASKS.md`（远期任务正式清单：FEAT/DEBT/AUDIT/DOC/TEST/DECIDE/SEALED/愿景）
- [x] 读 `GOVERNANCE.md`（任务控制治理章程：文档职责/书写模板/生命周期/红线）
- [x] 读 `WORKLOG.md`（关键裁定与长期约束）
- [x] 试用体系：`trials/_toolkit/`（run_batch/run_one/CLASSIFICATION/LLM_SERVICE）+ `trials/INDEX.md`
- [x] 测试基线：`~/miniconda3/envs/ibci/bin/python -m pytest tests/`（以实跑为准，不冻结数字）
- [x] 全程本地 commit、禁 push（除非用户显式授权）
- [x] **当前分支 = `unsafe-vibe-dev`**（P2/P6 地基已合并并删除实验分支；`main` 不触碰；本地领先 origin 未 push）
- [x] **P2/P6 地基低风险合并 unsafe-vibe-dev 完成**（用户确认零风险 → 纯 fast-forward `e8c7944b..b7479497` → exp 分支合并即删；全量 pytest 2997 零回归）
- [x] 当前基线实跑：`~/miniconda3/envs/ibci/bin/python -m pytest tests/`（以实跑为准，本 session：3030 passed / 1 skipped）
- [x] **✅ 复核并提交工作树内 P2-② 覆层机制未提交增量完成**：`git diff` 复核（含端到端实证）→ 全量 pytest 实跑 2997 零回归 → 描述性 commit → 删除临时文档 `tasks_docs/_code_overlay.md` 与 `tasks_docs/_code_protocol_vtable.md`（git 承载）→ 同步 WORKLOG/NEXT_STEPS/HANDOFF/检查单
- [x] **✅ P3 D8 snapshot 意图冻结补齐落地**：意图 fork 按 capture_mode 统一 + IbFnCallable.captured_intents + _vm_call_fn_callable 意图生命周期（IT-2/IT-3/IT-4）+ 判别测试 + 死字段清理；全量 3011 零回归
- [x] **✅ P3 G5/G2 意图一等值切片·可调用值有意契约嵌入落地**：函数/可调用/行为值渲染契约（func <name>(<params>)-><ret> / signature_name），去 Python repr；判别测试 + 既有断言语义演进；全量 3019 零回归
- [x] **✅ P4a LLMCallable 协议地基落地**：llm_callable 协议注册（__llm_call__ 必需方法 = 能否被 LLM 消费唯一判定）+ 判别测试；全量 3020 零回归
- [x] **✅ P4b 装配路径设计定稿**：装配上下文 IbLLMCallAssemblyCtx（IBCI 一等对象）+ __llm_call__ 契约 + 统一装配入口（CPS）+ 落地顺序，设计文档 _code_p4b_assembly.md（临时）
- [x] **✅ P4b-2a LLMCallable 统一装配路径实现落地**：_LLMCallableMixin（协议门 → __llm_call__ 装配 dict→LLMCallRequest → 统一 worker）+ 用户 llm 类端到端判别 + fail-fast；全量 3028 零回归
- [x] **✅ P4b-2b run_batch 统一消费 LLMCallable 实例落地**：run_batch 接受 llm 实例（_RunLLMCallableDrive 经统一装配，行为保留）+ 首参型宽化 any；全量 3029 零回归
- [x] **✅ P4b-2c llm 类 run_batch 逐项参数化落地**：__llm_call__(self, any item) 可选 item 参 + run_batch 批量化（每 item 一次调用）；全量 3030 零回归；下一步 = P4b-3（__intent__/__retry__ 可选协议方法发现）

---

## 附、书写模式（本文档专用模板，书写必须参照）

> 本节是本文档书写的**唯一权威模板**（模板归属 = 文档自身；`GOVERNANCE.md`
> §三 仅做索引）。更新本文档一律按下列结构与格式书写。

### 1. 文档结构

```
# HANDOFF — 常驻交接与固定化内容库
定位段（持久保留说明 + 使用方式 + 维护规则 + 书写要求）
一、固定化内容（长期不变）
  1.1 工作流程（指针，AGENTS.md 为权威源）
  1.2 关键用户裁定与工作原则（表格）
  1.2.1 goal 配置习惯
  1.3 goal objective 模板
  1.4 tasks_docs/ 文档结构指针（表格）
二、动态状态（随任务更新）
  2.1 当前工程状态 / 下一阶段
  2.2 交接检查单（当前有效）
```

### 2. 分区规则

| 区 | 维护规则 |
|----|----------|
| §一 固定化内容 | **长期不变**；仅新增用户裁定时补充；不复制 AGENTS.md 正文（单点真理，只放指针与模板） |
| §二 动态状态 | **随任务更新**：只保留当前任务/下一阶段状态；任务完成即移除（git 承载）；待用户确认项标注 ⏳ 并给出登记位置 |
| 检查单 | 随任务状态增删勾选项，保持与当前任务一致 |

### 3. 条目格式

- 状态条目：`- **<状态标记>**：<当前状态>——<内容摘要>。`
- 状态标记：🔴 当前任务 / ⏳ 待用户确认 / ❌ 阻塞（**不登记已完成记录**——git 承载）。
- 指针一律用仓库相对路径，不复制被指文档正文。

### 4. 维护规则

- **不因任务完成删除本文件**（常驻文档）；git 承载历史版本。
- 新增用户裁定时：先入 WORKLOG（长期约束力）或本节 §1.2（工作原则），不重复登记。
