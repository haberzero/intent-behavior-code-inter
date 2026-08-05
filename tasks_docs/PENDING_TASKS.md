# PENDING_TASKS - 阻塞 / 待前置任务的未来规划

> 本文档记录**暂时搁置但经过验证仍有有效性的规划**。
> 当前最紧要项见 `tasks_docs/NEXT_STEPS.md`。
>
> **最后更新**：2026-08-05（PT-ARCH-31/32/33/34 + PT-SMELL-R3 全部处置完成；当前最紧要见 NEXT_STEPS.md）

---

## 〇、IBCI 运行时多线程 + 通信机制（已全部完成，含通信领域设计完善）

> 用户裁定（2026-08-03）确立 PT-MT-1~8 主线（已全部完成 2026-08-03）。随后深度质询推翻 spawn/join/cancel/task 关键字语法，方向修正为 thread 对象 + 句柄方法模型——任务 A-F **已全部完成 2026-08-04**（见 `NEXT_STEPS.md`"已完成"节与 `WORKLOG.md` 关键裁定）。
>
> **通信领域设计完善**（审查记录已归档，决策见 WORKLOG 会话 6-12）**已全部完成**（B1/B2/B4 + G1/G2/G4 + G3/G5/G6/G7 + 收尾 L1-L8，见 `NEXT_STEPS.md`"已完成"节）。
>
> 本系列原规划已完成（历史记录保留）。

| 编号 | 标题 | 目标 | 状态 |
|------|------|------|------|
| PT-MT-1 | 详细设计文档 | 完整架构/AST 变更/接口/并发正确性/测试策略，先经用户审阅 | **已完成 2026-08-03**（经独立审查修正 6 处后落地；原详细设计文档已删除归档） |
| PT-MT-2 | 编译器地基 | 新 AST 节点（spawn/join/task/chan/signal/slot）+ parser + 4 阶段语义 + dispatch + 序列化（任务为运行时瞬态） | **已完成 2026-08-03**（AST/lexer/parser/语义/类型注册/序列化 + 18 测试；全量 1341 passed 零回归） |
| PT-MT-3 | 统一通信内核 | Channel（stream/message/pubsub）+ Signal（定向/广播）+ Slot（具名原子）三抽象，线程安全，语言层暴露 | **已完成 2026-08-03**（CommBuffer/ChannelCore/SignalCore/SlotCore/CommRegistry + IbChannel/IbSignal/IbSlot/IbTask + 6 dispatch handler；33+8 测试，全量 1382 passed 零回归） |
| PT-MT-4 | 内省层 | 快照式（`runtime.snapshot()`）+ 事件流（`runtime.subscribe()`）两者都提供 | **已完成 2026-08-03**（observability 包 + iruntime 模块 + 事件流；6 测试，全量 1388 passed 零回归） |
| PT-MT-5 | 控制层 | 统一启停接口 `runtime.configure(...)`（有开有关，部分默认开/关），粒度全局→单调用→单实例 | **已完成 2026-08-03**（ConfigStore 链式覆盖 + configure/get_config + parallel/observability 门控；5 测试，全量 1393 passed 零回归） |
| PT-MT-6 | 流式 + 并行 | 流式 provider 接口；Worker 增量→Channel→渲染线程；流式与并行都默认开启 | **已完成 2026-08-03**（AIPlugin.stream + IbStreamHandle + MOCK:STREAM + SSE 多块 + stream_call/stream_channel；8 测试，全量 1401 passed 零回归） |
| PT-MT-7 | 多 VM 实例 | 每并发路径一个轻量 VM 实例（完全隔离 + 全局只读数据），内核协调器管理生命周期 | **已完成 2026-08-03**（RuntimeCoordinator + SpawnedTask 后台线程 + 任务本地执行上下文；6 测试，全量 1407 passed 零回归） |
| PT-MT-8 | 用户代码多线程 | `task = spawn(fn)` 显式任务句柄（join/cancel），供实时 UI/输出刷新 | **已完成 2026-08-03**（eager spawn + 协作式取消挂起点 + 实时输出场景；8 测试，全量 1409 passed 零回归） |

**明确排除**：跨进程/CPU 并行；跨引擎通信（隔离运行是自我进化窗口，保持文件/序列化机制）。

---

## 一、Semantic Pipeline 后续演进

### PT-SEM-1　生产就绪化 [P2]

**前置条件**: Semantic 4-Phase pipeline 已稳定运行 ✅

**待做**：
1. 错误信息优化：`SEM_xxx` 错误码转化为用户友好表述（**Tier 3**：并行主线引入新错误类别——future 未 resolve/超时/资源生命周期，错误表达须覆盖）
2. 诊断工具：符号表/类型绑定/行为依赖图 JSON/dot 导出
3. 性能基准：编译时间基准测试
4. CI/CD 集成

### PT-SEM-2　CompilationResult 字段精简 [P3]

**前置条件**: PT-SEM-1 完成 + pipeline 稳定运行 ≥ 1 个月

### PT-SEM-3　二层 IR 路线评估 [VISION]

### PT-SEM-4　resolve_call_return 兜底双通道待深析 [P3]（Tier 4，独立于并行主线）【已完成 2026-08-03】

