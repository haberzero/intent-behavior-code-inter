# _trial_round3_intake — 第三轮试用需求接收入口（2026-09-08，free-explore）

> **单一接收入口**：试用方（ibci-trial）`docs/ibci_feedback_round3.md`（R185–R202 v3
> 统一自动机实证摩擦全集，2026-09-08）的逐条核验、定性、主线整合与长期登记。
> 权威队列以本文件 §三 为准（与 `NEXT_STEPS.md`/`WORKLOG.md`/`trials/INDEX.md` 同步落账）；
> 各任务开工时按 code-workflow Phase 0-1 重新核验代码现状（本文件是 intake 快照，非实现权威）。
> 试用方工作区 `/home/dsh/proj/ibci-trial/` 只读；其 run 存档（experiments/）为实证证据源。

## 一、逐条核验与定性（本 session 实码/实证核验）

### 1.1 正面反馈（§0，回归锁定，无动作）

错误定位链 / knowledge 注册表 / save_state / 模块两级搜索 / 缺省 void / 命名模型路由
/ LLM 可调用类迁移 / LLM-5 无复发——试用方 v3 全部批次实证良好面。LLM-5 持续
"未复发"观察面与事件驱动监视一致。

### 1.2 已落地能力反馈（§1 F-1~F-4）

| 项 | 核验结论 | 定性 |
|----|----------|------|
| F-1 call_info 弱模型测量 howto + finish_reason 最小用法 | 能力已在（T18），缺可运行示例 | **文档项**（R3-P2） |
| F-2 思考抑制"覆盖缺口"通知 | **真相核验**：警告为**每进程一次性**（`_thinking_suppress_failed_warned` 去重，run 存档实证 e34_p2_run2 / e34_p3_run1 各 1 次，非每调用）；试用方模型 `Qwen/Qwen3.5-4B` 后端强制思考为**事实**（reasoning 被服务端 parser 隔离进 `reasoning_content` 字段，content 干净——试用方只看 stdout 故"实测无思考内容"）；机制按设计工作（C5 定案的"强制思考场景"正是此面） | **小功能项**：可配置静默 + 语义澄清文档（R3-P1） |
| F-3 fs.write --root 语义示例 | 11_modules §11.7 已有 API 文档，缺 --root 场景最小示例（写入目标基准 + 越界错误码） | **文档项**（R3-P2，开工先实证语义） |
| F-4 embedding 通道确认 | T16 8/8 已验收（SiliconFlow 通道）；试用方 v3 端点为其自配（Qwen3-Embedding-0.6B 同模型），无漂移面 | 无动作（回复确认） |

### 1.3 P0 内核缺陷（§2 D-1~D-5）

