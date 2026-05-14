# NEXT_STEPS — 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `docs/PENDING_TASKS.md`；历史归档见 `docs/COMPLETED.md`；
> 已知语言级限制见 `docs/KNOWN_LIMITS.md`。
>
> **最后更新**：2026-05-14（基于全量事实回顾 + 试用探查；前次"P0-A/B/C/D 测试基线红线"
> 描述与真实代码状态严重不符，已重写）

---

## 当前测试基线（每次开新分支前必须复跑确认）

```bash
python -m pytest tests/ -q --tb=no --no-header
```

**2026-05-14 实测结果**（本 PR 完成 H1/H2/H3/H4 后）：`653 passed, 9 skipped, 5 failed`。
唯一真实失败：`tests/compiler/test_symbol_collection_pass.py` 共 5 个用例
（构造 `SpecRegistry()` 时未传新引入的必填参数 `axiom_registry`，详见下方 H5）。

> 这与前几版 `NEXT_STEPS.md` 中"88 contracts 用例 / 5 plugin 用例 / 25 meta 违规 / example 04 第 1 段崩溃"
> 等"P0-A..D"红线**完全不符**。复跑 `tests/contracts/`、`tests/runtime/test_plugin_implementations.py`、
> `tests/meta/` 全部绿（140/18/3 pass）；`examples/01_getting_started/04_mock_and_llmexcept.ibci`
> 完整执行 7 段。前述 P0 清单为旧文档残留，已统一删除。

---

## ✅ 已完成（本 PR / 2026-05-14 第二轮）

- **H1**（P0，异常跨函数边界类型降级）：已修。`core/runtime/vm/handlers.py::vm_handle_IbCall` 现在让 `ThrownException` 直通，只 wrap 真正的 Python 异常。新增契约 `tests/e2e/test_e2e_exceptions.py::TestExceptionAcrossFunctionBoundary`（4 用例）。
- **H2**（P1-B，import 必须居首）：已修。scheduler 的 `parse_imports_only` 现在过非 import token 后继续扫描，misplaced import 命中既有的 `DEP_003 DEP_INVALID_IMPORT_POSITION`（错误信息也更具体）。新增 `tests/compiler/test_import_position.py`（8 用例）。
- **H3**（P1-A，`ihost.run_isolated` 路径解析）：已修。`HostService._resolve_isolated_path` 在路径相对时基于 `execution_context.get_entry_dir()` 解析，绝对路径直通。新增 `tests/e2e/test_e2e_multi_interpreter.py::TestRunIsolatedPathRelativeToEntryDir`（2 用例）。
- **H4**（P1-C，零配置示例）：已修。`examples/01_getting_started/{01_hello_world,02_intent_demo,03_flow_control_and_behavior}.ibci` 现在用 `file.exists("./api_config.json")` 探测，缺失时自动切到 `ai.set_config("TESTONLY","TESTONLY","TESTONLY")` mock 模式。三个示例都已在零配置下端到端跑通。
- **H6**（README typo）：上轮已修。

详见 `docs/COMPLETED.md` 2026-05-14 的两条锚点。

---

## ⚠️ 优先级 P0：semantic_v2 SymbolCollectionPass 测试 fixture 失效（H5，真实 P0）

**严重级别**：中。Phase 3 测试验证流程的实际阻塞点。

### 现象

```
FAILED tests/compiler/test_symbol_collection_pass.py::test_symbol_collection_pass_empty_module
FAILED tests/compiler/test_symbol_collection_pass.py::test_symbol_collection_pass_function_def
FAILED tests/compiler/test_symbol_collection_pass.py::test_symbol_collection_pass_class_def
FAILED tests/compiler/test_symbol_collection_pass.py::test_symbol_collection_pass_variable_assign
FAILED tests/compiler/test_symbol_collection_pass.py::test_symbol_collection_pass_duplicate_definition
TypeError: SpecRegistry.__init__() missing 1 required positional argument: 'axiom_registry'
```

### 根因