> 反射排查归并遗留：`_expression_visitors.py:304` 在统一入口 `resolve_call_return` 之外直读 `func_type.return_type` 作最后兜底（功能性双通道，非机械冗余）。待评估 `resolve_call_return` 是否应覆盖该路径或显式收敛。
>
> **已完成（2026-08-03）**：收敛为单一入口。`resolve_call_return` 新增 Layer 6——仅对**可调用** spec 且显式 `return_type`（非默认 void/any/auto）时直读解析，非可调用返回 None（与调用方 `call_trait` 前置检查一致）；`_expression_visitors` 移除末尾直读兜底，统一走 `resolve_call_return`，未解析回退 any。全量 pytest 1322 passed/4 skipped 零回归。

---

## 二、VM 异步/协程层（L3）【已升为主线，见 NEXT_STEPS.md】

> **状态变更（2026-08-02）**：用户裁定 **LLM 真正可用的并行化 + 同步异步** 为当前主线，本方向由 SHELVED 升为主线。原阻塞项（调度器多任务化、async/await 关键字、快照协议）成为主线组成部分；设计文档：`docs/subsystems/05_coroutine.md`。
> **原搁置原因**：原为优先完善多模态功能（2026-08-01 多模态已封存，2026-08-02 无限期搁置）；协程方向已重新评估并升为主线。

### 阻塞原因
1. 调度器架构需从单根任务升级为多任务挂起/恢复
2. `async`/`await`/`yield` 关键字不在 KEYWORDS 表
3. 快照协议需覆盖协程 yield 点

### 被阻塞的子项

| 编号 | 标题 | 依赖 L3 的原因 | 状态 |
|------|------|---------------|------|
| PT-3.1 | `host.run_isolated()` 返回值改进 | 需要协程句柄实现异步等待 | **已完成 2026-08-03** |
| PT-3.2 | `ReceiveMode` 枚举演进 | 需要 yield/resume 语义 | **已完成 2026-08-03** |

> **PT-3.1/PT-3.2 完成（2026-08-03）**：宿主异步统一接入 VM 协作式 `Waitable` 协议。`run_isolated`/`collect` 返回 `HostAwaitable`（Waitable，VM 透明 await → 多值 dict）；`spawn_isolated` 返回非 Waitable handle；`run_isolated` 从 `bool` 改 `dict`（破坏性变更）。`ReceiveMode` 定义为 `COLLECT`（实现）/`STREAM`（多模态封存，deferred）。`Waitable` 移至 `core/runtime/shared/waitable.py`，`box()` 透传，`vm_handle_IbCall` 对 native 返回的 Waitable 做 yield 挂起。详见 `docs/subsystems/05_coroutine.md §7.7`。

### 主线隐含新任务（2026-08-02 梳理定案，并行主线自身要求）

| 编号 | 标题 | 目标 |
|------|------|------|
| PT-SYNC-1 | 并发正确性验证方法 | Stage 1/2 需要并发测试基建（并发 dispatch 测试、共享状态只读不变式测试）——否则"真正可用"无法被证明【已完成 2026-08-02：新增 `tests/runtime/test_concurrent_dispatch_integrity.py`，经 mock_server 真实 HTTP 驱动并行 dispatch，验证 真正并发重叠/no-cross-talk/乱序确定性/批次隔离；全量 pytest 1284 passed/4 skipped 零回归】 |
| PT-SYNC-2 | `LLMFuture` 生命周期/错误语义 | resolve 超时/取消/重复 resolve 的用户可见语义——并行可用性的边界【部分完成 2026-08-02：新增 `tests/runtime/test_llm_result_future.py` 锁定 `LLMResult`/`LLMFuture` 语义（is_success/三工厂/get 四分支/blocking/is_done；10 用例，全量 pytest 1296 passed/4 skipped 零回归）。顺带移除 `LLMResult.unwrap()` 死代码（零消费者 + None 分支构造 `IbNone()` 缺参属潜在 bug）。超时/取消语义仍待定】 |
| PT-SYNC-3 | 线程池资源生命周期 | close() 语义、关闭后 dispatch_eager 的行为（当前会重建池，语义模糊）——资源管理明确化【已完成 2026-08-03：判为 IBCI 自身设计缺陷，按"可推翻"+fail-fast 原则重建。变化：close() 后置 `_closed=True`，`_get_thread_pool()` 在 `_closed` 时抛 RuntimeError，不再静默重建；`close()` 幂等。新增 `tests/runtime/test_scheduler_threadpool_lifecycle.py`（4 用例）。全量 pytest 零回归】 |

---

## 三、语言级能力扩展

### PT-4.1　Enum 非 str 成员 + 迭代能力 [VISION]

> `primitives.py` 把成员值一律设为名字字符串，数字状态码枚举无法 round-trip。

### PT-4.2　`__call__` 协议类型推断一致性 [VISION]（Tier 3，独立于并行主线）

> `__call__` 协议在 3 个文档有 3 种不同定性，框架应统一。**2026-08-02**：与并行主线为弱-中关联（async 未来中可调用对象可能 awaitable，边缘交集）；保持独立，不阻塞主线，async 落地时再评估 `await` 与可调用对象的交互。
>
> **文档定性统一（2026-08-03）**：3 文档统一为"`__call__` 是基础可用的可调用对象协议，闭包捕获/意图副作用等特定跨路径存在限制"。`KNOWN_LIMITS.md` §一 由"不建议使用"改为"基础调用可用，特定跨路径受限"（与 `06_oop.md` 中性协议表、`03_callable_fn.md` 可用特性一致）。`await` 与可调用对象交互待 async 函数落地时再评估。

### PT-4.3　语言级协程 [升为主线，见 NEXT_STEPS.md]

