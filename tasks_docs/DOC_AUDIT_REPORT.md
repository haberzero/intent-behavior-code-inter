# DOC_AUDIT — docs/ 文档治理审核记录（2026-08-06）

> 依据 `doc-governance` skill + `docs/WRITING_GUIDE.md` 对 `docs/` 全量健康检查。
> 5 个并行 general subagent 分目录审计 + **全部 P0 已二次源码核验**。
> **执行完成（2026-08-06）**：F0-F4 全部落地（commit 87666d1 / d66d3df / 27e7e35 / d93d14d），
> 每阶段全量 pytest 零回归。执行记录见 git 历史与本文件各章，已完成项不再逐条勾选。

---

## 一、方法与范围

- 范围：`docs/` 全部 42 篇（9511 行），排除 `docs/backup/`（封存归档）。
- 标准：`docs/WRITING_GUIDE.md`（红线 E1-E12 / 结构 A / 行文 C / 模板 D / 引用 F）+ `docs/README.md` §三治理纪律。
- 红线分类速查：E1 过程叙述 | E2 历史演变 | E3 日期戳/完成标记 | E4 未实现设计 | E5 任务编号/代号 | E6 代码散文翻译 | E7 核查/进度/状态 | E8 作者私缩写 | E9 混合抽象层级 | E10 过时/事实矛盾 | E11 未标注假设 | E12 智能体元信息。

---

## 二、P0 事实矛盾/断链（~17 处，最优先）

> 全部已对源码核验属实。修复以"代码为最高真相"。

### 2.1 失效代码路径（文件不存在）

| 文件:行 | 错误引用 | 实际 |
|---------|---------|------|
| `architecture/01_principles.md:514` | `core/runtime/host/host_interface.py` | `core/kernel/host_interface.py` |
| `architecture/01_principles.md:515` | `core/runtime/bootstrap/builtin_initializer.py` | `core/runtime/bootstrap/primitive_initializer.py` |
| `architecture/02_metadata_ast.md:471` | `core/compiler/semantic/passes/side_table.py` | 侧表经 `ExecutionContext.get_side_table` + 序列化器 `side_tables` 承载 |
| `KNOWN_LIMITS.md:332, 348` | `core/runtime/bootstrap/builtin_initializer.py` | `primitive_initializer.py` |
| `subsystems/01_intent_system.md:633` | `core/compiler/semantic/passes/semantic_analyzer.py` | `core/compiler/semantic/analyzer.py` |
| `appendix_type_system_rationale.md:615` | `docs/IBCI_TYPE_SYSTEM.md` | 现为 `docs/architecture/03_type_system.md` |

### 2.2 不存在的 API/接口/枚举（与代码矛盾）

| 文件:行 | 错误内容 | 实际 |
|---------|---------|------|
| `subsystems/01_intent_system.md:188-210` | `set_pending_override_intent()` / `consume_pending_override_intent()` | `activate_statement_one_shot_intent()` / `cleanup_statement_one_shot_intent()` |
| `subsystems/01_intent_system.md:333-335` | `IntentMode.SMEAR`；`IntentRole.INLINE` | `IntentMode` 无 SMEAR；`IntentRole` 为 BLOCK/SMEAR/CALL/GLOBAL/DYNAMIC/STACK |
| `guide/07_testing.md:168` | `idbg.show_vars()` | `idbg.vars()` / `idbg.print_vars()` |
| `subsystems/04_plugin_system.md:70` | ai 模块 `set_retry_hint` / `get_retry_prompt` | 不存在（全仓无定义） |

### 2.3 自相矛盾 / 不存在的节点名

| 文件:行 | 问题 |
|---------|------|
| `architecture/05_vm_specification.md:32` vs `:42` | §1.1 称"不存在 `IbLLMExceptionalStmt` 包装节点"但 §1.2 列出它——需统一表述（节点实际存在 ast.py:294，binding 消费后不入 body） |
| `architecture/05_vm_specification.md:43` | `IbConst`/`IbList`/`IbFString` 不存在（实际 `IbConstant`/`IbListExpr`；无 IbFString） |
| `architecture/05_vm_specification.md:42` | `IbDelete` 不存在；CPS 主节点为 `IbSwitch`（表内缺失），`IbCase` 为其子节点 |

---

