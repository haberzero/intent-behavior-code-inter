# ARCHITECTURE_REVIEW_2026-05-15 — 回顾性事实核查与一体两面演进报告

> 本文档归档 2026-05-15 与项目所有者的回顾性事实核查对话中产出的**两份完整报告（一体两面）**。
> 文档**完整保留**两份报告原文（不做总结、不做精炼）以避免未来遗忘；后续基于本报告的具体下一步任务进入 `docs/NEXT_STEPS.md`，被阻塞的远期项进入 `docs/PENDING_TASKS.md`。
>
> 产出背景：用户提供了新的历史信息（llmexcept 演进从 try/except 风格 → 同缩进挂靠前一句的语法 → 旧设计曾用独立"node_protection"侧表挂载、导致侧表膨胀 → 最终回退到 AST 字段直接存储），并指出"现有 AST/侧表的大多数细节由智能体产生、人类已难以独立把控"，要求结合 IBCI 设计思路、易用性、亮点重新做一次从编译到运行的全链路回顾，并提交两份"一体两面"的报告。

---

## 0. 对上一轮分析的事实订正（必须先看）

1. **llmexcept 的 AST 绑定**：上一轮我说 "`IbLLMExceptionalStmt.target` 始终是 None、绑定走反向字段 `llmexcept_handler`"——**错了一半**。
   真实状况是：**两路并存的混合方案**：
   - 正则情形（assign / if / return / while 等含行为表达式的语句）：`IbLLMExceptionalStmt` 在 body 中**替换**前一句，并把 `stmt.target = prev_stmt`（在 semantic Pass 3 中写入）。
   - 条件驱动 for 循环情形：`IbLLMExceptionalStmt` **不**进入 body，而是挂在 `IbFor.llmexcept_handler`，`stmt.target = None`。
   这意味着 v2 必须**同时**处理这两条路径，而不是只读一个字段。

2. 你这次给我的关键历史信息也得到了代码佐证：旧设计确曾用一个独立的 `node_protection` 侧表挂载 llmexcept，后来被显式删除（`semantic_analyzer.py` 注释 "C11/P3 已完成"）。也就是说 **"侧表→AST 字段"的反向迁移已经在 IBCI 内部发生过一次**，而且事后看效果是积极的（删除了重定向重写逻辑、消除了一个能把 `node_to_type` 静默覆盖的坑）。这一历史事实直接支撑下面的核心建议。

3. **重复存储确认**：`capture_mode` 同时存在于 `IbAssign.capture_mode`、`IbLambdaExpr.capture_mode`、侧表 `node_capture_mode` 三处；`is_callable_instance` 同时存在于 `IbBehaviorInstance.is_callable_instance` 和侧表 `node_is_callable_instance`。这是上一轮没指出来的关键债务点。

---

## 报告 A — 宏观概述（自然语言，决策视角）

### A.1 IBCI 的本质形态：一条"编译期一次性塑形 + 运行期只读消费"的流水线

把 IBCI 现在的完整从源码到执行的链路抽象一下，它实际上是：

> 源文本 → 词法/语法 → 一棵**结构性 AST** → 语义阶段往这棵 AST 上**追加注解** → 序列化为**扁平的、按 UID 引用的只读产物** → 解释器以 UID 为唯一访问通道运行。

这条流水线的关键性质是：**编译期结束后所有信息都不可改**。这本身已经具备了相当多类似 LLVM/Tree-sitter 的"中间表示就是一切，运行时只是它的消费者"的精神。**这一条主轴是健康的，不需要推翻**。

### A.2 真正的设计债不在 "AST vs 侧表" 的选择上，而在**"同一份信息的多处真相"**

IBCI 走过的演进留下了三种存放语义信息的容器，并行存在：

- **A：AST 节点上的内建字段**（如 behavior 的依赖列表、for 循环挂的异常处理器、lambda 的自由变量列表、行为实例的目标类型名等）
- **B：侧表**（节点→符号、节点→类型、节点→捕获模式、节点→callable 实例标志、节点→位置等）
- **C：分析过程的瞬态内存**（作用域栈、当前类、当前函数返回类型推断缓存等）

