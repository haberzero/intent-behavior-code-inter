# PENDING_TASKS — 待办 / 长期规划

> 当前最紧要见 `tasks_docs/NEXT_STEPS.md`；本文档只保留**仍有价值**的待办、长期规划与设计决策。
> 已完成/无价值条目已删除（完整历史在 git）。
> 任务代号体系（2026-08-05 重整，按**性质**分域，一概念一前缀）：
> **PT-INTRO-1**（内省体系，已完成）｜**PT-FEAT-\*** 语言特性｜**PT-DEBT-\*** 缺陷/技术债
> ｜**PT-AUDIT-\*** 长期周期清扫（审查/审计/文档与注释治理，持续周期工作）
> ｜**PT-DOC-\*** 文档同步｜**PT-TEST-\*** 测试体系｜**PT-DECIDE-\*** 待用户拍板
> ｜**PT-SEALED-\*** 封存

---

## 〇、当前主线与优先级总表（单一权威源，2026-08-08 用户认可）

> **三维度判断：易用性 / 架构健康性 / 长远收益**。当前主线与长期优先级统一在此，
> `NEXT_STEPS.md` 只列当前最紧要并指向本节。

| 优先级 | 任务 | 维度 | 说明 |
|--------|------|------|------|
| **当前阶段（已完成，2026-08-12）** | **真实 LLM 全面试用 + 语法/语言功能评估**（`_REAL_LLM_TRIAL_REPORT_20260812.md`） | 验证/发布 | **已完成**：D1 全语法遍历 + D2 压力试用 + D3 批判检测（C1-C4）+ A1-A5 重验全部基于修复后代码真实 LLM 跑通；暴露 4 项 P1 KERNEL_ISSUE（PT-DEBT-25~28）+ 7 DOC_ISSUE + 5 BOUNDARY。**PT-DEBT-25/26/27/28 已修复（2026-08-12）**；REVERIFY 回归通过（`_LLM_TRIAL_20260812/REVERIFY.md`）。报告 §四/§五/§七 已基于修复后代码刷新 |
| **✅ 已完成（2026-08-12，合并执行）** | **unsafe-vibe-dev 合并取代 main**（`_MAIN_MERGE_PLAN.md`） | 发布/稳定性 | **阶段 3 已执行（用户显式授权）**：`git merge --no-ff unsafe-vibe-dev → main`（merge commit `eb4a7d1`，main 树 == unsafe-vibe-dev 树，全量 2308/1 验证通过）+ push main；原 unsafe-vibe-dev 本地+远端删除，从新 main 分支出新 unsafe-vibe-dev（== origin/unsafe-vibe-dev == eb4a7d1）。main 现为稳定基线；日常开发基于新 unsafe-vibe-dev |
| **✅ 已完成（2026-08-12，unsafe-vibe-dev 35bb2de，全量 2339 passed / 1 skipped）** | **用户类泛型参数（PT-FEAT-3 升主线）** | 易用性+架构 | **用户裁定（2026-08-12）升主线 + 本轮完整落地**。设计冻结 `PT_FEAT3_DESIGN.md`（6 项开放问题决断：无约束裸参数/使用面全/裸用禁止/特化名+registry 键/父泛型继承/Enum 排除）。**全链路**：AST `IbClassDef.type_params`+`parent_args` + parser（`class Box[T]`/`(Box[T])`）+ `TypeKind.TYPE_PARAM`/`SymbolKind.TYPE_PARAM`/`TypeDef.type_params` + 语义类型参数占位解析 + `resolve_specialization` 用户类分支（特化 spec 构造 + members 替换 + 父特化递归注册）+ 序列化（type_params/parent_args 落 artifact）+ 运行时（`IbClass.__getitem__` 类型特化 + 特化类 hydration）。**已支持**：多特化并存/字段·方法参数·返回类型特化（含嵌套 `Box[list[int]]`）/嵌套泛型 `list[Box[int]]`/多参数 `Pair[K,V]`/泛型继承 `class Sub[T](Box[T])`。**守卫**：裸用（注解+实例化）/实参数不匹配/字段-T 冲突/Enum 泛型/类型参数遮蔽内置/非泛型子类继承特化 fail-fast。**方法参数类型检查生效**（`Box[int].set("str")` 报 SEM_TYPE_MISMATCH）。**测试**：21 e2e + 2 序列化 round-trip（全量 2311→2339）。**独立复核两轮 PASS**（P2-1 父特化恒注册 / P2-2 嵌套实参映射 全整改）。**文档**：06_oop §6.4 + KNOWN_LIMITS §十四 #1 + arch/02 §2.6 + 15_diagnostics。**边界**（KNOWN_LIMITS §十四#1 ①-⑧）：bound 约束/`class Sub(Box[int])`/父引用嵌套实参/Enum 泛型 为后续增量。当前无阻塞 |
| **🟢 下一阶段主要目标（2026-08-12 用户提出，设计起点已落档 `TRIAL_SYSTEM_DESIGN.md`）** | **试用体系规范化** | 工程/验证 | **试用机制体系化 + 日志体系化 + 历史记录整理定型**。**✅ Phase 1 机制规范化已完成（2026-08-13）**：单一 harness `trials/_toolkit/run_one.py`（位置无关，`--root` 定位试用目录 + 仓库根上溯；4 套 harness 复制删净改软链）+ `CLASSIFICATION.md`（统一分类 PASS/GUARD/KERNEL_ISSUE/BOUNDARY/DOC_ISSUE/LLM_BEHAVIOR/LIMIT/HARNESS + 级别 P0-P3 + 编号 `KERNEL_ISSUE-<域>-<n>` + **登记前分诊闸门**：命中已知限制 ≠ 免罪，进待修候选池）+ DESIGN/REGISTER 模板。**✅ Phase 2 历史定型基本完成**：4 套 git mv 迁移（T01_llm_full/T02_enum_import/T03_user_class_generics/T04_generics_fix_regression）+ REGISTER 头部规范标注 + 编号映射表（T01/T03/T04，见各 REGISTER + `trials/INDEX.md` 全局映射）+ INDEX.md 跨套索引。**剩余**：T04 用例修正适配（G3 语义变更：R1-05/R5-01 多参构造 + R5-04 哨兵修正已完成）；**暴露 KERNEL_ISSUE-GEN-5**（嵌套内置泛型实参特化注册缺失，待独立窗口）；Phase 3（全量 pytest 零回归 + docs 治理评估）。**旧命名 `_LLM_TRIAL_*`/`_GENERICS_TRIAL_*` 全部迁入 `trials/`，旧路径不再使用**。设计 `TRIAL_SYSTEM_DESIGN.md` |
| **P0（发布）** | **CI/CD 退役 + 重新设计** | 发布/工程 | **GitHub 侧 CI 自动触发已停用（2026-08-11，`.github/workflows/ci.yml` → `workflow_dispatch`）**。现 CI 与本机 pytest 区别不大、必要性不足；待单独设计"可靠化/实用化"（真实 LLM e2e / 跨平台 / 发布产物）后重新启用，另行规划 |
| **P0（真实 LLM e2e 前置）** | **PT-FEAT-13 api_config 配置机制完备化（C1-C3）**（`_API_CONFIG_DESIGN.md`） | 验证/工程 | 现 api_config.json 非原生加载（脚本约定）、无校验、mock 字符串嗅探。为真实 LLM e2e（本地非思考模型）做**一等配置机制**：**C1 原生加载**（ai 模块/引擎自动，替代每脚本 file/json.parse）+ **C2 set_config 结构化** + **C3 校验诊断**（fail-fast/诊断码，不静默回退 mock）。C4-C7 随 e2e 完善、C8 远期。**C1-C7 已落地（2026-08-11，全量 2161/1）**。**注（2026-08-12）**：F9 用户裁定改显式配置（`ai.autoset`）后，C1 的"引擎自动加载"落地形态同步调整（"原生一等入口"仍成立，只是显式），见 F9 行与 `_code_ai_autoset.md` |
| **当前主线（已完成）** | **PT-DEBT-12/13/14/15 异步地基遗留妥协根治**（`_ASYNC_UNIFY.md`） | 架构健康性 | **统一执行模型闭环——全部收尾（2026-08-09）**。F1→B1→F2/F3→M4 已完成（2026-08-08），M3 已收敛；**M1（.call 双写收敛）/ M2（驱动去重）已完成（2026-08-09，独立分支 exp/async-m1m2，全量 2137/1）**。消"任务内同步重入调度器"遗留旁路 |
| **P1（异步统一完整）** | **异步统一遗留 A1-A6**（`_HEALTH_AUDIT_PLAN.md`） | 架构健康性 | 地基闭环后 6 处**次要路径**仍任务内同步重入/嵌套调度器：**A1-A4 已完成（2026-08-10，全量 2138/1）**；**A5 类构造已根治（2026-08-11，`_ClassInstantiateDrive` CPSDrivable，全量 2137/1）**；**A6 协议方法 `.call` 评估维持现状（2026-08-11，niche + 条件触发，CPS 化成本高收益低，登记已知项）** |
| **P1** | **PT-DEBT-17 `ai.run_batch` 同步阻塞**（统一执行模型冲突） | 架构健康性 | **已彻底修复（2026-08-11，unsafe-vibe-dev ebbb7f8，全量 2135/1）**：`run_batch` 返回 `CPSDrivable` Waitable（CPS 预求值 `_prepare_behavior_call_cps` 消除 vm.run 重入 + 多 LLM Future 聚合 `LLMBatchFuture` 由调度器非阻塞等待，与 `stream_call` Waitable 范式一致）。vtable return_type=list 契约不变（auto-yield 后仍收 boxed IbList）。顺带清理死代码 `resolve()`/`LLMFuture.get()`。`ihost.collect`/`run_isolated` 为透明异步 auto-yield（非问题，已澄清） |
| **P0** | 阶段 5 增量（`next()` 内建 + `yield from`） | 易用性 | **已完成（2026-08-09，全量 2128/1）**：`next()`（c61a6e0）+ `yield from` 生成器委托。设计 `_code_yield_from.md` |
| **P0** | PT-FEAT-5 错误用户友好化 | 易用性 | **已完成三项（2026-08-09）**：诊断码目录 + 符号表/类型绑定导出 + 编译基准。**CI/CD 已停用 GitHub 侧自动触发（2026-08-11 用户裁定）**——现 CI 与本机 pytest 区别不大、必要性不足；待单独设计"可靠化/实用化"后重新启用 |
| **P1** | PT-FEAT-10/11/12 UID/序列化统一 | 架构健康性 | **PT-FEAT-10 已完成（2026-08-09）**；PT-FEAT-11（序列化器自动化）、PT-FEAT-12（AST uid 字段）评估为维持现状（见下） |
| **P1** | PT-DEBT-4 `file` 模块重命名 | 架构健康性 | 影子化 Python 内建，长期隐患；破坏性变更独立窗口 |
| **P1** | **技术手册健康待修**（P1/P2） | 文档健康 | 三修**已完成（2026-08-10，PT-DOC-3）**：`01_principles.md:258` 过时 `inherit_intents`、`04_vm_interpreter.md:29` `.call` 表述、`README` 目录树补 `15_diagnostics.md`。剩余 How-to 层缺口为 P2 规划 |
| **P2** | PT-AUDIT-1/2 + R4/R5 | 架构健康性 | 长期周期清扫，阶段边界启动。**R4 覆盖率核对已执行 + R5 聚焦治理已执行 + PT-AUDIT-1 smell 全量事实回顾已完成（2026-08-09）**；**`runtime_serializer._collect_instance` 巨型 elif 链已拆具名 collector（2026-08-11，unsafe-vibe-dev 4592636，纯可读性/整洁性重构）**；PT-AUDIT-2（分支嵌套）剩余：`_get_instance`（已按 `_type` 干净分派，可选对称）、`core_scanner` 深度10 状态机、`binding_analysis` 深度9 AST 访问者（惯用模式，维持现状）待独立窗口 |
| **P1（下一 session 主线）** | PT-FEAT-2 Enum 非 str 成员 + 迭代能力 | 易用性+长远 | **✅ 已完成（2026-08-12，unsafe-vibe-dev，全量 2308/1）**：① 非 str 枚举 LLM 集成修复（编译期常量成员写 `MemberSpec.metadata["value"]`，EnumAxiom 成员名→值映射，含负数 `-1`；str 零回归/值≠名正确，真实 LLM 实证 qwen 成员名→值 200→switch 命中）；② 迭代 `for v in Color:` / 数量 `len(Color)`（has_iter_cap + get_method_specs + 运行时 Enum 基类绑定）；③ 自定义方法 = **值模型边界**（`Color.RED` 是底层值非实例，方法不可达）——实例化枚举为独立设计候选（`_code_enum_completion.md`）；④ KNOWN_LIMITS §二 更新。**遗留**：**枚举实例化设计窗口**（`_enum_instancing_assessment.md`——评估结论维持现状：LLM 集成改造为核心硬伤（kernel 层无法构造实例 + 通用解析路径需类型感知包裹），爆炸半径不确定，独立设计冻结候选） |
| **P3** | PT-FEAT-8 `.ibc_meta` 快照 / PT-FEAT-4/7 / PT-FEAT-6 | 长远 VISION | 概念验证阶段 / 前置条件多 |
| **暂缓** | PT-DEBT-5 文件命名清理 | 架构健康性 | 破坏面大纯机械，独立窗口 |
| **当前阶段（LLM e2e 已完成，不合格操作待重修）** | ~~**PT-DEBT-18 generator IbClass 注册 + IbGenerator.receive 特判回退**~~（`_HANDOFF_ISSUES_LLM_E2E.md` U1）**已修复 2026-08-11** | 架构健康性 | **修复方式**：新建 GeneratorAxiom（`core/kernel/axioms/primitives/generator.py`，声明 to_list/generic_next 方法规格）+ `GENERATOR_SPEC` 注册（specs.py + _runtime.py）+ `@register_ib_type("generator")` 于 IbGenerator（kernel/__init__ 导入触发）+ **删 IbGenerator.receive 特判** + leaf.py:373/392 改 `get_class("generator")` 优先。契约测试 `test_generator_ibclass.py`（GEN-1~4：generator 类注册 + vtable + 值身份 `type(gen)` = "generator" + 用户显式 .to_list()/.generic_next() 协议分发）。全量 2176/1 零回归（+4 契约 +3 meta 派生） |
| **当前阶段** | ~~**PT-DEBT-19 内建遮蔽 + LLM 表达式 UID 解析缺陷**~~（`_HANDOFF_ISSUES_LLM_E2E.md` U2）**已修复 2026-08-11** | 编译器正确性 | **真实根因（比交接推断更精确）**：编译器对模块级带类型声明 `int X = ...` 统一绑定既有 intrinsic 符号 UID（字面量/LLM 同 `intrinsic:X`），遮蔽语义由运行时 define 承担（`_vm_assign_to_target` define_only 路径）；但 dispatch-before-use 路径 `_assign_future_to_name_target`（`_shared.py`）在符号已存在时原地覆写 `.value` 而非 define → intrinsic 常量符号被写入 LLMFuture，使用点回写触发 `Cannot reassign constant`。**修复**：`_assign_future_to_name_target` 增加 `define_only` 参数（与 `_vm_assign_to_target` 同构），IbTypeAnnotatedExpr 递归置 True，定义路径恒走 `define_raw` 创建全新用户符号（遮蔽语义正确）。函数局部声明本就生成新局部符号 UID，不受影响。**验证**：`int sum/@~...~/int len` 遮蔽 LLM 初始化全通（+2 回归测试）；示例 01_hello_world.ibci 改回 `int sum`（真实跑通 mock 10）。全量 2178/1 零回归 |
| **当前阶段** | ~~**PT-DEBT-20 InterpreterError 双实现统一**~~（`_HANDOFF_ISSUES_LLM_E2E.md` U3）**已修复 2026-08-11** | 架构健康性 | **修复**：`core.extension.exceptions` 删除 `InterpreterError` 定义（历史遗留重复，无 error_code 能力）；公开名 `core.extension.InterpreterError` 改指 `core.kernel.issue.InterpreterError`（IBCBaseException，error_code/location/severity 能力完备）——公开契约保持；清理 ibcext.py 死 import（三个异常类均未使用）；__init__.py 直接导入。+3 契约测试（公开名同一类 / error_code 能力 / 无重复定义）。全量 2181/1 零回归。**注**：extension.exceptions 的 PluginError/CompilerError 仍为 SDK 独立类型（构造契约与 kernel 版不同，未纳入 U3 范围，无重复名冲突） |
| **当前阶段** | ~~**PT-DEBT-21 AIPlugin.setup 自动加载路径规范化绕过**~~（`_HANDOFF_ISSUES_LLM_E2E.md` U4+U6+U7）**已修复 2026-08-11** | 安全 | **U4**：config_path 经 `PathValidator.canonicalize_for_security` 规范化（插件层统一走符号链接解析机制）。**U7**：三重 if 收敛为 fail-fast 契约——execution_context/project_root 缺失=注入异常（InterpreterError），api_config.json 不存在=合法态静默跳过。**U6**：测试显式传 project_root=None 表意 + ExecutionContextImpl 类契约文档（生产必传，消费方对 None fail-fast）。+4 契约测试（含符号链接 project_root 加载验证）。全量 2185/1 零回归 |
| **当前阶段** | ~~**PT-DEBT-22 意图一次性/排他（@/@!）dispatch-before-use 路径丢失**~~（commit 7339220）**已修复 2026-08-11** | 语义正确性 | **真实缺陷（原被误判为'模型服从性'）**：`fork_intent_snapshot()` 把 @ smear / @! override 移入快照 `_inherited_*` 槽位，`_prepare_behavior_call`（sync+CPS）captured 分支只取 active/global → 赋值+并行预调度下 @/@! 从未进 prompt。**修复**：`IbIntentContext.resolve_to_prompts(+cps)` 单一权威消解（override>smear+active>global）+ `get_resolved_prompt_intents` 委托 + captured 分支改快照方法。真实模型实证 qwen3.6 遵循意图（'你好。'）。+6 回归测试。全量 2194/1 |
| **当前阶段** | ~~**PT-DEBT-23 配置机制 fail-fast 硬化**~~（commit 0eb8939，F1-F7）**已修复 2026-08-11** | 工程正确性 | general agent 独立彻查上一批次发现（自审计 D 段误标'正确'）：**F1** `{env:VAR}` 格式非法静默透传→残留检测 fail-fast；**F2** IBC_TEST_MODE 隐式覆盖显式 set_config→删 env 分支（mock 显式化）；**F3** load_config 锚 entry_dir vs setup 锚 project_root 分叉→统一锚 project_root；**F4** reasoning:true 不对称→对称落 probed/is_reasoning；**F5** extract_strategy/supports_system 死字段→删除；**F6** 空/空白凭据过校验→_require_nonempty+_init_client fail-fast；**F7** 默认值字面量三重复→引用 config_loader 常量。+5 契约测试。全量 2201/1 |
| **✅ 已清理（2026-08-12，unsafe-vibe-dev）** | **PT-DEBT-24 call_intent 预留机制死代码清理**（T2 审计发现） | 架构健康性 | `IbBehaviorExpr`/LLM 函数 AST 均无 intent 字段 → 所有调用方 call_intent 恒 None → 死代码全链清理：`_prepare_behavior_call(_cps)` auto_intent 关闭短路分支 + BehaviorCallSpec.pre_resolved + execute_behavior_expression_cps 参数 + execute/invoke_llm_function_cps 穿透参数 + IbBehavior.call_intent 值字段（含 meta 序列化/工厂/协议）。保留 `get_resolved_prompt_intents` 的 call_intent 协议预留参数（docstring 注明未消费）。全量 2308/1 零回归 |
| **✅ 已完成（2026-08-12，unsafe-vibe-dev a49555b，全量 2311 passed / 1 skipped）** | **F9 配置副作用显式化**（T4 审计发现） | 设计评估 | 真实配置 + 未装 openai 时 `import ai`/引擎启动即抛 RuntimeError（setup 自动加载 api_config.json → apply_config → set_config → _init_client）。**用户裁定（2026-08-12）：改为显式配置，命名拍板 `ai.load_project_config`，本轮实施**。**落地**：`setup()` 去自动加载段（仅保留 capabilities.expose）；新增 `load_project_config()`（ec/project_root 缺失 fail-fast + 路径规范化 + 缺失 no-op 合法态 + 存在即加载校验应用 + 幂等）；`_spec.py` vtable 注册；测试 TestEngineExplicitConfigLoad（无调用不加载/显式调用加载）+ TestLoadProjectConfigContract（fail-fast/no-op/符号链接/幂等）+ 语言级可达；examples 01/02/03 判断前加 `ai.load_project_config()`；文档同步（README/guide 01+02/syntax 11+15/config_loader/execution_context/catalog/codes）。独立复核 PASS（5 项整改全完成）。设计记录 `_code_ai_autoset.md` + 实施记录 `_code_f9_load_project_config.md` |
| **P2** | **PT-AUDIT-3 双路径分裂专项审计**（T1/T4 教训驱动，新增） | 架构健康性 | 意图缺陷（PT-DEBT-22）揭示"双路径语义分裂 + 快照半消费 + 自审计不可全信"三类模式；T4 独立审计已证明 general agent 能发现自审计 D 段误标的真问题。**对近期子系统做独立审计**：异步统一 A1-A6 / run_batch CPS（exp/run-batch-cps）/ yield 生成器 / generator IbClass / llmexcept / M1-M2 调用收敛——专项查：① sync vs CPS 孪生语义一致；② 快照/双路径"复制完整消费部分"；③ 自审计标注"正确"但实际漂移。用 general agent 独立执行 + 主代理交叉核验。**已执行（2026-08-11，general agent 独立审计 + 主代理核验）**：无 P0；3 确凿 P2 漂移已修复（run_batch 观测 / active_intents 漂移 / _drive 装箱一致）+ generator 兜底 fail-fast + KNOWN_LIMITS §二十四 机制描述修正（commit df1a896）。**疑似项处置（2026-08-12）**：① **S4 已根治**（PT-DEBT-24 call_intent 死代码全链清理）；② **S5 部分处置**（共享 axiom hint 查找抽单一实现，vtable 驱动分支保持各自驱动）；③ **S1/S2/S3 复核为已知边界**（S1 dispatch hint 同步 .call 嵌套调度器仅 hint 含 VM 依赖 Waitable 时可观察，niche；S2 跨线程 EC 模块名改写需 worker 同步构造类且 drive 返回非实例，路径非预期；S3 task 线程写单写槽为纯可观测性竞态，GIL 下无崩溃）——均登记待独立设计窗口，见 `_PT_AUDIT3_RECORD.md` §三 |
| **✅ 已修复（2026-08-12，unsafe-vibe-dev，全量 2252 passed / 1 skipped）** | **PT-DEBT-25/26/27/28 已根治** | 架构健康性 | 按 `_FIX_PROPOSAL_CRITICAL_REVIEW_20260812.md` 修正后方案执行。**PT-DEBT-25（global）**：symbol_resolution_pass 加 visit_IbGlobalStmt + prescan 排除 global 名（镜像 nonlocal），运行时零改动；+6 测试。**PT-DEBT-26（整模块 import）**：档3 写入侧 `_symbol_to_member` 统一 Symbol→MemberSpec/MethodMemberSpec（scheduler.py）+ 档2 `_expression_visitors` 零参数 callable 按 kind 绑定（不再退化 any）；+4 测试。**PT-DEBT-27（异常逃逸）**：`_drive_loop_gen` Waitable yield 加 except Exception 重投递 pending_exception（与值投递对称，TaskCancelled 穿透）；+4 测试。**PT-DEBT-28（ai vtable）**：`_spec.py` 补 get_retry/is_auto_intent_injection_enabled 注册；+3 测试。独立复核三修复全部 PASS（含 TaskCancelled/UnhandledSignal/异常沿 CPS 栈上抛验证）。**遗留**：嵌套包 `import subpkg.util` + `subpkg.util.fn()` 的 INT_INTERNAL_ERROR 为修复前既有缺陷（git stash 实证非本批引入）——中间模块符号以 VariableSymbol(kind=MODULE) 形态经 `import subpkg` 注入，成员访问仍触发 type_ref 缺失；待独立窗口（与 PT-DEBT-26 同族形态问题） |
| **✅ 已修复（2026-08-12，unsafe-vibe-dev，全量 2252 passed / 1 skipped）** | **PT-DEBT-O1/I1/O2 + 生成器/文档修正** | 架构健康性 | 按 `_FIX_PROPOSAL_CRITICAL_REVIEW_20260812.md` 批次 C/D 执行（用户授权破坏性变更）。**O1（可调用类实例 obj()）**：`IbObject.receive('__call__')` 对含用户 `__call__` 的类实例返回 `_UserCallDrive`（Waitable+CPSDrivable，与 A5 `_ClassInstantiateDrive` 同构），VM 经 cps_drive 帧内驱动（UserFunctionCall trampoline）——根治嵌套调度器（EXEC-1 深递归 Python 深度恒定恢复 + Waitable 协作挂起）；receive 保持唯一协议分派，VM 侧零新特判；+5 测试（含深递归 depth=400/fn 引用/LLM await/chan await）。**I1（生成器 __iter__）**：`IbUserFunction.call` 对生成器方法返回 IbGenerator（make_generator_driver 同构）+ `resolve_iterable` 对 __iter__ 返回的 IbGenerator 做 to_list——修复 `for x in obj` 的 GeneratorYield 崩溃，附带修复 `yield from <生成器 __iter__ 实例>`；+4 测试。**O2（字段默认值）**：static_val 改经 `try_deep_clone` 递归深克隆（补全"每实例独立默认值"既有意图，非语义反转；不可克隆值回退共享引用）——消除内层 list/用户对象跨实例共享；+3 测试。**文档**：05_functions §5.8/§5.9（for=to_list 急物化）、KNOWN_LIMITS §二十四（await 阻塞消费可用）、§十四 #2（运算符可重载）、§一（可调用实例已 CPS 化）修正。设计记录 `_code_call_cps_drive.md` |
| **✅ 已修复（2026-08-12，unsafe-vibe-dev，全量 2270 passed / 1 skipped）** | **试用易用性修复**（`_USABILITY_AUDIT_20260812.md`） | 易用性 | 用户观察"`while true` 无法工作"驱动系统审计。**① return@~ 编译期拦截随迁 v2**（v1 曾实现，v2 语义重构 afe9644 时未随迁→设计意图丢失；visit_IbReturn 补全拦截报 SEM_TYPE_MISMATCH，消除"文档说禁止实际通过+运行时类型错"陷阱；+4 测试）。**② switch 内 break 消费为 no-op**（IBCI switch 无 fall-through，break 是 C 冗余写法；vm_handle_IbSwitch 消费 BREAK、CONTINUE 透传外层循环，不再报 RUN_GENERIC_ERROR；+3 测试）。**③ 布尔字面量错误引导**（true/false/none 未定义报"Did you mean True/False/None"，不推翻 Python 对齐设计；+3 测试）。**④ KNOWN_LIMITS §十一 更新**（switch 基本可用 + 使用约束）。**根因**：① 重构丢失；② C 习惯冗余；③ 有意 Python 对齐（3c6d137 true→True）；④ 过度保守 |
| **✅ 已处置（2026-08-12，unsafe-vibe-dev）** | **DOC-ISSUE-001~007 + BOUNDARY-001~005**（`tasks_docs/_LLM_TRIAL_20260812/REGISTER.md`） | 文档/边界 | **全部处置**：DOC-ISSUE-001（02_variables §2.6 补 `-> void`）/002（9 处 `__init__` 补 `-> auto`）/003（14.6 await thread 矛盾修正）/004（stream_call 签名）/005（howto thread_result `.value()`）/006（§十二 警告可见性精确化——编译期诊断经 issue tracker，运行时不打印）/007（`__from_prompt__` 契约 `(bool,实例)`）。BOUNDARY-001（for=to_list 物化，§5.8/§5.9 已核验一致）/002（§二十四 已修）/003（§11.6 隔离不继承 LLM 配置明示）/004（§9.1 `@!` run_batch 粒度说明）/005（§11.3 probe_model 推理判定说明）。详见 commit 6f8506d |
| **✅ 已修复（2026-08-12，unsafe-vibe-dev，全量 2296/1）** | **嵌套包 `import subpkg.util` + 成员访问 INT_INTERNAL_ERROR** | 架构健康性 | 根治（PT-DEBT-26 同族形态遗留，修复前既有）。三层根因：① 调度器嵌套 import 把原始 Symbol 入 members（resolve_member 崩）；② visit_IbImport 绑定全名而 scheduler 只注入根段；③ 中间段 create_primitive 产出 PRIMITIVE kind 重导入守卫恒真 + 运行时缺包命名空间。修复：嵌套段统一 MemberSpec + 中间段 create_module 全名注册 + 绑定根段 + `_bind_package_chain` 运行时合成 IbModule 包命名空间（幂等合并）。2层/3层/同包多导入合并全过；+4 e2e（`test_ibc_file_imports.py` TestIbcFileNestedPackageImport）。**遗留**：`import subpkg`（纯包目录无模块）DEP_MODULE_NOT_FOUND（Python 同语义，包须含可导入模块） |
| **✅ 已修复（2026-08-12，unsafe-vibe-dev 32484fe，全量 2350 passed / 1 skipped）** | **KERNEL-ISSUE-G2 泛型类自引用字段特化替换失效（编译期）** | 架构健康性 | **现象**：`class Node[T]: Node[T] next` 特化后 `n1.next = Node[int](2)` 报 `Cannot assign 'Node[int]' to 'Node[T]'`（SEM_TYPE_MISMATCH）。**根因（深度核验实证）**：字段构造 `TypeRef.from_spec(Node[T] spec)` 对 CLASS kind 落**默认 fallback**（`TypeRef(get_base_name())`）→ 扁平化为 `TypeRef('Node[T]')`（head 含方括号、args 空）；`TypeRef.substitute` 对扁平形态无法替换。**修复**：TypeDef 新增 `type_args`+`base_name` 字段，`_specialize_user_class` 填充，`from_spec` CLASS 特化 spec 结构化构造（`TypeRef('Node',(int,))`），serializer/rehydrator 持久化保真。`Node[T] next` 特化后 `Node[int]`，赋值/递归特化均正确。+3 e2e。**P1** |
| **✅ 已修复（2026-08-12，unsafe-vibe-dev 32484fe，全量 2350 passed / 1 skipped）** | **KERNEL-ISSUE-G1 泛型方法体内类型参数表达式运行时失效（运行期）** | 架构健康性 | **现象**：`func make(self, T v) -> Box[T]: return Box[T](v)` 运行期 `Variable UID 'Box:T' is not defined`。**根因**：编译期语义正确（slice T 绑 TYPE_PARAM 符号，UID=`Box:T`），但运行时类型参数不产生变量、UID 未注册 → `vm_handle_IbName` 失败。**修复**：`IbFunctionDef.type_param_uids` 编译期收集（binding_analysis 进入类作用域解析 TYPE_PARAM [name,uid] 对），运行时 `_bind_type_params` 按 receiver 特化实参注册类型参数符号（简单实参→IbClass；嵌套实参→boxed 特化名，对齐 `_specialize` 内置泛型标识机制）。方法体内 `Box[T]` slice T 求值为类型标识，多特化/嵌套实参全正确。+6 e2e。**P1** |
| **✅ 已修复（2026-08-12，unsafe-vibe-dev 3fe98d6，全量 2350 passed / 1 skipped）** | **BOUNDARY-G1 非法特化实参编译期未拦截** | 架构健康性 | `Box[42]`/`Box[None]` 原编译通过、运行期裸 `AttributeError`；`Box[None]` 注解位置还产生幻影 `Box[None]` spec（赋值误报 SEM_TYPE_MISMATCH）。**修复**：注解+表达式位置字面量 slice（`Box[42]`）与哨兵类型实参（`None`/`auto`；`void` 按 base 收窄——仅内置 `thread[void]` 合法）报 `SEM_GENERIC_TYPE_NEEDS_ARGS`。+4 e2e。**P2** |
| **✅ 已修复（2026-08-12，unsafe-vibe-dev 32484fe，全量 2350 passed / 1 skipped）** | **双通道设计缺陷：特化方法参数 descriptors 替换两套实现** | 架构健康性 | `_substitute_members`（真实 mapping dict 驱动）与 `_sync_specialized_members`（**字符串解析特化名反推 mapping**）是同一语义的**两个实现**，违反工作模式定论第 3 条 + design-philosophy §四。**修复**：特化 spec 新增 `type_args` 字段（结构化实参，`_specialize_user_class` 填充），`_sync_specialized_members` 改用 `type_args`+基类 `type_params` 配对——**删除字符串反推**（`_type_param_mapping`/`_split_top_level_args`/`_parse_type_ref_name`），单一权威源。嵌套实参方法参数类型检查仍正确。**P2** |
| **✅ 已修复（2026-08-13，unsafe-vibe-dev b0f4d74，全量 2365 passed / 1 skipped）** | **KERNEL-ISSUE-G3 继承特化 + 父类字段值丢失** | 架构健康性 | **交接诊断纠偏**：并非"特化父类字段未绑定"（`Node[int].default_fields` 含 `data`/`next`，继承链收集正确）。**真实根因**：`_hydrate_user_classes` 自动构造器只收集**类自身 body** 的无默认值字段 → 子类 auto-init 参数被削减并遮蔽父 auto-init → `Linked[int](5)` 把 5 绑到 `tag`、`data` 静默 None。**非泛型同构复现**（`Sub(Base)`+单参→父字段静默 None），且原为文档化 Known Limit（KNOWN_LIMITS §六）——按"文档化限制是修复候选"重新定性为真实缺陷。**修复（chain-aware auto-init）**：自动构造器参数 = 继承链全部有效无默认值字段（父类优先、子类同名覆盖），与 instantiate 字段收集同构（机制同构）；构造器生成拆为独立第二 pass（父类字段须已 hydrate）。非泛型/泛型/多级继承全修；少传参 fail-fast 报缺参（不再静默错误值）。+7 e2e。**P1** |
| **✅ 已修复（2026-08-13，unsafe-vibe-dev b0f4d74，全量 2365 passed / 1 skipped）** | **BOUNDARY-G2 自引用链 while 遍历"类型退化"** | 架构健康性 | **交接诊断纠偏**：并非运行时类型退化（探针实证 `cur` 持续保持 `Node[int]`）。**真实根因**：试用用例设计无效——`Node[int]` 编译期禁止赋 `None`（SEM_TYPE_MISMATCH），`while cur is not None` 哨兵在非 Optional 字段上类型不可行；且 `nodes[2].next` 未赋值，默认 `= any` 产出非 None 的 truthy any 类对象，循环永不终止。**附带根治 Finding C**：`_check_type` 对 USER_DEFINED CLASS 目标无条件跳过运行时复查 → any 类对象静默流入用户类变量（§七 契约失效），现对动态 any 逃生值强制 `RUN_TYPE_MISMATCH`（is_assignable 因"类可调用"会放行，直接判定）。R5-04 现报清晰 `RUN_TYPE_MISMATCH` 而非困惑 AttributeError。+3 e2e。**P2** |
| **🟡 待修复（2026-08-13 试用体系规范化期发现，`tasks_docs/trials/T04_generics_fix_regression/`）** | **KERNEL_ISSUE-GEN-5 用户泛型类下标表达式位置特化未注册** | 架构健康性 | **现象**：`Box[list[int]]`（内置泛型 list 作实参的用户类特化）在**表达式位置**（如 `print(type(Box[list[int]]))` 的 type() 参数）求值时运行时 `_specialize` 报 `Generic class 'Box' has no registered specialization for type 'list[int]'`（R5-04 组合用例 Box 部分首次触发；探针实证最小形态仅需 Box 泛型类 + 表达式位置下标）。**git stash 实证为预存缺陷**（与 2026-08-13 G3/Finding C 修复无关）。**根因方向（探针实证）**：编译期对表达式位置的 `Box[list[int]]` 未注册特化 spec；对照注解位置 `Box[list[int]] bl = ...` 会触发编译期注册、正常运行。**触发用例**：`trials/T04_generics_fix_regression/cases/GEN5-01-nested-specialization.ibci`（持续复现证据，修复后应输出 `box_slice=Box[list[int]]`）。**P2**，独立窗口深挖（可能同源影响其它表达式位置泛型下标） |

