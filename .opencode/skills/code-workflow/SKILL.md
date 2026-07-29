---
name: code-workflow
description: Use ONLY when the user asks to implement, fix, refactor, or modify IBCI source code. Covers a 6-phase workflow: understand task context, read affected code and check architecture boundaries, design against hard constraints, implement with hygiene rules, test and verify, then clean up. Triggers on "implement X", "fix bug", "refactor", "add feature", "修改代码", "实现", "修复", "重构".
---

# IBCI 代码任务控制工作流

> 本 skill 规范 AI 智能体在 IBCI 项目中执行代码任务（实现、修复、重构）的工作流程。核心原则来自 `tasks_docs/NEXT_STEPS.md` 的"⛔ 工作模式定论"——扎实推进，质量优先于速度。

---

## 一、工作流程总览

```
Phase 0: 理解任务上下文
Phase 1: 理解代码上下文
Phase 2: 方案设计（对照硬约束）
Phase 3: 实现（遵守卫生纪律）
Phase 4: 测试与验证
Phase 5: 收尾与清理
```

---

## 二、各阶段详述

### Phase 0: 理解任务上下文

**动作**：
1. 读取 `tasks_docs/NEXT_STEPS.md`，确认：
   - 当前 P0 主线是什么
   - 任务是否属于当前主线（不属于需与用户确认优先级）
   - 是否有 GATED 或 SHELVED 标记阻止该任务
2. 读取 `tasks_docs/PENDING_TASKS.md`，确认：
   - 任务的 PT 编号和前置条件
   - 是否有阻塞项未完成
3. 如果任务涉及语言设计变更，先查 `docs/KNOWN_LIMITS.md`——确认不是设计排除项。

**决策点**：如果任务处于 GATED 或 SHELVED 状态，向用户明确报告阻塞原因，询问是否解封。

**输出**：对任务优先级的确认 + 前置条件检查。

### Phase 1: 理解代码上下文

**动作**：
1. **先读代码，再改代码**。禁止在未理解现有实现的情况下编写修改方案。
2. 使用 `grep` / `glob` 搜索相关模块：
   - 编译器相关 → `core/compiler/`
   - 运行时/VM 相关 → `core/runtime/`
   - 类型系统相关 → `core/kernel/axioms/` + `core/kernel/spec/`
   - AST 节点相关 → `core/kernel/ast.py`
   - 诊断码相关 → `core/base/diagnostics/codes.py`
3. 检查架构边界：
   - 不引入 `kernel → runtime` 或 `runtime → compiler` 的架构穿透（见 `docs/architecture/01_principles.md` §四）
   - compiler 和 runtime 是兄弟层，两者都只能依赖 kernel 和 base
4. 检查现有的测试覆盖：
   - `tests/` 目录结构：单元测试在 `tests/` 下按模块组织，e2e 在 `tests/e2e/`
   - 阅读相关测试文件，理解现有测试的模式和覆盖范围

**输出**：代码理解笔记 + 架构依赖检查结果。

### Phase 2: 方案设计（对照硬约束）

**输入**：Phase 0-1 的上下文理解。

**动作**：
1. 对照 **⛔ 工作模式定论**（`tasks_docs/NEXT_STEPS.md` §工作模式定论）检验方案：
   - **禁止 compat shim**：方案是否引入了过渡性包装？新设计必须是真设计。
   - **禁止胶水实现**：方案是否在两个子系统之间塞字符串拼接/魔法哨兵/隐式约定？
   - **禁止 tricky 实现**：方案是否依赖隐式字符串变换、凑巧相等、书写顺序掩盖数据依赖？
   - **禁止过程式硬编码分发**：决策是否通过协议驱动（`receive()` / vtable）完成？
   - **质量优先于速度**：是否存在先修技术债的需求？
2. **追踪根因**：问题是从哪里来的（设计遗漏 / 演进残留 / 临时方案残留）？方案是否在根因层面解决？症状层面打补丁（如"加 setter 但不清死分支"）禁止。
3. **检查级联依赖**：修复是否涉及多个必须同修的点？只修一处而遗留"旧路径 + 新路径并存"的半修复禁止。明确列出所有必须同修的文件和改动点。
4. 如果改动公理层（`core/kernel/axioms/`）或语义错误集，标记为**高影响**--需在 Phase 4 跑全量 pytest。
5. 如果新增 AST 字段或节点类型，先查 `docs/architecture/02_metadata_ast.md` 确认影响面。
6. 如果涉及新诊断码，在 `core/base/diagnostics/codes.py` 中定义命名常量，禁止在代码中使用字符串字面量。
7. 向用户简洁陈述方案（1-3 句），确认方向后再进入实现。