历史上这三个容器互相侵占边界：早期"侧表式"路线后来被部分回退到"AST 字段式"（llmexcept 那一次），但回退并不彻底——**至今还有至少两处事实性的"AST 字段 + 侧表 双备份"**（捕获模式、callable 实例标志）。这就是你担心的"元数据膨胀"的真实样子：不是字段数量多，而是**同一个事实有两份副本，且没有统一的写入入口**，新来的智能体看到任何一份都觉得"再加一份保险更稳妥"。

### A.3 v2 文档与 v2 代码之间的承诺差

v2 的重构文档把 "用 UID 元数据完全取代基于对象身份的侧表" 当成主要卖点之一。但事实是：

- 编译期到运行期之间已经存在序列化层，**它早就做了 id→UID 的边界转换**；运行时根本看不到对象引用。
- v2 真正在做的事，是把这层边界转换从"序列化层"**前移到了"语义分析层"**。这有一定好处（每个 Pass 之间也用 UID），但**代价是每次绑定都要拷贝整张字典**——对中型程序就已经是平方级别开销。
- 与此同时 v2 的 "TypeEnvironment" 留了一个 "按节点-约束类索引的约束表" 字段，但**从未被任何 Pass 写入**。这是一个**还没诞生就开始膨胀的元数据口袋**，**强烈建议在写入它之前就删除**——它本身就是把 Python 式"约束求解 + 类型细化"思维偷渡进 IBCI 的入口。

### A.4 IBCI 真正的设计亮点 — 别在 v2 重构中失手

按重要度排序：

1. **行为描述表达式与类型系统强耦合**（auto 锁定、any 兜底、llm_uncertain 作为 LLM 输出的标签）：这是 IBCI 唯一独有的体验。它要求类型系统**保持低灵活性、单次推断**——任何"再推一次"或者"再放宽一点"的改动都直接砸到这块。
2. **基于公理（axiom）的类型/运算调度**：把 `+`、`==`、可调用判定、是否动态等都委托给公理表，而不是访问者里硬编码。这是一种比 LLVM 的 intrinsic 表更轻、但比 Python 的 dunder 表更结构化的设计，**它给你未来支持用户运算符重载留了一条干净的通路**。
3. **意图栈 + 一次性意图窗口**：这是行为系统的另一个独有点。它的核心结构（窗口绑定到下一条语句的执行）已经在 v1 实现得很扎实。
4. **行为依赖图（dispatch_eligible）**：把"这一组 LLM 调用能否并行"作为编译期的判定写进 AST。是一种小而有效的"提前调度信息"，类似 LLVM 用 metadata 标注 nounwind/readonly。

如果 v2 不能复述这四个亮点的语义，就不算"等价替换 v1"。这是验收的根本红线。

### A.5 与成熟技术栈的类比（用来定方向）

- **Tree-sitter 的启示**：AST 应当只承担"程序结构 + 极少量、必然伴随结构的产物"。任何"分析者认为的注解"应当能从结构推回去。IBCI 现在的 `IbBehaviorExpr.llm_deps / dispatch_eligible`、`IbFor.llmexcept_handler` 都满足这个标准——它们是程序的本质属性，不是"分析者顺手记一下"。**结论：这些字段该留在 AST，不要往侧表搬。**
- **LLVM IR 的启示**：除了 IR 本身，LLVM 还有 `Metadata` 系统（命名、可丢弃、带版本）。它的关键设计在于：**元数据**和 **IR 本体** 是两件事，metadata 的丢失不会破坏程序，只是降低优化质量。IBCI 现在的侧表里**混了两类东西**：丢了不影响执行的（位置信息，仅用于诊断），和丢了就崩溃的（节点→符号、节点→类型）。**这两类不应当放进同一个容器**。把它们区分开是 v2 重构最大的一步收益。
- **Rust 的 HIR/MIR 启示**：每一个分析阶段产出一个新的 IR，**新 IR 替换旧 IR**，而不是在旧 IR 上"打补丁式追加字段"。IBCI 现在是 "AST 一直贯穿到运行时"，单 IR 流水线。这其实可以接受（毕竟 IBCI 体量小），但代价就是 AST 字段会随时间不断膨胀。**v2 是一次很好的时机来"内部假装存在两层 IR"**：编译器内部把 AST 看作结构 IR，把"含全部绑定的扁平产物"看作真正的执行 IR——尽管它们当前是用同一组节点表达的。

