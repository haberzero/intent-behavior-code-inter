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
subagent 仅 general agent / 决策纪律 / goal 配置习惯。

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
| 分支基准与真实 LLM 环境裁定（2026-09-02，用户） | 未来开发分支**始终以 `unsafe-vibe-dev` 为准**；本轮环境/文档去机器化工作因不涉及核心代码修改与功能推进而临时置于 `main`，完成后已 fast-forward 并入 `unsafe-vibe-dev`；用户显式授权 push 后已推送 `unsafe-vibe-dev`
   至 origin，本地 main 复位 origin/main（该 2 提交由 `unsafe-vibe-dev` 承载）。**远程 CI 暂不
   启动**（保持 `workflow_dispatch`，用户裁定；本地分层验证经 `scripts/ci_local.sh`）。**本机暂不
   跑真实 LLM**（无 api_config.json）：L3 真实 LLM 层与阶段 C 真实 LLM 残留项（恶意边界未测 9 项
   等，见 trials/INDEX.md）在本机搁置，待 LLM 环境就位后恢复。**（后段已被 2026-09-05 裁定取代：
   真实 LLM 环境已就位，见下行）** |
| LLM 试用端点迁移 + 阶段 E 目标整合（2026-09-05，用户） | ① **端点迁移**：本机 LLM 试用端点切至 vLLM `localhost:8001/v1`（强制 Bearer 鉴权；**只允许 `Qwen3.6-35B-A3B`，禁止 `Qwen3.8-27B-NVFP4`**），接下来及未来所有试用均用此端点。落地：43 个 gitignored `api_config.json` 批量迁移；tracked 用例经 `IBCI_TRIAL_LLM_KEY` 环境变量 + 宿主绑定 `os.getenv` 取密钥（tracked 文件不落密钥）；`trials/_toolkit/LLM_SERVICE.md` 单一权威源重写（关键实证：顶层 `enable_thinking` 被 vLLM 静默忽略，思考抑制须走 `chat_template_kwargs` 通道，内置默认 provider 双形态发送已兼容）；命名路由双用例真实 LLM 亚秒 PASS + 全量 pytest 零回归。② **阶段 E 定向**：本 session 实证暴露项（配置体系碎片化 61 份副本/语言层无环境变量通道 + idbg.env 命名冲突/harness 路径解析脆弱/provider max_tokens 硬编码/文档示例无验证闭环——详见临时文档 `tasks_docs/_next_phase_targets.md`）+ `ref/IBCI_REQUIREMENTS.md` 灰盒愿景需求单（"全部 ibci 内、不寄生 Python"；P0 = C1 embedding/C2 结构化输出/C3 模块解析/C4 ibci 内测试/B1 源码行号/A3 容器尾逗号）整合为下一阶段主攻目标；正式总条目 = `PENDING_TASKS.md` VISION-7。待用户裁定：C1 与 PT-SEALED-1 media 封存边界、PT-DECIDE-2 解封重估、ref 来源项目协同方式。 |

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
---

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
