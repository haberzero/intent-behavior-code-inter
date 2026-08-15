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

---

## 一、固定化内容（长期不变）

### 1.1 工作流程（AGENTS.md 为权威源，此处只列指针）

- **自主工作循环**：理解 → 设计质询 → 自主决策 → 实现 → 自反馈验证 → 自主纠错 → 交付自查 → 收尾。
- **上报阈值**：穷尽自主手段仍无法决定才上报；破坏性重构默认已授权；分支政策见 AGENTS.md。
- **交付纪律**：全程本地 commit；**禁止 push**（硬原则，除非用户显式授权）。
- **工作日志**：自主决策/方案取舍/变化前后记录于 `WORKLOG.md`（"只记录，不断决"）。
- **测试**：`conda activate ibci && python -m pytest tests/`（唯一命令）。
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
| 破坏性重构授权 / 分支政策 / 禁 push | 见 AGENTS.md（权威源）。**分支合并细则（2026-08-11）**：零风险/边界清晰改进（全量 pytest 零回归 + 复核放行）可**直接合并** unsafe-vibe-dev；大风险/无法确认边界仍走独立分支 + 手动 cherry-pick；判定以"是否确认零风险"为准 |

### 1.2.1 goal 配置习惯（每个 session 新配置 goal 时自动采用，2026-08-09 用户定案）

> 创建 goal（`create_goal` / `set_goal`）时按此默认参数，除非用户在本 session 显式覆盖：
>
> | 参数 | 值 | 说明 |
> |------|----|------|
> | `max_duration_seconds` | **14400（4 小时）** | 最晚结束时间 = 当前时刻 + 4h |
> | `max_auto_turns` | **10** | 允许 goal 自动续跑次数 |
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
  2026-08-11 补充"零风险直接合并"细则）：无法确认边界/危害程度的破坏性重构 100% 授权在其
  独立分支实验，独立分支禁止直接合并到 unsafe-vibe-dev 或 main，确认技术路线后仅允许手动
  单独更新 unsafe-vibe-dev；永远不允许触碰主干分支（main）。**零风险细则**：经充分验证零风险/
  边界清晰的改进（全量 pytest 零回归 + 复核放行，无对外契约/架构级风险）允许**直接合并**到
  unsafe-vibe-dev；识别到大风险/无法确认边界的破坏性重构仍走"独立分支 + 手动 cherry-pick 单独
  更新 unsafe-vibe-dev"。判定以"是否确认零风险"为准，非以改动规模。工作日志：所有自主决策/
  方案取舍/变化前后必须详尽记录于 WORKLOG，"只记录，不断决"。

四、工作流：每任务走 code-workflow Phase 0-5 + 质量门 + design-philosophy 对照 + self-grill
自我质询 + code-odor 自查 + 全量 pytest 零回归（python -m pytest tests/）。批量后 code-review
残留扫描。

五、主任务阻塞/暂停时的支线（按优先级，解阻立即回主线）：1) 质量维护/代码健康
（quality-maintenance Tier A/B）；2) PT-AUDIT-1/2 代码质量审计（独立分支）；
3) PT-FEAT-5 错误用户友好化 / PT-FEAT-2 Enum 非 str 成员；
4) 测试体系重构（PT-TEST-1）。每条支线仍须全量 pytest 零回归、commit+留痕（仅本地）。

六、停止条件：先穷尽自主手段，仅当确实无法自主决定时（用户意图不明穷尽无解/公理层语义
错误集确需用户裁决/与工作模式定论冲突/破坏性重构无法确认边界且独立隔离分支也无法确定
技术路线）才 update_goal(status="unmet", blocker=具体卡点+建议)。

七、非目标：media Phase 4（PT-SEALED-1）、跨进程/CPU 并行、跨引擎通信、线程无损挂起/恢复、用户级泛型类（PT-FEAT-3）、Hindley-Milner 约束求解。`yield` 惰性生成器（PT-FEAT-1）是阶段 5 下一主线，非"非目标"；是否纳入本 goal 视主任务界定。
```

### 1.4 tasks_docs/ 文档结构指针

| 文档 | 用途 |
|------|------|
| `NEXT_STEPS.md` | 当前最紧要项 / 已完成摘要 / 工作模式定论 / 工作规则 |
| `PENDING_TASKS.md` | 长期规划与搁置任务（任务代号按性质分域：PT-FEAT/PT-DEBT/PT-AUDIT/PT-DOC/PT-TEST/PT-DECIDE/PT-SEALED） |
| `HANDOFF.md` | 本文件：固定化内容 + 动态状态 |
| `WORKLOG.md` | 自主工作日志（关键裁定；设计决策收敛于 `PENDING_TASKS.md`） |
| `trials/` | 试用地基（T01-T07）与工具链 `trials/_toolkit/`（harness / batch / 用例即契约 / LLM_SERVICE）——测试资产，非任务控制文档 |

---

## 二、动态状态（随任务更新）

> 本部分随任务推进由各 session 更新，**不因任务完成删除**。

### 2.1 当前任务 / 下一阶段

> **接手起点**：先读本节 + `tasks_docs/NEXT_STEPS.md`（当前最紧要）+
> `tasks_docs/PENDING_TASKS.md` §〇（优先级总表）+ `tasks_docs/WORKLOG.md`（近期工作日志）
> + git 历史 `80783c8..HEAD`。

- **🔴 当前主线（2026-08-15 用户指定，下一 session 接手执行）：IBCI LLM 全能力真实压力试用（本地 qwen）**。
  **目标**：真实调用本地 qwen 模型，系统检查 IBCI 承诺的所有直接/间接 LLM 能力，
  验证“LLM 是语言第一成员”是否名副其实；发现缺陷自主修复（可破坏性重构，按
  AGENTS/HANDOFF 原则），全量 pytest 零回归 + 交接。
  **环境**：本机 LM Studio `qwen3.6-35b-a3b` @ `http://127.0.0.1:1234/v1`；
  当前服务可用，思考已禁用（响应约 1-2s）。真实配置见
  `trials/T01_llm_full/api_config.json`；运行入口 `trials/_toolkit/run_batch.py` /
  `run_one.py`（先探测服务再跑 LLM 批）。
  **已有基线**：全量 pytest 2789 passed / 1 skipped；真实 LLM 扫描 T01 57
  （54 PASS + 2 GUARD + 1 LLM_BEHAVIOR）、T02 3 PASS、T05 cases_D3 8 PASS、
  T06 7 PASS、T07 7 PASS。
  **压力维度（下一 session 按此展开）**：
  1. 内联行为表达式：赋值/条件/循环/表达式语句/dispatch-before-use/run_batch 并发。
  2. 输出类型解析：int/float/bool/str/list/dict/enum/跨模块用户类；`__from_prompt__`/
     `__validate_prompt__`/`__outputhint_prompt__`/`__to_prompt__` 协议全链路。
  3. 意图系统：`@`/`@!`/`@+`/global intents/`mask`/意图上下文；意图与类型输出约束
     优先级；run_batch 意图注入。
  4. 命名 LLM 函数：`__sys__`/`__user__`/`__llmretry__`/参数插值/返回类型/函数值。
  5. 重试与自愈：llmexcept/llmretry/自动错误回喂（多轮对话形态）/快照隔离/耗尽。
  6. 批量、流式与模型路由：`ai.run_batch`/`stream_call`/`stream_channel`/
     `ai.register_model` + `@NAME~`/`ai.probe_model`。
  7. 配置与观测：`ai.set_config`/`load_project_config`/`get_current_call_info`/
     类型提示注册；配置错误/服务不可达/provider 失败路径。
  8. 间接相关：LLM 与 thread/chan/generator/文件容器交互；多模块/插件项目中的
     LLM 调用；长 prompt/非确定性/超时边界。
  9. 多模态：media Phase 4 封存，仅核验 `__payload_prompt__` 协议在当前边界内行为。
  **运行方式**：优先 `trials/` 已有套件，缺口新写用例到 `trials/T08_llm_pressure/`
  （新增套件需更新 `trials/INDEX.md`）；mock 对照 + 真实 qwen 主跑。
  **交接纪律**：本地 commit、禁 push；发现与修复写入 WORKLOG；状态同步
  NEXT_STEPS/PENDING_TASKS/HANDOFF。

- **✅ 已完成（2026-08-15，exp/llm-prompt-mechanism → unsafe-vibe-dev，全量 2787 passed / 1 skipped 零回归）：
  IBCI LLM 调用机制改进（T5 枚举解析失败暴露）A-D 四项落地**。A 枚举输出约束注入
  module 感知修复；B 程序化调用纪律；C 期望输出类型注入；D retry 自动错误回喂。
  真实 LLM T02 T3/T4/T5 三连 PASS。详见 `_code_llm_prompt_mechanism.md` +
  WORKLOG + PENDING_TASKS §〇。

- **✅ 已完成（2026-08-14，完整 IBCI 真实代码试用核查）**：T01-T07 全量重跑，近期改动
  （断层根治 + fn/callable 方向 A + CALLABLE_SIG 根治）对已知试用代码零回归；更新 4 例
  过期触发用例 expect-class→PASS（核销）；记录 T02 T5 真实 LLM 间歇失败。报告
  `trials/VERIFICATION_20260814.md`。

