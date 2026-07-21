# HISTORY_LOG — 历史演进详细日志

> 本文档归档较早期的完成记录（详细日志）。精简时间线见 `tasks_docs/COMPLETED.md`。
> 当前最紧要项见 `tasks_docs/NEXT_STEPS.md`；阻塞项见 `tasks_docs/PENDING_TASKS.md`。

---

## 2026-05-15 锚点：回顾性事实核查与一体两面演进报告

针对项目所有者关于 llmexcept 演进史（曾用 `node_protection` 侧表挂载、最终回退到 AST 字段直接存储）以及"现有 AST/侧表大多由智能体产生、人类难以独立把控"的诉求，完成一次全链路回顾性分析，产出"一体两面"两份报告（宏观 + 技术细节），并对若干旧分析结论做事实订正。

- **新增**：`docs/ARCHITECTURE_REVIEW_2026-05-15.md`——完整保留两份报告原文（不做总结/精炼）。
- **关键订正**：
  - llmexcept AST 绑定为**双通道**（正则情形 `stmt.target=prev_stmt`；条件 for 情形 `prev_stmt.llmexcept_handler=stmt`），并非单一字段。
  - "侧表是 v1 的设计缺陷"这一表述不准确——序列化产物中侧表已是 `Dict[str,str]`（UID→UID），id() 仅是编译期内部细节。
  - 真正的设计债是**双写真相**：`capture_mode`（3 处副本）/ `is_callable_instance`（双处副本）。
- **PT-4.6 事实订正**：`llmexcept` 用户 `__snapshot__` / `__restore__` 协议**已实施**（`core/runtime/interpreter/llm_except_frame.py:189-197, 285-297, 299-304`；`core/runtime/objects/deep_clone.py:50-74`），不是待办；`PENDING_TASKS.md` 中相关条目已归档。
- **文档同步**：
  - `tasks_docs/NEXT_STEPS.md`：重写为"当前 P0 = H5 → 双写收敛 → v2 阻塞 bug + MetadataStore 字段收敛"的单线推进；P1 队列调整。
  - `tasks_docs/PENDING_TASKS.md`：归档 PT-4.6；修复重复编号"六、"；PT-SEM-1 / PT-SEM-2 前置条件更新；新增 PT-SEM-3（二层 IR 路线，远期）；"明确排除的方向"追加"禁止双写真相"与"禁止约束求解风格类型推断"两条。
  - `docs/architecture/02_metadata_ast.md`：追加附录 B 收口与本次报告的冲突——侧表字段清单、MetadataStore 字段定位、llmexcept 双通道、TypeEnvironment 字段、UID 生成两条潜在地雷、bind 反模式、扩充反模式警告。
  - `docs/SEMANTIC_REFACTORING_PLAN.md`：开头新增 2026-05-15 立场段，覆盖原文档与新立场冲突的措辞。

---

## 2026-05-14 锚点（第三轮）：one-shot 意图注释语义重定义与全链路收口

完成 `@` / `@!` 从"仅直连 LLM 语句"到"下一条语句执行窗口"的语义升级，确保普通函数调用路径可用且无 LLM 路径不泄漏。

- **编译期（SEM_060）**：`core/compiler/semantic/passes/semantic_analyzer.py`
  - 放宽规则：`@` / `@!` 必须跟下一条可执行语句，不再要求该语句直接包含 `@~...~`。
  - 保留防歧义约束：禁止连续两个 one-shot 注释（仍报 `SEM_060`）。
- **运行期（语句窗口生命周期）**：`core/runtime/vm/handlers.py`
  - 新增统一语句序列执行入口 `_vm_execute_stmt_sequence(...)`。
  - `IbIntentAnnotation` 不再作为"立即全局生效"语句处理，而是绑定到下一条语句窗口：窗口开始前安装、窗口结束后清理残留。
  - 该机制已接入 `IbModule` / `IbIf` / `IbWhile` / `IbFor` / `IbSwitch` / `IbTry` / `IbLLMExceptionalStmt` 的语句体执行路径。
- **运行时辅助 API**：
  - `core/runtime/interpreter/runtime_context.py` 新增 `activate_statement_one_shot_intent(...)` / `cleanup_statement_one_shot_intent(...)`。
  - `core/runtime/objects/intent_context.py` 新增 `discard_smear(...)` / `clear_override_if(...)`。
- **测试**：新增 3 套测试覆盖编译期、e2e、契约层。
- **文档同步**：`KNOWN_LIMITS.md §十九`、`IBCI_SYNTAX_REFERENCE.md §9.1`、`INTENT_SYSTEM_DESIGN.md` 全部更新。

