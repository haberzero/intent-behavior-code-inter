# 测试体系治理与彻底重构

> **状态**：**已并入 `OBSERVABILITY_REFACTOR.md`（2026-08-06 用户裁定）**——测试体系重构升格为从内核出发的
> 可观测性统一重构，本文件保留为**测试侧专项规划参考**（策略/铁律/Phase 0-5 沿用）。主任务控制文档见
> `tasks_docs/OBSERVABILITY_REFACTOR.md`（Phase 2D/3/4）。
> **性质**：正式任务文档（非临时），规划参考。4 份调研原始报告见 `TEST_REFACTOR_REPORTS.md`。

---

## 一、总体策略（强制）

1. **新建从零**：重构期间**不动现有 `tests/` 体系**。完全新建一个测试目录（命名 Phase 0 确定，下称"新体系"），从零参考已有测试项构建更健康、全面、架构合理的测试脚本体系。
2. **并行共存**：新体系与旧 `tests/` 并存，两者均可独立运行。覆盖对照靠"两者都跑 + 基准比对"。
3. **全面替换后删除**：新体系全面建好、覆盖经论证 ≥ 旧体系、meta 门禁全绿后，新体系替换旧 `tests/`，旧体系**彻底删除**。
4. **深入内核**：范围包含内核层面的测试接口改造（新增正式测试内省 API、test hooks、预留字段、MOCK 协议契约化、test-double 基建）。这些是**新增 additive**，不破坏现有测试。
5. **docs 治理**：`tests_docs/` 纳入 `docs/WRITING_GUIDE.md` 治理（闭合治理盲区）。
6. **工作模式定论优先**：全程遵守 `NEXT_STEPS.md` "⛔ 工作模式定论"。禁止 compat shim / 胶水 / tricky / 过程式硬编码分发。

---

## 二、工作路径（Phase 0-5）

> **铁律：Phase 0 规划与设计冻结完成前，不启动任何代码改动。** 避免"大量工作后偏移"。

### Phase 0：基准固化与设计冻结（不动代码）

**0.1 覆盖基准固化**
- 跑 `python3 -m pytest tests/ --collect-only -q` 输出 per-file 用例计数快照。
- 固化当前 INV-* 矩阵的"已覆盖项"清单（每条定位到 file:line）。
- 此快照作为"新体系必须 ≥ 此基准"的对照基线，存档。
- **并入 PT-TEST-3（2026-08-06 用户裁定）**：矩阵同步在此重构中一并完成。
  已有核对发现（改名映射 / TRUE_GAP / 契约漂移）见 `tasks_docs/TEST_MATRIX_FINDINGS.md`，作为输入。

**0.2 新体系架构设计冻结**（产出设计文档，评审通过后不动）
- 目录结构（采纳报告 A ⑥ 提议：kernel/compiler/runtime/plugins/contracts/e2e/compliance/sdk/meta/fixtures）。
- 命名规范（文件 `test_<concept>.py`、类 `Test<Concept><Aspect>`、禁里程碑代号；e2e 文件名去 `e2e_` 前缀由目录承载层义）。
- 分层模型（统一为单一模型：以实际目录为准；TEST_PHILOSOPHY 的 Examples/Regression 层落地或移除；contracts 进分层表；meta 定位为"测试规范执行器"）。
- conftest 设计（黑盒 API 在根；白盒 helper 下沉 runtime 层；`AI_MOCK_PREFIX` 真正单点真理；删/激活 `helpers` fixture；统一 kernel 命名去别名 shim）。
- 覆盖矩阵新结构（`file::class::method` 三段式引用 + meta 机器校验）。
- 新测试目录命名确定。

**0.3 内核测试接口设计冻结**（采纳报告 C ⑤⑥ 提议，详见本文档"三、内核改造清单"）

**0.4 docs 治理方案冻结**（纳入 WRITING_GUIDE 的具体条款）

