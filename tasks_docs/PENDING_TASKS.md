# PENDING_TASKS - 阻塞 / 待前置任务的未来规划

> 本文档记录**暂时搁置但经过验证仍有有效性的规划**。
> 当前最紧要项见 `tasks_docs/NEXT_STEPS.md`。
>
> **最后更新**：2026-07-24（文档卫生清理：PT-DOC-4/7/8/9/10/11 全部验证并关闭；§五 文档健康改善项清空撤销，原§六/§七上移）

---

## 一、Semantic Pipeline 后续演进

### PT-SEM-1　生产就绪化 [P2]

**前置条件**: Semantic 4-Phase pipeline 已稳定运行 ✅

**待做**：
1. 错误信息优化：`SEM_xxx` 错误码转化为用户友好表述
2. 诊断工具：符号表/类型绑定/行为依赖图 JSON/dot 导出
3. 性能基准：编译时间基准测试
4. CI/CD 集成

### PT-SEM-2　CompilationResult 字段精简 [P3]

**前置条件**: PT-SEM-1 完成 + pipeline 稳定运行 ≥ 1 个月

### PT-SEM-3　二层 IR 路线评估 [VISION]

---

## 二、VM 异步/协程层（L3）[SHELVED]

> **搁置原因**：当前优先完善多模态功能
> **独立设计文档**：`docs/subsystems/05_coroutine.md`

### 阻塞原因
1. 调度器架构需从单根任务升级为多任务挂起/恢复
2. `async`/`await`/`yield` 关键字不在 KEYWORDS 表
3. 快照协议需覆盖协程 yield 点

### 被阻塞的子项

| 编号 | 标题 | 依赖 L3 的原因 |
|------|------|---------------|
| PT-3.1 | `host.run_isolated()` 返回值改进 | 需要协程句柄实现异步等待 |
| PT-3.2 | `ReceiveMode` 枚举演进 | 需要 yield/resume 语义 |

---

## 三、语言级能力扩展

### PT-4.1　Enum 非 str 成员 + 迭代能力 [VISION]

> `primitives.py` 把成员值一律设为名字字符串，数字状态码枚举无法 round-trip。

### PT-4.2　`__call__` 协议类型推断一致性 [VISION]

> `__call__` 协议在 3 个文档有 3 种不同定性，框架应统一。

### PT-4.3　语言级协程 [SHELVED]

见 §二 + `docs/subsystems/05_coroutine.md`。

### PT-4.4　用户类泛型类型参数 [VISION]

### PT-4.5　用户类运算符重载 [VISION]

### PT-4.7　DDG 并行调度接入 VM（含原 C2 缺陷合并） [DESIGN-DEBT] [已激活]

> **已激活为当前主线**（见 `NEXT_STEPS.md`）。细化规划与工作路径见 `tasks_docs/_mock_concurrency.md`：MOCK 服务化（独立进程 HTTP 服务，模拟延迟/并发/失败）作为开发仪器，协同修复 dispatch 数据竞争，解锁 4 项 skip 测试。
>
> **原 C2 缺陷已并入此项**。dispatch_eager 曾被半接通（`dispatch_eligible` 默认 `True`）但后台线程执行完整 `execute_behavior_expression`（含 prompt 段求值），重入共享 `VMExecutor` 导致 `_current_stack`/`step_count`/`last_call_info`/`retry_hint` 数据竞争。已显式禁用（`dispatch_eligible` 一律置 `False`），行为表达式全部走同步路径。
>
> **接通前置条件**：
> 1. 修 `BehaviorDependencyPass` 实现 `05_vm_specification.md §3.1` 规则（插值依赖/Cell/llmexcept 强制 `False`，当前 pass 只检测环）
> 2. 拆分 `execute_behavior_expression` 为"主线程预求值 prompt"（同步）+"后台仅 `_call_llm`+解析"（异步）
> 3. `last_call_info`/`retry_hint` 线程安全或去共享化
> 4. 补"插值 + 真实并发"合规测试（现有 `test_concurrent_llm.py` / `test_e2e_llm_pipeline.py` 用 MOCK 只验值正确性，不验真实并发时序）
> 5. 重新启用被 skip 的 4 个 dispatch 专属测试（`test_e2e_llm_pipeline.py::test_two_independent_assignments_both_pending_after_run`、`test_e2e_llm_basic.py::TestE2EStaleResultIsolation` × 3）

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

## 五、测试基础设施改善项

### PT-TEST-6　e2e 测试覆盖率提升 [P2]

> `for...if` 过滤语法零 e2e 测试；复合赋值运算符零 e2e 测试（仅有 AST 级 false-positive 测试）。

