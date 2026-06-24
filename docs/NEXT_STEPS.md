# NEXT_STEPS — 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `docs/PENDING_TASKS.md`；历史归档见 `docs/COMPLETED.md`。
> 已知语言级限制见 `docs/KNOWN_LIMITS.md`。
>
> **最后更新**：2026-06-24（P0 全量完成，基线恢复绿色；P1 架构改善升为当前最紧要）

---

## 当前测试基线（每次开新分支前必须复跑确认）

```bash
python -m pytest tests/ -q --tb=no --no-header
```

**2026-06-24 实测结果**：`838 passed, 2 skipped`（P0 修复后，无需任何环境变量 workaround）

> ✅ 基线已可信：P0 修复了 11 个失败（6 个编码 + 5 个路径转义）+ 跨盘硬化 + 2 个 Critical bug + 1 个并发竞争。
> 2 个 skipped 为设计限制：`INV-LAMBDA-3`（无 walrus/lambda 体赋值）、`INV-SCOPE-1`（SEM_002 禁止 if-block 重声明）。
> 详见 `docs/worklogs/P0_BASELINE_RECOVERY.md`。

---

## ✅ P0 已完成（2026-06-24）

> P0 全部 6 项已完成并提交（commit 72f59e6）。详见 `docs/COMPLETED.md` 和 `docs/worklogs/P0_BASELINE_RECOVERY.md`。
> 此处仅保留指针，不再展开细节（遵守单点真理规则 #6）。

---

## P1（当前最紧要）：架构健康修复 + 测试基础设施 + 文档修复

### P1-A 提取 `core/runtime/shared/` 打破 3 个 runtime 内循环
- 移动 `interpreter/llm_result.py`（`LLMResult`/`LLMFuture`）→ `runtime/shared/llm_result.py`
- 移动 `vm/task.py` 的 `Signal`/`ControlSignal`/`UnhandledSignal` → `runtime/shared/signal.py`
- 移动 `interpreter/constants.py` → `runtime/shared/constants.py`
- 收益：消除 `interpreter↔vm`、`objects↔interpreter`、`objects↔vm` 三个延迟导入掩盖的循环

### P1-B 拆分 `HostInterface` → `ModuleMetadataProvider` + `HostModuleRegistry`
- 文件：`core/runtime/host/host_interface.py` + `core/compiler/scheduler.py:16` + `core/compiler/parser/core/context.py:6,39`
- 问题：编译器只需元数据部分却依赖整个 god object；`context.py:39` 自动实例化 `HostInterface()`
- 修复：拆分接口，编译器只依赖 `ModuleMetadataProvider`；删除自动实例化

### P1-C 移动 `fuzzy_json.py` → `core/base/support/`
- 文件：`core/kernel/axioms/primitives.py:28` → `core/runtime/support/fuzzy_json.py`
- 收益：恢复 "kernel 永不导入 runtime" 不变量（最便宜的架构修复）

### P1-D 拆分 `handlers.py`（2023 行 → 7 个分类子模块）
- 文件：`core/runtime/vm/handlers.py`
- 方案：按节点类别拆为 `handlers/{leaf,control_flow,assignment,llmexcept,decls,intent_behavior,loops}.py` + 保留 `build_dispatch_table`

### P1-E 加 `pytest.ini` + `.github/workflows/ci.yml` + `pytest-cov`
- 当前：无任何 pytest 配置、无 CI workflow
- 最低配置：`testpaths = tests`、`--strict-markers`、`--cov=core --cov-fail-under=70`

### P1-F 加 `tests/meta/test_layering.py` 静态强制层级红线
- 当前层级违反 3/5：`kernel/` 调 `run_ibci`、`compiler/` 系统性调 `run_ibci`（26+ 处）、`e2e/` 导入 `core.runtime.interpreter`
- 同时迁移：`tests/compiler/semantic/test_override_and_super.py` + `test_nonlocal.py` → `tests/e2e/`

