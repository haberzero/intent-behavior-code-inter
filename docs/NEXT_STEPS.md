# NEXT_STEPS — 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `docs/PENDING_TASKS.md`；历史归档见 `docs/COMPLETED.md`；
> 已知语言级限制见 `docs/KNOWN_LIMITS.md`。
>
> **最后更新**：2026-05-14（第二轮 PR 关闭 H1/H2/H3/H4/H6；并新增"semantic_v2 全方位评估"章节，给出 Phase A–F 渐进替换路径）

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
- **Intent one-shot 语义重定义**（第三轮）：已完成。`@` / `@!` 现绑定"下一条语句执行窗口"（不再仅限直接 LLM 语句）；VM 侧已实现语句窗口开始安装、结束清理，保证无 LLM 路径不泄漏。覆盖更新：`tests/e2e/test_e2e_intent.py`、`tests/contracts/test_intent_propagation.py`、`tests/compiler/test_pipeline.py`。文档已同步到 `KNOWN_LIMITS` / `IBCI_SYNTAX_REFERENCE` / `INTENT_SYSTEM_DESIGN`。

详见 `docs/COMPLETED.md` 2026-05-14 的对应锚点。

---

## ⚠️ 优先级 P0：semantic_v2 全方位评估结论与下一步指引（H5 扩展为完整路径）

**严重级别**：中（v2 当前并未挂在生产路径上；但是项目长期 roadmap 的核心，且测试 fixture 失效是当前唯一的红色基线）。

> 完整评估报告见本节"全方位评估"小节；下面先给出**当前最紧要**的 P0 与下一步指引（"先把灯绿了再说"原则）。

### 当前 H5（测试 fixture 失效）现象

```
FAILED tests/compiler/test_symbol_collection_pass.py::test_symbol_collection_pass_empty_module
FAILED tests/compiler/test_symbol_collection_pass.py::test_symbol_collection_pass_function_def
FAILED tests/compiler/test_symbol_collection_pass.py::test_symbol_collection_pass_class_def
FAILED tests/compiler/test_symbol_collection_pass.py::test_symbol_collection_pass_variable_assign
FAILED tests/compiler/test_symbol_collection_pass.py::test_symbol_collection_pass_duplicate_definition
TypeError: SpecRegistry.__init__() missing 1 required positional argument: 'axiom_registry'
```

### 根因（已交叉复核确认）

`tests/compiler/test_symbol_collection_pass.py:16` 用旧签名 `SpecRegistry()` 构造 registry；
`core/kernel/spec/registry.py:291` 早已改为 `def __init__(self, axiom_registry: "AxiomRegistry")`，
为必填位置参数。同文件还有**两处累加的字段名误用**：
- `test_symbol_collection_pass.py:23`：`SymbolTableContext(table=symbol_table)` —— 真实字段名是
  `current`（`core/compiler/semantic_v2/metadata/symbol_table.py:29`）。
- `test_symbol_collection_pass.py:66, 93, 118`：`result.context.symbol_table.table` —— 应为 `.current`。

`SpecRegistry` 一旦修好，剩下两类字段名问题会立刻暴露（链式 TypeError）。

参考活体调用：`core/kernel/factory.py:22` 的标准构造路径为 `AxiomRegistry()` + `SpecRegistry(axiom_reg)`；
`tests/kernel/conftest.py:24` 也是同款。

### 最小修复（推荐选项 A，**勿降级 SpecRegistry 签名**）

```python
# tests/compiler/test_symbol_collection_pass.py
from core.kernel.axioms.registry import AxiomRegistry  # 新增
...
def create_test_context(ast_node):
    axiom_reg = AxiomRegistry()
    registry = SpecRegistry(axiom_reg)             # 修 ①
    symbol_table = SymbolTable()
    context = SemanticContext(
        ast=ast_node,
        registry=registry,
        module_name="test_module",
        symbol_table=SymbolTableContext(current=symbol_table),  # 修 ②
        type_environment=TypeEnvironment(),
        metadata=MetadataStore(),
    )
    return context
# 修 ③：把 5 个断言里 .symbol_table.table 改为 .symbol_table.current
```

### 验收

