# WORKLOG — 关键裁定与长期约束

> 本文件只保留**仍有长期约束力的关键用户裁定**与**防止未来误解的重大方向裁定**；
> 历史完成记录与过程细节由 git 承载（`git log` 追溯）。
> 治理规则见 `tasks_docs/GOVERNANCE.md`。
>
> **书写要求**：新增/修改裁定必须按本文尾部「书写模式」模板与格式书写，保持一致。

## 一、长期约束裁定（已固化于 AGENTS.md/HANDOFF 的，此处不重复）

以下裁定已在 `AGENTS.md` 与 `tasks_docs/HANDOFF.md` §1.2 固化，WORKLOG 不复制：
禁 push / 破坏性重构授权 / 大范围破坏性重构分支政策（含 2026-08-11"零风险直接合并"
细则；2026-08-18 取消手动 cherry-pick，改为"确认低风险直接 merge 到 unsafe-vibe-dev +
merge 无误即删分支"，main 不更新不触碰）/ 自主推进偏好与上报阈值 / 工作日志纪律 /
碎片化判断基准 / "不删也不修"两档 /
subagent 仅 general agent / 决策纪律 / goal 配置习惯 / 总体规划灵活微调（2026-09-10）。

## 二、主线与方向裁定（保留追溯价值）

| 裁定 | 内容 |
|------|------|
| 架构健康性最高准则（2026-08-16） | 内核/架构体系健康性与宏观长远利益为最高准则；全量重跑与试用是对智能体的约束而非负担；理论问题清理完毕后进入下一主线。协议化重构主线（阶段 A-D）由此裁定。 |
| 文档体系正规化（2026-08-16） | 技术文档系统化重构（跟随代码事实 + 章节/讲解顺序/模块化/层次归属重整）；任务控制文档清理与八股化（GOVERNANCE 治理章程 + PENDING_TASKS 正式清单）；KNOWN_LIMITS 真实性查验与体系化；根目录清洁。**完成登记**：5 并行审计（43 文件）→ 五批修复（红线/漂移/结构）→ 全量 3006/1 零回归；LANGUAGE_DESIGN_EVOLUTION 恢复保留（审计复核：正文 1-344 为有价值规划内容，降格为演进评估参考、删除红线附录与自治豁免定位、重新登记 README 目录树与单点真理表）；协议化体系归属架构文档 03 §4.0（唯一权威）；docs/ 零日期戳/零任务编号/零断链（Phase 5 扫描实证）。 |
| 优先级原则（2026-08-08） | 架构缺陷 ≥ 强相关依赖顺序 > 小而快的独立任务 > 非紧急功能演进。"无事实用户，历史兼容不是考虑项"。 |
| 类型体系方向 v2（2026-08-13） | 类型地基根治**不拉回原始架构意图**（原始文档 §8.1 纯函数 substitute 是擦除式方向，照搬会回归已实现的运行时类型身份特性）；当前物化特化类路线（reified，C#/Kotlin 同族）正确，修的是物化路线内的实现缺陷（字符串接口扁平化/双真相/覆盖缺口）。历史文档不是权威——以架构远景+长远收益裁决。 |
| 真实试用定义（2026-08-12） | 试用 = 完整语法全面试用 + 各层面交叉/正交/多层次/多文件压力试用（略带挑刺/恶意试探边界）；**只记录不修复**（优先确定性记录可溯源）；技术手册为主要信息来源；所有试用必须加死循环保护（OS 级硬超时）。 |
| 批判性试用原则（2026-08-14） | 批判性试用应充分利用既有试用地基；以前的试用体系也要经历重跑；试用发现先记录、不查内核成因、不直接修改（非内核修改任务时）。唯一底线：不为规避缺陷改套件（缺陷触发用例保留）。 |
| 显式配置方向（2026-08-12） | LLM 配置显式优于隐式：`setup()` 去自动加载，新增 `ai.load_project_config()`（命名用户拍板）；fail-fast 保留且失败点更清晰。 |
| 用户类泛型升主线（2026-08-12） | PT-FEAT-3（`class Box[T]:`）升主线完整落地；其"泛型类必须特化使用"等守卫为语言约束（KNOWN_LIMITS §十四 #1）。 |
| 能力判定协议化口径（2026-08-16） | `__from_prompt__` 能力判定与获取口径不一致时——历史不是权威；"记录不整改"理由不成立，须整改收敛（get_from_prompt_cap 单一查询入口；结构性用户方法由 VTableParsingStrategy 职责分离，不合并）。 |
| LLM 总统一性主线（2026-08-18） | 用户定方向并两时点补充：① llm 机制重构为可调用的 llm 类（抛弃 llm 函数）；② **总统一性**——行为描述/意图注释/retry/prompt 协议族/lambda/snapshot/llm 函数全部收敛为"可调用实例 + 协议（类型类）"机制；lambda/snapshot 统一为 llm 匿名可调用类的两种捕获模式语法糖；`impl` 目标扩展至内置类型（可改写 `int` 等 `__prompt__` 系列）；retry 高阶化（行为实例也可经 impl 包装 retry）。调研/可行性/规划已产出（临时文档 `tasks_docs/_llm_callable_redesign.md`），设计定稿交下一 session。 |
| P4c llm 函数机制删除（2026-08-19 落地，决策 4 + 追加裁定执行） | `llm ... llmend` 语法与旧机制（`__sys__`/`__user__`/`__llmretry__` 段、`IbLLMFunctionDef`、`callable_kind="llm_function"`、`_LLMFunctionMixin`、`llmretry` 顶层语法糖、provider `user_sys` 槽、`llm func` llm 方法）**全链路删除、不兼容不包袱**；保留 `llmexcept`/`retry` 帧机制。**llm 可调用类直接调用形态**（P4c-1）：LLMCallable 实例 `f(args)` 经 `_dispatch_call` 路由统一装配执行（参数按位绑定、默认值惰性填充、`_finalize_invoke_result` 语义对齐），调用表达式静态类型 = 动态 any（结果类型由运行时 `expected_type` 决定）。语义演进记录：实例渲染 `<Instance of T>`（非函数契约）、`fn` 只收 lambda/函数（实例经类变量持有）、`__llmretry__` 段语义迁 `__retry__` 协议（P4d 落地）、output_hint 自动推导评估归 P4d/P5、Optional 返回由用户在装配 dict 表达。迁移面：36 测试文件 + examples + trials 12 case + docs 全面同步（08/05 重写为 llm 可调用类文档）。 |
| 环境规范与 AGENTS.md 去机器化（2026-09-02，用户拍板 R1/R2/R5） | 环境事实与共享契约分离：规范环境 recipe = venv + `pip install -e ".[dev]"`（与 CI 同构，CI 全层即 setup-python + pip，conda 在 CI 零出现）；`environment.yml` 删除，环境规格单源 = `pyproject.toml`（requires-python ≥3.10 不变，开发基线建议 3.12）；AGENTS.md §测试去机器化（删 conda 激活块/本机 env 路径/"系统 python 无依赖"状态快照，补规格权威源指针 + conftest basetemp 不变量），§编码与平台注意整节删除（CRLF/非 UTF-8/PowerShell/Windows 大小写 = 旧 Windows 机器快照，实测全仓 .md 0 CRLF、0 非 UTF-8，`.gitattributes` 已归一化），路径约定指针并入 §文档读者定位；新增本地层 `AGENTS.local.md`（gitignored，仅本机环境事实）+ §文档读者定位扩本地层例外。级联同步：README/GETTING_STARTED/00_environment（重写为 venv 流程）/run_trials/modify_llm_provider/tests README 的 conda 引用收敛 + `scripts/ci_local.sh` 删 /home/haber 硬编码改 .venv 解析 + HANDOFF §1.1 测试行。R4（wheel package-data 缺口：core/lib/prelude.ibc、core/builtin/primitives.ibci 未进 wheel，L4 smoke 不检出）用户裁定暂缓；**同日重新定性并彻底删除**——两文件为早期 OOP 底座时代遗留 IBCI 源文件（全仓零消费者：Python 内核 / trials / examples / docs 均无引用；内置模块注册集中 `core/runtime/bootstrap/builtin_modules.py`，docs 中 "prelude" 均指 Python 侧静态 Prelude 通道），`core/lib/`、`core/builtin/` 已清空删除，wheel 发布面实证齐备（ibci_modules + LICENSE 完整），`ci_local.sh` L4 发布产物层同步补齐。Python 3.11.2 venv 本机实证零回归（3185 passed / 1 skipped，与基线一致，2026-09-02 实跑）。 |
| 分支基准与真实 LLM 环境裁定（2026-09-02，用户） | 未来开发分支**始终以 `unsafe-vibe-dev` 为准**；本轮环境/文档去机器化工作因不涉及核心代码修改与功能推进而临时置于 `main`，完成后已 fast-forward 并入 `unsafe-vibe-dev`；用户显式授权 push 后已推送 `unsafe-vibe-dev` |
   至 origin，本地 main 复位 origin/main（该 2 提交由 `unsafe-vibe-dev` 承载）。**远程 CI 暂不
   启动**（保持 `workflow_dispatch`，用户裁定；本地分层验证经 `scripts/ci_local.sh`）。**本机暂不
   跑真实 LLM**（无 api_config.json）：L3 真实 LLM 层与阶段 C 真实 LLM 残留项（恶意边界未测 9 项
   等，见 trials/INDEX.md）在本机搁置，待 LLM 环境就位后恢复。**（后段已被 2026-09-05 裁定取代：
   真实 LLM 环境已就位，见下行）** |
| LLM 试用端点迁移 + 阶段 E 目标整合（2026-09-05，用户） | ① **端点迁移**：本机 LLM 试用端点切至 vLLM `localhost:8001/v1`（强制 Bearer 鉴权；**只允许 `Qwen3.6-35B-A3B`，禁止 `Qwen3.8-27B-NVFP4`**），接下来及未来所有试用均用此端点。落地：43 个 gitignored `api_config.json` 批量迁移；tracked 用例经 `IBCI_TRIAL_LLM_KEY` 环境变量 + 宿主绑定 `os.getenv` 取密钥（tracked 文件不落密钥）；`trials/_toolkit/LLM_SERVICE.md` 单一权威源重写（关键实证：顶层 `enable_thinking` 被 vLLM 静默忽略，思考抑制须走 `chat_template_kwargs` 通道，内置默认 provider 双形态发送已兼容）；命名路由双用例真实 LLM 亚秒 PASS + 全量 pytest 零回归。② **阶段 E 定向**：本 session 实证暴露项（配置体系碎片化 61 份副本/语言层无环境变量通道 + idbg.env 命名冲突/harness 路径解析脆弱/provider max_tokens 硬编码/文档示例无验证闭环——详见临时文档 `tasks_docs/_next_phase_targets.md`）+ `ref/IBCI_REQUIREMENTS.md` 灰盒愿景需求单（"全部 ibci 内、不寄生 Python"；P0 = C1 embedding/C2 结构化输出/C3 模块解析/C4 ibci 内测试/B1 源码行号/A3 容器尾逗号）整合为下一阶段主攻目标；正式总条目 = `PENDING_TASKS.md` VISION-7。 |
| embedding 立项解封 + 全自动自主运行授权（2026-09-05，用户） | ① **C1 embedding：必须、立项解封**（PT-FEAT-16，P0）——**设计纪律（用户明确）**：词嵌入不是"一种数据结构或一个库函数"，与 LLM 同等严肃对待：语言级表现形态、职责边界、承载的数据结构、系统级角色、ibci 其它全部元素与新成员的交互协议，须系统级架构设计先行（design-philosophy 全面审视 + LLM 集成先例作机制同构基准），设计文档 `tasks_docs/_embedding_design.md`。media Phase 4 封存边界切出（多模态本体保持封存，PT-SEALED-1 注记）。② **PT-DECIDE-2 解封**（重估聚焦"后端强制思考"场景）。③ 批 0 先行、ref 来源项目协同方式等其余项授权按工程经验自主推进；**进入全自动自主运行**。 |
| 批 0 执行（2026-09-05，自主推进） | ① **T1 配置单源收敛**：`discover_config_path` 向上发现（.git 仓库边界 + 就近覆盖）+ 仓库根单源 `api_config.json` + 59 份 trial 本地副本全删（内容等价或零消费者实证）+ run_one 路径解析修复；全量 pytest 3192 零回归。② **T3 harness**：probe.py 端点探测 + run_batch --probe 预检 + _common 单源化。③ **T4**：max_tokens 进 api_config 全链路。④ **清场复跑 233 例**（T01/T02/T06/T07/T08/T09）：全数达成预期分类；7 处用例断言漂移/机器特定修正；**新缺陷登记**：KERNEL_ISSUE-LLM-5（llm 可调用类声明用户类赋值约 1/6 竞态）、KERNEL_ISSUE-IMPORT-2（模块解析锚定 project_root，与 ref C3 关联，待 C3 定案）；rerun_old_suites REPO_ROOT 修复。⑤ 恶意边界 9 项未测（INDEX 清单）为批 0 剩余项，随批 1 推进。 |
| 涂抹消费语义确认 + LLM 服务文档去机器化（2026-09-05，用户） | ① **`@`/`@!` one-shot 消费语义确认**：绑定"下一条语句执行窗口"，**任何语句**（含非 LLM/非 ai 语句）都消费/清空窗口——语义一致性优先；与 `docs/syntax/09_intent_system.md` 既有文档一致（T15-E-M28 观测实证），非缺陷；语言不做强制检查，语义清晰由文档承载，消费检查由 ibci 使用者负责。② **LLM 服务文档去机器化**：`trials/_toolkit/LLM_SERVICE.md` 重写为服务无关规范（端点/模型/密钥/红线等本机事实全部移至 `AGENTS.local.md` 本地层）；run_batch 注释、run_trials、docs/trials/README、trials/INDEX 基线注记同步去机器值；`timeout` 单位明确为**秒**（默认 30s，用户问询澄清——非毫秒）。 |
| 流句柄生命周期契约 + 退出安全（2026-09-06，自主，free-explore 分支） | KERNEL_ISSUE-STREAM-1（stream_channel 放弃流 → daemon 消费线程在 C 扩展内、解释器终结不等待 daemon → SIGSEGV，2 并发 4/12 复现）：修复 = `IbStreamHandle.cancel()` 协作式截断（**生成器单写者**——CPython 对运行中生成器跨线程 `gen.close()` 抛 `ValueError: generator already executing`（实测），置标志线程不碰生成器、消费线程 in-thread close）+ **producer 契约 = 生成器**（非生成器无协作关闭协议 → 消费入口 fail-fast；provider mock 路径 `iter([...])` 同步改生成器）+ provider 流生成器 `finally` 关 HTTP 流（资源闭环）+ atexit live 注册表 drain（cancel + 有界 join 2s，daemon 语义不变：永不阻塞进程退出；live 登记先于线程启动防快速流残留泄漏）。pytest +7 判别 + 并发门 24/24 零段错误 + 全量零回归。后续：coordinator `SpawnedTask` 同型风险（阻塞外部 I/O 任务）归 Tier C 专项评估；用户层显式流截断 API 归 C6（批 3）评估。 |
| 外部试用工程（ibci-trial）回接：缺陷修复 + 需求核验 + 发展方向裁定（2026-09-06，用户指示回接 + 自主推进，free-explore 分支） | ① **端点切换**：旧 vLLM 端点下线（用户明确），切 SiliconFlow `api.siliconflow.cn`（chat `Qwen/Qwen3.6-35B-A3B` 思考模型双字段抑制实证有效 + 思考字段名 `reasoning_content`；embedding `Qwen/Qwen3-Embedding-0.6B` 直连验证 ~1024 维）——本机事实落 `AGENTS.local.md`（PT-DECIDE-2 的"后端强制思考"场景在新端点实证收窄：抑制有效，重估输入更新）。② **试用方缺陷实测核验**（微测试原样复跑 + 根因定位）：**P9a 已修复**（`IbDict` payload/fields 同一映射不变量被装箱/水化两处整体替换破坏 → `len(dict)` 函数形态恒 0；修复 = `IbDict.fields` 经 property 落 `payload`，与 `IbList`/`IbTuple` 的 `elements` property 同构的单点真理约定——双写真相结构上不可能，两处破坏点零改动自洽）；**P9b 已修复**（解析器链式合并把括号包裹的独立比较误并入链：`(a>b)==(c>d)` 解析成 `a>b==c>d`，求值语义反转；修复 = grouping 打 `_parenthesized` 标记，链的语义边界以括号为界，无括号链行为不变）——commit `1205a530`（+10 判别测试，全量 3219/1 零回归）。**P9c 定性修正**（keys/items 可用；真实缺口 = dict 不可 for 迭代）；**P11 微测试重新定性**（LHS 标注形态正常；实际暴露 = 比较运算符编译期类型检查缺失，静态 `str >= int` 漏到 `RUN_GENERIC_ERROR`）→ **新登记 `KERNEL_ISSUE-SEM-1`**（诊断面打包设计候选，与 B1/P2 同域）。③ **发展方向裁定**（单点记录 = `tasks_docs/_trial_intake_analysis.md`）：PT-FEAT-16 实施条件齐备（Q1-Q4 裁决建议：模块面并入 `ai` + 协议层独立 / 检索最小闭包 / `expected_type: vector` 不开放 / 新 `EMB_` 诊断码域；K1-K3 参考实现审查通过可平移，含 3 处合入时处理项）；**不做什么**排除项（通用数值科学计算面 / judgment 内建 / P3 显式注解维持）；残留队列 P0×3（PT-FEAT-16 实施 / N2 结晶注册表设计 / 诊断面打包）+ P1×2（N1 思考模型 / N4 finish_reason）+ P2×4 + 挂起×1（N3 logprob 方向保留）。 |
| ibci-trial 回接建议全量认可（2026-09-06，用户裁定） | 用户对回接分析（`tasks_docs/_trial_intake_analysis.md`）的全部建议拍板：① **Q1-Q4 裁定落定**（Q1 协议层独立 `embedding_protocol` 包 + 用户面并入 `ai`；Q2 cosine=vector 方法面 / 检索=模块面最小闭包不建索引；Q3 `expected_type: vector` 不开放——向量产生面单源；Q4 新 `EMB_` 诊断码域）→ **PT-FEAT-16 批① 实施解锁**；② **批次顺序** ①→②→③→④（语言用户面以最终形态出生，不做 List[float] 过渡面）；③ **P0 三线顺序**：诊断面打包（SEM-1+B1+P2 一个设计文档）→ PT-FEAT-16 四批 → N2 结晶注册表设计（先设计文档，文档内四开放问题——检索键/生命周期/存储/API 形态——二次裁决）；④ 排除项（不做通用数值面 / judgment 内建 / P3 显式注解维持 / 不复制试用方 runner）认可。主线任务入口 = `tasks_docs/_free_explore_handoff.md`。 |
| 收官三条裁定（2026-09-07，用户） | ① **分支**：工作维持在 free-explore；合并与否/如何合并由用户未来决定，当前不处理（下一 agent 不做 merge 动作）。② **周期质量维护等全部非主线质量工作解封**：触发节点 = 本次主线任务完成后（handoff §5.6 收敛判据成立）→ 自主启动，无需再等用户指令。③ **N2 命名与展开**：用户裁定废除"结晶注册表/crystallize"黑话名（平实名 = "已验证知识注册表"）；要求全量设计问题展开供确认——已产出设计文档 `tasks_docs/_n2_answer_registry.md`（平实说明 + 11 项设计问题逐问推荐：命名/API 形态/验证门机器强制[编译期 SEM]/路由形态[a 显式组合 vs b 引擎层路由，v1 推荐 a，与试用方原始强调存在分歧提请确认]/键纪律/append-only 更正 + 强制理由/事件序号审计/save_state 纳入 + 单写者并发/错误面与诊断码域/call_info 边界/mock 模式/v1 范围总括）；**待用户确认后进入实施**。  注：该文档后于同日经用户裁定重新定位废弃，由 `_knowledge_registry_design.md` 取代（见下行）。 |
| **N2 重新定位裁定**（2026-09-07，用户） | 用户裁定推翻 N2 设计文档（`_n2_answer_registry.md`）的"ai 模块载体"定位，三点硬约束：① **不以 `ai` 模块为载体**——ai 保持模型 I/O 面纯粹性，知识存储面不得污染 LLM 调用机制的一致性与纯粹性；② **行为描述语句（`@~...~`）语义 = 纯 LLM 调用行为**——知识存储的隐形判断（引擎路由/查表短路）永远不得进入 LLM 语句语义（原 Q3 方案 b 引擎层路由**原则性否决**）；③ 本机制是**语言学层面**问题（知识存储 ≈ 数据库层面机制），要求与 embedding（PT-FEAT-16）同级系统设计（建模/成体系实现/与既有组件有机交互/地位/合理使用/易用性）。已重新产出设计文档 `tasks_docs/_knowledge_registry_design.md`（**一等内置值类型**建模[同 dict/vector 地位，可构造/多实例/可 save_state] + 方法面 store/get/amend/history/keys/len + 验证门机器强制[check 不纯/不透明 fn 值 = 编译期 SEM，fail-fast 不做运行期探测] + 语义不变量 + 交互矩阵[snapshot=深克隆/save_state=自动值语义/llmexcept 无交互/overlay 不覆盖/mock=真实] + 批次 ①公理层→②方法面+诊断域→③save_state+文档→④T 试用）；**待用户确认 K1-K9**（K1 类型命名[knowledge 推荐] / K2 方法动词族 / K3 类型形态[一等内置值类型 vs stdlib 库类] / K4 诊断码域[独立域推荐] / K5-K9 验证门·更正·审计·取回·并发，推荐沿用旧文档）。 |
| **N2 K1-K9 全量确认 + 主线微调**（2026-09-07，用户） | 用户确认 N2 设计文档（`_knowledge_registry_design.md`）K1-K9 全部按推荐：**类型 = `knowledge`**（机制平实名定案 = 已验证知识注册表，各文档同步改名）/ 方法面 = store/get/amend/history/keys/len / 形态 = 一等内置值类型（公理层）/ 诊断域 = `KNW_` 独立域 / K5-K9 沿用 → **P0-3 转为实施线**（批次 ①公理层→②方法面+验证门→③save_state+文档→④T 试用，实施就绪，线内无用户决策点）。主线规划微调：P0 三线顺序维持（P0-1 诊断面 → P0-2 PT-FEAT-16 → P0-3 N2 实施），P0-3 出口标准 = 四批各全量零回归 + T 试用验收；交接文档（handoff §5.1/§4.2/§10.1 goal 文本）已同步。 |
| **任务规划自由 + 试用者需求恒高优先**（2026-09-07，用户指示） | 用户明确：① 主线顺序可微调——下一 agent 获**相当程度的自由任务规划权**，可基于实际执行、实时代码分析与开发进度状态自主微调进度顺序/优先级/批次划分（§五 为基线队列非固定脚本，调整理由记工作日志，不得把队列外新大任务拉入主线）；② **恒高优先原则：来自真实试用者（ibci-trial 反馈/早期试用者质询）的需求始终是优先处理的高优先级选项**——自由微调不得系统性地把试用者真实需求排到自研/卫生项之后，冲突时试用者需求优先。已同步 handoff §五 0（队列性质 + 恒高优先原则）/ §10.1（goal 文本内嵌两条款）/ §九（第一动作标注默认可调整）。 |
| **Rust 内核替换方向**（2026-09-10，用户） | ibci 主工程最耗时/最重负担部分（实测定性 = **VM 执行层**：40k 迭代微基准 ~1.1s / 24M Python 函数调用，每步 isinstance/typing/inspect 反射 + ast_view 包装 + 侧表查询开销主导；全量套件 114s 中 runtime 层 38% 即解释器 CPU）改用 Rust 实现，编译为 Python 可直接访问形态（pyo3），整合进 ibci——保持 Python 灵活性 + Rust 性能 + 线程真并行（执行期释放 GIL，解除 `task_scheduler` 既有文档化约束"只为 LLM IO 并发"）。**双内核纪律（用户明确）**：Python 内核**保留不删**，实验阶段继续以 Python 侧做灵活修改（一等实验内核，非过渡残留）；内核选择显式（无静默回退，fail-fast 一致）；语言语义单点真理不变（公理 + contracts 层语义红线为门）；差分等价 harness（双内核同输入输出比对）为常设交付物。分阶段：① 构建链 + 等价 harness → ② Rust 前端（lexer/parser/semantic，纯 CPU 高频、契约最清晰）→ ③ Rust 执行核心（CPS dispatch 表 43 节点移植，主战场）→ ④ 并发解除（task_scheduler 从 IO-only 升 CPU+IO）。基线数据（2026-09-10 实测，供替换后对比）：全量 main ~45s / dev ~114s（e2e 44% / runtime 38% / contracts 9% / compliance 7% / compiler 1.2%）；40k 迭代循环 ~1.1s；82KB 脚本编译 <0.2s。 |
| **全量 pytest 使用策略临时调整**（2026-09-10，用户） | 全量重跑代价较大（dev ~114s）且 Rust 内核替换期改动频繁 → 临时策略（**生效至 Rust 内核替换结束且测试速度显著提高**）：单任务默认验证 = 受影响子集 + smoke 子集（`tests/contracts` + `tests/compiler`，~11s 纯进程内无子进程）；全量 pytest 仅 ① merge/放行门（硬规则不变）② 公理层或语义错误集变更（红线不变）③ 阶段边界/里程碑 ④ 开新分支前。单点真理 = AGENTS.md §测试（本次同步：AGENTS.md §测试 + P5 / NEXT_STEPS 基线锚点 / code-workflow P4 / code-review P4；quality-maintenance 窗口级全量与 user-principles 放行门表述不变）。重估触发 = Rust 内核替换结束且全量耗时显著降低后重新评估默认验证策略。 |

## 三、重大方向决策记录（防止未来误解）

- **分支政策更新（2026-08-18，用户明确）**：**取消"独立分支禁止直接合并 + 手动 cherry-pick
  单独更新 unsafe-vibe-dev"流程**，改为：**确认低风险（全量 pytest 零回归 + 复核放行，无
  对外契约/架构级风险）后可直接 merge 到 unsafe-vibe-dev；merge 无误后直接删除无用分支**
  （除 main 与 unsafe-vibe-dev 外不长期保留分支，短期工作分支合并即删）；main 不更新不触碰。
  同日完成分支清理：`exp/unify-f5` 的两个调研/决策文档提交（0cb9264f/c6bfdc45）fast-forward
  并入 unsafe-vibe-dev，全部 31 个 `exp/*` 分支删除，本地仅剩 main + unsafe-vibe-dev。
  已同步 AGENTS.md / HANDOFF.md / code-workflow / user-principles / WORKLOG §一。
- **协议化重构（2026-08-16，exp/protocol-kernel → unsafe-vibe-dev 直接合并）**：
  协议注册表（ProtocolDef/Registry）为能力判定单一权威；普通函数与 LLM 函数全链路
  统一；retroactive implementation（impl 可携带方法体）。合并前 116 例真实 LLM 复跑
  分类与基线逐例一致，用户授权直接合并。设计要点固化于架构文档与交接记录。
- **阶段 A-D（2026-08-16，本 session）**：OOP 侧协议化（receive dunder 注册表化）、
  双轨收敛（self 形态统一/特化身份结构化/成员单一权威/auto-init 声明化/预评估诊断）、
  判定链双协议化（协议条目判定声明数据驱动 satisfies）、KNOWN_LIMITS 26 节终判。
  设计决策 D1-D7/B1-D1/B2-D1~D4 记录于临时设计文档（已随临时文档清理，git 承载）。
- **文档体系重构（2026-08-16，本任务）**：见 `tasks_docs/GOVERNANCE.md` 治理章程与
  `docs/` 重构记录（git）。
- **LLM 调用层插件化 / 供应商无关中间层（2026-08-17，exp/llm-providerization →
  unsafe-vibe-dev 手动 cherry-pick）**：内核只产出结构化 `LLMCallRequest` 委托给可
  插拔 `LLMProvider`；系统提示词组装（推荐模板）、思考抑制/探测、api_config.json
  书写格式全部下沉为可自定义 provider/ConfigSourceAdapter。移除旧 `ILLMProvider`
  标量协议死代码。设计要点固化于 `docs/architecture/01_principles.md` §3.7 与
  提交记录。验证：全量 pytest 3027 pass + T09 真实 LLM 8/8 PASS。
- **Provider 层分离（近期主线）+ IBCI 原生宿主绑定（远期愿景）· 两段式（2026-08-17，规划交接阶段）**：
  近期聚焦 LLM provider 层分离彻底完成（当前 Python 源码分发，近期不开放语言级自定义 API，
  需自定义的用户改内核 provider 文件 `ibci_modules/ibci_ai/provider_impl.py`）；远期才推进
  "抛弃 Python `_spec.py` 插件思路、用户 IBCI 层原生绑定 Python 内容"（宿主导入 + 类型/协议/impl
  绑定 + 插件体系重构 + 内核自举 + 缓存/JIT）。总路线图见 `tasks_docs/ROADMAP_NATIVE_BINDING.md`
  （近期 R0-R2 / 远期 F0-F5 / 关键裁决点；**已随 R0-R2 + F0-F5 完成删除，git 承载**）。触发背景：深度调研确认 `box()` 已能包装任意
  Python 对象/可调用，但 `import X` 与 `impl` 目前受 `_spec.py`/本模块用户类限制；近期先做对
  provider 解耦、为远期留位。
- **近期主线 R0-R2 完成（2026-08-17，exp/provider-decouple-r1 → unsafe-vibe-dev 零风险直接合并）**：
  近期分发形态确立 = 自定义 LLM 底层 = 修改/替换 `ibci_modules/ibci_ai/provider_impl.py`
  （`RecommendedProvider`，纯 provider，kernel-free 可整文件替换；宿主 `core.py` 仅 IBCI 胶水，
  内外结构 `AIPlugin(RecommendedProvider, IbStatefulPlugin)`）；MOCK 哨兵下沉
  `core/base/llm_protocol.llm_call`（单一权威源，kernel 消费者改从 base 导入）；kernel-free
  `config_normalize.py` 收拢默认常量与 to_llm_config 归一；provider 失败契约统一 RuntimeError
  （唯一行为差异：`_init_client` 配置缺失错误类 InterpreterError→RuntimeError，已记录）。
  接口位收敛口径：`LLMCallRequest.thinking_mode` 保持"契约字段存在、推荐实现不读"，推为远期
  F4 供应商字段映射位；`ConfigSourceAdapter` 不加注册入口（推荐默认适配器整文件替换路径）；
  不新增语言级注册 API。设计要点固化于 `docs/howto/modify_llm_provider.md` +
  `docs/architecture/01_principles.md` §3.7 + 路线图 §五。验证：全量 pytest 3027 pass +
  独立复核放行（probe 启发式 P1 修复 + 字节级二次验证）。远期 F0-F5 接口位已留、无返工债务。
- **远期主线 F0 完成（2026-08-17，exp/native-binding-f0 → unsafe-vibe-dev 零风险直接合并）**：
  Native Binding 地基验证——实证 `box` 裸 Python 模块 + 手动 vtable 绑定成员 + receive 调用
  可行（内核 API）；设计底稿 `docs/architecture/01_native_host_binding.md`。**裁决点 1（宿主
  绑定语法形态）定稿 = `import python "pkg" as lib`**（复用既有 import 形态 + `python` 伪模块
  + 字符串模块名），理由：统一设计语言（import 已承载"引入外部内容"）/ 机制同构（复用
  parser→scheduler→VM→module_manager 管线）/ 语义区分（python 伪模块标识宿主空间）/
  无外部用户（全新语法零迁移成本，风险可控自主决策）。裁决点 2（宿主导入类型 = 一等类型，
  复用 Provenance.EXTERNAL_MODULE）、3（成员绑定 = 显式声明式、非自动穿透）定方向。
- **远期主线 F1 完成（2026-08-17，exp/native-binding-f1 → unsafe-vibe-dev 零风险直接合并）**：
  宿主导入一等语法 `import python "pkg" as lib: bind ...` + 用户类持有 native。全链路实现
  （AST IbHostImport/IbHostBinding + bind 关键字 + parser 宿主 import/bind 块 + 依赖扫描跳过
  + scheduler 合成宿主模块 spec/注入 lib 符号 + 语义符号绑定 + module_manager import_host_module
  + vm_handle_IbHostImport）。**显式声明式绑定**：成员访问强制经 vtable/whitelist 门控，契约外
  fail-fast；bind 签名编译期类型检查；用户 IBCI 类 `any` 字段持 native。**单一权威源提取**：
  `_annotation_utils.annotation_to_typeref`（AST→TypeRef，自 symbol_collection_pass）与
  `proxy.create_proxy`（unbox→调→box，自 loader._validate_and_bind）供插件/宿主共用，消除双真相。
  验证：e2e（sqrt=4.0/pi/pow=1024.0/用户类=5.0/磁盘文件 rehydrate/跨模块=7.0/无 asname=4.0）；
  负样本（未声明成员 fail-fast、绑定缺失成员报错、编译期类型检查 SEM_TYPE_MISMATCH）；全量
  pytest 3041 passed / 1 skipped（新增 tests/runtime/test_host_binding.py 10 项）。
  **F1 独立复核（subagent a8fc712b）**：核心红线（禁双通道/兜底/历史包袱）干净，无阻塞性放行
  障碍。修复中 severity #1（import python 误伤真实模块——加 peek(1)==STRING 守卫）+ 低 severity
  #3/#4/#5/#7/#8/#9/#10（strip 死代码删、descriptor type_ref 同步、序列化缺节点 fail-fast、
  _spec.py 硬编码消息、重复 bind SEM_REDEFINITION、param _loc、类型检查 pass visit_IbHostImport）。
  设计取舍记录：#2（未声明成员编译期静默降级 any，与既有 import 一致，F2 再评估）、#6（宿主
  import 不传 registry_id，裸模块进程级单例低风险）。
- **远期主线 F2 完成（2026-08-17，exp/native-binding-f2 → unsafe-vibe-dev 零风险直接合并，65414738）**：
  协议/impl 扩展到宿主类型——bind class 宿主类型绑定 + impl 目标限制解除。**语法定稿**：
  `bind class Name: <嵌套 bind 成员>` 块形式 + `bind class Name -> any` 简写；成员表 =
  宿主声明 + impl 补充并集；impl provenance 放行 EXTERNAL_MODULE、拒绝 KERNEL_NATIVE。
  **编译期**：scheduler `_inject_host_class` 注册一等类型 EXTERNAL_MODULE CLASS（模块限定）+
  合成 owned_scope（宿主类无 AST 作用域，impl 注入需要）；协议满足 = 编译期静态 spec 判定
  （bind 声明 + impl 补充并集），零运行期改动。**运行期**：HostClassBinding(IbClass) 恒走
  instantiate（裸 Python 类构造）+ per-instance vtable（bind 方法 = create_proxy 绑定方法）+
  whitelist（bind 属性）；impl 方法经 IbNativeObject._dispatch_getattr 类方法回落 →
  IbBoundMethod（注入 receiver）；bind 方法返回 py_class 实例时重包装保持一等类型。
  **F2 独立复核（subagent b228d4fd）整改闭环**：B1（回落加 isinstance(HostClassBinding) 门控——
  实证为误诊，pre-F2 父提交 j.toString 经 Object 公理路径同样泄露；gate 保留为机制隔离）；
  M1（bind vs impl 同名编译期未拦截——宿主类合成 owned_scope 为空表，冲突检查只查符号表；
  修复：visit_IbImplDef 冲突判定改以权威成员面 spec.members 为准 SEM_REDEFINITION +
  bind 块内重复绑定同样 fail-fast，新增 3 回归测试）；M2（instantiate 内联拆箱 →
  base.unbox_for_native_call 单一权威含可调用透传，proxy/host_class 共用）；
  L1（UID 内联拼接 → uid.py helper）、L2（STAGE5/VM import 重复+错误类型漂移 →
  module_manager.import_host_py_module 单一入口）、L3（getattr 能力探测 →
  isinstance(IbNativeObject) 协议化判别）、L4（属性实例属性类级误拒已修，queue.Queue 回归）、
  L5（POSITIONAL_OR_KEYWORD 散落记录为已知限制，随 F3 统一绑定面收敛）。
  验证：全量 pytest 3053 passed / 1 skipped 零回归。测试
  `tests/runtime/test_host_binding.py`（F1 10 + F2 18）。