- **✅ 已完成（2026-08-14，exp/callable-sig-signature → unsafe-vibe-dev 合并，全量 2775 passed / 1 skipped 零回归）**：
  **fn[(...)->...]（CALLABLE_SIG）签名模型根治**。KNOWN_LIMITS §10.4"潜伏边界"深挖
  推翻为真实类型安全漏洞（匹配双通道只查数量+返回 / 嵌套类型参数不替换致检查静默
  跳过），根治（结构化构造/重建 + 统一匹配逐参数检查 + 延后规则），判别性回归 +12，
  两轮独立复核 P1 已整改。已知残留：`list[fn]` 容器元素级强制可调用未接线。
  **下一主线候选**：见 `NEXT_STEPS.md`。

- **✅ 已完成（2026-08-14，exp/fn-callable-redesign → unsafe-vibe-dev 合并，全量 2765 passed / 1 skipped 零回归）**：
  **fn/callable 关键字体系重构（方向 A）**。用户 2026-08-14 拍板：移除用户面
  `callable` 类型注解（内部化为运行期基类名/公理族根/thread 参数名），`fn` 参数/返回
  收紧为"任意可调用（强制）"。彻查 `_DESIGN_FN_CALLABLE.md`；判别性回归 +19；独立
  复核（general agent）P1/P2 已整改。已知残留 `list[fn]` 容器元素级强制可调用未接线。
  **下一主线候选**：见 `NEXT_STEPS.md`。

- **✅ 已完成（2026-08-14，exp/func-callable-identity → unsafe-vibe-dev 合并，全量 2746 passed / 1 skipped 零回归）**：
  **函数/可调用类型身份架构断层根治**（用户 2026-08-14 提升优先级的 P0 主线）。
  用户猜想"fn 设计早于泛型体系存在历史包袱"证实且深挖为**三层系统性断层**（spec→TypeRef
  无单一权威 / type_checking 字符串回填覆盖结构化 spec / 函数签名序列化缺口）。五项根治
  （from_spec 补三 kind + create_func 结构化升级 + resolve_member BOUND_METHOD +
  返回 Optional 包装 + 序列化签名保真），判别性回归 +29，独立复核（general agent）放行
  （P1/P2 已整改）。设计/实施 `（已清理任务文档）`；潜伏边界
  KNOWN_LIMITS §10.4。**下一主线候选**：见 `NEXT_STEPS.md`（当前无未决 P0）。

- **✅ 已完成（2026-08-14 无人值守 session，unsafe-vibe-dev 19920d39，全量 2714 passed / 1 skipped 零回归）**：
  **DOC-29 + BOUNDARY-NESTED-FUNC-1 两项根因修复**（E 批判批次发现的架构级修复）。
  **BOUNDARY-NESTED-FUNC-1（架构级，深度分析修正定性）**——真实根因=编译期 `visit_IbReturn`
  返回类型兼容校验整体缺失（`-> fn_callable[int]: return inner` 编译期放行、运行期
  RUN_TYPE_MISMATCH；实测 `-> int: return "abc"` 亦放行，非"嵌套函数类型身份"）。修复：
  `visit_IbReturn` 对非动态可调用返回类型（FUNCTION/BOUND_METHOD/CALLABLE_SIG/
  CALLABLE_INSTANCE）补 is_assignable 校验，与直接赋值路径语义对齐（fn_callable 槽只
  接受 lambda/behavior 实例；`-> fn` 动态哨兵跳过；普通类型返回保持宽松）。判别性回归
  +13（test_return_type_validation.py）。**DOC-29**——空 Optional 操作（for 迭代/unwrap）
  补 error_code=RUN_ATTRIBUTE_ERROR，三处发射点收敛 + 文档 arch/03 §8 一致。判别性回归
  +4（TestOptionalEmptyErrorCode）。E1/E2/E3 触发用例全部核销转 PASS（E3 语义改进：运行时
  RUN_TYPE_MISMATCH → 编译期 SEM_TYPE_MISMATCH，fail-fast 提前）。设计 `_code_return_type_check.md`。
  详见 PENDING_TASKS 两行 + WORKLOG + REGISTER §八bis。

- **✅ 已完成（2026-08-14 第二 session 复核，未改内核，全量 2693 passed / 1 skipped）**：
  **push github + 试用套件复核 T07 三项 P1 修复有效性 + 零退化确认 + E 批判补充批次**。
  push 已执行（124 commits → origin/unsafe-vibe-dev）。T07 全量 43 例重跑 + 旧套件
  T01-T06 238 例重跑**零回归**（三项修复有效、无内核退化；触发用例 D2-09/D2-10/D1-13
  全核销 PASS）。E 批判批次 8 例（`trials/T07_fixes_critical_stress/cases/E1-E8`）：
  5 PASS + 1 BOUNDARY + 2 DOC_ISSUE——**新登记 DOC-29**（空 Optional 迭代/`unwrap()`
  抛 RUN_GENERIC_ERROR vs arch/03 §8 承诺 RUN_ATTRIBUTE_ERROR，iterable.py:39 /
  optional.py:90 未指定 error_code；base 同现=pre-existing，修复②已改进为有码但码与
  文档承诺不符）与 **BOUNDARY-NESTED-FUNC-1**（函数返回嵌套函数赋 `fn_callable[T]`
  RUN_TYPE_MISMATCH，base 同现，与修复①的 rehydrator kind 保真无关）。详见
  REGISTER §八 E 批次 + PENDING_TASKS + trials/INDEX。

- **✅ 已完成（2026-08-14，unsafe-vibe-dev，全量 2693 passed / 1 skipped 零回归）**：
  **T07 三项 P1 修复 + DOC-24~28 文档同步**（承接 `_HANDOFF_T07_FINDINGS.md`，已标完成）。
  ① **OPTIONAL-SCOPE-1**（函数作用域局部变量声明类型编译期丢失的系统性根治：prescan
  解析注解 + type_checking 复用 owned_scope + 闭包/cell 写包装对齐 + rehydrator kind
  保真 + TYPE_PARAM 检查放行）；② **OPTIONAL-CONTAINER-1**（IbOptional.receive 统一
  委托链 + resolve_iterable 识别 Optional）；③ **ATTR-READ-1**（`_default_getattr`
  未命中改抛 RUN_ATTRIBUTE_ERROR，读取/调用一致 fail-fast）。触发用例 D2-09/D2-10/D1-13
  全部核销转 PASS；判别性回归 +28；DOC-24~28 全部同步（含 BOUNDARY-CHAN-ARGS-1 文档说明）。
  完整记录见 NEXT_STEPS"已完成"节 + WORKLOG。

- **✅ 已完成（2026-08-14，T05/T06 剩余代码缺陷四项修复，全量 2665 passed / 1 skipped 零回归）**：
  **① CROSSMOD-LLM-1**（`_resolve_type` 支持 IbAttribute 点号限定注解，行为节点
  node_to_type 绑定 module 限定 spec；D3-02/D2-05 转 PASS）。**② KI-2 统一 Optional
  值模型**（`wrap_optional` 单一包装权威覆盖全值创建路径 + `is None` 双向语义 +
  `is_none()` + `None==Opt` 对称 + deep_clone 保 _is_some + llmexcept 类符号跳过；
  判别性回归 +20）。**③ 幽灵诊断码**（7 发射 + PAR_MULTIPLE_INTENTS 删减 +
  RUNTIME_ERROR→RUN_GENERIC_ERROR + CAT-7 可发射性契约；判别性回归 +10）。
  **④ set_mock_mode 对称开关**（enable=False 退出 + fail-fast；判别性回归 +3）。
  独立复核（general agent）两轮全整改（tuple 元素/`is` 双向/进制尾字母/残缺科学计数）。
  完整记录见 `_code_optional_unify.md` / `_code_ghost_codes.md` / `_code_set_mock_mode.md`。

- **✅ 已完成（2026-08-14，统一类身份模型 S1-S4，独立复核放行后 cherry-pick unsafe-vibe-dev，全量 2614→2616 passed / 1 skipped）**：
  **同名类运行时类表宏观根治（`_code_class_identity_unify.md`）**。S1 run_string 稳定入口
  锚点（`__string_exec__`）；S2 类身份统一（删 qualify_types 双轨——所有模块含入口用户类
  qualified，get_class 裸名回落仅内置，LLM parse/hint module 感知）；S3 单类表（删
  Bootstrapper 影子表，Enum 缺口自动弥合）；S4 KI-1 线程侧表 module 感知 + is_truthy 任务
  本地化。判别性回归 +2（线程 worker imported/入口类）。独立复核 PASS（反向实验实证
  KI-1 回归测试有效）。**KI-1（CROSSMOD-THREAD-1）核销**。