| 项 | 核验结论 | 定性 |
|----|----------|------|
| **D-1 fielded 类×LLM 调用 → `VM: missing required argument`（参数名空）** | **根因已定（2026-09-08 实码核验，试用方 min_repro 独立复现 100%）**：非 VM 分派污染（试用方 R183 归因有误——其最小复现 `class Ctx: str tag` + `Ctx c = Ctx()` + `@~` 中，失败点在 **`Ctx()` 构造器调用自身**（traceback 实证：vm_handle_IbAssign→vm_handle_IbCall→_shared.py:179，报错参数名 = 字段名 'tag'））。真实缺陷 = **语义层无类构造器/方法调用静态参数绑定检查**（盲区实证：`Ctx()` 缺必填/`Ctx("a","b")` 多参/`Ctx(x="a")` 未知具名全部编译通过 → 运行期裸 RuntimeError 无码无行）；`Ctx()` 缺必填是 IBCI 合法报错（auto 构造器参数 = 继承链全部无默认值字段，父先子覆写——interpreter.py:908-941 运行期权威），缺陷在诊断质量（裸 RuntimeError 逃诊断体系：无诊断码/无 ibci 源行列/无说明 → 试用方误读为 LLM 分派 bug 并回避 fielded 类 = 数据建模硬阻塞的真相）。普通函数调用静态检查已齐（SEM_MISSING_REQUIRED_ARG 等四码，test_function_params 锁定）；盲区 = 类构造器（auto/explicit __init__）+ 方法调用（现仅 warn 级 SEM_CONTAINER_METHOD_HINT 类型提示，无绑定检查） | **✅ 已修复（2026-09-08，定性修正：诊断/语义检查缺陷 + 运行期 auto-init 回退角落缺陷，非 VM 机制缺陷）**：① 语义层构造器调用静态绑定检查（`registry.get_constructor_descriptors` 单入口：explicit __init__ 精化描述符 / auto = 链上有效无默认值字段，与运行期共享 `merge_decl_fields` 单一规则源；接入统一 `_resolve_with_descriptors`：同一 resolve_call_binding + SEM_* 四码 + ibci 源行列 + kind 感知主语）；② 零参绑定方法 arity 补全（param_types=[] 收集期权威）；③ **运行期 auto-init 回退条件修正**（实施中新发现：链上无必填字段时原回退"继承父构造器"把"子类同名覆盖父类无默认字段为默认值"误判为"链上无字段"——`class Base: str name` + `class Sub(Base): str name = "d"` + `Sub()` 运行期误要求 name，编译期/运行期语义分裂；修正 = 链上有字段 → 零参 auto-init，链上无字段 → 继承祖先显式构造器）；④ 显式内置父（如 `MyList[T](list[T])`）构造器调用动态跳过（auto 字段规则仅适用纯用户类链，防误报）。判别 25 项 + 既有 4 项语义演进 + 全量零回归。残余面（登记不扩）：动态接收者（any 类型 callee）构造器/方法调用仍运行期裁决 |
| D-2 无多行字符串（三引号 → LEX_UNTERMINATED_STRING ×16） | lexer 无语言级三引号形态（实证）；提示词 = 自动机核心资产，逐行拼接为 round1 以来最高频字符串摩擦 | **P0 语言特性**（LEX/PAR 面 → 全量 pytest 门；语义按 Python 三引号：保留内部换行、转义同单行；`'''` 是否同支持 = 开工设计裁定） |
| D-3 字符串原语 O(n²)/VM 逐字符 ~1000× 开销 | 实证：试用方 `sub_str` 逐字符拼接 12k 窗口挂起（>180s）；机制栈扫描习语 170-200s vs Python <0.1s。str 原语面缺 count/rfind/find(m,from)/原生切片（D-4 同面） | **P0 内建 str 面扩展**（四件套 O(n) 原生实现，机制栈代码量 -40%+）；**VM 逐字符分派快速路径（D-3.3）= VM 性能架构面 → 长期登记不实施**（不半接通） |
| D-4 str.find 单参（双参 RUN_TYPE_MISMATCH） | 与 D-3 同面（str 方法表） | 并入 R3-③（find(m,from) 重载 + 12_builtins 同步） |
| D-5 stdout 缓冲至进程结束（长 run 不可观测，无法区分"慢"与"挂"） | 实证：`main.py:167 print(output)`——ibci stdout 累积至 run 末输出 | **P0 小项**（行级 flush 或 --unbuffered 旗标；开工先实证 ibci print 通道全路径） |

### 1.4 P1 语言层（§3 D-6~D-10）

| 项 | 核验结论 | 定性 |
|----|----------|------|
| D-6 顶层缩进 PAR 诊断无说明 | 错误码准确（PAR_UNEXPECTED_TOKEN），缺"顶层不得缩进"提示行 | 诊断消息小项（R3-P1，与 D-8 同批 + **原批 2 B4 编译定位并入同批**） |
| D-7 裸类型声明 = None 初始化 → RUN_TYPE_MISMATCH 指向声明行（归因误导） | 试用方证据准确（e34_p7 双批次）；三选项：(a) 零值缺省初始化 / (b) 诊断改进指向首读点 / (c) 编译期检查 | **设计裁定项**（R3-P1；开工作设计对照——初步倾向 (b) 精确诊断：ICBI fail-fast 纪律下 (a) 零值缺省是魔法默认，(c) 条件初始化路径分析面大；最终以设计对照定） |
| D-8 true/false 小写 SEM_UNDEFINED_SYMBOL 每批首写中招 | 语义正确（须 True/False）；缺 did-you-mean 提示 | 诊断消息小项（R3-P1 同批 D-6） |
| D-9 保留词无单点文档（fn 碰撞） | SYNTAX_REFERENCE 无保留词表 | **文档项**（R3-P2） |
| D-10 json.parse malformed → print + 缺键 dict（双副作用）；数组须包装 | 解析侧鲁棒面缺口（C2 已落地生成侧）；请求：(a) 数组直 parse (b) parse_or_none 显式形态（失败 = none，无 print 副作用） | **P1 内建 json 面**（R3-P1；fail-fast 形态 = 显式可判失败，消 print 副作用） |

