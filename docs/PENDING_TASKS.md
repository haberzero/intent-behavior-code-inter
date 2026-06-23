# PENDING_TASKS — 阻塞 / 待前置任务的未来规划

> 本文档记录**暂时搁置但经过验证仍有有效性的规划**——每项都有明确的阻塞原因或前置条件。
> 当前最紧要项见 `docs/NEXT_STEPS.md`；已完成事项见 `docs/COMPLETED.md`。
>
> **最后更新**：2026-06-24（全量分析体检后重构：新增架构/文档/测试改善项 §五/§六/§七/§八，更新协程与 PT-4.7 条目，新增 Phase 3 决策矛盾记录 §六）
>
> **阅读指南**：
> - 标为 `[P1]` 的条目：前置条件已满足，可由 `NEXT_STEPS.md` 随时提升为当前任务
> - 标为 `[P2]`/`[P3]` 的条目：有明确前置链，需按序解锁
> - 标为 `[VISION]` 的条目：远期愿景，当前无明确用户需求推动
> - 标为 `[DESIGN-DEBT]` 的条目：已有部分基础设施但存在未解决的设计冲突
> - 标为 `[SHELVED]` 的条目：明确搁置，有独立文档记录设计思路
> - 标为 `[BLOCKED]` 的条目：因决策矛盾或前置未完成而阻塞

---

## 一、Semantic Pipeline 后续演进

### PT-SEM-1　生产就绪化 [P2 — 见 NEXT_STEPS 指针]

> 本条目的完整规划以此处为准；NEXT_STEPS 中仅保留指针，避免双重列出（遵守单点真理规则）。

**前置条件**: Semantic 4-Phase pipeline 已稳定运行 ✅（`create_semantic_pipeline()` 在 `core/compiler/semantic/pipeline.py:115-139`）+ NEXT_STEPS P0 基线修复完成

**现状核查**（2026-05-28）：
- Pipeline 作为唯一编译期分析路径已稳定运行，无回退开关
- 4 个 Phase（SymbolPhase → TypePhase → BindingPhase → IntegrityPhase）均有对应 Pass 子步骤
- `PassOutput` frozen dataclass + `MetadataStore.from_outputs()` 合并产物路径已就绪
- **多模态相关**：`TypeCheckingPass` 对多模态类型无特殊处理（by-design），`SymbolResolutionPass` 通过 registry 查询无需修改

**具体待做**：
1. **错误信息优化**：当前 `SEM_xxx` 错误码附带的消息偏技术化（"symbol not found in scope"），需转化为用户友好表述（"变量 'x' 在此位置尚未声明"）
2. **诊断工具**：为符号表、类型绑定、行为依赖图提供可视化导出（JSON/dot 格式），便于开发者调试复杂脚本
3. **性能基准**：建立编译时间基准测试（针对 100+ 行脚本），确保后续改动不引入回归
4. **CI/CD 集成**：语义分析测试套件纳入 CI 流水线自动运行

**预估工作量**: 15-20 小时

---

### PT-SEM-2　CompilationResult 字段精简 [P3]

**前置条件**: PT-SEM-1 完成 + pipeline 稳定运行 ≥ 1 个月

**现状核查**（2026-05-26）：
- `CompilationResult`（`core/kernel/blueprint.py`）仍携带若干历史字段
- `MetadataStore` 三张核心绑定（symbol_bindings / type_bindings / loc_bindings）是下游（序列化器/VM）唯一真实消费方
- `core/compiler/semantic/adapter.py` 做 PipelineResult → CompilationResult 转换时可能搬运冗余数据

**具体待做**：
1. 审计 `CompilationResult` 中哪些字段被下游（`core/runtime/vm/`、序列化器）实际读取
2. 将未消费字段降级为 debug-only 或直接移除
3. 确认 `MetadataStore` 的三张绑定表是否可直接作为 CompilationResult 的唯一载荷

---

### PT-SEM-3　二层 IR 路线评估 [VISION]

**前置条件**: PT-SEM-2 完成 + 单 IR 路径稳定 ≥ 1 个月

**设计问题**：当前 semantic pipeline 既做"AST 结构变换"（llmexcept body 重排、intent 注解附着）又做"语义分析"（类型推断、符号解析）。随着行为依赖图/intent 调度优化等功能扩展，可能需要分离为：
- **结构 IR**：AST 规整化产物（可序列化、可独立验证）
- **执行 IR**：VM 直接消费的扁平化指令序列

**为什么搁置**：当前 IBCI 脚本规模（通常 < 200 行）下，单 IR 性能足够；只有当 LLM 调用计费/调度优化等高级功能需要跨过程分析时才会成为瓶颈。