- **✅ 已完成（2026-08-14，`trials/T06_class_identity/`，全量 2616 passed / 1 skipped）**：
  **统一类身份模型回归 + 真实试用**。20 用例 18 PASS + 2 KERNEL_ISSUE（同一根因）。
  T05 KI-1 触发用例核销（D4-01）；入口类 qualified/单类表/get_class 回落/线程侧表/
  is_truthy 全验证；真实 LLM 8 例（思考已禁用，响应<1-2s）。**新暴露 pre-existing
  KERNEL_ISSUE-CROSSMOD-LLM-1（P1）**：跨模块用户类作行为表达式 LLM 输出目标
  node_to_type 未传播 → `__call__ on None`（base 同现）。详见 REGISTER/REPORT。

- **✅ 已完成（2026-08-14，doc-governance，全量 2616 passed / 1 skipped）**：
  **docs/ 全量文档治理**。四路并行审计 + 分阶段修复。KNOWN_LIMITS 三条不成立实证修正
  （§七/§八/§十三）+ 系统性日期戳/里程碑清理；syntax/（mock 值语义精确化、Optional
  is None、幽灵码标注、诊断码级别、cast_to/lambda 示例修复、TESTONLY→MOCK）；
  architecture/（is_none 删除、快照警告改静默恢复、ISO-2 矛盾、§3.4bis 元信息清理）；
  guide/howto（llmexcept 绑定修正、生成器语义统一、概念去重、补返回标注）；
  索引/根（GETTING_STARTED 计数、SUBSYSTEM_DESIGN、SYNTAX_REFERENCE）。**T05
  DOC_ISSUE-1~23 全部覆盖**（含 DOC-10 super 实证修正）。

- **✅ 已完成（2026-08-14，exp/runtime-class-module → 手动 cherry-pick unsafe-vibe-dev 6e68329c，全量 2614 passed / 1 skipped）**：
  **跨模块同名类运行时类表 module 化根治（S5 运行期闭环）**。注册键 = `spec.qualified_name`
  + `get_class(name, module)` module 感知 + `_specialize`/artifact_loader/序列化 module 化
  + `resolve_class_module` 权威父 module 解析（内置泛型父不加前缀）。判别性回归 +6（含
  105/hi! 方法表隔离）。独立复核（general agent）P1 已整改。设计 `_code_runtime_class_module.md`。

- **✅ 已完成（2026-08-14，`trials/T05_critical_stress/`，全量 2614 passed / 1 skipped）**：
  **T05 批判性压力试用 + 内核粗略问题分析（汇报任务，不修复）**。40 用例 37 PASS + 1 GUARD
  + 2 KERNEL_ISSUE；文档核验 23 DOC_ISSUE。**KERNEL_ISSUE 2 项（既有缺陷）**：
  ① **CROSSMOD-THREAD-1（P1）** 线程 worker 内被 import 模块用户类方法调用失败
  （task_ec 侧表回调读 interpreter 共享 current_module_name，忽略任务本地模块切换）；
  ② **OPTIONAL-ISNONE-1（P2）** `Optional[T] a = None; a is None` 返回 False
  （`is` 用 isinstance(IbNone)，Optional 包装不识别；`is_none()` 文档有实现缺）。
  报告 `REPORT.md` + `REGISTER.md`；完整明细 NEXT_STEPS 已完成节。**处置见上方当前交接**。

- **✅ 已完成（2026-08-13/14，类型体系地基根治 S0-S7 + 遗留边界，全量 2608 passed / 1 skipped）**：
  **类型体系地基根治（`_TYPE_SYSTEM_REBUILD.md` v2，物化路线内结构化）**。桩1 创建点结构化
  TypeRef、descriptor 双真相收敛、桩2 get_base_name 单义 + 句柄类物化、桩3 声明驱动序列化、
  元组解包检查 + 容器推断（含 `-> auto`）、`*expr` 元素级校验、S5 跨模块同名类编译期 module 化。
  判别性回归 +25。**运行期 module 化已在本 session 闭环（见上）**。详见 NEXT_STEPS + WORKLOG。

- **✅ 已完成（2026-08-13，unsafe-vibe-dev 617fb3a6/503f92fd 等 5 commits，全量 2579 passed / 1 skipped）**：
  **值层身份彻底收敛（`_code_generic_value_convergence.md`）**。统一"类型上下文→字面量"
  递归传递机制（`_bind_literal_with_type`）覆盖全部容器字面量产生路径：函数返回/lambda
  返回/调用实参/下标赋值/复合赋值/条件表达式/函数默认参数/for 循环源/嵌套内层/Optional
  包裹/生成器 yield/切片/运算符/跨引擎反序列化——`type(list[int]值)=list[int]` 全场景一致。
  两轮独立复核零风险。剩余已知边界（独立窗口）：`-> auto` 泛型实参推断 / `-> generator[T]`
  二次包裹（预存 c8b89564）/ `*expr` 展开实参（根本限制）。详见 NEXT_STEPS + WORKLOG。

- **✅ 已完成（2026-08-13，unsafe-vibe-dev 80294a64/447ad35c/7a15c1b9，全量 2559 passed / 1 skipped）**：
  **内置泛型类型身份双轨根治（缺陷一 + 缺陷二）**。统一根因 = 内置泛型与用户类泛型
  类型身份模型双轨不对称。缺陷一（is_assignable 同家族结构化实参比较 + 跨家族 axiom 父链）
  → 10/11 类 `X[int]→X[str]` 编译期拦截；缺陷二（特化 spec 水化为运行时特化类四层）→
  `type(list[int]值)=list[int]`、运行时值层类型安全闭环、深克隆/序列化 round-trip 保真。
  独立复核整改 3 项（dict 协变/boxed 防御/跨家族）。设计冻结
  `（已清理任务文档）`；边界增量（函数返回/实参/嵌套内层/切片/
  Optional/跨引擎反序列化）记录 §2.6。详见 NEXT_STEPS 已完成节 + WORKLOG。

- **✅ 已完成（2026-08-13，unsafe-vibe-dev e45dbb75，全量 2519 passed / 1 skipped）**：
  **spec→TypeRef 收敛 + 测试套件重构（反思分析驱动）**。
  **A 内核收敛**（反思揭示 spec→TypeRef 三实现分裂）：A1 `_spec_to_typeref` 委托
  `from_spec`（修 fn_callable 腐蚀/thread 读错字段/chan 扁平化）+ A2 `from_spec` 补
  tuple positional 分支 + A3 死接口清理（删 to_typeref/restore，TestToTyperef→
  TestTypeRefFromSpec）。**B 测试套件重构**（测试目标回归"应该具备的行为"）：B1 b 类
  反向断言改正面契约 + B2 空洞测试强化 + B3 47 文件历史锚定措辞清理 + B4 脆弱断言评估
  （4 类均合理保留）+ B5 meta docstring 历史锚定扫描规则永久化。

- **✅ 已完成（2026-08-13，unsafe-vibe-dev 0fee0c43，全量 2377 passed / 1 skipped）**：
  **GEN-5/GEN-6 架构级修复（`GEN_FIX_ARCHITECTURE.md` 四层全部落地）**。统一根因 =
  **TypeRef 生命周期双端口径漂移**（构造端扁平化 + 解析端丢实参 + 注册端机制不全）。
  ① 第 3 层 GEN-5（c00c87bb）：`visit_IbSubscript` 复用 `_resolve_type` 递归，GEN5-01 核销；
  ② 第 1 层 GEN-6A（8f7fff8a）：运算符推断改 `resolve_typeref` + 14 个 `.head` 解析点迁移；
  ③ 第 2 层 GEN-6B（52e7992f）：`_param_type_ref` 复用 `from_spec` + engine 扁平残留 +
  `to_typeref`/`from_spec` 双实现收敛，D2-01 核销；④ 第 4 层（0fee0c43）：`03_type_system.md`
  §3.4bis 规则永久化。判别性回归 +11。

- **✅ 已完成（2026-08-13，unsafe-vibe-dev 620de1c4，全量 2366 passed / 1 skipped）**：
  **试用体系重构（TRIAL_SYSTEM_REDESIGN.md）Phase B 收尾 + Phase C + Phase D 全部完成**。
  ① **T01 LLM 批真实重跑**（Phase B 收尾）：57 个 LLM 用例真实重跑 **55 PASS + 2 GUARD**
  （零 HARNESS/零缺陷复现）；断言从基线 `DONE` 精化为稳定确定性行；修复 8 个脚本缺陷
  （5 import 位置 / 2 守卫断言 / 1 API 类型）+ child_llm F9 配置。② **Phase C 干净彻底**：
  **用户原则确立——套件不冻结历史资产、问题直接重构，唯一底线不为规避缺陷改套件（缺陷
  触发用例保留）**；删除 40 个过期文档；套件重构（T02 T3/T4/T5 断言改映射有效性 / T04
  R1-05/R5-01/R5-04 重构为修复后语义、删 b 变体）；4 套 register.jsonl classification 写回
  **100%**。③ **Phase D 自动化衔接**：报告自动生成器 `_toolkit/gen_register.py` +
  收敛流程硬规则 `_toolkit/PHASE_D_AUTOMATION.md`（缺陷修复=根因修复+tests/ 回归双交付）。
  **遗留独立窗口**：供应商感知思考禁用机制（待设计）。
  详见 NEXT_STEPS 交接要点 + WORKLOG。