`tests/compiler/test_symbol_collection_pass.py` 5 个用例全绿；`pytest tests/ -q` 整体回到 **658 pass / 0 fail / 9 skip**。**这是恢复"零红基线"的关键且唯一动作**。

### 预估工作量

10–15 分钟实操；外加 1 次全量 `pytest` 复核。

---

## semantic_v2 全方位评估（2026-05-14 交叉复核完成）

> 本节是对用户"全方位评估 semantic v2 的代码情况、设计思路、与 v1 的差距、是否符合 IBCI 静态强类型 / auto 单次推断 / any 兜底等设计、测试修复路径、后续渐进替换方案"指令的回答归档。所有结论均带 v1/v2 文件 + 行号引用，不再重复列详细引用——具体细节查 v2 源码与下面的对照表。

### 一、v2 架构总览（设计意图：好）

v2（`core/compiler/semantic_v2/`）从 v1（`core/compiler/semantic/passes/semantic_analyzer.py`，单文件 ~107KB / 2000+ 行）的 **god-class + 可变实例状态** 模式，重构为：

- **管道 + 过滤器**：6 个独立 Pass 串行（`pipeline.py:115-137`）：
  `SymbolCollection → SymbolResolution → TypeChecking → BindingAnalysis → BehaviorDependency → IntegrityCheck`。
- **不可变上下文**：`SemanticContext`（`context.py:18-105`，`frozen=True` dataclass），通过 `with_*` 系列方法返回新对象。
- **错误即数据**：`PassResult.diagnostics: List[Diagnostic]`（`result.py:88-165`），不抛异常，全程累积。
- **UID 元数据**：`MetadataStore`（`metadata/metadata_store.py:16-175`）用 string UID 作 key，替换 v1 `side_table.py:1-66` 的 `id()` 对象身份方案——**可序列化、能跨进程、不再因 AST 重建失效**。

**这是 IBCI 设计原则上正确的方向**：与"运行时层级 ImmutableArtifact + 内核侧 SafePoint 同步"的整体路径一致。架构选型本身无需推翻。

### 二、与 v1 的真实差距（实质：v2 是骨架，远未完工）

#### 2.1 AST 节点覆盖缺口（结构性缺失）

下列 v1 已有专属 visitor 的节点，v2 **任何 Pass 都没有**对应处理，全部走 `generic_visit`：

`IbGlobalStmt`、`IbSwitch`、`IbCase`、`IbAugAssign`、`IbExprStmt`、`IbImport`、`IbImportFrom`、`IbIntentInfo`、`IbIntentStackOperation`、`IbFilteredExpr`、`IbSlice`、`IbCastExpr`、`IbBoolOp`、`IbIfExp`、`IbRaise`、`IbRetry`、`IbBehaviorInstance`。

合计 **15+ 个语义关键节点**。其中 `IbCastExpr` / `IbFilteredExpr` / `IbSwitch` / `IbCase` 的缺失，意味着任何用到强制转换、AI 过滤、switch 流的程序都会**静默跳过类型检查**。

#### 2.2 IBCI 设计原则符合度（关键问题）