## 三、P1 红线违规（~60 处，批量清理）

### 3.1 E3 日期戳 / 完成标记（~17）

- `KNOWN_LIMITS.md`：L217、237、295（"2026-08-05"）；L450（"已修复（2026-08-04，任务 A）"）；L571（"已修复（状态说明）"）；L380/412/448 标题带"（规则化已启用）（已加可观测性）（已补齐）"
- `architecture/01_principles.md:214`（"**2026-08-05 类型强化**"）；`architecture/03_type_system.md:348`（"返回标注强制（2026-08-05）"）
- `syntax/02_variables.md:34`；`syntax/07_behavior_expressions.md:128`
- `subsystems/05_coroutine.md`：L3、16、43、112、147、160、173（整篇日期戳）

### 3.2 E2 历史演变叙述（~15）

- `KNOWN_LIMITS.md`：L91（"已从用户 API 移除"）、416（"原先…已改为"）、580/588（"此前"）、594（"signal…已移除"）、596（"spawn/task 等旧形态已删除"）
- `architecture/03_type_system.md:204,134`（"已全部归并删除"/"已彻底删除"）；`01_principles.md:214`
- `syntax/01_types.md:28`；`syntax/02_variables.md:30,35`；`syntax/07_behavior_expressions.md:158,172,246`；`syntax/09_intent_system.md:17`
- `subsystems/01_intent_system.md:144,439,625`

**改写原则**：改现在时陈述当前事实（"不支持 X，用 Y"），删"已/不再/原先/此前/收紧"。

### 3.3 E5 任务编号 + E7 状态/进度（任务日志污染）

- **`subsystems/05_coroutine.md` 整篇是任务日志**：PT-3.1/3.2、PT-SEM-1.1、PT-4.2、PT-SEM-4（L3,112,140,160,181）；"实现进度"+"pytest 1311/1322 passed"（L147,156,179）；"下一步"（L181-183）；SHELVED 状态（ARCHITECTURE.md:14,18）
- `subsystems/03_callable_fn.md:7,44,48`（"当前状态"章节/"规划见任务文档"/"以上为当前设计状态的简要概述"）
- `subsystems/01_intent_system.md:497-506,548`（"验证覆盖"清单/持续验证）

**处置**：`05_coroutine` 设计要点迁 `tasks_docs/`（如 WORKLOG/THREAD_DESIGN），docs/ 仅留定位段 + SHELVED 状态 + 指向。

### 3.4 冻结测试数字（违反 README §3.2 数字纪律）

- `architecture/05_vm_specification.md:184-186`（"19 测试"实际 15/9/12，已过时）
- `architecture/appendix_type_system_rationale.md:642,646`（"1056 测试"）
- `subsystems/05_coroutine.md:156,179`（"1311/1322"）

### 3.5 E9 混合抽象层级

- `KNOWN_LIMITS.md:380-388`（§十五全量复制 `architecture/04` §5 的 DDG 内部机制：BehaviorDependencyAnalyzer/dispatch_eligible/_pending_futures）→ 压缩为"限制+边界"指向 architecture/04
- `KNOWN_LIMITS.md:382`（编译器内部类/实现路径入语言限制文档）
- `syntax/11_modules.md:158,117`（PermissionManager 类名/IMPORT_GATED 内部枚举）
- `syntax/13_mock_testing.md:201`（`ibci_modules.ibci_ai.mock_service` 实现路径）
- `syntax/14_concurrency.md:7`（runtime_context/node_pool/registry 实现概念）

### 3.6 E4 未实现设计（除非独立"规划"章节）

- `architecture/01_principles.md:442-447`（"需要的代码配合：--pre-scan-specs/export_metadata"）；`:382-386`（PyInstaller/Nuitka 兼容承诺）
- `KNOWN_LIMITS.md:71`（"未来版本中支持"）、376（"未来演进思路"）、458（"若未来需扩展"）
- `subsystems/02_file_container.md:47,162`（"未来全模态聚合容器"/"未来设计"）
- `subsystems/03_callable_fn.md:44`；`subsystems/04_plugin_system.md:50,111`（"预留/未实现"）

### 3.7 E12 智能体元信息（docs/ 只面向人类，绝对禁止）