### A.6 战略建议（决策视角，三选一/三选一/三选一）

| 主题 | 选项 1（保守） | **选项 2（推荐）** | 选项 3（激进） |
|---|---|---|---|
| 元数据模型 | 保持 AST 字段 + 侧表并存，按 metadata 文档继续走 | **明确"AST 即唯一可序列化真相，编译期侧表是一次性查询索引"**——可序列化的语义产物必须出现在 AST，瞬态查询用侧表（不进入产物） | 引入第二层 IR，AST → 装配后的 IR，运行时只看新 IR |
| v2 推进节奏 | 直接 shadow 跑 v1+v2，按 parity 推 | **先把"易用性 + 设计亮点"翻译成一组验收契约（auto 锁定、any 永久、运算符走公理、行为依赖图、意图窗口、llmexcept 双路径），把这组契约作为 v2 的对外承诺，再做 shadow** | 先停 v2，重写整套 IR 后再做 |
| MetadataStore 的命运 | 加更多字段满足 v2 现有 Pass | **缩减为最小集（只放"瞬态、不进产物"的索引），其它语义产出物全部回归 AST** | 整体删除，重写为只在 Pass 间显式传参 |

我推荐三个"选项 2"——它们在一起就是一句话：**"AST 是唯一可被序列化的真相、侧表/MetadataStore 只是编译期的一次性索引、v2 的验收以语言亮点的契约为准、不以代码相似度为准"**。

### A.7 最重要的"不要做"清单

- **不要**继续把 `auto/any/-> auto` 的推断状态做成"约束集合"或"待求解变量"——这是 Python 流派的诱因。
- **不要**给 MetadataStore 再加 `behavior_metadata / annotations` 这种"通用口袋"字段——它会立刻被滥用，相当于把侧表的债换个名字续命。
- **不要**重复存放"捕获模式"和"callable 实例标志"——选一个真相（建议留 AST 字段，丢侧表副本）。
- **不要**忽略 llmexcept 的"双路径绑定"——必须明确这是 AST 上的两个并存通道。
- **不要**让 TypeEnvironment 演化出"按节点-约束键"的字段——这是元数据膨胀的种子。

---

## 报告 B — 具体技术规划（术语 / 代码视角）

> 与 A 报告同一套结论，技术化展开。所有路径都用相对于仓库根的路径表达，命名沿用现有代码。

### B.1 当前从编译到运行时的真实数据流（核查后版本）

1. **Parser** (`core/compiler/parser/`) 产出 AST：节点是 `dataclass(eq=False)`，**用 Python 对象身份**作为编译期内 key。`IbLLMExceptionalStmt` 在此阶段 `target=None`；`IbBehaviorExpr.llm_deps=[]/dispatch_eligible=True` 默认值；`IbLambdaExpr.free_vars=[]/capture_mode` 已被 parser 设置。

2. **Semantic Analyzer** (`core/compiler/semantic/passes/semantic_analyzer.py`) 6 个 Pass，对 AST **就地写入**多种语义产物：
   - `_bind_llm_except` 写入 `IbLLMExceptionalStmt.target` 或 `IbFor.llmexcept_handler`（在 body 列表里做 pop/replace）。
   - `visit_IbFunctionDef/visit_IbAssign/...` 通过 `SideTableManager` 写 `node_to_symbol`、`node_to_type`、`node_is_callable_instance`、`node_capture_mode`、`node_to_loc`。
   - `BehaviorDependencyAnalyzer` 写 `IbBehaviorExpr.llm_deps / dispatch_eligible`。
   - `LambdaCaptureAnalyzer` 写 `IbLambdaExpr.free_vars`，同时往侧表写 `cell_captured_symbols`（UID 集合，跨边界字段）。

