# IBCI 项目全面审计与试用报告

**审计日期**：2026-05-27  
**审计范围**：代码库全览、文档一致性核对、语法完整性与正交性验证、Mock 试用与边界探查

---

## 一、IBCI 是什么 — 设计思想确认

**IBCI = Intent-Behavior-Code-Inter（意图-行为-代码 交互语言）**，定位为"人类与 LLM 协作编程的中间语言"。其核心范式是 **四元结构**：

- **Code 层**：传统确定性代码（赋值、控制流、运算）
- **Behavior 层**：`@~...~` LLM 调用表达式，作为一等公民"行为子句"嵌入代码流
- **Intent 层**：`@`/`@!`/`@+`/`@-` 四种意图标记 + `intent_context` 内置对象，形成显式可叠加的上下文栈
- **Inter 层**：人类与 LLM 通过 `__to_prompt__` / `__from_prompt__` / `__outputhint_prompt__` / `__payload_prompt__` / `__validate_prompt__` 协议族交换结构化语义

**工程框架** 严格分层（验证一致）：`core/base → core/kernel → {core/compiler, core/runtime} → core/extension`，单向依赖。公理体系（`AxiomRegistry` + `has_*_cap` 能力标志）与面向对象体系（`IbClass`/`IbObject`/`IbSpec`）正交解耦，内置类型走 axiom 路径，用户类走 spec 路径。

**关键设计资产**：
- 编译器语义采用 **4-Phase 流水线**：SymbolPhase → TypePhase → BindingPhase → IntegrityPhase（`core/compiler/semantic/pipeline.py`）
- 运行时 VM 采用 **CPS 风格 yield 驱动**（`vm_executor.py`），为将来协程/异步保留接口
- `llmexcept` 通过快照-隔离-重试机制将 LLM 不确定性局部化
- 意图均为 AST 节点（非旁路 side table），帧作用域 + fork-on-call 传播

---

## 二、当前工程进展 — 与文档核对

**测试基线**：`pytest` 全跑 **832 passed, 2 skipped in 8.31s**，与 `docs/COMPLETED.md` 记载完全一致。两个 skip（INV-LAMBDA-3、INV-SCOPE-1）是已记录的设计限制。

**最近完成**（与 `COMPLETED.md` / `NEXT_STEPS.md` 对账）：
- 2026-05-27  Phase 2 `__payload_prompt__` 多模态 payload 协议 ✅
- 2026-05-26  nonlocal 关键字完整实现链 ✅（lexer→parser→symbol_resolution→binding→VM Cell write-back 链已核实）
- 2026-05-14  ihost.run_isolated 路径相对入口目录解析修复 ✅（`service.py:222-232` 已核实）

**下一步**（`NEXT_STEPS.md`）：Phase 3 — `audio`/`image`/`video` 内置类型族，3-5 天预算。文档与代码状态自洽。

---

## 三、文档与代码不一致点 — 本次新发现

### 🔴 不一致 #1：KNOWN_LIMITS §二十.4 已严重过时

`KNOWN_LIMITS.md:481` 仍在声明：

> "`__snapshot__` / `__restore__` 用户协议在 llmexcept 路径里未被调用 …… 目前**只是文档承诺**"

但 `core/runtime/interpreter/llm_except_frame.py:189-197, 284-295` 的代码事实是：用户类的 `__snapshot__` / `__restore__` **已经实现** — 调用路径完整，方案 B（协议）优先于方案 A（深克隆），原地恢复 + 错误降级语义都已落地。这条 KNOWN_LIMITS 应当被删除或标注"已修复"。

**影响**：阅读文档的开发者会误认为该功能未实现，可能绕过协议走手动深拷贝，或者在评估用户类 llmexcept 可靠性时做出错误判断。

---

### 🔴 不一致 #2：`examples/03_advanced_features/isolation_demo/parent.ibci` 已无法跑通

**错误信息**：
```
Error: Entry file not found:
.../isolation_demo/examples/03_advanced_features/isolation_demo/sub_project/child.ibci
```

**根因**：`ihost.run_isolated` 在 2026-05-14 改为基于 `entry_dir`（即 `isolation_demo/` 目录）解析相对路径（`service.py:231`），但 `parent.ibci:22` 仍写着：

```
ihost.run_isolated("examples/03_advanced_features/isolation_demo/sub_project/child.ibci", policy)
```

这是基于旧的 CWD 假设写的路径，导致被双重拼接。**此示例违反 `NEXT_STEPS.md` 维护守则 §3 的"示例必须可零配置跑通"硬约束。**

**修复极小**：将路径改为 `"./sub_project/child.ibci"` 即可。

---

## 四、未知 Bug 发现 — 本次审计的最重要产出

### 🔴 BUG #A：控制流构造在面对不确定 LLM 条件时行为**严重不一致**

通过对比三个 VM handler（`core/runtime/vm/handlers.py`）：

