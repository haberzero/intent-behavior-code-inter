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
| **当前主线** | **PT-DEBT-12/13/14/15 异步地基遗留妥协根治**（`_ASYNC_UNIFY.md`） | 架构健康性 | 统一执行模型闭环——消"任务内同步重入调度器"遗留旁路。F1 用户方法 CPS 化 → B1 send Waitable → F2/F3 → M1-M4 |
| **P0** | 阶段 5 增量（`next()` 内建 + `yield from`） | 易用性 | 刚落地生成器，语言自然补全；复用既有驱动，改动小 |
| **P0** | PT-FEAT-5 错误用户友好化 | 易用性 | 实验性语言最直接的用户感知；语义管线已稳定，纯增益 |
| **P1** | PT-FEAT-10/11/12 UID/序列化统一 | 架构健康性 | 消"分散实现、机制正确"收敛债；独立分支谨慎回归 |
| **P1** | PT-DEBT-4 `file` 模块重命名 | 架构健康性 | 影子化 Python 内建，长期隐患；破坏性变更独立窗口 |
| **P2** | PT-AUDIT-1/2 + R4/R5 | 架构健康性 | 长期周期清扫，阶段边界启动 |
| **P2** | PT-FEAT-2 Enum 非 str 成员 | 易用性+长远 | 数字状态码枚举 round-trip 真实缺口，非紧急 |
| **P3** | PT-FEAT-8 `.ibc_meta` 快照 / PT-FEAT-3/4/7 / PT-FEAT-6 | 长远 VISION | 概念验证阶段 / 前置条件多 |
| **暂缓** | PT-DEBT-5 文件命名清理 | 架构健康性 | 破坏面大纯机械，独立窗口 |

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
| PT-FEAT-1 | 语言级协程完整形态：async 函数 / `yield` 生成器 | `await` 表达式已落地。**`yield` 惰性生成器已落地（2026-08-08，阶段 5，独立分支 exp/yield-generator → 手动应用 unsafe-vibe-dev，全量 2043/1）**：含 `yield` 函数自动为生成器（D-08 自标记，async 关键字已取消），单可恢复驱动 `_drive_generator_loop` + `GeneratorYield` 标记 + `IbGenerator` 值对象 + `generator[T]` 类型。设计 `YIELD_GENERATOR_DESIGN.md`。**增量**：`next()` 内建 / `yield from` / streaming |
| PT-FEAT-2 | Enum 非 str 成员 + 迭代能力 | 枚举成员值一律设为名字字符串 → 数字状态码枚举无法 round-trip（VISION） |
| PT-FEAT-3 | 用户类泛型类型参数 | VISION |
| PT-FEAT-4 | 用户类运算符重载 | VISION |
| PT-FEAT-5 | 语义错误用户友好化 + 诊断工具 + 性能基准 + CI/CD | 语义 4 阶段管线已稳定；错误码 `SEM_xxx` 转用户友好表述、符号表/类型绑定 JSON/dot 导出、编译时间基准 |
| PT-FEAT-6 | CompilationResult 字段精简 | 前置：PT-FEAT-5 完成 + 管线稳定 ≥ 1 月 |
| PT-FEAT-7 | 二层 IR 路线评估 | VISION |
| PT-FEAT-8 | `.ibc_meta` 静态元数据快照 | 原 `docs/architecture/01_principles.md` §7.3.7 规划（已移除，登记于此）：`ibcc` 构建命令 `--pre-scan-specs` 扫描 `_spec.py` 生成 `.ibc_meta` 快照，`export_metadata()`/`load_metadata_from_file()` 使编译器离线复用元数据，减少运行时发现开销。当前为全量 `discover_all() → HostInterface.metadata` 流程 |
| PT-FEAT-9 | 内核结构化诊断/可观测性机制（CORE_DEBUG 替代物） | **已完成（2026-08-07，unsafe-vibe-dev，全量 2021 passed / 1 skipped）**：`kernel_diagnostic` helper（单一记录双投影：警告不门控 + 事件受 observability 门控，rc best-effort）+ 12 处站点迁移（文案逐字）+ e2e 事件投影测试 + `docs/architecture/09_observability.md`。设计/决策见下方 §12（归档记录） |
| PT-FEAT-10 | UID 生成统一（符号/节点/类型） | **登记于文档清理（2026-08-08）**：原 `02_metadata_ast.md §九 优化1` 愿景内容。符号/节点/类型 UID 生成逻辑分散（`symbols.py` 作用域链式、`serialization.py` 内容哈希带 `node_` 前缀、类型 `type_{module}.{name}`），建议统一 `UIDGenerator` 单一入口。低优先级，机制正确但可收敛 |
| PT-FEAT-11 | 序列化器自动化（消除手动 `_collect_*` 调用） | **登记于文档清理（2026-08-08）**：原 `02_metadata_ast.md §九 优化3` 愿景内容。`FlatSerializer` 手动调用 `_collect_node`/`_collect_symbol`，建议按类型自动识别收集。低优先级，现有实现正确 |
| PT-FEAT-12 | AST 节点 UID 字段（编译期可见） | **登记于文档清理（2026-08-08）**：原 `02_metadata_ast.md §九 优化4` 愿景内容。UID 现仅序列化时生成，编译期不可见；建议 AST 节点加可选 `uid` 字段供编译期查询。低优先级，涉及 AST 结构变更（须查 `02_metadata_ast.md`） |

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
> **PT-DEBT-12/13/14/15**（异步地基遗留妥协）→ **新主线（2026-08-08 定案，见 `tasks_docs/_ASYNC_UNIFY.md`）**；
> **PT-DEBT-4/5**（破坏性/暂缓）→ 排后。

