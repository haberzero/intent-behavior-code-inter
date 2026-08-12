# _KERNEL_ISSUES_ANALYSIS_20260812 — 内核缺陷根因分析与修复方案

> 2026-08-12。基于真实 LLM 全面压力试用（`_LLM_TRIAL_20260812/`）暴露的问题，深入内核代码
> 逐一定因（含 general agent 独立调查 + 主代理亲自复核验证）。本文档 = 根因分析 + 修复方案 +
> 生成器/迭代器/OOP 层专项审计结论，供用户决定下一阶段开发/修复方向。**本文档只分析，不改代码。**

---

## 一、四项 P1 内核缺陷根因（试用已登记 PT-DEBT-25~28）

### 1. KERNEL-ISSUE-001：`global` 写访问失效（PT-DEBT-25）

**现象**：`func bump(): global counter; counter = counter + 1` 运行时 `RUN_UNDEFINED_VARIABLE:
.../bump:counter`（UID 带函数局部作用域前缀）。

**根因（全链路实证）**：
- Lexer/Parser/AST 完整：`core_scanner.py:46` 关键字 → `statement.py:111-120` → `ast.IbGlobalStmt`。
- **语义层完全空转**：`_statement_visitors.py:489-491` `visit_IbGlobalStmt` 直接 `return None`；
  `symbol_resolution_pass.py` **没有** `visit_IbGlobalStmt`/`_collect_global_names`（对照 nonlocal 的
  `:520/:602` 完整实现）。binding_analysis_pass 的 `_analyze_function_captures`（:867）只收集 nonlocal。
- **关键断点 `symbol_resolution_pass.py:562`** `_prescan_body_locals`：`if name not in scope.symbols
  and name not in nonlocal_names:`——未排除 global 名 → 把 `counter`（赋值目标）预声明为**函数局部符号**，
  UID=`scope_<module>/bump:counter`。
- 运行时 global 机制**其实已实现但收不到模块级 UID**：`runtime_context.py:697-710`
  `define_variable_at_global`/`is_global_symbol_uid` + `_shared.py:814-828` 写路由均就绪。
  实测：函数内**只读**模块变量 ✅；`counter += 1`（aug-assign 不走 prescan）✅ 直接证明"UID 为模块级时
  运行时全部可用"。
- **定性**：编译期符号解析层完全未消费 global 声明（binding 未变），运行时按 UID 工作的机制永远触发不了。
  死脚手架佐证：`symbols.py:102/125/172-179` `is_global`/`global_refs`/`get_global_scope` 零调用点。

**修复方案**：
- 最小（1 文件）：`symbol_resolution_pass.py` 加 `_collect_global_names` + `visit_IbGlobalStmt`
  （镜像 nonlocal，解析到根作用域/占位 define）+ `_prescan_body_locals:562` 排除 global 名。
- 正确架构：激活死脚手架（`is_global=True`/`add_global_ref`）+ 冲突校验（global 与参数同名等）
  + 新诊断码。运行时零改动。
- 测试：绑定 UID 断言 + `counter=1` 回归 + 写后读全局 + 只读/aug-assign 防回归 + 多名字/声明先于定义。

### 2. KERNEL-ISSUE-002：整模块 `import mod` + 成员访问 → 编译器 `INT_INTERNAL_ERROR`（PT-DEBT-26）

**现象**：`import greeting_mod; greeting_mod.greet()` 报 `'FunctionSymbol' object has no attribute
'type_ref'`；变量导出同理。

**根因（编译期，证据链）**：
- `scheduler.py:548-553` 被导入模块编译后，把其符号表**原样写回** `final_mod_meta.members`——members 里装的是
  `FunctionSymbol`/`VariableSymbol`（Symbol 家族，只有 `.spec` 无 `.type_ref`）。
