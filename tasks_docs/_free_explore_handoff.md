# _free_explore_handoff — free-explore 分支接管交接（2026-09-07 主线终版）

> **单一接管入口**。下一个 session 的 agent 从这里开始：§一 状态 → §二 已完成 →
> §三/§四 状态评估（易用性 + trial 缺陷修复）→ **§五 主线任务终版队列** → §七 环境 →
> §九 速查 → **§十 goal 配置提示（下一 agent 必读）**。
> 权威源仍是 tasks_docs 常驻文档 + `trials/INDEX.md` + git log；本文件是入口与快照。

---

## 一、分支与仓库状态

| 项 | 值 |
|----|-----|
| 分支 | `free-explore`（领先基线 b89fdc39 共 14 提交（2026-09-07 点；`git rev-list --count b89fdc39..HEAD` 复核）） |
| 提交链 | 全链见 `git log --oneline b89fdc39..HEAD`（STREAM-1 → P9a/P9b → 回接记录 → 交接重写+裁定 → 卫生 → overlay 评估 → 生成参数面评估 → 配置格式对齐评估 → 主线终版+goal 配置 → NEXT_STEPS 同步 → N2 重新定位 → N2 K1-K9 确认+主线微调） |
| 测试基线 | **3219 passed / 1 skipped**（2026-09-06/07 实跑；以实跑为准不冻结） |
| 硬约束 | **禁 push**（任何远程）；`main` / `unsafe-vibe-dev` 永不触碰；工作**维持 free-explore 分支**（合并与否/如何合并 = 用户未来决定，当前不处理，下一 agent 不做 merge 动作）；`/home/dsh/proj/ibci-trial/` 只读 |
| goal | 旧 goal（`goal-0756d638…`，自由探索版）**已退役——不要 resume**；下一 agent 按 §十 创建新 goal（主线大任务版，max 200 轮，无明确停止线，不申请审批） |
| 环境 | `.venv`（规范 recipe）/ `api_config.json`（仓库根单源，gitignored，现 SiliconFlow）/ `AGENTS.local.md`（本机事实层） |
| 未跟踪文件 | `.tmp_verify/`（P9a/P9b/P9c/P11/SEM-1 复现脚本，SEM-1 修复时复用作回归资产）/ `TEMP-35B-LLM-GUIDE.md`（旧端点指南，头部已加作废注记） |
| skills | 固定组合（code-workflow / code-quality / user-principles / design-philosophy）+ 按需（doc-governance / code-review / self-grill / code-odor） |

## 二、本 session 已完成工作（两轮）

### 轮 1（自主探索，暂停点前）

1. **全量真实 LLM 回归复跑**（10 套件 122 llm 用例，35B 共享端点）：分类全达预期
   （LLM_BEHAVIOR 项 = 端点输出非确定，非内核缺陷）；发现并修复 **KERNEL_ISSUE-STREAM-1**
   （stream_channel 放弃流 → daemon 消费线程 C 扩展内 + 解释器终结不等 daemon → SIGSEGV；
   2 并发 4/12 复现）。修复 = 流句柄生命周期闭环三层：`cancel()` 协作式截断（生成器单写者
   原则）+ producer 契约 = 生成器（fail-fast）+ atexit live 注册表 drain（有界 join，daemon
   语义不变）。设计文档 `tasks_docs/_stream_segfix.md`；验证 = +7 判别测试 + 并发门 24/24
   零段错误 + 全量零回归。已知角落（记录不修）：LLM 挂死 >2s 的 atexit 超时残留窗口。
2. **阶段 C 清场项登记**：named-model 端点泄漏 2 用例（修复方向已定案：`IBCI_TRIAL_LLM_URL`
   环境变量通道）/ T06 子目录复跑缺口 / 恶意边界 #15/#17/#19/#33 / BOUNDARY-LLM-5 裁定。
3. **暂停点紧急记录**（本文件前身：待办队列 + 恶意边界用例设计快照 + 风险注记）。

### 轮 2（用户回接指令，本轮）

1. **端点切换 SiliconFlow**（旧 `vllm.haberzero.cn` 35B 已下线）：
   - chat `Qwen/Qwen3.6-35B-A3B`（思考模型）：probe 通过（~166ms）；**双字段思考抑制实证
     有效**（顶层 `enable_thinking=false` + `chat_template_kwargs.enable_thinking=false`
     → `reasoning_content=None`、content 纯答案）；思考字段名 = `reasoning_content`
     （provider `_extract_reasoning` 兼容 `reasoning`/`reasoning_content` 两者，已核代码）。
   - embedding `Qwen/Qwen3-Embedding-0.6B`：`POST /v1/embeddings` 直连验证 ~1024 维。
     **IBCI provider 尚无 embeddings 通道** = PT-FEAT-16 实施范围。
   - 记录落点：`api_config.json`（default/qwen35 双模型 reasoning:false timeout 180）/
     `AGENTS.local.md` / `TEMP-35B-LLM-GUIDE.md` 作废注记。
