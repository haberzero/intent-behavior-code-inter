# _HANDOFF_ISSUES_LLM_E2E — LLM e2e session 不合格操作 + 待查问题清单

> 本文件是 2026-08-11 真实 LLM e2e session 的**自我审查交接清单**，供下一个智能体逐个查询与处理。
> 前一个智能体在追求进度时使用了用户禁止的绕过/兼容层/快速 tricky 操作，全部如实记录如下，
> 不掩饰、不粉饰。下一个智能体应按"工作模式定论"逐个根因修复。

---

## A. 不合格操作清单（需重新正确修复）

> ✅ 核销记录见各条目末行（下一个智能体按"工作模式定论"根因修复后回填）。

### U1: generator.to_list() / generic_next() 用 receive 重写特判（commit 8676554，高严重度）

**✅ 已核销（2026-08-11，本 session 修复）**：按下方"正确做法"落地——新建
`GeneratorAxiom`（`core/kernel/axioms/primitives/generator.py`，to_list/generic_next 方法规格）+
`GENERATOR_SPEC` 注册（specs.py/_runtime.py）+ `@register_ib_type("generator")` 于 IbGenerator +
kernel/__init__.py 导入触发装饰器 + **删 IbGenerator.receive 特判** + leaf.py 两处改
`get_class("generator")` 优先。契约测试 `tests/contracts/test_generator_ibclass.py`（GEN-1~4）。
全量 2176 passed / 1 skipped 零回归。

**违反原则**：禁止过程式硬编码分发（工作模式定论第 4 条）+ 质量优先于速度（第 5 条）
**症状**：选择"最小侵入"重写 receive 而非正确架构（注册专门 generator IbClass）
**位置**：`core/runtime/objects/kernel/generator.py` `IbGenerator.receive` 重写

**当前（不合格）实现**：
```python
def receive(self, message, args):
    if message == "__getattr__" and args:
        attr_name = args[0].to_native()
        if attr_name in self._ITER_METHODS:
            method = IbNativeFunction(getattr(self, attr_name), ...)
            return IbBoundMethod(self, method)
    if message in self._ITER_METHODS:
        return getattr(self, message)()
    return super().receive(message, args)
```

**根因**：IbGenerator 用 `executor.registry.get_class("callable") or func.ib_class`（leaf.py:372/391），
"callable" 类没有 to_list/generic_next 注册。`for` 循环内部经 `_resolve_iterable` 绕过 vtable 直接调 Python 方法，故 `for` 可用；用户显式 `.to_list()` 经 `__getattr__` 查 vtable 失败 → 返回 None → `None()` 报错。

**正确做法（推荐）**：
1. 在 `core/runtime/bootstrap/primitive_initializer.py` 注册专门 "generator" IbClass（含 to_list/generic_next 经 _reg_native 注册到 vtable）。
   注：当前 generator 无公理（axiom），需在 ib_classes 创建逻辑里加一个（或经 registry.create_subclass 手动建）。
2. `leaf.py:372/391` 改 `gen_class = executor.registry.get_class("generator") or executor.registry.get_class("callable") or func.ib_class`。
3. IbGenerator.receive 重写**删除**（回归基类协议驱动）。
4. e2e 测试 tests/e2e/test_generator_to_list.py 保留（验证用户显式 .to_list() 可达）。

**为什么这是不合格**：选了"小而快"的 receive 特判，而非"正确架构"的 generator IbClass 注册。
正是用户禁止的"快速 tricky 实现"和"过程式硬编码分发"。

**涉及文件**：generator.py、leaf.py、primitive_initializer.py、test_generator_to_list.py

---

### U2: `int sum = @~...~` 遮蔽 + LLM 表达式缺陷绕过（commit 3c768a4，高严重度）

**✅ 已核销（2026-08-11，本 session 修复）**：根因比交接推断更精确——编译器对模块级
`int X = ...` 统一绑定既有 intrinsic 符号 UID（字面量/LLM 同 `intrinsic:X`），遮蔽语义由
运行时 define 承担；缺陷在 dispatch-before-use 路径 `_assign_future_to_name_target`
（`_shared.py:743`）——符号已存在时原地覆写 `.value` 而非走 define，intrinsic 常量符号被
写入 LLMFuture、使用点回写触发 `Cannot reassign constant`。修复：加 `define_only` 参数
（与 `_vm_assign_to_target` 同构），IbTypeAnnotatedExpr 递归置 True，定义路径恒走
`define_raw`。+2 回归测试（test_builtin_expansion.py）；示例 01_hello_world.ibci 改回
`int sum` 真实跑通。全量 2178 passed / 1 skipped 零回归。

