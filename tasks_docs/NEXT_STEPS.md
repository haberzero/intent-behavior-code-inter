# NEXT_STEPS - 当前最紧要项

> 本文件**只**记录当前最紧要、可立即开工的下一步；长期规划见 `tasks_docs/PENDING_TASKS.md`。
>
> **最后更新**：2026-08-07（阶段 0 统一执行地基设计冻结完成，阶段 1 地基实现为下一主线）

---

## 🔴 下一主线：阶段 1 —— 统一执行地基实现（独立分支实验，禁合并）

> **阶段 0 设计冻结已完成（2026-08-07）**：**`tasks_docs/EXEC_FOUNDATION_DESIGN.md`**（零代码）——adopt 协作调度为
> VM 唯一执行模型；统一 Waitable 家族（is_done + try_result + result）；阻塞即挂起（阻塞语言操作统一返回 Waitable，
> 与 collect/run_isolated 同构）；线程 = I/O 并行任务（完成 = Waitable）；协作取消全路径；yield 点快照 × llmexcept
> 闭合；语言面 async fn/yield 形态；决策 D-01~D-08。
> **用户定案（2026-08-07，价值前提）**：设计优秀与统一、可维护性、宏观合理性、长期收益优先；难度与工作量不参与权衡。
> 深度审计见 **`tasks_docs/CONCURRENCY_AUDIT.md`**（S1-S9/D1-D9/W1-W6/P1-P9 + §十一 任务重排）。
>
> **阶段 1 实施（独立分支 `exp/exec-1a` 起，全绿后手动应用 unsafe-vibe-dev）**：
> 1a 调度器接入主路径（run/run_body/run_many 统一）→ 1b Waitable 家族扩展（SpawnedTask/ChannelRecvWaitable）
> + 阻塞方法返回 Waitable → 1c 协作取消全路径 → 1d llmexcept × await 闭合 → 1e 线程体调度器统一 → 1f 语言面 async/yield。
> **后续排序**：② 语言面 async fn/yield（PT-FEAT-1 解封）→ ③ 统一清理（W1-W5/P3/P4）→ ④ PT-FEAT-9 诊断 → ⑤ 增量。

---

## 🔴 下一主线（诊断机制）：PT-FEAT-9 内核结构化诊断机制重建（CORE_DEBUG 替代物）

> **2026-08-06 交接，挂起至阶段 4（依赖统一执行地基 + 全局事件总线）**。OBSERVABILITY_REFACTOR 主体已完成
> （四机制收敛 + 测试体系重建 + 矩阵三段式，全量 1963 passed / 1 skipped）；旧 CORE_DEBUG 已于 2A 移除
> （88 trace → 真实异常回退转 `warnings.warn`，实跑清点现为 12 处运行时 + 1 处编译期）。经观测骨架
> （EventBus + `emit_runtime_event`）发射结构化诊断事件，与 idbg/iruntime/test_hooks 同一设计语言，
> **禁止重建旧 print/级别门控/全局单例机制**。
> **设计已冻结：`tasks_docs/DIAGNOSTIC_DESIGN.md`**（技术定位/职责边界/核心决策 D1-D7/诊断码集/事件 schema/实施步骤）。
> **依赖前置**：`EXEC_FOUNDATION_DESIGN.md` §3.6（全局事件总线，阶段 3 落地）。
> **完整交接要点见 `PENDING_TASKS.md` §12**（背景/现状/设计方向/实施步骤/关联）。

---

## 📋 交接要点（下一 session）

- **首要任务（2026-08-07 阶段 0 完成）**：**阶段 1 统一执行地基实现**（独立分支 `exp/exec-1a` 起，禁合并，
  全绿后手动应用 unsafe-vibe-dev）——设计冻结见 `tasks_docs/EXEC_FOUNDATION_DESIGN.md`（D-01~D-08，
  1a 调度器接入主路径 → 1b Waitable 家族+阻塞方法返回 Waitable → 1c 协作取消 → 1d llmexcept×await →
  1e 线程体调度器统一 → 1f 语言面 async/yield）。
- **次任务（阶段 4，挂起）**：**PT-FEAT-9 内核结构化诊断机制重建（CORE_DEBUG 替代物）**——设计已冻结
  （`tasks_docs/DIAGNOSTIC_DESIGN.md`，D1-D7 + 诊断码集 + 实施步骤）；依赖 `EXEC_FOUNDATION_DESIGN.md`
  §3.6（全局事件总线，阶段 3）落地；完整交接要点见 `PENDING_TASKS.md` §12。
- **已完成（OBSERVABILITY_REFACTOR 主体）**：2C-2 idbg 深度收敛 + 用户层机制改造、2D 测试体系全面重建
  （tests_v2 全域迁移 + 切换 + 矩阵三段式 + tests_docs 治理）、测试规范化清理（弱断言升级 + 短簇参数化），
  全量 **1963 passed / 1 skipped**。
