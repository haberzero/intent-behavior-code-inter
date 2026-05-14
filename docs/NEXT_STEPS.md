# NEXT_STEPS — 当前最紧要项

> 本文档**只**记录当前周期内最紧要、可立即开工的下一步。
> 阻塞 / 等前置项见 `docs/PENDING_TASKS.md`；历史归档见 `docs/COMPLETED.md`；
> 已知语言级限制见 `docs/KNOWN_LIMITS.md`。
>
> **最后更新**：2026-05-14（基于全量事实回顾 + 试用探查；前次"P0-A/B/C/D 测试基线红线"
> 描述与真实代码状态严重不符，已重写）

---

## 当前测试基线（每次开新分支前必须复跑确认）

```bash
python -m pytest tests/ -q --tb=no --no-header
```

**2026-05-14 实测结果**：`639 passed, 9 skipped, 5 failed`。
唯一真实失败：`tests/compiler/test_symbol_collection_pass.py` 共 5 个用例
（构造 `SpecRegistry()` 时未传新引入的必填参数 `axiom_registry`）。

> 这与前几版 `NEXT_STEPS.md` 中"88 contracts 用例 / 5 plugin 用例 / 25 meta 违规 / example 04 第 1 段崩溃"
> 等"P0-A..D"红线**完全不符**。复跑 `tests/contracts/`、`tests/runtime/test_plugin_implementations.py`、
> `tests/meta/` 全部绿（140/18/3 pass）；`examples/01_getting_started/04_mock_and_llmexcept.ibci`
> 完整执行 7 段。前述 P0 清单为旧文档残留，已统一删除。

---

## ⚠️ 优先级 P0：异常跨函数边界类型降级（H1，新发现）

**严重级别**：高。这是唯一一处真正破坏语言机制承诺的 bug。

### 现象（最小复现）

```ibci
class MyError(Exception):
    func __init__(self, str msg):
        self.message = msg

func boom():
    raise MyError("kaboom")

try:
    boom()
except MyError as e:
    print("caught MyError:", e.message)   # ❌ 不会进入此分支
except Exception as e:
    print("caught Exception:", e.message) # ✅ 进入这里，但 e.message 是 wrapper 文本
```

实测 `e.message` 输出 `VM: Call failed: <MyError object at 0x...>`，**原始 IBCI 异常对象被吞**。

顶层 raise（不经过函数调用边界）行为正常；`tests/e2e/test_e2e_exceptions.py` 当前 8 个 raise 用例**全部在顶层 try 内**，未覆盖跨调用栈的情况。

### 根因

`core/runtime/vm/handlers.py:508-514`：

```python
try:
    if hasattr(func, "call"):
        return func.call(executor.registry.get_none(), args)
    return func.receive("__call__", args)
except Exception as e:
    # 与 ExprHandler.visit_IbCall 同语义：对外汇报为通用调用错误
    raise RuntimeError(f"VM: Call failed: {e}") from e
```

这个兜底 `except Exception` 把 IBCI 层的 `ThrownException`（语言级异常包装器）一并捕获并 wrap 成 Python `RuntimeError`，导致：
1. 异常的 IBCI 具体类型（`MyError`/`LLMRetryExhaustedError` 等）丢失，`except <SpecificType>` 无法匹配；
2. 用户字段（`e.message`、`e.detail` 等）被替换为 wrapper 字符串。

### 修复方向

1. 在 `vm_handle_IbCall` 的 try/except 中显式让 `ThrownException` 直通（与 `IbNativeFunction.call` 已采用的同款 pattern 一致，详见 `docs/COMPLETED.md` 2026-05-12 NS-4 锚点）。
2. 仅在确实是 Python 侧错误（`AttributeError`/`TypeError`/`KeyError` from native 等）时再 wrap 成 `RuntimeError`。

### 验收

新增契约用例（建议位置 `tests/e2e/test_e2e_exceptions.py`，独立 `class TestExceptionAcrossFunctionBoundary`）：

- 用户子类 raise 在函数 A 内、捕获在 caller B 中 → 类型保留、字段保留。
- `LLMRetryExhaustedError`（来自函数内 `llmexcept` 耗尽）跨函数边界 → `except LLMRetryExhaustedError as e:` 应能匹配。
- 嵌套两层 + finally 中再 raise → 类型链与抑制语义符合 Python 直觉。

### 预估工作量

- 修复改动：~10 行（限于 handlers.py）。
- 测试新增：~40 行。
- 回归：跑 `tests/e2e/test_e2e_exceptions.py` + 全量 `tests/` 一轮。
- 总：1.5–2 小时。

---

