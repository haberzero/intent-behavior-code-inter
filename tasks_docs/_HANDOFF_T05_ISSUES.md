# 交接：T05 批判性压力试用问题处置（下一 session 主任务）

> 2026-08-14 编制。承接 `trials/T05_critical_stress/`（40 用例 37 PASS + 1 GUARD +
> 2 KERNEL_ISSUE + 文档核验 23 DOC_ISSUE）。
> **用户 2026-08-14 指示：下一 session 处理并分析所有压力测试问题 + 所有文档过期
> 问题；以代码问题为优先。**
> 基线：unsafe-vibe-dev 6e68329c（全量 2614 passed / 1 skipped）。
> 本文件交接每项的现状 / 证据 / 粗略根因 / 修复方向 / 建议判别性回归。

---

## 一、处理总览（以代码问题为优先）

| 优先级 | 项 | 性质 | 级别 | 建议窗口 |
|--------|----|------|------|----------|
| **P0** | KI-1 线程 worker 内跨模块用户类不可用 | 代码缺陷 | P1 | 独立窗口（根因已定位） |
| **P1** | KI-2 Optional-None `is None` 语义 + `is_none()` 缺失 | 代码缺陷 | P2 | 独立窗口（与 DOC-5/-6 同修） |
| **P1** | mock STR/BOOL 值语义（实现 vs 文档抉择） | 代码/文档 | P1 | 独立窗口 |
| **P2** | 8 个幽灵诊断码 + 快照篡改警告未发射 | 代码缺陷 | P2 | 独立窗口（诊断码发射纪律） |
| **P2** | `set_mock_mode()` 单向无 off API | 代码缺口 | P3 | 独立窗口 |
| **P3** | DOC_ISSUE-1~23 文档批次（含 KNOWN_LIMITS 三条不成立） | 文档 | P1-P3 | doc-governance 批次 |

---

## 二、代码问题（优先处置）

### 2.1 KI-1｜KERNEL_ISSUE-CROSSMOD-THREAD-1（P1）——线程 worker 内被 import 模块的用户类不可用

**现状/现象**
- 主上下文 `geo.Box(5).get()` = 405；线程 worker 内同调用抛 `ThrownException(ThreadFailed)`
  （底层 `VM Execution Error: Symbol UID missing for name 'v'. Artifact is corrupted or unanalyzed`）。
- 入口模块类（entry-main）在 worker 内正常（main2 = 405）。
- **base（main 分支 eb4a7d10）同现**——既有缺陷，非跨模块 module 化引入。

**复现用例**
- `tasks_docs/trials/T05_critical_stress/cases/D1-10/main.ibci`（thread + `geo.Box(5).get()`）
- 最小探针：`/tmp/opencode/threadtest/main9.ibci`（主上下文 405 / 线程 -1）

**粗略根因（代码实证）**
1. 线程任务本地 EC：`coordinator.py:213` `get_side_table_callback=interpreter.get_side_table`。
2. `interpreter.get_side_table`（interpreter.py:350-368）读 `self.current_module_name`
   （**interpreter 共享值**）→ 查 `artifact.modules[module_name].side_tables`。
3. `_vm_call_user_function`（_shared.py:260-274）执行方法体前把 **task_ec 任务本地**
   `current_module_name` 切到 `func.module_name`（"geo"）；但侧表回调读的是
   **interpreter 的** current_module_name（未同步，仍是 main）→ imported 方法体
   `node_to_symbol` 查错模块 → 查空。
4. 入口类方法体因 main==entry 模块恰好命中 → 幸存。

**修复方向**
- 侧表查询须以**调用方 EC 的 current_module_name** 为准：回调改为使用 task_ec 自身
  模块（如 `interpreter.get_side_table` 增加 module 参数，或回调绑定 task_ec 的
  current_module_name），对齐 coordinator.py:177-178 注释"任务本地 current_module"设计意图。
