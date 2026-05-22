# NEXT_STEPS — 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `docs/PENDING_TASKS.md`；历史归档见 `docs/COMPLETED.md`；
> 已知语言级限制见 `docs/KNOWN_LIMITS.md`；架构演进方向见 `docs/ARCHITECTURE_REVIEW_2026-05-15.md`。
>
> **最后更新**：2026-05-22（P1 全套完成——文档收口 + 设计原则补全 + visitor 补齐 + TypeResolutionPass + llmexcept body 重写）

---

## 当前测试基线（每次开新分支前必须复跑确认）

```bash
python -m pytest tests/ -q --tb=no --no-header
```

**2026-05-22 实测结果**：`697 passed, 7 skipped, 0 failed`。
（原 673 + 24 新增 P1 测试；0 失败）

---

## ⚠️ 当前 P0/P1：完成（无阻塞项）

三个前序 P0 和全部 P1 已在 2026-05-22 全部完成：

1. ✅ **H5 测试基线恢复**
2. ✅ **双写真相收敛**
3. ✅ **v2 阻塞 bug + MetadataStore/TypeEnvironment 字段收敛**
4. ✅ **P1-A 文档与 v2 自我矛盾收口**
5. ✅ **P1-B 核心 IBCI 设计原则补全**（auto 锁定 / any 永久 / -> auto 统一 / resolve_op）
6. ✅ **P1-C AST 节点 visitor 补齐**（17 个新 visitor）
7. ✅ **P1-E 独立 TypeResolutionPass**
8. ✅ **P1-F 复刻 _bind_llm_except 到 v2**（双通道 body 重写）
9. ✅ **P1-D 序列化层加固**（评估完成，无阻塞）

---

## ⏭ 下一个 P0 候选（提升自 P2）

以下为按优先级排列的候选 P0 项。根据项目节奏选取一个或多个推进：

### P2-A v2 Shadow 模式与 parity 测试

- [ ] `scheduler` 加 `run_v2_shadow=False` 开关；启用时 v1 跑完后让 v2 跑同一份 AST。
- [ ] 新增 `tests/compiler/test_v2_v1_parity.py`：断言"v2 在 shadow 模式下产出的错误码集合 ⊆ v1 产出的错误码集合"，并对一组 fixture 比对关键产物（type/symbol/llm_deps）一致。允许 v2 漏报但禁止误报。

### P2-B `intent_context.push()` 静默无效陷阱编译期警告

`intent_context.push("X")` 在没有 `use(ctx)` 时是 no-op（详见 `docs/KNOWN_LIMITS.md §十八`），编译期不告警；用户极易踩坑。
**动作**：在 `semantic_analyzer` 中对 `IbCall(method='push'|'pop'|'merge'|'combine'|'clear')` 且 receiver 为类静态调用（非局部 `intent_context` 变量）的形态发出 SEM 警告。低风险，单点改动。

### P2-C NS-5 编译期类型转换检查（激活 `can_convert_from`）

技术路径已记录；保留为低优先背景项。实施前需先评估对 `tests/` 套件的破坏面，再决定动手。

### P2-D 已知设计取向项（参考性低优先）

- 嵌套 llmexcept 内 retry 计数器的"每次外层 retry 是否重置"语义在 `docs/INTENT_SYSTEM_DESIGN.md` / `docs/ARCH_DETAILS.md` 明文锁定。
- `@-` 在按内容/标签移除不存在意图时的 no-op 行为在 `docs/INTENT_SYSTEM_DESIGN.md §4.4` 明文锁定。
- `__to_prompt__` 在容器嵌套（list/dict 内含用户对象）插值时的递归展开规则在 `docs/IBCI_SYNTAX_REFERENCE.md §6 / §10` 写出契约。

### P1-B 遗留细化（可选）

以下 P1-B 子项已有基础框架但可进一步完善：
- [ ] `llm_uncertain` 标记与消解规则（需要确定 LLM 返回值不确定性标记何时引入、何时消解）
- [ ] 函数参数类型匹配 / `fn` 推断 / `CALLABLE_SIG` 结构匹配（D3 完整实现）

### P1-Z idbg.last_llm() 与 MOCK:SEQ 时序一致性核查（H7）

---

## P3 候选（远景，暂搁置；详见 PENDING_TASKS）

- v2 切换 + v1 删除（前提：P2-A parity 稳定 ≥ 2 个周期）。
- 二层 IR 路线（结构 IR + 执行 IR），见 `docs/ARCHITECTURE_REVIEW_2026-05-15.md` 报告 B 章节 B.5。
- 公理 + 元数据 LLVM 化（命名、可丢弃、带版本的 `!metadata` 系统）。

---

## 工作规则

- **每次开新分支前**，先复跑 `python -m pytest tests/ -q --tb=no --no-header`，把当前 pass/fail 计数写在 PR 描述里，不预设上一份文档里的数字。
- 同一时刻只主推一项 P0 任务（或一项 P1）；其余项保留待选。
- 任何改动公理层公约或语义错误集的任务，需在分支早期跑全量 pytest 评估破坏面。
- 每项完成后，把摘要追加到 `docs/COMPLETED.md`（极简时间线），并把对应条目从本文件移除。
- 出现新的紧要项时，按"先评估优先级、再决定是否替换 P0"原则操作。
- **本文件不冻结具体测试通过数字**——任何"X 测试通过"的表述都必须附运行命令或日期锚点。

---

## 维护守则

下述守则源于 2026-05-14 / 2026-05-15 全量事实回顾过程中暴露出的几次"文档幻觉"教训：

1. **先复跑、后下结论**。任何关于"测试基线红线 / P0 未通过"的表述，必须以"附完整 pytest 输出 + 日期 + 分支"的方式说服读者；否则视为待核查。
2. **不要相信"昨日完成"的总结**。`docs/COMPLETED.md` 的最新一两条锚点，必须能用一条具体 git 提交或一次具体 pytest 输出佐证。
3. **示例必须可零配置跑通**。任何"用户跟着 README 复制粘贴"的代码块，必须在 mock 模式下端到端跑通；改动后必须 `python main.py run <示例>` 至少一次。
4. **已知 bug 与已修 bug 之间要勤更**。每发现一个"文档说有但代码已修"的项目，立刻把文档同步更新；反向同理。
5. **跨文件状态保持一致**。`README.md`、`docs/KNOWN_LIMITS.md`、`docs/IBCI_SYNTAX_REFERENCE.md`、`docs/METADATA_ARCHITECTURE.md`、`docs/SEMANTIC_REFACTORING_PLAN.md` 之间对同一语法/限制/架构立场的描述必须用同一组事实；如不一致，以代码与最近一次 pytest 输出为准。
6. **避免重复声明、单点真理**。一条已完成项写一次（在 `COMPLETED.md`），一条已知限制写一次（在 `KNOWN_LIMITS.md`），一条紧要项写一次（在 `NEXT_STEPS.md`）。出现"同一条目在多个文件中以不同状态出现"，立即合并。
7. **新增 AST 字段或侧表前必须先在 `METADATA_ARCHITECTURE.md` 与 `ARCHITECTURE_REVIEW_2026-05-15.md` 中查证**：禁止"AST 字段 + 侧表"双写真相（同一份语义事实只能有一处可序列化位置）。