> 2026-08-02 随 §二 升为主线。**Stage 3 语言级 `await` 表达式已落地（2026-08-03）**：`await <expr>` 显式等待 Waitable（五层实现 + 4 e2e 测试，全量 pytest 1322 passed/4 skipped 零回归，见 `docs/subsystems/05_coroutine.md §7.8`）。**剩余**：async 函数/生成器（`yield` 使函数成为生成器）——语言级协程的完整形态，作为 `await` 之上的下一步。

### PT-4.4　用户类泛型类型参数 [VISION]

### PT-4.5　用户类运算符重载 [VISION]

### PT-INTRO-1　运行时内省与常用内置函数体系设计 [P2]【type() 已落地 2026-08-05 会话 17；其余待设计】

> **来源**：会话 16 类型强化收尾（2026-08-05，用户裁定）。用户确认编译期类型已静态传播
> （fn 返回类型等），运行时内省（`type()` / 查询 fn 输出类型等）与常用内置函数
> （`len()` 等）作为**独立设计任务**，不并入类型收紧。
>
> **现状（会话 17 更新）**：`type(x)` **已落地**（commit 待记）——返回 `ib_class.name` 规范
> 类型名（int/str/list/fn_callable/用户类名/None），编译期签名 `str type(any)`，测试
> `tests/runtime/test_introspection_intrinsics.py` 6 用例。`len()`/`range()`/`print()`/`input()`/
> `get_self_source()` 已存在；`str()`/`int()` 由 `(T)x` 强转语法覆盖（非函数形态）。
>
> **设计方向（需定，会话 17 自主决策后剩余）**：
> - `type(x)` 内建：✅ 已实现（值/容器/None/fn_callable/用户类返回规范类型名）。
>   **fn/behavior 返回含签名的类型名（`fn[()->T]` 形态）** 与专门的返回类型查询
>   （`f.__return_type__()`）**未做**——签名形态需 type_ref/params 内省，独立 API 形态待定。
> - `len()`/`str()`/`int()` 等常用内置的系统梳理与补齐：`len` 已存在（str/list/dict/elements/
>   receive 协议）；无单独 `str()`/`int()` 函数（语言面用 `(T)x` 强转，是既有设计）。
> - 参照 Rust（静态）/ TypeScript（`ReturnType<typeof f>` 类型层）/ Python（`get_type_hints`）
>   的取舍：`type()` 对齐 Python 运行时内省；fn 签名查询未定。
> - 对齐 idbg 内省哲学（调试/泛型分发场景）。
> **前置**：不依赖其他任务；建议在类型体系稳定后单独设计。

---

## 四、设计原则与明确排除方向

### 坚持的设计原则

1. **显式优于隐式**
2. **单点真理**
3. **公理调度 + 单次锁定**
4. **运行时可观测性优先**

### 明确排除

- **双写真相**：禁止同一事实在两处维护
- **完备约束求解类型推断**：原则上不实现 Hindley-Milner 级别的完备约束求解体系（设计过重）；但允许参考其设计思路（如占位符/待解析态/终局裁定）用于解决具体的类型解析时序问题
- **walrus (`:=`)**：IBCI 无此语法（设计限制）
- **if-block 内重声明同名变量**：SEM_002 禁止（设计限制）

---

## 五、测试与文档体系完善项

### PT-TEST-6　e2e 测试覆盖率提升 [P2]

> `for...if` 过滤语法零 e2e 测试；复合赋值运算符零 e2e 测试（仅有 AST 级 false-positive 测试）。

### PT-TEST-7　测试名与覆盖矩阵同步 [P3]

> `tests_docs/SEMANTIC_COVERAGE_MATRIX.md` 中的测试名与实际文件名不同步。

### PT-TEST-9　`ai.probe_model` 测试覆盖 [P2]（Tier 2，并行主线可靠性地基）【已完成 2026-08-02】

> `probe_model`（含 MOCK 路径与真实客户端路径）无任何测试。MOCK 路径返回 `MOCK_PROBE_SUCCESS` 并写入 `_model_capabilities`；真实路径含 reasoning 探测判定。**2026-08-02 目标细化**：reasoning 判定决定每个 LLM 调用（串行+并行）的 prompt 注入/提取策略，是行为正确性地基。测试须锁定：① probe 为 setup-time 显式动作（无懒探测竞争，已确认）；② `_model_capabilities` 在并行阶段只读消费（probe 后不可变）不变式；③ MOCK/推理判定/失败兜底三路径 + 消费方决策测试。
>
> **已完成**：新增 `tests/runtime/test_probe_model.py`（12 用例），锁定 ①②③ 三项不变式。验证：全量 pytest 1278 passed / 4 skipped（+12，零回归）。

### PT-HEALTH-3　LLMExecutor 共享状态健康审计 [P2]（已并入主线 Stage 1）