### 1.5 P0 自动机最紧要特性（§4 R-1~R-5）

| 项 | 核验结论 | 定性 |
|----|----------|------|
| **R-1 LLM 调用 journal + 确定性重放**（治理可审计性命脉） | 面不存在（grep 实证：无 journal/replay 通道）；call_info = 单次调用面，journal = 全 run 语料面，互补 | **P0 新子系统**（与 R-3/R-4 同一设计——见下） |
| R-3 run 级预算/令牌核算（tokens/calls/wall + api_config 阈值） | 面不存在（无 run_summary）；per-call generation 面已有（T18），此为 run 级聚合 | 并入 R-1 同一子系统（同源数据） |
| R-4 机器可读 run 摘要（--result-json：exit_status/exception{code,message,source}） | 面不存在；异常对象已携带 source（B1 面），JSON 化是最后一步 | 并入 R-1 同一子系统 |
| R-5 弱模型测量面 howto | 依赖 F-1（call_info 示例）+ R-1（journal 语料） | **文档项**（R3-P2，R-1 落地后；试用方 e33_p37/e34_p2/e34_p4 记录面授权引用为示例语料） |
| **R-2 进程内子 run / 编译** | R-2a run_file：ihost 子环境基建已有（独立 Engine + collect + save/load），缺"进程内运行另一 .ibci 文件 + 结果捕获"消费面；**与 E1（子环境 LLM 配置继承）同属 ihost 子环境设计域**（试用方实证注记"子环境不继承 LLM 配置 + 需自身 api_config"= E1 的语义需求）。R-2b meta.compile（字符串代码进程内编译作值）：**耦合长期类型类/函数式方向（VISION-4/5）+ 自举台阶 4（R-6）** | R-2a = **P0**（与 E1 整合设计，R3-⑥）；**R-2b = 长期登记不实施**（用户原则：架构安全与长期收益优先，不半接通 meta 层） |

### 1.6 P2/战略（§5 R-6~R-8）

| 项 | 定性 |
|----|------|
| R-6 行为表达式作为值（meta 层，长期） | **长期登记**（VISION-4/5 类型类/函数式方向合流；试用方 e34_p4 行为契约测试形态 = 设计参考——预注册向量+机械判定，与 MOCK 模板验收互补） |
| R-7 provider 429 rate-limit 自动退避（retry.backoff_s 配置化 + call_info 退避事件） | **P1 内建 provider 面**（R3-P1） |
| R-8 knowledge 扩展面（export / history kind 过滤 / provenance 字段） | **P1 knowledge 模块面**（R3-P1；均 P2 级价值，试用方手工替代已验证可行——排批内后段） |

## 二、耦合分析（架构安全 / 长期收益优先裁定）

1. **R-2b / R-6（meta 层）**：与 VISION-4/5（类型理论加固 / 函数式地基）同域——meta.compile
   是"代码作值"的入口面，属类型层承诺（自举台阶 4 明确"只差类型层承诺"）。**裁定：不实施，
   长期登记**；实施须待类型类/函数式方向设计落地后按该方向推进，禁止以"试用方急需"为由
   半接通（工作模式定论：禁止半修复/半接通）。
2. **D-3.3（VM 字符串扫描快速路径）**：VM 逐字符操作经生成器分派的 ~1000× 开销是 **VM
   执行模型性能架构面**（生成器分派 = CPS 协作让出的代价面，与 PT-DEBT-29 协作化同域）。
   **裁定：不实施，长期登记**（Tier C 专项审计候选）；R3-③ 内建四件套（O(n) 原生方法）
   消解 90%+ 试用方摩擦而不动 VM 执行模型。
