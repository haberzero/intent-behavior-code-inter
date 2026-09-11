# PENDING_TASKS — 远期任务规划

> 本文档是 IBCI 的**远期任务正式清单**（单一权威源）。按 `tasks_docs/GOVERNANCE.md`
> 治理章程维护：已完成条目从本文档移除（历史由 git 承载）；条目状态变更随任务推进更新。
> 当前主线与下一步候选见 `tasks_docs/NEXT_STEPS.md`。
>
> **书写要求**：新增/修改条目必须按本文尾部「书写模式」模板与格式书写，保持一致。

## 〇、概览

| 域 | 活跃 | 搁置 | 封存 | 说明 |
|----|------|------|------|------|
| FEAT（功能） | 3 | 1 | 0 | 语言/工具链功能（PT-FEAT-16 embedding 一等能力 done[四批落地]；PT-FEAT-17 N3 度量 shelved；PT-FEAT-5 远程 CI 启用待用户授权） |
| DEBT（技术债） | 0 | 1 | 0 | 架构缺陷与清理项（PT-DEBT-35/36 已完成；PT-DEBT-5 搁置） |
| AUDIT（审计） | 3 | 0 | 0 | 周期审计与健康检查 |
| DOC（文档） | 1 | 0 | 0 | 文档体系缺口（PT-DOC-4 文档示例验证闭环[待评估]；PT-DOC-3P2 done） |
| TEST（测试） | 1 | 0 | 0 | 测试体系缺口 |
| DECIDE（决策） | 1 | 0 | 0 | 待裁定设计问题（PT-DECIDE-2 已解封[覆盖缺口收窄为后端强制思考场景的探测/降级语义 + 其它供应商映射实施窗口]；PT-DECIDE-3 done） |
| SEALED（封存） | 0 | 0 | 1 | 显式封存（恢复需解封评估；embedding 边界已裁定切出 → PT-FEAT-16） |
| VISION（愿景） | 5 | 0 | 0 | 远期方向（VISION-4/5 = user-gated；VISION-6 = 主线进行中[P1-P6 ✅，P7 = 当前 P0]；VISION-8 = Round4 基础智能基底[P0 需求单已登记，P7 后最高优先]；VISION-3/7 done） |

---

## 一、功能规划（FEAT）

### PT-FEAT-5 语义错误用户友好化 + 诊断工具 + CI/CD

- **状态**：active（CI/CD 可靠化设计已落地 2026-08-20，远程启用待用户授权）｜**域**：FEAT｜**优先级**：P2
- **动机**：语义错误（`SEM_xxx`）转用户友好表述、符号表/类型绑定导出、编译基准，服务语言易用性与可诊断性。
- **成因**：语义 4 阶段管线稳定后暴露的错误可读性/工具链缺口。
- **当前理解**：前三项已落地（诊断码目录 + 符号表/类型绑定导出 + `bench` 编译基准）。**CI/CD
  可靠化/实用化设计已落地（阶段 B6）**：四层可靠性（L1 fast 单元/契约、L2 全量
  跨平台矩阵、L3 真实 LLM e2e 手动可选、L4 发布产物 build+smoke）+ `scripts/ci_local.sh` 本地
  分层复现；`.github/workflows/ci.yml` 保持 `workflow_dispatch`（远程启用待用户显式授权后恢复
  push/PR 触发并 push）。落地物：`scripts/ci_local.sh` + `.github/workflows/ci.yml`（分层模板，
  保持 workflow_dispatch；设计临时文档 `_code_cicd.md` 已按治理删除，git 承载历史）。
- **关联**：PT-FEAT-6（前置条件引用）。

### PT-FEAT-6 CompilationResult 字段精简

- **状态**：active（远期·近期不处理，用户 2026-08-19 划为更远期项目）｜**域**：FEAT｜**优先级**：P3
- **动机**：编译产物字段承载冗余信息，精简后利于序列化契约稳定与维护者心智负担。
- **成因**：管线演进中字段逐步累积，未做过系统性收敛。
- **前置**：PT-FEAT-5 完成 + 管线稳定 ≥ 1 月（诊断/导出/基准就绪）。
- **当前理解**：无独立设计文档，需先盘点 CompilationResult 消费方再定精简面。

### PT-FEAT-12 AST 节点 UID 字段（编译期可见）

- **状态**：active（远期·近期不处理，用户 2026-08-19 划为更远期项目）｜**域**：FEAT｜**优先级**：P3
- **动机**：UID 现仅序列化时生成、编译期不可见；编译期可见的 UID 可供诊断工具与
  元数据导出直接引用。