- 排查同类"任务本地状态 vs 共享回调"裂缝（node_to_symbol / node_to_loc / node_to_type
  等全部侧表 + resolve_type_from_symbol 等回调是否同病）。

**建议判别性回归**
- `geo.Box[int](5).get()` 在线程内 = 105（int 语义）、`graph.Box[str]("hi").get()` 在线程内
  = "hi!"；主/线程结果一致。
- 入口类线程内行为不回归。

### 2.2 KI-2｜KERNEL_ISSUE-OPTIONAL-ISNONE-1（P2）——`Optional[T] a = None; a is None` 返回 False + `is_none()` 缺失

**现状/现象**
- `Optional[int] a = None; a is None` → **False**；`a == None` → True；
  `any b = None; b is None` → True；`a.is_none()` 方法不存在（`Object of type 'None'
  has no method '__call__'`）。
- 文档 03_operators.md:70 声称 `x is None  # x 是否为 None`。

**复现用例**
- `tasks_docs/trials/T05_critical_stress/cases/D2-03.ibci`；`/tmp/opencode/optest.ibci`

**粗略根因（代码实证）**
1. `is` 的 None 分支用 `isinstance(left, IbNone)`（leaf.py:269-277）——Optional 空值被
   `IbOptional(is_some=False)` 包装（非 IbNone）→ False。
2. `IbOptional` docstring（optional.py:14-19）自述"空（payload 为 None，**语义上是
   None**）"——与 `is None` False 结果自相矛盾。
3. `OptionalAxiom` 声明 `is_none`（arch/03_type_system §8），`IbOptional` 未实现。

**修复方向**
- 方案 A（语义一致）：`is` 的 None 分支对 `IbOptional` 且 `is_some==False` 返回 True
  （与 `== None` 一致）。需核对 `is not None` 对称分支。
- 方案 B（API 补全）：实现 `is_none()`（OptionalAxiom 声明已有），文档统一判空 API。
- 建议 A+B 结合：`is None` 语义对齐 + 补 `is_none()` + DOC-5/-6 文档同步。

**建议判别性回归**
- `Optional[int] a = None; a is None` → True；`a.is_none()` → True；
  `Optional[int] b = 5; b is None` → False；`any c = None; c is None` → True（不回归）。

### 2.3 mock STR/BOOL 值语义（实现 vs 文档抉择，P1）

**现状/现象**
- `MOCK:STR:hello world` → `"hello"`（`mock_scenario.py` `_resolve_locked` 对 STR 用
  `mock_value.split()[0]`）；`MOCK:BOOL:1`/`MOCK:BOOL:True` → False（仅 `"TRUE"` 大写
  判真）。
- 文档（13_mock_testing §13.2.1/§13.3.1、guide/07:40-49、07_behavior_expressions §7.5）
  声称多词 STR 完整返回、`BOOL:1` 判真。

**处置方向（须决断，倾向代码为准修文档或修实现）**
- 若 `MOCK:STR:hello world`（无引号）取首 token 是有意设计 → 修文档示例为
  `MOCK:STR:"hello world"`（带引号才完整）。
- 若应支持多词 → 修 `mock_scenario` 解析（strip 后整体作为值）。
- BOOL 建议统一大小写不敏感判定（`bool_val.upper() == "TRUE"`）或文档只示范 `TRUE`。
- **判别性回归**：`MOCK:STR:hello world`（决定后语义）+ `MOCK:BOOL:TRUE`/`MOCK:BOOL:1`。

### 2.4 幽灵诊断码 + 快照篡改警告未发射（P2）

**现状/现象**
- 15_diagnostics.md 声称可触发，但 core/+ibci_modules/ 全仓零引用（从未发射）：
  `RUN_DIVISION_BY_ZERO`、`RUN_ATTRIBUTE_ERROR`、`RUN_INDEX_ERROR`、
  `RUN_PERMISSION_ERROR`、`RUN_LLMEXCEPT_SNAPSHOT_VIOLATION`、`LEX_INVALID_NUMBER`、
  `PAR_INDENTATION_ERROR`、`PAR_MULTIPLE_INTENTS`。