> 健康审计（2026-07-31，mock 子系统）发现的 executor 侧待诊断项。**2026-08-02**：executor 共享状态部分已并入并行主线 **Stage 1**（`_expected_type_stack` 死状态已删、`_result_parser` 懒重建竞争已修 fail-fast、`_current_call_info` 核验按构造无竞争）。**`scene` 协议参数已删除（2026-08-03）**：判为早期"provider 自有场景逻辑"设计的残留参数——当前场景化智能已收敛/上移至 executor `_prepare_behavior_call`（意图注入/输出约束/期望类型/reasoning 策略），provider 为薄传输层，`scene` 零消费者、零读取、可无痛重建（内部接口，消费方仅 `_call_llm` 一处）。
>
> **全仓健康诊断扫描（2026-08-02 已执行）**：按健康诊断十查 + code-odor 特征码扫描全部 `ibci_modules` 插件。分类结论：`ibci_isys`/`ibci_idbg` 的 `hasattr/getattr` 防御性内省属**合法**（可选项注入、调试内省工具、安全默认沙箱），非掩盖型兜底。
>
> **Stage 1 待核验项（2026-08-03 记录，来自已删除的 `_code_llm_core.md`）**：① `LLMResultParser.parse_result` 线程安全（strategy 链是否无实例突变）；② `_prompt.py`/`_llm_function.py` 实例级状态审计；③ 意图上下文并行隔离核验（fork 语义完整性）。需核验是否已完成，未完成则补。
>
> **Stage 1 三项核验完成（2026-08-03）**：① `LLMResultParser.parse_result` 线程安全——策略链（Axiom/VTable/Default）在 `parse` 期间无实例突变，`_auto_box_value` 只改新建实例，`registry`/`debugger` 只读；② `_prompt.py`/`_llm_function.py` 无实例级可变状态——所有方法仅构建局部状态，唯一实例写 `_current_call_info` 经 `_finalize_call` 在并行 dispatch 路径显式 `record_current=False`（仅主线程写）；③ 意图上下文并行隔离完整——`fork()` 返回值快照（新 smear/override 槽、浅拷贝 global 列表、不可变链表结构共享 intent_top），worker 线程仅读快照，`IntentResolver.resolve` 只读 intent 不突变共享对象。
>
> **`ai.__call__` 未 probe 回退决策（2026-08-03 裁定）**：原静默回退为推理模型。裁定：**保留行为 + 首次告警一次**（`_unprobed_warned` 去重），并在注释记录设计立场——本阶段 IBCI **不推荐使用 thinking 模型，推荐直接输出模式**；thinking 允许但非推荐；未来将专门设计"直接输出 vs thinking 后输出"的映射/分配策略（届时再细化）。此决策按"原则 > 行为维持"原则执行（见各级工作模式文档）。告警行为变化已由 `test_probe_model.py` 新增用例锁定。

### PT-DOC-1 语法手册定位段补充 [P3]

> `docs/syntax/*.md` 各章节文件缺少 `docs/README.md` §六.3 要求的定位段（1-3 句：本文是什么、给谁看、覆盖什么）。当前由 `SYNTAX_REFERENCE.md` 目录结构承担定位职责，未来应为每篇补充独立定位段以支持独立阅读。

### PT-DOC-2 多模态子系统设计文档恢复 [P3]

> 全模态行为表达式设计文档已移至 `docs/backup/02_multimodal_behavior.md`。多模态已封存（2026-08-01），解封恢复时需按 `docs/README.md` §六准则重新审视并纳入 `docs/subsystems/`。

---

## 六、通用技术债 与 media Phase 4（已封存）

### PT-ARCH-22：全项目文件命名清理 [暂缓]

> 全面排查过短/欠层次/欠区分度/影子化内建的代码文件命名。排期：暂缓，独立窗口执行。

### PT-SMELL-1：代码异味核对分析（独立分支）[P2]

> 对话/代码分析中反复出现的"兜底、双轨、双通道、双形态、三策略"等表述暗示潜在代码异味，属技术债。完整分类清单 + 代码位置 + 核验流程见 **`tasks_docs/CODE_SMELL_AUDIT.md`**（单一事实来源）。独立分支执行，不与主线混置。

### PT-SMELL-2：条件分支与异常嵌套复杂度审计（独立分支）[P2]

> 异常过多的 if-else 并用、过深 if-else、过多过深 except 嵌套（含我的工程经验补充：守卫子句缺失、长 elif 链查表化、宽 except 误吞语言级异常、异常当控制流等）。AST 度量基线（深度/elif 链/70 处宽 except/5 处嵌套 try）+ 位置清单见 **`tasks_docs/BRANCH_NESTING_AUDIT.md`**。独立分支执行。

### PT-SMELL-3：局部 import 审计（独立分支）【已完成 2026-08-03】

> 无意义的局部 import、为打破循环导入的内联 import。全仓 35 处局部 import 分类清单（原审计文档 `LOCAL_IMPORT_AUDIT.md` 已删除，结论归档于此）。
>
> **完成**：可提升类（L12/13/14/16/19/20）已提升至模块顶部；L15/L17 核验保留；循环打破类（L1-L10 等）核验为**标准运行时局部 import 环打破（非胶水）**，但按其 tradeoff 性质**极其谨慎地记录为未来推迟工作**，待架构重构时逐项复核。已并入 unsafe-vibe-dev。

##### 推迟工作记录 — 循环打破局部 import tradeoff（待架构重构时复核）

> 原则：理想上应永远避免循环依赖。但允许少量"设计合理、能显著减少工作量"的局部 import 作为**谨慎 tradeoff**。以下为保留的循环打破局部 import，列为**未来推迟工作**，待架构重构（依赖方向下沉 / 接口上移）时逐项复核。

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

> 复核触发：任一处所在模块发生架构重构、或引入新的循环依赖、或出现相关技术债时，返回本表逐项复核该 tradeoff 是否仍成立。

### PT-ARCH-23 G2 遗留：内核原生模块覆盖可观测性缺口 [待决策]

> `HostInterface.register_module()` 静默忽略与 kernel-native 同名的用户插件，无 warning。功能正确，可观测性不足。待诊断体系稳定后专项处理。

### PT-ARCH-29：命名历史包袱清理 [P1]

