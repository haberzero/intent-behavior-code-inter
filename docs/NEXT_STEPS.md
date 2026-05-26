# NEXT_STEPS — 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `docs/PENDING_TASKS.md`；历史归档见 `docs/COMPLETED.md`；
> 已知语言级限制见 `docs/KNOWN_LIMITS.md`。
>
> **最后更新**：2026-05-26（经代码验证：重新评估 7 个 skipped 测试，3 项确认已可通过、1 项需 semantic 增强、1 项需语言设计）

---

## 当前测试基线（每次开新分支前必须复跑确认）

```bash
python -m pytest tests/ -q --tb=no --no-header
```

**2026-05-26 实测结果**：`806 passed, 7 skipped`（0 failures）。

---

## P0：行为表达式一般化 + 闭包问题收口

> 以下为经实际代码验证后的任务分解，所有结论均有代码运行佐证（2026-05-26）。

### P0-A ✅ 可直接解除 SKIP 的测试（3 项）

以下测试经 `run_ibci()` 实际运行验证，底层实现已到位，仅需编写正式测试代码并移除 `pytest.skip()`：

| 测试 ID | 验证场景 | 验证结果 |
|---------|---------|---------|
| **INV-BEHAVIOR-4** | `if @~ MOCK:INT:1 ~:` 行为表达式作为 if 条件 | ✅ 正确进入分支（Parser 已支持、Semantic 绑定 bool、VM 正确执行） |
| **INV-CONTEXT-1** | `make_adder(5)` 返回 lambda 后调用 `a5(3)` = 8 | ✅ Cell 机制在帧退出后正确保留值（IbCell 生命周期独立于 ScopeImpl） |
| **INV-CELL-2** | 多个 lambda 读取同一外部变量，外部赋值后全部看到新值 | ✅ `promote_to_cell` 幂等返回同一 IbCell，`assign()` 同步到 cell |

**工作量**：为每个测试编写正式断言代码（替换 `pytest.skip()`），确认测试绿色后提交。预计 1-2 小时。

**注意事项**：
- INV-BEHAVIOR-4 的 mock 协议需用 `MOCK:INT:1`（走 `from_prompt` 到 bool 的转换路径），不可用 `MOCK:BOOL:1`（该模式直接返回字符串 "1" 无法被 bool 公理正确解析）。
- INV-CONTEXT-1 测试应验证 lambda 捕获函数参数（非全局变量）的场景。
- INV-CELL-2 测试应验证多个 lambda 在同一作用域创建、外部赋值后全部读到最新值。

---

### P0-B 行为表达式参与二元运算（INV-BEHAVIOR-3）[需 Semantic 增强]

**现状**：Parser 已正确处理 `x + @~...~`（Pratt 解析器在 LOWEST 优先级允许 behavior expr 作为操作数），但 TypeCheckingPass 的 `visit_IbBinOp` 对 `int + behavior` 组合发出 SEM_003 错误。

**根因**：`visit_IbBinOp` 通过 `registry.resolve_operation_type_name(op, left_type, right_type)` 查询操作返回类型，`behavior` 类型未注册任何算术操作能力。

**解决方案（Semantic 层类型适配）**：

在 `TypeCheckingPass.visit_IbBinOp` 中增加 behavior 操作数特殊路径：
1. 若左操作数或右操作数为 `behavior` 类型，根据另一侧的具体类型推断 behavior 应产出的类型
2. 将 behavior 节点的类型绑定 **适配** 为另一侧类型（复用已有的"左值驱动类型适配"机制）
3. 整体表达式返回非 behavior 侧的类型

**技术要点**：
- 关键代码位置：`core/compiler/semantic/passes/type_checking_pass.py` 的 `visit_IbBinOp`
- 复用模式：与 `visit_IbAssign` 中已有的 behavior 类型适配逻辑对齐（lines 254-264 的"行为表达式结果适配目标类型"）
- 需处理双侧均为 behavior 的退化情况（默认 `str`）
- 需处理比较运算符（`==`、`<` 等）：behavior 操作数适配为另一侧类型，表达式整体返回 `bool`

**验证标准**：
```ibci
int x = 5
int y = x + @~ MOCK:INT:3 ~   # 编译通过，y = 8
bool b = x > @~ MOCK:INT:2 ~  # 编译通过，b = True
```

**预估工作量**：3-5 小时（含测试编写）。

---

### P0-C 闭包写回语义（INV-CONTEXT-2）[需语言设计决策]

**现状验证**（2026-05-26）：

- **Lambda 只读捕获** ✅：lambda 体通过 Cell 读取外部变量最新值（INV-LAMBDA-1/2 通过）
- **Lambda 返回后读取** ✅：函数返回 lambda 后，Cell 保持有效（INV-CONTEXT-1 通过）
- **命名函数修改外部变量** ❌：在 `func inner()` 内执行 `outer_var = new_value` 失败

**根因分析**：

IBCI 编译器将函数体内的赋值目标视为**本地变量声明**（Symbol Collection Pass 在函数作用域内为所有赋值目标创建新符号）。当 `func inner()` 内部写 `count = count + 1` 时：
1. SymbolCollectionPass 为 `inner` 作用域创建局部符号 `inner:count`
2. SymbolResolutionPass 将 RHS 的 `count` 引用绑定到 `inner:count`（本地优先）
3. 运行时：`inner:count` 从未被初始化 → RUN_003 "variable not defined"

这与 Python 的行为一致（Python 同样需要 `nonlocal` 关键字）。IBCI 目前无此机制。

**设计选项**：

| 方案 | 描述 | 复杂度 | 与 IBCI 设计契合度 |
|------|------|--------|-------------------|
| A. `nonlocal` 关键字 | 显式声明 `nonlocal count`，告知编译器赋值目标为外部变量 | 中 | 高（Python 惯例，用户直觉明确） |
| B. 自动推断 | 若外部作用域已有同名变量且本作用域无声明，赋值自动作用于外部 | 低 | 低（违背 IBCI "显式优于隐式" 原则） |
| C. Cell 写入语法 | 提供 `outer.count = ...` 或其他显式访问外部变量的语法 | 高 | 中 |

**建议**：方案 A（`nonlocal` 关键字），理由：
- 与 IBCI "显式声明 > 隐式推断" 的设计哲学一致
- 用户心智模型清晰，Python 开发者零学习成本
- 改动面可控：Lexer（新关键字）→ Parser（新语句）→ SymbolCollectionPass（标记外部绑定）→ 运行时（Cell 写回）

**前置条件**：P0-A 完成后再启动，确保 Cell 基础设施验证充分。

**预估工作量**：8-12 小时（含词法/语法/语义/运行时全链路 + 测试）。

---

### 确认为设计决策（不修复）

| 测试 ID | 原因 | 处理 |
|---------|------|------|
| **INV-LAMBDA-3** | IBCI 无 walrus (`:=`) / lambda 体赋值语法 | 保持 SKIP，标注为"设计限制" |
| **INV-SCOPE-1** | SEM_002 禁止 if-block 内重声明同名变量 | 保持 SKIP，标注为"设计限制" |

---

## P3 候选（远景；详见 PENDING_TASKS）

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