**违反原则**：根因优先于症状 + 禁止半修复
**症状**：改示例变量名 `int sum`→`int result` 绕开，未修根因
**位置**：`examples/01_getting_started/01_hello_world.ibci:41,43`

**关键发现**：
- `int sum = 5`（普通字面量）→ 遮蔽成功（`sum: 5` 输出正常）
- `int sum = @~ MOCK:INT:42 ~`（LLM 表达式）→ `Cannot reassign constant UID 'intrinsic:sum'`

**根因推断**：对于 LLM 表达式 RHS，编译器可能拆为两阶段：
1. IbVarDecl（声明 + 遮蔽 intrinsic:sum → 新符号）
2. IbAssign（LLM 表达式求值 + 赋值，但用编译期符号 UID = 旧 `intrinsic:sum`，而非遮蔽后的新符号 UID）

遮蔽机制只在 define 路径清除旧 intrinsic uid 绑定，但 LLM 表达式赋值可能走 assign 路径用旧 UID → 触发 `Cannot reassign constant`。

**正确做法**：
1. 定位编译器中 `int <name> = @~...~`（带类型注解 + LLM 表达式初始化）的节点处理路径。
2. 确认是否拆为 VarDecl + Assign 两节点，Assign 用的符号 UID 是声明后的新 UID 还是编译期缓存的旧 UID。
3. 修复：Assign 节点应用 VarDecl 产生的新符号 UID（而非旧 intrinsic UID）。
4. e2e 测试：`int sum = @~ MOCK:INT:42 ~` 遮蔽内建后正确赋值（+1 测试）。
5. 示例 01_hello_world.ibci 改回 `int sum`（验证遮蔽机制修复后内建名仍可用）。

**为什么这是不合格**：改示例绕开是症状层处理，违反"根因优先"和"禁止半修复"。
这是用户最明确禁止的操作之一（"已落地内容被证明不合理 → 彻底修复，不保留历史遗留包袱"）。

**涉及文件**：编译器变量声明/赋值路径（需查询：`core/compiler/` 中 IbVarDecl + 带初始化器的变量声明处理）、examples/01_hello_world.ibci

---

### U3: InterpreterError 双实现绕过（commit 2fd3117，中严重度）

**✅ 已核销（2026-08-11，本 session 修复）**：`core.extension.exceptions` 删除
`InterpreterError` 定义；公开名 `core.extension.InterpreterError` 改指
`core.kernel.issue.InterpreterError`（能力完备）；清理 ibcext.py 死 import
（PluginError/InterpreterError/CompilerError 均未被该文件使用）；__init__.py 直接
导入。+3 契约测试。全量 2181 passed / 1 skipped 零回归。

**违反原则**：原则优先于行为维持 + 历史遗留未清理
**症状**：发现全仓有两个 InterpreterError 实现，只在 config_loader.py 换 import，未统一清理
**位置**：
- `core/extension/exceptions.py:10` `class InterpreterError(ExtensionError)`（简单 Exception，不支持 error_code）
- `core/kernel/issue.py:63` `class InterpreterError(IBCBaseException)`（支持 error_code/location/severity）

**当前（不合格）处置**：
- config_loader.py + ibci_ai/core.py：从 `core.extension.exceptions` 改 import 到 `core.kernel.issue`
- 其余模块仍用 `core.extension.exceptions.InterpreterError`（ibcext.py 等）

**正确做法**：
1. 统一为 `core.kernel.issue.InterpreterError`（支持 error_code，是 IBCBaseException 子类，能力完备）。
2. 删除 `core.extension/exceptions.py:10` 的 InterpreterError 定义。
3. 全仓 grep `from core.extension.exceptions import.*InterpreterError` → 改 `from core.kernel.issue import InterpreterError`。
4. 验证无模块仍 import 旧路径（grep + import 检查）。
5. 全量 pytest 零回归。

**为什么这是不合格**：发现历史遗留没清理，只在当前文件打补丁，是兼容层操作。
用户明确"不要保留历史遗留包袱"。