- **远期主线 F3 定稿 + F3-1 完成（2026-08-18，exp/plugin-refactor-f3）**：
  **F3 目标** = 废弃 Python 侧 `_spec.py` 磁盘发现/加载通道、不保留双通道，用户侧扩展
  唯一边 = 宿主绑定 bind。**F3 定稿决策**：内置模块全部内联 TypeDef 字面量集中
  `core/runtime/bootstrap/builtin_modules.py`（`BUILTIN_MODULE_SPECS`，内核原生 5 +
  工具 5 + file，file 自 engine.py 挪入），Engine 构造期一次注册全部含实现；工具插件
  实现不改（探针 A1：类实例路径可行，仅 bind 模块成员路径需模块级函数）；
  F3-0（bind 默认参数语法）**裁定跳过**——默认值放 .ibci 包装层（IBCI 用户函数本支持
  默认参数），bind 语法零改动；工具库归宿收敛为第三态「内联 spec 的内置模块」
  （保 `import math` 全兼容，bind-based IBCI 标准库推迟 F5 内核自举评估）。
  **F3-1 落地决策**：文件/函数重命名（`kernel_native_modules.py` → `builtin_modules.py`、
  `register_kernel_native_modules` → `register_builtin_modules`——职责从"内核原生 5"扩展
  为"全部内置模块"，命名同步，design-philosophy §八）；loader 环 2 跳过构造期已注册
  实现模块（消除"环 1 绑定 + 环 2 再建实例重绑"双绑定，即 F3-2 删除环 2 的终点语义
  提前落地）；去除冗余显式 `reserve_kernel_native_name`（`register_module` 对 KERNEL_NATIVE
  provenance 元数据已内建自动 reserve，机制同构）；测试迁移（`test_kernel_native_modules.py`
  → `test_builtin_modules.py` 含结构契约断言；`test_idbg.py` 改断言内联 spec；
  SDK `test_check_plugin.py` 迁移至 F3 语义——ibci_modules 安装包不再算用户插件目录）。
  验证：结构等价探针（9 模块字面量 vs 旧 discovery 路径逐字段比对等价，_spec.py 删除前
  运行）+ 全量 pytest 3056 passed / 1 skipped 零回归。设计要点固化于
  `docs/architecture/01_native_host_binding.md` §3.4 与 07_kernel_native_modules.md（F3 落地决策）。
  遗留：discovery/auto_discovery/main.py --plugin/SDK _spec 面删除 = F3-2；测试/
  examples/trials/docs 迁移 = F3-3。
- **F3-2 完成（2026-08-18，exp/plugin-refactor-f3）**：磁盘插件发现/加载双通道彻底铲除。
  **删除面**：`core/runtime/module_system/discovery.py` + `core/extension/auto_discovery.py`
  （ModuleDiscoveryService/AutoDiscoveryService）；loader 环 2（磁盘扫描 + create_implementation
  实例化 + 二次绑定），`load_and_register_all` 收敛为仅对已注册实现做环 1 契约绑定；
  插件搜索路径配置面（`IbciConfig` plugin_paths/global_plugin 整模块 `core/kernel/config.py`
  删除、`ProjectDetector.get_plugin_paths` 嗅探、`inherited_plugin_paths`/
  `inherited_global_plugin` 继承透传）；main.py `--plugin`/`--no-sniff`/`load_external_plugins`；
  `engine.register_native_module` API（唯一消费者即 main.py）；SDK `ibci_sdk/` 整包
  （gen_spec/check 为写/查 _spec.py 插件工具，F3 后无场景）；`__ibcext_axiom__` 死协议
  （engine 公理加载面）；`core/extension/spec_builder.py`（SpecBuilder/ClassSpecBuilder
  零消费者死代码）；幽灵诊断码 `KDIAG_POLICY_MODULE_NO_EXPORT`（唯一发射点为 loader 环 2，
  从 codes.py/catalog/docs 一并删除）。**Engine 签名简化**为 `IBCIEngine(root_dir=...)`
  单一参数（auto_sniff/inherited_* 移除；41 处测试机械迁移）。**隔离超时测试稳定化**：
  `test_timeout_raises_when_child_exceeds_deadline` 由"启动耗时 > 1ms"脆弱墙钟假设改为
  子任务先 sleep 再返回——F3 移除插件发现使子引擎启动更快使原假设偶发失效，追踪根因
  修正而非 flaky 搪塞。验证：全量 pytest 零回归；幽灵码清除经 test_diagnostic_catalog
  CAT-7 佐证。遗留：examples/trials/docs 迁移 = F3-3；_spec 主题残留扫描 = F3-4。
- **F3-3 + F3-4 完成，F3 全部落地（2026-08-18，exp/plugin-refactor-f3）**：
  **F3-3（examples/trials/docs 迁移，subagent 1ba1f995 执行 + 本 session 复核）**：
  删除 `examples/plugins_demo/`、`isolation_demo/sub_project/plugins/`、
  `trials/T01_llm_full/plugins/`（演示/试用已删除的用户插件 `_spec.py` 系统）；
  `trials/cases/D2-21-plugin.ibci` 改写为宿主绑定演示（`import python "math" as m:
  bind sqrt/pow`，经 main.py 实跑通过）；旧 write_user_plugin howto 删除 →
  新建 `docs/howto/extend_with_host_binding.md`（用户扩展 howto 换宿主绑定语义）；
  `docs/subsystems/04_plugin_system.md` 重写为"内置模块系统与宿主绑定"；01_principles/
  06_path_system（删插件发现优先级章节）/07_kernel_native_modules/11_modules
  （§11.9 改宿主绑定指针）/KNOWN_LIMITS §十九/README 等 20+ 文档更新到 F3 事实。
  **F3-4（残留扫描 + 全量验证）**：`_spec.py` 物理文件清零；discovery/auto_sniff/
  plugin_paths/ibci_sdk/SpecBuilder 等功能性引用全零；剩余 `_spec.py` 均为历史说明
  注释（顺手清除 ibci_ai/core.py 与 builtin_modules.py docstring 过时引用）。全量
  pytest 2946 passed / 1 skipped 零回归。**F3 完整度**：三阶段放行门全过，达分支合并
  细则"零风险直接合并 unsafe-vibe-dev"标准（全量 pytest 零回归 + F3-1 结构探针 +
  F3-2/F3-3 独立 subagent 复核 + F3-4 残留扫描，无对外契约/架构级风险）——仍禁
  push，合并须用户授权。
- **F3 低风险直接合并 unsafe-vibe-dev 完成（2026-08-18，用户授权）**：用户确认低风险后
  授权直接合并。`unsafe-vibe-dev` 与 `exp/plugin-refactor-f3` 分叉点为 3ce67993，二者
  无分歧 → 纯 fast-forward 合并（3ce67993..3261200e，115 文件 +1529/-4278），两分支同
  指向 3261200e。合并后全量 pytest 2946 passed / 1 skipped 零回归。F3 插件体系重构即
  此合入主开发分支（未 push；禁 push 硬原则不解除。合并是用户授权的单次动作，不改变
  "合并/推送皆须用户授权"原则——用户本次仅授权 F3 低风险合并，未授权后续自动合并或 push）。
- **F4 授权推翻"不新增语言级注册 API"（2026-08-18，exp/provider-bind-f4，用户拍板）**：
  F4（Provider 自定义经宿主绑定统一）推进时发现其与 R0-R2 已固化裁定冲突——R0-R2 明确
  "不新增语言级注册 API / 不提前实现用户入口"、01_principles §3.7 把 bind-based provider
  统一定为"远期、不提前实现"。向用户呈报该设计分叉（F4 推迟到 F5 vs 现在做 F4 授权推翻；
  附 F3 先例 bind-based 用户库推迟 F5）。**用户选择"现在做 F4（授权推翻不新增注册 API）"**
  ——本次新增 bind-based provider 注册出口/api、统一 F4，推翻 R0-R2"不新增语言级注册
  API"裁定。此为有拍板依据的破坏性/对外契约变更授权。F4 临时设计底稿（已随 F4
  完成删除，决策沉 docs/architecture/01_principles.md §3.7 + howto）。
- **F4 完成（2026-08-18，exp/provider-bind-f4）**：Provider 自定义经宿主绑定统一。
  **机制**：内核 LLM 执行器 `llm_callback` 每次从 capability_registry 惰性读
  `llm_provider` 能力；用户经 `import python "<mod>" as lib: bind provider` 声明实现
  `LLMProvider` 契约的 provider，`ai.set_provider(lib.provider)` 以 HIGH 优先级注册为
  激活 provider（覆盖内置默认 `RecommendedProvider`）——运行期切换立即生效，不改内核
  LLM 执行器架构。SPIKE 发现：`CapabilityRegistry.replace()` 不能同等优先级换 primary
  （只移除同 plugin_id），须以 `HIGH` 优先级 `register()`（能力表优先级主选，单一
  primary、非双通道）。**实现**：`ai.set_provider`（契约校验 fail-fast：缺
  call/stream/get_retry/is_auto_intent_injection_enabled/get_current_call_info 即拒）；
  内置 spec 加 `set_provider` 成员。**拆除 R 期临时态**：`provider_impl.py` 降为内置
  默认实现（不手动改）；`docs/howto/modify_llm_provider.md` 由"改 provider_impl.py"
  改写为宿主绑定通道；01_principles §3.7"自定义分两段/不提前实现用户入口"改为
  "自定义已统一（F4）"。**验证**：全量 pytest 2956 passed / 1 skipped 零回归 +
  `tests/e2e/test_provider_host_binding.py`（自定义 provider 被内核实际调用非 stub +
  契约 fail-fast + 默认 provider 保持）。设计底稿沉 docs/architecture/01_principles.md
  §3.7 + docs/howto/modify_llm_provider.md。
- **F4 低风险直接合并 unsafe-vibe-dev 完成（2026-08-18，用户"请继续推进"授权）**：
  用户对上轮汇报（含"是否让我合并 F4 到 unsafe-vibe-dev"第一步）回复"请开始继续推进"，
  结合 F3 的"确认低风险后允许直接合并"既定授权模式，判定为合并默许。`unsafe-vibe-dev`
  未动，F4 分支是其上 3 个提交（bcc416aa/28049708/28df3dae）→ 纯 fast-forward
  （3261200e..28df3dae，9 文件 +371/-105），两分支同点 28df3dae。合并后全量 pytest
  2956 passed / 1 skipped 零回归（已在 F4 分支验证同提交）。此后主线进入 F5。
- **F5 评估决策（2026-08-18，exp/unify-f5；用户指示远期 pending 规划即可，不展开设计）**：
  F0-F4 落地后对 F5 各候选评估，全部**列为远期 pending 规划**（进 roadmap，不当前实现，不展开详细设计）：
  - **档 A 缓存预编译**：当前引擎为"单次执行"模型（每引擎编一次、execute 后封印），跨
    编译产物缓存的缓存失效/序列化保真/沙箱边界风险 > 当前收益 → pending（未来出现
    同一项目多次编译/复用消费形态（REPL/watch/服务常驻）再评估）。
  - **内核自举（内置契约再表达为 bind 声明）**：bind 为运行时用户侧机制，与内核构造期
    需求时序矛盾 → pending（保持 builtin_modules.py 字面量为内置契约单一权威）。
  - **档 B 真 JIT / 隔离改造 / 反射能力**：无当前可验证收益/消费方 → pending 规划。
  F5 当前聚焦可落地的文档/架构收敛（见 F5-2）。
  **F5-2 文档/架构收敛**：docs/README 目录树与 docs/ 实际文件一致（校验无悬空/遗漏）；
  修正 `09_observability.md` 示例残留的 `auto_sniff` 参数。发现 **`IsolationPolicy.inherit_plugins`
  为 F3 后的孤儿字段**（engine 已删 inherited_plugin_paths 传播机制，core/tests 零消费者）——
  因属公开策略字段（to_dict/from_dict/工厂 + 序列化契约），按其 public 面与用户 F5 pending 指示，
  记录为本阶段收敛项、留待单独清理（不仓促动契约）。
- **F5 低风险直接合并 unsafe-vibe-dev 完成（2026-08-18，用户"一并合入"授权）**：
  用户确认把 `exp/unify-f5`（F5 评估 + 文档规整）一并合入。dev 未动（在 F4 合并点
  28df3dae），F5 分支是其上 4 个提交（7231461e/bb45a6b7/7857cc51/d1af8390）→ 纯
  fast-forward（28df3dae..d1af8390，8 文件 +72/-232），两分支同点。合并后全量 pytest
  2956 passed / 1 skipped（该提交已在 F5 分支验证）。
- **主线下一条：彻底大改 llm 函数机制（2026-08-18，用户定方向；调研/需求确定留给下一 session）**：
  用户决定**抛弃"llm 函数"概念**，重新设计为**可调用的 llm 类**（面向对象形态承载
  LLM 调用/意图/llmexcept 等语义）。本轮仅确立方向并写入任务控制文档，不做调研/实现；
  具体调研与需求确定由下一 session 承接（见 NEXT_STEPS/ROADMAP 新主线条目）。
- **五大地基改造调研 + 总路线（2026-08-18，本 session，只读调研无代码改动）**：完成交接清单
  `_llm_callable_redesign.md` §6bis.3 六项补充调研全部点（内置类型协议方法表机制形态/
  lambda-snapshot 捕获策略参数化落点/retry 协议化边界/行为语句 vs llm 可调用类统一点/
  能力公理→协议满足收敛/prompt 协议族类型类化），扩展为五大地基（函数式/类型类/类型理论/
  高阶函数/协议化）现状评估（评分 3-3.5/5）与总路线 P1-P9。**关键调研结论（设计定稿输入）**：
  ① 内置类型协议方法表三选一落点（spec 注入+vtable 覆写 / per-IbClass 协议方法表 /
  `_dispatch_<dunder>` 钩子），核心障碍 = satisfies_protocol 读 spec.members vs receive 读
  vtable 双表不同步（D3）；② capture_mode 值层已参数化、类型层隐形，改造面 = 运行时闭包
  机制三处（vm_handle_IbLambdaExpr/_vm_call_fn_callable/bind_behavior_closure）+ snapshot
  意图快照文档漂移（D8，纯 snapshot lambda 不冻结意图与文档不符）；③ retry 收敛边界 = 保留
  LLMExceptFrame 帧机制作执行基质，retry/llmretry 语法与策略高阶化（语法糖 + 协议方法）；
  ④ 行为语句与 llm 函数两条路径已收敛到 LLMCallRequest，统一点 = 引入 LLMCallable 协议统一
  消费路径（修复 D9 裸 `@~` 非可调用值/D11 双装配/D12 可调用类无 LLM 语义）；⑤ 能力公理
  收敛三层划分 = 类型元属性（is_*/kind）保留 axiom、行为层收敛协议满足、编译期推断专用
  （resolve_*）保留 axiom 方法；⑥ prompt 协议族双注册表（PROMPT_PROTOCOL_SPECS vs
  BUILTIN_PROTOCOLS）收敛 + to_prompt 死条目激活 + str 缺 output_hint（D4）。**产出**：
  `tasks_docs/_five_foundation_redesign.md`（临时，路线 P1-P9 与待决项 §五）；NEXT_STEPS/
  HANDOFF 同步。设计定稿（P1）交下一 session。调研方法：代码实证 + 运行探针
  （create_default_registry）+ 同步 subagent（本环境后台 subagent 不稳定已弃用）。
- **五大地基改造 6 项关键决策（2026-08-18，用户逐项拍板，落 `_five_foundation_redesign.md` §五）**：
  ① **内置类型协议方法表选 B**——per-IbClass 协议方法表，以彻底完整系统化重构为目标
  （非最小 A/non-能力探测 C）；② **内置类型行为改写 = 临时覆层机制**（新设计约束，最关键）：
  无覆层→按默认；声明不启用（flag 未启、不在相关作用域）→常规程序段仍按默认；仅用户明确
  启用作用域才生效用户自定义 impl；告警基于覆层存在/启用状态设计。与 per-IbClass 协议方法表
  （B）结合 = 覆层作影子条目、默认不参与分派；与 D6（内置 spec 不可持久化）天然互补（覆层
  运行期按需注册）。③ **snapshot 意图冻结按文档补齐**（用户确认原初意图：lambda=引用捕获不
  保证时不变/无状态；snapshot=冻结保证时不变/无状态/可重入）；④ **`llm ... llmend` 语法彻底
  删除**（推翻语法糖映射推荐，彻底转向统一 llm 可调用类，全量迁移示例/试用/测试）；⑤ **retry
  帧机制保留 + 语法/策略高阶化**；⑥ **P1-P6 本主线，P7/P8 远期**（类型理论加固/函数式组合子
  登记 PENDING_TASKS 远期，P1-P6 稳定后重估）。**交接**：下一 session 开工 = P1 设计定稿，
  决策输入清单见 `_five_foundation_redesign.md` §六。
- **llm 函数语法/旧机制彻底删除（2026-08-18，本 session，用户追加裁定）**：用户再次明确——
  `llm ... llmend` 语法**彻底删除**，且**与 llm 函数语法相关的旧机制一并彻底删除**
  （`__sys__`/`__user__`/`__llmretry__` 段、顶层 `llmretry` 语法糖、`IbLLMFunctionDef`、
  `callable_kind="llm_function"`、`_LLMFunctionMixin`、provider `user_sys` 槽等）。
  **不保留、不考虑历史兼容、不考虑历史包袱**——非语法糖映射、非过渡双轨。语义由统一
  LLMCallable 协议覆盖。此裁定细化决策 4，为 P1 设计定稿的最高约束。
- **五大地基改造 · P1 设计定稿完成（2026-08-18，本 session，只写设计文档无代码改动）**：
  产出 `tasks_docs/_five_foundation_P1_design.md`（§一-§九），逐项定稿 P1 开工输入 7 项：
  ① `LLMCallable` 协议方法族（`__llm_call__` 必需 / `__intent__`/`__retry__` 可选，required
  vs optional 分组）+ LLMCallRequest 承载；② llm 函数语法彻底删除范围（lexer/parser/AST/
  semantic/runtime/mixin/provider 全链路）+ 语义迁移映射表 + 全量迁移清单；③ 临时覆层机制
  形态（声明语法/作用域 flag/影子条目/告警）；④ per-IbClass 协议方法表全局数据形态
  （`protocol_vtable` + `ProtocolSlot` + receive 前置查表）；⑤ snapshot 意图冻结补齐
  （意图冻结并入 capture_mode，移除 body_is_behavior 特判）；⑥ retry 高阶化边界（帧机制
  保留 + 语法/策略高阶化）；⑦ 破坏面评估 + P2-P6 分阶段迁移路径与验证门。P2-P6 实现以
  `_five_foundation_P1_design.md` 为设计规格、`_five_foundation_redesign.md` 为决策/调研
  权威。已同步 `_five_foundation_redesign.md` §六 指针。
- **五大地基改造 · P2/P6 地基自主重排序（2026-08-18，本 session，独立分支 exp/protocol-vtable）**：
  按 P1 设计定稿 §五/§八，决策 1 B（per-IbClass 协议方法表）改动面大（IbClass.__slots__ +
  receive + 水化 + 序列化契约）→ 按分支政策走**独立分支 exp/protocol-vtable** 原型验证。
  subagent 只读爆破面报告确认：① `receive` 协议分派骨架被 **6 份同构复制**（base/functions/
  native_module/optional/callables×2），均用 getattr 探测 `_dispatch_<name>`（D5 机制同构破坏）；
  ② 内置类型全部方法（含 __to_prompt__/cast_to/__call__）走 IbClass.methods vtable，仅
  __from_prompt__ 走 axiom cap（唯一现存活双通道）；③ 序列化契约不受影响（class_ref 只存名）；
  ④ `dunder_names()` 是扁平并集、丢方法→协议归属；⑤ register_method 是 methods 唯一写闸门。
  **自主重排序**：P2 的 impl 目标放宽（放行内置）与 to_prompt 死条目激活、P5 prompt 类型类化、
  P6 protocol_vtable 全部依赖"协议方法表地基"；为免半接通/双通道（质量红线），先建地基：
  **增量 1** = 收敛 6 份 receive 分派骨架为单一 `_dispatch_protocol_message` 助手（D5 集中落点，
  behavior 不变，全量 2956 零回归，commit 6d933080）。后续增量沿"协议方法表数据结构 + impl
  放行 + 覆层机制 + to_prompt 激活"推进。
- **五大地基改造 · 调研实证（2026-08-18，exp/protocol-vtable）**：D2+D1 逐项核验——①`to_prompt` 协议**零消费者**（核心无 satisfies_protocol(...,'to_prompt') 调用，仅协议条目定义），所有内置类型 satisfies to_prompt=F 但运行期均经 vtable `__to_prompt__` 渲染（真激活须接 PromptRenderer 协议前置，属 P5，不宜 P2 半接通）；②`PROMPT_PROTOCOL_SPECS`（4 方法，无 __payload_prompt__）与 BUILTIN_PROTOCOLS 的 payload_prompt 双注册表（D1）——补 __payload_prompt__ 会激活 `validate_prompt_protocol_signature`（L565 警告级）对用户声明 __payload_prompt__ 的校验；`trials/T08_llm_pressure/cases/D2-05-payload.ibci` 与 test_multimodal_* mock 类均有此类声明，契约须按 axiom 签名 `(self,value,spec=None)` 定，落地前需核验不产生伪警告。**结论**：两者皆与 P5 prompt 类型类化纠缠，P2 阶段不宜半接通，登记为 P5 落地项。
- **五大地基改造 · D9 死字段清理（2026-08-18，exp/protocol-vtable，commit 6fd2cefc）**：移除行为 AST 节点 vestigial 死字段 `is_callable_instance`（编译器从不赋 True，运行期分支死路径）+ 其死代码路径。实证：`IbBehaviorExpr` 已无此字段（设计文档行号过期），仅 `IbBehaviorInstance`（ast.py L581）存在；`vm_handle_IbBehaviorExpr` 的 create_behavior 死分支与 assignment.py is_callable_instance 死守卫移除，直接执行行为主路径与 lambda/snapshot 行为体 create_behavior 活路径保留。全量 2980 零回归。**后续发现**：① `IbBehaviorInstance` 类本身是更大死代码候选（core/ 无构造点），留作独立清理；② `binding_analysis_pass.py:235` 有 `getattr(ast, "IbBehaviorInstance", type(None))` 能力探测（code-quality 红线模式），若删该类一并清理。
- **五大地基改造 · D4 补齐（2026-08-18，exp/protocol-vtable，commit eb8ecd30）**：str 缺 output_hint 能力（satisfies_protocol(str,'output_hint')=False，与 int/list/dict/tuple 不一致，D4）。StrAxiom（core/kernel/axioms/primitives/sequences.py）增 has_output_hint_cap + __outputhint_prompt__（镜像 ListAxiom 模式），satisfies_protocol(str,'output_hint')=True，无半接通。test_str_behavior_gets_generic_expected_type_declaration 随语义演进重构为 test_str_behavior_gets_axiom_output_hint（旧断言即 D4 前的非一致特例，非缺陷规避）。全量 2980 零回归。
- **五大地基改造 · protocol_vtable 数据结构形状修正（2026-08-18，exp/protocol-vtable）**：
  爆破面报告实证冲正 P1 设计 §五的键映射假设——`receive` 分派按**消息名（dunder 方法名）**
  查 `_dispatch_<name>`（这些是值 Python 实现类上的**实例方法**，非 IbClass.methods 里的
  IbFunction）；`dunder_names()` 是扁平并集、丢"方法→协议"归属；协议名与 handler 名非 1:1
  （cast_to→converter、__eq__→operator）；"返回 None = 继续路由 / 显式关闭"是隐式协议。
  **设计含义**：per-IbClass 协议方法表应承载**消息名→处理器**（对应 `_dispatch_*` 实例方法）
  的分派，而非我 P1 初稿的"协议名→方法"；多协议共方法（__getattr__→attribute 等）须按
  方法名索引。D3（satisfies_protocol 读 spec.members vs receive 读运行期）的桥接 = 运行期
  协议成员查询，非简单的协议名表。**P6 实现须按此修正后的形状落地**；P1 设计 §五 数据形态
  需在回归 unsafe-vibe-dev 后按此修正（现处于实验分支，不污染已定稿权威文档）。



- **五大地基改造 · protocol_vtable 数据结构落地（2026-08-18，exp/protocol-vtable）**：
  决策 1 B（per-IbClass 协议方法表）核心数据结构落地，全量 2985（+5 判别性测试）零回归。
  **实现**：① `ProtocolSlot`（base.py）：消息名槽（native 原生处理器 + overlay/overlay_enabled
  覆层影子条目，默认不参与分派）；native 按**值 Python 实现类**（`type(value)`）惰性解析并记忆化
  `_dispatch_<name>`——**多态安全实证约束**：`callable` 类宿主 `IbFunction` 族（MRO 落
  `IbObject._dispatch_call`）且 `IbSuperProxy`（自有）、`Type` 类宿主 `IbClass` 且
  `HostClassBinding`、类对象与其实例共用 ib_class（自指）——按 IbClass 静态烘焙单一处理器会破坏
  super proxy / HostClassBinding / 类对象分派；② `IbClass.__slots__` 增 `protocol_vtable`
  （消息名键，惰性建槽：仅协议注册表方法集建槽）+ `protocol_slot(message)` 查表；③
  `_dispatch_protocol_message` 改为查表分派（`active_handler`：覆层启用→overlay，否则按值类
  native；返回 None 继续普通 vtable 路由），消除逐次 getattr 能力探测（D5）。
  **设计决策**：protocol_slot **不做父链查找**——native 继承由值 Python 类 MRO 承担（per-IbClass
  父链冗余），覆层影子条目挂声明类自身（父链查找会误挂到 Object 祖先导致覆层全局泄漏，P2-②
  若需继承在其机制内显式设计）。判别性测试：协议消息名键建槽/非协议落 vtable、callable 多态
  native 解析、覆层默认不参与分派、消息级协议语义保持（super proxy/类特化/Optional 委托/
  用户 __call__ CPS）。临时任务文档 `_code_protocol_vtable.md` 已随本增量收尾删除（git 承载）。

- **五大地基改造 · 会话交接点最终状态（2026-08-18，exp/protocol-vtable）**：
  **当前分支 = `exp/protocol-vtable`**（从 `unsafe-vibe-dev` 的 `e8c7944b` 分叉的独立实验分支；
  P6 协议方法表原型验证用；`unsafe-vibe-dev`/`main` 未触碰；未 push）。本会话完成零回归增量：
  ① 地基 receive 6 份骨架收敛（`6d933080`，2956）；② P2-① impl 目标扩展到内置类型（`6c3f6c94`，
  2980，含合成 owned_scope）；③ D4 str output_hint 补齐（`eb8ecd30`，2980）；④ D9 is_callable_instance
  死字段清理（`6fd2cefc`，2980）。**当前 exp 分支全量基线 2980 passed / 1 skipped**。
  **自主重排序（用户认可自主）**：P2 剩余②覆层机制/③to_prompt 激活/④_dispatch 查表与 P5 prompt
  类型类化、P6 protocol_vtable 数据结构深度纠缠（D2/D1 实证归 P5）——protocol_vtable 数据结构
  （P6 核心）优先，作为后续落点；不含半接通/双通道。
  **剩余任务接管**：protocol_vtable 数据结构（决策 1 B，按形状修正：receive 按消息名查 _dispatch_*）
  → P2-② 临时覆层机制（决策 2，影子条目默认不生效/flag 启用/作用域化）→ D2 to_prompt 激活 + P5
  prompt 类型类化（D1 双注册表收敛/补 __payload_prompt__）→ P3（意图一等值 G5 + snapshot 冻结 D8）
  → P4（llm 可调用类内核 + retry 高阶化 + llm/llmend 彻底删除）→ P6 落地。每步全量 pytest 零回归
  + 复核 + 本地 commit；确认低风险可 merge `unsafe-vibe-dev`。见 `NEXT_STEPS.md` 下一步候选 #1。
  **工作过程自查**：本会话我在目标轮次多次出现思维链退化（长叙述、迟迟不真正发工具调用），
  消耗大量上下文产出骤降——下个 session 接手时应**短促化工具调用、主动及时暴露此类退化**，
  避免空转到上下文耗尽。

- **五大地基改造 · P2-② 覆层机制实现完毕但未提交（2026-08-18，exp/protocol-vtable，工作树）**：
  **🔴 交接关键**：P2-② 临时覆层机制（决策 2）**已完整实现并实证，但留在工作树未 commit**——
  16 个修改文件 + 3 个新文件（含 `tests/e2e/test_overlay_mechanism.py` 5 项判别性测试）。
  **实现面**：`overlay`/`with` 新关键字（tokens/core_scanner）；AST `IbImplDef.is_overlay` +
  新 `IbWithOverlayStmt`；parser（`impl overlay for <T>:` 变体 + `with overlay(<T>.<协议方法>):`
  语句）；语义（`_declaration_visitors`/`_statement_visitors` 校验 + `_overlay_registry` 新模块 +
  未启用告警 `SEM_OVERLAY_UNUSED`（codes/catalog/`docs/syntax/15_diagnostics.md` 同步）+ symbol
  collection overlay 分支 + binding_analysis 递归）；水化（overlay impl → `target.protocol_slot(m).
  overlay` 影子条目，**不**进 vtable/members/implements）；VM `vm_handle_IbWithOverlay`（scope
  enter/exit + `overlay_enabled` save/restore）；分派 `_dispatch_protocol_message` 对 IbFunction
  覆层经 `.call(receiver, args)` 执行。
  **实证**：receive('__to_prompt__') 块内覆层生效/块外恢复原生；未启用告警 warning_count=1
  发射；e2e 5 项全过；全量 pytest 2985 passed / 1 skipped 零回归。
  **设计决策**（详见 `tasks_docs/_code_overlay.md` §四，提交后删除该临时文档）：覆层走 impl
  变体声明（真设计非 compat）；作用域块 save/restore 天然作用域化；目标为编译期声明引用
  （`<类型>.<协议方法>`）不求值为表达式（避免 getattr 反身性）；覆层方法不进 spec.members/
  implements（不改变编译期 satisfies_protocol 判定，仅运行时改写分派——职责分离）。
  **下一步（下一 session 第一步）**：`git diff` 复核 → 全量 pytest 实跑 → 描述性 commit →
  删临时文档 → 同步 NEXT_STEPS/WORKLOG/交接检查单；随后 P2③/P5 prompt 类型类化 → P3 → P4
  → P5 → P6。**禁 push**；低风险增量可 merge `unsafe-vibe-dev`。
- **五大地基改造 · P2-② 覆层机制复核并提交完成（本 session，exp/protocol-vtable）**：
  **复核结论**：机制正确——`git diff` + 未跟踪文件逐文件对照红线/边界/契约；handler 实证命中、
  块内 `overlay_enabled` 生效/块外恢复；端到端实证（真实 `with overlay(int.__to_prompt__)` 语句 +
  行为 `@~ report: $x ~` prompt 渲染经 PromptRenderer `receive('__to_prompt__')` → 块内
  "overlayed-int"/块外 "5"，mock 回显判别）。`x.__to_prompt__()` 直走 vtable 方法查找、不经
  flag 敏感分派——覆层生效面是协议分派（receive/PromptRenderer），非普通成员方法调用，此为
  机制设计面而非缺陷。
  **复核补充两处**：① 新增端到端判别测试
  `test_with_overlay_block_end_to_end_via_prompt_rendering`（真实 `with overlay` 语句驱动 +
  LLM 渲染 + mock 回显）——原有"块内生效/块外恢复"测试为手动翻转 `slot.overlay_enabled` 模拟、
  未走语句路径，覆盖声明与实测有差距，已补齐；② `_OverlayRegistry` 增 `declared_items()`
  公开遍历 API（收敛 `_declared` 私有字段跨模块访问，封装纪律）。
  **提交**：e2e 6 项全过；全量 pytest **2997 passed / 1 skipped** 零回归；临时文档
  `_code_overlay.md`/`_code_protocol_vtable.md` 已删除（git 承载）；NEXT_STEPS/HANDOFF 已同步到
  已提交状态。**禁 push**；低风险增量可 merge `unsafe-vibe-dev`（须用户授权）。
- **五大地基改造 · P2③/P5 prompt 协议族类型类化 D1+D2 落地（本 session，unsafe-vibe-dev，commits 见 git log）**：
  **D1 双注册表收敛 + 补 __payload_prompt__**：`PROMPT_PROTOCOL_SPECS` 补第 5 成员
  `__payload_prompt__`（is_instance_method=True / param_count=0 / return_type=any）——
  **用户向契约 = `(self) -> dict|list|str`**：runtime 经 `receive('__payload_prompt__', [])`
  **零参数**分派（PromptRenderer.to_payload / `_prompt.py` 段插值），公理层 `(self,value,spec=None)`
  是内置 media 委托的内部 Python 签名（不经用户 IbFunctionDef 校验）；故 param_count=0，
  与 trial D2-05 声明一致——伪警告核验：`(self)->dict` 零 SEM_PROTOCOL_SIGNATURE、2 参声明出码。
  **D2 to_prompt 死条目激活**：to_prompt 是**通用渲染路径**（探针：34 内置类型 vtable 均持
  `__to_prompt__` 而 satisfies 全 False，仅 7 个动态/结构类型满足）——与 from/outputhint/payload
  的可选能力本质不同 → `BaseAxiom.has_to_prompt_cap` 默认 **True**（单一真理，免逐公理重复声明）
  + `BUILTIN_PROTOCOLS.to_prompt` 接 `axiom_cap="has_to_prompt_cap"` + `PromptRenderer.to_prompt_str`
  增 `satisfies_protocol` 前置门（镜像 to_payload；无 registry 时回退 `_has_method`/receive 存在性）。
  **行为保持实证**：门不改变渲染内容（内置经 receive 一致；无 __to_prompt__ 用户类落
  to_native/str 与既有一致；覆层端到端测试经门仍走覆层——satisfies 静态 True、receive 动态走
  overlay，二者解耦正确）。**G7 三层划分衔接**：has_llm_call_cap → LLMCallable 协议属 P4；
  **validate_prompt 死条目激活 = P5 剩余项**（本步只做 to_prompt 激活，不扩面、不半接通）。
  **P1 设计 §五 形状修正同步**：protocol_vtable 数据形态按爆破面实证订正为**消息名 → ProtocolSlot**
  （native 按 value 类惰性解析 / overlay / overlay_enabled），非协议名键（落地 WORKLOG 前文
  "回归 unsafe-vibe-dev 后订正"项）。验证：全量 pytest **3003 passed / 1 skipped** 零回归（+6）。
- **五大地基改造 · P3 D8 snapshot 意图冻结补齐 + lambda IT-3 意图 fork（本 session，unsafe-vibe-dev）**：
  **定稿实现（决策 3 / IT-2/IT-3/IT-4）**：纯 snapshot lambda（非行为体，fn_callable 路径）同样在
  **定义时刻**冻结意图——`vm_handle_IbLambdaExpr` 的意图 fork 从 `body_is_behavior` 特判中移出，
  改为**按 capture_mode 统一**（snapshot 恒 `fork_intent_snapshot()`、lambda 恒 None）；`IbFnCallable`
  增 `captured_intents` 字段（与 IbBehavior 同构，消 D10 双类字段设计重复）+ 工厂透传 + 序列化
  `_collect_fn_callable`/反序列化补齐；`_vm_call_fn_callable` 增意图生命周期——进入
  `enter_intent_scope()`（lambda 在执行窗口看到调用点意图的 fork 副本，IT-3 高阶函数透明，修复
  lambda 此前不 fork、与函数调用（`_vm_call_function` 恒 fork）不一致）+ snapshot 安装冻结快照
  （`replace_intent_context(captured_intents.fork())`，fork 一份保 IT-4 冻结不可修改——调用期
  @+/@-/@! 只落在调用副本）。
  **判别性证据（自定义宿主绑定 provider 记录 `LLMCallRequest.intents.merged`，`tests/
  e2e/test_snapshot_intent_freeze.py`）**：快照调用 merged=定义时刻意图、调用处 `@` smear 被忽略；
  lambda 调用 merged=调用处 smear（IT-3 对照）。**顺带清理 P1 §六.4 死字段** `IbAssign.capture_mode`
  （从未构造传递、从未读取，恒 None）。
  验证：全量 pytest **3011 passed / 1 skipped** 零回归。**G5 意图一等值**（`IbIntent.content: str` →
  可渲染值栈 `IntentValue`，修复 G2/G5/G9）为 P3 剩余大项，下轮开工（设计见
  `_five_foundation_redesign.md` 交接点/P3 行）。
