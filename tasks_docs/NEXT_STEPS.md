# NEXT_STEPS - 当前最紧要项

> 本文件**只**记录当前最紧要、可立即开工的下一步；长期规划见 `tasks_docs/PENDING_TASKS.md`（§〇 优先级总表）。
>
> **最后更新**：2026-08-12（**用户类泛型 PT-FEAT-3 完整落地** + F9 `ai.load_project_config` 实施完成；
> 全量 **2339 passed / 1 skipped**；见下方"已完成"与"交接要点"节）

---

## ✅ 已完成：用户类泛型参数 PT-FEAT-3 完整落地（2026-08-12，unsafe-vibe-dev 35bb2de，全量 2339 passed / 1 skipped）

> 设计冻结 `PT_FEAT3_DESIGN.md`；独立复核两轮 PASS（P2-1 父特化恒注册 / P2-2 嵌套实参映射 全整改）。

- **全链路**：AST `IbClassDef.type_params`+`parent_args` + parser（`class Box[T]`/`(Box[T])`）+
  `TypeKind.TYPE_PARAM`/`TypeDef.type_params` + 语义类型参数占位解析 + `resolve_specialization`
  用户类分支（特化 spec 构造 + members 替换 + 父特化递归注册）+ 序列化（type_params/parent_args
  落 artifact）+ 运行时（`IbClass.__getitem__` 类型特化 + 特化类 hydration）。
- **已支持**：多特化并存 / 字段·方法参数·返回类型特化（含嵌套 `Box[list[int]]` 参数类型检查）/
  嵌套泛型 `list[Box[int]]` / 多参数 `Pair[K,V]` / 泛型继承 `class Sub[T](Box[T])`。
- **守卫**：裸用（注解+实例化）/ 实参数不匹配 / 字段-T 冲突 / Enum 泛型 / 类型参数遮蔽内置 /
  非泛型子类继承特化，均 fail-fast。
- **测试**：21 e2e + 2 序列化 round-trip（全量 2311→2339）。文档：06_oop §6.4 / KNOWN_LIMITS
  §十四 #1 / arch/02 §2.6 / 15_diagnostics。
- **边界**（KNOWN_LIMITS §十四#1 ①-⑧）：bound 约束 / `class Sub(Box[int])` / 父引用嵌套实参 /
  Enum 泛型，后续增量。

## ✅ 已完成：F9 显式配置 `ai.load_project_config`（2026-08-12，unsafe-vibe-dev a49555b，全量 2311 passed / 1 skipped）

> 用户拍板命名 + 本轮实施。独立复核 PASS（5 项整改全完成）。设计记录 `_code_ai_autoset.md` +
> 实施记录 `_code_f9_load_project_config.md`。

- `setup()` 去自动加载段（引擎启动不再自动加载 api_config.json）；新增 `load_project_config()`
  （ec/project_root 缺失 fail-fast + 路径规范化 + 缺失 no-op + 幂等）；vtable 注册；测试
  （无调用不加载/显式调用加载/fail-fast/符号链接/幂等/语言级可达）；examples 01/02/03 判断前
  加显式调用；文档同步（README/guide 01+02/syntax 11+15/config_loader/execution_context/
  catalog/codes）。

## ✅ 已完成：遗留独立窗口批次——PT-DEBT-24 call_intent 清理 + PT-AUDIT-3 S1-S5 处置 + 枚举实例化评估（2026-08-12，unsafe-vibe-dev，全量 2308 passed / 1 skipped）

> general agent 独立复核 PASS；设计记录 `_enum_instancing_assessment.md`。

- **PT-DEBT-24（S4）call_intent 死代码根治**：AST 均无 intent 字段 → call_intent 恒 None →
  全链清理（behavior 短路分支 / BehaviorCallSpec.pre_resolved / LLM 函数穿透参数 /
  IbBehavior.call_intent 值字段+序列化 / 工厂 / 协议）；保留 get_resolved_prompt_intents
  协议预留参数。
- **PT-AUDIT-3 S1-S5**：S4 根治；S5 双实现去重（共享 `_try_axiom_output_hint`）；
  S1/S2/S3 复核为已知边界（S1 dispatch hint 同步 .call 嵌套调度器仅 hint 含 VM 依赖 Waitable
  时可观察；S2 跨线程 EC 模块名改写需 worker 同步构造类且 drive 返回非实例；S3 task 线程写
  单写槽为纯可观测性竞态）——各登记独立设计窗口（`_PT_AUDIT3_RECORD.md` §三）。
- **枚举实例化设计候选评估**：`_enum_instancing_assessment.md`——维持现状（LLM 集成改造为
  核心硬伤：kernel 层无法构造实例 + 通用解析路径需类型感知包裹），独立设计冻结候选。

## ✅ 已完成：enum 补全 + 嵌套包 import 根治 + 文档批次 + 用户试用（2026-08-12，unsafe-vibe-dev，全量 2308 passed / 1 skipped）

> 按 `_ENUM_SWITCH_COMPLETION_HANDOFF.md` + 独立窗口打包（用户确认）。设计记录
> `_code_enum_completion.md`；独立复核（general agent）PASS + 建议项整改；用户试用
> `_LLM_TRIAL_ENUM_IMPORT_20260812/`（9 例全过）。

- **enum 补全（PT-FEAT-2）**：① **非 str 枚举 LLM 集成修复**——编译期枚举常量成员
  （含负数 `-1`）写 `MemberSpec.metadata["value"]`，`EnumAxiom` 建 `{成员名→成员值}`
  映射，from_prompt 大小写不敏感返回值；str 零回归、值≠名正确，真实 LLM 实证
  （qwen 输出成员名 OK→值 200→switch 命中）。② **迭代/数量**——`has_iter_cap` +
  `get_method_specs(to_list/len)` + 运行时 Enum 基类绑定（子类经父链继承）；
  `for v in Color:` / `len(Color)` 可用。③ **自定义方法 = 值模型边界**（`Color.RED`
  是底层值非实例，方法不可达）——文档化 KNOWN_LIMITS §二 §2.4，实例化枚举记设计候选。
  ④ KNOWN_LIMITS §二 更新。+22 契约/e2e 测试。
- **嵌套包 import 根治**：`import subpkg.util` + `subpkg.util.fn()` INT_INTERNAL_ERROR
  三层根因（嵌套段原始 Symbol 入 members / visit_IbImport 绑定全名 / 中间段 PRIMITIVE
  kind 重导入守卫 + 运行时缺包命名空间）全部修复；2 层/3 层/同包多导入合并全过；+4 e2e。
- **文档批次**：DOC-ISSUE-001~007 批量同步 + BOUNDARY-001~005 处置（001/002 已修核验，
  003/004/005 文档精确化）+ KNOWN_LIMITS §十四 #2 运算符覆盖度实测核对
  （比较/算术/一元/成员全可用，`is` 恒身份；+6 回归测试）。
- **用户试用**：自建 `_LLM_TRIAL_ENUM_IMPORT_20260812/`（harness 三层保护复用），
  9 例全过（含真实 LLM 非 str 枚举集成实证），**无新增缺陷**。
