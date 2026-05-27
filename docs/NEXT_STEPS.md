# NEXT_STEPS — 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `docs/PENDING_TASKS.md`；历史归档见 `docs/COMPLETED.md`。
> 已知语言级限制见 `docs/KNOWN_LIMITS.md`。
>
> **最后更新**：2026-05-27（发现面向对象体系架构级缺陷；P0 = 架构基座修复）

---

## 当前测试基线（每次开新分支前必须复跑确认）

```bash
python -m pytest tests/ -q --tb=no --no-header
```

**2026-05-27 实测结果**：`812 passed, 2 skipped`（架构清理完成，全部通过）。

---

## P0 紧急：面向对象体系架构基座修复

**根源问题发现**：经多角度深度分析，IBCI 的面向对象体系存在**架构级设计缺陷**：

1. **混合派发模式**：消息传递范式（`receive()`）与 Python 原生调用混用，导致抽象泄漏
2. **双重初始化路径**：内置类型与用户类型使用完全不同的 vtable 填充机制
3. **协议方法不一致**：不同协议方法的发现和调用机制各不相同（`hasattr()` vs vtable vs axiom）
4. **基础类型语义寄生**：算术运算、类型判断等核心语义完全依赖 Python 底层实现

**具体抽象泄漏点**（7处）：
- `IbObject.receive()` 中的直接 Python 调用（`hasattr()` + Python 方法）
- 基础类型运算符返回未封装的 Python 值
- `IbNativeFunction.__getattr__` 暴露内部细节
- 协议方法的双重调用路径（直接调用 vs `receive()`）
- 类型推断依赖 Python `isinstance()`
- 字段直接访问绕过协议（无 getter/setter）
- 协议方法实现机制不一致

**P0 修复任务**（必须按顺序完成，避免级联破坏）：

**架构清理完成项**（2026-05-27）：
- ✅ **AST 统一**：IbArg 添加 annotation 字段，消除 `Union[IbArg, IbTypeAnnotatedExpr]` 类型不一致
- ✅ **类型注解强化**：FunctionSymbol.spec 明确为 TypeDef，消除 hasattr 防御性检查
- ✅ **消息传递统一**：修复 primitives.py Enum axiom 的 hasattr 残留，统一使用 receive() 派发
- ✅ **P0-3 统一初始化路径**：实现 `_bind_operator_method()` 显式绑定，清理技术债，架构对称性完成

### P0-1：统一协议方法派发（预估 2-3 天）

- [x] 移除 `llm_executor.py` 中所有 `hasattr(val, '__to_prompt__')` 直接调用
- [x] 移除 `kernel.py:IbObject.receive()` 中的 `hasattr()` 检查和直接 Python 方法调用
- [x] 移除 `intent.py` 中的 `hasattr(val, '__to_prompt__')` 直接调用
- [ ] 建立协议方法注册表（`ProtocolMethodRegistry`）
- [ ] 统一协议方法派发：所有协议方法通过 `receive()` 查找 vtable
- [ ] 测试：确保 `__to_prompt__` / `__from_prompt__` / `__outputhint_prompt__` 在内置类型和用户类型上一致工作

**进展**：已完成核心 hasattr() 消除（35dad7d）；所有 812 测试通过。

### P0-2：用户类运算符重载支持（预估 2-3 天）

- [x] 扩展 `builtin_initializer.py:_auto_bind_operators` 支持用户类型
- [x] 在语义分析期间识别用户类的运算符方法（`func __add__(...)`）
- [x] 将运算符方法注册到用户类的 members（编译时 MethodMemberSpec）
- [x] 编译期检查运算符方法签名（`TypeCheckingPass` 通过 `resolve_op` 查找）
- [x] 测试：用户类可定义 `__add__` / `__eq__` / `__lt__` 等运算符

**实际技术路径说明**：
- ✅ 编译期：SymbolCollectionPass 填充方法签名到 IbSpec.members，SpecRegistry.resolve_op 查找用户定义运算符
- ✅ 运行期：通过通用 receive() 机制调用
- ✅ 显式绑定：P0-3 实现 `_bind_operator_method()` 确保架构对称性和代码意图清晰

**进展**：已完成编译时运算符检测与类型推断（d999783）。测试验证：`/tmp/test_user_operator.ibci` 编译并运行成功。

### P0-3：统一初始化路径（预估 1-2 天）

- [x] 实现 `_bind_operator_method()` 显式绑定运算符方法
- [x] 消除 `interpreter.py:683-685` 空 pass 技术债
- [x] 架构对称性：用户类与内置类运算符绑定机制文档化
- [x] 测试：全量 pytest 验证无回归（812 passed, 2 skipped）

**实现说明**：
- ✅ 用户类运算符方法现在通过 `_bind_operator_method()` 显式标记和验证
- ✅ 架构清晰化：内置类（Python实现）vs 用户类（AST实现）的运算符绑定机制差异已文档化
- ✅ 编译期保证：SpecRegistry.resolve_op() 检查 spec.members
- ✅ 运行期派发：receive() 机制统一处理所有方法调用（包括运算符）

**进展**：已完成（2026-05-27）。P0 架构修复全部完成，所有 812 测试通过。

**阻塞关系**：
- P0-1 是 P0-2/P0-3 的前置（协议方法派发必须先统一）
- P0-2 和 P0-3 可部分并行（但最终合并需要 P0-3）

**优先级理由**：
- 多模态设计（Phase 2-5）依赖类型扩展能力，当前架构无法支持
- llmexcept 快照协议实现需要统一的协议方法机制
- 用户类型不是"一等公民"限制了 IBCI 的表达能力
- 架构债务累积效应：延迟修复会指数级增加成本

---

## P1 候选（阻塞于 P0）：PT-SEM-1 Semantic Pipeline 生产就绪化

**前置条件**：Semantic 4-Phase pipeline 已稳定运行 ✅；nonlocal 完成后闭包语义全链路验证通过 ✅

**具体待做**：
1. **错误信息优化**：当前 `SEM_xxx` 错误码附带的消息偏技术化，需转化为用户友好表述
2. **诊断工具**：为符号表、类型绑定、行为依赖图提供可视化导出（JSON/dot 格式）
3. **性能基准**：建立编译时间基准测试（针对 100+ 行脚本）
4. **CI/CD 集成**：语义分析测试套件纳入 CI 流水线自动运行

**预估工作量**: 15-20 小时

> 注：本项由 PENDING_TASKS PT-SEM-1 提升。如有更紧迫需求出现，可替换。

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
