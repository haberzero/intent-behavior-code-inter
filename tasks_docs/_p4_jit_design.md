# P4 真 JIT 设计确认（VISION-6 数据平面性能线 · 高风险 → 隔离分支）

> 状态：设计确认（Phase 0-2，未实现）。本文是临时任务控制文档（落地后收敛进 docs/architecture/04_vm_interpreter.md §真 JIT 或独立章节）。
> 分支：隔离分支 `p4-real-jit`（100% 授权，永不触碰 main/unsafe-vibe-dev）。
> 裁判：`scripts/perf_bench.py`（改前/改后吞吐比，P2 收束基线 arith 179.7 / branch 262.9 µs/iter）。

## 0. 目标与定位

P4 = 真 JIT（用户点名优先）。在 §11 九项不变量约束下，为**热路径（while 循环体 / 直线函数体）生成更快执行体**，绕开每节点 CPS 生成器协议（`gen.send`/`StopIteration`，P1 profile 主导成本），保持统一执行入口 + 控制流数据化 Signal + 协作挂起 Waitable + 协议分派 receive。

**P2 收束基线**（vs P1 基线）：arith −30.1% / branch −29.4% / recurse −24.2% / string −24.9% / container −22.1% / class −23.9%。P4 目标：在 P2 基线之上再 **≥2×**（热路径 arith/branch）。

## 1. 现状（Phase 0-2 实证，file:line）

- **CPS 核心**：`vm_executor.py:_drive_loop_gen`（~208-342）。逐帧推进栈；handler yield child_uid 求值子节点 / return/return Signal 完成帧；`gen.send`/`gen.throw` 驱动；StopIteration.value 携 Signal 沿栈数据化。
- **每节点开销**（热路径）：`gen.send`/`StopIteration`（生成器协议）+ `_make_task`（每节点 VMTask 构造，已优化 is_generator 预计算）+ 分派 isinstance（child_uid 类型判定）+ 值层（box/receive）。
- **语句序列驱动**：`_shared.py:_vm_execute_stmt_sequence`（~585）= **生成器**（`yield stmt_uid` → CPS 循环推 VMTask）——循环体/函数体的每节点协议源头。
- **插入点**：
  - while 循环体：`control_flow.py:vm_handle_IbWhile` line ~103（`res = yield from _vm_execute_stmt_sequence(executor, body)`）。
  - 函数体：`_shared.py:_vm_call_function` line ~445（`seq_result = yield from _vm_execute_stmt_sequence(executor, body)`）。
- **值语义**（codegen 体须复刻）：
  - 变量读：`runtime_context.get_variable_by_uid(uid)`（`_current_scope.get_by_uid`，O(1)）；写：`set_variable_by_uid(uid, val, skip_type_check=True)`。
  - binop：`left.receive(method, [right])`（**协议分派**，OP_MAPPING 映射 op→dunder；invariant #6 禁 isinstance(IbXxx) 分派，receive 是统一入口）。
  - 常量：装箱 IbValue（IbInteger.from_native 等）。
  - 控制流：return/break/continue → `Signal(ControlSignal.RETURN/BREAK/CONTINUE, value)` 数据化（invariant #2，handler 不抛 ControlSignalException）。
  - LLM/IO：`Waitable` 协作挂起（invariant #8，executor yield Waitable 给调度器）。

## 2. 方案（route ①：Python 层 codegen）

**最小可行 codegen（v1）目标 = while 循环体**（perf_bench 热程序均为顶层 while 循环；函数体代码生成留 v2）。

### 2.1 codegen 判据（仅热路径 + 安全子集触发）
一个 `IbWhile`/`IbFunctionDef` 体被 codegen 当且仅当：
- 体为**直线序列**（无嵌套 if/while/for/try/raise/yield/await/llmexcept/函数调用/意图注解 `@`）。
- 仅含：变量读、binop/unaryop（经 receive）、常量、赋值（简单目标，无下标/属性/解包）、`return`/`break`/`continue`（→ Signal）。
- 命中判据 → 编译期/首次解释后生成 codegen 体；未命中 → 走原 CPS 路径（`_vm_execute_stmt_sequence`）。