- **遗留**：枚举实例化（设计候选，独立窗口）；KNOWN_LIMITS §十四 #1 用户类泛型参数（独立大任务）；
  嵌套包 `import subpkg`（无子模块的纯包）仍 DEP_MODULE_NOT_FOUND（包目录非模块，Python 同）。

## ✅ 已完成：真实 LLM 压力试用暴露缺陷修复 + 易用性修复（2026-08-12，unsafe-vibe-dev，全量 2270 passed / 1 skipped）

> 按 `_FIX_PROPOSAL_CRITICAL_REVIEW_20260812.md` 修正后方案 + `_KERNEL_ISSUES_ANALYSIS_20260812.md`
> 根因分析执行（用户授权破坏性变更）。修复后独立复核全部 PASS。易用性修复见
> `_USABILITY_AUDIT_20260812.md`。

- **批次 A（低风险直接合并）**：**PT-DEBT-27** 真实 LLM provider 失败异常投递对称化
  （`_drive_loop_gen` Waitable yield except→pending_exception 重投递，TaskCancelled 穿透；+4 测试）；
  **PT-DEBT-25** `global` 关键字镜像 nonlocal（visit_IbGlobalStmt + prescan 排除 global 名，
  运行时零改动；+6 测试）；**PT-DEBT-28** `_spec.py` vtable 补注册 `ai.get_retry`/
  `is_auto_intent_injection_enabled`（+3 测试）。
- **批次 B（专项）**：**PT-DEBT-26** 整模块 import 档3 写入侧统一 MemberSpec 形态
  （`_symbol_to_member`/`_spec_to_typeref`）+ 档2 零参数 callable 按 kind 绑定（+4 测试）。
- **批次 C（设计级）**：**O1+I1** 用户类协议方法（`__call__`/`__iter__`）帧内 CPS 驱动
  （`_UserCallDrive` Waitable+CPSDrivable，根治嵌套调度器；生成器方法经 IbUserFunction.call 返回
  IbGenerator + resolve_iterable to_list；+9 测试）。设计记录 `_code_call_cps_drive.md`。
- **批次 D**：**O2** 字段默认值递归深克隆（try_deep_clone，消除内层 list/用户对象跨实例共享；+3 测试）；
  **文档修正**（05_functions §5.8/§5.9、KNOWN_LIMITS §二十四/§十四 #2/§一）。
- **易用性批次**：**return@~ 编译期拦截随迁 v2**（补全设计意图，消除"文档说禁止实际通过+运行时
  类型错"陷阱；+4 测试）；**switch 内 break 消费为 no-op**（C 习惯冗余写法不再报
  RUN_GENERIC_ERROR，CONTINUE 透传；+3 测试）；**布尔字面量错误引导**（true/false/none 报
  "Did you mean True/False/None"；+3 测试）；**KNOWN_LIMITS §十一 更新**（switch 基本可用 +
  使用约束）。
- **遗留待独立窗口**：嵌套包 `import subpkg.util` + 成员访问的 INT_INTERNAL_ERROR（修复前既有）；
  DOC-ISSUE-001~007 文档同步；BOUNDARY 记录；**enum 补全（见 `_ENUM_SWITCH_COMPLETION_HANDOFF.md`）**。

## ✅ 已完成：真实 LLM 全面压力试用重启（2026-08-12，修复后代码）

> **unsafe-vibe-dev，全量 2210 passed / 1 skipped（试用零回归，未改内核）**。
> 完整证据：`tasks_docs/_LLM_TRIAL_20260812/`（DESIGN/harness/cases/logs/REGISTER）+ 报告
> `tasks_docs/_REAL_LLM_TRIAL_REPORT_20260812.md`。

- **试用地基**：三层死循环保护 harness（OS 进程级硬超时 SIGKILL 进程组 + `--max-inst` + LLM 调用
  超时，无超时不运行，零遗漏）+ 确定性文件化记录（logs/ + register.jsonl + REGISTER.md）。
- **D1 全语法遍历**：docs/syntax/01-15 每章特性真实 LLM 各跑一遍，~110 次运行全经保护。
- **A1-A5 重验全通过**：意图 @/@! 赋值路径（7339220 实证：r1=收到）、内建遮蔽+LLM 初始化
  （sum=7）、generator.to_list（U1）、dispatch 赋值后 idbg 观测（d6d28e1）、run_batch 观测（df1a896）。
- **B1-B3 补正式记录**：ihost 隔离（child 需自带 api_config.json）/内建/异常。
- **D2 压力试用**：交叉（生成器+意图+llmexcept、thread+chan+run_batch、类+LLM+slot、闭包+生成器）、
  正交（@+×run_batch、snapshot vs lambda、双批并发）、多层次（高阶 lambda、循环体 LLM+llmexcept）、
  多可能性（边界值/遮蔽拒绝/str'0'真值）、多文件（循环导入/插件/隔离子项目）全 PASS。
- **D3 批判检测**：格式服从稳定、C1 长提示注入完整、C2 非确定性稳定、C4 并发无竞态、
  llmexcept 真实收敛、耗尽可捕获、意图实证。
- **暴露问题（只记录，未修复）**：**4 项 P1 KERNEL_ISSUE**（global 写访问失效 /
  整模块 import+成员访问 INT_INTERNAL_ERROR / provider 失败 LLMCallError 逃逸 try/except /
  ai.get_retry 等 vtable 未注册）+ **7 DOC_ISSUE** + **5 BOUNDARY**。登记 PENDING_TASKS
  （PT-DEBT-25~28 + 清单），见 REGISTER §六/报告 §六。
- **合并条件重估**：检测维度已基于修复后代码确认（无 P0；4 项 P1 不阻断主路径，待独立窗口）；
  阶段 3 合并/push 仍待用户显式授权（禁 push 硬原则）。

## ✅ 已完成：合并收尾准备（2026-08-11，doc-health P1/P2 + 版本 0.2.0 + examples 真实跑通 + PT-AUDIT-3）

> **unsafe-vibe-dev，全量 2209 passed / 1 skipped**。合并前置全部完成，`_MERGE_READY_REPORT.md` 落档。

- **doc-health P1/P2 全部处置**（`_DOC_HEALTH_20260811.md`）：P1 16 项复核修齐（已修核对 4 + 实修 12，
  含 `@method` 陈旧引用、`已重构为包` 历史演变、09 章节编号、KDIAG 码表补全、super 归属唯一化、
  05_coroutine 状态文档重写、04_control_flow 小节归位、15_diagnostics 分域引言）；P2 12 项
  （A5 类构造 CPS 变更反映 arch/04 §2.7 + arch/05 公理 EXEC-4、README 阅读路径、howto 扩充 2 篇、
  死引用清理、定位段强化、TestHooks 模板化）。