- `_expression_visitors.py:638` `greeting_mod.greet` → `_members.py:59` `resolve_member` → 
  `self.resolve_typeref(member.type_ref)`——`resolve_member` **假定 members 全是 MemberSpec 形态**
  （该契约对原生模块成立，`discovery.py:212/217` 用 MethodMemberSpec 填充），用户 IBC 模块按 Symbol 形态
  放入 → AttributeError → 包装成 INT_INTERNAL_ERROR。
- `from helper import square` 正常：命名导入走 `_create_symbol_from_member`（scheduler.py:580-615）**形状感知**，
  使用点是裸 `IbName`，不经过 `resolve_member`。
- **同一路径既有独立缺陷**：`_expression_visitors.py:641-649` 用 `getattr(member,'param_types',None)` 真值判定
  零参数函数 → `[]` 为 falsy → 类型退化为 `any`。修好崩溃后 `int x = helper.greet()` 仍不报类型错。

**修复方案**：
- 档1（最小）：`_members.py:59` 形状探测——member 有 `.spec` 无 `.type_ref` 时返回 `member.spec`
  （注意 `_members.py` 不能 import symbols，circular import，须形状探测）。
- 档2（同路径完整性）：`_expression_visitors.py:641` 零参数判定改形态判定（FUNCTION/CALLABLE_SIG）。
- 档3（正确架构）：scheduler 写入时把 Symbol 转 MemberSpec（与原生模块对齐）。
- 测试：`TestIbcFileWholeImport`（mod.func/mod.var/别名/嵌套 pkg）+ 两路类型诊断对账。

### 3. KERNEL-ISSUE-003：真实 LLM provider 失败 `LLMCallError` 逃逸 `try/except`（PT-DEBT-27）

**现象**：`ai.set_timeout(0.01)` + `try: str r = @~...~ except LLMCallError/LLMError/Exception` 全不捕获，
`ThrownException: <LLMCallError object>` 冒泡崩溃。MOCK 解析失败与手动 raise 均可捕获。

**根因（唯一断点，实证）**：
- 异常对象形态两路径**完全相同**：都是 `ThrownException(IbObject)`（`_core.py:255`），error_obj 的
  `ib_class=LLMCallError`、assignable 到 LLMError/Exception 均 True——**不是类型/语义问题**。
- **断点在 `vm_executor.py:290`**：`pending_value = yield child_uid`（Waitable 挂起点）位于 `_drive_loop_gen`
  内部 try/except（:244-274）**之外**。
  - MOCK 解析失败：Future 以 value 完成 → 调度器 `send` 进 :290 → 值流到 `vm_handle_IbName` → **同步**
    `raise ThrownException`（在内部 try 内，:244-252 的 send 路径）→ 被 :270 except 捕获 → 弹栈重投递 ✅。
  - 真实 provider：异常在 worker 线程 `raise` → Future 捕获 → `try_result` re-raise（`llm_result.py:110`）→
    调度器存 `resume_exception` → `gen.throw(exc)`（task_scheduler.py:179）投进 **:290 的 yield 点** →
    该 yield 在内部 try 之外 → **异常穿透整个 VM**，从未转为 `pending_exception` 沿 CPS 栈重投递 ❌。
- `vm_handle_IbTry` 的 except 帧在整个挂起期有效；`control_flow.py:361` 按 `__class__` 捕获 `ThrownException`
  后解包——若异常到达该帧必然匹配成功。断点纯粹是"调度器→VM 栈异常投递断链"。

**修复方案**：
- 档1（最小，推荐）：`vm_executor.py:289-291` 把 Waitable yield 的异常重注入 innermost task 生成器
  （`except Exception: pending_exception = e; continue`），让其自身 try/except 优先处理、未捕获再经 :270 弹栈
  重投递。**必须用 `except Exception`**（`TaskCancelled` 是 BaseException，须穿透给调度器 :190）。