| 设计原则 | v1 实现 | v2 状态 | 问题严重度 |
|---|---|---|---|
| **静态、强类型** | `is_assignable` + 公理驱动 `resolve_op` | TypeChecking 仅做了 `IbAssign` 同名 target 的 `is_assignable`；`IbBinOp` 用硬编码 numeric/str 判断（`type_checking_pass.py:451-461`），未走 axiom | 🟠 影响类型表达力 |
| **`auto` 仅在首次赋值推断** | `_infer_target_type_from_declared`（`semantic_analyzer.py:1085-1112`）：`auto` 锁定首次赋值类型；`any` 永久动态 | **完全未实现**。`type_checking_pass.py:363-366` 留有 `# TODO: 更新符号的返回类型`；`TypeEnvironment.auto_return_accumulator`（`type_environment.py:29`）字段已声明但从未被任何 Pass 写入 | 🔴 核心机制缺失 |
| **`any` 作动态兜底** | `is_dynamic` 区分；`any` 永久不收窄 | 不区分 `any` 与 `auto`，所有未知类型都默认返回 `_any_desc` | 🔴 与 `auto` 缺失同源 |
| **`llm_uncertain` 作 LLM 输出类型** | 在 prelude 注入 + `__assign__` 时按容器规则消解 | `LLM_UNCERTAIN_SPEC` 在 v2 任何 Pass 中 **0 次引用** | 🔴 完全没有 |
| **`func`/`behavior`/`llm` 签名检查** | `visit_IbFunctionDef:683-832` 解析参数/返回类型，构造 callable 签名，回填 class 成员 | 函数注册用 `any → any` 占位（`symbol_collection_pass.py:191-227`）；参数从未被注册为符号；`fn` 变量调用、`CALLABLE_SIG` 结构匹配（D3）、`__call__` 协议——全无 | 🔴 函数体内任何参数引用都会 `SEM_001` |
| **`llmexcept` §9.2 只读作用域** | `SEM_052`（`semantic_analyzer.py:1033-1046`） | 仅检查 target 必须是 IbBehaviorExpr（SEM_040），只读约束**未实现** | 🟠 |
| **`intent_context` 注解 → 行为语句** | `SEM_060` | 实现了（`binding_analysis_pass.py:178-291`），但用错误码 `SEM_050`；`IbIntentInfo` / `IbIntentStackOperation` 内部仍未 visit | 🟡 |
| **lambda 自由变量捕获 / cell_captured_symbols** | `semantic_analyzer.py:1902-2019`：完整自由变量分析 + 写入 cell_captured_symbols | `LambdaCaptureAnalyzer` 收集了自由变量，但**没写回 `MetadataStore.cell_captured_symbols`**；未区分 lambda vs snapshot 捕获模式 | 🟠 影响 VM 帧/闭包 |
| **行为依赖图（dispatch_eligible）** | `_analyze_node` 正确遍历 `IbAssign.value` | **关键 bug**：`behavior_dependency_pass.py:89` 在 `isinstance(node, IbAssign)` 分支里又写 `isinstance(node, IbBehaviorExpr)`——同一对象不可能同时是两个类；`symbol_to_behavior` 永远为空，`llm_deps` 永远空，cycle detection 形同虚设 | 🔴 静默正确性缺陷 |
| **`func_type.return_type` 访问** | 正确 | `type_checking_pass.py:489-490` 访问的是 `func_type.ret`，但 `TypeDef` 实际字段名是 `return_type`，导致 **所有函数调用静默返回 any** | 🔴 静默正确性缺陷 |

#### 2.3 元数据层的结构性 bug

`MetadataStore`（`metadata/metadata_store.py:16-45`）只定义了 6 个字段：
`symbol_bindings, type_bindings, callable_instances, capture_modes, cell_captured_symbols, annotations`。

但 `BindingAnalysisPass.run()`（`binding_analysis_pass.py:54-63`）写入了三个**未声明**字段：
`llmexcept_bindings`、`intent_annotations`、`behavior_metadata`。

**只要 Pass 4 一执行就 `AttributeError`**——这是 v2 整条管线当前根本跑不起来的硬阻塞。

#### 2.4 "不可变"承诺的部分破坏

`SymbolTableContext.define`（`metadata/symbol_table.py:62-74`）注释自承：

> "Note: This mutates the underlying SymbolTable (V1 behavior preserved). For true immutability, would need to copy the entire table tree. **This is a pragmatic compromise for V1 compatibility**."

`BehaviorDependencyPass`（`behavior_dependency_pass.py:39`）明确说"直接写入 AST 节点（V1 的正确设计）"。

> 这两处妥协本身**可以接受**（性能 + 与 v1 兼容），但应当在文档明示，避免让"v2 全不可变"的口号误导后续维护者。

#### 2.5 builtin prelude 未注入

v1 通过 `_init_builtins`（`semantic_analyzer.py:70-97`）在分析前注入内置函数 / 类型 / 常量。v2 的 `ContextBuilder.build()`（`context.py:157-181`）**没有等价步骤**——任何对 `print` / `len` / 内置类型的引用都会 `SEM_001`。

### 三、v2 设计是否合理？结论

**架构选型合理，实现远未完工，且存在 4 处静默正确性 bug**：

✅ 合理：六阶段管线、不可变 Context、UID 元数据、错误即数据、可独立测试每个 Pass。这些都是教科书级正确的编译器架构选择，也契合 IBCI 项目"内核可序列化、SafePoint 同步、Plugin 隔离"的整体方向。

