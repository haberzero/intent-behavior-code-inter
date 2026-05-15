# NEXT_STEPS — 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `docs/PENDING_TASKS.md`；历史归档见 `docs/COMPLETED.md`；
> 已知语言级限制见 `docs/KNOWN_LIMITS.md`；架构演进方向见 `docs/ARCHITECTURE_REVIEW_2026-05-15.md`。
>
> **最后更新**：2026-05-15（基于 2026-05-15 回顾性事实核查报告重写——`docs/ARCHITECTURE_REVIEW_2026-05-15.md`）

---

## 当前测试基线（每次开新分支前必须复跑确认）

```bash
python -m pytest tests/ -q --tb=no --no-header
```

**2026-05-14 实测结果**：`653 passed, 9 skipped, 5 failed`。
唯一真实失败：`tests/compiler/test_symbol_collection_pass.py` 共 5 个用例（H5，详见下方）。
本周期前几版 NEXT_STEPS 中"P0-A..D 红线"皆与代码事实不符，已统一删除。

---

## ⚠️ 当前 P0：semantic_v2 测试基线恢复（H5）

**严重级别**：中（v2 当前并未挂在生产路径上；但是项目长期 roadmap 的核心，且测试 fixture 失效是当前唯一的红色基线）。

### 现象

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
为必填位置参数。同文件还有两处累加的字段名误用：
- `test_symbol_collection_pass.py:23`：`SymbolTableContext(table=symbol_table)` —— 真实字段名是
  `current`（`core/compiler/semantic_v2/metadata/symbol_table.py:29`）。
- `test_symbol_collection_pass.py:66, 93, 118`：`result.context.symbol_table.table` —— 应为 `.current`。

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

`tests/compiler/test_symbol_collection_pass.py` 5 个用例全绿；`pytest tests/` 整体回到 **658 pass / 0 fail / 9 skip**。**这是恢复"零红基线"的关键且唯一动作**。

### 预估工作量

10–15 分钟实操；外加 1 次全量 `pytest` 复核。

---

## ⏭ 下一个 P0：双写真相收敛（H5 完成后立刻开工）

> 来源：`docs/ARCHITECTURE_REVIEW_2026-05-15.md` 报告 B 章节 B.2.1 / B.4。

历史上"侧表 → AST 字段"反向迁移已经发生过一次（llmexcept 的 `node_protection` 侧表删除）。当前仍有两处明确的"AST 字段 + 侧表"双写：

| 信息 | AST 字段 | 侧表 | 处理方向 |
|---|---|---|---|
| 捕获模式 | `IbAssign.capture_mode` + `IbLambdaExpr.capture_mode` | `node_capture_mode` | **删侧表，留 AST 字段** |
| callable 实例 | `IbBehaviorInstance.is_callable_instance` | `node_is_callable_instance` | **删侧表，留 AST 字段** |

### 任务

- [ ] 删除 `core/compiler/semantic/passes/side_table.py` 中的 `node_capture_mode` / `node_is_callable_instance` 字段及对应 setter/getter。
- [ ] 同步删除 `core/kernel/blueprint.py::CompilationResult` 中两个字段。
- [ ] 同步删除 `core/compiler/serialization/serializer.py` 中 `remaped_node_capture_mode` / `remaped_node_is_callable_instance` 两段分支以及 `side_tables` 输出对应 key。
- [ ] 改 `core/runtime/vm/handlers.py:710-712, 1431, 1445`：直接从 `node_data["capture_mode"]` / `node_data["is_callable_instance"]` 读取（AST 字段在序列化时已经写入 `node_data`）。
- [ ] 跑 `tests/runtime/test_lambda_*.py` 与 `tests/contracts/` 验证回归。

### 验收

`pytest tests/` 仍为 658/9/0；同时新增最小契约用例 `tests/contracts/test_no_redundant_side_tables.py`，断言序列化产物 `side_tables` 字典中不再含上述两个 key。

### 预估工作量

1–2 小时实操；半小时复核。

---