- **pyproject 版本 0.1.0 → 0.2.0**（0.1.0 后 411 commits / 65 feat）。
- **examples 真实 LLM 跑通确认**：11 例全过（本地 qwen3.6-35b-a3b）；**暴露并修复 dispatch 赋值后
  idbg/ai 调用信息不可观测缺陷**（`_record_dispatch_call_info` 单写槽即时记录，resolve 补全 response，
  +3 回归测试，commit d6d28e1）。
- **PT-AUDIT-3 双路径专项审计执行**（general agent 独立审计）：无 P0；3 确凿 P2 漂移修复
  （run_batch 观测 / active_intents / _drive 装箱）+ generator 兜底 fail-fast + KNOWN_LIMITS 修正；
  5 疑似项待独立窗口（`_PT_AUDIT3_RECORD.md`）。
- **合并就绪报告**：`tasks_docs/_MERGE_READY_REPORT.md`（四项合并条件全满足；阶段 3 待用户授权）。

## ✅ 已完成：R 批次 —— 统一执行地基复核与根治修复（R1-R6）

> **2026-08-07 用户裁定**：阶段 1-3 落地暴露的妥协处理**必须彻底修复，不留妥协**；工作成本/难度不参与权衡；
> IBCI 无用户，已文档化设计可为长远可维护性与架构健康性被推翻。
> **完整设计/深度分析/决策见 `tasks_docs/EXEC_REFACTOR_BATCH.md`**（无悬而未决问题）。

**批次（各独立分支，禁合并，全量零回归后手动 cherry-pick 应用 unsafe-vibe-dev）——全部完成**：

| 序 | 项 | 分支 | 内容 |
|----|----|------|------|
| 1 | R4 + R3 | `exp/exec-ra` | P3 公开协议（`IbCell.mark_shared_with_main`）+ D-04 意图修复（`IbThread` 本体满足 Waitable，unify `is_done`，auto-bind 支持 property-backed 方法，`await t` 可用）——**完成 82c9c0f，全量 1988/1** |
| 2 | R6 | `exp/exec-rb` | 嵌套函数自动只读捕获（与 lambda 同构，`nonlocal` 仅用于写）——P3 触发面回到审计预期宽度——**完成 35f1437，全量 1995/1** |
| 3 | R2 | `exp/exec-rc` | 调度器通知式唤醒（Waitable `register_wake` + 各 waitable 完成通知 + CommBuffer 回调表 + 引擎 spawn 钩子）——根治 poll+park 与"单待决阻塞"——**完成 c16b05e/c4c63aa，全量 1998/1** |
| 4 | R1 | `exp/exec-rd` | 函数调用 trampoline 化（`_vm_call_user_function` CPS 内联，EXEC-1 根治，深递归 Python 深度恒定）——**完成 6dc9214，全量 2001/1** |

**已定案（不再重议）**：R5 撤回（`await` 幂等是 auto-yield 组合的承载）；D-08 保留透明 async（CPS 天然可挂起 +
auto-yield 组合 + 值契约 + yield 自标记）。

**后续路线（R 批次已完成，进入下一主线）**：**阶段 4 PT-FEAT-9 诊断机制**（`DIAGNOSTIC_DESIGN.md` 已冻结）→
**阶段 5 `yield` 惰性生成器**（`EXEC_FOUNDATION_DESIGN.md` §5.2）→ 增量（streaming / host async 改进）。

---

## ✅ 已完成：阶段 4 PT-FEAT-9 内核结构化诊断机制重建（CORE_DEBUG 替代物）

> **2026-08-07 完成，unsafe-vibe-dev，全量 2021 passed / 1 skipped**。
> 设计权威：`tasks_docs/DIAGNOSTIC_DESIGN.md`（D1-D7 + 诊断码集 + 实施步骤 A-E）。
> 完整落地记录见 `WORKLOG` PT-FEAT-9 阶段 B-D 落地。

- **B 机制落地**：`codes.py` 增 `=== 内核诊断 (KDIAG_) ===` 节（10 码）；新建
  `core/runtime/observability/diagnostics.py`（`kernel_diagnostic` helper：单一记录双投影——投影A 警告
  不门控 + 投影B 事件受 observability 门控；rc 解析 best-effort：显式 > current-EC > 无→仅警告面）；
  events.py docstring 对账确认 P4 已先行完成（如实清单），增补 `kernel_diagnostic`；helper 单测 8 项。
- **C 站点迁移**：12 处运行时 warnings → `kernel_diagnostic`（文案逐字保留、detail JSON-safe）——
  协议回退 8 / 策略 2 / 运行时 2；host_interface（kernel 层）用函数体内惰性 import（先例
  registry.py:283）；scheduler.py 编译期站点按 D5 保持 warnings。
- **D 事件投影测试**：tests/e2e/test_kernel_diagnostics.py——协议回退双投影（警告逐字 + 事件结构化）、
  策略忽略站点无活跃 EC→仅警告面（fail-open 实证）、observability 门控（关→事件停、警告留）。
- **E docs 治理**：新写 `docs/architecture/09_observability.md`（状态面/事件面/诊断面/配置面四机制
  单点真理）；README/ARCHITECTURE/01_principles 索引同步；WORKLOG 记录。

**归档记录（均已根治 2026-08-08，见下方"已完成：2026-08-08 批次"节）**：PT-DEBT-9（RecursionError 级联包装）、PT-DEBT-10（线程体递归非 trampoline）、PT-DEBT-11（`_UserFunctionCall` 定义位置）。

---

## ✅ 已完成：阶段 5 yield 惰性生成器（2026-08-08）

> **unsafe-vibe-dev，全量 2043 passed / 1 skipped**（基线 2029，+14）。独立分支 exp/yield-generator 实验 → 手动应用（设计/决策见 `tasks_docs/YIELD_GENERATOR_DESIGN.md`）。

- **yield 惰性生成器落地**（c8b8956）：含 `yield` 的函数自动为惰性生成器（D-08 自标记函数种类，无 async 关键字）。
  - 词法 `yield` 关键字 + 语法 `yield` 表达式（LOWEST 优先级，`yield x+1` 产出 `x+1`）+ AST `IbYieldExpr`/`IbFunctionDef.is_generator`。
  - 语义 `_contains_yield` 自动标记生成器；yield 仅函数体内（`SEM_YIELD_OUTSIDE_FUNCTION`）；生成器返回类型 = `generator[元素类型]`。
  - 类型 `GENERATOR` TypeKind + `generator[T]` 泛型（factory/generic/type_ref/artifact_rehydrator 全链路）。
  - VM `vm_handle_IbYieldExpr` yield `GeneratorYield(value)` 标记 + `_drive_generator_loop` 单可恢复驱动（与 `_drive_loop_gen` 同构，GeneratorYield 挂起交付、Waitable 宿主等待）。
  - 运行时 `IbGenerator` 值对象 + `for`/`to_list` 迭代；调用路径经 UserFunctionCall/make_generator_driver。
  - **e2e 9 项**：基础迭代/状态跨 yield 保留/嵌套循环/条件内 yield/break 提前终止/生成器 as 值/LLM 组合（await 正交）/auto 赋值/非函数体 yield 报错。
  - docs/syntax/05_functions.md §5.8 惰性生成器章节。
