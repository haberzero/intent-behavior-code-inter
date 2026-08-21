# HANDOFF_SESSION — 会话交接文档（一次性，下一 session 核验后并入 HANDOFF.md）

> **性质**：会话边界交接文档。内容自包含，下一 session 开工前读本文件 +
> `tasks_docs/NEXT_STEPS.md` + `tasks_docs/PENDING_TASKS.md` + `tasks_docs/WORKLOG.md` +
> `tasks_docs/HANDOFF.md`。
> **核验并接手后**：把本文件要点收敛进 `HANDOFF.md` §二，然后删除本文件（git 承载历史）。

> **本 session 主线**：交接核验接手 + **阶段 B（B1-B6）全部完成**——功能稳健与对外能力
> （测试补测 / 协议定案 / 两项技术债 / 文档补齐 / CI 设计）。每步全量 pytest 零回归 + 本地
> commit；**未 push**（禁 push 硬原则，等待用户显式授权）。

---

## 一、总览（一句话）

本 session 完成：① 交接核验接手；② **阶段 B 全部六项落地**——B1 PT-TEST-2 覆盖缺口补测
（判别 +17）、B2 PT-DECIDE-3 项②④ 定案（判别 +4）、B3 PT-DEBT-36 intent_context 方法族重构 +
axiom 能力契约校验（判别 +13，**修复 bool|bool 误绑元类 type.__or__ 真实缺陷**）、B4 PT-DEBT-35
`_ctx` 契约单一权威形式化（判别 +9）、B5 PT-DOC-3P2 how-to 读者旅程补齐（+2 篇）、B6 PT-FEAT-5
CI/CD 可靠化设计 + 本地配置（**远程启用待用户授权**）。基线 **3182 passed / 1 skipped**（以实跑
为准），worktree 干净，**未 push**（本地领先 origin 25 提交）。

## 二、仓库状态（权威）

| 项 | 值 |
|----|----|
| 当前分支 | `unsafe-vibe-dev`（HEAD=`2f6b1cd2`，**本地领先 origin 25 提交未 push**——禁 push 硬原则，等待用户显式授权） |
| 其它分支 | `main`（未触碰）；无其它本地分支 |
| 测试基线 | `~/miniconda3/envs/ibci/bin/python -m pytest tests/` → **3182 passed / 1 skipped**（以实跑为准） |
| 工作树 | 干净 |
| push | **本 session 未 push**（25 提交本地领先）；后续 push 需用户显式授权 |
| Goal | 阶段 B goal（`goal-e5811877`）已 complete；下一任务（阶段 C VISION-3）按排布新建 |
| 排布 | `tasks_docs/_planning_health_first.md`（四阶段规划；阶段 A/B 全部完成，当前 P0 = 阶段 C） |

## 三、本 session 提交序列（unsafe-vibe-dev，旧→新；均未 push）

| 提交 | 内容 | 基线 |
|------|------|------|
| `1eaefb12` | B1 PT-TEST-2 覆盖缺口补测（判别 +17 + 矩阵卫生 + 模块重载=设计排除） | 3156 |
| `d58de0f8` | B1 任务控制同步 | — |
| `9e326471` | B2 PT-DECIDE-3 项②④ 落地（validate_prompt 不扩展内置 + impl 内置解析方法编译期拒绝 + to_prompt_str KDIAG） | 3160 |
| `31f6ddd9` | B2 任务控制同步 | — |
| `6882f5b8` | B3 PT-DEBT-36（intent_context 方法族重构 + _is_impl_method 排除元类伪影修复 bool\| + _verify_axiom_bindings 契约校验） | 3173 |
| `a6c32f16` | B3 任务控制同步 | — |
| `a482dcb6` | B4 PT-DEBT-35（_ctx 契约单一权威 get/set_intent_ctx，判别 +9） | 3182 |
| `dd3578f3` | B4 任务控制同步 | — |
| `00eaf873` | B5 PT-DOC-3P2（use_isolation + orchestrate_llm_calls 2 篇 howto + 交叉引用） | 纯文档 |
| `079f534f` | B5 任务控制同步 | — |
| `46c5a18e` | B6 PT-FEAT-5 CI/CD 可靠化设计 + 本地配置（ci.yml 分层就绪 + scripts/ci_local.sh） | 纯配置 |
| `2f6b1cd2` | 阶段 B 全部完成同步（当前 P0 前移阶段 C） | 纯文档 |