- `subsystems/05_coroutine.md:3`（tasks_docs/NEXT_STEPS.md 指针）
- `KNOWN_LIMITS.md:458`（tasks_docs/COMMS_DESIGN_REVIEW.md 指针——且该文件不存在）
- `guide/00_environment.md:46`（"详见 tests/README 与 tasks_docs/NEXT_STEPS.md"）
- `ARCHITECTURE.md:28`（阅读路径以 tasks_docs/ 结尾）
- `docs/README.md:112,150-157`（分支工作流指令/grep 命令——属 AGENTS.md 职责）

### 3.8 其它 P1

- `subsystems/01_intent_system.md:6-7`（"以下模块已重构为包"历史免责声明，改修正路径并删声明）；`:27-41,346-383`（syntax 使用说明越层入 subsystems）；`:633`（见 2.1）
- `subsystems/04_plugin_system.md:8-141`（模块 API 参考越层入 subsystems，应属 syntax/11）

---

## 四、P2 可改进（~70）

### 4.1 C1 中文长句（~15，拆分）

- `KNOWN_LIMITS.md:17,204,332,382,515`
- `syntax/10_robustness.md:85,89`；`syntax/13_mock_testing.md:196,215`
- `architecture/03_type_system.md:281`；`architecture/04_vm_interpreter.md:107,109`；`architecture/05_vm_specification.md:155`
- `WRITING_GUIDE.md:17,200`（规范自身 C1 自违规）
- `subsystems/02_file_container.md:106`；`guide/06_multistep.md:112`

### 4.2 D1 平行模板 / A3 标题格式

- `syntax/13_mock_testing.md:7`（`## N.` 层级与其余 13 篇 `### N.N` 不一致；"启用 MOCK 模式"动词标题）
- `syntax/04_control_flow.md:84`（`### 4.4b pass` 编号不一致）
- `architecture/02_metadata_ast.md:490`（"## 变量存储模型"误置文末，未编号章节）
- `subsystems/03_callable_fn.md`、`subsystems/05_coroutine.md`（`## N.` 体例与 subsystems 其他篇不一致）

### 4.3 A5 概念部分复制（归属唯一）

- `syntax/10:87-105` 与 `KNOWN_LIMITS.md:541-565` 重述同一"llmexcept 禁文件写"限制 → 择一为归属，另一改摘要+引用
- `architecture/03:348-352` 重复 `syntax/07:131-146` 的 `-> auto` 规则 → 删越层复制留指针
- `guide/04:93-150` 全量重述意图上下文（subsystems/01 权威）→ 教程体改为精要+指向
- `KNOWN_LIMITS.md:448-458`（§十八）重述 Optional 方法（syntax/01:41-54 权威）
- `architecture/01_principles.md` 与 `07_kernel_native_modules.md`、`02_metadata_ast.md:87-93`（exported_types 部分复制）
- `syntax/13_mock_testing.md:180` 与 `syntax/07:217` 逐字重复
- `architecture/04:23,75`（handler 数 43 与实际 45 不一致）；`:85`（节点表遗漏 4 个实际存在节点）

### 4.4 C6 超长文件（>500 行，审视拆分）

- `appendix_type_system_rationale.md`（678）、`subsystems/01_intent_system.md`（634）、`KNOWN_LIMITS.md`（596）、`architecture/02_metadata_ast.md`（516）

### 4.5 其它

- `architecture/01_principles.md:142`（UTS 无定义缩写）；`:241`（§5.4 自指循环引用）
- `architecture/03_type_system.md:137`（"艺术品"错别字→"产物"）；`:1`（标题"代码对齐版"标签）；`:98`（allowed_element_types 注释"多类型 list"与"已移除"矛盾）
- `architecture/04_vm_interpreter.md:65,152,...`（`VM_SPEC.md` 别名引用，实际 05_vm_specification.md）；`:238`（"当前 LLM 调用路径"状态叙述）
- `architecture/05_vm_specification.md:1`（标题夹 VM_SPEC.md 别名）
- `architecture/02_metadata_ast.md:125-135`（SideTableManager 示意类代码）；`:459`（"旧代码"）；`:87-93`（A5）；`:512-513`（FAQ 掺未来规划）
- `appendix_type_system_rationale.md:24`（"7 种 XxxSpec"与 03"旧 9 个"数字不一致）；`:7,674-676`（对话体，归档可豁免但宜标注）
- `guide/01_setup.md:121-122`（悬空链接定义）
- `subsystems/04_plugin_system.md:1,3`（"指南"语义/定位段缺"给谁看"）
- `syntax/09_intent_system.md:17`（"约束（当前）"时间限定）
- `docs/README.md:6`（"5 个主手册+3 子目录"与实际 6+4 矛盾）；`:67-73`（目录树遗漏 backup/）
- `ARCHITECTURE.md:18`（附录标注"历史"）；`:25`（指引读者去"非当前实现参考"的附录，自相矛盾）