---

## 2026-05-14 锚点（第二轮）：H1/H2/H3/H4 阶段性维修

按 `tasks_docs/NEXT_STEPS.md` 第一阶段任务清单，一次性完成四个开放问题。`pytest tests/` 基线由 639 pass / 5 fail → **653 pass / 5 fail**。

### H1 — 用户异常跨函数边界类型保留（P0）

- **根因**：`vm_handle_IbCall` 的兜底 `except Exception` 把 IBCI 层 `ThrownException` 包成 Python `RuntimeError`。
- **修复**：让 `except ThrownException` 直通在通用 `except Exception` 之前。
- **文档**：`docs/KNOWN_LIMITS.md §二十三` 关闭。

### H2 — `import` 必须居首：编译错误更可读（P1）

- **修复**：`parse_imports_only` 改为遇到非 import token 后设 `imports_allowed=False` 继续扫描，misplaced import 走 `DEP_003`。
- **文档**：`docs/KNOWN_LIMITS.md §二十四` 关闭。

### H3 — `ihost.run_isolated(path)` 路径相对入口目录而非 cwd（P1）

- **修复**：新增 `HostService._resolve_isolated_path(path)` — 相对路径以 `execution_context.get_entry_dir()` 为锚。
- **文档**：`docs/KNOWN_LIMITS.md §二十五` 关闭。

### H4 — `examples/01_getting_started/{01,02,03}` 零配置 mock fallback（P1）

- **修复**：三个示例统一改为 `if file.exists("./api_config.json")` 检测，未命中切 mock 模式。

---

## 2026-05-14 锚点：事实重核与文档诚实化

完成一次全量事实回顾与文档同步，纠正前序 PR 中的几处状态描述失实。

**事实重核结果**（基线：639 passed / 9 skipped / 5 failed）：
- 唯一真实失败：`tests/compiler/test_symbol_collection_pass.py` 共 5 个用例，`SpecRegistry()` 构造缺必填参数 `axiom_registry`。
- `tests/contracts/` 140 passed / `tests/runtime/test_plugin_implementations.py` 18 passed / `tests/meta/` 3 passed —— 前次 NEXT_STEPS.md 中的"88 contracts 失败 / 5 plugin 失败 / 25 meta 违规"描述与事实完全不符，已删除。
- Enum-from-LLM（旧 `KNOWN_LIMITS Bug #3`）实际已工作。

**本轮试用新发现的真实开放问题**（H1/H2/H3，已在上方条目中修复）。

**文档同步动作**：删除 `docs/OPEN_ISSUES.md`；重写 `tasks_docs/NEXT_STEPS.md`；新增维护守则。

---

## 2026-05-13 锚点：LLM 结果解析责任链重构

完成 LLM 结果解析逻辑的重构，采用责任链模式消除深层嵌套和多重回退逻辑。

- 创建 `llm_parsing_strategy.py` 模块（331 行），4 个策略类
- llm_executor.py: 1016 → 930 行 (-86 行, -8.5%)
- 嵌套深度从 8+ 层降到 3 层

---

## 2026-05-13 锚点：代码库健康度全面审计与局部导入清理

完成对 IBCI 代码库的全方位深度审计（229 个 Python 源文件、44,329 行代码、10 个插件模块），识别代码健康度问题并制定重构计划。同时清理了所有非必要的局部导入。

---

## 2026-05-13 锚点：测试体系契约化重构（Phase 1 + Phase 2）

测试目录从"覆盖实现细节"转向"验证语义不变量"的重构完成。

**Phase 1 成果**（2026-05-12）：建立统一基础设施、去除文件名里程碑代号、建立覆盖映射文档、15步重构全部完成。

**Phase 2 成果**（2026-05-13）：创建契约测试系统、删除白盒实现测试、建立测试哲学文档。

> **⚠ 2026-05-14 修订说明**：Phase 2 原写有"116 个 INV-XXX-N 不变量测试"，经事实核查后其中可执行的部分远少于 116。Phase 1 的目录重构基础设施部分有效，Phase 2 已在后续 PR 中逐步修复。

---

## 2026-05-12 锚点：NS-4 / NS-6 / NS-7（语言级语法/类型清理）

三项 NEXT_STEPS 一并收口：
- **NS-4**：收紧 `str + llm_uncertain` 隐式拼接 → 改为 `ThrownException(LLMParseError)`
- **NS-6**：链式下标 `(expr)[index]` 语法消歧
- **NS-7**：`tuple[T1, T2, ...]` 位置元素类型标注

---

## 2026-05-12 锚点：PT-1.2 / PT-1.3 / PT-3.3（idbg）收口