3. **R-1/R-3/R-4（run 级可观测）**：单一子系统（journal = 调用级语料、budget = 聚合面、
   result-json = run 级判定面，同源数据同设计）。**裁定：一个设计文档一批批实施**；
   设计时对照原批 3 C7（性能内省：单调时钟/调用级埋点）——同源面不双通道（C7 若与本
   子系统重叠则并入，不另起）。
4. **E1 + R-2a（ihost 子环境）**：E1（子环境 LLM 配置继承，设计定案 on_ready hook 形态）
   是 R-2a run_file 的前置（子环境配置语义须先定）。**裁定：整合为一个"ihost 子环境完善"
   设计**（E1 继承语义 + run_file 结果捕获契约 {exit_status, stdout, exception} +
   沙箱继承（--root 门禁）+ 配置源语义）。
5. **D-7（裸声明语义）**：触及语言值语义（初始化契约）——开工作设计对照，以 IBCI 类型
   系统 fail-fast 纪律为基准（不为消除摩擦引入魔法默认）。
6. **D-2（三引号）**：LEX/PAR 面变更——语义错误集邻域，全量 pytest 门 + KNOWN_LIMITS
   检查（确认非设计排除项）。

## 三、主线整合（新队列，2026-09-08）

> 恒高优先原则（用户 2026-09-07 裁定）：真实试用者需求始终优先。round3 队列插入
> 现有阶段 E 队列之前；原批 2 剩余 / 批 3 整体顺延（保留不丢弃）。

### P0（按序，每步全量 pytest 零回归 + commit + 落账）

1. **R3-① D-1 修复**（KERNEL_ISSUE-VM-2）✅ **已完成（2026-09-08）**：mock 确定性复现
   （试用方 min_repro 100%）→ 根因（语义层无构造器/方法静态绑定检查 + 运行期
   auto-init 回退条件把"链上全默认/子类覆盖"误判为"继承父构造器"）→ 修复
   （编译期构造器描述符单入口 `get_constructor_descriptors` + 零参方法 arity
   补全 + 运行期回退两形态区分 + 显式内置父动态跳过防误报）→ 判别 25 项
   （tests/compiler/semantic/test_constructor_call_binding.py）+ 既有 4 项测试
   语义演进（运行期→编译期，触发场景保留）+ 全量零回归。
2. **R3-② D-2 三引号多行字符串** ✅ **已完成（2026-09-08）**：双形态
   同构（双/单三引号定界均支持）+ raw 前缀正交 + 值语义对照 Python（换行
   保留含首个换行、缩进保留、闭合=连续三引号、转义表与单行同一规则源
   [_apply_string_escape 共享]、反斜杠+换行=拼接）；实施 = LEX 层
   IN_TRIPLE_STRING 态（机制同构：多行构造独立 SubState 先例 = IN_BEHAVIOR）；
   同路径既有缺陷修复（字符串内置位 continuation_mode 泄漏吞声明收尾换行
   → PAR_EXPECTED_TOKEN，实证触发后移除字符串内置位）；判别 36 项 +
   文档（01_types §1.1.1 字符串字面量权威节）+ 全量 3605/1 零回归。
3. **R3-③ D-3/D-4 str 原语四件套** ✅ **已完成（2026-09-08）**：缺口面实证
   收窄（probe 先行）——原生切片已支持（s[1:3]/s[::2] 实证 OK）= 判别锁定
   +文档；count(sub[, from]) 新增（运行期+公理表）；find 扩 from 选参（公理表
   声明全形 [str,int]——split 先例：内建方法编译期绑定非严格）；find_last 改名
   rfind（试用方点名 Python 惯用语 + 仓内零消费方，破坏性改名不留兼容层）。
   from 语义直接委托 Python 原语（负偏移对等）。判别 27 项
   （test_str_primitives.py）+ 12_builtins §12.2 同步 + 公理层变更全量
   3638/1 零回归。D-3.3（VM 快速路径）维持长期登记。
