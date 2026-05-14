# NEXT_STEPS — 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `docs/PENDING_TASKS.md`；历史归档见 `docs/COMPLETED.md`。
>
> **最后更新**：2026-05-14（基于全量事实核查；测试基线红线 + 文档失实修正阶段）

---

## ⚠️ 优先级 P0：基线诚实化（本周期主推）

2026-05-14 全量巡检发现：2026-05-13 标记为"测试体系契约化重构 Phase 2 完成 + 测试基线 Full pass"的产物**实际并未通过任何一次成功的编译**。`tests/contracts/` 中 ~89 个 INV-XXX-N 用例使用了非法 IBCI 语法（C 风格 `func <ret> <name>():`、假大括号 `llmexcept { } retry { }`、`cast(T,x)`、`Some(v)`、`MOCK:INVALID` 等），属于典型的"智能体幻觉式假完成"。同时 `tests/runtime/test_plugin_implementations.py` 对 NetLib / SchemaLib 不存在的 API（`set_base_url` / `get_headers` / ...）发起调用，也从未跑通。

**P0 任务清单**（本 PR 启动）：

- **P0-A** 重写 `tests/contracts/` 的 88 个失败用例，使其使用真实 IBCI 语法验证它们各自命名的 INV-XXX-N 不变量。
- **P0-B** 重写 `tests/runtime/test_plugin_implementations.py` 中 5 个失败用例，使其调用 NetLib / SchemaLib 真实 API。
- **P0-C** 修复 `tests/meta/test_no_duplicate_helpers.py` 揭示的 25 处违反"测试不可重复定义 helpers"的约定。
- **P0-D** 修复 `examples/01_getting_started/04_mock_and_llmexcept.ibci` 当前在 MOCK:FAIL 段崩溃导致后续 5 节不可达的问题。
- **P0-E** 把 `docs/VM_SPEC.md` / `docs/KNOWN_LIMITS.md` / `docs/COMPLETED.md` 中"硬编码 pass 数字 (1180 / 1195 / 1239 / Full pass)"全部改为"相对表述 + 锚定日期"，以避免下一个智能体读到陈旧数字后再次产生"无 P0/P1"的幻觉。

完成 P0-A..E 之后，`tests/contracts/` 才能真正纳入 `docs/VM_SPEC.md §6` 声明的跨实现合规基线。

---

## P1 候选（按优先级排队，不与 P0 并行）

> 以下三项均经过 2026-05-14 事实核查；技术路线已落定，仅缺工时。每完成一项即把摘要追加到 `docs/COMPLETED.md` 并把对应条目从本文件移除。

### P1-A `@` 意图注释放置规则进入 IBCI_SYNTAX_REFERENCE §9
- **现状**：编译器以 SEM_060 强制"`@` 必须紧跟行为表达式"、"不允许两条连续 `@`"、"`@-` 不是合法语法"，但 `IBCI_SYNTAX_REFERENCE.md` 与 `README.md` 例 2 暗示可以堆叠（误导用户）。
- **动作**：在 `docs/IBCI_SYNTAX_REFERENCE.md §9` 补"放置约束"小节；改写 README 例 2，明确"多个 @+ 可以堆叠，但 @ 仅可一条"。

### P1-B `intent_context.push()` 静默无效陷阱编译期警告
- **现状**：`intent_context.push("X")` 在没有 `use(ctx)` 时是 no-op（详见 `docs/KNOWN_LIMITS.md §十八`），但编译期不告警；用户极易踩坑。
- **动作**：在 `semantic_analyzer` 中对 `IbCall(method='push'|'pop'|'merge'|'combine'|'clear')` 且 receiver 为类静态调用（非局部 `intent_context` 变量）的形态发出 SEM 警告。低风险，单点改动。

### P1-C ⚠️ 代码健康度重构（沿用旧 NEXT_STEPS）
**代码健康度审计**已识别出紧要问题（沿用 2026-05-13 计划）：
- **超大文件拆分**: 8 个文件 >1000 行
- **深层嵌套逻辑优化**: 7 处复杂条件分支
- ✅ **局部导入清理**: 已完成（2026-05-13）

详见 `docs/CODE_HEALTH_REFACTORING.md`。在 P0 完成、契约基线诚实化之后再启动。