- **成因**：原 `docs/architecture/02_metadata_ast.md` 愿景内容（§九 优化4）。
- **当前理解**：涉及 AST 结构变更（新增可选字段），实施前须查 `02_metadata_ast.md`
  元数据规约；低优先级，无阻塞。

### PT-FEAT-16 词嵌入（embedding）一等能力（阶段 E · ref C1）

- **状态**：done（四批落地：契约包 / vector 值类型 / ai.embedding 语言面 + MOCK:VEC /
  试用 T16 8/8；语言面文档收敛 = `docs/syntax/11_modules.md` ai 节 +
  `docs/syntax/15_diagnostics.md` EMB_ 诊断码；设计文档已删除，git 承载）｜**域**：FEAT｜**优先级**：P0
- **动机**：灰盒自动机愿景的关键缺口（ref C1）——检索/候选生成/相对排序的语义侧当前
  完全无法在 ibci 内做，是"不寄生 Python"的最大单点。
- **成因**：外部灰盒自动机工作区实证（trial2 e18：短词坍缩、VSA 需离散层）；阶段 E
  用户裁定"embedding 是必须的"。
- **当前理解**：**系统级架构设计先行（用户明确纪律）**——embedding 不是"一种数据结构
  或一个库函数"，须与 LLM 同等严肃对待：语言级表现形态、职责边界、承载的数据结构、
  系统级角色、ibci 其它全部元素与新成员的交互协议，经设计哲学（单一权威源/设计语言
  统一/机制同构/配合模式统一/一致性先于便利）全面审视；深读 LLM 集成先例（协议化
  契约/provider 契约/ai 模块面/mock 体系/序列化与类型边界五地基）作为机制同构基准。
  范围基线（ref C1）：vector 类型 + 相似度（cosine）+ 向量检索 + 与 LLM 协同 +
  OpenAI 兼容 embeddings 服务接入。设计过程（系统级架构设计先行纪律/五层同构/
  配置单源）git 承载。

---

## 二、技术债（DEBT）

### PT-FEAT-17 N3 弱模型输出漂移度量（logprobs 通道）

- **状态**：shelved（设计完成、实施未启动、方向保留；重估触发 = provider 支持
  completions/logprob 通道，或 corpus/probe 内化时机成熟）｜**域**：FEAT｜**优先级**：P3
- **动机**：试用方需求（round3 N3 measure_freq）——弱模型输出漂移的频率度量需 logprobs
  通道。
- **唯一探针实证**：SiliconFlow——chat 通道（IBCI 现用）静默忽略 logprobs；legacy
  completions 通道完整支持。设计 + 实证记录 = `tasks_docs/_n3_measure_freq_design.md`
  （活跃挂起，不删）。

### PT-DEBT-5 全项目文件命名清理

- **状态**：shelved｜**域**：DEBT｜**优先级**：P3
- **动机**：过短/欠层次/欠区分度/影子化内建的代码文件命名排查。
- **搁置原因**：破坏面大纯机械，独立窗口执行。
- **当前理解**：无明确清单，启动时先做命名扫描。

### PT-DEBT-35 `_ctx` 内部契约完整形式化（intent_context 判别单一权威）

- **状态**：done（`_ctx` 契约单一权威 = `intent_context.get_intent_ctx`/`set_intent_ctx`
  精确判别[isinstance]，全仓 ~10 处字段探测双轨收敛；过程与判别测试 git 承载）｜**域**：DEBT｜**优先级**：P2

### PT-DEBT-36 intent_context 方法族结构重构 + axiom 声明能力契约校验

- **状态**：done（方法族收敛至 `_ic_get_ctx`/`_ic_frame` 单一权威访问[消 10 处恒真死守卫]；
  `_verify_axiom_bindings` bootstrap 末契约校验；`bool | bool` 误绑 `type.__or__` 修复；
  过程与判别测试 git 承载）｜**域**：DEBT｜**优先级**：P2

### PT-DEBT-37 engine run_string(variables=...) 运行时注入缺陷（RUN_UNDEFINED_VARIABLE）

- **状态**：registered（2026-09-11 P9 ⑦ 切换门侦察发现）｜**域**：DEBT｜**优先级**：P2
- **动机**：⑦ 状态面差分门构建中实证：`engine.run_string('print(a)\n',
  variables={'a': 42})` 编译通过（variables 编译面预知符号名 ✅）但运行时 VM
  报 RUN_UNDEFINED_VARIABLE（`scope___string_exec__:a` 未定义）——
  rt_scheduler.execute 的 `runtime_context.define_variable(name, val)` 注入
  未生效于 VM 符号 UID 查找面（注入/符号绑定/当前 scope 三者的衔接缺陷）。