---

## 二、VM 异步/协程层（L3）[SHELVED]

> **独立设计文档**：`docs/COROUTINE_DESIGN_NOTES.md`
> **搁置决策日期**：2026-05-28
> **搁置原因**：当前优先完善多模态功能（Phase 3-5）；`dispatch_eager` + `LLMFuture` 已覆盖主要异步需求

> ⚠️ **2026-06-24 全量分析补充**：
> - 搁置理由"dispatch_eager + LLMFuture 已覆盖主要异步需求"**有漏洞**：`handlers.py:732` 在 llmexcept 活跃时禁用 dispatch → retry-safe 代码无 async，而这正是用户最想隐藏延迟的地方
> - **11 个失败的 `test_e2e_multi_interpreter` 测试就是 PT-3.1**（host.run_isolated/spawn），而 PT-3.1 被下方标为"blocked by L3"→ L3 搁置等于合法化 11 个已知失败留在基线中
> - L3 与 PT-4.7 实为同一根因（execution_context 跨线程共享），见 §三 PT-4.7

### 阻塞原因

L3 协程层需要 VM 从"单任务调度器"升级为"多任务挂起/恢复"架构。这牵涉三个独立维度的协同变更：
1. **调度器架构**：当前 `VMExecutor` 是单根任务（`vm.run(uid)` 一次执行完毕）；需要多任务队列 + `Signal.YIELD` 挂起语义
2. **语言层关键字**：`async`/`await`/`yield` 均不在现有 KEYWORDS 表中；需设计语法与类型
3. **快照协议对齐**：协程挂起时如何保存 intent_context 栈 + llmexcept 帧栈（当前 `try_deep_clone` 仅服务 llmexcept retry，不覆盖协程 yield 点）

### 被阻塞的子项

| 编号 | 标题 | 依赖 L3 的原因 |
|------|------|---------------|
| PT-3.1 | `host.run_isolated()` 返回值改进 | 当前返回 `IbObject`/`bool`，需要协程句柄才能实现"异步等待子脚本完成"。⚠️ 2026-06-24 实测 5 个 `test_run_isolated_*` / `test_spawn_collect_*` 测试失败与此相关 |
| PT-3.2 | `ReceiveMode` 枚举演进 | 需要 yield/resume 语义支持流式接收模式 |

### 恢复条件

详见 `docs/COROUTINE_DESIGN_NOTES.md §六`。核心前提：多模态 Phase 3-5 稳定后 + 出现明确用户需求。**2026-06-24 补充**：建议把"11 个 host 测试恢复绿色"作为 L3 恢复的前置信号之一。

---

## 三、语言级能力扩展（暂搁置，经事实核查确认有效）

### PT-4.1　Enum 非 str 成员 + 迭代能力 [VISION]

**已验证的现状**（2026-05-26 代码核查）：
- `EnumAxiom`（`core/kernel/axioms/primitives.py:1076+`）：`has_from_prompt_cap = True` / `has_output_hint_cap = True`
- `_get_enum_index_map(spec)` 遍历 `spec.members`，建立 `{name → name}` 映射——**不携带成员声明类型**，一律把成员"名字本身"当字符串值返回给 LLM
- `from_prompt(...)` 把 LLM 返回值大写化后查表；`__outputhint_prompt__` 仅列出成员名
- 运行时 `IbEnumValue` / `IbEnum`（`core/runtime/objects/enum.py`）所有比较退化到 `name` 字符串等价
- 写 `int RED = 1` 时 `from_prompt` 仍按名字匹配，与底层值 `1` 不一致

**扩展方向**：
- 支持 `int` / `float` 成员：`_get_enum_index_map` 升级为携带类型信息，`from_prompt` 同时接受名字或字面值
- 支持 `for v in Color:` 迭代：为 Enum 基类注册 `__iter__` / `__len__` 方法
- 统一 `Color.RED` 返回 `IbEnumAdapter` 而非原始 `IbString`

> ⚠️ **2026-06-24 全量分析质疑**：
> - 原"现有 str 枚举 + LLM 名字匹配已覆盖 95% 用例"声明**未经验证且可能有误**：`primitives.py:1140-1144` 把成员值一律设为名字字符串本身，任何带数字状态码的枚举（`int OK = 200`/`int ERR = 500`）无法 round-trip
> - `from_prompt` 在 `primitives.py:1158` 对 `"1"/"0"/"TRUE"/"FALSE"` 做穿透 sentinel——若枚举成员名恰好为 `"1"` 会与布尔 sentinel 冲突
> - 数字状态码是生产代码的主流枚举用法，"95% 覆盖"数字可能反向
> - **需用户反馈验证真实使用分布后再定优先级**