- **五大地基改造 · P3 G5/G2 意图一等值切片：可调用值有意契约嵌入（本 session，unsafe-vibe-dev）**：
  **实证定位**：意图段求值渲染大面已工作（int/str 值经 segments→PromptRenderer 正确渲染）；**G2
  具体缺口** = 函数/可调用/行为值渲染为 Python repr（`<Function 'helper'>`/`<FnCallable ...>`/
  `<Behavior ...>`），意图嵌入无意义。
  **实现**：`IbUserFunction.__to_prompt__` → `func <name>(<参数类型…>) -> <返回>`（取值自持 spec 的
  `param_types`/`return_type`，与 capture_mode/expected_type 同层值层属性）；`IbFnCallable` 与
  `IbBehavior` 的 `__to_prompt__`（未执行形态）+ `_dispatch_to_prompt` 统一为 `signature_name()`
  （机制同构，无双写）。普通 vs llm 函数仍可区分（不同名/签名）。
  **判别测试 `tests/e2e/test_intent_callable_embedding.py`**（自定义 provider 记录
  `intents.merged`）：函数值→`func helper(int, str) -> str`、snapshot 可调用→`fn_callable` 契约。
  **语义演进重构**：`tests/e2e/test_callable_unification.py` 2 用例断言从 `<Function 'f'>` 更新为
  `func f() -> int`/`func g() -> str`（核心"普通/llm 可区分 + fn 可赋值"保留，非规避缺陷）。
  **架构定位**：G5 深交 P4（LLMCallable 将重塑可调用/意图交互）；"意图值栈 content:str → 原始值
  栈全量重构"的剩余面（栈存原始值/按值匹配语义）与 P4 对齐评估再推进——本切片在"勿半接通"
  红线内闭合交付"意图段有意义嵌入"。
  验证：全量 pytest **3019 passed / 1 skipped** 零回归。
- **五大地基改造 · P4a LLMCallable 协议地基（本 session，unsafe-vibe-dev）**：
  P4 为巨型阶段（llm 可调用类内核 + `llm ... llmend` 语法及旧机制彻底删除 + retry 高阶化 +
  全量迁移——摸底：36 个测试文件 + 66 个示例/试用文件用 llm 函数面）。拆**子增量轮次推进**
  （勿半接通）：
  **P4a（本轮）= LLMCallable 内置协议注册 + satisfies 判定**：`BUILTIN_PROTOCOLS` 增
  `llm_callable`（`__llm_call__` 为**必需方法** = "能否被 LLM 消费"的唯一判定，P1 §2.1；
  `__intent__`/`__retry__` 为可选能力、运行时经 receive 发现，required/optional 形式化归
  P5/P6）——判别测试：用户类实现 `__llm_call__` → satisfies True / 不实现 → False。纯增量、
  零语法破坏。验证：全量 pytest **3020 passed / 1 skipped** 零回归。
  **后续子增量（登记 NEXT_STEPS）**：P4b LLMCallable 装配路径（`assemble_llm_callable_request_cps`
  + 行为值 `__llm_call__` 内核原生实现 + run_batch/stream 统一消费 LLMCallable 实例）
  → P4c `llm/llmend` 语法+旧机制全链路删除（lexer token/llm_scanner 整块/parser/AST/
  semantic is_llm 分支/`callable_kind="llm_function"`/`_LLMFunctionMixin`/provider `user_sys`
  槽，决策 4 + 用户追加裁定）+ 全量迁移（36+66 面，语义随演进重构测试，不规避缺陷）
  → P4d retry 高阶化（决策 5 帧机制保留 + 语法/策略高阶化）。
- **五大地基改造 · P4b LLMCallable 装配路径设计定稿（本 session，unsafe-vibe-dev，设计轮）**：
  P4b 为设计最密集阶段（装配上下文形态/用户 `__llm_call__` 契约/CPS 段求值 vs 同步 receive
  分派均未钉死）。**设计定稿**落 `tasks_docs/_code_p4b_assembly.md`（临时，实现后删除）：
  ① 装配上下文 = IBCI 一等对象 `IbLLMCallAssemblyCtx`（`llm_call_ctx` 类型，封装意图三层/
  输出契约输入/目标模型 + 可写槽 set_user_prompt/add_prompt_slot/set_output_hint/set_model）；
  ② 用户 `__llm_call__(self, any ctx) -> void` **ctx 变异契约**（LLMCallRequest 非语言类型，
  用户变异 ctx、内核映射——与 `ai.load_project_config` 配置对象变异同构，机制同构）；
  ③ 统一装配入口 `assemble_llm_callable_request_cps` = CPS 生成器（用户类经 UserFunctionCall
  yield 驱动、行为值内核原生装配，差异经协议方法自身承载，禁 if 标志位）；
  ④ 行为值满足 llm_callable 由内核注册承载（P4b-2）。
  **落地顺序（勿半接通）**：P4b-1（设计，本轮）→ P4b-2（ctx 对象 + 统一入口 + 用户 llm 类
  支持 + run_batch 统一）→ P4b-3（__intent__/__retry__ 运行时发现）。验证门与用户侧蓝图
  （Translator 示例）见设计文档。
- **五大地基改造 · P4b-2a LLMCallable 统一装配路径实现（本 session，unsafe-vibe-dev）**：
  新增 `_LLMCallableMixin`（`llm_executor/_llm_callable.py`，组合进 `LLMExecutorImpl`）：
  - `assemble_llm_callable_request_cps`：协议门（`satisfies_protocol(..., 'llm_callable')` 为
    唯一入口判定）→ CPS 调用用户 `__llm_call__(self) -> dict`（`UserFunctionCall` yield）→
    装配 dict 映射为 `LLMCallRequest`（user_prompt/output_hint/expected_type/model + 意图三层
    消解，与行为路径共用 `_resolve_llm_callable_intents_cps`）；
  - `invoke_llm_callable_cps`：装配 → 统一 worker `_call_and_parse`（`_call_llm`+`_parse_result`，
    与行为路径同构）。
  **契约定稿（修订 `_code_p4b_assembly.md`，理由记录）**：P4b-2a 用户 `__llm_call__` =
  **返回装配配置 dict**（避免新内核 ctx 类型注册成本、函数返回配置数据更 IBCI 惯用）；装配
  上下文 `IbLLMCallAssemblyCtx`（可写槽/只读意图入参）降级为 P4b-2b 扩展。
  判别测试 `tests/e2e/test_llm_callable_unified.py`：用户 llm 类（Translator）经 host 桥接触发
  统一入口 → mock provider 收到 `user_prompt="将「hello」翻译为英语"` + output_hint（端到端
  装配生效）；非 llm 可调用值 fail-fast。验证：全量 pytest **3028 passed / 1 skipped** 零回归。
  后续：P4b-2b（run_batch 统一消费 LLMCallable 实例 + 行为经统一入口收敛 + 装配上下文扩展）。
- **五大地基改造 · P4b-2b run_batch 统一消费 LLMCallable 实例（本 session，unsafe-vibe-dev）**：
  `_BehaviorMixin.run_batch` 移除"仅 behavior"窄拒——接受行为值（既有 items 逐项绑参语义
  保留）+ 用户 llm 可调用实例（新增 `_RunLLMCallableDrive` Waitable，经统一装配入口
  `invoke_llm_callable_cps` 执行一次；llm 类 items 逐项参数化归 P4b-2c 定义）；非 llm 可调用
  fail-fast。`builtin_modules.py` `run_batch` 首参型由 `behavior` 宽化为 `any`（编译期放行
  behavior 与 llm 类，运行期由 executor 协议门 fail-fast）。判别测试（新增
  `test_run_batch_accepts_llm_callable_instance`）：`ai.run_batch(tr, [])` llm 类经统一装配 →
  provider 收到装配 prompt + 单元素结果；行为 run_batch 7 项 d-test 零破坏。
  验证：全量 pytest **3029 passed / 1 skipped** 零回归。后续：P4b-2c（stream 统一 + llm 类
  per-item 契约）→ P4b-3（__intent__/__retry__ 可选协议方法发现）。
- **五大地基改造 · P4b-2c llm 类 run_batch 逐项参数化契约（本 session，unsafe-vibe-dev）**：
  `__llm_call__(self, any item)` **可选 item 参**（经 `method.spec.param_types` 长度检测
  非 self 参数——声明 item 参则逐项传入）：`assemble_llm_callable_request_cps` / 
  `invoke_llm_callable_cps` 增 `item` 参数，`UserFunctionCall` 按需传项；`_RunLLMCallableDrive`
  批量化（`_invoke_llm_callable_batch_cps` 逐项 CPS 执行 + `_invoke_llm_callable_batch_sync`
  同步兜底，返回 boxed 结果列表；并发优化留待后续）。run_batch 语义收敛为**每 item 一次 LLM
  调用**（llm 类；item 仅在声明时参数化）。判别测试：`run_batch(tr,[0])` 无 item 参 → 单次固定
  装配；`run_batch(g,[1,2])` 声明 item 参 → 逐项装配（"欢迎1"/"欢迎2"）。修正测试间 provider
  模块 Python 缓存导致的跨测试累积（每测试唯一模块名）。验证：全量 pytest **3030 passed / 1
  skipped** 零回归。后续：P4b-3（__intent__/__retry__ 可选协议方法运行时发现）→ P4c。
- **五大地基改造 · P4d retry 高阶化（本 session，unsafe-vibe-dev；决策 5 落实）**：
  `__retry__` 可选协议方法落地（P1 §2.2 契约 + §七 边界）：`func __retry__(self) -> dict`
  （无参）返回策略声明 `{"max_retry": int>=1(缺省 3), "hint": str}`；发现走
  `_discover_optional_protocol_method`（与 `__intent__` P4b-3a 同一虚表通道）；契约违约
  fail-fast（带参/非 dict/max_retry 非法/hint 非 str）。装配入口返回三元组
  `(request, type_hint, retry_policy)`；invoke 路径有策略时驱动**调用级重试循环**
  （`_invoke_llm_callable_retry_cps`：失败轮经 _prompt_assembly 单一消息构造累积
  `message_history` 回喂、达到 max_retry 仍不确定交语句层 llmexcept/LLMParseError）；
  直接调用 `f(args)` 与 run_batch 逐项自动继承。**边界裁定（帧机制与 CPS 栈耦合的合理处置）**：
  帧机制 = ①执行窗口重求值（re_eval + 快照恢复 + 写保护，纯 VM 语句语义，不可也不应高阶化）
  ⊕ ②LLM 重试信息装配（已模块化 _prompt_assembly）；高阶化只作用于②——协议层产出策略数据、
  执行层（帧机制/调用循环）消费数据，CPS 状态机不进协议。`__llmretry__` 旧语义（重试提示回喂）
  由 `hint` 承接；快照策略复用 `__snapshot__`/`__restore__`（不重复声明，无双写真相）。
  行为语句默认 retry 由帧机制提供（零改动）。判别测试 6 项 `tests/e2e/test_llm_retry_callable.py`；
  docs/syntax/08_llm_callable.md §8.4 + 10_robustness.md §10.5 同步。验证：全量 pytest
  **3047 passed / 1 skipped** 零回归。后续：P5（validate_prompt 激活 + prompt 类型类化剩余 +
  required/optional 协议条目形式化）。
- **五大地基 · P4d/P5 承接评估：output_hint 自动推导 = 不落地（保持显式）**：P4b 记录的
  "output_hint 自动推导评估"结论——llm 类装配 dict 的 `output_hint` 保持**显式声明**，不自动
  从 expected_type 类型推导。理由：用户 2026-08-12 "显式配置方向"裁定（显式优于隐式 + fail-fast）；
  llm 类 `__llm_call__` 装配由用户全权构造，expected_type 已注入类型约束，output_hint 是额外
  格式说明；行为路径自动取 hint 是行为值节点语义（`_get_llmoutput_hint_cps`），不扩及 llm 类。
- **五大地基改造 · P5 prompt 类型类化收尾 + validate_prompt 激活 + required/optional 形式化（本 session，unsafe-vibe-dev）**：
  **P5a validate_prompt 死条目激活**（G7 能力公理收尾，D2 to_prompt 同构）：`BaseAxiom` 增
  `has_validate_prompt_cap: bool = False`（内置预校验由内建解析器承担，非通用路径——与 to_prompt
  通用渲染默认 True 相对）+ `BUILTIN_PROTOCOLS validate_prompt` 接 `axiom_cap` +
  `structural_methods`（用户类经 spec.members 结构判定）+ `llm_parsing_strategy` 消费前置门
  （satisfies_protocol 统一判定，advisory：实际分派仍走虚表 lookup + call）。**P5b required/optional
  协议条目形式化**（P1 §2.2）：`ProtocolDef` 增 `optional_methods` 字段 + `all_methods()` 全量
  方法集（必需+可选保序去重）；`methods` 保持必需单一权威、判定不变（optional 不参与
  satisfies 强制判定）；`llm_callable` 条目正式登记 `optional_methods=("__intent__", "__retry__")`
  （description 移除"formalized later"）。**P5c 评估即收尾**：prompt 协议族五成员
  （to_prompt/from_prompt/output_hint/payload_prompt/validate_prompt）消费面前置门全部
  satisfies_protocol 协议化（D1 双注册表单一方法名权威 P2③ 已收敛），无剩余代码缺口。
  判别测试 +8（kernel：validate 条目声明/axiom flag 默认 False/内置不满足/用户类满足；llm_callable
  optional 登记/all_methods 并集/requires 仅必需/仅 optional 不满足）；全量 pytest **3055
  passed / 1 skipped** 零回归。后续：P6（per-IbClass 协议方法表最终收尾：spec.members 与
  protocol_vtable 双表同步 D3/D6）。
- **五大地基改造 · P6 per-IbClass 协议方法表最终收尾（本 session，unsafe-vibe-dev）**：
  **据实评估（分支决策）**：P6 主体（protocol_vtable 数据结构 + receive 前置查表 + 覆层影子
  条目 + `_dispatch_protocol_message` 集中落点）已在 P2-② 落地并回归（cd60ea6d + 覆层）——
  决策 1"一举解决 D3+D5"已达成（D5 能力探测 getattr 消除；D3 判定与分派均以**协议条目为单一
  权威**：satisfies 数据驱动 + dunder_names 派生协议消息面 + 惰性建槽）。剩余面 = 双表收敛
  实证锁定 + 接口补齐 + 文档漂移修正——**边界清晰、非架构级破坏，不独立分支**（P1 §8.3 分支
  政策基于"改动面大"的原始评估，当前剩余面已脱离该前提，直推 unsafe-vibe-dev）。
  **落地**：① D3 收敛契约测试 +4（用户类协议方法 satisfies↔receive 一致；未声明 satisfies
  False + 无默认实现消息不误分派——to_prompt 例外为 Object 根类默认渲染，消费前置门以
  satisfies 为准；protocol_vtable 惰性建槽；llm_callable optional 不建协议槽）——
  `test_protocol_dispatch_contract.py::TestSatisfactionDispatchConvergence`；② `TypeAxiom`
  接口补齐 `has_validate_prompt_cap` 声明（P5a 只改了 BaseAxiom，接口 Protocol 缺失）；
  ③ docs 漂移修正：03_type_system §4.0 内置协议列表补 llm_callable + optional_methods 说
  明、§4.1 TypeAxiom 能力布尔补 has_to_prompt_cap/has_validate_prompt_cap；04_vm_interpreter
  §2 receive 分派补 protocol_vtable/ProtocolSlot/覆层查表形态。
  验证：全量 pytest **3059 passed / 1 skipped** 零回归（判别 +4）。后续：五大地基 P1-P6
  全链路收尾评估（剩余对齐债务：意图值栈全量重构 / has_llm_call_cap → llm_callable /
  行为值深程统一装配入口收敛）。
- **五大地基 · 剩余对齐债务评估（本 session，记录交接）**：三项债务均**不属小而清晰**，
  记录评估依据供后续：① **G5 意图值栈全量重构**（值栈存原始值/按值匹配）——大面重构
  （intent_context/栈模型/消费点），与 run_batch/invoke 意图消费对齐后再评估；②
  **has_llm_call_cap → llm_callable**——实证其消费者为**编译期 DDG**（callable 公理经
  此能力识别 behavior 节点，`core/kernel/axioms/primitives/callable.py`），与运行期
  llm_callable 协议（`__llm_call__` 用户方法结构判定）**不同层**——不可简单接 axiom_cap
  （axiom flag 语义 ≠ 结构方法判定），迁移须先做编译期/运行期分层设计；③ **行为值深程
  统一装配入口收敛**——run_batch/invoke 行为路径经各自入口（`_prepare_behavior_call_cps`
  vs 统一装配），中大型重构（行为执行路径），`assemble_stream_request_cps` 桥接为先例。
  均记录于 NEXT_STEPS 候选 #1（收尾评估），不阻塞主线。
- **五大地基 · 剩余对齐债务评估修正（本 session，候选 #1 收尾定论）**：② **has_llm_call_cap
  实证为死字段**——穷尽 grep：无任何协议映射（axiom_cap 无该项）、`get_call_cap` 只读
  `has_call_cap`、DDG 实际经 `IbBehaviorExpr` AST 节点类型识别（非该 flag）、无任何直接/
  动态消费者（`getattr(axiom, protocol.axiom_cap)` 无 has_llm_call_cap 键）。上 session
  "编译期 DDG 层实证"记录与代码不符——纠正并**删除**该字段（BaseAxiom 默认/BehaviorAxiom
  覆写/TypeAxiom 接口 + 03_type_system.md 能力表）；P4 llm_callable 协议化已取代其设计
  意图，删除为真收尾。① G5 意图值栈全量重构维持登记不推进（P3 已落地核心切片，勿半接通）；
  ③ 行为统一装配评估为值自身差异承载（非双通道），收窄为登记项。
- **五大地基超大型重构专项审计发现（2026-08-19，本 session 末，只检测未修）**：基线
  `e8c7944b`..HEAD（130 文件 +4592/-1627）审计产出技术债清单 A-G（定位/详情见会话交接
  HANDOFF_SESSION.md §七，常驻摘要 HANDOFF.md §2.1）：A **注释/文档任务代号污染**（core
  12 + tests 19 + docs 6 文件——违"代码注释禁任务代号"与 docs 治理红线，含 P4x/D8/G5/G7/
  "决策 1 B"字样，下 session 建议机械批清理）；B **死代码**（`_invoke_llm_callable_cps_boxed`
  / `_invoke_llm_callable_sync` 零消费者）；C **意图三层解析双写真相**（`_resolve_llm_callable_intents_cps`
  与 `_prepare_behavior_call_cps` 内联块同构重复）与行为/llm 类双装配入口（与候选 #1 同源）；
  D **overlay_enabled 跨根并发污染风险**（IbClass 级共享态，`with overlay` 作用域化在多根
  并发下不成立，需隔离设计）；E 半接通边界（stream 不消费 retry 循环，登记为设计边界）；
  F 登记债务核对（无新增）；G 工作过程遗留（临时文档待删）。处置建议：A+B 零风险机械批 →
  C 并入主线债务评估 → D 独立窗口设计。
- **五大地基临时设计文档删除（2026-08-19，技术债收敛阶段 1）**：P1-P6 全部竣工后，
  `_llm_callable_redesign.md` / `_five_foundation_redesign.md` / `_five_foundation_P1_design.md`
  三份设计阶段临时文档删除（git 承载历史）；6 项关键决策与完成记录已在本文件 §二/§三 内联保留，
  架构事实已收敛入 docs/（03_type_system / 04_vm_interpreter / 08_llm_callable 等）。
- **技术债收敛 8 阶段全部完成（2026-08-19，unsafe-vibe-dev）**：用户批准后按 12 项定案决策
  （D1-D12）执行收敛——D1-D2 用户拍板（__from_prompt__ 单向契约 B / SEM_PROTOCOL_SIGNATURE
  required=error B）；D3 自主定案 file→fs（破坏性重构授权 + 无外部用户）；D4 docs/README
  治理章程 tasks_docs 指针保留 + AGENTS.md 红线消歧；D5 补登记 PT-FEAT-5（PT-FEAT-2/PT-TEST-1
  已完成删过期引用）；D6-D7 删 inherit_plugins 孤儿字段与 IbBehaviorInstance 死类型；D8-D9 质量
  红线（interpreter.py:989 双通道收敛=删错误 node_to_symbol fallback、_llm_callable 能力判定掩错
  fail-fast）；D10 NEXT_STEPS 治理；D11 三份 _five_foundation_* 临时文档删除；D12 G5/行为装配
  维持登记。全程 8 阶段每步全量 pytest 零回归 + 描述性 commit（9 笔：69952657/a1b66755/
  0093527d/d08f42c4/855ae13e/ce297e88/704c4f3e/f9f47324/9b5c5fd8），终基线 3069 passed /
  1 skipped（+3 判别测试）。
- **后续任务排布（2026-08-19，用户指定健康度优先 + 全面试用纳入）**：排布原则 = 健康度优先
  （代码/架构）→ 功能稳健 → 对外能力 → 远期演进 → 真实 LLM 全面试用（健康阈值后重启，非最高
  优先但必做）。**阶段 A（当前 P0·代码/架构健康）**：主线架构债落地（G5 意图值栈 + 行为统一
  装配收敛）、PT-DEBT-29 生成器让出型消费、Tier C 专项审计（C 类异味/静默降级补诊断/深嵌套）、
  PT-DEBT-30/33 类型边界、PT-AUDIT-1/3 周期。**阶段 B（功能稳健/对外能力）**：PT-TEST-2 覆盖
  缺口、PT-DECIDE-3 项②④、PT-DECIDE-2 思考禁用、PT-FEAT-5 CI/CD、PT-DOC-3P2、PT-FEAT-6/12。
  **阶段 C（真实 LLM 全面试用重启·VISION-3）**：对五大地基重构后全部新特性重试用（llm 可调用
  类/意图三层改写/retry 高阶化/流式/覆层/prompt 协议族/fs 等），真实 qwen3.6 全量回归 + 压力扩展，
  缺陷→修复→核销循环；阈值 = A/B 健康稳定达标后。**阶段 D（远期演进）**：P7 类型理论、P8 函数式、
  二层 IR；PT-SEALED-1 保持封存。完整排布见 NEXT_STEPS 下一步候选。
- **排布微调（2026-08-19，用户裁定）**：A4（Tier C 审计）与 A3（PT-DEBT-30/33）交换；
  **PT-DECIDE-2（供应商思考禁用）封存**——短期不再考虑启动（PENDING 标 sealed，解封条件=
  多供应商思考模式部署需求）；**PT-DOC-3P2 提前至 B3**（how-to 读者旅程，对外可用性优先）；
  **PT-FEAT-6/12 划更远期**（近期不处理）。完整排布见 `tasks_docs/_planning_health_first.md`。
- **阶段 A1 主线架构债务落地完成（2026-08-20，unsafe-vibe-dev）**：按 `_a1_architecture_debt.md`
  设计执行（临时设计文档，完成后删除）——两块登记架构债解除：
  - **① G5 意图值栈全量重构**（`08c4b787`）：意图段在注释/栈操作执行点 **eager 求值为一等值
    列表**（`IbIntent.values`），删除运行时 `content`/`segments` 双表示（`content` 变协议计算
    属性 = `render_text()`，`IntentProtocol` 不破）；`@-` 按**值派生渲染文本**匹配（操作数求值
    → `__to_prompt__` → 与栈内意图渲染文本比较，修复动态意图按退化字符串匹配失效）；
    **求值时序语义**：`@+ $x` 压入当时值，重赋值不影响已压入意图（值栈语义，替代原 resolve
    时惰性重求值——无测试依赖旧语义，判别测试锁定）；**意图消解链同步化收敛**——渲染已同步，
    删除死 CPS 包装（`resolve_content_cps`/`resolve_to_prompts_cps`/`get_resolved_prompt_intents_cps`/
    `IntentResolver.resolve_cps`，`_resolve_llm_callable_intents` 同步化）；**`@-` 解析修复**——
    pop_top 误判（`@- "text"`/`@- $x` 带空格时被当 pop_top），修复为"纯空白后须换行/EOF 才是
    pop_top"；序列化改值列表往返。判别测试 `tests/e2e/test_intent_value_stack.py` +7。
  - **② 行为值深程统一装配入口收敛**（`202c6ff3`）：新增 `assemble_llm_call_request_cps` 统一
    装配入口（行为值→语义槽装配 / llm 可调用类→用户装配 dict，单一分派源）；`assemble_stream_request_cps`
    委托统一入口；`run_batch` 行为路径（`_run_batch_sync`/`_run_batch_cps`）与 `execute_behavior_object_cps`
    收敛到统一入口；提取 `_execute_behavior_spec_cps` 共享提交（机制同构）；行为表达式路径保持
    `_prepare_behavior_call_cps`（无值对象，非双通道）。判别测试 run_batch 拒绝非法值 +1。
  全量 pytest **3082 passed / 1 skipped 零回归**（基线 3069）；阶段 A P0 前移至 PT-DEBT-29。
  文档同步：09_intent_system（一等值/按值匹配）、01_intent_system（值栈模型）、LDE（§1.3/§3.5 收敛注记）。
- **新技术债登记：变量语义建模显式化（2026-08-20，用户裁定）**：用户指出 ibci **没有显式且合理地
  区分变量引用 / 变量拷贝 / 变量赋值 / 变量传递** 等值语义建模——语义存在混乱与不清晰，语法与说明书
  亦不够清晰，判定为**巨大隐患**（语义地基级）。登记为 **PT-DEBT-34**（P1，评估→调研→修复），
  **放置在真实 LLM 全面试用（阶段 C）之前**（NEXT_STEPS 阶段 A 置顶 + 阶段 C 阈值含其完成）。
  排布自主决策：置于阶段 A 首位（当前 P0 由 PT-DEBT-29 前移至 PT-DEBT-34）——语义建模是试用评估
  可信度的地基前提，且"巨大隐患"须优先处置；若用户倾向先做 PT-DEBT-29，调整排布即可（PENDING/
  NEXT_STEPS 已记录）。
- **PT-DEBT-34 迅速评估（2026-08-20，影响面 + 工作量）**：实查运行时值语义机制——
  **结论：运行时模型一致完整，非大重构**。
  - **模型本体（一致）**：复合对象（list/dict/用户类实例）共享引用（同 Python）；赋值 = 引用复制
    （别名）；参数传递 = 共享引用（函数内可变影响调用方）；显式拷贝 = `copy`（浅）/`deepcopy`（深）
    内建（实现正确：新容器+元素共享 / 递归独立副本）；snapshot lambda/behavior = 深克隆冻结；
    llmexcept 快照 = 深克隆（`__snapshot__`/`__restore__` 协议可覆写）；类静态字段 = 每实例深克隆
    （`ib_class.py:413`，避免共享默认容器）；`is` = 身份、`==` = `__eq__`（KNOWN_LIMITS §十四.2）。
  - **"混乱不清晰"集中在三处**：① **用户面文档契约缺失**——`02_variables.md` 无值语义/赋值语义章节、
    `05_functions.md` 无参数传递语义章节、共享引用模型只在 `KNOWN_LIMITS.md §五`（"已知边界"非教学
    契约）、`is` vs `==` 身份语义无用户文档；② **文档漂移**——`KNOWN_LIMITS §五.2` 建议"始终在构造
    函数中初始化列表/字典字段"，但代码已每实例深克隆静态默认值，文档过时；③ **判别测试缺口**——无
    测试锁定赋值别名/传引用/copy vs deepcopy/snapshot 冻结/llmexcept 快照/静态字段独立性。
  - **影响面**：docs（02_variables / 05_functions / 12_builtins / KNOWN_LIMITS §五 + 交叉章节
    07 snapshot / 09 intent fork / 03_handling_errors / 10_robustness）+ 新判别测试 + 运行时审计
    （找发散点，预计少量小修——文档漂移属文档修）。
  - **工作量**：**中等（约 4-6 个专注窗口）**。四步：① 调研对照（主流语言值语义，快）→ ② 文档权威
    契约（值语义章节 + 各章教学段 + 修漂移）→ ③ 判别测试锁定 → ④ 运行时审计（发散点 + 小修）。
  - **排布结论（自主调整）**：维持 PT-DEBT-34 为阶段 A 首位 P0（高价值/中成本，先于试用消除隐患并
    解锁试用）；细化任务为上述四步子阶段；不改变其余阶段次序。
- **PT-DEBT-34 完成（2026-08-20，四步全落地）**：
  - **① 调研对照**：主流语言值语义（Python/C++/Rust/Java）对照——IBCI 与 Python 完全对齐
    （赋值别名 + 传参共享引用 + 可变/不可变二分 + `is` 身份 vs `==` 值）；运行时实核与上 session
    评估一致（赋值=`set_variable` 存引用、传参=`define_variable(arg, args[i])`、copy/deepcopy 内建
    正确、静态字段每实例 `try_deep_clone`、snapshot/llmexcept 深克隆）。
  - **② 文档权威契约**：决策——**`02_variables.md` §2.8 作值语义唯一权威归属**（避免插入新章节触发
    03-15 章重编号 + 跨文档 §N 引用破坏；02 文件身份本即赋值范围，符合 WRITING_GUIDE §A.4/§A.6）。
    新增值语义章节（两类值/赋值别名/不可变原语/is vs ==/传参/闭包捕获/快照序列化）+ `05_functions`
    §5.10 传参教学段 + 修 `KNOWN_LIMITS §五.2` 漂移（代码已每实例深克隆静态默认值，原"始终构造函数
    初始化"建议过时）+ `03_operators`/`12_builtins` is/== 精确化与互引闭环。
  - **③ 判别测试**：`test_value_semantics.py` +11（赋值别名×3/传引用×3/不可变原语×2/is vs ==×3）；
    copy/snapshot/llmexcept/静态字段由既有测试锁定，docstring 交叉引用（单点真理不重复）。
  - **④ 运行时审计**：**重要语义事实——容器（list/dict）`==` 默认身份比较**（未定义 `__eq__`，
    仅同一对象为真，与 Python 逐元素不同；与用户类未覆写 `__eq__` 原则一致 KNOWN_LIMITS §十四 #2）。
    定性内部一致非缺陷，文档精确化、不改行为；若用户后续要逐元素 `==` 属独立设计项。**无代码小修**。
  - 全量 pytest **3100 passed / 1 skipped 零回归**（基线 3083，+17 = 11 新测试 + 6 meta 按文件参数化）。
- **PT-DEBT-29 生成器消费协作化完成（2026-08-20，消除同步阻塞模型）**：
  - **设计**：复用 `CPSDrivable`（Waitable+`cps_drive`）——用户面 `to_list`/`generic_next`/seq 内建返回
    drive，`vm_handle_IbCall` 自动 `yield from cps_drive`（**免原生调用机制改动**）；内部 for/yield-from
    直接用 CPS 方法。单一机制，无双通道；宿主/线程体同步兜底为 CPSDrivable 既有契约（非双通道）。
  - **实现修正（关键）**：① **PEP 479**——生成器帧内显式抛 StopIteration 被转 RuntimeError，`generic_next_cps`
    改用 `_GeneratorExhausted` 哨兵（携带子生成器 return 值）；② **Waitable 解析值形态**——`LLMFuture.
    try_result` 返回原始 `LLMResult`，须 `send` 回生成器驱动（路由回 yield Waitable 的 handler 解析），
    非直接当事件。
  - **消费面**：`generic_next_cps`/`to_list_cps`（generator.py）+ `_GeneratorConsumeDrive`（用户面）+
    `_IterableComputeDrive`（seq 内建 sum/all/enumerate/zip/sorted/reversed/min/max）+ `resolve_iterable_cps`
    （for/yield-from）。
  - **判别测试**：`test_generator_coop_consume.py` +6（chan.recv 经 for/next/to_list/yield from +
    跨线程投递 + LLM 经 for）；同调度器跨任务死锁在用户代码模型下不可构造（thread 独立调度器），
    测试锁定协作路径正确性与可恢复性。
  - **文档**：KNOWN_LIMITS §二十四（同步阻塞边界）**移除**（限制已消除），§二十五-§二十七 重编号为
    二十四-二十六，全仓引用同步（04_vm_interpreter L3/05_functions §5.9/01_native_host_binding ×2）。
  - 全量 pytest **3112 passed / 1 skipped 零回归**（3100 + 12 = 6 新判别 + 6 meta 参数化）。
- **PT-DEBT-30 + PT-DEBT-33 类型边界闭合完成（2026-08-20）**：
  - **PT-DEBT-30 `yield from` 序列委托收紧**：`visit_IbYieldFromExpr` 按委托目标区分节点静态类型——
    生成器操作数保持元素类型（表达式值 = return 值）；序列/`__iter__` 操作数收紧为 `None`（运行时
    表达式值恒 None，`int r = yield from [seq]` 编译期 SEM_TYPE_MISMATCH 拦截，须 Optional[T] 兼容）。
    原 KNOWN_LIMITS §二十四（序列委托静态类型偏乐观）移除，25-26 重编号 24-25。
  - **PT-DEBT-33 三子边界**：① **10.1 dict 键编译期校验**（`visit_IbSubscript`：dict[K,V] 静态错位键
    SEM_TYPE_MISMATCH，动态键放行）；② **10.3 中置/前导星偏移修正**（逐 *expr 以其前显式位置实参数为
    目标形参偏移，与运行期顺序展开一致——原仅保证末尾星）；③ **跨引擎封印优雅回退**（见下）。
  - **跨引擎封印处置定论（防未来误解）**：密封+异产物场景下用户类特化重建受注册表封印限制（seal 在
    `create_subclass` 与 `register_class` 双层强制 + token 校验）。**不放松封印**——选择与内置泛型
    （list[int]→list）同构的**优雅回落基类**（`_hydrate_specialized_class` 重建失败返回基类，字段保留、
    方法可经 receive 分派），杜绝 ib_class=None 坏对象；特化跨引擎身份保真仍须目标引擎已编译该类
    （KNOWN_LIMITS §十.2 契约不变）。理由：① 内置密封场景本就回落基类，用户类收敛至同构行为即"随类型
    地基收敛"；② 放松双层封印属安全敏感架构变更，且破坏"类表冻结"不变量，收益（仅跨异产物恢复特化
    身份）不足以抵偿风险；③ 判别测试锁定回退正确性。
  - 判别测试 +11（yield from 3 + dict 键 3 + 星偏移 4 + 跨引擎回退 1）；全量 pytest **3123 passed /
    1 skipped 零回归**。