> 代码层已零残留（完成）；剩余：历史设计文档/工作日志中的旧 API 引用加"历史文档"标注（低优先级，随文档治理顺带处理）。

### PT-ARCH-30：`file` 模块命名风险 [P1]

> `file` 影子化 Python 内建。长期需重命名（如 `fs`/`filesys`/`io`）。当前过渡措施已实施。

### PT-ARCH-31：behavior / fn_callable 闭包序列化 + fn_callable round-trip 损坏 [P1]【已完成 2026-08-05 会话 17】

> **来源**：R3 复核（2026-08-05）确认为明确设计缺陷（用户裁定记录）。2026-08-05 会话尾
> 深入取证，**用户裁定档位 A + B 都必须完成**。
>
> **已完成**：档位 A+B 全部落地（commit 662b83c）。序列化端补 closure/is_cell（cell 值优先）、
> fn_callable 补 closure/params_uids/body_uid、可调用实例不再冗余写 value_meta、expected_type
> 按 Optional[str] 契约落盘；反序列化端新增 fn_callable 分支、closure 重建（cell 先自包含可调用 +
> 待重链）、is_cell 符号 promote_to_cell 重建、post-pass 按 sym_uid 重链共享 cell（修复外层重赋值
> 不可见 + 多闭包共享分叉）。测试 tests/runtime/test_closure_serialization.py 12 用例。
> 原始缺陷记录保留如下。
>
> **缺陷（三处，均已实证）**：
> 1. **`fn_callable` round-trip 完全损坏**：反序列化器**无 `fn_callable` 分支**，落入通用
>    `else` 变成空 `IbObject`（node/closure/params_uids/body_uid 全丢，恢复后调用失败）。
> 2. **closure 丢失**：`behavior` 缺 closure；`fn_callable` 缺 closure/params_uids/body_uid
>    （body_uid 丢失致恢复后调用错节点）。
> 3. **作用域 cell 结构未序列化**：`_serialize_symbol` 只存 name/value/is_const/declared_type，
>    `sym.cell`/`_cell_map` 不存，闭包 cell 无法重建。
>
> **修复（档位 A + B，都做）**：
> - **档位 A（务实主体）**：
>   - 序列化：behavior 加 closure（snapshot 存深克隆种子值 / lambda 存 cell 当前值）；
>     fn_callable 加 closure/params_uids/body_uid；作用域符号加 `is_cell` 标记。
>   - 反序列化：**新增 fn_callable 分支**；behavior/fn_callable 重建 closure
>     （snapshot 值直接重建 / lambda 重建独立 IbCell）。
> - **档位 B（完整重链，修复 A 的两个退化：恢复后外层重赋值闭包不可见 + 多闭包共享
>   同一 cell 各自分叉）**：
>   - 作用域反序列化重建 cell（is_cell 符号经 `promote_to_cell` 语义重建），closure
>     反序列化后 **post-pass 按 sym_uid 扫描恢复的作用域树重链 cell**（保持共享引用
>     不变量：外层赋值对闭包可见、多闭包共享同步）。
> - **测试**：round-trip（snapshot 保真 / lambda 值拷贝 / 档位 B 双闭包共享同步 /
>   外层重赋值可见 / 调用结果一致）。save_state 测试现有 asset/mock 聚焦，需补 callable 往返。
>
> **设计确认**：behavior/fn_callable 的 `_execution_context` 丢失无碍（恢复后调用走
> call-site ContextVar，`get_current_execution_context() or self._execution_context`）。
> 全局变量不进闭包（`promote_to_cell` 对全局返回 None），闭包只捕获函数局部 cell。

### PT-ARCH-32：Axiom 家族分裂——IntentAxiom / IntentContextAxiom 未并入 BaseAxiom [P2]【已完成 2026-08-05 会话 17】

> **来源**：R3 code-odor 扫描（2026-08-05）确认为碎片化，主会话建议修但未落地；用户裁定
> 记录为未修缺陷待下一 session 处理。
> **缺陷**：`core/kernel/axioms/primitives/base.py:BaseAxiom` 是全部基础类型公理的统一基类；
> 但 `intent.py:IntentAxiom` 与 `intent_context.py:IntentContextAxiom` **不继承 BaseAxiom**，
> 手抄全部 9 个 capability flag（False）与十几个 no-op 默认方法（`resolve_return_type_name`/
> `get_element_type_name`/`from_prompt`/`get_diff_hint` 等），连 `_m` 辅助函数也复制一份。
> 公理体系存在**两条基线**，有漂移风险（曾致 `_members.py:85` 用 hasattr 探测迁就分裂，
> 该 hasattr 已删，但分裂本体仍在）。
> **已完成（commit 759956b）**：两公理改继承 `BaseAxiom`，仅保留差异覆盖（name 属性/is_class()/
> get_method_specs），删除手抄 no-op 与重复 `_m`。行为等价：全量 pytest 零回归。

### PT-ARCH-33：EnumAxiom.from_prompt 双通道 + 静默吞错 [P2]【已完成 2026-08-05 会话 17】

