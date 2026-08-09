# NEXT_STEPS - 当前最紧要项

> 本文件**只**记录当前最紧要、可立即开工的下一步；长期规划见 `tasks_docs/PENDING_TASKS.md`（§〇 优先级总表）。
>
> **最后更新**：2026-08-08（阶段5 yield 落地 + 异步地基遗留妥协根治定为新主线；优先级总表归 PENDING_TASKS §〇）

---

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

**遗留技术债（不阻塞阶段 5）**：PT-DEBT-9（RecursionError 级联包装，建议随下次执行层重构承接）、
PT-DEBT-10（线程体递归非 trampoline）、PT-DEBT-11（`_UserFunctionCall` 定义位置）——见 `PENDING_TASKS.md` §五。

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
  EXP-3 dot 结构 / EXP-4 JSON round-trip / EXP-5 空数据 fail-open。
- **剩余子项**（PT-FEAT-5 未完）：编译时间基准、CI/CD。

## 📋 交接要点（下一 session）

- **当前主线（架构健康性优先，用户 2026-08-08 定案）**：**异步地基遗留妥协根治**（统一执行模型闭环）——
  审计确认内核层仍有"任务内同步重入调度器"遗留旁路（用户方法 `obj.method()` / `slot.update(fn)` / prompt hint /
  `chan.send` 满阻塞）。**PT-DEBT-12（F1 用户方法 CPS 化）、PT-DEBT-13（B1 chan.send Waitable 化）、
  PT-DEBT-14（F2 slot.update + F3 prompt hint CPS 化）、PT-DEBT-15（M4 LLM 真挂起）已完成（2026-08-08，全量 2071/1）；
  M3（prompt 单源）已确认收敛**。**剩余 PT-DEBT-15 中 M1（.call 双写收敛）/ M2（驱动去重）为大型收敛重构
  （中严重度，回归风险高）**。实施计划见 `tasks_docs/_ASYNC_UNIFY.md`（F1→B1→F2/F3→M1-M4）。
  登记 PT-DEBT-12/13/14/15。
- **优先级总表（用户 2026-08-08 认可，三维度判断）**：见 `PENDING_TASKS.md` §〇（单一权威源）。
  当前主线后：**P0 阶段 5 增量（`next()` 内建 + `yield from`）已完成（2026-08-09，全量 2083/1）** → **PT-FEAT-5**；
  P1 UID/序列化统一 + `file` 重命名；P2 审计 R4/R5 + Enum；P3 VISION。
- **P0 阶段 5 增量已完成（2026-08-09）**：见上方"已完成"节。`next()` + `yield from` 全落地，设计记录
  `tasks_docs/_code_yield_from.md`。
- **PT-FEAT-5 错误用户友好化已完成两项（2026-08-09）**：见上方"已完成"节（诊断码目录 + 符号表/类型绑定导出）。
  剩余子项：编译时间基准、CI/CD（见 `PENDING_TASKS.md`）。
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