**涉及文件**：core/extension/exceptions.py、core/kernel/issue.py、ibcext.py、所有 import InterpreterError 处

---

### U4: AIPlugin.setup 自动加载绕过路径规范化（commit 2fd3117，中严重度）

**✅ 已核销（2026-08-11，本 session 修复）**：config_path 统一经
`PathValidator.canonicalize_for_security` 规范化（插件层统一走符号链接解析机制，
与 kernel 层 config 路径处理同源）。与 U6/U7 合并为"加载契约 fail-fast"：注入异常
fail-fast、配置缺失静默跳过。+4 契约测试（含符号链接 project_root 加载验证）。
全量 2185 passed / 1 skipped 零回归。

**违反原则**：绕过安全路径规范化
**症状**：setup 里 `os.path.join(project_root, "api_config.json")` + `os.path.isfile` + `ApiConfig.load` 直接读，未走 canonicalize_for_security
**位置**：`ibci_modules/ibci_ai/core.py` `AIPlugin.setup`

**当前（不合格）实现**：
```python
ec = capabilities.execution_context
if ec is not None:
    project_root = ec.get_project_root()
    if project_root:
        config_path = os.path.join(project_root, "api_config.json")
        if os.path.isfile(config_path):
            config = ApiConfig.load(config_path)
            self.apply_config(config)
```

`project_root` 来自 ExecutionContextImpl（经 engine 注入，已有 canonicalize），所以 `project_root` 本身规范化。但 `os.path.join(project_root, "api_config.json")` 未再 canonicalize，且 `os.path.isfile`/`open` 是原生 OS 操作不经 IbPath/PathValidator。

**对比**：`core/kernel/config.py` IbciConfig.load 用原生 open（在 kernel 层，project_root 已 canonicalize），但 kernel 是受信层。AIPlugin 是插件层，绕过路径规范化可能允许路径遍历（尽管 project_root 来自受信源）。

**正确做法**（择一）：
1. api_config.json 加载经 kernel 层 IbciConfig 扩展（新增 api_config 字段）或新 kernel 层加载器，走 canonicalize_for_security。
2. 或 AIPlugin 用 `PathValidator.canonicalize_for_security` 规范化 config_path 后再 open。
3. 或明确记录 api_config.json 加载属配置特权（同 ibci.json），但需与 IbciConfig 一致使用规范化。

**为什么这是不合格**：绕过统一路径规范化机制，可能在路径注入场景下不安全。

**涉及文件**：ibci_modules/ibci_ai/core.py（AIPlugin.setup + load_config）、core/kernel/config.py（参考 IbciConfig 路径处理）、core/kernel/path/validator.py

---

### U5: _code_api_config.md 临时文档未清理（低严重度）

**违反原则**：code-workflow Phase 5 清理纪律
**症状**：临时任务文档保留"供追溯"，未按 Phase 5"汇报后经用户确认必须删除"
**位置**：`tasks_docs/_code_api_config.md`

**正确做法**：删除（或经用户确认保留）。本 session 已由用户授权其它智能体处理，本文件可在交接后由下一个智能体清理或保留作为追溯。

**涉及文件**：tasks_docs/_code_api_config.md

---

### U6: execution_context 持有 project_root 用默认 None（低严重度）

**✅ 已核销（2026-08-11，本 session 修复）**：测试 `_make_ec` 显式传
`project_root=None` 表意（方式 2）+ `ExecutionContextImpl` 类契约文档注明
"生产路径（engine 注入 / coordinator 任务 EC）必传，None 仅测试直构未确立态"；
消费方（AIPlugin.setup）对 project_root 缺失 fail-fast（方式 1+2 组合，哨兵方式
不必要——生产链 Interpreter 本身允许默认 None 供 spawn 路径，硬性必传无法在
构造器层强制）。

**违反原则**：向测试妥协的兼容（向后兼容非 fail-fast）
**症状**：ExecutionContextImpl.__init__ 加 project_root 参数默认 None；测试 _make_ec 不传也 OK
**位置**：`core/runtime/interpreter/execution_context.py:34`

**问题**：project_root 缺失时应 fail-fast 或测试明确传 None 表意，而非静默默认 None。
当前测试 `tests/runtime/test_execution_context.py::_make_ec` 不传 project_root，
如果改 fail-fast 会破坏测试。

