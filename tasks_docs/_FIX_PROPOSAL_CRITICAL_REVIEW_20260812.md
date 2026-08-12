# _FIX_PROPOSAL_CRITICAL_REVIEW_20260812 — 修复方案批判性审查

> 2026-08-12。对 `_KERNEL_ISSUES_ANALYSIS_20260812.md` 提出的全部修复方案，从**架构一致性 /
> 代码健康 / 代码质量 / 长期收益**四个维度批判性复审。重点判定：哪些方案合理、哪些需要调整、
> 哪些不合适。全部结论经主代理亲自重读内核代码验证（非转述 subagent 报告）。

---

## 一、判定总览

| 方案 | 判定 | 一句话结论 |
|------|------|-----------|
| PT-DEBT-25 global 档1（镜像 nonlocal） | ✅ **合理** | 机制同构、运行时零改动、单点修复 |
| PT-DEBT-26 import 档1（resolve_member 形状探测） | ❌ **不合适，应改档3** | 在通用内核机制里引入鸭子类型探测，治标留双形态契约 |
| PT-DEBT-26 import 档2（零参数退化修复） | ✅ **合理且必要** | 是档3 的必需配套，形态判定精确 |
| PT-DEBT-27 档1（Waitable yield 异常重投递） | ✅ **合理（已验证正确）** | 使异常投递与值投递对称，TaskCancelled 安全 |
| PT-DEBT-27 档2（结构收敛） | ✅ 可选 | 档1 已达成语义，档2 为结构清理 |
| PT-DEBT-28 档1（vtable 补 2 行） | ✅ **合理** | vtable 即单一权威源，补注册即修复 |
| PT-DEBT-28 档2（native_module 硬错误） | ⚠️ **需独立评估** | 行为面广，勿并入最小修复 |
| O1 obj()（vm_handle_IbCall 加特判） | ❌ **与代码既有设计决策冲突** | 违反"单一协议分派"注释，需重新设计 |
| I1 __iter__ 生成器（resolve_iterable 补丁） | ⚠️ **方向可，实现需调整** | 与 O1 同根（receive→.call→嵌套调度器），应在 .call 层修 |
| O2 字段默认值 | ⚠️ **需用户拍板** | 三种取向各有代价，非纯技术取舍 |
| G3 生成器 __init__（编译期拒绝） | ✅ **合理** | 与 SEM_YIELD_OUTSIDE_FUNCTION 先例一致 |
| G1/G2 文档修正 | ✅ 合理 | 纯文档，无争议 |

---

## 二、详细审查

### 1. ✅ PT-DEBT-25 global 档1 — 合理

**验证**：`symbol_resolution_pass.py` 的 nonlocal 路径（`visit_IbNonlocalStmt`:520-546 + `_collect_nonlocal_names`:602-610 + `_prescan_body_locals`:562 排除）是**完整可照抄的模板**；运行时 global 路由（`runtime_context.py:697-710` + `_shared.py:814-828`）已实现且实测可用。

**架构一致性**：global 镜像 nonlocal = 机制同构（design-philosophy"机制同构"原则的直接应用），不引入新机制、不改运行时、不改变任何既有路径。唯一注意：`visit_IbGlobalStmt` 解析到根作用域并占位 define（支撑"声明先于定义"），与 nonlocal 的"解析到外层"方向相反但机制相同。

**长期收益**：消灭死脚手架（`symbols.py` 的 `is_global`/`global_refs` 从零调用变被消费），把文档承诺的功能真正激活，同时补上"global 从未被测试"的覆盖盲区。

**风险**：近零。只影响带 `global` 声明的函数。

### 2. ❌ PT-DEBT-26 import 档1 — 不合适（重点批判对象）

**原提案**：`_members.py:59` 处形状探测——member 有 `.spec` 无 `.type_ref` 时返回 `member.spec`（因 `_members.py` 不能 import Symbol，circular import，故用鸭子类型）。

**批判理由（三条）**：