- **架构缺陷优先起点清空**：PT-DEBT-9/10/11 全部根治（上一批次）。下一主线已完成，无阻塞项。

## ✅ 已完成：2026-08-08 批次（PT-DEBT-11/9/10 根治）

> **unsafe-vibe-dev，全量 2029 passed / 1 skipped**。完整记录见 `WORKLOG` 与 git 历史。

- **PT-DEBT-11**（4bf2644）：`UserFunctionCall` 下沉 `core/runtime/shared/user_call.py`（与 Signal/Waitable
  同类叶子），handler/线程体不再向上依赖 VMExecutor 内部类——保持"handler 是叶子、VMExecutor 调度"分层方向。
- **PT-DEBT-9**（c75541f）：环境限制异常（RecursionError/MemoryError/SystemError）根因保留——新建
  `core/runtime/shared/env_limits.py` 判定 + `diagnostics.handle_environment_limit` 发射 `KDIAG_RUNTIME_ENV_LIMIT`
  诊断，VM 五处语义错误包装站点（Symbol not defined/VM: Call failed/模块导入/try-except）不再掩盖根因。
  深递归触底时用户看到 `RecursionError` 而非误导性符号未定义/调用失败（+2 测试）。
- **PT-DEBT-10**：`_drive_generator` 改显式生成器栈（trampoline，与 `_drive_loop_gen` 同构），线程体内深递归
  不再嵌套 Python 栈（depth=300 e2e 通过）。顺带根治线程体模块级函数解析（任务全局作用域链到模块作用域，
  此前线程体无法解析模块级函数，n≈2 即失败）、线程逻辑栈上限对齐主路径（`max_call_stack`）、
  `_vm_call_user_function`/`IbUserFunction.call`/`IbLLMFunction.call` push 后 finally 无条件 pop 的
  栈不均衡潜在 bug（`pushed` 标志）（+1 测试）。

## ✅ 已完成：2026-08-08 批次（穿透根治 + 文档对账治理 + 意图栈历史兼容移除）

- **kernel→runtime 穿透根治**（d11bad0）：用户红线"禁止一切 kernel→runtime 穿透"。全仓扫描确认两处
  （registry 惰性 import EventBus、host_interface 惰性 import kernel_diagnostic），改依赖注入——
  `registry.set_event_bus`（未注入 get fail-fast、peek fail-open）+ `HostInterface.set_diagnostic_emitter`
  （未注入回退 warnings.warn），engine 组装期注入。残留扫描 core/kernel/ 零 runtime import。
- **死代码清理**（ffaffc0）：删 `KernelRegistry.clone()`（零调用方，spawn 隔离走独立 engine 路径）。
- **文档-代码对账治理**（fe80595/5f5e26d/a8de1b1/3368c28）：5 个并行 general task 全量审查 →
  P0 断链/自相矛盾 4 处、P1 过期/红线/事实错误 ~20 处、P2 缺失/格式/体系 ~15 处全部修复。
  重点：arch/04、05 执行模型对齐调度器（TaskScheduler/Waitable/trampoline/await/auto-yield）、
  kernel-native 清单补 iruntime、意图系统穿透代码块、红线清理（日期戳/已落地/阶段5/搁置项）。
- **意图栈扁平化历史兼容彻底移除**（3ce9b7d）：用户裁定"无事实用户，历史兼容不是考虑项"。删序列化
  `intent_stack` 平铺双写 + 旧格式反序列化回退 + `context.intent_stack` property + 两处接口协议声明；
  补意图上下文 6 槽位 round-trip 测试（+3）。
- **登记 PT-FEAT-10/11/12**（8376195）：原被删愿景（UID 统一/序列化器自动化/AST UID 字段）中值得
  保留的未来任务。

---

## ✅ 已完成：P0 阶段 5 增量（`next()` 内建 + `yield from` 生成器委托）（2026-08-09）

> **unsafe-vibe-dev，全量 2083 passed / 1 skipped**（基线 2074）。设计记录 `tasks_docs/_code_yield_from.md`。

- **`next()` 内建**（c61a6e0）：`IbGenerator` 经 `generic_next()` 逐次推进，耗尽抛可捕获 `InterpreterError`；其它可迭代对象取首元素。
- **`yield from` 生成器委托**（本批次）：把子迭代对象（嵌套生成器 / 序列 / 有 `__iter__` 的对象）的每个产出
  **逐值透传**为当前生成器的产出（惰性：逐值推进、外层 `break` 提前终止时子迭代不再继续）；子生成器为
  `IbGenerator` 时表达式值 = 其 `return` 值。全管线：AST `IbYieldFromExpr` + 语法（`yield` 后 `match(FROM)`）+
  语义（仅函数体内，`SEM_YIELD_OUTSIDE_FUNCTION`）+ 类型（`resolve_iter_element` 补 `GENERATOR` kind）+
  VM handler（复用 `GeneratorYield`/`generic_next` 既有机制）+ e2e 8 项。
- **顺带根治预存缺陷**：`_drive_generator_loop` 的 `UserFunctionCall` 分支缺 `is_generator → make_generator_driver`
  （与 `_drive_loop_gen` 同构）——此前生成器体内调用生成器函数损坏（`yield from inner()` 依赖此修复）。
- **迭代解析收敛（单一权威源）**：`for` 的迭代解析（序列 / `IbGenerator`→`to_list` / `__iter__` / `to_list`）抽为
  `_shared._resolve_iterable`，`for` 与 `yield from` 共用——去双写，行为不变（全量零回归验证）。

## ✅ 已完成：PT-FEAT-5 错误用户友好化——诊断码目录（2026-08-09）

> **unsafe-vibe-dev，全量 2092 passed / 1 skipped**。PT-FEAT-5 四项中第一项（诊断码用户友好化）落地。

- **诊断码目录 `core/base/diagnostics/catalog.py`**（单点真理）：76 个诊断码（LEX/PAR/SEM/DEP/INT/RUN/KDIAG）→
  `CodeInfo(title, fix)`——一句话定位 + 修复指引。新增码必须登记（契约测试强制覆盖完备，无孤儿条目）。
- **Formatter 集成**：`DiagnosticFormatter` 渲染时按码附加"说明/修复"段；未登记码 fail-open（正文照常输出不阻断）。
- **参考文档 `docs/syntax/15_diagnostics.md`**：按 WRITING_GUIDE 诊断码模板（触发条件/严重级别/修复方式），
  与目录一一对应（数据驱动，无正文复制）；`SYNTAX_REFERENCE.md` 新增第四部分"诊断与错误"。
- **契约测试 `tests/contracts/test_diagnostic_catalog.py`**：CAT-1 每码有条目 / CAT-2 无孤儿 / CAT-3 条目规范 /
  CAT-4 已知码渲染说明 / CAT-5 未知码 fail-open。

## ✅ 已完成：PT-FEAT-5 诊断工具——符号表/类型绑定 JSON/dot 导出（2026-08-09）