**正确做法**（择一）：
1. project_root 仍默认 None（向测试兼容），但 ExecutionContextImpl 文档注明"生产路径必传，测试可 None"。
2. 测试 _make_ec 改为显式传 project_root=None（表意清晰）。
3. 或 ExecutionContextImpl 区分"未确立"vs"显式 None"（用哨兵），未确立 fail-fast。

**为什么这是不合格**：为不破坏测试而选默认 None，是向测试妥协。用户要求 fail-fast 原则。

**涉及文件**：execution_context.py、tests/runtime/test_execution_context.py

---

### U7: AIPlugin.setup 自动加载三重 if 容错（低严重度）

**✅ 已核销（2026-08-11，本 session 修复）**：三重 if 收敛为显式加载契约——
`ec is None` / `project_root` 缺失 = 注入异常 → **fail-fast**（InterpreterError，
带契约说明）；`os.path.isfile` False（api_config.json 不存在）= 合法态 → 静默跳过
（注释注明）。与 U4/U6 合并落地，+4 契约测试。

**违反原则**：静默降级（应 fail-fast 或 warn）
**症状**：`if ec is not None: if project_root: if os.path.isfile: load()`，project_root 缺失静默跳过
**位置**：`ibci_modules/ibci_ai/core.py` `AIPlugin.setup`

**问题**：project_root 已确立（engine.run 调用路径）时，ec 和 project_root 应非 None。
三重 if 容错掩盖了不应发生的 None 状态。

**正确做法**：
1. project_root 已确立时 ec 必非 None（引擎注入路径保证），可断言或去掉 ec None 检查。
2. project_root 缺失应警告（kernel_diagnostic）或 fail-fast（取决于设计）。
3. api_config.json 不存在是合法状态（用户无配置）→ os.path.isfile 静默跳过 OK。
4. 但 ec/project_root None 是异常状态（engine 未正确注入）→ 不应静默。

**为什么这是不合格**：把"配置不存在"（合法）和"注入异常"（非法）混在一起静默跳过。

**涉及文件**：ibci_modules/ibci_ai/core.py（AIPlugin.setup）

---

## B. 真实 LLM 调用遇到的问题（非不合格操作，需查询/讨论）

### P1: 意图注入效果弱（设计问题，非缺陷）

**现象**：`@ 用冷酷无感情的口吻回复` 意图注释未明显改变 qwen3.6-35b-a3b 输出风格，LLM 仍回复热情内容。
`int/bool` 类型约束（格式服从）则稳定生效。

**有待查询**：
1. auto_intent_injection 机制的实际注入路径（系统提示词？用户提示词？注入位置？）
2. 意图注入在 prompt 中的强度（是否仅追加，不强制约束？）
3. 是否文档应注明"意图效果取决于模型服从性"？
4. 是否需要增强机制（如更强 system 角色约束）？

**位置**：`ibci_modules/ibci_ai/core.py` auto_intent_injection 相关 + `intent_manager`
**不是缺陷**：真实 LLM 行为，MOCK 不会暴露。但暴露了 IBCI 意图机制对低服从性模型的弱效。

### P2: examples 真实跑通的 project_root 检测（流程问题）

**现象**：`main.py run examples/01_getting_started/01_hello_world.ibci` 时 ProjectDetector 向上探测找到仓库根（含 ibci_modules/），所以 project_root=仓库根而非 examples/01_getting_started/。
examples 子目录放 api_config.json 不会被自动加载（引擎去仓库根找）。

**有待查询**：
1. ProjectDetector.detect_project_root 的探测逻辑（向上找 ibci_modules/plugins/ 签名）
2. "examples 真实跑通"验收点如何达成：
   a. 仓库根放 api_config.json（mock:true 或真实配置）？
   b. examples 子目录加 ibci.json 限定 project_root？
   c. 接受"独立临时目录验证"（/tmp/opencode/llm_probe/）为 examples 真实跑通的证据？

**位置**：`core/project_detector.py`、`main.py`、examples 目录

### P3: apply_config mock 模式 _config 状态不完整（设计审视）

**现象**：`apply_config({"defaults":{"mock":true}, ...})` 时走 set_mock_mode，_config["mock"]=True，但 _config["url"]/["key"] 仍为 None（set_mock_mode 不设 url/key）。
has_api_key 特判 mock=True 返回 True（规避 url/key 检查）。