- **✅ 已完成（2026-08-12，unsafe-vibe-dev 35bb2de，全量 2339 passed / 1 skipped）**：
  - **用户类泛型参数（PT-FEAT-3 主线）完整落地**：设计冻结 `PT_FEAT3_DESIGN.md`（6 项开放问题
    决断）+ 全链路（AST/parser/语义/序列化/运行时/诊断/文档）。已支持多特化/字段·方法参数·返回
    类型特化/嵌套泛型/多参数 `Pair[K,V]`/泛型继承 `class Sub[T](Box[T])`；守卫（裸用/实参数/
    字段-T 冲突/Enum 泛型/类型参数遮蔽内置/非泛型子类继承特化）；21 e2e + 2 round-trip；
    独立复核两轮 PASS（P2-1/P2-2 全整改）。
  - **🟡 泛型压力/恶意试用（`_GENERICS_TRIAL_20260812/`，30 次运行全经死循环保护）**：D1 核心
    语义 + D2 正交交叉（运算符/继承/协议/容器/控制流/函数/并发/生成器/行为/闭包/多文件）+ D3
    恶意挑刺。深度核验 + 两轮独立复核后 G1/G2/BOUNDARY-G1/双通道**全部修复**
    （32484fe/3fe98d6/d100ee1，+11 e2e，全量 2350/1）。详见 REGISTER.md。
  - **🟡 泛型修复回归试用（`_GENERICS_TRIAL_FIX_20260812/`，28 用例 + 冒烟全经死循环保护）**：
    修复成果验证 G1 方法体/G2 自引用基础/BOUNDARY-G1 守卫/双通道 全 PASS。**新发现 2 项
    既有缺陷**（git worktree 在修复前 35bb2de 复现，非本次引入）：G3 继承特化父类字段值
    丢失（P1，静默 None——`Linked[int](5).get()` 返回 None）+ BOUNDARY-G2 自引用链 while
    遍历类型退化（P2）——登记 PENDING_TASKS。
  - **遗留独立窗口批次**：PT-DEBT-24 call_intent 死代码根治（S4）+ PT-AUDIT-3 S1-S5 处置
    （S4 根治 / S5 去重 / S1-S3 已知边界）+ 枚举实例化设计候选评估（`_enum_instancing_assessment.md`，
    维持现状）。独立复核 PASS。
  - **F9 显式配置（用户拍板命名 `ai.load_project_config` + 本轮实施）**：`setup()` 去自动加载段；
    新增 `load_project_config()`（ec/project_root 缺失 fail-fast + 路径规范化 + 缺失 no-op + 幂等）；
    vtable 注册；测试 + examples 01/02/03 + 文档同步。独立复核 PASS。设计记录 `_code_ai_autoset.md`
    + 实施记录 `_code_f9_load_project_config.md`。

- **✅ 已完成（2026-08-12，合并执行）**：**阶段 3 合并**（用户显式授权）——`unsafe-vibe-dev` 全面
  合并取代 `main`（merge commit `eb4a7d1`，main 树 == unsafe-vibe-dev 树，全量 2308/1 验证通过 +
  push）；原 unsafe-vibe-dev 本地+远端删除，从新 main 分支出新 unsafe-vibe-dev（== origin/unsafe-vibe-dev
  == eb4a7d1）供后续开发。main 现为稳定基线。

- **✅ 已完成（2026-08-12，unsafe-vibe-dev，全量 2308 passed / 1 skipped）**：
  - **enum 补全（PT-FEAT-2）**：非 str 枚举 LLM 集成修复（成员名→值映射，真实 LLM 实证 qwen
    成员名→值 200→switch 命中）+ 迭代 `for v in Color:` + `len(Color)` + KNOWN_LIMITS §二 更新。
    **自定义方法 = 值模型边界**（`Color.RED` 是底层值非实例）——实例化枚举为独立设计候选
    （`_code_enum_completion.md`）。
  - **嵌套包 import 根治**：`import subpkg.util` + 成员访问 INT_INTERNAL_ERROR 三层根因全部修复
    （嵌套段 MemberSpec 统一 + 中间段 create_module 全名注册 + 绑定根段 + 运行时包命名空间幂等合并）。
  - **文档批次**：DOC-ISSUE-001~007 批量同步 + BOUNDARY-001~005 处置 + KNOWN_LIMITS §十四 #2
    运算符覆盖度实测核对（比较/算术/一元/成员全可用，`is` 恒身份；+6 回归测试）。
  - **用户试用**：自建 `_LLM_TRIAL_ENUM_IMPORT_20260812/`（harness 复用），9 例全过（含真实 LLM
    非 str 枚举集成实证），**无新增缺陷**。
  - **独立复核（general agent）PASS** + 建议项整改（负数成员映射/注释卫生/死分支清理）。

- **遗留待独立窗口**：枚举实例化设计候选；KNOWN_LIMITS §十四 #1 用户类泛型参数；PT-DEBT-4
  （file 重命名）；PT-DEBT-24（call_intent 死代码）；PT-AUDIT-3 S1-S5；`import subpkg`（纯包目录）
  DEP_MODULE_NOT_FOUND（Python 同语义）。

- **本 session（2026-08-12，enum 补全 + 独立窗口打包 + 用户试用）**：按用户确认的建议打包推进。
  enum 补全（值模型下 ①③④ 实现，② 根因为值模型文档化为边界）→ 嵌套包 import 根治 → DOC/BOUNDARY
  文档批次 → 运算符覆盖度核对 → 自建用户试用 9 例全过。全量 2270 → 2308 passed / 1 skipped。
  详见 WORKLOG 与本文件 §2.2。

- **本 session（2026-08-12，真实 LLM 试用重启交接编制）**：评估确认原"真实 LLM e2e 全面试用"报告
  （`_REAL_LLM_E2E_REPORT.md` §四 9/12 类）基于含 U1-U7 不合格操作的旧代码；意图机制结论已纠错；
  修复后未重跑。产出 `_REAL_LLM_E2E_RESTART.md`（重启交接：背景/代码事实/重验清单 A1-A5 + B1-B3 +
  C1-C4/执行方式/约束）；NEXT_STEPS/HANDOFF/PENDING_TASKS 同步。全量 **2210 passed / 1 skipped**。

- **本 session（2026-08-11，合并收尾准备 + PT-AUDIT-3，unsafe-vibe-dev，全量 2169 → 2209 passed / 1 skipped）**：
  - **doc-health P1/P2 全部处置**：P1 16 项（`@method` 陈旧引用改真实 ihost API、`已重构为包` 历史演变清除、
    09 章节编号四·五→五、KDIAG 码表补 KDIAG_RUNTIME_ENV_LIMIT + 码集权威源标注、super 归属 06_oop §6.4、
    05_coroutine 状态文档重写、05_functions `-> auto` 行为体语义对齐代码、04_control_flow 4.7.x 归位、
    15_diagnostics 分域引言、11_modules 平行模板、E9 模块路径清除）；P2 12 项（A5 类构造 CPS 变更反映
    arch/04 §2.7 + arch/05 EXEC-4、README 阅读路径、howto 扩充 use_generators + write_concurrent_tasks、
    subsystems/01 断链 stmt_handler→llm_behavior、KNOWN_LIMITS 当前状态标签清除、guide 死引用清理、
    TestHooks 模板化）。已提交 f168215/c4307ad。
  - **pyproject 0.1.0 → 0.2.0**（30ebdf0）。
  - **examples 真实 LLM 跑通**（本地 qwen3.6-35b-a3b）：11 例全过；**暴露并修复 dispatch 赋值后
    idbg/ai 调用信息不可观测**——`_record_dispatch_call_info`（只写单写槽不追加 trace）+ resolve 点
    覆盖补全 response；+3 回归测试（d6d28e1）。
  - **PT-AUDIT-3**（general agent 独立审计）：无 P0；3 确凿 P2 修复（run_batch 观测 / active_intents
    漂移 / `_drive` 装箱一致）+ generator 兜底 fail-fast + KNOWN_LIMITS §二十四 修正（df1a896）；
    5 疑似项 S1-S5 待独立窗口（`_PT_AUDIT3_RECORD.md`）。
  - **合并就绪报告**：`_MERGE_READY_REPORT.md`（四项合并条件全满足）。
  - **遗留**：PT-AUDIT-3 疑似项 S1-S5、PT-DEBT-24（call_intent 死代码，复核确认）、F9（评估为
    设计意图保持）、PT-DEBT-4（独立窗口）、P3 VISION、test_mock_service 偶发 flaky（无关功能）。