- **当前理解**：既有 Python 运行时缺陷（非 Rust 化引入）；⑦ 切换门变量面
  契约 = Rust 状态面（run_artifact_state 初始注入 + 最终状态导出，已自洽
  验证）——修复面归 Python 运行时批次（define_variable → runtime_context
  符号 UID 绑定面核查）。

### PT-DEBT-38 ⑦ 切换缺口批次（Rust 值模型保真度长尾——engine 面分区路由已隔离）

- **状态**：registered（2026-09-11 P9 ⑦-1c 切换门全量放行门收敛发现）｜**域**：DEBT｜**优先级**：P2
- **背景**：⑦-1c engine 路由接入后全量 pytest = 4307 passed / 4 failed（4 例
  全部 = 本条目登记的 Rust 值模型保真度缺口——生产行为经面分区路由已隔离
  至 Rust 已证数据面，4 例 = 宿主 .call 桥 / Optional 实例同一性两族）。
- **面 1：宿主 .call 桥函数值保真度（2 例 =
  tests/runtime/test_call_drive_convergence.py::TestCallHostSemantics::
  test_user_function_void_returns_none / test_user_function_explicit_return）**：
  数据面源含用户函数声明 → Rust 执行 → 状态镜像函数值 = 显示形态串（repr
  契约）→ 宿主侧 `obj.call(None, args)`（.call 薄包装路径）无 .call 面。
  **修复面**：Rust 函数值宿主调用桥（bridge API：按名/值调用 Rust 内核函数
  值 + 参数注入 + 返回导出——状态面 run_artifact_state 的函数值扩展）或
  镜像物化可调用代理（经 bridge 委托 Rust 执行）。
- **面 2：Optional 实例同一性（2 例 =
  tests/runtime/test_optional_value_model.py::test_none_is_literal_and_
  identity_preserved / test_optional_is_identity_preserved_between_optionals）**：
  两个空 Optional 变量 `a is b` = False（Python 包装实例恒等面——每赋值
  新实例）；Rust 值模型空 Optional = None_ 单例 → `is` = True。
  **修复面**：Rust Optional 包装值变体（每空 Optional = 独立实例 + is 恒等
  语义 + 现有 unwrap/is_none/is_some 面穿透）或窄路由规则（含 2+ Optional
  声明 + is 比较的源 → Python）。
- **非缺口面（已证）**：数据面 print 等价（34 语料 + 探针全管线）；错误码
  契约（RUN_* 映射 + 现场位置 line/col/file_path）；闭包/nonlocal；类型
  错误面（str 混合运算 TypeError + 关系跨族 TypeError + 容器特化身份
  递归绑定）；内征/方法面（str 方法全集 + optional 方法 + list/dict 方法 +
  位运算/bool 算术）；三引号串 + 资产引用常量；递归深度守卫 + KDIAG 事件。

---

## 三、周期审计（AUDIT）

### PT-AUDIT-1 代码异味核对分析

- **状态**：active（周期，用户 2026-08-20 裁定推迟到真实试用后）｜**域**：AUDIT｜**优先级**：P2
- **动机**：按 code-quality/code-odor 技能周期回顾；历史 CODE_SMELL_AUDIT 结论（A/B/C/D 全量定案）已并入 WORKLOG 与 git。
- **当前理解**：A/B/C/D 全量定案已完成；**D2「hasattr 全量逐点分类」已由 Tier C 专项审计完成**
  （113 处位点分类：58 合法保留 / 50 简单异味 / 4 真缺陷 / 4 深层次，处置见
  NEXT_STEPS Tier C + WORKLOG 审计记录）；周期复核。

### PT-AUDIT-2 条件分支与异常嵌套复杂度审计

- **状态**：active（独立窗口）｜**域**：AUDIT｜**优先级**：P2
- **动机**：巨型 elif 分派链（`runtime_serializer._collect_instance` 深度 16、
  `_get_instance` 17、`core_scanner` 10、`binding_analysis_pass` 9）——方向：
  分派表/守卫子句。
- **当前理解**：ibci_ai 窄化、auto_discovery fail-fast 生效（A 类保留）。**前提复核（本 session）**：
  实测核心模块最大 if/elif 平铺链长 2、最大缩进 24 空格（6 层，多来自 for+if 组合嵌套）——
  未发现 >5 层纯 if/elif 分派链；`_collect_instance`/`_get_instance`/`core_scanner` 的"深度
  16/17/10"主张与现状不符（历史代码已重构摊平）。条目收窄为对 for+if 组合嵌套的可读性抽查
  （低优先级，随主线顺带）。

### PT-AUDIT-3 代码复核审查循环（R 系列）

