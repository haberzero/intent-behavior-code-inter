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
| **测试验证策略放开 + 测试资产处理**（2026-09-11，用户） | ① **全量 pytest 使用限制略微放开**：Rust 化推进后测试耗时缩短、全量并非不可接受 → 全量 pytest **不再限 4 场合**（原 ① merge/放行门 ② 公理层或语义错误集 ③ 阶段边界/里程碑 ④ 开新分支前 仍为强制门），**可按需自由全量**；单任务默认（受影响子集 + smoke）不变。② **测试脚本自由处理**：已过期或被证不正确的测试脚本可自由处理（重构/修正/删除），**重构的质量原则大于维持现状的重要性**（与 user-principles"不冻结历史资产 / 问题直接重构"一致）。已同步 AGENTS.md §测试 / NEXT_STEPS 基线锚点 / HANDOFF §1.2。 |

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
- **P3 磁盘格式落地（KB 内容寻址 artifact + world_model 模块，2026-09-10，
   unsafe-vibe-dev；世界模型 DB 主线批次 3，两批 C1-C2 收束）**：世界模型 KB 的
   **磁盘面** = 新 kernel-native 模块 `world_model`（同 `fs` 注册模式，无物理包）：
   `load_kb(path) -> knowledge`（三级验证门后水化为**活 KB 值**）/
   `save_kb(kb, path) -> str`（KB 面序列化落盘，返回 content_hash 钉扎基准）。
   **artifact 格式（共享契约 = 试用方按此重新导出 v30）**：单 JSON 文件
   `{schema_version: 1, content_hash, facts[seq 序], vocab{words,relations,
   worlds}, seq}`；**JSON 降为传输格式**（pretty 布局），**身份 = canonical**
   （facts/vocab/seq 键排序 + 紧凑分隔 + UTF-8 字面 sha256 全摘要 64-hex——
   同内容不同排版 = 同 hash，排版无关性实证）。
   **关键裁定（self-grill 全分支消解）**：① 磁盘面归**模块域**非值方法
   （load_kb 产生值——值方法面无接收者；磁盘 I/O = 外部效应面，沙箱校验
   resolve_path + PermissionManager 归模块域[fs 先例]；值方法无 capabilities
   注入面）；② 函数名 `load_kb`/`save_kb`（试用方 B1 验收字面 = 共享契约名；
   模块名 `world_model` = 主设计 §3.3 sketch 名——试用方文档为权威）；③
   **entries 面不入 artifact**（artifact 只辖 KB 面——entries 持久化通道 =
   ihost.save_state 全状态面，两通道各辖其面非双通道：不同概念不同载体）；
   ④ content_hash = sha256 **全摘要**（非 UID 家族 16-hex 前缀——数据完整性
   契约非进程内标识符；uid.py 不扩）；⑤ schema_version 策略 = 1，未知版本
   fail-fast 无自动迁移（兼容层红线）；⑥ 文件缺失/沙箱拒绝**复用 fs 面
   诊断**（RUN_GENERIC_ERROR/RUN_PERMISSION_ERROR——实证 fs.read 缺失文件
   同码同构，不另造码）；⑦ 加载 = 活 KB（B1 验收"增量可用无需重编译"=
   活 KB 值语义；artifact 文件只读不被 load 改写）；⑧ 差分 harness 语料
   **不做磁盘 I/O**（语料纪律 = 自包含脚本无外部文件依赖；磁盘面由 pytest
   覆盖——P9 差分面如需文件语料再显式扩 temp root，不预置）。
   **变化前后**：+world_model 模块（core/runtime/modules/world_model_impl.py
   WorldModelLib：load_kb/save_kb + canonical/hash 纯函数 + 共用结构门
   _validate_kb_payload）+ builtin_modules 注册面（_SPEC_WORLD_MODEL +
   BUILTIN_MODULE_SPECS + register_builtin_modules；kernel-native 8→9）+ 诊断码
   +3（KNW_KB_ARTIFACT_MALFORMED/SCHEMA_VERSION/HASH_MISMATCH；catalog +
   15_diagnostics 对账）+ 文档（11_modules §11.12 world_model 节 + 11.2 列表
   [meta/selfref 补列——既有缺列一致性修正] + 16_knowledge_system 磁盘面节 +
   07_kernel_native_modules 计数/表行[既有 `file`→`fs` 命名漂移修正]）+ 测试
   17 例（runtime 13：canonical 确定性/排版无关/round-trip 保真/加载=活 KB
   增量/重导出同 hash/三级门各判别/排版无关 load/空 KB 面合法存 + e2e 4：
   **B1 验收形态**[load→活查询→增量 100 事实[循环批量注册+登记]→重导出再
   加载] + hash 审计面 + 篡改 try/except 用户面）。
   **验证**：全量 pytest 零回归（模块注册面变更保守放行门，见 NEXT_STEPS 基线
   锚点）。**B1 验收达成**（试用方 R-B 验收面 1/4）：load_kb 后活查询 + 增量
   100 事实可用 + 无需重编译（全 IBCI 代码面实证）；M1 = P2+P3+P4 联合
   （P4 确定性模式为余项）。
   设计要点 = `tasks_docs/_p3_disk_format_design.md`（P4 批次开工前保留——含
   §3 加载三级门 + §4 保存语义 + §6 测试面；试用方配合项 ② = 按此格式重新
   导出 v30 补 id/source/status 元数据）。
- **P4 R-C 确定性执行模式落地（--deterministic 零 LLM 不变量 + 审计凭证，
   2026-09-10，unsafe-vibe-dev；世界模型 DB 主线批次 4，两批 D1-D2 收束）**：
   **试用方 R-C 验收面 + M1 余项收口**（M1 = P2+P3+P4 联合——P4 落地即 M1
   达成）。面 = CLI `run --deterministic` + 引擎级 `deterministic_guard` 参数
   （同 budget_guard 装配路径）+ result-json 凭证字段。
   **关键裁定（self-grill 全分支消解）**：① 面定位 = CLI flag + 引擎参数
   （非新 IBCI 模块——run 级执行模式 = 宿主装配语义，同 journal/budget/replay
   三兄弟；脚本内容不因模式改变；试用方请求字面 = "run --deterministic 或
   等价"）；② 机制 = **LLM 调用汇点 guard**（journal/budget 同点同边界——
   单一核算点 `_call_llm`；流式 ai.stream_call 不经汇点 = 子系统既有诚实
   边界同族；meta.eval 子进程 = 新引擎守卫不跨 spawn 继承——eval 环境参数
   边界同族，M1 事实表达式 = 纯代码子进程自然零 LLM）；③ 与 budget 分码
   （RUN_DETERMINISTIC_LLM_CALL vs RUN_BUDGET_EXCEEDED——零容忍 run 级
   不变量 vs 用户配置阈值——不同概念不同码；检查序 deterministic 先行
   [强不变量优先]）；④ 凭证 = `{enforced: true, llm_calls: 0}`（拦截在前
   post-call 永不达——计数恒 0 = 结构事实非观测推断；result-json v1 加法
   演进：字段缺省 = 未启用）；⑤ --deterministic × --replay **互斥**（replay
   供给 LLM 响应 = 预期有 LLM 调用 vs 零容忍——矛盾组合装配前校验期
   fail-fast，不装入注定失败的组合）；⑥ 审计凭证机读 = 试用方"LLM 调用
   次数=0"验收的字面落法（trailer 末行 JSON，验收机 tail -n1 即得）。
   **关键发现（既有缺陷 + 既有边界，落档）**：
   - **既有缺陷修复**：budget/deterministic guard 的 `InterpreterError` 曾把
     node_uid（str）当 location（Location 对象）传——CLI 渲染面
     DiagnosticFormatter 按 Location 契约取 `.file_path` 崩溃（budget fail
     面同型既有崩溃实证后修复：location=None + 消息面；经 VM 翻译面到达时
     定位信息归 statement 侧诊断承载——CLI 实证含源定位 + snippet 正常渲染）。
   - **既有边界发现并落档**（KNOWN_LIMITS 新 §二十七）：行为值 future 按需
     解析——**未引用 LLM 值的错误静默吞没**（无 guard 基线同型实证：mock
     失败/真失败/确定性拦截同面——值被消费或顶层 = 正常 fail-fast）；
     应对 = 需显形的 LLM 值必须被消费；确定性零 LLM 不变量结构性成立
     不受影响（拦截在 provider 前——llm_calls=0 凭证恒真）。
   **变化前后**：+DeterministicGuard（core/runtime/observability/
   deterministic.py 新模块——observability 三兄弟 journal/budget/
   deterministic）+ ServiceContext set_deterministic_guard/属性 + _call_llm
   汇点检查（budget 之前）+ 引擎 run/run_string/execute deterministic_guard
   参数 + main.py --deterministic（互斥校验 + 凭证字段 + result-json schema
   加法）+ budget.py location 修复 + 新码 RUN_DETERMINISTIC_LLM_CALL
   （catalog + 15_diagnostics[码条目 + run 可观测面节 + 凭证 schema]）+
   KNOWN_LIMITS §二十七 + 测试 12 例（runtime 7：单元恒拦截/凭证形态/引擎面
   纯代码零侵入/顶层拦截/无 guard 基线/双 guard 先行 + budget 零消耗/
   try-except 可捕获[值消费面] + e2e CLI 5：**M1 验收形态**[KB artifact +
   load_kb + quote/eval 一条事实数据形态对拍 + 成立性判定；两次独立 CLI run
   数据面逐字节一致 + 凭证 llm_calls=0] / LLM 脚本拦截面 / 互斥面 /
   零侵入对照 / 纯代码凭证）。
   **验证**：全量 pytest 零回归（语义错误集变更放行门——新 RUN_ 码 +
   budget 行为修复；见 NEXT_STEPS 基线锚点）。**M1 验收达成**（试用方里程碑
   1：load_kb → 确定性模式下 quote/eval 一条事实，全程零 LLM、可复现、
   凭证机读——替代静态投影的最小活集成）。
   设计要点 = `tasks_docs/_p4_deterministic_mode_design.md`（P5 批次开工前
   保留——含 §2 汇点机制/边界 + §5 测试面；quote/eval 当前契约 = 纯表达式
   自包含源[__qeval__ = <source> 包装]——M1 脚本形态按此契约书写）。
    **P4 批次开工收尾**：删除 `tasks_docs/_p4_deterministic_mode_design.md`
    （P5 开工——裁定全在本条目 + docs/）。
- **P5 R-D 工件加载落地（narrow_model 值类型 + world_model.bind_artifact
   窄模型工件面，2026-09-10，unsafe-vibe-dev；世界模型 DB 主线批次 5，
   两批 E1-E2 收束）**：**试用方 R-D 验收面**（bind 已训练窄模型工件 →
   推理时 score/topk 可调用且确定性，**纯推理零训练**）。
   **调研结论（试用方窄模型真实形态，D-ISO 实证）**：试用方窄模型 = **KG
   嵌入向量空间模型**（e30/e40）——主架构 **TransE**（实体嵌入 E∈R^{N×d} +
   关系嵌入 R∈R^{M×d}；`f(s,r,o)=‖e_s + r_r − e_o‖` 平移假设，距离越小越
   优）；推理面 = `predict_rank`（全候选算距离升序排序）——**纯算术零训练**
   （训练在试用方侧离线完成）。多架构（TransE+DistMult）consensus = 试用方
   侧**离线交叉验证/质控**，非推理时 score 面——**推理时模型 = TransE**
   （实证：predict_rank 只用 TransE fdist）。
   **关键裁定（self-grill 全分支消解）**：① 实现 **TransE 推理面**（忠实
   试用方实际推理模型）；DistMult/ComplEx **不预置**（离线质控面非 R-D
   推理契约；架构字段预留扩展位，未知架构 = 结构门 fail-fast）；② 面定位 =
   **新值类型 `narrow_model`（不可变冻结工件值）+ `world_model` 模块加载面**
   （与 P3 `knowledge` 值 + `world_model.load_kb` 同构——值类型承载数据，
   模块函数承载磁盘装配）；③ score 语义 = TransE **距离**（忠实试用方
   predict_rank 升序语义，文档明示"越小越优"；不反转——忠实试用方实际
   指标，判定面归 D1 确定性路径，此处仅内容信号）；④ 确定性 = 候选序
   artifact entities 固定序 + 排序键 (距离,实体名) 升序（稳定 tie-break）+
   IEEE 浮点纯算术（同输入同输出）；⑤ 参考未注册词 = **fail-fast**（同 KB
   治理门纪律：冻结模型词表固定，无静默默认）；⑥ 不可变（同
   quoted/vector/run_result 纪律：无修改面 + deep_clone 引用复用 + 序列化
   原生直存）；⑦ 空白构造 fail-fast（模型必经 bind_artifact 加载门——良构
   由加载门成立，同 quoted 仅经 meta.quote 产出）。
   **变化前后**：+`narrow_model` 值类型（core/runtime/objects/primitives/
   narrow_model.py 新原语 + NarrowModelAxiom 新公理 + NARROW_MODEL_SPEC 新
   spec 原型 + 序列化 collect/hydrate + deep_clone 不可变面 + primitives
   __init__ 注册）+ world_model 模块扩展（bind_artifact/save_artifact +
   窄模型 artifact 格式 + canonical hash + 三级门——同 load_kb 纪律）+
   builtin_modules world_model spec 面加 bind_artifact/save_artifact +
   新码 +6（NAR_ARTIFACT_MALFORMED/SCHEMA_VERSION/HASH_MISMATCH 加载门域 +
   NAR_ENTITY_UNREGISTERED/RELATION_UNREGISTERED/TOPK_INVALID 推理域）+
   catalog + 15_diagnostics + 11_modules §11.12 窄模型工件面 + 测试 38 例
   （E1 值类型 20：注册/vtable 绑定/score 算术对照手工 TransE/topk 排序+
   tie-break 确定性/同输入同输出/未注册实体关系 k 非法 fail-fast/k 超界
   截断/元数据面+副本/不可变无修改面/to_native 快照独立/deep_clone 引用
   复用/序列化 round-trip + E2 磁盘面 15：canonical hash 确定性/排版无关/
   内容敏感/版本常量 + bind 保真/save 重导出同 hash/save 门 + 三级门各
   判别/未知架构/维度不符/排版重排/缺失文件 fs 同构 + e2e 3：R-D 两次独立
   CLI run 数据面逐字节一致+凭证 llm_calls=0/score topk 可调用确定值/
   bind 纯读取零训练）。
   **关键发现（既有边界落档）**：topk 返回容器（list of dict）经 IBCI `==`
   = **恒等语义**（KNOWN_LIMITS §10.5，P2 已落档）——e2e 确定性断言不直接
   容器 `==` 对比（改逐元素值对比 / CLI 数据面逐字节对比）；narrow_model
   的确定性由"值（str/float）逐元素按值 + CLI 数据面逐字节"两路佐证。
   **验证**：全量 pytest 零回归（公理层变更放行门——新值类型 + 新码 +
   模块面；见 NEXT_STEPS 基线锚点）。**R-D 验收达成**（bind 后 score/topk
   可调用且确定性同输入同输出；全程无训练调用——纯推理零 LLM）。
   设计要点 = `tasks_docs/_p5_artifact_loading_design.md`（P5 设计单点
   真理：调研结论 + 面定位 + artifact 格式 + 测试面；P6 批次开工前保留）。
   **P5 批次开工收尾**：删除 `tasks_docs/_p5_artifact_loading_design.md`
   （P6 开工——裁定全在本条目 + docs/）。
- **P6 向量面落地（knowledge 词嵌入面 + KB artifact v2，2026-09-10，
   unsafe-vibe-dev；世界模型 DB 主线批次 6，两批 F1-F2 收束）**：**KB 词嵌入
   cosine 内容信号（非判定）；磁盘格式预留 ANN**。
   **调研结论（现有向量面实证）**：`ai` 模块已有低层向量原语——`embed(texts)`
   （文本→向量，`set_embedding_mock` 提供**确定性 mock 向量**）+ `retrieve
   (query: vector, corpus: list, k)`（通用暴力 cosine 检索）+ `recall`（文本→
   embed→retrieve）；`vector` 原语已有一等值类型（dot/cosine/scale/add/sub）。
   **缺口 = KB 无嵌入面**（词/事实嵌入无处持久化 + KB 无原生相似检索）。
   **关键裁定（self-grill 全分支消解）**：① **嵌入面挂 `knowledge` 值类型**
   （单点真理 = KB 值，决策点3；与 P2"演化 knowledge 就地"同纪律——不另立
   平行向量索引类型）；② **词级（非事实级）**——嵌入挂治理词表（词全局非
   per-world）；事实级嵌入（需定义事实嵌入=词嵌入组合 or 独立）= 后置扩展不
   预置（避免事实嵌入语义臆测）；设计签名 `embed_search(query, world?, k)`
   的 `world?` 对词嵌入无意义（词全局）——本批落词级 `embed_search(query, k)`
   ，world 过滤归事实级嵌入扩展；③ **内容信号非判定**（`embed_search` 返回
   相似度 rank/分数，异常检测/语义对比用，从不做判定——D1 判定走图平面，与
   narrow_model.score 同定位）；④ **query = vector**（纯内容信号，str/vector
   无多态；按词检索先 `embedding(word)` 取向量，任意文本经 `ai.embed`）；
   ⑤ **暴力 cosine**（小规模；无索引常驻服务；ANN/FAISS 派生加速 = 后置，
   决策点3：纯 IBCI 值+工件起步）；⑥ **确定性**（cosine = IEEE 浮点纯算术；
   排序键 (−score, word) 升序 = score 降序 + 平手按词名稳定 tie-break）；
   ⑦ **机制分层非重复**（`ai.embed`/`ai.retrieve` = 低层原语保留；
   `kb.embed_search` = KB 自身词表上高层内容信号检索）；⑧ **vector 参数不可
   unbox**（`vector.to_native` 显式违约）——set_embedding/embed_search 经
   `.elements` 取原生元素（统一纪律）。
   **KB artifact 版本演进（v1 → v2 加法）**：v2 加 `vector: {dim,
   embeddings}` 节（词嵌入持久化）；canonical/hash **版本感知**（v1 =
   `{facts,seq,vocab}` 无 vector / v2 = `{facts,seq,vocab,vector}` 含 vector）；
   保存恒 v2（空嵌入面 `dim=0`）；加载接受 v1+v2（v1 向后兼容嵌入面空）；
   `KB_SCHEMA_VERSION = 2` + `_KB_KNOWN_VERSIONS = (1, 2)`。
   **变化前后**：+`knowledge` 嵌入面（payload 新面 `embeddings: {word: [float]}`
   + 5 方法 set_embedding/embedding/has_embedding/embedding_dim/embed_search
   + 公理 KnowledgeAxiom 加 5 方法面 + 序列化 collect/hydrate 嵌入面）+
   world_model load_kb/save_kb 版本感知（v1 向后兼容 + v2 vector 节）+ 新码
   +3（KNW_EMB_DIM_MISMATCH / KNW_EMB_NOT_SET / KNW_EMB_SEARCH_INVALID）+
   catalog + 15_diagnostics + 16_knowledge_system 向量面节 + 11_modules KB
   artifact v2 格式 + 测试 26 例（F1 值类型 18：set_embedding 治理门/
   embedding 取回+fail-fast/embed_search cosine 排序+确定性 tie-break+同输入
   同输出+k 非法超界截断空面+cosine 值对照手工/embedding_dim+has_embedding/
   序列化 round-trip + F2 磁盘面 6：v2 round-trip 保真/重导出幂等/v1 向后兼容/
   hash 版本感知 v1≠v2/嵌入篡改检测 + e2e 2：内容信号确定性两次独立 CLI run
   逐字节一致+凭证 llm_calls=0/v2 artifact 往返）。
   **既有边界**：`ai.embed`/embedding provider 不经 LLM 汇点（独立 provider
   路径）——`--deterministic` 零 LLM 凭证对向量面成立（mock 嵌入零 LLM，
   cosine 纯算术）；与 P4 流式/eval 子进程边界同族（embedding 独立面）。
   **验证**：全量 pytest 零回归（公理层变更放行门——knowledge 新面 + artifact
   v2 + 新码；见 NEXT_STEPS 基线锚点）。
   设计要点 = `tasks_docs/_p6_vector_plane_design.md`（P6 设计单点真理：
   调研结论 + 面定位 + artifact v2 演进 + 测试面；P7 批次开工前保留）。
   **P6 批次开工收尾**：删除 `tasks_docs/_p6_vector_plane_design.md`
   （P7 开工——裁定全在本条目 + docs/）。
- **P7 R-F 投影派生视图落地（knowledge.to_ibci()，2026-09-10，
   unsafe-vibe-dev；世界模型 DB 主线批次 7，两批 G1-G2 收束）**：**KB 当前态
   的确定性 IBCI 代码派生视图（非存储层）**——替代 lossy stopgap
   `schema_to_ibci.py`（全词汇/全事实无丢失 + 无魔法默认 + 按需派生免全量
   重编译）。
   **调研结论（stopgap 实证 + IBCI 代码面实证）**：stopgap 每词生成 IBCI
   class 用硬编码 if 字符串分支 + `"target:relation_type"` 单字符串 + **根本不
   存 axioms（静默丢 34 条 only_in_axioms 事实，lossy 实证）** + `return
   "unknown"`/`return ""` 魔法默认（红线）+ 无查询/索引 + KB 增长需全量重编译。
   IBCI 代码面实证：支持 dict/list/bool 字面量 + 字符串转义 + 末尾裸值合法
   可执行 + 执行后经 `runtime_context.get_variable` 取回重建值 → 投影代码可
   确定性生成 + 可执行重建 + 可对拍。
   **关键裁定（self-grill 全分支消解）**：① 面定位 = `to_ibci()` 挂
   `knowledge` 值类型（设计 §3.3 `kb.to_ibci()` 权威形态；与 P6 嵌入面同纪律
   ——KB 值的方法面；只读导出无修改面，同 export()）；② **派生视图非存储
   层**（单一权威源 = 活 KB / artifact；代码投影从日志派生绝不独立存储）；
   ③ **当前态非全史**（不回放 amend/retract 事件史——amend 原始 o 不可恢复
   [事件链只存 new_o，原 o 被覆盖丢失]→ 全史回放不可能；投影重建当前态，
   active+retracted 事实均含 status 保真；历史归 fact 日志权威面 + artifact）；
   ④ **确定性**（词汇序 = KB 自身插入序[worlds/relations/words] + 事实序 =
   fact_id(str(seq))序 + 字面量序列化规范化[dict 键排序 + str 转义 \\\" \\\\
   \\n \\t，bool 先于 int] → 同 KB 逐字节一致）；⑤ **治理门顺序**（先注册全
   词汇 worlds→relations→words 再 add_fact——满足 add_fact 词表 allowlist
   门）；⑥ **无新诊断码**（to_ibci 只读导出无治理违约面——语义错误集不变）；
   ⑦ **fact_id 边界**（add-only KB = 投影 fact_id 与原一致；含 amend/retract
   历史的 KB = id 可能偏移[历史事件也增 seq]——当前态 o/status 仍一致，对拍
   按语义查询结果非 fact_id 本身）。
   **变化前后**：+`knowledge.to_ibci()`（确定性 IBCI 代码发射器：词汇[KB 插入
   序] + 当前态事实[fact_id 序] + 字面量序列化 _ibci_literal/_ibci_str + 末尾
   裸 kb 可求值）+ 公理 KnowledgeAxiom 加 to_ibci 方法面 + 测试 16 例（G1
   runtime 对拍 13：确定性两次/两引擎逐字节一致/投影代码编译+执行无错/末尾裸
   kb/对拍 lookup_pair+exists+by_subject+contradicts+transitive+facts 语义字段
   全一致 + 词表一致/retracted 事实投影 status 保真/全事实无 lossy + G2 e2e 3：
   投影代码两次独立 CLI run 数据面逐字节一致 + 零 LLM 凭证/对拍活 KB 逐字节
   一致/独立执行重建 KB 无外部依赖）。
   **既有边界（e2e 层红线）**：e2e 禁 import `core.runtime.objects.`——投影
   代码经 `run_ibci`（`print(kb.to_ibci())`）生成（黑箱，不 import runtime
   内部件），经独立 CLI run 执行；对拍/确定性/零 LLM 凭证全在 CLI 数据面
   验证。
   **验证**：全量 pytest 零回归（公理层变更放行门——knowledge 新面 to_ibci；
   见 NEXT_STEPS 基线锚点）。**R-F 验收达成**（to_ibci 产物与活 KB 查询结果
   对拍一致；派生视图确定性/零 LLM/无 lossy）。
   设计要点 = `tasks_docs/_p7_projection_design.md`（P7 设计单点真理：stopgap
   缺陷实证 + 面定位 + 投影代码形态 + 对拍面 + 测试面；P8 批次开工前保留）。
    **P7 批次开工收尾**：删除 `tasks_docs/_p7_projection_design.md`
    （P8 开工——裁定全在本条目 + docs/）。
- **P8 测试进程内化（e2e 降子进程开销 + 消冗余，2026-09-10，
  unsafe-vibe-dev；世界模型 DB 主线批次 8，单批收束）**：**消除端到端流水线
  可复现性的 4x 冗余（dual-channel）**——P4-P7 各做一次 CLI 两 run 逐字节一致
  测试，但流水线可复现性是**流水线属性**（CLI → 引擎 → 输出序列化的端到端
  可复现性），非每 feature 属性——流水线确定性对全部 feature 一致，测一次即
  够。
  **调研结论（e2e 子进程开销实证，2026-09-10 实跑）**：e2e 层子进程开销
  **大部分不可化约**——① 纯 CLI 机制测试（replay 8 / result_json 6 / budget 5 /
  journal 3 / check_export 等 `_run_cli` 调用，每次 ~0.4-1s 子进程）测 CLI 本身
  机制，subprocess by design；② ihost 子运行测试（run_file/run_code/run_isolated
  5 文件 ~19s）测子进程子运行机制，subprocess by design。安全内化空间 = ③
  P4-P7 的 4x 冗余流水线可复现性两 run 测试（每 feature 各重复一次流水线
  属性，3x 冗余）。
  **关键裁定（self-grill 全分支消解）**：① **流水线可复现性 = 流水线属性**
  （非 feature 属性）——归并为**单一代表性测试**（P4 M1 两 run：旗舰 R-C 验收
  + 代表性流水线可复现性）；② **feature 确定性 = feature 属性**（同输入同
  输出）——归**进程内**（P5 test_topk_same_input_same_output / P6
  test_search_same_input_same_output / P7 test_same_kb_byte_identical 已存在；
  P5 另有 test_bind_is_pure_read 进程内同值）；③ **CLI 凭证机制 = CLI 属性**
  （`--deterministic` 凭证 llm_calls=0 + exit ok + 查询值）——每 feature
  **单 run** CLI 保留（非两 run）；④ **P4 不加进程内 M1 两 run**（P4 M1 两 run
  即代表性流水线可复现性 + M1 确定性，保留 CLI 两 run 不瘦身）。
  **变化前后**：P5 narrow_model e2e（两 run → 单 run CLI 凭证，确定性归并进
  process）+ P6 embedding e2e（两 run → 单 run CLI 凭证，确定性归并进 process）
  + P7 to_ibci e2e（两 run → 单 run CLI 凭证，确定性归并进 process）+ P4 M1
  e2e（文档澄清 = 代表性流水线可复现性单一测试，保留两 run）。
  **既有边界**：纯 CLI 机制测试 + ihost 子运行测试 subprocess by design 保留
  （非冗余——测 CLI/子运行机制本身）；端到端流水线可复现性由 P4 M1 单点覆盖。
  **验证**：全量 pytest 零回归（阶段边界放行门——P7→P8；测试层变更不动
  core/，见 NEXT_STEPS 基线锚点）。**P8 验收达成**（消 3x 冗余流水线可复现性
  两 run + 4 e2e 文件省 ~3s[12→9s]；确定性覆盖无损——进程内 feature 确定性 +
  P4 M1 代表性流水线可复现性 + 单 run CLI 凭证）。
  **诚实结论（P8 价值定性）**：e2e 子进程开销大部分不可化约（CLI 机制 +
  子运行 by design）；P8 安全内化空间有限（~3s，全量门 ~129→~126s）。主价值 =
  **消 dual-channel 冗余（质量）**，非大幅省时（速度）。
- **P9 Rust 内核 阶段① 地基（构建链 + 差分等价 harness，2026-09-10，
  隔离分支 `rust-kernel`；世界模型 DB 主线批次 9 第 1 阶段）**：**Rust 化最耗时
  的 VM 执行层**（生产负载 cProfile 实证：执行层每步 Python 反射/间接开销 =
  数量级瓶颈，Rust 移植后同循环预计 ~1ms 量级 100-1000x；runtime 层 38% 解释器
  CPU 直接受益）——pyo3 四阶段（① 地基 → ② Rust 前端 → ③ 执行核心[主战场] →
  ④ 并发解除），每阶段独立有价值、可回退。
  **阶段① 交付（零风险加法式地基）**：
  - **构建链**：新 crate `ibci-ext/`（pyo3 0.23 extension-module，crate-type
    cdylib，产物 `ibci_ext.so`）+ `scripts/build_rust_ext.sh`（**pin
    CARGO_HOME=$PWD/.cargo_local + CARGO_TARGET_DIR=$PWD/target**——默认 cargo
    位置不可写[agent bash EACCES]；PYO3_PYTHON=项目 venv；常规网络允许[pyo3
    依赖下载免审批]）。Rust 扩展 = **opt-in**（默认 Python 内核零依赖可装——
    wheel 发布面不变；.so 为可再生构建产物 gitignore 不入库）。
  - **crate 骨架**：`version()`/`kernel_info()`（name/stage/status 元数据——
    差分 harness 接入点）/`run()`（**显式 NotImplemented，无静默回退**——双
    内核协议：Rust 内核未落地 = 显式报错，不悄悄切 Python 内核）。
  - **差分等价 harness**（`tests/diff_harness/`，**常设交付物 = 整个替换的
    安全网**）：比对 Python 内核（一等实验内核，参考）与 Rust 内核（生产快
    路径）对同一 IBCI 语料的数据面（print 输出）**同输入→同输出逐字节等价**。
    语料 = 代表语义面种子 14 条（算术/控制流/函数[显式类型注解]/容器/字符串/KB
    世界模型[register/add_fact/lookup/contradicts]）+ 后续扩展（现有测试用例 +
    fuzz 种子）。Rust 未就绪（status != "ready"）→ 仅 Python 参考确定性验证
    （两次执行逐字节一致），不冒充 Rust。
  **关键裁定（self-grill 全分支消解）**：① **双内核协议**（核心设计裁定）：
  Python 内核 = 一等实验内核（默认，保留不删）+ Rust 内核 = 生产快路径（显式
  opt-in，**无静默回退** fail-fast）——两内核共享同一 AST 契约 + contracts 层
  语义红线，语言语义单点真理不变；双内核 ≠ compat shim（工作模式定论）= 同一
  语言的两个一等执行后端，选择经协议显式化；② **构建链 opt-in**（Rust 非硬
  构建依赖——setuptools 后端不变，.so 经独立 build 脚本产出，默认安装零 Rust
  依赖）；③ **差分 harness 为常设安全网**（阶段②/③/④ 每阶段 Rust 落地后须经
  harness 验证与 Python 参考内核差分等价零差异方可放行；语义漂移 = 最高风险，
  harness + contracts 红线 + 公理层/语义错误集变更全量 pytest 红线三重防护）；
  ④ **CARGO pin 纪律**（默认 cargo 位置不可写 → pin workspace 内，免审批）；
  ⑤ **IBCI 函数须显式类型注解**（参数 + 返回值；用返回值/递归须 `-> 类型` 定
  型——语料种子面实证）。
  **验证**：全量 pytest 零回归（开新分支前 + 阶段边界放行门——加法式地基不动
  Python 执行路径，计数 = 4257 + harness 5 = 4262；见 NEXT_STEPS 基线锚点）。
  **阶段① 出口达成**（构建链 + crate 骨架 + 差分 harness 安全网就位；Rust 扩展
  可构建可加载，run 显式 NotImplemented 待阶段②/③ 落地执行核心）。
  **分支状态**：`rust-kernel` 隔离分支（自 unsafe-vibe-dev）；阶段① 零风险加
  法式地基，验证后 merge unsafe-vibe-dev 并删分支（分支政策：确认零风险即
  merge + 删分支）；阶段②/③/④ 续在隔离分支（Rust 执行核心触及公理层语义，
  高风险面须隔离 + 差分 harness 门）。
  **P9 调研单点真理** = `tasks_docs/_rust_kernel_survey.md`（实测定性 + 四阶段
  + 双内核协议 + 预期效果 + 风险对策 + 环境事实）；本阶段展开 = 阶段① 实施。
- **P9 终点裁定（用户 2026-09-10，重新定义 P9 终点——全量 Rust 化）**：
  "Rust 部分任务完成后，允许开启新的评估和新的自主执行模式，评估全核心逻辑、
  全量 Rust 化。保留关键部分的 Python 接口，以提供灵活性和供 Python 使用的
  入口能力。当我们证明绝大部分关键核心逻辑都可以 Rust 化的时候，就可以全量
  转向 Rust，而不必再保留 Python 双通道和对比。"
  **裁定解析（self-grill）**：① **终点演进**：P9 从"Rust 化 VM 执行层"（四阶段
  ①-④）扩展为**全核心逻辑全量 Rust 化**（编译/语义/执行/调度/并发等核心面）——
  Rust 部分（①-④）完成后开启**新评估 + 新自主执行模式**，评估全核心逻辑可 Rust
  化面；② **保留关键部分 Python 接口**（终点态，非废弃）：供灵活性（热迭代/调试）
  + 供 Python 使用的入口能力——终点态 = Rust 核心 + 关键部分 Python 接口层（入口/
  灵活性），**非** 100% 无 Python；③ **废弃 Python 双通道/对比（触发条件）**：当
  **证明绝大部分关键核心逻辑可 Rust 化**（差分等价零差异 + 全量 pytest 零回归 +
  覆盖面实证）→ 全量转向 Rust，废弃 Python 双内核 + 差分 harness 对比（迁移期安全
  网退场）；④ **迁移期安全网**：双内核协议（Python = 参考基准 + 调试路径，Rust =
  待证明生产内核）+ 差分等价 harness = 迁移期防护（**临时**，非永久——调研文档
  §2.3 定位已从"永久双内核"演进为"迁移机制"）；⑤ **渐进证明纪律**：全量 Rust 化
  是渐进证明（非一次性）——逐面证明可 Rust 化（差分等价）→ 覆盖面达"绝大部分关键
  核心逻辑" → 触发全量转向 + 废弃双通道。
  **变化前后**：调研文档 §2.3 双内核协议定位（永久双内核 → 迁移机制[临时]）+
  新增 §2.6 终点裁定（全量 Rust 化 + 保留关键 Python 接口 + 废弃双通道触发条件 +
  渐进证明纪律）；NEXT_STEPS/HANDOFF P9 终点同步。
  **执行序列（据裁定）**：Rust 部分（阶段②前端 → ③执行核心 → ④并发解除）继续 →
  完成后开启新评估 + 新自主执行模式（评估全核心逻辑全量 Rust 化：编译/语义/调度/
  并发等核心面逐一证明可 Rust 化）→ 证明绝大部分关键核心逻辑可 Rust 化 → 全量
  转向 Rust + 废弃 Python 双通道/对比（保留关键部分 Python 接口）。
- **P9 阶段② Rust 前端首增量（Rust lexer 移植 + token 级差分等价，2026-09-10，
  隔离分支 `rust-kernel`；全量 Rust 化迁移的前端地基）**：**Rust 化 IBCI 前端
  首增量**——lexer（源码 → token 流）移植到 Rust，经 token 级差分等价验证与
  Python 参考 lexer 逐条等价（差分 harness 门）。
  **交付**：
  - **Rust lexer**（`ibci-ext/src/lexer.rs`）：对齐 Python `core/compiler/lexer`
    的 core normal 模式——StrStream（位置跟踪 line/col，对齐 str_stream.py）+
    CoreScanner（scan_line 行循环 + _scan_normal_char 字符分派 + 字符串/数字/
    标识符/关键字/运算符[两字符优先] + 括号栈[续行] + 注释）+ IndentProcessor
    （INDENT/DEDENT，start_col 消费前记录 + tab=1 + EOF dedent column=0）+ 行
    处理（lexer.py 循环 + 续行）。移植范围 = 语料面（算术/控制流/函数/容器/
    字符串/KB）；行为块(@~...~)/意图/三引号串/raw 串/变量引用($x) = 后续增量。
  - **pyo3 暴露**：`ibci_ext.lex(script) -> list[dict]`（每项 = {type, value,
    line, column, end_line, end_column, is_at_line_start}）。
  - **差分 harness 扩展**（`tests/diff_harness/harness.py`）：token 级差分面
    （`python_lexer_tokens`/`rust_lexer_tokens`/`token_differential`）——Rust
    token 流 == Python token 流（type 名 + value + line + column 逐条）；.so 未
    构建 = 优雅降级（不冒充等价）。
  **关键裁定（self-grill 全分支消解）**：① **token 级差分 = 前端首增量门**
  （Rust lexer 与 Python lexer 逐条等价——后续 parser/semantic 增量经 AST 级
  差分门，最终执行核心经数据面差分门[现有 harness]，三级差分逐级验证）；②
  **移植范围 = 语料面**（覆盖差分 harness 14 条语料；行为块/意图等子状态 = 后续
  增量，非 subset 双通道——是渐进移植 + 差分门，终点 = 全量 Rust 前端）；③
  **差分等价实证（14/14 语料 token 级逐条等价）**——修 3 类移植 bug（运算符未
  先消费首字符致 match 误匹配 / INDENT column 须消费前记录 start_col / EOF
  dedent column=0）；④ **Rust 借用纪律**（单一 Lexer struct 自持 scanner + 状态，
  `&mut` 方法——避免 Python 共享 StrStream 的借用问题）。
  **验证**：token 级差分 14/14 语料逐条等价 + 全量 pytest 零回归（阶段边界放行
  门——加法式增量不动 Python 执行路径，计数 = 4263 + harness 3 = 4266；见
  NEXT_STEPS 基线锚点）。**阶段② 首增量出口达成**（Rust lexer 移植 + token 级
  差分等价门就位）。
  **分支状态**：`rust-kernel` 隔离分支；阶段② 首增量零风险加法式（opt-in，不动
  Python 执行路径），验证后 merge unsafe-vibe-dev 并删分支；阶段② 后续（parser/
  semantic）+ ③ 执行核心 + ④ 并发解除续在隔离分支（差分门逐级验证）。