- **本 session（2026-08-11，不合格操作 U1-U7 修复 + P1-P4 决断 + 意图注入纠错 + T1-T5 泛化审计，unsafe-vibe-dev，13 commits，全量 2169 → 2201 passed / 1 skipped）**：
  - **U1**：GeneratorAxiom（新公理）+ GENERATOR_SPEC + @register_ib_type("generator") + 删
    IbGenerator.receive 特判 + leaf.py 改查 generator 类；顺带闭合 generator[T] `_axiom_name`
    无公理缺口（此前 get_axiom 恒 None）。契约测试 GEN-1~4。
  - **U2**：真实根因 = dispatch-before-use 路径 `_assign_future_to_name_target` 未走 define 遮蔽
    （比交接推断"编译器 UID 新旧分裂"更精确——编译器对字面量/LLM 统一绑 intrinsic UID，遮蔽由
    运行时 define 承担）。加 define_only 参数 + define_raw。+2 回归测试；示例改回 `int sum`。
  - **U3**：删 extension.exceptions.InterpreterError，公开名指 kernel.issue 版；清理 ibcext.py
    死 import。+3 契约测试。
  - **U4/U6/U7**：setup 用 PathValidator.canonicalize_for_security + 注入异常 fail-fast /
    配置缺失静默跳过 + project_root 契约文档。+4 契约测试（含符号链接验证）。
  - **U5**：删 _code_api_config.md。
  - **P1-P4**：意图注入措辞强化统一 + 文档；project_root 检测文档化；P3/P4 维持现状。
  - **⚠ 意图注入纠错（7339220）**：P1 结论实证推翻——`@`/`@!` 一次性意图在 dispatch-before-use
    路径从未进 prompt（`fork` 移入 `_inherited_*` 而 captured 分支只取 active/global）；修复
    `resolve_to_prompts` 单一权威消解；真实模型实证 qwen3.6 遵循意图。+6 回归测试。
  - **T1-T5 泛化审计批次（本 session 追加）**：① T1 模式分析（双路径分裂/快照半消费/机制同构
    假象/探针缺失 4 教训）；② T2 同族审计（dispatch/同步/lambda/snapshot/llmexcept/CPS 孪生
    逐项验证，无新缺陷，call_intent 登记 PT-DEBT-24）；③ **T3 LLM 调用追踪（c1e63d1）**——
    `engine.get_llm_call_trace()` 有界环形缓冲（完整 prompt+响应+意图），调试不再靠 monkeypatch；
    ④ **T4 历史彻查（0eb8939）**——general agent 独立审计发现上批次自审计 D 段误标"正确"的
    F1-F7（env 透传/环境覆盖/双锚点/reasoning 不对称/死字段/空凭据/字面量重复）全部修复；⑤
    T5 重规划（PT-DEBT-22/23 已修复 + 24/F9 登记）。
  - **遗留**：`extension.exceptions` PluginError/CompilerError 为 SDK 独立类型未纳入 U3 范围
    （构造契约不同，无同名冲突）；test_mock_service 一次偶发 flaky（HTTP 时序，与改动无关）；
    PT-DEBT-24（call_intent 清理）、F9（import ai 配置副作用评估）待独立窗口。
  - **认知**：全程按"工作模式定论"根因修复（不留新兼容层），逐项 code-workflow Phase 0-5 +
    全量 pytest 零回归验证。

- **PT-DEBT-17 `ai.run_batch` 同步阻塞根治（2026-08-11，独立分支 exp/run-batch-cps → 手动应用 unsafe-vibe-dev ebbb7f8，全量 2135 passed / 1 skipped）**：
  - **三层不一致全部根治**：`run_batch` 返回 `CPSDrivable` Waitable（与 `stream_call` 返回 `IbStreamHandle`、A3
    `_SlotUpdateWaitable.cps_drive` 同构）——VM `vm_handle_IbCall` `yield from result.cps_drive(executor)` 帧内驱动。
    **① 主线程 `fut.result()` 硬阻塞** → `_run_batch_cps` 把多 LLM Future 聚合为 `LLMBatchFuture`（新聚合 Waitable）
    由调度器非阻塞等待；**② 同步 `_prepare_behavior_call` `vm.run` 重入** → 用 `_prepare_behavior_call_cps`（段求值/
    意图消解/hint 嵌入 VM 帧栈）消除；**③ 与 `stream_call` Waitable 范式割裂** → 返回 Waitable 统一。vtable
    return_type=list 契约不变（auto-yield 后仍收 boxed IbList）。宿主/线程体无 VM 走 `_run_batch_sync` 同步兜底。
  - **顺带清理死代码**：`LLMExecutorImpl.resolve()` + `LLMFuture.get()`（VM 全走 `resolve_future_cps`）+ 其 5 个
    死测试 + 死 import + `LLMExecutor` 协议声明同步；统一批量聚合 `_aggregate_batch_results`（消除双路径分叉）。
  - 设计记录 `（已清理任务文档）`；general 复核 3 建议级全整改；补判别性回归测试
    `TestRunBatchWaitableContract`（旧实现返回 List 必失败）。文档 `05_vm_specification.md` §3.4 公理 LLM-4 同步。
- **A5 用户类构造帧内 CPS 根治（2026-08-11，独立分支 exp/a5-cps-construct → 直接合并 unsafe-vibe-dev 356b0d8，全量 2137 passed / 1 skipped）**：用户类（不含原生 __init__）构造改返回 `_ClassInstantiateDrive`（Waitable+CPSDrivable）——`cps_drive` 在 VM 帧内 yield 字段默认值 + 用户 __init__（UserFunctionCall），消除 `vm.run` 重入与 `init_method.call` 嵌套 TaskScheduler；leaf.py 兜底细化（CPSDrivable 无论 func 是否 IbClass 均帧内驱动，纯 Waitable 仅非 IbClass auto-yield，thread 原生 __init__ 返回 IbThread 句柄仍不 auto-yield）；宿主/线程体走同步 instantiate 兜底。general 复核 5 检查点 PASS + 全量 2137/1 零回归。**A6 评估维持现状**（niche + 条件触发，登记已知项）。**分支政策细则**：2026-08-11 用户明确"零风险直接合并"，A5 因零风险直接合并到 unsafe-vibe-dev。
- **当前主线（架构健康性优先，2026-08-08 用户定案）**：**异步地基遗留妥协根治（统一执行模型闭环）——全部收尾（2026-08-09）**。
  审计确认内核层仍有"任务内同步重入调度器"遗留旁路（登记 PT-DEBT-12/13/14/15）：
  - **PT-DEBT-12（F1）用户方法 CPS 化、PT-DEBT-13（B1）chan.send Waitable 化、PT-DEBT-14（F2/F3）
    slot.update + prompt hint CPS 化、PT-DEBT-15（M4）LLM 真挂起——已完成（2026-08-08）**；M3（prompt 单源）
    已确认收敛。
  - **PT-DEBT-15 剩余 M1（.call 双写收敛）/ M2（驱动去重）已完成（2026-08-09，独立分支 exp/async-m1m2，
    全量 2137 passed / 1 skipped）**。M2 线程体 `_drive_generator` 复用 `_drive_loop_gen` + `TaskScheduler`
    （单一权威驱动）；M1 四个可调用对象（IbUserFunction/IbFnCallable/IbBehavior/IbLLMFunction）`.call()` 变薄
    宿主包装委托 CPS 生成器（消绑定双写）。实施计划与落地状态 `_ASYNC_UNIFY.md`（F1→B1→F2/F3→M1-M4 全部收尾）。
- **低风险推进（2026-08-09，unsafe-vibe-dev，4 commit）**：
  - **PENDING_REVIEW_ITEMS 状态同步**（29e7017）：D1-D5 已落地、R5 聚焦治理已执行（消除与 PENDING_TASKS 交叉滞后）。
  - **PT-AUDIT-2 宽 except 核验**（314e260/5bed073，独立分支 exp/audit-branch-nesting）：ibci_ai 已窄化
    `_PROVIDER_ERRORS`、auto_discovery 为 fail-fast 重抛——A 类保留，无代码变更。
  - **docs/ 过时表述修复**（92a1676）：05_coroutine/04_vm 标记 yield 惰性生成器已落地；L3 收敛为生成器内
    LLM 并发流水线未实现。
- **技术手册三修 + 文档残留清理（2026-08-10，unsafe-vibe-dev，PT-DOC-3）**：① `01_principles.md:255` §6.3
  改写为现状（意图栈继承由 `IbIntentContext.fork()` 承担公理 IC-1；`IsolationPolicy` 实际字段
  `inherit_plugins`/`collect_timeout`，跨隔离边界不继承意图）；② `04_vm_interpreter.md:29` 统一执行入口表述
  （模块入口 `execute_module`→`run_body`；宿主入口 `.call` 薄包装委托 `_vm_call_*`+`_drive_generator`）；
  ③ `docs/README.md` 目录树补 `15_diagnostics.md`；④ NEXT_STEPS.md:50 旧"遗留技术债"表述改归档记录。