- **状态**：active（周期，用户 2026-08-20 裁定推迟到真实试用后）｜**域**：AUDIT｜**优先级**：P2
- **动机**：R1-R5 已执行；复核清单按 code-review 技能流程执行（历史 PENDING_REVIEW_ITEMS 结论已入 git）。
- **当前理解**：随主线阶段边界择机启动。

---

## 四、文档（DOC）

### PT-DOC-3P2 How-to 层补齐（读者旅程）

- **状态**：done（补齐 `use_isolation.md` + `orchestrate_llm_calls.md` + 交叉引用接线 +
  代码示例实跑验证；过程 git 承载）｜**域**：DOC｜**优先级**：P2

### PT-DOC-4 文档示例验证闭环

- **状态**：active（待评估："文档示例抽取冒烟验证"机制可行性）｜**域**：DOC｜**优先级**：P3
- **动机**：docs 代码块无"与内核对账"机制（诊断/语法有契约测试，文档示例没有）——治理
  缺口；`env("KEY")` 漂移实证暴露（docs 示例用漂移形态未被拦截）。

---

## 五、测试（TEST）

### PT-TEST-2 e2e 测试覆盖率提升

- **状态**：active（阶段 B 主体已补齐，剩余随主线顺带）｜**域**：TEST｜**优先级**：P2
- **动机**：覆盖缺口由 `tests/COVERAGE_MATRIX.md` 矩阵 `🔶 缺失` 项承接。
- **当前理解**：`for...if` 过滤、复合赋值运算符 e2e 已补；**阶段 B 缺口全收敛（B1）**
  ——新增判别测试 17 项（INV-CAST-2 隐式转换 / INV-INTENT-PRIORITY-2 / INV-INTENT-FLOW-3 /
  INV-MOCK-3 / 模块缓存 / 循环 import / switch 内 return）+ 矩阵卫生（INV-INTENT-SCOPE-3 已有
  snapshot 冻结测试、INV-LLMEXCEPT-CATCH-4→5 重号、switch 已有 break+continue）+ §7 模块重载
  =设计排除（无热重载机制，违反解释器不修改代码原则，见 `docs/architecture/01_principles.md`）；
  剩余缺口随主线顺带补齐。

---

## 六、决策（DECIDE）

### PT-DECIDE-2 供应商感知的模型思考禁用机制

- **状态**：active（用户 2026-09-05 裁定解封；批次 = 阶段 E 批 2 重估）｜**域**：DECIDE｜**优先级**：P2
- **动机**：思考禁用/探测是 provider 侧能力；API 参数对部分部署无效时，IBCI 侧需按
  供应商参数形态实现思考禁用/检测失败覆盖。
- **成因**：真实 LLM 试用环境调查实证（LM Studio model.yaml 机制）。
- **当前理解**：机制边界已由 LLM 调用层插件化定案——`LLMCallRequest.thinking_mode` 是
  供应商无关声明，各供应商字段映射在各自 provider 实现内完成。**新实证（2026-09-05，
  vLLM 端点迁移）**：推荐 provider 双形态抑制字段（顶层 `enable_thinking=false` +
  `chat_template_kwargs.enable_thinking=false`）对 vLLM 有效性实证通过（非思考亚秒、
  零告警），顶层单发被 vLLM 静默忽略——覆盖缺口收窄为"后端强制思考（API 无法关闭）"
  场景；重估聚焦该场景的探测/降级语义（现状 = 一次性警告），及其它供应商参数映射的
  实施窗口。

### PT-DECIDE-3 LLM prompt 协议家族待决项

- **状态**：done（项①-④ 全部定案：① `__from_prompt__` 单向契约[返回值必须是目标类型实例，
  非实例=契约违约，删三级启发式兜底]；② 不扩展至内置类型[内置预校验由内建解析器单一权威
  承担，`impl` 在内置类型上定义解析协议方法编译期 SEM_TYPE_MISMATCH 拒绝]；③ required
  协议成员签名违约升编译错误；④ `__to_prompt__` 异常回退可观测发射
  `KDIAG_PROTOCOL_TO_PROMPT_FALLBACK`；过程实证 git 承载）｜**域**：DECIDE｜**优先级**：P2

## 七、封存（SEALED）

### PT-SEALED-1 media Phase 4 多模态容器

- **状态**：sealed（无限期搁置；**embedding 边界已裁定切出**——用户 2026-09-05 裁定：
  词嵌入是语义内容缝基础能力、非媒体，独立立项解封，见 VISION-7/PT-FEAT-16）｜**域**：SEALED｜**优先级**：—
- **动机与成因**：多模态为远期愿景；前置（路径统一/内核原生化/磁盘型存储）已完成，
  但因语言主线（类型地基/协议化）长期优先而显式封存。