> **来源**：R3 code-odor 扫描 Zone A 疑似真缺陷 #3（2026-08-05），主会话核验确认为未修缺陷，
> 用户裁定记录待办。
> **位置**：`core/kernel/axioms/primitives/enum.py:104-114`（`EnumAxiom.from_prompt`）。
> **缺陷**：
> 1. **双通道探测**：`hasattr(raw_response, "to_native")` / `hasattr(raw_response, "receive")`
>    两套入口并存——正是 `base.py:279 unbox()` 声明要收敛的
>    `x.to_native() if hasattr(x, 'to_native') else x` 双轨写法在 kernel 层的残留散落点。
> 2. **静默吞错**：`except Exception: val = raw_response` 把 `receive('__to_prompt__', [])`
>    内的任何异常（含协议分派真实 bug）吞掉，静默用原值兜底。
> **已完成（commit d82b989）**：删除双轨探测 + 宽 except；按协议契约（protocols.py + 全部
> 调用点均传 str）以 str 入参，非 str 输入 fail-fast 抛 TypeError。测试
> tests/kernel/test_enum_axiom.py 8 用例。

### PT-ARCH-34：RuntimeContext.use_intent_context 恒真守卫 + 静默 False [P2]【已完成 2026-08-05 会话 17】

> **来源**：R3 code-odor 扫描 Zone B 疑似真缺陷 #6（2026-08-05），主会话核验确认为未修缺陷，
> 用户裁定记录待办。
> **位置**：`core/runtime/interpreter/runtime_context.py:692-697`（`use_intent_context`）。
> **缺陷**：
> 1. **三层恒真 hasattr 守卫**：`hasattr(intent_ctx_obj, "fields")`（IbObject 恒有）、
>    `hasattr(self._intent_ctx, "get_global_intents")`（IbIntentContext 恒有）、
>    `hasattr(other_ctx, "fork")`（恒有）——对协议保证成员做能力探测，守卫恒真无分支价值。
> 2. **静默 fail**：用户误传非 intent_context 对象时静默 `return False` 无任何诊断（语言面
>    `intent_context.use(ctx)` 的错误输入被无声吞掉）。
> **已完成（commit 661d02c）**：删除恒真守卫；非 intent_context 入参 fail-fast 抛
> InterpreterError（可读诊断）；返回类型对齐接口声明（-> None）。注意：这是用户可见语言 API
> （`intent_context.use`），return False → 抛错属行为变更，已与调用方/测试核对。
> 测试 test_e2e_intent.py +2。

### PT-SMELL-R3：R3 code-odor 需讨论项全量待办（2026-08-05 用户裁定全部记录）

> R3 四 Zone 扫描的"需讨论"项中，除已修（批次 A-D + 后续）与设计确认保留（media 封存 /
> llm_except best-effort 协议兜底 / ibci_ai 宽 except 已修 / permissive any 已由类型强化处理 /
> closure 序列化见 PT-ARCH-31）外，以下全部记录为待办。每项标注建议处置（修 / 复核定案 /
> 设计确认），下一 session 按序处理。
>
> **✅ 全部处置完成（2026-08-05 会话 17，详见 WORKLOG）**。处置分布：
> **修 19 项**（A-D1/2/5/7/9/10，B-D1/4/5/7/8/12，C-D1/2/4/6/9，D-D1/2/3/6/7 — 其中
> D-D4 消费者清理并入，D-D5 node_pool 直访并入）；**复核定案保留 10 项**（A-D3/4/8，
> B-D2/6/9/10/11，C-D3/8/10，D-D4 双接口）；**设计确认保留 6 项**（A-D6 media 封存、
> B-D3 side-car、C-D5 deep_clone 精确判别、C-D7 snapshot 待协议化、D-D5 comm 槽文档化契约）。
> 全部修复经全量 pytest 零回归。以下各表保留为原始记录（处置列已更新为实际结果）。
>
> **Zone A（compiler + kernel）** ✅

| # | 位置 | 特征 | 处置结果 |
|---|------|------|---------|
| A-D1 | `core/compiler/lexer/core_scanner.py` | try_scan 全量 except 回滚；NORMAL 模式 `$` 路径忽略返回值 | **修**：失败路径消费 `$` 对齐 IN_INTENT（防御纵深，当前不可达） |
| A-D2 | `core/compiler/scheduler.py:145-148` | 记录 DEP_GRAPH_ERROR 后 `raise e` 抛非 CompilerError（双通道，诊断孤儿） | **修**：统一抛 CompilerError |
| A-D3 | `binding_analysis_pass.py:537/545-546` | owned_scope 缺失返回 False（fail-open，编译期尽力 + 运行时守卫兜底） | **复核定案保留**（运行时 file_impl 守卫有测试背书，fail-open 不可达） |
| A-D4 | `binding_analysis_pass.py:898-907` | lambda 捕获双通道（注释与兜底条件矛盾，实际只覆盖函数体未出现的名） | **复核定案保留** + 注释修正（nonlocal 非 lambda；兜底条件与注释不符已修正） |
| A-D5 | `expression.py` chan/slot | 类型注解多形状链式探测 + `str()` 兜底（无意义类型名/点分截断/关键字 mode 坏死） | **修**：`_expr_name` shape 归一 + 修复关键字参数路径（previous() 只读不移动光标致坏死） |
| A-D6 | `media.py:46-47` | 能力探测 + 占位兜底 | **media 封存，零改动** |
| A-D7 | `parser/core/component.py:24-44` | `_loc` hasattr 双形状探测（elif 死分支） | **修**：直访统一属性（Token/IbASTNode 均实现） |
| A-D8 | `symbol_collection_pass.py:117-146` | `except ValueError` 捕获重定义转诊断（库错误契约转换，非异常控制流） | **复核定案保留** |
| A-D9 | `kernel/registry.py:298-299` | `hasattr(ib_class, 'registry')` 恒真守卫 | **修**：直访（IbClass.registry 槽恒在） |
| A-D10 | `compiler/dependencies.py:97-103` | `except ValueError` 伪环死兜底（DFS 不变量下不可达） | **修**：删除 |