3. **CompilationResult** (`core/kernel/blueprint.py`) 是 (module_ast, symbol_table, **五张侧表**) 的简单聚合，内部仍用 `id(node)` 索引。

4. **FlatSerializer** (`core/compiler/serialization/serializer.py`)：递归遍历 AST 与符号表，把每个对象池化到 `node_pool / symbol_pool / scope_pool / type_pool`，键为内容哈希（节点）或稳定字符串（符号、类型）。**这里完成 `id → UID` 的边界转换**——五张侧表统一转为 `Dict[str, str]`，AST 内部嵌套的对象引用（比如 `IbBehaviorExpr.llm_deps` 里的节点引用、`IbFor.llmexcept_handler` 字段）通过 `_process_value` 自动展平为 UID 字符串。

5. **运行时 Interpreter / VM** (`core/runtime/interpreter/interpreter.py`, `core/runtime/vm/handlers.py`)：只与 `artifact_dict` 打交道，访问入口是 `get_side_table(table_name, node_uid)` 与 `get_node_data(node_uid)`。**运行时永远看不到原始 AST 对象**。

> 关键观察：**侧表在产物里就是 5 张 `Dict[str, str]`，不是"对象身份"的延续**。也就是说，"侧表用 id() 索引" 是**纯编译期内部实现细节**，"侧表是 v1 的设计缺陷"这一论断需要被收回——它在运行时已经不是 id() 了。

### B.2 现状中已被验证的设计债（按严重度）

#### B.2.1 双写真相（高）
| 信息 | AST 字段 | 侧表 | 写入者 | 读取者 |
|---|---|---|---|---|
| 捕获模式 | `IbAssign.capture_mode` + `IbLambdaExpr.capture_mode` | `node_capture_mode` | parser + semantic | VM (`handlers.py:1445`) |
| callable 实例 | `IbBehaviorInstance.is_callable_instance` | `node_is_callable_instance` | semantic | VM (`handlers.py:710,1431`) |
| 行为依赖 | `IbBehaviorExpr.llm_deps` / `dispatch_eligible` | — | BehaviorDependencyAnalyzer | VM 调度 |

**结论**：行为依赖那一行是**单一真相**（健康）；前两行是**双写**，必须收敛。建议方向：**保留 AST 字段，删除侧表副本**（与 llmexcept 那次回退方向一致）。

#### B.2.2 v1 → v2 跨边界的语义产物分类（指导 v2 metadata 模型）

把当前所有"语义阶段写入的东西"按性质分为 4 类：

| 类别 | 是否进入运行时产物 | 是否需要 UID 化 | 建议存放位置 |
|---|---|---|---|
| **C1: 结构性产物**（llm_deps, dispatch_eligible, llmexcept 绑定, free_vars, target_type_name, capture_mode） | 是 | 由序列化层自动做 | **AST 字段**（已经如此，保持） |
| **C2: 节点 → 符号绑定**（哪个 IbName 指向哪个 Symbol） | 是 | 是 | **保留为侧表**，但**改名**为 "符号决议表" 以强调含义；不进入 AST（否则需要在 AST 上挂 Symbol 对象） |
| **C3: 节点 → 类型绑定**（每个表达式的静态类型） | 是 | 是 | **保留为侧表**；理由同 C2 |
| **C4: 编译期瞬态**（作用域栈、auto 累积返回类型、llmexcept body 的外层快照名集） | 否 | 否 | **Pass 内部局部变量**，不出 Pass 边界 |

这样切分以后，"侧表" 就只剩 C2/C3 两张表 + 位置表（仅诊断用），结构清晰。**这才是 v2 元数据模型应当瞄准的终态**——而不是当前 v2 那个有 6 个字段（其中 1 个未被填、3 个不存在却被使用）的 `MetadataStore`。

#### B.2.3 v2 `MetadataStore` 的具体调整建议