`core/kernel/spec/registry.py` 的 `SpecRegistry.__init__(self, axiom_registry)` 在某次（已合入 main 的）改动中把 `axiom_registry` 从可选变为必填位置参数；但 `tests/compiler/test_symbol_collection_pass.py:16` 的 `create_test_context()` 仍按旧签名 `SpecRegistry()` 调用。

### 修复方向

- 选项 A（推荐）：在测试 fixture 中显式构造 `AxiomRegistry()` 实例传入，与生产路径一致。
- 选项 B：把 `axiom_registry` 改回可选并在缺省时构造空 registry。可能掩盖真实问题，**不推荐**。

### 验收

`tests/compiler/test_symbol_collection_pass.py` 5 个用例全绿；`pytest tests/ -q` 整体回到 658 pass / 0 fail。

### 预估工作量

10 分钟。

---

## P1 候选（按优先级排队，单线推进）

> **更新**：上一份 P1 队列中的 H1/H2/H3/H4/H6 均已在 2026-05-14 第二轮 PR 中完成（详见上方"已完成"清单与 `docs/COMPLETED.md` 同日锚点）。本节当前清单是 H5 修复完成之后的下一批候选项。

### P1-Z idbg.last_llm() 与 MOCK:SEQ 时序一致性核查（H7）

`examples/01_getting_started/06_enum_switch_with_llm.ibci` 输出显示 `MOCK 情感 = SAD` 但 `idbg last_llm.response = HAPPY`，存在游标推进一拍偏差。

**动作**：先用最小用例复现 `MOCK:SEQ` 与 `idbg.last_llm()` 的取值顺序；判断是 demo 写法问题还是 `idbg` 语义不清。如属后者，在 `docs/IBCI_SYNTAX_REFERENCE.md` 的 `idbg` 章节锁定语义。

**预估**：复现 1 小时；定性后再决定修复或文档化。

---

## P2 候选（背景项；与 P0/P1 不抢资源）

### P2-A semantic_v2 测试验证 (Phase 3)

semantic_v2 的 6 个 Pass 代码实现已完成（共 ~1929 行），架构已优化并文档化（详见 `docs/SEMANTIC_REFACTORING_PLAN.md` 与 `docs/METADATA_ARCHITECTURE.md`）。在 P0（H5）修复后，可正式进入 Phase 3：

**Task 1**：创建 `tests/compiler/semantic_v2/` 单元测试 + 集成测试（每个 Pass 独立 + 完整管道）。**目标**：20 单测 + 10 集成测试。  
**Task 2**：实现 `tools/validate_semantic_v2.py` 自动化对比工具，对比维度=符号表 / 类型绑定 / 错误信息 / 元数据。  
**Task 3**：用现有 V1 测试套件做回归比对，记录差异。  
**成功指标（2 周）**：30+ 测试通过，V1/V2 对比工具可运行。

### P2-B `intent_context.push()` 静默无效陷阱编译期警告（沿用旧 P1-B）

`intent_context.push("X")` 在没有 `use(ctx)` 时是 no-op（详见 `docs/KNOWN_LIMITS.md §十八`），但编译期不告警；用户极易踩坑。

**动作**：在 `semantic_analyzer` 中对 `IbCall(method='push'|'pop'|'merge'|'combine'|'clear')` 且 receiver 为类静态调用（非局部 `intent_context` 变量）的形态发出 SEM 警告。低风险，单点改动。

### P2-C NS-5 编译期类型转换检查（激活 `can_convert_from`）

技术路径已在前版 `NEXT_STEPS.md` NS-5 详细记录；保留为优先级 P3 背景项。实施前需：先评估对 `tests/` 套件的破坏面，再决定是否动手。

### P2-D 已知设计取向项（参考性低优先）

- 嵌套 llmexcept 内 retry 计数器的"每次外层 retry 是否重置"语义在 `docs/INTENT_SYSTEM_DESIGN.md` / `docs/ARCH_DETAILS.md` 中明文锁定。  
- `@-` 在按内容/标签移除不存在意图时的 no-op 行为在 `docs/INTENT_SYSTEM_DESIGN.md §4.4` 明文锁定。  
- `__to_prompt__` 在容器嵌套（list/dict 内含用户对象）插值时的递归展开规则在 `docs/IBCI_SYNTAX_REFERENCE.md §6 / §10` 写出契约。