2. **ibci-trial 回接**（外部试用智能体 172 轮灰盒语言自动机探索）：文档全量读取
   （14 docs + K1-K3 参考实现代码 + e01-e58 实验 + 172 轮记录）+ 逐条实测核验 +
   适配/发展方向分析。**单点记录 = `tasks_docs/_trial_intake_analysis.md`**。
3. **P9a/P9b 修复**（commit `1205a530`，+10 判别测试，全量 3219/1 零回归）：
   - **P9a** `len(dict)` 函数形态恒 0 → 根因 = `IbDict` "payload 与 fields 同一映射"
     不变量被 `_box_dict`/序列化水化两处整体替换 `fields` 破坏（IbList/IbTuple 的
     `elements` property 早已防住同型问题，IbDict 唯一例外）→ 修复 = `IbDict.fields`
     经 property 落 `payload`（机制同构，双写真相结构上不可能，两处破坏点零改动自洽）。
   - **P9b** 内联布尔比较反转（真==真→假）→ 根因 = 解析器 `binary()` 链式合并把括号
     包裹的独立比较误并入链（`(a>b)==(c>d)` 解析成 `a>b==c>d`）→ 修复 = grouping 打
     `_parenthesized` 标记，链的边界以括号为界；无括号链行为不变（四操作数链仍合并）。
4. **P9c/P11 重新定性 + 新发现登记**：P9c 真实缺口 = dict 不可 `for` 迭代（keys/items
   可用）；P11 微测试实际暴露 = **比较运算符编译期类型检查缺失**（静态 `str >= int`
   漏到运行期 `RUN_GENERIC_ERROR`）→ **新登记 `KERNEL_ISSUE-SEM-1`**（`trials/INDEX.md`）。
5. **用户裁定**：回接分析的全部建议认可——Q1-Q4 裁决落定（PT-FEAT-16 批① 实施解锁）+
   批次顺序 ①→②→③→④ + P0 三线顺序（诊断面打包 → PT-FEAT-16 → N2 设计）+ 排除项。
   裁定记录 = WORKLOG 两行 + `_trial_intake_analysis.md` 头部状态注记。

## 三、易用性项状态评估（用户点名的单独评估 ①）

> 范围：前一个 agent（阶段 E 工作）提出的易用性项（T1-T6，含"错误信息合理展示"类）
> + 本轮回接中确认的诊断面现状。**不含**本轮新增的 trial 需求（§四）。

### 3.1 阶段 E 易用性项（`tasks_docs/_next_phase_targets.md` §二）

| 项 | 内容 | 状态 | 落点 |
|----|------|------|------|
| **T1** 配置体系碎片化 | 61 份 api_config 本地副本（双写真相）→ 单源收敛 | ✅ **已落地**（批 0，2026-09-05） | `discover_config_path` 向上发现 + 仓库根单源 + 59 份副本全删 + 7 项契约测试 |
| **T2** 语言层无环境变量通道 + `idbg.env` 命名冲突 | IBCI 脚本读 OS 环境变量的唯一通道 = python 宿主绑定样板；`idbg.env()`（运行时诊断）与"环境变量"同名不同物 | ⏳ **队列中**（设计未开始；阶段 E 小项，与 ref D1 idbg 增强关联收敛） | `_next_phase_targets.md` §二 T2；恢复时读该节 + compiler 内建面 + design-philosophy 命名粒度统一 |
| **T3** trial harness 可用性 | run_one 路径拼接错误 / 快跑单用例 6 个必填参数 / 端点探测靠手工 curl | ✅ **已落地**（批 0） | run_one 路径修复 + `probe.py`（读发现配置/鉴权/模型校验/诊断退出码）+ `run_batch --probe` 预检 + `_common.find_repo_root` 单源化 |
| **T4** provider max_tokens 硬编码 | `max_tokens=4096` 硬编码，api_config 无 per-model 参数面 | ✅ **已落地**（批 0） | api_config 模型条目 `max_tokens`（正整数 fail-fast）→ ModelSpec → provider `_resolve_max_tokens`（命名模型 > 默认配置 > 内置 4096）全链路 + 6 项契约测试 |
| **T5** 文档示例无验证闭环 | docs 代码块无"与内核对账"机制（`env("KEY")` 漂移实证暴露） | ⏳ **队列中**（治理缺口；"文档示例抽取冒烟验证"机制可行性未评估） | `_next_phase_targets.md` §二 T5 |
| **T6** 次要观察 | pyproject 版本/安装面同步注记；test fixture 旧端点值合法 | ✅ 记录备查（无需处理） | `_next_phase_targets.md` §二 T6 |

### 3.2 错误信息展示面（诊断/可定位性）——已做 vs 队列中

**已有基础（完成态，保持）**：
- `15_diagnostics` 诊断码体系：PAR_/SEM_/RUN_/LLM_/DEP_ 分域码 + 每条码带
  **说明 + 修复提示** 的结构化渲染（编译错误面质量良好——P9c 复现时实测：
  `[ERROR] PAR_EXPECTED_TOKEN: ... 说明:... 修复:...`）；
- fail-fast 纪律（契约违约显式报错、不静默降级）——全系统一致；
- 编译错误定位到 ibci 源文件 + 行列（PAR/SEM 面）；
- 诊断码 catalog 登记流程 + expect-code 测试机制（BOUNDARY-LLM-4 先例）。