- **删除**：`capture_modes`、`callable_instances`、`cell_captured_symbols`、`annotations`（这四个要么是 AST 字段的副本，要么是泛用口袋）。
- **保留并明确**：`symbol_bindings: Dict[node_uid, Symbol]`、`type_bindings: Dict[node_uid, IbSpec]`、`loc_bindings: Dict[node_uid, Location]`（用于诊断）。
- **删除**：`TypeEnvironment.constraints`、`TypeEnvironment.generic_instances`（IBCI 静态强类型 + auto 单次锁定，不需要约束表与泛型实例化记账）。
- **保留**：`TypeEnvironment.auto_return_accumulator`（这是 `-> auto` 函数实现的唯一合法瞬态）。
- **每次 bind 不要返回新 store**：上一版 v2 用 `{**self.x, k: v}` 拷整张字典，节点上千就是 O(n²)。改成 mutable，但**只能从 Pass 内部修改**——这等价于 v1 的 SideTableManager，已有方案，不需要重做。

#### B.2.4 v2 `behavior_dependency_pass.py:89` 与 `type_checking_pass.py:489` 两个静默 bug 仍然存在
这两个 bug 在我上一轮就指认了，**事实核查后依然有效**——`func_type.ret` 在 `TypeDef` 上不存在（应为 `return_type`），`isinstance(node, IbBehaviorExpr)` 不可能在 `IbAssign` 分支为真。

#### B.2.5 v2 `BindingAnalysisPass` 的 `IbIntentAnnotation` visitor 字段访问错误
`stmt.op` / `stmt.text` 是 v2 凭空捏造的字段；真实 AST 是 `intent: IbIntentInfo`，应改为读 `stmt.intent.mode` / `stmt.intent.content`。

#### B.2.6 v2 `llmexcept` 绑定路径方向必须修正
v2 当前依赖 `IbLLMExceptionalStmt.target`——这是**parser 阶段的初值**，**还没被 Pass 3 写入**。
两个可选方案：
- **方案 A**：在 v2 中复刻 v1 的 `_bind_llm_except` 流程（替换 prev_stmt / 写 target；条件 for 写 `IbFor.llmexcept_handler`）。**推荐**。
- **方案 B**：把"绑定 llmexcept"这一动作从语义阶段挪到 parser 之后的独立"AST 规整阶段"（结构 IR 化预处理），这样 Semantic 看到的 AST 就已经完成了绑定。**长期更优**，但属于二层 IR 路线，工作量大。

### B.3 序列化层的两个潜在地雷

#### B.3.1 类型 UID 冲突
`serializer._collect_type` 用 `type_{module_path or 'root'}.{name}` 作为 UID（`serializer.py:166`），对结构化 `CALLABLE_SIG`（name 都是 "callable" 或匿名）会塌成同一个 UID。当前未爆是因为 fn 推断少；未来支持 HOF 参数签名匹配（D3）时这是定时炸弹。
**修法**：CALLABLE_SIG 的 UID 改为 `sig_<sha16(return_head + ','.join(param_heads))>`；其它 kind 保持现状。

#### B.3.2 节点内容哈希作为 UID 的"语义重影"问题
`_collect_node` 把节点的所有字段做 JSON 排序后哈希。这意味着两个**语法相同但语义不同的节点**（例如两个 `IbName("x")` 出现在不同作用域）会哈希到**同一个** UID，**然后被侧表共用同一份绑定**。
当前能跑是因为 semantic 写侧表是按 `id()` 写，序列化前每个节点对象的字段不会重复；但**只要哈希恰好相同就会塌**。验证可以快速做：跑一遍现有 e2e 用例，统计 `node_pool` 中"同 UID 对应不同对象集合"的频率。**强烈建议把 UID 改为内容哈希 + 单调计数器后缀**，或直接采用"父节点 UID + 字段路径"作为复合 UID。

### B.4 v2 推进路径（落地版，可被后续 PR 直接挑选）

> 每个阶段独立 PR；以保持 658/9/0 测试基线为前提。

**P0：v2 文档与代码自我矛盾收口**
- [ ] `docs/SEMANTIC_REFACTORING_PLAN.md` 中 "AST 不放分析结果 / MetadataStore 取代侧表 / Context 完全不可变" 三处口号按 `docs/METADATA_ARCHITECTURE.md` 真实立场改写。
- [ ] 在 plan 中新增一节《结构性产物（C1）字段清单》，逐条列出 AST 上的语义字段、何时写、何时读，作为合同。

