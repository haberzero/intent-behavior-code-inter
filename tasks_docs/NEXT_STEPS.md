# NEXT_STEPS - 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `tasks_docs/PENDING_TASKS.md`。
> 已知语言级限制见 `docs/KNOWN_LIMITS.md`。
>
> **最后更新**：2026-08-04（任务 A、B 已完成；任务 C 待开工；PT-MT-1~8 已全部完成）
---

## 🔴 当前主线：线程对象模型方向修正（已授权，待实现）

> **用户裁定（2026-08-04）**：PT-MT-1~8 完成后深度质询，推翻 spawn/join/cancel/task 关键字语法，改为 **thread 对象 + 句柄方法** 模型。完整决策见 `tasks_docs/THREAD_DESIGN_REVISION.md`（唯一决策依据）。
>
> **核心裁定**：
> - async 与 thread 彻底分离（IbTask 不得满足 Waitable；await 只服务异步）
> - 删 spawn/join/cancel/task 关键字；`thread[T]` 泛型 + 句柄方法（start/join/cancel/is_done）
> - `thread_result[T]` 泛型容器（成功值/错误/状态，可继承改写，禁止 any）
> - err 类型统一接入 Exception 体系；`t.cancel()` 返回 err
> - 统一泛型模型立即启动（内置类型泛型化正式机制；thread[T] 首个消费者）
> - Optional 配套（运行时 IbOptional 缺失需补齐）
> - 挂起机制取消；通信领域（chan/signal/slot）暂缓下阶段
>
> **任务 A-F（按序，依赖驱动）**：
> A. Optional 配套完整实现 → B. 统一泛型模型 → C. 线程对象模型（thread[T] + 句柄方法 + 状态机）→ D. err 类型统一 → E. 线程相关清理（VP-1~VP-6 + F-1~F-8）→ F. 关键字精简（删 spawn/join/cancel/task）+ 废除旧测试 + 新测试。
>
> **约束**：大范围重构已授权（可推翻/删除既有代码）；save_state 检测未完成线程则抛异常 fail；旧测试废除。
>
> **进度**：任务 A（Optional 配套完整实现）**已完成 2026-08-04**——运行时 `IbOptional` + is_some/unwrap/or_else + 绑定入口单一化（`_wrap_optional`）+ Optional 基础可赋值性 + 值协议 + 序列化。测试：新增 `tests/runtime/test_optional_runtime.py`（17 用例），全量 pytest 1426 passed/4 skipped 零回归。
>
> **任务 B（统一泛型模型）已完成 2026-08-04**——`GenericTypeDeclaration` + `GenericTypeRegistry`（单一权威源），`resolve_specialization` 统一走注册表创建/解析；删除 Optional/List/Dict/Tuple Axiom 的 `resolve_specialization_by_names` 遗留路径（用户明确要求删除历史包袱）；`thread[T]` 首个消费者（THREAD_SPEC + ThreadAxiom + create_thread + join→T 特化 + 序列化/还原）。测试：新增 `tests/kernel/test_generic_model.py`（16 用例），全量 pytest 1443 passed/4 skipped 零回归。
>
> **任务 C（线程对象模型）已完成 2026-08-04**——C0 前置（类构造关键字参数支持，`_get_callee_param_specs` 支持 IbClass + `_auto_init` 补 param_meta）；C1（`IbThread` 值对象 + 生命周期状态机 + `thread(callable=..., args=...)` 构造）；C2（`thread_result[T]` 容器 + join 返回容器 + `expect()`/`unwrap()`/`unwrap_or()` 等，用户裁定 join 返回容器）；C5（序列化）；C6（测试）。**设计裁决**：构造参数名 `callable`（设计文档原 `fn`/`func` 均与关键字碰撞，按"内部接口设计不违反关键字碰撞"原则弃用）。测试：新增 `test_thread_model.py`（7 用例）+ `test_thread_result.py`（4 用例），全量 pytest 1459 passed/4 skipped 零回归。详见 `tasks_docs/_code_thread_model.md`。
>
> **任务 D（err 类型统一）已完成 2026-08-04**——TaskError（parent Exception）→ TaskCancelled/TaskFailed（parent TaskError）映射 IBCI Exception 子类；`make_task_cancelled`/`make_task_failed` 运行时工厂；`cancel()` 返回 TaskCancelled err；`join()` 错误值化进容器；`expect()` 抛容器内 err 供语言层 try/except 按类型捕获；err 用户可见可继承（`class MyTaskError(TaskError)` 验证）。测试：新增 `tests/runtime/test_thread_err.py`（5 用例），全量 pytest 1464 passed/4 skipped 零回归。
>
> **任务 E（线程相关清理）已完成 2026-08-04**——VP-2（死 `_task_handle` 引用 → handle 全链透传）、F-2（coordinator `_tasks` 自动清理防泄漏）、F-1（快照补充协调器线程，单数据源）、疏漏 4（save_state 检测未完成线程抛异常）+ save_state 磁盘型误判修复（类对象不再误判）+ 序列化瞬态线程存根化。VP-1/VP-4/VP-5 随任务 F 删除旧关键字路径一并清除。测试：新增 `tests/runtime/test_thread_cleanup.py`（4 用例），全量 pytest 1468 passed/4 skipped 零回归。
>
> **下一步（开工）**：任务 F——关键字精简（删 spawn/join/cancel/task 全链：lexer/parser/AST/semantic/dispatch/serialization）+ 废除旧测试 + 新测试单独制作。

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
8. **破坏性重构授权（用户 2026-08-03 明确，硬原则）**：当判断符合一般工程经验、符合通常意义下的普适性、属于合理的架构选择与设计，且经分析确实优于 IBCI 现有体系及已有代码时，**哪怕该设计已被 IBCI 文档明确记录，也允许进行破坏性重构**。用户**不禁止对已有代码的修改**；已有代码的优先级**低于**架构正确性与设计上的统一一致。此类破坏性变更（含已被文档记录的设计）**默认已授权自主推进**，仅需详尽记录决策依据与工作内容（实现+测试+文档变化前后）即推进。
9. **大范围破坏性重构的分支政策（用户 2026-08-03 明确，硬原则）**：对于**无法确认边界、无法判断危害程度**的破坏性重构，**100% 授权在其独立分支上**（不污染 `main` 与 `unsafe-vibe-dev`，不污染任何计算机环境与用户目录），允许任意程度破坏性实验与重构。**只有当即使该独立隔离分支也无法经自主实验确定工作路线时**，才将相关任务配置为阻塞。**独立分支禁止直接合并到 `unsafe-vibe-dev` 或 `main`**；只有在确认完整技术路线后，才允许单独进行手动 `unsafe-vibe-dev` 代码更新。**永远不允许触碰主干分支（`main`）的代码。**

---

## 当前测试基线

```bash
python -m pytest tests/
```

> 基线以实跑为准，不冻结数字。

---

## 独立并行任务

- **测试体系治理与彻底重构**：独立、较低优先级，`tasks_docs/TEST_REFACTOR.md`（含 4 份调研报告 `TEST_REFACTOR_REPORTS.md`），不与主线混置。
- **技术债审计分支任务**：PT-SMELL-1/2（`CODE_SMELL_AUDIT.md` / `BRANCH_NESTING_AUDIT.md`），独立分支执行；PT-SMELL-3 已完成（见 `PENDING_TASKS.md` §六）。
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
