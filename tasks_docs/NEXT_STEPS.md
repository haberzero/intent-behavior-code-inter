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

> **✅ round3 队列 + 原阶段 E 顺延批全部收束（2026-09-08）——收敛判据达成。**
> 全阶段（A P0 / B P1 / C P2 文档批 / D meta 层设计 / E 顺延批 / F 收敛）全部项处于
> 完成/挂起/裁定不做终态。测试基线以实跑为准（末次全量 3867 passed / 1 skipped 零回归）。
>
> **🔴 当前 P0 = 内核完整系统工程化 + 真 JIT（数据平面性能线，自主执行主线，2026-09-08
> 用户定向扩展）**：meta 层 MVP（自举台阶 ④，字符串级直接执行）✅ 主线收束（2026-09-08，
> M1/M2/M3 全完成）+ **按用户指示一次 fast-forward 并入 `unsafe-vibe-dev`**（全本地未
> push，unsafe = free-explore = f598a609）。新主线 = VISION-6 内核工程化范畴[数据平面
> 性能线/真 JIT[优先，用户点名] + 缓存预编译 + 内核自举 + 隔离改造 + 反射能力]，硬约束
> = 9 项 VM 设计不变量（`docs/architecture/04_vm_interpreter.md` §11）+ 工作模式定论。
> **Phase 0 ✅ 完成（2026-09-08，只读实证调查，WORKLOG 详录）**：架构实证 = 编译管线五
> 阶段无字节码/IR[确定性内容哈希 node_uid node_{sha256[:16]}] → VM 数据面 = AST 直走的
> CPS/生成器解释器[显式帧栈非递归 + 50 个 vm_handle_IbXxx 查表分派 + Signal 经
> StopIteration.value 数据化 + 函数调用 trampoline + LLM Waitable 协作挂起]。
> **量化锚点（JIT/快速路径目标点）**：单节点 5 条开销 = (1) 每语句新建 TaskScheduler
> [run_body 逐 stmt run()] / (2) 每节点生成器分配[纯 return handler 中央化包装] / (3) 每
> 节点 dict + ReadOnlyNodePool 递归代理 / (4) node_type 字符串查表分派 / (5) StopIteration
> 异常驱动控制流；**D-3/D-3.3 实证 ~1000× 逐字符开销**（12k 窗口 sub_str 挂起 >180s；
> 170-200s vs Python <0.1s；已落地缓解 = R3-③ str 四件套 O(n)，D-3.3 VM 侧快速路径登记不
> 实施）。
> **P2 进度（收束）**：step1 ✅ AST 只读视图缓存（commit e2949d2b，~6-9%）；step2 ✅
> TypeRef.from_spec 按 spec 缓存（commit 62194fb9，~11-18%）；后段 ✅ CPS 循环每节点
> is_generator 建表期预计算（commit 5dc56f03，~4-9%）——**累计数据平面 vs P1 基线：arith
> -30.1% / branch -29.4% / recurse -24.2% / string -24.9% / container -22.1% / class -23.9%**
> （算术/分支热程序达 ~30% 目标）。调查结论：box per-call 开销 + _check_type isinstance
> 复用 = wall-clock wash 已回退；per-stmt TaskScheduler 仅顶层非热点。**P2 收束**——CPS 内
> 可干净削减项全部落地（AST 视图/TypeRef/is_generator 缓存）；剩余主导 = CPS 生成器协议核心
> [每节点 send/StopIteration] + 每节点分派 = **真 JIT/P4 范畴**（核心执行模型，高风险→隔离
> 分支）。P4 真 JIT[用户点名优先·隔离分支] / P5 持久 artifact 缓存[编译期·可并行·较低风险]
> 接续；P3 D-3.3[P1 实证已 O(n)，紧迫性下调]。
>
 > **P4 真 JIT（用户点名优先）✅ 完成 + 里程碑合并 unsafe-vibe-dev**：v1.0 codegen
 > ✅ + v1.5 cond-codegen ✅[drive-loop 交互归零，arith 179.7→36.1(~5×)/branch 262.9→50.0
 > (~5.3×)，远超 2× 目标] + v1.1 控制流 ✅[break/continue 在 cond-codegen 体合法] + 判别
 > 套件 D1-D7 ✅[15 例语义等价性验证]。**全量 3928/1 零回归**。数据平面线累计收益（vs
 > P1 基线 arith 257）：P2 收束 ~-30% → v1.0 ~-46% → **v1.5 ~-86%（~7×）**。route ①
 > 实证成功（route ② 弃）。合并：隔离分支 p4-real-jit → free-explore（ort 无冲突）→
 > ff unsafe-vibe-dev（全本地未 push）+ 文档收敛 04_vm_interpreter §12。**P4 完成**。下一
 > 里程碑：P5 持久 artifact 缓存[编译期·可并行·较低风险]；P3 D-3.3[紧迫性下调]。