> **Zone B（interpreter + vm）** ✅

| # | 位置 | 特征 | 处置结果 |
|---|------|------|---------|
| B-D1 | `llm_executor/_prompt.py:34-52` | 能力探测 + 宽 except 吞用户 `__to_prompt__`/`to_native` 真实 bug | **修**：except 收窄 AttributeError（仅协议缺失回退，用户 bug fail-fast） |
| B-D2 | `llm_parsing_strategy.py:285-303` | DefaultParsingStrategy 把不可解析输出静默 box 为成功字符串 | **复核定案保留**：auto 无类型→box 成功合理；"已声明类型无 parser→uncertain"属语言级语义决策待用户拍板（改动会回归现有测试） |
| B-D3 | `coordinator.py:54-58` | `getattr(rc, "_runtime_coordinator")` side-car 挂载 | **设计确认保留**（同模块权威访问器；可观测性层走公开 property 属可选增强） |
| B-D4 | `coordinator.py:253-255` | "兜底：原生函数/其它可调用" + hasattr 探测 | **修**：isinstance(IbFunction) 明确判别 |
| B-D5 | `engine.py:772-781` | request_collect 宽 except 跳过 | **修**：isinstance(IbObject) 前置判占位符，try 缩至 to_native() |
| B-D6 | `module_manager.py:132-145` | `dir(package)` 枚举 | **复核定案保留**：uid_map 含当前模块全部符号（int/str 内建），dir∩uid_map 交集才是正确白名单；尝试改 uid_map 迭代引入回归已回退 |
| B-D7 | `module_manager.py:184-187` | 宽 except 把内部异常包装成 "Module not found"（误译） | **修**：删除宽 except 包装，内部错误直传 |
| B-D8 | `vm/handlers/_shared.py:748-762` | tuple 解包宽 except 折叠真实异常 | **修**：照搬 for 循环结构化 lookup_method("to_list") 预检 |
| B-D9 | `interpreter/intrinsics/io.py:24-31` | reconfigure 宽 except pass + GBK 转义兜底（Windows 编码） | **复核定案保留**（编码感知替换转义，UX 取舍，测试经 callback 旁路） |
| B-D10 | `vm/handlers/comm.py:45-58` | `rc._comm_config_store`/`_comm_event_bus` 私有直取 + 宽 except | **复核定案保留**：runtime_context.py 注释明文的内部注入契约（comm/iruntime 三方共用），协议化列入长期项 |
| B-D11 | `interpreter.py:604-613` | 用户类预评估宽 except 留待 instantiate 重试 | **复核定案保留**（预评估优化 + instantiate 权威 fail-fast，issue_tracker 恢复；instantiate 无 context 静默 None 边缘已记录） |
| B-D12 | `llm_executor/_prompt.py:245-256` | axiom→vtable 双轨 + except 吞用户 `__outputhint_prompt__` bug | **修**：lookup_method 已预检，删 try/except，用户 bug fail-fast |

> **Zone C（objects / shared / base / loader）** ✅

| # | 位置 | 特征 | 处置结果 |
|---|------|------|---------|
| C-D1 | `objects/kernel/base.py:46-59` | `__call__` 双路径（vtable lookup 死分支 + hasattr 兜底） | **修**：删死 vtable 'call' 分支（全库无注册点）+ isinstance(IbFunction) |
| C-D2 | `objects/kernel/native_module.py:78-82` | 白名单 getter 内部 AttributeError 被双层吞成成员缺失 | **修**：getter 异常重抛 InterpreterError（区分真实错误与成员缺失） |
| C-D3 | `native_module.py:41` + `loader.py:71` | `_ibci_registry_id` 跨对象私有标记注入 | **复核定案保留**（fail-closed 自洽；低优先协议化 BoundPlugin 容器，列入长期项） |
| C-D4 | `objects/kernel/_helpers.py:19/28-44` | Compatibility fallback：side-table miss 后节点形态嗅探 | **修**：删 wrapper 嗅探（形参恒为 IbArg，side-table 单一判别源） |
| C-D5 | `objects/deep_clone.py:109` | `type(val) is KernelIbObject` 精确判别 | **设计确认保留**（精确判别有意，专用子类不可克隆属契约） |
| C-D6 | `objects/kernel/ib_class.py:182` | `hasattr(val_info, 'static_val')` | **修**：isinstance(IbClassField)（同文件其它处一致） |
| C-D7 | `observability/snapshot.py:24-104` | 跨对象私有穿透 + 宽 except（可观测性层） | **设计确认保留**（best-effort 快照契约有测试，待接口协议化列入长期项） |
| C-D8 | `modules/file_impl.py:44-54` | 运行时兜底注释（编译期漏检防御纵深） | **复核定案保留**（有专项测试背书动态分派兜底） |
| C-D9 | `module_system/discovery.py:121-122` + `artifact_loader.py:91-96` | 静默 except 吞错 | **修**：discovery 删 except ImportError（Fatal Error 暴露）；artifact_loader 先查 get_class 再创建（已存在有意跳过，真实错误上抛） |
| C-D10 | `runtime_serializer.py` + `callables.py:295` | 池布局歧义回退 native + hasattr 探测 | **复核定案保留**（前缀守卫 + 有注释的鸭子类型，先例 deep_clone.py:87；单独立池属中重构不推进） |