## ⚠️ 优先级 P0：semantic_v2 SymbolCollectionPass 测试 fixture 失效（H5，真实 P0）

**严重级别**：中。Phase 3 测试验证流程的实际阻塞点。

### 现象

```
FAILED tests/compiler/test_symbol_collection_pass.py::test_symbol_collection_pass_empty_module
FAILED tests/compiler/test_symbol_collection_pass.py::test_symbol_collection_pass_function_def
FAILED tests/compiler/test_symbol_collection_pass.py::test_symbol_collection_pass_class_def
FAILED tests/compiler/test_symbol_collection_pass.py::test_symbol_collection_pass_variable_assign
FAILED tests/compiler/test_symbol_collection_pass.py::test_symbol_collection_pass_duplicate_definition
TypeError: SpecRegistry.__init__() missing 1 required positional argument: 'axiom_registry'
```

### 根因

`core/kernel/spec/registry.py` 的 `SpecRegistry.__init__(self, axiom_registry)` 在某次（已合入 main 的）改动中把 `axiom_registry` 从可选变为必填位置参数；但 `tests/compiler/test_symbol_collection_pass.py:16` 的 `create_test_context()` 仍按旧签名 `SpecRegistry()` 调用。

### 修复方向

- 选项 A（推荐）：在测试 fixture 中显式构造 `AxiomRegistry()` 实例传入，与生产路径一致。
- 选项 B：把 `axiom_registry` 改回可选并在缺省时构造空 registry。可能掩盖真实问题，**不推荐**。

### 验收

`tests/compiler/test_symbol_collection_pass.py` 5 个用例全绿；`pytest tests/ -q` 整体回到 644 pass / 0 fail。

### 预估工作量

10 分钟。

---

## P1 候选（按优先级排队，单线推进）

### P1-A `ihost.run_isolated(path, policy)` 路径解析与入口文件目录对齐（H3）

**现状**：`core/runtime/host/service.py:182,196` 用 `os.path.abspath(path)` —— 等价相对 cwd 解析。
与 `file.read("./api_config.json")`（基于 `isys.entry_dir()`）的语义不一致。README §5 与 `examples/03_advanced_features/isolation_demo/parent.ibci` 写的相对路径只在用户碰巧 cd 到正确目录时才能跑通。

**动作**：
- `run_isolated` / `spawn_isolated` 在 `path` 非绝对时，先以**调用方脚本的入口目录**（`HostService` 可由 `execution_context.runtime_context` 取得当前执行的入口文件路径）解析；保留绝对路径直通。
- 文档：`README.md §5`、`docs/IBCI_SYNTAX_REFERENCE.md §10.x`（如已涉及）以"相对调用脚本目录解析"统一表述。
- 测试：`tests/e2e/test_e2e_dynamic_host.py` 增"相对路径 + cwd 不同于入口目录"的用例。

**预估**：1 小时。

---

### P1-B `import` 必须居首：编译错误更可读（H2）

**现状**：

```ibci
str x = "hello"
print(x)
import idbg   # ← 报错：[ERROR] SEM_001: Module 'idbg' not found or failed to load
```

错误描述把"位置错误"误诊为"模块不存在"，会让用户去查模块安装/插件路径，浪费排查时间。

**动作**：
- `core/compiler/scheduler.py` 在解析后、`SymbolCollection` 之前增加一次扫描：若 `import` 语句的 AST 位置不在所有非 import / 非 comment 顶层语句之前，发出新错误码 `IMP_001 IMPORT_MUST_BE_AT_TOP`（建议放在 `core/base/codes.py`），明确指出"`import` 必须位于所有可执行语句之前"。
- 不阻塞 `SEM_001`：先报 `IMP_001`，再走原有解析；用户修正后才会看到模块自身的问题（如真不存在）。
- 测试：`tests/compiler/test_import_position.py` 覆盖正确顺序、错位、混合 comment、模块块内 import 等情况。

**预估**：1.5 小时。

---

### P1-C `examples/01_getting_started/{01,02,03}` 零配置 mock fallback（H4）

**现状**：三个入门示例都通过 `file.read("./api_config.json")` 读取真实配置；缺该文件时 Python `FileNotFoundError` 抛出，用户首次试用即遇断点。

**动作**：
- 改写 01/02/03 的开头：
  - 先尝试 `file.exists("./api_config.json")` 之类的检查；
  - 命中 → 走真实 API；
  - 未命中 → `ai.set_config("TESTONLY","TESTONLY","TESTONLY")` 并 `print` 一句"未检测到 api_config.json，已切换到 mock 模式"。