- **P9 阶段② 第二增量（Rust parser 移植 + AST 级差分等价，2026-09-10，
  隔离分支 `rust-kernel`；全量 Rust 化迁移的前端第二增量）**：**Rust 化 IBCI
  parser 首增量**——最小语句/表达式面（Assign / ExprStmt / Constant / Name /
  BinOp[+] / Call[func(args)]）移植到 Rust，经 AST 级差分等价验证与 Python
  参考 parser 逐条等价（差分 harness 门）。
  **交付**：
  - **AST 规范 dumper**（`tests/diff_harness/ast_dump.py`，Python 侧差分参考
    工具）：IBC 语法树 → 规范字符串形态 `<节点类名>(field1=<val1>, ...)`（字段
    按 dataclass 声明序，子节点递归，标量 repr，列表 `[...]`，None = "None"）；
    `include_positions=False` = structure 模式（排除位置字段——AST 结构差分核心；
    位置跟踪 = Rust parser 后续增量单独验证）。
  - **Rust parser**（`ibci-ext/src/parser.rs`）：对齐 Python `core/compiler/
    parser` 的最小面——AST 类型（Module / Assign / ExprStmt / Constant[int/
    str/bool/None] / Name / BinOp / Call）+ 递归下降解析（token 流 → AST）+
    structure dumper（产出与 Python ast_dump 一致的规范形态）。
  - **pyo3 暴露**：`ibci_ext.parse_struct(source) -> str`（AST structure 规范
    形态）。
  - **差分 harness 扩展**：AST 级差分面（`rust_parse_struct` / `ast_differential`
    ）——Rust AST structure == Python AST structure（逐字节）；.so 未构建 = 优雅
    降级。
  **关键裁定（self-grill 全分支消解）**：① **AST 级差分 = parser 增量门**（Rust
  parser 与 Python parser 的 AST structure 逐字节等价——三级差分逐级验证：token
  级[lexer ✅] → AST 级[parser 本增量] → 数据面[执行核心]）；② **structure 模式**
  （AST 结构差分核心 = 节点类型 + 字段值；位置跟踪 = 后续增量单独验证——避免
  本轮陷入复杂的位置跟踪对齐）；③ **最小语句/表达式面**（Assign / ExprStmt /
  Constant / Name / BinOp[+] / Call——覆盖差分验证面；完整语句/表达式面 + 语义层
  = 后续增量，渐进移植 + 差分门，非 subset 双通道）；④ **Rust 借用纪律**（parse_
  primary 先拷贝 token type+value 再 match + 消费——避免 peek 借用跨 advance
  mutable 调用）。
  **验证**：AST 级差分 6/6 片段等价（assign_int/assign_str/binop/call/call_2arg/
  multi——Rust AST structure == Python AST structure 逐字节）+ 全量 pytest 零
  回归（阶段边界放行门——加法式增量不动 Python 执行路径，计数 = 4266 + AST 级
  差分 1 例 = 4267；见 NEXT_STEPS 基线锚点）。**阶段② 第二增量出口达成**（Rust
  parser 移植 + AST 级差分等价门就位）。
  **分支状态**：`rust-kernel` 隔离分支；阶段② 第二增量零风险加法式（opt-in，不动
  Python 执行路径），验证后 merge unsafe-vibe-dev 并删分支；阶段② 后续（完整语句/
  表达式面 + 位置跟踪对齐 + 语义层）+ ③ 执行核心 + ④ 并发解除续在隔离分支
  （差分门逐级验证）。
- **P9 阶段② 第三增量（Rust parser 完整语句/表达式面 + AST 级差分等价，
  2026-09-10，隔离分支 `rust-kernel`；全量 Rust 化迁移的前端第三增量）**：**Rust
  parser 扩至完整语料面**——从最小面（Assign/ExprStmt/Constant/Name/BinOp[+]/Call）
  扩展到完整语料面（14/14 语料 AST 级逐字节等价），覆盖 if/elif/for/func def 等
  完整语句 + 完整表达式。
  **交付**：
  - **Rust parser 扩展**（`ibci-ext/src/parser.rs` 完整重写）：
    - 语句面：Assign[Name/Subscript/Attribute target，回退式前瞻] / ExprStmt /
      If[elif 链 = orelse 嵌套 IbIf] / For[target ctx='Store'] / FunctionDef[typed
      args Ibrg + returns] / Return / Break / Continue / Pass + INDENT/DEDENT body
      解析（parse_body）。
    - 表达式面：Constant / Name / BinOp[+ - * / // % **，递归下降优先级
      compare < additive < term < power[右结合] < unary < postfix] / UnaryOp /
      Compare[链] / Call[func(args)] / List / Dict / Attribute[obj.method] /
      Subscript[obj[idx]]。
  - **AST 级差分门扩展**：`test_ast_differential_corpus`（全部 14 条语料 Rust AST
    structure == Python AST structure 逐字节）。
  **关键裁定（self-grill 全分支消解）**：① **回退式前瞻 Assign 解析**（解析
  target[Name/Subscript/Attribute]后随 ASSIGN = Assign，否则回退 ExprStmt——
  处理 `d['c'] = 3`[Subscript target] 与 `xs.append(4)`[ExprStmt] 的区分）；②
  **递归下降优先级**（compare < additive < term < power[右结合] < unary <
  postfix[call/attr/subscript]——对齐 Python 运算符优先级）；③ **INDENT/DEDENT
  body 解析**（parse_body 经 lexer 的 INDENT/DEDENT token 界定 if/for/func body）；
  ④ **elif 链 = orelse 嵌套 IbIf**（对齐 Python AST——elif 非独立节点，是 orelse
  里的嵌套 If）；⑤ **For target ctx='Store'**（对齐 Python——for 循环 target 是
  存储上下文）。
  **验证**：AST 级差分 **14/14 语料逐字节等价**（完整语料面——Rust parser 完整
  语句/表达式面 == Python parser）+ 全量 pytest 零回归（阶段边界放行门——加法式
  增量不动 Python 执行路径，计数 = 4267 + AST 级差分 1 例 = 4268；见 NEXT_STEPS
  基线锚点）。**阶段② 第三增量出口达成**（Rust parser 完整语料面 + AST 级差分
  等价门就位）。
  **分支状态**：`rust-kernel` 隔离分支；阶段② 第三增量零风险加法式（opt-in，不动
  Python 执行路径），验证后 merge unsafe-vibe-dev 并删分支；阶段② 后续（位置跟踪
  对齐 + 语义层 + 剩余语句/表达式[while/try/lambda/三元/复合类型注解]）+ ③ 执行
  核心 + ④ 并发解除续在隔离分支（差分门逐级验证）。
- **P9 阶段② 第四增量（Rust parser 位置跟踪对齐 + AST 完整形态差分等价，
  2026-09-10，隔离分支 `rust-kernel`；全量 Rust 化迁移的前端位置跟踪）**：**Rust
  parser 位置跟踪对齐**——每节点 (lineno/col_offset/end_lineno/end_col_offset) 对齐
  Python parser 的 `_loc`（start token 的 line/col + end token 的 end_line/end_col），
  经 AST 完整形态（含位置）差分等价验证与 Python 参考 parser 逐字节等价。
  **交付**：
  - **lexer end 位置修复**（`ibci-ext/src/lexer.rs`）：合成 token（NEWLINE/EOF/
    INDENT/DEDENT）的 end_line/end_column 统一 = (0,0)（对齐 Python Token dataclass
    默认 end=(0,0)——这些 token 无实际结束位置）。**关键发现**：此前 token 级差分
    只比 (type/value/line/column)，未比 end 位置，漏过此 bug（NEWLINE/EOF/INDENT/
    DEDENT 的 end 误设为自身位置）。修复后 token 完整位置（含 end）14/14 语料等价。
  - **Rust parser 位置跟踪**（`ibci-ext/src/parser.rs`）：每 AST 节点记录 Pos
    （line/col + end_line/end_col），从 token 设置——对齐 Python `_loc` 模式：
    IbName/IbConstant=token 位置；IbBinOp=left 起/right 止；IbCall=func 起/RPAREN
    止；IbAssign=**target 起/target 止**（end=target.end，非 value.end）；IbExprStmt
    =value 位置；IbIf/IbFor/IbFunctionDef=**keyword 起/DEDENT 止(0,0)**；IbReturn=
    **RETURN token 起/止**（非 value 止）；IbArg=arg name 起/止；IbUnaryOp=**op
    token 起/止**（非 operand 止）；IbModule=(0,0,None,None)。
  - **AST dumper 含位置**：`parse_struct` 产出完整形态（含位置）；差分 harness
    `ast_differential` 升级为完整形态比对（include_positions=True）；token 级差分
    升级为完整位置比对（含 end_line/end_column）。
  **关键裁定（self-grill 全分支消解）**：① **位置跟踪 = 从 token 设置**（每节点
  的 start/end token 对齐 Python `_loc` 的 token 选择——IbAssign end=target.end /
  IbReturn end=RETURN.end / IbUnaryOp end=op.end 等节点特定规则）；② **合成 token
  end=(0,0)**（NEWLINE/EOF/INDENT/DEDENT 无实际结束位置——修 lexer 的 end 误设）；
  ③ **IbModule end=None**（模块节点 end 未设——区别于其他节点的 Some(0)）；④
  **位置跟踪对齐 = 完整 AST 差分门**（Rust AST 完整形态[含位置] == Python AST 完整
  形态——比 structure 模式更强）。
  **验证**：AST 完整形态（含位置）差分 **14/14 语料逐字节等价** + token 完整位置
  （含 end）差分 14/14 语料等价 + 全量 pytest 零回归（阶段边界放行门——加法式增量
  不动 Python 执行路径，计数 = 4268；测试数不变[更新现有 10 例，非新增]；见
  NEXT_STEPS 基线锚点）。**阶段② 第四增量出口达成**（Rust parser 位置跟踪对齐 +
  AST 完整形态差分等价门就位）。
  **分支状态**：`rust-kernel` 隔离分支；阶段② 第四增量零风险加法式（opt-in，不动
  Python 执行路径），验证后 merge unsafe-vibe-dev 并删分支；阶段② 后续（语义层
  [符号表/类型环境] + 剩余语句/表达式[while/try/lambda/三元/复合类型注解/class]）
  + ③ 执行核心 + ④ 并发解除续在隔离分支（差分门逐级验证）。
- **P9 阶段② 第五增量（Rust parser 剩余语句/表达式面 + AST 完整形态差分等价，
  2026-09-10，隔离分支 `rust-kernel`；全量 Rust 化迁移的前端剩余面）**：**Rust
  parser 扩至剩余语句/表达式面**——while / try[except/else/finally] / class / 三元
  （IbIfExp）/ lambda[IbLambdaExpr，typed params + 返回类型]，经 AST 完整形态（含
  位置）差分等价验证与 Python 参考 parser 逐字节等价。
  **交付**：
  - **Rust parser 剩余面**（`ibci-ext/src/parser.rs`）：
    - 语句面：While（while test: body [else]）/ Try（try: body except [type] [as
      name]: body [else] [finally]，IbExceptHandler）/ ClassDef（class Name: body，
      fields = Assign 语句[类变量] / methods = FunctionDef 语句）。
    - 表达式面：IfExp 三元（`body if test else orelse`，最低优先级层——parse_expr
      拆为 parse_ternary[三元] → parse_compare[比较]）/ Lambda（`lambda [(typed
      params)][: or -> TYPE:] body_expr`，IbLambdaExpr，capture_mode='lambda'）。
  - **位置跟踪**：IbWhile/IbClassDef = keyword 起/DEDENT 止(0,0)；IbTry = TRY
    token 起/止；IbExceptHandler = EXCEPT token 起/止；IbIfExp = body 起/orelse
    止；IbLambdaExpr = LAMBDA 起/body 止。
  - **递归类型断环**（Rust 借用/大小纪律）：Expr::Lambda → Vec<Arg> →
    Option<Expr> 递归致无限大小——Box Arg.annotation/default + Lambda.returns
    断环。
  **关键裁定（self-grill 全分支消解）**：① **三元 = 最低优先级层**（parse_expr 拆
  为 parse_ternary → parse_compare——三元低于比较，右结合[嵌套三元]）；② **class
  fields/methods 从 body 提取**（fields = Assign 语句，methods = FunctionDef 语句，
  对齐 Python IbClassDef——body 含全部语句，fields/methods 为分类视图）；③ **lambda
  语法 = `lambda[(typed params)][: or -> TYPE:] body`**（params 须类型注解，对齐
  IBCI——`lambda(a):` 无类型注解编译失败，`lambda(int a):` 正确）；④ **递归类型断
  环**（Box 断 Expr→Lambda→Arg→Expr 循环——Rust 类型大小纪律）。
  **验证**：剩余面 AST 完整形态（含位置）差分 **7/7 逐字节等价**（while/try/class/
  三元/lambda[typed/noarg/ret]）+ 语料面 14/14 无回归 + 全量 pytest 零回归（阶段
  边界放行门——加法式增量不动 Python 执行路径，计数 = 4268 + 剩余面 1 例 = 4269；
  见 NEXT_STEPS 基线锚点）。**阶段② 第五增量出口达成**（Rust parser 剩余语句/
  表达式面 + AST 完整形态差分等价门就位——Rust 前端 parser 面（语料面 + 剩余面）
  全量对齐 Python parser）。
  **分支状态**：`rust-kernel` 隔离分支；阶段② 第五增量零风险加法式（opt-in，不动
  Python 执行路径），验证后 merge unsafe-vibe-dev 并删分支；阶段② 后续（语义层
  [符号表/类型环境]——AST → 带符号/类型的 AST）+ ③ 执行核心 + ④ 并发解除续在
  隔离分支（差分门逐级验证）。
- **P9 阶段③ 首增量（执行核心：Rust artifact 反序列化器 + 战略微调，2026-09-10，
  隔离分支 `rust-kernel`）**：
  **战略微调（据总体规划灵活微调授权）**：P9 阶段②（前端）的语义层（7427 行多
  pass pipeline + 需完整编译环境[registry/source manager/issue tracker]）推迟
  Rust 移植；**直接推进阶段③ 执行核心（主战场）**——执行核心消费 Python 前端
  产出的序列化 artifact（FlatSerializer JSON，含语义层输出[符号表/类型/侧表]），
  Rust 侧反序列化 + 执行；语义层 Rust 移植 = 全量 Rust 化后续（非阻塞执行核心）。
  **依据**：① 执行核心 = cProfile 实证的性能瓶颈（per-step Python 反射/间接，
  量级差距）——主战场，价值最高；② 语义层 7427 行 + 完整环境依赖，移植成本高，
  且执行核心可消费 Python 语义层输出（经 artifact），非阻塞；③ 渐进 Rust 化：
  执行核心（Rust）+ 前端（Python）先行，前端 Rust 化（语义层）后续。
  **交付**：
  - **Rust artifact 反序列化器**（`ibci-ext/src/deserializer.rs`）：序列化
    CompilationArtifact（FlatSerializer JSON dict，nodes/symbols/scopes/types 池
    + UID 引用）→ Rust AST（复用 parser 的 Expr/Stmt 类型 + dumper）。本增量 =
    nodes 池（AST 节点，语料面 19 种节点类型）→ Rust AST。符号池/类型池/侧表 =
    后续增量（执行核心需要）。
  - **pyo3 暴露**：`ibci_ext.deserialize_struct(artifact_json) -> str`（反序列化
    AST 完整形态，含位置）。
  - **serde_json 依赖**（Cargo.toml + cargo 网络下载）——artifact JSON 解析。
  - **差分 harness 扩展**：反序列化器差分面（`rust_deserialize_struct`）——
    artifact JSON → Rust AST == Python AST（完整形态含位置）。
  **关键裁定（self-grill 全分支消解）**：① **执行核心消费 Python artifact**（迁移
  期策略——前端 Python[lexer/parser/semantic] → artifact → Rust 执行核心；前端
  Rust 化[语义层]后续，非阻塞执行核心）；② **反序列化器 = 执行核心输入契约**
  （Rust 侧消费 FlatSerializer JSON——nodes 池 UID 引用 → 重构 AST；符号/类型/
  侧表后续）；③ **复用 parser AST 类型 + dumper**（反序列化器重构 parser 的
  Expr/Stmt，复用 dumper 验证——单一 AST 权威形态）；④ **serde_json 依赖**
  （artifact 是 JSON dict，serde_json 是标准解析——非常规网络下载，允许）。
  **验证**：反序列化 AST 差分 **14/14 语料逐字节等价**（artifact → Rust AST ==
  Python AST，完整形态含位置）+ 全量 pytest 零回归（阶段边界放行门——加法式增量
  不动 Python 执行路径，计数 = 4269 + 反序列化器 1 例 = 4270；见 NEXT_STEPS 基线
  锚点）。**阶段③ 首增量出口达成**（Rust artifact 反序列化器 + 执行核心输入契约
  就位）。
  **分支状态**：`rust-kernel` 隔离分支；阶段③ 首增量零风险加法式（opt-in，不动
  Python 执行路径），验证后 merge unsafe-vibe-dev 并删分支；阶段③ 后续（执行核心：
  符号池/类型池/侧表反序列化 + 对象模型 + CPS 分发[43 节点] + 数据面差分门）+ ④
  并发解除续在隔离分支（差分门逐级验证）；语义层 Rust 移植 = 全量 Rust 化后续。