- **Tier C 专项审计定案 + 用户 6 决策（2026-08-20）**：
  - **审计结论**：hasattr 全量分类（113 处，4 并行 subagent + 独立复核）：58 合法保留（协议/分层
    边界 + 可选字段）/ 50 简单异味（恒真/恒假死守卫 ~22 + 双轨残留 4 + 探测分派 + 附带死代码）/
    4 真缺陷（intent_context merge/combine 静默 no-op、__from_prompt__ 形状违约静默、binding_analysis
    兜底、serializer mode.value 死守卫+错误兜底）/ 4 深层次（contract_validator:63 公理契约校验静默
    死亡最严重、_helpers:32 层穿透、deep_clone:117 鸭子类型、intent_context 方法族+axiom 能力契约）。
    静默降级补诊断复核：leaf/runtime_serializer/artifact_loader 全部「返回未知上层决策」合法（主缺陷
    已由 PT-DEBT-33 修复）。for+if 深嵌套：真实控制流最深 8-10 层但纯 if/elif 链最长 4 段——可读性
    问题非架构。
  - **用户 6 决策（2026-08-20）**：① contract_validator:63 **彻底根因修复**（恢复 get_method_specs
    校验 + 实跑评估揭露面 + 根因修复）；② **全量彻底清理**（全部简单异味 + 真缺陷，全部记录）；
    ③ _helpers 本次最小收紧（补 isinstance）+ **_ctx 完整形式化登记 PT-DEBT-35 独立窗口**；④ deep_clone
    **彻底切换惰性 isinstance**；⑤ intent_context 方法族死守卫本次清、**结构重构 + axiom 能力契约校验
    登记 PT-DEBT-36 独立窗口**；⑥ 反序列化宽异常收窄 except PermissionError + kernel_diagnostic 补观测。
  - 执行：分 6 阶段（规划记录→机械清理→真缺陷→contract_validator→深层次→反序列化），每步全量
    pytest 零回归；执行顺序允许自主微调，但所有发现问题必须彻底解决（用户明示）。
  - **周期质量维护推迟裁定（2026-08-20，用户）**：近期为相对深层次重构期，**周期性质量维护任务
    （PT-AUDIT-1/3 周期复核 + quality-maintenance Tier A/B + aimless-review）推迟到真实试用（阶段 C）
    之后**；不占用近期主线。阶段 A 一次性攻坚（A1-A5）全部完成，当前 P0 前移阶段 B。
  - **PT-DEBT-35/36 不再推迟（2026-08-20，用户）**：两项原"独立窗口"任务**移入阶段 B 排布**
    （B3/B4，不再推迟）——B3 PT-DEBT-36（intent_context 方法族结构重构 + axiom 能力契约校验）、
    B4 PT-DEBT-35（_ctx 契约形式化）；与 B2 协议主题衔接。同期完成任务控制清理：PENDING 移除 7 个
    已完成条目（PT-DEBT-4/29/30/31/33/34 + PT-DECIDE-4，git 承载）、KNOWN_LIMITS 修 3 处 PT-DEBT-33
    遗留陈旧条目（§10.1 dict 键编译期校验、§10.3 中置星偏移已修、§16.7 __retry__ 已实现）、
    NEXT_STEPS 当前状态收敛（移除历史完成块）。
  - **PT-DEBT-35/36 状态确认（2026-08-20）**：决策 3/5 的"完整任务登记为后续独立窗口"——**已完整记录
    （PENDING §二 DEBT 活跃 2）但未完成**（本 session 仅完成最小收紧/死守卫清除部分）；PT-DEBT-35（_ctx
    契约形式化）与 PT-DEBT-36（intent_context 方法族结构重构 + axiom 能力契约校验）为独立窗口任务，
    不属本次完成范围。
  - **✅ 6 阶段全部落地完成（2026-08-20）**：Phase 1 机械清理（恒真/恒假死守卫 ~24 + 双轨残留 unbox
    收敛 4 + 附带死代码 3：symbol_table/_expression_visitors 死 type_ref 块/registry 守卫/binding_analysis/
    declaration_visitors is_method/component 双形状/strings·numbers·converters·base/collection._len/
    expression buffer fail-fast/snapshot 死 else/symbol_resolution 重复空 def 等）；Phase 2 真缺陷 fail-fast
    （merge/combine 对齐 use()、__from_prompt__ 形状违约、binding_analysis 死兜底删除、mode.value 直接）；
    Phase 3 contract_validator:63 彻底根因修复（get_methods→get_method_specs + 移除死 kind 门——get_method_specs
    恒返回 MethodMemberSpec，原 kind 门会使校验仍死；恢复后实跑验证 ListAxiom 等真实内置类零违约零误报）；
    Phase 4 深层次（_helpers 补 isinstance(IbIntentContext) 惰性 import、deep_clone 三方法鸭子类型→惰性
    isinstance，均 align base.py:176 先例）；Phase 6 反序列化（_hydrate_specialized_class except Exception→
    except PermissionError、_rehydrate_type_pool_spec 去宽 except fail-fast、新增 KDIAG_RUNTIME_SPECIALIZATION_
    FALLBACK 观测特化身份丢失）。判别测试 +9；全量 pytest **3133 passed / 1 skipped 零回归**（基线 3123）。
- **阶段 B 起点（2026-08-20）**：当前 P0 = 阶段 B（功能稳健/对外能力），按序 B1（PT-TEST-2）→ B2
  （PT-DECIDE-3 项②④）→ B3（PT-DEBT-36）→ B4（PT-DEBT-35）→ B5（PT-DOC-3P2）→ B6（PT-FEAT-5）。
  **B6 交付边界（用户 2026-08-20 裁定）**：CI/CD = 可靠化设计 + 本地配置（不 push、不启用 GitHub 侧），
  B6 完成标准 = 设计 + 配置就绪，远程启用待用户授权（延续"禁 push"硬原则与 CI"必要性不足"裁定）。
  **B1 完成（2026-08-20）**：COVERAGE_MATRIX 缺口全收敛——新增判别测试 17 项 + 矩阵卫生 3 处陈旧
  TRUE_GAP 收敛（INV-INTENT-SCOPE-3 实际已有 `tests/e2e/test_snapshot_intent_freeze.py` 覆盖、
  INV-LLMEXCEPT-CATCH-4 与 §6.1 CATCH-5 重号重复描述已收敛、switch break/continue 已有
  `test_switch_usability.py` 覆盖）+ **模块重新加载 = 设计排除定论**（IBCI 无热重载机制——模块体仅
  首次导入执行、后续复用缓存实例；`hot_reload_pools` 违反"解释器不修改代码"原则
  `docs/architecture/01_principles.md`）。全量 pytest **3156 passed / 1 skipped 零回归**（基线 3133）。
  **B2 完成（2026-08-20）**：PT-DECIDE-3 项②④ 定案落地——② **评估定论：不扩展 `__validate_prompt__`
  至内置类型**（内置 LLM 输出预校验由内建解析器承担 = from_prompt_cap/内建 parser，单一权威；
  扩展即与 parser 构成双通道）+ **闭合半接通边缘**：`impl` 在内置类型上定义 `__from_prompt__`/
  `__validate_prompt__` 编译期 SEM_TYPE_MISMATCH 拒绝（同 `__init__` 先例——AxiomParsingStrategy
  永不分派 impl 补充的解析协议方法，声明即"满足协议"但从不执行）；④ **复核结论：`PromptRenderer.
  to_prompt_str` 的 AttributeError 静默吞并 → 改 `KDIAG_PROTOCOL_TO_PROMPT_FALLBACK` 可观测发射**
  （与 to_payload/base.py 回退路径同构，不再隐藏用户 `__to_prompt__` 方法 bug）。判别测试 +4。
  全量 pytest **3160 passed / 1 skipped 零回归**（基线 3156）。
  **B3 完成（2026-08-20）**：PT-DEBT-36 落地——① intent_context 方法族收敛（`_ic_get_ctx`/
  `_ic_frame` 单一权威，消除 10 处恒真死守卫/帧探测簇/hasattr 字段探测，push/merge/combine/use
  缺参 fail-fast 不再静默 no-op）；② **`_is_impl_method` 排除元类伪影**：`bool | bool` 曾经
  `hasattr(IbBool, '__or__')` 命中 Python `type.__or__`（PEP 604 类型联合运算符），绑定成类对象
  运算符 → 运行期 "expected 1 argument, got 2"；改 `getattr_static` 校验实例级方法修复；③
  **`_verify_axiom_bindings` bootstrap 末契约校验**：公理声明方法必须 vtable/协议分派/字段承载，
  否则 fail-fast（杜绝"声明即满足但运行期 AttributeError"静默缺口）。判别测试 +13。全量 pytest
  **3173 passed / 1 skipped 零回归**（基线 3160）。
  **B4 完成（2026-08-20）**：PT-DEBT-35 落地——`_ctx` 契约单一权威 = `intent_context.
  get_intent_ctx`/`set_intent_ctx`（isinstance(IbIntentContext) 精确判别，全仓唯一读写入口），
  全仓 ~10 处 `_ctx` 字段探测双轨收敛（`_helpers` 判别 / `use` / `merge` / `combine` /
  `get_current` / 序列化 collect + rehydrate）。判别测试 +9（fake `_ctx` 不误激活 / round-trip /
  非对象 None / clear）。全量 pytest **3182 passed / 1 skipped 零回归**（基线 3173）。
  **B5 完成（2026-08-20）**：PT-DOC-3P2 落地——补齐 2 篇 howto（`use_isolation.md` = ihost
  隔离、`orchestrate_llm_calls.md` = LLM 调用链编排），交叉引用接线（debug→orchestrate、
  guide 03→orchestrate、syntax 11→use_isolation、README 目录树）；代码示例实跑验证。
  纯文档变更。
  **B6 完成（2026-08-20）**：PT-FEAT-5 CI/CD 可靠化设计 + 本地配置——四层可靠性（L1 fast
  单元/契约 ~6s / L2 全量跨平台矩阵 / L3 真实 LLM e2e 手动可选（自托管 runner + api_config）/
  L4 发布产物 build+smoke）+ `.github/workflows/ci.yml` 保持 `workflow_dispatch`（远程启用待
  用户显式授权后恢复 push/PR 并 push）+ `scripts/ci_local.sh` 本地分层复现（无需 push 获得 CI
  分层价值）。设计文档 `tasks_docs/_code_cicd.md`。本地全量 pytest **3182 passed / 1 skipped
  零回归** + L1 909/1 + wheel 构建验证。**阶段 B（B1-B6）全部完成（2026-08-20）**——当前 P0
  前移阶段 C（真实 LLM 全面试用重启，VISION-3）。
- **P0-1 诊断面打包（错误定位链）完成（2026-09-07，free-explore）**：P0 三线之线 1 全链路
  落地（设计文档 `tasks_docs/_diagnostic_design.md`，批次 0-5 每批独立 commit + 全量零回归）：
  ① **SEM-1 编译期运算符类型检查**（唯一语义错误集变更批）——公理层比较分支条件化
  （单一权威源 = `resolve_op → resolve_operation_type_name`，不新建兼容矩阵；排序比较
  `< <= > >=` 仅数值族/str↔str，`== !=` 维持无条件——运行期跨型合法）+ `visit_IbCompare`
  逐对检查 + `visit_IbBinOp` 兜底收紧（删"str 操作数→str"无条件推断，公理声明完备后
  与兜底并存 = 双写真相）；防误报纪律 = 编译期检查是运行期行为的静态近似（实测矩阵为
  准：`int*str`/`bool*str` 重复合法须声明放行，`float*str` 非法）。**长期约束裁定**：
  `in` 运算符编译期检查分组挂起（KERNEL_ISSUE-SEM-2 登记，误报面大于价值）；一元运算符
  收紧同挂起（`not` 属 to_bool 通用能力，误报面大）；if/while/for 非 bool 条件**非缺陷**
  （一切值可 bool 化）。② **B1 错误定位链**——编译侧：语义 error()/warn() 5 处填
  line/col（原全 SEM_ 报 0:0）+ node_to_loc 侧表 file_path 从模块名标识改为模块源文件
  真实路径（idbg script path 失真一并修复）；运行侧：VM CPS 首次捕获点位置补位
  （内层帧 task.node_uid = 出错现场，单一权威源；ThrownException/环境限制异常天然
  排除）+ 码权威源 = throw 点（值层/幽灵码补 `RUN_TYPE_MISMATCH`，翻译点不猜码）；
  CLI 侧：main.py run 为唯一渲染点（DiagnosticFormatter 与编译错误同形态，Python 默认
  traceback 不再出现）。③ **错误对象渲染**——异常公理声明 + IbException 实现
  `__to_prompt__`（`<类型名>: <message>`，str(e) 不再直漏 `<Instance of T>`）+ cast_to
  无法转换 fail-fast（静默 `return self` = 类型谎言修复）。④ **P2 解析位置归位**——
  跨行续行态（词法器 paren 位置栈单一权威源）错误归位到最内层未闭合构造起点；同行
  错误维持卡住点（列号精确不劣化）；废弃 cast 位置 = cast 起点 `(`。已知局限登记
  （EOF 卡住点不归位，KNOWN_LIMIT-PARSE-EOF）。全量 pytest 3289 passed / 1 skipped
  零回归（3219 基线 + 70 判别/回归测试）；验收基线（设计文档 §五）逐项达成。
  **P0 主线前移线 2（PT-FEAT-16 四批）**。
- **P0-2 词嵌入一等能力（PT-FEAT-16 四批）完成（2026-09-07，free-explore）**：P0 三线之
  线 2 全链路落地（每批独立 commit + 全量零回归；设计文档 `tasks_docs/_embedding_design.md`
  §九/§9.6/§9.7 定案 + 交叉核验裁定）：① **契约包** `core.base.embedding_protocol`
  （K1-K3 参考实现平移 + 3 处合入处理：零范数兜底改 fail-fast / mock 派生键文档对齐 /
  测试 runner→pytest 33 项；机制同构基准 = llm_protocol 五层）+ `EMB_` 诊断码域
  （6 码，provider 层异常携带 code——失败语义 → 码单点权威源）；② **vector 一等值类型**
  （公理层：固定维度不可变/值语义/NaN 构造封死/to_native 显式违约[类型身份红线——
  与 int/str 原语同纪律的不可变引用复用克隆]；方法面 dim/dot/norm/cosine/scale/add/sub
  + `==`/`!=` 经 get_operators 自动绑定 + `__to_prompt__` 截断摘要；序列化 2 分支 +
  deep_clone 不可变分支；`vec()` 内置函数——**实测静态返回类型 = vector**
  [register_function 元数据经 resolve_call_return 生效，推翻"builtin 无静态签名"初判]）；
  ③ **ai 模块面**（EmbeddingService 组合接线：embed 动态重载 str→vector / list→list[vector]、
  retrieve 检索最小闭包、api_config `kind: "embedding"` 条目路由[default_model 引用 embedding
  拒绝]、MOCK:VEC mock 面、内省面；**unbox_args 机制泛化**——MethodMemberSpec 声明面，
  值身份敏感方法（retrieve）参数保留 IbObject 原形，非 vector 特判；**幽灵码原码透传**
  ——_runtime_error_code_for 首查异常 code 属性，显式码优先于类型猜测）；④ **真实试用**
  （T16 套件 8/8：mock 6 + SiliconFlow 真实 2，dim=1024 探针、自参考相似度 1.0、top-k
  召回；断言纪律 = mock 确定性 + 真实面相对测量）。全量 pytest 3376 passed / 1 skipped
  零回归（3289 → 3376 = +87 判别/回归测试）。**P0 主线前移线 3（N2 已验证知识注册表，
  K1-K9 已定案实施就绪）**。
- **P0-3 已验证知识注册表（N2 四批）完成（2026-09-07，free-explore）**：P0 三线之
  线 3 全链路落地（K1-K9 已定案：类型 `knowledge`；设计文档
  `tasks_docs/_knowledge_registry_design.md`；每批独立 commit + 全量零回归）：
  ①+② **一等值类型 + 验证门**（公理层 KnowledgeAxiom + IbKnowledge 值对象
  [_create_blank 类型化实例钩子——thread 先例同型，knowledge() 零参构造产生真实
  实现]；条目模型 = 键 → {value 冻结快照, check 谓词引用, check_name 审计,
  events append-only 事件流 + 引擎单调 seq}；混合语义显式声明[知识库可变容器
  同 dict + 条目值冻结快照双深克隆——防引用陷阱污染审计]；方法面
  store/get/amend/history/keys/len；**验证门铁律编译期检查**——visit_IbCall
  hook 遍历 check 函数体 AST[IBCI dataclass 经 __dataclass_fields__ 子节点遍历]：
  行为表达式/ai 模块调用 → SEM_KNW_CHECK_LLM，不透明值 → SEM_KNW_CHECK_OPAQUE
  [不纯度不可证明即拒绝]；KNW_ 码域 3 码 + SEM_KNW_ 2 码三处同步；序列化/克隆
  专用分支[谓词引用不入值快照——水化后 amend fail-fast 已知边界文档化]）；
  ③ **状态保真 + docs 子系统页**（save_state/load_state 保真实证[同入口程序
  形态 T15-E-M28 契约同型：save 后变更丢弃/值保真/事件保真；load 后 VM 读经
  UID 绑定表恢复快照面]；docs/syntax/16_knowledge_system.md[地位三支柱/语义
  不变量/条目模型/方法面/canonical idiom/边界/并发语义]）；④ **T17 试用套件
  7/7**（mock 6 + 真实 1：**L1 canonical idiom 双轨实证 e25 机制"用得越久越
  确定"语言级落地**——首次未命中 LLM 提案+验证+登记、复查命中 0 次 LLM 调用）。
  **附修复**：T17 M6 暴露 host 层缺陷——save_state 单层相对路径[无目录组件]
  经 IbPath.resolve_dot_segments 后 parent=None → os.makedirs('') 抛
  FileNotFoundError（Python 3.12 空串 makedirs 语义）——空目录名守卫 + 回归
  +2。全量 pytest 3400 passed / 1 skipped 零回归（3376 → 3400 = +24
  判别/回归/保真测试）。**P0 三线全部收官（线 1 诊断面 3289 → 线 2 词嵌入
  3376 → 线 3 知识注册表 3400）；主线前移 P1（N1 生成参数面 6 项 / N4
  finish_reason 结构化）**。
- **P1/P2/支线推进 + Tier B 质量巡检（2026-09-07，free-explore）**：P0 三线收官后
  主线前移，本日完成：
  - **P1 · N1 思考模型支持 + N4 finish_reason（生成参数面，单设计 pass 六项）**：
    配置 schema 标准生成参数命名字段（temperature/top_p/top_k/seed——fail-fast
    类型+范围校验）+ extra_body vendor 透传口子（本机硬编码思考抑制 dict 迁入
    api_config——机器事实收敛配置单源）+ 配置未知字段严格性
    （CFG_CONFIG_UNKNOWN_FIELD——静默丢弃不再允许）；provider 层参数通道路由
    单点（temperature/top_p/seed = SDK 直传 kwarg，top_k = vendor 扩展经
    extra_body）+ 三调用点硬编码抑制 dict 移除（reasoning: true 思考模型模式
    请求层可表达）+ **finish_reason 契约面暴露**（LLMCallResult 字段 +
    call_info 观测面——截断检测 length ≠ 解析失败）+ **空内容确定性处理**
    （content 空 + reasoning 非空 = RUN_LLM_EMPTY_CONTENT fail-fast——新增
    LLMProviderError 携带诊断码，替代原静默以 reasoning 替代 content 的可审计性
    违约；异常面原样上抛经码透传机制）+ call_info 采样姿态审计闭环
    （generation 有效值 + finish_reason 经 provider_meta 单通道回填——内核
    _call_info merge 面）；语言面 register_model/set_config 参数面显式化
    （**kwargs 静默吞参移除——未知参数编译期 SEM_UNKNOWN_KEYWORD + 运行时范围
    违约 RUN_TYPE_MISMATCH）；T18 套件 5/5 + 单元测试 +19。
  - **P2 四项**：dict 可迭代 P9c（for k in d 键序列——resolve_iterable 的 to_list
    协议面覆盖 dict + vtable 注册；判别 +6）/ 尾逗号 A3（list/dict 字面量尾逗号
    接受——单行/多行；判别 +9）/ named-model 端点泄漏修复（T01 D1-07-006 /
    T08 D5-03 硬编码旧端点改走 IBCI_TRIAL_LLM_URL/MODEL/KEY env 通道——机器事实
    不入 tracked 文件；真实端点验证通过）/ T06 子目录复跑缺口关闭（run_batch
    收集支持子目录布局[0→20 用例] + 命名可辨识 + 目录型用例 root=用例目录
    [KERNEL_ISSUE-IMPORT-2 短期 harness 解]；T06 全量复跑 20/20 PASS）。
  - **支线**：恶意边界 #17 解封核验（T15-E-M29——SER-1 修复后：特化类类型身份
    Box[int] round-trip 保真 + enum 成员值模型一致——序列化子系统零缺陷；INDEX
    核销）；BOUNDARY-LLM-5 机制澄清文档化（call_info 观测契约——两形态快照：
    dispatch 请求面 → resolve 补全 response/sys_prompt/finish_reason/generation；
    变量读点触发 resolve——观测完整信息须在消费 LLM 结果变量之后；入
    docs/syntax/11_modules.md；mock 路径观测面机制同构化[provider_meta 补
    generation]）；剩余 #15/#19/#33 为专项（观测面设计/overlay 交互/LLM-5 依赖）。
  - **基础设施修复**：全量 pytest 间歇性 120s 超时根因——ThreadPoolExecutor
    worker 非 daemon + 无哨兵唤醒（未显式 close 的 LLM 线程池让进程退出挂起）：
    进程级 weakref 池登记 + atexit shutdown + None 终止哨兵显式投递；
    MockServer daemon_threads=True（keep-alive handler 不阻塞进程退出）。
  - **Tier B 质量巡检**（主线阶段边界触发——P0/P1/P2 全完成）：残留扫描
    （临时目录清理）/ 范围常量双写提炼单点（_TEMPERATURE_RANGE/_TOP_P_RANGE）/
    注释纪律零命中 / 无双通道 / fail-fast 全生效。
  - 全量 pytest 基线 3400 → **3447 passed / 1 skipped**（+47 判别/回归/试用/
    基础设施测试），全程零回归；git 承载（本段 8 commit）。
- **阶段 C 文档复核登记项收敛 + 装配未知键裁定（2026-09-07，free-explore）**：
  ① call_info 键结构——11_modules 单点（08_llm_callable 无 call_info 键描述，无双写漂移；
  本段新增观测契约注记：两形态快照 + 变量读点触发 resolve + generation/finish_reason 面）；
  ② 装配 dict 未知键——**裁定 = 警告级诊断（LLM_ASSEMBLY_UNKNOWN_KEY）**（静默忽略不再
  允许——拼写错误须可见；警告不阻断——扩展字段属调用方约定）：契约字段清单提炼单一
  权威源 `_ASSEMBLY_CONFIG_KEYS` + 缺失 user_prompt 错误消息增强（含契约字段清单）；
  T10-M5 判别用例 +1（警告不阻断 + 输出正确）；INDEX T15"待文档复核项"核销 + T10 行刷新；
  ③ KNOWN_LIMITS 漂移 = 零（dict 可迭代 P9c / 尾逗号 A3 无相关陈旧描述）；
  ④ BOUNDARY-LLM-5 = 机制澄清文档化（观测契约入 11_modules）+ mock 路径观测面机制同构
  （provider_meta 补 generation——字段结构与真实路径一致）。
  全量 pytest 3447 passed / 1 skipped 零回归；git 承载（本段 2 commit）。
- **恶意边界未测项支线收敛（2026-09-07，free-explore）**：#15/#17/#19 全部核销
  （mock 层对抗性用例 + 零缺陷实证）：
  - **#15 intent_context 类字段 deep_clone 路径**（T15-E-M30）：两条独立机制——①
    snapshot 捕获持有 intent_context 类字段的容器（定义时深克隆，嵌套对象路径
    [类实例字段 → intent_context 内部结构] 冻结语义保持：原 context 定义后 push
    不改变快照拷贝）② 序列化 round-trip 类字段路径嵌套保真（与 M28 顶层变量路径
    互补）。观测面确认：intent_context 语言面方法族无实例级栈顶查询，to_prompt
    渲染内部活跃意图结构为权威观测面（#15 前置"观测面确认"成立）。
  - **#19 overlay × 序列化/snapshot/retry 交互**（T15-E-M31）：① overlay ×
    snapshot（作用域化运行时状态不被 snapshot 捕获——与值深克隆捕获语义正交；
    作用域内调用经覆层/作用域外原渲染）② overlay × 序列化（with 块内 save/load
    后渲染回落原形态——overlay 状态不跨序列化边界，临时作用域状态非持久值）③
    overlay × retry 经机制同构确立（retry 复用首轮已渲染字符串不重新渲染——
    无附加对抗面）。
  - **#17 跨引擎序列化/水化**（T15-E-M29，前批）：特化类类型身份 + enum 值模型
    round-trip 保真（SER-1 修复后解封）。
  - **剩余**：#33（_pending_futures 长会话累积——依赖 KERNEL_ISSUE-LLM-5 同子系统
    修复后观测，被动挂起）；KERNEL_ISSUE-LLM-5（llm 可调用类声明用户类赋值约 1/6
    竞态——事件驱动监视复发，近期运行无复发）。
  - harness 附修：expect-out 断言尾部空白不敏感（内容语义匹配；行首敏感保持）。
  git 承载（本段 commit：M29/M30/M31 + harness 修正）。
- **无目的审视（2026-09-07，free-explore——本 session 变更子系统，首次新起清单；
  均为潜在参考，非缺陷判定，待周期事实复审）**：
  1. **引擎资源生命周期契约**（`core/runtime/interpreter/llm_executor/_scheduler.py`
     进程级 atexit 兜底）：LLM 线程池经 atexit + 哨兵兜底确定性释放，但 IBCIEngine
     无显式 close()——executor.close() 存在却无调用方（引擎创建→使用→隐式 GC
     路径由 atexit 代偿）。当下收益 = 进程退出确定性（测试/脚本场景）；潜在问题 =
     长期进程（host 常驻场景）线程池随引擎实例累积（每引擎一池，GC 回收前 worker
     滞留）；形态参考 = 未来可补 IBCIEngine.close() 显式生命周期（atexit 降级为纯
     保险）。另：哨兵投递依赖 CPython 内部属性（_threads/_work_queue，try/except
     防御性降级）——CPython 版本漂移时静默失效（退出挂起风险回归但不报错）。
  2. **运行期诊断的用户端呈现面**（`_llm_callable.py` LLM_ASSEMBLY_UNKNOWN_KEY
     警告）：运行期 warning 经 issue_tracker 记录（severity WARNING + 码）但
     未呈现到用户终端（silent=False 亦不可见，引擎无 diagnostics 输出面——
     编译期诊断有呈现，运行期诊断只有记录）。"可见性"目标半达成（仅测试/检视
     侧可见）。潜在参考 = 运行期警告的用户端呈现设计（console 呈现面 vs 仅
     检视面）——若裁定"运行期 warning 须用户可见"则为缺陷项（转 code-review）。
  3. **dict.to_list 语义清晰度**（`collections.py`/`primitive_initializer.py`
     dict 可迭代 P9c）：to_list = 键序列（对齐 Python dict 迭代约定），但
     "to_list"命名对 dict 的直觉语义可能是"值列表"（list-ification 的常见
     心智）。形态参考 = 命名-语义对齐度（to_keys? 或 to_list 文档强化）；
     当前文档（集合章节）已注明键序列语义，风险低（文档面兜住命名歧义）。
  4. **call_info 单写槽的并发语义**（provider `_record_call_info` + 内核
     `_call_info`）：单写槽 = 最近一次调用（顺序/单线程语义明确；多根并发
     run_many / 线程内并发 LLM 调用时槽被覆盖——观测非确定（哪个调用最后
     resolve 取决于调度）。当下 = 顺序场景契约清晰（T18 观测契约已文档化）；
     潜在参考 = 并发场景 call_info 的观测语义（per-future 观测面 vs 全局
     最近——run_many 批量调用场景的观测需求未现，暂不设计）。
- **T2 环境变量一等通道 + C2 容器解析边缘（2026-09-07，free-explore）**：
  - **T2（handoff §五 队列项，阶段 E 小项）**：① `ihost.getenv(key)` —— IBCI 脚本
    读取宿主 OS 环境变量的一等语言面通道（缺失返回空串，对齐 os.getenv(key, "")
    语义）：HostService.getenv（宿主能力委托链单点）+ IHostPlugin.getenv（插件
    委托纪律保持）+ _SPEC_IHOST spec 成员；此前唯一通道 = 宿主绑定样板
    （import python "os" + bind getenv）——样板保留为通用底层手段，ihost.getenv
    为常用路径便捷面；用例收敛（T01 D1-07-006 / T08 D5-03 密钥通道读法改
    ihost.getenv，真实端点验证通过）+ 文档同步（11_modules/LLM_SERVICE §五/
    AGENTS.local）。② `idbg.env`/`show_env` → `idbg.runtime`/`show_runtime`
    改名消歧——运行环境诊断（调用栈深度+活跃意图）与"OS 环境变量"同名不同物；
    语言面破坏性变更（旧名运行期 RUN_ATTRIBUTE_ERROR fail-fast）；T01 D3-61 用例
    + 文档同步。测试 +5（test_ihost_getenv.py）。
  - **C2（阶段 E 批 1，结构化 LLM 输出契约"文档+边缘补齐"）**：边缘核验发现
    dict 容器 expected_type 解析不可用（LLMParseError）——根因 = MOCK:STR 值
    指令首 token 截断（`MOCK:STR:{"a": 1}` → `{"a":`——JSON 对象冒号/空格处
    截断；解析器/策略层经 spy 实证均正常，mock 内容截断为唯一根因）。修复：
    MOCK:STR 全量回显语义（指令后完整内容原样保留；引号包裹兼容形态去引号；
    INT/FLOAT/BOOL/LIST/DICT 结构化指令不变）+ 控制指令（SLEEP/ERROR）文本
    内容解析前剥离（组合指令语义正交）。文档：08_llm_callable 容器解析（裸
    形态 list/dict + 模糊提取）+ 13_mock_testing STR 语义。回归测试 +14
    （test_mock_scenario.py）+ 既有断言 6 处按全量语义更新（llmexcept/
    multimodal×4/mock_directives/closure/test_hooks——含 closure 注释勘误：
    提示词变量插值展开 $p 为真实语义，旧截断掩盖之）。
  - 全量 pytest 基线 3457 → **3474 passed / 1 skipped**（本段 +19，零回归；
    分三组实跑验证——job 时长上限规避）；git 承载（本段 2 commit：dbc15a15 T2 /
    6334fe15 C2）。
- **C3 用户模块路径解析定案（2026-09-07，free-explore——阶段 E 批 1，
  KERNEL_ISSUE-IMPORT-2 修复）**：
  - ① **绝对导入两级搜索**：① 导入方文件所在目录（同目录模块——多文件用例
    入口目录模块可解析，此前锚定 project_root 单候选致 DEP_MODULE_NOT_FOUND；
    T06 子目录用例"须 harness 以用例目录为 root"的隐性耦合消除）→ ② 项目根
    （项目级模块兜底，既有语义）；逐级探测首个命中；相对导入（./.. 前缀）
    锚定导入方目录不变。
  - ② **模块 artifact 键 = 用户 import 名**：导入模块经 scheduler 用户名映射
    （resolved_path → import 声明名）——运行期 import_module 查询名一致
    （此前键 = 路径 root 相对派生嵌套名，子目录模块键（cases.D1-02.geo）
    与用户 import 名（geo）不一致致运行期 DEP_MODULE_NOT_FOUND）；包路径
    形态（pkg.sub.mod）键 = 完整包路径名（既有嵌套导入语义一致——三段包
    路径回归通过）；入口模块按路径派生/显式锚点名（既有）。
  - ③ **合成入口载体场景**：run_string 入口 = tempfile 载体（系统临时目录，
    沙箱外）——① 级越界候选跳过（沙箱外不报错），回落 ② 级（项目根恒在
    沙箱内）；安全边界（DEP_SECURITY_ERROR）相对导入语义不变。
  - 文档：11_modules §11.1 模块路径解析（两级搜索序 + 模块键语义 + 安全
    边界）。判别测试 +5（test_module_path_resolution.py）。T06 全量复跑
    20/20 PASS（harness root=用例目录形态保持兼容）。
  - 全量 pytest 基线 3474 → **3484 passed / 1 skipped**（零回归；git
    c0d40eaf）。
- **A1 用户自定义协议核验（2026-09-07，free-explore——阶段 E 批 1）**：
  机制端到端核验**已落地**（LANGUAGE_DESIGN_EVOLUTION §3.1 规划项已实现——
  ref A1"内置协议族为封闭集合"宣称过期）：① 协议声明（`protocol Name:` +
  方法签名 pass 体）② 类结构判定满足（satisfies_protocol 用户协议路径：
  无内置判定声明 → required methods 全部结构判定）③ 类型参数 bound
  （`class Box[T: Shape]` 符合参数通过 / 违约 `Box[int]` 编译期 fail-fast
  SEM_TYPE_MISMATCH）④ 协议继承（`protocol Child(Parent)`）。文档
  06_oop 协议节已存在。回归锁定 +4（tests/compiler/test_user_protocols.py）。
  全量 pytest 基线 3484 → **3493 passed / 1 skipped**（零回归；git 62e56155）。
  **阶段 E 批 1 状态**：C1 ✅ / B1 ✅ / A3 ✅ / C2 ✅ / T2 ✅ / C3 ✅ /
  A1 ✅ / C4（裁定维持现状）；**剩余 B3（一等环境/作用域对象）**——
  intent_context 已结构化但偏提示词注入，world/mode/discourse 环境对象缺
  （可快照/嵌套；批 1-2 P0-P1）。
- **B3 一等环境对象实施（2026-09-07，free-explore——阶段 E 批 1 收官项）**：
  `environment` 一等内置值类型落地（可快照/嵌套的作用域化键值环境；与
  intent_context 平行——意图栈[提示词注入专用] vs 键值环境[一般执行上下文]）：
  - EnvironmentState frames 栈（内帧遮蔽外帧 shadowing；get 内→外 / set/pop
    最内层帧）+ 值深拷贝读写双向隔离（同 knowledge 冻结快照纪律）+ fork
    深拷贝快照（双向隔离）。
  - 语言面（预lude 可见）：environment() 构造 + 静态面 get_current()（当前
    环境 fork 快照）/ use(env)（fork 副本替换——原件变异不泄漏，与
    intent_context.use 同构）+ 实例面 get/set/pop/clear/fork/len/contains/
    keys（vtable unbox_args=False 值直通）。
  - Axiom（EnvironmentAxiom）+ ENVIRONMENT_SPEC（kind=CLASS parent=Object）
    + 注册链；deep_clone EnvironmentState 分支（类字段/容器值深克隆独立副本）。
  - 序列化 round-trip（native 条目[frames 原生值] + wrapper[_environment 槽
    env_uid] + hydration 双分支 + 池重建）——save_state/load_state 保真
    frames 键值（含嵌套容器）。
  - **序列化池前缀一致性修复**：_collect 返回值/pool 键统一 inst_ 前缀
    （environment 同型）；修复 _get_intent_context 池查询无 inst_ 前缀回落的
    同类潜伏缺陷（intent_context 实例 _ctx 水化跨池命中——此前水化恒 None
    静默降级，M28 测试未覆盖 _ctx 字段断言故未暴露）。
  - 文档：docs/syntax/17_environment_system.md（语义不变量/方法面/边界
    [用户类值 to_native 降级说明]/与 intent_context 关系对照表）+ docs/README 树。
  - 判别测试 +8（test_environment_type.py：基本面 + fork 双向隔离 + use fork
    语义 + 容器值深拷贝入 + 序列化 round-trip）。
  - 全量 pytest 基线 3493 → **3505 passed / 1 skipped**（零回归；git 9c952524）。
  - **阶段 E 批 1 全部完成**：C1/B1/A3/C2/T2/C3/A1/B3 ✅（C4 裁定维持现状）；
    批 2/3 剩余：A2/A4/A5/B2/B4/C5 重估/D1/E1/E2（批 2）+ A6/B5/C6/C7/D2/D3
    （批 3）+ D1（idbg 增强——T2 命名消歧已完成，增强面随批 2）。
- **E2 save/load 覆盖帧级 Environment（2026-09-07，free-explore——阶段 E 批 2，
  B3 后续解锁项）**：ref E2"save/load_state 覆盖 Environment（现仅变量级）"
  落地——① serialize_context 增 `environment_uid`（当前帧环境 frames 栈经
  _collect_environment 拓扑收集；空环境亦收集[frames=[] 保真]；旧快照无该键
  恢复端跳过[向前兼容]）；② deserialize_context 恢复——保存 frames 栈经
  use_environment 替换当前环境（fork 语义：恢复后当前环境独立于池内副本，
  与 intent_context 恢复先例同构）；③ 文档 17_environment_system §边界
  序列化面补帧级语义（实例 + 帧级状态双保真）。判别测试 +2
  （TestFrameEnvironmentSerialization：save→变异→load 恢复保存态 /
  帧环境键值保真）。全量 pytest 基线 3505 → **3507 passed / 1 skipped**
  （零回归；git e855db78）。**阶段 E 批 2 进度**：E2 ✅；剩余 A2 泛型约束 /
  A4 缺省 void / A5 解构 / B2 惰性结构 / B4 编译定位 / C5 思考抑制重估 /
  D1 idbg 增强 / E1 ihost 完善。