### P1-G 加 `tests/runtime/test_mock_directives.py` 独立测试 MOCK
- 当前：`_handle_mock_response` 被 ~hundreds 测试信任但从未独立测过

### P1-H 标注 `AUDIT_REPORT_20260527.md` 5 个发现为已解决
- 5 个 P0/P1 发现已于 2026-05-27 关闭，但审计文档未记录
- 修复：每个发现加 "✅ Resolved 2026-05-27 — see COMPLETED.md"

### P1-I 修复 2 个 hub 文档锚点传播
- `KNOWN_LIMITS.md` 编号被 4 个文档引用（旧编号 → 新 §一..§十六）
- `COMPLETED.md` 测试计数被 5 个文档引用
- 修复 `TEST_PHILOSOPHY.md:618`、`AUDIT_REPORT_20260527.md`、`ARCH_DETAILS.md:275`、`FUNC_DESIGN_NOTES.md:42`、`HISTORY_LOG.md` 4 处旧编号

---

## 阻塞中：Phase 3 — `audio` / `image` / `video` 内置类型

> ⚠️ **状态变更**：原 P0，本次全量分析后**降为阻塞**。

**阻塞原因**：
1. **决策矛盾未解决**：DEC-5（路径引用 snapshot）与 DEC-6（Phase 3 纯内存）互相矛盾；D4 示例（`ai.register_model("GPT4o", {dict})`）与实际 vtable 签名不兼容，无法编译；D6 与 DEC-4 同文档对立
2. **DEC-5 可能根本不工作**：`llm_except_frame.py:199` 用 `type(val) is IbObject` 严格身份检查，若 `IbAudio` 是 `IbObject` 子类则 snapshot 分支不匹配 → 变量被静默跳过，不进入 snapshot
3. **基线不可信**：在 P0 修复完成前，"0 回归"声明无法验证

**解除阻塞条件**：
- P0 全部完成，基线恢复可信
- DEC-1~6 决策矛盾解决（需建立 ADR，见 PENDING_TASKS §六）
- DEC-5 snapshot 分发机制验证通过（`type(val) is IbObject` → `isinstance` 或 axiom-backed dunder）
- D4 `register_model` vtable 与示例调用一致

**设计文档**：`docs/MULTIMODAL_BEHAVIOR_DESIGN.md` §七 Phase 3 + 附录 C §C.6 决策表

---

## P2 候选：PT-SEM-1 Semantic Pipeline 生产就绪化

> 注：本条目的完整规划见 `docs/PENDING_TASKS.md §一`（为遵守单点真理规则 #6，此处仅保留指针）。

**前置条件**：Semantic 4-Phase pipeline 已稳定运行 ✅ + P0 基线修复完成

**具体待做**：错误信息优化 / 诊断工具 / 性能基准 / CI/CD 集成

**预估工作量**：15-20 小时

---

## P2 候选：ADR 制度建立

### P2-A 建立 `docs/decisions/` 目录
- 当前：无任何正式 ADR
- 先补 Top 10 历史 ADR（CPS VM 选型、Axiom vs 继承、7-Pass→4-Phase、llmexcept 影子执行、BUG #A 语义变更、dispatch_eager、tag 大小写、TypeSlot 单锁、协程搁置、intent fork-on-call）

### P2-B 写 5 份紧急 ADR 解决决策矛盾
- ADR-DEC-5/6：snapshot × storage 交互（记录 `type(val) is IbObject` 限制、media 类层次、temp 生命周期）
- ADR-D4：`register_model` vtable 一致性（记录 modalities/endpoint/audio_config 字段、MOCK 不可绕过性）
- ADR-D6：`_call_llm_raw` 引入（记录 MOCK 重构后果、caller 分支需求、Phase 4 推迟事实）
- ADR-R5：per-model capability probing（记录非 chat 端点失败模式）
- ADR-Baseline：测试基线可复现性（记录跨盘 relpath 限制、11 个 ever-failing 测试）

**预估工作量**：3-5 天

---

### 确认为设计决策（不修复）