---

## 五、体系级问题

1. **[P0] 工作流元信息污染 docs/**：`subsystems/05_coroutine.md` 整篇是任务日志；`KNOWN_LIMITS`/`guide/00`/`ARCHITECTURE` 含 tasks_docs/PT 指针。处置：`05_coroutine` 设计要点迁 tasks_docs/，docs/ 只留定位段+SHELVED+指向；清除全部 tasks_docs/PT/日期/pytest 数字引用。
2. **[P1] KNOWN_LIMITS 角色越界 + 章节编号混乱**：§十五（DDG 内部机制→architecture/04）、§十六（待决策设计→tasks_docs）、§十八（已修复状态→git）、**§二十二 重复编号**（见 §六）。处置：重排章节号 + 越界内容迁出。
3. **[P2] How-to 整类缺失**（WRITING_GUIDE 自认"当前缺失"）+ **A.8"深入指引"尾段全体系未落地**（无一篇含）。处置：补 1-2 篇 How-to；为 syntax/architecture/subsystems 各篇补"深入指引"。
4. **孤儿文档**：`docs/backup/02_multimodal_behavior.md`（896 行，无引用、未入目录树、已封存）→ 归档删除或移出 docs/。

---

## 六、本批次自身引入的违规（须优先修）

> 2026-08-06 整合巩固工作引入，**审核自查归属，最先修复**：

1. **`KNOWN_LIMITS.md:592` §二十二 重复编号**：追加"## 二十二、通信原语面"撞上 `:541` 已有的"## 二十二、llmexcept"——应改为 **§二十四**（当前 §二十三 在 :569）。
2. **`syntax/14_concurrency.md:7` E9**：syntax 层出现 `runtime_context`/`node_pool`/`registry` 实现概念，改为用户可见语义或指引 subsystems。
3. **`KNOWN_LIMITS.md:594,596` E2**：§二十二 内"signal 已移除/spawn/task 已删除"历史叙述，改现在时。
4. **`KNOWN_LIMITS.md:594` F3**：指向 `docs/syntax/14_concurrency.md` 的引用有效（此条无误，保留）。

---

## 七、执行计划（分阶段，每阶段全量 pytest 零回归 + commit）

| 阶段 | 内容 | 验证 |
|------|------|------|
| **F0 本批引入修复** | §六 的 3 处（重编号/E9/E2） | 目视 + grep |
| **F1 P0 断链/矛盾** | §二 全部 ~17 处 | grep 路径存在 + 源码核验 |
| **F2 P1 红线批量** | §三：清日期戳/历史叙述/冻结数字/任务代号；`05_coroutine` 迁 tasks_docs；KNOWN_LIMITS 章节重排 + 越界内容迁出 | grep 残留扫描（pattern 从 WRITING_GUIDE 红线派生） |
| **F3 P2 改善** | §四：长句拆分/模板统一/A5 去重/超长文件审视 | 目视 + 抽样 |
| **F4 体系** | §五：How-to 补齐 + "深入指引"尾段 + backup 处置 | 体系级复查 |

**交叉核验纪律**：每阶段后重读 WRITING_GUIDE（不凭记忆），grep 扫描残留违规，差距分析；修复"事实矛盾以源代码为最高真相"，不确定标注"待验证"。

---

## 八、验证方式

- 断链：`ls`/`grep` 核实路径与 API 存在。
- 日期戳/历史/任务代号残留：grep `2026-0[0-9]|已移除|原先|此前|不再|PT-[A-Z]|tasks_docs/`。
- 每阶段全量 `python -m pytest tests/` 零回归。
- 完成标准：本文件各阶段勾除，NEXT_STEPS 中 DOC_AUDIT 条目移除。