---

## 一、运行时内省体系（PT-INTRO-1，已完成）

> `type(x)` 内建 + fn/behavior 签名形态 + `__return_type__()` 返回类型查询 **全部落地（2026-08-06）**。
> 完成形态：
> 1. `type(f)` 对 fn_callable/behavior 返回含签名类型名（`fn_callable[()->int]` /
>    `behavior[(int,str)->bool]`）；其余值返回 `ib_class.name` 规范名。
> 2. `f.__return_type__()` 返回返回类型规范名；签名随序列化 round-trip 保真。
>
> 设计决策（签名属值层属性）见 §十。

---

## 二、PT-DECIDE-1 LLM 解析默认策略语义（已裁定，2026-08-06）

> **裁定**：编译期 `SEM_BEHAVIOR_OUTPUT_NOT_PARSEABLE` + 运行时兜底（DefaultParsingStrategy）。
>
> **问题**："已声明具体类型但无 `__from_prompt__`/parser" 的 LLM 输出被静默 box 成成功
> 字符串 → 错误类型静默流入（实测：`Point p = make()` 中 p 实际为 str）。
>
> **方案评估**：`uncertain`（原提案）有致命缺陷——无 parser 类型在 llmexcept 下重试
> 永远不可能成功，每轮重试重新调用 LLM，白耗 3 次后必然 `LLMRetryExhaustedError`；
> 且需小心排除 `-> any`（运行时 type_hint 为裸 behavior）。编译期错误在零成本处暴露根因，
> 与 fail-fast / 根因优先原则一致。
>
> **落地**：
> 1. 编译期：lambda 行为体 `-> T`、`T x = @~...~`、`obj.field = @~...~` 三处检查
>    T 是否可解析（from_prompt/parser 公理能力 或 类 `__from_prompt__` 含继承）；
>    不可解析报 `SEM_BEHAVIOR_OUTPUT_NOT_PARSEABLE`。`auto`/`any`/行为本体动态类型不设
>    契约，豁免。
> 2. 运行时兜底：`DefaultParsingStrategy` 对"已声明具体类型却无解析能力"返回 uncertain
>    （含明确 retry_hint），不再静默 box；无契约情形（空/auto/any/行为本体）保持 box。
>
> **兼容性**：`auto result = @~...~`、`-> auto/any`、有 parser 的内建类型全部保留原行为；
> 现有测试无"无 parser 具体类型 → str"依赖。设计决策（含 futile-retry 论证）见 WORKLOG。