**缺口（全部在队列，P0 线 1"诊断面打包"覆盖——已裁定开工）**：

| 缺口 | 内容 | 状态 |
|------|------|------|
| **B1** | 运行期错误**无 ibci 源行号**（RUN_* 诊断有码无行，traceback 全 Python 帧；LLMParseError 甚至 `<LLMParseError object at 0x...>` repr 直漏） | ⏳ 线 1（P0） |
| **P2** | 解析错误**位置漂移**（错误报到错误行；一个废弃 cast 导致后面 print 报错） | ⏳ 线 1（P0） |
| **SEM-1** | 比较运算符**编译期类型检查缺失**（静态 `str >= int` 漏到运行期；新登记 `KERNEL_ISSUE-SEM-1`，复现脚本 `.tmp_verify/p11*.ibci`） | ⏳ 线 1（P0，登记于 INDEX） |
| 设计形态 | 三者打包为一个"错误定位链"设计（编译期检查覆盖审计 → 运行期错误对象携带 loc → CLI 渲染），一个设计文档 `tasks_docs/_diagnostic_design.md` | ⏳ 线 1（P0） |

**结论（回答用户问题）**：前一个 agent 提出的易用性项中，**配置体系（T1）/ harness（T3）/
max_tokens（T4）已处理完毕**；**环境变量通道（T2）/ 文档示例闭环（T5）仍在队列**（支线，
不阻塞主线）；**错误信息合理展示**（B1 源行号 / P2 位置漂移 / 编译期类型检查覆盖 /
错误对象渲染质量）——**已有诊断码体系的良好基础（码 + 说明 + 修复提示 + 编译期定位），
但运行期定位链有三个洞，全部已登记并在 P0 线 1 队列首位**（本轮已裁定，下一个开工项）。

## 四、trial 智能体缺陷与需求修复情况（用户点名的单独评估 ②）

> 试用方 = `/home/dsh/proj/ibci-trial/`（外部工作区，只读；零改动 IBCI 仓库纪律）。
> 其缺陷/需求编号：P1-P11（第一轮缺陷反馈）/ N1-N4（第二轮需求）/ A1-E2（需求表）。

### 4.1 缺陷 P1-P11（逐条：现象 → 本轮核验 → 状态）

| 编号 | 现象 | 本轮核验（free-explore @ 1205a530 实测） | 状态 |
|------|------|----------------------------------------|------|
| **P9a** | `len(dict)` 函数形态恒 0 | ✅ 复现 → **根因定位 + 修复**（IbDict payload/fields 不变量，§二 3） | **已修复**（1205a530） |
| **P9b** | 内联布尔子表达式比较反转（1 vs 1 → False） | ✅ 复现 → **根因定位 + 修复**（解析器链合并吞括号比较，§二 3） | **已修复**（1205a530） |
| **P9c** | "无 dict 键枚举" | ⚠️ **部分过期**：`d.keys()/values()/items()` 实测可用；真实缺口 = dict 不可 `for` 迭代（无 to_list） | 定性修正；for 迭代入 P2 队列（低成本） |
| **P11** | 内联 @~ 结果类型漂移 str/dict | ⚠️ **重新定性**：LHS 标注形态正常（`dict d = @~...~` → dict 实测）；其微测试（`e32x/p11_cast.ibci`）实际暴露 = 比较运算符编译期类型检查缺失 | **新登记 KERNEL_ISSUE-SEM-1**（INDEX）；入线 1 队列 |
| **P2** | 解析错误位置漂移 | 维持（试用方多轮复现）；与 B1/SEM-1 同域 | ⏳ 线 1（P0） |
| **P3** | 强制返回类型注解（`-> auto` 样板） | 维持（语言决定）：**不改**——显式注解是类型论 ISA 的承载，试用方自身机制（类型驱动归约）依赖；样板痛感的正确解 = 错误定位（线 1 覆盖"忘了注解 → 清晰 SEM 错误 + 源行"） | 状态维持（已裁定不改） |
| **P4/B1** | 运行错误无 ibci 源行号 | 维持；= 线 1 核心 | ⏳ 线 1（P0） |
| **P10** | dict/list 引用传递陷阱 | 标准语义（设计非缺陷）；`copy()/deepcopy()` 已备 | ⏳ 文档面（P2 队列：语言手册补引用语义说明） |
| **P7/P8** | 顶层行为表达式 DDG 异步派发语义 | 既有设计（lazy resolve；函数内同步）；试用方已适应（lambda 包一层） | 状态维持（文档面注记，随 B1 诊断文档顺带） |
| **P1** | 多行容器字面量尾逗号 PAR 错误 | = A3（语法易用性） | ⏳ P2 队列 |

### 4.2 需求 N1-N4（第二轮）