> 全部 12 个提交未 push。阶段 B 累计新增判别测试 43 项（17+4+13+9），基线 3133 → 3182。

## 四、待验证清单（下一 session 首步，按序）

- [ ] `git status` → 干净；`git branch -vv` → unsafe-vibe-dev 本地领先 origin 25 提交（未 push）、main 未动。
- [ ] `git log --oneline -15` 对齐 §三 提交序列。
- [ ] 全量 pytest 实跑 → 记录 passed/skipped（预期 3182 量级，**以实跑为准**）。
- [ ] 读 `tasks_docs/NEXT_STEPS.md`（当前 P0 = 阶段 C）+ `tasks_docs/_planning_health_first.md`（阶段 C 详案）。
- [ ] 读 `trials/INDEX.md` + `trials/_toolkit/LLM_SERVICE.md`（真实 LLM 服务基线 + 探测方法）。
- [ ] 读本文件 §五-§七（契约 + 下一 session 主任务 + 恶意测试要求）。
- [ ] 确认 push 授权状态：**本 session 未 push，25 提交等待授权**。

## 五、关键处置定论与契约（下一 session 必须知道）

1. **阶段 B 全部完成（B1-B6，2026-08-20）**，当前 P0 前移阶段 C。周期质量维护
   （PT-AUDIT-1/3 + Tier B + quality-maintenance）按用户裁定**推迟到真实试用（阶段 C）之后**，
   近期不占用主线——**阶段 C 结束后恢复**。
2. **B3 真实缺陷修复**：bootstrap `_auto_bind_operators` 曾用 `hasattr(py_impl_cls, magic_name)`
   探测运算符，`bool.__or__` 经 Python 元类命中 `type.__or__`（PEP 604 类型联合运算符），绑定成
   类对象运算符 → `bool | bool` 运行期 "expected 1 argument, got 2"。改 `_is_impl_method`
   （`getattr_static` 校验实例级方法）修复。**新增 `_verify_axiom_bindings` 契约校验**：公理声明
   方法必须 vtable/协议分派/字段承载，否则 bootstrap fail-fast。
3. **B4 `_ctx` 契约单一权威**：`intent_context.get_intent_ctx`/`set_intent_ctx`（isinstance 精确
   判别）为全仓 `_ctx` 槽唯一读写入口；后续新增 `_ctx` 访问一律走此入口，禁止散落字段探测。
4. **B6 CI/CD 交付边界（用户 2026-08-20 裁定）**：可靠化设计 + 本地配置已落地（四层可靠性
   L1 fast/L2 全量跨平台/L3 真实 LLM 手动/L4 发布产物 + `scripts/ci_local.sh` 本地复现）；
   **远程启用待用户授权**——授权后恢复 `.github/workflows/ci.yml` 的 `on:` 为 push/PR 并 push。
   设计文档 `tasks_docs/_code_cicd.md`（临时，收敛后删除）。
5. **push 契约**：本 session 未 push，25 提交本地领先；push 一律需用户显式授权（禁 push 硬原则，
   不因历史授权而默许）。
6. **goal 契约**：阶段 B goal 已 complete；阶段 C 新建 goal 用 HANDOFF §1.2.1 配置习惯
   （`max_auto_turns`=7、objective 按 §1.3 模板）。
7. **临时文档**：`tasks_docs/_code_cicd.md`（B6 设计）与 `tasks_docs/_planning_health_first.md`
   （四阶段规划）仍被引用；按治理经用户确认后删除（阶段 C 规划收敛进 NEXT_STEPS/PENDING 后）。
   `tests/COVERAGE_MATRIX.md` §13 TRUE_GAP 已收敛（仅剩 CATCH-4 重号说明）；B1 后缺口全闭。

## 六、下一 session 主任务：阶段 C · 真实 LLM 全面试用重启（VISION-3，用户指令强化）

> **用户 2026-08-20 明确（本交接强化版）**：下一 session 主任务 = **真实试用全面重启**，
> 且不仅是"试用重启"，还要**对相关试用项目做大规模更新补全**——近期大重构（五大地基 P1-P6 /
> 阶段 A-B）给 IBCI 带来了很多改变和新特性，**所有这些都要被真实试用评估**。此外，试用**不仅**
> 测试文档宣称/我们认为可用的功能，还要**带着恶意测试 IBCI 的边界**：可能存在缺陷的逻辑、
> 可能存在问题的逻辑、开发者没有考虑到的场景——这样才算测试的全面合理。最后，**全面试用结束后
> 对技术文档做全方位复核、更新、同步**。