---

## 三、内核接口协议化（PT-DEBT-1/2/3，已完成）

> 三者同性质（跨对象私有穿透 → 公开访问器/容器）**全部落地（2026-08-06）**，全量 pytest 零回归。

| # | 落地内容 |
|---|---------|
| PT-DEBT-1 | `BoundPlugin(implementation, registry_id)` 容器替代 `_ibci_registry_id` 私有标记注入；`InterOpImpl` 记录/查询 registry_id；`IbNativeObject` 构造时携带（跨引擎隔离校验保留）；加载期跨引擎单例守卫改用 process 级 weak map（保留安全语义，不污染实现对象） |
| PT-DEBT-2 | `snapshot.py` 改走公开访问器（`peek_runtime_coordinator`/`peek_comm_registry`/`get_current_call_info`）；LLMExecutor 补 `pending_futures_count()` 只读计数 |
| PT-DEBT-3 | RuntimeContextImpl 补通信域/协调器公开访问器（`get_comm_registry`/`get_comm_config_store`/`get_comm_event_bus`/`get_runtime_coordinator` 惰性创建 + `peek_*` 只读），统一替换 core（comm/assignment/host/coordinator）与插件（iruntime）全部 `rc._comm_*`/`rc._runtime_coordinator` 直接访问 |

