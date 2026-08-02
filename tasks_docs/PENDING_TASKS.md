# PENDING_TASKS - 阻塞 / 待前置任务的未来规划

> 本文档记录**暂时搁置但经过验证仍有有效性的规划**。
> 当前最紧要项见 `tasks_docs/NEXT_STEPS.md`。
>
> **最后更新**：2026-08-02（任务控制清洁：PT-HEALTH-1/PT-HEALTH-2/PT-ARCH-28/PT-TEST-8 完成移除；反射排查已全线完成，遗留项归并至 PT-SEM-4 / REFLECT-ARCH-1；新增 PT-SMELL-1/2/3 技术债审计分支任务；LLM 并行/异步主线确立并梳理 Tier 分层，新增 PT-SYNC-1/2/3）

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

### PT-SEM-4　resolve_call_return 兜底双通道待深析 [P3]（Tier 4，独立于并行主线）

> 反射排查归并遗留：`_expression_visitors.py:304` 在统一入口 `resolve_call_return` 之外直读 `func_type.return_type` 作最后兜底（功能性双通道，非机械冗余）。待评估 `resolve_call_return` 是否应覆盖该路径或显式收敛。

---

## 二、VM 异步/协程层（L3）【已升为主线，见 NEXT_STEPS.md】

> **状态变更（2026-08-02）**：用户裁定 **LLM 真正可用的并行化 + 同步异步** 为当前主线，本方向由 SHELVED 升为主线。原阻塞项（调度器多任务化、async/await 关键字、快照协议）成为主线组成部分；设计文档：`docs/subsystems/05_coroutine.md`。
> **原搁置原因**：原为优先完善多模态功能（2026-08-01 多模态已封存，2026-08-02 无限期搁置）；协程方向已重新评估并升为主线。

### 阻塞原因
1. 调度器架构需从单根任务升级为多任务挂起/恢复
2. `async`/`await`/`yield` 关键字不在 KEYWORDS 表
3. 快照协议需覆盖协程 yield 点

### 被阻塞的子项

| 编号 | 标题 | 依赖 L3 的原因 |
|------|------|---------------|
| PT-3.1 | `host.run_isolated()` 返回值改进 | 需要协程句柄实现异步等待 |
| PT-3.2 | `ReceiveMode` 枚举演进 | 需要 yield/resume 语义 |

### 主线隐含新任务（2026-08-02 梳理定案，并行主线自身要求）

| 编号 | 标题 | 目标 |
|------|------|------|
| PT-SYNC-1 | 并发正确性验证方法 | Stage 1/2 需要并发测试基建（并发 dispatch 测试、共享状态只读不变式测试）——否则"真正可用"无法被证明【已完成 2026-08-02：新增 `tests/runtime/test_concurrent_dispatch_integrity.py`，经 mock_server 真实 HTTP 驱动并行 dispatch，验证 真正并发重叠/no-cross-talk/乱序确定性/批次隔离；全量 pytest 1284 passed/4 skipped 零回归】 |
| PT-SYNC-2 | `LLMFuture` 生命周期/错误语义 | resolve 超时/取消/重复 resolve 的用户可见语义——并行可用性的边界 |
| PT-SYNC-3 | 线程池资源生命周期 | `close()` 语义、关闭后 `dispatch_eager` 的行为（当前会重建池，语义模糊）——资源管理明确化 |

---

## 三、语言级能力扩展

### PT-4.1　Enum 非 str 成员 + 迭代能力 [VISION]

> `primitives.py` 把成员值一律设为名字字符串，数字状态码枚举无法 round-trip。

### PT-4.2　`__call__` 协议类型推断一致性 [VISION]（Tier 3，独立于并行主线）

> `__call__` 协议在 3 个文档有 3 种不同定性，框架应统一。**2026-08-02**：与并行主线为弱-中关联（async 未来中可调用对象可能 awaitable，边缘交集）；保持独立，不阻塞主线，async 落地时再评估 `await` 与可调用对象的交互。

### PT-4.3　语言级协程 [升为主线，见 NEXT_STEPS.md]

> 2026-08-02 随 §二 升为主线（Stage 3 语言级 async/await）；完整设计见 `docs/subsystems/05_coroutine.md`。

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

> 健康审计（2026-07-31，mock 子系统）发现的 executor 侧待诊断项。**2026-08-02**：executor 共享状态部分已并入并行主线 **Stage 1**（`_expected_type_stack` 死状态已删、`_result_parser` 懒重建竞争已修 fail-fast、`_current_call_info` 核验按构造无竞争）。**剩余**：`scene` 协议参数保留但无消费者（`__call__` 已注明协议兼容）——删除或激活；`MOCK_CLIENT_SENTINEL`/`TESTONLY` 字面量已常量化的同一批健康问题在其它 `ibci_modules` 插件（json/math/time 等）中可能仍存在，需按 `.opencode/skills/code-quality/SKILL.md` 健康诊断十查全仓扫描。

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

### PT-SMELL-3：局部 import 审计（独立分支）[P2]

> 无意义的局部 import、为打破循环导入的内联 import（含我的工程经验补充：循环依赖应重构方向而非胶水掩盖、TYPE_CHECKING 替代、热路径重复 import、惰性依赖合法模式）。全仓 35 处局部 import 分类清单见 **`tasks_docs/LOCAL_IMPORT_AUDIT.md`**。独立分支执行。

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