**为什么搁置**：非 str 成员涉及 prompt 输出约定变更（"reply with RED" vs "reply with 1"），需用户反馈驱动。

---

### PT-4.2　`__call__` 协议类型推断一致性 [VISION]

**已验证的现状**（2026-05-26 代码核查）：
- 编译期：`TypeCheckingPass.visit_IbCall`（`type_checking_pass.py:388-396, 991-1003`）识别 `__call__` 成员并通过 `registry.resolve_callable_instance_return()` 推断返回类型
- 运行时：`vm_handle_IbCall`（`handlers.py:512`）对任意 `func` 派发 `func.receive("__call__", args)` — 语法层可用
- **已知灰区**（同步登记在 `KNOWN_LIMITS.md §一`）：
  1. `__call__` 内部 `@~...~` 的 intent_context 合并规则未显式规定
  2. `fn f = obj`（obj 是带 `__call__` 的类实例）的兼容性未被类型系统覆盖（`TypeKind.CLASS` 与 `fn_callable` 不在同一兼容轴）
  3. `__call__` 省略返回类型时回落到 `auto`，未与调用站左值类型协商

**扩展方向**：
- 在 `MethodMemberSpec` 上为 `__call__` 增设"is_callable_proxy"标记
- 显式规定 `__call__` 内 intent_context 合并规则
- 评估是否要求 `__call__` 的返回类型必须显式声明

**为什么搁置**：触及类型系统兼容性轴（class ↔ callable），跨 axiom/spec/semantic/vm 四层；用户可用"普通方法 + lambda 包装"作为零成本替代。

> ⚠️ **2026-06-24 全量分析备注**：`__call__` 协议在 3 个文档有 3 种不同定性（KNOWN_LIMITS §一"建议禁用"、AUDIT_REPORT"已知缺陷"、本条目"VISION 未来愿景"），框架应统一。

---

### PT-4.3　语言级协程 [SHELVED]

见 §二 + `docs/COROUTINE_DESIGN_NOTES.md`。明确搁置，待多模态稳定后再评估。

---

### PT-4.4　用户类泛型类型参数 [VISION]

**已验证的现状**（2026-05-26 代码核查）：
- `core/compiler/lexer/core_scanner.py` KEYWORDS 无泛型 token
- `core/kernel/ast.py:IbClassDef` 无 `type_params` 字段
- `SpecRegistry.resolve_specialization()`（`registry.py:966+`）仅响应 axiom 内置类型（list/dict/Optional/tuple）；用户 class 的 spec 不参与泛型特化

**扩展方向**：
- `IbClassDef` 扩展 `type_params: List[str]`；语法层支持 `class Box[T]:` 形态
- 语义层对类成员中的 `T` 做延迟绑定；运行时走 erasure（不建立完整 HM 推断）

**为什么搁置**：`any` 兜底 + axiom 内置泛型已覆盖绝大多数 LLM 集成脚本需求；引入用户级泛型会撑大类型系统兼容性轴。

---

### PT-4.5　用户类运算符重载 [VISION]

**已验证的现状**（2026-05-26 代码核查）：
- 内置 axiom 通过 `resolve_operation_type_name(op, other_name)` 处理 `+ - * / < == !=` 等运算符
- 用户类 `IbClass` **无** dunder 运算符注册位；`==` 在用户类实例上退化为 `id()` 比较
- 现有 dunder 协议仅覆盖：`__init__` / `__call__` / `__to_prompt__` / `__from_prompt__` / `__outputhint_prompt__` / `__snapshot__` / `__restore__`

**扩展方向**：
- `IbClass.receive(op, [other])` 中增加"先查自身 dunder，再 fallback 到 axiom"分发
- `TypeCheckingPass.visit_IbBinOp` 增加用户类操作数分支：查找 `__add__` 等 → 推断返回类型

**为什么搁置**：IBCI 业务脚本主要使用 LLM + 容器操作，运算符重载不是核心需求；且涉及类型系统兼容性轴 + 编译期方法分派两个维度。

---

### PT-4.7　DDG 并行调度真正接入 VM [DESIGN-DEBT]