> **unsafe-vibe-dev，全量 2103 passed / 1 skipped**。PT-FEAT-5 四项中第二项落地。

- **`core/compiler/diagnostics/exporter.py`**（只读导出，单一权威源）：`export_symbols_json`（作用域树递归，
  符号 name/kind/uid/type/provenance）+ `export_type_bindings_json`（节点类型+位置 → 类型名）+
  `export_dot`（作用域 cluster + 符号节点 + 作用域父子/类型绑定边）+ `export_artifact`（按格式统一导出）。
- **CLI 修复（两个预存死路径）**：`inspect` 命令原只有 handler 无 subparser 且引用未定义 `module_name`（死代码）；
  `semantic` 命令原只有 subparser 无 handler（静默无输出）。统一接入 exporter，支持 `--format json|dot` 与 `--output`。
- **契约测试 `tests/contracts/test_diagnostic_exporter.py`**：EXP-1 根符号字段 / EXP-2 类型绑定映射 /
  EXP-3 dot 结构 / EXP-4 JSON round-trip / EXP-5 空数据 fail-open / CLI-1 inspect+semantic 子进程 /
  CLI-2 bench 成功 + 编译错误退出 1。

## ✅ 已完成：PT-FEAT-5 编译时间基准（`bench` 命令）（2026-08-09）

> **unsafe-vibe-dev，全量 2107 passed / 1 skipped**。PT-FEAT-5 四项中第三项落地。

- **`main.py bench <file> --runs N --warmup M`**：warmup 后重复编译 N 次，报告 min/avg/max/stdev。
  编译失败按诊断码格式（catalog 说明）报错并以非零码退出（fail-fast）。
- **CLI 测试**：tests/contracts/test_diagnostic_exporter.py CLI-2（bench 成功输出统计 / 编译错误退出 1）。
- **剩余子项**（PT-FEAT-5 未完）：**CI/CD**——涉及远程 push，属禁 push 硬原则范围，须用户显式授权后另行执行。

## ✅ 已完成：PT-FEAT-10 UID 生成统一（2026-08-09）

> **unsafe-vibe-dev，全量 2121 passed / 1 skipped**。P1 第一项落地。

- **`core/base/uid.py` 单一权威源**：UID 生成收敛为九家族函数（`scope_uid`/`child_scope_uid`/`symbol_uid`/
  `intrinsic_uid`/`node_uid`/`type_uid`/`anon_symbol_uid`/`asset_uid`/`rt_scope_uid`），**零内联格式字符串**。
- **调用方全部接入**：symbols.py（scope/symbol）、serialization（node/type/anon/asset）、context.py（intrinsic）、
  scheduler.py（intrinsic）、runtime intrinsics/__init__.py（intrinsic）、interpreter.py（intrinsic）、
  runtime_serializer（rt_scope）。
- **格式逐字不变（round-trip 保真）**：收敛只集中格式、不改任何已产出 UID 值——序列化 round-trip 与
  `intrinsic:` 前缀比对（binding/symbol_resolution/engine）均不受影响。
- **契约测试 `tests/contracts/test_uid_generator.py`**：UID-1 格式逐字一致 / UID-2 确定性 / UID-3 区分性 /
  UID-4 rt_scope 每次唯一。

## ✅ 已完成：异步地基 M1/M2 收尾（.call 双写收敛 + 驱动去重）（2026-08-09）

> **独立分支 exp/async-m1m2 实验，全量 2137 passed / 1 skipped**。统一执行模型闭环全部收尾。
> 设计记录 `tasks_docs/_code_m1_call_dedup.md` / `_code_m2_drive_dedup.md`；落地状态 `_ASYNC_UNIFY.md`。

- **M2 驱动去重**（31884a8）：线程体 `coordinator._drive_generator` 从"手写阻塞泵"改为复用主 VM 单一权威驱动
  ——根生成器包装为 `VMTask`，经 `task_vm._drive_loop_gen` + `TaskScheduler` 驱动到完成；trampoline/GeneratorYield/
  Signal/None 规范化/协作取消统一由 `_drive_loop_gen`+`TaskScheduler` 承担，消双写；`TaskScheduler` park 期取消承接
  线程体 cancel 中断（初版手写泵对 recv `.result()` 死锁，self-grill+实测发现后改 TaskScheduler）。移除死参数 `send_first`。
- **M1 `.call` 双写收敛**（0bdecbb/4038102/3060950）：四个可调用对象 `.call()` 变薄宿主包装，委托 CPS 权威路径 +
  `_drive_generator`——IbFnCallable→`_vm_call_fn_callable`、IbUserFunction→`_vm_call_user_function`、
  IbLLMFunction→`_vm_invoke_llm_function`、IbBehavior→`_vm_invoke_behavior`；消模块/意图/作用域/闭包/self+super/
  实参绑定双写。返回值语义探针实测一致（void/none/ret）。清理 user_functions.py 8 个死 import；保留真原生
  `IbNativeFunction`/`IbBoundMethod`（无 CPS 孪生）与 `bind_behavior_*` helper。
- **独立复核（general agent）**：A/B/D 放行 + C 记录（IbUserFunction void 返回语义向主路径收敛，方向正确）。
- **回归测试 +9**（`tests/runtime/test_call_drive_convergence.py`）：宿主 .call void/return/self/fn_callable 返回语义
  + 线程体取消/深递归保持。修 coordinator 陈旧 docstring；生产代码注释任务代号清除。

## 📋 交接要点（下一 session）

- **✅ 已完成（2026-08-12）**：**enum 补全 + 嵌套包 import 根治 + 文档批次 + 用户试用**
  （unsafe-vibe-dev，全量 **2308 passed / 1 skipped**）。enum 补全（非 str 枚举 LLM 集成
  真实模型实证 / 迭代 / 数量 / KNOWN_LIMITS §二）+ 嵌套包 `import subpkg.util` INT_INTERNAL_ERROR
  根治（2层/3层/同包多导入合并）+ DOC-ISSUE-001~007 + BOUNDARY-001~005 + 运算符覆盖度核对。
  独立复核 PASS + 用户试用 `_LLM_TRIAL_ENUM_IMPORT_20260812/` 9 例全过（无新增缺陷）。
  详见上方"已完成"节与 `_code_enum_completion.md`。

- **✅ 已完成（2026-08-12）**：**阶段 3 合并执行**——`unsafe-vibe-dev` 全面合并取代 `main`（用户显式授权）。
  `git merge --no-ff`（merge commit `eb4a7d1`），main 树 == unsafe-vibe-dev 树，全量 **2308 passed / 1 skipped**
  验证通过；push main 到 origin。原 unsafe-vibe-dev 本地 + 远端已删除，从新 main 分支出新 unsafe-vibe-dev
  （== origin/unsafe-vibe-dev == eb4a7d1）供后续开发。