### PT-TEST-7　测试名与覆盖矩阵同步 [P3]

> `tests_docs/SEMANTIC_COVERAGE_MATRIX.md` 中的测试名与实际文件名不同步。

### PT-TEST-8 MOCK 指令文档与代码同步 [P3]

> `docs/syntax/13_mock_testing.md` 需与 `ibci_ai/core.py` MOCK 处理逻辑保持同步。

---

## 5.5、文档体系完善项

### PT-DOC-1 语法手册定位段补充 [P3]

> `docs/syntax/*.md` 各章节文件缺少 `docs/README.md` §六.3 要求的定位段（1-3 句：本文是什么、给谁看、覆盖什么）。当前由 `SYNTAX_REFERENCE.md` 目录结构承担定位职责，未来应为每篇补充独立定位段以支持独立阅读。

### PT-DOC-2 多模态子系统设计文档恢复 [P3]

> 全模态行为表达式设计文档已移至 `docs/backup/02_multimodal_behavior.md`。待多模态主线恢复时，需按 `docs/README.md` §六准则重新审视并纳入 `docs/subsystems/`。

---

## 六、media Phase 4 前置技术债与延迟项

### PT-ARCH-22：全项目文件命名清理 [暂缓]

> 全面排查过短/欠层次/欠区分度/影子化内建的代码文件命名。排期：暂缓，独立窗口执行。

### PT-ARCH-23 G2 遗留：内核原生模块覆盖可观测性缺口 [待决策]

> `HostInterface.register_module()` 静默忽略与 kernel-native 同名的用户插件，无 warning。功能正确，可观测性不足。待诊断体系稳定后专项处理。

### PT-ARCH-28：`file` 模块统一写入 API [P2]

> 当前提供 `write_copy`/`write_overwrite`/`write_new` 三种写入函数。未来统一为 `file.write(target, data, overwrite_flag="copy"|"overwrite"|"new")`，需 IBCI 支持动态/命名参数。

### PT-ARCH-29：命名历史包袱清理 [P1]

> 代码层已零残留；历史设计文档/工作日志中的旧 API 引用需加"历史文档"标注。items 3-5 待做。

### PT-ARCH-30：`file` 模块命名风险 [P1]

> `file` 影子化 Python 内建。长期需重命名（如 `fs`/`filesys`/`io`）。当前过渡措施已实施。

### Phase 4 延迟项（从 ADR-008/010/013 提取）

以下三项在 media Phase 4 开工时需实现：

**PT-PHASE4-1：多模态模型注册字段**

`ai.register_model(name, url, key, model, **kwargs)` 当前仅存储 `timeout`，需扩展存储 `modalities`/`endpoint`/`audio_config` 字段，并更新 vtable 声明。

**PT-PHASE4-2：非聊天端点推理绕过**

当前所有未探测的命名模型默认 `is_reasoning_model = True`，导致非聊天端点（Whisper/DALL-E）被注入 reasoning prompt。需实现 endpoint-based 检测：命名模型配置了 `endpoint` 字段时，强制 `is_reasoning_model = False`，跳过 reasoning prompt 注入。

**PT-PHASE4-3：磁盘型响应解析协议**

当前 LLM 响应解析使用 `__from_prompt__` 协议（内存型）。磁盘型类型需要平行的 `from_response` 协议：
- 新增 `has_multimodal_response_cap` flag + `from_response` 方法到 BaseAxiom
- 新增 `get_from_response_cap` accessor 到 SpecRegistry
- 新增 bypass register（`set_last_raw_response`/`get_last_raw_response`）到 runtime_context
- `_call_llm` 存储完整响应对象到 bypass register

### media Phase 4（未来低优先级）

> **已暂停**。代码层零启动（仅设计文档 `docs/subsystems/02_multimodal_behavior.md` 存在）。前置（路径统一/内核原生化/磁盘型存储）均已完成，但 Phase 4 容器工作（MediaAxiom + IbMedia + from_response 协议）暂不推进，降级为未来低优先级。恢复时需重新评估设计文档与当前代码基线的一致性。

---

## 确认为设计决策（不修复）

| 测试 ID | 原因 | 处理 |
|---------|------|------|
| **INV-LAMBDA-3** | IBCI 无 walrus (`:=`) / lambda 体赋值语法 | 设计排除（见 `docs/KNOWN_LIMITS.md` §十九.1）；原 SKIP 测试已删除（永久死代码） |
| **INV-SCOPE-1** | SEM_002 禁止 if-block 内重声明同名变量 | 设计排除（见 `docs/KNOWN_LIMITS.md` §十九.2）；原 SKIP 测试已删除（永久死代码） |
