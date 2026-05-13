# NEXT_STEPS — 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `docs/PENDING_TASKS.md`；历史归档见 `docs/COMPLETED.md`。
>
> **最后更新**：2026-05-13（semantic_v2 Phase 3 已启动，测试基础设施和引擎集成已完成）

---

## 🎯 当前最紧要：semantic_v2 Phase 3 测试验证与完善

**状态**: ✅ 测试基础设施已建立 → ✅ 引擎集成已完成 → ⏸️ 测试验证进行中

semantic_v2 的**代码实现和引擎集成已全部完成**。现已建立完整测试框架和V1/V2对比验证工具，引擎支持通过 `use_semantic_v2=True` 参数选择使用V2。**下一步是运行测试验证并修复发现的问题**。

### 已完成的工作（2026-05-13）

**✅ Task 1: 创建测试基础设施** [完成]
- ✅ 创建 `tests/compiler/semantic_v2/` 目录结构
- ✅ 实现 `test_symbol_collection_pass.py` 单元测试（7个测试用例）
- ✅ 实现 `test_pipeline_integration.py` 集成测试（10个测试用例）
- ✅ 创建测试fixture和helper函数

**✅ Task 2: V1/V2 并行验证工具** [完成]
- ✅ 实现 `tools/validate_semantic_v2.py` 自动化对比工具
- ✅ 对比维度：符号表、类型绑定、错误信息
- ✅ 生成Markdown格式差异分析报告
- ✅ 默认7个测试用例覆盖核心场景

**✅ Task 4: 引擎集成** [完成]
- ✅ IBCIEngine 添加 `use_semantic_v2` 参数
- ✅ Scheduler 添加 `use_semantic_v2` 参数
- ✅ 创建 `SemanticV2Adapter` 适配V1/V2接口
- ✅ 实现 `engine_integration.py` 模块
- ✅ 条件选择V1或V2分析器

### 当前任务（1周内，P0 优先级）

**Task 3: 运行测试与验证** [估算: 2-3h, 进行中]
- [ ] 运行单元测试验证各Pass功能
- [ ] 运行集成测试验证完整管道
- [ ] 运行 `validate_semantic_v2.py` 生成V1/V2对比报告
- [ ] 分析差异并修复V2中的bug
- [ ] 确保差异率 < 5%

**Task 5: 文档完善** [估算: 2-4h]
- [ ] 更新 `NEXT_STEPS.md` 记录最新进展
- [ ] 创建 `docs/SEMANTIC_V2_USAGE.md` - V2使用指南
- [ ] 创建 `docs/V1_TO_V2_MIGRATION.md` - 迁移指南
- [ ] 更新主 README 说明 V2 状态

### 使用方法

**启用 semantic_v2:**
```python
from core.engine import IBCIEngine

# 使用V2语义分析器
engine = IBCIEngine(use_semantic_v2=True)

# 使用V1语义分析器（默认）
engine = IBCIEngine(use_semantic_v2=False)
```

**运行验证工具:**
```bash
python tools/validate_semantic_v2.py --verbose
```

**运行测试:**
```bash
python -m pytest tests/compiler/semantic_v2/ -v
```

### 成功指标

- **短期（1周）**:
  - ✅ 测试基础设施完成
  - ✅ 引擎集成完成
  - ⏸️ 30+ 测试通过
  - ⏸️ V1/V2差异 < 5%

- **中期（2周）**:
  - V2测试覆盖率 > 80%
  - V2性能数据收集完成
  - 发现的bug全部修复

- **长期（1月）**:
  - V2稳定运行
  - 用户可选使用V2
  - 准备默认切换到V2

**详见**:
- `docs/SEMANTIC_REFACTORING_PLAN.md` - 完整重构规划
- `docs/METADATA_ARCHITECTURE.md` - 架构设计
- `tools/validate_semantic_v2.py` - 验证工具
- `tests/compiler/semantic_v2/` - 测试套件

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