- 档2（正确架构）：重构 `_drive_loop_gen` 使挂起/恢复对称（send value 与 throw exception 统一走 CPS 再投递）。
- 潜伏缺口（一并收口建议）：`vm_executor.py:278` GeneratorYield 的 yield 同样在内部 try 之外（生成器消费者
  throw 会穿透 VM）；TaskCancelled 在 Waitable 挂起点被 throw 时 CPS 栈内任务 finally 不执行。
- 测试：`_FailingProvider` + `try/except LLMCallError/LLMError/Exception` 三档；parallel=true/false 两路；
  llm 函数/run_batch 路径；取消回归。

### 4. KERNEL-ISSUE-004：`ai.get_retry()`/`is_auto_intent_injection_enabled()` 不可调用（PT-DEBT-28）

**现象**：`ai.get_retry()` → `None has no method '__call__'`。实现存在于 core.py:380/383，但不可调用。

**根因（vtable 契约漂移）**：
- `_spec.py` vtable 只注册了 21 个函数，**漏了这两个**（其余 §11.3 文档化 API 全部对账一致）。
- 运行时解析链：`ai.get_retry` → `IbModule.receive('__getattr__')`（native_module.py:113-135）→ 原生对象
  已正确抛严格错误 "not defined in module contract"（native_module.py:91），**但被 IbModule.receive 连续吞掉**
  （:125/:131）→ 落到基类 Object 宽松 `__getattr__` 兜底 → `registry.get_none()` → None → `None('__call__')` 报错。
- **副作用**：None 兜底把"意外漏注册"与 idbg `inspect`/`dump_intent_stack`（文档明说未实现）的"故意移除"
  混为一谈，无 fail-fast。这与 WORKLOG "设计决策" 里的 fail-fast 原则相悖，是**契约漂移的静默化**。

**修复方案**：
- 档1（最小，推荐）：`_spec.py` vtable 补两行（`get_retry`→int、`is_auto_intent_injection_enabled`→bool），
  loader 自动绑定实现。
- 档2（加固）：`native_module.py:113-135` 让原生模块成员契约违例的严格错误直接上抛（区别于普通对象缺属性），
  消除静默 None 兜底；或至少区分"契约缺失 vs 普通缺属性"。属破坏性改动需评估与 idbg 文档化行为对齐。
- 测试：契约对账反向漂移检测（现有 `check.py:184-213` 只查"vtable 声明→实现存在"，不查"实现有公共方法
  vtable 无"）+ 语言级冒烟（`set_retry(5); get_retry()`）。

---

## 二、生成器 / 迭代器 / 面向对象层专项审计（用户要求顺带核查）

### 生成器块

| # | 发现 | 定性 | 根因 |
|---|------|------|------|
| G1 | `for x in gen(n)` 中 break 后生成器体仍完全跑完 | 文档张力（BOUNDARY-001） | `vm_handle_IbFor`→`_resolve_iterable`→`iterable.py:30-31` 对 IbGenerator 先 `to_list()` 急物化；`for` 对 list 是惰性活迭代、对生成器是急物化——**两条消费路径惰性语义不一致**。§5.8:240 说"break 提前终止"错，§5.9:274"to_list 一次性物化"对 |
| G2 | 生成器体内 `await c.recv()` 实测可用，KNOWN_LIMITS §二十四 报错路径不可达 | 文档过时（BOUNDARY-002） | `generic_next`（generator.py:62-63）`while isinstance(event, Waitable): event.result()` 阻塞等待任意 Waitable 并注回驱动；`"unexpected event"` 分支（:66）在当前 handler 集下不可达。**但底层是阻塞 VM 线程而非协作挂起**——若 Waitable 只能靠 VM 线程推进则死锁（当前生产零调用，潜在风险） |
| G3 | 生成器 `__init__` 静默不执行（`self.v=42` 失效，v=0） | **真缺陷** | `_invoke_init_cps`（ib_class.py:304-305）yield UserFunctionCall → `_drive_loop_gen` 见 is_generator → make_generator_driver → 返回的 IbGenerator 被**丢弃**。与 Python 语义一致但完全无文档 |
| G4 | 生成器驱动帧跨 next() 挂起期间持有 intent scope（`enter_intent_scope` 在 finally 才弹出），中途丢弃依赖 GC | 潜在残留风险 | 需专项验证，未实证为缺陷 |