**决策点**：方案与工作模式定论冲突 → 驳回，重新设计。用户坚持 → 记录分歧原因，标记风险。

**输出**：获批的方案说明。

### Phase 3: 实现（遵守卫生纪律）

**动作**：
1. 遵循现有代码的命名约定、文件组织方式。**不引入新的代码风格**。
2. **代码注释卫生**（来自 `docs/README.md` §三.6）：
   - 注释只写**功能设计**和**已知问题**
   - 禁止出现：任务编号（PT-xxx）、ADR 编号、设计代号（D1/D2/C2/G1-G6）、历史叙述（"原实现"、"旧 bug"）、文档章节指针（"见 §6.1"、"见 docs/xxx.md"）
   - 谨慎出现：诊断码常量（`SEM_TYPE_MISMATCH`）、公理码（`EXEC-1`）、功能性术语（"锚点"、"Phase N"）。仅当代码逻辑直接涉及诊断码判断、公理合规约束或算法阶段编号时出现——非必要不使用，不因"规范允许"而滥用。
3. **诊断码使用规则**：
   - 新增诊断码 → 在 `codes.py` 定义常量
   - 引用诊断码 → `from core.base.diagnostics.codes import SEM_XXX` → `code=SEM_XXX`
   - 禁止：`code="SEM_TYPE_MISMATCH"` 字符串字面量
4. **路径引用**：以 `docs/README.md` §四"代码路径约定"为准（多个模块已重构为包）。
5. 每完成一个独立修改单元，记录到临时任务文档（如 `tasks_docs/_code_<task>.md`）。

**输出**：修改后的代码 + 更新的临时任务文档。

### Phase 4: 测试与验证

**动作**：
1. **运行测试**：唯一命令 `python -m pytest tests/`。无需附加 flag（`pytest.ini` 已配置）。
2. 将测试的 pass/fail 计数报告给用户。
3. 如果当前基线失败（与 NEXT_STEPS.md 顶部记录不一致），先汇报再分析原因——可能是环境问题或已有回归。
4. 如果改动涉及公理层或语义错误集，**必须**全量跑 pytest 评估破坏面。

**输出**：测试通过/失败报告。

### Phase 5: 收尾与清理

**动作**：
1. 向用户汇报完成情况：
   - 改动了哪些文件
   - 测试结果（pass/fail 计数）
   - 是否有需要后续处理的技术债
2. 如果改动涉及重大架构决策 → 写入 `docs/architecture/` 对应章节（不创建独立 ADR 文件）。
3. 如果发现了新的语言级限制 → 更新 `docs/KNOWN_LIMITS.md`。
4. 清理临时任务文档：汇报后经用户确认，删除 `tasks_docs/_code_*.md`。
5. 如果当前文件的任务条目已完成，从 `tasks_docs/NEXT_STEPS.md` 中移除对应条目。

**输出**：完成汇报 + 已清理的临时任务文档。

---

## 三、硬约束速查

### 3.1 工作模式定论（最高优先级）

```
1. 禁止 compat shim / 兼容层
2. 禁止胶水实现
3. 禁止 tricky 实现
4. 禁止过程式硬编码分发（协议驱动：receive() / vtable）
5. 质量优先于速度（技术债先清，潜伏 bug 不允许过渡修复）
```

### 3.2 架构依赖规则

```
kernel → base       ✅
compiler → kernel   ✅
runtime → kernel    ✅
kernel → runtime    ❌ 架构穿透
runtime → compiler  ❌ 架构穿透
```

### 3.3 代码注释卫生

| 禁止 | 谨慎使用（仅当代码逻辑直接涉及时） |
|------|------|
| PT-xxx, ADR-xxx | 功能设计说明 |
| D1/D2/C2/G1-G6 等设计代号 | 诊断码常量（SEM_XXX） |
| "原实现"、"旧 bug"、"修复见PR" | 公理码（EXEC-1, OM-2 等） |
| "见 §6.1"、"docs/xxx.md" | 功能性术语（Layer N, Phase N） |
| "经过讨论/验证/实测..." | 已知问题描述 |