| 测试 ID | 原因 | 处理 |
|---------|------|------|
| **INV-LAMBDA-3** | IBCI 无 walrus (`:=`) / lambda 体赋值语法 | 保持 SKIP，标注为"设计限制" |
| **INV-SCOPE-1** | SEM_002 禁止 if-block 内重声明同名变量 | 保持 SKIP，标注为"设计限制" |

---

## P3 候选（远景；详见 PENDING_TASKS）

- 多模态 Phase 5 磁盘卸载与生命周期管理
- `isinstance()` 运行时类型检查
- 二层 IR 路线
- 用户级泛型 (`class Box[T]:`)
- 协程层（搁置中，详见 `docs/COROUTINE_DESIGN_NOTES.md`）
- 拆分剩余 6 个 god modules（详见 PENDING_TASKS §五）
- 折叠重复分支（详见 PENDING_TASKS §五）
- 修复 17+ 处静默吞异常
- 删除死代码（`IbStatelessPlugin`、3 个 orphan fixtures 等）

---

## 工作规则

- **每次开新分支前**，先复跑 `python -m pytest tests/ -q --tb=no --no-header`，把当前 pass/fail 计数写在 PR 描述里，不预设上一份文档里的数字。
- **跨盘环境注意**：若 repo 与 `%TEMP%` 不同盘，需先 `set TMP=<repo_dir>` / `set TEMP=<repo_dir>`，否则 `scheduler.py:162` 跨盘 `relpath` 会产生大量假失败。
- 同一时刻只主推一项 P0 任务（或一项 P1）；其余项保留待选。
- 任何改动公理层公约或语义错误集的任务，需在分支早期跑全量 pytest 评估破坏面。
- 每项完成后，把摘要追加到 `docs/COMPLETED.md`（极简时间线），并把对应条目从本文件移除。
- 出现新的紧要项时，按"先评估优先级、再决定是否替换 P0"原则操作。
- **本文件不冻结具体测试通过数字**——任何"X 测试通过"的表述都必须附运行命令或日期锚点。

---

## 维护守则

1. **先复跑、后下结论**。任何关于"测试基线红线"的表述，必须以"附完整 pytest 输出 + 日期 + 分支 + 环境条件（盘符/locale）"的方式说服读者；否则视为待核查。
2. **不要相信"昨日完成"的总结**。`docs/COMPLETED.md` 的最新一两条锚点，必须能用一条具体 git 提交或一次具体 pytest 输出佐证。
3. **示例必须可零配置跑通**。任何"用户跟着 README 复制粘贴"的代码块，必须在 mock 模式下端到端跑通；改动后必须 `python main.py run <示例>` 至少一次。
4. **已知 bug 与已修 bug 之间要勤更**。每发现一个"文档说有但代码已修"的项目，立刻把文档同步更新；反向同理。
5. **跨文件状态保持一致**。`README.md`、`docs/KNOWN_LIMITS.md`、`docs/IBCI_SYNTAX_REFERENCE.md`、`docs/METADATA_ARCHITECTURE.md` 之间对同一语法/限制/架构立场的描述必须用同一组事实；如不一致，以代码与最近一次 pytest 输出为准。
6. **避免重复声明、单点真理**。一条已完成项写一次（在 `COMPLETED.md`），一条已知限制写一次（在 `KNOWN_LIMITS.md`），一条紧要项写一次（在 `NEXT_STEPS.md`），一条搁置项写一次（在 `PENDING_TASKS.md`）。出现"同一条目在多个文件中以不同状态出现"，立即合并。
7. **新增 AST 字段或侧表前必须先在 `METADATA_ARCHITECTURE.md` 中查证**：禁止"AST 字段 + 侧表"双写真相（同一份语义事实只能有一处可序列化位置）。
8. **重大架构决策必须写 ADR**。新增决策在 `docs/decisions/` 建对应 ADR 文件；已有非正式决策记录（如 `PHASE1_TECHNICAL_DECISIONS.md`）应逐步迁入 ADR 目录。