1. **在通用内核机制里引入鸭子类型探测 = code-odor 明令禁止的"反射/能力探测隐蔽变体"**。
   `resolve_member`（`core/kernel/spec/registry/_members.py`）是**所有**成员解析的通用机制（原生模块、用户类、泛型容器共用）。用 `hasattr` 探测成员形态等于让通用机制学会"猜"，猜错了静默返回 `any`。这是症状层打补丁，不是根因修复。

2. **双形态契约被固化而非消除**。根因是 `scheduler.py:548-553` 把 `Symbol` 原样写进 `members`（而 members 契约是 `MemberSpec`/`MethodMemberSpec`——原生模块 `discovery.py:212/217` 如此填充，`_create_symbol_from_member` 也显式按此处理）。档1 不改写入侧，只让消费侧"凑合识别两种形态"——**契约仍不统一，未来每个新消费点都要重新猜**。这违反 design-philosophy"单一权威源/设计语言统一"。

3. **已有正确模板被绕开**。`_create_symbol_from_member`（scheduler.py:580-615）已经用**显式 isinstance 分派**处理了 Symbol 与 MemberSpec 双形态——这才是"形状感知"的正确写法（显式类型判别，非鸭子类型）。档1 却选择在 `resolve_member` 里用隐式探测重新实现一遍，造成"两处形状感知、两种写法"的碎片化。

**正确做法（档3，改为推荐）**：在**写入侧** `scheduler.py:548-553` 把 `Symbol` 转为 `MemberSpec`/`MethodMemberSpec`（复用 `_create_symbol_from_member` 的转换逻辑或抽取共享 helper），使 members 契约统一为 MemberSpec 形态——与原生模块、命名导入三方一致。`resolve_member` 零改动，通用机制保持纯净。

**注意**：档2（`_expression_visitors.py:641` 零参数退化）**必须保留**——即便档3 统一形态，MethodMemberSpec 分支构造的 `param_types=[]` 仍是 falsy，`getattr(member,'param_types',None)` 判定依旧退化。档2 应改为"按 kind 判定 FUNCTION/CALLABLE_SIG/BOUND_METHOD 即绑定"，与调用能力判定同源。

### 3. ✅ PT-DEBT-27 档1 — 合理（主代理已验证正确性）

**我亲自验证了三个关键点**：

1. **语义对称性**：`_drive_loop_gen` 中 Waitable 值路径（调度器 `send(val)` → :290 `pending_value = val` → 下轮 `gen.send(val)` 进 handler）与异常路径（调度器 `throw(exc)` → :290 `except Exception` → `pending_exception = e` → 下轮 `gen.throw(exc)` 进 handler）在档1 后**完全对称**——异常像值一样投递给挂起该 Waitable 的 handler 帧，其 try/except 优先处理，未捕获则走 :270 弹栈继续上抛。这正是 CPS 异常语义的应有形态。

2. **TaskCancelled 安全**：`TaskCancelled` 是 `BaseException`（task_scheduler.py:47），档1 用 `except Exception` 不会捕获 → 正确穿透给调度器 :190 的 `except TaskCancelled`。协作取消语义不受影响。

3. **UnhandledSignal 安全**：`UnhandledSignal`（signals.py:51）是 Exception 子类，若经 Waitable 投递会被档1 捕获重投递给 handler——但该信号本就不应经 Waitable 路径投递（它是函数体逃逸信号，只在 send 路径 :255-262 触发），档1 捕获后交给 handler 处理语义合理。

**结论**：档1 不是"症状补丁"——它把"调度器异常→CPS 栈"的投递通道补齐，与 :270 弹栈机制复用同一 `pending_exception` 通道，是**机制收敛而非新增**。档2（结构对称化）为可选清理，档1 已达语义目标。

### 4. ✅ PT-DEBT-28 档1 — 合理；档2 需独立评估

**档1**：vtable 就是模块成员的单一权威源（`_spec.py` 是成员契约声明、`core.py` 是实现、`loader` 校验"声明→实现存在"）。漏注册 2 项 = 契约不完整，补上即闭环。零风险、零架构变化。**批准**。

