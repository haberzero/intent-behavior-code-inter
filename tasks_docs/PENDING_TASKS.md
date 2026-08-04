# PENDING_TASKS - 阻塞 / 待前置任务的未来规划

> 本文档记录**暂时搁置但经过验证仍有有效性的规划**。
> 当前最紧要项见 `tasks_docs/NEXT_STEPS.md`。
>
> **最后更新**：2026-08-04（PT-MT-1~8 全部完成；任务 A、B 已完成；任务 C-F 见 NEXT_STEPS.md）

---

## 〇、IBCI 运行时多线程 + 通信机制（已全部完成，方向修正中）

> 用户裁定（2026-08-03）确立下一主线，PT-MT-1~8 已全部完成（2026-08-03，全量 1409 passed 零回归）。**随后用户深度质询推翻 spawn/join/cancel/task 关键字语法**，方向修正为 thread 对象 + 句柄方法模型——任务 A-F 见 `NEXT_STEPS.md`"当前主线"节与 `tasks_docs/THREAD_DESIGN_REVISION.md`（已授权，**任务 A、B 已完成 2026-08-04**，任务 C-F 待开工）。
>
> 本系列原规划已完成（历史记录保留）。

| 编号 | 标题 | 目标 | 状态 |
|------|------|------|------|
| PT-MT-1 | 详细设计文档 | 完整架构/AST 变更/接口/并发正确性/测试策略，先经用户审阅 | **已完成 2026-08-03**，见 `tasks_docs/THREADING_DESIGN_DETAIL.md`（经独立审查修正 6 处后落地） |
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

### PT-SMELL-3：局部 import 审计（独立分支）[P2]【已完成 2026-08-03】

> 无意义的局部 import、为打破循环导入的内联 import（含我的工程经验补充：循环依赖应重构方向而非胶水掩盖、TYPE_CHECKING 替代、热路径重复 import、惰性依赖合法模式）。全仓 35 处局部 import 分类清单见 **`tasks_docs/LOCAL_IMPORT_AUDIT.md`**。独立分支执行。
>
> **完成**：可提升类（L12/13/14/16/19/20）已提升至模块顶部；L15/L17 核验保留；循环打破类（L1-L10 等）核验为**标准运行时局部 import 环打破（非胶水）**，但按其 tradeoff 性质**极其谨慎地记录为未来推迟工作**（见 `LOCAL_IMPORT_AUDIT.md` §四"推迟工作记录"），待架构重构时逐项复核。已并入 unsafe-vibe-dev。

### PT-ARCH-23 G2 遗留：内核原生模块覆盖可观测性缺口 [待决策]

> `HostInterface.register_module()` 静默忽略与 kernel-native 同名的用户插件，无 warning。功能正确，可观测性不足。待诊断体系稳定后专项处理。

### PT-ARCH-29：命名历史包袱清理 [P1]

> 代码层已零残留（完成）；剩余：历史设计文档/工作日志中的旧 API 引用加"历史文档"标注（低优先级，随文档治理顺带处理）。

### PT-ARCH-30：`file` 模块命名风险 [P1]

> `file` 影子化 Python 内建。长期需重命名（如 `fs`/`filesys`/`io`）。当前过渡措施已实施。

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