**P0：v2 阻塞 bug 修复 + 字段收敛**
- [ ] `MetadataStore`：删除 `capture_modes / callable_instances / cell_captured_symbols / annotations`；**不要**新增 `behavior_metadata / llmexcept_bindings / intent_annotations`（让 BindingAnalysisPass 直接把这些产物**写回 AST 字段或写回 symbol_bindings/type_bindings**）。
- [ ] `TypeEnvironment`：删除 `constraints / generic_instances`；只留 `auto_return_accumulator`。
- [ ] 修 `behavior_dependency_pass.py:89` isinstance 错配（`node.value`）。
- [ ] 修 `type_checking_pass.py:489` (`ret → return_type`)。
- [ ] 补 `ContextBuilder.build`：注入 `Prelude` 内置符号（复用 v1 `core/compiler/semantic/passes/prelude.py`，不重写）。
- [ ] 修 `BindingAnalysisPass` 中 `IbIntentAnnotation` 字段访问（`stmt.intent.mode / stmt.intent.content`）。
- [ ] 重写 v2 的 llmexcept 绑定：移植 v1 `_bind_llm_except` 的 body 重写（pop + replace + 写 `target`；for-loop 写 `llmexcept_handler`）。

**P0：消除双写真相**
- [ ] 删除侧表 `node_capture_mode`、`node_is_callable_instance`；改 VM handler 直接读 AST 字段 `IbAssign.capture_mode / IbLambdaExpr.capture_mode`、`IbBehaviorInstance.is_callable_instance`。
- [ ] 一并删除 `SideTableManager` / `CompilationResult` 中对应字段、`FlatSerializer` 中对应分支。
- [ ] 跑 `tests/runtime/test_lambda_*.py` / `tests/contracts/` 验证回归。

**P1：独立的 TypeResolutionPass**
- [ ] 新建 `core/compiler/semantic_v2/passes/type_resolution_pass.py`：处理类继承链展开、方法签名解析、`override` 兼容性、基类未定义检测。
- [ ] 这是后续支持运算符重载、用户自定义可调用、`__from_prompt__` 协议的着力点。

**P1：核心 IBCI 设计原则补全**（每条独立 PR）
- [ ] `auto` 单次锁定（仅在符号首次赋值时把推断结果固定到 `Symbol.spec`，后续禁止再变）。
- [ ] `any` 永久动态（识别声明类型为 `any` 的 Symbol，跳过窄化）。
- [ ] `-> auto` 函数：用 `TypeEnvironment.auto_return_accumulator` 收集 return 语句类型并统一。
- [ ] `IbBinOp / IbUnaryOp / IbCompare` 接通 `registry.resolve_op`，删硬编码。
- [ ] `IbLLMFunctionDef` 与 `@~..~` 返回类型标记 `llm_uncertain` 并参与 str + 容器消解规则。
- [ ] 函数参数 / `fn` 推断 / `CALLABLE_SIG` 结构匹配（D3）。

**P1：AST 节点 visitor 补全**
- [ ] 按上一轮列表补 15+ 缺失 visitor；其中 `IbCastExpr` 同步激活 `can_convert_from`（NS-5），`IbSwitch/IbCase` 进行模式类型检查。

**P1：序列化层加固**
- [ ] 给 CALLABLE_SIG 改 UID 策略（结构哈希）。
- [ ] 评估节点 UID 复合化（父 UID + 字段路径）的成本/收益；若成本可接受则切换。

**P2：Shadow 模式 + parity 测试**
- [ ] `scheduler` 加 `run_v2_shadow=False` 开关；通过后再设默认 True。
- [ ] `tests/compiler/test_v2_v1_parity.py`：对一组 fixture，断言 v2 错误码集合 ⊆ v1 错误码集合，且 type/symbol/llm_deps 关键产物一致。