- **✅ 已完成（2026-08-12）**：**遗留独立窗口批次**——PT-DEBT-24 call_intent 死代码根治 +
  PT-AUDIT-3 S1-S5 处置（S4 根治 / S5 去重 / S1-S3 已知边界）+ 枚举实例化设计候选评估
  （`_enum_instancing_assessment.md`，维持现状）。独立复核 PASS，全量 2308/1 零回归。

- **✅ 已完成（2026-08-12，unsafe-vibe-dev 35bb2de，全量 2339 passed / 1 skipped）**：**用户类泛型参数（PT-FEAT-3）**——
  设计冻结 `tasks_docs/PT_FEAT3_DESIGN.md`（6 项开放问题决断）+ 全链路落地（AST/parser/语义/序列化/运行时/
  诊断/文档）。已支持多特化并存/字段·方法参数·返回类型特化/嵌套泛型/多参数/泛型继承；守卫含裸用拦截、
  实参数不匹配、字段-T 冲突、Enum 泛型拒绝、类型参数遮蔽内置拒绝。21 e2e + 2 序列化 round-trip；
  独立复核两轮 PASS（P2-1 父特化恒注册 / P2-2 嵌套实参映射 全整改）。

- **✅ 泛型压力/恶意试用完成（2026-08-12，`_GENERICS_TRIAL_20260812/`，30 次运行全经死循环保护）**：
  D1 核心语义（7）+ D2 正交交叉（泛型×运算符/继承/协议/容器/控制流/函数/并发/生成器/行为/闭包/多文件，
  11）+ D3 恶意挑刺（10，守卫类 PASS）。**发现并全部修复**（深度核验 + 两轮独立复核）：
  ① **G2（编译期）自引用字段 `Node[T]` 特化替换失效**（`from_spec` 扁平化既有行为暴露）——
  修复：TypeDef.type_args+base_name + from_spec 结构化；② **G1（运行期）方法体 `Box[T]`
  类型参数表达式失效**（运行期符号解析）——修复：type_param_uids 编译期收集 +
  方法帧 _bind_type_params 注册；③ **BOUNDARY-G1** 非法特化实参（`Box[42]`/`Box[None]`/
  `Box[void]`）编译期未拦——修复：语义层拦截；④ **双通道设计缺陷** descriptors 两套实现——
  修复：type_args 结构化单一权威源。全量 2339→2350，+11 e2e。详情 REGISTER.md 与 PENDING_TASKS。

- **✅ 已完成（2026-08-12，unsafe-vibe-dev a49555b，全量 2311 passed / 1 skipped）**：**F9 显式配置**——
  用户拍板命名 `ai.load_project_config` + 本轮实施。`setup()` 去自动加载段；新增
  `load_project_config()`（ec/project_root 缺失 fail-fast + 路径规范化 + 缺失 no-op + 幂等）；
  vtable 注册；测试（无调用不加载/显式调用加载/fail-fast/符号链接/幂等/语言级可达）；examples
  01/02/03 判断前加显式调用；文档同步（README/guide 01+02/syntax 11+15/config_loader/
  execution_context/catalog/codes）。独立复核 PASS（5 项整改全完成）。设计记录 `_code_ai_autoset.md`
  + 实施记录 `_code_f9_load_project_config.md`。

- **📌 独立窗口（与主线错峰）**：
  - PT-DEBT-4 `file` 重命名（破坏性）；PT-AUDIT-3 S1-S3 已知边界（跨线程 EC 状态共享 /
    dispatch hint 嵌套调度器 / 单写槽线程化，各需设计窗口）；枚举实例化设计冻结
    （`_enum_instancing_assessment.md`）；`import subpkg`（纯包目录）DEP_MODULE_NOT_FOUND
    （Python 同语义，低优先增强）；CI/CD 重新设计（P0，独立规划）；PT-FEAT-13 C4-C7 已落地、
    C8（容器类型改善）远期。

- **📌 已完成支线（2026-08-11 本 session）**：
  - **PT-AUDIT-3 双路径分裂专项审计已执行**（general agent 独立审计 + 主代理核验）：无 P0；
    3 确凿 P2 修复（run_batch 观测 / active_intents 漂移 / _drive 装箱一致）+ generator 兜底
    fail-fast + KNOWN_LIMITS §二十四 修正（commit df1a896）；5 疑似项记录待独立窗口
    （`_PT_AUDIT3_RECORD.md`）。
  - **PT-DEBT-24**（call_intent 死代码）：PT-AUDIT-3 复核确认，登记待独立窗口清理。
  - **F9**（import ai 配置副作用）：评估为**设计意图保持**（fail-fast 契约，测试显式处理）。

- **本 session 已完成批次（供回顾，见 git 历史）**：
  U1-U7 修复 → 意图注入纠错（7339220）→ P1-P4 决断 → T1-T5 泛化审计 → **合并收尾准备
  （doc-health P1/P2 + 版本 0.2.0 + examples 真实跑通 + dispatch 观测修复 + 合并就绪报告）→
  PT-AUDIT-3 → **真实 LLM 全面压力试用重启（2026-08-12）**。全量 **2210 passed / 1 skipped**（零回归）。

- **CI/CD 状态**：**GitHub 侧自动触发已停用（2026-08-11，`.github/workflows/ci.yml` → `workflow_dispatch`）**；
  待单独设计"可靠化/实用化"后重新启用，勿自动恢复。
- **分支政策**：经充分验证零风险/边界清晰改进可**直接合并** unsafe-vibe-dev；大风险仍"独立分支 + 手动 cherry-pick"；永远不触碰 main。
- **剩余长期项**：PT-DEBT-4 `file` 重命名（独立窗口）、P3 VISION、PT-DEBT-24、F9（已评估）、
  PT-AUDIT-3 疑似项 S1-S5（独立窗口）、**PT-DEBT-25~28（2026-08-12 试用发现，独立窗口）**。
