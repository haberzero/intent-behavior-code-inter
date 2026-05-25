# NEXT_STEPS — 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `docs/PENDING_TASKS.md`；历史归档见 `docs/COMPLETED.md`；
> 已知语言级限制见 `docs/KNOWN_LIMITS.md`。
>
> **最后更新**：2026-05-25（P2-D/E 完成：SEM_092 + SEM_093；Semantic Pipeline 5-Step 路线图全部归档）

---

## 当前测试基线（每次开新分支前必须复跑确认）

```bash
python -m pytest tests/ -q --tb=no --no-header
```

**2026-05-25 实测结果**：`806 passed, 7 skipped`（0 failures）。

---

## ✅ 已完成：Semantic Pipeline 架构改进（5 步渐进式重构）

> 全部 5 步已完成并归档至 `docs/COMPLETED.md`。此处仅保留摘要索引。

- Step 1: TypeEnvironment → TypeInferenceState
- Step 2: ScopedVisitor 基类
- Step 3: SpecRegistry.resolve_call_return() 统一类型决议
- Step 4: 7-Pass 归并为 4-Phase
- Step 5: PassOutput + Immutable Pipeline

---

## ✅ 已完成：Semantic 静态诊断增强

### P2-B ✅ `intent_context.push()` 静默无效陷阱编译期警告 (SEM_090)

### P2-C ✅ NS-5 编译期类型转换检查 (SEM_091)

### P2-D ✅ 方法重写签名兼容性编译期检查 (SEM_092)

子类重写父类方法时，TypeCheckingPass 现在检查：
- 参数数量一致性（含 self）
- 参数类型兼容性（逆变 / 双向兼容）
- 返回类型兼容性（协变）
- `__init__` 及协议方法 (`__to_prompt__` 等) 豁免

### P2-E ✅ `super()` 调用合法性编译期检查 (SEM_093)

- 在类方法外调用 `super()` → 编译错误
- 在无父类的类方法中调用 `super()` → 编译警告

---

## ⏭ 下一步候选工作

### 仍被 SKIP 的 7 个测试（按难度分类）

| 类别 | 涉及测试 | 核心障碍 | 预估难度 |
|------|---------|---------|---------|
| 闭包 write-back | INV-CONTEXT-1, INV-CONTEXT-2, INV-CELL-2 | Cell 返回后变量绑定丢失 | 高（运行时帧管理改造） |
| 行为表达式嵌入 | INV-BEHAVIOR-3, INV-BEHAVIOR-4 | `@~...~` 不能用于子表达式/条件 | 中（Parser + VM handler） |
| Lambda 体赋值 | INV-LAMBDA-3 | IBCI 无 walrus/lambda 赋值语法 | 低（设计决策，非 bug） |
| 块级变量遮蔽 | INV-SCOPE-1 | SEM_002 禁止 if-block 重声明 | 低（设计决策，非 bug） |

### P3 候选（远景；详见 PENDING_TASKS）

- `isinstance()` 运行时类型检查语法与 VM handler
- 二层 IR 路线（结构 IR + 执行 IR）
- 公理 + 元数据 LLVM 化
- 用户级泛型 (`class Box[T]:`)

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

1. **先复跑、后下结论**。任何关于"测试基线红线"的表述，必须以"附完整 pytest 输出 + 日期 + 分支"的方式说服读者；否则视为待核查。
2. **不要相信"昨日完成"的总结**。`docs/COMPLETED.md` 的最新一两条锚点，必须能用一条具体 git 提交或一次具体 pytest 输出佐证。
3. **示例必须可零配置跑通**。任何"用户跟着 README 复制粘贴"的代码块，必须在 mock 模式下端到端跑通；改动后必须 `python main.py run <示例>` 至少一次。
4. **已知 bug 与已修 bug 之间要勤更**。每发现一个"文档说有但代码已修"的项目，立刻把文档同步更新；反向同理。
5. **跨文件状态保持一致**。`README.md`、`docs/KNOWN_LIMITS.md`、`docs/IBCI_SYNTAX_REFERENCE.md`、`docs/METADATA_ARCHITECTURE.md` 之间对同一语法/限制/架构立场的描述必须用同一组事实；如不一致，以代码与最近一次 pytest 输出为准。
6. **避免重复声明、单点真理**。一条已完成项写一次（在 `COMPLETED.md`），一条已知限制写一次（在 `KNOWN_LIMITS.md`），一条紧要项写一次（在 `NEXT_STEPS.md`）。出现"同一条目在多个文件中以不同状态出现"，立即合并。
7. **新增 AST 字段或侧表前必须先在 `METADATA_ARCHITECTURE.md` 中查证**：禁止"AST 字段 + 侧表"双写真相（同一份语义事实只能有一处可序列化位置）。