## ⏭ 后续 P0：v2 阻塞 bug + MetadataStore 字段收敛

> 来源：`docs/ARCHITECTURE_REVIEW_2026-05-15.md` 报告 B 章节 B.2.3 / B.4。

H5 + 双写收敛完成后，v2 才有"独立可运行"的基础。本步是把 v2 静默 bug 一次性收口，并把 `MetadataStore` 字段结构与 `docs/METADATA_ARCHITECTURE.md` 真实立场对齐。

### 任务

- [ ] **修四个静默 bug**：
  - `core/compiler/semantic_v2/passes/behavior_dependency_pass.py:89`：把 `isinstance(node, IbBehaviorExpr)`（在 `IbAssign` 分支内）改为 `isinstance(node.value, IbBehaviorExpr)`。
  - `core/compiler/semantic_v2/passes/type_checking_pass.py:489`：`func_type.ret` → `func_type.return_type`（与 `TypeDef` 实际字段对齐）。
  - `core/compiler/semantic_v2/passes/binding_analysis_pass.py`：`IbIntentAnnotation` visitor 改读 `stmt.intent.mode` / `stmt.intent.content`（删除对捏造字段 `stmt.op` / `stmt.text` 的引用）。
  - `core/compiler/semantic_v2/context.py::ContextBuilder.build`：注入 builtin prelude（直接 import `core/compiler/semantic/passes/prelude.py` 现有实现）。
- [ ] **`MetadataStore` 字段收敛**（`core/compiler/semantic_v2/metadata/metadata_store.py`）：
  - 删除：`capture_modes`、`callable_instances`、`cell_captured_symbols`、`annotations`（均为 AST 字段副本或通用口袋）。
  - **不要**新增 `behavior_metadata` / `llmexcept_bindings` / `intent_annotations`；改为让 BindingAnalysisPass 把结果**写回 AST 字段或 symbol_bindings/type_bindings**。
  - 保留并明确：`symbol_bindings: Dict[str, Symbol]` / `type_bindings: Dict[str, IbSpec]` / `loc_bindings: Dict[str, Location]`。
- [ ] **`TypeEnvironment` 字段收敛**（`core/compiler/semantic_v2/metadata/type_environment.py`）：
  - 删除：`constraints`、`generic_instances`（IBCI 单次推断 + 静态强类型，不需要约束求解记账）。
  - 保留：`auto_return_accumulator`（`-> auto` 函数唯一合法瞬态）。
- [ ] **`MetadataStore` bind 操作改 mutable**：删除 "每次 bind 拷整张字典" 的反模式（O(n²)），改为 Pass 内部 mutable in-place 更新——这等价于 v1 SideTableManager 的成熟方案，可直接复用。
- [ ] **复刻 `_bind_llm_except` 到 v2**：v2 当前依赖 `IbLLMExceptionalStmt.target`，但 parser 阶段该字段为 None；v2 必须在适当 Pass 中**显式做 body 重写**——正则情形把 `stmt.target=prev_stmt` 并 pop/replace；条件 for 情形写 `prev_stmt.llmexcept_handler=stmt` 并保持 `stmt.target=None`、不入 body。**两路并存**。
- [ ] 每条 bug 修复都补到 `tests/compiler/semantic_v2/test_*_pass.py`（按 Pass 分文件）的最小回归用例。

### 验收

- `tests/compiler/semantic_v2/` 下每个 Pass 至少 1 个独立回归用例覆盖以上修复。
- `pytest tests/` 仍为 658/9/0（v2 仍未挂在 scheduler 主路径上）。

---

## P1 候选（按优先级排队，单线推进）

> P1 队列源于 `docs/ARCHITECTURE_REVIEW_2026-05-15.md` 报告 B 章节 B.4。

### P1-A 文档与 v2 自我矛盾收口（轻量）

- [ ] `docs/SEMANTIC_REFACTORING_PLAN.md` 中"AST 不放分析结果"等口号改写为与 `docs/METADATA_ARCHITECTURE.md` 真实立场一致（结构性产物保留在 AST，元数据存放符号/类型/位置绑定）。
- [ ] 在 plan 中新增《结构性产物（C1）字段清单》：列出 AST 字段、何时写、何时读，作为 v2 与 v1 的契约。