**原则**：右列术语仅在代码注释中**不可或缺**时出现——即代码逻辑实际涉及该诊断码的分发、该公理合规约束、或该算法阶段编号。不因"规范允许"而在无关代码中引用。

### 3.4 诊断码规则

```python
# ✅ 正确
from core.base.diagnostics.codes import SEM_TYPE_MISMATCH
self.error("msg", node, code=SEM_TYPE_MISMATCH)

# ❌ 错误
self.error("msg", node, code="SEM_TYPE_MISMATCH")
```

### 3.5 测试纪律

- 唯一命令：`python -m pytest tests/`
- 不可附加自定义 flag
- 开新分支前复跑
- 公理层/语义错误集改动 → 全量 pytest
- pass/fail 计数写入 PR 描述
- 不冻结具体数字

### 3.6 设计原则速查

以下原则从工程实践中提炼，与工作模式定论同等约束力：

**根因优先于症状**：方案设计前必须追踪根因（设计遗漏 / 演进残留 / 临时方案残留）。症状层面打补丁禁止。示例：`setattr` 穿透私有属性是症状，根因是 `hydrate` 死分支 + setter 缺失；只加 setter 不清死分支 = 半修复。

**禁止半修复**：修复有级联依赖时必须全部同修。遗留"旧路径 + 新路径并存"的半修复禁止。示例：ServiceContext 注入修复必须三处同修（加 setter + 清死分支 + 清全部 setattr），只修一处留下双通道破窗。

**Fail-fast 优于静默回退**：配置错误/环境变化应立即暴露，不静默降级。`except Exception: pass` / `hasattr` 兜底回退 / `else val` 静默 fallback 均应改为 raise 或显式错误。示例：`llm_uncertain` 未注册改 raise；`_resolve_isolated_path` 移除 broad except。

**封装纪律**：禁止通过 `hasattr`/`setattr` 访问其它对象的私有属性（`_xxx`）。必须走公开协议方法；无公开方法时新增方法而非穿透。示例：`_intent_ctx` 22 处跨文件穿透 -> 新增 `enter_intent_scope`/`exit_intent_scope`/`replace_intent_context` 公开方法 + Protocol 补全。

---

## 四、关键文件速查表

| 场景 | 必查文件 |
|------|---------|
| 任务优先级 | `tasks_docs/NEXT_STEPS.md` |
| 阻塞/搁置任务 | `tasks_docs/PENDING_TASKS.md` |
| 语言设计限制 | `docs/KNOWN_LIMITS.md` |
| 架构依赖规则 | `docs/architecture/01_principles.md` §四 |
| 新增 AST 字段 | `docs/architecture/02_metadata_ast.md` |
| VM 执行模型 | `docs/architecture/04_vm_interpreter.md` + `05_vm_specification.md` |
| 类型系统设计 | `docs/architecture/03_type_system.md` |
| 代码注释纪律 | `docs/README.md` §三.6 |
| 诊断码定义 | `core/base/diagnostics/codes.py` |
| 路径约定 | `docs/README.md` §四 |
| 测试基线 | `tasks_docs/NEXT_STEPS.md` 顶部 |
| 当前缺陷 | `tasks_docs/_defect_review.md` |

---

## 五、临时任务文档规范

**创建时机**：Phase 3（实现开始时），任务复杂到需要追踪多个修改单元时。

**格式**：
```markdown
# 代码任务追踪：<简短描述>

> 临时任务文档。任务完成后删除。

## Phase 3: 实现
- [ ] 修改文件 A：<说明>
- [ ] 修改文件 B：<说明>

## Phase 4: 测试
- [ ] 运行 pytest：<预期结果>
- [ ] 修复测试回归（如有）

## Phase 5: 收尾
- [ ] 向用户汇报
- [ ] 更新 KNOWN_LIMITS.md（如需要）
- [ ] 清理本文档
```

**位置**：`tasks_docs/_code_<short_name>.md`。

**生命周期规则**（强制）：Phase 5 汇报后经用户确认，必须删除。禁止保留已完成的临时任务文档。

---

## 六、与 AGENTS.md 的关系

`AGENTS.md` 是本 skill 的上位文档——其中的"不要做的事"和"编码与平台注意"是本 skill 规则的来源之一。本 skill 不重复 AGENTS.md 的内容（单点真理），而是将分散在多个文件（NEXT_STEPS、PENDING_TASKS、架构原则、WRITING_GUIDE）中的代码相关规则整合为可执行的工作流。