### 迭代协议块

| # | 发现 | 定性 | 根因 |
|---|------|------|------|
| I1 | 用户类 `__iter__` 写成分片生成器方法 → 编译通过但运行崩溃（`No CPS handler for node type 'GeneratorYield'`） | **真缺陷** | `resolve_iterable`（iterable.py:32-35）`receive('__iter__')` → `method.call` → `_drive_generator`（非生成器模式）→ GeneratorYield 泄漏。直接 `auto it = r.__iter__()`（走 vm_handle_IbCall is_generator 分支）返回正常 IbGenerator——**两条路径行为分裂**。06_oop §6.6 说 `__iter__` 返回"可遍历列表"，生成器形式是契约外但编译器不拒绝也不清晰报错 |
| I2 | `for` 对 list 活迭代（迭代中 append 延伸循环）vs 生成器急物化 | 设计边界 | 与 Python 一致，文档需明确 |

### 面向对象块

| # | 发现 | 定性 | 根因 |
|---|------|------|------|
| O1 | 可调用类实例 `obj()` 深递归 Python RecursionError（depth~300 崩；普通函数 depth=500 通过） | **真缺陷（PT-DEBT-12/F1 遗留）** | `vm_handle_IbCall`（leaf.py:405-420）非函数/非 bound-method 落回 `func.receive('__call__')` → `method.call` → `_drive_generator`（coordinator.py:309-336，**新建嵌套 TaskScheduler**）——违反 EXEC-1 trampoline 保证。`__call__` 含依赖外层调度器推进的 Waitable 时同样死锁。**KNOWN_LIMITS §一"跨路径限制"的真实机制就是它**（文档描述模糊且过时） |
| O2 | 用户类字段默认值可变共享：`list[list[int]]` 内层共享、用户对象默认值整体共享 | **真缺陷（比文档更广）** | `_eval_field_defaults(_cps)`（ib_class.py:178-183, 267-272）只对 list/dict 的 static_val 做**浅拷贝**。`list[int]=[]` 头层安全（浅拷贝生效）造成假象；内层 list 与用户对象默认值完全共享、静默泄漏。KNOWN_LIMITS §五.2 提示的陷阱实际更广 |
| O3 | KNOWN_LIMITS §十四 #2"用户类无法重载运算符"**已过时** | 文档过时 | 实测用户 `__eq__`/`__add__` 正常分派（interpreter.py:651-652 注册 + vtable）。`==` 退化为身份比较已不成立 |
| O4 | 多继承 `class C(A,B)` 报原始 `PAR_UNEXPECTED_TOKEN`，无清晰错误 | 设计边界 | 无"不支持多继承"的明确诊断 |
| O5 | `IbClass.receive('__call__')` 捕获主 EC + `_eval_field_defaults_cps` 跨线程改写 `context.current_module_name` | 风险（已登记 S2） | 线程任务内构造用户类污染主 EC 模块名 |

---

## 三、汇总与修复优先级建议

### 修复排序（按 ROI + 风险）