- **A4 缺省 void 实施（2026-09-07，free-explore——阶段 E 批 2）**：
  ref A4"无显式返回 void/auto | 现无缺省；样板负担"落地——① **func 函数无
  返回标注 = 缺省 void**（副作用函数声明简化——消 `-> void` 样板；体内
  return 值丢弃，与显式 `-> void` 同语义；返回值不可赋非 void 变量
  [void 语义 SEM_TYPE_MISMATCH 拦截]）。此前的缺标注 fail-fast
  （SEM_MISSING_RETURN_ANNOTATION）所防为隐式 **any**（击穿类型推断与
  泛型体系——设计注释明确）：**void 缺省返回类型已知，不击穿推断体系**
  （原则裁定：缺省语义须类型确定——void 确定，any 不成立）。② 显式标注
  （-> void / -> auto / -> TYPE / -> any）行为不变（4 形态回归）。③
  lambda 与 llm 行为体保持显式标注要求（值表达式语义——缺失标注仍
  SEM_MISSING_RETURN_ANNOTATION）。④ 文档 05_functions 返回类型面重写
  （缺省 void + lambda/llm 严格性边界）。判别测试 +8
  （test_default_void_return.py：缺省 void 运行 / return 值丢弃 / void 值
  不可赋 + 显式四形态 + lambda 缺标注仍报错）。全量 pytest 基线 3507 →
  **3520 passed / 1 skipped**（零回归；git 8ed6d189）。**阶段 E 批 2
  进度**：E2 ✅ / A4 ✅；剩余 A2 泛型约束 / A5 解构 / B2 惰性结构 / B4
  编译定位 / C5 思考抑制重估 / D1 idbg 增强 / E1 ihost 完善。
- **D1 idbg 增强——show_environment 环境可视化（2026-09-07，free-explore——
  阶段 E 批 2）**：ref D1"意图栈/环境/world 注册可视化，UID 反查源行"——
  环境可视化面补齐（主项落地）：① `idbg.show_environment()` 打印当前帧环境
  （frames 栈：键值行[最内层帧在前——读取序] + 键数[去重遮蔽后]/帧数统计；
  空环境显式 '(空)'）——单一权威源经当前帧 current_environment（与
  environment.get_current() 同源，B3/E2 延伸）；② _SPEC_IDBG 增
  show_environment MethodMemberSpec；③ 文档 11_modules idbg API 面补
  show_environment。D1 三面现状核销：意图栈可视化（show_intents 既有）/
  环境可视化（本项）/ UID 反查源行（line-1 定位链既有——诊断 SEM-1 文件
  行号）。判别测试 +3（test_idbg_show_environment.py：空/有值[键值行+统计]/
  use 替换后输出；capsys 捕获[idbg Python print 先例]）。全量 pytest 基线
  3520 → **3527 passed / 1 skipped**（零回归；git 6b068790）。**阶段 E 批 2
  进度**：E2 ✅ / A4 ✅ / D1 ✅；剩余 A2 泛型约束 / A5 解构 / B2 惰性结构 /
  B4 编译定位 / C5 思考抑制重估 / E1 ihost 完善。
- **C5 思考抑制重估定案（2026-09-07，free-explore——阶段 E 批 2，
  PT-DECIDE-2 重估）**：ref C5 焦点"后端强制思考场景"重估——现状核
  （provider 已含双形态抑制固定发送 + 模型声明 is_reasoning + 抑制失败
  一次性告警 + 空内容+reasoning RUN_LLM_EMPTY_CONTENT 确定性诊断）——
  重估定案三面完整化：① **reasoning 捕获记录**（provider 调用路径
  reasoning 非空即记录进 provider_meta[reasoning]——强制思考可观测面：
  调试时可见模型实际思考过程，此前仅告警、思考内容丢弃；provider_meta
  瞬态不持久化，无 token 成本）；② 既有双面回归锁定（空内容+reasoning
  fail-fast + 抑制失败告警去重）；③ **接口位裁定**——api_config model
  条目 reasoning: true 显式声明强制推理模型（驱动 is_reasoning，既有）；
  请求级 LLMCallRequest.thinking_mode 供应商无关远期接口位**维持未接线**
  （模型级声明已覆盖现有场景——无每请求切换用例）。文档 LLM_SERVICE.md
  §二补强制思考场景重估定案。判别测试 +3
  （test_llm_reasoning_capture.py：reasoning 记录 / 空内容+reasoning
  fail-fast / 无 reasoning 无键）。全量 pytest 基线 3527 → **3534 passed
  / 1 skipped**（零回归；git f5192e4e）。**阶段 E 批 2 进度**：E2 ✅ /
  A4 ✅ / D1 ✅ / C5 ✅；剩余 A2 泛型约束 / A5 解构 / B2 惰性结构 / B4
  编译定位 / E1 ihost 完善。
- **E1 ihost 完善——子环境 LLM 配置继承（2026-09-07 设计定案 + 首次尝试
  回退，free-explore——阶段 E 批 2；进行中/待重做）**：ref E1"run_isolated/
  spawn_isolated/collect 已有；配置继承缺"——设计定案：**spawn 时点快照继承**
  （父激活 provider 的运行时配置状态[model/端点/生成参数/mock]经能力注册
  中心（CAP_LLM_PROVIDER）读取，spawn 时点快照；子引擎 bootstrap 后应用
  （sealed registry 约束：继承须在子 prepare 之后——子 registry 封印前无
  新 artifact 注入）；快照而非活链接（spawn 后父端变异不影响子）。
  **首次尝试（execute 形态）回退**：spawn 时点 sub.compile + sub
  ._prepare_interpreter（bootstrap）+ 继承 + 子线程 execute——
  **sealed registry 冲突**（sub prepare 封印 registry 后 execute 拒绝新
  artifact：PermissionError "Cannot execute new artifact on a sealed
  registry"）+ 继承未生效（子 provider 在 prepare 前读取）。工作树已恢复
  干净（git checkout core/engine.py；全量 pytest 3534/1 基线零回归）。
  **下轮重做方案（hook 形态）**：engine.run 增 on_ready 参数——prepare
  （bootstrap）后、execute 前触发钩子（run 的 L~395 execute 调用点，以
  abs_entry 上下文精确定位——run_string 同名形态须排除）；子 provider 在
  bootstrap 后可及（capability registry 已注册）——子线程 run(on_ready=
  _on_sub_ready) 钩子内应用父配置快照（to_llm_config 归一化 apply_config）；
  失败经 issue_tracker WARNING（HOST_ISOLATE_LLM_INHERIT_FAILED，不阻断）。
  验证面：mock 模式（set_mock_mode + set_config 免 client）+ 继承断言（子
  model = 父 spawn 时点 model）+ 快照语义（spawn 后父变异子不变）。
- **pytest 卡死问题处置（2026-09-07，free-explore——接手智能体报告"特定测试项
  死循环无法退出/无有效输出"）**：
  - **根因**：tests/conftest.py 死锁看门狗 `_DEADLOCK_TIMEOUT_S = 90` 与全量
    pytest 时长（本机 ~95s——含启动/解释开销）竞态——全量 ~95s 完成时看门狗
    90s 先 `os._exit(124)` 误杀进程，表现为"pytest 无输出退出 124 / 卡死"
    假象（非真实死锁；接手智能体跑特定套件时长接近/超过 90s 时触发）。
    期间逐文件复测全部通过（compiler 434 in 4.81s；三组 3534/1 零回归）——
    确认无真实 hang。
  - **处置**：看门狗超时 90s → 180s（全量 2 倍余量——真死锁[线程 join 无界
    等待等]仍被终止并经 faulthandler.dump_traceback 留 traceback）。
  - **卡死定位指引（交接）**：pytest 无输出退出 124 时，捕获**完整 stderr**
    （勿 tail 截断）——看门狗 dump_traceback 输出全部线程栈，hang 线程栈
    即根因所在；先核对看门狗注释的时长基准再怀疑真实死锁。
  - **E1 重做防卡死注意**：spawn 隔离执行测试（request_collect 无界等待
    collect_timeout=None 默认）——若子线程 hang，collect 将无界阻塞至看门狗
    终止。E1 重做的判别测试须传有限 collect 超时（IsolationPolicy
    collect_timeout 或测试级 timeout 守护），避免重蹈卡死表象。
  - 全量 pytest 基线 **3534 passed / 1 skipped**（零回归；conftest 改动）。
- **测试套件自身安全——系统化双层防护（2026-09-07，free-explore）**：
  用户裁定：不应靠智能体的测试行为操作（外部手动超时/捕获）确保安全——
  测试套件自身须能确保自身安全。实施 pytest-timeout 系统化方案：
  - **第一层（pytest-timeout 插件，每测试独立超时）**：pytest.ini
    `timeout = 60` / `timeout_method = thread`——单测试 60s 上限；卡死测试
    （线程 join 无界等待 / spawn collect 无界 / 死锁）**自动 FAIL** 并输出
    测试名 + 全部线程栈（faulthandler dump 到 hang 行）——自动定位，无需
    人工干预。验证：70s sleep 探针测试 60s 自动失败，报告精确到
    `test_hang_probe` 的 `time.sleep(70)` 行。全量 pytest 时长（~95s）
    不受影响——超时按测试计、非按套件计（三组 3534/1 零回归）。
  - **第二层（conftest 进程级看门狗，180s 兜底）**：仅 pytest 框架层 hang
    （collect/plugin 死锁——测试级超时不生效的场景）触发：dump_traceback
    全部线程栈到 stderr 后 os._exit(124)。时长基准注释更新（90s 曾与全量
    时长竞态误杀——180s = 2 倍余量）。
  - **易用/单源**：pytest-timeout 为 pytest 标准插件（无自定义代码）；依赖
    进 pyproject.toml test/dev（`pytest-timeout>=2`，环境规格单源）；超时
    配置进 pytest.ini（addopts 同域单源）。
  - 双层防护注释落位（pytest.ini + conftest 看门狗头注）——后续接手者
    直接可读防护机制与定位路径。全量 pytest 基线 **3534 passed / 1
    skipped**（零回归）。
- **round3 试用需求接入与主线整合（2026-09-08，free-explore）**：试用方
  `docs/ibci_feedback_round3.md`（v3 统一自动机 R185–R202 实证摩擦全集）intake
  完成。裁定要点：① **恒高优先**——round3 P0（D-1 VM 缺陷 / D-2 三引号 /
  D-3/4 str 原语 / D-5 输出缓冲 / R-1+R-3+R-4 run 级可观测 / E1+R-2a ihost
  子环境整合）插入现有阶段 E 队列之前，原批 2 剩余（A2/A5/B2）与批 3
  （A6/B5/C6/C7/D2/D3）整体顺延保留；② **架构安全优先**（用户 2026-09-08
  指示：与主线架构/长期任务耦合项以代码质量、架构安全、IBCI 长期演进收益
  为准）——R-2b meta.compile 与 R-6 行为表达式作值耦合 VISION-4/5 类型类/
  函数式长期方向，**登记不实施**（不半接通 meta 层）；D-3.3 VM 字符串扫描
  快速路径 = VM 执行模型性能架构面，**登记不实施**（Tier C 专项候选；str
  内建四件套消解 90%+ 摩擦而不动执行模型）；③ **单点真理**——R-1/R-3/R-4
  同源数据合并为一个 run 级可观测子系统（一个设计文档一批批实施，对照原批
  3 C7 消重防双通道）；E1（子环境 LLM 配置继承，on_ready hook 形态定案）与
  R-2a run_file 同属 ihost 子环境设计域，整合为一个设计（继承语义 + 结果
  捕获契约 + 沙箱/配置源语义）；④ D-1（fielded 类×LLM 调用 VM 缺陷，试用方
  R183 上报）**补登记 `KERNEL_ISSUE-VM-2`**（此前未入 trials/INDEX = 流程
  缺口，已修）；⑤ F-2 真相核验 = 警告每进程一次性（去重机制工作正常）+
  试用方 4B 后端强制思考为事实（reasoning 隔离 `reasoning_content` 字段），
  处置 = 可配置静默 + 语义澄清（非机制缺陷）。单点记录 =
  `tasks_docs/_trial_round3_intake.md`（逐条核验 + 耦合分析 + 新队列 P0×6/
  P1×6/P2×2/长期×2）；`trials/INDEX.md`（KERNEL_ISSUE-VM-2）/
  `NEXT_STEPS.md`（主线刷新）同步。
- **R3-① D-1 修复完成（2026-09-08，free-explore）**：KERNEL_ISSUE-VM-2
  （试用方 R183 上报 D-R183-1）。归因修正：非 VM/LLM 分派污染——失败点在
  fielded 类零参构造器调用自身（`class Ctx: str tag` + `Ctx()` = auto 构造器
  缺必填，IBCI 合法报错）；真实缺陷 = 构造器/零参方法调用无编译期静态绑定
  检查（缺必填/多参/未知具名全编译放行 → 运行期裸 RuntimeError 无码无行，
  误导试用方误读为内核 bug 并回避 fielded 类）。修复三面：① 编译期构造器
  描述符单一入口（`registry.get_constructor_descriptors`：explicit __init__
  精化描述符[descriptors_synced 门防前置引用误报] / auto = 链上有效无默认
  值字段，与运行期 hydration 共享 `core.kernel.spec.member.merge_decl_fields`
  单一规则源；接入既有 `_resolve_with_descriptors` 统一绑定检查：同一
  resolve_call_binding + SEM_* 四码 + ibci 源行列 + kind 感知主语）；② 零参
  绑定方法 arity 补全（param_types=[] 收集期权威签名——多余实参结构裁决；
  resolved 独立变量限定路由范围防既有空描述符可调用误入）；③ 运行期
  auto-init 回退条件修正（实施中新发现的同域角落缺陷：链上无必填字段时原
  回退把"子类同名覆盖父类无默认字段为默认值"误判为"链上无字段→继承父构造器"
  ——`Base: str name` + `Sub(Base): str name = "d"` + `Sub()` 运行期误要求
  name，编译期/运行期语义分裂；修正 = 链上有字段 → 零参 auto-init，链上无
  字段 → 继承祖先显式构造器，两判据编译期/运行期同构）。边界裁定：显式内置
  父（`MyList[T](list[T])`）构造器调用动态跳过（auto 字段规则仅适用纯用户类
  链，内置父原生构造机制按既有运行期边界形态裁决——防误报）；动态接收者
  （any 类型 callee）残余面登记不扩。变化前后：既有 4 项测试语义演进
  （运行期 RuntimeError → 编译期 SEM_*，触发场景保留：
  test_missing_arg_fails_fast / test_arity_error_from_single_authority /
  test_init_missing_argument_errors / test_init_extra_argument_errors）+
  1 项 fixture 修正（test_fn_sig_covariant_return_allowed 的 `Dog()` 缺必填
  潜伏错误 → `Dog(0, 0)`——新检查正确暴露的既有潜伏错误）+ 判别 25 项
  （test_constructor_call_binding.py：auto/explicit/继承链/默认值排除/子类
  覆盖/泛型特化/零参方法/防误报面）+ 文档（06_oop auto 构造器节 +
  KNOWN_LIMITS §六 补编译期绑定检查与两形态边界）。全量 pytest
  **3563 passed / 1 skipped 零回归**（基线 3534 + 判别 25 + meta 按文件
  参数化 +4，计数对账一致）。
---

- **R3-② D-2 三引号多行字符串完成（2026-09-08，free-explore）**：试用方
  round3 需求 D-2（v3 统一自动机高频摩擦：提示词是核心资产，LEX_UNTERMINATED_
  STRING ×16 实证）。设计裁定：双形态同构（双/单三引号定界均支持——与 Python
  同构、扫描器零额外成本）；raw 前缀正交（r 前缀 + 三引号定界）；值语义对照
  Python（换行保留含开定界符后首个换行、无 docstring 式剥离；缩进保留；
  闭合 = 连续三引号；转义表与单行同一规则源；反斜杠+换行 = 拼接）。实施面
  （core/compiler/lexer/：tokens.py SubState + IN_TRIPLE_STRING；core_scanner.py
  字符串开启统一 _open_string[单行/三引号/正交 raw 单一入口]、_scan_triple_
  string_char[三引号态字符扫描]、_handle_newline 三引号分支[换行入值]、
  check_eof_state 三引号分支、转义逻辑抽取共享 _apply_string_escape[单行/
  三引号同一规则源，不双写]）。**同路径既有缺陷修复**（实施中实证发现）：
  字符串内反斜杠+换行续行此前泄漏语句级 continuation_mode 标志（字符串
  token 跨物理行由 _handle_newline 返回 False 机制承载，两机制本不混用）→
  字符串收尾后声明终止换行被 _handle_newline case 4 吞掉（无 NEWLINE token）→
  PAR_EXPECTED_TOKEN（单行串 `str s = "abc\\<nl>def"` 顶层声明此前必挂——
  缺陷触发实证后修复：移除字符串内置位，NORMAL 态语句级续行路径不变）。判别
  36 项（tests/compiler/test_lexer.py +14：token 值/位置/边界形态；
  tests/e2e/test_triple_quoted_strings.py +22：值语义精确断言[eq 模式]/既有
  缺陷修复面/对照面/未闭合错误码）+ 文档（01_types §1.1.1 字符串字面量
  权威节——四种形态+三引号语义，此前无此节）。全量 pytest **3605 passed /
  1 skipped 零回归**（基线 3563 + 判别 36 + meta 按文件参数化增长，对账一致）。
---

- **R3-③ D-3/D-4 str 原语四件套完成（2026-09-08，free-explore）**：试用方
  round3 需求 D-3/D-4（v3 机制栈语料规模摩擦：sub_str 逐字符拼接 12k 窗口
  挂起 >180s；str.find 单参双参 RUN_TYPE_MISMATCH）。缺口面实证收窄
  （probe 先行）：原生切片已支持（s[1:3]/s[::2] 实证 OK，__getitem__ slice
  处理）→ 本项 = 判别锁定 + 文档确认，无实施。实施三面：① count(sub[,
  from]) 新增（运行期 + 公理表；不重叠计数，Python str.count 对等）；
  ② find 扩 from 选参（运行期 find(sub, from_idx=None)；公理表声明全形
  [str, int]——split 先例：内建方法声明最大参数列、运行期接受更少、编译期
  绑定非严格[split() 零参先例实证]）；③ find_last 改名 rfind（试用方点名
  Python 惯用语 + 仓内零消费方[tests/ibci 代码均无 find_last]，破坏性改名
  授权下不留兼容层；行为不变仅命名对齐）。from 选参语义 = 直接委托 Python
  原语（负偏移等语义天然 Python 对等；判别测试期望值逐一按 Python 真值
  计算验证——本 session 三处期望值算错后按真值修正，运行期自始正确）。
  判别 27 项（tests/e2e/test_str_primitives.py：count/find/rfind 各形态 +
  from 生效判别[无 from 基线对照] + 切片 8 形态 + 三引号×切片组合面 +
  既有方法对照面）。公理层变更（str 方法表）→ 全量 pytest 破坏面评估：
  **3638 passed / 1 skipped 零回归**（基线 3605 + 判别 27 + meta 按文件
  参数化 +6，对账一致）。文档 12_builtins §12.2 同步（find from/rfind/
  count/切片示例）。长期项 D-3.3（VM 逐字符快速路径）维持登记不实施
  （本轮四件套消解试用方 90%+ 摩擦而不动执行模型）。
---

- **R3-④ D-5 stdout 行缓冲完成（2026-09-08，free-explore）**：试用方
  round3 需求 D-5（长 run 不可观测：v3 长批次惯例=后台作业+轮询，e34_p6
  run2 外部 timeout 150s 截断后归档文件只有半程输出——无法区分"慢"与"挂"，
  误读为网络故障）。通道实证（开工前置）：CLI run → engine.run(silent=True,
  output_callback=None) → _print → Python print → sys.stdout——缓冲源 =
  Python 非 TTY stdout 块缓冲（非 ibci 累积）；无修复态时间戳实证：L1/L2
  同刻到达（进程终止 flush，间隔 1.7ms）= 试用方现象复现。设计裁定：
  **run 命令默认行级 flush，不加 --unbuffered 旗标**（试用方请求为二选一
  "行缓冲/flush 或旗标"；ibci print = 行输出语义，可观测性为默认底线；
  旗标 = 同一目标第二通道，不设）。实施 = main.py run 分支
  sys.stdout.reconfigure(line_buffering=True)（TTY 本已行缓冲无副作用；
  非 TTY 管道/重定向 = 每行 print 即时可见）。判别 1 项（subprocess
  Popen 时间隙判别：L1 到达须早于进程结束 ≥1.5s——循环 ~4s 裕量充分；
  第一版 poll() 即时性判别实证竞态误过[终止窗口 0.25s 内 poll()=None]后
  重构为时间隙判定；双向验证：无修复 0.25s 失败 / 带修复通过）。文档
  15_diagnostics §诊断工具补 run 命令输出语义（CLI 面单点归属）。全量
  pytest **3645 passed / 1 skipped 零回归**（基线 3638 + 判别 1 + meta
  按文件参数化 +6，对账一致；新测试 ~5s 入套件总时长）。
---

- **R3-⑤ 批 3 预算核算完成（2026-09-08，free-explore）**：round3 需求
  R-3（run 级预算：tokens/calls/wall，api_config 阈值）。实施面：
  ① core/runtime/observability/budget.py（BudgetGuard：check_pre_call =
  provider 调用前确定性拦截[fail 模式超限 → InterpreterError
  RUN_BUDGET_EXCEEDED，零浪费——被拦调用不发出]；record_post_call = 调用后
  累计[calls 成功/失败同计；tokens += usage.total，usage 缺失 = 0；wall =
  monotonic]；warn 模式每维度首次超限 stderr 告警一次[不重复不阻断] +
  exceeded 标记[批 4 result-json 面]；parse_budget_section 纯函数校验
  [正数/enum/未知字段 fail-fast，不静默忽略用户写错的预算]）；② 核算挂接
  _call_llm 汇点（与 journal 同源——单一核算点；check 在 try 前[拦截不包
  装为 LLMCallError]，record 成功/失败两面）；③ provider usage 提取
  （_extract_usage：OpenAI 兼容标准字段入 provider_meta[usage]——瞬态观测
  通道，契约不变；未上报 = 缺省）；④ CLI（api_config.json budget 节读取：
  节自身形态错 = [CFG_CONFIG_INVALID_BUDGET] exit 1；文件级损坏 = ai 模块
  自身校验面不重复报告）+ ServiceContext 槽 + engine 参数链（journal 同
  模式）。诊断码新增 2（RUN_BUDGET_EXCEEDED / CFG_CONFIG_INVALID_BUDGET，
  纯增面 + catalog + 15_diagnostics 两节 + parity 门过）。**C7 消重落地**
  （_next_phase_targets 批 3 清单 C7 = ~~消重~~：调用级埋点面由 journal
  行[ts/ts_mono] + 预算累计承载，不开第二条埋点管线）。实施裁定：预算是
  独立治理概念（区别于 VM 指令上限 RUN_LIMIT_EXCEEDED——失败语义单一权威
  源，不复用）；核算边界诚实记录（wall 仅在 LLM 调用点检查非轮询；流式不
  经汇点 = 不入 journal 同边界）。判别 22 项（runtime 白箱 18：parse
  校验/拒绝面 12 + guard fail/warn/维度 6；e2e CLI 黑箱 4：零侵入对照/
  fail 拦截[拦截前 2 次完成]/warn 告警显形/坏节拒绝）。全量 pytest **3727 passed /
  1 skipped 零回归**（语义错误集变更面：parity 门 + 全量过）。
---

- **R3-⑤ run 级可观测子系统完成（2026-09-08，free-explore）**：round3 需求
  R-1（journal + 确定性重放）+ R-3（预算核算）+ R-4（result-json）单一设计
  四批实施（设计文档 `tasks_docs/_run_observability_design.md`——试用方
  "治理可审计性命脉"：复测/审计零 LLM 成本、长 run 预算护栏、验收机告别
  grep stdout 文本面）。批 1 journal（b87d8a00）：LLMJournalWriter
  （append-only JSONL，schema v1 版本化；汇点 _call_llm 单一挂接成功/失败
  两面；写失败不阻断 run[观测侧信道尽力而为定位]；CLI 默认开 + --no-journal
  + stderr 提示行）。批 2 replay（bd55212b）：ReplayLLMProvider =
  LLMProvider 协议实现形态（能力槽 SYSTEM 优先级替换真实 provider，真实
  provider 不加载无需 key；seq 序重放/error 行同形态 raise/流式诚实
  拒绝[覆盖边界]；耗尽 fail-fast 经既有 LLMCallError 面[实施裁定：不新增
  专用码——改内核包装路径破坏面>收益]；重放 run 仍写新 journal[replay_of
  审计链完整]）。批 3 预算（5c05d73b）：BudgetGuard（api_config budget 节
  驱动；fail = provider 调用前确定性拦截 RUN_BUDGET_EXCEEDED[零浪费]；warn
  每维度首次告警一次；calls 成功/失败同计/tokens usage 缺失=0/wall
  monotonic）+ provider _extract_usage（OpenAI 兼容字段入 provider_meta）
  + 诊断码 +2（RUN_BUDGET_EXCEEDED/CFG_CONFIG_INVALID_BUDGET 纯增面 +
  catalog + 15_diagnostics + parity 门）+ **C7 消重落地**（_next_phase_
  targets：调用级埋点 = journal 行 + 预算累计，不开第二条埋点管线）。
  批 4 result-json（本条目）：stdout 末行单行 JSON trailer（v1 契约：
  exit_status/exception{code,message,source[含 snippet]}/journal/budget/
  replay；三 exit 面 ok/运行期/编译期——exception 复用既有诊断对象与异常
  字段，无新渲染管线；默认无 trailer 零侵入）。文档收敛：15_diagnostics
  §诊断工具 run 命令可观测面完整节（行级 flush/journal/replay/预算/
  trailer 五面 + 用法示例）。**架构要点**（系统统一性）：四面共享单一
  汇点（_call_llm：journal/预算/事件/call_info 同源同点，无第二条调用
  管线）；replay provider 走能力槽既有优先级机制（机制同构：provider 就是
  provider）；trailer 复用诊断对象（单一渲染源）。判别累计 59 项（批 1 11 +
  批 2 20 + 批 3 22 + 批 4 6）。全量 pytest **3739 passed / 1 skipped
  零回归**（批 4 后终态；各批间亦零回归）。
---

- **R3-⑥ E1 重做 + R-2a run_file 完成（2026-09-08，free-explore）**：ihost
  子环境整合（round3 需求 R-2a P0 + round2 遗留 E1；设计文档
  `tasks_docs/_ihost_subenv_design.md`；试用方实证摩擦"子环境不继承 LLM 配置
  + 需自身 api_config"修复）。
  **E1（子环境 LLM 配置继承）**：① 快照源裁定（对 HANDOFF 原设计措辞偏离，
  依据记录）——采用父 LLM provider 活状态快照（经既有 IbStatefulPlugin
  save/restore 契约——机制同构，跨引擎状态既有通道），弃用文件快照 +
  to_llm_config（api_config.json 只是配置初始源之一，活状态可经
  register_model/set_mock_mode/set_config 漂移；单一权威源 = provider 活
  _config）；② save_plugin_state 补 `_model_registry`（@NAME~ 命名模型注册表
  = 活配置状态一部分——既有状态保真缺口补漏，checkpoint/restore 同受益）；
  ③ engine run/run_string/execute 增 on_ready 参数（解释器 + 插件就绪后、
  执行开始前触发；None 零侵入）；request_spawn_isolated spawn 时点捕获快照
  （深拷贝不可变）+ 子线程 run(on_ready=_apply_llm_inheritance)；失败/不适用
  = kernel_diagnostic WARNING（新码 HOST_ISOLATE_LLM_INHERIT_FAILED，不阻断——
  与同域 KDIAG_RUNTIME_COLLECT_SKIP 同通道；实施裁定：issue_tracker = 编译
  诊断收集器，运行时告警非其职责面）；④ 语义面：子继承父 LLM 配置（mock
  态/端点/命名模型/生成参数）；子代码显式 load_project_config/set_config
  覆盖继承（时间序优先）；快照语义 = spawn 时点值（父后续变异不影响已
  spawn 子）。**ThrownException 消息面根因修复（判别面发现既有缺陷）**：
  str(ThrownException) 原 = IbObject 裸 repr（<LLMCallError object at 0x...>
  ——错误文本跨 VM 边界/子线程透传丢失）→ 显示面 = "TypeName: message"
  （Python 异常显示对等；类型名 + message 双保真；既有 4 项契约测试的
  类型名断言在新形态下仍满足——旧断言本经 repr 副作用成立）。
  **R-2a（ihost.run_file 进程内子 run + 结果捕获）**：语言面
  `ihost.run_file(path, policy) -> dict{exit_status, stdout, exception}`
  （**错误作值**——子失败不抛穿父；与 run_isolated 的错误作异常 + 导出变量
  字典互补 = 同一 spawn 机制的两个消费面，各负责子 run 结果的一个面，非
  双通道）；机制 = request_spawn_isolated（增 output_callback 参数——子
  print 收集）+ 同步 request_collect（子线程经独立引擎执行，不依赖父 VM
  线程，无循环等待）；防卡死 = collect_timeout 经 policy（IsolationPolicy
  既有面；默认无界文档化；超时 = exception 携带 timed out，daemon 孤儿
  语义既有）；TypeDef/接口协议/插件包装三面对称。
  文档：11_modules §11.6 整节更新（推翻"LLM provider 配置也不继承"旧表述
  + 继承语义/优先级/边界 + run_file 结果记录契约 + 防卡死）+ 15_diagnostics
  HOST_ 节 + parity 门。
  判别 15 项（runtime 白箱 8：快照深拷贝/registry 补漏/restore 面/apply
  成功/非 stateful 跳过警告/损坏快照 fail-safe/on_ready 时序 2 项 + e2e
  黑箱 7：继承 mock 保真/干净态对照 + 消息保真[非裸 repr]/快照语义[spawn
  后父变异]/run_file ok 记录/错误记录[错误作值]/stdout 捕获隔离/
  collect_timeout 防卡死）。孤儿线程 CPU 裁定（超时测试循环 10 亿 → 10 万：
  daemon 孤儿须套件时间尺度内收尾，不抢 CPU 拖垮全量套件——全量门 124 实证
  后修正）。全量 pytest **3770 passed / 1 skipped 零回归**（基线 3739 + 判别 15 + meta 按文件参数化增长）。
---

- **Tier B 质量巡检窗口完成（2026-09-08，Phase A 阶段边界）**：低强度批量
  巡检（code-quality 十查 + §九特征码扫描 + 兼容/兜底措辞扫描——本会话新面
  重点 + 全仓快扫）。**已修（低风险 7 项）**：① main.py `_source_dict`
  Locatable 面提纯（line/column 契约直取；file_path = Location 专属字段
  显式 None 默认 + 注释理由）；② ThrownException.__str__ hasattr 探测 →
  isinstance(IbObject) 协议化解箱；③ journal write_failed 半接通面接线
  （CLI 收尾面报告——写失败 stderr 警告"journal may be incomplete"；承诺
  的"收尾面报告"获得消费方）；④ test_budget_cli 死参数（budget_key 恒参）
  清理；⑤ test_ihost_llm_inheritance 未用导入（AI_MOCK_PREFIX）清理；
  ⑥ host/service.py 历史叙述注释移除（注释卫生：不叙述历史）；
  ⑦ provider_impl.py 模糊"保持兼容"措辞移除。**维持现状（合法保留 4 项，
  不扩窗处理）**：observability/snapshot.py getattr 探测（既有观测面
  duck-typed 跨层访问——Tier C 候选）；host/service.py save_state getattr
  链（既有检查点面）；budget/provider docstring"兜底"措辞（维度降级诚实
  描述：usage 缺失 → tokens 记 0，预算以 calls/wall 维继续功能——文档化
  设计非掩盖）；get_current_call_info 覆写链（协议层覆写 provider 层，
  文档化职责分离）。**待决断：无**。判别 = 受影响组回归 + 全量零回归
  （全量 **3770 passed / 1 skipped 零回归**——仅重构无新增测试，计数持平）。
---

- **R3-⑦ 诊断消息批完成（2026-09-08，free-explore）**：round3 P1 首项
  （D-6 顶层缩进提示 + D-8 小写布尔 did-you-mean + 原批 2 B4 编译定位并入）。
  核验面：D-8 既有已修（symbol_resolution_pass did-you-mean 面已存在——
  "Did you mean 'True'? IBCI boolean/null literals are capitalized"；intake
  时点前落地）= 本批锁定防回归。实施面：① D-6——parse_precedence 遇
  INDENT/DEDENT 期望表达式 = 缩进结构错乱 → stream.error 增 hint 参数
  （tracker 既有 hint 面）+ 定向提示"顶层语句须顶格（列 0）/ 块内同级缩进
  一致"（码面 PAR_UNEXPECTED_TOKEN 不变，提示定向不泛化——非缩进类语法
  错误无提示）；② B4——赋值型 SEM_TYPE_MISMATCH 定位精化 = RHS 值节点
  （实际违约源：变量/属性/下标两赋值路径 node → node.value）——实证前态
  `int x = "abc"` 定位 line 1 col 1（语句行首）→ 后态 col 9（"abc" 字面量）；
  二元运算定位（运算符位置）已精确不变。文档 15_diagnostics 三条目同步
  （PAR_UNEXPECTED_TOKEN 缩进提示 / SEM_UNDEFINED_SYMBOL 大小写 did-you-mean
  / SEM_TYPE_MISMATCH 定位面说明）。判别 8 项（test_diagnostic_precision.py：
  D-6 提示 2 项[D-6 有提示/非缩进无提示定向性] + D-8 锁定 3 项[true/false/none
  参数化] + B4 定位 3 项[变量 RHS/属性 RHS 精确列/调用 RHS 行]）。
  全量 pytest **3783 passed / 1 skipped 零回归**（基线 3770 + 判别 8 +
  meta 按文件参数化增长）。
---

- **R3-⑧ D-7 裸声明语义完成（2026-09-08，free-explore）**：round3 P1 第二项
  （设计裁定项——intake 初步倾向 (b) 精确诊断，设计对照后裁定 (c) 编译期
  检查）。语义面实证（开工复现）：语句域裸声明 `int x`（无初始值）编译通过
  但运行期**声明语句执行时即抛** RUN_TYPE_MISMATCH（define(x, None, int)
  类型校验——非"读取时"）；"从不读"的裸声明同样失败（int x + print('ok')
  抛错）= 裸声明在语句域**无任何合法运行期语义**（死语法）；对照面：类字段
  裸声明 = 构造器必填参数（合法形态，P(3) 可用）/ for 循环变量 / 函数形参 =
  合法。**裁定 (c) 依据**：① fail-first——无合法运行期语义的语法不应到达
  运行期（(b) 精确诊断治标：运行期检查仍在拒绝本可编译期拒绝的输入）；
  ② 一致性——类字段已编译期门禁（构造器参数），语句域裸声明同门禁；
  ③ (c) 包含 (b)——编译期精确定位声明语句（归因精确面达成）；④ (a) 零值
  缺省 = 魔法默认（fail-fast 纪律否决，intake 已判）。实施面：① 新码
  SEM_DECLARATION_WITHOUT_INITIALIZER（纯增面 + catalog + 15_diagnostics
  条目[含合法形态对照说明] + parity 门）；② visit_IbAssign 前置检查：
  node.value is None 且非类域（in_class_def 既有标志排除——类字段语义不
  同不在此限）→ 编译错（定位 = 声明节点）；③ 语义变更面评估：全量 pytest
  破坏面 = 0 既有测试依赖裸声明运行期行为（无既有代码依赖该死语法）——
  纯收紧（可编译→编译拒），无行为放宽。判别 9 项（test_bare_declaration.py：
  顶层/函数局部/多类型参数化拒绝 + 定位面 + 合法形态 4 项[类字段构造器/
  未传参仍 SEM_MISSING_REQUIRED_ARG/for 变量/带初始值/形参]）。
  全量 pytest **3797 passed / 1 skipped 零回归**（基线 3783 + 判别 9 +
  meta 按文件参数化增长）。