### P1-B 核心 IBCI 设计原则补全（每条独立 PR）

- [ ] `auto` 单次锁定（仅在符号首次赋值时把推断结果固定到 `Symbol.spec`，后续禁止再变）。
- [ ] `any` 永久动态（识别声明类型为 `any` 的 Symbol，跳过窄化）。
- [ ] `-> auto` 函数：用 `TypeEnvironment.auto_return_accumulator` 收集 return 语句类型并统一。
- [ ] `IbBinOp / IbUnaryOp / IbCompare` 接通 `registry.resolve_op`，删硬编码。
- [ ] `IbLLMFunctionDef` 与 `@~..~` 返回类型标记 `llm_uncertain` 并参与 str + 容器消解规则。
- [ ] 函数参数 / `fn` 推断 / `CALLABLE_SIG` 结构匹配（D3）。

### P1-C AST 节点 visitor 补齐（v2）

按出现频率从高到低补全：`IbExprStmt` → `IbAugAssign` → `IbFilteredExpr` → `IbCastExpr`（含 `can_convert_from` 激活，与 NS-5 合并）→ `IbSwitch/IbCase` → `IbBoolOp/IbIfExp` → `IbImport/IbImportFrom` → `IbIntentInfo/IbIntentStackOperation` → `IbRaise/IbRetry/IbGlobalStmt/IbSlice`。

### P1-D 序列化层加固

- [ ] CALLABLE_SIG UID 策略改为结构哈希（`sig_<sha16(return_head + ','.join(param_heads))>`），避免与未来 D3 HOF 参数匹配场景的 UID 塌缩。
- [ ] 评估节点 UID 复合化（父 UID + 字段路径）的成本/收益；若可接受则切换。

### P1-E 独立 TypeResolutionPass（v2）

- [ ] 新建 `core/compiler/semantic_v2/passes/type_resolution_pass.py`：处理类继承链展开、方法签名解析、`override` 兼容性、基类未定义检测。
- [ ] 为后续用户运算符重载（PT-4.5）、可调用类实例一致性（PT-4.2）、`__from_prompt__` 协议铺路。

### P1-Z idbg.last_llm() 与 MOCK:SEQ 时序一致性核查（H7）

`examples/01_getting_started/06_enum_switch_with_llm.ibci` 输出显示 `MOCK 情感 = SAD` 但 `idbg last_llm.response = HAPPY`，存在游标推进一拍偏差。
**动作**：先用最小用例复现 `MOCK:SEQ` 与 `idbg.last_llm()` 的取值顺序；判断是 demo 写法问题还是 `idbg` 语义不清。如属后者，在 `docs/IBCI_SYNTAX_REFERENCE.md` 的 `idbg` 章节锁定语义。

---

## P2 候选（背景项；与 P0/P1 不抢资源）

### P2-A v2 Shadow 模式与 parity 测试

- [ ] `scheduler` 加 `run_v2_shadow=False` 开关；启用时 v1 跑完后让 v2 跑同一份 AST。
- [ ] 新增 `tests/compiler/test_v2_v1_parity.py`：断言"v2 在 shadow 模式下产出的错误码集合 ⊆ v1 产出的错误码集合"，并对一组 fixture 比对关键产物（type/symbol/llm_deps）一致。允许 v2 漏报但禁止误报。

### P2-B `intent_context.push()` 静默无效陷阱编译期警告

`intent_context.push("X")` 在没有 `use(ctx)` 时是 no-op（详见 `docs/KNOWN_LIMITS.md §十八`），编译期不告警；用户极易踩坑。
**动作**：在 `semantic_analyzer` 中对 `IbCall(method='push'|'pop'|'merge'|'combine'|'clear')` 且 receiver 为类静态调用（非局部 `intent_context` 变量）的形态发出 SEM 警告。低风险，单点改动。