**已验证的现状**（2026-05-26 代码核查）：
- **编译期已就绪**：`BehaviorDependencyAnalyzer`（`core/compiler/semantic/passes/behavior_dependency_pass.py:37+`）为每个 `IbBehaviorExpr` 计算 `llm_deps` / `dispatch_eligible` 字段
- **运行时有部分通路**：`vm_handle_IbBehaviorExpr`（`handlers.py:691-754`）在 `dispatch_eligible=True` 时调用 `LLMScheduler.dispatch_eager()` 提交后台 LLM 请求，得到 `LLMFuture` 占位符；`vm_handle_IbName`（`handlers.py:90-117`）在读取 `LLMFuture` 时阻塞解引用
- **限制**：Cell 变量被标记为 `dispatch_eligible=False`（`handlers.py:744`），避免 Cell 同步问题

> ⚠️ **2026-06-24 全量分析修正**：
> - 原描述的失败模式"llmexcept 快照 × future 解引用"**误诊**：`deep_clone.py:102` 对 `LLMFuture` 返回 None → 变量被 `llm_except_frame.py:211` 静默跳过（harmlessly skipped）；且 dispatch 在 llmexcept 活跃时已被 `handlers.py:732` 禁用
> - **真实失败模式**：`dispatch_eager` 捕获 `execution_context` **按引用**（`llm_executor.py:547` 传 live context 给后台线程）。若 future 在 llmexcept block 前分发，body 修改了 future prompt 通过共享 context 读取的变量 → future 观察到**中途变异状态** → 真实数据竞争
> - **与 L3 的关联**：此问题与 §二 L3 搁置实为同一根因（execution_context 跨线程共享）；修复需线程隔离的 context 快照 per dispatch，接近 L3 工作
> - **原"future-aware snapshot"补救不足**：实际需 thread-isolated context snapshots per dispatch

**为什么搁置**：收益高（非依赖 LLM 调用可真正并行）但风险高——真实失败模式是并发 hazard，不是 clone 问题。建议与 L3 一并评估。

---

## 四、设计原则与明确排除方向

> 以下原则经项目主要贡献者确认，作为架构决策的长期约束。

### 坚持的设计原则

1. **显式优于隐式**：所有语义行为必须在代码中可见（如 `nonlocal` 而非自动推断、显式 `(Type)cast` 而非隐式转换）
2. **单点真理**：同一份语义事实只能存在于一处可序列化位置——AST 字段 ∨ 侧表 ∨ MetadataStore，不允许双写（详见 `docs/METADATA_ARCHITECTURE.md`）
3. **公理调度 + 单次锁定**：类型系统不引入完整约束求解/HM 风格推断，但允许从中汲取受控设计思路（如 `TypeSlot` 单次锁定延迟绑定）
4. **运行时可观测性优先**：不以牺牲调试/内省能力换取短期性能优化

> ⚠️ **2026-06-24 全量分析备注**：
> - 原则 1 "显式优于隐式"在代码中有违反：`ibci_ai/core.py:399-402` 未探测模型静默 `is_reasoning_model = True`；`ibci_ai/core.py:85-86` 自动给 base_url 追加 `/v1`；`llm_except_frame.py:206-207,304-305` `__snapshot__`/`__restore__` 异常被 `pass` 吞掉
> - 原则 4 "运行时可观测性优先"在多模态设计中有冲突：D3 磁盘卸载"对用户透明"默认隐藏 `.location`；D-P2-4 MOCK flatten 破坏多模态结构信号
> - 这两处违反应作为后续 ADR 的修正输入

### 明确排除的方向

- ❌ 静态类型检查器作为解释器前置强依赖
- ❌ 为优化同一程序内独立 LLM 调用而创建多 Interpreter（这是 L1 流水线职责）
- ❌ 完整的 HM 风格类型推断（但 TypeSlot 延迟绑定等受控借鉴是允许的）
- ❌ AST 字段 + 侧表 + MetadataStore 三处同时存储同一语义事实（"双写真相"禁令）

> ⚠️ **2026-06-24 全量分析备注**：
> - "❌ 静态类型检查器作为解释器前置强依赖"的排除**正变得自相矛盾**：4-Phase semantic pipeline 已达 ~1491 行 `type_checking_pass.py` 做真实检查；DEC-1（关键字）+ DEC-2（固定属性）会重新引入编译期类型结构。应重新评估此排除是否仍成立。

---

## 五、架构健康改善项 [P1-P3 — 见 NEXT_STEPS 指针]

> 来源：2026-06-24 全量分析体检架构健康度审查。

### PT-ARCH-1 提取 `core/runtime/shared/` 打破 3 个 runtime 内循环 [P1]