- 与 `04_mock_and_llmexcept.ibci`、`05_enum_and_switch.ibci`、`06_enum_switch_with_llm.ibci` 行为对齐。
- 不修改 03_advanced_features 下的真实 LLM 示例（保持其"需要真实 key"的属性）。

**预估**：1 小时。

---

### P1-D Enum-from-LLM 文档与 example 05 收口（已修，但文档/示例仍在教过时方案）

**现状**：`docs/KNOWN_LIMITS.md` 旧版本及 `examples/01_getting_started/05_enum_and_switch.ibci` 均提及
"Bug #3：Enum 类型变量无法直接接收 LLM 输出（得到 None），必须先以 str 接收再手动映射"。

本次试用实测：

```ibci
class Color(Enum):
    str RED = "RED"
    str GREEN = "GREEN"
    str BLUE = "BLUE"

Color c = @~ MOCK:STR:BLUE ~
print("c == Color.BLUE:", c == Color.BLUE)  # → True ✅
```

`EnumAxiom`（`core/kernel/axioms/primitives.py:1071-1164`）已实现完整的 `has_from_prompt_cap` / `has_output_hint_cap` / `has_converter_cap`，Bug #3 实际**已修复但未关闭**。

**动作**：
- 修改 `examples/01_getting_started/05_enum_and_switch.ibci`：删除"规避方案"段落，直接展示"以 Enum 类型变量接收 LLM 输出"的成功用法。
- `docs/KNOWN_LIMITS.md §四`：移除"Bug #3"相关旧表述（如有遗留），保留"仅 str 成员 / 不支持 for 迭代 / 不支持 len/序数查询"三条真限制。
- `docs/COMPLETED.md`：添加 2026-05-14 锚点（"Enum-from-LLM 路径回归核验"）。

**预估**：0.5 小时。

---

### P1-E README.md 示例代码块大小写订正（H6）

**现状**：`README.md:103-105` dict 字面量用了小写 `true`/`false`：

```ibci
dict policy = {
    "isolated": true,
    "registry_isolation": true,
    "inherit_variables": false
}
```

直接复制无法编译（`SEM_001: Variable 'true' is not defined` × 3）。

**动作**：已在 2026-05-14 本次 PR 内修正为 `True` / `False`。后续保持 `docs/IBCI_SYNTAX_REFERENCE.md §10.x` 的 ihost 示例与其同步即可。

**预估**：完成。

---

## P2 候选（背景项；与 P0/P1 不抢资源）

### P2-A semantic_v2 测试验证 (Phase 3)

semantic_v2 的 6 个 Pass 代码实现已完成（共 ~1929 行），架构已优化并文档化（详见 `docs/SEMANTIC_REFACTORING_PLAN.md` 与 `docs/METADATA_ARCHITECTURE.md`）。在 P0（H5）修复后，可正式进入 Phase 3：

**Task 1**：创建 `tests/compiler/semantic_v2/` 单元测试 + 集成测试（每个 Pass 独立 + 完整管道）。**目标**：20 单测 + 10 集成测试。  
**Task 2**：实现 `tools/validate_semantic_v2.py` 自动化对比工具，对比维度=符号表 / 类型绑定 / 错误信息 / 元数据。  
**Task 3**：用现有 V1 测试套件做回归比对，记录差异。  
**成功指标（2 周）**：30+ 测试通过，V1/V2 对比工具可运行。

### P2-B `intent_context.push()` 静默无效陷阱编译期警告（沿用旧 P1-B）

`intent_context.push("X")` 在没有 `use(ctx)` 时是 no-op（详见 `docs/KNOWN_LIMITS.md §十八`），但编译期不告警；用户极易踩坑。

**动作**：在 `semantic_analyzer` 中对 `IbCall(method='push'|'pop'|'merge'|'combine'|'clear')` 且 receiver 为类静态调用（非局部 `intent_context` 变量）的形态发出 SEM 警告。低风险，单点改动。

### P2-C NS-5 编译期类型转换检查（激活 `can_convert_from`）

技术路径已在前版 `NEXT_STEPS.md` NS-5 详细记录；保留为优先级 P3 背景项。实施前需：先评估对 `tests/` 套件的破坏面，再决定是否动手。

### P2-D `idbg.last_llm()` 与 `MOCK:SEQ` 时序一致性核查（H7，待复现）

`examples/01_getting_started/06_enum_switch_with_llm.ibci` 输出显示 `MOCK 情感 = SAD` 但 `idbg last_llm.response = HAPPY`，存在游标推进一拍偏差。  
**动作**：先用最小用例复现 `MOCK:SEQ` 与 `idbg.last_llm()` 的取值顺序；判断是 demo 写法问题还是 idbg 语义不清。如属后者，在 `docs/IBCI_SYNTAX_REFERENCE.md` 的 `idbg` 章节锁定语义。  
**预估**：复现 1 小时；定性后再决定修复或文档化。