- **当前主线（架构健康性优先，用户 2026-08-08 定案）**：**异步地基遗留妥协根治（统一执行模型闭环）——全部收尾（2026-08-09）**。
  审计确认内核层仍有"任务内同步重入调度器"遗留旁路（用户方法 `obj.method()` / `slot.update(fn)` / prompt hint /
  `chan.send` 满阻塞）。**PT-DEBT-12（F1 用户方法 CPS 化）、PT-DEBT-13（B1 chan.send Waitable 化）、
  PT-DEBT-14（F2 slot.update + F3 prompt hint CPS 化）、PT-DEBT-15（M4 LLM 真挂起）已完成（2026-08-08）**；
  **M1（.call 双写收敛）/ M2（驱动去重）已完成（2026-08-09，独立分支 exp/async-m1m2，全量 2137 passed / 1 skipped）**；
  M3（prompt 单源）已确认收敛。**统一执行模型闭环全部收尾**。实施计划与落地状态见 `tasks_docs/_ASYNC_UNIFY.md`（F1→B1→F2/F3→M1-M4）。
  登记 PT-DEBT-12/13/14/15。
  > **注意**：地基闭环后仍有 6 处"任务内同步重入/嵌套调度器"**次要路径遗留**（`_HEALTH_AUDIT_PLAN.md` 异步 A1-A6）——
  > 内联 `@~` 表达式、意图消解、`_SlotUpdateWaitable`、LLM 函数同步阻塞、类构造、协议方法。属"彻底统一"的未完项。
 - **优先级总表（用户 2026-08-08 认可，三维度判断）**：见 `PENDING_TASKS.md` §〇（单一权威源）。
   当前主线后：**P0 阶段 5 增量已完成（2026-08-09）→ PT-FEAT-5 三项已完成（CI/CD 待授权）→
   P1 PT-FEAT-10 已完成 → P2 R4/R5 审计已执行 → 异步地基 M1/M2 已完成（2026-08-09）**；
   剩余 PT-DEBT-4 `file` 重命名（破坏性变更独立窗口）、P3 VISION。
 - **低风险推进已完成（2026-08-09）**：PENDING_REVIEW_ITEMS 状态同步、PT-AUDIT-2 宽 except 核验（A 类保留）、
   docs/ 过时表述修复（yield 已落地）。见 HANDOFF §2.1。
 - **三轴健康盘点（2026-08-09，只读）**：见 `tasks_docs/_HEALTH_AUDIT_PLAN.md`——异步遗留 A1-A6 + 内核健康
   （深层嵌套/死同步包装/双驱动循环）+ 技术手册健康（P1/P2 待修 + How-to 缺口）。
 - **P0 阶段 5 增量已完成（2026-08-09）**：见上方"已完成"节。`next()` + `yield from` 全落地，设计记录
   `tasks_docs/_code_yield_from.md`。
 - **PT-FEAT-5 已完成三项（2026-08-09）**：见上方"已完成"节（诊断码目录 + 符号表/类型绑定导出 + 编译基准）。
   剩余：CI/CD（涉远程 push，须用户显式授权后另行执行；见 `PENDING_TASKS.md`）。
 - **P1 PT-FEAT-10 UID 生成统一已完成（2026-08-09）**：见上方"已完成"节。
 - **P2 审计 R4/R5 已执行（2026-08-09）**：R4 覆盖率核对（12 项，2 处 TRUE_GAP 补测）+ R5 聚焦治理
   （session 改动文档核验）。PT-FEAT-11/12、PT-FEAT-2 均评估为维持现状（见 `PENDING_TASKS.md`）。
- **阶段 5 yield 惰性生成器已完成（2026-08-08）**：见上方"已完成"节。`YIELD_GENERATOR_DESIGN.md`。
- **PT-FEAT-9 阶段 4 已完成（2026-08-07，unsafe-vibe-dev，全量 2021 passed / 1 skipped）**：
  kernel_diagnostic helper（单一记录双投影：警告不门控 + 事件受 observability 门控，rc best-effort）+
  12 处站点迁移（文案逐字）+ e2e 事件投影测试 + `docs/architecture/09_observability.md`。
  详见上方"已完成"节与 `WORKLOG`。
- **R 批次全部完成（2026-08-07，unsafe-vibe-dev，全量 2001 passed / 1 skipped）**：
  - R4+R3（82c9c0f，1988/1）：P3 公开协议（`IbCell.mark_shared_with_main()`）+ D-04 意图修复（`IbThread` 本体满足
    Waitable：`is_done` 改 property、auto-bind 支持 property-backed 方法、`try_result`/`result`、`join()` 返回自身、
    `await t` 可用、语言 `t.is_done()` 保留）+ 修复 auto-yield 缺口（类构造返回 Waitable 不自动挂起）+
    编译期 `await thread[T]`→`thread_result[T]`。
  - R6（35f1437，1995/1）：嵌套函数自动只读捕获（与 lambda 同构，`nonlocal` 仅用于写）；真闭包只读捕获可用；
    P3 写共享 cell 拦截保持。
  - R2（c16b05e/c4c63aa，1998/1）：调度器通知式唤醒（Waitable `register_wake` + `_wake_event` + CommBuffer 回调表 +
    engine `register_spawn_wake`）；根治 poll+park 与"单待决阻塞"。
  - R1（6dc9214，2001/1）：函数调用 trampoline 化（`_vm_call_user_function` CPS + `_UserFunctionCall` 压栈）；
    EXEC-1 根治，深递归 Python 深度恒定（n=5000 深度恒 13，原 ~130 层栈溢出）。
- **2026-08-08 批次已完成（unsafe-vibe-dev，全量 2026 passed / 1 skipped）**：
  穿透根治（d11bad0，事件总线/诊断发射器依赖注入）+ 死代码清理（ffaffc0，删 registry.clone()）+
  文档对账治理（fe80595/5f5e26d/a8de1b1/3368c28，P0/P1/P2 全修复）+ 意图栈历史兼容移除（3ce9b7d）+
  登记 PT-FEAT-10/11/12。详见上方"已完成：2026-08-08 批次"节。
- **阶段 1/3 已完成（2026-08-07，unsafe-vibe-dev）**：地基 1a-1e（调度器执行核心/Waitable 家族/阻塞即挂起/
  协作取消/llmexcept×await/取消覆盖用户函数）+ 统一清理 W1-W5/P3/P4（命名/订阅契约/comm 命名回归/死状态/
  文档/cell 隔离/全局事件总线），全量 **1984 passed / 1 skipped**。
- **已完成（OBSERVABILITY_REFACTOR 主体）**：2C-2 idbg 深度收敛 + 用户层机制改造、2D 测试体系全面重建
  （tests_v2 全域迁移 + 切换 + 矩阵三段式 + tests_docs 治理）、测试规范化清理（弱断言升级 + 短簇参数化），
  全量 **1963 passed / 1 skipped**。
- **本 session 已完成（2026-08-06，unsafe-vibe-dev，11 commits）**：Phase 0 设计冻结、Phase 1 契约修复+死码+零成本穿透替换、
  **2A CORE_DEBUG 整体移除**（88 trace → warnings 8 处/删除，commit 6878986）、**2B 观测骨架测试合作面**
  （EngineTestSnapshot + test_hooks + resolve_plugin_search_paths 公开 + layering 豁免归零，commit 73f373d/ae2209e/feff694）、
  **2C idbg 适配**（删死代码 + show_intents 单一权威源 + fields 协议化，commit 8a0065c）。全量 pytest **1633 passed / 4 skipped**。
- **已完成**：PT-DEBT-7（删 is_nullable 死字段）、PT-DEBT-8（值层分派收敛，重定义原折叠目标）、
  PT-DEBT-6（register_module 可观测性）、PT-DOC-2（定位段收尾）、DOC_AUDIT 文档治理（F0-F4）、
  PT-INTRO-1/PT-DECIDE-1/PT-DEBT-1/2/3、内建函数群完善+遮蔽——详见 `PENDING_TASKS.md` 与 git 历史。
- **待办池**：完整清单见 `PENDING_TASKS.md`。

---

## ✅ 已完成交付

> 全部落地 unsafe-vibe-dev（本地 commit，未 push）。commit 明细见 git 历史。