- **异步统一完整性 A1/A3/A4 完成（2026-08-10，独立分支 exp/async-unify-a，全量 2138/1，待手动应用 unsafe-vibe-dev）**：
  - **A1 内联 `@~` 接 CPS**（llm_behavior.py）：`vm_handle_IbBehaviorExpr` 非 callable 分支切
    `execute_behavior_expression_cps`（段求值 yield 嵌入帧栈 + LLM 线程池挂起）。顺带补 `IbGenerator.generic_next`
    Waitable 契约缺口（`_drive_generator_loop` 声明"向外 yield 的只有 GeneratorYield 与 Waitable"，迭代侧此前只实现其一）。
  - **A4 LLM 函数 CPS-yield**（_llm_function.py，PT-FEAT-1 直接项）：`execute_llm_function_cps` 拆分
    `_prepare_llm_function_call_cps`（CPS 段求值 + `LLMFunctionCallSpec` 快照）+ `_call_and_parse_llm_function`
    （worker 安全、record_current=False）+ 提交线程池 yield LLMFuture。
  - **A3 `_SlotUpdateWaitable` 并入调度器**（comm.py + leaf.py）：新增 `cps_drive` 帧内 CPS 驱动生成器；
    `vm_handle_IbCall` 对 `getattr(result, "cps_drive", None)` 非 None 的 Waitable 帧内 `yield from`（消除
    `try_result` 内嵌套 TaskScheduler）。宿主 `_drive` 路径保留。
  - 测试 +1（slot.update(snapshot) 帧内驱动）；独立复核通过；A2（意图消解）/A5（类构造）/A6（协议方法）遗留待评估。
- **内核健康三项 + A2（2026-08-10，unsafe-vibe-dev，全量 2138/1，0 warning）**：
  - **测试持续 warning 修复**：`test_recursion_overflow_propagates_root_cause` 改用 `pytest.warns` 显式断言
    `KDIAG_RUNTIME_ENV_LIMIT` 警告投影（PT-FEAT-9 设计内"警告不门控"，非缺陷；生产代码不动）。
  - **死同步包装清理（-241 行）**：删 `invoke_behavior`/`execute_behavior_object`/`execute_llm_function`/
    `invoke_llm_function`（M1 收敛后零消费者互引成环，协议注释"唯一对外接触点"已过时）；保留
    `_prepare_behavior_call`/`_evaluate_segments`（dispatch_eager/run_batch 后台线程依赖）与 `run_batch`
    （ai.run_batch 消费）；同步更新 IILLMExecutor/LLMExecutor 协议声明。
  - **双驱动循环合并（-105 行）**：`_drive_generator_loop` 并入 `_drive_loop_gen`（`yield_generator_values` 参数），
    顺带修复生成器体缺 step/cancel 检查。
  - **A2 意图消解 CPS 化（+76 行）**：`resolve_content_cps`/`IntentResolver.resolve_cps`/
    `get_resolved_prompt_intents_cps`，CPS 预求值路径消除 `vm.run` 同步重入；同步 `_prepare_behavior_call`
    保留（后台线程合法）。
- **彻查：`run_batch` 三层设计不一致 + 同类排查（2026-08-10，只读彻查，登记 PT-DEBT-17）**：
  - **PT-DEBT-17 `ai.run_batch` 同步阻塞（确凿，待彻底修复）**：`run_batch`（`_behavior.py:339`）返回
    `List`（非 Waitable）→ 不走 auto-yield → 主线程 `fut.result()`（:383）同步阻塞等全部 LLM（实测
    main_thread=True + `_prepare_behavior_call`（:369）`vm.run` 重入 + 同模块 `stream_call`/`stream_channel`
    返回 Waitable 协作对比范式割裂（design-philosophy §三/§四）。修复方向：CPS 化（预求值改 yield +
    多 Future 聚合 Waitable）+ `ai.run_batch` vtable return_type 契约评估。涉及对外契约，独立窗口。
  - **彻查证伪（非问题）**：`ihost.collect`/`run_isolated` 返回 `HostAwaitable`（标准 Waitable），经
    `request_collect` 精确打点证实 fast 子任务完成后立即返回、总时=max 非 sum——是文档化透明异步契约
    （`14_concurrency.md` auto-yield），非同步阻塞。一度误判已撤回。
  - **死代码发现**：同步 `LLMExecutorImpl.resolve()`（`_scheduler.py:78`）与 `LLMFuture.get()`（`llm_result.py:129`）
    零真实调用（仅 docstring 示例），VM 全走 CPS `resolve_future_cps`——可随 PT-DEBT-17 清理。
  - **同类排查结论**：`collect`/`stream_call`/`thread`/`stream` 均正确 Waitable 范式；`run_batch` 是唯一
    "返回非 Waitable 的等待型原语"；无其它 `fut.result()`/`thread.join()` 在 VM 主路径同步阻塞（已全量扫描）。
  - 详见 WORKLOG 与 PENDING_TASKS PT-DEBT-17。
- **三轴健康盘点（2026-08-09，只读调查，见 `_HEALTH_AUDIT_PLAN.md`）**：从异步统一完整性 + 内核健康 +
  技术手册健康三维度，结合真实代码给出下一步规划（见下方"下一步候选"）。
- **本 session（2026-08-09，崩溃恢复点 c61a6e0 起，全量 2074 → 2137 passed / 1 skipped）**：
  - **P0 阶段 5 增量**：`next()` 内建 + `yield from` 生成器委托（主交付）——顺带根治 `_drive_generator_loop`
    生成器体内调用生成器函数的预存缺陷、迭代解析收敛 `_resolve_iterable`（现居 `shared/iterable.py`）。
  - **PT-FEAT-5 三项**：诊断码目录（`catalog.py` 76 码 + formatter fail-open + `15_diagnostics.md`）、
    符号表/类型绑定导出（`exporter.py` + 修 `inspect`/`semantic` CLI 死路径）、`bench` 编译基准。
  - **P1 PT-FEAT-10 UID 生成统一**：`core/base/uid.py` 单一权威源（11 家族），零内联，round-trip 保真。
  - **P2 审计**：R4 覆盖率核对（2 处 TRUE_GAP 补测）、R5 聚焦治理、PT-AUDIT-1 smell 全量事实回顾（A/B/C/D 定案）。
  - **质量**：三次独立 general 复核（中间/交付门/兜底专项）全部整改（含 `is_generator` 基类化、迭代解析中立归属、
    非可迭代测试修正、注释卫生）。兜底专项审计结论：全部属职责分离型合法 fallback，无 tricky/兼容妥协。
  - **异步地基收尾（M1/M2）**：见上——统一执行模型闭环完成。独立分支 exp/async-m1m2 实验，复核（general agent）
    A/B/D 放行 + C 记录（IbUserFunction void 返回语义向主路径收敛）。补回归测试 +9（`test_call_drive_convergence.py`）。
  - 设计记录 `（已清理任务文档）` / `_code_m1_call_dedup.md` / `_code_m2_drive_dedup.md`；完整逐项见 `WORKLOG.md` 与 git 历史。
- **下一步候选（按优先级，见 `PENDING_TASKS.md` §〇 + `_HEALTH_AUDIT_PLAN.md`）**：
  1. **技术手册三修**（低风险立即可做）：`01_principles.md:258` P1 过时 `inherit_intents` 字段、`04_vm_interpreter.md:29`
     P2 `.call` 路径表述、`README` 目录树补 `15_diagnostics.md`。
  2. **PT-DEBT-9/10/11 文档残留清理**：NEXT_STEPS.md:50 旧"遗留技术债"表述与根治状态不同步。
  3. **异步统一完整性（中风险，独立分支）**：A1 内联 `@~` 表达式接 CPS（llm_behavior.py:156，最高价值）、
     A4 LLM 函数 CPS-yield（_llm_function.py:202，PT-FEAT-1 直接项）、A3 `_SlotUpdateWaitable` 并入当前调度器。
  4. **PT-DEBT-4 `file` 模块重命名**（P1，破坏性变更独立窗口——已授权但需独立窗口审慎执行）。
  5. **PT-FEAT-5 剩余 CI/CD**（P0，涉远程 push，禁 push 硬原则，须用户显式授权后另行执行）。
  6. **P3 VISION**（PT-FEAT-8 分层张力待独立窗口；PT-FEAT-2 Enum 设计冻结级；PT-AUDIT-2 深嵌套/长 elif 链独立分支）。
- **评估为维持现状（已登记 PENDING_TASKS，勿重复推进）**：PT-FEAT-11（序列化器自动化）、PT-FEAT-12（AST uid 字段）、
  PT-FEAT-2（Enum 非 str 成员）、PT-FEAT-8（`.ibc_meta` 快照，分层张力）。
- **阶段 5 `yield` 惰性生成器已完成（2026-08-08，unsafe-vibe-dev，全量 2043 passed / 1 skipped）**：
  含 `yield` 函数自动为惰性生成器（D-08 自标记，async 关键字已取消），单可恢复驱动
  `_drive_generator_loop` + `GeneratorYield` 标记 + `IbGenerator` 值对象 + `generator[T]` 类型。
  设计权威 `（已清理任务文档）`。
- **PT-FEAT-9 阶段 4 已完成（2026-08-07，unsafe-vibe-dev，全量 2021 passed / 1 skipped）**：
  `kernel_diagnostic` helper（单一记录双投影：警告不门控 + 事件受 observability 门控，rc best-effort）+
  12 处站点迁移（文案逐字）+ e2e 事件投影测试 + `docs/architecture/09_observability.md`。设计权威
  `DIAGNOSTIC_DESIGN.md`（实施步骤 A-E 全部完成）。