**现状**：3 个 runtime 内循环被延迟导入掩盖：
- `interpreter↔vm`：`interpreter.py:501` 延迟导入 `VMExecutor`
- `objects↔interpreter`：`builtins.py:199,225` 延迟导入 `LLMResult`
- `objects↔vm`：`kernel.py:1019` 延迟导入 `vm.task`

**待做**：
- 移动 `interpreter/llm_result.py`（`LLMResult`/`LLMFuture`）→ `runtime/shared/llm_result.py`
- 移动 `vm/task.py` 的 `Signal`/`ControlSignal`/`UnhandledSignal` → `runtime/shared/signal.py`
- 移动 `interpreter/constants.py` → `runtime/shared/constants.py`
- 收益：消除所有延迟导入 workaround，使 `objects`/`vm` 干净地低于 `interpreter`

### PT-ARCH-2 拆分 `HostInterface` [P1]

**现状**：`HostInterface`（`host_interface.py:9-76`）是混合关注 god object：
- 编译器只需 `SpecRegistry` + `TypeDef` map + discovery-name map（元数据部分）
- 但同时持有 `HostModuleRegistry`（runtime 实现部分）
- `compiler/parser/core/context.py:39` **自动实例化** `HostInterface()` —— 编译器不应 fabricate runtime 对象

**待做**：
- 拆为 `ModuleMetadataProvider`（kernel/compiler 可见）+ `HostModuleRegistry`（runtime 实现）
- 编译器只依赖 `ModuleMetadataProvider`
- 删除 `context.py:39` 的自动实例化

### PT-ARCH-3 移动 `fuzzy_json.py` → `core/base/support/` [P1]

**现状**：`core/kernel/axioms/primitives.py:28` → `core.runtime.support.fuzzy_json` 违反 "kernel 永不导入 runtime" 不变量（`ARCHITECTURE_PRINCIPLES.md:167`）。`fuzzy_json.py` 是纯 stdlib 叶子（`re`/`json`/`ast`），非真循环，但阻塞 axiom 层向 C++ 迁移。

**待做**：移动文件，更新一处 import。最便宜的架构修复。

### PT-ARCH-4 拆分 7 个 god modules [P1-P3]

**现状**：7 个文件 > 1000 行（健康边界）：
| 文件 | 行数 | 拆分方案 |
|------|------|---------|
| `runtime/vm/handlers.py` | 2023 | `handlers/{leaf,control_flow,assignment,llmexcept,decls,intent_behavior,loops}.py` + `build_dispatch_table` |
| `compiler/semantic/passes/type_checking_pass.py` | 1491 | `type_checking/{assign_handler,decl_handler,expr_handler,intent_check}.py` |
| `kernel/axioms/primitives.py` | 1351 | `axioms/{numeric,seq,callable,errors,sentinels}.py` + 折叠 LLM-error 工厂 |
| `runtime/objects/kernel.py` | 1183 | `objects/{base,class_system,functions,sentinels,native}.py` |
| `kernel/spec/registry.py` | 1147 | `SpecFactory` 独立 + `capability_queries.py` + `assignability.py` + `member_resolution.py` |
| `runtime/interpreter/llm_executor.py` | 1132 | `llm_prompt_builder.py` + `llm_scheduler.py` + 删除 5 对 CPS/non-CPS 重复 |
| `runtime/objects/builtins.py` | 1052 | `builtin_strings.py` + `builtin_behavior.py` + 保留其余 |

**优先级**：P1 = `handlers.py`（最大）；P2 = 其余 4 个；P3 = `builtins.py`/`spec/registry.py`

### PT-ARCH-5 折叠重复分支 [P2]

**现状**：3 处近重复：
- 4 个 LLM-error axioms（`primitives.py:822-939`）→ 数据驱动工厂 `_make_llm_error_axiom(name, parent, extra_fields, chain)`，省 ~120 行
- 8 个 SpecRegistry capability accessors（`registry.py:397-457`）→ `_get_cap(spec, flag)` + 薄包装
- 5 对 CPS/non-CPS 方法（`llm_executor.py:170-1060`）→ 选 CPS 为单一路径，删非 CPS 变体

**收益**：省 ~250 行近重复代码，消除"哪条路径运行"类 bug

### PT-ARCH-6 删除死抽象与死代码 [P3]

- `IbStatelessPlugin`（`ibcext.py:163-178`）零插件使用，`HostService` 从不检查它 → 删除
- 3 个 orphan fixtures（`tests/fixtures/`）无测试导入 → 删除或接入
- `AI_SETUP` 重复定义（`tests/fixtures/llm_samples.py:11` vs `conftest.py:68` `AI_MOCK_PREFIX`）→ 统一
- `_sync_classes_from` stub（`interpreter.py:130-132`）→ 实现或删除
- `_check_type` dead `pass` 分支（`runtime_context.py:79-82`）→ 删除
- `TypeRef` 重复 import（`registry.py:32 vs :40`）→ 删一个
- `IbInteger.__hash__` 隐式 None（`builtins.py:81`）→ 显式设置或标记