---

## 当前主线完成情况（保持）

类型系统 M1–M5、VM CPS 主线、intent 系统 OOP 化（NS-2 全部 4 步）、LLM 调用路径合并入 CPS 调度循环（NS-1）、lambda/snapshot/behavior 跨帧 EC 边界（NS-3）、intent_context 高级 OOP 场景（PT-2.1）、IbIntentContext 序列化/反序列化（PT-2.2）、`_evaluate_segments` CPS 化、PT-1.2（llmexcept 错误历史）、PT-1.3（llmexcept 嵌套深度限制）、PT-3.3（`idbg.protection_map()`）、NS-4（`str + llm_uncertain` 收紧）、NS-6（链式下标）、NS-7（tuple 位置类型标注）均已完成。

**2026-05-14 第二轮 PR**：H1（异常跨函数边界类型降级）、H2（import 位置错误诊断）、H3（ihost 路径相对入口目录）、H4（示例零配置 fallback）、H6（README typo）一并完成；详见 `docs/COMPLETED.md` 同日两条锚点。

**当前主线（VM / Intent / llmexcept / 类型系统骨架）的内核能力没有新的 P0 开放项**。本周期剩余的真实 P0 仅有：

1. semantic_v2 测试 fixture 修复（H5）

---

## 工作规则

- **每次开新分支前**，先复跑 `python -m pytest tests/ -q --tb=no --no-header`，把当前 pass/fail 计数写在 PR 描述里，不预设上一份文档里的数字。
- 同一时刻只主推一项 P0 任务（或一项 P1）；其余项保留待选。
- 任何改动公理层公约或语义错误集的任务，需在分支早期跑全量 pytest 评估破坏面。
- 每项完成后，把摘要追加到 `docs/COMPLETED.md`（极简时间线），并把对应条目从本文件移除。
- 出现新的紧要项时，按"先评估优先级、再决定是否替换 P0"原则操作。
- **本文件不冻结具体测试通过数字**——任何"X 测试通过"的表述都必须附运行命令或日期锚点，避免下一个智能体把陈旧数字当作真实状态。

---

## 维护守则（写给后续智能体与人类维护者）

下述守则源于 2026-05-14 全量事实回顾过程中暴露出的几次"文档幻觉"教训：

1. **先复跑、后下结论**。任何关于"测试基线红线 / P0 未通过 / 88 用例失败"的表述，必须以"附完整 pytest 输出 + 日期 + 分支"的方式说服读者；否则视为待核查。
2. **不要相信"昨日完成"的总结**。`docs/COMPLETED.md` 的最新一两条锚点，必须能用一条具体 git 提交或一次具体 pytest 输出佐证。本轮发现 2026-05-13 "Phase 2 完成 + 测试基线 Full pass" / "88 contracts 失败 + 5 plugin 失败 + 25 meta 违规" 两份**互相矛盾**的描述同时存在，皆与代码事实不符。
3. **示例必须可零配置跑通**。任何"用户跟着 README 复制粘贴"的代码块，必须在 mock 模式下端到端跑通；改动后必须 `python main.py run <示例>` 至少一次。
4. **已知 bug 与已修 bug 之间要勤更**。每发现一个"文档说有但代码已修"的项目（如 Enum Bug #3），立刻把文档同步更新；反向（代码有 bug 但文档没记）同理。
5. **跨文件状态保持一致**。`README.md`、`docs/KNOWN_LIMITS.md`、`docs/IBCI_SYNTAX_REFERENCE.md` 三处对同一语法/限制的描述必须用同一组事实；如不一致，以代码与最近一次 pytest 输出为准。
6. **避免重复声明、单点真理**。一条已完成项写一次（在 `COMPLETED.md`），一条已知限制写一次（在 `KNOWN_LIMITS.md`），一条紧要项写一次（在 `NEXT_STEPS.md`）。出现"同一条目在多个文件中以不同状态出现"，立即合并。
