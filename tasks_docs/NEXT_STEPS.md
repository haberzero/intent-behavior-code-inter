# NEXT_STEPS - 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `tasks_docs/PENDING_TASKS.md`。
> 已知语言级限制见 `docs/KNOWN_LIMITS.md`。
>
> **最后更新**：2026-07-31（新主线立项：函数参数机制——默认/具名/动态参数，规划见 `tasks_docs/_function_params.md`）

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

## 当前主线：函数参数机制（默认 / 具名 / 动态参数）

> **下一里程碑**（2026-07-31 立项）。调研已完成：当前全链路仅位置参数（`IbKeyword` AST 预留未激活、`IbArg` 无 default/kind、parser 硬编码 `keywords=[]`、vtable `param_types` 固定）；lexer `STAR`/`STAR_STAR` 已就绪。可行性成立，规模为语言级里程碑。受益项：PT-ARCH-28（`file.write` 统一 API）、PT-PHASE4-1（`register_model(**kwargs)`）、函数 API 设计僵硬度。
>
> 细化规划与相位化实施（P1 AST+Parser → P2 语义 → P3 运行时统一绑定器 → P4 应用+文档）见 `tasks_docs/_function_params.md`。设计决策待确认（覆盖面 / Python 语义对齐 / vtable 签名格式）。

**已完成**（前主线，LLM 并行化与状态重设计，提交见 `git log`）：
- llmexcept 机制统一 + 状态模型重设计（Phase A，U1-U7）
- 环境与依赖正规化 + MOCK 服务化（B0：pyproject 分组 / conda env / `MockServer`）
- Phase B dispatch 修复（运行时拆分 + 规则化调度，4 项 skip 解锁）
- `ai.run_batch` 批量并发原语（并发 map，公理 LLM-4）

**次要候选**（新主线之外）：
- U5 命名审查；`_pending_futures` 泄漏观测性；PT-HEALTH-1/2/3——见 `PENDING_TASKS.md`。

---

## 独立并行任务

- **测试体系治理与彻底重构**：独立、较低优先级，`tasks_docs/TEST_REFACTOR.md`（含 4 份调研报告 `TEST_REFACTOR_REPORTS.md`），不与主线混置。
- **media Phase 4**（多模态容器）：已暂停，代码层零启动，降级未来低优先级（`PENDING_TASKS.md` §六）。

---

## 工作规则

- **每次开新分支前**，先复跑 `python -m pytest tests/`，把当前 pass/fail 计数写在 PR 描述里。
- **同一时刻只主推一个 P0 阶段**。
- **工作模式定论优先**：任何与"⛔ 工作模式定论"冲突的提议一律以定论为准。
- 任何改动公理层公约或语义错误集的任务，需在分支早期跑全量 pytest 评估破坏面。
- 每个阶段完成后，用描述性 commit message 记录完成的工作，并把对应条目从本文件移除。
- **本文件不冻结具体测试通过数字**。
- 重大架构决策记录在技术文档中（`docs/ARCHITECTURE.md`、`docs/architecture/02_metadata_ast.md`、`docs/architecture/01_principles.md`），不再使用独立 ADR 文件。