---

## 四、语言特性 / 功能规划（PT-FEAT-*）

| # | 内容 | 说明 |
|---|------|------|
| PT-FEAT-1 | 语言级协程完整形态：async 函数 / `yield` 生成器 | `await` 表达式已落地。**`yield` 惰性生成器已落地（2026-08-08，阶段 5，独立分支 exp/yield-generator → 手动应用 unsafe-vibe-dev，全量 2043/1）**：含 `yield` 函数自动为生成器（D-08 自标记，async 关键字已取消），单可恢复驱动 `_drive_generator_loop` + `GeneratorYield` 标记 + `IbGenerator` 值对象 + `generator[T]` 类型。设计 `YIELD_GENERATOR_DESIGN.md`。**增量 `next()` 内建 + `yield from` 委托已落地（2026-08-09，全量 2083/1）**。剩余：**LLM 函数同步阻塞收敛**（`execute_llm_function_cps` 的 `_call_llm` 阻塞调度线程，`_llm_function.py:202`——behavior 路径已 yield LLMFuture，llm 函数路径未对齐，即 `_HEALTH_AUDIT_PLAN.md` A4）、streaming / host async 改进（STREAM 依赖已封存多模态，deferred） |
| PT-FEAT-2 | Enum 非 str 成员 + 迭代能力 | **✅ 已完成（2026-08-12，unsafe-vibe-dev，全量 2308/1）**：非 str 枚举 LLM 集成修复（成员名→值映射，真实 LLM 实证）+ 迭代/数量 + KNOWN_LIMITS §二 更新；自定义方法 = 值模型边界（`_code_enum_completion.md` / `_enum_instancing_assessment.md`） |
| PT-FEAT-3 | 用户类泛型类型参数 | **2026-08-12 用户升主线（下一 session）**：`class Box[T]:` 语法/语义/序列化扩展。地基已备（GenericTypeRegistry 全链路）。见 §〇 当前主线行 |
| PT-FEAT-4 | 用户类运算符重载 | VISION |
| PT-FEAT-5 | 语义错误用户友好化 + 诊断工具 + 性能基准 + CI/CD | 语义 4 阶段管线已稳定；错误码 `SEM_xxx` 转用户友好表述、符号表/类型绑定 JSON/dot 导出、编译时间基准。**前三项已落地（2026-08-09：诊断码目录 + 符号表/类型绑定导出 + `bench` 编译基准）**；**CI/CD：GitHub 侧自动触发已停用（2026-08-11 用户裁定，`.github/workflows/ci.yml` 改 `workflow_dispatch` 手动）**——现 CI 与本机 pytest 区别不大、必要性不足；待单独设计"可靠化/实用化"（真实 LLM e2e / 跨平台 / 发布产物等）后重新启用并补充，另行规划 |
| PT-FEAT-6 | CompilationResult 字段精简 | 前置：PT-FEAT-5 完成 + 管线稳定 ≥ 1 月 |
| PT-FEAT-7 | 二层 IR 路线评估 | VISION |
| PT-FEAT-8 | `.ibc_meta` 静态元数据快照 | **评估：维持现状待独立窗口（2026-08-09）**。核心切片（export_metadata/load_metadata_from_file）存在分层张力：加载侧重建要么重复 runtime `ArtifactRehydrator`（违禁双写真相），要么引入跨层入口（kernel→runtime / runtime→compiler 均禁止）。generic registry `restore` 仅覆盖 11 种泛型 kind（primitive/class/function 等需另建重建）。需独立窗口做完整设计冻结再落地。原 `docs/architecture/01_principles.md` §7.3.7 规划（已移除，登记于此） |
| PT-FEAT-9 | 内核结构化诊断/可观测性机制（CORE_DEBUG 替代物） | **已完成（2026-08-07，unsafe-vibe-dev，全量 2021 passed / 1 skipped）**：`kernel_diagnostic` helper（单一记录双投影：警告不门控 + 事件受 observability 门控，rc best-effort）+ 12 处站点迁移（文案逐字）+ e2e 事件投影测试 + `docs/architecture/09_observability.md`。设计/决策见下方 §12（归档记录） |
| PT-FEAT-10 | UID 生成统一（符号/节点/类型） | **已完成（2026-08-09）**：新建 `core/base/uid.py` 单一权威源（scope/symbol/intrinsic/node/type/anon_symbol/asset/rt_scope 九家族），symbols.py/serialization/context/runtime_serializer/scheduler/intrinsics/interpreter 全部经此生成，零内联格式字符串；格式逐字不变（round-trip 保真），契约测试 `test_uid_generator.py` 固化 |
| PT-FEAT-11 | 序列化器自动化（消除手动 `_collect_*` 调用） | **评估：维持现状（2026-08-09）**。`_process_value` 已对 `IbASTNode` 自动分派到 `_collect_node`（base 层）；`serialize_result` 的手动 `_collect_node/_collect_symbol/_collect_type/_collect_scope` 属**类型显式**调用（各写不同 pool），改 isinstance 自动分派不减少复杂度、反降可读性。标记"现有实现正确"成立，不强制重构。**撤销登记** |
| PT-FEAT-12 | AST 节点 UID 字段（编译期可见） | **登记于文档清理（2026-08-08）**：原 `02_metadata_ast.md §九 优化4` 愿景内容。UID 现仅序列化时生成，编译期不可见；建议 AST 节点加可选 `uid` 字段供编译期查询。低优先级，涉及 AST 结构变更（须查 `02_metadata_ast.md`） |
| PT-FEAT-13 | `api_config.json` 配置机制完备化（`_API_CONFIG_DESIGN.md`） | **2026-08-11 用户提出**：现 api_config.json 非运行时原生加载（仅脚本级约定）、schema 极简、无校验、mock 靠字符串嗅探。改进（参考 opencode.json）：**C1 原生加载**（`ai.load_config`/引擎自动，替代每脚本 file/json.parse）+ **C2 set_config 结构化** + **C3 校验诊断**（P0）；**C4 env 引用** + **C5 mock 配置化** + **C6 命名模型路由** + **C7 reasoning/每模型参数**（P1）；**C8 容器类型系统**（P2，示例 `(dict)config[...]` 强制转换限制）。C1-C3 为真实 LLM e2e 前置准备 |