- **P9 阶段③ 第二增量（执行核心：Rust 对象模型 + tree-walking 解释器 + 数据面
  差分等价，2026-09-10，隔离分支 `rust-kernel`）**：**Rust 执行核心（主战场）
  突破**——非 KB 语料面（11/11）数据面差分等价（Rust 执行 print 输出 == Python
  执行 print 输出），证明 Rust 执行核心可消费 Python 前端 artifact 并产出等价数据
  面。
  **交付**：
  - **Rust 对象模型**（`ibci-ext/src/interpreter.rs` IbValue）：Int / Float / Str /
    Bool / None / List / Dict——List/Dict 经 **Rc<RefCell>**（共享可变——append/
    dict 下标赋值原地修改，clean Rust 方式，避免 tricky 特判）。数据面 repr 对齐
    Python print（float 整数值 = `4.0`；list `[e, e]`；dict `{"k": v}`；str 原样）。
  - **Rust 解释器**（tree-walking）：反序列化 AST → 执行 → 数据面。语句面：Assign
    [Name/Subscript target] / ExprStmt / If[elif 链] / For / While / FunctionDef /
    Return / Break / Continue / Pass；表达式面：Constant / Name / BinOp[+ - * /
    // % **] / UnaryOp / Compare / Call / List / Dict / Attribute[方法] / Subscript /
    IfExp；内建：print / len / range；方法：list.append / str 方法（upper 等）。
  - **IBC 数值语义对齐**：`/` = `//` = floor 除（`-7 / 2` = `-4`）；int + float =
    float（`2 + 2.0` = `4.0`）；`%` = euclidean（`rem_euclid`）；`**` = pow。
  - **环境 + 作用域链**：变量绑定 + 函数定义 + 递归（call_env 父 = 全局环境，使
    函数体可访问全局函数）。
  - **pyo3 暴露**：`ibci_ext.run_artifact(artifact_json) -> list`（数据面）。
  **关键裁定（self-grill 全分支消解）**：① **tree-walking 解释器**（非 CPS——
  迁移期验证数据面等价；CPS 优化[43 节点 enum 分发] = 后续增量，数据面等价后做
  性能优化）；② **Rc<RefCell> 共享可变容器**（clean Rust 方式——避免 tricky 特判
  的 append/dict 赋值）；③ **递归经作用域链**（call_env 父 = 全局环境——函数体可
  访问全局函数）；④ **IBC 数值语义 = floor 除**（`/` 与 `//` 同义，`-7/2 = -4`——
  对齐 Python IBCI 行为，非 IEEE 除）；⑤ **KB 语料面 = 后续增量**（knowledge()
  宿主服务需宿主环境——非 KB 语料面 11/11 先验证）。
  **验证**：数据面差分 **11/11 非 KB 语料逐条等价**（Rust 执行 == Python 执行：
  算术[7,2,1]/循环[55]/负数[-2,8]/控制流[big,0,1,2,嵌套]/函数[5,7]/递归[120]/
  list[1,2,3,4,2,4]/dict[1,{"a":1,"b":2,"c":3}]/string[hello world,5]）+ 全量
  pytest 零回归（阶段边界放行门——加法式增量不动 Python 执行路径，计数 = 4270 +
  数据面差分 2 例 = 4272；见 NEXT_STEPS 基线锚点）。**阶段③ 第二增量出口达成**
  （Rust 执行核心对象模型 + 解释器 + 数据面差分等价门就位——**主战场突破**）。
  **分支状态**：`rust-kernel` 隔离分支；阶段③ 第二增量零风险加法式（opt-in，不动
  Python 执行路径），验证后 merge unsafe-vibe-dev 并删分支；阶段③ 后续（CPS 优化
  [43 节点 enum 分发] + KB 语料面[宿主服务] + 符号池/类型池/侧表反序列化 + 性能
  基准[cProfile 对比]）+ ④ 并发解除续在隔离分支（差分门逐级验证）；语义层 Rust
  移植 = 全量 Rust 化后续。
- **P9 阶段③ 第三增量（执行核心性能基准——Rust 23–30x 加速实证，2026-09-10，
  加法式零风险增量直接提交 unsafe-vibe-dev）**：**Rust 执行核心性能基准**——
  常设基准脚本 `scripts/bench_rust_kernel.py`（测量同一 IBCI 语料的两执行核心
  耗时，微秒/次）实证 Rust 执行核心比 Python 执行核心**快 23–30x**（主战场价值
  实证——cProfile 实证的 per-step Python 反射/间接瓶颈被 Rust 消除）。
  **交付**：
  - **常设基准脚本**（`scripts/bench_rust_kernel.py`）：Python（run_ibci =
    compile[artifact 缓存] + VM 执行）vs Rust（compile[Python 缓存] → serialize →
    run_artifact[反序列化 + 执行]）耗时对比（微秒/次，300 次迭代均值）。非测试
    （性能断言 flaky）——基准脚本，结果记录 WORKLOG。
  **基准结果（2026-09-10 实跑，非 KB 语料面 11 条）**：
    - arithmetic_basic：Python 10427μs / Rust 378μs = **27.6x**
    - arithmetic_loop：10806 / 379 = **28.5x**
    - arithmetic_neg：10298 / 356 = **28.9x**
    - control_if：10645 / 384 = **27.7x**
    - control_for_break：10954 / 367 = **29.9x**
    - control_nested：10856 / 379 = **28.6x**
    - function_basic：11107 / 397 = **28.0x**
    - function_recursion：11008 / 402 = **27.4x**
    - list_ops：11029 / 470 = **23.5x**
    - dict_ops：10784 / 468 = **23.1x**
    - string_ops：10690 / 369 = **28.9x**
    - **均值 ≈ 27x 加速**（Rust tree-walking 未优化即显著领先）。
  **关键裁定（self-grill 全分支消解）**：① **基准公平性**（两侧均含 load +
  execute——Python 的 compile 缓存查找 vs Rust 的 JSON 反序列化，非偏袒）；②
  **tree-walking 未优化即 27x**（Rust 执行核心即使未做 CPS 优化[43 节点 enum
  分发]已显著领先——CPS 优化 = 后续增量，进一步提升）；③ **非 KB 语料面**（KB
  语料需宿主服务——后续增量）；④ **基准脚本非测试**（性能断言 flaky——记录
  结果，不进测试套件）。
  **验证**：基准脚本运行无错（11/11 非 KB 语料产出加速比）+ 全量 pytest 零回归
  （加法式增量——基准脚本非测试，不动 Python 执行路径，计数 = 4272；见 NEXT_STEPS
  基线锚点）。**阶段③ 第三增量出口达成**（执行核心性能基准 + 23–30x 加速实证
  就位——主战场价值确认）。
  **分支状态**：加法式零风险增量直接提交 `unsafe-vibe-dev`（与 doc-sync 同理——非
  破坏性，无需隔离分支）；阶段③ 后续（CPS 优化[43 节点 enum 分发] + KB 语料面
  [宿主服务] + 符号池/类型池/侧表反序列化）+ ④ 并发解除续推进（差分门逐级验证）；
  语义层 Rust 移植 = 全量 Rust 化后续。
- **P9 阶段③ 第四增量（执行核心 KB 语料面——host service 桥接，全语料 14/14 数据
  面差分等价，2026-09-10，隔离分支 `rust-kernel`）**：**Rust 执行核心覆盖全语料
  面**——KB 语料面（knowledge() 宿主服务）经 host service 桥接（Rust → Python
  回调）委托给 Python knowledge 对象（KB 逻辑留 Python 单点真理，不复制 KB 逻辑
  到 Rust 避免双通道），全语料 **14/14 数据面差分等价**（11 非 KB + 3 KB）。
  **交付**：
  - **host service 桥接**（Rust → Python 回调）：`IbValue::Host(Py<PyAny>)` 变体
    （宿主对象引用）+ `knowledge()` → 经桥接 `create_knowledge()` 创建 Python
    knowledge 对象 + KB 方法调用（register_world/add_fact/worlds/exists/
    lookup_pair/contradicts）→ 委托 Python 对象方法（GIL 下 call_method）+ 参数/
    结果双向转换（Rust IbValue ↔ Python 对象：int/str/bool/None/list/dict/宿主
    对象）。
  - **Python 桥接助手**（`tests/diff_harness/bridge.py`）：`create_knowledge()`
    （经 IBCI 类型系统 registry 创建 knowledge 对象——单点真理）。
  - **pyo3 暴露**：`ibci_ext.run_artifact(artifact_json, bridge)`——bridge = host
    service 桥接（KB 操作经此委托；None = 无宿主服务，非 KB 面）。
  **关键裁定（self-grill 全分支消解）**：① **host service 桥接（Rust → Python
  回调）**（KB 逻辑留 Python 单点真理——不复制 KB 逻辑到 Rust 避免双通道；Rust
  执行核心委托 KB 操作给 Python knowledge 对象）；② **IbValue::Host（宿主对象
  引用）**（Rust 侧持有 Python 对象引用——KB 对象经桥接创建，方法调用委托）；
  ③ **参数/结果双向转换**（Rust IbValue ↔ Python 对象——int/str/bool/None/
  list/dict/宿主对象，嵌套结构[lookup_pair 的 list of dict of nested list]正确
  转换）；④ **call_method 动态参数**（pyo3 0.23：args = 直接传 PyTuple[解包为
  独立参数]，非 (tuple,)[包装成单参数]——修复参数传递 bug）；⑤ **Py<PyAny> 无
  Clone**（手动 Clone impl 经 clone_ref 增引用 + as_ptr 身份比较）；⑥ **桥接助手
  经 registry 创建**（`reg.get_class("knowledge")` + `IbKnowledge._create_blank`
  ——经 IBCI 类型系统，非直接构造）。
  **验证**：数据面差分 **14/14 全语料逐条等价**（11 非 KB[算术/循环/控制流/函数/
  递归/list/dict/string] + 3 KB[kb_world_vocab/kb_fact_lookup/kb_contradicts，
  host service 桥接]）+ 全量 pytest 零回归（阶段边界放行门——加法式增量不动
  Python 执行路径，计数 = 4272 + 数据面差分 2 例 = 4274；见 NEXT_STEPS 基线锚点）。
  **阶段③ 第四增量出口达成**（Rust 执行核心覆盖全语料面——14/14 数据面差分等价
  + host service 桥接就位）。
  **分支状态**：`rust-kernel` 隔离分支；阶段③ 第四增量零风险加法式（opt-in，不动
  Python 执行路径），验证后 merge unsafe-vibe-dev 并删分支；阶段③ 后续（CPS 优化
  [43 节点 enum 分发，在 27x 基础上进一步提升] + 符号池/类型池/侧表反序列化 +
  更宽 IBCI 语料[超出当前 14 条]）+ ④ 并发解除续在隔离分支（差分门逐级验证）；
  语义层 Rust 移植 = 全量 Rust 化后续。
- **P9 阶段③ 第五增量（执行核心更宽 IBCI 语料 + 布尔逻辑解析——全语料 20/20 数据
  面差分等价，2026-09-10，隔离分支 `rust-kernel`）**：**Rust 执行核心泛化性验证**
  ——语料从 14 扩至 20（+control_while/expr_ternary/expr_bool/function_nested/
  string_methods/list_more），全语料 **20/20 数据面差分等价**（四级差分逐级验证：
  token/AST/反序列化/数据面），证明执行核心可处理更宽 IBCI 语义面（while 循环/
  三元表达式/布尔逻辑 and/or/not/嵌套函数/字符串方法/列表拼接）。
  **交付**：
  - **语料扩展**（`tests/diff_harness/corpus.py`）：+6 条（control_while[while
    循环] / expr_ternary[三元表达式赋值形式] / expr_bool[布尔逻辑 and/or/not] /
    function_nested[嵌套函数] / string_methods[strip/upper/lower] / list_more[列表
    拼接 + 下标]）。
  - **Rust parser 加布尔逻辑层级**（`ibci-ext/src/parser.rs`）：`Expr::BoolOp`
    变体 + dumper[对齐 Python IbBoolOp 格式] + parse_or/parse_and/parse_not 层级
    （优先级：ternary < or < and < not < compare，对齐 Python；BoolOp 左结合，
    not 右结合；位置：BoolOp = 首 value 起/末 value 止，not = not token 起/止）。
  - **Rust deserializer 加 IbBoolOp**（`ibci-ext/src/deserializer.rs`）：artifact
    IbBoolOp 节点 → Rust BoolOp（values = UID 数组 → expr_of）。
  - **Rust interpreter 加 BoolOp + not**（`ibci-ext/src/interpreter.rs`）：and/or
    短路求值（and 返回第一个假值/末值，or 返回第一个真值/末值）+ not（UnaryOp
    op='not' → !truthy）。
  **关键裁定（self-grill 全分支消解）**：① **布尔逻辑优先级对齐 Python**（ternary
  < or < and < not < compare——parse_or/parse_and/parse_not 层级插入 ternary 与
  compare 之间）；② **BoolOp 左结合 + not 右结合**（`a or b or c` = (a or b) or
  c；`not not x` = not (not x)）；③ **BoolOp 位置 = 首/末 value**（start=首个
  value 起，end=末个 value 止，对齐 Python）；④ **三元用赋值形式**（IBCI 三元
  `body if test else orelse` 在赋值上下文工作，call 参数内受限[IBCI 语法边界]）；
  ⑤ **嵌套函数当前实现支持语料面**（inner 不访问 outer 变量——闭包完整语义[访问
  outer 局部] = 后续增量，非当前语料面需求）。
  **验证**：四级差分 20/20 全语料逐条等价（token[完整位置]/AST[完整形态含位置]/
  反序列化[artifact → Rust AST]/数据面[Rust 执行 == Python 执行]）+ 全量 pytest
  零回归（阶段边界放行门——加法式增量不动 Python 执行路径；计数 = 4274；见
  NEXT_STEPS 基线锚点）。**阶段③ 第五增量出口达成**（Rust 执行核心泛化性验证
  ——全语料 20/20 四级差分等价）。
  **分支状态**：`rust-kernel` 隔离分支；阶段③ 第五增量零风险加法式（opt-in，不动
  Python 执行路径），验证后 merge unsafe-vibe-dev 并删分支；阶段③ 后续（CPS 优化
  [43 节点 enum 分发，在 27x 基础上进一步提升] + 符号池/类型池/侧表反序列化 + 闭
  包完整语义 + 更宽 IBCI 语料[行为表达式/quoted 值等]）+ ④ 并发解除续在隔离分支
  （差分门逐级验证）；语义层 Rust 移植 = 全量 Rust 化后续。
- **P9 阶段③ 第六增量（执行核心闭包完整语义——嵌套函数访问 outer 局部变量，22
  语料四级差分等价，2026-09-10，隔离分支 `rust-kernel`）**：**Rust 执行核心闭包
  语义**——`Rc<RefCell<Environment>>` 重构（环境共享可变）+ Function 捕获
  enclosing（定义处环境）——嵌套函数可访问 outer 局部变量（closure_capture /
  closure_top_global），全语料 **22/22 四级差分等价**（token/AST/反序列化/数据
  面），执行核心作用域语义完整（递归 + 顶层读全局 + 嵌套闭包捕获）。
  **交付**：
  - **Rc<RefCell<Environment>> 重构**（`ibci-ext/src/interpreter.rs`）：环境从
    `Box<Environment>`（独占）→ `Rc<RefCell<Environment>>`（共享）——作用域链 +
    闭包捕获经 Rc 共享（同一环境可被多处引用）。
  - **Function 捕获 enclosing**（定义处环境）：FunctionDef 执行时 `enclosing =
    Some(env.clone())`（捕获当前环境 Rc）；调用时 `call_env` 的 parent = enclosing
    [嵌套函数访问 outer 局部] 或 global[顶层函数，递归 + 读全局]。
  - **global_rc 自由函数**：短借用走 Rc 链取全局环境（不跨递归持借用——避免
    RefCell 运行时 panic）。
  - **语料扩展**（+closure_capture[嵌套函数读 outer 局部] / closure_top_global[
    顶层函数读全局]）。
  **关键裁定（self-grill 全分支消解）**：① **Rc<RefCell> 共享环境**（闭包需共享
  同一环境——Box 独占无法共享；RefCell 运行时借用检查，短借用避免跨递归持借用）；
  ② **enclosing 捕获**（定义处环境——嵌套函数 call_env parent = enclosing，访问
  outer 局部；顶层函数 enclosing = global，递归 + 读全局）；③ **global_rc 短借用
  走链**（不跨递归持借用——RefCell 双借用运行时 panic 防护）；④ **IBCI 闭包边界
  对齐**（读 captured 变量工作；mut captured 全局是 IBCI 限制[VM Symbol UID 作用
  域]，非执行核心缺陷——Python VM 亦报错）；⑤ **删 Environment::global()**（返回
  临时借用悬空 E0515——被 global_rc 取代）。
  **验证**：闭包面 3/3 MATCH（nested_read_local[10]/top_read_global[100]/
  closure_counter2[42]）+ 四级差分 22/22 全语料逐条等价[token/AST/反序列化/数据
  面] + 全量 pytest 零回归（阶段边界放行门——加法式增量不动 Python 执行路径，计数
  稳定 4274[语料扩展不增测试数]；见 NEXT_STEPS 基线锚点）。**阶段③ 第六增量出口
  达成**（Rust 执行核心闭包语义完整——作用域链 + 闭包捕获 + 递归）。
  **分支状态**：`rust-kernel` 隔离分支；阶段③ 第六增量零风险加法式（opt-in，不动
  Python 执行路径），验证后 merge unsafe-vibe-dev 并删分支；阶段③ 后续（CPS 优化
  [43 节点 enum 分发，在 27x 基础上进一步提升] + 符号池/类型池/侧表反序列化 + 更
  宽 IBCI 语料[quoted 值/行为表达式]）+ ④ 并发解除续在隔离分支（差分门逐级验证）；
  语义层 Rust 移植 = 全量 Rust 化后续。
- **P9 阶段③ 第七增量（执行核心更宽 IBCI 面——链式比较/方法/嵌套容器，27 语料
  四级差分等价，2026-09-10，隔离分支 `rust-kernel`）**：**Rust 执行核心更宽 IBCI
  语义面**——链式比较（a < b < c）+ list 方法（index/pop）+ dict 方法（get[带
  默认值]/keys/values）+ str 方法（split/find）+ 嵌套容器（data['xs'][1]），全
  语料 **27/27 四级差分等价**（token/AST/反序列化/数据面），执行核心覆盖更宽 IBCI
  语义面。
  **交付**：
  - **链式比较**（`ibci-ext/src/interpreter.rs`）：Compare 从单比较（ops.first()）
    → 全链（左到右，全部成立——`a < b < c` = (a<b) and (b<c)，当前比较右值 = 下一
    比较左值）。
  - **list 方法扩展**：index[首次出现位置] / pop[末元素弹出+返回]。
  - **dict 方法扩展**：get[key] / get[key, default][缺失返默认] / keys[键列表] /
    values[值列表]。
  - **str 方法扩展**：split[分隔符切分→list] / find[子串位置，缺失=-1]。
  - **嵌套容器**：subscript on subscript（data['xs'][1]）——eval_expr 递归已支持。
  - **语料扩展**（+list_methods/dict_methods/nested_container/str_methods/
    chained_cmp）。
  **关键裁定（self-grill 全分支消解）**：① **链式比较左到右全链**（a < b < c =
  (a<b) and (b<c)——当前比较右值 = 下一比较左值，对齐 Python/IBC 链式语义）；②
  **dict.get 带默认值**（get[key, default] 缺失返默认——args.get(1)）；③ **str.
  split 空分隔符**（sep 空 = 按字符切分，对齐 Python）；④ **str.find 缺失 = -1**
  （对齐 Python）；⑤ **嵌套容器经递归**（subscript on subscript——eval_expr 递归
  求值 base 再求 slice，无特殊处理）；⑥ **while-else 是 IBCI 限制**（编译失败——
  非执行核心缺陷，Python VM 亦不支持，语料不含）。
  **验证**：更宽面 5/5 MATCH[链式比较[True, True]/list 方法[2, [1,2,3]]/dict
  方法[1, 0, [a, b]]/str 方法[[a, b, c], 2]/嵌套容器[2, 13]] + 四级差分 27/27 全
  语料逐条等价[token[完整位置]/AST[完整形态含位置]/反序列化[artifact→Rust AST]/
  数据面[Rust 执行==Python 执行]] + 全量 pytest 零回归（阶段边界放行门——加法式
  增量不动 Python 执行路径，计数稳定 4274[语料扩展不增测试数]；见 NEXT_STEPS 基线
  锚点）。**阶段③ 第七增量出口达成**（Rust 执行核心更宽 IBCI 语义面——链式比较 +
  方法扩展 + 嵌套容器）。
  **分支状态**：`rust-kernel` 隔离分支；阶段③ 第七增量零风险加法式（opt-in，不动
  Python 执行路径），验证后 merge unsafe-vibe-dev 并删分支；阶段③ 后续（CPS 优化
  [43 节点 enum 分发，在 27x 基础上进一步提升] + 符号池/类型池/侧表反序列化 + 更
  宽 IBCI 语料[quoted 值/行为表达式]）+ ④ 并发解除续在隔离分支（差分门逐级验证）；
  语义层 Rust 移植 = 全量 Rust 化后续。
- **P9 阶段③ 第八增量（执行核心符号池/侧表反序列化——完整 artifact 消费，27 语料
  符号表差分等价，2026-09-10，隔离分支 `rust-kernel`）**：**Rust 执行核心完整
  artifact 消费**——反序列化器从 nodes 池（AST）扩展至 symbols 池 + node_to_symbol
  侧表（语义层输出：变量/函数/方法的符号解析），全语料 **27/27 符号表差分等价**
  （Rust symbol_table == Python node_to_symbol 解析），执行核心可消费完整 artifact
  （不止 nodes 池）。
  **交付**：
  - **符号池/侧表反序列化**（`ibci-ext/src/deserializer.rs`）：`Symbol` 结构
    [name/kind/type_uid] + `symbol_table(artifact_json)`（消费 symbols 池 +
    node_to_symbol 侧表，输出 node → symbol 名解析规范表示，按 node_uid 排序）。
  - **pyo3 暴露**：`ibci_ext.symbol_table(artifact_json) -> str`（符号表规范表示）。
  - **差分 harness 扩展**：`rust_symbol_table` + `test_symbol_table_corpus`（符号
    表差分门——Rust symbol_table == Python node_to_symbol 解析）。
  **关键裁定（self-grill 全分支消解）**：① **完整 artifact 消费**（执行核心不止
  消费 nodes 池[AST]——还消费 symbols 池 + 侧表[语义层输出]，为后续类型检查/错误
  报告/CPS 分发就位）；② **node → symbol 解析**（node_to_symbol 侧表映射 AST 节点
  → 符号 UID，解析符号名——执行核心经此关联节点与语义）；③ **规范表示按 node_uid
  排序**（确定性输出，差分可比）；④ **serde_json Value 的 as_str 返回 Option**
    （侧表值是 Value，需解 Option——修 E0308）；⑤ **本增量不用于执行**（符号表
  是完整 artifact 消费的就位——tree-walking 解释器当前用简单变量绑定，符号表用于
  后续类型检查/错误报告，非当前数据面需求）。
  **验证**：符号表差分 **27/27 全语料逐条等价**（Rust symbol_table == Python
  node_to_symbol 解析）+ 四级差分 27/27 全语料逐条等价[token/AST/反序列化/数据
  面，无回归] + 全量 pytest 零回归（阶段边界放行门——加法式增量不动 Python 执行
  路径，计数 = 4274 + 符号表差分 1 例 = 4275；见 NEXT_STEPS 基线锚点）。**阶段③
  第八增量出口达成**（Rust 执行核心完整 artifact 消费——symbols 池 + node_to_symbol
  侧表就位）。
  **分支状态**：`rust-kernel` 隔离分支；阶段③ 第八增量零风险加法式（opt-in，不动
  Python 执行路径），验证后 merge unsafe-vibe-dev 并删分支；阶段③ 后续（CPS 优化
  [43 节点 enum 分发，在 27x 基础上进一步提升] + 类型池/资产池反序列化 + 更宽 IBCI
  语料[quoted 值/行为表达式]）+ ④ 并发解除续在隔离分支（差分门逐级验证）；语义层
  Rust 移植 = 全量 Rust 化后续。
- **P9 阶段③ 第九增量（执行核心类型池/node_to_type 反序列化——完整 artifact 消费
  续，27 语料类型表差分等价，2026-09-10，隔离分支 `rust-kernel`）**：**Rust 执行
  核心完整 artifact 消费续**——反序列化器从 symbols 池 + node_to_symbol 侧表扩展至
  types 池 + node_to_type 侧表（语义层类型输出：节点的类型解析），全语料 **27/27
  类型表差分等价**（Rust type_table == Python node_to_type 解析），执行核心可消费
  完整 artifact 的符号 + 类型输出。
  **交付**：
  - **类型池/node_to_type 反序列化**（`ibci-ext/src/deserializer.rs`）：
    `type_table(artifact_json)`（消费 types 池[uid → name] + node_to_type 侧表
    [node_uid → type_uid]，输出 node → type 名解析规范表示，按 node_uid 排序）。
  - **pyo3 暴露**：`ibci_ext.type_table(artifact_json) -> str`（类型表规范表示）。
  - **差分 harness 扩展**：`rust_type_table` + `test_type_table_corpus`（类型表差分
    门——Rust type_table == Python node_to_type 解析）。
  **关键裁定（self-grill 全分支消解）**：① **完整 artifact 消费续**（执行核心消费
  语义层符号[第八增量] + 类型[本增量]输出——为后续类型检查/错误报告/CPS 分发就
  位）；② **node → type 解析**（node_to_type 侧表映射 AST 节点 → 类型 UID，解析
  类型名——执行核心经此关联节点与类型）；③ **规范表示按 node_uid 排序**（确定性
  输出，差分可比）；④ **本增量不用于执行**（类型表是完整 artifact 消费的就位——
  tree-walking 解释器当前用简单变量绑定，类型表用于后续类型检查/错误报告，非当前
  数据面需求）；⑤ **资产池本增量不含**（语料面 assets 池为空——后续语料扩展后
  再消费）。
  **验证**：类型表差分 **27/27 全语料逐条等价**（Rust type_table == Python
  node_to_type 解析）+ 符号表/四级差分 27/27 无回归 + 全量 pytest 零回归（阶段
  边界放行门——加法式增量不动 Python 执行路径，计数 = 4275 + 类型表差分 1 例 =
  4276；见 NEXT_STEPS 基线锚点）。**阶段③ 第九增量出口达成**（Rust 执行核心完整
  artifact 消费——types 池 + node_to_type 侧表就位）。
  **分支状态**：`rust-kernel` 隔离分支；阶段③ 第九增量零风险加法式（opt-in，不动
  Python 执行路径），验证后 merge unsafe-vibe-dev 并删分支；阶段③ 后续（CPS 优化
  [43 节点 enum 分发，在 27x 基础上进一步提升] + 资产池反序列化 + 更宽 IBCI 语料
  [quoted 值/行为表达式]）+ ④ 并发解除续在隔离分支（差分门逐级验证）；语义层 Rust
  移植 = 全量 Rust 化后续。
- **P9 阶段③ 第十增量（执行核心 quoted 值面——IbImport + host 属性访问 + meta
  模块桥接，30 语料全级差分等价，2026-09-10，隔离分支 `rust-kernel`）**：**Rust
  执行核心 IBCI 自指原语**——quoted 值（meta.quote 冻结 / meta.eval 取值，P1 R-A
  自指地基）经 host service 桥接（宿主逻辑留 Python 单点真理），全语料 **30/30
  全级差分等价**（token/AST/反序列化/数据面 + 符号表/类型表），执行核心可处理
  IBCI 自指面（import + 宿主模块 + 宿主属性访问）。
  **交付**：
  - **IbImport 反序列化**（parser `Stmt::Import` + `Alias` 结构{name/asname/位置}
    + dumper[IbAlias 格式] + deserializer[IbImport → Alias 数组] + interpreter
    [import X [as Y] 绑定宿主模块]）。
  - **host 属性访问**（interpreter `Expr::Attribute`：宿主对象属性[如 q.source]委托
    桥接 host_getattr——IBC 宿主值类型经运行时 _dispatch_getattr 提供，纯 getattr
    不可达，对已知宿主值类型经 to_native 边界拆箱取字段）。
  - **meta 模块桥接**（bridge `get_host_module("meta")` → `_MetaModule` 封装 host
    service 的 quote_expression[编译门冻结 quoted 值] / eval_quoted[子进程取值]；
    engine project_root 确立[root_dir + _explicit_root，_sub_engine_compile +
    request_spawn_isolated 要求]）。
  - **语料扩展**（+quoted_source/quoted_eval_value/quoted_eval_expr）。
  **关键裁定（self-grill 全分支消解）**：① **quoted 值经 host service 桥接**（宿主
  逻辑留 Python 单点真理——meta.quote/eval 委托 Python host service，不复制自指
  逻辑到 Rust 避免双通道）；② **IbImport.names = Alias 节点数组**（非字符串——对齐
  Python IbImport 格式，含 IbAlias 位置 + asname）；③ **host 属性访问经桥接
  host_getattr**（IbQuoted.source 纯 getattr 不可达[经 IBC 运行时 _dispatch_getattr
  需 IbObject 包装]——对已知宿主值类型经 to_native 边界拆箱，非 tricky 硬编码分
  发）；④ **engine project_root 双重确立**（root_dir[_sub_engine_compile 读
  orchestrator.root_dir] + _explicit_root[request_spawn_isolated 读]）；⑤ **quoted
  数据面经桥接**（meta.eval 子进程 spawn——每例 ~0.3-1s，差分 harness 覆盖）。
  **验证**：quoted 值面 4/4 MATCH[quote_source[21 * 2]/eval_value[3]/eval_expr
  [13]/eval_str[hi]] + 全级差分 30/30 全语料逐条等价[token/AST/反序列化/数据面 +
  符号表/类型表] + 全量 pytest 零回归（阶段边界放行门——加法式增量不动 Python 执行
  路径，计数稳定 4276[语料扩展不增测试数]；见 NEXT_STEPS 基线锚点）。**阶段③ 第十
  增量出口达成**（Rust 执行核心 IBCI 自指原语——quoted 值经 host service 桥接）。
  **分支状态**：`rust-kernel` 隔离分支；阶段③ 第十增量零风险加法式（opt-in，不动
  Python 执行路径），验证后 merge unsafe-vibe-dev 并删分支；阶段③ 后续（CPS 优化
  [43 节点 enum 分发，在 27x 基础上进一步提升] + 资产池反序列化 + 更宽 IBCI 语料
  [行为表达式]）+ ④ 并发解除续在隔离分支（差分门逐级验证）；语义层 Rust 移植 = 全
  量 Rust 化后续。
- **P9 阶段③ 收束（执行核心就绪评估——kernel_info 状态升级 + 模块/run 文档，
  2026-09-10，`unsafe-vibe-dev` 直接提交[加法式零风险]）**：**P9 阶段③ 执行核心
  收束**——tree-walking 执行核心经 10 增量达成完整数据面（30 语料全级差分等价
  [token/AST/反序列化/数据面 + 符号表/类型表] + 性能 23–30x + 闭包完整语义 + KB
  世界模型面 + quoted 值自指原语 + 完整 artifact 消费[nodes/symbols/types 池 + 侧
  表]），**执行核心就绪**（数据面经 `run_artifact` 消费 Python 前端 artifact 执
  行）。本收束升级 `kernel_info` 状态（stage 1/skeleton → stage 3/execution-
  core）+ 更新模块/run 文档（执行核心就绪态 + run script 入口待前端）。
  **交付**：
  - **kernel_info 状态升级**（`ibci-ext/src/lib.rs`）：`{stage: 3, status:
    "execution-core"}`——执行核心就绪（数据面经 run_artifact 可用）；"ready"
    保留给全量内核（run script 入口，待 Rust 前端[语义层]移植后升）。
  - **模块文档更新**（`//!`）：执行核心就绪态（构建链 + lexer + parser + 反序列化
    器 + tree-walking 执行核心；30 语料全级差分等价 + 23–30x）。
  - **run 文档/消息更新**：全量 script 入口待前端（语义层）移植——执行核心就绪面
    经 run_artifact 单独验证（双内核协议无静默回退）。
  **关键裁定（self-grill 全分支消解）**：① **执行核心就绪 ≠ 全量内核就绪**
    （tree-walking 执行核心消费 Python 前端 artifact 执行——数据面就绪；全量
    script 入口需 Rust 前端[lexer + parser + 语义层]，语义层移植未落地故 run
    script 入口显式 NotImplemented；两就绪面区分：execution-core[数据面] /
    ready[全量]）；② **kernel_info.stage = 3**（阶段③ 执行核心）；③ **常设门行为
    不变**（`differential_check` 用 run script 全量入口，status "execution-core"
    ≠ "ready" → 仅 Python 确定性验证——Rust 数据面由 test_data_plane_* 经
    run_artifact 单独验证，覆盖不降）；④ **资产池不消费**（语料面 0 条，无差分
    价值——后续语料扩展后再消费）；⑤ **CPS 优化[43 节点 enum 分发]归阶段④**
    （tree-walking 已是 27x，CPS 为并发解除[task_scheduler 集成]服务，非执行核心
    数据面需求）。
  **验证**：kernel_info = {stage 3, execution-core} + run 显式 NotImplemented
    [消息更新] + 差分 harness 18/18 + smoke 832 零回归 + 性能基准重测[23–30x 确认
    仍成立] + 全量 pytest 零回归（阶段③→④ 边界放行门——加法式增量不动 Python
    执行路径，计数稳定 4276；见 NEXT_STEPS 基线锚点）。**阶段③ 收束达成**（Rust
    执行核心就绪——数据面经 run_artifact 消费 Python 前端 artifact）。
  **分支状态**：`unsafe-vibe-dev` 直接提交（加法式零风险——kernel_info + 文档，不
    动 Python 执行路径）；**阶段③ 执行核心收束**，下一批 = **阶段④ 并发解除**
    （task_scheduler IO-only → CPU+IO 真并行 GIL-free——CPS 优化[43 节点 enum 分发]
    在此落地）+ 语义层 Rust 移植 = 全量 Rust 化后续。
- **P9 阶段④ 首增量（并发解除——GIL-free 并行执行：py.allow_threads + 并行基准，
  4 线程 3.58x 真并行，2026-09-10，隔离分支 `rust-kernel`）**：**Rust 执行核心
  CPU+IO 真并行地基**——解释执行（CPU 工作）经 `py.allow_threads` 释放 GIL，多执行
  核心可**真正并行**（非协作式轮转）；IO 工作（宿主服务）经 `Python::with_gil` 重
  取 GIL 协作式推进。**4 线程并行 3.58x**（≈4x 理想，GIL-free 真并行成立）vs Python
  参考内核 GIL-bound ≈1.00x（无加速）。
  **交付**：
  - **GIL-free 执行**（`ibci-ext/src/lib.rs` `run_artifact`）：解释执行（CPU 工作）
    经 `py.allow_threads` 释放 GIL（持有 JSON 所有权，不跨 GIL 释放借用 Python 内
    存）；纯 CPU artifact（无 bridge）全程 GIL 释放；含宿主服务的 artifact 仅在宿主
    操作时经 `Python::with_gil` 重取 GIL。
  - **并行执行基准**（`scripts/bench_rust_parallel.py`）：固定总工作量 W 对等比较
    ——单线程跑 W 次 = T1，N 线程各跑 W/N 次墙钟 = TN，并行加速比 = T1/TN；Rust
    GIL-free（加速比 ≈N）vs Python GIL-bound（加速比 ≈1）对照。
  **关键裁定（self-grill 全分支消解）**：① **CPU+IO 真并行模型**（CPU 工作[解释
    执行]GIL-free 真并行 + IO 工作[宿主服务]GIL-bound 协作式——两面对应两种并发
    语义，非双通道）；② **持有 JSON 所有权**（不跨 GIL 释放借用 Python 内存——
    `&str` 借 Python 内存，跨 `allow_threads` 会悬垂，故 `to_string()` 持有）；③
    **并行基准对等比较**（固定总工作量 W——单线程 W 次 vs N 线程各 W/N 次，非不对
    等的单线程 3 次 vs 4 线程 12 次[初版基准计算错误已修正]）；④ **3.58x ≈ 4x
    理想**（GIL-free 真并行成立——略低于理想 = 线程启动/调度开销，非 GIL 竞争）；
    ⑤ **CPS 优化[43 节点 enum 分发]本增量不含**（GIL-free 地基先行，CPS 为 task_
    scheduler 集成服务，后续增量）。
  **验证**：**GIL-free 真并行 4 线程 3.58x**（≈4x 理想）vs Python GIL-bound ≈1.00x
    + 差分 harness 18/18 + smoke 832 零回归 + 全量 pytest 零回归（阶段④ 首增量放行
    门——加法式增量不动 Python 执行路径，计数稳定 4276；见 NEXT_STEPS 基线锚点）。
    **阶段④ 首增量出口达成**（Rust 执行核心 CPU 工作 GIL-free 真并行地基）。
  **分支状态**：`rust-kernel` 隔离分支；阶段④ 首增量零风险加法式（opt-in，不动
    Python 执行路径），验证后 merge unsafe-vibe-dev 并删分支；阶段④ 后续（CPS 优化
    [43 节点 enum 分发] + task_scheduler GIL-free 集成）续在隔离分支（差分门逐级
    验证）；语义层 Rust 移植 = 全量 Rust 化后续。
- **P9 阶段④ 第二增量（CPS 优化——node_types dispatch table + 扩 3 高频节点
  AugAssign/Tuple/Slice，33 语料全级差分等价，2026-09-10，隔离分支
  `rust-kernel`）**：**Rust 执行核心 CPS 优化**——① `node_types()` 暴露执行核心
  分发的节点类型（CPS dispatch table，对齐 Python VM 的 43/50 节点分发）；② 扩 3
  高频节点（IbAugAssign 复合赋值 / IbTuple 元组 / IbSlice 切片），33 语料全级差分
  逐条等价（token/AST/反序列化/数据面 + 符号表/类型表）。
  **交付**：
  - **CPS dispatch table**（`ibci-ext/src/deserializer.rs` `node_types()` +
    `ibci_ext.node_types()`）：执行核心分发的节点类型（反序列化 match 覆盖的 AST
    节点）——差分 harness 经此与 Python VM dispatch table（53 节点）比对覆盖差
    （当前 30 节点，23 节点覆盖差 = 阶段④ CPS 优化目标）。
  - **IbAugAssign**（`x += 1` / `x -= 1`）：parser（复合赋值 token PlusAssign/
    MinusAssign）+ deserializer + interpreter（load x → 应用 op → store，复合算子
    映射 +=→+ / -=→-）。
  - **IbTuple**（`(1, 2, 3)`）：parser（Lparen 后随 Comma = Tuple，位置 = 首元素起
    → 末元素止[不含括号]）+ deserializer + interpreter（元组 = 列表，IBC 数据面）。
  - **IbSlice**（`x[1:3]` / `x[:2]`）：parser（Lbracket 内 ':' = Slice，lower/upper
    可空[空 lower = xs[:2]]，位置 = ':' token）+ deserializer + interpreter（列表
    切片 lower:upper，Python 语义 [lower, upper)）。
  - **语料扩展**（+aug_assign/tuple_basic/list_slice）。
  **关键裁定（self-grill 全分支消解）**：① **node_types = CPS dispatch table**
    （执行核心分发的节点类型——对齐 Python VM 43/50 节点分发，差分 harness 经此
    比对覆盖差[当前 30/53，23 节点覆盖差 = 优化目标]）；② **IbTuple 位置 = 首元素
    起 → 末元素止**（不含括号——对齐 Python IbTuple 位置约定，非 `(` → `)`）；③
    **IbSlice lower/upper 可空**（`xs[:2]` 空 lower——parser 检测 `[` 后直接 `:`，
    非 parse_expr 误调）；④ **IbSlice 位置 = ':' token**（对齐 Python IbSlice 位
    置约定）；⑤ **复合算子映射**（`+=` → `+` / `-=` → `-`——复用 binop，非重复实
    现）；⑥ **元组 = 列表**（IBC 数据面元组表示 = 列表，同 List）。
  **验证**：**33/33 全语料数据面差分等价**（含 aug_assign[3,7]/tuple_basic[1,3]/
  list_slice[[2, 3],[1, 2]]）+ 全级差分 33/33 逐条等价[token/AST/反序列化/数据面
  + 符号表/类型表] + node_types = 30 节点（覆盖差 23）+ 全量 pytest 零回归（阶段④
  第二增量放行门——加法式增量不动 Python 执行路径，计数稳定 4276；见 NEXT_STEPS
  基线锚点）。**阶段④ 第二增量出口达成**（Rust 执行核心 CPS 优化——node_types
  dispatch table + 扩 3 高频节点）。
  **分支状态**：`rust-kernel` 隔离分支；阶段④ 第二增量零风险加法式（opt-in，不动
    Python 执行路径），验证后 merge unsafe-vibe-dev 并删分支；阶段④ 后续（CPS 优化
    续[覆盖差 23 节点逐步补齐] + task_scheduler GIL-free 集成）续在隔离分支（差分
    门逐级验证）；语义层 Rust 移植 = 全量 Rust 化后续。
- **P9 阶段④ 第三增量（CPS 优化续——扩 IbImportFrom[from X import Y] + 覆盖差
  可行性分析，34 语料全级差分等价，2026-09-10，隔离分支 `rust-kernel`）**：**Rust
  执行核心 CPS 优化续**——扩 IbImportFrom（from X import Y，经桥接 host_getattr 解析
  Y = X 的宿主属性 + call_host_function 调宿主函数对象），并分析覆盖差 23 节点的可
  行性（哪些 IBCI 支持/可 parse，哪些不支持/LLM 特殊），34 语料全级差分逐条等价。
  **交付**：
  - **IbImportFrom**（`from meta import quote`）：parser（From token + module 名 +
    import + Alias 列表）+ deserializer（module + names[IbAlias 数组] + level）+
    interpreter（bind Y = host_getattr(host_module X, Y)）。
  - **call_host_function**（interpreter）：调宿主函数对象（如 from meta import quote
    的 quote）——委托 Python 调用（obj.call），区别于 call_host_method[方法调用]。
  - **Call 的 Name 分支扩展**：函数为宿主对象（env 变量为 Host）→ 调宿主函数；否则
    → call_function[Rust 函数]。
  - **语料扩展**（+from_import）。
  **关键裁定（self-grill 全分支消解）**：① **IbImportFrom = from X import Y**（Y =
    X 的宿主属性，经桥接 host_getattr 解析——与 import X[绑定模块本身]互补：import
    绑模块，from-import 绑模块的属性[函数/值]）；② **call_host_function vs
    call_host_method**（前者调宿主函数对象[obj.call]，后者调宿主对象的方法
    [obj.call_method]——两面对应两种调用语义，非双通道）；③ **覆盖差可行性分析**
    （23 节点中：IBC 支持/可 parse = IbImportFrom[本增量已补]；IBC 不支持[parse
    错误] = IbGlobalStmt/IbNonlocalStmt/IbStarred/IbSwitch[IbRaise 因无 Python 内建
    异常 SEM_UNDEFINED_SYMBOL]；LLM/意图/宿主特殊面 = IbBehaviorExpr/IbAwaitExpr/
    IbChannelExpr 等——语料面低频，后续按需补齐）；④ **node_types 30→31**（覆盖差
    23→22）。
  **验证**：**34/34 全语料数据面差分等价**（含 from_import[1 + 2]）+ 全级差分
    34/34 逐条等价[token/AST/反序列化/数据面 + 符号表/类型表] + node_types = 31 节
    点[覆盖差 22] + 全量 pytest 零回归（阶段④ 第三增量放行门——加法式增量不动
    Python 执行路径，计数稳定 4276；见 NEXT_STEPS 基线锚点）。**阶段④ 第三增量出口
    达成**（Rust 执行核心 CPS 优化续——IbImportFrom + 覆盖差可行性分析）。
  **分支状态**：`rust-kernel` 隔离分支；阶段④ 第三增量零风险加法式（opt-in，不动
    Python 执行路径），验证后 merge unsafe-vibe-dev 并删分支；阶段④ 后续（CPS 优化
    续[覆盖差 22 节点——IBC 支持面按需补齐 + LLM/意图面后续] + task_scheduler GIL-
    free 集成）续在隔离分支（差分门逐级验证）；语义层 Rust 移植 = 全量 Rust 化后续。
- **P9 阶段④ 第四增量（task_scheduler GIL-free 集成——Rust 原生并行执行 API
  run_artifacts_parallel，4 线程 3.31x 真并行，2026-09-10，隔离分支
  `rust-kernel`）**：**Rust 执行核心 task_scheduler GIL-free 集成地基**——原生 Rust
  并行执行 API（std::thread，GIL-free 真并行），多 artifact 经 Rust 线程并行执行，
  结果 == 顺序执行（顺序保持）。这是 task_scheduler GIL-free 集成的地基（Rust 内核
  可并行执行 CPU 任务）。
  **交付**：
  - **run_artifacts_parallel**（`ibci-ext/src/lib.rs`）：多 artifact（JSON 列表）经
    Rust 线程（std::thread）GIL-free 真并行执行——均分 workers 批，每线程执行一批
    （纯 CPU 无宿主服务，全程 GIL 释放），按线程序拼接（chunk 按 artifact 序均分 →
    拼接 = artifact 序，顺序保持）；返回 list of list（每项 = 一个 artifact 的 print
    输出列表）。
  - **差分 harness 测试**（`test_parallel_execution_equivalence`）：并行执行 == 顺序
    执行（结果 + 顺序保持）。
  **关键裁定（self-grill 全分支消解）**：① **Rust 原生并行（std::thread）**（非
    Python 线程——Rust 线程经 py.allow_threads 释放 GIL 后各执行一批，纯 CPU GIL-
    free 真并行；区别于 bench_rust_parallel 的 Python 线程模型）；② **按线程序拼接
    = artifact 序**（chunk 按 artifact 序均分[chunk i = artifact i*per..(i+1)*per]
    → 线程序拼接 = artifact 序，顺序保持）；③ **纯 CPU 面**（无宿主服务——含宿主服务
    的 artifact 由单线程 run_artifact 经桥接处理[IO 协作式]）；④ **每线程返回
    Vec<Vec<String>>**（每 artifact 一个 print 输出列表——类型显式化，避免 collect
    目标类型歧义）；⑤ **3.31x ≈ 4x 理想**（GIL-free 真并行成立——略低于理想 = 线程
    启动/调度开销，非 GIL 竞争）。
  **验证**：**4 线程并行 3.31x**（≈4x 理想，GIL-free 真并行）+ 并行结果 == 顺序结果
    [4 artifact 顺序保持 MATCH] + 差分 harness 19/19 + smoke 832 零回归 + 全量 pytest
    零回归（阶段④ 第四增量放行门——加法式增量不动 Python 执行路径，计数 4276 + 并行
    执行测试 1 例 = 4277；见 NEXT_STEPS 基线锚点）。**阶段④ 第四增量出口达成**（Rust
    执行核心 task_scheduler GIL-free 集成地基——原生 Rust 并行执行 API）。
  **分支状态**：`rust-kernel` 隔离分支；阶段④ 第四增量零风险加法式（opt-in，不动
    Python 执行路径），验证后 merge unsafe-vibe-dev 并删分支；阶段④ 后续（task_
    scheduler GIL-free 集成续[Python task_scheduler 接入 Rust 并行执行 API] + CPS
    优化续[覆盖差 22 节点——LLM/意图面按需补齐]）续在隔离分支（差分门逐级验证）；
    语义层 Rust 移植 = 全量 Rust 化后续。
- **P9 阶段④ 第五增量（task_scheduler GIL-free 集成——CPU+IO 真并行验证：Rust
  CPU 任务 GIL-free 与 GIL-bound Python 任务真并行，并行比 1.07≈1.0，2026-09-10，
  隔离分支 `rust-kernel`）**：**Phase ④ 核心能力验证**——CPU+IO GIL-free 真并行（
  task_scheduler IO-only → CPU+IO GIL-free 目标）。验证 Rust 执行核心的 CPU 工作
  （GIL-free，经 py.allow_threads/run_artifacts_parallel 释放 GIL）可与 GIL-bound
  的 Python 任务**真并行**（墙钟 ≈ max[CPU, IO]，非 sum[串行]）——task_scheduler 可
  调度 CPU+IO 真并行（GIL-free）的地基。
  **交付**：
  - **CPU+IO 真并行验证**（`scripts/bench_rust_cpu_io.py`，常设基准）：线程 A =
    GIL-bound Python 任务[纯 Python CPU 计算，持 GIL，T_io]；线程 B = GIL-free Rust
    执行核心[run_artifacts_parallel，释放 GIL，T_cpu]；两线程并行测墙钟 T_wall——
    **GIL-free 真并行 = T_wall ≈ max(T_io, T_cpu)**[非 T_io + T_cpu 串行]。
  **关键裁定（self-grill 全分支消解）**：① **CPU+IO 真并行模型**（Rust CPU 工作
    GIL-free[释放 GIL] + Python IO/CPU 工作 GIL-bound[持 GIL]——两者真并行，墙钟
    ≈ max 非 sum；这是 Phase ④ 的核心目标[task_scheduler IO-only → CPU+IO GIL-
    free]）；② **GIL-bound Python 任务 = 纯 Python CPU 计算**（持 GIL——对照组：
    若 Rust 也持 GIL，两者串行[墙钟 ≈ sum]）；③ **并行比 T_wall/max**（≈1.0 = 真
    并行；≈(T_io+T_cpu)/max = 串行——本验证 1.07 ≈ 1.0 真并行成立）；④ **timing
    验证非常设测试**（CPU+IO 并行是 timing 属性，非确定性断言——归常设基准[bench_
    rust_cpu_io.py]，不入 pytest[避免 flaky]）；⑤ **task_scheduler 接入后续**
    （本增量验证核心能力；Python task_scheduler 实际接入 Rust 并行执行 API 归后续
    增量）。
  **验证**：**CPU+IO GIL-free 真并行并行比 1.07 ≈ 1.0**（T_io=0.045s GIL-bound +
    T_cpu=0.013s GIL-free → T_wall=0.048s ≈ max[0.045s]，非 sum[0.058s]）+ 差分
    harness 19/19 + 全量 pytest 零回归（阶段④ 第五增量放行门——仅加常设基准脚本，
    不动 Rust/测试代码，计数稳定 4277；见 NEXT_STEPS 基线锚点）。**阶段④ 第五增量
    出口达成**（Phase ④ 核心能力验证——CPU+IO GIL-free 真并行成立）。
  **分支状态**：`rust-kernel` 隔离分支；阶段④ 第五增量零风险加法式（仅常设基准脚本，
    不动 Rust/测试代码），验证后 merge unsafe-vibe-dev 并删分支；阶段④ 后续（task_
    scheduler GIL-free 集成续[Python task_scheduler 实际接入 Rust 并行执行 API——
    submit CPU 任务经 run_artifacts_parallel 并行] + CPS 优化续[覆盖差 22 节点——
    LLM/意图面按需补齐]）续在隔离分支（差分门逐级验证）；语义层 Rust 移植 = 全量
    Rust 化后续。
- **P9 阶段④ 第六增量（task_scheduler GIL-free 集成——Rust 有状态任务池 TaskPool：
  submit/run_all GIL-free 并行，4 线程 3.37x，2026-09-10，隔离分支
  `rust-kernel`）**：**Rust 执行核心 task_scheduler GIL-free 集成的有状态执行体**——
  有状态任务池（pyclass TaskPool）：CPU 任务（artifact）经 submit 增量入队、run_all
  经 Rust 线程 GIL-free 真并行执行、按任务 ID 取结果。这是 task_scheduler 增量 submit
  CPU 任务 + 一次性并行执行 + 按 ID 取结果的集成点（区别于 run_artifacts_parallel 的
  无状态批处理 API）。
  **交付**：
  - **TaskPool**（`ibci-ext/src/task_pool.rs`，pyclass）：有状态任务池——`__new__(
    workers)`[创建池] + `submit(artifact_json) -> task_id`[入队，返回任务 ID] +
    `pending() -> usize`[入队任务数] + `run_all() -> list of [task_id, result_list]`
    [取出全部任务，Rust 线程 GIL-free 真并行执行，按任务 ID 序返回]。
  - **pyo3 暴露**：`ibci_ext.TaskPool`（pyclass，m.add_class）。
  - **差分 harness 测试**（`test_task_pool_equivalence`）：TaskPool run_all（按任务
    ID 序）== 顺序执行（run_artifact），空池 run_all = 空列表。
  **关键裁定（self-grill 全分支消解）**：① **有状态任务池（pyclass）**（task_
    scheduler 可增量 submit CPU 任务[submit 入队]、一次性 run_all 并行执行、按任务
    ID 取结果——区别于 run_artifacts_parallel 的无状态批处理 API[一次性传入全部
    artifact]；两 API 互补：批处理 = 简单场景，任务池 = 增量 submit 场景）；② **按
    任务 ID 序返回**（chunk 按任务序均分 → 线程序拼接 = 任务序；结果 = list of
    [task_id, result_list]，调用方按 ID 匹配）；③ **纯 CPU 面**（无宿主服务——含宿主
    服务的任务由单线程 run_artifact 经桥接处理[IO 协作式]）；④ **Mutex 任务队列 +
    AtomicU64 任务 ID**（submit 线程安全[多任务增量入队]，run_all 取出全部[drain]）；
    ⑤ **空池 run_all = 空列表**（无任务 = 无操作，非报错）。
  **验证**：TaskPool 4 线程 3.37x 真并行[≈4x 理想] + run_all（按任务 ID 序）== 顺序
    执行[MATCH] + 空池 run_all = [] + 差分 harness 20/20 + 全量 pytest 零回归（阶段④
    第六增量放行门——加法式增量不动 Python 执行路径，计数 = 4277 + TaskPool 测试 1 例
    = 4278；见 NEXT_STEPS 基线锚点）。**阶段④ 第六增量出口达成**（Rust 执行核心
    task_scheduler GIL-free 集成的有状态执行体——TaskPool）。
  **分支状态**：`rust-kernel` 隔离分支；阶段④ 第六增量零风险加法式（opt-in，不动
    Python 执行路径），验证后 merge unsafe-vibe-dev 并删分支；阶段④ 后续（task_
    scheduler GIL-free 集成续[Python task_scheduler 接入 TaskPool[submit CPU 任务] +
    CPS 优化续[覆盖差 22 节点——LLM/意图面按需补齐]）续在隔离分支（差分门逐级验证）；
    语义层 Rust 移植 = 全量 Rust 化后续。
- **P9 阶段④ 第七增量（task_scheduler GIL-free 集成续——Python task_scheduler 接入
  TaskPool：CPU+IO 并发验证，并发比 1.05≈1.0，2026-09-10，隔离分支
  `rust-kernel`）**：**Phase ④ CPU+IO GIL-free 集成落地验证**——实际 Python
  task_scheduler（TaskScheduler，协作式调度 IO 任务，持 GIL）与 Rust TaskPool（GIL-free
  真并行执行 CPU 任务）协同工作——IO 任务经 task_scheduler 协作式推进（持 GIL），CPU
  任务经 TaskPool GIL-free 真并行（释放 GIL），两者并发（墙钟 ≈ max[IO, CPU]，非
  sum[串行]）。这是 task_scheduler 接入 TaskPool 的集成验证（Phase ④ 目标：task_
  scheduler IO-only → CPU+IO GIL-free）。
  **交付**：
  - **task_scheduler 集成验证**（`scripts/bench_task_scheduler_integration.py`，常设
    基准）：线程 A = 实际 TaskScheduler.run() 推进 IO 任务[生成器，协作式，持 GIL，
    T_io]；主线程 = Rust TaskPool.run_all() 并行执行 CPU 任务[释放 GIL，T_cpu]；两者
    并发测墙钟 T_wall——**GIL-free 真并行集成 = T_wall ≈ max(T_io, T_cpu)**[非 T_io +
    T_cpu 串行]。
  **关键裁定（self-grill 全分支消解）**：① **实际 TaskScheduler + TaskPool 协同**
    （非简化模型——用实际的 Python task_scheduler[TaskScheduler.run() 协作式推进 IO
    任务] + 实际的 Rust TaskPool[run_all GIL-free 并行 CPU 任务]，验证真实集成）；
    ② **IO 任务 = 生成器**（task_scheduler 契约：yield 挂起 / return 完成——本演示的
    IO 任务为 CPU 密集[持 GIL，无实际 IO]，经 yield from iter(()) 成为生成器[无 yield
    挂起，一步完成]）；③ **并发比 T_wall/T_io ≈ 1.0**（IO 主导，CPU 任务并行叠加，不
    串行阻塞 IO——若 TaskPool 持 GIL，T_wall ≈ T_io + T_cpu[串行]）；④ **timing 验证
    非常设测试**（CPU+IO 集成是 timing 属性，归常设基准，不入 pytest 避免 flaky）；
    ⑤ **task_scheduler 本身不改**（本增量验证集成能力[TaskScheduler + TaskPool 并发]；
    task_scheduler 内部接入 TaskPool[submit CPU 任务]归后续增量[需 task_scheduler 支
    持 CPU 任务类型]）。
  **验证**：**task_scheduler GIL-free 集成并发比 1.05 ≈ 1.0**（T_io=0.045s[TaskScheduler
    协作式持 GIL] + CPU 任务×4[TaskPool GIL-free 并行] → T_wall=0.047s ≈ max[0.045s]，
    非 sum）+ 差分 harness 20/20 + 全量 pytest 零回归（阶段④ 第七增量放行门——仅加常
    设基准脚本，不动 Rust/测试代码，计数稳定 4278；见 NEXT_STEPS 基线锚点）。**阶段④
    第七增量出口达成**（Phase ④ CPU+IO GIL-free 集成落地验证——实际 TaskScheduler +
    TaskPool 并发）。
  **分支状态**：`rust-kernel` 隔离分支；阶段④ 第七增量零风险加法式（仅常设基准脚本，
    不动 Rust/测试代码），验证后 merge unsafe-vibe-dev 并删分支；阶段④ 后续（task_
    scheduler GIL-free 集成续[task_scheduler 内部接入 TaskPool——支持 CPU 任务类型，
    submit CPU 任务经 TaskPool 并行] + CPS 优化续[覆盖差 22 节点——LLM/意图面按需补
    齐]）续在隔离分支（差分门逐级验证）；语义层 Rust 移植 = 全量 Rust 化后续。
- **P9 阶段④ 第八增量（task_scheduler GIL-free 集成续——task_scheduler 内部接入
  TaskPool：异步 CPU 任务 waitable，并发比 1.04≈1.0，2026-09-10，隔离分支
  `rust-kernel`）**：**Phase ④ CPU+IO GIL-free 集成（task_scheduler 内部接入）落地
  验证**——task_scheduler 可调度**异步 CPU 任务**（CPU 工作经 TaskPool 在后台线程
  GIL-free 真并行执行）——CPU 任务 waitable 符合 task_scheduler 的 waitable 协议
  （is_done / 非阻塞 try_result / register_wake）；task_scheduler 推进 IO 任务（持
  GIL）时，CPU 任务在后台线程 GIL-free 真并行（墙钟 ≈ max[IO, CPU]，非 sum[串行]）。
  这是 task_scheduler 内部接入 TaskPool 的集成验证（Phase ④ 目标：task_scheduler
  支持 CPU 任务类型）。
  **交付**：
  - **异步 CPU 任务 waitable 集成验证**（`scripts/bench_task_scheduler_cpu_task.py`，
    常设基准）：CPUTaskWaitable（Python 侧 waitable，CPU 工作经 TaskPool 在后台线程
    GIL-free 真并行执行，符合 task_scheduler 的 waitable 协议：is_done[非阻塞查询
    完成] / try_result[非阻塞取结果，未完成 = (False, None) 继续等待] / register_
    wake[完成时设事件] / result[阻塞取结果，宿主/线程体兜底]）；CPU 任务（生成器，
    task_scheduler 契约）yield 该 waitable，完成后取结果；task_scheduler 按提交序
    推进——CPU 任务先提交[后台线程先启动] + IO 任务后跑[持 GIL T_io]——期间 CPU 后台
    线程 GIL-free 真并行。
  **关键裁定（self-grill 全分支消解）**：① **异步 CPU 任务 waitable 协议**（符合
    task_scheduler 契约：is_done 非阻塞查询完成 / try_result 非阻塞取结果[未完成 =
    (False, None) 继续等待，区别于 BaseCPSDrive 的阻塞 try_result[宿主/线程体兜底]]
    / register_wake 完成时设事件[唤醒全等待 park] / result 阻塞取结果[宿主/线程体同
    步兜底]）；② **CPU 工作经 TaskPool 在后台线程 GIL-free 真并行**（后台线程调
    pool.run_all()[释放 GIL，Rust 线程各执行一批纯 CPU]——task_scheduler 推进 IO 任务
    [持 GIL] 时，CPU 后台线程 GIL-free 真并行）；③ **每 waitable 独立 TaskPool**
    （避免共享池 run_all 竞争[run_all drain 全部已 submit 任务]）；④ **提交序 =
    并行序**（task_scheduler 按提交序推进 ready 任务——CPU 任务先提交[后台线程先启动]
    + IO 任务后跑[持 GIL]——期间 CPU 后台 GIL-free 真并行；若 IO 任务先提交[先跑完
    T_io]，CPU 后台线程才启动 = 串行[并发比 ≈ (T_io+T_cpu)/T_io]）；⑤ **timing 验证
    非常设测试**（CPU 任务并行是 timing 属性，归常设基准，不入 pytest 避免 flaky）；
    ⑥ **task_scheduler 本身不改**（本增量验证 task_scheduler 内部接入能力[调度异步
    CPU 任务 waitable]；CPUTaskWaitable 为 Python 侧集成点[依赖 Rust 内核 TaskPool，
    opt-in]，非生产模块——归全量 Rust 化后续）。
  **验证**：**task_scheduler 内部接入（异步 CPU 任务 waitable）并发比 1.04 ≈ 1.0**
    （CPU 任务先提交[后台线程先启动] + IO 任务后跑[持 GIL T_io=0.043s] → T_wall=
    0.045s ≈ max[T_io, T_cpu]，非 sum[T_io + T_cpu]）+ 差分 harness 20/20 + 全量
    pytest 零回归（阶段④ 第八增量放行门——仅加常设基准脚本，不动 Rust/测试代码，计数
    稳定 4278；见 NEXT_STEPS 基线锚点）。**阶段④ 第八增量出口达成**（Phase ④ CPU+IO
    GIL-free 集成[task_scheduler 内部接入]落地验证——异步 CPU 任务 waitable）。
  **分支状态**：`rust-kernel` 隔离分支；阶段④ 第八增量零风险加法式（仅常设基准脚本，
    不动 Rust/测试代码），验证后 merge unsafe-vibe-dev 并删分支；阶段④ 后续（task_
    scheduler GIL-free 集成收束[CPUTaskWaitable 归全量 Rust 化——task_scheduler 原生
    CPU 任务类型] + CPS 优化续[覆盖差 22 节点——LLM/意图面按需补齐]）续在隔离分支
    （差分门逐级验证）；语义层 Rust 移植 = 全量 Rust 化后续。
- **P9 阶段④ 收束（task_scheduler GIL-free 集成完成——kernel_info 升级 stage 4 /
  concurrency-core，2026-09-10，隔离分支 `rust-kernel`）**：**阶段④ 并发解除收束**——
  task_scheduler GIL-free 集成全部 Rust 侧验证完成（GIL-free 并行执行地基 + Rust 原生
  并行执行 API + CPU+IO 真并行验证 + 有状态任务池 TaskPool + task_scheduler 接入验证
  + task_scheduler 内部接入[异步 CPU 任务 waitable]），kernel_info 升级 stage 3 → 4
  （status "execution-core" → "concurrency-core"）——阶段④ 收束（并发核心就绪）。
  **交付**：
  - **kernel_info 升级**（`ibci-ext/src/lib.rs`）：stage 3 → 4（并发解除[GIL-free 并行
    执行 + 任务池]）；status "execution-core" → "concurrency-core"（并发核心就绪：GIL-
    free 并行执行[run_artifacts_parallel + TaskPool] + 数据面经 run_artifact 可用）。
  - **模块 //! doc 更新**：当前形态加并发解除（GIL-free 并行执行：run_artifacts_
    parallel 无状态批处理 + TaskPool 有状态任务池，Rust 线程 py.allow_threads 释放 GIL
    真并行）；语料 30 → 34 全级差分等价；GIL-free 并行 4 线程 ≈3.3x；kernel_info.stage
    = 4 / status = "concurrency-core"。
  **关键裁定（self-grill 全分支消解）**：① **阶段④ 收束 = Rust 侧验证全部完成**（GIL-
    free 并行执行地基[py.allow_threads] + Rust 原生并行执行 API[run_artifacts_parallel]
    + CPU+IO 真并行验证[bench_rust_cpu_io] + 有状态任务池[TaskPool] + task_scheduler
    接入验证[bench_task_scheduler_integration] + task_scheduler 内部接入[异步 CPU 任务
    waitable，bench_task_scheduler_cpu_task]——全部 Rust 侧 GIL-free 并行执行能力验证
    完成，阶段④ 并发解除收束）；② **kernel_info stage 3 → 4 / status "execution-core"
    → "concurrency-core"**（阶段④ 收束 = 并发核心就绪；"ready" 仍保留[全量内核就绪，
    待 Rust 前端[语义层]移植后 run script 入口生效]——双内核协议不变）；③ **standing
    gate 行为不变**（kernel_info.status != "ready" → ready=False → 仅 Python 确定性；
    Rust 并发核心经 run_artifact/run_artifacts_parallel/TaskPool 单独验证——差分 harness
    不变）；④ **CPUTaskWaitable 归全量 Rust 化**（Python 侧集成点[依赖 Rust 内核
    TaskPool，opt-in]，非生产模块——task_scheduler 原生 CPU 任务类型归全量 Rust 化后续）；
    ⑤ **零风险加法式**（kernel_info 升级不动 Python 执行路径，计数稳定）。
  **验证**：kernel_info = {stage:4, status:"concurrency-core"} + node_types 31 + run_
    artifacts_parallel/TaskPool 全在 + 差分 harness 20/20 + 全量 pytest 零回归（阶段④
    收束放行门——加法式增量不动 Python 执行路径，计数稳定 4278；见 NEXT_STEPS 基线锚
    点）。**阶段④ 收束出口达成**（并发解除完成——kernel_info stage 4 / concurrency-core）。
  **分支状态**：`rust-kernel` 隔离分支；阶段④ 收束零风险加法式（kernel_info 升级，不动
    Python 执行路径），验证后 merge unsafe-vibe-dev 并删分支。**阶段④ 并发解除全部完
    成**（GIL-free 并行执行 + task_scheduler GIL-free 集成 + kernel_info stage 4 /
    concurrency-core）；P9 Rust 部分（阶段②③④）完成 = 全量 Rust 化评估前置就绪；后续
    = 全量 Rust 化评估[用户 2026-09-10 裁定：Rust 部分完成后开启新评估 + 新自主执行模
    式，评估全核心逻辑全量 Rust 化——编译/语义/执行/调度/并发，保留关键 Python 接口] +
    CPS 优化续[覆盖差 22 节点——LLM/意图面按需补齐]。
- **P9 全量 Rust 化评估开启（核心逻辑面盘点 + Rust 化覆盖分析 + 可行性评估 + 关键
  Python 接口识别，2026-09-10，隔离分支 `rust-kernel`）**：**P9 Rust 部分（阶段②③④）
  完成后的全量 Rust 化评估前置**——按用户 2026-09-10 裁定，开启新评估 + 新自主执行模
  式，评估全核心逻辑全量 Rust 化（编译/语义/执行/调度/并发/值对象/宿主服务），保留关
  键 Python 接口，证明绝大部分关键核心逻辑可 Rust 化后全量转向 Rust。
  **交付**：
  - **全量 Rust 化评估文档**（`tasks_docs/_full_rustification_evaluation.md`）：核心
    逻辑面盘点[规模 + 当前 Rust 化状态] + Rust 化覆盖分析[已证明 vs 剩余] + 可行性评
    估[逐面] + 关键 Python 接口识别[保留供 Python 使用的入口能力] + 全量 Rust 化执行
    计划[阶段 A[已证明] + 阶段 B[可 Rust 化，纯计算] + 阶段 C[保留 Python，LLM/意图/宿
    主面]]。
  **核心逻辑面盘点（规模 + 当前 Rust 化状态）**：编译·lexer[1238 行，✅ 已 Rust 化] +
    编译·parser[3267 行，✅ 已 Rust 化] + 编译·semantic[8317 行，⏸ 推迟，最大面] + 序列
    化[FlatSerializer 329 行，⏸ 未 Rust 化] + 执行·VM[CPS 执行核心 4404 行 + interpreter
    6589 行 ≈ 11000 行，🟡 部分 Rust 化[Rust 执行核心 = tree-walking 解释器，数据面 34/34
    全级差分等价，23–30x]] + 调度·task_scheduler[229 行，🟡 GIL-free 集成已验证] + 并发
    [横切，✅ 已 Rust 化[GIL-free 并行执行 + TaskPool]] + 值对象[core/runtime/objects
    8902 行，⏸ 未 Rust 化] + 宿主服务[core/runtime/host 670 行，⏸ 未 Rust 化]。
  **关键裁定（self-grill 全分支消解）**：① **确定性代码路径[编译 + 执行 + 并发]已 Rust
    化**（绝大部分关键核心逻辑[确定性代码]可 Rust 化，已证明[34 语料全级差分等价]）；
    ② **语义层 + 序列化 + 值对象 = 可 Rust 化[纯计算]**（语义层[8317 行，最大工作量] +
    序列化[FlatSerializer 329 行] + 值对象[8902 行]是纯计算面，Rust 化可行[lexer/parser
    已证 Rust 前端可行，IbValue 已证 Rust 值类型可行]）；③ **宿主服务 + CPS VM[LLM/意
    图/宿主面] = 保留 Python**（涉及 LLM IO + 宿主集成[非纯计算]，保留 Python 接口[用户
    裁定：保留关键部分 Python 接口]）；④ **关键 Python 接口 = 入口能力[run_ibci/compile_
    ibci + Rust 内核 pyo3 入口[run_artifact/TaskPool]] + LLM/意图/宿主面[HostService +
    CPS VM + 值对象]**（供 Python 使用的入口 + 非纯计算面保留 Python）；⑤ **全量 Rust
    化 = 阶段 B[语义 + 序列化 + 值对象]Rust 化 + 差分验证，之后全量转向 Rust**（不保留
    Python 双通道和对比；LLM/意图/宿主面保留 Python 接口）。
  **可行性结论**：**绝大部分关键核心逻辑[确定性代码路径：编译 + 执行 + 并发 + 语义 + 序
    列化 + 值对象]可 Rust 化**（已证明 + 可证明）；**LLM/意图/宿主面保留 Python 接口**
    （非纯计算）。**全量 Rust 化评估开启**（下一步 = 阶段 B 启动[语义层 Rust 移植[最大
    面] 或序列化[FlatSerializer，规模小，先启动] 或值对象[IbValue 扩展]] + 差分 harness
    扩语料[语义/序列化/值对象面] + 保留 Python 接口[HostService + CPS VM]）。
  **分支状态**：`rust-kernel` 隔离分支；全量 Rust 化评估零风险加法式（仅评估文档，不动
    Rust/测试代码），验证后 merge unsafe-vibe-dev 并删分支；后续 = 阶段 B 启动[全量 Rust
    化：语义 + 序列化 + 值对象 Rust 化 + 差分验证] + 保留 Python 接口[HostService + CPS
    VM[LLM/意图/宿主面]]。
- **P9 全量 Rust 化阶段 B 第一增量（序列化 Rust 化——Rust UID 生成 node_uid/type_uid/
  asset_uid，34 语料节点池差分等价，2026-09-10，隔离分支 `rust-kernel`）**：**阶段 B
  启动（可 Rust 化，纯计算：序列化面）**——Rust UID 生成（node_uid/type_uid/asset_uid，
  对应 Python core/base/uid.py）——FlatSerializer 的节点/类型/资产 UID 生成核心 Rust 化，
  与 Python UID 逐条差分等价（确定性哈希 = sha256 前 16 hex；稳定 UID = 命名规则）。
  **交付**：
  - **serialization 模块**（`ibci-ext/src/serialization.rs`）：node_uid[content →
    `node_<sha256[:16]>`，内容确定性] + type_uid[module_path + name → `type_<module>.<name>`
    [root 模块退化 `type_root.<name>`]] + asset_uid[text → `asset_<sha256[:16]>`，内容确定
    性]（sha2 crate，sha256 哈希）。
  - **Cargo.toml**：加 sha2 0.10 依赖（sha256 哈希）。
  - **pyo3 暴露**：`ibci_ext.node_uid/type_uid/asset_uid`（pyfunctions）。
  - **差分 harness 测试**（TestRustSerializationUid）：test_node_uid_corpus_node_pool[34
    语料节点池：Rust node_uid[json.dumps(node_data, sort_keys=True)] == Python uid[节点池
    键]] + test_type_uid_and_asset_uid[type_uid/asset_uid Rust == Python]。
  **关键裁定（self-grill 全分支消解）**：① **确定性哈希 = sha256 前 16 hex**（node_uid =
    `node_<sha256[:16]>`，asset_uid = `asset_<sha256[:16]>`——与 Python hashlib.sha256
    .hexdigest()[:16] 逐条等价；sha2 crate[sha256]）；② **稳定 UID = 命名规则**（type_uid
    = `type_<module>.<name>`[root 模块退化 `type_root.<name>`]——与 Python type_uid 等价）；
    ③ **节点池差分 = json.dumps(node_data, sort_keys=True)**（Python _collect_node 用
    json.dumps(node_data, sort_keys=True) 生成内容串 → node_uid；Rust node_uid 消费同一
    内容串 → 逐条等价[34 语料节点池]）；④ **type_uid 参数序适配 pyo3**（name 必需在前 +
    module_path Option 在后——pyo3 禁 Option 后跟必需参数；Python type_uid(module_path,
    name) 经差分 harness 按此序调用）；⑤ **序列化面 = UID 生成核心先 Rust 化**（FlatSerializer
    的节点/类型/资产 UID 生成 = 序列化核心；节点数据序列化[node_data dict] + 符号/类型/
    scope 收集归后续增量——先证 UID 生成核心 Rust 可行）；⑥ **零风险加法式**（UID 生成为
    独立 pyfunction，不动 Python 执行路径/FlatSerializer，计数 +2 测试）。
  **验证**：34 语料节点池 Rust node_uid == Python uid[逐条差分等价] + type_uid/asset_uid
    Rust == Python + 差分 harness 22/22 + 全量 pytest 零回归（阶段 B 第一增量放行门——
    加法式增量不动 Python 执行路径，计数 = 4278 + 序列化 UID 测试 2 例 = 4280；见
    NEXT_STEPS 基线锚点）。**阶段 B 第一增量出口达成**（序列化 Rust 化——Rust UID 生成
    node_uid/type_uid/asset_uid）。
  **分支状态**：`rust-kernel` 隔离分支；阶段 B 第一增量零风险加法式（UID 生成为独立
    pyfunction，不动 Python 执行路径），验证后 merge unsafe-vibe-dev 并删分支；阶段 B 后续
    （序列化 Rust 化续[节点数据序列化[node_data dict] + 符号/类型/scope 收集] + 语义层
    Rust 移植[最大面 8317 行] + 值对象[IbValue 扩展 8902 行]）续在隔离分支（差分门逐级
    验证）；保留 Python 接口[HostService + CPS VM[LLM/意图/宿主面]]。
- **P9 全量 Rust 化阶段 B 第二增量（序列化 Rust 化续——节点数据序列化 node_data dict，
  34 语料节点池差分等价，2026-09-10，隔离分支 `rust-kernel`）**：**阶段 B 续（序列化
  面：节点数据序列化）**——Rust 节点数据序列化（Rust AST → node_data dict，对应 Python
  FlatSerializer._collect_node）——AST 节点 → node_data dict（_type + 基类位置字段 +
  节点字段 + 节点引用[UID]）→ content_str[自定义 JSON 序列化，匹配 Python json.dumps
  sort_keys] → node_uid → 节点池[uid → node_data]。与 Python 节点池逐条差分等价（34
  语料，节点内容 829/835 匹配，剩余 6 因 free_vars[语义层输出，Rust parser 未承载]）。
  **交付**：
  - **node_serializer 模块**（`ibci-ext/src/node_serializer.rs`）：NodeSerializer[Rust
    AST → 节点池]——serialize_module[根节点] + serialize_stmt[14 语句] + serialize_expr
    [16 表达式] + serialize_arg[IbArg] + serialize_alias[IbAlias]；node_data dict[_type
    + 基类位置字段[lineno/col_offset/end_lineno/end_col_offset] + 节点字段 + 节点引用
    [UID]]；content_str 自定义 JSON 序列化[匹配 Python json.dumps[sort_keys=True]：键
    字母序 + `": "` 分隔 + `", "` 对间分隔 + 非 ASCII → \uXXXX[ensure_ascii]] → node_uid
    → 节点池。
  - **parser.rs**：加 parse_to_module[source → Rust AST Module]（供节点数据序列化消费）。
  - **pyo3 暴露**：`ibci_ext.serialize_nodes(source) -> (root_uid, node_pool_json)`。
  - **差分 harness 测试**（TestRustSerializationUid::test_node_pool_corpus）：34 语料节
    点池差分（Rust 节点池 == Python 节点池，节点内容集合等价；排除 free_vars[语义层
    输出] + 规范化节点引用 UID[node_... → <UID>]）。
  **关键裁定（self-grill 全分支消解）**：① **content_str 自定义 JSON 序列化**（匹配
    Python json.dumps[sort_keys=True]：键字母序 + `": "` 分隔 + `", "` 对间分隔 + 值格式
    [string 带引号 JSON 转义 + 非 ASCII → \uXXXX[ensure_ascii] / int 原样 / float[整值
    = 4.0] / null / list[", " 分隔]]——serde_json::to_string 用 `","`/`":"` 无空格，不匹
    配，故自定义序列化器）；② **节点引用 = UID**（node_data 的节点引用字段[targets/
    value/body/elts/...] = 子节点 UID[递归序列化]——与 Python _process_value[IbASTNode
    → _collect_node → UID] 对齐）；③ **缺失字段对齐 Python**（IbCall.keywords=[] /
    IbFunctionDef.type_params=[]+type_param_uids=[]+type_param_bounds={}-free_vars=[]-
    is_generator=False / IbIf·For·While·ExprStmt·Assign.llmexcept_handler=null /
    IbImportFrom.level=0[Rust parser 未承载，对齐默认值] / IbList→IbListExpr[Python 类
    名] / IbFunctionDef.returns[-> int 类型标注，Rust parser 已产生]）；④ **free_vars =
    语义层输出**（非序列化面——Rust parser 未承载[闭包捕获]，比对时排除[其值差异改变
    content_str → UID]；归语义层 Rust 移植后续）；⑤ **ClassDef/Try = 占位**（语料面不
    含；Rust/Python 结构差异[fields/methods vs parent/parent_args]归后续）；⑥ **零风险
    加法式**（serialize_nodes 为独立 pyfunction，不动 Python 执行路径/FlatSerializer）。
  **验证**：34 语料节点池节点内容 829/835 匹配[剩余 6 因 free_vars 语义层输出] + 差分
    harness 23/23 + 全量 pytest 零回归（阶段 B 第二增量放行门——加法式增量不动 Python
    执行路径，计数 = 4280 + 节点池差分测试 1 例 = 4281；见 NEXT_STEPS 基线锚点）。**阶
    段 B 第二增量出口达成**（序列化 Rust 化续——节点数据序列化 node_data dict）。
  **分支状态**：`rust-kernel` 隔离分支；阶段 B 第二增量零风险加法式（serialize_nodes
    为独立 pyfunction，不动 Python 执行路径），验证后 merge unsafe-vibe-dev 并删分支；
    阶段 B 后续（序列化 Rust 化续[符号/类型/scope 收集 + 完整 artifact 组装] + 语义层
    Rust 移植[最大面 8317 行，含 free_vars 闭包捕获] + 值对象[IbValue 扩展 8902 行]）
    续在隔离分支（差分门逐级验证）；保留 Python 接口[HostService + CPS VM[LLM/意图/
    宿主面]]。
- **P9 全量 Rust 化阶段 B 第三增量（语义层 Rust 移植启动——scope 符号解析，34 语料
  scope 符号 52/52 全 MATCH，2026-09-10，隔离分支 `rust-kernel`）**：**阶段 B 续（语
  义层：scope 符号解析启动）**——Rust scope 符号解析（对应 Python 语义层的 scope 符号
  解析：遍历 Rust AST，将用户定义的名字绑定到 scope 符号 `scope_<scope>:<name>`）。
  scope 符号 = 用户定义符号（区别于 intrinsic 符号[内置类型/方法，语义层 intrinsic
  符号表产出]）。与 Python scope 符号逐条差分等价（34 语料，52/52 全 MATCH）。
  **交付**：
  - **symbol_resolver 模块**（`ibci-ext/src/symbol_resolver.rs`）：SymbolResolver[Rust
    AST → scope 符号池]——resolve_module[遍历 Module.body] + resolve_stmt[语句分发：
    Assign/AugAssign 目标 → VARIABLE / FunctionDef 名 → 顶层 FUNCTION·嵌套 VARIABLE +
    参数 → VARIABLE + scope 栈 push/pop / ClassDef 名 → CLASS / For 目标 → VARIABLE /
    Import 模块 → MODULE / FromImport 绑定 → FUNCTION]；scope 栈[module → function
    ...]，scope 符号 UID = `scope_<scope_stack 串>:<name>`。
  - **pyo3 暴露**：`ibci_ext.resolve_symbols(source) -> symbol_pool_json`。
  - **差分 harness 测试**（TestRustSerializationUid::test_scope_symbols_corpus）：34
    语料 scope 符号差分（Rust scope 符号 == Python scope 符号，name + kind 逐条等价）。
  **关键裁定（self-grill 全分支消解）**：① **scope 符号 = 用户定义符号**（区别于
    intrinsic 符号[内置类型/方法，语义层 intrinsic 符号表产出]——归语义层 Rust 移植后
    续；本增量 = 用户定义符号[赋值目标/函数名/for 循环变量/import 模块/from-import
    绑定/嵌套函数]）；② **scope 栈**（module scope → function scope ...，scope 符号
    UID = `scope_<scope_stack 串>:<name>`——顶层 = `scope___string_exec__:x`，函数内 =
    `scope___string_exec__/f:a`）；③ **顶层函数 = FUNCTION，嵌套函数 = VARIABLE**
    （Python 语义层：嵌套函数名是持有函数的变量[非顶层函数定义]——scope_stack.len()==
    1 时 FUNCTION，否则 VARIABLE）；④ **for 循环目标 = VARIABLE**（for 循环变量绑定到
    当前 scope）；⑤ **import 模块 = MODULE，from-import 绑定 = FUNCTION**（import X
    绑定 X 模块[MODULE]，from X import Y 绑定 Y[模块属性，FUNCTION]）；⑥ **type_uid/
    node_uid = null**（Rust scope 符号解析不产 type_uid/node_uid[类型解析/节点绑定归语
    义层后续]——比对 name + kind）；⑦ **零风险加法式**（resolve_symbols 为独立
    pyfunction，不动 Python 执行路径/语义层）。
  **验证**：34 语料 scope 符号 52/52 全 MATCH[顶层函数/嵌套函数/for 变量/import 模块/
    from-import 绑定] + 差分 harness 24/24 + 全量 pytest 零回归（阶段 B 第三增量放行
    门——加法式增量不动 Python 执行路径，计数 = 4281 + scope 符号差分测试 1 例 = 4282；
    见 NEXT_STEPS 基线锚点）。**阶段 B 第三增量出口达成**（语义层 Rust 移植启动——
    scope 符号解析）。
  **分支状态**：`rust-kernel` 隔离分支；阶段 B 第三增量零风险加法式（resolve_symbols
    为独立 pyfunction，不动 Python 执行路径），验证后 merge unsafe-vibe-dev 并删分支；
    阶段 B 后续（语义层 Rust 移植续[类型解析[type_uid] + 节点绑定[node_uid] + intrinsic
    符号表 + free_vars 闭包捕获 + scope 完整收集] + 序列化续[符号/类型/scope 收集 + 完
    整 artifact 组装] + 值对象[IbValue 扩展 8902 行]）续在隔离分支（差分门逐级验证）；
    保留 Python 接口[HostService + CPS VM[LLM/意图/宿主面]]。
- **P9 全量 Rust 化阶段 B 第四增量（intrinsic 符号表——42 内置类型，全字段 42/42 匹配，
  2026-09-10，隔离分支 `rust-kernel`）**：**阶段 B 续（语义层：intrinsic 符号表启动）**
  ——Rust intrinsic 符号表中的内置类型（CLASS 符号）。IBC 语言有固定 42 个内置类型
  （int/float/str/bool/void/any/list/dict/tuple/... 等）。每个内置类型的 intrinsic 符
  号：uid = `intrinsic:<name>`，kind = CLASS，type_uid = `type_root.<name>`，
  node_uid/owned_scope_uid = null，metadata = {}。与 Python intrinsic 符号表内置类型
  逐条差分等价（42/42 全字段匹配）。**交付**：
  - **intrinsic_symbols 模块**（`ibci-ext/src/intrinsic_symbols.rs`）：`BUILTIN_TYPES`
    [42 内置类型固定集] + `builtin_type_symbols()`[→ 42 CLASS 符号 BTreeMap]。
  - **pyo3 暴露**：`ibci_ext.intrinsic_type_symbols() -> intrinsic_symbol_pool_json`。
  - **差分 harness 测试**（TestRustSerializationUid::test_intrinsic_type_symbols_corpus）：
    42 内置类型 CLASS 符号差分（uid/name/kind/type_uid/node_uid/owned_scope_uid/
    metadata 全字段等价）。
  **关键裁定（self-grill 全分支消解）**：① **42 内置类型 = 固定集**（与 Python 语义层
    intrinsic 符号表对齐；type_uid 全为 `type_root.<name>`[已核]，node_uid/owned_
    scope_uid = null，metadata = {}[已核]——可硬编码）；② **只移植 CLASS 类型**（内置
    函数[19 FUNCTION]/方法[sym_anon_*]/模块[2 MODULE]归后续增量——method = 类型解析输
    出，归语义层后续）；③ **零风险加法式**（intrinsic_type_symbols 为独立 pyfunction，
    不动 Python 执行路径/语义层）；④ **命名**（pyfunction = `intrinsic_type_symbols`，
    区别于模块名 `intrinsic_symbols`[避免 E0428 重名]）。**验证**：42/42 全字段匹配 +
    差分 harness 25/25 + 全量 pytest 零回归（阶段 B 第四增量放行门——加法式增量不动
    Python 执行路径，计数 = 4282 + intrinsic 类型差分测试 1 例 = 4283；见 NEXT_STEPS
    基线锚点）。**阶段 B 第四增量出口达成**（intrinsic 符号表——42 内置类型）。
  **分支状态**：`rust-kernel` 隔离分支；阶段 B 第四增量零风险加法式（intrinsic_type_
    symbols 为独立 pyfunction），验证后 merge unsafe-vibe-dev 并删分支；阶段 B 后续（语
    义层 Rust 移植续[类型解析[type_uid] + 节点绑定[node_uid] + intrinsic 函数/方法/模块
    + free_vars 闭包捕获 + scope 完整收集] + 序列化续[符号/类型/scope 收集 + 完整 artifact
    组装] + 值对象[IbValue 扩展 8902 行]）续在隔离分支（差分门逐级验证）；保留 Python
    接口[HostService + CPS VM[LLM/意图/宿主面]]。
- **P9 全量 Rust 化阶段 B 第五增量（intrinsic 符号表完整——63 符号，全字段 63/63 匹配
  无多余，2026-09-10，隔离分支 `rust-kernel`）**：**阶段 B 续（语义层：intrinsic 符
  号表完整）**——intrinsic 符号表完整（42 内置类型 CLASS + 19 内置函数 FUNCTION + 2
  内置模块 MODULE = 63 符号）。每个 intrinsic 符号：uid = `intrinsic:<name>`，kind =
  CLASS/FUNCTION/MODULE，type_uid = `type_root.<name>`，node_uid/owned_scope_uid = null，
  metadata = {}（已核全同构）。与 Python intrinsic 符号表逐条差分等价（63/63 全字段匹
  配 + 无多余）。**交付**：
  - **intrinsic_symbols 模块扩展**（`ibci-ext/src/intrinsic_symbols.rs`）：加
    `BUILTIN_FUNCTIONS`[19 内置函数] + `BUILTIN_MODULES`[2 内置模块] + `make_
    intrinsic(name, kind)`[构建单符号] + `builtin_intrinsic_symbols()`[→ 63 符号
    BTreeMap]。
  - **pyo3 暴露**：`ibci_ext.intrinsic_symbol_table() -> intrinsic_symbol_pool_json`
    （区别于 `intrinsic_type_symbols()`[42 类型]）。
  - **差分 harness 测试**（TestRustSerializationUid::test_intrinsic_symbol_table_corpus）：
    63 intrinsic 符号差分（全字段等价 + 无多余）。
  **关键裁定（self-grill 全分支消解）**：① **intrinsic 符号表完整 = 42 类型 + 19 函数
    + 2 模块**（method = sym_anon_*[类型解析输出，归语义层后续]；19 函数/2 模块全同构
    [type_uid = type_root.<name>，node_uid/owned null，metadata {}——已核]）；② **复用
    make_intrinsic**（单符号构建函数，42 类型 + 19 函数 + 2 模块共用[机制同构，消除重
    复]）；③ **零风险加法式**（intrinsic_symbol_table 为独立 pyfunction，不动 Python
    执行路径/语义层）；④ **差分含无多余检查**（Rust 63 符号 ⊆ Python intrinsic 符号 +
    无多余[防 Rust 误产符号]）。**验证**：63/63 全字段匹配 + 无多余 + 差分 harness
    26/26 + 全量 pytest 零回归（阶段 B 第五增量放行门——加法式增量不动 Python 执行路径，
    计数 = 4283 + intrinsic 符号表差分测试 1 例 = 4284；见 NEXT_STEPS 基线锚点）。
    **阶段 B 第五增量出口达成**（intrinsic 符号表完整——63 符号）。
  **分支状态**：`rust-kernel` 隔离分支；阶段 B 第五增量零风险加法式（intrinsic_symbol_
    table 为独立 pyfunction），验证后 merge unsafe-vibe-dev 并删分支；阶段 B 后续（语义
    层 Rust 移植续[类型解析[type_uid] + 节点绑定[node_uid] + method[sym_anon_*] + free_
    vars 闭包捕获 + scope 完整收集] + 序列化续[符号/类型/scope 收集 + 完整 artifact 组装]
    + 值对象[IbValue 扩展 8902 行]）续在隔离分支（差分门逐级验证）；保留 Python 接口
    [HostService + CPS VM[LLM/意图/宿主面]]。
- **P9 全量 Rust 化阶段 B 第六增量（语义层 Rust 移植续——node 绑定 node_uid，34 语料
  scope 符号 node_uid 50/52 匹配，2026-09-10，隔离分支 `rust-kernel`）**：**阶段 B 续
  （语义层：node 绑定）**——Rust scope 符号的 node 绑定（node_uid = 定义节点 UID）。对应
  Python 语义层的 scope 符号 node 绑定：遍历 Rust AST，将用户定义符号绑定到定义节点
  （经 node_serializer 计算节点 UID）。定义节点映射：赋值目标/增赋值 → IbAssign/
  IbAugAssign / 函数名 → IbFunctionDef / 参数 → IbArg / for 目标 → IbFor / import 绑定
  → null（Python 语义层：import 模块/from-import 绑定无定义节点）/ 类名 → IbClassDef。
  **交付**：
  - **node_serializer 暴露**（`ibci-ext/src/node_serializer.rs`）：`serialize_stmt` /
    `serialize_expr` / `serialize_arg` 改 pub（供符号解析计算定义节点 UID）。
  - **symbol_resolver 改造**（`ibci-ext/src/symbol_resolver.rs`）：加 lifetime `'a`（绑定
    AST）+ `DefNode`[Stmt/Arg] + `def_nodes` 字段[符号 uid → 定义节点]；`resolve_stmt`
    改 `&'a Stmt`；`bind_symbol` 加 `def_node: Option<DefNode>` 参数；`resolve_module`
    末尾经 NodeSerializer 计算各定义符号的 node_uid（serialize_module 填充节点池 +
    serialize_stmt/arg 算定义节点 UID[节点 UID 确定性]）。
  - **差分 harness 测试**（TestRustSerializationUid::test_scope_symbols_node_uid_corpus）：
    34 语料 scope 符号 node_uid 差分（已知边界：closure_capture 嵌套函数 free_vars 致节
    点 UID 链式差异，跳过）。
  **关键裁定（self-grill 全分支消解）**：① **node 绑定 = 定义节点 UID**（经
    node_serializer 计算；节点 UID 确定性[content_str → sha256]，serialize_module 后
    serialize_stmt/arg 重算同一 UID）；② **lifetime 参数**（SymbolResolver<'a> 绑定
    AST；def_nodes 持有 AST 节点引用；resolve_stmt 改 &'a Stmt）；③ **import 绑定
    node_uid = null**（Python 语义层：import 模块/from-import 绑定无定义节点——已核，
    Rust 对齐[不传定义节点]）；④ **嵌套函数 = VARIABLE**（沿用阶段 B 第三增量裁定）；
    ⑤ **已知边界：closure_capture**（嵌套函数 `get` + 外层 `make` 2 例——嵌套函数 IbFunc-
    tionDef 节点含 free_vars[闭包捕获，语义层输出，Rust 节点不产]致节点 UID 差异 + 外层
    函数 body 含嵌套函数 UID 链式差异——归 free_vars Rust 移植后续）；⑥ **零风险加法式**
    （resolve_symbols 签名不变，node_uid 从 null → 定义节点 UID[对齐 Python]，不动 Python
    执行路径）。**验证**：34 语料 scope 符号 node_uid 50/52 匹配[2 差异 = closure_capture
    已知边界] + 差分 harness 27/27 + 全量 pytest 零回归（阶段 B 第六增量放行门——加法式
    增量不动 Python 执行路径，计数 = 4284 + node 绑定差分测试 1 例 = 4285；见 NEXT_STEPS
    基线锚点）。**阶段 B 第六增量出口达成**（语义层 Rust 移植续——node 绑定 node_uid）。
  **分支状态**：`rust-kernel` 隔离分支；阶段 B 第六增量零风险加法式（resolve_symbols 签名
    不变，node_uid 对齐 Python），验证后 merge unsafe-vibe-dev 并删分支；阶段 B 后续（语
    义层 Rust 移植续[类型解析[type_uid] + method[sym_anon_*] + free_vars 闭包捕获 + scope
    完整收集[owned_scope_uid]] + 序列化续[符号/类型/scope 收集 + 完整 artifact 组装] + 值
    对象[IbValue 扩展 8902 行]）续在隔离分支（差分门逐级验证）；保留 Python 接口[Host-
    Service + CPS VM[LLM/意图/宿主面]]。
- **P9 全量 Rust 化阶段 B 第七增量（语义层 Rust 移植续——类型解析 type_uid 字面值，
  34 语料 VARIABLE scope 符号 type_uid 23/43 字面值匹配，2026-09-10，隔离分支
  `rust-kernel`）**：**阶段 B 续（语义层：类型解析 type_uid 字面值子集）**——Rust 类
  型解析（对应 Python 语义层的类型解析[type resolution]中的字面值类型推断）：遍历 Rust
  AST 表达式，推断字面值的类型（int/str/bool/float/list/dict/tuple），计算 VARIABLE
  scope 符号的 type_uid（`type_root.<类型字符串>`）。类型字符串格式：`int`/`float`/
  `str`/`bool`/`None`/`list[<元素类型>]`/`dict[<键类型>,<值类型>]`/`tuple[<元素类型
  列表>]`。**交付**：
  - **type_inference 模块**（`ibci-ext/src/type_inference.rs`）：`infer_type(expr) ->
    Option<String>`[字面值类型推断：Constant → int/float/str/bool/None / List →
    list[<元素类型>] / Dict → dict[<键类型>,<值类型>] / Tuple → tuple[<元素类型列表>
    ]；非字面值 → None]。
  - **symbol_resolver 扩展**（`ibci-ext/src/symbol_resolver.rs`）：加 `value_exprs`
    字段[VARIABLE 符号 uid → 赋值右值表达式] + `bind_symbol` 加 `value_expr: Option<
    &Expr>` 参数[赋值传值表达式，其他传 None]；`resolve_module` 末尾经 type_inference
    计算 VARIABLE 符号的 type_uid（字面值可推断子集）。
  - **差分 harness 测试**（TestRustSerializationUid::test_scope_symbols_type_uid_corpus）：
    34 语料 VARIABLE scope 符号 type_uid 差分（Rust 设值时[字面值可推断]比对 Python；
    非字面值 Rust 不产[type_uid = null]——归类型解析后续）。
  **关键裁定（self-grill 全分支消解）**：① **类型解析 = 字面值类型推断**（int/str/
    bool/float/list/dict/tuple；type_uid = type_root.<类型字符串>；容器类型 = 首元素/
    键值/元素列表类型[list[<首元素类型>] / dict[<首键类型>,<首值类型>] / tuple[<全元
    素类型>]]）；② **非字面值归后续**（变量引用/函数调用/二元运算等需类型环境 + 函数
    签名——Rust 不产[type_uid = null]，34 语料 20 例）；③ **value_expr 跟踪**（赋值
    右值表达式[Option<Expr>]，bind_symbol 加参数[赋值传值表达式，其他传 None]）；
    ④ **零风险加法式**（resolve_symbols 签名不变，type_uid 从 null → 字面值类型[对齐
    Python]，不动 Python 执行路径）。**验证**：34 语料 VARIABLE scope 符号 type_uid
    23/43 字面值匹配[20 非字面值归后续，无 DIFF] + 差分 harness 28/28 + 全量 pytest
    零回归（阶段 B 第七增量放行门——加法式增量不动 Python 执行路径，计数 = 4285 + 类型
    解析差分测试 1 例 = 4286；见 NEXT_STEPS 基线锚点）。**阶段 B 第七增量出口达成**
    （语义层 Rust 移植续——类型解析 type_uid 字面值）。
  **分支状态**：`rust-kernel` 隔离分支；阶段 B 第七增量零风险加法式（resolve_symbols
    签名不变，type_uid 对齐 Python），验证后 merge unsafe-vibe-dev 并删分支；阶段 B 后
    续（语义层 Rust 移植续[类型解析续[变量引用/函数调用/二元运算等需类型环境 + 函数
    签名] + method[sym_anon_*] + free_vars 闭包捕获 + scope 完整收集[owned_scope_uid]]
    + 序列化续[符号/类型/scope 收集 + 完整 artifact 组装] + 值对象[IbValue 扩展 8902
    行]）续在隔离分支（差分门逐级验证）；保留 Python 接口[HostService + CPS VM[LLM/意
    图/宿主面]]。
- **P9 全量 Rust 化方向裁定重述 + 第一批（差分 harness 状态注册表：gap/divergence
  显式化，2026-09-11，本 session，unsafe-vibe-dev）**：**方向裁定（用户本 session 重申，
  凌驾于"对齐 Python 为验证门"旧定位）**：与 Python 行为对齐非首要目标；设计合理性/
  系统健康性/内部代码架构/宏观设计思路一致性 = 设计最主要原则；Rust 化后行为若有可证明
  正向（或至少无害/无负面/无危险）的轻微改变允许；已有设计非绝对事实，允许按破坏性
  重构授权推翻。用户授权全量 Rust 化无人值守（goal max_goal_rounds=100）+ 最大自主权限
  （批次重排/合并/细分/实现思路调整均可，不改变主线方向 + 不违反硬约束时无需拍板）。
  **第一批 = 差分 harness 状态注册表（单一权威源 + 通用查询）**——现状问题：随语义层
  Rust 化推进，Rust 中间产物（节点池/scope 符号/类型表）相对 Python 参考存在已知缺口，
  原本散落在各差分测试函数隐式 if + 注释（① test_node_pool_corpus `_normalize`
  `if k != "free_vars"` 静默排除 free_vars 字段；② test_scope_symbols_node_uid_corpus
  `if name == "closure_capture": continue` 按语料名硬编码跳过；③
  test_scope_symbols_type_uid_corpus `if rs.get("type_uid") is not None` 非字面值条件
  跳过）。违反 code-quality §二 静默绕过/§一.4 半接通 + design-philosophy §一 单一
  权威源/§二 统一设计语言（三处割裂形态表达同一概念）+ 工作模式定论 #3 禁 tricky（
  按名 continue 隐式约定）。**方案**：新增 tests/diff_harness/divergence.py = 已裁定
  状态注册表（单一权威源）——声明三态（GAP[Rust 尚未承载，随批次收缩，可观测度量] /
  DIVERGENCE[已裁定正向偏离，含 verify 核对器，供后续批次] / DEGRADE[环境态降级]）；
  DeclaredState[id/kind/plane/scope/rationale/verify?]；scope 结构化前缀（field:<name>
  排除字段 / case:<name> 跳 case / symbol:null:<field> 字段 null 即 gap）——协议驱动
  分派，非能力探测；通用查询 API（excluded_fields/skipped_cases/null_gap_fields/
  divergences_for/gap_count/summary）；测试函数改查注册表（消除散落硬编码 if）+ 新
  测试类 TestDivergenceRegistry 验证合法性 + 被消费（monkeypatch 移除声明→排除集合
  变化，证明非死代码）。**关键裁定（self-grill 全分支消解）**：① 单一权威源放 tests
  安全网层（非 core 内核层）——描述"Rust 相对 Python 参考的迁移期已知状态"，全量转向
  后 harness + 注册表一并退场，不污染生产内核；② GAP 不冒充通过——命中不计 fail 但显式
  声明可查询，超出 scope 差异仍 fail（fail-fast，不掩盖范围外回归）；③ DIVERGENCE 需
  verify 核对器（正向偏离不靠跳过，靠核对符合已登记预期）；④ 注册表有明确退场（每 GAP
  rationale 标归属批次，批次落地→移除，全量转向→GAP 清空退场）；⑤ 不双写文档（注册表
  = 机器权威状态，WORKLOG/NEXT_STEPS 只指针指向）。**变化前后**：前 = 3 处散落隐式 if
  + 注释承载"为什么豁免"（不可观测/不可统一治理/tricky）；后 = 单一声明式注册表 + 通用
  查询（可观测 + 随批次收缩 + DIVERGENCE 机制就绪）；比对语义不变（free_vars 仍排除/
  closure 仍跳过/非字面值仍条件比对）——纯收敛，零行为变化，零风险加法式。**验证**：
  diff_harness 子集 34 passed（34 语料差分门零差异 + 新 6 测试）+ smoke 子集 832 passed
  零回归（2026-09-11 实跑）；设计/裁定 = _p9b1_harness_state_registry.md[落地后删]。
- **P9 全量 Rust 化第二批 侦察（语义层类型解析，2026-09-11，本 session）**：**Phase
  0-1 代码上下文侦察完成**（实现留后续 round，质量优先不 rushed）——① 非字面值 type_uid
  目标精确锁定（诊断脚本 func_ret/binop/name_ref）：Name[变量引用→查类型环境，t=s→
  str] / BinOp[二元运算→结果类型，c=a+b→int，d=c*1.5→float[IBCI 数值语义 int*float=
  float]] / Call[函数调用→返回类型，x=add(1,2)→int[add 的 ->int 注解]] / 参数[类型
  注解，func add(int a)→a:int]；字面值[int/str/float/bool/None/list/dict/tuple]已由
  阶段 B 第七增量 Rust 承载（34 语料 23/43）。② IBCI 类型推导架构（关键裁定基准）：
  TypeCheckBase.visit(node)→IbSpec[类型 spec 对象非字符串；type_uid 字符串 = Flat
  Serializer 序列化 IbSpec 派生]；**运算符类型推导 = 公理层数据驱动**（registry.
  resolve_op(left,op,right)→各类型公理 resolve_operation_type_name(op,other)：int/
  float/str/bool/list/dict/tuple/None 各声明支持 op + 结果类型，core/kernel/axioms/
  primitives/*.py）；**无兜底推断**（数值提升/str 规则已并入公理声明，兜底与公理并存
  =双写真相；resolve 失败=None→报错 SEM_TYPE_MISMATCH + 退化 any）——贯彻"一切皆对象"。
  ③ 战略判断（自主裁定，记 WORKLOG）：Rust 类型推导应**同构对齐 IBCI 公理驱动架构**
  [类型→运算符声明表，协议驱动非硬编码 if，工作模式定论 #4]，非机械复刻 Python
  TypeCheckingVisitor 历史实现[含未接线的 TypeSlot/TypeInferenceState 设计载体=
  code-quality §一.4 预留未激活红旗]；按新方向[对齐 Python 非首要]，Rust 实现干净的
  IBCI 类型推导，确定性语义面差分等价 + 已裁定偏离白名单[divergence.py 机制已就绪，
  第一批]。④ 下一步（实现计划，后续 round 起）：移植 numeric.py[int/float op 表] +
  sequences.py[list/dict/tuple] + str/bool/None 运算符声明→Rust 运算符公理表[协议
  驱动]；Rust 类型环境[作用域栈 Name→type string，赋值/参数/声明填充]；Call 函数
  返回类型[func 定义 -> TYPE 注解]；差分验证[test_scope_symbols_type_uid_corpus 非字
  面值补齐]；偏离白名单登记。IBCI 类型 = 声明式 + 简单推断[非 HM 约束求解，非目标]，
  规则可管理。
- **P9 全量 Rust 化第二批 增量 1（语义层类型解析·非字面值 type_uid：Name/BinOp/Call/
  参数/returns，2026-09-11，本 session，unsafe-vibe-dev）**：**Rust 类型推导子系统**
  ——对齐 IBCI 公理驱动类型推导（侦察结论），非机械复刻 Python TypeCheckingVisitor。
  **交付**：① type_inference.rs 重构：infer_type_env[expr, 类型环境, 函数签名]（Name
  查类型环境[作用域栈，内层往外] + BinOp[公理 op 表] + Call[函数签名返回类型] + 容器/
  字面值）；infer_type = 空环境特例[单一实现无重复]；resolve_op[left,op,right] 移植
  IBCI int/float/bool/str 公理 resolve_operation_type_name[从左操作数类型分派，无兜底，
  贯彻一切皆对象]；parse_type_annotation[returns/参数 Name → intrinsic 子集]。②
  symbol_resolver.rs 重构：加 type_env[作用域栈，与 scope_stack 同步，push_scope/
  pop_scope 单一权威源] + func_sigs[函数名→返回类型]；Assign 即时算 type_uid（推断右
  值类型→类型环境+符号 type_uid，替换原 value_exprs 事后算）；FunctionDef 注册 returns
  签名 + 参数注解类型 + push/pop scope；bind_symbol 去 value_expr 参数[即时化]。**关键
  裁定**：① 对齐 IBCI 公理（numeric/sequences resolve_operation_type_name），非 Python
  TypeCheckingVisitor 历史[含未接线 TypeSlot 设计载体]——按新方向[对齐 Python 非首要]
  Rust 实现干净的 IBCI 类型推导；② IBCI 数值语义复现（int*float=float / int*str=str
  [字符串重复] / 比较→bool / str+str=str）；③ UnaryOp/BoolOp/Compare/用户类类型/容器
  泛型格式 = 后续增量（gap 声明 symbol:null:type_uid 自适应跳过）；④ 即时类型环境贴近
  Python 递归 visit 语义[先定义后使用]。**验证**：诊断脚本 func_ret/binop/name_ref/
  str_concat 全 OK（a/b 参数 int + x=add 返回 int + c=a+b int + d=c*1.5 float + t=s
  str + b=a+"y" str）；34 语料 VARIABLE type_uid 23/43→**30/43**（非字面值补齐 7，全部
  匹配，**0 DIFF**）；diff_harness 34 passed + smoke 832 passed 零回归。gap 注册表
  自适应（Rust 未产 13 个跳过）。第二批后续：method[sym_anon_*] + free_vars 闭包捕获 +
  scope 完整[owned_scope_uid] + 容器泛型 type_uid 格式对齐 + UnaryOp/BoolOp/Compare。
- **P9 全量 Rust 化第二批 增量 2（语义层类型解析·剩余面补齐：for 目标/IfExp/嵌套
  函数/内置调用，type_uid 43/43 全对齐，2026-09-11，本 session，unsafe-vibe-dev）**：
  **类型解析面 100% 对齐里程碑**——增量 1 后 13 个 gap 分 6 类（均 IBCI 语义规则，非
  机械复刻 Python）：① for 循环目标 = any[IBCI iter 类型不推断]；② IfExp 三元 = body
  类型；③ 嵌套函数名 = 函数类型 type_root.<name>[持有函数的变量类型]；④⑤⑥ 内置调用
  类型表（intrinsic_call_type）：knowledge()→knowledge / quote→quoted / meta.eval→
  auto[一等值类型 + 无注解返回]。**交付**：type_inference.rs 加 IfExp 分支[body 类型]
  + intrinsic_call_type[内置调用表，Name/Attribute 分派] + Call 分支[用户 func_sigs
  优先，再 intrinsic]；symbol_resolver.rs For 目标 bind_var_type(any) + 嵌套函数名
  bind_var_type(name)。**关键裁定**：① 6 类规则均为 IBCI 类型系统语义（for 目标 any/
  三元 body/嵌套函数类型/一等值类型 knowledge·quoted/无注解 auto），非 Python 历史
  复刻——按新方向对齐 IBCI 语义；② intrinsic_call_type 协议驱动[Name/Attribute 分派]
  非硬编码 if；③ UnaryOp/BoolOp/Compare 仍 gap（op 格式对齐[Python unary- vs Rust -]
  + 运算符扩展归后续增量）。**验证**：34 语料 VARIABLE type_uid **43/43 全对齐 0
  DIFF**（增量 1 后 30/43→43/43）；diff_harness 34 passed + smoke 832 passed 零回归。
  **第二批剩余（增量 3+）**：method[sym_anon_* 方法符号] + free_vars 闭包捕获 + scope
  完整[owned_scope_uid] + UnaryOp/BoolOp/Compare + 容器泛型 type_uid 格式对齐。
- **P9 全量 Rust 化第二批 增量 3 子项 1（语义层 scope 完整收集：owned_scope_uid，
  52/52 全对齐，2026-09-11，本 session，unsafe-vibe-dev）**：**owned_scope_uid**——
  函数符号（FUNCTION + 嵌套持有函数的 VARIABLE）拥有的函数体 scope 的 UID
  （`scope_<函数体 scope 串>`），非函数符号 = null。侦察发现容器泛型 type_uid 已
  对齐（Rust list[int]/dict[str,int] == Python，name 直接含泛型参数，无额外工作）。
  **交付**：symbol_resolver.rs FunctionDef push_scope 后设函数符号 owned_scope_uid =
  scope_ + current_scope()[push 后]（正对应 Rust scope_stack 语义——函数体 scope 串）；
  差分 harness 加 test_scope_symbols_owned_scope_corpus[比对全符号 owned_scope_uid]。
  **关键裁定**：① owned_scope_uid 是 IBCI scope 收集语义（函数符号拥有函数体
  SymbolTable），Rust scope_stack push 后的 current_scope 天然对应（机制同构，非
  硬编码）；② 容器泛型 type_uid 侦察确认已对齐（消除后续顾虑）；③ method 符号
  [sym_anon_<content_hash>] + free_vars[节点级 Lambda/闭包分析] 较复杂，归后续子项。
  **验证**：owned_scope_uid 52/52 全对齐 0 DIFF（7 函数符号有值 + 45 null）；
  diff_harness 35 passed[+1 owned_scope 门] + smoke 832 passed 零回归。
  **第二批剩余（增量 3 子项 2+）**：method 符号[sym_anon_*] + free_vars[闭包捕获]。
- **P9 全量 Rust 化 战略 reframe + 第三批侦察（2026-09-11，本 session）**：**第二批
  语义层类型解析收束 + method/free_vars 重新定位**（批次细分，自主裁定）。侦察发现：
  ① method 符号[sym_anon_*，187 distinct/5390 总/34 语料]的 get_content_hash 用**原始
  Symbol 的 spec[MethodMemberSpec.module_path/name]**（非序列化 type_uid）——探针
  0/148 无法从序列化 sym_data 反推；method 符号是类型系统方法声明固有面，正确 Rust 化
  需统一 artifact 产出流程。② free_vars[节点级 node_data，当前语料仅 1 节点
  closure_capture]跨"符号分析[scope]→节点序列化"两层，正确实现需统一 artifact 产出。
  ③ 完整 artifact = modules[entry_module + root_node/scope_uid + import_star_members +
  side_tables[node_to_symbol/node_to_type/**node_to_loc**] + pools[nodes/symbols/
  **scopes**/**types**/assets]] + **global_symbols**——Rust 当前已有 nodes
  [serialize_nodes，free_vars 缺] + symbols[resolve_symbols + intrinsic 63] +
  side_tables[node_to_symbol/node_to_type]，**缺 types 池[78 distinct = 73 fixed[66
  KERNEL_NATIVE + 7 USER_DEFINED] + 5 generic 容器泛型] / scopes 池 / global_symbols /
  node_to_loc / method 符号 / free_vars / modules 组装**。**战略 reframe**：第二批
  "语义层类型解析"收束于 scope 符号 + type_uid 43/43 + owned_scope_uid 52/52 +
  node_uid + intrinsic 符号 63[已达成核心]；method 符号 + free_vars +
  types/scopes/global_symbols/node_to_loc 池 + modules 组装 = **第三批[Rust 独立完整
  artifact 产出]**（消除"消费 Python 前端 JSON"输入边界的完整闭环）。第三批子项序列：
  types 池[intrinsic 固定集 + 用户 + 泛型] → scopes 池 → global_symbols → node_to_loc
  → method 符号 → free_vars → modules 组装。
