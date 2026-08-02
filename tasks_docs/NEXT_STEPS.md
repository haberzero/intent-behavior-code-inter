# NEXT_STEPS - 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `tasks_docs/PENDING_TASKS.md`。
> 已知语言级限制见 `docs/KNOWN_LIMITS.md`。
>
> **最后更新**：2026-08-01（任务控制清洁：函数参数机制家族收官项删除/归并；PENDING §七 反射排查解封为下一任务）

---

## ⛔ 工作模式定论（强制，凌驾于本文件一切任务之上）

> **扎实推进，禁止任何形式的快速实现 / 兼容层 / 胶水实现 / tricky 实现。**

1. **禁止 compat shim / 兼容层**：不写"过渡性包装"。新设计就是真设计，旧代码要么真合并、要么真删除。
2. **禁止胶水实现**：不在两个不统一的子系统之间塞字符串拼接 / 魔法哨兵 / 隐式约定来强行粘合。
3. **禁止 tricky 实现**：不靠隐式字符串变换承载语义；不靠"凑巧相等"；不靠书写顺序掩盖数据依赖。
4. **禁止过程式硬编码分发**：同一决策只通过协议驱动（`receive()` / vtable）完成，不在运行流程里写 `if 能力标志位` 分支。
5. **质量优先于速度**：技术债必须先清，再推进依赖它的特性。潜伏 bug 不允许过渡修复。

---

## 当前测试基线

```bash
python -m pytest tests/
```

> 基线以实跑为准，不冻结数字。

---

## 当前主线：无（函数参数机制家族已全线收官）

> 2026-08-01 完成并推送（`git log`：`f3b54e8`…`3dc09ba`）：函数参数机制（默认/具名/动态参数 + `file.write` 统一 API）、架构决策收尾、语义/运行时解析算法收敛（`core/kernel/arg_binding.py` 共享纯核心）、原生 `**kwargs` 分传（VAR_KEYWORD）、PT-HEALTH-1（provider 能力探测协议化）。详细记录见 git 历史；已完成条目已从本文件移除。
>
> **PT-PHASE4-1（已封存）受益**：`register_model(..., **kwargs)` 的运行时前置（kwargs 收集 + 原生分传）已全部就绪，解封恢复时只需声明 vtable VAR_KEYWORD。

## 下一任务：反射规避架构缺陷全仓排查（已解封，新 session 首项）

> **来源**：处理 PT-HEALTH-1 时用户裁定——代码中可能存在更多"用反射/探测规避架构设计缺陷"的代码，需全仓找出并**确认背后是否确为架构缺陷**（若是则修架构根因，而非继续用反射绕开）。完整任务定义原为 `PENDING_TASKS.md` §七，现已移入本文档（单点真理）。

- 全仓扫描 `hasattr(obj, 'method')` / `getattr(obj, 'attr', default)` / 静默 `except` 等能力探测（判定基准见 `.opencode/skills/code-quality/SKILL.md` 健康诊断十查 §5、§8 与兜底识别）。
- 每个命中点分类：**职责分离型 fallback**（协议声明能力、显式降级路径 → 允许保留）vs **为规避架构问题而做的穿透**（→ 禁止，修架构根因而非用反射绕开）。
- 已发现命中点（先处理）：`core/runtime/vm/handlers/_shared.py:449-451` `_get_max_retry`——`hasattr(cap_reg, "get")` / `hasattr(llm_provider, "get_retry")`（与 PT-HEALTH-1 同族，`get_retry` 可并入 provider 协议或显式能力标志）。
- 判定分界：无法自主决断的（架构取舍 / 契约变更 / 用户意图）→ 上报；可自主的（根因明确）→ 直接修。
- 验证：`python -m pytest tests/` 全量，零回归。

---

## 独立并行任务

- **测试体系治理与彻底重构**：独立、较低优先级，`tasks_docs/TEST_REFACTOR.md`（含 4 份调研报告 `TEST_REFACTOR_REPORTS.md`），不与主线混置。
- **media Phase 4**（多模态容器）：**已彻底封存（2026-08-01）**，短期不考虑实现，恢复需显式解封；代码层零启动（`PENDING_TASKS.md` §六）。

---

## 工作规则

- **每次开新分支前**，先复跑 `python -m pytest tests/`，把当前 pass/fail 计数写在 PR 描述里。
- **同一时刻只主推一个 P0 阶段**。
- **工作模式定论优先**：任何与"⛔ 工作模式定论"冲突的提议一律以定论为准。
- 任何改动公理层公约或语义错误集的任务，需在分支早期跑全量 pytest 评估破坏面。
- 每个阶段完成后，用描述性 commit message 记录完成的工作，并把对应条目从本文件移除。
- **本文件不冻结具体测试通过数字**。
- 重大架构决策记录在技术文档中（`docs/ARCHITECTURE.md`、`docs/architecture/02_metadata_ast.md`、`docs/architecture/01_principles.md`），不再使用独立 ADR 文件。