### P2-C NS-5 编译期类型转换检查（激活 `can_convert_from`）

技术路径已记录；保留为低优先背景项。实施前需先评估对 `tests/` 套件的破坏面，再决定动手。

### P2-D 已知设计取向项（参考性低优先）

- 嵌套 llmexcept 内 retry 计数器的"每次外层 retry 是否重置"语义在 `docs/INTENT_SYSTEM_DESIGN.md` / `docs/ARCH_DETAILS.md` 明文锁定。
- `@-` 在按内容/标签移除不存在意图时的 no-op 行为在 `docs/INTENT_SYSTEM_DESIGN.md §4.4` 明文锁定。
- `__to_prompt__` 在容器嵌套（list/dict 内含用户对象）插值时的递归展开规则在 `docs/IBCI_SYNTAX_REFERENCE.md §6 / §10` 写出契约。

---

## P3 候选（远景，暂搁置；详见 PENDING_TASKS）

- v2 切换 + v1 删除（前提：P2-A parity 稳定 ≥ 2 个周期）。
- 二层 IR 路线（结构 IR + 执行 IR），见 `docs/ARCHITECTURE_REVIEW_2026-05-15.md` 报告 B 章节 B.5。
- 公理 + 元数据 LLVM 化（命名、可丢弃、带版本的 `!metadata` 系统）。

---

## 工作规则

- **每次开新分支前**，先复跑 `python -m pytest tests/ -q --tb=no --no-header`，把当前 pass/fail 计数写在 PR 描述里，不预设上一份文档里的数字。
- 同一时刻只主推一项 P0 任务（或一项 P1）；其余项保留待选。
- 任何改动公理层公约或语义错误集的任务，需在分支早期跑全量 pytest 评估破坏面。
- 每项完成后，把摘要追加到 `docs/COMPLETED.md`（极简时间线），并把对应条目从本文件移除。
- 出现新的紧要项时，按"先评估优先级、再决定是否替换 P0"原则操作。
- **本文件不冻结具体测试通过数字**——任何"X 测试通过"的表述都必须附运行命令或日期锚点。

---

## 维护守则

下述守则源于 2026-05-14 / 2026-05-15 全量事实回顾过程中暴露出的几次"文档幻觉"教训：

1. **先复跑、后下结论**。任何关于"测试基线红线 / P0 未通过"的表述，必须以"附完整 pytest 输出 + 日期 + 分支"的方式说服读者；否则视为待核查。
2. **不要相信"昨日完成"的总结**。`docs/COMPLETED.md` 的最新一两条锚点，必须能用一条具体 git 提交或一次具体 pytest 输出佐证。
3. **示例必须可零配置跑通**。任何"用户跟着 README 复制粘贴"的代码块，必须在 mock 模式下端到端跑通；改动后必须 `python main.py run <示例>` 至少一次。
4. **已知 bug 与已修 bug 之间要勤更**。每发现一个"文档说有但代码已修"的项目，立刻把文档同步更新；反向同理。
5. **跨文件状态保持一致**。`README.md`、`docs/KNOWN_LIMITS.md`、`docs/IBCI_SYNTAX_REFERENCE.md`、`docs/METADATA_ARCHITECTURE.md`、`docs/SEMANTIC_REFACTORING_PLAN.md` 之间对同一语法/限制/架构立场的描述必须用同一组事实；如不一致，以代码与最近一次 pytest 输出为准。
6. **避免重复声明、单点真理**。一条已完成项写一次（在 `COMPLETED.md`），一条已知限制写一次（在 `KNOWN_LIMITS.md`），一条紧要项写一次（在 `NEXT_STEPS.md`）。出现"同一条目在多个文件中以不同状态出现"，立即合并。
7. **新增 AST 字段或侧表前必须先在 `METADATA_ARCHITECTURE.md` 与 `ARCHITECTURE_REVIEW_2026-05-15.md` 中查证**：禁止"AST 字段 + 侧表"双写真相（同一份语义事实只能有一处可序列化位置）。