---

## §12 PT-FEAT-9 交接要点：内核结构化诊断机制重建

> **状态**：**已完成（2026-08-07，unsafe-vibe-dev，全量 2021 passed / 1 skipped）**。本节为决策记录
> 归档。设计权威：`tasks_docs/DIAGNOSTIC_DESIGN.md`；实施记录见 `WORKLOG` PT-FEAT-9 阶段 B-D 落地。
> 落地后观测体系统一文档：`docs/architecture/09_observability.md`（状态面/事件面/诊断面/配置面）。
> **设计已冻结（2026-08-07）**：`tasks_docs/DIAGNOSTIC_DESIGN.md`——技术定位、职责边界、核心决策 D1-D7
> （单一事件类型 + KDIAG 代码注册表；单一记录双投影；代码即数据非门控；rc best-effort；边界；
> 码入 codes.py；不设 severity）、诊断码集（10 码 / 12 站点）、事件 schema、实施步骤 A-E。
> **前置依赖（2026-08-07 更新）**：统一执行地基已落地（阶段 1/3，unsafe-vibe-dev）；**先完成 R 批次**
> （`EXEC_REFACTOR_BATCH.md`：R1 trampoline/R2 通知式唤醒/R3 D-04 unify/R4 P3 公开/R6 函数自动捕获——彻底修复
> 阶段 1-3 的妥协处理）→ 诊断机制（阶段 4）落地；全局事件总线（P4）已就绪。