| # | 内容 | 说明 |
|---|------|------|
| PT-DEBT-12 | 用户方法调用任务内同步重入调度器（F1） | **异步地基遗留（2026-08-08 审计）**：`vm_handle_IbCall` 不展开 `IbBoundMethod` → `receive('__call__')` → `vm.run_body` 嵌套调度器。最常见 `obj.method(x)` 路径；方法含 Waitable 时死锁、深递归方法嵌套 Python 栈。改造：解包 `IbBoundMethod` → CPS trampoline（与函数调用同构）。见 `_ASYNC_UNIFY.md` F1 |
| PT-DEBT-13 | `chan.send` 有界满通道任务内真阻塞（B1） | **异步地基遗留（2026-08-08 审计）**：`send` 返回 None（满时 `_cond.wait` 阻塞线程），与 `recv`（已转 Waitable）不对称；唯一消费者同调度器时死锁。改造：send 满时返回 Waitable（宿主契约变更需评估）。见 `_ASYNC_UNIFY.md` B1 |
| PT-DEBT-14 | `slot.update(fn)` CAS 同步回调 / prompt hint 同步调用（F2/F3） | **异步地基遗留（2026-08-08 审计）**：CAS 锁外 `fn.call`（lambda 嵌套调度器、behavior 阻塞 LLM）；`_get_llmoutput_hint` CPS 路径内同步 `.call()`。改造：update 可调用分支返回 Waitable / hint vtable CPS 化。见 `_ASYNC_UNIFY.md` F2/F3 |
| PT-DEBT-15 | 同步 `.call()` 孪生 / 驱动循环 / LLM 调用双路径（M1-M4） | **异步地基遗留（2026-08-08 审计）**：各 CPS 路径保留同步 `.call()` 双写（M1）、`_drive_generator` vs `_drive_loop_gen` 重复（M2）、prompt 构建双实现（M3）、CPS 内 `_call_llm` 同步阻塞（M4）。改造：收敛单一 CPS 权威路径 + 薄宿主包装 + LLM 真挂起。见 `_ASYNC_UNIFY.md` M1-M4 |
| PT-DEBT-4 | `file` 模块重命名 | `file` 影子化 Python 内建，长期重命名（如 `fs`/`io`）。当前过渡措施已实施 |
| PT-DEBT-5 | 全项目文件命名清理 | 过短/欠层次/欠区分度/影子化内建的代码文件命名排查。暂缓，独立窗口执行 |
| PT-DEBT-6 | `register_module()` 可观测性缺口 | **已落地（2026-08-06）**：用户插件覆盖 kernel-native 时 `warnings.warn`（原静默忽略）。顺带修正测试配置 bug（plugin_paths 指向插件目录本身导致插件从未加载）。全量 pytest 零回归 |
| PT-DEBT-7 | 删除 `is_nullable` 字段，全面 `Optional[T]` | **已落地（2026-08-06）**：死字段清理（`is_assignable` 早已用 `Optional[T].wrapped_type`，序列化不消费）。全量 pytest 零回归 |
| PT-DEBT-8 | ~~折叠 `IbXxx` 为单一 `IbValue`~~ → **重定义为"值层分派收敛审计"** | **已落地（2026-08-06）**：系统层面定论——折叠是伪目标（消 isinstance 动机已由 name 分派达成；具体类=领域方法载体，折叠违反单一职责）。实际收敛：`is_sequence_value` 统一容器分派、`IbLLMCallResult.is_uncertain` 统一不确定判断；类角色分工固化于 `03_type_system.md` §6.4。全量 pytest 零回归 |
| PT-DEBT-9 | RecursionError 被 `VM: Call failed` 级联包装掩盖根因 | **R 批次 R1 排查发现（2026-08-07）**：深递归触底时，`leaf.py:315-317` 的 `except Exception` 把 RecursionError（`Exception` 子类）包装为 `VM: Call failed`，且每层调用递归包装一次 → 级联链掩盖真实根因（R1 期间 `f` not defined 的根因即 Python 栈溢出副作用被此掩盖）。关联诊断面（`kernel_diagnostic` 站点可承接异常分类；建议诊断事件区分"环境限制"如栈溢出 vs "语义错误"）。处置：随下次执行层重构或专项诊断改进一并评估 |
| PT-DEBT-10 | ~~线程体用户函数递归仍同步嵌套（`_drive_generator` 非 trampoline）~~ → **已根治** | **已落地（2026-08-08）**：`_drive_generator` 改显式生成器栈（trampoline，与 `_drive_loop_gen` 同构），UserFunctionCall 压栈而非递归驱动——线程体内深递归不再嵌套 Python 栈。顺带根治线程体模块级函数解析（任务全局作用域链到模块作用域，`ScopeImpl(parent=main_global_scope)`；此前线程体无法解析模块级函数，n≈2 即失败）与线程逻辑栈上限对齐主路径（`max_call_stack`）；修复 `_vm_call_user_function`/`IbUserFunction.call`/`IbLLMFunction.call` push 后 finally 无条件 pop 的栈不均衡潜在 bug（`pushed` 标志）。新增线程体深递归 e2e（depth=300）。全量 pytest 零回归 |
| PT-DEBT-11 | `_UserFunctionCall` 内部标记类定义位置（handler 依赖 VMExecutor 内部） | **R1 引入（2026-08-07）**：`_UserFunctionCall` 定义于 `vm_executor.py`，但 `leaf.py:293`（handler 层）与 `coordinator.py:316` 从 `vm_executor` import 它——handler 层向上依赖 VMExecutor 内部类，与"handler 是叶子、VMExecutor 调度"的分层方向略有违背。机制正确、功能无误，但按 design-philosophy"模块配合模式统一"应复核下沉（与 Waitable/Signal 同类放 `shared` 层）或改协议化标记。处置：随下次执行层重构一并评估 |