---

- **R3-⑨ D-10 json.parse 鲁棒面完成（2026-09-08，free-explore）**：round3
  P1 第三项（json 模块解析侧鲁棒面缺口——生成侧 C2 已落地）。缺陷面实证：
  parse 返回魔法包装键（数组 `{"_list": [...]}` / 原始值 `{"_value": ...}`——
  试用方"数组须包装"摩擦源）+ malformed = print 副作用 + 静默空 dict 双兜底
  （调用方无法区分"解析空对象"与"解析失败"）；stringify/pretty 同缺陷族
  （print + "{}" 静默回退）。**破坏性变更面评估**：`_list`/`_value` 包装键
  仓内零消费方（grep 实证）→ 安全移除。实施面：① parse 返回实际值（对象→
  dict / 数组→list / 原始值→标量；无包装键）——TypeDef 返回类型 dict→any
  （数据形态决定结果形态 = any 正当语义）；② malformed = JsonParseError
  （新插件级异常，code 属性 = RUN_JSON_PARSE_ERROR——VM 边界显式码透传机制
  原码透传，可经 try/except 捕获；fail-fast 替代双兜底）；③ 新增
  parse_or_none（显式宽松形态：malformed = None，无副作用——调用方按数据
  形态显式选择失败面[None 判定 vs 异常捕获]，非默认回退）；④ stringify/
  pretty 同缺陷族同修（失败 = JsonParseError，无 print、无 "{}" 静默回退——
  半修复禁止）。新码 RUN_JSON_PARSE_ERROR（纯增面 + catalog + 15_diagnostics
  + parity 门）。文档 11_modules §11.8 更新（parse 实际值语义 + parse_or_none
  + 失败面示例）。判别 13 项（test_json_robust.py：实际值 5[对象/数组/标量
  int/str/null] + fail-fast 3[可捕获/未捕获终止/码面] + parse_or_none 3
  [None/值/无副作用] + stringify 2[正常/循环引用抛错]）。全量 pytest
  **3816 passed / 1 skipped 零回归**（基线 3797 + 判别 13 + meta 按文件参数化增长）。
---

- **R3-⑩ F-2 思考抑制警告可配置完成（2026-09-08，free-explore）**：round3
  P1 第四项（F-2 真相核验后的处置：可配置静默 + 语义澄清——非机制缺陷）。
  缺陷面/语义面：① 警告走 **stdout**（数据面污染——审计/适配警告混入 run
  数据，试用方验收机解析 stdout 受影响）；② 试用方 4B 后端强制思考
  （run 存档实证：reasoning 隔离 reasoning_content 字段，content 干净）→
  警告每进程一次 = 已知行为下的噪音；③ 原警告文本"待完善覆盖缺口，联系
  开发者"——真相核验后语义过时（思考隔离机制下 content 不受影响，代价 =
  思考预算 tokens 消耗）。实施面：① 可配置静默——api_config.json
  `defaults.accept_forced_thinking`（bool，缺省 false）：true = 用户已知晓
  后端强制思考为已知行为 → 警告静默（CallDefaults 新字段纯增面 +
  config_loader 校验 + to_llm_config 映射 + apply_config 落地 _config——
  全配置链贯通；E1 继承面自动覆盖——_config 在快照内）；② 警告通道
  stdout → **stderr**（数据面纪律——与 journal/replay 提示行同定位）；
  ③ 语义澄清入警告文本（reasoning 隔离 reasoning_content / content 干净 /
  思考预算 tokens 消耗 / 观测面 provider_meta[reasoning]·journal / 静默
  途径提示）+ 声明失配提示面保留（config_declared_non_reasoning）。一次性
  去重（每进程一次）保持。文档 01_setup defaults 字段说明 + 思考抑制警告
  语义注记。判别 7 项（test_thinking_suppress_warning.py：配置落地 2 +
  静默/通道/澄清/失配/去重 5）。全量 pytest **3827 passed / 1 skipped 零回归**（基线 3816 + 判别 7 + meta 按文件参数化增长）。
---

- **R3-⑪ R-7 provider 429 退避完成（2026-09-08，free-explore）**：round3 P1
  第五项（provider 429 退避：retry.backoff_s 配置化 + call_info 退避事件记录）。
  缺口面实证：全仓无 429/rate-limit 处理、无退避 sleep（唯一 sleep = mock
  MOCK:SLEEP 模拟）——429 限流错误经 provider 包装为泛化 RuntimeError 立即
  上抛，重试层（llmexcept / __retry__）无退避立即重试 = 连续撞限流配额。
  实施面：① 配置——api_config `defaults.backoff_s`（float，缺省 0.0 = 不退避
  零侵入 opt-in）：CallDefaults 新字段纯增面 + config_loader 校验（
  _check_number）+ to_llm_config 映射 + apply_config 落地 _config（全配置链
  贯通；E1 继承面自动覆盖）；② 429 检测——provider `_is_rate_limit_error`
  （openai.RateLimitError isinstance 支 + status_code==429 属性支——供应商
  SDK 错误对象合法适配面，非字符串嗅探）；③ 退避执行——provider `call()`
  异常面（429 检测点）：检测命中 → `_apply_rate_limit_backoff`（sleep
  backoff_s + call_info 记录 last_backoff 事件{delay_s/reason/error}）→ 上抛
  （供重试层在退避后重试）。退避在 provider 层（唯一见原始 429 的点），
  重试层无感知（机制同构——重试循环不改动）。文档 01_setup defaults 字段 +
  429 退避语义注记。判别 11 项（test_rate_limit_backoff.py：配置落地 2 +
  429 检测 5[status 支/response 支/非 429 拒/泛化拒/真实 openai.RateLimitError
  isinstance 支] + 退避执行 2[事件记录/零缺省不记录] + 集成 2[call 遇 429
  退避+上抛/零缺省无事件]）。全量 pytest **3842 passed / 1 skipped 零回归**（基线 3827 + 判别 11 + meta 按文件参数化增长）。
---

- **R3-⑫ R-8 knowledge 扩展面完成（2026-09-08，free-explore）**：round3 P1
  第六项（knowledge 模块扩展面：export / history kind 过滤 / provenance 字段——
  均 P2 级价值，试用方手工替代已验证可行，排批内后段）。实施面：① provenance
  字段——store 第 4 参（可选，来源标记：知识出处——模块/文件/采集轮次等），
  入条目 + 经 export/history 可观测（审计"知识从哪来"）；② history kind 过滤——
  第 2 参（可选，"store"/"amend"）过滤事件类型，缺省 = 全事件（向后兼容）；
  ③ export()——整库导出（dict：键 → {value, check_name, provenance, events}
  审计链全量；值 = 快照深克隆防导出引用污染活库；供整库序列化/检视/迁移）。
  公理表：store params +provenance / history params +kind / 新增 export（内建
  方法声明最大参数列、运行期接受更少、编译期绑定非严格——str.find from_idx
  先例）。保真面：provenance 经深克隆（deep_clone 条目重建）+ 序列化（
  runtime_serializer _collect_knowledge 收集 + 水化 .get 默认空——旧快照无
  provenance 面兼容）+ to_native（原生表征完整性）全链随行不丢失。文档
  16_knowledge_system 条目模型 +provenance + 方法面 store/history 行更新 +
  新增 export 行。判别 11 项（e2e test_knowledge_extension.py：provenance 2
  [带/缺省空] + export 2[结构/多键] + history kind 过滤 4[amend/store/缺省全/
  未知空] + runtime test_knowledge_type.py provenance 往返保真 1）。全量 pytest **3857 passed / 1 skipped 零回归**（基线 3842 + 判别 11 + meta 按文件参数化增长）。
---

- **R3-⑬ N3 measure_freq 设计优先完成（2026-09-08，free-explore；待决裁定）**：
  round3 P1 收束项（N3 新解封；设计先行含 SiliconFlow logprobs 能力探测——端点
  不支持则记"待决"转其他项，不硬造通道；试用方 e26-e28 验收基线）。本项 =
  设计 + 探针实证交付物（**无代码/测试改动**——零回归面 = 文档面，全量 pytest
  计数不变）。探针实证（SiliconFlow 真实端点 api.siliconflow.cn/v1，openai SDK
  3.8.0 直连，模型 Qwen/Qwen3.6-35B-A3B）：① **chat completions**（IBCI provider
  现用通道）`logprobs=True, top_logprobs=5` = 400 校验错；仅 `logprobs=True` =
  **静默忽略**（接受参数但响应无 logprobs 字段——不报错、无数据）；② **legacy
  completions** `logprobs=N` = **完整支持**（返回 tokens/token_logprobs/
  top_logprobs 逐 token top 候选——样例 "The capital of France is" → " Paris"
  logprob -0.547，top3 含 " a" -2.172 / " the" -3.047）。**结论**：logprob 能力
  在 SiliconFlow 后端**存在**，但仅经 legacy completions 暴露；IBCI 的 chat 路径
  **不暴露**（通道形态约束，非 IBCI 缺陷）。**裁定 = 待决（挂起，方向保留）**，
  依据：① 与试用方自我裁定一致（corpus/probe 设计当前全手工、内化时机未到——
  e26-e28 为现成验收基线，无需 IBCI 承载即可跑通）；② 通道约束（落地须新增
  completions 形态通道 = 新面设计，非小改——与 PT-FEAT-16 embedding 面同属
  "收窄内容层数值面落外部 Python"边界，可同批评估）；③ 重估触发条件明确
  （provider 支持 completions/logprob 通道 或 corpus/probe 设计内化）。交付物：
  `tasks_docs/_n3_measure_freq_design.md`（定位/探针实证/设计影响/裁定/验收基线
  五节）+ handoff N3 行探针实证更新（单点）。不做什么：不在 chat 通道强行探测
  （静默忽略 = 探测无意义）；不为此新增独立数值科学计算面（同 PT-FEAT-16 排除项）。
---

- **R3-⑭/R3-⑮ P2 文档批完成（2026-09-08，free-explore；round3 P2 文档 howto 组 +
  R-5 弱模型测量 howto）**：纯文档批（**无代码/测试改动**——零回归面 = 文档面，
  全量 pytest 计数不变）。交付面：① **F-1《弱模型输出漂移测量》howto**（
  docs/howto/measure_weak_model_drift.md）——call_info 两形态[活面
  ai.get_current_call_info() 进程内最近值 / journal 持久面 llm_journal/<run-id>.jsonl
  跨运行语料] + finish_reason 最小用法[stop=正常 / length=达 max_tokens 截断——
  弱模型"没说完"漂移第一信号] + 漂移测量五步流程；② **F-3 fs.write --root 最小
  示例**（11_modules §11.7 追加）——实证语义：相对路径以 isys.project_root() 为
  基准解析、越出 project_root = RUN_PERMISSION_ERROR 沙箱拒绝（"Security Error:
  Permission denied ... path outside workspace"）；③ **D-9 保留词表**（
  SYNTAX_REFERENCE 追加）——lexer KEYWORDS 49 词单点清单（分类：import/函数/
  作用域/控制流/异常处理/类型/并发/逻辑/常量/LLM 健壮性），核验零缺失
  （表内 49 词全覆盖 lexer；小写 true/false/none 正确标注"非"关键字）；④ **F-4
  embedding 通道确认**（无 docs 动作）——PT-FEAT-16 已落地（embedding_impl +
  embedding_protocol），T16 8/8 验收，16 项 embedding 测试复核通过（通道可用：
  SiliconFlow Qwen3-Embedding-0.6B）；⑤ **R-5《弱模型提案稳定性测量》howto**（
  docs/howto/measure_proposal_stability.md）——journal 跨运行语料 + 稳定性度量面
  [完全一致率/归一化一致率/长度离散度 CV/截断占比/两两相似度] + 最小度量脚本 +
  结晶门槛判定（与知识注册表结晶验收衔接）。文档治理：README 单点真理表登记两
  howto；零日期戳/零任务编号（移除 R3-⑤ 引用）/零断链（引用面核验）/零 agent
  元信息（docs/ 面向人类）。**round3 队列全收束**（P0 R3-②~⑥ + Tier B + P1
  R3-⑦~⑬ + P2 R3-⑭~⑮ 全部完成/待决终态）。
---

- **Phase D meta 层/代码作值设计交付完成（2026-09-08，free-explore；设计交付，本运行
  不实施）**：round3 阶段 D（用户 2026-09-08 裁定：架构安全与长期收益优先，不半接通
  meta 层；实施待 VISION-4/5 类型类/函数式方向落地后推进）。交付物 = 单点设计文档
  `tasks_docs/_meta_layer_design.md`（**无代码/测试改动**——零回归面 = 文档面）。设计
  内容：① **安全执行架构**（run_file + meta.compile + R-6 行为表达式作值 统一）——
  分层为原语面（内核提供安全基元：compile[engine.compile_string 语言级暴露]/
  execute-isolated[ihost.run_file R3-⑥ 已落地]/capture[结果作值
  {exit_status,stdout,exception}]/judge[调用方机械判定]）+ 治理面（调用方用 IBCI 表达）；
  R-6 归位（复用统一原语面，值类型待 VISION-4）；② **安全模型选项 A**（用户 2026-09-08
  裁定：调用方表达治理 + 语言原语）——内核 = 安全基元提供者、调用方 = 治理策略表达者；
  三门管线（编译门 meta.compile / 隔离门 ihost.run_file / 判定门 调用方 judge）固化为
  文档化惯用法 + 参考实现（非内核强制机制）+ e34_p4 形态[预注册向量+机械判定]；选项 A
  依据[使命定位/单一权威源/可组合性]；ihost policy 参数 = 未来策略模型演进点（A 不堵死
  此路）；③ **类型层承诺需求清单**（VISION-4 开工输入，"自举台阶 ④ 只差类型层承诺"）——
  ① CompilationArtifact 作类型值 / ② RunResult 作类型值[dict→具名类型] / ③ BehaviorExpr
  值类型[R-6] / ④ fn[...] 高阶签名 / ⑤ Verdict 判定结果类型（what 非 how——how = VISION-4/5）；
  ④ **F5 档案重估结论**——档 A 缓存预编译/真 JIT 与 meta 层正交（挂独立性能线）、档 B 隔离
  改造/反射 = 长期主线、D-3.3 VM 字符串扫描快速路径维持长期登记（与演化平面设计合流规划）；
  meta 层不依赖任何 F5 档案项；⑤ **自举台阶 ④ 端到端架构**——台阶 ①-③ 已达成 → 台阶 ④
  [机制面已存在 + 类型层承诺待 VISION-4/5 + 治理面选项 A] → 自举闭环[IBCI 用 IBCI 表达
  "安全运行 IBCI 代码"治理]。边界：本运行不实施 / 不设计 VISION-4 类型理论本身 / 不设计
  真 JIT / 不内建治理引擎。**round3 全部阶段收束**（A P0 + B P1 + C P2 文档批 + D meta
  层设计交付）。
---

- **Phase E 原阶段 E 顺延批收束（2026-09-08，free-explore）**：round3 阶段 E（原批
  2 剩余 A2/A5/B2 + 批 3 A6/B5/C6/C7/D2/D3 终态裁定 + 两项实施）。**终态裁定**：
  ① **A2 泛型约束 / A5 解构模式匹配 / A6 Enum-tagged union / B2 惰性短路结构**
  = **挂起 → VISION-4 整合推进**（类型层语义项，与 VISION-4 类型理论加固[ADT/match/
  泛型约束]同域——round3 intake 已定"整合推进"；实施须待 VISION-4 类型理论设计落地
  后按该方向推进，禁止以"试用方急需"为由半接通——工作模式定论：禁止半修复/半接通）；
  ② **C7 性能内省** = 完成（R3-⑤ run 级可观测子系统消重——调用级埋点面 = LLM journal
  行 + 预算核算，不开第二条埋点管线）；③ **D3 新能力配套诊断码** = 挂起（随新能力
  配套——诊断码经纯增面随各特性落地，非独立批）；④ **B5 并发原语成熟化** = 挂起
  （chan/slot/subscriber/thread/thread_result 已是一等原语[14_concurrency +
  write_concurrent_tasks howto + KNOWN_LIMITS §二十二 边界完整]——基础成熟；具体
  成熟化专项需单独立项评估；流式调用观测边界[stream 不入 call_info]已记 KNOWN_LIMITS
  §五十为待评估）；⑤ **C6 流式/批量/多模型编排完善** = **完成**（多模型组合编排
  模式 howto——orchestrate_llm_calls.md 新增"多模型组合编排"节：强弱分工[强模型规划
  + 弱模型 @FAST~ 执行]/跨模型校验[生成 + 独立判官 @JUDGE~]/扇出聚合[多模型投票]三
  模式 + 命名路由 @NAME~ 机制面 + 关键语义澄清[行为表达式作容器元素保持 behavior 型
  须经类型变量强转；retry 是保留词不可作变量名——D-9 保留词表暴露的陷阱]；三模式
  示例均实测编译验证）；⑥ **D2 CLI inspect/check 导出** = **完成**（check 命令新增
  --format json / --output——静态检查诊断结构化导出[success + diagnostics{severity,
  code, message, location{file,line,column}, hint}]；check 与 compile 同源
  scheduler.compile_project，JSON 导出复用 compile 面捕获诊断序列化；默认 pretty
  形态不变零侵入；判别 4 项 test_check_export.py：成功 json/失败诊断面/输出到文件/
  默认 pretty 不变）。**round3 全阶段 + 原阶段 E 顺延批全部收束**（A/B/C/D/E 全部项
  处于完成/挂起/裁定不做终态——收敛判据达成）。全量 pytest **3867 passed / 1 skipped 零回归**（基线 3857 + D2 判别 4 + meta 按文件参数化增长；C6 纯文档无测试增量）。
---

- **Phase F 收敛——周期质量维护 Tier B 窗口 + 长期注册项状态复查（2026-09-08，free-explore；收敛判据达成后自主启动）**：
  round3 全阶段 + 原阶段 E 顺延批全部收束（A/B/C/D/E 全部项处于完成/挂起/裁定不做终态）
  → 收敛判据达成 → 周期质量维护于收敛判据成立时自主启动（AGENTS.md 排布：Tier B 定期窗口
  于主线阶段边界低强度批量巡检）。**Tier B 窗口**（code-quality 十查 + code-odor 特征码
  扫描全仓，只分类 + 只修低风险无契约影响项）：① 注释任务代号（红线——代码注释禁任务
  代号/PT 编号/历史叙述）扫描命中 4 处（vector.py 拆箱边界"C6 排除面" / ib_class.py
  auto-init"B4 声明化" / interpreter.py auto-init"B4 声明化" / _declaration_visitors.py
  协议签名"PT-DECIDE-3 项③"）——**已修**（移除任务代号，保留功能设计语义；注释不影响
  行为，低风险）；复核零残留。② 宽 except（except Exception: pass）扫描命中 3 处
  （events.py 事件发射 / _scheduler.py 线程清理×2）——**A 合法保留**（best-effort
  清理/关停/事件发射面，吞错合理且刻意，非错误吞噬异味）。③ 历史叙述注释扫描命中 7 处
  ——**A 合法保留**（"此前/旧的"均为功能语境[设计理由/已知问题/观测面变化说明]，非任务
  追踪，符合"注释注功能设计+已知问题"纪律）。④ 未用 import——linter 未装（pyflakes/ruff
  缺），手动扫描无命中。**长期注册项状态复查**（各项终态一致性核验）：VISION-4/5/6
  （PENDING_TASKS 远期，无排期）状态准确——补 VISION-4 开工输入指针（meta 层设计 §四
  类型层承诺需求清单 5 项 = VISION-4 开工输入 what 非 how + ref A2/A5/A6/B2 挂起整合推进）
  + 补 VISION-6 重估指针（F5 档案项与 meta 层正交，档 B 隔离/反射 = 长期主线，真 JIT 挂
  数据平面性能线，D-3.3 维持长期登记）；R-2b/R-6（meta 层，设计交付不实施）/ N3
  （measure_freq，待决——探针实证 chat 通道不支持）/ D-3.3（VM 快速路径，Tier C 候选）/
  远程 CI（待授权）状态一致，无漂移。**全量 pytest 3867 passed / 1 skipped 零回归**
  （基线 3867 不变——本窗口仅注释清理 + 文档指针，无行为变更）。
---

- **meta 层 MVP（字符串级直接执行）依赖评估 + 任务规划（2026-09-08，free-explore；用户定向再评估）**：
  用户问"语言级字符串直接执行是否可稳健推进？内核工程化紧随其后还是须先行？"——评估结论
  已写入 `_meta_layer_design.md` §八（新增实施任务规划节）：
  **① MVP 前置依赖 = 0（机制面全部既有并实证）**：compile_string/run_string 合成 entry
  `__string_exec__`（engine.py:316-337）/ request_spawn_isolated 子环境（新 Engine + 子线程
  + LLM 快照 + on_ready，engine.py:608）/ 字符串源扩展点 = 子线程体 `sub_engine.run(abs_path)`
  ↔ `sub_engine.run_string(code)` **同构单点**（同一 spawn 核心两源形式）/ E1 继承（R3-⑥）/
  collect_timeout 防卡死 / CompilerError.diagnostics 诊断面（R3-⑦）/ 值类型注册模式
  （file_handle/knowledge 先例）/ 模块注册模式（ihost TypeDef 先例）/ `meta`（模块名）与
  `run_result`（类型名）无占用非保留词（lexer KEYWORDS 核验）。MVP 缺口 = 纯新增面
  （run_result 值类型 + meta 模块 + ihost.run_code + 执行路径统一化）。
  **② VISION-6 内核工程化非前置**（用户问题二答案）：档 A 缓存/内核自举/真 JIT/反射 =
  无关（MVP 进程内单次，新增模块走既有注册模式）；**档 B 隔离改造 = 唯一交点**——MVP
  威胁模型 = 受信任候选代码（选项 A 调用方治理），既有进程内子环境隔离充分；威胁模型
  演进到对抗性代码 → 档 B 上修（MVP 落地后联合重估：新增隔离消费方 + 威胁模型边界实证）。
  依赖方向 = MVP 不依赖 VISION-6；VISION-6 档 B 在 MVP 后获得新重估输入。推荐顺序：
  MVP 先行 → MVP 后联合重估 VISION-6 档 B → VISION-4/5 类型层（全形态前置）。
  **③ MVP / 全形态范围重划（对 Phase D §七"防半接通"裁定的对账）**：MVP 边界 crisp
  自洽无空洞承诺（meta.compile = fail-fast 校验操作[成功 void/失败抛 CompilerError——
  纯既有机制，与 CLI check 面同构]；ihost.run_code = 字符串形式[同一 spawn 核心 + 错误作值
  + 类型化结果 run_result]；判定门 = 调用方普通 IBCI 代码）——试用方 R-2b 真实用例
  （候选代码执行 + 机械判定 e34_p4 形态）MVP 全满足；全形态（artifact 作类型值 / R-6 /
  fn[...] / Verdict）继续登记 VISION-4 依赖（§四清单收窄 ①③④⑤ + ② run_result 类型层
  深度参与——类型存在半被 MVP 满足）。user-principles 裁决四问通过（普适性 = code-as-value
  主流模式 Python compile/exec/Lua load+pcall/JS new Function；架构合理性 = 机制同构无新
  执行模型；实测优于现状 = 消除试用方手写临时文件 + run_file 胶水绕路；非机械遵循历史 =
  范围重划尊重"不半接通"原则而重划范围）。
  **④ 批次计划**（每批 = 设计确认 → 实现 → 全量 pytest 零回归 → 落账 → commit）：
  **M1** = run_result 值类型（axiom + TypeDef[KERNEL_NATIVE] + 深克隆 + 序列化 + to_native
  全链照先例；字段面 exit_status: str[ok/error] / stdout: str / exception: any[None 或
  结构化 dict {code, message, source{file,line,column,snippet}}]——exception 捕获面从
  既有平坦错误串升级为结构化[CLI --result-json exception 面同构，统一设计语言]）+ 执行
  路径统一（request_spawn_isolated 子线程体提取单一 spawn 核心：文件形式 = run(abs_path)
  [R3-⑥ 行为不变] / 字符串形式 = run_string(code)[新，sub project_root = 父 project_root
  合成 entry 锚定]）+ ihost.run_file 返回值 dict → run_result 精化[破坏性精化：消费方仅
  本轮判别测试 → 安全] + 新 ihost.run_code。
  **M2** = meta 模块（_SPEC_META：KERNEL_NATIVE + IMPORT_GATED；compile(code: str) →
  void）+ 实现 = 子引擎 compile-only（新 Engine + compile_string，零父状态污染——父程序
  可能自身即字符串运行[合成 entry 同名冲突面]；compile-only 无需 LLM 继承/防卡死）+
  失败抛 CompilerError[ibci 源定位：合成 entry 标记 + line/column]。
  **M3** = 三门管线惯用法固化（howto run_code_safely.md[meta.compile 校验 + ihost.run_code
  执行 + 机械判定参考实现] + README 单点真理表登记 + 设计文档 §四/§七 对账注记 +
  NEXT_STEPS/PENDING_TASKS/HANDOFF 同步）。**M4（登记不启动）** = 全形态
  （CompilationArtifact 作类型值[meta.compile 返回值 void → Compilation 接口扩展] / R-6 /
  fn[...] / Verdict）← VISION-4/5。
  **⑤ 边界注记**（M1 实施时入 KNOWN_LIMITS）：威胁模型 = 进程内子环境隔离（变量不继承 /
  LLM 继承 / fs 沙箱 / 防卡死），**非对抗性代码安全边界**（无进程级隔离）；性能 = 每
  run_code/meta.compile 一次子引擎构造（候选验证场景充分；热循环 = VISION-6 上修输入）。
  **⑥ 诊断码面**：预期零新码（meta.compile 复用 PAR_*/SEM_* 码族；run_code 子运行失败 =
  既有码经 exception 值面传递）；若实施中确需新码按纯增面纪律。
  本条纯评估 + 规划（设计文档/台账更新，无代码改动，零回归面 = 文档面）。MVP 实施自
  M1 起按 NEXT_STEPS 当前 P0 推进。
---

- **本 session 分支拓扑 + goal 配置（2026-09-08，free-explore）**：用户直接指示——
  开启代码修改前把现阶段 free-explore 代码 merge 到 unsafe-vibe-dev，后续开发继续在
  free-explore 分支进行。执行：free-explore 相对 origin/unsafe-vibe-dev = 0 behind /
  105 ahead（merge-base = origin tip b89fdc39，纯 fast-forward，零冲突零分歧）；建本地
  unsafe-vibe-dev 分支并 `--ff-only` merge free-explore → unsafe-vibe-dev = free-explore
  = b67d87b0。**全本地不 push**（硬原则未授权 push；main 不触碰）。free-explore 不删除
  （本 session 后续在其上开发——偏离历史"短期工作分支合并即删"细则，用户明示，属 session
  级分支裁定）。merge 前置复跑全量 pytest 3867 passed / 1 skipped 零回归。配置长期 goal
  （meta 层 MVP 无人值守，max_goal_rounds=7，按 HANDOFF §1.2.1 习惯）；主线 M1→M2→M3
  依 `_meta_layer_design.md` §八 批次计划推进。
---

- **meta 层 MVP M1 实施（2026-09-08，free-explore）**：run_result 内核原生值类型 +
  执行路径统一（ihost.run_file dict→run_result 精化 + ihost.run_code 落地）。M1 落地
  细化（`_meta_layer_design.md` §八.4 未定实现取舍的定案）：
  ① run_result = 不可变值类型（CLASS kind / parent Object / PRELUDE 可见——同
  knowledge/environment 先例；命名与 thread_result 区分[非泛型]）；② 字段访问面 =
  **字段**（attribute，`r.exit_status`/`r.stdout`/`r.exception`，`MemberSpec
  kind="field"` 经 `_dispatch_getattr` 实例字段优先命中——Exception.message 先例；
  设计 §8.3 明言"字段面"；非方法[误导须括号]非下标[map 语义]）；③ exception 结构化
  `{code, message, source{file,line,column,snippet}}` = 单一权威源
  `core/runtime/exception_record.py`（CLI --result-json + host run_file/run_code 共用，
  消双写真相；main.py `_extract_compile/runtime_error` 委托之）；④ 执行路径统一 =
  `request_spawn_isolated` 单一 spawn 核心两源形式（文件源 entry_path[既有行为不变]
  XOR 字符串源 code[新，sub project_root = 父 project_root 合成 entry `__string_exec__`
  锚定]，fail-fast 恰好一源；两源共享 E1 继承/沙箱/防卡死/输出捕获/错误作值）；⑤
  deep_clone 不可变引用复用[同 vector] + serializer collect/hydration + 全链值类型
  注册模式。诊断码零新增（子运行失败经 exception 值面传递既有码；字符串源沙箱外 =
  既有 RUN_PERMISSION_ERROR）。判别：runtime test_run_result_type 12 项[字段 attribute
  访问/exception None/未知字段 fail-fast/值相等/不可哈希/to_native/deep_clone identity/
  cast_to str·违约/序列化 round-trip/类型锁] + e2e test_ihost_run_file 4 项[精化：字段
  访问 + 结构化 exception + 超时] + test_ihost_run_code 7 项[成功/运行异常
  RUN_DIVISION_BY_ZERO/字符串源编译错误 PAR_ 码作值/超时[孤儿负载压低至 ~20000 迭代
  ·~3.75s 防看门狗]/沙箱内 ok/沙箱外 RUN_PERMISSION_ERROR/E1 LLM 继承]。全量
  3896 passed / 1 skipped 零回归（首跑 GC 收尾孤儿线程拖过 180s 看门狗[run_code 超时
  孤儿 ~100k/18s 叠加既有 run_file 孤儿]——裁定：run_code 超时循环 100000→20000[仍 >1s
  触发超时，孤儿寿命 ~3.75s]，稳定复跑 164s 退出 0）。M2（meta.compile 编译门）接续。
---

- **meta 层 MVP M2 实施（2026-09-08，free-explore）**：meta 模块 + meta.compile 编译门
  （代码作值 fail-fast 校验面）。M2 落地裁定（`_meta_layer_design.md` §8.4 M2）：①
  meta = 新内核原生模块（KERNEL_NATIVE + IMPORT_GATED，_SPEC_META：`compile(code: str)
  -> void`）；② 实现 = 子引擎 compile-only（新 IBCIEngine 锚定父 project_root，零父状态
  污染[父可能自身即字符串运行·合成 entry 同名冲突面]；compile-only 无 LLM 继承/防卡死
  [编译不执行]）；③ 编译失败 fail-fast：compile_string 的 CompilerError[引擎级诊断集]
  翻译为**可被 IBCI try/except 结构化捕获**的 InterpreterError[首个诊断 = 根因面，携带
  ibci 源定位——诊断码 + 合成 entry 标记 `__string_exec__.ibci` + line/column；message
  含源定位]。裁定：不引入新 IBCI 异常类型（MVP 不新增 CompileError 类型——复用既有
  Exception 捕获面 + InterpreterError 定位透传）；源定位 file_path 从 compile_string 的
  tempfile 载体重写为合成 entry 标记[字符串源可辨识，替代实现细节]（原生函数边界对
  CompilerError 会扁平化包装[functions.py]，对 InterpreterError 透传[IbTry 捕获 str()
  含定位]——翻译面即据此）；④ 成功静默（void）——与 CLI check 面同构（compile-only +
  失败即断）。诊断码零新增（复用 PAR_*/SEM_* 码族）。判别：e2e test_meta_compile 7 项
  [成功静默/语法错误捕获/语义错误捕获/message 含 ibci 源定位[marker+line1+col9+PAR_]/
  父状态零污染/compile-only 不执行/mock 模式无 LLM 依赖]。全量 3909 passed / 1 skipped
  零回归。M3（三门管线惯用法固化）接续。
---

- **meta 层 MVP M3 实施（2026-09-08，free-explore）——MVP 主线收束**：三门管线惯用法
  固化（纯文档批，零代码变更[docs 面]，test 计数沿用 M2 3909/1 零回归）。交付：① 新
  howto `docs/howto/run_code_safely.md`（代码作值安全执行：三门管线[编译门 meta.compile /
  隔离门 ihost.run_code[run_result] / 判定门 调用方机械判定] + 完整参考实现[预注册
  期望向量 + 机械判定 e34_p4 形态，实测编译运行验证：候选 A 三门全通过 + 候选 B 编译门
  拒绝[PAR_ 码 + ibci 源定位]] + 安全保证与边界[威胁模型=非对抗性/性能=每调用一次子引擎]
  + 常见陷阱[布尔字面量大小写 / run_result 值类型非 dict / 判定门调用方职责]）；② README
  单点真理表登记（howto 目录树 + 单点真理行）；③ 跨文件一致性修正——use_isolation.md
  "常见陷阱" 旧"LLM provider 配置不继承"表述（E1 前残留）→ 更正为"自动继承父 LLM 配置
  [spawn 时点快照] + 子代码显式覆盖[时间序优先]"（跨文件一致，零断链）；④ 台账同步：
  设计文档 `_meta_layer_design.md` 头部状态[设计交付→MVP 实施中 M1/M2✅] + NEXT_STEPS
  [MVP 主线收束→转稳定维护态] + PENDING_TASKS VISION-4 [MVP 落地注记] + HANDOFF §2.1
  [M3✅/MVP 收束/候选后续主线 VISION-4]；⑤ 删除 M1 临时实施文档 `_code_meta_mvp_m1.md`
  [内容已收敛入 WORKLOG M1 条目 + 设计文档 §八.4；MVP 完成后按文档生命周期删除]。
  **meta 层 MVP（M1 run_result+执行路径统一 / M2 meta.compile / M3 三门管线 howto）主线
  收束**——全形态（M4：artifact 作值/R-6/fn[...]/Verdict）登记 VISION-4/5 类型层前置不
  实施（防半接通原则不变）。候选后续主线 = VISION-4 类型理论加固[开工输入就绪] / round4
  需求单到达重新 intake / 周期质量维护。
---