- **本 session 已完成（2026-08-06，unsafe-vibe-dev，11 commits）**：Phase 0 设计冻结、Phase 1 契约修复+死码+零成本穿透替换、
  **2A CORE_DEBUG 整体移除**（88 trace → warnings 8 处/删除，commit 6878986）、**2B 观测骨架测试合作面**
  （EngineTestSnapshot + test_hooks + resolve_plugin_search_paths 公开 + layering 豁免归零，commit 73f373d/ae2209e/feff694）、
  **2C idbg 适配**（删死代码 + show_intents 单一权威源 + fields 协议化，commit 8a0065c）。全量 pytest **1633 passed / 4 skipped**。
- **已完成**：PT-DEBT-7（删 is_nullable 死字段）、PT-DEBT-8（值层分派收敛，重定义原折叠目标）、
  PT-DEBT-6（register_module 可观测性）、PT-DOC-2（定位段收尾）、DOC_AUDIT 文档治理（F0-F4）、
  PT-INTRO-1/PT-DECIDE-1/PT-DEBT-1/2/3、内建函数群完善+遮蔽——详见 `PENDING_TASKS.md` 与 git 历史。
- **待办池**：完整清单见 `PENDING_TASKS.md`。

---

## ✅ 已完成交付

> 全部落地 unsafe-vibe-dev（本地 commit，未 push）。commit 明细见 git 历史。

- **PT-DEBT-7/8 + PT-DEBT-6 + PT-DOC-2（2026-08-06）**：
  - PT-DEBT-7：删 `TypeDef.is_nullable` 死字段（可空性早已由 `Optional[T].wrapped_type` 承载，序列化不消费）。
  - PT-DEBT-8：系统层面重定义"折叠 IbXxx→IbValue"为伪目标（消 isinstance 动机已由 name 分派达成）→
    值层分派收敛审计：`is_sequence_value` 统一容器分派、`IbLLMCallResult.is_uncertain` 统一不确定判断；
    类角色分工固化 `03_type_system.md` §6.4。
  - PT-DEBT-6：`register_module` 用户插件覆盖 kernel-native 时发 warning（原静默忽略）；修正测试配置 bug。
  - PT-DOC-2：14 篇 syntax 定位段核实完成（DOC_AUDIT F3 已补齐），条目移除。
- **DOC_AUDIT 文档治理（2026-08-06）**：docs/ 全量治理（42 篇）分四阶段执行——F0 本批引入修复（KNOWN_LIMITS §二十二重复编号→§二十四、14_concurrency E9、E2 历史叙述）；F1 P0 断链/矛盾 ~17+ 处（以代码为最高真相）；F2 P1 红线批量（日期戳/历史叙述/冻结数字/任务代号清除、KNOWN_LIMITS 章节重排为一~二十二并同步跨文档引用、05_coroutine 任务日志迁 tasks_docs/THREAD_DESIGN.md、__prompt__ 待决项迁 tasks_docs/PROMPT_DESIGN_REVIEW.md）；F3 P2 改善（模板统一 13_mock_testing/04_control_flow、A5 去重、侧表/MetadataStore 事实修正、handler 数 43→45）；F4 体系（How-to 层 docs/howto/ 两篇、'深入指引'尾段 23 篇补齐）。**后续清理**：删除自治标注文档 appendix_type_system_rationale.md 与 backup/（未完成规划迁 PENDING_TASKS PT-FEAT-8/PT-DEBT-7/8，media 设计浓缩为 tasks_docs/MEDIA_DESIGN.md）。完整记录见 `tasks_docs/DOC_AUDIT_REPORT.md`。
- **整合巩固批次（2026-08-06）**：新写 `docs/syntax/14_concurrency.md`（并发语言面，此前缺失）+ KNOWN_LIMITS §二十二（signal 移除）；修复 PT-DEBT-1 文档漂移（`_ibci_registry_id` 残留）；修复 for 循环变量类型恒为 any 缺陷（复合赋值在 for 体内无法定型）；for...if + 复合赋值 e2e 覆盖（PT-TEST-2）。
- **内建函数群完善（2026-08-06）**：类型转换全局函数 `int()`/`str()`/`float()`/`bool()` +
  序列辅助 `enumerate`/`zip`/`sorted`/`reversed`/`sum`/`all`/`min`/`max`；级联修复 for 循环
  元组解包 `for (int x, int y) in`；内建函数名可被用户变量声明遮蔽（`int len = 5`），
  内建类型名与对内建的直接赋值仍禁。`any` 因与动态类型名冲突未纳入。
- **PT-DEBT-1/2/3 内核接口协议化（2026-08-06）**：
  - PT-DEBT-1：`BoundPlugin` 容器替代 `_ibci_registry_id` 私有标记注入；加载期跨引擎
    单例守卫改用 process 级 weak map（安全语义保留）。
  - PT-DEBT-2：`snapshot.py` 改走公开访问器；LLMExecutor 补 `pending_futures_count()`。
  - PT-DEBT-3：RuntimeContextImpl 补 `get_comm_*`/`peek_*`/`get_runtime_coordinator`
    访问器，统一替换 core 与 iruntime 插件的私有槽直接访问。