### 背景与现状

- **旧 CORE_DEBUG 已移除**（OBSERVABILITY 2A，commit 6878986）：`CoreDebugger` 类 / `IBC_CORE_DEBUG` env /
  CLI `--core-debug` / `debugger=` 参数链 / `ServiceContext.debugger` 契约 / 88 个 trace 调用点全部删除。
- **诊断价值承接**：真实异常回退 8 处 → `warnings.warn`（`intent.py:__to_prompt__` 回退、`kernel/base.py`
  cast/parse 回退、`llm_except_frame.py` snapshot/restore 回退、`_prompt.py` __payload_prompt__ 回退、
  `llm_parsing_strategy.py` validate/from_prompt、`engine.py` collect 跳过、`scheduler.py` 预定义符号、
  `loader.py` 插件跳过）；AttributeError 协议缺失回退 = 设计路径静默；流程日志直接删除。
- **观测骨架已存在**（单一权威源，勿另造）：`core/runtime/observability/`——`snapshot.py`（状态聚合）、
  `events.py`（EventBus + `emit_runtime_event` 统一发射入口 + EventSource 协议）、`config.py`（ConfigStore，
  `observability` 开关门控）。用户侧消费经 `iruntime`（snapshot/subscribe/configure）；测试侧经
  `IBCIEngine.test_snapshot()` / `ServiceContext.test_hooks`（TestHooks 协议）。

### 设计方向（对照 design-philosophy，禁止平行机制）

1. **不重建旧 CoreDebugger**：print 推送 + 级别门控 + 进程全局单例 + env/CLI 配置都是历史包袱，不再采用。
2. **结构化诊断面**：诊断事件经既有 EventBus 发射（如 `emit_runtime_event(rc, "kernel_diagnostic", {...})`，
   受 `observability` 开关门控、无订阅者零成本）——与 llm/chan/slot 事件同一机制（机制同构）。
3. **与现有消费端对齐**：`warnings.warn` 8 处是否迁入事件面，或保持 warnings（已可被 pytest.warns 断言）？
   需裁决：warnings 是"开发者可见"通道，事件面是"可编程观测"通道——两者语义不同，可能并存（非双通道冲突）。
4. **可测试**：事件面天然可被测试断言（订阅 + 收事件），优于 print。
5. **文档**：`docs/architecture/01_principles.md` 已删 diagnostics/debugger 引用；重建后按 WRITING_GUIDE 记录。

### 建议实施步骤

1. 设计冻结：诊断事件类型集 + 数据形态（对齐 events.py 现有事件 dict 形态）。
2. 评估 8 处 warnings 是否/如何接入；明确 warnings 与事件面的边界。
3. 在 EventBus 上落地 `kernel_diagnostic` 事件 + 门控 + 测试。
4. docs 治理：architecture 章节记录新诊断机制（人类手册）。

### 关联

- 移除记录：`OBSERVABILITY_REFACTOR.md` 决策记录 2A 行。
- 既有事件类型：`core/runtime/observability/events.py`（llm_dispatched/llm_resolved/chan_*/slot_updated/
  task_*/vm_*/configured）。
- 测试规范：`tests/COVERAGE_MATRIX.md` + `test_matrix_sync`。

---

## 五、缺陷 / 技术债（PT-DEBT-*）

> **优先级排序（2026-08-08 用户裁定原则：架构缺陷 ≥ 强相关依赖顺序 > 小而快的独立任务 > 非紧急功能演进）**：
> **PT-DEBT-9/10/11**（架构缺陷）→ **已根治（2026-08-08）**；
> **PT-DEBT-12/13/14/15**（异步地基遗留妥协）→ **全部收尾（2026-08-09，见 `tasks_docs/_ASYNC_UNIFY.md`）**；
> **PT-DEBT-4/5**（破坏性/暂缓）→ 排后。