- **PT-1.2**：LLMExceptFrame 重试历史追踪（`error_history` 字段）
- **PT-1.3**：LLMExceptFrameStack 最大嵌套深度限制（默认 128）
- **PT-3.3**：idbg 改进（protection_map / show_retry_stack / show_env）

---

## 2026-05-12 锚点：NS-3 / PT-2.1 / PT-2.2 / `_evaluate_segments` CPS 化

四项配套工作按"调用现场优先 / 段求值入帧 / 意图上下文身份贯通"主线一并落地。

- **NS-3**：lambda/snapshot/behavior 跨帧 `_execution_context` 边界 — 统一使用调用现场 EC
- **PT-2.1**：intent_context OOP 高级场景 — combine/to_prompt/deep_clone
- **PT-2.2**：IbIntentContext 序列化/反序列化 — 完整 4 槽位
- **`_evaluate_segments` CPS 化**：yield-based 段求值，消除 `_drive_loop` 重入

---

## 2026-05-11 锚点：lambda / snapshot 语义最终对齐

按用户澄清的最终设计收口：
- **lambda**：自由变量经共享 `IbCell` 引用，调用时 deref 最新值；不拷贝任何内容
- **snapshot**：定义时深克隆 + 每次调用前再克隆，完全无状态可重入
- 删除 snapshot 结果缓存

---

## 2026-05-11 锚点：NS-1 LLM 调用路径合并入 CPS 调度循环

将 `IbBehavior.call()` / `IbLLMFunction.call()` 合并入 VMExecutor 的 CPS 主循环。新增 `_vm_invoke_behavior` / `_vm_invoke_llm_function` CPS 生成器助手。所有 LLM 调用触发时在帧栈上可观察。

---

## 2026-05-11 锚点：NS-2 intent 系统 OOP 化完整收口

NS-2 全四步合龙——意图注释体系语法路径（`@`/`@+`/`@-`/`@!`）与 OOP 路径（`intent_context` 实例方法）打通为同一底层 `IbIntentContext`，双轨断裂彻底消除。

- NS-2a：`intent_context` 参数自动激活
- NS-2b：帧级活跃实例指针
- NS-2c：llmexcept restore 干净替换
- NS-2d：11 项测试覆盖

---

## 2026-05-08 锚点：类型系统主线收口 + VM CPS 全链路

### 类型系统五件套（M1–M5）

| 里程碑 | 完成日 | 摘要 |
|--------|--------|------|
| **M1**　TypeRef 引入 | 2026-05-07 | 不可变 / 递归 / 工厂入口 |
| **M2**　Optional[T] 与空安全 | 2026-05-07 | `OptionalSpec` + `OptionalAxiom` + 赋值规则 |
| **M3**　TypeDef 单一化 | 2026-05-08 | 旧 `*Spec` 子类全部归并入统一 `TypeDef` |
| **M4**　运行时值模型单一化 | 2026-05-08 | `IbValue(type_ref, payload, fields, meta)` |
| **M5**　Axiom 接口统一化 | 2026-05-08 | 单一 `TypeAxiom` 取代 9 个 Capability 子协议 |

### VM CPS 全链路（M3a–M3d / M5a–M5c / M6 / Phase 1–5）

| 里程碑 | 完成日 | 摘要 |
|--------|--------|------|
| **M3a**　CPS 调度循环骨架 | 2026-04-28 | `VMExecutor` + `VMTask` + dispatch table |
| **M3b**　控制信号数据化 | 2026-04-28 | `Signal(kind, value)` 替代异常 |
| **M5a**　DDG 编译期分析 | 2026-04-28 | `BehaviorDependencyAnalyzer` |
| **M3c**　llmexcept retry CPS 化 | 2026-04-28 | `vm_handle_IbLLMExceptionalStmt` |
| **M5b**　LLMScheduler / LLMFuture | 2026-04-28 | ThreadPoolExecutor + 占位符模式 |
| **M3d / M5c**　主路径切换 | 2026-04-29 | 全部经 `VMExecutor.run_body()` |

### 命名规范化 / 语法系统重设计 / llmexcept 影子执行 / 公理化通道

- `IbDeferred` → `IbFnCallable`；`DeferredAxiom` → `FnCallableAxiom`
- D1–D6 语法系统重设计
- llmexcept 旗标轮询模式替代旧异常模式
- `IILLMExecutor` 通道 + `BehaviorAxiom` 一等公民类型

---

## 远期归档

更早期（2026-04-17 之前 + C1–C14 / L1–L4 / S1–S4 等清理）的实现细节归档于 `git log`。