- **P9 全量 Rust 化第三批 子项 1（Rust 独立 artifact 产出：types 池 KERNEL_NATIVE
  固定集，66/66 全对齐，2026-09-11，本 session，unsafe-vibe-dev）**：**intrinsic 类型
  池**——Rust 静态表（对齐 Python registry/prelude 固有类型集，与 intrinsic_symbol_table
  机制同构）。**侦察**：完整 artifact = modules[root_node/scope_uid + import_star_members
  + side_tables[node_to_symbol/node_to_type/node_to_loc] + pools[nodes/symbols/scopes/
  types/assets]] + global_symbols；types 池 = 66 non-generic KERNEL_NATIVE 固定集[10
  primitive + 2 callable_instance + 19 class + 1 optional + 1 bound_method + list/tuple/
  dict/chan/slot/subscriber/thread/thread_result/generator 各 1 + 21 function + 3 module]
  + 5 generic 容器泛型[随语料] + 7 USER_DEFINED[用户类/模块]。**交付**：intrinsic_symbols
  .rs 加 INTRINSIC_TYPES[66，含 3 IMPORT_GATED eval/quote/meta] + builtin_intrinsic_types
  [uid=type_root.<name> + kind[细粒度 TypeKind，非符号 CLASS/FUNCTION] + module_path=None
  + provenance=KERNEL_NATIVE + visibility[PRELUDE/IMPORT_GATED] + storage_model=
  MEMORY_BACKED]；lib.rs 加 intrinsic_type_pool pyfunction；差分 harness 加
  test_intrinsic_type_pool[用 import meta + quote + eval 语料覆盖全部 66，含 IMPORT_GATED
  按需引入]。**关键裁定**：① types 池 kind = 细粒度 TypeKind（primitive/callable_instance/
  class/...），非 intrinsic_symbol_table 的符号 kind[CLASS/FUNCTION/MODULE]——两池 kind
  语义不同；② IMPORT_GATED（meta/quote/eval）按需引入[import/调用时]，固有 intrinsic 集
  含之[语言设计]，差分语料需同时引入全覆盖；③ members_uids[方法 sym_anon] / 用户类 /
  泛型实例 = 后续子项[需统一 artifact 产出 + method content_hash 原始 spec]。**验证**：
  intrinsic_type_pool 66/66 全对齐 0 field diff 无多余；diff_harness 36 passed[+1] +
  smoke 832 passed 零回归。**第三批剩余**：scopes 池 / global_symbols / node_to_loc /
  method 符号 / free_vars / modules 组装。