**有待查询**：
1. mock 模式下 url/key/model 的预期状态（None 是否合理？还是应设占位？）
2. has_api_key 特判 mock 是否属"if 能力标志位分派"（第 4 条）？还是合理领域逻辑？
3. set_mock_mode 是否应设占位 url/key/model（避免 None 泄露到序列化等场景）？

**位置**：`ibci_modules/ibci_ai/core.py` AIPlugin.set_mock_mode / has_api_key / apply_config

### P4: AIPlugin.setup 自动加载 + 用户脚本 set_config 的覆盖语义

**现象**：引擎自动加载 project_root/api_config.json 后，用户脚本仍可 `ai.set_config(...)` 或 `ai.set_mock_mode()` 覆盖。

**有待查询**：
1. 自动加载 → 用户 set_config 覆盖的顺序是否符合设计（显式 > 隐式）？
2. 自动加载失败（api_config.json 格式错误）是否 fail-fast 阻止引擎启动？当前是 raise InterpreterError → 阻止。符合设计？
3. 用户脚本 ai.load_config("./other.json") 显式加载是否覆盖自动加载？当前是（apply_config 重设 _config）。

**位置**：`ibci_modules/ibci_ai/core.py` AIPlugin.setup / apply_config

---

## C. 修复优先级建议

| 优先 | 项 | 理由 |
|------|-----|------|
| 高 | U1 generator IbClass 注册 | 核心架构正本清源，删除 receive 特判 |
| 高 | U2 遮蔽 + LLM 表达式 UID 根因 | 编译器深层缺陷，遮挡内建名遮蔽语义 |
| 中 | U3 InterpreterError 双实现统一 | 历史遗留清理（用户明确要求不保留包袱） |
| 中 | U4 setup 自动加载路径规范化 | 安全路径规范化绕过 |
| 低 | U5 _code_api_config 清理 | Phase 5 纪律 |
| 低 | U6 project_root 默认 None | fail-fast 原则 |
| 低 | U7 setup 三重 if | 静默降级 |
| 讨论 | P1 意图注入弱效 | 设计决策（是否增强机制） |
| 讨论 | P2 examples 真实跑通 | 流程决策（如何验收） |
| 讨论 | P3 mock _config 状态 | 设计审视 |
| 讨论 | P4 覆盖语义 | 设计确认 |

---

## D. 本 session 已落地且**正确**的工作（不需重新审查）

以下工作经 self-audit 确认**未**使用不合格操作，可作为交接基础：

1. CFG_ 诊断码域（10 码）+ catalog + 15_diagnostics.md — 正确（公开协议，数据驱动）
2. config_loader.py ApiConfig.load/validate/_validate_model_entry — 正确（单一职责，显式校验）
3. {env:VAR} 解析(_resolve_env) — 正确（正则 + os.environ，fail-fast）
4. mock 显式化 _config["mock"] + set_mock_mode + _is_test_mode 读 mock/env — 正确（消字符串嗅探）
5. has_api_key mock 特判 — **存疑**（见 P3，可能属合理领域逻辑，但需审视）
6. _spec.py vtable 声明（load_config/apply_config/set_mock_mode）— 正确
7. example_api.json 新 schema — 正确
8. _REAL_LLM_E2E_REPORT.md 验证报告 — 正确（除不合格操作段需补充，下方处理）
9. 测试 AI_MOCK_PREFIX 全项目改（set_config TESTONLY → set_mock_mode）— 正确
10. 文档全项目同步（guide/01_setup, syntax/11/13/15, README, howto）— 正确

---

## E. 建议下一个智能体的工作顺序

1. 先读本文件 + tasks_docs/_REAL_LLM_E2E_REPORT.md + tasks_docs/PENDING_TASKS.md（新登记项）
2. 按 C 节优先级：先 U1（generator IbClass）→ U2（遮蔽根因）→ U3（InterpreterError 统一）→ U4（路径规范化）
3. 每项修复走 code-workflow Phase 0-5，全量 pytest 零回归 + commit
4. 完成后清理 U5（_code_api_config.md）
5. 讨论 P1-P4（如能自主决断则推进；不能则上报用户）

---

> 本文件由前一个智能体主动自审并如实记录。承认在追求进度时使用了用户禁止的快速 tricky 操作。
> 下一个智能体应以"工作模式定论"为最高指导，根因修复，不留新兼容层。