- **PT-DEBT-7/8 + PT-DEBT-6 + PT-DOC-2（2026-08-06）**：
  - PT-DEBT-7：删 `TypeDef.is_nullable` 死字段（可空性早已由 `Optional[T].wrapped_type` 承载，序列化不消费）。
  - PT-DEBT-8：系统层面重定义"折叠 IbXxx→IbValue"为伪目标（消 isinstance 动机已由 name 分派达成）→
    值层分派收敛审计：`is_sequence_value` 统一容器分派、`IbLLMCallResult.is_uncertain` 统一不确定判断；
    类角色分工固化 `03_type_system.md` §6.4。
  - PT-DEBT-6：`register_module` 用户插件覆盖 kernel-native 时发 warning（原静默忽略）；修正测试配置 bug。
  - PT-DOC-2：14 篇 syntax 定位段核实完成（DOC_AUDIT F3 已补齐），条目移除。
- **DOC_AUDIT 文档治理（2026-08-06）**：docs/ 全量治理（42 篇）分四阶段执行——F0 本批引入修复（KNOWN_LIMITS §二十二重复编号→§二十四、14_concurrency E9、E2 历史叙述）；F1 P0 断链/矛盾 ~17+ 处（以代码为最高真相）；F2 P1 红线批量（日期戳/历史叙述/冻结数字/任务代号清除、KNOWN_LIMITS 章节重排为一~二十二并同步跨文档引用、05_coroutine 任务日志迁 tasks_docs/THREAD_DESIGN.md、__prompt__ 待决项迁 tasks_docs/PROMPT_DESIGN_REVIEW.md）；F3 P2 改善（模板统一 13_mock_testing/04_control_flow、A5 去重、侧表/MetadataStore 事实修正、handler 数 43→45）；F4 体系（How-to 层 docs/howto/ 两篇、'深入指引'尾段 23 篇补齐）。**后续清理**：删除自治标注文档 appendix_type_system_rationale.md 与 backup/（未完成规划迁 PENDING_TASKS PT-FEAT-8/PT-DEBT-7/8，media 设计浓缩为 tasks_docs/MEDIA_DESIGN.md）。完整记录见 `tasks_docs/DOC_AUDIT_REPORT.md`。
- **整合巩固批次（2026-08-06）**：新写 `docs/syntax/14_concurrency.md`（并发语言面，此前缺失）+ KNOWN_LIMITS §二十二（signal 移除）；修复 PT-DEBT-1 文档漂移（`_ibci_registry_id` 残留）；修复 for 循环变量类型恒为 any 缺陷（复合赋值在 for 体内无法定型）；for...if + 复合赋值 e2e 覆盖（PT-TEST-2）。
- **内建函数群完善（2026-08-06）**：类型转换全局函数 `int()`/`str()`/`float()`/`bool()` +
  序列辅助 `enumerate`/`zip`/`sorted`/`reversed`/`sum`/`all`/`min`/`max`；级联修复 for 循环
  元组解包 `for (int x, int y) in`；内建函数名可被用户变量声明遮蔽（`int len = 5`），
  内建类型名与对内建的直接赋值仍禁。`any` 因与动态类型名冲突未纳入。
- **PT-DEBT-1/2/3 内核接口协议化（2026-08-06）**：
  - PT-DEBT-1：`BoundPlugin` 容器替代 `_ibci_registry_id` 私有标记注入；加载期跨引擎
    单例守卫改用 process 级 weak map（安全语义保留）。
  - PT-DEBT-2：`snapshot.py` 改走公开访问器；LLMExecutor 补 `pending_futures_count()`。
  - PT-DEBT-3：RuntimeContextImpl 补 `get_comm_*`/`peek_*`/`get_runtime_coordinator`
    访问器，统一替换 core 与 iruntime 插件的私有槽直接访问。
- **PT-DECIDE-1 裁定落地（2026-08-06）**：行为输出具体类型必须可解析——编译期
  `SEM_BEHAVIOR_OUTPUT_NOT_PARSEABLE` + 运行时 Default 兜底（见 `PENDING_TASKS.md` §二）。
- **PT-INTRO-1 运行时内省体系（2026-08-06）**：
  - `type(f)` 对 fn_callable/behavior 返回含签名类型名（`fn_callable[()->int]` /
    `behavior[(int,str)->bool]`）；其余值仍返回规范名。
  - `f.__return_type__()` 返回类型查询 API（receive 消息 + vtable 原生方法）。
  - 签名在运行时值创建时经 node_to_type 捕获、自持于值，序列化 round-trip 保真；
    lambda 参数节点类型绑定补全（编译期 bind_type）。

- **闭包序列化 + fn_callable round-trip 修复**：作用域 cell 重建 + 按 sym_uid 重链共享；
  value_meta/expected_type JSON 安全。
- **Axiom 家族分裂收敛**：IntentAxiom/IntentContextAxiom 并入 BaseAxiom。
- **EnumAxiom 双通道收敛**：str 契约 + fail-fast。
- **use_intent_context 守卫修复**：删恒真守卫 + 可读错误。
- **R3 异味四 Zone 处置**：修 19 + 复核定案保留 10 + 设计确认保留 6。
- **import-* 精确成员枚举根治**：编译器记录 + 运行时枚举；**IBC 文件跨模块导入三层断裂修复**
  （TypeDef 别名 NameError / Lazy 描述符 members 恒空 / IbModule.get_variable）。
- **`type()` 内建落地**：运行时内省第一项。
- **任务控制文档全面重整**：任务代号按性质分域（FEAT/DEBT/AUDIT/DOC/TEST/DECIDE/SEALED），
  删除已完成/无价值条目与无用设计决策，清理注释任务代号/历史说明。
- **周期清扫启动**：文档清洗与梳理、注释卫生清理、代码复核审查（R1/R2/R3）均已执行，
  周期复核。

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

## 当前测试基线

```bash
conda activate ibci
python -m pytest tests/
```

> 基线以实跑为准，不冻结数字。

---

## 独立并行任务

- **测试体系重构**：PT-TEST-1（`TEST_REFACTOR.md`），独立低优先级。
- **技术债审计**：PT-AUDIT-1/2（`CODE_SMELL_AUDIT.md` / `BRANCH_NESTING_AUDIT.md`），独立分支执行。
- **media Phase 4**：PT-SEALED-1，彻底封存（恢复需显式解封）。

---

## 工作规则

- 每次开新分支前，先复跑 `python -m pytest tests/`，把 pass/fail 计数写在 PR 描述里。
- 同一时刻只主推一个 P0 阶段。
- 工作模式定论优先；改动公理层或语义错误集的任务需全量 pytest 评估破坏面。
- 每阶段完成后用描述性 commit 记录，并把对应条目从本文件移除。
- 本文件不冻结具体测试通过数字。
- 重大架构决策记录在技术文档（`docs/ARCHITECTURE.md`、`docs/architecture/02_metadata_ast.md`、
  `docs/architecture/01_principles.md`），不再使用独立 ADR 文件。