| # | 内容 | 说明 |
|---|------|------|
| PT-DEBT-12 | 用户方法调用任务内同步重入调度器（F1） | **异步地基遗留（2026-08-08 审计）**：`vm_handle_IbCall` 不展开 `IbBoundMethod` → `receive('__call__')` → `vm.run_body` 嵌套调度器。最常见 `obj.method(x)` 路径；方法含 Waitable 时死锁、深递归方法嵌套 Python 栈。改造：解包 `IbBoundMethod` → CPS trampoline（与函数调用同构）。见 `_ASYNC_UNIFY.md` F1 |
| PT-DEBT-13 | `chan.send` 有界满通道任务内真阻塞（B1） | **异步地基遗留（2026-08-08 审计）**：`send` 返回 None（满时 `_cond.wait` 阻塞线程），与 `recv`（已转 Waitable）不对称；唯一消费者同调度器时死锁。改造：send 满时返回 Waitable（宿主契约变更需评估）。见 `_ASYNC_UNIFY.md` B1 |
| PT-DEBT-14 | `slot.update(fn)` CAS 同步回调 / prompt hint 同步调用（F2/F3） | **异步地基遗留（2026-08-08 审计）**：CAS 锁外 `fn.call`（lambda 嵌套调度器、behavior 阻塞 LLM）；`_get_llmoutput_hint` CPS 路径内同步 `.call()`。改造：update 可调用分支返回 Waitable / hint vtable CPS 化。见 `_ASYNC_UNIFY.md` F2/F3 |
| PT-DEBT-15 | 同步 `.call()` 孪生 / 驱动循环 / LLM 调用双路径（M1-M4） | **异步地基遗留（2026-08-08 审计）→ 全部收尾（2026-08-09）**：各 CPS 路径保留同步 `.call()` 双写（M1）、`_drive_generator` vs `_drive_loop_gen` 重复（M2）、prompt 构建双实现（M3）、CPS 内 `_call_llm` 同步阻塞（M4）。改造：收敛单一 CPS 权威路径 + 薄宿主包装 + LLM 真挂起。**M1/M2 已完成（独立分支 exp/async-m1m2，全量 2137/1）**；M3 已收敛；M4 已完成（2026-08-08）。见 `_ASYNC_UNIFY.md` M1-M4 |
| PT-DEBT-16 | 异步统一完整性遗留（A1-A6，`_HEALTH_AUDIT_PLAN.md`） | **地基闭环后 6 处次要路径仍任务内同步重入/嵌套调度器（2026-08-09 只读审计）→ A1-A4 已完成（2026-08-10，全量 2138/1）**：**A1** 内联 `@~` 表达式接 CPS（llm_behavior.py 切 `execute_behavior_expression_cps`，顺带补 `IbGenerator.generic_next` Waitable 契约缺口）；**A2** 意图消解 CPS 化（`resolve_content_cps`/`IntentResolver.resolve_cps`/`get_resolved_prompt_intents_cps`，CPS 预求值路径消除 `vm.run` 重入）；**A3** `_SlotUpdateWaitable` 增 `cps_drive` 帧内驱动（`CPSDrivable` 协议分派，消除嵌套 TaskScheduler）；**A4** LLM 函数 CPS-yield（`_prepare_llm_function_call_cps`+`_call_and_parse_llm_function` worker 化，PT-FEAT-1 直接项）。**剩余**：**A5** 类构造 `instantiate` 字段 `vm.run` / `init_method.call`（ib_class.py:128/154）；**A6** 协议方法 `.call` 条件触发嵌套（llm_parsing_strategy / llm_except_frame）。**处置**：**A5 已根治（2026-08-11，unsafe-vibe-dev 356b0d8，全量 2137/1）**——用户类（不含原生 __init__）构造改返回 `_ClassInstantiateDrive`（Waitable+CPSDrivable），`cps_drive` 在 VM 帧内 yield 字段默认值 + 用户 __init__（UserFunctionCall），消除 `vm.run` 重入与 `init_method.call` 嵌套 TaskScheduler；leaf.py 兜底细化（CPSDrivable 无论 func 是否 IbClass 均帧内驱动，纯 Waitable 仅非 IbClass auto-yield——thread 原生 __init__ 返回 IbThread 句柄仍不 auto-yield）；宿主/线程体走同步 instantiate 兜底。**A6 评估维持现状（2026-08-11）**——`__snapshot__`/`__restore__` 为 niche 协议、条件触发（仅用户定义且 llmexcept 异常时），CPS 化需侵入异常/重试路径、成本高收益低；`__from_prompt__`/`__validate_prompt__` 在 worker 线程（非缺陷）。登记为已知项，待未来独立窗口评估。见 WORKLOG 2026-08-11 |
| PT-DEBT-17 | `ai.run_batch` 同步阻塞路径（统一执行模型冲突） | **已彻底修复（2026-08-11，unsafe-vibe-dev ebbb7f8，全量 2135/1）**：三层不一致（①主线程 `fut.result()` 同步阻塞等全部 LLM ②同步 `_prepare_behavior_call` `vm.run` 重入 ③与 `stream_call` Waitable 范式割裂）全部根治——`run_batch` 返回 `CPSDrivable` Waitable（`_run_batch_cps` 用 `_prepare_behavior_call_cps` 嵌入 VM 帧栈消除 vm.run 重入 + 多 LLM Future 聚合 `LLMBatchFuture` 由调度器非阻塞等待），与 `stream_call` 同范式；vtable return_type=list 契约不变（auto-yield 后仍收 boxed IbList）；宿主/线程体无 VM 走 `_run_batch_sync` 同步兜底（与 `_SlotUpdateWaitable._drive` 同构）。顺带清理死代码：`LLMExecutorImpl.resolve()` + `LLMFuture.get()`（VM 全走 `resolve_future_cps`）+ 其 5 个死测试 + 协议声明同步。`ihost.collect`/`run_isolated` 为透明异步 auto-yield（非问题，已澄清）。详见 `_code_run_batch_cps.md` / WORKLOG |
| PT-DEBT-4 | `file` 模块重命名 | `file` 影子化 Python 内建，长期重命名（如 `fs`/`io`）。当前过渡措施已实施 |
| PT-DEBT-5 | 全项目文件命名清理 | 过短/欠层次/欠区分度/影子化内建的代码文件命名排查。暂缓，独立窗口执行 |
| PT-DEBT-6 | `register_module()` 可观测性缺口 | **已落地（2026-08-06）**：用户插件覆盖 kernel-native 时 `warnings.warn`（原静默忽略）。顺带修正测试配置 bug（plugin_paths 指向插件目录本身导致插件从未加载）。全量 pytest 零回归 |
| PT-DEBT-7 | 删除 `is_nullable` 字段，全面 `Optional[T]` | **已落地（2026-08-06）**：死字段清理（`is_assignable` 早已用 `Optional[T].wrapped_type`，序列化不消费）。全量 pytest 零回归 |
| PT-DEBT-8 | ~~折叠 `IbXxx` 为单一 `IbValue`~~ → **重定义为"值层分派收敛审计"** | **已落地（2026-08-06）**：系统层面定论——折叠是伪目标（消 isinstance 动机已由 name 分派达成；具体类=领域方法载体，折叠违反单一职责）。实际收敛：`is_sequence_value` 统一容器分派、`IbLLMCallResult.is_uncertain` 统一不确定判断；类角色分工固化于 `03_type_system.md` §6.4。全量 pytest 零回归 |
| PT-DEBT-9 | ~~RecursionError 被 `VM: Call failed` 级联包装掩盖根因~~ → **已根治（2026-08-08）** | `leaf.py` 等五处语义错误包装站点加环境限制防护（`core/runtime/shared/env_limits.py` 判定 + `diagnostics.handle_environment_limit` 发射 `KDIAG_RUNTIME_ENV_LIMIT`），RecursionError 根因保留传播，不再被掩盖成语义错误。见 NEXT_STEPS 2026-08-08 批次 |
| PT-DEBT-10 | ~~线程体用户函数递归仍同步嵌套（`_drive_generator` 非 trampoline）~~ → **已根治** | **已落地（2026-08-08）**：`_drive_generator` 改显式生成器栈（trampoline，与 `_drive_loop_gen` 同构），UserFunctionCall 压栈而非递归驱动——线程体内深递归不再嵌套 Python 栈。顺带根治线程体模块级函数解析（任务全局作用域链到模块作用域，`ScopeImpl(parent=main_global_scope)`；此前线程体无法解析模块级函数，n≈2 即失败）与线程逻辑栈上限对齐主路径（`max_call_stack`）；修复 `_vm_call_user_function`/`IbUserFunction.call`/`IbLLMFunction.call` push 后 finally 无条件 pop 的栈不均衡潜在 bug（`pushed` 标志）。新增线程体深递归 e2e（depth=300）。全量 pytest 零回归 |
| PT-DEBT-11 | ~~`_UserFunctionCall` 内部标记类定义位置（handler 依赖 VMExecutor 内部）~~ → **已根治（2026-08-08）** | `UserFunctionCall` 下沉 `core/runtime/shared/user_call.py`（与 Signal/Waitable 同类叶子），handler/线程体不再向上依赖 VMExecutor 内部类。见 NEXT_STEPS 2026-08-08 批次 |

---

## 六、长期周期清扫（PT-AUDIT-*，持续周期工作，随主线阶段边界择机启动）

> 审查/审计/治理均为**周期性持续清扫**，非一次性完成——每轮主线改动后按需复核，
> 与"文档清洗与梳理 / 注释卫生清理"同性质。执行记录见 git 历史。

| # | 内容 | 说明 |
|---|------|--------------|
| PT-AUDIT-1 | 代码异味核对分析 | `CODE_SMELL_AUDIT.md`（单一事实来源），独立分支执行。**周期事实回顾已完成（2026-08-09，A/B/C/D 全量定案）** |
| PT-AUDIT-2 | 条件分支与异常嵌套复杂度审计 | `BRANCH_NESTING_AUDIT.md`（AST 基线），独立分支执行。**剩余待核验项已核验（2026-08-09）**——ibci_ai 已窄化 `_PROVIDER_ERRORS`、auto_discovery 为 fail-fast 重抛（A 类保留）。**深嵌套/长 elif 链待独立窗口**（`runtime_serializer._collect_instance` 深度16/`_get_instance`17、`core_scanner._scan_complex_access` 10、`binding_analysis_pass._analyze_node` 9——巨型 elif 分派链，方向：分派表/守卫子句）。**内核健康项（2026-08-09 登记 → 2026-08-10 处置）**：疑似死同步包装（`_behavior.py`/`_llm_function.py` 4 方法）**已清理**；`_drive_loop_gen`/`_drive_generator_loop` 双维护循环**已合并**；A2 意图消解 `vm.run` 重入**已 CPS 化**。**2026-08-10 彻查补充**：同步 `LLMExecutorImpl.resolve()`（`_scheduler.py:78`）与 `LLMFuture.get()`（`llm_result.py:129`）为**死代码**（零真实调用，仅 docstring 示例，VM 全走 CPS `resolve_future_cps`）——可随 PT-DEBT-17 或独立清理（涉及 IILLMExecutor 协议声明） |
| PT-AUDIT-3 | 代码复核审查循环（R 系列） | R1 正式 review / R2 健康诊断 / R3 异味扫描 **已执行（2026-08-05）**；R4 覆盖率核对 **已执行（2026-08-09）**、R5 doc 审计聚焦治理已执行（全量待独立窗口）。复核清单见 `PENDING_REVIEW_ITEMS.md` |
| PT-AUDIT-4 | 任务控制文档清洗与梳理（文档治理周期） | 删除已完成/无价值任务、无用设计决策、任务代号重整、交叉一致性核对。**已执行（2026-08-05）**，周期复核 |
| PT-AUDIT-5 | 注释卫生清理（周期） | 删除代码注释中的任务代号、历史实现方案、修复过程叙述，保留功能设计语义。**已执行（2026-08-05）**，周期复核 |