- **P9 全量 Rust 化第三批 子项 2a（Rust 独立 artifact 产出：scopes 池，39 scope +
  2194 symbol 全对齐，2026-09-11，本 session，unsafe-vibe-dev）**：**scope 池**——顶层
  scope[scope___string_exec__] = intrinsic 符号[固定 63，intrinsic:<name>] + 用户顶层
  符号；函数 scope[scope___string_exec__/f] = 用户函数内符号，parent = 定义处 scope
  [scope 串去最后一段]；global_refs=[]。**交付**：intrinsic_symbols.rs 加
  intrinsic_names()[63]；scope_serializer.rs[新] scope_pool(source)[解析 AST →
  SymbolResolver.resolve_module → 按 scope 分组用户符号[uid=scope_<串>:<name>] → 顶层
  组合 intrinsic 63 + 用户顶层 + 函数 scope[parent 推导]]；lib.rs 加 scope_pool
  pyfunction；差分 harness 加 test_scope_pool_corpus[Rust ⊆ Python：每个 scope
  uid/parent_uid + 每 symbol name→uid 相等，允许 Python 多 IMPORT_GATED]。**关键裁定**：
  ① scopes 池的 symbols 字段引用符号 uid（intrinsic:<name> 或 scope_<串>:<name>），顶层
  scope 含全 63 intrinsic[固有] + 用户顶层；② parent_uid = scope_<父 scope 串>[含
  scope_ 前缀，非裸串]——初版漏 scope_ 前缀致 5 parent DIFF，修复；③ IMPORT_GATED
  [meta/quote/eval 按需引入] 不在 intrinsic 固定 63，差分用 ⊆ 验证[Rust 产的对，Python
  可多]。**验证**：scope_pool 39 scope 全 parent 对齐 + 2194 symbol name→uid 全对齐
  0 DIFF；diff_harness 37 passed[+1] + smoke 832 passed 零回归。**第三批剩余**：
  global_symbols / node_to_loc 侧表 / method 符号 / free_vars / modules 组装。
- **P9 全量 Rust 化第三批 子项 2b-1（Rust 独立 artifact 产出：node_to_loc 侧表，
  位置多重集全对齐，2026-09-11，本 session，unsafe-vibe-dev）**：**node_to_loc 侧表**
  ——node_uid → {file_path, line, column}。**交付**：node_serializer.rs 加
  node_to_loc[source]（派生自 node 池的 lineno/col_offset，file_path=null）；lib.rs 加
  node_to_loc pyfunction；差分 harness 加 test_node_to_loc_corpus[位置多重集验证]。
  **关键裁定**：① Rust node 已有 lineno/col_offset/end_*[== Python node_to_loc 的
  line/column，1-based]，node_to_loc 直接派生[node_uid → {file_path:null, line:lineno,
  column:col_offset}]；② file_path=null 是 Rust 架构自然（Rust 无临时文件，source
  直接输入；Python 的 file_path 是编译临时 .ibci 文件的副产物，非 artifact 语义）——
  非对齐偏离；③ node_to_loc 差分验证用 (line,column) 多重集[非 uid 关联]——closure 的
  IbFunctionDef/IbModule node_uid 属既有 closure gap[Rust uid ≠ Python]，但**位置集合
  完全相等**[closure_capture 23==23]，位置多重集验证 closure 友好。**验证**：
  node_to_loc 位置多重集 34 语料全对齐（832 node，closure 位置集合相等）+ file_path
  全 null；diff_harness 38 passed[+1] + smoke 832 passed 零回归。**第三批剩余**：
  global_symbols / method 符号 / free_vars / modules 组装。
- **P9 全量 Rust 化第三批 战略判断 + 统一 artifact 产出设计（2026-09-11，本 session）**：
  **node_to_symbol/node_to_type/free_vars 统一遍历分析** + **双通道消除设计**。**侦察
  发现**：① global_symbols 0/34（当前语料全空，低价值）；② node_to_symbol[262：
  IbName 211/IbAssign 34/IbFunctionDef 7/IbArg 6/IbAlias 4] + node_to_type[635：
  IbName/IbConstant/IbCall/IbAttribute/IbBinOp/... 几乎所有表达式节点] 的**节点 uid =
  node_data content hash**（NodeSerializer sha256[:16]），但**符号解析需 scope
  栈**（SymbolResolver）+ **type_uid 推导需 type_env**（type_inference）—— 三者分离；
  ③ symbol_table/type_table pyfunction 是 **deserializer（消费 artifact）**，**非独立
  产出**——node_to_symbol/node_to_type 侧表 Rust **尚未独立产出**（只有 node_to_loc）；
  ④ node_to_type 的值 = type_uid（Rust type_inference 已推导，符号级 43/43 验证；节点
  级复用）。**战略判断**：第三批**核心确定性池**[nodes/scope 符号 type_uid 43/43 +
  owned_scope_uid 52/52/intrinsic 符号 63/类型 66/scopes 池/node_to_loc side_table]
  **已 Rust 化并验证**；剩余[node_to_type/node_to_symbol 侧表独立产出 + method 符号
  187[content_hash 用原始 spec，探针 0/148] + generic/用户类型条目[耦合 method
  members_uids] + free_vars + modules 组装]**都需统一 AST 遍历**[节点 uid + scope
  栈 + type_env + 节点语义关联]。**设计[统一 artifact 产出]**：当前 NodeSerializer
  [node uid/node_data] + SymbolResolver[scope 栈/符号/type_uid] + type_inference
  [type_env] **分离**[潜在双通道——都遍历 AST]。**正确方向**[design-philosophy
  机制同构/单一权威源]：统一 AST 遍历[一次遍历产 nodes + symbols + scopes +
  side_tables[node_to_symbol/node_to_type/node_to_loc] + free_vars]，消除双通道。
  **推进序列**：node_to_type[节点级 type_uid，复用 type_inference + NodeSerializer
  scope 栈] → node_to_symbol → free_vars → method 符号[content_hash 偏离：Rust 确定性
  hash，语义等价[方法集+签名]，白名单] → generic/用户类型[耦合 method] → modules 组装
  [完整 artifact 闭环]。
- **P9 全量 Rust 化第三批 子项 2b-2a（Rust 独立 artifact 产出：node_to_type 侧表独立
  产出 + NodeSerializer 统一遍历基础，IbConstant 字面量 type_uid 34/34 全对齐，
  2026-09-11，本 session，unsafe-vibe-dev）**：**node_to_type 侧表独立产出**
  （node_uid → type_uid，节点级 type_uid）+ **NodeSerializer 统一遍历基础**（scope 栈
  + type_env + func_sigs，**消除双通道的方向**——design-philosophy 机制同构）。**交付**
  ：NodeSerializer 加 scope_stack + type_env + func_sigs + node_to_type 字段（**复用
  SymbolResolver 逻辑**：push_scope/pop_scope/bind_type_env，单一权威源避免双通道漂移）
  + serialize_expr 委托 serialize_expr_impl + infer_type_env 记录 node_to_type
  [type_root.<类型名> 前缀，与符号 type_uid 格式一致] + serialize_stmt[IbAssign 目标
  type_env 绑定 + node_to_type 更新[bind_type_env 后] / IbFunctionDef 函数名 type_env
  [含顶层] + func_sigs[returns] + 参数 type_env / IbFor 目标 any] + new() 绑定
  intrinsic 函数[19]；intrinsic_symbols 加 builtin_function_names；lib.rs 加
  node_to_type pyfunction；差分 harness 加 test_node_to_type_corpus[验证 IbConstant
  字面量 type_uid 多重集对齐]。**关键裁定**：① node_to_type 值 = type_root.<类型名>
  [infer_type_env 返回裸类型名加前缀]——初版漏 type_root 前缀致全 34 DIFF，修复；
  ② node_to_type 的 IbName/IbAssign/IbFor 目标 type_uid **顺序**：serialize_expr 先
  记录[未绑定] → bind_type_env 后**更新**[值类型/any]——初版顺序错误致 target None，
  修复；③ NodeSerializer 复用 SymbolResolver 的 scope 栈/type_env 逻辑[统一遍历方向，
  消除 NodeSerializer/SymbolResolver 分离]；④ node_to_type **IbConstant**[字面量]
  **34/34 全对齐**[不依赖 func_sigs/any/generic]，**其余**[IbName any/int-from-Call +
  IbBinOp/IbListExpr/IbDict/IbTuple/IbCall/IbIfExp + infer_type_env 节点覆盖
  [UnaryOp/BoolOp/Compare/Subscript/Attribute] + IbCall intrinsic 函数签名
  [print→void/range→list] + 方法 bound_method + generic]**是 infer_type_env 的改进**
  [后续]。**验证**：node_to_type IbConstant 字面量 type_uid 34/34 全对齐 0 DIFF；node
  池不破坏[829/832，closure 3 个 uid 既有 gap]；diff_harness 39 passed[+1] + smoke 832
  passed 零回归。**第三批剩余**：node_to_type 完整[infer_type_env 改进：Call func_sigs
  查表 + Name 未定义→any + 节点覆盖 + IbCall intrinsic 函数签名 + 方法 + generic] /
  node_to_symbol 侧表 / free_vars / method 符号 / generic+用户类型条目 / modules 组装
  [完整 artifact 闭环]。
- **P9 全量 Rust 化第三批 子项 2b-2b-1（Rust 独立 artifact 产出：node_to_type 的
  IbCall intrinsic 函数返回类型，IbConstant+IbCall 34/34 全对齐，2026-09-11，本
  session，unsafe-vibe-dev）**：**node_to_type 的 IbCall**（**intrinsic 函数返回类型**
  + 用户函数 func_sigs）。**侦察**：node_to_type 剩余 DIFF[IbConstant+IbCall 24/34]
  **根因** = **intrinsic_call_type** **不含** **intrinsic 函数返回类型**
  [print→void/range→list/len→int，之前只含 knowledge/quote/eval]；用户函数 IbCall
  [add] **已对齐**[func_sigs 查表，infer_type_env 的 Call 处理已查 func_sigs]。**交付**：
  type_inference 的 intrinsic_call_type 加 **print→void + range→list + len→int**
  [intrinsic 函数返回类型]；差分 harness 的 test_node_to_type_corpus **验证**
  **IbConstant+IbCall**[排除 Attribute callee 方法[bound_method 返回类型后续] +
  generic[泛型后续]]。**关键裁定**：① **intrinsic_call_type 的 eval 保持 auto**
  [非 any]——**scope 符号 type_uid**[y = meta.eval(x) 的 y] **= auto**[Python 43/43]，
  **node_to_type** 的 **meta.eval() 调用 = any**[Python]**是节点级偏离**[已排除
  Attribute callee，gap]——**符号 type_uid 优先**[43/43 已验证]；② **IbCall 方法**
  [Attribute callee：xs.append/s.upper] **的返回类型** **缺口**[方法类型 bound_method，
  后续]；③ **完整 intrinsic 函数返回类型**[19 个，34 语料覆盖 print/range/len，其他后续
  从 Python 语义层移植]。**验证**：node_to_type **IbConstant+IbCall 非方法/非 generic**
  **34/34 全对齐 0 DIFF**；**scope 符号 type_uid 43/43 恢复**[eval→auto 保持]；
  diff_harness 39 passed + smoke 832 passed 零回归。**第三批剩余**：node_to_type 完整
  [IbCall 方法 bound_method + generic + intrinsic 函数返回类型其他 16 个 + IbName any +
  infer_type_env 节点覆盖] / node_to_symbol / free_vars / method 符号 / generic+用户类型
  / modules 组装。
