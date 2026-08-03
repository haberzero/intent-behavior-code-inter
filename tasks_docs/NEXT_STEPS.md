# NEXT_STEPS - 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `tasks_docs/PENDING_TASKS.md`。
> 已知语言级限制见 `docs/KNOWN_LIMITS.md`。
>
> **最后更新**：2026-08-02（新主线确立：LLM 混合执行核心加固——PT-TEST-9 / PT-HEALTH-3 / PT-4.2；多媒体无限期搁置）
---

## ⛔ 工作模式定论（强制，凌驾于本文件一切任务之上）

> **扎实推进，禁止任何形式的快速实现 / 兼容层 / 胶水实现 / tricky 实现。**

1. **禁止 compat shim / 兼容层**：不写"过渡性包装"。新设计就是真设计，旧代码要么真合并、要么真删除。
2. **禁止胶水实现**：不在两个不统一的子系统之间塞字符串拼接 / 魔法哨兵 / 隐式约定来强行粘合。
3. **禁止 tricky 实现**：不靠隐式字符串变换承载语义；不靠"凑巧相等"；不靠书写顺序掩盖数据依赖。
4. **禁止过程式硬编码分发**：同一决策只通过协议驱动（`receive()` / vtable）完成，不在运行流程里写 `if 能力标志位` 分支。
5. **质量优先于速度**：技术债必须先清，再推进依赖它的特性。潜伏 bug 不允许过渡修复。
6. **原则优先于行为维持**：当既有行为被确认违反一般性的工程/架构原则时，优先以架构原则与工程原则为准，**不以"保持已有行为"为主**。改前先分析，改后详尽记录变化前后（供追溯）。"已有代码不因'已在仓库里'而正确"。
7. **可推翻 IBCI 自身设计缺陷**：若为 IBCI 自身的设计缺陷/失误，**哪怕该设计思路已在文档中明确记录，也可被推翻**，按更普适、实践上更合理且有充分理由的方案重建。此类问题（IBCI 自身设计缺陷修正）**通常可不询问用户**，仅需详尽记录决策依据与工作内容（实现 + 测试 + 文档的变化前后）即推进。

---

## 当前测试基线

```bash
python -m pytest tests/
```

> 基线以实跑为准，不冻结数字。

---

## 当前主线：LLM 真正可用的并行化 + 同步异步

> **用户裁定（2026-08-02）**：多媒体无限期搁置。主线为 **LLM 真正可用的并行化、同步异步等相关工作**——即现有并行 dispatch（`dispatch_eager`/`resolve`/`run_batch`）从"能用"到"真正可靠可用"，并推进语言级 async/await 与 VM 多任务挂起/恢复（原 PENDING_TASKS §二 L3 协程方向，由 SHELVED 升为主线）。
>
> **范围分解**：
> 1. **并行可靠性地基**：executor/behavior 共享状态**去共享化**（per-task/per-dispatch 所有权）——`_expected_type_stack`/`_current_call_info`/意图上下文。根因修复（状态不应跨线程共享），非加锁症状层
> 2. **VM 调度器多任务化**：单根任务 → 多任务协作调度（`Signal.YIELD` 挂起/恢复、任务句柄、快照覆盖 yield 点）——L3 解封落地
> 3. **语言级 async/await**：作为多任务调度器之上的显式表面（**暂缓完整语言机制**，Stage 3 落地）
> 4. **宿主级异步**：`host.run_isolated()` 异步句柄（PT-3.1）、`ReceiveMode` 演进（PT-3.2）
>
> **架构定案（2026-08-02，Option A 混合模型）**：LLM IO 保持线程池但**只做纯 IO 边界**（不触碰共享状态）；VM 多任务协作调度（单线程、无锁，公理调度+单次锁定）；语言级 async/await 为演进目标。**核心洞察：共享状态去共享化 = 多任务调度器地基，Stage 1 与 Stage 2 是同一重构的两面。**
>
> **任务分层（2026-08-02 梳理定案）**：
> - **Tier 1 主线组成部分**：PT-HEALTH-3（executor 共享状态 → Stage 1）、PT-3.1/PT-3.2（宿主异步 → Stage 4）
> - **Tier 2 可靠性地基（前置/并行推进）**：PT-TEST-9 probe_model 测试——reasoning 判定决定每个 LLM 调用行为；目标含"probe 为 setup-time 显式动作 + `_model_capabilities` 并行阶段只读不变式 + 三路径测试"
> - **Tier 3 交叉独立（顺带，不阻塞）**：PT-SEM-1.1 错误用户友好化（覆盖并行新增错误类别）、PT-4.2 `__call__` 协议（async 边缘交集，保持独立）
> - **Tier 4 独立**：PT-SEM-1 其余 / PT-SEM-4 / PT-4.1/4.4/4.5
> - **主线隐含新任务（进 PENDING）**：并发正确性验证方法、LLMFuture 生命周期/错误语义、线程池资源生命周期
>
> **关联**：PT-TEST-9（probe_model 测试）为并行可靠性的组成；PT-HEALTH-3 核心并入 Stage 1；PT-4.2（`__call__` 协议）降为次要。
>
> **验证**：每批 `python -m pytest tests/` 全量零回归。
>
> **Stage 2 地基已落地（2026-08-03）**：
> - `TaskScheduler` 多任务协作调度器（纯 stdlib，`Waitable` 协议）+ `run_many` 多根并发入口
> - `TaskScheduler` 结果按**提交序**收集（非完成序），`run_many` 按 roots 索引取结果可靠
> - `leaf.py` `vm_handle_IbName` 对 `LLMFuture` 改 `yield from resolve_future_cps` 挂起（单脚本内 LLM 阻塞可挂起，对齐多根语义）
> - Stage 1 三项核验完成（parse_result 线程安全 / `_prompt`+`_llm_function` 无实例级可变状态 / 意图 fork 隔离完整）
>
> **下一步**：语言级 `async`/`await`（Stage 3，暂缓）——在统一 `Waitable` 地基之上的显式语法表面。宿主异步（PT-3.1/3.2）已落地（见 §七、7.7 与 PENDING_TASKS §二）。

---

## 独立并行任务

- **测试体系治理与彻底重构**：独立、较低优先级，`tasks_docs/TEST_REFACTOR.md`（含 4 份调研报告 `TEST_REFACTOR_REPORTS.md`），不与主线混置。
- **技术债审计分支任务**：PT-SMELL-1/2/3（`CODE_SMELL_AUDIT.md` / `BRANCH_NESTING_AUDIT.md` / `LOCAL_IMPORT_AUDIT.md`），独立分支执行。
- **media Phase 4**（多模态容器）：**已彻底封存（2026-08-01），且 2026-08-02 起无限期搁置**；恢复需显式解封并重估；代码层零启动（`PENDING_TASKS.md` §六）。

---

## 工作规则

- **每次开新分支前**，先复跑 `python -m pytest tests/`，把当前 pass/fail 计数写在 PR 描述里。
- **同一时刻只主推一个 P0 阶段**。
- **工作模式定论优先**：任何与"⛔ 工作模式定论"冲突的提议一律以定论为准。
- 任何改动公理层公约或语义错误集的任务，需在分支早期跑全量 pytest 评估破坏面。
- 每个阶段完成后，用描述性 commit message 记录完成的工作，并把对应条目从本文件移除。
- **本文件不冻结具体测试通过数字**。
- 重大架构决策记录在技术文档中（`docs/ARCHITECTURE.md`、`docs/architecture/02_metadata_ast.md`、`docs/architecture/01_principles.md`），不再使用独立 ADR 文件。