>
 > **P5 持久 artifact 缓存 ✅ 完成 + 里程碑合并 unsafe-vibe-dev**：编译产物持久缓存（相同源码 + 内核
 > 版本，命中跳过 5 阶段管线，~8× 编译加速；IBCI_ARTIFACT_CACHE=1 启用默认关闭零侵入）。安全加固 +
 > 复核根因修复：pickle 信任域策略（仅 core/core.* + builtins 类引用——安全前提实证 = core 全域
 > 零 __reduce__/__setstate__ 定义）+ 缓存目录 0700/payload 0600 + 篡改拒绝 stderr 可观测 + 命中/未命中
 > 哨兵判别（复核发现首版精确白名单与产物真实类闭包不符致缓存静默死亡 → 信任域前缀策略根因修复，
 > commit 9eb638ca）。**全量 3938/1 零回归**。下一里程碑：P6 内核自举（bind 表达内核契约）[Phase 0
 > Phase 0 实证裁定完成：bind 化范围 = 工具 4 契约源 IBCI 化 + net 契约源
> [kernel 5+fs 维持宿主侧]；批次 B1→B4 计划落 tasks_docs/_p6_selfbootstrap_design.md）；P3 D-3.3[紧迫性下调]。
>
> **分阶段路线图 P1→P7**（排序 = 价值/依赖/可验证性；数据平面/真 JIT 用户点名优先；每阶段
> 闭环 = 设计确认→实现→全量零回归→落账→本地 commit[禁 push]；高破坏性/边界不清走独立隔离
> 分支永不触碰 main）：**P1 执行期性能基准 + 热路径 profile（⭐低风险先行，纯观测，解锁
> P2-P5 一切性能工作[改前/改后裁判]）→ P2 每节点开销消除[§11 不变量内]（⭐优先、中风险）
> → P3 D-3.3 字符串扫描快速路径（中高风险）→ P4 真 JIT codegen（⭐用户点名优先、高风险→
> 隔离分支）→ P5 档 A 持久 artifact 缓存[编译期与 JIT 正交，可并行]（中风险）→ P6 内核自举
> + 反射（高工作量、结构面）→ P7 档 B 进程级隔离（高风险→隔离分支）**。**当前 P0 = P6 内核自举
> 开工**（bind 表达内核契约；Phase 0 实证裁定完成[范围 = 工具 4 + net 契约源，
> kernel 5+fs 维持宿主侧；设计文档 `tasks_docs/_p6_selfbootstrap_design.md`；下一批 = B1
> 共享合成提取]——P1-P5 已全部完成收束，git 承载）。硬约束 = 9 项 VM 设计不变量
> [§11，尤其 #1 统一执行入口] + 确定性 UID 单一权威源[不得改变已产出 UID 值] + 工作模式定论。
>
> ~~meta 层 MVP（字符串级直接执行）~~ **✅ 已收束并入 unsafe（见上）**：
> 依赖评估结论——**MVP 前置依赖 = 0**（机制面全部既有：compile_string/run_string 合成
> entry / request_spawn_isolated 子环境 / E1 继承 / collect_timeout / 诊断面 / 值类型
> 注册模式；字符串源扩展点 = 子线程体 run(abs_path)↔run_string(code) 同构单点）；
> **VISION-6 内核工程化非前置**（独立线；唯一交点 = 档 B 隔离改造，MVP 落地后联合重估）；
> **VISION-4/5 类型层只约束全形态**（artifact 作值/R-6/fn[...]/Verdict），MVP 不依赖。
> **批次计划 M1 → M2 → M3 全部 ✅ 完成（2026-09-08）**（M1 run_result 值类型 + 执行路径
> 统一[commit 359b1eef，判别 23 项]；M2 meta.compile 编译门[commit 3fa51eec，判别 7 项]；
> M3 三门管线惯用法固化[howto run_code_safely.md + 参考实现[预注册向量 + 机械判定
> e34_p4 形态，实测编译验证] + 文档同步[README 单点真理表 + use_isolation LLM 继承面
> 修正]，全量零回归]）+ 范围重划对账（防半接通原则不变；全形态 M4[artifact 作值/R-6/
> fn[...]/Verdict] 登记 VISION-4/5 前置不实施）= `tasks_docs/_meta_layer_design.md` §八。
> （meta 层 MVP 已收束并入 unsafe；其后 = 内核完整系统工程化 + JIT 自主主线[当前 P0]。
> VISION-4 类型理论加固 = 独立方向[非内核工程化范畴，user-gated]，MVP 后开工输入就绪见
> `_meta_layer_design.md` §四清单。支线 = 周期质量维护 / round4 需求单到达重新 intake /
> 长期注册项按重估触发推进。）
> 其余稳定维护态工作（周期质量维护 / 长期注册项按重估触发推进 / round4 需求单到达重新
> intake）在 MVP 主线之外并行。

**当前主线 = round3 试用需求整合队列（2026-09-08 intake，free-explore）**：
试用方第三轮需求单（`ibci_feedback_round3.md`，v3 统一自动机实证摩擦全集）
已完成 intake（单点记录 = `tasks_docs/_trial_round3_intake.md`：逐条核验 +
耦合分析 + 队列）。按恒高优先原则，round3 队列插入现有阶段 E 队列之前：
**~~R3-① D-1 fielded 类×LLM 调用 VM 缺陷修复（`KERNEL_ISSUE-VM-2`）~~ 已完成
（2026-09-08：编译期构造器/方法静态绑定检查 + 运行期 auto-init 回退角落修正 +
显式内置父动态跳过；判别 25 项 + 既有 4 项语义演进 + 全量零回归，git 承载）
→ ~~R3-② D-2 三引号多行字符串~~ 已完成（2026-09-08：LEX 层 IN_TRIPLE_STRING
态 + 转义共享 _apply_string_escape + 同路径既有缺陷修复[字符串内置位
continuation_mode 泄漏吞声明收尾换行 → PAR_EXPECTED_TOKEN]；判别 36 项 +
全量 3605/1 零回归，git 承载）→ ~~R3-③ D-3/D-4 str 原语四件套~~ 已完成（2026-09-08：count 新增 + find
扩 from 选参 + find_last 改名 rfind[零消费方破坏性改名] + 原生切片实证
已支持[判别锁定+文档]；公理层变更全量 3638/1 零回归，git 承载）
→ ~~R3-④ D-5 stdout 行缓冲~~ 已完成（2026-09-08：run 命令默认行级 flush，不加 --unbuffered 旗标[裁定：行缓冲=默认底线，旗标=第二通道不设]；时间隙判别 1 项 + 全量 3645/1 零回归，git 承载）→ ~~R3-⑤ R-1+R-3+R-4 run 级可观测子系统~~ 已完成（2026-09-08：journal append-only[CLI 默认开] + --replay 确定性重放[能力槽 SYSTEM 优先级替换 provider] + 预算核算[api_config budget 节 warn/fail] + --result-json trailer；单一设计文档四批实施 + C7 消重；判别 59 项 + 全量 3739/1 零回归，git 承载）→ ~~R3-⑥ E1 重做 + R-2a run_file~~ 已完成（2026-09-08：E1 子环境 LLM 配置继承[spawn 时点活状态快照，IbStatefulPlugin save/restore 机制同构 + on_ready 钩子 + _model_registry 补漏；HOST_ISOLATE_LLM_INHERIT_FAILED 新增；ThrownException 消息面根因修复 "TypeName: message" 显示对等] + ihost.run_file 结果捕获[exit_status/stdout/exception 错误作值；output_callback 收集 + 同步 collect；防卡死 collect_timeout 经 policy]；11_modules §11.6 整节更新；判别 15 项 + 全量 3770/1 零回归，git 承载）→ ~~Tier B 质量巡检窗口~~ 已完成（2026-09-08：低强度批量巡检——已修 7 项低风险[trailer 定位提纯/ThrownException 协议化解箱/write_failed 收尾面接线/死参数·未用导入清理/历史叙述·模糊措辞注释移除] + 维持现状 4 项[合法保留，Tier C 候选已标注]；3770/1 零回归）→ **P1 六项**（~~R3-⑦ 诊断消息批~~ 已完成[2026-09-08：D-6 顶层缩进定向提示 + D-8 小写布尔 did-you-mean[既有面锁定] + B4 赋值型定位精化[RHS 值节点]；判别 8 项 + 3783/1 零回归] / ~~R3-⑧ D-7 裸声明语义~~ 已完成[2026-09-08：裁定 (c) 编译期检查[语句域裸声明无合法运行期语义——fail-fast 编译期拒绝，精确定位声明语句；类字段/for 变量/形参合法形态不受限]；新码 SEM_DECLARATION_WITHOUT_INITIALIZER 纯增面；判别 9 项 + 全量 3797/1 零回归] / ~~R3-⑨ D-10 json 鲁棒面~~ 已完成[2026-09-08：parse 返回实际值[消 _list/_value 魔法包装键，仓内零消费方] + malformed = 可捕获异常 RUN_JSON_PARSE_ERROR[新码，fail-fast 替代 print+空 dict 双兜底] + parse_or_none 显式宽松形态 + stringify/pretty 同族同修；判别 13 项 + 3816/1 零回归] / ~~R3-⑩ F-2 思考抑制警告可配置~~ 已完成[2026-09-08：可配置静默[api_config defaults.accept_forced_thinking] + 警告 stdout→stderr[数据面纪律] + 语义澄清[reasoning 隔离/思考预算/观测面] + 文档；判别 7 项 + 3827/1 零回归] / ~~R3-⑪ R-7 429 退避~~ 已完成[2026-09-08：defaults.backoff_s 配置化[缺省 0 零侵入] + provider 层 429 检测[RateLimitError/status_code] + 退避执行[sleep 后上抛，重试层退避后重试] + call_info 退避事件[last_backoff]；判别 11 项 + 3842/1 零回归] / ~~R3-⑫ R-8 knowledge 扩展面~~ 已完成[2026-09-08：provenance 字段 + history kind 过滤 + export 整库导出；判别 11 项 + 3857/1 零回归]）→ ~~R3-⑬ N3 measure_freq~~ 设计优先完成[2026-09-08：新解封；SiliconFlow logprobs 探针实证——chat 通道[IBCI 现用]静默忽略 logprobs、legacy completions 通道完整支持；裁定**待决**（挂起方向保留——corpus/probe 设计全手工内化时机未到 + 落地须新增 completions 形态通道；重估触发 = provider 支持 completions/logprob 或 corpus/probe 内化）；设计文档 `_n3_measure_freq_design.md`，无代码/测试改动]；**P1 全部收束**（R3-⑦~R3-⑬）→ ~~P2 文档批~~ 已完成[2026-09-08：R3-⑭ howto 组[F-1 漂移测量[call_info 两形态+finish_reason] + F-3 fs.write --root 实证 + D-9 保留词表[lexer 49 词单点] + F-4 embedding 通道确认[PT-FEAT-16 已落地 T16 8/8]] + R3-⑮ R-5 提案稳定性测量 howto[journal 语料+度量面+脚本]；纯文档批] → ~~Phase D meta 层/代码作值设计~~ 设计交付完成[2026-09-08：安全执行架构[run_file+meta.compile+R-6 统一，原语面+治理面分层] + 安全模型选项 A[调用方表达治理+ 三门管线惯用法+参考实现 + ihost policy 演进点] + 类型层承诺需求清单[VISION-4 开工输入，台阶④只差类型层承诺] + F5 档案重估[meta 层不依赖 F5] + 自举台阶④端到端架构；设计文档 `_meta_layer_design.md`，本运行不实施] → **round3 全部阶段收束**（A/B/C/D 全部完成/待决/设计终态）
按序。~~原批 2 剩余（A2/A5/B2）与批 3（A6/B5/C6/C7/D2/D3）~~ **Phase E 终态裁定**
[2026-09-08：A2/A5/A6/B2 = 挂起 → VISION-4 整合推进[类型层同域，待 VISION-4 类型理论
设计落地后推进，不半接通]；C7 = 完成[R3-⑤ 消重]；D3 = 挂起[随新能力配套，非独立批]；
B5 = 挂起[并发一等原语已成熟[14_concurrency + howto + KNOWN_LIMITS 边界完整]，专项需
单独立项；流式观测边界记 KNOWN_LIMITS 待评估]；C6 = 完成[多模型组合编排模式 howto：
强弱分工/跨模型校验/扇出聚合 + 关键语义澄清[behavior 型容器元素/retry 保留词]]；
D2 = 完成[check --format json 结构化诊断导出，判别 4 项 + 3867/1 零回归]]（
`tasks_docs/_next_phase_targets.md` §三）。**round3 全阶段 + 原阶段 E 顺延批全部收束**
（A/B/C/D/E 全部项处于完成/挂起/裁定不做终态——收敛判据达成）。 → ~~Phase F 收敛~~ ✅ 已完成[2026-09-08：周期质量维护 Tier B 窗口[注释任务代号 4 处已修[红线] + 宽 except 3 处 A 合法保留[best-effort] + 历史叙述注释 7 处 A 合法保留[功能语境]+ 未用 import 无命中] + 长期注册项状态复查[VISION-4/6 补设计文档指针，R-2b/R-6/N3/D-3.3/远程 CI 状态一致无漂移]；全量 3867/1 零回归[本窗口仅注释清理+文档指针，无行为变更]]。~~长期登记不实施：R-2b
meta.compile + R-6 行为表达式作值（VISION-4/5 类型类/函数式方向耦合，不半
接通）~~ **范围重划（2026-09-08 用户定向再评估，`_meta_layer_design.md` §八）**：
R-2b meta.compile 拆 **MVP**（meta.compile fail-fast 校验面 + ihost.run_code 字符串
形式 + run_result 值类型——不依赖类型层，**当前 P0 主线**）/ **全形态**（artifact
作值 + R-6 行为表达式作值——VISION-4/5 类型层前置，登记不实施，防半接通原则不变）/
D-3.3 VM 字符串扫描快速路径（VM 执行模型性能架构面，Tier C 候选）。
背景（git 承载）：P0 三线 / P1 生成参数面 / P2 四项 / 阶段 E 批次 1 /
批次 2（E2/A4/D1/C5 ✅ + E1 进行中）均已完成，基线以实跑为准。

## 下一步候选（当前主干按序；支线仅在不打断主线时介入）

**排布总则**：健康度优先（代码/架构）→ 功能稳健 → 对外能力 → 远期演进 → 真实 LLM 全面试用
（健康阈值后重启，非最高优先但必做）；同一时刻只推一个 P0。

1. **主线（2026-09-06 用户裁定：全部建议认可）= P0 三线，同一时刻只推一线**：
   ~~线 1 · 诊断面打包~~ **已完成（2026-09-07，git 承载）** →
   ~~线 2 · PT-FEAT-16 四批~~ **已完成（2026-09-07，git 承载：① 契约包 ② vector 值类型
   ③ ai 模块面 ④ T16 真实试用 8/8）** →
   **~~线 3 · N2 已验证知识注册表实施~~ 已完成（2026-09-07，git 承载：①+② knowledge 一等值类型 + 验证门 + SEM 纯度检查 + KNW_/SEM_KNW_ 码域 ③ 状态保真 + docs 16 ④ T17 7/7；附 host save_state 单层相对路径缺陷修复）**（2026-09-07 用户裁定重新定位：不以 ai 为载体、一等内置值类型/语言级知识子系统、`@~...~` 保持纯 LLM 语义无隐式路由；K1-K9 已定案；设计文档 `tasks_docs/_knowledge_registry_design.md`）。
   **P0 三线全部收官 → P1 完成 → P2 四项完成 → 阶段 E 批次 0 清场 + T2 环境变量通道 + C2 容器边缘完成（2026-09-07）**。
   **阶段 E 批次 1 全部完成 + 批次 2（E2/A4/D1/C5）完成（git 承载）**。
   **当前主线 = round3 试用需求整合队列（2026-09-08 intake）**：见
   "🔴 当前状态" + `tasks_docs/_trial_round3_intake.md` §三（R3-① D-1
   `KERNEL_ISSUE-VM-2` 修复首位 → R3-② 三引号字符串 → R3-③ str 原语四件套
   → R3-④ 输出缓冲 → R3-⑤ run 级可观测子系统 → R3-⑥ E1 重做 + R-2a
   run_file[E1 on_ready hook 形态定案；细节见 HANDOFF §2.1 + 防卡死：spawn
   测试传有限 collect 超时] → P1 六项 → P2 文档批）；原批 2 剩余（A2/A5/B2；
   B4 并入 R3-⑦）与批 3（A6/B5/C6/C7/D2/D3；C7 对照 R3-⑤ 消重）整体顺延
   **终态裁定收束**[A2/A5/A6/B2 挂起 VISION-4 / C7 完成 / D3 挂起 / B5 挂起 / C6 完成 / D2
   完成] → **round3 全收束（收敛判据达成）** → **当前 P0 = meta 层 MVP（字符串级直接
   执行）**（2026-09-08 用户定向再评估列入主线；批次计划 M1 run_result 值类型 +
   执行路径统一 → M2 meta.compile 编译门 → M3 三门管线惯用法固化；依赖评估[前置=0 /
   VISION-6 非前置 / VISION-4 只约束全形态] + 范围重划对账[防半接通原则不变] =
   `tasks_docs/_meta_layer_design.md` §八；每批全量 pytest 零回归 + 落账 + commit）；
   基线以实跑为准。
2. **支线（不中断主线时介入）· 阶段 C 真实 LLM 残留项清场（全量 LLM 回归复跑已完成）**：
   ~~① named-model 端点泄漏 2 用例（T01 D1-07-006 / T08 D5-03 硬编码旧本机端点 →
   `IBCI_TRIAL_LLM_URL`/`IBCI_TRIAL_LLM_MODEL`/`IBCI_TRIAL_LLM_KEY` env 通道）~~ **已完成
   （2026-09-07，真实端点验证通过；AGENTS.local 机器事实同步）**；
   ~~② T06 子目录布局用例（7 llm）run_batch 不收集——收集策略扩展~~ **已完成（2026-09-07：
   子目录布局收集 + 目录型用例 root=用例目录[KERNEL_ISSUE-IMPORT-2 短期 harness 解]；
   T06 全量复跑 20/20 PASS）**；
   ③ 恶意边界未测 #15/#17/#19/#33（`trials/INDEX.md` 清单，mock 层；#33 依赖 LLM-5 同
   子系统）——**#17 已核销（2026-09-07 T15-E-M29）；剩余 #15（snapshot 类字段捕获观测面）/
   #19（overlay × 序列化/snapshot/retry 交互）/ #33（LLM-5 依赖）**；缺陷追修随批 1：
   KERNEL_ISSUE-LLM-5（事件驱动监视复发）。
3. **阶段 C 文档复核登记项收敛**：~~复核登记项关闭状态交叉核验（KNOWN_LIMITS §十五 漂移 /
   call_info 键结构 / 装配未知键是否应告警 / BOUNDARY-LLM-5），doc-governance Phase 0-8~~
   **已完成（2026-09-07：call_info 键结构 = 11_modules 单点[观测契约新增]；装配未知键 =
   LLM_ASSEMBLY_UNKNOWN_KEY 警告实施[T10 M5]；KNOWN_LIMITS 漂移 = 零[dict 可迭代/尾逗号
   无相关陈旧描述]；BOUNDARY-LLM-5 = 机制澄清文档化[观测契约] + mock 路径观测面机制同构）**。
4. **周期质量维护（PT-AUDIT-1/3 + Tier B + quality-maintenance 等全部非主线质量工作）
   已解封（用户 2026-09-07 裁定）**——触发节点 = **主线任务完成后**（handoff §5.6 收敛
   判据成立：主线队列全部项处于完成/挂起/裁定不做终态）→ **自主启动**，无需再等用户
   指令。（原"真实试用后恢复"阈值已过期：真实 LLM 环境已就位。）
5. **远程 CI 启用（暂不启动，用户裁定）**：`ci.yml` 恢复 push/PR 触发（本地分层验证经
   `scripts/ci_local.sh`，不依赖远程；启用需用户显式授权）。
6. **阶段 D · 主线远期演进（试用稳定后）**：VISION-4 P7 类型理论加固 / VISION-5 P8 函数式地基 /
   VISION-1 二层 IR（见 `tasks_docs/PENDING_TASKS.md` §八）；PT-SEALED-1 保持封存。

**已解封**：PT-DECIDE-2（供应商思考禁用，2026-09-05 用户裁定解封；重估聚焦"后端强制
思考"场景——新端点 SiliconFlow 实证双字段抑制有效，重估输入已并入 P1-1 生成参数面批
随其设计自然闭合，见 handoff §5.5）。
**划远期（近期不处理）**：PT-FEAT-6/12（工具链项）。

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