### 6.1 阶段 C 评估面（五大地基重构后全部新特性，需大规模更新补全试用用例）

| 特性域 | 评估点 |
|--------|--------|
| **llm 可调用类** | 直接调用 `f(args)` / 装配 dict（user_prompt/prompt_slots/expected_type）/ 参数绑定 / `__intent__` 三层改写 / `__retry__` 高阶化 / 实例 `<Instance of T>` 渲染 / run_batch 逐项参数化 |
| **stream 流式** | `ai.stream_call` / `ai.stream_channel`（逐块 recv）/ `await` 后完整文本 / 流式错误处理 |
| **run_batch 批量** | 行为值（items 逐项绑参）+ llm 可调用实例（每 item 一次调用）/ 批量并发上限 / 错误传播 |
| **覆层机制** | `impl overlay for <T>` 声明 / `with overlay(<T>.<方法>):` 作用域 / 跨根并发隔离 / SEM_OVERLAY_UNUSED 告警 / snapshot·序列化影子条目 |
| **prompt 协议族五成员** | `__to_prompt__` / `__from_prompt__`（单向契约：必须返回目标类型实例）/ `__outputhint_prompt__` / `__payload_prompt__` / `__validate_prompt__`（+ `__retry__` 调用级 / `__intent__` 可选成员） |
| **意图一等值嵌入** | 行为/可调用值经 `__to_prompt__` 嵌入意图 / `@-` 按值派生渲染文本匹配 / snapshot 意图冻结（定义时刻）/ lambda 调用点 live |
| **fs 模块** | 原 file→fs 迁移后全部接口（open/read/read_bytes/write/overwrite_flag/exists/remove）/ file_handle 只读语义 / 沙箱限制 / llmexcept retry 体内文件写禁用 |
| **Optional/容器解析** | Optional[T] 值模型（is_some/unwrap/or_else）/ 容器解析 / 泛型特化 / 值语义（赋值别名 vs 拷贝） |
| **意图上下文 OOP** | intent_context 方法族（push/pop/fork/merge/combine/clear/use/get_current/clear_inherited）缺参 fail-fast / `_ctx` 契约 / 意图参数自动激活 |

### 6.2 试用方式（延续既有试用地基规范）

- **真实 LLM 为主**：本地 `qwen3.6-35b-a3b` 非思考模式（LM Studio @ 127.0.0.1:1234，
  `reasoning: false`）。**每次试用前先探测**：
  `curl -s -m 5 http://127.0.0.1:1234/v1/models`（失败 → 只跑 mock 用例，LLM 用例标 HARNESS）。
- **运行工具**：`trials/_toolkit/run_batch.py`（mock 批 `--mock-only` + LLM 批 `--llm-only`，
  parallel=8）+ `run_one.py`（子目录用例 `--root=`）。用例头部 `expect-class` 断言，harness 自动判定。
- **压力维度扩展**：>4k token / 多轮长对话 / 批量并发上限 / 多模块交叉。
- **缺陷闭环**：缺陷→根因修复→回归核销（trials INDEX 生命周期状态机：发现→登记→修复（tests/
  补回归）→回归试用（触发用例核销）→已修复/已核销）。
- **分层节奏**：mock 层先确认工具链与用例契约（快速），再真实 LLM 层全量回归。

### 6.3 大规模更新补全试用项目的方向

- **新建/重构套件覆盖新特性**：五大地基重构（P1-P6 协议化、`llm ... llmend` 语法删除、
  LLM 可调用类、覆层、prompt 协议族、意图一等值、fs 迁移）后，既有 T01-T09 用例大量基于
  **已删除语法**（`__sys__`/`__user__`/`__llmretry__` 段、`llm func`、`_spec.py` 插件体系等）——
  需系统性排查、迁移到新语法并补全新特性用例。新套件命名 `T<nn>_<主题>`（遵循
  `_toolkit/CLASSIFICATION.md`），更新 `trials/INDEX.md`。
- **对照文档/代码双源**：用例以 `docs/syntax/`（15 章）+ `docs/guide/` 声明的行为为契约基准；
  发现"文档宣称 vs 实际行为"差异即登记 DOC_ISSUE（代码以代码事实为准，文档漂移后续统一治理）。