- **kernel→runtime 穿透已根治（2026-08-08，unsafe-vibe-dev，commit d11bad0）**：用户红线"禁止一切
  kernel→runtime 穿透"。两处穿透（registry 惰性 import EventBus、host_interface 惰性 import
  kernel_diagnostic）改为依赖注入——registry 新增 `set_event_bus`（未注入 get fail-fast、peek fail-open）、
  HostInterface 新增 `set_diagnostic_emitter`（未注入回退 warnings.warn），engine 组装期注入。
  残留扫描确认 core/kernel/ 零 runtime import。
- **意图栈扁平化历史兼容已彻底移除（2026-08-08，unsafe-vibe-dev，commit 3ce9b7d）**：用户裁定"无事实
  用户，历史兼容不是考虑项"。删除序列化 `intent_stack` 平铺双写与旧格式反序列化回退、`context.intent_stack`
  property、两处接口协议声明；补意图上下文 6 槽位 round-trip 测试（+3）。
- **R 批次全部完成（2026-08-07，unsafe-vibe-dev，全量 2001 passed / 1 skipped）**：R4+R3（82c9c0f，1988/1）
  P3 公开协议 + D-04 `IbThread` 满足 Waitable → R6（35f1437，1995/1）嵌套函数自动只读捕获 → R2（c16b05e/c4c63aa，
  1998/1）调度器通知式唤醒 → R1（6dc9214，2001/1）函数调用 trampoline 化（EXEC-1 根治，深递归 Python 深度恒定）。
  各独立分支实验、手动 cherry-pick 应用 unsafe-vibe-dev。设计/决策见 `EXEC_REFACTOR_BATCH.md`（无悬而未决问题）。
- **已定案（不再重议）**：R5 撤回（`await` 幂等是 auto-yield 组合承载，改报错破坏 `await collect(h)`）；
  D-08 保留透明 async（CPS 天然可挂起 + auto-yield 组合 + 值契约 + yield 自标记）。
- **阶段 1/3 已完成（2026-08-07，unsafe-vibe-dev，全量 1984 passed / 1 skipped）**：地基 1a-1e（调度器执行核心/
  Waitable 家族 try_result/阻塞即挂起/协作取消/llmexcept×await/取消覆盖用户函数）+ 统一清理 W1-W5/P3/P4
  （非阻塞命名/订阅契约/pubsub EventBus/comm 命名回归/死状态/文档/cell 隔离/引擎级全局事件总线）。
- **后续增量（可选起点）**：streaming / host async 改进（`YIELD_GENERATOR_DESIGN.md` §五遗留）或
  `_ASYNC_UNIFY.md` M1/M2（当前主线未完）。
- **保留规划**：media Phase 4（PT-SEALED-1，彻底封存）。
- 要求：subagent 仅 general agent；每批全量 pytest 零回归；新缺陷按"不删也不修"两档处置；全程本地 commit、禁 push。

### 2.2 已完成摘要

- **2026-08-12（enum 补全 + 独立窗口打包 + 用户试用，unsafe-vibe-dev，全量 2270 → 2308 passed / 1 skipped）**：
  - **enum 补全（PT-FEAT-2）**：① 非 str 枚举 LLM 集成修复——symbol_collection_pass 写常量成员值到
    `MemberSpec.metadata["value"]`（含负数 `-1`），`EnumAxiom` 成员名→值映射 + from_prompt 大小写不敏感
    返回值；str 零回归/值≠名正确；**真实 LLM 实证**（qwen 输出成员名 OK→值 200→switch 命中）。
    ② 迭代 `for v in Color:` / `len(Color)`（has_iter_cap + get_method_specs + 运行时 Enum 基类绑定）。
    ③ **枚举自定义方法 = 值模型边界**（`Color.RED` 返回底层值 static_val 非实例，根因是值模型非注册
    缺口；实例化枚举为独立设计候选）。④ KNOWN_LIMITS §二 更新。设计记录 `_code_enum_completion.md`。
  - **嵌套包 import 根治**：`import subpkg.util` + 成员访问 INT_INTERNAL_ERROR——三层根因（嵌套段原始
    Symbol 入 members / visit_IbImport 绑定全名 / 中间段 PRIMITIVE kind 重导入守卫 + 运行时缺包命名空间）
    全部修复；2层/3层/同包多导入合并 e2e 全过。
  - **文档批次**：DOC-ISSUE-001~007 批量同步 + BOUNDARY-001~005 处置 + KNOWN_LIMITS §十四 #2 运算符
    覆盖度实测核对（比较/算术/一元/成员全可用，`is` 恒身份；+6 回归测试）。
  - **用户试用**：自建 `_LLM_TRIAL_ENUM_IMPORT_20260812/`（harness 三层保护复用），9 例全过，
    无新增缺陷。
  - **独立复核（general agent）PASS** + 建议项整改（负数映射/注释卫生/死分支清理/KNOWN_LIMITS 落档）。
- **2026-08-12（本 session 合并前）**：真实 LLM 全面压力试用重启（D1 全语法 + D2 压力 + D3 批判 +
  A1-A5 重验，2210/1）→ 试用暴露缺陷修复（PT-DEBT-25/26/27/28 + O1/I1/O2，2252/1）→ REVERIFY →
  易用性修复（return@~ 拦截/switch break/布尔引导，2270/1）。详见 NEXT_STEPS。
- **2026-08-09（本 session：P0 阶段5增量 + PT-FEAT-5×3 + PT-FEAT-10 + P2 审计 + 异步地基 M1/M2 收尾 + 低风险推进，unsafe-vibe-dev + 独立分支 exp/async-m1m2 / exp/audit-branch-nesting，全量 2074 → 2137 passed / 1 skipped）**：
  - **异步地基 M1/M2 收尾**：PT-DEBT-15 剩余 M1（.call 双写收敛）/ M2（驱动去重）完成——统一执行模型闭环
    全部收尾。M2 线程体 `_drive_generator` 复用 `_drive_loop_gen` + `TaskScheduler`（单一权威驱动）；M1 四个
    可调用对象 `.call()` 变薄宿主包装委托 CPS 生成器。独立分支 exp/async-m1m2 实验 + general 复核 + 补回归测试 +9
    （`test_call_drive_convergence.py`）。设计记录 `_code_m1_call_dedup.md` / `_code_m2_drive_dedup.md`。
  - **低风险推进**：PENDING_REVIEW_ITEMS 状态同步（D1-D5/R5）；PT-AUDIT-2 宽 except 核验（A 类保留）；docs/
    过时表述修复（yield 已落地）。4 commit（29e7017/314e260/5bed073/92a1676）。
  - **三轴健康盘点**：只读调查产出 `_HEALTH_AUDIT_PLAN.md`（异步遗留 A1-A6 + 内核健康 + 技术手册健康）。
  - **P0 阶段 5 增量**：`next()` 内建（c61a6e0）+ `yield from` 生成器委托（本 session 主交付，6c9555c）——
    完整文法管线（AST `IbYieldFromExpr`/语法 match(FROM)/语义 `SEM_YIELD_OUTSIDE_FUNCTION`/类型 GENERATOR/
    VM 委托 handler），顺带根治 `_drive_generator_loop` 生成器体内调用生成器函数的预存缺陷、迭代解析收敛
    `_resolve_iterable`（现居 `core/runtime/shared/iterable.py`，VM 与内建共用单一权威源）。e2e 13 项。
  - **PT-FEAT-5 三项**：诊断码目录（`core/base/diagnostics/catalog.py` 76 码 → 说明/修复 + `DiagnosticFormatter`
    集成 fail-open + `docs/syntax/15_diagnostics.md` + 契约测试 CAT-1~6）；符号表/类型绑定 JSON/dot 导出
    （`core/compiler/diagnostics/exporter.py` + 修 `inspect`/`semantic` 两处 CLI 预存死路径 + `bench` 编译基准）。
  - **P1 PT-FEAT-10 UID 生成统一**：`core/base/uid.py` 单一权威源（11 家族 UID 函数），调用方全部接入、
    格式逐字不变（round-trip 保真）、零内联格式字符串；契约测试 UID-1~4。
  - **P2 审计**：R4 覆盖率核对（12 项，2 处 TRUE_GAP 补测：subscriber 语言层生命周期、generator[T] 泛型身份）；
    R5 聚焦治理（session 改动文档核验）；PT-AUDIT-1 smell 审计全量事实回顾（A/B/C/D 定案，A7/A15 失效确认、
    多数设计内、C6 已解决）。
  - **质量**：三次独立 general 复核（中间/交付门/兜底专项）全部整改——含 `is_generator` 基类化（IbFunction）、
    迭代解析中立归属 `shared/iterable.py`、非可迭代测试修正（`yield from` 无协议对象）、注释卫生（生产代码零任务代号）、
    文档单点真理（catalog↔doc 契约一致）。**兜底专项审计结论**：全部兜底属职责分离型合法 fallback
    （声明面能力查询/显式 None/决策点报错/契约强制完备），无 tricky/兼容妥协。
  - 设计记录 `（已清理任务文档）`；完整逐项见 `WORKLOG.md` 尾部。