- **解封条件**：恢复需显式解封并重估；代码层零启动，设计要点在 git 历史。
  解封需实现：① 多模态模型注册字段（`ai.register_model` 存 modalities/endpoint/
  audio_config）；② 非聊天端点推理绕过；③ 磁盘型响应解析协议。
- **现有基础**：`__payload_prompt__` 协议与 `audio`/`image`/`video` 类型
  （见 `docs/syntax/07_behavior_expressions.md` §7.6、`docs/subsystems/02_file_container.md`）。

---

## 八、愿景（VISION）

### VISION-1 二层 IR 路线

- **动机**：为诊断、优化与跨后端铺路的中间表示层。概念验证阶段，前置条件多
  （编译器管线稳定 + 基准就绪）；与 PT-FEAT-7 同源。

### VISION-3 真实 LLM 压力试用扩展（T08 延续）

- **状态**：done（六套件 T10-T15 + 全量回归 + 恶意边界 22 例 + 压力 PR1-4；过程 git 承载）
  ｜**域**：VISION

### VISION-4 类型理论加固（五大地基改造 · P7）

- **动机**：五大地基"完整改造"最终目标的一部分（用户 2026-08-18 定方向，决策 6 列为
  远期，P1-P6 稳定后重估）。
- **当前理解**：ADT（enum 升级为实例化成员）/联合类型可选；模式匹配 `match`（建立在协议+
  泛型上，`docs/LANGUAGE_DESIGN_EVOLUTION.md` §3.7/Phase 4）；轻量约束收集推断扩展（非完整
  HM，HM 仍非目标）；fn[...] 变体规则形式化。调研与总路线见 git 历史
  （`_five_foundation_redesign.md` 已随 P1-P6 竣工删除，git 承载）§四 P7。
- **开工输入（类型层承诺需求清单，按依赖序）**：meta 层接通（代码作值）缺的是类型层
  承诺——代码工件/行为表达式/判定结果作为**有类型的一等值**（机制面 `compile_string` /
  `run_file` 已存在）。清单（what 非 how；类型理论设计 = 本项范畴）：
  1. `compile(code: str) -> CompilationArtifact`——编译工件作类型值（可传参/可存变量/
     可进 save_state；当前 artifact 是内核内部对象，未暴露为语言级类型值）；
  2. `run_file(path, policy) -> RunResult`——执行结果作类型值（字段 `exit_status: int` /
     `stdout: str` / `exception: Optional[ExceptionInfo]`；当前返回 dict——MVP 已落地
     `run_result` 值类型[既有值类型注册模式]，本项收窄为类型层深度参与[内建/参与而非仅
     内核注册]）；
  3. 行为表达式值类型（R-6 归位）——`@~ ... ~` 作有类型的一等值（如 `BehaviorExpr`，
     可传参/可作 LLM 可调用类的提案源；依赖本项类型类方向）；
  4. `fn[...]` 高阶签名支持——meta 函数一等性（`meta.compile`/`run_file`/`judge` 可
     引用/可组合；依赖 VISION-5 函数式地基）；
  5. 判定结果类型——`judge(result, expectation) -> Verdict`（`pass/fail + 漂移度量`，
     供调用方消费）。
  ref 类型层项 A2 泛型约束 / A5 解构模式匹配 / A6 Enum-tagged union / B2 惰性短路结构经
  round3 阶段 E 裁定挂起 → 本项整合推进（同域）。
### VISION-5 函数式地基补齐（五大地基改造 · P8）

- **动机**：五大地基"完整改造"最终目标的一部分（用户 2026-08-18 定方向，决策 6 列为
  远期，P1-P6 稳定后重估）。
- **当前理解**：协议化高阶组合子（map/filter/reduce/fold 经协议/impl）；部分应用/柯里化
  （可选）；不可变/纯函数标注（可选，评估价值）。依赖 P2/P4 协议化地基（组合子经协议）。
  调研与总路线见 git 历史（`_five_foundation_redesign.md` 已随 P1-P6 竣工删除，git 承载）§四 P8。

### VISION-6 内核工程化（缓存预编译 / 内核自举 / 真 JIT / 隔离改造 / 反射能力）

- **状态变更（2026-09-08 用户定向）**：本项由"远期 pending"升级为**自主执行主线**——
  用户明确把"内核完整系统工程化 + 真 JIT"纳入无人值守自主推进范畴（meta 层 MVP[自举
  台阶 ④]已落地并入 `unsafe-vibe-dev`）。**真 JIT / 数据平面性能线 = 优先推进面**（用户
  点名）。当前 VM 架构（CPS 调度循环 + AST 直走[无字节码层] + 协议分派）与 9 项设计
  不变量（`docs/architecture/04_vm_interpreter.md` §11）为硬约束；JIT/性能上修须在不
  绕过统一执行入口/控制流数据化/协作挂起的前提下推进。路线图（分阶段）随自主执行推进
  落账于 WORKLOG（Phase 0 = 现状实证调查 + 性能基线 → 分阶段实施）。