| 编号 | 需求 | 状态 |
|------|------|------|
| **N1** | 思考模型支持（extra_body 透传 + 空 content 确定性处理 + max_tokens 预算） | ⏳ **P1-1**（已重定性为根因项：provider 现硬编码双字段抑制 dict 进每请求且无条件发送——vendor 机器事实滞留代码层 + `reasoning: true` 请求层不可表达；并入"生成参数面批"六项——temperature/top_p/top_k/seed 命名字段 + extra_body + 硬编码归位 + `**kwargs` fail-fast + call_info 审计闭环 + 未知字段严格性，详见 `_trial_intake_analysis.md` §五 5.4/5.5） |
| **N2** | 已验证知识注册表（试用方原名"结晶注册表"为黑话，用户 2026-09-07 裁定废除；机制 = 验证过的 LLM 答案登记：确定性验证门 + 查表命中 0 调用 + append-only 更正 + 事件审计） | ✅ **方向已裁定认可；2026-09-07 用户裁定重新定位**（不以 ai 为载体 = 一等内置值类型/语言级知识子系统，`@~...~` 保持纯 LLM 语义无隐式路由）；设计文档已产出 `tasks_docs/_knowledge_registry_design.md`（取代已删的 `_n2_answer_registry.md`；**K1-K9 已按推荐确认（2026-09-07），实施就绪**） |
| **N3** | measure_freq（logprob 测量通道） | ⏸ **挂起，方向保留**（试用方自我质疑后建议挂起；e26-e28 为现成验收基线；待 embedding/知识注册表面落地后重估） |
| **N4** | finish_reason 暴露 + max_tokens 键 | ⏳ **P1 队列**（max_tokens 键 = T4 ✅ 已落地；finish_reason 暴露未做 = call_info 观测面补充，截断检测是批量管线运行细节） |

### 4.3 需求表 A1-E2（ref 需求单 + 试用方 A1-E2 表）

| 编号 | 需求 | 状态 |
|------|------|------|
| **C1** | embedding/vector 一等能力 | ✅ **PT-FEAT-16 实施解锁**（Q1-Q4 已裁定）：批① 底本 = ibci-trial `kernel_overlay/` K1-K3（33/33 契约测试、零冲突平移指引在 `ibci_kernel_changes.md`；3 处合入处理项：mock 派生文档漂移 / norm==0 兜底改显式违约 / 测试 runner 迁 pytest）；批② pre-study 检查单 C1-C15/T1-T10 就位（值语义 C5 为核心判别） |
| **C2** | 结构化 LLM 输出契约 | **收窄为文档 + 边缘补齐**（机制已存在：expected_type + llm 可调用类 + `__from_prompt__` + RUN_LLM_CALLABLE fail-fast；试用方主力模式实证可用；缺的是边缘交互文档，如 LHS 标注 × 容器返回） |
| **C3** | 用户模块路径解析完善与文档化 | ⏳ P2 队列（关联 `KERNEL_ISSUE-IMPORT-2`：锚定 project_root 语义未定案） |
| **C4** | ibci 内测试设施 | **维持现状**（试用方自包含 runner 是其零改动纪律产物，不适用我方；pytest 基建完备） |
| **B1** | 运行时错误 ibci 源行号 | ⏳ 线 1（P0，§四 4.1 已述） |
| **A3** | 多行容器尾逗号 | ⏳ P2 队列（解析器项，低成本；触及 PAR 面须全量 pytest 门） |
| **A1/A2/A4/A5/A6/B2-B7/C5-C7/D1-D3/E1-E2** | 其余 ref 需求（用户协议一等公民 / 泛型约束 / 缺省 void / 解构 / Enum 增强 / 惰性结构 / 环境对象 / 并发成熟化 / 性能内省 / idbg 增强 / CLI 导出 / ihost 完善 / save_state 覆盖 Environment） | 阶段 E 批次表内（`_next_phase_targets.md` §三，批 1-3 排布）；其中 **C5 供应商感知思考抑制 = PT-DECIDE-2**：新端点实证双字段抑制有效，缺口收窄为"后端强制思考"场景，解封重估输入已更新 |
| **D1**（idbg 增强） | 与 T2（idbg.env 命名冲突）关联收敛 | ⏳ 队列（随 T2） |

### 4.4 trial 方监测到的上游项

| 项 | 状态 |
|----|------|
| **STREAM-1**（其在途监测的段错误修复） | ✅ **已修复并验证**（751ddb5d；试用方 R45 的只读分析与本修复一致） |
| P9-P11 未修复（其 44 轮监测记录） | P9a/P9b **本轮已修复**；P9c/P11 已重新定性（§四 4.1） |
| PT-FEAT-16 无实施提交（监测期） | 本轮起实施解锁（Q1-Q4 裁定） |

### 4.5 汇总（回答用户问题）

**已修复**：P9a、P9b（含判别测试 + 全量零回归）、STREAM-1（上一轮）。
**已重新定性（原描述与真实根因有偏差，按真实根因入队）**：P9c（→ dict for 迭代缺口）、
P11（→ SEM-1 编译期类型检查缺失，新登记）。
**已裁定不改（设计决定，有依据）**：P3（显式注解维持）、P10（标准引用语义，走文档面）、
P7/P8（既有 DDG 设计，走文档面）。
**队列中（已排优先级）**：P2/B1/A3/P9c-for/N1/N4（线 1 + P1/P2 队列）、C1（PT-FEAT-16
四批，线 2）、N2（线 3 设计）、C3（P2）、C2（文档面补齐）。