> **Zone D（ibci_modules + sdk）** ✅

| # | 位置 | 特征 | 处置结果 |
|---|------|------|---------|
| D-D1 | `ibci_ai/core.py` | reasoning/reasoning_content 双字段探测两处重复（DRY） | **修**：抽象单一 `_extract_reasoning` helper |
| D-D2 | `ibci_isys/core.py:38-83` | PluginCapabilities 恒真守卫 + 静默降级 | **修**：契约直访 fail-fast；is_sandboxed 保留无 pm 默认沙箱开；request_external_access 不可用即 raise |
| D-D3 | `ibci_iruntime/core.py:39-180` | ec 公开 property 死守卫 + snapshot 无 executor 静默 {} | **修**：直访 + 无 EC/executor 统一 raise；get_config 无 EC 保留默认值语义 |
| D-D4 | `ibci_idbg/core.py:361-364` | IStackInspector(List[str]) vs IStateReader(List[IbIntent]) 接口形状不一致 | **复核定案保留双接口**（轻量视图 vs 富对象视图是刻意设计，统一不可行）；消费者 hasattr 死守卫/逐元素探测删除、except 收窄 |
| D-D5 | `ibci_iruntime:148-171` + `ibci_idbg:273-309` | 跨对象私有槽访问 | **设计确认保留**（comm 槽为 runtime_context 注释明文内部契约；node_pool 为公开只读 property）——node_pool 改直访 |
| D-D6 | `ibci_ai/core.py:304` | `getattr(behavior, "_execution_context")` 私有穿透 | **修**：仅 `get_current_execution_context()` + fail-fast（CPS 主路径恒有调用现场 EC） |
| D-D7 | `ibci_ai/core.py:90-91/160-161` | `"/v1"` 字符串嗅探启发式自动补 URL 后缀 | **修**：删除嗅探（base_url 是显式契约）；5 个测试文件显式补 `/v1` |

> 处置原则：每项按"修 / 复核定案 / 设计确认"三档处理；"复核定案"项先证据化判定再决定
> 修或文档化；`media 封存 / deep_clone / snapshot 协议化 / file_impl 防御` 等已确认设计项
> 仍列为待办（复核时确认无需动即关闭）。
>
> **全部处置完成（2026-08-05 会话 17）**：修 19 项 + 复核定案保留 10 项 + 设计确认保留 6 项，
> 全部修复经全量 pytest 零回归（各批 commit 见 git 历史）。长期项（C-D3 协议化 / C-D7 /
> B-D10 / B-D2 语义决策）已记录，不阻塞主线。


### Phase 4 延迟项（已封存，从 ADR-008/010/013 提取）

以下三项在 media Phase 4 开工时需实现（**封存期间不推进**）：

**PT-PHASE4-1：多模态模型注册字段**

`ai.register_model(name, url, key, model, **kwargs)` 当前仅存储 `timeout`，需扩展存储 `modalities`/`endpoint`/`audio_config` 字段，并更新 vtable 声明。运行时前置（`**kwargs` 收集 + 原生分传）已就绪（2026-08-01），解封时只需声明 vtable VAR_KEYWORD。

**PT-PHASE4-2：非聊天端点推理绕过**

当前所有未探测的命名模型默认 `is_reasoning_model = True`，导致非聊天端点（Whisper/DALL-E）被注入 reasoning prompt。需实现 endpoint-based 检测：命名模型配置了 `endpoint` 字段时，强制 `is_reasoning_model = False`，跳过 reasoning prompt 注入。

**PT-PHASE4-3：磁盘型响应解析协议**

当前 LLM 响应解析使用 `__from_prompt__` 协议（内存型）。磁盘型类型需要平行的 `from_response` 协议：
- 新增 `has_multimodal_response_cap` flag + `from_response` 方法到 BaseAxiom
- 新增 `get_from_response_cap` accessor 到 SpecRegistry
- 新增 bypass register（`set_last_raw_response`/`get_last_raw_response`）到 runtime_context
- `_call_llm` 存储完整响应对象到 bypass register

### media Phase 4（已彻底封存，短期不考虑）

> **已彻底封存（2026-08-01）**：短期不考虑实现，恢复需显式解封并重新评估设计文档与当前代码基线的一致性。代码层零启动（仅设计文档 `docs/backup/02_multimodal_behavior.md` 存在）。前置（路径统一/内核原生化/磁盘型存储）均已完成，但 Phase 4 容器工作（MediaAxiom + IbMedia + from_response 协议）封存期间不推进。

---

## 确认为设计决策（不修复）

| 测试 ID | 原因 | 处理 |
|---------|------|------|
| **INV-LAMBDA-3** | IBCI 无 walrus (`:=`) / lambda 体赋值语法 | 设计排除（见 `docs/KNOWN_LIMITS.md` §十九.1）；原 SKIP 测试已删除（永久死代码） |
| **INV-SCOPE-1** | SEM_002 禁止 if-block 内重声明同名变量 | 设计排除（见 `docs/KNOWN_LIMITS.md` §十九.2）；原 SKIP 测试已删除（永久死代码） |
| **REFLECT-ARCH-1** | `loader.py` 与 `ibci_sdk/check.py` 签名校验存在复制 | 设计隔离（`check.py:209` 刻意 `# 不 import core.*`——SDK 离线校验不初始化运行时）；强制收敛引入 SDK↔runtime 错误耦合，**不收敛** |

> 上述设计决策来自 2026-08-02 反射排查收尾，决策归并于此。