- **P9 全量 Rust 化第三批 子项 2b-2b-2 增量 1（Rust 独立 artifact 产出：node_to_type
  完整面——全节点级 type_uid 34 语料 635/635 全量多重集对齐 0 DIFF，2026-09-11，本
  session，unsafe-vibe-dev）**：**node_to_type 完整面**（消除 2b-2a/2b-2b-1 的节点
  类型过滤门——测试从"IbConstant+非方法非 generic IbCall"扩至**全节点类型全量**多重集
  等价，无过滤无排除）。**侦察实证**（Python node_to_type 34 语料 635 条全分布 + 节点
  覆盖面对账）：① 节点覆盖 = 全部表达式节点，**唯二例外**：参数注解 Name 不绑定（6/6
  实证——Python type checker 绑定返回注解不绑定参数注解）+ Slice 节点不绑定（2/2 实证）；
  ② **双通道语义实证**（2b-2b-1 裁定实体化）：meta.eval() 的 Call 节点 = any（checker
  绑定回退）vs 符号 x = auto（声明返回类型）vs target 节点 x = any（右值节点类型）——
  三值分属节点通道/符号通道/target 绑定；③ **首次绑定优先实证**（arithmetic_loop）：
  `total = total + i` 的 target 节点与符号 = int（既有类型保持），非右值 any——any
  传播只影响右值节点绑定；④ **容器裸形态实证**：空列表/空字典字面量 = 裸 list/dict
  （非 list[any]——Rust 此前空容器产 list[any]/dict[any,any] 为既有错误，本增量修复）；
  ⑤ **方法返回类型表实证**（公理声明式方法表 `_m(name, params, ret)` 为权威源）：str
  [strip/upper/lower→str, split→list, find→int] / list[append→void, index→int, pop→
  元素 T] / dict[get→值 V, keys→list[K], values→list[V]——**容器方法按类型参数特化**：
  公理声明 ret=any 但 checker 按容器实参特化，语料实证 list[int].pop→int /
  dict[str,int].get→int / dict[str,int].keys→list[str]] / knowledge[40 方法全表，
  add_fact→str 非 void] / vector / 数值族[cast_to/to_bool/to_list] / quoted[字段
  source→str 非方法]；⑥ **intrinsic 函数返回类型表 19 实证探测**（all→bool/
  callable→auto/copy→any/deepcopy→any/len→int/max→any/min→any/print→void/range→
  list/reversed→list/sorted→list/sum→any/type→str/vec→vector/zip→list +
  knowledge→knowledge + quote→quoted；enumerate/fn/next/get_self_source = 特殊形态
  语料面不覆盖）；⑦ **运算符 any/auto 传播实证**（BinOp/Compare 任一操作数 any/auto →
  any）+ list+list→list（公理 sequences 不特化）。**交付**：
  - **type_inference.rs 重构**（单一入口 `infer_type_env(expr, &InferCtx)`——InferCtx
    [type_env + func_sigs + modules] 供符号/节点两 walker 共用[机制同构，无平行实现]）：
    完整节点规则[Name 类型环境/容器[裸+泛型+空裸形态]/BinOp[公理 op 表 + any 传播 +
    list 拼接]/UnaryOp[not→bool, ±→操作数类型]/BoolOp[bool]/Compare[any 传播]/Call
    [Name callee=签名+intrinsic 19 表 / Attribute callee=模块成员[meta.quote→quoted,
    meta.eval→any 节点通道] + 方法表[容器特化]]/IfExp[body]/Subscript[容器元素特化]/
    Attribute[模块成员→type_root.<attr> / 方法→bound_method / quoted.source→str /
    其余→any]/Slice 不绑定]；`symbol_level_type`[符号通道：meta.eval→auto 唯一差异]
    ；`method_call_return`[公理方法表转录，parse_container 括号深度感知分割
    dict[str,list[int]]]；`intrinsic_function_return`[19 表]。
  - **node_serializer.rs 统一遍历扩展**：顶层 type_env = 全 63 intrinsic 符号名
    [42 类型 + 19 函数 + 2 模块，与 scope 池"顶层 scope = intrinsic 63"语义同构] +
    modules 集[Import 绑定] + from-import 绑定名 + ClassDef 类名绑定；Assign 双通道
    + 首次绑定优先[target 节点/type_env：当前 scope 已有类型 = 保持，新变量 = 右值
    节点通道[节点]/符号通道[环境]]；serialize_expr 记录态参数化[ser(e, record) 单一
    递归路径]——参数注解位置无记录[serialize_expr_no_record，Python 实证一致]。
  - **symbol_resolver.rs 接入 InferCtx**（modules 集 + 符号通道 symbol_level_type +
    首次绑定优先[符号已有 type_uid 不覆盖]）。
  - **差分 harness**：test_node_to_type_corpus 去过滤——**全节点类型全量多重集等价**
    （rust only / py only 差集诊断输出）。
  **关键裁定（self-grill 全分支消解）**：① **双通道实体化非回避**——meta.eval 的
  any[节点]/auto[符号] 分离是 Python 实际语义（checker 绑定 vs 声明类型）的忠实
  转录，非静默兜底；两通道共用单一 infer 实现 + 一处显式差异[已记录]；② **静态表
  = 公理转录**（与 sub-item 1 类型池 66 固定集同模式——Rust 独立 artifact 产出的
  固有面，权威源 = IBCI 公理，差分门 = 安全网）；③ **首次绑定优先 = IBCI 变量
  类型语义**（首次声明定型，语料实证；非"保持行为"迁就）；④ **空容器裸形态修复
  = 根因修正**（既有 list[any] 产式与 Python 实证不符——原则优先于行为维持）；
  ⑤ **any 语义合法**（IBC 动态类型一等语义——dict.get 声明 ret=any / 未解析
  checker 绑定 any = Python 实际语义转录，非掩盖型兜底）；⑥ **零风险加法式**
  （Rust 侧扩展面变更 + 测试扩面，不动 Python 执行路径/FlatSerializer/语义层）。
  **验证**：node_to_type **34 语料 635/635 全量多重集对齐 0 DIFF**（全节点类型，无
  过滤无排除；scope 符号 type_uid 43/43 + owned_scope 52/52 + 节点池 829/832 +
  intrinsic 面全回归无损）；diff_harness 39 passed + smoke 832 passed + **全量
  pytest 4297 passed / 1 skipped 零回归**（2026-09-11 实跑 141.54s；用户本 session
  裁定全量 pytest 限制放开后首跑）。**第三批剩余**：node_to_symbol 侧表独立产出
  / free_vars / method 符号[sym_anon_* content_hash 偏离白名单] / generic+用户类型
  条目 / modules 组装[完整 artifact 闭环]。
- **P9 全量 Rust 化第三批 子项 2b-2b-2 增量 2（Rust 独立 artifact 产出：node_to_symbol
  侧表独立产出，34 语料 262/262 全量多重集对齐 0 DIFF，2026-09-11，本 session，
  unsafe-vibe-dev）**：**node_to_symbol 侧表独立产出**（node_uid → symbol uid——消除
  2b-2a 侦察指出的"node_to_symbol Rust 尚未独立产出"缺口）。**侦察实证**（Python
  node_to_symbol 34 语料 262 条全分布）：① 条目构成 = IbName 引用[211：VARIABLE 127
  变量 + FUNCTION 76[intrinsic 函数 4 + 用户函数引用] + MODULE 5 + CLASS 3] +
  IbAssign[34 定义节点] + IbFunctionDef[7：顶层 5 FUNCTION + 嵌套 2 VARIABLE——uid
  串同构] + IbArg[6 参数] + IbAlias[4 import 绑定] + for 目标 Store Name[4]；② 符号
  uid 双形态：用户定义 = `scope_<定义 scope 串>:<name>`（含嵌套 scope 串
  scope___string_exec__/outer:inner）/ intrinsic 固有名字 = `intrinsic:<name>`
  [print/range/len/knowledge 等——Python：intrinsic 符号 uid 独立驻顶层 scope 符号表]；
  ③ **注解位置不绑定符号**（Python 实证 13/13：返回注解 Name 7 + 参数注解 Name 6——
  node_to_symbol 与 node_to_type 的注解规则不同：返回注解有类型无符号）；④ **首次赋值
  target Name 节点也绑定定义符号**（arithmetic_loop：total 4 Name + 2 IbAssign = 6）。
  **交付**：
  - **NodeSerializer 统一遍历扩展**：user_defined 标记层[每 scope 一个 Name 集，与
    scope_stack/type_env 同步 push/pop] + define_name 单一写入点[type_env + user
    _defined 同步写，无漂移——区分"用户顶层定义"与"顶层 intrinsic 固有绑定"] +
    intrinsic_names 固定集[new() 预计算] + resolve_symbol_uid[scope 链内层→外层用户
    定义优先 → scope uid；否则 intrinsic 63 → intrinsic uid；未命中 → 不产条目]；
    定义节点条目：IbAssign[IbAssign 节点 + target Name 节点 双重绑定定义符号] /
    IbFunctionDef[定义 scope = 外层，pop_scope 后当前 scope 即定义处] / IbArg[函数体
    scope——serialize_arg 移入函数 scope 内序列化] / IbAlias[绑定名，当前 scope] /
    for 目标；Name 引用条目经 Full 模式记录（serialize_expr_recorded + RecordMode
    三态[Full=值位置 type+symbol / TypeOnly=返回注解 type only / None=参数注解
    无记录——位置语义显式分派，非能力探测]）。
  - **lib.rs**：node_to_symbol pyfunction[独立产出，同 node_to_type 模式]。
  - **差分 harness**：test_node_to_symbol_corpus[全量多重集等价，无过滤——scope 串
    确定性非 uid 派生，closure 友好]。
  **关键裁定（self-grill 全分支消解）**：① **user_defined 标记层非双通道**——与
  type_env 经 define_name 单一写入点同步（同 push_scope 同步 scope_stack+type_env
  的既有模式），承载"用户定义 vs intrinsic 固有"的解析差异（两事实：类型值 vs
  定义性）；② **Arg 序列化移入函数 scope**（scope 语义修正——arg 符号归属函数体
  scope，此前 pop 后序列化是既有错误面，节点池 uid 不受影响[内容确定性]）；③
  **RecordMode 三态 = 位置语义显式化**（值/返回注解/参数注解三位置的绑定规则差异是
  Python 实证事实，以模式参数承载，非散落 if）；④ **零风险加法式**（Rust 侧扩展面
  + 测试新增，不动 Python 执行路径/FlatSerializer/语义层）。**验证**：node_to_symbol
  **34 语料 262/262 全量多重集对齐 0 DIFF**（node_to_type 635/635 + scope 符号 43/43
  + owned_scope 52/52 + 节点池 829/832 + intrinsic 面全回归无损）；diff_harness
  40 passed[+1 node_to_symbol 门] + smoke 832 passed 零回归（全量 pytest 见放行门
  实跑）。**第三批剩余**：free_vars 闭包捕获 / method 符号[sym_anon_* content_hash
  偏离白名单] / generic+用户类型条目 / modules 组装[完整 artifact 闭环]。
- **P9 全量 Rust 化第三批 子项 2b-2b-2 增量 3（Rust 独立 artifact 产出：free_vars
  闭包捕获 + 定义节点 UID 统一遍历化 + divergence 注册表 GAP 清零，2026-09-11，本
  session，unsafe-vibe-dev）**：**free_vars 闭包捕获**（消除节点池 free_vars 排除
  GAP）+ **定义节点 UID 计算统一遍历化**（根因修复 symbol_resolver 事后重序列化）+
  **divergence 注册表 GAP 3 → 0**（free_vars 2 处 GAP 本增量消除 + 非字面值 type_uid
  GAP 已过期移除——用户 2026-09-11 裁定"过期测试资产可自由处理"适用面）。**侦察实证**
  （Python 语料 free_vars 分布）：① 语料面唯一定点 = closure_capture 的 get 函数
  （free_vars = [['a', 'scope___string_exec__/make:a']]——**[name, 定义符号 uid] 二元
  组**，非纯名字列表）；② **全局引用非自由变量**（closure_top_global：get_a 引用顶层
  a 无 free_vars——Python 闭包语义：free = 外层函数 scope，非全局）；③ 嵌套函数体
  引用归嵌套函数自身（外层不重复捕获）；④ 参数注解/返回注解名字 = 定义处 scope 求值
  （引用收集含注解，不含嵌套体）。**交付**：
  - **NodeSerializer free_vars 计算**（FunctionDef 分支，scope 上下文内）：函数体引用
    收集（collect_refs/collect_refs_stmt/collect_refs_expr——不进入嵌套函数体[归嵌套
    函数自身]，但收集嵌套函数参数默认值/返回注解引用[注解在定义处 scope 求值]）−
    函数自身 scope 定义（pop 前捕获 own_names）→ 命中外层函数 scope（排除顶层 index
    0 = 全局引用）→ [name, scope_<定义 scope 串>:name]；BTreeSet 序确定性。
  - **定义节点 UID 统一遍历化（根因修复）**：NodeSerializer 加 def_node_uids
    [符号 uid → 定义节点 uid，首次定义优先]——统一遍历中在 scope 上下文内记录
    （IbAssign 目标→IbAssign 节点 / IbFunctionDef 名→IbFunctionDef 节点 / IbArg→
    IbArg 节点 / for 目标→IbFor 节点 / ClassDef 名→IbClassDef 节点 / import 绑定→
    无定义节点）；symbol_resolver 改消费 def_node_uids_map（**删除 DefNode 事后重
    序列化机制**——根因：嵌套函数 IbFunctionDef 节点的 free_vars 只在定义处上下文可
    正确产出，事后顶层上下文重序列化产 free_vars=[] → 节点 UID 链式差异[既有
    closure node_uid gap 的根因]；DefNode/def_nodes/生命周期 'a 整体移除，死代码
    清理）。
  - **死代码清理**（code-quality 红线，本增量顺带）：infer_type（零消费者）+
    EMPTY_MODULES（唯一消费者 = infer_type）+ builtin_function_names（NodeSerializer
    改 intrinsic_names 63 后零消费者）+ symbol_resolver 未用 Arg import。
  - **divergence 注册表收缩**：gap-node-pool-free-vars / gap-scope-node-uid-closure
    （free_vars 对齐消除）+ gap-scope-type-uid-non-literal（第二批 43/43 收束后过期）
    移除——**GAP 计数 3 → 0**（全部已知缺口收束；节点池比对全字段含 free_vars，
    scope node_uid 比对含 closure_capture）；TestDivergenceRegistry 自检同步
    （query 空集断言 + 合成声明注入证明注册表仍驱动逻辑[非死代码]）。
  **关键裁定（self-grill 全分支消解）**：① **def_node_uids 统一遍历记录 vs 事后重
    序列化**——前者是根因修复（scope 上下文内产出 = 节点内容正确性的必要条件），
    后者机制上无法承载 scope 相关节点内容（free_vars/未来更多），违反机制同构
    （同一遍历两次走）——原则优先于行为维持；② **free_vars = [name, 定义符号 uid]
    二元组**（Python 实证形态忠实转录，非简化为纯名字列表——artifact 消费面需要
    uid 引用）；③ **顶层排除 = 闭包语义**（非"保持 Python 行为"迁就，是 Python/
    IBCI 共同的词法作用域闭包定义——自由变量 = 外层函数 scope，全局 = 直接引用）；
    ④ **GAP 清零 = 注册表纪律执行**（批次落地即移除声明；过期声明移除——用户裁定
    适用）；⑤ **零风险加法式**（Rust 侧 + 测试面变更，不动 Python 执行路径/
    FlatSerializer/语义层）。**验证**：节点池 **34 语料全字段（含 free_vars）内容
    集合等价**（closure_capture 3 节点 UID 链式差异消除 = 835/835 全对齐）+
    scope 符号 node_uid **52/52 全对齐**（closure_capture 纳入比对）+ node_to_type
    635/635 + node_to_symbol 262/262 + scope 符号 43/43 + owned_scope 52/52 全回归
    无损；diff_harness 40 passed + smoke 832 passed + 全量 pytest 零回归（flaky
    判别：test_replay_field_linked 并行负载下子进程 spawn 时序偶发失败，隔离重跑
    6/6 通过 = 非回归，与 test_p7_process_isolation/test_run_result_type 同类；
    放行门以清理后全量实跑为准）。**第三批剩余**：method 符号[sym_anon_*
    content_hash 偏离白名单] / generic+用户类型条目 / modules 组装[完整 artifact
    闭环]。
