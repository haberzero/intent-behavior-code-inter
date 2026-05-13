# NEXT_STEPS — 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `docs/PENDING_TASKS.md`；历史归档见 `docs/COMPLETED.md`。
>
> **最后更新**：2026-05-13（NS-4/NS-6/NS-7 已完成；测试体系Phase 2完成；代码健康度审计完成；semantic_v2 开发完成）

---

## 🎯 当前最紧要：semantic_v2 测试验证 (Phase 3)

**状态**: ✅ Phase 1 & 2 已完成 → ⏸️ Phase 3 待开启

semantic_v2 的**代码实现已全部完成**（6 个 Pass + 基础设施，共 1,929 行），架构已优化并文档化。**现在可以立即开启测试流程**，开始 V2 对 V1 的逐步替换和逻辑正确性验证。

### 短期任务（1-2 周，P0 优先级）

**Task 1: 创建测试基础设施** [估算: 4-6h]
- [ ] 创建 `tests/compiler/semantic_v2/` 目录结构
- [ ] 编写单元测试框架（每个 Pass 独立测试）
- [ ] 编写集成测试（完整管道测试）
- [ ] 创建测试用例库（覆盖各种 IBCI 语法）
- **目标**: 至少 20 个单元测试 + 10 个集成测试

**Task 2: V1/V2 并行验证工具** [估算: 4-6h]
- [ ] 实现 `tools/validate_semantic_v2.py` 自动化对比工具
- [ ] 验证维度：符号表、类型绑定、错误信息、元数据
- [ ] 实现差异可视化和分析报告
- **目标**: V1/V2 输出差异可量化对比

**Task 3: 运行回归测试** [估算: 2-3h, P1]
- [ ] 使用现有 V1 测试套件验证 V2
- [ ] 记录和分析 V1/V2 差异
- [ ] 修复 V2 中发现的 bug
- **成功标准**: V2 错误率 < V1，差异可解释

### 中期任务（2-4 周）

**Task 4: 引擎集成** [估算: 6-8h, P1]
- [ ] IBCIEngine 添加 `use_semantic_v2` 配置参数
- [ ] 修改 `compile_string()` 支持 V2 路径
- [ ] 创建适配器层（统一 V1/V2 输出格式）
- [ ] 添加性能监控（对比 V1/V2 性能）

**Task 5: 文档完善** [估算: 2-4h, P2]
- [ ] 创建 `MIGRATION_GUIDE.md` - V1 → V2 迁移指南
- [ ] 创建 `SEMANTIC_V2_API.md` - V2 API 文档
- [ ] 创建 `TESTING_STRATEGY.md` - 测试策略文档
- [ ] 更新主 README 说明 V2 状态

### 成功指标

- **短期（2周）**: 30+ 测试通过，V1/V2 对比工具运行成功
- **中期（1月）**: V2 集成到 Engine，测试覆盖率 > 80%，V1/V2 差异 < 5%
- **长期（2月）**: V2 稳定运行，用户可选使用 V2

**详见**: `docs/SEMANTIC_REFACTORING_PLAN.md` 完整重构规划与 `docs/METADATA_ARCHITECTURE.md` 架构设计

---

## ⚠️ 代码健康度重构计划

**代码健康度审计**已识别出紧要问题。建议与 semantic_v2 测试并行处理：

- **超大文件拆分**: 8 个文件 >1000 行
- **深层嵌套逻辑优化**: 7 处复杂条件分支
- ✅ **局部导入清理**: 已完成（2026-05-13）

**详见**: `docs/CODE_HEALTH_REFACTORING.md`（统一的审计与重构指南，150-200 小时工作量）

**Phase 1 任务清单**（约 50-60 小时）:
1. ✅ 清理标准库局部导入（已完成）
2. ✅ 简化 LLM 结果解析逻辑（已完成，2026-05-13）
3. ✅ semantic_analyzer.py 重构为 semantic_v2（Phase 1 & 2 已完成，Phase 3 测试中）

---

## 主线完成情况

类型系统 M1–M5、VM CPS 主线、intent 系统 OOP 化（NS-2 全部 4 步）、LLM 调用路径合并入 CPS 调度循环（NS-1）、lambda/snapshot/behavior 跨帧 EC 边界（NS-3）、intent_context 高级 OOP 场景（PT-2.1）、IbIntentContext 序列化/反序列化（PT-2.2）、`_evaluate_segments` CPS 化、PT-1.2（llmexcept 错误历史）、PT-1.3（llmexcept 嵌套深度限制）以及 PT-3.3（`idbg.protection_map()`）均已完成。**当前主线（VM / Intent / llmexcept / 类型系统骨架）无开放的 P0/P1 任务**。

新提出的下一阶段语言收尾项见下：均经过当次事实核查后落定技术路线，仅缺工时；可按优先级依次主推。**建议在处理重构任务后再继续语言特性开发**。

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

> **最后更新**：2026-05-13
