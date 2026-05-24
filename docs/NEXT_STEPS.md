# NEXT_STEPS — 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `docs/PENDING_TASKS.md`；历史归档见 `docs/COMPLETED.md`；
> 已知语言级限制见 `docs/KNOWN_LIMITS.md`；架构演进方向见 `docs/ARCHITECTURE_REVIEW_2026-05-15.md`。
>
> **最后更新**：2026-05-24（P0-NEXT-4 逐步替换：use_v2=True 默认 + 12 项 parity 修复）

---

## 当前测试基线（每次开新分支前必须复跑确认）

```bash
python -m pytest tests/ -q --tb=no --no-header
```

**2026-05-24 实测结果**：`744 passed, 8 skipped, 17 failed`（use_v2=True 默认模式）。
17 项均为 **TypeCheckingPass 严格性差异**（v2 尚未实现的静态检查），不影响运行时正确性。

---

## ⏭ 当前 P0：v2 TypeCheckingPass 补全 + v1 删除

v2 默认开启后的核心 Symbol/Type 绑定已实现 100% runtime parity。
剩余 17 个测试失败全部是 TypeCheckingPass 在以下方面未发出编译期诊断：

### P0-NEXT-5 TypeCheckingPass 静态诊断补全

1. **D3 fn 签名结构检查 (5 tests)**
   - [ ] 参数数量不匹配 → SEM_005
   - [ ] 参数类型不匹配 → SEM_003
   - [ ] 返回类型不匹配 → SEM_003
2. **Lambda/fn 类型安全 (6 tests)**
   - [ ] fn 声明拒绝非 callable RHS → SEM_003
   - [ ] lambda 返回类型不匹配 → SEM_003
3. **泛型类型检查 (2 tests)**
   - [ ] list append 类型不匹配 → SEM_081 warning
   - [ ] list subscript 类型不匹配 → SEM_003
4. **Optional 类型安全 (1 test)**
   - [ ] plain int 拒绝 Optional[int] → SEM_003
5. **Tuple 位置类型检查 (3 tests)**
   - [ ] 编译期检测而非运行期 RUN_002

### P0-NEXT-6 v1 删除

- [ ] 删除 `core/compiler/semantic/passes/semantic_analyzer.py`（v1）
- [ ] 删除 `use_v2` flag，v2 成为唯一路径
- [ ] 清理 test_v1_v2_comparison.py（不再需要对比测试）

---

## P0 已完成里程碑

### P0-NEXT-4 全量 parity 验证 ✅ DONE (2026-05-24)

- [x] scheduler 默认 `use_v2=True`
- [x] 修复 IbImport/IbImportFrom alias node 绑定
- [x] 修复 IbClassDef 节点绑定 + self/super 注入
- [x] 修复 IbExceptHandler 节点绑定 (as e)
- [x] 修复 BehaviorExpr → bool 类型覆写 (if/while/for 条件位)
- [x] 修复 Lambda free_vars 填充（使用 node_to_symbol 绑定）
- [x] 修复 BinOp any 操作数容许性
- [x] 修复嵌套 IbFunctionDef 预注册
- [x] 修复 fn 声明容许性

### P0-NEXT-1/2/3 ✅ DONE

（详细归档见 docs/COMPLETED.md）

---

## P2 候选（降级为背景项）

### P2-B `intent_context.push()` 静默无效陷阱编译期警告

`intent_context.push("X")` 在没有 `use(ctx)` 时是 no-op（详见 `docs/KNOWN_LIMITS.md §十八`），编译期不告警；用户极易踩坑。
**动作**：在 TypeCheckingPass 中对相关形态发出 SEM 警告。

### P2-C NS-5 编译期类型转换检查（激活 `can_convert_from`）

技术路径已记录；保留为低优先背景项。

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