- 实测越界/除零/属性缺失报裸 `[ERROR][RUNTIME_ERROR]`（issue.py:65 默认码，本身也是
  未注册字符串）。
- 快照篡改（10_robustness:85、arch/04:327、arch/05:177 声称发警告）实为静默恢复
  （_shared.py:668-672 restore_snapshot 无警告）。
- `indent_processor.py:60` 误用 `LEX_INVALID_ESCAPE` 上报缩进失配。

**处置方向**
- 逐码决断：实现发射（越界→RUN_INDEX_ERROR、除零→RUN_DIVISION_BY_ZERO、
  属性缺失→RUN_ATTRIBUTE_ERROR）或从文档删除/标注未实现。
- `issue.py` 默认 RUNTIME_ERROR 登记入 catalog（或换已注册码）。
- 快照篡改：按文档语义补警告发射（或改文档为静默恢复）。
- `indent_processor` 错误码修正。
- **建议**：新增契约测试——catalog 码须有真实发射点（杜绝幽灵码；CAT-6 目前只校验
  码集合一致性不校验可发射性）。

### 2.5 `set_mock_mode()` 单向无 off API（P3，代码缺口）

**现状/现象**
- `set_mock_mode()` 仅进入 mock（core.py:175-185 置 `_config["mock"]=True`），无 off API。
  退出只能 `ai.set_config(...)`（内部 mock=False）或 `ai.apply_config`。
- 文档（11_modules、guide/01）未说明单向性（DOC-23）。

**处置方向**
- 补 `set_mock_mode(False)` 或 `set_mock_mode(enable: bool = True)`（对称开关）；
  或维持单向并文档明示。倾向补对称开关（易用性）。
- **判别性回归**：mock→真实→mock 往返切换。

---

## 三、文档过期问题（DOC_ISSUE-1~23 全清单）

> 处置方式建议走 doc-governance Phase 0-8（先审计→规划→交叉核验→实施→读者视角）。
> 每条：位置 | 文档声称 | 实际 | 建议。P1 优先。

### P1（4 条）——示例不能运行 / 结果与文档不符

| # | 位置 | 内容 |
|---|------|------|
| DOC-1 | 13_mock_testing §13.2.1/§13.3.1、guide/07:40-41、07_behavior §7.5 | `MOCK:STR:hello world` 只返回 `hello`（实现 `split()[0]`）；建议示例改带引号或修实现（见 2.3） |
| DOC-2 | guide/07:49-50、13_mock §13.2.1 | `MOCK:BOOL:1`/`MOCK:BOOL:True` 判真与实现相反（仅大写 `TRUE`）；统一为 `MOCK:BOOL:TRUE/FALSE`（见 2.3） |
| DOC-3 | guide/06_multistep:121-128 | lambda 多行语句体示例解析失败（lambda 仅单表达式）；改写为单表达式 + `@+` 前置意图 |
| DOC-4 | 01_types:77-85 | cast_to 覆盖示例不能编译（参数缺注解 + `target == str` 类对象比较崩）；参数补 `any` + 比较用 `type(target) == "str"` 并实测通过 |

### P2（11 条）——语义误导 / 文档矛盾 / 与实现脱节