## 七、文档同步（PT-DOC-*）

### PT-DOC-1 docs/ 技术手册同步（D1-D5 已落地 2026-08-06）
| # | 内容 |
|---|------|
| D1-D5 | **已落地**：新写 `docs/syntax/14_concurrency.md`（chan/slot/subscriber/thread/thread_result + pubsub/send_nowait 语义 + signal 移除说明），KNOWN_LIMITS §二十二，SYNTAX_REFERENCE/README 接入。详见 WORKLOG |

### PT-DOC-2 语法手册定位段补充
**已完成（2026-08-06）**：14 篇 `docs/syntax/*.md` 均已有合格定位段（`> 本章描述...面向...覆盖...`），DOC_AUDIT F3 期间随"深入指引"补齐时一并落地。条目移除。

### PT-DOC-3 技术手册健康修复（2026-08-09 三轴盘点，低风险）
> 来源 `_HEALTH_AUDIT_PLAN.md` 文档健康节。
- **P1/P2 三修已完成（2026-08-10）**：① `01_principles.md:255` §6.3 改写为现状（意图栈继承由 `IbIntentContext.fork()` 承担，公理 IC-1；`IsolationPolicy` 实际字段 `inherit_plugins`/`collect_timeout`，跨隔离边界不继承意图）；② `04_vm_interpreter.md:29` 统一表述（模块入口 `execute_module`→`run_body`，宿主入口 `.call` 薄包装委托 `_vm_call_*`+`_drive_generator`）；③ `docs/README.md` 目录树补 `15_diagnostics.md`。
- **P2（规划）** How-to 层仅 2 篇：生成器/并发/llmexcept/隔离缺操作指南（Reference→How-to 读者旅程断裂），需按 WRITING_GUIDE 评估。

---

## 八、测试体系（PT-TEST-*）

| # | 内容 | 说明 |
|---|------|------|
| PT-TEST-1 | 测试体系治理与彻底重构 | **已完成（2026-08-06，OBSERVABILITY_REFACTOR 2D）**：tests_v2 全域迁移 + Phase 5 切换 + 语义覆盖守恒 1565=1565，全量 1962/1。详见 `TEST_REFACTOR.md` |
| PT-TEST-2 | e2e 测试覆盖率提升 | `for...if` 过滤、复合赋值运算符 e2e **已补（2026-08-06）**；其余覆盖缺口由矩阵 `🔶 缺失` 项承接 |
| PT-TEST-3 | 测试名与覆盖矩阵同步 | **已完成（2026-08-06，并入 PT-TEST-1）**：矩阵三段式填充（`tests/COVERAGE_MATRIX.md`，13 语义域 154 真实引用 + `test_matrix_sync` 机器校验）。核对发现存档于 `tasks_docs/TEST_MATRIX_FINDINGS.md`（TRUE_GAP 项已在矩阵标 `🔶 缺失`） |

---

## 九、封存（PT-SEALED-1：media Phase 4 多模态容器）

> **已彻底封存（2026-08-01，无限期搁置）**：恢复需显式解封并重估。代码层零启动，
> 设计要点见 `tasks_docs/MEDIA_DESIGN.md`。前置（路径统一/内核原生化/磁盘型
> 存储）已完成。解封时需实现三项：
> 1. 多模态模型注册字段（`ai.register_model` 存 modalities/endpoint/audio_config）；
> 2. 非聊天端点推理绕过（endpoint 字段强制非推理，跳过 reasoning prompt 注入）；
> 3. 磁盘型响应解析协议（`from_response` 平行协议 + `has_multimodal_response_cap` flag）。

> **已落地部分**：`__payload_prompt__` 协议与 `audio`/`image`/`video` 类型（见 `docs/syntax/07_behavior_expressions.md` §7.6、`docs/subsystems/02_file_container.md`）。

---

## 十、设计决策（保留——防止未来误解）

### 仍有效的设计决策

| 决策 | 内容 |
|------|------|
| 运行时值 `type_ref` 保持基础 spec | 可变值（list/dict）不固有泛型身份（同一对象可赋给 list[int]/list[str]，语义不自洽）；符号/序列化侧已精确 |
| callable 签名属值层属性 | fn_callable/behavior 的签名（param_types + return_type）在运行时值创建时经 node_to_type 捕获、自持于值（JSON 安全字符串，序列化保真）；不落 CALLABLE_INSTANCE 类型 spec（该 spec 仅载 value_type）。`type(f)`/`__return_type__()` 据此内省 |
| 通信 `Signal` 抽象移除 | 零消费者空壳 + 与 VM 控制流 Signal 撞名 → 彻底删除 |
| 瞬态序列化协议 | thread/chan/slot/subscriber 统一 `__transient_state__` 存根；反序列化不复活活体 |
| 类型符号 `class_ref` | IbClass 序列化为类名引用、反序列化重绑定 registry 真实类 |
| 泛型成员特化协议化 | `resolve_member` per-type 级联收敛为 `GenericTypeDeclaration` 声明回调 |
| 行为体 fn `-> auto` = str 强制 | LLM 输出默认字符串；要其它类型必须显式 `-> T` |
| 可调用实例不写 value_meta | meta 冗余拷贝专用字段且含非 JSON 值（IbIntentContext/IbCell/TypeDef）；专用字段是单一事实来源 |
| `expected_type` 落盘为类型名字符串 | 运行期由调用点经 node_to_type 解析；字段本身仅元数据 |

### 设计排除（语言级限制，已写入 `docs/KNOWN_LIMITS.md`）

| 排除 | 原因 |
|------|------|
| walrus `:=` / lambda 体赋值 | 设计排除（KNOWN_LIMITS §十九.1） |
| if-block 内重声明同名变量 | 设计排除（KNOWN_LIMITS §十九.2） |
| loader 与 check.py 签名校验收敛 | 设计隔离：SDK 离线校验不初始化运行时，强制收敛引入 SDK↔runtime 错误耦合，不收敛 |

---

## 十一、推迟工作记录：循环打破局部 import tradeoff（待架构重构时复核）

> 原则：理想上应永远避免循环依赖。但允许少量"设计合理、能显著减少工作量"的局部 import 作为
> **谨慎 tradeoff**。以下为保留的循环打破局部 import，列为未来推迟工作，待架构重构
> （依赖方向下沉 / 接口上移）时逐项复核。

| 记录 | 位置 | 引用 | 保留理由（tradeoff） | 未来复核方向 |
|---|---|---|---|---|
| L1 | `core/runtime/objects/kernel/base.py:31/32` | `from .functions import IbBoundMethod` / `from .ib_class import IbClass` | 运行时构造/分派所需，base↔functions/ib_class 环 | 下沉共享基类到独立叶子 |
| L2 | `core/runtime/objects/kernel/ib_class.py:165` | `from .functions import IbBoundMethod` | 运行时构造，ib_class↔functions 环 | 同上 |
| L3 | `core/kernel/spec/type_ref.py:128` | `from .base import TypeKind` | 运行时 kind 比较分派，base↔type_ref 环 | 下沉 TypeKind 到叶子 |
| L4 | `core/kernel/spec/registry/_members.py:121` | `from ..base import TypeDef` | 运行时构造 TypeDef | 下沉 TypeDef 到叶子 |
| L5 | `core/kernel/spec/registry/_runtime.py:90` | 相对导入 | 运行时（审计标注循环打破） | 复核定位并下沉 |
| L6 | `core/runtime/interpreter/interpreter.py:466` | `from vm.vm_executor import` | interpreter↔vm 环 | 延迟属性引用评估 |
| L7 | `core/runtime/objects/kernel/user_functions.py:42/79/140` | `from ..primitives` / `..cell` / `..signals` | 运行时（热路径） | 复核能否去环 |
| L8 | `core/runtime/shared/llm_result.py:56/130` | `from ..objects.primitives/kernel` | 运行时 | 复核能否去环 |
| L9 | `core/runtime/path/install.py:36/40` | `import ibci_modules` / `import core` | 模块加载期 | 重构加载顺序 |
| L10 | `ibci_modules/ibci_ai/core.py:298` | `from core.runtime.frame import` | 插件↔core 环 | 接口上移 |
| L15 | `core/engine.py:119/123` | `kernel_native_modules` / `file_impl` | 构造期延迟加载重型实现 | 核验是否可去除 |
| L17 | `core/compiler/semantic/context.py:117` | `from ...passes.prelude import Prelude` | context↔passes 环 | 依赖方向重构 |
| L18 | `core/runtime/bootstrap/kernel_native_modules.py:75` | `from kernel.host_interface import` | 环（审计待核验） | 复核定位并下沉 |

> 复核触发：任一处所在模块发生架构重构、或引入新的循环依赖、或出现相关技术债时，返回本表
> 逐项复核该 tradeoff 是否仍成立。