| 优先级 | 项 | 性质 | 风险 | 建议窗口 |
|--------|----|------|------|---------|
| **P0** | PT-DEBT-27 LLMCallError 逃逸 | 真实网络场景必然触发 + 文档承诺契约失效 | 档1 极小（vm_executor.py:289 加 except） | **独立分支 → 零风险直接合并** |
| **P0** | PT-DEBT-26 整模块 import 崩溃 | 文档化用法 + 编译器对正常输入崩溃 | 档1+2 低（_members.py 形状感知） | 独立分支 |
| **P1** | O1 `obj()` 嵌套调度器 | 深递归崩溃 + 死锁风险 + KNOWN_LIMITS §一机制 | 中（leaf.py 插入 CPS 分支，需测序列化/契约） | 独立分支实验 |
| **P1** | PT-DEBT-25 global 失效 | 文档化功能完全失效 | 档1 极低（symbol_resolution_pass 1 文件） | 独立分支 |
| **P1** | I1 用户类 `__iter__` 生成器崩溃 | 契约外用法无清晰错误 | 低（iterable.py 接受 IbGenerator 或编译期拒绝） | 独立分支 |
| **P1** | O2 字段默认值共享 | 静默泄漏（用户对象/inner list） | 低-中（深拷贝 or 文档精确化） | 独立分支 |
| **P2** | G3 生成器 `__init__` 静默丢弃 | 语义与 Python 一致但无文档 | 低（编译期拒绝 or 文档） | 随文档窗口 |
| **P2** | PT-DEBT-28 ai vtable 2 API | 契约漂移静默化 | 极低（_spec.py 补 2 行） | 零风险直接合并 |
| **P3** | G2/G1/O3 文档过时/张力 | 文档与实测不符 | 低（纯文档） | 文档治理窗口 |
| **P3** | G4/I2/O4 潜在/边界 | 记录 | - | 记录/文档 |

### 建议的组合执行

**批次 A（紧急，2 项，低风险）**：PT-DEBT-27（异常逃逸）+ PT-DEBT-28（ai vtable）+ PT-DEBT-25（global）+
PT-DEBT-26（import 崩溃）——四个都是"文档化但失效"，档1 修复面小、全量 pytest 零回归验证、经零风险
直接合并政策合入 unsafe-vibe-dev。这是试用暴露问题的最小闭环。

**批次 B（专项，3 项，需独立分支实验）**：O1（obj() 嵌套调度器 CPS 化）+ I1（__iter__ 生成器）+
O2（字段默认值深拷贝）——后两者修复方向明确；O1 涉及 leaf.py 调用分派改动 + 契约/序列化验证，
按"独立分支 + 手动应用"政策。

**批次 C（文档/记录）**：G1/G2/G3/O3 文档修正（05_functions §5.8、KNOWN_LIMITS §二十四/§十四/§一）、
I2/O4 边界记录、G4 专项验证。

### 关联既有项（勿遗漏）

- O1 与 PT-DEBT-12/F1（用户方法 CPS 化）同族，但**`obj()` 实例调用路径**是 F1 未覆盖的遗留——修复时
  应对照 `_ASYNC_UNIFY.md` 确认。
- O5 与 PT-AUDIT-3 疑似项 S2 同源，可合并窗口。
- G2 与 KNOWN_LIMITS §二十四 的修复（df1a896 只改了 :554 段没改 :552 段）——本次应一并收口。

---

## 四、架构层面总体判断

1. **缺陷共性**：除 O1 外，全部是"文档化但未测试的边角路径"或"双路径形态不一致"——没有一项是测试覆盖内
   功能退化。这印证了真实 LLM 试用 + 挑刺式遍历的价值：MOCK 为主的测试体系覆盖主路径，但**契约完整性
   （vtable/模块成员形态/异常投递/符号绑定）缺乏系统性测试**。
2. **修复质量要点**：档1 修复都遵循"与既有机制同构"（global 镜像 nonlocal；resolve_member 形状感知对齐
   _create_symbol_from_member；异常重投递对齐 :270 弹栈路径；vtable 补注册对齐 loader 校验），符合
   design-philosophy 机制同构原则，非兼容层/胶水实现。
3. **需用户拍板项**：O2 字段默认值——选"统一深拷贝"（改变语义，需评估序列化/性能）还是"文档精确化"
   （保留浅拷贝+明确边界）。此两项方向建议先独立分支实验论证后合并。