---

## 主线完成情况

类型系统 M1–M5、VM CPS 主线、intent 系统 OOP 化（NS-2 全部 4 步）、LLM 调用路径合并入 CPS 调度循环（NS-1）、lambda/snapshot/behavior 跨帧 EC 边界（NS-3）、intent_context 高级 OOP 场景（PT-2.1）、IbIntentContext 序列化/反序列化（PT-2.2）、`_evaluate_segments` CPS 化、PT-1.2（llmexcept 错误历史）、PT-1.3（llmexcept 嵌套深度限制）以及 PT-3.3（`idbg.protection_map()`）均已完成。

**当前主线（VM / Intent / llmexcept / 类型系统骨架）没有新的开放 P0/P1 内核任务**，但**测试基线 / 文档基线本身需要诚实化**（见上）。

---

## NS-4　收紧 `str + llm_uncertain` 隐式拼接（OI-1 收口）

✅ **已完成（2026-05-12）** — 详见 `docs/COMPLETED.md` 2026-05-12 NS-4 锚点。

---

## NS-5　编译期类型转换检查（激活 `can_convert_from`）

**优先级**：P3

### 当前事实状态

- `core/compiler/semantic/passes/semantic_analyzer.py:1704-1712` 的 `visit_IbCastExpr` 仅 `self.visit(node.value)`（不使用 source 类型），随即把目标类型作为节点类型回填到 side_table。所有 cast 校验都推迟到运行时 `value.receive("cast_to", [target_class])`。
- `core/kernel/spec/registry.py:411-422` 的 `get_converter_cap()` 已实现并存在显式 TODO："activate this in `semantic_analyzer.py::_resolve_cast_expr()` once compile-time cast validation is added."
- 各 axiom 的 `can_convert_from` 在 `core/kernel/axioms/primitives.py` 中以**目标类型视角**给出："target 能否接受来自 src 的显式 cast？"。
- 与 `is_compatible`（赋值兼容性，源类型视角）正交，不可混用。

### 真实可接受的转换矩阵（核查所得）

| 目标 axiom | `can_convert_from(src)` 接受集 | 备注 |
|-----------|---------------------------|------|
| Int | str, float, bool, int | — |
| Float | str, int, bool, float | — |
| Bool | **任意**（`return True`） | 一切都可 truthy 测试 |
| Str | （需核查 379-460 行） | — |
| List | 仅 list | 严格 |
| Dict | （598 行） | — |
| Tuple | （675 行） | — |
| Exception | **任意** | 异常包装兼容性 |
| LLMError 子类 | str + 自身 | 允许 str→错误对象 |
| LLMUncertain | 仅 llm_uncertain | 哨兵自封闭 |
| Enum（用户自定义类） | 仅 str | LLM from_prompt 协议要求 |
| BaseAxiom 默认 | 全部 False | 用户类、callable 系列等 |

### 落地难点（必须先解决）

1. **用户类的 cast 矩阵**：用户定义的 `MyClass`/子类未走 axiom 路径，`BaseAxiom.can_convert_from` 默认 False。但 `(BaseClass)derived_var`、`(DerivedClass)base_var` 等 OOP cast 用例很常见。需要在 `visit_IbCastExpr` 中**短路**：source/target 任一为用户类时，按继承链 IS-A 判定，不走 axiom。
2. **`any` 兜底**：source 或 target 名为 `any` 时一律放行（与运行时 `cast_to "any"` 一致）。
3. **`auto` / `void` / `Optional[T]`**：需要明确策略——`auto` 在变量声明阶段已绑定具体类型；`void` 不可作为 source/target；`Optional[T]` cast 视为 `T` 的兼容形式。
4. **`is_compatible` vs `can_convert_from` 不重合**：例如 `(int)bool_var` 在 `can_convert_from` 接受集中（"bool"∈int 接受集），但 `bool→int` 的 `is_compatible` 关系也是赋值兼容（隐式可行）。这意味着即使禁用显式 cast，赋值路径仍能完成，不会丢功能。
5. **测试套件回归**：`tests/compiler` 与 `tests/e2e` 中可能存在依赖运行时宽松 cast 的用例，需逐一审视。

### 技术路径