- **VISION-6 内核工程化 Phase 0 现状实证调查 + 数据平面性能基线（2026-09-08，free-explore，
  主线转移后首阶段交付；只读调查未改代码，末次全量 3909/1 零回归以实跑为准）**：
  ① **架构实证**（引实际代码/文档 path:line）：编译管线五阶段无字节码/IR 层——项目扫描+词法+
  依赖图（scheduler.py）→ 逐模块编译（Parser→AST class IbModule）→ 语义分析 4-Phase 流水线
  [Symbol/Type/Binding/Integrity，产物写 AST 节点字段+MetadataStore]（semantic/pipeline.py）→
  FlatSerializer 序列化[AST→扁平 UID 池，**node_uid = 内容哈希 node_{sha256[:16]} 确定性**
  （serializer.py:127-128，UID 权威源 core/base/uid.py）→ ImmutableArtifact]→ 水化执行
  （interpreter.py 水化为运行期 node_pool[dict 池]，ReadOnlyNodePool 只读代理）。**VM 数据面
  = AST 直走的 CPS/生成器解释器**（VMExecutor._drive_loop_gen，显式帧栈非递归，50 个
  vm_handle_IbXxx 经 node_type 字符串查表分派；Signal 经 StopIteration.value 数据化传递；
  函数调用 trampoline；LLM dispatch-before-use Waitable 协作挂起）。
  ② **单语句/单节点开销实证（JIT/快速路径目标点，5 条）**：(1) 每语句新建 TaskScheduler
  （run_body 逐 stmt 调 run()→vm_executor.py:144）；(2) 每节点生成器分配（非生成器 handler
  中央化包装 _gen，vm_executor.py:405-411）；(3) 每节点 dict + ReadOnlyNodePool 递归代理
  （get_node_data，interpreter.py:406-412）；(4) 分派查找 node_data["_type"] 字符串查表；
  (5) StopIteration 异常驱动正常控制流（每帧完成走 except StopIteration）。
  ③ **D-3/D-3.3 实证（唯一既有性能数据）**：VM 逐字符操作经生成器分派 ~1000× 开销（试用方
  sub_str 逐字符 12k 窗口挂起 >180s；机制栈扫描 170-200s vs Python <0.1s）；已落地缓解 = R3-③
  内建 str 四件套 O(n) 原生方法（消解 90%+ 摩擦）；D-3.3 VM 逐字符分派快速路径本身 = 登记不
  实施（Tier C 候选）。
  ④ **JIT 就绪度**：已有 = 编译期 bench CLI（main.py bench，仅测编译非执行）+ 内存 mtime 增量
  缓存[非持久] + 确定性内容哈希 node_uid[磁盘缓存天然地基] + O(n) str 原语 + 并发墙钟测试；
  缺失 = 执行期性能基准/profiler + 字节码/IR 层 + JIT + VM 热点快速路径 + 持久 artifact 缓存。
  ⑤ **JIT/快速路径插入点（受 9 项 VM 设计不变量 04_vm_interpreter §11 约束，不可绕过统一执行
  入口 #1）**：(a) 确定性子树内联特化求值[产出仍交回 CPS 帧栈]；(b) 模块级复用持久
  TaskScheduler[消除逐 stmt 构造]；(c) 去 ReadOnlyNodePool 每节点递归代理；(d) D-3.3 字符串
  扫描快速路径；(e) 真 JIT codegen[最高风险，隔离分支]。
  ⑥ **分阶段路线图 P1→P7**（排序 = 价值/依赖/可验证性，数据平面/真 JIT 用户点名优先；每阶段
  闭环 = 设计确认→实现→全量零回归→落账→本地 commit[禁 push]；高破坏性/边界不清走独立隔离
  分支永不触碰 main）：
  - **P1 执行期性能基准 + 热路径 profile**（⭐低风险先行，纯观测无行为变更，解锁 P2-P5 全部
    性能工作[改前/改后裁判]）：建执行期基准 harness[代表性程序集 算术/循环/函数递归/字符串/
    容器/类方法/并发 + 计时协议，区别于 main.py bench 编译期] + cProfile 量化 CPS 热路径
    [send 步/每节点生成器/代理/StopIteration/逐 stmt TaskScheduler]→ 定量基线。
  - **P2 数据平面快速路径 #1：每节点开销消除**（⭐优先、中风险）：§11 不变量内消除 ①的
    5 条开销（内联特化 + 持久 TaskScheduler + 去每节点代理），严格保留 EXEC-1/2/Signal/协作
    挂起；验收 = P1 基准可测执行时间下降[如热程序 -30%+] + 行为等价判别 + 全量零回归。
  - **P3 D-3.3 字符串扫描快速路径**（中高风险）：VM 侧逐字符/字符串分派快速路径（消除 char
    级生成器分派，下沉原生 O(n)）；验收 = D-3 复现程序 挂起/170-200s → Python 同量级。
  - **P4 真 JIT（代码生成）**（⭐用户点名优先、**高风险→隔离分支**）：§11 约束下生成更快执行
    体（Python codegen 到闭包/字节码 保持 receive 分派+Signal+Waitable；或引入受约束 IR/字节
    码层[须评估与 AST 直走不变量冲突]）；验收 = P1 基准 JIT vs 解释吞吐比 + 语义等价判别 +
    隔离分支实验通过。
  - **P5 档 A 缓存预编译（持久 artifact 缓存）**（中风险、编译期面与 JIT 正交，可并行）：按
    源码内容哈希键[复用确定性 node_uid]持久化 FlatSerializer 产物，re-run 命中跳过
    lex/parse/semantic + 保真校验[水化 round-trip] + 沙箱边界[路径规范化]；验收 = 二次 run 编
    译时间 → ~0 + 失效正确性判别。
  - **P6 内核自举（bind 表达内核契约）+ 反射能力**（高工作量、结构面）：内置契约[
    builtin_modules.py 字面量单一权威]再表达为 bind 声明（解 F5"bind 运行时 vs 构造期时序"矛盾
    ）；反射 = 元数据/协议面（喂类型层）；验收 = 行为等价 + 全量零回归。
  - **P7 档 B 隔离改造（进程级隔离）**（高风险→隔离分支）：威胁模型演进到对抗性代码时进程级
    隔离上修（现为进程内子环境，KNOWN_LIMITS §二十六）；验收 = 对抗性用例正确拒止。
  ⑦ **风险分层**：低风险先行 = P1[纯观测] + P5[编译期不动执行模型]；优先主线[数据平面/真 JIT
    用户点名] = P2 → P3 → P4[高风险隔离分支]；结构/高风险 = P6 + P7[排性能线之后，避免执行模
    型剧变中并动契约/威胁模型面]；P5 可并行 P2-P4[编译期 vs 执行期不同轴]。
  ⑧ **硬约束**（任何 JIT/性能/工程化工作必遵守）：9 项 VM 设计不变量[统一执行入口/控制流
    数据化/执行帧抽象/LLM 通道唯一/公理层无运行时依赖/isinstance(IbXxx) 禁用/快照隔离/阻塞
    即挂起/调度器永不阻塞] + 元数据/AST 不变量[AST 不可变蓝图、静态分析写 AST 节点、确定性
    UID 单一权威源[**不得改变已产出 UID 值**]、侧表编译期临时、运行只收 UID] + 公理化可验证
    规范 05_vm_specification.md + 工作模式定论[禁 compat shim/胶水/tricky]。
  ⑨ **裁定/决定**：Phase 0 完成（架构实证 + 开销量化 + 路线图）；**P1 = 唯一低风险先行且解锁
    后续一切性能工作的阶段，下一轮直接开工 P1**（执行期基准 harness + 热路径 profile → 定量
    基线）。P4/P7 须先开独立隔离分支实验。所有 JIT/快速路径须在 §11 不变量 #1[统一执行入口]
    内推进（"不绕统一入口提性能"核心设计假设，P2 为第一块试金石）。
---