- **2026-08-08（异步地基遗留妥协审计，unsafe-vibe-dev，全量 2043 passed / 1 skipped）**：
  用户追问"异步是否已完整接入内核" → general subagent 全面只读审计 + 逐项代码核实。结论：**主流已完整**
  （协作调度器唯一执行核心/阻塞即挂起/Waitable 统一/trampoline/通知式唤醒/线程=IO/await+yield），
  但内核层仍有"任务内同步重入调度器"遗留旁路（同步 `.call()` 后备在任务内可达）。发现 F1-F3 高严重度 +
  B1 真阻塞 + M1-M4 中严重度；登记 PT-DEBT-12/13/14/15；用户定案新主线（异步遗留根治）+ 认可优先级表。
  详见 WORKLOG 与 `_ASYNC_UNIFY.md`。
- **2026-08-08（阶段 5 yield 惰性生成器，unsafe-vibe-dev，全量 2043 passed / 1 skipped）**：
  含 `yield` 函数自动为惰性生成器（D-08 自标记，async 关键字已取消）。词法 `yield` 关键字 + 语法
  `yield` 表达式（LOWEST 优先级）+ AST `IbYieldExpr`/`is_generator`；语义 `_contains_yield` 自动标记 +
  yield 仅函数体内（`SEM_YIELD_OUTSIDE_FUNCTION`）+ 返回类型 `generator[T]`；类型 `GENERATOR` TypeKind +
  `generator[T]` 泛型全链路；VM `vm_handle_IbYieldExpr` yield `GeneratorYield` 标记 + `_drive_generator_loop`
  单可恢复驱动（与 `_drive_loop_gen` 同构）；运行时 `IbGenerator` 值对象 + `for`/`to_list` 迭代。
  独立分支 exp/yield-generator 实验 → 手动应用 c8b8956。设计权威 `（已清理任务文档）`。
  e2e 9 项（基础迭代/状态保留/嵌套循环/条件内 yield/break/生成器 as 值/LLM 组合/auto 赋值/非函数体报错）。
- **2026-08-08（PT-DEBT-11/9/10 根治，unsafe-vibe-dev，全量 2029 passed / 1 skipped）**：
  ① **PT-DEBT-11**（4bf2644）——`UserFunctionCall` 下沉 `core/runtime/shared/user_call.py`（与 Signal/Waitable 同类叶子），handler/线程体不再向上依赖 VMExecutor 内部类；② **PT-DEBT-9**（c75541f）——环境限制异常（RecursionError/MemoryError/SystemError）根因保留：`core/runtime/shared/env_limits.py` 判定 + `diagnostics.handle_environment_limit` 发射 `KDIAG_RUNTIME_ENV_LIMIT` 诊断，VM 五处语义错误包装站点不再掩盖根因（+2 测试）；③ **PT-DEBT-10**——`_drive_generator` 改显式生成器栈（trampoline，与 `_drive_loop_gen` 同构），线程体内深递归不再嵌套 Python 栈；顺带根治线程体模块级函数解析（任务全局作用域链到模块作用域）、线程逻辑栈上限对齐主路径、`_vm_call_user_function`/`IbUserFunction.call`/`IbLLMFunction.call` push 后 finally 无条件 pop 的栈不均衡潜在 bug（+1 测试）。详见 WORKLOG 与 git 历史。
- **2026-08-08（本 session 收尾，unsafe-vibe-dev，全量 2026 passed / 1 skipped）**：
  ① **kernel→runtime 穿透根治**（d11bad0）——事件总线/诊断发射器依赖注入，kernel 层零 runtime 依赖；
  ② **死代码清理**（ffaffc0）——删 `KernelRegistry.clone()`（零调用方，spawn 隔离走独立 engine 路径）；
  ③ **文档-代码对账治理**（fe80595/5f5e26d/a8de1b1/3368c28）——P0 断链/自相矛盾 4 处、P1 过期/红线/事实错误
  ~20 处（执行模型对齐调度器、kernel-native 补 iruntime、意图系统穿透代码块、红线清理等）、P2 缺失/格式/体系
  ~15 处（14_concurrency 补 await/auto-yield、TestHooks、意图语法权威收敛 syntax/09、插件 howto 收敛等）；
  ④ **意图栈扁平化历史兼容彻底移除**（3ce9b7d）+ 补意图上下文 6 槽位 round-trip 测试（+3）；
  ⑤ **登记 PT-FEAT-10/11/12**（UID 统一/序列化器自动化/AST UID 字段，原被删愿景中值得保留的未来任务）。
  详见 WORKLOG 与 git 历史。
- **2026-08-08（文档-代码对账审查）**：5 个并行 general task 全量审查 + 逐项代码核实 + 独立交叉复核。
  结论：8 篇文档需修（重点：arch/04、05 执行模型停在旧叙事）；5 篇与代码一致。修复后残留扫描清零。
- **2026-08-07（PT-FEAT-9 阶段 4 完成）**：内核结构化诊断机制重建——`kernel_diagnostic` helper（单一记录双投影：
  警告不门控 + 事件受 observability 门控，rc best-effort）+ 12 处运行时站点迁移（文案逐字）+ e2e 事件投影测试
  （协议回退双投影/策略忽略 fail-open/门控）+ `docs/architecture/09_observability.md`（观测体系统一文档）。
- **2026-08-07（R 批次完成）**：统一执行地基复核与根治——R4+R3 P3 公开协议 + `IbThread` 满足 Waitable（`await t` 可用）、
  R6 嵌套函数自动只读捕获、R2 调度器通知式唤醒（根治 poll+park）、R1 函数调用 trampoline 化（深递归 Python 深度恒定）。
- **2026-08-06**：**OBSERVABILITY_REFACTOR 主体完成**——Phase 0-2C + 2C-2（idbg 深度收敛：protection_map
  内核化/统一变量视图/snapshot vars bug/LLM 事件流）+ 2D 测试体系全面重建（tests_v2 全域迁移 + 切换 +
  矩阵三段式 + tests_docs 治理）+ Phase 4 收敛全部落地。测试体系现为单一分层模型（kernel/compiler/runtime/
  plugins/contracts/e2e/compliance/sdk/meta/fixtures），meta 机器强制（分层/命名/helper 去重/矩阵对账）。
- **2026-08-05**：闭包序列化 round-trip 修复 + Axiom 家族分裂收敛 + EnumAxiom 双通道收敛 +
  use_intent_context 守卫修复 + R3 异味四 Zone 处置 + import-* 精确成员枚举根治（含 IBC 文件
  跨模块导入三层断裂修复）+ `type()` 内建落地 + 任务控制文档全面重整（任务代号按性质分域）。
- **线程对象模型方向修正（A-F）** + **通信领域设计完善三阶段** + **收尾 L1-L8 + T2** +
  **代码复核审查（code-review / 健康诊断 / 异味扫描）** + **类型强化** 全部落地（详见 git 历史）。
- **测试基线**：以实跑为准，不冻结数字（当前 **2209 passed / 1 skipped**）。
- **分支**：unsafe-vibe-dev（唯一活动分支；main 永不触碰；实验分支 exp/obs-2a/2b/2c/2c2/2d、exp/exec-ra/rb/rc/rd、
  exp/yield-generator、exp/async-m1m2、exp/async-unify-a、exp/run-batch-cps、exp/refactor-nesting、exp/a5-cps-construct
  保留供追溯——其中 exp/a5-cps-construct 因零风险已直接合并 unsafe-vibe-dev，其余未合并/部分已手动应用）。

### 2.3 交接检查单

- [ ] 读本节 §2.1（✅ 已完成：**T07 三项 P1 修复 + DOC-24~28 文档同步**，承接 `_HANDOFF_T07_FINDINGS.md` 已标完成；全量 **2693 passed / 1 skipped**）
- [ ] 读 `NEXT_STEPS.md`（当前最紧要：见 §2.1；T07 三项修复已完成记录）
- [ ] 读 `PENDING_TASKS.md` §〇（优先级总表；T07 三项 KI + DOC 批次已标修复/已同步；供应商感知思考禁用机制 / CI-CD 重设计等主线候选）
- [ ] 试用体系规范：`trials/_toolkit/CLASSIFICATION.md`（分类/编号）+ `CONTRACT_FORMAT.md`（用例即契约）+ `LLM_SERVICE.md`（本机真实 LLM 服务，当前在线且思考已禁用）+ `gen_register.py`（报告生成）+ `PHASE_D_AUTOMATION.md`（收敛流程硬规则）+ `run_batch.py`（分层批量）
- [ ] 跨套索引/缺陷状态：`trials/INDEX.md`（单一状态权威；新缺陷从 `KERNEL_ISSUE-*` 继续编号）
- [ ] 本 session 修复面：`_code_optional_unify.md`（CROSSMOD-LLM-1 + KI-2 统一 Optional 值模型）+ `_code_ghost_codes.md`（幽灵诊断码 + CAT-7）+ `_code_set_mock_mode.md`（对称开关）+ WORKLOG（T07 三项 KI 系统性根因与修复）
- [ ] 泛型剩余边界：`_HANDOFF_GENERIC_REMAINING.md`（7 项已知边界）
- [ ] 确认测试基线：`~/miniconda3/envs/ibci/bin/python -m pytest tests/`（当前 **2693 passed / 1 skipped**）
- [ ] 工作全程本地 commit、禁 push（除非用户显式授权）