## 五、主线任务终版整理（2026-09-07 用户确认收官；下一 agent 的权威队列）

> **队列性质**：完成"trial 试用者需求 + 已知近期主线"的大任务。本表是基线队列；
> **执行 agent 有权根据实际进展自主微调任务优先级与批次顺序**（工作日志记录微调理由），
> 但不得把队列外的新大任务拉入主线（新发现按 INDEX/WORKLOG 登记后归入相应批次）。
> **每项出口标准（统一）**：设计阶段文档（如适用）→ 实现 → 全量 pytest 零回归 →
> 落账（INDEX/WORKLOG/本文件）→ 该项转"完成"。同一时刻只主推一个 P0 项。

### 5.1 P0 主线（三条线，按序推进；每线可含多个批次）

| 序 | 项 | 内容 | 出口 |
|----|----|------|------|
| **P0-1** | **线 1 · 诊断面打包** | 一个设计文档 `tasks_docs/_diagnostic_design.md` 覆盖"错误定位链"三段：① 编译期类型检查覆盖审计（`KERNEL_ISSUE-SEM-1` 比较运算符起点，同类漏检面一次审完：二元运算/调用参数等）；② 运行期错误对象携带 ibci 源行列（B1；`node_to_loc` 侧表已有位置信息，断点在运行期错误路径；含 LLMParseError repr 直漏渲染）；③ 解析错误位置漂移修正（P2）。复现资产 `.tmp_verify/p11*.ibci`、`p9*.ibci` | SEM 面变更 = 语义错误集 → 全量 pytest 评估门；三形态复现脚本全转回归测试 |
| **P0-2** | **线 2 · PT-FEAT-16 四批**（Q1-Q4 已裁定） | ① 契约包+provider+配置（底本 = ibci-trial `kernel_overlay/` K1-K3 33/33，3 处合入处理项见 `_trial_intake_analysis.md` §4.2）→ ② `vector` 值类型（公理层：值语义 C5/克隆/序列化，全量评估；pre-study 检查单 C1-C15/T1-T10）→ ③ `ai` 模块面+MOCK:VEC+检索最小闭包（cosine=vector 方法面；top-k=模块面）→ ④ SiliconFlow 真实试用 | 设计文档 `_embedding_design.md`（Q1-Q4 已落裁定）+ 四批各全量零回归 + ④ 真实端点实证存档 |
| **P0-3** | **线 3 · N2 已验证知识注册表**（用户 2026-09-07 裁定废除"结晶注册表"黑话名 + 重新定位：**不以 ai 为载体、一等内置值类型/语言级子系统**） | 设计文档已产出：`tasks_docs/_knowledge_registry_design.md`（取代已删的 `_n2_answer_registry.md`；重新定位后展开——**一等内置值类型**（同 dict/vector 地位，可构造/多实例/可 save_state）而非 ai 的 4 个 API + 方法面 store/get/amend/history/keys/len + **语义不变量**（`@~...~` 永远纯 LLM、无查表隐式路由）+ 验证门机器强制（check 不纯/不透明 = 编译期 SEM，fail-fast）+ 交互矩阵 + 批次 ①公理层→②方法面+诊断域→③save_state+文档→④T 试用，**K1-K9 已按推荐确认定案，实施就绪**）。实施四批 ①公理层→②方法面+验证门+KNW_ 诊断域→③save_state+文档→④T 试用；check 函数的编译期 SEM 错误依赖 P0-1 诊断面 | 四批各全量零回归 + T 试用验收（试用方 e25 机制改写 + fail-fast 判别 + save/load 保真 + 并发读） |

### 5.2 P1（运行面；P0 三线推进间隙或其后按 agent 判断排入）

| 序 | 项 | 内容 |
|----|----|------|
| **P1-1** | **N1 生成参数面批**（重定性根因项，单设计 pass 六项） | ① 标准采样参数命名字段（temperature/top_p/top_k/seed，fail-fast 范围校验）② `extra_body` 逃生口（代码默认不发送）③ 硬编码双字段抑制 dict 迁出代码层归位 api_config.json（机器事实归位；落地后 `reasoning: true` 请求层可表达）④ `register_model **kwargs` 静默吞参 → 显式参数 + 未知参数 fail-fast ⑤ call_info 采样姿态审计闭环（每调用记录有效生成参数）⑥ 配置 model 条目未知字段严格性（静默丢弃 → fail-fast）。详见 `_trial_intake_analysis.md` §五 5.4/5.5 |
| **P1-2** | N4 finish_reason 暴露 | call_info 观测面补 `finish_reason`（截断检测 = 批量管线运行细节；与 P1-1 同链可同批） |

### 5.3 P2（易用性/能力缺口，低成本顺带项）