- **动机**：引擎工程化与执行能力扩展的远期方向（源自原生宿主绑定 F5 评估）。
- **成因**：F5 评估（2026-08-18）全部列为远期 pending 规划——档 A 缓存预编译（"引擎单次
  执行"模型下缓存失效/序列化保真/沙箱边界风险 > 收益）、内核自举（bind 为运行时用户侧机制，
  与内核构造期契约表达不匹配）、档 B 真 JIT / 隔离改造 / 反射能力（无当前可验证收益/消费方）。
  评估依据与决策见 `tasks_docs/WORKLOG.md` F5 决策记录。
- **F5 档案项（2026-08-18 评估）归位现状**：档 A 缓存预编译 → P5 ✅（持久 artifact
  缓存落地）；真 JIT → P4 ✅（数据平面 ~7×）；内核自举 → P6 ✅（bind 表达内核契约，
  原"时序矛盾"裁定经实证精化——纯声明契约面无矛盾）；档 B 隔离改造/反射 → P7（当前
  P0，高风险→隔离分支）；D-3.3 VM 字符串快速路径 → 长期登记（紧迫性下调，可交错；与
  演化平面设计合流规划）。meta 层（代码作值）与本项各档案项正交（复用既有原语，无依赖）。
- **进度**：P1-P6 ✅ 完成 + 里程碑收束并入 `unsafe-vibe-dev`（git 承载）；**P7 档 B 隔离
  改造 + 反射 = 当前 P0**（高风险→独立隔离分支）。主线状态单点真理 = `tasks_docs/NEXT_STEPS.md`。

### VISION-7 真实使用整改与灰盒愿景整合（阶段 E）

- **状态**：done（阶段 E + round3 全收束：批次建议各线终态——C1 embedding = PT-FEAT-16 done；
  其余线完成/挂起/裁定不做（挂起项归 VISION-4 整合推进 / 长期登记区）；过程 git 承载）
  ｜**域**：VISION

- **动机**：用户裁定下一阶段主攻目标——本机真实 LLM 试用与端点迁移实证暴露的易用性/缺陷
  项（配置体系单源收敛、语言层环境变量通道、trial harness 可用性、provider 配置面、文档
  示例验证闭环）+ 外部灰盒自动机需求单（`ref/IBCI_REQUIREMENTS.md`，本地未入库资产）整合。
  愿景基调："灰盒自然语言自动机全部在 ibci 内完成、ibci 不寄生 Python"。
- **成因**：阶段 C 真实试用 + 端点迁移实证暴露（配置碎片化 / 脚本密钥通道缺失 / harness
  路径解析脆弱等）；外部使用反馈（e01-e17 / trial2 e18-e23）沉淀为需求单。
- **当前理解**：批次建议（git 承载历史）：批 0 = 阶段 C 残留 LLM 项清场 + 配置单源收敛 +
  harness 可用性；批 1 = ref P0 语言大项（C1 embedding / C2 结构化输出 / C3 模块解析 /
  C4 ibci 内测试 / B1 源码行号 / A3 容器尾逗号 / A1 用户协议 / B3 一等环境）；批 2/3 =
  P1/P2。**裁定（用户）**：C1 embedding 必须、解封独立立项（PT-FEAT-16，media 封存
  边界切出）；PT-DECIDE-2 解封（重估收窄后缺口）；批 0 先行与 ref 来源项目协同按工程
  经验自主推进，进入全自动自主运行。**设计纪律（用户明确）**：embedding 须系统级架构
  设计先行（语言形态/职责/数据结构/系统角色/全元素交互），与 LLM 同等严肃对待。
  语言大项触及语义错误集/公理层时按工作模式定论全量评估破坏面。

### VISION-8 Round4 基础智能基底（记忆托管·自修改·可观测灰盒）

- **动机**：试用方 2026-09-09 战略重定——最终目标不是普通语言自动机，而是可观测灰盒的
  基础智能（能 100% 取代甚至超越现有 LLM 的构建思路与功能）：自反馈、按实际环境实时修改
  自身行为模式甚至修改自身工作代码、无严重上下文限制（把借用的 LLM 上下文当高速内存，
  把真正可高效使用的知识/记忆当等效记忆窗口）。系统（而非 LLM 本身）是智能体。