| 构造 | 文件位置 | 不确定 LLM 条件下的行为 |
|---|---|---|
| `if @~...~:` | `handlers.py:628-629` | **静默返回 None**，两个分支都不进入 |
| `while @~...~:` | `handlers.py:647-648` | **静默 break**，循环体一次都不执行 |
| `for @~...~:`（条件式） | `handlers.py:1751-1757` | **抛出 `LLMParseError`** |

**具体代码对比**：

`vm_handle_IbIf`（`handlers.py:619`）：
```python
last = executor.runtime_context.get_last_llm_result()
if last and not last.is_certain:
    return executor.registry.get_none()   # ← 静默吞掉
```

`vm_handle_IbWhile`（`handlers.py:637`）：
```python
last = executor.runtime_context.get_last_llm_result()
if last and not last.is_certain:
    return executor.registry.get_none()   # ← 静默退出循环
```

`vm_handle_IbFor`（`handlers.py:1750`）：
```python
# uncertain 且无 llmexcept handler：抛出 LLMParseError
raise ThrownException(error)             # ← 正确抛错
```

**影响**：

- `if` 的语义错误最隐蔽：当 LLM 输出无法解析为 bool 时，用户既看不到 else 分支也看不到错误 — 整段 `if/else` 被静默吞掉。在 condition-driven 流程是 IBCI 核心特色的前提下，这是**非常严重的语义陷阱**。
- `while` 看似优雅退出，但与"LLM 解析失败应触发 llmexcept 或抛错"的官方语义（`IBCI_SYNTAX_REFERENCE §10.3`）完全相悖，用户无任何提示地得到一个"循环 0 次"的结果。
- `for` 是唯一行为正确的（要么 llmexcept 自愈、要么抛错）。

**复现路径**：`examples/01_getting_started/03_flow_control_and_behavior.ibci` 在 TESTONLY/MOCK 模式下：
1. 第 41 行 `if @~情绪积极？~:` — 两个分支都不打印（静默吞 bug）
2. 第 64 行 `while @~...~` — 循环 0 次直接结束（静默吞 bug）
3. 第 86 行 `for @~...~` — 抛 `LLMParseError` 崩溃

**建议修复**：统一 `if`/`while`/`for` 在 LLM 条件不确定时的语义，全部抛出 `LLMParseError`（或进入 llmexcept 自愈）。`if`/`while` 当前的静默吞错行为是历史遗留隐患，建议作为下一个**插队**修复优先项。

---

### 🟡 BUG #B：示例 03 的 bool LLM 调用未保护（即便 BUG #A 修复后仍崩溃）

`examples/01_getting_started/03_flow_control_and_behavior.ibci` 三个 `@~...~` bool 调用都没有 `llmexcept` 保护，也没有 `# MOCK:` 指令。即便 BUG #A 统一了语义（全部抛错），此示例仍然崩溃。应同时为示例中的 LLM 条件调用添加 `# MOCK:` 指令或 `llmexcept` 保护，使其在零配置下可跑通。

---

## 五、语法完整性与正交性核验结论

依据 `docs/IBCI_SYNTAX_REFERENCE.md`（1401 行）逐项核对：

| 维度 | 状态 | 备注 |
|---|---|---|
| 内置类型 + 公理（int/float/str/bool/list/dict/tuple/Optional/range） | ✅ 完整 | 能力标志与 axiom 一致 |
| 用户类（class/继承/super/构造/方法/字段） | ✅ 完整 | — |
| 闭包（lambda/snapshot/nonlocal/Cell 提升） | ✅ 完整 | nonlocal 链路已验证 |
| 控制流（if/while/for/break/continue/return/throw） | ⚠️ 有缺陷 | **BUG #A：不确定 LLM 条件处理不正交** |
| LLM 行为表达式 `@~...~` | ✅ 完整 | 解析+执行链完整 |
| 意图栈（`@`/`@!`/`@+`/`@-`/`intent_context`） | ✅ 完整 | 帧作用域 + fork-on-call 已验证 |
| `llmexcept` + retry | ✅ 完整 | 用户协议优先 + 深克隆降级均已落地 |
| Prompt 协议族（5 个 dunder） | ⚠️ 有隐患 | §26 自检发现 4 类隐患（KNOWN_LIMITS §26 已记录） |
| 强转 `(T)x` + SEM_091 | ✅ 完整 | 编译期预检 warning |
| 方法重写 + SEM_092 | ✅ 完整 | 协变检查 warning |
| `__call__` 协议 | 🟡 已知缺陷 | KNOWN_LIMITS §3 已记录，非本次新发现 |
| 动态宿主 ihost.run_isolated | ⚠️ 示例坏 | **不一致 #2**，但运行时实现本身正确 |
| 插件系统 | ✅ 完整 | `plugins_demo` 验证通过 |
| DDG 并发分析 | 🟡 编译完成/运行未接通 | KNOWN_LIMITS §21 已记录 |