| 序 | 项 | 内容 |
|----|----|------|
| **P2-1** | dict 可 `for` 迭代 | P9c 真实缺口（to_list 协议覆盖 dict；keys/items 已可用） |
| **P2-2** | 多行容器尾逗号（A3） | 解析器项；触及 PAR 面须全量 pytest 门 |
| **P2-3** | named-model 端点泄漏修复 | T01 D1-07-006 / T08 D5-03 两用例 tracked 硬编码旧端点 → `IBCI_TRIAL_LLM_URL` 环境变量通道（与 `IBCI_TRIAL_LLM_KEY` 同构）+ `LLM_SERVICE.md` §五同步 |
| **P2-4** | T06 子目录复跑缺口 | 7 llm 用例 run_batch 不收集（手工 harness 复跑或收集策略扩展——涉 harness 变更需评估） |
| **P2-5**（可选） | 公开 JSON Schema 发布 | 随 P1-1 批 schema 生长后顺带（对齐 OpenCode 生态做法，编辑器校验） |

### 5.4 支线（不中断主线时介入；mock 层优先）

| 项 | 内容 |
|----|------|
| 恶意边界 #15/#17/#19 | 用例设计快照就绪（本文件 §六）；mock 层确定性，快 |
| 恶意边界 #33 | `_pending_futures` 长会话内存面（依赖 LLM-5 同子系统，随其修复后观测） |
| BOUNDARY-LLM-5 裁定收敛 | INDEX 已有补充实证；doc-governance 复核关闭或维持登记 |
| T2 环境变量通道 + idbg.env 命名冲突 | 与 ref D1（idbg 增强）关联收敛；设计未开始 |
| T5 文档示例验证闭环 | 文档代码块与内核对账机制可行性评估 |
| LLM-5 复发监视 | 用例保留，batch judge 自动监视 |
| STREAM-1 后续项 | coordinator SpawnedTask 同型风险（Tier C 专项）/ 用户层流截断 API（C6 批 3） |
| P10/P7/P8 文档面注记 | 引用语义/DDG 语义说明（随线 1 诊断文档或 doc-governance 顺带） |

### 5.5 挂起 / 封存 / 远期（不入主线，记录备查）

- **周期质量维护（PT-AUDIT-1/3 + Tier B + quality-maintenance 等全部非主线质量工作）**：
  **用户 2026-09-07 裁定解封**——解封节点 = **本次主线任务之后**（§5.1-5.4 全部项处于
  完成/挂起/裁定不做终态，即 §5.6 收敛判据成立时）→ **自主启动**（无需再等用户指令）；
- **N3 measure_freq**（logprob 通道）：挂起，方向保留（e26-e28 为验收基线；待 embedding/
  知识注册表面落地后重估）；
- **ref E1 ihost 子环境配置隔离**：scoping 设计（overlay 评估 §5.4 形态 C 的真实需求归宿）；
- PT-FEAT-6/12（工具链项）：远期；**远程 CI**：用户裁定暂不启动；**PT-SEALED-1 media**：封存；
- **PT-DECIDE-2**（供应商思考禁用）：已解封，缺口收窄为"后端强制思考"场景——P1-1 批
  落地后其重估自然闭合。

### 5.6 队列收敛判据（agent 每轮自检，非硬停止线）

队列全部项处于终态（完成 / 已登记挂起 / 裁定不做）时，主线转入**稳定维护态**
（只响应新发现/新反馈，不主动扩张范围）。在此之前，每轮自主选择下一项推进——
**队列有活，持续干**（与下一 agent 的 goal 配置一致，见 §十）。

## 六、恶意边界用例设计快照（#15/#17/#19，轮 1 探索结论，全部已核代码）

**语法/机制实证**（设计依据）：
- 用户类：auto-构造 `Box[int](42)`（字段按声明序位置参）；字段赋值 `s.value = expr`；
  枚举 `class Color(Enum): str RED = "RED"`，成员 `Color.GREEN`，`==` 身份比较可用。
- `intent_context` 全方法面（公理 `core/kernel/axioms/intent_context.py` +
  `primitive_initializer.py` §5.6 原生注册）：`intent_context()` 空构造 /
  `push(content[, tag])` / `pop()` → 渲染文本 / `fork()` / `resolve()` → 意图字符串 list
  （任意 ctx 实例的状态观测面）/ `merge` / `combine` / `clear` / `clear_inherited` /
  `use(ctx)`（替换当前作用域 = fork(ctx)，非引用）/ `get_current()` / `__to_prompt__`。
- snapshot 机制（`llm_behavior.py` vm_handle_IbLambdaExpr + `_shared.py`
  `_vm_call_fn_callable`）：定义时自由变量 `try_deep_clone` 深克隆为种子 + 意图
  `fork_intent_snapshot()` 冻结；调用时对种子再深克隆一份私有副本；`try_deep_clone`
  （`core/runtime/objects/deep_clone.py`）有 `IbIntentContext` → `fork()` 专支
  （类字段路径 = #15 目标）。
- save/load_state（ihost → HostService → `runtime_serializer.py`）：用户类实例
  `_collect_object` + qualified 类名（module 感知）；特化类 `_hydrate_specialized_class`
  （type_pool 重建 spec；注册表封印回落基类 + KDIAG_RUNTIME_SPECIALIZATION_FALLBACK 诊断，
  KNOWN_LIMITS §十 契约）；intent_context 专用 collector/wrapper；pytest 层
  （`test_host_save_state.py`）只覆盖文件布局，**值保真（特化类/枚举/意图）无覆盖 =
  #17 真实缺口**。