### P2-E 已知设计取向项（参考性低优先）

- 嵌套 llmexcept 内 retry 计数器的"每次外层 retry 是否重置"语义在 `docs/INTENT_SYSTEM_DESIGN.md` / `docs/ARCH_DETAILS.md` 中明文锁定。  
- `@-` 在按内容/标签移除不存在意图时的 no-op 行为在 `docs/INTENT_SYSTEM_DESIGN.md §4.4` 明文锁定。  
- `__to_prompt__` 在容器嵌套（list/dict 内含用户对象）插值时的递归展开规则在 `docs/IBCI_SYNTAX_REFERENCE.md §6 / §10` 写出契约。

---

## 当前主线完成情况（保持）

类型系统 M1–M5、VM CPS 主线、intent 系统 OOP 化（NS-2 全部 4 步）、LLM 调用路径合并入 CPS 调度循环（NS-1）、lambda/snapshot/behavior 跨帧 EC 边界（NS-3）、intent_context 高级 OOP 场景（PT-2.1）、IbIntentContext 序列化/反序列化（PT-2.2）、`_evaluate_segments` CPS 化、PT-1.2（llmexcept 错误历史）、PT-1.3（llmexcept 嵌套深度限制）、PT-3.3（`idbg.protection_map()`）、NS-4（`str + llm_uncertain` 收紧）、NS-6（链式下标）、NS-7（tuple 位置类型标注）均已完成。

**当前主线（VM / Intent / llmexcept / 类型系统骨架）的内核能力没有新的 P0 开放项**。本周期的真实 P0 集中在：

1. 异常跨函数边界类型保留（H1）
2. semantic_v2 测试 fixture 修复（H5）

---

## 工作规则

- **每次开新分支前**，先复跑 `python -m pytest tests/ -q --tb=no --no-header`，把当前 pass/fail 计数写在 PR 描述里，不预设上一份文档里的数字。
- 同一时刻只主推一项 P0 任务（或一项 P1）；其余项保留待选。
- 任何改动公理层公约或语义错误集的任务，需在分支早期跑全量 pytest 评估破坏面。
- 每项完成后，把摘要追加到 `docs/COMPLETED.md`（极简时间线），并把对应条目从本文件移除。
- 出现新的紧要项时，按"先评估优先级、再决定是否替换 P0"原则操作。
- **本文件不冻结具体测试通过数字**——任何"X 测试通过"的表述都必须附运行命令或日期锚点，避免下一个智能体把陈旧数字当作真实状态。

---

## 维护守则（写给后续智能体与人类维护者）

下述守则源于 2026-05-14 全量事实回顾过程中暴露出的几次"文档幻觉"教训：

1. **先复跑、后下结论**。任何关于"测试基线红线 / P0 未通过 / 88 用例失败"的表述，必须以"附完整 pytest 输出 + 日期 + 分支"的方式说服读者；否则视为待核查。
2. **不要相信"昨日完成"的总结**。`docs/COMPLETED.md` 的最新一两条锚点，必须能用一条具体 git 提交或一次具体 pytest 输出佐证。本轮发现 2026-05-13 "Phase 2 完成 + 测试基线 Full pass" / "88 contracts 失败 + 5 plugin 失败 + 25 meta 违规" 两份**互相矛盾**的描述同时存在，皆与代码事实不符。
3. **示例必须可零配置跑通**。任何"用户跟着 README 复制粘贴"的代码块，必须在 mock 模式下端到端跑通；改动后必须 `python main.py run <示例>` 至少一次。
4. **已知 bug 与已修 bug 之间要勤更**。每发现一个"文档说有但代码已修"的项目（如 Enum Bug #3），立刻把文档同步更新；反向（代码有 bug 但文档没记）同理。
5. **跨文件状态保持一致**。`README.md`、`docs/KNOWN_LIMITS.md`、`docs/IBCI_SYNTAX_REFERENCE.md` 三处对同一语法/限制的描述必须用同一组事实；如不一致，以代码与最近一次 pytest 输出为准。
6. **避免重复声明、单点真理**。一条已完成项写一次（在 `COMPLETED.md`），一条已知限制写一次（在 `KNOWN_LIMITS.md`），一条紧要项写一次（在 `NEXT_STEPS.md`）。出现"同一条目在多个文件中以不同状态出现"，立即合并。