- **VISION-6 P1 执行期性能基准 harness + 数据平面热路径 profile（2026-09-08，free-explore）——
  性能线改前/改后裁判交付**：① **新执行期基准 harness**（`scripts/perf_bench.py`，区别于
  `main.py bench` 编译期）：6 项代表性程序[算术 arith/分支 branch/递归 recurse[strampoline
  调用帧]/字符串 string[D-3 热路径]/容器 container/类方法 class[协议分派+实例化]] + warmup +
  N 次取中位 + 每迭代成本[规模无关主指标]；可复现（改前/改后相对比较）。② **执行期基线
  （us/iter，本机实跑，warmup+3 取中位，以实跑为准）**：arith 257.1 / branch 372.4 /
  recurse 5954.6[函数调用 ~10× trampoline 开销] / string 286.6 / container 273.3 / class
  688.7[实例化+方法分派]。**关键发现：string 项 = 286.6 us/iter（非历史 D-3 ~1000× 逐字符
  开销）——R3-③ str 四件套 O(n) 原生方法已消解逐字符热点，`s + 'x'` 现走 O(n) 原生拼接
  [144ms/500 iter = ~1.16 ns/char-copy]**（P3 D-3.3 VM 侧快速路径的紧迫性因此下调：执行
  面 str 已 O(n)，余量 = 更深的 VM char 级分派/字符串热路径）。③ **热路径 profile（cProfile
  arith N=1e4，8s[含 ~3× cProfile 开销，绝对值膨胀但相对占比有效]）——主导成本 = 值层分派
  而非 CPS 控制流结构**：(a) **isinstance 分派（不变量 #6 `isinstance(obj, IbValue) and
  ib_class.name == ...`）= 2.8M 次调用 / ~2.2s = 单一大头**（每 binop/assign/compare 多次
  类型身份判定）；(b) **box（native→IbValue 装箱）= ~2.5s**（每个原生运算结果装箱：
  registry.box + bootstrapper.box）；(c) **receive（协议分派）= ~2.3s**（60k 次属性/方法
  分派）；(d) **inspect.getattr_static = 200k 次 / ~1.1s**（协议/vtable 查找经 inspect 反射）；
  (e) **ast_view.get（ReadOnlyNodePool 每节点 dict 代理）= 490k 次 / ~0.63s**；(f) **_gen
  [每节点生成器包装] = 20k / ~0.57s**；(g) **_make_task = 110k / ~0.94s**；(h) TypeRef.from_spec
  = 80k / ~1.06s（类型解析）。④ **P2 目标裁定（据 profile 量化）**：**数据平面开销主导 = 值
  层分派（isinstance/box/inspect/receive），非 CPS 循环结构**——故 P2 首个数据平面快速路径
  优先攻**值层分派**（低风险高收益，且"不绕统一执行入口"核心假设的试金石）：(1) isinstance
  分派降频[类型身份缓存/更省判定路径，目标 2.2s 大头]；(2) 去 inspect 反射[协议/vtable 直查，
  目标 1.1s]；(3) box 装箱降频[热数值运算路径，目标 2.5s]；(4) ast_view 每节点代理直读[目标
  0.63s]。**CPS 循环结构重构（每语句 TaskScheduler 合并/每节点生成器消除）= 更硬的后段项
  （P2 后段或 P4 真 JIT 范畴）**。硬约束复申：任何上修须保留 §11 不变量（#1 统一执行入口/
  #2 控制流数据化/#6 isinstance 分派形态可优化但判定语义不变/协作挂起/调度器不阻塞）。
  ⑤ 全量零回归待验（harness 纯观测+落账，无行为变更）；P1 交付 = harness + 基线 + profile +
  P2 目标裁定，**P2 = 下一轮开工（值层分派快速路径，isinstance/box/inspect 三目标）**。
---

- **VISION-6 P2·step1 数据平面快速路径 #1a（2026-09-08，free-explore，commit e2949d2b）**：
  P1 profile 定位值层分派主导，首个快速路径攻 **AST 只读视图重复包装**（profile：
  ast_view.get ~490k 次/程序）——消除逐次节点访问的 ReadOnlyNodePool 重包装。交付（§11
  不变量内，不绕统一执行入口）：① interpreter.get_node_data 缓存只读视图（node_uid →
  ReadOnlyNodePool，per-interpreter；同一节点反复访问[循环体]复用同一视图实例，消除逐次
  外层包装；随解释器回收无泄漏）；② ReadOnlyNodePool._wrap 记忆化（id → 已包装视图，
  per-instance；AST 节点不可变且生命周期内存活[id 稳定]，重复字段访问命中缓存，消除逐次
  嵌套 dict/list 递归重包装）。只读语义不变（视图不可变）；62 处调用点无身份依赖（仅
  is None）。**改前/改后（perf_bench，µs/iter，warmup+3 取中位）一致 ~6-9%**：arith
  257.1→240.5 / branch 372.4→343.5 / recurse 5954.6→5429.9 / string 286.6→270.8 /
  container 273.3→255.8 / class 688.7→624.7。全量 3909/1 零回归。
  **P2 后续（值层分派更大头，更硬核心分派面，下一步评估）**：isinstance 分派[~2.2s，2.8M
  次；热站点 = runtime_context 变量赋值类型校验[每赋值 ~7 次 isinstance + 句柄物化/spec
  兼容检查，简单 int/str 赋值也全跑] + binop/compare handler + receive] / box 装箱[~2.5s，
  每原生值转换] / inspect 反射[~1.1s，typing.Protocol isinstance 经 inspect.getattr_static]。
  这些触及核心分派/类型安全逻辑，风险高于 ast_view 视图缓存（后者纯只读视图复用，零行为
  变更面）——step2 起逐个评估（低风险先行）。
---

- **VISION-6 P2·step2 数据平面快速路径 #1b——TypeRef.from_spec 按 spec 缓存（2026-09-08，
  free-explore，commit 62194fb9）**：P1 profile 定位值层分派中 **TypeRef.from_spec ~80k
  次/程序**（每标量装箱一次，IbValue.__init__ 触发，profile 1.06s）。裁定：TypeRef 仅由
  spec 字段派生（name/kind/module/element/key/value/wrapped，**非 members**）+ spec 不可
  变（单一类型身份源）→ 同 spec 结果恒定 → 按 spec 实例缓存。实现：① from_spec 拆为缓存
  包装 + `_from_spec_uncached`（既有逻辑原样保留，多 return 点不动）；② 缓存键 = spec
  实例（生命周期内 id 稳定；`_type_ref` 为实例属性[非 dataclass 字段]，不影响 asdict
  序列化/eq；frozen 异常路径缓存失败不阻断构造）。**改前/改后（perf_bench，µs/iter，
  warmup+3）一致 ~11-18%**：arith 240.5→196.7 / branch 343.5→281.4 / recurse 5429.9→
  4816.5 / string 270.8→227.2 / container 255.8→222.4 / class 624.7→557.2。累计 P2（step1
  AST 视图缓存 ~6-9% + step2 TypeRef 缓存 ~11-18%）≈ **-11%~-24%**（vs P1 基线 257/372/
  5955/287/273/689）。全量 3909/1 零回归。
  **P2 调查结论（同批，自纠错）**：box 装箱 per-call 开销[Uncertain 串比较 + memo={} 分配]
  + _check_type isinstance 复用[5→1] = 均 **wall-clock wash**（isinstance 为廉价 C 级检查、
  分散多站点[~28 处]，per-call 节省在 ~2% 噪声内）→ 已回退；per-stmt TaskScheduler 仅
  顶层语句（非循环迭代热路径，while 体经 handler 内部 CPS 驱动）→ 非热点。inspect.
  getattr_static[~200k/1.1s] 源非热路径直接 isinstance（vm_executor/loader 仅 setup 用
  inspect.isgeneratorfunction/signature）→ 未定位到热路径可削减点，暂搁。
  **P2 数据平面 CPS 内可干净削减项裁定**：AST 视图缓存[step1] + TypeRef 缓存[step2] =
  已落地（累计 ~11-24%）；剩余主导成本 = **CPS 生成器协议[每节点 send/StopIteration] +
  每节点分派**（_drive_loop_gen 主导）= 真 JIT/P4 范畴（核心执行模型改动，高风险→隔离分
  支）。P2（CPS 内数据平面快速路径）主体完成，P3/P4 接续。
---

- **VISION-6 P2·后段 数据平面快速路径 #1c——CPS 循环每节点 is_generator 建表期预计算
  （2026-09-08，free-explore，commit 5dc56f03）**：P1 profile：_make_task 每节点调用
  inspect.isgeneratorfunction(handler)（~110k 次/程序，反射开销）。裁定：handler 为模块级
  函数，生成器身份恒定 → 建表期一次判定（_handler_is_generator 缓存；dispatch 表建表后
  只读[无扩展点]，缓存与表一致），运行期查表免反射。改前/改后一致 ~4-9%：arith
  196.7→179.7 / branch 281.4→262.9 / recurse 4816.5→4513.6 / string 227.2→215.2 /
  container 222.4→212.9 / class 557.2→524.4。**累计 P2（step1 AST 视图缓存 + step2
  TypeRef 缓存 + 后段 is_generator 缓存）vs P1 基线：arith -30.1% / branch -29.4% /
  recurse -24.2% / string -24.9% / container -22.1% / class -23.9%**——算术/分支热程序
  达 ~30% 数据平面目标（P1 设计验收阈值）。全量 3909/1 零回归。
  **P2 数据平面快速路径小结**：CPS 内可干净削减项已全部落地（AST 只读视图缓存 + TypeRef
  按 spec 缓存 + 每节点 is_generator 建表期预计算），累计 ~-22%~-30%。剩余主导成本 =
  CPS 生成器协议核心[每节点 gen.send/StopIteration] + 每节点分派 = 真 JIT/P4 范畴（核心
  执行模型改动，高风险→隔离分支）。P2 收束，P4（真 JIT）/ P5（持久 artifact 缓存，编译
  期可并行）接续。
---

- **VISION-6 P4 真 JIT·设计确认 + 最小可行 codegen 实验（2026-09-08，free-explore，设计
  commit 7e091cfd）**：P2 收束后数据平面剩余主导 = CPS 生成器协议核心/每节点分派 = 真 JIT/
  P4 范畴（用户点名优先·高风险→隔离分支）。本轮完成 P4 设计确认（`tasks_docs/_p4_jit_design.
  md`，route ① Python codegen，codegen 体作为 CPS 循环内快速路径[保统一入口+Signal 数据化+
  receive 分派，§11 九项不变量合规表]）+ 最小可行 codegen 实验（隔离分支 p4-real-jit，已删）。
  **设计要点**：插入点 = `vm_handle_IbWhile` line ~103（循环体 `yield from _vm_execute_stmt_
  sequence`）/ `_vm_call_function` line ~445（函数体）；codegen 体经 `rt.get/set_variable_
  by_uid`（O(1) 作用域）+ `receive`（协议分派，binop 经 OP_MAPPING）+ `return Signal(...)`
  （控制流数据化）直接执行直线体，绕开每节点 CPS 生成器协议；安全子集 v1 = 直线赋值序列
  （排除嵌套控制流/LLM/IO/异常/函数调用/复合赋值/多目标）。验收判据 = arith/branch ≥2× P2
  基线 + 全量 pytest 零回归 + 语义等价判别测试。
  **最小可行 codegen 实验发现（自纠错，已回退）**：codegen 体（生成 `_jit_body(rt)` 函数，
  经 exec 一次创建）在 `vm_handle_IbWhile` 内被调用时，`rt.get_variable_by_uid('scope___
  string_exec__:i')` 返回 None（循环变量 `i` 读不出）→ `int.__add__` 报 `unsupported operand
  type(s) for +: 'int' and 'NoneType'`。符号 UID 正确（target/value 节点 `node_to_symbol` 均
  解析到 `scope___string_exec__:i`），但 codegen 体上下文的作用域变量读取与 CPS 路径（`vm_
  handle_IbName`）不等价——**P4 codegen 语义等价性 = 核心难点**（codegen 体须复刻 CPS 路径的
  变量读取/作用域/装箱/binop 边界/Signal 语义，非平凡）。
  **P4 定性**：真 JIT = MAJOR 高风险工程（核心执行模型改动，语义等价性为最高风险面）。最小可
  行 codegen（while 直线体）已证实现状下不 trivial——需深入作用域/变量读取机制（codegen 体
  上下文的 `rt._current_scope` 与 CPS 路径的等价性）方能正确复刻。设计已确认（route ① + 插入
  点 + 不变量合规 + 验收判据），实现留后续（多轮·隔离分支实验）。**下一步候选**：P4 实现续推
  （codegen 语义等价性攻坚，隔离分支）/ P5 持久 artifact 缓存（编译期·可并行·较低风险）/
  P3 D-3.3（P1 实证已 O(n)，紧迫性下调）。
---

- **VISION-6 P4 真 JIT·v1.0 codegen 落地（2026-09-09，隔离分支 p4-real-jit，commit 5fd9372e）**：
  P4 真 JIT（用户点名优先）v1.0——为符合安全子集判据的 **while 循环体**生成**直接执行体**
  （Python 函数），绕开每节点 CPS 生成器协议（P1 profile 主导成本），保 §11 不变量（统一
  执行入口#1: codegen 体在 CPS 循环内被 vm_handle_IbWhile 调用，非独立通道；控制流数据化
  #2: v1 体无 return/break/continue → 返回 None；协议分派#6: binop/比较经 receive，禁内联
  op 特化）。
  **实现（subagent B1-B7 修复版）**：① `jit_codegen.py`——`_gen_expr`（IbConstant/IbName/
  IbBinOp/IbUnaryOp/IbCompare[left/ops/comparators]）+ `_stmt_eligible`（whitelist 判据：
  IbAssign 单目标/IbIf 递归/IbPass，llmexcept None）+ `_module_has_behavior_expr`（B4 声呐：
  模块节点池含 IbBehaviorExpr → LLM 污点不安全 → None）+ `generate_jit_body`（编译一次，
  `__builtins__={}` 闭包 B7）。② `vm_executor._get_jit_body`——per node_uid 缓存（B7 建表期
  初始化 `_jit_body_cache`）。③ `vm_handle_IbWhile`——codegen 体直接执行（`jit_body` 非
  None）；**B3 异常位置标注**（`loc[0]` 逐语句设值 + `_annotate_exception_location` 复用
  单一权威标注器，避免 while 节点误导位置）。④ **B1** 常量 `box(native)`（原 `box(None,
  native)` 因 box=registry.box 绑定方法误传 memo → 每常量 IbNone，即前轮 `i+NoneType` 崩溃
  根因）；⑤ **B2** 赋值去 `skip_type_check`（保运行时类型检查同 CPS 语义——该 flag 是
  LLMFuture 写回内部标志，误用跳过类型检查致语义分歧）。
  **改前/改后（perf_bench，µs/iter，warmup2+5）**：arith 179.7→96.8（**~1.86×**，loop-body
  codegen；v1.5 cond-codegen 推至 ~2×+）/ branch 262.9→110.7（**~2.37×，超 2× 目标**）。
  全量 **3909/1 零回归**。
  **subagent 调查关键结论（设计依据）**：P2.5（CPS 内驱动层快速路径）上限 ~1.4-1.6×（每节点
  协议地板 11 VMTasks/iter ≈ 30-45% 不可约）；codegen（route ①）实测 ~2-4× 余量（值层复合
  32.8µs/iter 无 CPS）。route ②（IR/字节码层）更险（双通道 + Python opcode 分派 ~1.3-1.5×
  上限）→ 弃。§11 九项不变量逐条合规（codegen 体经 receive，不内联 op 特化——#6 最难守）。
  **v1.0 后段（隔离分支续推）**：v1.5 cond-codegen（条件也 codegen，drive-loop 交互归零，
  arith 推至 ~2×+）/ v1.1 break/continue/return / 判别测试套件（D1-D7：值 oracle/判据边界/
  错误等价/污点/Signal/多引擎缓存/overlay）/ 语义等价攻坚。v1.0 已证 codegen 路线可行 +
  保语义 + 超 2× 收益面（branch）；合并 unsafe-vibe-dev 待 v1.5 + 判别套件完成。
---

- **VISION-6 P4 真 JIT·v1.5 cond-codegen 落地（2026-09-09，隔离分支 p4-real-jit，commit
  88545392）**：P4 真 JIT（用户点名优先）v1.5——while **条件 + 循环体一起 codegen** 为单一
  直接执行体 `_jit_loop(rt, ec, loc, cancel_event)`（内含 `while True` 条件检查
  `ec.is_truthy` + 循环体），整个 while 循环在 codegen 体内**一次执行完**（vm_handle_IbWhile
  纯 return，无 per-iteration gen.send，**drive-loop 交互归零**）。条件含 LLM/不确定/非
  ExprSet → 回退 v1.0（循环体 codegen）/CPS。
  **实现**：① `jit_codegen.generate_jit_loop`——`_gen_body_source` 复用 v1.0 体生成；
  loop_src 加**协作取消检查**（`cancel_event.is_set()` → `raise TaskCancelled`，与
  _drive_loop_gen 同语义——codegen 体整循环一次执行，须显式检查 cancel 保 `t.cancel()`
  终止，否则 test_cancel_stops_while_loop_body 卡死）；TaskCancelled 进 namespace。②
  `vm_executor`——`_jit_loop_cache`（v1.5 缓存）+ `cancel_event` **公共属性**（封装纪律，免
  穿透 `_cancel_event` 私有属性）+ `_get_jit_loop`（per node_uid 缓存）。③
  `vm_handle_IbWhile`——v1.5 优先（jit_loop 非 None → 一次执行整个循环）；否则回退
  v1.0/CPS。
  **改前/改后（perf_bench，µs/iter，warmup2+5）**：arith 179.7→36.1（**~4.98×**）/ branch
  262.9→50.0（**~5.26×**）——**远超 2× 验收目标**。全量 **3909/1 零回归**。
  **测试适配**（codegen ~5× 加速 → 超时判别阈值上调）：test_collect_timeout_policy
  （run_code + run_file）child 循环 20000→100000 迭代（保 > collect_timeout 1s 触发超时
  判别）。
  **P4 数据平面线累计收益（vs P1 基线 arith 257/branch 372）**：P2 收束 ~-30%（arith
  179.7）→ P4 v1.0 ~-46%（arith 96.8）→ **P4 v1.5 ~-86%（arith 36.1，~7×）**。真 JIT 路线
  ① 实证成功（route ② IR/字节码层弃——更险 + 上限低）。
  **P4 后段（隔离分支续推）**：v1.1 break/continue/return（控制流数据化扩展）+ 判别测试
  套件 D1-D7（值 oracle/判据边界/错误等价/污点/Signal/多引擎缓存/overlay）+ 语义等价攻坚 +
  合并 unsafe-vibe-dev（全本地未 push）。
---

- **VISION-6 P4 真 JIT·判别测试套件 D1-D7 落地（2026-09-09，隔离分支 p4-real-jit，commit
  b4c4137c）**：codegen 语义等价性验证（vs CPS 路径）——`tests/runtime/test_p4_jit_discriminants.py`
  14 例：D1 值 oracle（eligible 程序固定最终值）/ D2 判据边界（每个 ineligible 特征[调用/嵌套
  循环/增强赋值/llmexcept]断言回退 CPS + oracle 正确）/ D3 错误等价（codegen 体内除零报
  RUN_DIVISION_BY_ZERO + 位置 = 出错语句行[B3 标注，line 7 非 while 节点 line 4]）/ D4 污点
  （模块含 behavior expr[LLM 调用]⇒ 循环 ineligible）/ D5 Signal（break/continue 在 while 体
  ⇒ 控制流信号 ⇒ 循环 ineligible 走 CPS）/ D6 多引擎缓存（两独立引擎同源 ⇒ 各自独立缓存）/
  D7 协议分派（codegen 体经 receive 分派，非硬编码 Python 运算符）。全量 **3927/1 零回归**。
  命名规范适配：类名避免里程碑代号（TestD1..TestD7 → TestJit*）。
  **P4 真 JIT 进度**：v1.5 cond-codegen（~5-7× 数据平面收益）+ 判别套件 D1-D7（语义等价性
  证据）落地。下一步：v1.1 break/continue/return（控制流数据化扩展）+ 合并 unsafe-vibe-dev。
---

- **VISION-6 P4 真 JIT·v1.1 控制流扩展落地（2026-09-09，隔离分支 p4-real-jit，commit
  4cbc8da3）**：P4 v1.1 控制流数据化扩展——IbBreak/IbContinue 在 v1.5 cond-codegen
  （while True 循环体）中合法（Python break/continue 作用于 while True 循环）。
  **实现**：`_stmt_eligible` + `_gen_body_source` 加 `allow_break_continue` 参数（仅
  `generate_jit_loop` 传 True——cond-codegen 体含 while True 循环）；v1.0 体 codegen
  （per-iteration 调用）中 break/continue 会作用于函数体（非循环）⇒ 非法（allow_break_
  continue=False，raise _Ineligible 回退 CPS）。
  **同时修复 B4 声呐**：`_module_has_behavior_expr` 原用 `ec._nodes`（历史属性，未
  populate）→ LLM 污点检测失效（`ai.run_batch` 模块被错误 codegen）。改用 `ec.node_pool`
  （dict，populate 期填充）⇒ 正确检测 `IbBehaviorExpr` ⇒ LLM 污点模块循环回退 CPS。
  **判别套件 D5 更新**：break/continue 在 cond-codegen 体 eligible（缓存非空）+ v1.1 边界
  （break 在 v1.0 体 ineligible，条件含调用非 ExprSet ⇒ v1.5 回退 + v1.0 体回退 ⇒ CPS）。
  全量 **3928/1 零回归**。
  **P4 真 JIT 进度**：v1.0 codegen + v1.5 cond-codegen（~5-7×）+ v1.1 控制流（break/
  continue）+ 判别套件 D1-D7 落地。下一步：合并 unsafe-vibe-dev + P4 收敛进
  `docs/architecture/04_vm_interpreter.md` §真 JIT。
---

- **VISION-6 P4 真 JIT·里程碑合并 unsafe-vibe-dev（2026-09-09）**：P4 真 JIT（用户点名
  优先）全形态落地——v1.0 codegen（循环体直接执行）+ v1.5 cond-codegen（条件 + 体一起
  codegen，drive-loop 交互归零，**~5-7× 数据平面收益**）+ v1.1 控制流（break/continue）
  + 判别测试套件 D1-D7（15 例语义等价性验证）。
  **合并流程**：隔离分支 `p4-real-jit`（4 commits：5fd9372e v1.0 / 88545392 v1.5 /
  b4c4137c D1-D7 / 4cbc8da3 v1.1）→ merge 入 `free-explore`（ort 策略，无冲突）→ 全量
  **3928/1 零回归**验证 → 删除 `p4-real-jit` 分支 → fast-forward `unsafe-vibe-dev`
  （里程碑分支，全本地未 push）。
  **文档收敛**：P4 真 JIT 收敛进 `docs/architecture/04_vm_interpreter.md` §12（codegen
  路线 ①——定位/路线裁定/版本线/eligible 判据/9 不变量对照/协作取消/数据平面线收益/
  判别套件；§12 深入指引 → §13；无跨文档引用需更新）。
  **P4 数据平面线累计收益（vs P1 基线 arith 257/branch 372 µs/iter）**：P2 收束 ~-30%
  → v1.0 ~-46% → **v1.5 ~-86%（~7×）**。route ① 实证成功（route ② 弃）。
  **核心主线 ①（数据平面性能线 / 真 JIT，用户点名优先）实质完成**。下一里程碑：**P5
  持久 artifact 缓存**（编译期、可并行、较低风险）。
---

- **VISION-6 P5 持久 artifact 缓存落地（2026-09-09，free-explore，commit b146e602）**：
  P5 持久 artifact 缓存（编译期上修）——相同源码 + 相同内核版本的编译产物（CompilationArtifact
  蓝图）缓存到磁盘（`<project_root>/.ibci_cache/artifact_<key>.pkl`），命中时跳过 5 阶段
  编译管线（扫描/依赖图/拓扑/语义/序列化），直接加载缓存产物。
  **设计**：① 缓存键 = sha256(源码 + entry_module_name + kernel_version + project_root)
  ——源码内容（非 tempfile 路径）保 run_string 可复现；kernel_version 保内核变更后失效；
  project_root 保跨项目隔离。② 启用门：IBCI_ARTIFACT_CACHE=1（env）；默认关闭（零侵入）。
  ③ 缓存存储：pickle 序列化。④ 命中/未命中：命中 → 加载；未命中 → 编译 + 保存（失败
  不抛穿编译流程）。
  **契约**（tests/compiler/test_artifact_cache.py，3 例）：命中 → 值 oracle + 缓存文件
  创建 / 默认关闭 → 不创建缓存 / 源码变更 → 键变更 → 未命中。全量 **3936/1 零回归**。
  **下一里程碑**：P6 内核自举（bind 表达内核契约）/ P7 隔离改造 + 反射。
---

- **VISION-6 P5 持久 artifact 缓存复核裁定：信任域前缀策略替代猜测式白名单（2026-09-09，free-explore，commit 2dac1e11→9eb638ca）**：
  里程碑 ff 合并前复核发现 2dac1e11（安全加固）功能回归——精确模块白名单与 CompilationArtifact
  真实类闭包不符（实测闭包 = core.kernel.ast/symbols/spec.base/spec.member/spec.type_ref +
  core.base.enums；白名单内 core.compiler.ast 为不存在模块）→ 全部合法缓存文件被 find_class
  拒绝 → 缓存自加固提交起功能死亡（每次静默未命中→重编译，零收益）而安全契约仍成立 + 全量
  测试绿（命中测试只断言输出、不可区分命中/未命中，无判别力）。根因 = 白名单凭目测未实证
  推导 + 缓存编码与产物类闭包无一致性契约 + 命中路径无可观测性（静默功能死亡不可测）。
  **修复（根因而非症状）**：① 精确模块枚举 → **信任域前缀策略**（core/core.* + builtins，
  外部模块一律拒绝）——安全前提实证 = core 全域零 __reduce__/__setstate__ 定义（pickle 重建
  = 分配 + 字段赋值，无代码执行面）；前缀策略对表面增长稳定（新 AST/spec/符号类自动入域，
  消枚举漂移的静默失效模式）；② 加载边界类型契约（仅返回 CompilationArtifact，漂移→未命中）；
  ③ 篡改事件可观测（外部模块类引用拒绝 → stderr 一行告警，不静默）；④ 目录权限缺口闭合
  （0700 每次保存强制收敛，含既有目录）；⑤ 命中/未命中判别测试（哨兵：patch 5 阶段管线入口
  IBCIEngine.compile 抛异常 → 二跑仍成功 ⇒ 产物由缓存供给）锁定命中路径。缓存粒度（engine
  边界 CompilationArtifact——execute() 内部经 FlatSerializer 再序列化，产物是引擎级接口）与
  编码（plain-data dataclass 的 pickle）裁定正确；FlatSerializer/dict 编码替代方案否决（反向
  dict→CompilationArtifact 不存在，引入须新建子系统 + 双通道为更劣解）。判别探针：合法产物
  加载 OK / 命中哨兵通过（管线真实跳过）/ 篡改仍拒绝（posix.system 等外部模块 → 无执行）/
  前缀逃逸 corex 不匹配。全量 3938/1 零回归（新增 1 例哨兵测试）。unsafe-vibe-dev ff 合并
  （零风险直接合并细则：全量零回归 + 复核放行）。
- **VISION-6 P6 内核自举 Phase 0 实证裁定：bind 化范围 = 工具 4 完整通道 + net 契约源（2026-09-09，free-explore，设计文档 tasks_docs/_p6_selfbootstrap_design.md）**：
  实证基础（逐项代码/测试证据，详见设计文档 §一）：① 内核契约面 = 11 内置模块
  （builtin_modules.py 构造期字面量 + ibci_modules 工厂实现）——工具 5
  （math/json/time/net/schema）无 setup 钩子、无 exported_types = 纯声明面；net 独有
  per-engine 可变状态；② bind 机制表达力边界（01_native_host_binding）= 成员契约
  声明 + importlib 运行期绑定，无构造期 lifecycle/内核值类型/引擎内部服务表达面；
  ③ 引擎时序：spec 可见性 = 共享 metadata registry（构造期注册先于一切编译）+
  STAGE 4→5 loader 循环对"registry 有 spec + HostInterface 有实现"的模块自动严格
  绑定（_validate_and_bind 完全泛型 getattr + 签名校验，实现对象须 per-engine
  身份——registry 隔离守卫）；④ built-in 通道与 bind 通道机制同构（同 spec 消费/
  同绑定/同运行期 InterOp 路径）；⑤ F5（2026-08-18）时序矛盾裁定**精化非推翻**：
  对 kernel 5+fs 成立（lifecycle/不变量 #4 LLM 通道/spawn/沙箱/值类型导出），对工具
  5 纯声明面不成立（bootstrap 期处理声明源无时序矛盾）。
  **裁定**：bind 化 = 工具 4（math/json/time/schema）契约源 IBCI bind 声明化
  （单一权威源迁移，字面量真删除）+ 实现重打包（模块级函数 + per-engine 身份命名
  空间，消 sys.modules 单例的引擎隔离违规）；net 契约源 bind 化但实现绑定保留
  per-engine 实例（本质差异登记：模块级函数无法表达 per-engine 状态）；kernel 5 +
  fs 维持宿主侧字面量（bind 机制无对应表达面，强行为之 = tricky 违反工作模式
  定论 #3）。bootstrap 阶段 = 直接 parse + 共享合成函数（自 _inject_host_import/
  _inject_host_class 提取，用户路径与 bootstrap 路径机制同构）+ 既有
  register_module 通道 + 既有 STAGE 4→5 严格绑定——**零新运行期机制**；拒绝全 5
  阶段管线编译契约源（死 artifact + 符号表副作用 harvest = 穿透耦合）。9 不变量
  对照通过（#5 依赖方向实施期核查）；工作模式定论九条对照通过。
  **批次计划**：B1 共享合成提取（低风险纯重构，合成等价判别）→ B2 契约源 4 件 +
  bootstrap + 重打包（中风险；用户面既有测试全量锁定 + provenance 等价判别 +
  契约漂移 fail-fast 判别；破坏面超预期 → 独立隔离分支）→ B3 net（B2 模式单模块
  复制 + 多引擎状态隔离判别）→ B4 文档收敛（01_native_host_binding 增内核契约
  自举节）。self-grill 8 问全部自主消解（冲突处理留在用户路径/契约源不泄漏用户
  编译域/子引擎逐引擎重 parse 成本可忽略/P5 缓存无交互/无待用户决断项）。
- **VISION-6 P6·B1 共享合成函数提取落地（2026-09-09，free-explore）**：宿主绑定声明 →
  成员 spec 合成逻辑自 scheduler（_inject_host_import 模块成员循环 + _inject_host_class
  嵌套成员循环，两处同构手写）提取为单一权威源
  core/compiler/host_spec_synthesis.synthesize_host_members（用户侧编译路径与内核
  bootstrap 契约路径共用——P6 bootstrap 阶段设计 §3.3 的前置）。scheduler 两方法改调
  共享函数：成员表逐字段同构（方法 → MethodMemberSpec[逐参注解 + 返回注解/void 缺省 +
  descriptors 同源]、属性 → MemberSpec[field/any 缺省]、重复同名 → 不入表 + 结构化
  校验错误由调用方携自身语境定位/消息上报）。重复条目上报时序微差（成员表先成、class
  注入后行）经全量零回归裁定无消费方敏感（诊断顺序无既有断言）。scheduler 未用导入
  清理（annotation_to_typeref/ParamDescriptor 重构后零消费）。判别测试 7 例
  （tests/compiler/test_host_spec_synthesis.py：方法/字段/缺省语义/泛型注解/重复条目/
  混合序）+ 既有宿主绑定 22 例 + 全量 **3950/1 零回归**（收集数对账：+7 判别 + 5 meta
  扫描[新模块 1 + 命名 3 + 重复助手 1]，逐文件 diff 全消——新模块经 layering/naming/
  no_duplicate_helpers 元契约自动纳管且通过）。B1 完成，下一批 = B2（契约源 4 件 +
  bootstrap 阶段 + 实现重打包，中风险，用户面既有测试全量锁定）。
- **VISION-6 P6·B2 工具 4 契约源自举落地 + B3（net）实施期实证取消（2026-09-09，free-explore）**：
  B2 交付：① 契约源 4 件 `core/runtime/bootstrap/contracts/{math,json,time,schema}.ibci`
  （IBCI bind 声明 = 工具契约单一权威源；成员面经探针与现字面量逐字段等价锁定[27/10/
  14/5 成员，param_types/return/descriptors 全同]）；② bootstrap 阶段
  `kernel_contracts.load_tool_contracts`（engine 构造期：parse[声明域，非声明体/重复绑定
  fail-fast] → 共享合成 → TypeDef[EXTERNAL_MODULE/IMPORT_GATED] → importlib[modules_path
  _guard 单一原语] → BoundToolModule per-engine 严格命名空间[仅契约声明成员，缺失
  fail-fast] → register_module → STAGE 4→5 既有严格绑定——零新运行期机制）；③ 实现重打包
  （4 包类实例 → 模块级函数，builtins 遮蔽显式化[math abs/round 经 builtins.*，消书写
  顺序依赖]；__init__ 经 __all__ 再导出）；④ builtin_modules 4 字面量真删除（单一权威
  源迁移非双写）+ sys.path 守卫收敛单一原语；⑤ kernel_version 递增（ibci-2026.09.1-py312
  ——工具 spec 派生机制/provenance 变更 = 内核变更，P5 缓存失效设计用途）；⑥ 测试迁移
  （test_plugin_implementations 4 fixture → 模块级函数面）+ 判别套件 8 例（spec 形态/
  成员面锁定、缺失成员/重复绑定/非声明体构造期 fail-fast、per-engine 隔离、shadowing
  等价）。**B3（net 契约源）实施期实证取消**：net 8 方法 headers 参数 has_default=True
  默认值面超出 bind 表达力（F3-0 默认值裁定未推翻）+ per-engine 可变状态双重边界 →
  net 维持宿主侧字面量（USER_DEFINED 不变）；远期项登记 = bind 默认值语法（语言级设计，
  独立立项）。provenance 变更（工具 4 USER_DEFINED→EXTERNAL_MODULE）行为安全实证：
  消费点仅符号兼容性[EXTERNAL 互兼，宽松方向]+ 诊断只读投影；import 解析/覆盖保护与
  provenance 无关（e2e + shadowing 判别锁定）。全量 **3963/1 零回归**（⚠️ **本条内
  "test_task_scheduler 全量负载偶发 hang = 已知框架层并发 flake 类"诊断已被后续看门狗
  根因条目更正：两次 exit 124 实证 = 看门狗固定窗口误杀，该测试本身无 hang，观察项
  关闭**——见后条）。下一批 = B4 文档收敛（01_native_host_binding 内核契约自举
  节 + 插件体系同步 + KNOWN_LIMITS 边界注记）。
- **测试基础设施裁定：死锁看门狗改阶段感知（进程级固定时点触发 → sessionfinish 解除）（2026-09-09，free-explore）**：
  P6 全量验证期间两次 exit 124（"无输出退出"假象）触发根因排查——线程栈实证：套件已
  100% 完成，hang 点在 pytest unconfigure 期 GC（弱引用回调 + 孤儿 futures worker
  线程）；conftest 看门狗为进程启动后 180s **固定时点**触发（time.sleep 后无条件
  dump + os._exit(124)），其设计注释自述时长基准 = 全量 ~95s——套件增长至 150s+
  （collect + 执行 + teardown GC）后越过 180s 总窗口 → teardown 期误杀。**根因 =
  固定时点看门狗与增长中的套件总时长竞态**（注释预言的"运行时长越过看门狗时限"
  场景实证命中），非测试卡死。**修复（根因，非调大时限的魔法数字）**：看门狗改
  **阶段感知**——职责与其文档化用途对齐（框架层 collect/plugin 死锁，测试级超时不
  生效的场景）：``pytest_sessionfinish``（测试执行完毕）设置事件 → 看门狗解除
  （event.wait 替代 sleep）；teardown 慢 ≠ 死锁，测试级 60s 超时已覆盖执行期。
  合成验证：collect 期死锁用例（临时文件，跑完即删）→ 看门狗 180s 触发 exit 124 +
  线程栈（保护面不缩水）；正常全量 3963/1 干净跑完含 teardown。文档同步：
  docs/howto/keep_tests_safe.md 第二层语义更新（阶段感知 + 触发即框架层真卡死）。
- **VISION-6 P6 内核自举里程碑收束（2026-09-09，free-explore）**：P6（bind 表达内核
  契约）分阶段实施完成——Phase 0 实证裁定（bind 化范围 = 工具 4；kernel 5+fs 维持
  宿主侧；F5 时序矛盾裁定精化）→ B1 共享合成函数提取（host_spec_synthesis 单一权威
  源，用户路径/bootstrap 路径机制同构）→ B2 工具 4 契约源自举落地（contracts/ 4 件
  IBCI bind 声明 = 契约单一权威源 + kernel_contracts bootstrap[parse→共享合成→per-
  engine 严格命名空间→register_module→STAGE 4→5 既有严格绑定，零新运行期机制] + 实现
  重打包[类实例→模块级函数] + 4 字面量真删除 + kernel_version 递增 + 判别套件 8 例）→
  **B3（net）实施期实证取消**（net 8 方法 headers 默认参数面 has_default 超出 bind 表达
  力[F3-0 裁定未推翻] + per-engine 可变状态双重边界 → net 维持宿主侧字面量 USER_DEFINED；
  远期项登记 = bind 默认值语法独立立项）→ B4 文档收敛（01_native_host_binding §六 内核
  契约自举[形态/设计理由/边界表] + 04_plugin_system/07_kernel_native/01_principles/
  06_path_system 五文档两域分述同步）。**P6 收束判据**：全量 3963/1 零回归 + 用户面
  既有测试全量锁定 + 契约源↔字面量逐字段等价 + provenance 变更行为安全实证 + 多引擎
  隔离判别。下一里程碑 = P7 档 B 进程级隔离 + 反射能力（高风险 → 隔离分支 100% 授权）；
  P3 D-3.3 可交错。P6 期间附交付：P5 缓存复核根因修复（信任域前缀策略，9eb638ca）+
  测试基础设施看门狗阶段感知修复（上条）。
- **unsafe-vibe-dev 合并安全评估（用户指定：性能/功能/内核稳定性/风险回归四面实证，2026-09-09，free-explore）**：
  评估对象 = P6 收束态（HEAD 4e024377，unsafe-vibe-dev 已 ff 收束）。方法 = 两面 A/B 实测
  （pre-P6 worktree `9eb638ca` vs post-P6 主树，交错多轮）+ 官方裁判 harness + 稳定性探针
  + 残留扫描。**功能面**：干净全量 3963/1 零回归（157s）+ 用户面 e2e + P6 判别 8 例 +
  P4 D1-D7 / P5 哨兵（套件内）全过。**性能面**：① 数据平面官方裁判 harness
  （scripts/perf_bench.py，5 轮取中位）A/B：六项（arith/branch/recurse/string/container/
  class）皆噪声范围内（最大偏差 +1.8% < 该项 stdev）——P4 ~7× 收益完整保留，P6 对执行
  平面零影响；② 构造期 A/B 发现 **P6 引入 +12.6 ms/engine 回归**（40 次构造均值，3 轮
  交错复现非噪声）——成本分布实证 = 每引擎 4 次契约源 lex+parse（10.2ms/引擎，install
  树静态文件重复解析）→ **修复 = 契约源解析进程级缓存**（内容哈希自失效键；首引擎
  parse+synthesize+fail-fast 语义不变，后续引擎 deepcopy 成员表保 per-engine spec 身份；
  per-engine 实现对象/隔离守卫语义不变）→ 复测 **+12.6 → +3.3 ms/engine（-74%）**，残余
  皆内存有界操作；③ 编译期 = P5 缓存通道未触碰（kernel_version 递增为设计内失效）。
  **内核稳定性面**：10 引擎同进程链（构造 + 工具 4 运行 + 正确性断言）全过，10 个独立
  per-engine math 实现（registry 隔离守卫 intact）；net per-engine 状态隔离探针
  （n1.set_timeout 不泄漏 n2）。**风险回归面**：残留扫描全绿（任务代号/孤儿引用/未用
  导入/旧阶段边界引用零命中）+ B4 文档一致性（两域分述单点真理）+ 测试基础设施缺陷
  根因修复两项（见下条）。**评估结论：四面全绿，合并安全成立**。附：评估期间暴露并
  根因修复的测试基础设施缺陷 = 看门狗阶段边界（sessionfinish → collection_finish：
  全量 98% 处 exit 124 实证 = 180s 固定窗口与套件总时长竞态的第二次形态；修正后
  窗口与套件时长彻底解耦）+ 遗留合成文件干扰实证（dump 精确捕获真实 collect hang，
  设计行为确认）。
- **测试基础设施裁定：死锁看门狗阶段边界 = collection 结束（sessionfinish 不足的根因）（2026-09-09，free-explore）**：
  合并安全评估期间全量 98% 处再遇 exit 124（dump 实证主线程在测试执行中）——
  sessionfinish 解除边界仍不足：180s 固定窗口自进程启动计，套件 collect+执行总时长
  （~180s+）越过窗口 → 执行期误杀。**根因 = 阶段边界选错**（sessionfinish 在 100% 才
  触发，窗口与执行时长仍耦合）。修正 = ``pytest_collection_finish`` 即解除：职责分界
  彻底——框架层（进程启动→collect 结束）= 看门狗 180s 窗口；测试执行期 = 第一层 60s
  每测试超时（含 setup）；teardown 慢 ≠ 死锁。验证：① 干净全量 3963/1（157s 零误杀，
  collect ~20s 即解除）② 合成 collect 阻塞 → 124 + dump 主线程栈精确指向卡死模块导入行
  ③ 干扰实证：遗留合成文件误入全量 collect → dump 精确捕获真实 collect hang（设计行为）。
  keep_tests_safe.md 同步（阶段边界 = collect 结束）。**记录更正**：本 session 早先条目中
  "test_task_scheduler 全量负载偶发 hang[单独 0.17s 过·重跑全绿] = 已知框架层并发 flake
  类"诊断有误——两次 96%/98% 处 exit 124 的实证根因皆为看门狗固定窗口误杀（线程栈：
  套件已 100%/98%，主线程在 GC/执行中），test_task_scheduler 本身无 hang（单独 0.17s
  通过 + 全量测试 100% 完成后才被杀）。该观察项关闭。
- **tasks_docs 交接文档体系审计 + 收束清理（用户放行 A 层三项后执行，free-explore）**：
  5 路并行全量审计（HANDOFF/NEXT_STEPS/PENDING_TASKS/15 个 _*.md 生命周期/WORKLOG+
  章程漂移，统一检查标准 + 逐项直接证据核验）。**用户放行的 A 层裁定**：① 工作模式定论
  第 9 条对齐 2026-08-18 合并流程（独立隔离分支实验 + 确认零风险后 ff 直合 unsafe-
  vibe-dev + merge 无误删分支；main 永不触碰）；② 章程 G3 统一方向 = 章程向实践靠拢
  （WORKLOG 重定义为记录类：关键裁定 + 重大方向决策详尽记录，豁免"不保留已完成历史"
  红线）；③ 13 个 _*.md 按审计分层删除（3 个先迁移后删 + 10 个干净删；_n3 挂起保留）。
  **章程修订（GOVERNANCE 9 处）**：WORKLOG 记录类重定义 + 单点真理归属行（主线 = 
  NEXT_STEPS / 定论单点 = NEXT_STEPS ⛔ 节 / 工作规则单点 = AGENTS.md）+ 日期戳豁免
  清单（记录类全量 + 状态变更时间戳 + session 边界标记）+ 锚点机制登记 + _*.md 生命周期
  细化（默认删除；留存须登记理由）+ 更正回注通则（更正须标原条目失效）+ 红线措辞对齐。
  **三常驻文档收束**：NEXT_STEPS 收束式重写（259→127 行：顶部唯一基线锚点块[3963/1] +
  单一"当前 P0 = P7"开工指令 + 里程碑一行指针 + 候选仅开放项；删 6 个已完成阶段块/
  ~40 日期戳/15 冻结数字/5 处过期"当前"声明）；HANDOFF 大修（§2.1 160 行历史块移除
  [留指针] + round3 历史检查单移除 + goal 配置习惯按当前工具 API 重写[create_goal/
  get_goal/update_goal + 轮次预算 + pause/resume/disarm 生命周期] + goal 模板六处修正
  [支线/停止条件 API/非目标去硬编码冲突项/危险工作变体注记] + §1.4 补 GOVERNANCE 行 +
  T18 + §1.1 补两 skill + 尾部模板登记 §2.0 + _p6 引用清理）；PENDING_TASKS（PT-FEAT-16
  active→done[四批落地实证] + VISION-6 过期"当前理解"删除 + F5 档案归位现状化[档A→P5✅/
  JIT→P4✅/内核自举→P6✅/档B→P7] + 概览表计数修正[DECIDE-2 解封/SEALED=1/VISION=4/
  FEAT+17/DOC+4] + 5 个 done 条目压缩一行 + 36 日期戳/冻结数字清扫 + N3 迁入 PT-FEAT-17
  [shelved] + T5 登记 PT-DOC-4 + VISION-4 开工输入内联[类型层承诺 5 项清单自 _meta 迁入]）。
  **迁移先行（删前保唯一信息）**：_meta §四/§五 → PENDING VISION-4/6；_embedding 语言面
  → docs/syntax/01_types §1.5 vector + 11_modules §11.3 embedding 服务面（新增，精确签名
  自公理/spec 实证提取）；_next_phase T5 → PT-DOC-4。**引用连带清理**：14 个 _*.md 删除
  （_n3 保留 + 其单点记录指针重定向至 PT-FEAT-17）+ 12 处 code docstring 文档指针清除
  （AGENTS.md 注释禁文档指针红线）+ docs/ 4 处 _meta 指针 repoint run_code_safely +
  全仓残留复扫零命中（WORKLOG 历史落账豁免，保审计链）。**WORKLOG 结构修复**：更正回注
  原条目（test_task_scheduler 误诊标失效）+ §二表格挤行拆分 + 缩进/行尾归一。全量 pytest
  零回归验证后提交（本条随批）。
- **Round5 自指性体系架构转向 + 试用者本地提交吸收 + ai.recall 设计调和（2026-09-09，unsafe-vibe-dev）**：
   ①**战略转向（来自试用方 R216）**：试用方（ibci-trial）独立自主 agent R205–R218 基于实证
   （e49 LLM 写 ibci 3/3 语法伪迹失败 vs e50/e51 LLM 低阈值+架构确定性组装成功）确立
   **自指性体系架构**横切原则——可靠性与自指性来自确定性代码/架构非 LLM 智力；LLM =
   低阈值基础细胞（仅语义选择/分类/草稿/先验，不产结构/不写 ibci/不做判定）；架构 =
   确定性计算机。该原则与 IBCI 设计本意一致（`01_principles` §1.3/§1.4/§3.7/§十一），
   round5 需求单（SR-1..5：自描述/显式 IBCI 生成器/自修改安全/行为值直接执行/LLM 阈值纪律）
   作为最高优先主线。**裁定：Phase C 从原"pattern 自由调参"重定为自指性架构一等化
   （显式生成器 + 自描述 + 确定性验证门），非 LLM 提自由文本 instruction**（依据 = 试用方
   e49 实证 LLM 产码不可靠 + 工作模式定论 #4 协议驱动 + §十一排除 generate_and_run）。
   ②**ai.recall 设计调和（命名/架构裁定，用户授权自主决定）**：试用方 `f5a6e356`(REC-6) 与
   上游 B5b 均欲占用 `ai.recall` 名但签名/语义不同（试用方 = 低层 corpus 向量原语，上游 B5b
   = 高层 memory 感知）。按单一权威 + 机制同构裁定：**`ai.recall(query,corpus,k,instruct,
   dimensions)` = 低层向量原语**（吸收试用方版，含 document 侧内容缓存 + `ai.recall_stats`
   成本遥测，与 `ai.retrieve` 同族）；**`mem.search` = 文本召回**（原 mem.recall 改名，Jaccard
   零 LLM）；**`mem.corpus(scope)` = 组合向量召回的语料收集**。记忆感知向量召回 = 调用方组合
   （`ai.recall(query, mem.corpus(scope), ...)`），**非 memory 方法**——因 embedding 服务
   （含 doc 缓存/配置状态）归 ai 插件持有，memory 值对象不持有引用（无 memory→ai 依赖、
   单一权威、符合试用方 e40-e51 实际用法）。
   ③**TYPE-1 吸收**：试用方 `af5c9c6e`（meta.compile 返回编译产物摘要 dict）= 上游 Phase D
   的 TYPE-1，已吸收落地（host/service.py meta_compile + interfaces + ibci_meta/core.py +
   _SPEC_META）。
   ④**试用者交接**：TRIAL_ANNOUNCE_2026-09-09.md（gitignored 交接工件）+ 指针
   UPSTREAM_ANNOUNCE_POINTER_2026-09-09.md（置于试用方工作区，指引重新钉扎 123a341f +
   回收本地补丁 + 原生 memory 替换 Python PoC）。
   ⑤**分支收束 + push（用户 2026-09-09 显式授权）**：free-explore 纯 ff 并入
   unsafe-vibe-dev（= 123a341f），free-explore 删除；unsafe-vibe-dev push origin
   （11a893a7..123a341f，13 提交）。全量 3973/1 零回归。
- **Phase C 自指性架构一等化起步：selfref 模块地基（2026-09-09，unsafe-vibe-dev，C1）**：
   ①**命名裁定**：自指性架构承载模块名 = `selfref`（非 `self`）——IBCI 类方法首参即
   `self`（`func m(self, ...)`），模块名 `self` 与方法参数概念冲突（混淆命名）；`selfref`
   对齐 round5 需求 ID（SR = SELF-REF）。
   ②**架构裁定（design-philosophy 单一权威/机制同构）**：自指性架构所有原语集中在一个
   core-level plugin `selfref`（同 meta/idbg 族，但**持有系统级状态**：宪法 + 模板注册表，
   每引擎一实例）——非散落各子系统。机制同构：模板注册同 knowledge、审计同 memory、
   验证同 meta。
   ③**C1 落地**：SR-1 `describe()`（真内省，从系统实际结构组装 dict{modules/constitution/
   templates}，非 e50 硬编码字符串）+ SR-3 `constitution()`（结构化不变量集）+ SR-2
   `register_template`/`templates`/`render`（模板注册 + 确定性组装，零 LLM，fail-fast）。
   SR-5 结构性保证：selfref 零 LLM（组装/内省/判定全确定性）。完整管线实证：register →
   render（确定性组装合法 ibci）→ meta.compile（n_funcs 内省）= e49 教训的架构解。
   设计要点固化 = `tasks_docs/_round5_selfref_design.md`（SR-1..5 全景 + C1-C5 批次规划 +
   开放问题裁定 Q1-Q4）。verify 三关门 / modify 自修改+回滚 归 C2/C3。全量 3988/1 零回归。
- **run 输出行缓冲契约 e2e 计时测试降层（2026-09-10，unsafe-vibe-dev）**：e2e 墙钟
   时间隙判别（`gap>1.5s` + 40000 次循环"~4s"标定假设）实证为机器速度依赖——
   32 核机上循环 ~1.1s 致误报失败（契约本身生效：实测 L1 到达 t+0.10s，非退出
   时 flush；main.py run 分支 reconfigure 在位）。裁定：契约断言降层为机器无关
   白箱（`tests/runtime/test_run_stdout_line_buffering.py`：真实管道 TextIOWrapper
   默认块缓冲 → `main._ensure_stdout_line_buffered()` [run 分支初始化，自 main()
   内联提取为具名函数] 调用后行缓冲生效）；e2e 计时黑箱测试删除。边界：run
   输出通道行级 flush 契约不变（单点真理 = 15_diagnostics §run 命令可观测面）；
   机器标定依赖的墙钟判别不置于 e2e 层（防未来复犯）。
 - **世界模型数据库（IBCI 原生 DB）主线确立 + 设计定稿（2026-09-10，unsafe-vibe-dev；试用方
    v2 需求单驱动）**：试用方提"数据结构 + 数据库"需求（**不能永远用 IBCI 代码 / JSON 承载
    数据**）→ 深度调研确立"IBCI 原生数据库"设计：一等值类型（世界模型知识图谱），单一权威源 =
    append-only 事实日志 `(world,s,r,o)`+source/status，融合**图/三元组平面**（治理词表 + 8 倒排
    索引 + 矛盾/传递/展开，D1 零 LLM）与**向量平面**（内容信号，非判定）；压缩态存储/按需展开 +
    quote/eval 数据行为二元 + 跨尺度自指 + 值化存储（非服务）。**设计裁定（用户授权推进）**：
    ① 演化现有 `knowledge`（文档明写=D 纸带，append-only amend/history + 引擎单调序号；消费面
    轻 → 低风险）为一等 KB，**不另立平行类型**；② R-A quote/eval 先设计+POC（触及公理层 → 全量
    pytest 评估）；③ 向量面 = 纯 IBCI 值 + `ImmutableArtifact` 工件（暴力 cosine 起步，格式预留
    ANN/FAISS 派生加速）；④ 磁盘格式 = IBCI 内容寻址 artifact（JSON 降传输格式，IBCI 代码降派生
    视图 `to_ibci()`）。**实证关键**：现状 stopgap（trial `schema_to_ibci.py`）lossy（丢 34 条
    only_in_axioms / 关系字符串化 / `return "unknown"` 魔法默认 / 无查询 / 全量重编译）；IBCI 已
    有全部子件（knowledge/vector/memory/behavior/ai.recall/ImmutableArtifact）——**缺的是"融合
    成一致数据层"，非从零造库**。工作节奏：三轴收束进自指弧线（R-A 并入 selfref / R-B 演化
    knowledge / R-C 横切）+ Rust 内核独立隔离分支（设计+构建均可：pin `CARGO_HOME` 到 workspace +
    允许网络免审批——实测 agent bash 对默认 `~/.cargo`/`/opt/rust/cargo` 不可写，须 pin）+
    e2e 进程内化升格使能项。
    设计要点落点 = `tasks_docs/_world_model_db_design.md`（调研结论/决策点/风险/P0-P9 执行清单）
    + `tasks_docs/HANDOFF.md` §2.0 + `tasks_docs/NEXT_STEPS.md` 当前 P0。
 - **环境重建（机器更换后，2026-09-10，unsafe-vibe-dev）**：按 `/shared/CONTAINERS.md` +
    `/shared/MODELS.md` 重建丢失的 gitignored 工件：`api_config.json`（SiliconFlow key 取自
    /shared/MODELS.md；probe 通过 + 35B 非思考基线 `has_reasoning=False` + embedding 0.6B 实证）
    + `AGENTS.local.md`（本机环境事实）；补装 `maturin 1.15.0` 入 `.venv`（pyo3 构建前置）；验证
    Rust 1.98.1 + in-workspace offline cargo build 可行（`CARGO_HOME`+`CARGO_TARGET_DIR` pin
    workspace，no-dep lib rc=0）。venv Python 3.12.3 + editable 安装 intact；smoke 子集
    （contracts+compiler）828 passed / 11.3s 进程内。
 - **世界模型 DB 前期检验（环境/工具/库完备性，2026-09-10，unsafe-vibe-dev）**：为下一 session
    自主执行预先核验，避免开工后缺环境/库/工具。① **Rust↔Python 协同端到端验证**：pyo3 crate
    （extension-module）`cargo build --release`（`CARGO_HOME`+`CARGO_TARGET_DIR` pin workspace +
    网络下载 pyo3）→ `.so` → Python import + 调用 Rust 函数 OK（`RUST_PY_COLLAB_OK`）；工具链
    maturin 1.15.0 + cargo/rustc 1.98.1 全通；pyo3 3.12 用 0.22/0.23（3.14 需 ≥0.29）。② **全量
    pytest 基线实跑**：3990 passed / 1 skipped / 103.58s / rc=0（干净起点）。③ **P1-P9 子件核验**：
    conftest `run_ibci`/`compile_ibci` + `IBCIEngine.run_string(output_callback, journal_writer,
    budget_guard)`（差分 harness 基石，原生带 LLM 审计/预算钩子）/ llm_journal / budget /
    HostService(run_code/meta_compile/save_state) / knowledge 测试 均在位。④ **发现唯一前置缺口 =
    Python 3.12 dev headers 缺失**（venv 基座 `/usr/bin/python3.12` 无 headers；系统无 3.12 headers；
    agent 无 root 无法装）→ **需用户/root `apt-get install -y python3.12-dev`**；该缺口仅阻塞 P9 Rust
    构建，**P1-P8 纯 Python 主线不受影响**。落账 = AGENTS.local.md + HANDOFF.md §2.0 + 设计文档 §2.5。
- **P1 R-A quote/eval 落地（数据/命令二元地基，2026-09-10，unsafe-vibe-dev；世界模型 DB 主线批次 1）**：
   世界模型 DB 主线 P1 批次收束——`meta.quote(source) -> quoted` / `meta.eval(expr) -> any` 语言原语 +
   `quoted` 一等不可变值类型（单字段 `source: str`；无运算符面/无 call 能力——提及与使用的切换必经显式
   eval，二元性的结构保证）。**关键裁定（self-grill 全分支消解，无待用户项）**：① 承载 = `meta` 模块
   （"代码作值"单一权威源：compile = 验证侧既有面，quote/eval = 数据侧/执行侧——新模块 = 碎片化）；
   ② 提及形态 = **源串**（非 AST 捕获——AST node uid 绑定具体引擎 = 不可移植值，正是"代码不是值"
   陷阱；系统代码作值轴全部以源串为传输形态，机制同构）；③ quote **单一验证门**（子引擎 compile-only
   包装 `__qeval__ = <source>`：语法/语义/表达式性/自包含性一次门尽——fresh scope 使引用父模块自由名
   的源 quote 时刻即 fail-fast，**良构由构造成立**；eval 子进程同 root 重编译必然通过，错误面 = 纯
   运行期）；④ eval = 子进程 spawn + JSON **值通道**（复用 run_isolated collect 协议——唯一既有值交换
   面；返回值非 stdout 文本；结果槽缺失 = 显式 fail-fast 非静默 None；None 合法）；⑤ 错误语义 fail-fast
   上抛（与 run_code 错误作值互补——不同概念不同面，非双通道）；⑥ 对比语义 = source **逐字节**（语义
   等价判定不可判定，归 P2 事实层 UID）；⑦ str→quoted 无隐式 cast（验证门唯一入口 = meta.quote）。
   **变化前后**：新增 quoted 类型全链（axiom/spec/runtime object/deep_clone 不可变集/serializer 双面）
   + HostService（quote_expression/eval_quoted + `_sub_engine_compile` 单一编译门核心提取——
   meta.compile 同路径复用，消双写）+ meta 插件（quote/eval 方法 + spec 面：入参静态锁定 quoted/str，
   str 直调 eval = 编译期类型违约）+ 测试 30 例（tests/runtime/test_quoted_type.py 13 +
   tests/e2e/test_meta_quote_eval.py 17，含 R-A 自指验收演示：句作数据 + 句作命令）+ 差分 harness 语料
   2 例（quote/eval 判别面，P9 fuzz 语料首批）。**文档漂移修复（同批）**：KNOWN_LIMITS §二十六 重写
   （子运行 = 子进程进程级隔离 + JSON 值通道边界——原文"进程内/无进程级隔离"为 P7 前旧态）+ 11_modules
   11.6/11.11 + 07_kernel_native_modules 模块表（meta/selfref 行缺失 + 计数漂移：内核原生 6→8）+
   run_result 面 9 处 docstring "进程内"→"子进程"。**验证**：全量 pytest 零回归 **4038 passed /
   1 skipped / 115.28s / rc=0**（公理层变更放行门；= 基线 3998 + 新增 30 + tests/meta 治理参数化
   增量 10[docs 同步所致]，收集计数逐文件核对吻合）。设计要点 = `tasks_docs/_ra_quote_eval_design.md`
   （P2 批次开工前保留——含 §7 边界裁定：eval 环境参数/归一化对比/SR-4 承载 均 P2+ 不预置）。
- **P2 R-B 世界模型 KB 落地（knowledge 就地演化为三元组知识图谱，2026-09-10，
   unsafe-vibe-dev；世界模型 DB 主线批次 2，四批 B1-B4 收束）**：`knowledge` 值就地演化为
   世界模型 KB——**一个值、一个审计序号、三正交数据面**（entries 通用登记面[既有契约
   零改动] / facts append-only 事实日志[KB 单一权威源] / vocab 治理词表
   words-relations-worlds）+ 8 派生索引（6 图索引 active 视图 + by_source/by_status 全日志
   视图；**日志是权威、索引是视图**——增量维护 + 构造/水化确定性重建，永不独立序列化）。
   **关键裁定（self-grill 全分支消解）**：① 就地演化非新类型（单点真理：KB = D 纸带，
   knowledge 公理文档明写的知识层——另立平行类型 = 碎片化；消费面实证审计 = 轻
   [语义层 check 纯度 1 处 + serializer + deep_clone + 注册]，entries 面零改动零回归）；
   ② facts 准入 = **内建治理门**（world/relation/s/o 词表 allowlist 机器强制，确定性零
   LLM——knowledge check 门纪律的图平面落法；entries 面调用方谓词门不变，两门各辖
   一面非双通道）；③ fact_id = str(KB seq)（引擎单调序号，同操作序列同 id 字节可复现）；
   ④ s/o = 已注册词 lexeme（治理 allowlist；**结构化 o / R-E 自指事实 = 后续扩展面**，
   P2 不预置）；⑤ 墓碑/版本化同构 knowledge amend 纪律（retract/amend_fact reason 强制 +
   append-only 事件链 + 图视图即时排除 + 日志全史保留；**恢复语义 = 登记新事实**，墓碑
   不复活）；⑥ 事实平面操作一律收 fact_id 返回 KB 权威数据（防调用方自持陈旧副本双真相）；
   ⑦ by_pair/by_subject 按试用方规格 §3.2 为 **world 无关** 索引（world 维经
   all_in_world/by_triple 表达）；⑧ transitive 非传递关系 = 空 list（无闭包 ≠ 错误——
   诚实语义）；⑨ compare 层 4 语义相似归向量面不预置（D1：判定恒走确定性 1/2/3/5 层）；
   ⑩ 对比/展开的字节对比经 JSON 序列化路径（**新发现语言边界：容器 == 恒等语义**——
   既有事实，落 KNOWN_LIMITS §10.5 + 规避路径）。
   **变化前后**：IbKnowledge payload 三面扩展 + 27 方法面（词表 9 / 事实 8 / 查找 7 /
   对比展开 3——B1 词表+事实+索引+序列化/克隆 13 方法 → B2 查询面 10 方法 → B3 审计面 4
   方法）+ 派生索引 8（_build_indexes_from_facts 单一重建源）+ 诊断码 +6（KNW_VOCAB_
   UNREGISTERED/EXISTS/MALFORMED + KNW_FACT_DUPLICATE/NOT_FOUND/RETRACTED；reason 空
   复用 KNW_REASON_EMPTY 单名）+ 序列化双面（facts/vocab 原生直存、索引丢弃水化重建）+
   deep_clone KB 面独立深拷贝 + to_native 三面对外快照 + 文档（16_knowledge_system 主文档
   扩展 KB 三面/27 方法/边界；15_diagnostics +6 码对账；KNOWN_LIMITS §10.5 容器 == 恒等
   边界 + §二十六 值通道边界[P1 批]）+ 测试 48 例（tests/runtime/test_world_model_kb.py
   42：词表/事实/治理门/索引确定性/序列化/克隆/7 查找/矛盾 multi_valued 门/传递闭包链+
   防环/展开逐字节一致/对比 4 层/墓碑/版本化/entries 零回归 + tests/e2e/
   test_world_model_kb_e2e.py 6：用户面微型世界模型 2 世界/3 关系/4 词/5 事实全链路）+
   差分 harness 语料 +2（kb_query + kb_expand_determinism——R-B 里程碑语料）。
   **验证**：全量 pytest 零回归 **4090 passed / 1 skipped / 116.49s / rc=0**（公理层变更
   放行门；= 前基线 4038 + 新增 48 + tests/meta 治理参数化增量 4[docs 同步所致]）。**双写根治（结构性）**：词关系
   = by_subject 派生（无 word.relations 独立存储面）；展开态不存（expand 纯派生）；
   索引不存（水化重建）——v30 的 word.relations×axioms 双写（34 条 only_in_axioms）
   在活 KB 中无对应物（P3 load_kb 时 axioms 单一落点 = facts 平面）。
   设计要点 = `tasks_docs/_p2_world_model_kb_design.md`（P3 批次开工前保留——含
   §2 D5 值域边界裁定 + §6.2 验收对照：试用方 M1 = P2+P3+P4 联合达成）。
## 附、书写模式（本文档专用模板，书写必须参照）

> 本节是本文档书写的**唯一权威模板**（模板归属 = 文档自身；`GOVERNANCE.md`
> §三 仅做索引）。新增/修改裁定一律按下列模板与规则书写。

### 1. 文档结构

```
# WORKLOG — 关键裁定与长期约束
定位段（只保留仍有长期约束力的裁定；历史由 git 承载）
一、长期约束裁定（已固化于 AGENTS.md/HANDOFF 的，此处只列指针不复制）
二、主线与方向裁定（表格）
三、重大方向决策记录（防止未来误解）
```

### 2. 裁定表格模板（§二）

```markdown
| 裁定标题（时间 YYYY-MM-DD） | 关键裁定/决策 + 变化前后摘要（实现+测试+文档）|
```

规则：
- 只保留**仍有长期约束力**的用户裁定与**防止未来误解**的重大方向裁定；
- 例行完成记录由 commit 消息承载，**不写入** WORKLOG；
- 内容一句话说清裁定本身与适用边界，不写过程叙述；
- 已固化于 `AGENTS.md` / `HANDOFF.md` 的裁定，在 §一 列指针、不复制正文（单点真理）。

### 3. 重大方向决策记录格式（§三）

```markdown
- **<决策名>（时间 YYYY-MM-DD，<分支/来源>）**：决策内容 + 设计要点落点（
  架构文档 / 交接记录 / git）。
```

规则：每条一至三段；设计要点**不在此展开**，标注其固化的权威位置（指针）。