- overlay：编译期 `_overlay_registry` / binding_analysis 等 pass；T12 mock 层基本覆盖
  （overlay 端到端/嵌套/守卫）；#19 = overlay × (save/load_state / snapshot / llmexcept
  retry) 交互未测。

**用例设计（T15 新增，mock 层确定性）**：
- **#15 → `T15-E-M29-ctx-classfield-deepclone.ibci`**：`class Holder: intent_context ctx`；
  `Holder h = Holder(base)`（base 含 FROZEN_A）；`fn snap = snapshot -> str: h.ctx.use(h.ctx)
  后 mock LLM 调用`；定义后 `h.ctx.push("LIVE_B")`；断言 ① 快照内 merged 含 FROZEN_A
  ② 不含 LIVE_B（冻结 fork 不泄漏后定义 push）③ 原 h.ctx.resolve() 仍恰 2 项（反向隔离）。
- **#17 → `T15-E-M30-state-crossengine-types.ibci`**：save_state → 变更变量 → load_state
  → 三断言（M28 同构模式）：`Box[int](42)` 值+方法保真 / `list[Box[int]]` 容器元素保真 /
  枚举成员 `==` 身份保真（可加 combine/override 变体对抗加料）。
- **#19 → `T15-E-M31-overlay-serialization-snapshot-retry.ibci`**：overlay 覆层类 ×
  save/load_state（覆层状态 round-trip 保真）+ × snapshot（覆层自由变量捕获）+ ×
  llmexcept retry（覆层类字段快照隔离）；三子断言合一或拆三例，按 T15 命名纪律定。

## 七、环境与端点事实（速查；权威 = `AGENTS.local.md`）

- 解释器：`.venv/bin/python`（Python 3.12.x）；全量测试唯一命令 `.venv/bin/python -m pytest tests/`。
- 端点：**SiliconFlow** `https://api.siliconflow.cn/v1`（key 在 `api_config.json`，gitignored）
  = IBCI 试用端点。旧 `vllm.haberzero.cn` 的 **35B 模型已下线**；该端点本身及 27B
  （Qwen3.8-27B-NVFP4）长期保持服务（用户 2026-09-07 明确）——宿主环境事实，
  非 IBCI 试用端点。
- 模型：chat `Qwen/Qwen3.6-35B-A3B`（思考模型，双字段抑制有效，思考字段 `reasoning_content`）/
  embedding `Qwen/Qwen3-Embedding-0.6B`（IBCI 侧无通道，PT-FEAT-16 范围）。
- 命名路由用例密钥 = env `IBCI_TRIAL_LLM_KEY`；端点 URL 通道 `IBCI_TRIAL_LLM_URL`
  **尚未建立**（named-model 泄漏修复项）。
- 探测：`.venv/bin/python trials/_toolkit/probe.py` / `run_batch.py <trial> --probe`。
- 试用方环境注记（其测量纪律，重放其实验时注意）：单模型单端点标定值不可跨模型/维度迁移；
  live 向量 ~1e-3 微方差（集合级主张稳健，<0.01 边际不主张）；自参考 1.0 boost = 均值聚合
  内建先验（复现须保持同聚合方案）。

## 八、风险注记

1. **退出期崩溃孤例（未解释，监控中）**：轮 1 全量 pytest 首跑退出期 faulthandler 崩溃栈
   （`pytest/__main__` 入口帧），其后多次全量 + 24 并发全干净。按 LLM-5 处置模式登记观察：
   不建投机性修复，复现时 faulthandler 全套 dump 分析。若频率上升，优先排查 C 扩展
   （jiter/pydantic-core）终结竞态。
2. **端点可用性**：SiliconFlow 为云端共享服务，可能限流/下线。开工先 `probe.py`；失败则
   mock 组照跑（`--mock-only`），LLM 用例记 HARNESS（环境缺失）不误判缺陷。
3. **分支合并（用户 2026-09-07 裁定）**：工作**维持在 free-explore 分支**；具体合并
   与如何合并由用户未来决定，**当前不处理**（下一 agent 不做任何 merge 动作）。
   free-explore 现领先基线 9 提交（`git rev-list --count b89fdc39..HEAD` 复核）。
4. **KEY 卫生**：api_config.json / TEMP-35B-LLM-GUIDE.md 均 gitignored；tracked 文件
   不落密钥（named-model 用例走 env 通道）。
5. **既有 flaky**：`tests/runtime/test_mock_service.py::TestMockServiceHTTP::test_stats_recorded`
   偶发失败（HTTP mock 时序；stash 对照实证与本轮改动无关，两组各 4/4 全过）——全量跑遇
   单发失败先隔离重跑再定性。
6. **试用方工作区只读**：`/home/dsh/proj/ibci-trial/` 不写（其零改动纪律的镜像）；
   平移其代码时按 §五 线 2 的合入处理项走。

## 九、恢复速查