1. **新增 SEM 码**：建议 `SEM_011 SEM_CAST_INVALID`（`core/base/codes.py`），错误信息附带建议（"use `(any)x` and then receive…"）。
2. **`visit_IbCastExpr` 改造**（`semantic_analyzer.py:1704`）：
   - 拿到 `source_type = self.visit(node.value)`。
   - 若 source / target 任一为 `any` → 通过。
   - 若两者均为用户类且存在 IS-A 关系（任一方向） → 通过。
   - 否则调 `self.registry.get_converter_cap(target_type)`：返回 None ⇒ 报错（"type has no converter capability"）；返回 axiom ⇒ 检查 `axiom.can_convert_from(source_type.get_base_name())`，False 时报 SEM_011。
3. **`can_convert_from` 局部修正**（须先于 step 2 落地）：
   - 把 `IbException.can_convert_from(...)` 收紧（不再"任意接受"），改为 IS-A Exception 子类即可。运行时 `IbException.cast_to(target="str")` 行为不变。
   - 把 `BoolAxiom.can_convert_from(...)` 维持"任意"（truthy 测试是底层公理）。
4. **测试**：新增 `tests/compiler/test_compile_time_cast.py` 覆盖：原始类型矩阵、用户类继承、`any` 兜底、错误样本。

### 风险

- 行为破坏面较大；建议先在 dev branch 跑 `pytest tests/ -q --tb=short`，按失败用例反推 `can_convert_from` 是否应放宽，谨慎调整。
- `cast_to "any"` 通用 escape hatch 必须保持开放，避免阻断现有"动态对象"模式。

---

## NS-6　链式下标 `(expr)[index]` 语法消歧

**已完成（2026-05-12）** — 详见 `docs/COMPLETED.md` 2026-05-12 NS-6 锚点。

---

## NS-7　`tuple[T1, T2, ...]` 位置元素类型标注

**已完成（2026-05-12）** — 详见 `docs/COMPLETED.md` 2026-05-12 NS-7 锚点。

## 工作规则

- 同一时刻只主推一项 P0 任务（或一项 NS-x）；其余项保留待选。
- 任何改动公理层公约或语义错误集的 NS-x，需在分支早期跑 `python -m pytest tests/ -q --tb=short` 评估破坏面。
- 每项完成后，把摘要追加到 `docs/COMPLETED.md`（极简时间线），并把对应条目从本文件移除。
- 出现新的紧要项时，按"先评估优先级、再决定是否替换"原则操作。
- **本文件不再冻结具体测试通过数字**——任何"X 测试通过"的表述都必须附运行命令或日期锚点，避免下一个智能体把陈旧数字当作真实状态。

> **最后更新**：2026-05-14


---

## NS-4　收紧 `str + llm_uncertain` 隐式拼接（OI-1 收口）

✅ **已完成（2026-05-12）** — 详见 `docs/COMPLETED.md` 2026-05-12 NS-4 锚点。

---

## NS-5　编译期类型转换检查（激活 `can_convert_from`）

**优先级**：P3

### 当前事实状态

- `core/compiler/semantic/passes/semantic_analyzer.py:1704-1712` 的 `visit_IbCastExpr` 仅 `self.visit(node.value)`（不使用 source 类型），随即把目标类型作为节点类型回填到 side_table。所有 cast 校验都推迟到运行时 `value.receive("cast_to", [target_class])`。
- `core/kernel/spec/registry.py:411-422` 的 `get_converter_cap()` 已实现并存在显式 TODO："activate this in `semantic_analyzer.py::_resolve_cast_expr()` once compile-time cast validation is added."
- 各 axiom 的 `can_convert_from` 在 `core/kernel/axioms/primitives.py` 中以**目标类型视角**给出："target 能否接受来自 src 的显式 cast？"。
- 与 `is_compatible`（赋值兼容性，源类型视角）正交，不可混用。

### 真实可接受的转换矩阵（核查所得）