- **成因**：round1-3 大量落地后，试用方从"语言分析自动机"升级为"记忆托管·自修改·
  可观测的基础智能基底"。现有地基（确定性骨架 + LLM 提案 + 治理 + 观测）已成立并被
  证明可靠；缺的是"记忆层级 + 高效召回 + 连续自修改 + 持续可观测"这一层。
- **需求权威源**：`/home/dsh/proj/ibci-trial/docs/ibci_round4_vision_requirements.md`
  （试用方工作区文档，本仓库不复制正文；以下为需求分层指针）。
- **优先级方案（按依赖与杠杆排序）**：
  - **P0-MEM** 记忆基底：MEM-1..4（层级记忆模型/生命周期/容量扩展/完整性+内容寻址）
    + MEM-5（完整环境快照）
  - **P0-REC** 召回策略（★杠杆最高）：REC-1..6（指令条件化召回/层级召回/经验证召回/
    成本模型/工作集管理/query+doc 不对称+MRL 维度轴）
  - **P1-SELF** 自修改基底：SELF-1..5（连续经验证自适应原语/宪法不变量/行为模式层/
    自反馈通道/回滚）
  - **P1-OBS** 持续可观测：OBS-1..4（持续活体快照/召回审计/自修改审计/成本遥测）
  - **P1-COST** 成本感知调度：COST-1..2（确定性优先路由/投机验证）
  - **P2-TYPE** 类型/函数式基底：TYPE-1..2（行为作值/谓词约束泛型）
- **核心洞察（需求单 §2）**：记忆/学习/自修改是同一个子系统——现有 knowledge 注册表 +
  M6 学习原语 + M7 自修改台阶应统一收敛到 IBCI 原生一等"记忆基底"子系统。
- **技术锚点（需求单 §2b）**：Qwen3-Embedding instruction 域（query 侧条件化 + document
  侧裸嵌入可缓存 + MRL 维度 32-1024 可自定义）——day-0 基本形态已可用，IBCI 原生承载 =
  内核保证不对称 + 可审计。
- **建造顺序（依赖图）**：MEM-1..4 → REC-1..6（★效率前沿）+ MEM-5 → OBS-1..3 伴随 →
  SELF-1..4 + COST-1 → SELF-5 + COST-2 + OBS-4 + TYPE-1..2。
- **与主线关系**：P7（进程级隔离 + 反射）完成后，本项为最高优先级主线。P7 的反射能力
  消费方重估中，本需求单本身即新消费方（MEM/REC/SELF/OBS 全部需要运行时内省）。
- **设计纪律（沿用）**：系统级架构设计先行（design-philosophy 全面审视 + 既有
  knowledge/vector/LLM 先例作机制同构基准），与 LLM/embedding 同等严肃对待。
- **状态**：active（P7 完成后进入实施）｜**域**：VISION｜**优先级**：P0（P7 后）

---

## 九、设计决策保留（防止未来误解）

### 9.1 仍有效的设计决策

| 决策 | 内容 |
|------|------|
| 运行时值 `type_ref` 保持基础 spec | 可变值（list/dict）不固有泛型身份（同一对象可赋给 list[int]/list[str]，语义不自洽）；符号/序列化侧已精确 |
| callable 签名属值层属性 | fn_callable/behavior 的签名在运行时值创建时经 node_to_type 捕获、自持于值（JSON 安全字符串，序列化保真）；不落 CALLABLE_INSTANCE 类型 spec |
| 通信 `Signal` 抽象移除 | 零消费者空壳 + 与 VM 控制流 Signal 撞名 → 彻底删除（KNOWN_LIMITS §二十二） |
| 瞬态序列化协议 | thread/chan/slot/subscriber 统一 `__transient_state__` 存根；反序列化不复活活体 |
| 类型符号 `class_ref` | IbClass 序列化为类名引用、反序列化重绑定 registry 真实类 |
| 泛型成员特化协议化 | `resolve_member` per-type 级联收敛为 `GenericTypeDeclaration` 声明回调 |
| 行为体 fn `-> auto` = str 强制 | LLM 输出默认字符串；要其它类型必须显式 `-> T` |
| 可调用实例不写 value_meta | meta 冗余拷贝专用字段且含非 JSON 值；专用字段是单一事实来源 |
| `expected_type` 落盘为类型名字符串 | 运行期由调用点经 node_to_type 解析；字段本身仅元数据 |

### 9.2 设计排除（语言级限制，已写入 `docs/KNOWN_LIMITS.md`）

| 排除 | 原因 |
|------|------|
| walrus `:=` / lambda 体赋值 | 设计排除（KNOWN_LIMITS §十七） |
| if-block 内重声明同名变量 | 设计排除（KNOWN_LIMITS §十七） |
| loader 与 check.py 签名校验收敛 | 设计隔离：SDK 离线校验不初始化运行时，强制收敛引入 SDK↔runtime 错误耦合，不收敛 |

