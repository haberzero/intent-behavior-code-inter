---
name: code-workflow
description: Use ONLY when the user asks to implement, fix, refactor, or modify IBCI source code. Covers a 6-phase workflow: understand task context, read affected code and check architecture boundaries, design against hard constraints, implement with hygiene rules, test and verify, then clean up. Triggers on "implement X", "fix bug", "refactor", "add feature", "修改代码", "实现", "修复", "重构".
---

# 代码任务控制工作流

> 规范 AI 智能体执行代码任务（实现、修复、重构）的流程。核心：先理解再动手，对照硬约束设计，质量优先于速度。

## 一、流程总览

```
Phase 0 理解任务上下文 -> Phase 1 理解代码上下文 -> Phase 2 方案设计（对照硬约束）
-> Phase 3 实现（遵守卫生纪律）-> Phase 4 测试与验证 -> Phase 5 收尾与清理
```

## 二、各阶段

### Phase 0: 理解任务上下文
读 `tasks_docs/NEXT_STEPS.md` 确认当前主线、任务是否属主线、是否有 GATED/SHELVED 阻塞。读 `tasks_docs/PENDING_TASKS.md` 确认前置条件与阻塞项。涉及语言设计变更先查 `docs/KNOWN_LIMITS.md` 确认非设计排除项。**GATED/SHELVED 任务**：与当前主线目标一致、且不触及对外契约/架构级变更时，可**自行重新评估并解封**（记录解封依据与工作内容）后推进；仅当解封触及架构/契约/破坏性变更时才向用户报告并询问。

### Phase 1: 理解代码上下文
**先读代码再改代码。** 用 grep/glob 搜索相关模块，阅读现有实现与测试，理解模式与覆盖范围。检查架构边界（依赖规则见 `docs/architecture/01_principles.md` §四，禁止架构穿透）。

### Phase 2: 方案设计（对照硬约束）
对照下方"工作模式定论"五条检验方案；追踪根因（设计遗漏/演进残留/临时方案残留），症状层打补丁禁止；检查级联依赖，半修复禁止，明确列出所有必须同修的点；改动公理层或语义错误集标记高影响（Phase 4 须全量 pytest）；新增 AST 字段先查 `docs/architecture/02_metadata_ast.md`。**自主决策**：能自主决断的自行决断并记录理由，直接进入 Phase 3；仅触及 `AGENTS.md` "自主工作循环"上报阈值的项才向用户陈述方案（1-3 句）+ 推荐理由，确认方向后再实现。

### Phase 3: 实现（遵守卫生纪律）
遵循现有命名约定与文件组织，不引入新风格。代码注释卫生、诊断码使用规则、路径约定见 `docs/README.md` §三.6 与 §四--不在此重复，以该文档为准。每完成一个独立修改单元记入临时任务文档。

### Phase 4: 测试与验证
唯一命令 `python -m pytest tests/`（`pytest.ini` 已配置，无需附加 flag）。报告 pass/fail 计数。基线以实跑为准，不冻结数字。改动公理层或语义错误集必须全量 pytest 评估破坏面。

### Phase 5: 收尾与清理
汇报：改动文件、测试结果、后续技术债。重大架构决策写入 `docs/architecture/`（不创建独立 ADR）。新发现的语言级限制更新 `docs/KNOWN_LIMITS.md`。清理临时任务文档（汇报后经用户确认删除）。已完成条目从 `NEXT_STEPS.md` 移除。
**交付纪律（硬原则）**：只做本地 `git commit`；**禁止 push 到 GitHub**——除非用户明确指示允许 push，否则一律禁止 `git push` 到任何远程仓库。push 不因"已授权自主运行"而默许，必须等用户显式授权。

## 三、工作模式定论（方案检验门，最高优先级）

```
1. 禁止 compat shim / 兼容层：新设计就是真设计，旧代码真合并或真删除
2. 禁止胶水实现：不在子系统间塞字符串拼接 / 魔法哨兵 / 隐式约定
3. 禁止 tricky 实现：不靠隐式字符串变换 / 凑巧相等 / 书写顺序掩盖数据依赖
4. 禁止过程式硬编码分发：决策只通过协议驱动（receive() / vtable）
5. 质量优先于速度：技术债先清，潜伏 bug 不允许过渡修复
```

> 完整表述与权威来源：`tasks_docs/NEXT_STEPS.md` "⛔ 工作模式定论"。冲突时以该文档为准。

## 四、配套工程原则

以下原则与工作模式定论同等约束力，方案设计时一并对照：

- **根因优先于症状**：追踪根因，症状层打补丁禁止。
- **禁止半修复**：级联依赖必须全部同修，遗留"旧路径 + 新路径并存"的双通道禁止。
- **Fail-fast 优于静默回退**：配置错误/环境变化应立即暴露，`except: pass` / `hasattr` 兜底回退 / 静默 fallback 改为 raise。
- **封装纪律**：禁止通过 `hasattr` / `setattr` 穿透对象私有属性，走公开协议方法；无公开方法则新增而非穿透。
- **原则优先于行为维持**：既有行为被确认违反一般性工程/架构原则时，优先以原则为准，不以"保持已有行为"为主；改前分析、改后详尽记录变化前后（实现 + 测试 + 文档）供追溯。
- **可推翻 IBCI 自身设计缺陷**：IBCI 自身设计缺陷/失误，即使文档化设计思路也可推翻，按更普适+实践合理+充分理由的方案重建；此类问题通常不询问用户，仅详记决策与工作内容即推进。
- **破坏性重构授权（硬原则）**：当判断符合一般工程经验/普适性/合理架构设计且经分析确实优于 IBCI 现有体系及已有代码时，哪怕设计已被文档记录也允许破坏性重构；不禁止修改已有代码，已有代码优先级低于架构正确性与设计统一一致；默认已授权自主推进（仅详记决策与工作内容）。
- **大范围破坏性重构分支政策（硬原则，用户 2026-08-11 补充"零风险直接合并"细则）**：无法确认边界/危害程度的破坏性重构，100% 授权在独立分支（不污染 main 与 unsafe-vibe-dev，不污染任何计算机环境与用户目录）任意实验；仅当独立隔离分支也无法经自主实验确定技术路线时才将任务配置为阻塞；独立分支禁止直接合并到 unsafe-vibe-dev 或 main，确认技术路线后仅允许手动单独更新 unsafe-vibe-dev；永远不允许触碰主干分支（main）的代码。**零风险细则**：经充分验证零风险/边界清晰的改进（全量 pytest 零回归 + 复核放行，无对外契约/架构级风险）允许**直接合并**到 unsafe-vibe-dev；识别到大风险/无法确认边界的破坏性重构仍走"独立分支 + 手动 cherry-pick 单独更新 unsafe-vibe-dev"。判定以"是否确认零风险"为准，非以改动规模。

## 五、临时任务文档

复杂任务用 `tasks_docs/_code_<short_name>.md` 追踪多修改单元。Phase 5 汇报后经用户确认必须删除，禁止保留已完成文档。