### PT-ARCH-7 修复 17+ 处静默吞异常 [P2]

**现状**：17 处 `except Exception: pass` + 5 处裸 `except:`，违反"运行时可观测性优先"原则。

**关键位置**：
- `engine.py:241`（axiom 注册失败静默）
- `kernel.py:156,188`（cast_to/__from_prompt__ 吞异常返硬编码 fallback）
- `kernel.py:947,1112`（已列为 P0-B-2）
- `runtime_context.py:301`（裸 except 吞 KeyboardInterrupt）
- `scheduler.py:94`、`runtime_serializer.py:230`
- `handlers.py` 多处（742/770/902/958/1616/1805/1812）
- `module_manager.py:88,150`、`host/service.py:118,156,228`
- `llm_parsing_strategy.py:269,277`

**待做**：统一为 `except SpecificException as e: self.debugger.trace(CoreModule.X, DebugLevel.BASIC, f"...: {e}")`；lint 禁止裸 `except:` 和 `except Exception: pass`

### PT-ARCH-8 `CapabilityRegistry` 类型化键 [P3]

**现状**：`CapabilityRegistry` 是字符串键 service locator（`registry.get("llm_provider")`），依赖不可 grep、不可静态检查。`replace`/priority 机制复杂但无真实多 provider 竞争用例。

**待做**：字符串键 → 类型化 `CapabilityKey` Enum；drop `replace`/priority 直到出现真实多 provider 用例。

### PT-ARCH-9 `AutoDiscoveryService` 健壮性 [P3]

**现状**：
- `_get_default_paths` 用 4× `os.path.dirname(os.path.dirname(...))` 从 `__file__`（`auto_discovery.py:63`）→ 打包/迁移易碎
- 一个 broken plugin 中止全部 discovery（`auto_discovery.py:95,109,134,139` 全部 raise）
- `dependencies` 字段收集但从不强制

**待做**：catch+log+skip broken plugin；robust base_dir；validate `dependencies` against registered capabilities

---

## 六、Phase 3 多模态决策矛盾 [BLOCKED]

> 来源：2026-06-24 全量分析对抗性审查。Phase 3 在这些矛盾解决前**不应启动实施**。

### 矛盾 1：DEC-5 vs DEC-6（Phase 3 内部不可调和）
- DEC-5：snapshot 用"路径引用（与磁盘卸载一致）"
- DEC-6：Phase 3 "先纯内存，Phase 5 再加磁盘"
- → Phase 3 时 media 在内存，但 snapshot 设计已承诺路径引用给尚不存在的磁盘后端
- **需 ADR 联合裁决**

### 矛盾 2：DEC-5 可能根本不工作
- `llm_except_frame.py:199` 用 `type(val) is IbObject` **严格身份检查，非 isinstance**
- `deep_clone.py:89` 同样 `type(val) is KernelIbObject`
- 若 `IbAudio`/`IbImage`/`IbVideo` 是 `IbObject` 子类 → 两个分支都不匹配 → 变量被**静默跳过，不进入 snapshot**
- "路径引用省深拷贝"的说法空洞成立（什么都没存，当然没拷贝开销）
- **需验证 snapshot 分发机制**（`isinstance` 或 axiom-backed dunder）

### 矛盾 3：D4 示例不可编译
- `MULTIMODAL_BEHAVIOR_DESIGN.md` 所有 `ai.register_model("GPT4o", {dict})` 示例
- 实际 `register_model(name, url, key, model, **kwargs)` 是 4 个位置 str 参数（`ibci_ai/core.py:113`）
- `_spec.py:22` vtable 声明 `["str","str","str","str"]` → 编译器拒绝 dict 调用
- §10.2 `config.endpoint == "audio/transcriptions"` 分支——但 `register_model` 不存 `endpoint` 字段（`core.py:127-132`）
- **需同步修复 register_model 签名 + vtable + IBCI 调用示例 + endpoint 存储**

### 矛盾 4：D6 vs DEC-4（同文档对立）
- D6："不改 `_call_llm` 返回契约"
- DEC-4："Phase 3 预留 `_call_llm_raw`"
- 实际 `COMPLETED.md:49` 选了"Phase 4 再改"——两个建议都没真正落地
- **需 ADR 裁决**