**0.5 4 份调研报告归档**（已完成，见 `TEST_REFACTOR_REPORTS.md`）

### Phase 1：内核测试接口层（additive，非破坏性）

> 先建内核正式测试接口，使新体系从 day 1 用正式接口、无私有穿透。每项加后跑全量 pytest 确认无回归。

按"三、内核改造清单"优先级实施。全为新增，不动现有测试。

### Phase 2：新体系骨架（新目录）

- 新建测试目录。
- 根 conftest（黑盒 API）+ 各层 conftest（白盒 helper 下沉）。
- meta 测试骨架（命名规范、layering 无白名单、COVERAGE_MAP/矩阵双向同步、helper 禁列自动派生）。
- 覆盖矩阵新结构骨架。

### Phase 3：逐域移植（domain-by-domain，每域独立可验证）

按域移植，每域：移植 + 合并冗余（报告 B M1/M2/M3）+ 补缺口（报告 B G1-G4、D2/D4/D5）+ 参数化 + 用新内核接口取代穿透（报告 C ②）。每域后跑新域测试 + 旧体系全量不退化。

移植顺序建议：kernel -> compiler（拆 mixed-concerns）-> contracts（补 G1）-> runtime（拆 plugins）-> e2e（合并冗余）-> compliance -> sdk -> meta（强制规范）。

### Phase 4：全面对照论证

- 新体系全量跑通。
- 覆盖对照：新 per-file collect ≥ 旧；INV-* 矩阵每条定位到新测试；缺口项（G1-G4）已补。
- meta 测试全绿（命名/layering/矩阵同步/helper 禁列，无白名单）。
- 产出论证文档：新旧覆盖等价性 + 增量。

### Phase 5：切换与清理

- 新体系替换旧 `tests/`。
- 删除旧 `tests/`。
- 更新文档：`tests/COVERAGE_MAP.md`、`tests_docs/SEMANTIC_COVERAGE_MATRIX.md`、`tests/README.md`、`docs/WRITING_GUIDE.md`（纳入 tests_docs）。
- `NEXT_STEPS.md` 移除完成项；本临时文档删除。

---

## 三、内核改造清单（报告 C ⑤⑥，按优先级）

| # | 改造 | 替代的现有 hack | 类型 |
|---|---|---|---|
| 1 | `Interpreter.execution_context` 取代 `_execution_context` 穿透 | 报告C ②#1（4 处） | 零成本测试侧 |
| 2 | `IIbBehavior` Protocol 声明 `llm_deps`/`dispatch_eligible` | 报告C ④.1 `hasattr` 探测 | Protocol 契约化 |
| 3 | MOCK 哨兵字符串常量化（`MOCK_REPAIR_SENTINEL` 等） | 报告C ③.1 跨模块魔法字符串（6+ 处） | 契约化 ✅ 已完成（B0，含 enum 镜像一致性测试） |
| 4 | 统一 LLM mock 注册口 + `is_test_mode` 收敛 | 报告C ③.2 TESTONLY 散落判定（4 处重复+MOCK_KEY 孤儿） | 机制收敛 ✅ 已完成（B0，`_is_test_config`） |
| 5 | `IBCIEngine.test_snapshot()` 内省 API | 报告C ②#2-7（12 处私有穿透） | 正式内省 API |
| 6 | `resolve_plugin_search_paths()` 公开 | 报告C ②#3 | 正式 API |
| 7 | `LLMExecutor.pending_future_count()`/`has_pending()` | 报告C ②#8（5 处穿透） | 正式观测口 |
| 8 | `FileLib.get_file_handle_class()` 或经 `registry.get_class` | 报告C ②#9 | 正式 API |
| 9 | test-double 基类（`NullStackInspector` 等） | 报告C ④.3 自造 Dummy 双胞 | test 基建 |
| 10 | `path_scoped_import` 统一模块加载清理 API | 报告C ③.6 check.py 与 ModuleLoader 各自管理 | 基建统一 |
| 11 | 预留字段：`IsolationPolicy.test_mode`/`mock_provider` | 隐式 `silent=True` 硬编码 | 显式化 |
| 12 | 预留字段：`ServiceContext.test_hooks`（on_llm_call/on_dispatch/on_llmexcept_enter/exit） | 散落可观测字段 | 结构化事件流 |
| 13 | 预留字段：`ExecutionContext.last_llm_call` + `reset_test_state()` | `get_last_call_info` 散落 + 多个分散 reset | 统一隔离入口 |
| 14 | 预留字段：`IBCIEngine.reset_test_state()` | spawned_tasks 残留 | 引擎复用隔离 |