**档2**（`native_module.py:113-135` 让契约违例直接上抛，消除静默 None）：方向正确（符合 fail-fast），但**影响面是所有原生模块成员访问**（ai/idbg/isys/ihost/file 全走 IbModule.receive），且要处理"故意移除但文档化"的 idbg `inspect`/`dump_intent_stack`（docs §11.5 明说"未实现，调用产生运行时错误"——若硬抛，行为反而与文档一致，但需确认无其它宽松依赖）。**应作为独立加固窗口评估，不并入档1**。

### 5. ❌ O1 obj() 修复方案 — 与既有设计决策冲突（重点批判对象）

**原提案**：在 `vm_handle_IbCall` 的通用 `receive('__call__')` 兜底前，识别"func 为用户类实例且有用户 `__call__`"，解包为 `UserFunctionCall` trampoline。

**批判理由**：`leaf.py:405-406` 有一段**明确的设计决策注释**：
> "统一走 `receive('__call__')` 协议分派（base.receive 内置 .call 兜底），**不再用 hasattr 探测双路径（单一协议分派）**。"

原提案**正是要重新引入这个刚被移除的双路径探测**（在 vm_handle_IbCall 里加"用户类实例 + 有 __call__"特判，绕过协议分派）。这直接违反代码自身的既定架构决策，属于"开历史倒车"。

**正确方向**：保持"单一协议分派"，但让 `__call__` 协议路径**本身**在 VM 内不产生嵌套调度器。即：`IbObject.receive('__call__')` 解析到用户 `__call__` 方法时，返回一个 CPS 请求（`UserFunctionCall(method, args, self)` 请求对象），`vm_handle_IbCall` 通过既有的 `isinstance(child_uid, UserFunctionCall)` 分支（:299-306 已存在）驱动——VM 侧天然 trampoline，宿主侧保持 `.call()` 同步兜底。这是"协议分派不变、VM 驱动方式变"，与 `CPSDrivable`（A5 类构造）同构。

> 这是**设计层面**改动（receive 契约 + vm_handle_IbCall 处理），不是"插一个分支"。需独立设计冻结，按 code-workflow 独立分支实验。原提案的"特判"是错误形状。

### 6. ⚠️ I1 __iter__ 生成器 — 与 O1 同根，应在 .call 层修

**重新分析**：I1 的崩溃（`resolve_iterable` → `receive('__iter__')` → `method.call` → `_drive_generator` 无生成器模式 → GeneratorYield 泄漏）**与 O1 是同一根因**：`receive(protocol)` → `IbUserFunction.call`（同步宿主包装）→ `_drive_generator`（嵌套调度器）对生成器方法无处理。

**因此 I1 的修复不应只在 `resolve_iterable` 打补丁**（`iterable.py` 加"__iter__ 返回 IbGenerator 则 to_list"），因为崩溃发生在 `.call` 内部、结果根本回不到 resolve_iterable。正确修复在 `IbUserFunction.call`/`_drive_generator` 层：使同步 `.call` 对**生成器方法**返回 IbGenerator（与 VM 的 is_generator 分支一致）——这一处修复**同时治好 O1（生成器 __call__）与 I1（生成器 __iter__）**，是共同根因的机制收敛。

**语义取向**：选"接受 __iter__ 返回生成器并 to_list"（与 `resolve_iterable` 已对顶层 IbGenerator 的 to_list 处理一致，机制同构），而非编译期拒绝（过度限制，Python 惯用法）。

### 7. ⚠️ O2 字段默认值 — 需用户拍板（非纯技术）

现状：`_eval_field_defaults(_cps)`（ib_class.py:178-183, 267-272）只对 list/dict 首层浅拷贝；内层 list 与用户对象默认值完全共享。

**三种取向及代价**：