| # | 位置 | 内容 |
|---|------|------|
| DOC-5 | 03_operators:70 | `x is None` 对 Optional 误导（关联 KI-2）；补"Optional 判空用 `== None`/`is_none()`" |
| DOC-6 | arch/03_type_system:434 | `Optional.is_none()` 文档有、实现缺失（关联 KI-2）；实现后保留或从 §8 删除 |
| DOC-7 | KNOWN_LIMITS §十三 | 连续/悬空 one-shot 报 SEM_INTENT_PLACEMENT 不成立；改为"后者覆写前者/悬空丢弃，编译期不拦" |
| DOC-8 | 09_intent_system §9.3 | 示例缺 `use(ctx)` 静默无效；补 `intent_context.use(ctx)`（与 §十二一致） |
| DOC-9 | KNOWN_LIMITS §八 | `auto x = mixed[0]` 编译失败不成立；改为"锁定具体元素类型，建议 `any` 中转" |
| DOC-10 | 06_oop §6.5 | 无父类时 `super()` 指向 Object 不成立；限定"仅显式父类可用" |
| DOC-11 | 15_diagnostics:399-468 | 8 个幽灵诊断码；删除/标注未实现 或 实现发射（见 2.4） |
| DOC-12 | 10_robustness:85、arch/04:327、arch/05:177 | 快照篡改警告未发射；改"静默恢复"或补发射（见 2.4） |
| DOC-13 | 14_concurrency §14.1 | "共享只读类型定义"与 KI-1 矛盾；补限制"worker 内不可用被 import 模块类"（修 KI-1 后撤除） |
| DOC-14 | KNOWN_LIMITS §七 | any→用户类恒 RUN_TYPE_MISMATCH 不成立；改为"仅 any 类装箱标记拦截，普通 any 值不校验" |
| DOC-15 | howto/use_generators | for 惰性/break 提前终止与 §5.8 急物化矛盾；统一为"for=一次性物化，逐值用 next()" |

### P3（8 条）——口径/术语/缺口

| # | 位置 | 内容 |
|---|------|------|
| DOC-16 | 02_variables:21 | `auto nums=[1,2]` 注释应 `list[int]` |
| DOC-17 | 12_builtins:69 | `find_last("l")` 索引 9 应 11 |
| DOC-18 | 15_diagnostics:145 | SEM_IMPORT_CONFLICT 级别 ERROR 应 WARNING |
| DOC-19 | 15_diagnostics:265 | SEM_INTENT_STATIC_CALL 级别 ERROR 应 WARNING |
| DOC-20 | 15_diagnostics:29 | "编译期诊断均 ERROR"笼统（有 WARNING 例外）；加"除标注 WARNING 者外" |
| DOC-21 | 13_mock/guide/07/KNOWN_LIMITS:419 | "TESTONLY 模式"遗留术语；统一为"MOCK 模式" |
| DOC-22 | 05_functions:216 | `behavior[(auto)->str]` 应为 `behavior[()->str]` |
| DOC-23 | 11_modules:83、guide/01:116-121 | `set_mock_mode()` 单向性未说明（见 2.5） |

**交叉核对**：无重复登记；KNOWN_LIMITS 自身 3 条（§七/§八/§十三）不成立须实证修正。

---

## 四、建议处理顺序（代码优先）

1. **KI-1**（P1）：线程 worker 侧表 module 上下文修复 + 判别性回归 + 并发裂缝排查。
2. **KI-2 + DOC-5/-6**（P2）：Optional 判空语义统一 + `is_none()` + 文档同步。
3. **mock STR/BOOL**（P1）：实现/文档抉择 + 判别性回归。
4. **幽灵诊断码**（P2）：发射实现或文档删减 + 可发射性契约测试。
5. **`set_mock_mode` 对称开关**（P3）。
6. **DOC 批次**（P1-P3，doc-governance）：P1 示例 → P2 语义/矛盾 → P3 口径/术语。

## 五、纪律与验证

- 每项：根因修复 + `tests/` 判别性回归（缺陷=根因修复+回归双交付）+ 全量 pytest 零回归
  （`~/miniconda3/envs/ibci/bin/python -m pytest tests/`）。
- 代码改动走 code-workflow Phase 0-5 + 独立复核（general agent）；文档走 doc-governance。
- 分支政策：无法确认边界走独立分支；确认零风险可直接合并 unsafe-vibe-dev；不触碰 main。
- 全程本地 commit、禁 push。
- WORKLOG 详尽记录决策与变化前后。