**P3：切换 + 删 v1**（前提：parity 稳定 ≥ 2 个周期）
- [ ] `scheduler` 切默认 v2、v1 deprecate。
- [ ] 删 `core/compiler/semantic/`，合并 `CompilationResult` 字段。

### B.5 长期方向（可选，记录用）

- **二层 IR 路线**：把"AST 规整阶段"（llmexcept 重排、intent 注解附着等）从 Semantic 中剥离出来，产出 "结构 IR"；Semantic 在结构 IR 上做分析；序列化器输出"执行 IR"。这样 AST 本身可以保持纯 parse 结果，所有"分析者写入的字段"都进入结构 IR，AST 字段不再随时间膨胀。这是 Rust HIR/MIR 类的演化路径。**当前 IBCI 体量下尚不必做**，但若行为依赖图/intent 分析将来还要扩展（例如做 LLM 调用计费/调度优化），这一步几乎不可避免。
- **公理 + 元数据分层 LLVM 化**：把 `IbSpec` 的 metadata 字段（现已用于 specs 静态属性）系统化为类似 LLVM 的 `!metadata` 节点，每条 metadata 都有唯一 owner pass、可丢弃。**作用**：将来加新分析（例如成本估计、副作用标记）时不会再往 AST/侧表/Symbol 上随手加字段。

---

## 一句话最终结论

**IBCI 当前的真正风险不是"v2 没跑起来"，也不是"侧表是否要改 UID"，而是同一份语义事实在 AST 字段、侧表、未来的 MetadataStore 三处反复落地，造成的"信息双写"** ——这一现象在历史上已通过 llmexcept 那次反向迁移得到部分纠正，**v2 的最大机会是把这条纠正贯彻到底**：让 AST 成为唯一被序列化的真相，让侧表/MetadataStore 萎缩成"编译期一次性查询索引"，让 IBCI 的静态强类型、auto 单次锁定、any 兜底、公理调度、行为依赖、意图窗口这六大亮点以**合同**形式被 v2 复现。完成这件事，v2 才算"等价并且更干净地替代 v1"；其它工作（独立 TypeResolutionPass、shadow 测试、激进的二层 IR）都是这条主轴的附属。

---

## 附：本次回顾的核查事实清单（与上一轮分析的差异）

| 主题 | 上一轮表述 | 2026-05-15 核查后表述 | 证据 |
|---|---|---|---|
| llmexcept AST 绑定 | "stmt.target 始终 None，反向走 IbFor.llmexcept_handler" | **双路径**：正则情形 `stmt.target=prev_stmt`；条件 for 情形 `prev_stmt.llmexcept_handler=stmt`，stmt.target 保持 None | `core/compiler/semantic/passes/semantic_analyzer.py:235-285` |
| 侧表本质 | "侧表用 id()，是 v1 的设计缺陷" | **运行时产物里侧表是 5 张 `Dict[str, str]`**，id() 仅是编译期实现细节；真正问题是"双写真相"，不是"侧表存在" | `core/compiler/serialization/serializer.py:74-98` |
| 双写真相 | 未指认 | `capture_mode` 三处 / `is_callable_instance` 双处 | `core/kernel/ast.py:185, 419-420, 463-472`、`core/compiler/semantic/passes/side_table.py:19-20`、`core/runtime/vm/handlers.py:710-712, 1431, 1445` |
| 旧"node_protection"侧表 | 不知道存在 | 已确认存在过；C11/P3 已删除——历史上"侧表 → AST 字段"反向迁移已发生一次 | `core/compiler/semantic/passes/semantic_analyzer.py` 注释 "C11/P3 已完成" |
| TypeEnvironment.constraints | 未指认 | "尚未被任何 Pass 写入"的元数据口袋，建议在写入前删除 | `core/compiler/semantic_v2/metadata/type_environment.py` |
| PT-4.6 (llmexcept 快照 dunder 协议) | 文档列为待办 | **已实现**用户 `__snapshot__`/`__restore__` 协议，文档滞后 | `core/runtime/interpreter/llm_except_frame.py:189-197, 285-297, 299-304`；`core/runtime/objects/deep_clone.py:50-74` |