### 矛盾 5：DEC-1 vs ARCH_PRINCIPLES §九
- DEC-1 建议 audio/image/video 作为关键字"与 str/int 同级"
- 但 str/int **本就不是关键字**（`core_scanner.py:33-54` KEYWORDS 无 int/str）
- §九 明确"99% 禁止硬编码关键字"
- **需重新评估注册路径**（普通类名 vs 关键字）

### 矛盾 6：R5 破坏非 chat 端点
- 未探测的命名模型默认 `is_reasoning_model = True`（`ibci_ai/core.py:397-402`）
- 注入 ANSWER-tag/reasoning prompt → `@WHISPER~` 转录 API 收到语义错误的系统提示
- **需 per-endpoint-type 默认策略**

### 矛盾 7：D3 vs 运行时可观测性优先
- D3 磁盘卸载"对用户透明"默认隐藏 `.location`
- 与"运行时可观测性优先"原则冲突
- **需 ADR 重新评估透明 vs 可观测的权衡**

---

## 七、文档健康改善项 [P1-P2]

> 来源：2026-06-24 全量分析文档健康度审查。

### PT-DOC-1 标注 AUDIT_REPORT_20260527.md 已解决发现 [P1 — 见 NEXT_STEPS P1-H]
- 5 个 P0/P1 发现已于 2026-05-27 关闭（`COMPLETED.md:30-36`），但审计文档未记录
- 修复：每个发现加 "✅ Resolved 2026-05-27 — see COMPLETED.md"

### PT-DOC-2 修复 2 个 hub 文档锚点传播 [P1 — 见 NEXT_STEPS P1-I]
- `KNOWN_LIMITS.md` 编号被 4 个文档引用（旧 §三/§八/§十九/§二十三/§二十四/§二十五/§二十六 → 新 §一..§十六）
- `COMPLETED.md` 测试计数被 5 个文档引用（781/778/3、818/2、832/2 vs 当前 827/11/2）
- 受影响文件：`TEST_PHILOSOPHY.md:618`、`AUDIT_REPORT_20260527.md`（旧编号）、`ARCH_DETAILS.md:275`、`FUNC_DESIGN_NOTES.md:42`、`HISTORY_LOG.md:41,53,58,63`

### PT-DOC-3 IBCI_SYNTAX_REFERENCE.md 补充 [P1]
- 补 `@NAME~` 命名模型路由 + `__payload_prompt__` 多模态协议 + super() §6.4
- header 日期 2026-05-08 → 更新为 2026-06-24

### PT-DOC-4 ARCH_DETAILS.md §1.2 更新 [P1]
- "if/while 检测 uncertain → 立即返回空结果"（pre-BUG-#A，:31）
- 更新为 BUG #A 后的 raise `LLMParseError` 语义（2026-05-27）

### PT-DOC-5 SEMANTIC_COVERAGE_MATRIX.md 全面刷新 [P1]
- INV-CONTEXT-1/2 从 SKIPPED 翻转为 ✅（2026-05-26 已 un-SKIP）
- 测试数 612 → 840
- 重日期 2026-05-13 → 2026-06-24

### PT-DOC-6 清理 7 个幽灵引用 [P2]
- `ARCHITECTURE_REVIEW_2026-05-15.md`、`SEMANTIC_REFACTORING_PLAN.md`、`OPEN_ISSUES.md`（HISTORY_LOG:12,22,82）
- `TYPE_SYSTEM_ANALYSIS_REPORT.md`（METADATA_ARCHITECTURE:440）
- `AXIOM_OOP_ANALYSIS.md`（ARCH_DETAILS）
- `IBCI_TYPE_SYSTEM.md`（IBCI_TYPE_SYSTEM_FROM_ZERO_ARCHITECTURE:616 误引）
- `PENDING_TASKS §七 PT-5.1`（VM_SPEC:6 — 本文档已无 §七）

### PT-DOC-7 清理 HISTORY_LOG 旧编号 [P2]
- 4 处引用 KNOWN_LIMITS §十九/§二十三/§二十四/§二十五（:41,53,58,63）→ 全部死指针
- 处置：标注为"历史编号，对应旧版 KNOWN_LIMITS，现已被 §一..§十六 取代"

### PT-DOC-8 README 补全 [P2]
- 补测试命令 `python -m pytest tests/ -q --tb=short`
- 补架构概览（模块布局/数据流图）
- 链接 NEXT_STEPS/COMPLETED/VM_SPEC（当前只链 3 个 docs）
- 加 CONTRIBUTING.md（从 NEXT_STEPS 工作规则提取）