❌ 未达 IBCI 设计承诺：
1. **`auto` 单次推断**和**`any` 永久动态**——这是 IBCI 静态强类型体系的两条根支柱，v2 完全没实现。
2. **`llm_uncertain`** 类型——0 处引用。
3. **函数参数注册 / `fn`-callable / `CALLABLE_SIG` D3 结构匹配**——0 处实现。
4. **`IbCastExpr` 与 `can_convert_from`**——`registry.py:430-435` 注释指出"激活 `can_convert_from` 编译期检查"本来就是 NS-5 待办，v2 也未推进。

❌ 静默正确性 bug（即使现在被 wired in 也会出错）：
1. `behavior_dependency_pass.py:89` 的 isinstance 类型错配 → 依赖图永远空。
2. `type_checking_pass.py:489` `func_type.ret` → 所有 call 返回 any。
3. `MetadataStore` 缺三个字段 → Pass 4 立刻 AttributeError。
4. `TypeEnvironment` 整个组件从未被任何 Pass 写入。

### 四、与生产路径的关系（当前完全隔离）

`grep -rln "semantic_v2" .` 仅命中两处：
- `core/compiler/semantic_v2/` 自身；
- `tests/compiler/test_symbol_collection_pass.py`。

`core/compiler/scheduler.py:9` 仍 `from core.compiler.semantic.passes.semantic_analyzer import SemanticAnalyzer`。**v2 没有任何生产入口，且没有 shadow-mode 对照**。

→ 这是**机会**：可以放心改 v2，绝不会影响 653 个通过的测试；但**长期不接入也意味着永远不会熟**。

### 五、推荐的渐进替换路径（分 6 个阶段，单线推进）

每个阶段都应当：(a) 不破现有 653/9skip/5fail 基线（H5 修后是 658/9/0）；(b) 单独一个或几个 PR 完成；(c) 完成后能立即跑 `pytest tests/compiler/test_*_pass.py`。

#### Phase A — 解锁测试基线（**P0，立即可做，<1 小时**）

- [ ] **A-1**：修 `tests/compiler/test_symbol_collection_pass.py` 三处问题（H5 三连：`SpecRegistry(AxiomRegistry())` / `SymbolTableContext(current=...)` / `.symbol_table.current`）。
- [ ] **A-2**：跑 `pytest tests/` 确认 658 pass / 0 fail。

#### Phase B — 修 v2 自身的"哪怕跑都跑不通"的静默 bug（**P0，0.5–1 天**）

- [ ] **B-1**：`MetadataStore` 添加 `llmexcept_bindings: Dict[str, Any]`、`intent_annotations: Dict[str, Any]`、`behavior_metadata: Dict[str, Any]` 三字段（带 `field(default_factory=dict)`）。
- [ ] **B-2**：修 `behavior_dependency_pass.py:89` 的 isinstance 错配——`isinstance(node, ast.IbBehaviorExpr)` → `isinstance(node.value, ast.IbBehaviorExpr)`。
- [ ] **B-3**：修 `type_checking_pass.py:489` `func_type.ret` → `func_type.return_type`。
- [ ] **B-4**：补 `ContextBuilder.build` 的 builtin prelude 注入（参考 v1 `_init_builtins`）。
- [ ] **B-5**：为这 4 处都补**最小回归用例**到 `test_*_pass.py`。

#### Phase C — 补完核心 IBCI 设计原则（**P0–P1，2–4 天**）

- [ ] **C-1**：`TypeCheckingPass._handle_assign_target` 实现 `auto` 单次锁定 + `any` 永久动态（参照 `semantic_analyzer.py:1094-1112`）。
- [ ] **C-2**：函数参数注册——`SymbolCollectionPass.visit_IbFunctionDef` 遍历 `node.args` 并 `define VariableSymbol`。
- [ ] **C-3**：`fn` 类型推断 + `CALLABLE_SIG` D3 结构匹配（参照 v1 `visit_IbCall`、`visit_IbAssign` 的 fn 分支）。
- [ ] **C-4**：`llm_uncertain` 类型传播——`IbLLMFunctionDef` 与 `@~..~` 表达式的返回标记。
- [ ] **C-5**：`IbBinOp`/`IbUnaryOp`/`IbCompare` 接通公理驱动 `registry.resolve_op`，去掉硬编码。
- [ ] **C-6**：每条都补对应单测。