- **PT-DECIDE-1 裁定落地（2026-08-06）**：行为输出具体类型必须可解析——编译期
  `SEM_BEHAVIOR_OUTPUT_NOT_PARSEABLE` + 运行时 Default 兜底（见 `PENDING_TASKS.md` §二）。
- **PT-INTRO-1 运行时内省体系（2026-08-06）**：
  - `type(f)` 对 fn_callable/behavior 返回含签名类型名（`fn_callable[()->int]` /
    `behavior[(int,str)->bool]`）；其余值仍返回规范名。
  - `f.__return_type__()` 返回类型查询 API（receive 消息 + vtable 原生方法）。
  - 签名在运行时值创建时经 node_to_type 捕获、自持于值，序列化 round-trip 保真；
    lambda 参数节点类型绑定补全（编译期 bind_type）。

- **闭包序列化 + fn_callable round-trip 修复**：作用域 cell 重建 + 按 sym_uid 重链共享；
  value_meta/expected_type JSON 安全。
- **Axiom 家族分裂收敛**：IntentAxiom/IntentContextAxiom 并入 BaseAxiom。
- **EnumAxiom 双通道收敛**：str 契约 + fail-fast。
- **use_intent_context 守卫修复**：删恒真守卫 + 可读错误。
- **R3 异味四 Zone 处置**：修 19 + 复核定案保留 10 + 设计确认保留 6。
- **import-* 精确成员枚举根治**：编译器记录 + 运行时枚举；**IBC 文件跨模块导入三层断裂修复**
  （TypeDef 别名 NameError / Lazy 描述符 members 恒空 / IbModule.get_variable）。
- **`type()` 内建落地**：运行时内省第一项。
- **任务控制文档全面重整**：任务代号按性质分域（FEAT/DEBT/AUDIT/DOC/TEST/DECIDE/SEALED），
  删除已完成/无价值条目与无用设计决策，清理注释任务代号/历史说明。
- **周期清扫启动**：文档清洗与梳理、注释卫生清理、代码复核审查（R1/R2/R3）均已执行，
  周期复核。

---

## ⛔ 工作模式定论（强制，凌驾于本文件一切任务之上）

> **扎实推进，禁止任何形式的快速实现 / 兼容层 / 胶水实现 / tricky 实现。**

1. 禁止 compat shim / 兼容层：新设计就是真设计，旧代码要么真合并、要么真删除。
2. 禁止胶水实现：不在两个不统一的子系统之间塞字符串拼接 / 魔法哨兵 / 隐式约定。
3. 禁止 tricky 实现：不靠隐式字符串变换承载语义；不靠"凑巧相等"；不靠书写顺序掩盖数据依赖。
4. 禁止过程式硬编码分发：同一决策只通过协议驱动（`receive()` / vtable），不写 `if 能力标志位`。
5. 质量优先于速度：技术债必须先清；潜伏 bug 不允许过渡修复。
6. 原则优先于行为维持：既有行为违反一般工程/架构原则时，以原则为准，不以"保持已有行为"为主。
7. 可推翻 IBCI 自身设计缺陷：即使设计思路已在文档记录，也可按更普适、实践更合理的方案重建。
8. 破坏性重构授权：符合一般工程经验且经分析优于现有体系时默认已授权自主推进，详记决策。
9. 大范围破坏性重构分支政策：无法确认边界/危害程度的重构 100% 授权在独立分支实验；
   独立分支禁止直接合并到 unsafe-vibe-dev 或 main；永远不触碰 main。

---

## 当前测试基线

```bash
conda activate ibci
python -m pytest tests/
```

> 基线以实跑为准，不冻结数字。

---

## 独立并行任务

- **测试体系重构**：PT-TEST-1（`TEST_REFACTOR.md`），独立低优先级。
- **技术债审计**：PT-AUDIT-1/2（`CODE_SMELL_AUDIT.md` / `BRANCH_NESTING_AUDIT.md`），独立分支执行。
- **media Phase 4**：PT-SEALED-1，彻底封存（恢复需显式解封）。

---

## 工作规则

- 每次开新分支前，先复跑 `python -m pytest tests/`，把 pass/fail 计数写在 PR 描述里。
- 同一时刻只主推一个 P0 阶段。
- 工作模式定论优先；改动公理层或语义错误集的任务需全量 pytest 评估破坏面。
- 每阶段完成后用描述性 commit 记录，并把对应条目从本文件移除。
- 本文件不冻结具体测试通过数字。
- 重大架构决策记录在技术文档（`docs/ARCHITECTURE.md`、`docs/architecture/02_metadata_ast.md`、
  `docs/architecture/01_principles.md`），不再使用独立 ADR 文件。