---

## 六、长期周期清扫（PT-AUDIT-*，持续周期工作，随主线阶段边界择机启动）

> 审查/审计/治理均为**周期性持续清扫**，非一次性完成——每轮主线改动后按需复核，
> 与"文档清洗与梳理 / 注释卫生清理"同性质。执行记录见 git 历史。

| # | 内容 | 说明 |
|---|------|--------------|
| PT-AUDIT-1 | 代码异味核对分析 | `CODE_SMELL_AUDIT.md`（单一事实来源），独立分支执行 |
| PT-AUDIT-2 | 条件分支与异常嵌套复杂度审计 | `BRANCH_NESTING_AUDIT.md`（AST 基线），独立分支执行 |
| PT-AUDIT-3 | 代码复核审查循环（R 系列） | R1 正式 review / R2 健康诊断 / R3 异味扫描 **已执行（2026-08-05）**；R4 覆盖率核对、R5 doc 审计待做。复核清单见 `PENDING_REVIEW_ITEMS.md` |
| PT-AUDIT-4 | 任务控制文档清洗与梳理（文档治理周期） | 删除已完成/无价值任务、无用设计决策、任务代号重整、交叉一致性核对。**已执行（2026-08-05）**，周期复核 |
| PT-AUDIT-5 | 注释卫生清理（周期） | 删除代码注释中的任务代号、历史实现方案、修复过程叙述，保留功能设计语义。**已执行（2026-08-05）**，周期复核 |

## 七、文档同步（PT-DOC-*）

### PT-DOC-1 docs/ 技术手册同步（D1-D5 已落地 2026-08-06）
| # | 内容 |
|---|------|
| D1-D5 | **已落地**：新写 `docs/syntax/14_concurrency.md`（chan/slot/subscriber/thread/thread_result + pubsub/send_nowait 语义 + signal 移除说明），KNOWN_LIMITS §二十二，SYNTAX_REFERENCE/README 接入。详见 WORKLOG |

### PT-DOC-2 语法手册定位段补充
**已完成（2026-08-06）**：14 篇 `docs/syntax/*.md` 均已有合格定位段（`> 本章描述...面向...覆盖...`），DOC_AUDIT F3 期间随"深入指引"补齐时一并落地。条目移除。

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