#### Phase D — 补齐 AST 节点覆盖（**P1，2–3 天**）

按"出现频率从高到低"补全 visitor：

`IbExprStmt` → `IbAugAssign` → `IbFilteredExpr`（bool 上下文绑定）→ `IbCastExpr`（含 `can_convert_from` 激活，与 NS-5 合并）→ `IbSwitch`/`IbCase` → `IbBoolOp`/`IbIfExp` → `IbImport`/`IbImportFrom`（严格导入：要求 Scheduler 注入符号）→ `IbIntentInfo`/`IbIntentStackOperation` → `IbRaise`/`IbRetry`/`IbGlobalStmt`/`IbSlice`。

#### Phase E — Shadow 模式（**P1，1 天**）

- [ ] **E-1**：`SemanticAnalyzer.analyze()` 顶部加一个 `run_v2_shadow=False` 默认参数；启用时 v1 跑完后再让 `create_semantic_pipeline().run(...)` 跑同一份 AST。
- [ ] **E-2**：写 `tests/compiler/test_v2_v1_parity.py`——遍历一组 fixture（来自现有 e2e .ibci 文件 + 玩具样例），断言"v2 在 shadow 模式下产出的错误码集合 ⊆ v1 产出的错误码集合"。允许 v2 漏报但禁止误报。

#### Phase F — 切换 + 移除 v1（**P2，估 1 周，需 Phase E 全绿后**）

- [ ] **F-1**：在 shadow 模式 100% 对齐后，scheduler 切到 v2，v1 设 deprecated。
- [ ] **F-2**：观察 1–2 个周期，无回归后删除 `core/compiler/semantic/`。
- [ ] **F-3**：合并 `CompilationResult` 字段（v1 `side_table` → v2 `MetadataStore`），下游 VM 适配。

### 六、风险与建议

1. **不要急于在 v2 没有 shadow 对照前切到生产**——v2 当前等于"完成度 30% 的骨架 + 4 个静默 bug"，直接切换会大面积破坏 653 个通过的测试。
2. **不要回滚 `SpecRegistry(axiom_registry)` 为可选参数**——这是 H5 的"看起来更省事"诱惑选项；公理 / 规约分层是项目核心，回滚会埋下更深的设计债。
3. **优先补"4 个静默 bug + 测试基线 + 核心设计原则三件套"，再谈节点覆盖**——这是"让 v2 至少能跑能验证"的最小集。
4. **shadow 模式必须先建**——否则后续任何 v2 改动都没有客观验证手段，迟早回到 v1 单体模式的老问题。
5. **每个 Pass 都要有专属单测**——v2 的最大架构卖点就是"Pass 可独立测试"，目前却只有 SymbolCollectionPass 一个测试文件。

### 七、当前 H5 → Phase A 的 actionable checklist

> 本节由后续 agent 直接接力执行；预计 1 个小 PR 关闭。

- [ ] 修 `tests/compiler/test_symbol_collection_pass.py` 三处 fixture（`SpecRegistry(AxiomRegistry())` / `current=` 关键字 / `.current` 访问）。
- [ ] `pytest tests/compiler/test_symbol_collection_pass.py` 5/5 绿。
- [ ] `pytest tests/` 全量 658/9/0。
- [ ] `docs/COMPLETED.md` 新增 H5 修复锚点。
- [ ] 在 `docs/NEXT_STEPS.md` 把 H5 部分缩减为一行存档；把"Phase B"提升为新的 P0 起点。

---

## P1 候选（按优先级排队，单线推进）

> **更新**：上一份 P1 队列中的 H1/H2/H3/H4/H6 均已在 2026-05-14 第二轮 PR 中完成（详见上方"已完成"清单与 `docs/COMPLETED.md` 同日锚点）。本节当前清单是 H5 修复完成之后的下一批候选项。

### P1-V2 semantic_v2 渐进完工（核心长期工程）

参见上面的"semantic_v2 全方位评估 / 五、推荐的渐进替换路径"。**Phase A 完成（H5 修好）后**，Phase B 是当前下一个 P0，Phase C 进入 P1。每个 Phase 应独立 PR。



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
