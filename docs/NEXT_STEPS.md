# NEXT_STEPS — 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `docs/PENDING_TASKS.md`；历史归档见 `docs/COMPLETED.md`；
> 已知语言级限制见 `docs/KNOWN_LIMITS.md`；架构演进方向见 `docs/ARCHITECTURE_REVIEW_2026-05-15.md`。
>
> **最后更新**：2026-05-24（P0-NEXT-1/2/3 核心修复完成：for循环变量作用域 + TypeCheckingPass产出验证 + node_to_loc实现）

---

## 当前测试基线（每次开新分支前必须复跑确认）

```bash
python -m pytest tests/ -q --tb=no --no-header
```

**2026-05-24 实测结果**：`725 passed, 7 skipped, 0 failed`。
（原 715 + 10 新增 v2 fix 验证 tests；0 失败）

---

## ⚠️ P2-A v2 替换基础设施：已完成

v2 pipeline 已具备直接替换 v1 的基础条件：

1. ✅ **MetadataStore 对齐**：使用 node-object-identity 作为键（与 v1 SideTableManager 完全一致）
2. ✅ **SemanticAnalyzerV2 入口**：`analyze() → CompilationResult` 接口与 v1 完全兼容
3. ✅ **adapter.py**：`PassResult → CompilationResult` 桥接（无 fallback）
4. ✅ **scheduler.py 集成**：`use_v2=True` 标志直接切换到 v2 pipeline
5. ✅ **18 parity tests**：验证结构、符号收集、引用解析、llmexcept 绑定

---

## ⏭ 当前 P0：v2 功能补全 → 全量替换 v1

v2 pipeline 基础设施就位，接下来的核心任务是**补全 v2 各 Pass 的功能覆盖**，使其达到 v1 的等效输出水平，然后直接删除 v1。

### P0-NEXT-1 SymbolResolutionPass 作用域正确性

~~v2 的 SymbolResolutionPass 当前不处理函数参数作用域（进入函数时不 push scope），导致函数体内的参数引用报 SEM_001 undefined。~~

- [x] 实现 `visit_IbFunctionDef`/`visit_IbLLMFunctionDef` 中的 push_scope + 参数注册（已在 P2-A 中完成）
- [x] 实现 `visit_IbClassDef` 中的作用域管理（已在 P2-A 中完成）
- [x] 实现 `visit_IbFor` 中的循环变量作用域（2026-05-24 修复）
- [ ] 验证：相同程序通过 v1 和 v2 产出相同的 symbol_table 内容

### P0-NEXT-2 TypeCheckingPass 完整绑定

~~TypeCheckingPass 需要对所有表达式节点进行类型推断并写入 `node_to_type`。~~

- [x] 确保 `visit_IbAssign` 正确推断赋值值的类型并绑定到节点（2026-05-24 验证：测试 conftest 使用 `create_default_registry()` 后 node_to_type 正常产出）
- [x] 确保 `visit_IbCall` 推断返回类型（代码已存在，registry 初始化修复后生效）
- [x] 确保 `visit_IbBehaviorExpr` 绑定 behavior type（代码已存在，registry 初始化修复后生效）
- [x] 验证：v2 的 `node_to_type` 条目数非零（2026-05-24 验证通过）

### P0-NEXT-3 Location 绑定（node_to_loc）

~~v2 当前不产出 `node_to_loc`（v1 在 Pass 3.5 中填充）。~~

- [x] 在 IntegrityCheckPass 中遍历所有 AST 节点写入 location 信息（2026-05-24 实现 LocationBinder）
- [ ] 验证序列化器能正确消费 v2 产出的 node_to_loc

### P0-NEXT-4 全量 parity 验证 + v1 删除

- [ ] 在 scheduler 中设 `use_v2=True` 为默认值，跑全量 pytest
- [ ] 修复所有 parity 差异
- [ ] 删除 `core/compiler/semantic/passes/semantic_analyzer.py`（v1）
- [ ] 删除 `use_v2` flag，v2 成为唯一路径

---

## P2 候选（降级为背景项）

### P2-B `intent_context.push()` 静默无效陷阱编译期警告

`intent_context.push("X")` 在没有 `use(ctx)` 时是 no-op（详见 `docs/KNOWN_LIMITS.md §十八`），编译期不告警；用户极易踩坑。
**动作**：在 TypeCheckingPass 中对相关形态发出 SEM 警告。

### P2-C NS-5 编译期类型转换检查（激活 `can_convert_from`）

技术路径已记录；保留为低优先背景项。

### P1-B 遗留细化（可选）

- [ ] `llm_uncertain` 标记与消解规则
- [ ] `CALLABLE_SIG` 结构匹配（D3 完整实现）

---

## P3 候选（远景；详见 PENDING_TASKS）

- 二层 IR 路线（结构 IR + 执行 IR），见 `docs/ARCHITECTURE_REVIEW_2026-05-15.md` 报告 B 章节 B.5。
- 公理 + 元数据 LLVM 化。

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