### 2.2 生成形态
生成一个 Python 闭包（或字节码），直接执行直线体：
```
def _jit_body(rt, ec, box, <常量 IbValue...>, <sym_uid...>, <op_method...>):
    s = rt.get_variable_by_uid(s_uid)
    i = rt.get_variable_by_uid(i_uid)
    s = s.receive(OP_ADD, [i]); rt.set_variable_by_uid(s_uid, s, skip_type_check=True)
    i = i.receive(OP_ADD, [ONE]); rt.set_variable_by_uid(i_uid, i, skip_type_check=True)
    return None   # 无 Signal
```
- 变量存取经 `rt.get/set_variable_by_uid`（O(1) 作用域字典，不穿透 scope 私有属性——封装纪律）。
- binop 经 `receive`（协议分派，invariant #6）。
- 控制流经 `return Signal(...)`（数据化，invariant #2）。
- 无 LLM/IO（v1 安全子集排除 yield/await/llmexcept）→ 无 Waitable 挂起点（v2 扩展）。

### 2.3 插入与分派（统一执行入口，invariant #1）
- **不改 CPS 循环**：`vm_handle_IbWhile`/`_vm_call_function` 仍是 CPS handler（生成器）。codegen 体作为**被 CPS 循环调用的快速路径**：handler 检测到"本节点有 codegen 体"→ 直接 `return _jit_body(...)`（一次 CPS 步进内完成整个体），否则走原 `yield from _vm_execute_stmt_sequence`。
- **codegen 体缓存**：per-`IbWhile`/`IbFunctionDef` node_uid 缓存（执行期，executor 级），键 = 体根 uid。判据在首次解释后静态评估（体 AST 不变）。
- **语义等价不变**：codegen 体结果（值 / Signal）与 CPS 路径逐语句一致；循环/函数的控制流（break/continue/return）经 Signal 数据化，与 CPS 路径同语义。

### 2.4 不变量合规（§11 九项）
| # | 不变量 | codegen 合规 |
|---|--------|-------------|
| 1 | 统一执行入口 TaskScheduler | codegen 体在 CPS 循环内被调用（handler 内），非独立执行通道 ✅ |
| 2 | 控制流数据化 Signal | codegen 体 return Signal（break/continue/return）✅ 不抛 ControlSignalException |
| 3 | IExecutionFrame | codegen 体不改帧抽象（仍经 handler 帧）✅ |
| 4 | LLM 通道唯一 | v1 无 LLM（安全子集排除）✅ |
| 5 | 公理层无运行时依赖 | codegen 体在 runtime 层（vm/），非 kernel/axioms ✅ |
| 6 | isinstance(IbXxx) 禁用 | codegen 体经 receive（协议分派）✅ |
| 7 | 快照隔离 | codegen 体不改快照语义（变量经 scope，同 CPS 路径）✅ |
| 8 | 阻塞即挂起 Waitable | v1 无阻塞点（安全子集排除 yield/await）✅ |
| 9 | 调度器永不阻塞 | codegen 体同步返回（无挂起点）✅ |

## 3. 验收判据
1. **吞吐**：perf_bench arith/branch 在 P2 基线（179.7/262.9 µs/iter）上 **≥2×**（arith ≤~90 / branch ≤~130 µs/iter）。
2. **语义等价**：① 全量 pytest 3909/1 零回归（codegen 体与 CPS 路径逐语句等价，经全量测试覆盖）；② 新增判别测试：codegen 触发 vs 未触发的同一循环程序输出一致（热循环结果正确）。
3. **不变量**：§11 九项逐条合规（§2.4 表）；codegen 体不绕过统一入口/控制流数据化/协作挂起。

## 4. 风险与首切片
- **风险**：codegen 体与 CPS 路径语义等价性（最高风险——变量别名/作用域/binop 边界/常量装箱/Signal 语义）；codegen 判据（安全子集）是否过窄/过宽。
- **缓解**：① 隔离分支实验（100% 授权）；② 最小可行切片（v1 = while 直线体，排除 LLM/IO/异常/嵌套）；③ 语义等价判别测试（codegen vs CPS 同程序）；④ 全量 pytest 零回归；⑤ perf_bench 改前/改后裁判。
- **首切片**：v1 = while 循环体 codegen（直线、无 LLM/IO/异常/嵌套）→ 验证 arith/branch ≥2× + 语义等价 → v2 扩展（函数体 / 含 LLM/IO 的 Waitable 挂起点 / 更宽判据）。

## 5. 决策记录
- **选 route ①（Python codegen）而非 route ②（IR/字节码层）**：route ① 不需引入字节码层（与"AST 直走"现状一致，风险低）；route ② 须评估与不变量的冲突（大改，留后续）。
- **v1 目标 = while 循环体**：perf_bench 热程序均为顶层 while 循环（函数体代码生成留 v2）。
- **codegen 体作为 CPS 循环内快速路径**（非独立执行通道）：保持统一执行入口（invariant #1）+ 控制流数据化（invariant #2）。