---

## 四、docs 治理（纳入 WRITING_GUIDE）

- `tests_docs/` 纳入 `docs/WRITING_GUIDE.md` 管辖范围（修订 WRITING_GUIDE §9 排除条款）。
- 新增约束：禁冻结通过数字（仅指向 `NEXT_STEPS.md` 顶部锚点）、禁过程叙述/日期戳/版本号、矩阵必须可机器校验。
- 统一分层模型：三份文档（TEST_PHILOSOPHY / tests/README / COVERAGE_MAP）收敛为单一模型。
- 矩阵改 `file::class::method` 三段式 + meta `test_matrix_sync.py` 机器校验。
- 清理冻结数字（TEST_PHILOSOPHY:617 / COVERAGE_MAP:134 / MATRIX:588）。
- 契约测试深度标记：区分"编译期契约"与"运行时不变量"（`✅` vs `🔶编译期`）。

---

## 五、覆盖保活铁律

1. **缺口先行**：报告 B G1（INV-STR-6）/D2/D4/D5 等"名义覆盖实为空"项，在移植对应域时**先补真测试**，再合并/删除。
2. **删除前先承接**：R2/R3/M1-M3 类合并，**先写新测试跑通，再删旧测试**。禁止"先删后补"。
3. **前后 collect 数对照**：每域移植后 `--collect-only` per-file 计数，任何下降逐条说明承接关系。
4. **INV-* 矩阵对照**：重构后逐条核对每个 ✅ 项仍能定位到测试。
5. **分批小步 + 全绿门禁**：每域一 PR，每批后全量 `pytest` 不退化（passed 不降、skipped 不增）。
6. **meta 测试始终通过**：layering 白名单随移植逐步收缩，最终无白名单。
7. **不碰设计限制项**：报告 B G5/G6（INV-LAMBDA-3、dispatch 禁用相关 skip）属设计限制，重构不取消 skip。

---

## 六、需决策点

1. **新测试目录命名**：`tests_v2/` / `testing/` / 其它？（Phase 0.2 确定）
2. **分层模型取舍**：TEST_PHILOSOPHY 的 Examples/Regression 层是落地为目录还是从哲学文档移除？（Phase 0.2 确定）
3. **内核改造批次**：Phase 1 全部做完再进 Phase 2，还是与 Phase 2/3 交织？（建议 Phase 1 先做完，地基先行）
4. **覆盖矩阵重写 vs 修复**：是重设计矩阵结构，还是修现有矩阵为三段式引用？（Phase 0.2 确定）

---

## 七、进度追踪

| Phase | 状态 | 备注 |
|---|---|---|
| 0 基准固化与设计冻结 | ⏳ 待启动 | 规划阶段，不动代码 |
| 1 内核测试接口层 | ⬜ | |
| 2 新体系骨架 | ⬜ | |
| 3 逐域移植 | ⬜ | |
| 4 全面对照论证 | ⬜ | |
| 5 切换与清理 | ⬜ | |

---

## 八、关联文档

- 4 份调研原始报告：`tasks_docs/TEST_REFACTOR_REPORTS.md`
- 工作模式定论：`tasks_docs/NEXT_STEPS.md` "⛔ 工作模式定论"
- 6 项测试相关（原缺陷复查）：已被本重构吸收（对应报告 B ④）。