- **P9 全量 Rust 化第三批 子项 2b-2b-2 增量 4（Rust 独立 artifact 产出：types 池
  members_uids 成员面 35 类型 244 成员 uid 逐条精确等价 + Python 匿名符号 canonical
  内容哈希根因修复[既有缺陷：artifact 身份非 canonical]，2026-09-11，本 session，
  unsafe-vibe-dev）**：**types 池成员面**（members_uids——intrinsic 类型池 66 基础
  字段之上的成员符号引用面）。**既有缺陷发现（侦察实证）**：Python 匿名符号（类型
  成员 method/field + __string_exec__ 用户模块成员）的 uid = `hash(str(sym)) &
  0xFFFFFFFFFFFFFFFF`（serializer._collect_symbol fallback）——**PYTHONHASHSEED 进程
  随机 → 同 corpus 跨进程 members_uids 指纹不同（3 进程实证）→ artifact 身份非
  canonical**（违反 P3 artifact 内容寻址不变量[identity = canonical sha256 全摘要] +
  双内核差分协议的跨进程可比性前提）。**根因修复（变化前后详记）**：
  - **变化前**：`_collect_symbol` 匿名分支 = `get_content_hash`[无实现] →
    `hash(str(sym))`[进程随机]；成员 uid 跨进程漂移；members_uids 不可差分。
  - **变化后**：匿名分支 = **canonical 内容哈希**（与 node_uid 同机制——设计语言
    统一：内容确定性）：content = {kind, metadata, name, node_uid, owned_scope_uid,
    type_uid, owner_type_uid[声明类型 uid，_collect_type 成员循环传入]} 的 canonical
    JSON（json.dumps sort_keys + compact separators）→ sha256[:16] →
    sym_anon_<hash>；成员符号 metadata 固定 {}、type_uid/node_uid/owned_scope_uid
    固定 null（全语料实证），content 实变 = owner_type_uid + name + kind。
  - **owner 分量**：同名成员跨类型区分（str.len vs dict.len vs list.len——实证 3 类
    各含 len）；owner = 声明类型 uid（type_root.<name>，确定性）。
  - **影响面**：anon_symbol_uid 唯一消费方 = _collect_symbol（grep 实证）；格式
    不变（sym_anon_<16hex>，contracts/test_uid_generator 仅断言格式✅）；artifact
    自洽（uid = 池内引用键，全量再生成）；缓存原子性（artifact 整体换代，无跨代
    混合）。
  **交付**：
  - **intrinsic_symbols.rs**：METHOD_MEMBERS 静态成员表[35 类型 / 244 成员，转录自
    IBCI 公理层声明式成员表，全语料实证跨语料稳定；(type name, [(member name,
    kind)]) 字母序] + anon_member_uid[canonical 内容哈希，键序 owned_scope_uid <
    owner_type_uid[d<r]——首跑因键序错位 1 次后修正] + builtin_intrinsic_types 扩
    members_uids[35 类型；泛型条目继承基类表[owner uid 区分]归后续]。
  - **serialization.rs**：hash_prefix 转 pub + anon_symbol_uid[与 Python 同构]。
  - **差分 harness**：test_intrinsic_type_pool 扩 members_uids 断言（uid 逐条精确
    等价——双方同一 canonical 哈希）；__string_exec__ 用户模块成员面（用户顶层符号，
    随语料变化）经 divergence 注册表声明 GAP（gap-entry-module-user-members，
    TYPE_MEMBERS 新面）——归 modules 组装增量。
  **关键裁定（self-grill 全分支消解）**：① **canonical 内容哈希替代进程 hash =
  根因修复非行为维持**（历史非权威——旧 uid 机制使 artifact 身份不可判定，属 IBCI
  自身设计缺陷，可推翻[工作模式定论 7]；修复方向 = 与 node_uid/asset_uid 同一
  内容确定性机制[设计语言统一]，非发明新方案）；② **owner 分量 = 区分性必要**
  （同名成员跨类型实证；owner = 类型 uid 而非裸名——与池内引用键同构）；③ **静态
  成员表 = 公理转录**（与 66 类型池/intrinsic 符号表/方法返回类型表同模式——Rust
  独立 artifact 产出的固有面；权威源 = IBCI 公理，差分门 = 安全网）；④ **Python
  生产路径变更经全量 pytest 门**（序列化面变更 = 红线场合；smoke + 全量双验）；
  ⑤ **__string_exec__ 用户面归 modules 组装**（固定产出面无 source 输入——机制边界
  清晰，GAP 声明登记非隐式排除）。**验证**：members_uids 35 类型 244 成员 **uid
  逐条精确等价 0 DIFF**（跨进程 3 次同指纹）+ intrinsic 66 基础字段回归无损 +
  node_to_type 635/635 + node_to_symbol 262/262 + 节点池全字段 + scope 52/52 全
  回归无损；diff_harness 40 passed + smoke 832 passed + 全量 pytest 零回归（放行门
  实跑）。**第三批剩余**：generic/用户类型条目（泛型 members[owner uid 区分] +
  __string_exec__ 用户模块成员）+ modules 组装[完整 artifact 闭环——消除"消费
  Python 前端 JSON"输入边界]。
- **P9 全量 Rust 化第三批 子项 2b-2b-2 增量 5（Rust 独立完整 artifact 产出闭环——
  第三批收官，2026-09-11，本 session，unsafe-vibe-dev）**：`full_artifact(source)`
  pyfunction——Rust 从源码独立产出完整 artifact JSON（顶层形态与 Python
  FlatSerializer.serialize_artifact 同构），**34 语料全池精确等价**（nodes /
  symbols / scopes / types / assets 五池 uid 精确 + 全字段；module 条目 side_tables
  值多重集 + root uids + import_star_members + pools；entry_module / global_symbols）。
  **消除"消费 Python 前端 JSON"输入边界**——双内核差分协议进入 Rust 独立 artifact
  产出阶段（后续批次 = 值对象 / KB 推理面 / CPS 同构，非 artifact 产出面）。
  **交付**：
  - **lib.rs**：full_artifact 组装（NodeSerializer 统一遍历[nodes + side tables +
    泛型/用户面] + scope_serializer[scopes 池] + SymbolResolver[scope 符号] +
    intrinsic_symbols[63 符号 + 类型池 + 成员符号]；types 池键 = 类型 uid）。
  - **intrinsic_symbols.rs**：METHOD_SIGS 方法声明签名表（35 类型 / 223 方法——
    公理层声明式方法表转录，错误类继承面合并）+ method_signature 查表 +
    type_entry 全字段构建（kind 载荷：函数签名 / 类 parent[CLASS_PARENTS 16 条] /
    callable_instance axiom_name / list-dict-tuple-optional-channel-slot-thread-
    generator payload[裸 = any] / subscriber members-only / exported_types 恒 []）+
    generic_type_entry（list[T] / dict[K,V] / tuple[T,...]——payload 实参 + members
    继承基类表[owner uid 区分] + tuple positional 表[element = any]）。
  - **type_inference.rs**：method_signature_specialized（**public core 泛型成员特化
    协议转录**——core/kernel/spec/generic.py 的 resolve_member 回调：list[T] 的
    pop/__getitem__ → T、append/insert/__setitem__ 末参 → T；dict[K,V] 的 get/pop →
    V、values → list[V]、keys → list[K]；Optional[T] 的 unwrap/or_else → T[or_else
    首参]；thread/T 的 join → thread_result[T]、unwrap → Optional[T]）+
    bound_method_rewrite（attribute_type 判定单一权威源）+ attribute_type 转 pub。
  - **node_serializer.rs**：bound_method_sig last-wins 记录（方法属性访问即触发——
    Full 模式）+ method_returns[泛型闭包种子] + 泛型闭包产出
    [generic_type_names：类型环境值 + 方法特化返回种子 → payload 实参展开] +
    用户函数类型条目[user_function_entries：全深度 FunctionDef + from-import 函数
    绑定，USER_DEFINED + IMPORT_GATED + 注解签名] + __string_exec__ 用户模块类型
    条目[entry_module_type_entry：用户顶层符号成员，函数 → method 其余 → field——
    from-import 函数绑定亦 method；空成员键省略] + IMPORT_GATED 条件包含
    [called_module_functions：meta.X() 属性调用 → X KERNEL 函数类型进池；
    imported_modules：import meta → meta 模块类型进池；from-import 裸名调用只产
    USER 条目] + top_functions / user_functions / called_module_functions /
    bound_method_sig / method_returns 字段。
  - **scope_serializer.rs**：函数 scope 由 AST 结构枚举（每个函数定义建 scope
    条目——**含空符号 scope**，Python 实证；替代符号分组推导——空 scope 消失
    缺陷修复：closure_capture 的 make/get）。
  - **symbol_resolver.rs**：FUNCTION/MODULE/CLASS/from-import 符号 type_uid =
    type_root.<name>（此前仅 VARIABLE 绑定 type——FUNCTION/MODULE 符号 type_uid
    空缺陷修复）。
  - **差分 harness**：test_full_artifact_corpus（34 语料全池精确等价 + file_path
    规范化[Python 编译临时路径副产物，既有声明的非对齐偏离]）；test_intrinsic_
    type_pool 升级完整条目等价（全字段）；divergence 注册表 gap-entry-module-user-
    members rationale 更新（完整 artifact 面已承载用户成员，GAP 仅指固定产出面）。
  **Python 参考内核既有缺陷再发现（bound_method 共享单例就地改写）**：types 池
  bound_method 条目（单一共享 TypeDef）的 param_type_names / return_type_name 随
  **源序最后一个方法属性访问**改写（last-wins；受控实验 strip/keys 顺序敏感 +
  属性访问未调用亦改写 + 容器方法 params 按泛型协议特化[list[int].append →
  ['int']、dict[str,int].keys → ret list[str]]）——**types 池内容依赖书写顺序 =
  artifact 内容非 canonical**（与工作模式定论"靠书写顺序掩盖数据依赖"同型缺陷，
  且使 artifact 身份对源码等价重排不稳定）。迁移期裁定：**Rust 忠实复现**
  （统一遍历源序 = 与 checker 遍历同序，实证 34/34 对齐）；根因修复（bound_method
  条目签名独立化/稳定化）= 后续架构裁定项（触及公理层 spec 建模，按红线场合
  全量评估后推进）。**验证**：full_artifact 34/34 全池精确等价 + 全部既有差分门
  回归无损（node_to_type 635/635 + node_to_symbol 262/262 + 节点池全字段 + scope
  52/52 + intrinsic 66 完整条目 + members_uids）+ diff_harness 41 passed +
  smoke 832 passed + 全量 pytest 零回归（放行门实跑）。**第三批 = 完成**
  （2b-2b-2 增量 1-5：node_to_type 完整面 → node_to_symbol → free_vars/def_node_
  uids/GAP 清零 → members_uids + canonical 哈希根因修复 → 完整 artifact 闭环）。
- **P9 全量 Rust 化第四批设计（值对象去 Host 化——IbValue 值域封闭，2026-09-11，
  本 session，unsafe-vibe-dev）**：设计阶段文档 `tasks_docs/_value_objects.md`
  （落地后按治理纪律收敛/删除）。**现状盘点**：IbValue 8 变体 = 7 原生
  [Int/Float/Str/Bool/None_/List/Dict] + 1 Host(Py<PyAny>)——值域已 ~75% 原生，
  from_py 边界转换器已就位；Host 残差面 4 类[KB 对象 41 成员 / 模块对象[语料面仅
  meta] / quoted[q.source 经 host_getattr] / 宿主方法属性比较真值类型名分支]。
  **面分解裁定**：① quoted = Quoted{source} 原生变体；② meta 模块对象退役——
  quote/eval/compile 直接 intrinsic 分发；③ **eval 语义 = Rust parser + interpreter
  原生闭环**（source → artifact → 执行，与 2b-2b-2 完整 artifact 闭环机制同构——
  不发明新求值器）；④ KB = Rust 原生数据模型（公理层 41 成员表转录，Python KB =
  差分参照非真相源）；⑤ **embedding 端点保留 Host IO 边界**（LLM IO = 用户裁定面）。
  **增量序列**：增量 1 quoted+meta 原生面[差分探针 = quoted 3 语料] → 增量 2 KB
  Rust 原生数据模型[2a facts / 2b worlds / 2c embeddings+vector，差分探针 = kb
  3 语料；vec intrinsic 顺带实现] → 增量 3 Host 变体退役[执行面 Host 分支全删，
  边界值即过即转]。**登记缺口**：vec intrinsic 未在 Rust 解释器实现（34 语料无
  用例，非阻塞，增量 2 顺带）。红线 = 语义单一权威源（公理转录）+ 迁移期差分门
  零差异放行。
- **P9 全量 Rust 化第四批 增量 1（值对象去 Host 化：quoted + meta 模块原生面，
  2026-09-11，本 session，unsafe-vibe-dev，设计 = tasks_docs/_value_objects.md）**：
  meta 函数面（quote/eval）+ quoted 值 + q.source 属性 **去 Host 化**——Rust 执行面
  原生闭环（bridge=None 下 4 语料数据面等价实证）。**实施**：
  - `IbValue::Quoted { source: String }` 变体（不可变值；相等 = 源串逐字节精确对比
    [公理]；repr = 完整源串[同 __to_prompt__ 数据面忠实呈现]；真值 = true）+
    `IbValue::MetaFn(&'static str)` 变体（from meta import quote/eval 的原生函数
    引用绑定值）。clone/debug/cmp/repr/truthy/to_py[quoted 跨边界 = source 串，同
    to_native 边界拆箱契约] 全臂。
  - **quote 验证门转录**（HostService.quote_expression 契约——包装体
    `__qeval__ = <source>` compile-only 门等价）：① 非空 str ② parse 语法 ③
    表达式性[module = 单 ExprStmt] ④ 自包含性[collect_refs_expr 自由名 ⊆ intrinsic
    63——fresh scope 无用户绑定，引用父模块自由名即 fail-fast 等价]。零 LLM
    （compile-only 同契约）。
  - **eval 隔离执行转录**（HostService.eval_quoted 契约——子进程独立引擎 + 值通道
    结果槽）：fresh Environment（无用户全局——自包含门已保证）+ 值通道取回表达式
    值 + silent stdout 面丢弃（同 silent=True）。**裁定（进程隔离 vs scope 隔离）**：
    子进程进程级隔离 = 资源治理面，数据面语义等价 fresh scope 隔离——语料零 LLM /
    零跨进程状态依赖（KB/LLM 态不经 quoted 面）；资源治理差异登记于限制面。
  - 分发拦截：Call Attribute func（value = Name "meta" + attr ∈ {quote, eval}）+
    Call Name func（env 值 = MetaFn）→ call_meta_fn 原生分发；FromImport meta 绑定
    = MetaFn（非宿主属性取值）；Attribute q.source = 原生字段访问。
  **登记限制（非本增量范围）**：验证门失败 / eval 运行错误 = None_ 静默（Rust
  解释器无错误传播面——InterpreterError 值语义[try/except 可捕获] = 跨切面后续
  增量；34 语料无错误探针，数据面无偏离；bridge 失败面同为 unwrap_or(None_) 惯例）。
  **验证**：test_data_plane_quoted_native[新增——quoted 4 语料[import meta 3 +
  from meta import 1]**无桥接**数据面等价：bridge=None 证明 meta 函数面去 Host 化
  完成] + 全差分 harness 42 passed + smoke 832 passed + 全量 pytest 4300 passed /
  1 skipped 零回归（141.47s，放行门实跑）。**值域 Host 残差收缩**：KB 对象 +
  宿主方法/属性/比较/真值分支（quoted/meta 面已除）——第四批增量 2 = KB Rust 原生
  数据模型。
- **P9 全量 Rust 化第四批 增量 2a（值对象去 Host 化：KB 语料面 Rust 原生数据模型，
  2026-09-11，本 session，unsafe-vibe-dev，设计 = tasks_docs/_value_objects.md）**：
  KB 执行面（knowledge() 值 + 语料面 10 方法）去 Host 化——Rust 原生 KB 值
  （KB 3 语料无桥接数据面等价实证）。**实施**：
  - **ibci-ext/src/kb.rs（新模块）**：KbState（治理词表 words/relations/worlds
    [插入序 = 确定性枚举序] + append-only 事实日志 facts[seq 前置自增，fact_id =
    str(seq)] + active 倒排索引 by_pair[(s,r) → 事实下标] / by_triple[(w,s,r,o) →
    事实下标][派生视图——日志是权威]）+ KbWord/KbRelation/KbWorld/KbFact/KbEvent
    记录；dispatch 方法面（register_world/register_relation/register_word[参数形态
    门 + 重复登记拒绝] / worlds/words[插入序枚举] / add_fact[治理门：词表
    allowlist——world/relation/s/o 全注册 + 去重门：同 (w,s,r,o) active 唯一；
    缺省 source=""/status="active"] / exists[by_triple 成员检查] / lookup_pair[
    by_pair 全部 active 事实记录] / contradicts[关系未注册拒绝 + multi_valued 恒
    非矛盾 + 同 (s,r) 存在 active o'≠o]）——语义转录自 Python 参考内核
    knowledge.py（单一权威源 = IBCI KB 声明；零 LLM 机器强制治理门）。
  - **interpreter.rs**：IbValue::Knowledge(Rc<RefCell<KbState>>) 变体（共享可变
    容器——同 List/Dict 机制；clone = Rc 共享引用；相等 = 身份[ptr_eq]；repr =
    "<knowledge>"）；knowledge() intrinsic → 原生空白 KB（call_knowledge 去桥接）；
    call_method Knowledge 分支 → kb::dispatch。
  - **差分 harness**：test_data_plane_kb_native 新增（KB 3 语料无桥接数据面等价——
    bridge=None 证明 KB 面去 Host 化完成）；test_data_plane_kb_corpus（桥接版）
    删除（过期——KB 面不再经桥接；按 2026-09-11 用户裁定"过期测试脚本可自由
    处理"）；test_data_plane_full_corpus 改全原生无桥接（34 语料全 native——
    宿主桥接仅余 LLM/意图 IO 边界，语料面零依赖）；bridge.py / harness.py
    docstring 更新（边界语义收窄声明）。
  **KB 语料面数据面形态对齐实证**：lookup_pair 事实记录 = Dict[键序 id/world/s/
  r/o/source/status/events——Python 事实 dict 插入序同构] + events 事件链
  [seq/kind/reason/new_o(None)]；worlds()/words() = 插入序 list[str]；exists/
  contradicts = bool——全对齐。
  **登记限制（非本增量范围）**：① 错误面 = None_ 静默（同增量 1——治理门失败/
  参数形态错误不产生 InterpreterError 值语义；语料无错误探针，数据面无偏离；
  错误传播面 = 跨切面后续增量）② KB 全 41 成员面未齐（语料面 10 方法 + 枚举面
  已载；amend_fact/retract/transitive/embedding 面 = 增量 2b/2c）③ embedding
  端点 = LLM IO 边界保留（HostService——用户裁定面）。**验证**：KB 3 语料无桥接
  数据面等价 + quoted 4 语料无桥接回归无损 + 全 harness 41 passed + smoke 832
  passed + 全量 pytest 4299 passed / 1 skipped 零回归（139.02s，放行门实跑——
  净 −1 = 删过期桥接测试）。**值域 Host 残差**：宿主对象变体仅 LLM/意图 IO 边界
  消费（语料面 = 0）。
- **P9 全量 Rust 化第四批 增量 2b（值对象去 Host 化：KB 查询/审计/对比/展开/传递
  面，2026-09-11，本 session，unsafe-vibe-dev，设计 = tasks_docs/_value_objects.md）**：
  kb.rs dispatch 扩 13 方法——**词表查询面**（word/relation/world 记录查询，未注册
  = None 合法态非错误——记录 = 词{lexeme/gloss/is_set/members/entries} / 关系
  {type/semantics/transitive/multi_valued} / 世界{name/description/size_rank}）+
  **事实查询面**（get_fact 权威形态[含全事件链] / facts 全日志[seq 序，含 retracted
  墓碑] / fact_len / all_in_world[active 视图 seq 序] / source / history_fact 事件
  链）+ **审计面**（retract：墓碑 status → retracted + 事件链 + active 图索引即时
  移除[by_pair 过滤 + by_triple 删键] + 已墓碑再 retract 拒绝 + reason 强制非空；
  amend_fact：o 版本化 + 事件链[new_o 留史] + new_o 词表治理门 + 索引仅在新 o
  变更且 active 时 by_triple 切换[by_pair 不变——(s,r) 未变]）+ **对比/展开面**
  （same_word：a==b 且均已注册；compare 确定性 4 层{exact/contradiction/scale/
  same_word}；expand 纯派生不存展开态：事实 + 主语/对象词记录 + 关系语义 + 世界
  上下文 + 跨世界词形 entries[world]，未登记 = 空 dict）+ **传递闭包面**
  （transitive：BFS 防环 + 确定性发现序[队列序] + via 中间对象链[不含端点] +
  非传递关系 = 空 list[诚实语义] + 关系未注册拒绝）。
  **差分门**：test_data_plane_kb_surface_snippets 新增（25 行自包含合成探针——
  语料集 3 条只覆盖 register/add_fact/exists/lookup_pair/contradicts/worlds/
  words 基础面；本探针覆盖全 2b 面：查询[含未注册 None] / 事件链[add → amend →
  retract 全史] / 索引更新语义[amend 后 exists/lookup_pair 切换；retract 后
  lookup_pair 空 + facts 全日志保留墓碑] / compare / expand / transitive[传递
  闭包 + 非传递空]——**无桥接全对齐一次通过**）。
  **验证**：合成探针 25 行全对齐 + KB 3 语料 + quoted 4 语料无桥接回归无损 +
  全 harness 42 passed + smoke 832 passed + 全量 pytest 4300 passed / 1 skipped
  零回归（141.63s，放行门实跑）。**KB 41 成员面进度**：词表 3 + 事实 4 + 查询
  9 + 审计 2 + 对比/展开 3 + 传递 1 = 22 方法原生；剩向量面[embedding 5 +
  向量运算] = 增量 2c。
- **P9 全量 Rust 化第四批 增量 2c（值对象去 Host 化：vector 值 + KB 嵌入面，
  2026-09-11，本 session，unsafe-vibe-dev，设计 = tasks_docs/_value_objects.md）**：
  向量面全原生（41 成员面收官面——KB 全 41 成员面 = 22[2a+2b] + 5 嵌入面[2c] +
  向量类型 10 成员[2c] 全载）。**实施**：
  - **IbValue::Vector(Vec<f64>) 不可变值**：值语义相等（元素逐位）；显示面 =
    截断摘要 `vector[<dim>](前 8 维 %.6g, ...)`（同 __to_prompt__/_string_repr
    ——全量维度进提示词 = 污染风险，截断即纪律）；真值 = 非空。
  - **format_g6 = Python `%.6g` 等价助手**（C %g 语义转录：6 位有效数字；
    -4 ≤ 指数 < 6 = 定点 + 尾零截断，否则科学计数法[e±两位指数]）——vector
    显示面单一权威源；非有限值 = Rust Display（vector 构造期封死 NaN/Inf——
    公理契约，语料面不可达）。
  - **vec intrinsic**（元素面数值校验：Int/Float 元素，非数值 = None_[错误面]）。
  - **vector 方法面**（dim/dot/norm/cosine[零范数 fail-fast 面]/scale/add/sub——
    修改操作返回新 vector[不可变值语义] + 维度一致门 + 下标元素 float）。
  - **KB 嵌入面**（kb.rs +5 方法 + embeddings 存储[词 → float 向量，插入序]）：
    set_embedding[治理门：词已注册 + 数值向量 + 维度全一致——首个嵌入定维度；
    同词重设 = 替换] / embedding[未挂 = None_[fail-fast 面]] / has_embedding /
    embedding_dim[全一致取任一] / embed_search[query 须 vector 值 + k 正整数；
    暴力 cosine + 维度不符跳过 + (−score, word) 确定性排序[tie-break] + top-k
    截断[k 超 = 全量]；返回原生结构 list of {word, score}]。
  **裁定（vector.cast_to 执行面不可达）**：cast_to 目标 = 类对象（`v.cast_to(str)`
  的 str 经 VM 类型名解析为 class 对象——Rust 值域无类对象面，执行面不可达 =
  类型面[artifact]职责）；用户调用 `v.cast_to("str")` = 非法 IBCI（Python 参考
  fail-fast 实证：AttributeError → InterpreterError）→ 执行面 dispatch 不含
  cast_to（死代码红线——不承载不可达面）。**裁定（embedding 文本端点）**：
  ai.embed 文本 → 向量 = LLM IO 边界保留（HostService 契约；语料面零依赖——
  嵌入面语料 = 显式向量 set_embedding）。
  **差分门**：test_data_plane_vector_surface_snippets 新增（22 行自包含合成探针
  全对齐一次通过——%.6g 全形态[1.23457e+06 / 1.23456e-05 / 1e+20 /
  -0.000123456 / 3.14159e+07 / 尾零截断] + 9 维截断摘要[...] + 浮点最短往返
  repr[dot 32.0 / norm / cosine] + embed_search 排序 + top-k 截断）。
  **验证**：合成探针 22 行全对齐 + KB 3 + quoted 4 + 2b 探针 25 行无桥接回归
  无损 + 全 harness 43 passed + smoke 832 passed + 全量 pytest 零回归（放行门
  实跑）。**值域封闭进度**：8 → 10 原生变体（+Quoted/MetaFn 增量 1、+
  Knowledge/Vector 增量 2）；Host 残差 = 仅 LLM/意图 IO 边界消费。
- **P9 全量 Rust 化第四批 增量 3b（CPS 覆盖差收缩 31→36：5 节点移植，2026-09-11，
  本 session，unsafe-vibe-dev，设计 = tasks_docs/_value_objects.md）**：Rust 执行
  核心 CPS 分发扩 5 节点（Python VM dispatch 50 handler 对照，覆盖差 19→15）：
  **IbGlobalStmt/IbNonlocalStmt**（`global x[, y]` / `nonlocal x`——编译期语义，
  运行时无操作[语义效果经符号解析在编译期完成，运行期赋值经作用域链自然穿透]）；
  **IbRaise**（`raise [exc]`——异常对象求值；错误面登记：Rust 解释器无异常
  传播机制[ThrownException/Try 捕获语义 = 跨切面后续增量]，语料面无 raise）；
  **IbSwitch + IbCase**（`switch <test>:` + `case <pattern>:` / `default:`——
  匹配后自动跳出[无 fall-through]；case 内 break = no-op[C 习惯，接受为退出
  case]；Return 透传；Continue 透传外层循环[switch 本身不是循环]；pattern 值
  相等匹配，default = 无 pattern）。**实施面**：lexer（switch/case/default
  token）+ parser（parse_switch 缩进块 + Case 节点 + 3 语句）+ deserializer
  （5 节点数据反序列化——names 裸串数组 / cases uid 数组 / pattern null =
  default）+ node_serializer（节点内容——**IbCase 位置 = switch 关键字位置**
  [Python 序列化器约定：case 节点复用 switch start_token，语料实证全部 case 同
  位置] + end 位置 = 0）+ interpreter（执行语义）。**差分门**：
  test_data_plane_switch_global_snippets 新增（3 探针：case 2 匹配 + break no-op
  + 无 fall-through；continue 透传外层循环[while 内 switch]；global/nonlocal
  no-op 读取面）+ switch 源 full_artifact 五池全等价实证（nodes 35 / symbols
  306——含 IbSwitch/IbCase 节点内容 + 位置约定全对齐）。**登记缺口（非本增量
  范围）**：① 声明面 `TYPE x = v`（IbTypeAnnotatedExpr——auto/fn/泛型注解/
  元组解包）= Rust parser 既有缺口[语料面零覆盖，探针规避；移植 = 后续 parser
  增量——实证：Rust 将 `int x = 2` 误解析为 ExprStmt(int) + Assign(x=2)]；② LLM
  面 15 节点覆盖差（IbCastExpr[类型注解消歧复杂] + IbRetry/IbIntentAnnotation/
  IbImplDef/IbProtocolDef/IbHostImport/IbBehaviorExpr/IbChannelExpr/IbAwaitExpr/
  IbYieldExpr/IbYieldFromExpr/IbFilteredExpr/IbSlotExpr/IbIntentStackOperation/
  IbWithOverlay——LLM/意图/宿主运行时面 = 协程/通道/行为深度语义，归 LLM 运行时
  移植批次）；③ raise 错误面（异常传播机制 = 跨切面增量）。
  **验证**：3 探针全对齐 + 34 语料回归无损 + 全 harness 44 passed + smoke 832
  passed + 全量 pytest 4302 passed / 1 skipped 零回归（144.42s，放行门实跑）。
- **P9 全量 Rust 化第四批 增量 3c（声明面移植：TYPE x = v 变量声明，2026-09-11，
  本 session，unsafe-vibe-dev，设计 = tasks_docs/_value_objects.md）**：Rust
  parser 声明面——**`TYPE x = v` / `auto x = v` / 泛型 `list[int] xs = v` /
  `TYPE x: TYPE2 = v` 显式覆盖**（auto = 值推导；声明类型优先于推导）。
  **实施面**：
  - **parser**：声明面前瞻 is_var_declaration（TYPE [ [ typeargs ] ] x (=|:)
    识别——类型名 + 可选泛型括号深度匹配 + 变量名 + =/:）+ parse_declaration_
    identifier / parse_declaration_auto（Auto token 独立臂）+ parse_type_
    annotation（IDENT [ [ typearg, ... ] ]；多参 = IbTuple[ctx Load]；位置 =
    类型名 token——泛型节点 end = 类型名 end，非括号跨度，Python 位置约定实证）
    + Expr::TypeAnnotatedExpr{target: Name(Store), annotation}（位置 = 类型起始
    token；IbAssign 位置 = 类型起始 token，end = 0[Python 声明 Assign 位置
    约定，实证]）。
  - **node_serializer**：IbTypeAnnotatedExpr 节点内容 + 声明 Assign 绑定面
    （Python 实证裁定：注解节点仅顶层 node_to_type[泛型内层名字不单独绑定——
    ser_annotation 内层 None 记录 + 顶层 = type_root.<注解串>，含 auto →
    type_root.auto]；annotated 节点 + 值节点 node_to_type = 声明类型[auto =
    符号通道推导]；target name + annotated + Assign 节点 node_to_symbol → 定义
    符号；Assign 节点不绑 node_to_type[实证：仅 annotated/值/注解]；符号
    type_uid = 声明类型[auto = 推导]）。
  - **symbol_resolver**：声明 target 解包（TypeAnnotatedExpr → 内层 Name）+
    声明类型优先绑定（annotation_type_str 单一权威源[node_serializer 导出]，
    auto = symbol_level_type 推导）。
  - **interpreter**：声明 target = 运行时纯赋值（注解仅类型/编译期语义，值域
    不消费——Assign 臂 effective target 解包）。
  - **deserializer**：IbTypeAnnotatedExpr 节点数据反序列化。
  **差分门**：test_data_plane_declaration_snippets 新增（顶层 + 函数内 scope
  双探针：数据面 = 运行时纯赋值对齐 + artifact 5 池[节点 33 / 符号 326 /
  类型 64] + node_to_type[20]/node_to_symbol[16] 侧表内容归一全等价——
  声明面全语义对齐一次通过[经 2 轮侧表绑定面修正：注解记录模式 + 泛型内层
  去绑定]）。
  **登记缺口（非本增量范围）**：声明面剩余形态——`fn f = ...` 可调用声明 /
  元组解包 `(int x, int y) = t` / 裸列 `int a, int b = t` / 点分类型
  `mod.Type` / chan/slot 类型[LLM 运行时面]。
  **验证**：2 探针全对齐 + 34 语料回归无损[Assign 臂重构面] + 全 harness 45
  passed + smoke 832 passed + 全量 pytest 零回归（放行门实跑）。
- **P9 全量 Rust 化第四批 增量 3d（声明面剩余形态 + 函数值一等化，2026-09-11，
  本 session，unsafe-vibe-dev，设计 = tasks_docs/_value_objects.md）**：
  ① **fn 可调用声明**（`fn f = g`——annotation = Name(fn)；符号/绑定语义同
  auto：值推导[type_root.g] + 注解节点 type_root.fn；**别名签名链**
  link_function_alias：f 的 func_sigs = g 的签名——Call f() 节点
  node_to_type = 返回类型[Python 类型检查器别名链语义实证]）。
  ② **元组解包声明**（括号 `(int x, int y) = t` + 裸列 `int a, int b = t`
  [前瞻 Comma 分支] + 函数内解包——目标 IbTuple[ctx Store]，位置 = LPAREN /
  首类型 token[Python 位置约定：end = 首 token end]；运行时 = 值 List 逐元素
  赋值；**解包绑定面裁定（Python 实证）**：target name 节点 node_to_symbol +
  annotated 节点 node_to_type = 声明类型（分量注解不绑 node_to_type——仅单
  声明注解进）+ Assign 节点不绑 symbol[单声明绑] + 解包值 node_to_type =
  推导 tuple 型[不覆盖为分量声明类型]；符号 node_uid = Assign 节点[同单声明]）。
  ③ **点分类型**（`mod.Type`——Attribute 链 + annotation_type_str 点分串）。
  ④ **函数值一等化（根因修复）**：fn 声明/普通赋值别名（`fn f = g` /
  `x = g`）暴露 Rust 函数仅驻 functions 表[值通道 env.get = None → 别名调用
  = None]——**IbValue::Function(Rc<Function>) 新值变体**（一等值：可赋值/别名/
  传参；Function 扩 param_types/ret 字段[显示面 source 形态
  `func <name>(<param types>) -> <ret>`——Python 实证：参数面仅类型名不含参数
  名，无返回类型省略 -> 段]；define_function 双写 functions 表 + vars 表；
  Call 分支经值调用[call_user_function 共享]；身份相等[Rc ptr_eq]；真值 =
  true；不经桥接）。
  ⑤ **types 池泛型条目触发面扩展**：generics 种子含 node_to_type 值
  [解包值 tuple[int,int] 仅经 node_to_type 引用无符号绑定——条目仍须进池；
  lib.rs 顺序修正：generic_type_names 先于 node_to_type_map[mem::take 取走
  语义，顺序敏感]]。
  **差分门**：test_data_plane_declaration_extended_snippets 新增（2 探针：
  fn + 括号解包 + 函数值显示/别名；裸列 + 函数内解包——数据面 + 5 池 + 2 侧表
  内容归一全对齐[3 轮修正：解包绑定面 / 泛型种子时序 / 前瞻 Comma]）。
  **登记缺口（非本增量范围）**：auto/fn 分量元组解包[Python 不支持——探针
  实证] / 可调用签名 `fn[(...) -> ...]` = IbCallableType / 普通赋值别名链
  `x = g` 的 Call 返回类型[类型检查器深度语义——数据面无偏离，仅 artifact
  node_to_type 差] / chan/slot 类型[LLM 运行时面]。
  **验证**：2 探针全对齐 + 函数值面独立探针全对齐（f()/g()/print(f)/x = g
  别名/参数化函数 repr）+ 34 语料回归无损[Function 值变体核心面] + 全
  harness 46 passed + smoke 832 passed + 全量 pytest 零回归（放行门实跑）。
- **P9 全量 Rust 化第四批 增量 3e（错误面统一——异常传播机制，2026-09-11，
  本 session，unsafe-vibe-dev，设计 = tasks_docs/_value_objects.md）**：Rust
  解释器异常传播机制（3b 登记的跨切面错误面增量落地——raise/try/except 全
  语义原生）：
  **① Thrown 值传播（架构面）**：exec_stmt/exec_body/eval_expr/eval_iter/
  call_function/call_user_function 全签名 Result<_, Thrown> 线程化（raise 求值
  后 Err(Thrown{value})；未捕获异常 = 模块边界降级为消息[Send 约束：Thrown 含
  Rc 非 Send——lib.rs run_artifact/run_artifacts_parallel/TaskPool 边界
  PyRuntimeError；meta.eval 隔离执行内 raise = 错误面 None_[登记]]）。
  **② IbValue::Error{class, message} 值变体**：异常对象（8 类构造器：
  Exception/LLMError/LLMCallError/LLMParseError/LLMRetryExhaustedError/
  ThreadError/ThreadCancelled/ThreadFailed——call_function 名分支；显示面 =
  `<class>: <message>`[无 message = 仅类名——Python IbException.__to_prompt__
  契约实证]；值语义相等；真值 = true；不经桥接）。
  **③ try/except/else/finally 全语义（Python VM IbTry 转录）**：raise 不做
  类型检查[值任意] + handler 类可赋性匹配[exception_assignable：值类型名 =
  handler 类型名或在继承链上——intrinsic_symbols::class_parent[CLASS_PARENTS
  传递闭包]；**原语类型不继承 Exception[Python 实证：raise 5 不被 except
  Exception 捕获，落入 except int]**] + 首匹配 handler + **异常变量全局绑定**
  [set_global_env parent 链顶——Python runtime_context.define_variable 全局面，
  越 try 块可见实证] + else 仅无异常且 body 无 signal + finally 所有路径执行
  且 signal 覆盖 pending + 无匹配 = finally 后 re-raise + handler 内再抛 =
  未处理（re-raise）。
  **④ artifact 面**：IbTry/IbExceptHandler 节点全序列化（handler type 表达式 +
  name + body 语句；e 符号 = VARIABLE/any/全局 scope[scope_stack 顶] + 定义
  节点 = handler 节点[Python 实证 node_uid] + node_to_symbol[handler 节点 +
  body 内引用]）+ IbRaise 节点 cause=null 字段 + 位置约定（raise 位置 = 关键
  字 end[实证]）。
  **⑤ 多参 print 修复（同批暴露的既有数据面缺口）**：print(a, b) = "a b"
  （repr 空格连接；无参 = 空行——Python print 语义实证；单参行为不变）。
  **差分门**：test_data_plane_exception_surface_snippets 新增（13 探针：
  raise+catch / 多 handler 首匹配 / finally / else / 嵌套 rethrow /
  finally+return / 变量泄漏 / Exception 基类不捕获原语 / 异常对象 / 继承链
  [LLMError→Exception / LLMCallError→LLMError] / 构造 msg / break 透传 +
  未捕获面双侧报错）+ try 源 full_artifact 5 池 + 2 侧表内容归一全等价
  （3 源实证）。
  **裁定（错误面统一登记限制收缩）**：原"治理门失败/参数错误 = None_ 静默"
  登记限制仍成立（Rust 内部治理错误不转 Thrown——语料面无内部错误探针）；
  **显式 raise = 可传播值**（本增量落地）；meta.eval 内 raise = None_（隔离
  执行错误面——同 2b 登记）。
  **验证**：13 探针全对齐 + try 源 3 全等价 + 34 语料回归无损[异常机制 +
  多参 print 核心面] + 全 harness 47 passed + smoke 832 passed + 全量 pytest
  零回归（放行门实跑）。
- **P9 全量 Rust 化第四批 增量 3f（全 Rust 管线闭环 + LLM 面边界裁定，
  2026-09-11，本 session，unsafe-vibe-dev，设计 = tasks_docs/_value_objects.md）**：
  **① 全 Rust 管线（主线 ⑦ 安全证明门）**：`rust_run_source(source, bridge)`
  pyfunction——IBC 源 → Rust lexer/parser → Rust artifact 组装
  （assemble_artifact_json）→ Rust 反序列化 → Rust 解释器执行；全程不消费
  Python 前端（消除"消费 Python 前端 JSON"输入边界——双内核输入面收敛为 Rust
  单通道的证明面）。assemble_artifact_json 从 full_artifact pyfunction 体抽出
  为共享权威源（签名裁定 `-> String`：Rust parser 非失败 + serde_json 对本
  Value 形态实质不可失败[仅非有限浮点报错——值域无浮点条目]）。
  **② LLM 面 15 节点边界裁定**：CPS 覆盖差 15 节点（IbCastExpr/IbRetry/
  IbIntentAnnotation/IbImplDef/IbProtocolDef/IbHostImport/IbBehaviorExpr/
  IbChannelExpr/IbAwaitExpr/IbYieldExpr/IbYieldFromExpr/IbFilteredExpr/
  IbSlotExpr/IbIntentStackOperation/IbWithOverlay）= HostService 边界保留面
  （非移植范围）——主线目标"仅 LLM/意图/宿主 IO 面保留 Python 接口"裁定；
  语料 + 全部差分探针零 LLM 节点；Rust 解释器数据面节点覆盖 = 全集（36 类）
  完整。**③ ⑦ 切换门登记**：engine 内核选择面切换（kernel_info.status 提升 +
  run 入口激活 + LLM/意图面 HostService 边界行为验证）= 独立放行门批次——
  本增量仅证明管线安全，不改变生产行为（run 仍 NotImplemented[双内核协议]）。
  **差分门**：test_full_rust_pipeline_equivalence 新增（34 语料 + 8 探针面
  数据面逐字节等价——全管线 vs Python 参考）。
  **验证**：34/34 语料 + 8/8 探针全管线等价 + 全 harness 48 passed + smoke 832
  passed + 全量 pytest 零回归（放行门实跑）。
- **P9 全量 Rust 化第四批 增量 3f 续：⑦ 切换门批次设计（2026-09-11，本
  session，unsafe-vibe-dev，设计 = tasks_docs/_p9_switch.md）**：
  **① engine 内核选择面侦察**：生产 engine 零 ibci_ext 消费（Rust 仅差分
  harness 验证面）——⑦ 切换 = engine 执行路径替换（engine.execute →
  run_string/compile_string → FlatSerializer → rt_scheduler.execute
  [Python 运行时调度器]）；engine 外围面（journal_writer/budget_guard/
  deterministic_guard/on_ready/variables/output_callback）= 切换门承载面。
  **② 切换门批次设计（v1，_p9_switch.md）**：目标架构 = 数据面 Rust 唯一
  执行者 + LLM/意图/宿主 IO 面 Python HostService；engine 路由 = 面分区
  （artifact 节点类型判定：无 LLM 面 15 节点 → Rust 内核[run_artifact +
  bridge]；含 → Python 运行时全源执行[单一内核归属纪律，无对比/无回退]）；
  HostService 桥接面 = 现有 bridge 机制承载（LLM 调用/意图/journal/budget；
  KB = Rust 原生不经桥）；LLM 面 15 节点 = Python 语义宿主（Rust 反序列化
  器不实现此 15 类[3f 边界裁定]；长期 b 模型 = Rust 语义 + IO 桥[非本批次]）；
  变量面 = 初始注入（py_to_ibvalue 转换面缺口）+ 数据面源执行后状态 = 仅
  print 输出（Rust 执行函数化——无残留态）；切换 3 阶段（每阶段独立放行门：
  ①engine 路由 + HostService 桥 + 初始变量 → ②Python 数据面 VM 退役
  [双通道消亡] → ③差分 harness 退场 + 基线重建）。
  **裁定（切换策略）**：面分区路由（非双通道 fallback）——每源按节点类型
  归属单一内核，维持双内核协议显式态纪律；阶段 1 实施 = 下一轮起点。
- **P9 全量 Rust 化 ⑦ 切换门批次 阶段 ① 增量 1a/1b（状态面 + 路由判定面，
  2026-09-11，本 session，unsafe-vibe-dev，设计 = tasks_docs/_p9_switch.md）**：
  **① Rust 状态面（⑦ 变量面契约——engine 路由前置能力）**：
  - `Interpreter::run_module_with_state`（初始变量 = 顶层环境预置 + 最终
    状态 = 顶层环境全条目导出）；`ibvalue_to_json`（原生数据值 = 原生
    JSON 形态；非数据值[Function/MetaFn/Knowledge/Quoted/Error/Vector] =
    显示形态字符串[repr 契约]）
  - `run_artifact_state(artifact_json, bridge, initial_vars) -> (输出列表,
    状态 dict)` pyfunction：**Send 安全设计**——初始变量 GIL 侧 py_to_json
    （Python 对象 → JSON）→ 线程内 json_to_ibvalue（IbValue 含 Rc 非
    Send——转换于 GIL 释放区内完成）；状态于线程内降级 JSON（ibvalue_to_json）
    → GIL 侧 json_to_py 还原
  - 验证：最终状态 vs Python 参考（engine runtime_context payload）等价 +
    注入数据面自洽（注入值可见 + 状态回读）+ 函数值 = 显示形态字符串 +
    异常变量全局绑定入状态（e=5）
  **② 路由判定面（⑦ 面分区）**：
  - `artifact_is_rust_executable`（harness）：artifact 节点类型全集 ⊆ Rust
    node_types = 数据面源（Rust 可执行）——**单一真相源 = Rust
    deserializer::node_types**（缺口集随 deserializer 演进自动正确，无
    Python 侧硬编码 LLM 面清单）
  - node_types 补 IbArg/IbAlias（arg_of/alias 内联消费节点——池节点不经
    build_node 分发但属处理全集；文档注记修正）；验证：34 语料 = 全 True +
    ihost 宿主面源 = False
  **③ 既有缺陷登记（PT-DEBT-37）**：engine run_string(variables=...) 运行时
  注入缺陷——编译面预知符号名 ✅ 但 VM 报 RUN_UNDEFINED_VARIABLE（rt_scheduler
  define_variable 注入未生效于 VM 符号 UID 查找面）——既有 Python 运行时缺陷
  （非 Rust 化引入）；⑦ 变量面契约 = Rust 状态面（本增量自洽验证）。
  **裁定（变量面契约）**：⑦ 切换后变量面 = Rust 状态面（run_artifact_state：
  初始注入 + 最终状态导出）——Python 引擎 variables 通道缺陷修复归 Python
  运行时批次（PT-DEBT-37）。
  **差分门**：test_rust_state_surface + test_rust_routing_decision 新增。
  **验证**：50 harness passed + smoke 832 passed + 全量 pytest 零回归
  （放行门实跑）。
## P9 ⑦-1c engine 路由接入 + 错误码对等 + 数据面语义缺口收敛（2026-09-11）

**⑦ 切换门批次 阶段 ① 增量 1c**：engine.execute 接入面分区路由（数据面源
→ Rust 内核执行 + 最终状态镜像；LLM/宿主面源 → Python 运行时）——生产行为
已切换（数据面执行真相 = Rust 内核唯一）。

**路由判定面（core/runtime/kernels/__init__.py——artifact_is_rust_executable
单一入口，全源按节点类型/导入/语义族路由至唯一内核）**：
- 基础判定：节点类型全集 ⊆（Rust node_types − 对象系统排除集 {IbClassDef,
  IbLambdaExpr}）且无宿主模块导入（RUST_NATIVE_MODULES = {meta}）
- 面角规则（Python 语义宿主）：单符号元组赋值（元组值物化 + 声明类型推断
  交互——`x = (1, 2)` 运行期 RUN_TYPE_MISMATCH 契约）；内建名重定义
  （`int int = 5` 常量保护面）；meta.compile 属性调用（编译器访问面）；
  内征引用 ⊄ rust_intrinsic_names（Rust 已实现内征集——print/len/range/
  knowledge/vec + 异常构造器 + meta quote/eval；随移植批次自动扩展）；
  对象身份内征（knowledge()/vec() 构造 = payload 物化契约——Rust 数据面
  已证[2a-2c]，镜像物化 = 缺口批次）
- 语料判定：34 语料 = 30 Rust 面 + 4 Python 面角（tuple_basic + 3 KB 源）

**engine _execute_rust（core/engine.py）**：
- 状态镜像双路径（声明家族驱动）：数据家族声明（int/float/str/bool/any/
  list/dict/Optional）= define_variable（VM 权威 _check_type 同构——语义
  错误集经同一检查面发射）；非数据家族 = materialize_variable（新增
  runtime_context 公共 API——符号物化无检查，declared_type 内省保留）
- declared_type 经 execution_context.resolve_type_from_symbol（符号 UID
  面——与 Python VM 赋值路径同一权威源）
- 容器特化身份绑定（_bind_container_specialization 助手——registry 面
  递归复刻 leaf._bind_container_specialization：ib_class 重绑水化特化类 +
  TypeRef 结构化 + 嵌套元素经 spec.element_type 递归；标量元素装箱形态
  保持[解箱/回箱循环会破坏元素装箱身份——实测深克隆面回归修复]）
- quoted 保真物化（declared quoted + 值串 → IbQuoted[source 全保真]）
- 输出面同构（VM print 契约：callback 优先，无 callback = stdout 渲染点
  ——子进程 CLI/main.py run silent 面同语义——ihost run_code 子源输出
  丢失根因修复）
- 错误边界：异常类名 → _RUST_ERROR_CODES 映射（ZeroDivisionError→
  RUN_DIVISION_BY_ZERO / IndexError|KeyError→RUN_INDEX_ERROR /
  AttributeError→RUN_ATTRIBUTE_ERROR / TypeError→RUN_TYPE_MISMATCH）；
  RecursionError 边界 = KDIAG_RUNTIME_ENV_LIMIT 事件投影（diagnostics
  kernel_diagnostic 同面）+ UserWarning + 根因原样传播；现场位置 = Rust
  表达式 pos @line:col 后缀 → Location(file_path=模块源文件, line, column)

**Rust 内核增量（ibci-ext）**：
- 类型错误面（Python 契约实证移植）：str 混合运算 = TypeError（str+str
  连接 / str*int 重复合法，含 int*str；其余 str 混合 = 错误）；关系运算
  跨族 = TypeError（数值 vs str；==/!= 跨族 = 不相等非错误——cmp 跨族
  修正[Str==Int 等从 0→2]）；is/is not = 同一性语义（None 同一性 + 数值
  按值相等 + 非数值异对象恒 False）
- None 相等性（None == None / None == 空 Optional 对称——cmp 前置臂）
- 三引号串（lexer：三引号字面量多行内容保真含换行 + 三连引号闭合；
  ext_ref 资产常量解析[反序列化器加载期就地替换——长/多行串内容寻址]）
- str 方法全集移植（join/format/rfind/count/contains/is_empty/replace/
  startswith/endswith + 既有 split/find/upper/lower/strip）
- optional 方法面（unwrap/to_list/or_else/next——空值错误面 = AttributeError）
- 空 Optional 错误面（len(空) / for 迭代空 = AttributeError）
- 切片 step 面（slice_indices Python 切片语义[负索引归一 + 负 step 反向]；
  str/list 同面）
- AugAssign 运算符全面（*= / /= / //= / %= / **= 映射）
- For 元组目标解包（`for (a, b) in [...]` 逐元素绑定——typed 目标同面）
- Thrown.pos 管线（表达式级错误携带 pos → 边界消息 @line:col → engine
  Location 构造）
- 借用贯穿修复（Call 臂 env.borrow().get 的 Ref 贯穿调用体 → nonlocal
  重入赋值 RefCell panic 根因——值克隆出借用语境）
- 内征面 API（rust_intrinsic_names——路由判定单一真相源）

**验证**：harness 50/50 + contracts/compiler 全绿 + 全量 pytest
4307 passed / 4 failed（4 例 = PT-DEBT-38 登记缺口族：宿主 .call 桥函数
值保真度 2 例 + Optional 实例同一性 2 例——面分区路由已隔离生产数据面）。
**基线**：4307 passed / 4 failed / ~135s（⑦-1c 后）。

## P9 转向裁定：停止 ⑦ 增量 → 内核接口层重审 + 测试体系重设计（2026-09-11）

**用户转向裁定（round 8 中途，verbatim 要点）**：停止工作，书写交接文档。
（1）须确认有没有为对接既有测试项而在 Rust/Python 接口层定义的不干净代码、
现有 Rust/Python 分层与职责分配是否真的合理；（2）内核已彻底变动，测试脚本
体系必须全部重新设计（哪怕上千测试项、代价巨大），且必须是体系/架构级重设计，
避免旧测试体系拖累 Rust 新内核；（3）初步 Rust 验证停留在 8129af0a——之后
所有修改都可能藏着代码异味；（4）怀疑接口区分/接口设计/架构层级设计存在碎片
适配性代码（碎片化 if-else 本质，形式未必是 if-else）——未能完全统一化/
体系化/形式化，未良好利用自动且抽象的转换处理机制；（5）授权从 8129af0a
起接口层/架构设计/整个内核体系推翻重来——引擎级重构，不计代价。

**本回合收尾动作（停止前固化）**：
- ⑦ 缺口批次 WIP（host .call 桥会话 API：Rust open_session/session_call/
  session_release + RustFunctionProxy + engine 接线 + Optional 同一性路由
  规则）以**审计标本**身份固化为提交 b66a210a（不完整——函数符号
  declared_type 解析 None 未修，2 个目标测试预期失败；零功能增量 + 纯新增
  适配面 = 用户怀疑的"测试驱动接口定义"的典型样本）。
- 交接任务书落档：tasks_docs/_handoff_kernel_reaudit.md（使命分解 + 嫌疑
  清单 3.1-3.7[路由谓词堆/镜像双路径/错误字符串协议/内征集合双真相/
  语义双实现结构性双真相/WIP 会话 API/测试体系时代错位] + 开工入口序列 +
  硬约束继承面）。
- HANDOFF.md §2.0 动态状态更新（接手起点指向交接任务书）；goal objective
  按转向裁定改写。

**嫌疑清单自曝面（self-grill 纪律——前序推进者自认的异味，供下一智能体
独立复核）**：⑦-1a/1b/1c 三批 + WIP 中，适配层（路由谓词 8 条 + 硬编码集合
4 个 + 镜像双路径 + materialize_variable 旁路 + 特化绑定复刻 + quoted 特判 +
错误字符串正则协议 + 内征集合双真相）随移植进度**单调增长**——每加一个
语义移植角就加一条路由规则/镜像特判，非从内核能力面自上而下声明的单一
机制。⑦ 终点（单内核）若仅退役 Python VM 而不收敛适配层，则适配层本身
成为新的历史包袱。测试体系同理：VM 时代白盒断言 + 消息子串匹配 + 速度
假设（ihost 超时校准 100000→15000000 迭代）+ 差分临时壳 = 时代错位。

**审计判定基准（交接文档 §四 使命 1 固化）**：若"路由谓词堆 + 镜像双路径 +
字符串协议 + 双真相语义面"在增量清理下无法收敛为[单一内核能力声明表 +
单一状态物化机制 + 类型化跨边界契约]，则触发使命 3（独立分支推翻重来——
8129af0a 之前资产[构建链/parser/deserializer/serializer/差分 harness 资产/
3e-3f 证明]为可信地基优先复用）。

## 使命 1 审计结论：内核接口层重审——触发使命 3（推翻重来）（2026-09-11）

**审计范围**：`git log 8129af0a..HEAD`（08758567[⑦-1a/1b] / fe1dfcf7[⑦-1c] /
b66a210a[WIP] / 016f3716[文档]）。**方法**：逐提交 diff + 逐落点读源（code-review
纪律：前序报告 ≠ 结论，全部第一手证据复核）+ 对照 ⑦ 设计 v1（_p9_switch.md）
"设计意图 vs 实现漂移" + design-philosophy/code-quality/工作模式定论。**基线实跑**：
4306/2/1/140.94s（与交接一致；2 failed = 宿主 .call 面 WIP 预期失败）。

**用户两问回答**：
1. **有没有为对接测试定义的不干净接口代码？——有，已证实**：WIP 会话 API
   （open_session/session_call/session_release + SESSIONS 注册表 + unsafe raw ptr +
   RustFunctionProxy + engine 第三分支，唯一动机 = 2 测试，且自身不完整零功能增量）；
   路由谓词堆 8 谓词 + 4 硬编码集合（每条 = 一个失败测试的静态近似）；engine 镜像
   （declared 白名单 + materialize_variable 旁路 + 特化复刻 + quoted 特判）；
   _RUST_ERROR_CODES 映射（functions.py 第二真相）。
2. **Rust/Python 分层职责分配是否合理？——不合理，已证实**：engine（自述"组装者，
   不参与执行"）在执行面做语义判断（重跑 Python 类型检查 _check_type 于 Rust 执行
   结果上）；runtime_context 核心状态模块被开 materialize_variable 旁路（poke 内部
   符号表，封装侵蚀）；kernels 加载层从"加载 .so"膨胀为 327 行路由裁判（自下而上
   补丁堆非能力声明表）。

**嫌疑清单复核**：3.1-3.6 全部**证实**（证据见审计文档 §三）；3.7 证实（测试体系
时代错位 = 使命 2 对象）；diff_harness 语料/探针/divergence 资产 = (a) 契约驱动
保留升格；**新增 N1**（非数据值显示形态串状态导出 = 类型信息丢失 + 镜像再水化
特判）、**N2**（diff_harness harness 委托生产路由面，测试资产与生产耦合）。

**总体判定：须推翻重来（触发使命 3）**。判定基准 = 交接任务书固化基准："路由谓词堆
+ 镜像双路径 + 字符串协议 + 双真相语义面"增量清理下**无法收敛**为[单一能力声明表 +
单一状态物化机制 + 类型化契约]——三个收敛目标均需**接口契约层面重新设计**而非现有
层边界内重构：镜像动因 = 两值模型状态契约决策；路由谓词编码 = 未移植语义缺口（整理
不消除）；类型化契约单独可增量但属边界整体重设计面。**推翻范围** = 8129af0a 之后接口
适配层（engine 路由/镜像/状态契约、kernels 路由判定面、错误跨边界协议、WIP 会话 API、
materialize_variable 旁路、repr 降级导出）；**复用** = 8129af0a 之前可信地基（Rust
构建链/lexer/parser/deserializer/serializer/解释器执行核心、Python 前端、artifact 契约、
diff_harness 语料资产、3e-3f 证明）；**红线不变** = 语言语义（公理+contracts 语义错误
集）/双内核协议/禁 push/main 永不触碰/独立分支。

**重设计方向（使命 3 蓝图）**：D1 内核能力声明表（Rust 导出能力清单[node_types +
intrinsic 从分发表生成消除手工清单 + native_modules + unported_corners]，Python 路由 =
清单查询零谓词堆零硬编码集合）；D2 单一状态物化机制（typed value 通道[值+类型标签]
替代 repr 降级 + 数据驱动转换表，engine 零语义判断，materialize_variable 旁路删除）；
D3 类型化跨边界契约（结构化 {class,code,line,col,message}，诊断码单真相，RecursionError
contains 特判删除）；D4 宿主 callable 统一协议（替代 WIP 会话 API，状态值持有期生命周期
非全局注册表）；D5 执行通道收敛（run_artifact_state 唯一入口，删持久会话通道）。

**执行纪律**：独立隔离分支实施（零风险确认后 merge unsafe-vibe-dev 即删分支）；分阶段
实施 + 每阶段差分门/受影响子集+smoke 零回归 + commit + 文档同步；测试体系重设计（使命 2）
协同推进（新接口落地后测试断言面按新体系承接，契约不留空洞）。**审计结论文档** =
tasks_docs/_kernel_interface_audit.md（详细证据 + 三分类 + 重设计方向）。

## IBCI 架构 v2 技术路线裁定（R0，2026-09-11 用户战略框架八点）

**用户授权**："总体的技术路线由你自己决定，我不过多干涉"，唯一原则 = 代码质量 /
可维护性 / 远期长期收益。八点框架：① 顶层 Python 保留 = 易用性（用户写 Python 实现
自己的功能/逻辑）② pip 安装 ③ 未来 tilelang 类并行低级库（GPU 块层，不裸 CUDA）
④ Rust↔Python 交融须协议化不能碎片 ⑤ 特性尽量不破坏，允许更合理设计（无负向收益
论证）⑥ 允许推倒重写执行核心 + 真正多线程 + 统一化大量同构计算（AVX/GPU 可各自独立
库；或 IBCI 传 tilelang 代码给底层只取结果）⑦ AVX/GPU = 未来战略储备非当前性能目的，
内核易维护/易用/架构稳固 >> 语言性能 ⑧ 测试体系全量重构（碎片 Python 测试太慢）。

**裁定（R0 文档 = tasks_docs/_architecture_v2_route.md）**：
- **核心命题**：Rust 不是换执行后端，而是体系化重设计契机——利用 Rust 严格性让内核
  更稳固（typed 值模型/无静默路径/enum 分派/协议化），保持 IBCI DSL 易用性。
  **内部严格性 ≠ 语言严格性**（严格性在内核内部，不推向用户；IBCI 绝不变成 Rust 式
  通用语言）。