### 6.4 恶意边界测试要求（用户 2026-08-20 明确，强制）

> 试用**不仅**测试文档宣称/我们认为可用的功能，还要**带着恶意测试 IBCI 的边界**。
> 具体方向（在既有批判试用精神上扩展）：

- **可能存在缺陷的逻辑**：边界条件、空值/缺省、越界、类型边界、数值极值（int 溢出/float 精度）、
  深递归/深嵌套、超长标识符/字符串、空脚本/极简脚本。
- **可能存在问题的逻辑**：并发竞态（多线程/多子环境/覆层跨根）、共享状态污染、重入、双通道/
  双轨残留、错误恢复路径（llmexcept/retry/try-except 组合）、序列化 round-trip 边界、封印/特化
  退化路径。
- **开发者没考虑到的场景**：语法组合（嵌套/交叉/正交）、模块交互（循环 import/多模块同名类/
  跨模块 LLM 解析）、宿主绑定边界（未声明成员/类型不符/绑定缺失）、隔离边界（子环境越权/
  project_root 约束/LLM 配置不继承）、异常路径的异常（retry 体内非法操作/快照污染）。
- **原则**：只记录不修复（优先确定性记录可溯源）→ 分类（KERNEL_ISSUE/BOUNDARY/DOC_ISSUE/
  LLM_BEHAVIOR/LIMIT/GUARD/HARNESS）→ 修复阶段再根因修复 + 触发用例核销。**不为规避缺陷改套件**
  （缺陷触发用例保留）。每个试用必须加死循环保护（OS 级硬超时，run_batch harness SIGKILL）。

### 6.5 阶段 C 结束后：技术文档全方位复核、更新、同步

- 全面试用结束后，对 `docs/` 做**全方位复核、更新、同步**（doc-governance Phase 0-8）：
  - 代码/行为 vs 文档一致性（`docs/syntax/` 15 章 + `docs/guide/` + `docs/howto/` + KNOWN_LIMITS）。
  - 五大地基重构后新语义是否已在文档准确反映（`llm ... llmend` 已删、LLM 可调用类、覆层、
    prompt 协议族、意图一等值、fs、值语义 §2.8/§5.10、KNOWN_LIMITS 编号已变）。
  - 试用发现的 DOC_ISSUE 全量处置；文档漂移以代码事实为准修正。
  - 单点真理 / 跨文件一致性 / 读者旅程复核（docs/README.md §三治理纪律）。

## 七、下一 session 起点与排布（按序）

1. **交接核验**（§四清单）。
2. **阶段 C VISION-3 重启**：
   a. 探测 LLM 服务 → 确认真实 LLM 可用。
   b. **大规模更新补全试用项目**：排查既有 T01-T09 用例对已删语法/旧机制的依赖，迁移到
      新语法；为五大地基全部新特性新建用例（§6.1 评估面）；更新 `trials/INDEX.md`。
   c. **真实 LLM 全面回归**（mock 层先确认，再 LLM 层）+ 压力维度扩展（§6.2）。
   d. **恶意边界测试**（§6.4，与 b/c 并行穿插）。
   e. 缺陷→根因修复→回归核销循环。
3. **阶段 C 结束后**：技术文档全方位复核、更新、同步（§6.5）+ 周期质量维护恢复
   （PT-AUDIT-1/3 + Tier B，用户裁定试用后恢复）。
4. 阶段 D（P7 类型理论 / P8 函数式 / 二层 IR）在试用稳定后启动。

## 八、执行纪律（勿忘）

- 测试唯一命令 `~/miniconda3/envs/ibci/bin/python -m pytest tests/`；基线以实跑为准。
- 全程本地 commit；**禁 push**（除非用户显式授权——本 session 25 提交等待授权）。
- 工作模式定论（NEXT_STEPS ⛔）全程适用；注释纪律（禁任务代号/历史叙述，规范编号保留）。
- 试用体系：`trials/INDEX.md` 生命周期状态机 + `_toolkit/LLM_SERVICE.md` 服务规范为单一权威。
- goal 配置习惯：`max_auto_turns` = 7；objective 按 HANDOFF §1.3 模板。
- 阶段 C 主任务若因 LLM 服务不可用受阻：先做试用项目更新补全（不依赖 LLM 的部分），
  mock 层先行，LLM 用例标 HARNESS 不误判缺陷。