### PT-DOC-9 评估合并/删除小文档 [P3]
- `FUNC_DESIGN_NOTES.md`（48 行，2026-04-29 冻结）→ 合并入 KNOWN_LIMITS §一 或删除
- `MULTIMODAL_ANALYSIS_CONCLUSIONS.md`（已归档，内容并入 Appendix C）→ 评估删除

### PT-DOC-10 TYPE_SYSTEM_DESIGN.md §5.1 更新 [P2]
- "Pass 4/5 SemanticAnalyzer"（:241，2026-05-08）→ 4-Phase pipeline（2026-05-25）
- §10 "主线债务：无"（:357）→ 更新为当前 P0/P1 状态

### PT-DOC-11 VM_AND_INTERPRETER_DESIGN.md §12 更新 [P2]
- "目前无新增 P0/P1/P2 主线开放议题"（:405，2026-05-12）→ 更新为当前 P0 基线修复 + P1 架构改善
- 状态表补 nonlocal/Phase 1-2/super()/4-Phase rename

---

## 八、测试基础设施改善项 [P1-P3]

> 来源：2026-06-24 全量分析测试体系审查。

### PT-TEST-1 加 pytest.ini + CI workflow + pytest-cov [P1 — 见 NEXT_STEPS P1-E]
- 当前：无任何 pytest 配置、无 CI workflow 文件
- 最低配置：`testpaths = tests`、`--strict-markers`、`--cov=core --cov-fail-under=70`
- slow/fast markers

### PT-TEST-2 加层级元测试 + 迁移违规文件 [P1 — 见 NEXT_STEPS P1-F]
- `tests/meta/test_layering.py` 静态强制红线（kernel 不调 run_ibci、compiler 不调 run_ibci、e2e 不导入 core.runtime.interpreter）
- 迁移 `tests/compiler/semantic/test_override_and_super.py` + `test_nonlocal.py` → `tests/e2e/`

### PT-TEST-3 加 MOCK 独立测试 [P1 — 见 NEXT_STEPS P1-G]
- `tests/runtime/test_mock_directives.py` 测每个 `MOCK:` 变体
- 消除"mock 被 ~hundreds 测试信任但从未独立测过"风险

### PT-TEST-4 填补覆盖缺口 Top 5 [P2]
1. `core/runtime/serialization/` round-trip property test（serialize → deserialize == identity）
2. `core/runtime/host/service.py` collect 数据通路（不需启动子解释器）
3. `core/runtime/path/` 跨盘/relpath 回归
4. `core/engine.py` 生命周期/重入/跨盘/单次使用
5. `core/runtime/objects/kernel.py.__getitem__` 契约（空/缺键应返正确错误类型）

### PT-TEST-5 补 BUG #A if-uncertain 回归 [P2]
- `while`/`for` uncertain → `LLMParseError` 有测试
- `if` uncertain → `LLMParseError` **无专属回归测试**
- 添加 `test_if_condition_uncertain_raises_llm_parse_error` 到 `tests/e2e/test_e2e_llmexcept.py`

### PT-TEST-6 删除死 fixtures + 统一 MOCK 前缀 [P3]
- 3 个 orphan fixtures（`control_flow_samples.py`/`llm_samples.py`/`type_system_samples.py`）无测试导入 → 删除或接入
- `AI_SETUP`（`fixtures/llm_samples.py:11`）→ 统一为 `conftest.py:68` `AI_MOCK_PREFIX`

### PT-TEST-7 清理 stale 引用 [P3]
- `tests/kernel/conftest.py:3-7` 引用不存在的 `test_typeref.py`/`test_spec_layer.py`/`test_axioms.py`
- `tests/COVERAGE_MAP.md` 41 文件/781 collected/778 passed/3 skipped → 45/840/827/11/2

### PT-TEST-8 修复测试命名违规 [P3]
- `tests/compiler/test_type_annotations.py` 6 个 `TestM2*`/`TestD3*` 类（违反 `tests/README.md:45` "不允许前缀 TestNS2b/TestPT21"）
- `tests/compiler/test_generics.py` 5 个 `TestG2*`/`TestG3*` 类
- 重命名为行为导向名称

### PT-TEST-9 修复 `IbString.to_bool` 越层访问 [P2]
- `builtins.py:185-209` `IbString.to_bool`/`cast_to` 越层访问 `runtime_context.get_current_llm_except_frame()`
- 原始包装层不应知道 LLM 控制流
- 修复：把 LLM-aware 分支移入 `LLMResultParser` 或 `BoolAxiom`/`StrAxiom.from_prompt`