---

## 十、推迟工作记录：循环打破局部 import tradeoff

> 原则：理想上应永远避免循环依赖。允许少量"设计合理、能显著减少工作量"的局部 import
> 作为谨慎 tradeoff。以下为保留的循环打破局部 import，待架构重构（依赖方向下沉/
> 接口上移）时逐项复核。

| 记录 | 位置 | 引用 | 保留理由（tradeoff） | 未来复核方向 |
|---|---|---|---|---|
| L1 | `core/runtime/objects/kernel/base.py` | `from .functions import IbBoundMethod` / `from .ib_class import IbClass` | 运行时构造/分派所需，base↔functions/ib_class 环 | 下沉共享基类到独立叶子 |
| L2 | `core/runtime/objects/kernel/ib_class.py` | `from .functions import IbBoundMethod` | 运行时构造，ib_class↔functions 环 | 同上 |
| L3 | `core/kernel/spec/type_ref.py` | `from .base import TypeKind` | 运行时 kind 比较分派，base↔type_ref 环 | 下沉 TypeKind 到叶子 |
| L4 | `core/kernel/spec/registry/_members.py` | `from ..base import TypeDef` | 运行时构造 TypeDef | 下沉 TypeDef 到叶子 |
| L5 | `core/kernel/spec/registry/_runtime.py` | 相对导入 | 运行时（审计标注循环打破） | 复核定位并下沉 |
| L6 | `core/runtime/interpreter/interpreter.py` | `from vm.vm_executor import` | interpreter↔vm 环 | 延迟属性引用评估 |

---

## 附、书写模式（本文档专用模板，书写必须参照）

> 本节是本文档条目书写的**唯一权威模板**（模板归属 = 文档自身；`GOVERNANCE.md`
> §三 仅做索引）。新增/修改条目一律按下列模板与规则书写。

### 1. 条目编号

- 格式：`PT-<域代号>-<序号>`，序号在域内**递增分配**（不重用已移除序号）。
- 域代号：FEAT / DEBT / AUDIT / DOC / TEST / DECIDE / SEALED。
- VISION 条目用 `VISION-<序号>`，独立编号。
- 编号是纯标识符，不承载优先级或时间信息。

### 2. 域分类（条目必须归属且仅归属一个域）

| 域 | 含义 |
|----|------|
| FEAT | 语言/工具链功能愿景 |
| DEBT | 架构缺陷与清理项 |
| AUDIT | 周期审计与健康检查 |
| DOC | 文档体系缺口 |
| TEST | 测试体系缺口 |
| DECIDE | 待裁定设计问题 |
| SEALED | 显式封存（恢复需解封评估） |
| VISION | 远期方向（无排期） |

### 3. 条目模板

```markdown
### PT-XXX 任务名（短名词短语）

- **状态**：active（活跃）/ shelved（搁置）/ sealed（封存）/ done（完成）
- **域**：<域代号>｜**优先级**：P0 / P1 / P2 / P3
- **动机**：为什么想实现（用户驱动 / 架构统一 / 实际需求）
- **成因**：问题从哪来（历史妥协 / 演进缺口 / 缺陷暴露）
- **搁置原因**：（shelved 时必填）为什么停止
- **当前理解**：现状边界 + 已确认方向（如有）
- **关联**：相关文档/代码/其他任务（指针，不复制内容）
```

VISION 条目模板（仅保留规划价值字段）：

```markdown
### VISION-N 名称

- **动机**：远期方向与价值
- **成因**：（如有）从哪来
- **当前理解**：（如有）现状边界
```

### 4. 字段规则

| 字段 | 规则 |
|------|------|
| 状态 | 值域 `active` / `shelved` / `sealed` / `done`；`shelved` 必须填搁置原因；`sealed` 必须给解封条件 |
| 优先级 | P0 > P1 > P2 > P3（维度：架构健康性 > 易用性 > 长远收益）；shelved/sealed 可标注"恢复后"优先级 |
| 动机/成因 | 各 1 句，说清"为什么想要"与"从哪来"，不写历史叙述（git 承载） |
| 关联 | 只放指针（文档路径/代码路径/任务编号），不复制正文（单点真理） |

### 5. 概览表与生命周期

- 概览表统计（各域 活跃/搁置/封存 计数）在条目增删/状态变更时**同步更新**。
- 条目完成：标 `done` 或从本文档移除（历史由 git 承载），同时更新概览表。
- 条目不承载已完成内容的历史叙述；需要追溯时用 `git log`。