- **目标分层**：语言面（IBCI DSL + Python 宿主扩展 HOST-EXT）/ 协议层（五协议 P1-P5：
  能力声明/typed 值通道/typed 错误/宿主调用/计算基板）/ Rust 内核（前端→typed IR、
  执行核心重写、值模型、计算基板、并发）/ Python 宿主面（HostService + 用户扩展 + 编排）。
- **八点裁定**：① Python = 宿主层 + 用户扩展层（HOST-EXT 协议化一等扩展，typed 值
  转换 + 句柄生命周期，非内核）② maturin wheel（pip install ibci；插件独立 wheel）
  ③⑤⑥⑦ 计算基板 = P5 ComputeSubstrate trait + Tensor 值入值模型；协议统一、实现
  独立（scalar 原生/AVX crate/tilelang-GPU 插件）；IBCI 传 tilelang 代码只做值编组
  调度不包装；AVX/GPU 当前只接口预留不实现 ④ 五协议禁碎片 ⑥ 执行核心推倒重写 =
  typed tree-walking（非 bytecode，易维护>>性能）：typed 值 + 无静默路径 + enum 分派
  + Result 全链 + i128 有界整数（超界显式错误）；真正多线程 = 批量计算并行 + 任务
  并行（TaskPool 保留）+ 语言级并行谨慎评估 ⑧ 测试五层重构（使命 2 设计落地，
  cargo test 内核层，速度目标秒级）。
- **打破清单 8 项**（无负向收益论证，登记 §五）：last-wins 确定性化 / Optional 值
  语义 / handler 异常变量词法作用域 / 错误协议诊断码化 / f64 全包→typed 运算+i128 /
  静默降级 13+ 实例清零 / artifact UID 去 Python json.dumps 绑定（canonical 哈希，
  artifact v2 版本化迁移）/ Python 语义转录文化→公理契约驱动。
- **保留清单**：语言表面/KB 27 方法+磁盘格式/quote-eval/vector-embedding/LLM 15
  节点宿主面/intent-behavior-memory/ihost-overlay-journal-budget-deterministic/
  诊断码契约面。
- **实施路线**：R0 裁定（本文档）→ R1 接口协议化（使命 3 D1-D5，kernel-interface-
  rebuild 分支）→ R2 执行核心重写（独立分支，推倒授权）→ R3 测试五层重构 → R4
  HOST-EXT + maturin 打包 → R5 计算基板（Tensor + ComputeSubstrate；AVX/GPU =
  战略期）。

**变化前后**：变化前 = 双内核 + Python 转录 Rust + 接口适配层（审计判定推翻重来）；
变化后 = Rust 唯一内核 + 协议层 + HOST-EXT + 计算基板预留。目标（用户裁定/本裁定）
已同步 goal objective（revision 4 active）。

## R1 接口协议化收束（E1-E4 全部落地，2026-09-11，分支 kernel-interface-rebuild → merge）

**R1 = 架构 v2 五协议中的四协议落地**（P1 能力声明 / P2 typed 值通道 / P3 typed
错误 / P4 宿主调用 + D5 单一执行入口）——审计使命 1 的 3.1/3.2/3.3/3.4/3.6 全部收敛：
- **E1（P3）**：RustRuntimeError pyclass + ErrorPayload（Send 载荷）+ 全边界
  结构化错误；诊断码单一权威 = core/base/diagnostics/runtime_error_map.py
  （functions.py 与 engine 同源委托）；删 _RUST_ERROR_CODES / 正则回拆 /
  RecursionError contains。→ commit a6a9b590
- **E2（P1）**：call_function 改内征分发表（INTRINSICS + EXCEPTION_CLASSES，
  intrinsic_names 由表派生——审计 3.4 双真相消除）；capability() pyfunction
  （node_types/intrinsic_names/intrinsic_symbol_names[63]/native_modules/
  unported_corners[5 角]）；Python capability.py（KernelCapability + ArtifactView
  + 角注册表 + ArtifactRouter 单一查询）——删 8 谓词堆 + 4 硬编码集合（审计 3.1）。
  → commit 5b451c38
- **E3（P2）**：ibvalue_to_typed_json（状态导出 {kind, value} 类型标签——审计 N1
  消除）；StateMaterializer 单一物化表（quoted→IbQuoted / vector→IbVector 真实
  数据 / 容器特化绑定移入）；engine 镜像 = 调物化器 + kind 驱动写入路径（删
  quoted 特判/容器复刻/declared 白名单——审计 3.2）。→ commit d838f6d3
- **E4（P4/D5）**：删 WIP 会话 API 全组（unsafe 全局注册表 + 双执行通道——审计
  3.6）；call_top_level_function 无状态顶层函数调用 + RustHostCallable（Python
  callable → IbNativeFunction .call 契约）；engine 改 run_artifact_state 单一
  执行入口；divergence 登记 host_call_closure_state。→ commit 324da716

**验证**：全量 pytest 4306/2/1 → **4308/0/1**（2 个宿主 .call 测试转 pass——
RustHostCallable 修复 WIP 未接线根因）；smoke+diff+host-call 888 passed；残留
扫描零（会话 API/字符串协议/硬编码集合零残留）。

**merge**：全量零回归 + 复核放行（无对外契约/架构级风险——公开 engine API 不变，
状态导出形状为内部契约）→ merge unsafe-vibe-dev，删分支（分支政策）。

**变化前后**：变化前 = 8 谓词路由 + 镜像双路径 + 字符串错误协议 + 会话双通道 +
内征双真相；变化后 = 能力声明查询 + 单一物化表 + 类型化错误 + 单一执行入口 +
分发表派生内征集。**下一步 = R2 执行核心重写**（typed 值模型 + 无静默路径 +
enum 分派 + i128 数值 + Tensor 值——独立分支，推倒授权）。

## R2 执行核心重写（独立分支 execution-core-hardening）——R2-1/R2-3a/R2-2 落地（2026-09-11）

**R2 目标（架构 v2 R0 §2.6 + 打破清单 5/6）**：typed 值模型 + 无静默路径 +
enum 分派 + i128 数值 + Tensor 值；推倒授权（用户⑥），独立分支逐增量。

- **R2-1（无静默路径第一波，commit 775b2024）**：容器/字符串方法面 + 标量
  运算静默清零——list.index/pop/remove 错误化；str.split 无参 = 空白切分
  （修旧"逐字符切分"错误值）+ 缺参/非 str TypeError（find/rfind/count/
  contains/startswith/endswith/replace）；slice step 0/非 int step/非序列
  错误化；assign_subscript 支持 List 元素赋值（修旧仅 Dict 静默 no-op）+
  越界 IndexError；Name 未定义 NameError；len/range 类型错误；num_result/
  pow/bitwise/floor/modulo 非数值 TypeError；eval_iter 非可迭代 TypeError；
  PartialEq bool==数值（dict 键 True==1）；vector 方法参数错误 TypeError。
  全量 4308/0/1 零回归。
- **R2-3a（typed 数值运算，commit e95466f4）**：消灭 f64 全包——num_arith
  单一入口（Int/Bool = i64 精确 checked 路径，溢出 = 显式 OverflowError；
  含 Float = f64）；floor 除/floor mod 精确（负号正确）；** 精确幂（负指数
  = 浮点）；位运算 i64 精确；cmp 精确 i64 比较（修大整数经 f64 误判相等）。
  登记 DIVERGENCE bounded-int-overflow（i64 有界契约，超界显式错误优于静默
  错误值；i128/num-bigint = R2 值模型后续）；test_execution_model
  factorial(100)→(20)（100! 超界 = 旧 Rust 静默 i64::MAX 垃圾，改断言 20!
  精确值）。全量 4308/0/1 零回归。
- **R2-2（deserialize fail-fast，commit e285af6c）**：run_artifact/
  run_artifact_state 非良构 artifact = ArtifactDeserializeError 显式错误
  （旧 = 空输出静默）。

**变化前后**：变化前 = 静默 None_/0/空输出/错误值（13+ 实例）+ f64 全包精度
丢失 + 有界溢出静默饱和；变化后 = 显式结构化错误 + i64 精确算术 + 溢出显式
错误。**下一步 R2 续**：kb 治理门结构化错误、host 桥异常传播（低生产价值——
KB/宿主源路由 Python）、enum 分派（R2-4）、Tensor/ComputeSubstrate（R2-5）、
值模型 i128（R2 核心）→ R2 收束 merge。

## R2 执行核心硬化波收束（R2-4 + GAP 登记，2026-09-11，execution-core-hardening → merge）

**R2 硬化波 = 架构 v2 R2 的"核心硬化"实施**（typed tree-walking 硬化，非 bytecode
重写——R0 §2.6 裁定"结构保持 tree-walking，易维护>>性能"；推倒授权执行于"推翻
f64 全包/静默路径/stringly 错误"的旧实现）：
- **R2-1**（775b2024）无静默路径第一波（容器/字符串/标量静默清零 13+ 实例）
- **R2-3a**（e95466f4）typed 数值运算（消灭 f64 全包，i64 精确 + 溢出显式错误，
  DIVERGENCE bounded-int-overflow）
- **R2-2**（e285af6c）deserialize fail-fast
- **R2-4**（6ba87884）typed 错误枚举 ErrorKind（8 类 + class_name() 契约面，全 65
  调用点机械替换——编译期拼写检查，删 stringly-typed 错误类名）
- **GAP 登记**（本条目）：kb-governance-error-face + host-bridge-error-face——
  两处静默路径经实证为 Python 参考抛错（KNW_ 码/宿主异常）而 Rust 静默 None_，
  但生产不可见（KB/宿主源路由 Python，Rust 侧仅 harness 直调无错误探针）；
  修复 = 扩展错误契约（值模型/错误面/host 协议后续）。str.format 经实证 = IBCI
  单参简化语义（Python 参考 strings.py 同）——非偏差，跳过。

**验证**：全量 pytest 4308/0/1 零回归（R2-1/R2-3a/R2-2/R2-4 各一轮全量）；
diff_harness 全绿（GAP 2→3 / DIVERGENCE 1→2 断言同步）。
**merge**：零回归 + 复核放行（内部内核硬化，无对外契约变化——错误类名字符串
契约不变，数值行为严格改善 + bounded-int DIVERGENCE 登记）→ merge unsafe-vibe-dev
删分支。
**R2 续项（后续轮次）**：call_method 方法分派表（enum 分派剩余，维护性）、
i128 值模型（有界界扩大，边界/JSON 复杂度——值模型核心工作）、Tensor 值 +
ComputeSubstrate（R5 计算基板）。**下一步 = R3 测试体系五层重构**（用户⑧：
测试太慢/碎片——语言行为层升格 + 白盒降级删除 + cargo test 内核层 + 差分机制
退场准备）。

## R3 测试体系五层重构——R3-1 语言行为层骨架（2026-09-11，unsafe-vibe-dev）

**R3 = 用户⑧（测试太慢/碎片）体系级重构**（设计 = `_test_redesign.md` 五层）。
- **R3-1（commit 274b9644）**：tests/behavior/ 语言行为层种子——helpers
  （run/assert_output/assert_error[诊断码+结构化现场，禁消息子串]/assert_
  compile_error）+ 18 测试（数据面[typed 数值精度/floor 除/容器/字符串/函数/
  quoted] + 运行时错误[诊断码+位置] + 编译错误[诊断码]）。
- **引擎错误边界补齐（P3 契约完成）**：未映射错误类（ValueError/OverflowError
  等）= InterpreterError[RUN_GENERIC_ERROR]（与 Python VM 边界同一契约——
  不泄漏内核边界 RustRuntimeError）；行为层 assert_error 断言面据此成立。
- **实证**：IBCI 容器 str 元素显示无引号（Python 参考同 [a, b]——Rust 正确，
  非偏差）；str.format = IBCI 单参简化语义（非偏差）。
- 全量 pytest 4308 → **4326/0/1** 零回归（+18 行为层）。

**下一步 R3 续（后续轮次）**：阶段 B 行为层语料升格（diff_harness 语料/探针 →
显式预期用例）+ 契约层巩固（诊断码表/错误现场/artifact 格式测试）→ 阶段 C 白盒
断言降级删除（runtime/kernel 层 VM 内部形态断言逐项迁移映射）+ 宿主面层组建 →
阶段 D（⑦ 终点）差分机制退场。

## R3 阶段 B：语料升格 + 契约层巩固（2026-09-11，unsafe-vibe-dev）

- **R3-阶段B-1（commit 17f09522）**：diff_harness 34 语料升格 = tests/behavior/
  test_corpus_behavior.py 显式预期用例（绝对行为断言，非双内核对比）——预期 =
  当前生产行为捕获（引擎自动路由 Rust/Python 混合内核，34/34 确定性）；
  差分机制 = 迁移期临时壳（⑦ 终点退场），语料种子正式入行为层。
- **R3-阶段B-2（commit 本条目）**：契约层 tests/contracts/test_error_contract.py
  ——诊断码映射单一权威（runtime_error_map 全映射可解析 + 已知映射 + 未映射
  None）+ 引擎错误面契约（Rust 执行错误 → InterpreterError + 诊断码 + 现场；
  ValueError/OverflowError → RUN_GENERIC_ERROR）。
- 全量 pytest **4328/0/1** 零回归；行为层 18 测试 + 契约层 7 测试。

**下一步 R3 续**：阶段 C 白盒断言降级删除（runtime/kernel ~50 文件 VM 内部形态
断言逐项迁移映射）+ 宿主面层组建（LLM/意图/ihost/overlay 归类）→ 阶段 D（⑦
终点）差分机制退场。R4 HOST-EXT+pip 打包紧随其后。

## R3 阶段 C：白盒断言降级第一切片（R3-C1，2026-09-11，unsafe-vibe-dev）

**阶段 C = 白盒断言降级删除 + 宿主面层组建**（迁移映射 = `tasks_docs/_test_
migration_C.md`——21 个强白盒文件逐文件分类[行为/契约/宿主/内部] + 承接面；
纪律 = 先落承接再删，契约不留空洞）。
- **R3-C1（commit 6467e502）**：
  - 新建 tests/host/ 宿主面层：test_llm_behavior_roots.py（LLM 行为根可观察
    契约——2 独立 @~ MOCK:STR:... ~ 经公共 engine API 求值 + LLM 请求数 >= 2）。
  - 删除 test_vm_run_many.py（VM 内部 run_many/UUID 编排——可观察契约 = 新
    宿主测试承接）+ test_execution_context.py（ExecutionContextImpl 查询 API
    内部——llmexcept 行为 = e2e/test_llmexcept.py 承接）。
  - 全量 pytest 4337 → 4326/0/1 零失败（+1 承接 -5 白盒；收集差 = 参数化细节）。
- **阶段 C 续（后续轮次）**：optional_value_model（identity 2 例 = 打破清单 #2
  待重设计）/ generic_value_identity（deep_clone 内部）/ file_handle（clone_ref
  内部）/ storage_model_dispatch（内部）等逐文件迁移映射执行；行为类白盒文件
  （vector/knowledge/narrow_model/optional 语义）重构为行为层可观察断言。

## R4：HOST-EXT 用户 Python 扩展协议 + pip 打包（2026-09-11，unsafe-vibe-dev）

**R4 = 用户战略点①②**（Python 保留 = 易用性 + 允许 pip 安装）落地：
- **R4-1（commit 83ba220a）**：core/host_ext.py register_host_extension
  （engine, name, implementation）——从实现成员签名自动构建 IBCI TypeDef
  （inspect 内省：Python 注解 → IBCI TypeRef[基础 + 容器泛型 + 显式 None=void
  + 无注解=any]）；复用既有宿主模块装配链（构造期注册 → 编译期跳过文件解析 →
  装配期 loader 自动绑定 vtable → 运行期 interop.get_package 分发），零碎片；
  值转换 = 原生直通（P2 精神）；扩展异常显式传播；迟到注册拒绝。e2e 7 测试
  （标量/容器/dict 返回/动态/错误/迟到）。
- **R4-2（commit 23860c50）**：pyproject.toml 改 maturin 后端 + include
  core/ibci_modules 收录；内核加载器支持 wheel 形态（import ibci_ext 优先，
  dev .so 回退）。**验收（全新 venv）**：pip install wheel → Rust 内核加载
  + 运行 + HOST-EXT 全正常；dev editable 回归。
- 全量 pytest 4326 → **4333/0/1** 零回归（+7 HOST-EXT）。

**下一步 = R5 计算基板**（架构 v2 用户点③⑥⑦）：Tensor 值入值模型 + 
ComputeSubstrate trait（批量同构计算协议，scalar 实现；AVX/GPU = 未来战略
期接口预留，不实现）；IBCI 传 tilelang 代码给底层 = 值编组形态（不包装）。

## R5 计算编排协议（R5-1 Tensor 统一 + R5-2 compute_engine 网关，2026-09-11）

**R5 = 职责重定位落地（内核不实现外部引擎内部数学——编排而非执行；`_ibci_role_
platform.md`）**：
- **R5-1（commit 0dcbd6ff）Tensor 值入值模型**：IbValue::Vector(Vec<f64>) →
  IbValue::Tensor(TensorValue{shape, data})——**值模型统一**（vector = 1D
  tensor，架构健康原则"同一语义两种实现必漂移"——不并行保留两套 bulk 值）；
  tensor() 内征（1D/2D 矩形校验）+ 方法面（shape/ndim/dtype + dim/norm/dot/
  cosine[1D] + scale/add/sub[元素级泛化]）+ 2D 下标 = 行；typed 通道
  kind="tensor"；kb 嵌入面迁移；语言三处注册 + 静态表（full_artifact 对齐）。
- **R5-2（commit ab6f2151）compute_engine 编排网关**：宿主模块（IMPORT_GATED）
  register_engine + run(op, operands, engine) 分派到已注册引擎（numpy 参考引擎
  add/sub/scale/dot/matmul）；无引擎 = 显式错误、引擎失败 = 显式传播（fail-fast
  非静默）；Tensor 缓冲交换 = to_list/tensor（vector 一等值契约保持，对象不跨
  边界、数据穿越）+ bootstrapper.box ndarray→list 守卫；Python 路径 tensor 内征
  + IbVector to_list/shape/ndim/dtype；Tensor 桥接穿越（to_py/from_py）。
- **全量 pytest 4333 → 4343/0/1 零回归**（+5 tensor 行为 +4 编排）；diff_harness
  全绿（含 full_artifact/intrinsic 符号表对齐）。
- **R5 续**：torch 互转 + tilelang 插件后端 = 未来战略期（接口已就绪——编排协议
  + Tensor 缓冲交换；2D Python 对象模型统一 = R5-3 后续）。

**下一步 = R6 Rust 插件协议**（④层：ibci-sdk crate + cdylib 插件 ABI——回答
"外部人员写 Rust"，不在内核核心）+ 背景 R3 阶段 C 长尾。

## R6 Rust 插件协议（④层，2026-09-11，commit 492c56ba + 2eb1bdb8）

**R6 = 回答"外部人员书写 Rust"**（不修改内核、不 python.h；职责重定位"内核不执行
外来代码"：插件 = 纯函数面[数据进 → 数据出]，内核 GIL-free 执行）：
- **ibci-sdk crate**：repr(C) PluginValue（借用实参 Int/Float/Bool/None/Str/List
  + 自有标量结果）+ PluginApi（内核回调 register_function/log）+ ibci_plugin_
  register 入口 + register_plugin! 宏（插件作者安全注册）。
- **内核加载**（ibci-ext/src/plugins.rs）：libloading 加载 cdylib + 调 C-ABI
  注册入口（与编译器/版本解耦）；进程级注册表 + Arc<Library> 保活（函数指针
  生命周期内库不卸载）；pyo3 load_plugin/call_plugin。
- **plugins 宿主模块**（IMPORT_GATED）：IBCI 侧 load(path)/call(name, args)。
- **示例插件**（plugins/demo）：sum/mul（register_plugin!）。
- **自审修正（2eb1bdb8）**：插件桥去 JSON 字符串传输 → pyo3 对象直接提取/构造
  （P2 typed 精神——无序列化层；字符串协议异味自审清除）。
- **验证**：端到端 load → 2 函数 → call("sum",[1,2,3,4])=10、mul=42；全量
  pytest 4343 → **4347/0/1** 零回归；宿主层 +3 插件测试。
- **R6 值面**（R6-1）：标量 int/float/bool/null + 扁平列表实参；Str/List 结果
  + 嵌套容器 = 后续增量（所有权纪律）。

**主线 R5+R6 全部完成**（架构 v2 编排平台：Tensor 统一数据形态 + 计算编排协议
+ Rust 插件协议）。剩余 = 背景（R3 阶段 C 长尾：21 白盒文件——C1 已删 2；
vector_type/world_model_kb 等迁移行为层 + clone_ref 等内部断言重构 + cargo test
内核层组建）+ R2 续项（方法分派表/i128）+ 阶段 D（差分退场）。

## R3 阶段 C 长尾（R3-C2 ~ C5，2026-09-11，commit 30e4fbbd~bf670054）

**测试体系重构推进（21 强白盒文件：C1 已删 2）**：
- **C2**（30e4fbbd）：test_vector_type.py → tests/behavior/test_vector_behavior.py
  （18 断言：值语义/构造封死/dim 不一致/dict 键/数学性质精确值；round-trip =
  Rust artifact 契约面）——白盒删除。
- **C3**（542bbd97）：test_specialization_identity_runtime.py → 跨模块特化独立
  可观察断言（SEM_TYPE_MISMATCH 锁定独立身份）；3 个 VM 内部直调删除。
- **C4**（0d0adb5e + 89770e4d）：test_knowledge_to_ibci.py 裁决——to_ibci =
  Python 参考 KB 功能（Rust kb.rs 无分派，角路由送 Python；行为层须内核无关）
  → 删除 + PENDING 登记（⑦ 终点裁决移植/退役 + kb.rs catch-all None_ GAP）。
- **C5**（bf670054）：test_knowledge_type.py → 行为层 15 断言 + 宿主层 2 断言
  （ihost 状态往返）；2 序列化 round-trip = ⑦ 路径删除。
- **全量门**：4332/0/1（e2e CLI 投影测试间歇性失败 1 次——序依赖，隔离/重跑
  通过，登记观察）。
- **归类无动作**：7 文件归宿主/契约层（保留原文件）。
- **剩余**：optional_value_model（identity 2 例 = 打破清单 #2）/ world_model_kb
  （36 测试大件）/ narrow_model（宿主层 + artifact 夹具）/ 3 个 clone_ref 内部
  断言重构 + cargo test 内核层组建。

## R3-C6 + 打破清单 #2 落地 + 码族/GAP 分析（2026-09-11，commit 0172fd5c）

- **C6（0172fd5c）**：test_optional_value_model.py → tests/behavior/
  test_optional_behavior.py（28 断言）。**打破清单 #2 落地**：Optional 空值 =
  None 值语义统一——`a is b`（两空 Optional）= True（原 Python 包装实例身份
  废弃）；optional_instance_identity 角移除（Rust `is` 对 None_ 恒真）。全量
  4304/0/1。
- **分析发现（登记 PENDING）**：① kb_vec_payload_materialization 角路由所有
  knowledge()/vec() 源送 Python——Rust kb.rs/intrinsic_vec 静默 None_ GAP
  （生产不可见，diff harness 直调才见）；② 双码族：Rust RUN_* vs Python
  EMB_/KNW_（ValueError 未映射 →RUN_GENERIC_ERROR）——行为层错误断言目前 =
  Python 码（内核相关）。关闭方案 = Rust 错误面扩展承载语义码 + kb.rs/vec
  fail-fast + 角移除（⑦ 终点/内核收尾）。
- **剩余迁移**：world_model_kb（36 测试，前置 = GAP 关闭或 Python 验证）、
  narrow_model（宿主层 + artifact 夹具）、3 个 clone_ref 内部断言重构 +
  cargo test 内核层。

## GAP-vec-kb-failfast 关闭 + R3-C7a（2026-09-11，commit af6f30d7 + b004bb9a）

- **GAP 关闭（af6f30d7，打破清单 #6 实质清零）**：Thrown.code + ErrorPayload.
  code + RustRuntimeError.code 通道（P3 typed 错误协议扩展——语义码 EMB_/KNW_
  经 typed 错误承载，engine 优先取 e.code）；runtime_error_coded 新增；
  intrinsic_vec fail-fast[EMB_INVALID_INPUT]；**kb.rs 分派 Result 化**（治理门
  fail-fast[KNW_VOCAB_EXISTS/MALFORMED/UNREGISTERED/FACT_DUPLICATE] + 未知方法
  AttributeError[旧 catch-all 静默 None_ 清零] + 查询面 Ok 化行为不变）；
  divergence gap-kb-governance-error-face → CLOSED。全量 4304/0/1。
- **R3-C7a（b004bb9a）**：world_model_kb Vocab+Fact 平面 → 行为层 11 断言
  （词表/事实/治理门[诊断码+定位]）；前置 GAP 关闭后迁移可行。全量 4316/0/1。
- **剩余**：C7b（KB 索引/序列化/deep_clone/查找/对比/审计平面）、narrow_model
  （宿主层 + artifact 夹具）、3 个 clone_ref 内部断言重构、cargo test 内核层、
  R2 续项（方法分派表/i128）、阶段 D（⑦ 终点：角移除 + 双码族统一 + IR）。

## R3-C7b（world_model_kb 全平面迁移完成，2026-09-11，commit 1dcc9bae）

- tests/behavior/test_kb_world_model_behavior.py → 31 断言（C7a 11 + C7b 20）：
  查找面（lookup_pair/exists/all_in_world/by_source/by_subject/contradicts/
  transitive[防环]）+ 对比展开面（expand 全字段/same_word/compare 4 层）+
  审计面（retract 墓碑/amend_fact 版本化/source/history_fact/复活语义[诊断码+
  定位]）+ deepcopy 独立 + entries 零回归。
- 删除 test_world_model_kb.py（36 测试：31 迁移 + 2 索引结构[内部——契约 =
  查询面已承接] + 2 legacy 序列化[⑦ 路径] + 1 展开确定性[纯函数吸收]）。
- **用户指示 GitHub 提交（显式授权 push）**：unsafe-vibe-dev 116 commit 全量
  push（main 未触碰）。后续每增量同步 push。
- 全量 pytest 4296/0/1。
- **剩余**：narrow_model（宿主层 + artifact 夹具）、3 个 clone_ref 内部断言
  重构（file_handle/generic_value_identity/storage_model_dispatch）、cargo
  test 内核层组建、R2 续项、阶段 D。

## R3 阶段 C 全部完成（C8-C10，2026-09-11，commit 7052b167/7327ff05/3335d7ad）

- **C8**（7052b167）：narrow_model → 宿主层 12 断言（bind_artifact 语言路径 +
  artifact 夹具[canonical hash]；TransE/topk/元数据/NAR_* fail-fast/content_hash
  篡改门）。
- **C9**（7327ff05）：clone_ref/deep_clone 内部断言重构 → 行为层 3 断言（list/dict
  特化类型保留+独立）+ file_handle 原位可观察化；generic_value_identity/
  storage_model_dispatch 内部断言删除（契约承接）。
- **C10**（3335d7ad）：**cargo test 内核层组建**——ibci-sdk 2 + ibci-ext 6 内核
  内部层单测（TensorValue/ErrorKind/错误码通道/PluginValue）+ scripts/test_rust.sh。
- **R3 阶段 C 全量完成**：21 强白盒文件处置完毕（C1-C10 逐项迁移/删除，契约
  逐项承接）+ 测试体系五层齐备（行为/契约/宿主/前端/内核内部层）。
- **用户要求"测试体系重构最终全部推进完毕"达成**。
- 全量 pytest 4283/0/1；Rust 单测 8/0。
- **剩余**：R2 续项（方法分派表 enum 化 / i128 评估）+ 阶段 D（⑦ 终点：差分
  退场 + Python 参考内核退役 + 双码族统一 + artifact IR）。

## R2 续项完成（2026-09-11，commit b5d0ae9f + a38c072b）

- **R2-续-1（b5d0ae9f）call_method 方法分派表 enum 化**：审计项"方法分派
  stringly-typed"关闭——4 个值类型 `match method {"..."}` 大 match 块 →
  每值类型方法分派表（TENSOR_METHODS 11 / LIST_METHODS 6 / DICT_METHODS 4 /
  STR_METHODS 14）+ dispatch_method 表查找（单一权威：新增方法 = 只加表项 +
  实现 fn；未知方法 = AttributeError）。纯结构重构，行为不变。全量 4283/0/1。
- **R2-续-2（a38c072b）i128 值模型评估裁决**：维持 i64 有界契约——i128/任意
  精度 = JSON/serde/通道/差分全局复杂度远超边际收益（大整数非 DSL 场景）；
  溢出 = 显式 OverflowError（fail-fast）；可扩展 = 未来独立 BigInt 值类型。
  文档化：docs/KNOWN_LIMITS.md §二十八 + divergence int_overflow rationale。
- **剩余 = 阶段 D（⑦ 终点）**：差分机制退场 + Python 参考内核退役 + 双码族
  统一 + artifact IR 重设计。**成熟度评估**：尚未成熟——kb_vec 角仍路由
  knowledge/vec 送 Python（Rust KB 缺 store/get 面）、meta.compile/tuple 物化
  等角未移除；⑦ 终点前置 = 先移植 Rust 剩余面 + 角移除，再退役 Python 语义
  执行 + 差分机制（独立项目，下轮主线）。

## 阶段 D（⑦ 终点）D1：角移除前置（2026-09-11，commit c41ad788 + a4df9944）

- **D1a（c41ad788）**：intrinsic_redefinition 角移除——Rust 顶层常量保护
  （裸赋值重绑内建名 = RUN_TYPE_MISMATCH；带注解声明可遮蔽；函数局部允许）。
  编译期已拒顶层 print = 5[类型检查]，本检查覆盖 int/str 类型名等。
- **D1b（a4df9944）**：tuple_value_materialization 角移除 + **IbValue::Tuple
  冻结列表变体**——旧 tuple-as-list 泄漏可变方法面（append 可改元组 = 真实
  语义分歧，角隐藏）；tuple 不可变契约落地（TUPLE_METHODS len/index/count
  无修改面）+ 值模型全触点 + 解包/迭代/序列化（materialize _tuple = Python
  tuple 保真）。
- **角进度**：4 角移除 2（intrinsic_redefinition + tuple）；剩 kb_vec
  （knowledge store 面移植 + 大验证）与 meta_compile。
- 全量 pytest 4283/0/1 每步零回归；diff harness 语料现含 Rust 路由的元组源
  且匹配（契约权威化推进）。

## 阶段 D1（⑦ 终点前置）完成：kb_vec 角移除（2026-09-11，commit 2c6fa77b）

- **D1c（2c6fa77b）kb_vec 角移除 + knowledge 面全量 Rust 移植**：KbState.
  entries 登记面 + store/get/keys/len/amend/history/export + to_ibci 投影 +
  deep_clone_value 快照隔离；修复角隐藏的 Rust 缺口（str.len/审计面 fail-
  fast[KNW_*]/未注册关系 fail-fast/by_subject/by_source/relations 臂/dict 键
  可哈希门/cosine 零范数/错误位置内层优先/add_fact 5 参）。
- **角移除进度 3/4**：intrinsic_redefinition + tuple + kb_vec 移除（语义缺口
  全 Rust 化 + 行为测试转 Rust 验证）；**meta_compile 保留**——编译器访问面
  （编译器 = Python 宿主服务，非 Rust 语义缺口；按职责重定位 = 宿主路由正确）。
- **D1 完成**：非宿主 IBCI 语义全部 Rust 路由（行为层 108 测试[KB/vector/
  knowledge] Rust 验证）。
- 全量 pytest 4283/0/1 每步零回归；diff harness 全绿。
- **剩余**：D2（Python 参考内核退役 + 差分退场——宿主 import 源仍路由 Python
  [fs/ai/ihost 等 = 宿主面保留]；差分 = Rust vs Python 参考，D2 退休）+ D3
  （双码族统一）+ D4（artifact IR）。

## 阶段 D2 评估：Python 参考内核退役路径（2026-09-11）

- **D2 关键路径 = Rust 宿主 import 执行**：import 绑定（get_host_module 别名已
  加）✓；宿主方法调用 = **桥接重设计点**——Rust call_host_method 现为裸 Python
  call_method，但宿主对象（IbFileHandle 等）的方法经 Python 对象系统
  vtable/receive 分派（非裸属性）→ 需桥接 host_call API（经对象系统分派 +
  typed 结果）。fs.open 可调（返回 Host 对象），h.read() 不通（vtable 面）。
- **D2 步骤**：① 桥接 host_call API（对象系统分派）② 路由全源送 Rust
  （native_modules 扩为全宿主模块）③ Python VM + 参考对象系统退役（大删）
  ④ 差分 harness 退场（数据面先、前端面后）⑤ 前端 Rust 权威化。
- **D2 = 多轮项目**（非单轮）：宿主对象系统耦合深（host 函数返回 boxed
  IbObjects——退役需 host 函数返回 typed 形态经桥接物化）。
- 全量 pytest 4283/0/1 维持。

## 阶段 D2-① 完成 + 路由变更评估（2026-09-11，commit 89ea63b5）

- **D2-①（89ea63b5）宿主桥接 host_call 打通**：HostService.host_call（模块懒
  setup[capabilities 注入同 loader 装配协议] + 裸属性/receive 分派 + 显式错误
  传播）+ get_host_module + set_service_context；Rust call_host_method →
  bridge.host_call + Result 化；engine 传 HostService 作 bridge。验证（内核
  直调）：fs.open/read → hello-d2、compute_engine/tensor 2D/str.len/tuple
  count 全通。
- **路由变更评估（未落地——本轮回退）**：扩 native_modules 试探 → 宿主测试
  6+ 失败。**缺口 = 宿主错误码边界**：host 面 InterpreterError（NAR_*/KNW_*）
  经桥接丢失码（Rust map_err → AttributeError）——需 host-call 错误边界提取
  error_code + 现场（P3 typed 错误贯通）+ compute/ihost 等形态差异修复。
- **下一步 D2-②**：宿主错误码边界（桥接异常 → RustRuntimeError[code+line]）
  → 路由全源送 Rust（大验证）。

## 阶段 D2-② 完成 + 路由变更评估（2026-09-11，commit a7a103d3）

- **D2-②（a7a103d3）宿主错误码边界**：host_pyerr_to_thrown（宿主异常 →
  Thrown 携带 error_code + line/col——P3 typed 错误贯通）；call_host_method/
  Function 错误传播改造；Optional to_list 特例跳过 Tensor（遮蔽修复）。
  验证（内核直调）：narrow_model NAR_* + line 经桥接 ✓；tensor to_list ✓。
- **路由变更评估（回退）**：扩 native_modules → **55 失败**（LLM/async/thread/
  ihost 状态/文件内核集成深缺口）——路由全源送 Rust = 多轮项目。桥接 +
  错误码成果保留（D2-② 为 D2 后续的地基）。
- **D2 路线修正**：① 桥接 host_call ✓ ② 错误码边界 ✓（均为地基）③ 路由
  变更 = 后续多轮（按宿主面逐模块验证：compute/plugins[已通] → fs → ai/LLM
  → ihost 状态 → async/thread）④ Python VM 退役 ⑤ 差分退场。
- 全量 pytest 4283/0/1。

## 阶段 D2-③：路由增量 + Knowledge 穿越缺口（2026-09-11，commit 976aba01）

- **D2-③a（976aba01）3 模块路由 Rust**：compute_engine + plugins + fs → Rust
  （native_modules 增量；宿主 getattr 经对象系统 __getattr__ 协议 + from_py
  基本值类型解箱[自定义类型 = Host 句柄语义]）——fs e2e（write/read/path）+
  host 38 测试全绿 + 全量 4283/0/1。
- **world_model 路由试探（回退）**：20 失败——**Knowledge 值跨桥接缺口**：
  to_py 显式违约（Knowledge → None，"不经桥接"）——world_model.save_kb(kb,
  path) 第一参须为 knowledge 值失败。**D2-③b = Knowledge 穿越设计**：
  Rust Knowledge → 状态导出（KbState → dict）+ host_call 参数处理重建
  IbKnowledge（registry + 状态装载）——深集成，多轮。
- 路由现状：meta/compute_engine/plugins/fs → Rust；ai/ihost/world_model 仍
  Python（逐模块验证推进中）。

## 阶段 D2-③b 完成：Knowledge 值跨桥接 + world_model 路由（2026-09-11，f3a4913e）

- **Knowledge 穿越**：to_py Knowledge → 状态 dict（to_native 同构——save_kb
  消费值快照；word/relation/world 记录补 lexeme/type/name）；from_py
  IbKnowledge → 状态 → Rust 首等值重建（knowledge_from_state——by_pair/
  by_triple 派生重建；entries 谓词恢复后 = None[KNW 边界]）——load_kb 结果
  全方法走 Rust 臂。
- **host_call 参数拆箱**（同 proxy_wrapper 单一入口——IbObject → native；
  可调用实例透传）+ host_pyerr 回退类 = Python 异常类名（非硬编码）。
- **路由：4 模块 Rust**（compute_engine/plugins/fs/world_model）——逐模块增量
  + 全量门（4283/0/1）；world_model disk 9 + embedding 往返 + host 38 全绿。
- 剩余：ai（LLM 面——深）、ihost（状态往返）、async/thread；之后 Python VM
  退役 + 差分退场 + 前端权威化。

## 附、书写模式（本文档专用模板，书写必须参照）
## 附、书写模式（本文档专用模板，书写必须参照）
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