| 取向 | 语义 | 代价 | 架构契合 |
|------|------|------|---------|
| A. 递归深拷贝 | 值语义：每次构造独立 | 性能（大对象）、用户对象 identity 语义、与"引用共享"整体设计（KNOWN_LIMITS §五）冲突 | 弱——IBCI 定位是引用语义（与 Python 一致），深拷贝是特例 |
| B. 编译期限制可变默认值 | fail-fast：`list`/`dict`/用户对象默认值要求 `__init__` 显式初始化 | 语法面变严、打破"字段默认值"既有特性（06_oop §6.1 文档化 `list[str] tags = []`） | 强——符合 fail-fast 哲学，但**破坏现有文档化特性**，需改文档+测试 |
| C. 文档精确化 | 保留浅拷贝，明确"仅首层复制" | 陷阱仍在（静默泄漏） | 弱——最低成本但留雷 |

**我的建议**：不推荐 A（与引用语义设计冲突）。B 是长期正确的方向（与 KNOWN_LIMITS §五.2"始终在构造函数初始化"的既有建议一致，把建议变强制），但属**破坏性变更**（06_oop §6.1 示例 `list[str] tags = []` 会变非法），需独立窗口设计 + 文档/示例/测试联动。若近期要快速止血，C 最小成本。

### 8. ✅ G3 生成器 __init__ 编译期拒绝 — 合理

与 `SEM_YIELD_OUTSIDE_FUNCTION`（模块顶层 yield 报错）先例一致，fail-fast 哲学。Python 虽静默丢弃，但 IBCI 更倾向显式。P2 低风险，随文档窗口。

### 9. ✅ G1/G2 文档修正 — 合理

G1（05_functions §5.8 "break 提前终止" 表述错误，实际 for=to_list 急物化）、G2（KNOWN_LIMITS §二十四 首段过时，await chan 实测可用）均为纯文档修正，无争议。G2 附带"阻塞式消费是潜在死锁风险"应记录而非修复（当前零生产调用）。

---

## 三、修正后的修复批次建议

| 批次 | 内容（修正后） | 风险 | 政策 |
|------|--------------|------|------|
| **A（紧急，低风险，可直接合并）** | PT-DEBT-27 档1（异常投递对称化）+ PT-DEBT-25（global 镜像 nonlocal）+ PT-DEBT-28 档1（vtable 补 2 行） | 三处均单点、机制同构、零回归面小 | 独立分支 → 全量零回归 → 零风险直接合并 |
| **B（专项，独立窗口）** | PT-DEBT-26 改走**档3**（scheduler 写入侧统一 MemberSpec 形态）+ 档2（零参数退化形态判定） | 低-中（编译期、契约统一） | 独立分支实验 |
| **C（设计级，需冻结）** | O1 + I1 **合并为"receive→.call 生成器/__call__ 同步路径 CPS 化"**（共同根因一处修）+ 保留协议单分派 | 中（receive 契约 + leaf.py 驱动方式，影响序列化/vtable 契约） | 独立设计冻结 + 独立分支实验 + 手动应用 |
| **D（决策/文档）** | O2（B 或 C 取向，用户拍板）+ G1/G2/G3/O3 文档修正 + I2/O4 边界记录 | 低 | 按用户决定 |

## 四、结论

- **合理的方案**：PT-DEBT-25（global）、PT-DEBT-27（异常投递）、PT-DEBT-28 档1（vtable）、G3、G1/G2 文档。这些是**机制同构、单点、低风险**的干净修复。
- **需要调整的方案**：PT-DEBT-26 应从档1（鸭子类型探测）**改走档3**（写入侧统一形态）；I1 应从"resolve_iterable 补丁"**改为与 O1 合并**在 `.call` 层修共同根因。
- **不合适的方案**：O1 的"vm_handle_IbCall 特判"——直接违反 `leaf.py:405` 刚确立的"单一协议分派"设计决策，需按"协议分派不变、VM 驱动方式变"重新设计。PT-DEBT-26 档1 的鸭子类型探测是 code-odor 禁止的反射变体，不应引入通用内核机制。
- **需用户拍板**：O2 字段默认值取向（B 破坏性 vs C 止血）。