4. **R3-④ D-5 stdout 行缓冲/--unbuffered** ✅ **已完成（2026-09-08）**：通道
   实证（CLI run → engine silent=True + output_callback=None → _print → Python
   print → sys.stdout；缓冲源 = Python 非 TTY 块缓冲非 ibci 累积；无修复态
   时间戳实证 L1/L2 同刻到达[终止 flush 1.7ms]）；设计裁定 = run 命令默认行级
   flush 不加旗标（试用方请求二选一；行缓冲=默认底线，旗标=第二通道不设）；
   实施 = main.py run 分支 sys.stdout.reconfigure(line_buffering=True)；时间隙
   判别 1 项（第一版 poll() 竞态误过后重构；双向验证）+ 15_diagnostics §诊断
   工具补 run 输出语义 + 全量 3645/1 零回归。
5. **R3-⑤ R-1+R-3+R-4 run 级可观测子系统**：设计文档 `_run_observability_design.md`
   （journal append-only + --replay 确定性重放 + run_summary 预算面 + --result-json；
   对照 C7 消重）→ 批次实施 ① journal ② replay ③ budget ④ result-json。
6. **R3-⑥ E1 重做 + R-2a run_file（ihost 子环境完善）**：整合设计（E1 on_ready hook
   形态[定案] + run_file 结果契约 + 沙箱/配置源语义；防卡死：有限 collect 超时）→
   实施 + 判别（mock 模式）。

### P1（按序）

7. **R3-⑦ 诊断消息批**：D-6 顶层缩进说明 + D-8 true/false/None did-you-mean + 原批 2
   B4 编译定位并入。
8. **R3-⑧ D-7 裸声明语义**：设计对照（零值缺省 vs 精确诊断 vs 编译期检查）→ 裁定实施。
9. **R3-⑨ D-10 json.parse 鲁棒面**：数组直 parse + parse_or_none 显式形态（消 print
   副作用，fail-fast 形态）。
10. **R3-⑩ F-2 思考抑制警告可配置**：api_config 可配置静默 + 语义澄清（reasoning 隔离
    字段 = 思考预算已消耗；provider_meta[reasoning] 观测面）+ 文档。
11. **R3-⑪ R-7 provider 429 退避**：retry.backoff_s 配置化 + call_info 退避事件记录。
12. **R3-⑫ R-8 knowledge 扩展面**：export / history kind 过滤 / provenance 字段。

### P2（文档批）

13. **R3-⑬ 文档 howto 组**：F-1《弱模型输出漂移测量》（call_info 两形态 + finish_reason
    最小用法）+ F-3 fs.write --root 最小示例（实证语义）+ D-9 保留词表（SYNTAX_REFERENCE
    单点）+ F-4 embedding 通道确认回复。
14. **R3-⑭ R-5《弱模型提案稳定性测量》**：依赖 R3-⑤ journal 落地；试用方 v3 记录面
    （e33_p37/e34_p2/e34_p4，授权引用）为示例语料。

### 长期登记（不实施，git/WORKLOG 承载）

- D-3.3 VM 字符串扫描快速路径（VM 执行模型性能架构——Tier C 专项候选）
- R-2b meta.compile + R-6 行为表达式作为值（meta 层——VISION-4/5 类型类/函数式方向；
  试用方 e34_p4 行为契约测试形态为设计参考）

### 原队列顺延（保留）

- 原批 2 剩余：A2 泛型约束 / A5 解构 / B2 惰性结构（B4 已并入 R3-⑦）
- 原批 3：A6 Enum 增强 / B5 并发成熟化 / C6 流式编排 / C7 性能内省（设计对照 R3-⑤
  消重）/ D2 CLI 导出 / D3 配套诊断码
- 被动项不变：#33 / LLM-5 事件驱动监视；远程 CI 待授权；阶段 D 远期演进

## 四、上报/待决项（穷尽自主手段后仍无法决定）

- 无。round3 全部项可自主推进（D-7 语义取舍按"设计对照 + 自主裁定 + 详记"处理；
  触及公理层/语义错误集的面（D-2 LEX/PAR、D-7 值语义）以全量 pytest 破坏面评估为门）。
