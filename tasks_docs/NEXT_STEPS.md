# NEXT_STEPS - 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `tasks_docs/PENDING_TASKS.md`。
> 已知语言级限制见 `docs/KNOWN_LIMITS.md`。
>
> **最后更新**：2026-07-30（主线切换为 MOCK 服务化与 LLM 并发调度；测试体系重构降级为独立任务）

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

**2026-07-30 实测结果**：`1186 passed, 8 skipped`（0 failures/errors，linux / bash）

> 当前基线以实跑为准，不冻结数字。

---

## 当前主线：MOCK 服务化与 LLM 并发调度

> **media Phase 4（MediaAxiom + IbMedia 全模态容器）已暂停**，降级为未来低优先级任务（详见 `tasks_docs/PENDING_TASKS.md` §六）。代码层零启动，仅设计文档存在。
>
> 缺陷复查已全部完成。当前最优先任务：MOCK 机制升级为可编程独立进程 HTTP 服务（模拟延迟/并发/失败/流式），并修复 `dispatch_eager` 数据竞争（PT-4.7），解锁 4 项 dispatch 专属 skip 测试。细化规划见 `tasks_docs/_mock_concurrency.md`。**Phase 0 设计冻结前不动代码。**
>
> 测试体系治理与彻底重构降为**独立、较低优先级**任务，单独立项于 `tasks_docs/TEST_REFACTOR.md`（含 4 份调研报告 `TEST_REFACTOR_REPORTS.md`），不与本主线混置。

---

## P1 后续任务

以下任务不影响 media Phase 4 的开工决策：

1. **PT-ARCH-22**：全项目文件命名清理（暂缓，独立窗口执行）。
2. **PT-ARCH-28**：`file` 模块统一写入 API + 函数动态/命名参数支持（临时 `write_new` 已就位）。
3. **PT-ARCH-29**：命名历史包袱全方位代码卫生清理（代码层零残留，历史文档标注待做）。
4. **PT-ARCH-30**：内置 `file` 模块命名风险清理（长期需重命名，如 `fs`）。

详见 `tasks_docs/PENDING_TASKS.md`。

---

## 工作规则

- **每次开新分支前**，先复跑 `python -m pytest tests/`，把当前 pass/fail 计数写在 PR 描述里。
- **同一时刻只主推一个 P0 阶段**。
- **工作模式定论优先**：任何与"⛔ 工作模式定论"冲突的提议一律以定论为准。
- 任何改动公理层公约或语义错误集的任务，需在分支早期跑全量 pytest 评估破坏面。
- 每个阶段完成后，用描述性 commit message 记录完成的工作，并把对应条目从本文件移除。
- **本文件不冻结具体测试通过数字**。
- 重大架构决策记录在技术文档中（`docs/ARCHITECTURE.md`、`docs/architecture/02_metadata_ast.md`、`docs/architecture/01_principles.md`），不再使用独立 ADR 文件。