```bash
cd /home/dsh/proj/intent-behavior-code-inter
git log --oneline -5                    # 确认 free-explore 分支与提交链
.venv/bin/python -m pytest tests/ 2>&1 | tail -3   # 基线 3219/1（以实跑为准）
.venv/bin/python trials/_toolkit/probe.py          # SiliconFlow 端点活性
# goal：旧 goal（goal-0756d638…，自由探索版）已退役（pause，勿 resume）；
#   下一 agent 按 §十 配置新 goal（主线大任务版）。
# 任务入口：本文件 §五（主线终版队列；P0-1 = 第一开工项：诊断面打包设计文档）
# 权威文档：tasks_docs/NEXT_STEPS.md（主线 + 工作模式定论）/ _trial_intake_analysis.md
#   （回接单点：需求/缺陷核验 + 全部评估裁决）/ _embedding_design.md（PT-FEAT-16）
#   / trials/INDEX.md（缺陷登记）/ WORKLOG.md（裁定追溯）
```

**第一个动作**（开工时）：写 `tasks_docs/_diagnostic_design.md`（P0-1 设计文档）
——先做错误定位链现状审计（SEM-1 三形态复现 `.tmp_verify/p11*.ibci` + B1 运行错误
traceback 实证 + P2 漂移案例），对照 design-philosophy §一/§二（单一权威源/统一设计
语言）定"错误定位链"机制形态，再实施。

## 十、下一 agent 的 goal 配置提示（用户 2026-09-07 指定）

> 用途：下一个 session 的 agent 开工时创建 goal 的配置指引。**旧 goal
> （`goal-0756d638…`，"自由探索"版）已退役——不要 resume 它**；新 goal 是
> **以完成 trial 试用者需求 + 已知近期主线为主要目标的大任务**，不再是自由探索。

### 10.1 goal 目标文本（供 create_goal 使用；agent 可据实微调措辞，语义不可变）

```
主线推进：完成外部试用工程（ibci-trial）需求与已知近期主线——按
tasks_docs/_free_explore_handoff.md §五 终版队列（P0-1 诊断面打包 → P0-2
PT-FEAT-16 四批 → P0-3 N2 已验证知识注册表实施[K1-K9 已确认]；P1 生成参数面批/finish_reason；P2 易用性项；
支线 mock 层项）在 free-explore 分支自主推进 设计→实现→全量 pytest 零回归验证→落账
（WORKLOG/INDEX/handoff）闭环。每轮自主评估现状、自主决定推进哪一项并**有权微调任务
优先级与批次顺序**（§五 为基线队列非固定脚本；微调理由记入工作日志）。队列有活持续
推进——不设固定停止线；仅当 §五 6 的收敛判据成立（全部项处于完成/挂起/裁定不做终态）
时转稳定维护态。硬约束：全部工作在 free-explore 分支、只本地 commit、禁 push、不触碰
main/unsafe-vibe-dev、不写 /home/dsh/proj/ibci-trial/（只读）。
```

### 10.2 配置要求（用户指定，逐条遵守）

1. **尽可能多触发、尽可能多自主触发**：`max_goal_rounds` 设大值（建议 200，与旧 goal
   同量级）；goal 的自动延续机制是主要推进动力——每轮结束自动触发下一轮，不要主动
   pause（除非用户指示或触发硬约束冲突）。
2. **不在 goal 里留下太明确的任务停止线**：目标文本是"完成 trial 需求 + 近期主线"的
   **大任务**，不是"做完 X 即止"的短目标；队列内各批次的完成不构成 goal 完成
   （收敛判据 §五 6 是 agent 每轮的自检软判断，不是写进 goal 的硬条件）。
3. **尽可能自主执行**：自主工作循环全闭环（理解→设计质询→自主决策→实现→自反馈验证
   →自主纠错→交付自查→收尾）；能自主决断的一律自主决断并详记（只记录，不断决）。
   **设计/裁定类项**（产出设计文档 + 推荐方案）即可继续推进队列其他项，不空等——
   注意：主线 P0 三线的设计裁定**均已定案**（P0-1 范围已列 / P0-2 Q1-Q4 已裁定 /
   P0-3 K1-K9 已确认），执行中如再触及**新的**语义取舍（如公理层值语义细节、
   语义错误集扩展的边界）：按 AGENTS.md 上报阈值的"自主评估并推进"精神处理——
   能自主决断的决断 + 详记；**确实无法决断的 → 记入工作文档（含选项/推荐/影响）
   标记"待决"，转做队列其他项，交付汇报时一并陈述**；不调用 ask_user_question
   （用户不在场，调用必失败阻塞），不因此停摆。
4. **不允许申请审批/提权**（用户不在场）：不调用 ask_user_question 请求拍板、不申请
   沙箱提权；遇权限/审批壁垒 → 记录壁垒点到工作文档（含所需动作与影响），转做队列
   内其他任务，下轮再评估。
5. **skills 固定组合**：code-workflow / code-quality / user-principles /
   design-philosophy（任何任务开工前加载，分析类不豁免）；按任务类型选配其余。
6. **goal 生命周期**：创建后用 get_goal 核对 id/revision；每轮开工/收尾按 goal 机制
   推进；用户中途指示时优先响应用户（含 pause/resume/edit）。