| 目标 axiom | `can_convert_from(src)` 接受集 | 备注 |
|-----------|---------------------------|------|
| Int | str, float, bool, int | — |
| Float | str, int, bool, float | — |
| Bool | **任意**（`return True`） | 一切都可 truthy 测试 |
| Str | （需核查 379-460 行） | — |
| List | 仅 list | 严格 |
| Dict | （598 行） | — |
| Tuple | （675 行） | — |
| Exception | **任意** | 异常包装兼容性 |
| LLMError 子类 | str + 自身 | 允许 str→错误对象 |
| LLMUncertain | 仅 llm_uncertain | 哨兵自封闭 |
| Enum（用户自定义类） | 仅 str | LLM from_prompt 协议要求 |
| BaseAxiom 默认 | 全部 False | 用户类、callable 系列等 |

### 落地难点（必须先解决）

1. **用户类的 cast 矩阵**：用户定义的 `MyClass`/子类未走 axiom 路径，`BaseAxiom.can_convert_from` 默认 False。但 `(BaseClass)derived_var`、`(DerivedClass)base_var` 等 OOP cast 用例很常见。需要在 `visit_IbCastExpr` 中**短路**：source/target 任一为用户类时，按继承链 IS-A 判定，不走 axiom。
2. **`any` 兜底**：source 或 target 名为 `any` 时一律放行（与运行时 `cast_to "any"` 一致）。
3. **`auto` / `void` / `Optional[T]`**：需要明确策略——`auto` 在变量声明阶段已绑定具体类型；`void` 不可作为 source/target；`Optional[T]` cast 视为 `T` 的兼容形式。
4. **`is_compatible` vs `can_convert_from` 不重合**：例如 `(int)bool_var` 在 `can_convert_from` 接受集中（"bool"∈int 接受集），但 `bool→int` 的 `is_compatible` 关系也是赋值兼容（隐式可行）。这意味着即使禁用显式 cast，赋值路径仍能完成，不会丢功能。
5. **测试套件回归**：`tests/compiler` 与 `tests/e2e` 中可能存在依赖运行时宽松 cast 的用例，需逐一审视。

### 技术路径

1. **新增 SEM 码**：建议 `SEM_011 SEM_CAST_INVALID`（`core/base/codes.py`），错误信息附带建议（"use `(any)x` and then receive…"）。
2. **`visit_IbCastExpr` 改造**（`semantic_analyzer.py:1704`）：
   - 拿到 `source_type = self.visit(node.value)`。
   - 若 source / target 任一为 `any` → 通过。
   - 若两者均为用户类且存在 IS-A 关系（任一方向） → 通过。
   - 否则调 `self.registry.get_converter_cap(target_type)`：返回 None ⇒ 报错（"type has no converter capability"）；返回 axiom ⇒ 检查 `axiom.can_convert_from(source_type.get_base_name())`，False 时报 SEM_011。
3. **`can_convert_from` 局部修正**（须先于 step 2 落地）：
   - 把 `IbException.can_convert_from(...)` 收紧（不再"任意接受"），改为 IS-A Exception 子类即可。运行时 `IbException.cast_to(target="str")` 行为不变。
   - 把 `BoolAxiom.can_convert_from(...)` 维持"任意"（truthy 测试是底层公理）。
4. **测试**：新增 `tests/compiler/test_compile_time_cast.py` 覆盖：原始类型矩阵、用户类继承、`any` 兜底、错误样本。

### 风险

- 行为破坏面较大；建议先在 dev branch 跑 `pytest tests/ -q --tb=short`，按失败用例反推 `can_convert_from` 是否应放宽，谨慎调整。
- `cast_to "any"` 通用 escape hatch 必须保持开放，避免阻断现有"动态对象"模式。

---

## NS-6　链式下标 `(expr)[index]` 语法消歧

**已完成（2026-05-12）** — 详见 `docs/COMPLETED.md` 2026-05-12 NS-6 锚点。

---

## NS-7　`tuple[T1, T2, ...]` 位置元素类型标注

**已完成（2026-05-12）** — 详见 `docs/COMPLETED.md` 2026-05-12 NS-7 锚点。

## 工作规则

- 同一时刻只主推一项 NS-x；其余项保留待选。
- NS-4 / NS-5 改动公理层公约或语义错误集，需在分支早期跑 `python -m pytest tests/ -q --tb=short` 评估破坏面。
- 每项完成后，把摘要追加到 `docs/COMPLETED.md`（极简时间线），并把对应条目从本文件移除。
- 出现新的紧要项时，按"先评估优先级、再决定是否替换 NS-x"原则操作。

> **最后更新**：2026-05-12