**正交性缺口**：除了 BUG #A 之外，未发现新的正交性缺陷。语法间交互（lambda × snapshot、`@!` × `@+` 共存、nonlocal × llmexcept、`__call__` × intent context）均在测试体系下有覆盖。

---

## 六、试用结论 — 设计理想与实现的差距

**总体评价**：IBCI 当前实现质量**高于其用户文档自我评价**。

**强项**：
- 832 测试稳定全绿，分层架构干净，公理与 spec 解耦清晰，4-Phase 编译流水线易于扩展
- 多数 KNOWN_LIMITS 条目已被实际修复但 doc 未跟进（§20.4 是典型），说明开发节奏快于文档维护节奏
- 意图系统、llmexcept 快照、CPS VM 这三个最复杂的子系统已经稳定可用，给未来异步/并发留了完整钩子

**核心差距**：

1. **控制流面对 LLM 不确定性的语义不正交（BUG #A）** — 本次审计的最大未知发现。`if`/`while` 静默吞错而 `for` 正确抛错，会让用户写出"看上去能跑、实际静默吞掉错误"的代码，属于语言层面的隐性陷阱。
2. **示例维护滞后** — 2 个跑不通的示例（`03_flow_control_and_behavior.ibci` + `isolation_demo/parent.ibci`），与项目高度强调的"零配置跑通"承诺矛盾。
3. **文档（KNOWN_LIMITS）滞后于代码** — 至少 §20.4 已彻底过时（`__snapshot__`/`__restore__` 已实现），建议安排一次文档大扫除。
4. **DDG 并发**（§21）、**`__call__` 协议**（§3）、**容器深快照**（§5）等已知缺口仍按计划排队，无需关注。

---

## 七、建议的下一步演进优先级（供决策）

按"边际收益 / 成本"排序：

### P0 — 立即处理（成本极低，收益极高）

1. **统一 `if`/`while`/`for` 在不确定 LLM 条件下的语义（BUG #A）**  
   修复位置：`core/runtime/vm/handlers.py` `vm_handle_IbIf`（~5 行）和 `vm_handle_IbWhile`（~5 行）  
   方案：仿照 `vm_handle_IbFor`，当 `last.is_certain == False` 且无 llmexcept handler 时抛 `LLMParseError`  
   建议：在 Phase 3 多模态开始之前**插队**修复。

2. **修复 2 个跑不通的示例**  
   - `examples/01_getting_started/03_flow_control_and_behavior.ibci`：为三个 LLM bool 条件添加 `# MOCK:` 指令或 `llmexcept` 保护  
   - `examples/03_advanced_features/isolation_demo/parent.ibci:22`：路径从 `"examples/03_advanced_features/isolation_demo/sub_project/child.ibci"` 改为 `"./sub_project/child.ibci"`

### P1 — 近期处理

3. **KNOWN_LIMITS 文档大扫除**  
   - §20.4：标注"已修复"或移除（`__snapshot__`/`__restore__` 已实现）  
   - 通读全部章节逐条对照代码，将已修项目移入 `COMPLETED.md` 或加 ✅ 标注

### 按原计划

4. **Phase 3 多模态类型**（`audio`/`image`/`video` 内置类型族）
5. **远期**：PT-4.7 DDG 并发分发接通；`__call__` 协议重新设计；用户类泛型与运算符重载（KNOWN_LIMITS §20.1–.2）

**建议立即处理顺序**：P0-1 → P0-2 → P1-3 → 继续 Phase 3。前三项预计 1-2 天内可全部完成。

---

## 附录：审计所用关键文件索引

| 文件 | 用途 |
|---|---|
| `docs/NEXT_STEPS.md` | 当前最紧要下一步 + 维护守则 |
| `docs/COMPLETED.md` | 完成时间线；最近：Phase 2 payload_prompt (2026-05-27) |
| `docs/KNOWN_LIMITS.md` | 590 行；§26 在本次审计当日新增 |
| `docs/IBCI_SYNTAX_REFERENCE.md` | 1401 行，用户侧语法权威参考 |
| `docs/PENDING_TASKS.md` | 已阻塞/等待中的未来规划 |
| `core/runtime/vm/handlers.py` | **BUG #A 所在**：`vm_handle_IbIf:628`、`vm_handle_IbWhile:647`、`vm_handle_IbFor:1751` |
| `core/runtime/interpreter/llm_except_frame.py` | llmexcept 快照/恢复实现（与 §20.4 文档相悖，代码已实现） |
| `core/runtime/host/service.py:222-232` | run_isolated 路径解析（2026-05-14 修复） |
| `examples/01_getting_started/03_flow_control_and_behavior.ibci` | **BUG #B 所在**：3 个 LLM bool 条件无 MOCK 无保护 |
| `examples/03_advanced_features/isolation_demo/parent.ibci:22` | **不一致 #2 所在**：旧路径导致双重拼接崩溃 |
