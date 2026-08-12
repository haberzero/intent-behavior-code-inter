# EXEC_REFACTOR_BATCH — 统一执行地基复核与根治修复批次（R1-R6）

> **定位**：阶段 1-3 落地后的**复核发现与根治修复**（用户裁定：禁止妥协性处理，工作成本/难度不参与权衡）。
> **深度分析**：本 session（2026-08-07）已完成并定案——**无悬而未决问题**。
> **关联**：`EXEC_FOUNDATION_DESIGN.md`（被复核/修正的设计冻结）｜`CONCURRENCY_AUDIT.md`（审计）｜
> `NEXT_STEPS.md`（下一主线）。

---

## 〇、摘要

阶段 0-3 落地过程中暴露 5 处妥协/可疑处理，经用户裁量：**必须彻底修复，不留妥协**。本批次给出每项的根治方案；
其中 R5 经深度分析**撤回**（原判断错误，幂等是设计特性）；D-08 经深度分析**定案保留**。全部决策已记录，无遗留问题。

| # | 问题 | 处置 | 规模 |
|---|------|------|------|
| R1 | 函数调用未 trampoline 化（EXEC-1 违背，深递归靠帧数压制） | **根治**：用户函数调用改 CPS 内联驱动（`_vm_call_user_function`） | 大（调用路径） |
| R2 | 调度器 poll+park（~1ms）非主流；"单待决阻塞"未实现 | **根治**：通知式唤醒（Waitable 完成钩子 + 调度器 wake event） | 中（协议+调度器+实现者） |
| R3 | `IbThread` 未满足 Waitable（D-04 偏离，`_ThreadJoinWaitable` 包装） | **根治**：unify `is_done`（property + auto-bind 支持 property-backed 方法），`await t` 可用 | 小-中（auto-bind 机制） |
| R4 | P3 对共享 cell 私有属性直写（`coordinator` 摸 `_shared_with_main`） | **根治**：`IbCell.mark_shared_with_main()` 公开协议 | 琐碎 |
| R5 | ~~`await` 非 waitable 幂等"偏松"~~ | **撤回**：幂等是 auto-yield 组合的承载（`await collect(h)` 依赖），非偏松 | — |
| R6 | 嵌套函数仅 `nonlocal` 捕获（比 lambda/Python 严格，只读捕获需声明） | **根治**：函数自动捕获外层只读引用（与 lambda 同机制），`nonlocal` 仅用于写 | 中（编译器+闭包） |
| D-08 | 透明 async 是否需要 async 标记（重议项） | **定案**：保留透明 async（CPS 天然可挂起 + auto-yield 组合 + 值契约 + yield 自标记） | — |

---

## 一、复核发现与处置依据（用户裁定）

- 用户裁定（2026-08-07）：**1/2/4 必须完整且彻底修复，不允许妥协性处理**；工作成本/重构难度不参与权衡。
- 用户裁定：不要求 100% 遵循文档化设计；**IBCI 无用户，可为长远可维护性与架构健康性推翻已文档化设计**。
- 设计哲学基准：系统统一、单一权威源、机制同构、命名统一、宏观合理性、长期收益。

---

## 二、深度分析：R1 函数调用 trampoline 化（EXEC-1 根治）

### 2.1 现状问题（Python 嵌套链）

当前 `vm_handle_IbCall` 对用户函数走 `func.receive("__call__")` → `IbUserFunction.call`（同步 Python 方法）→
`vm.run_body` → 逐语句 `vm.run(stmt)` → 每语句**新建调度器 + 新建 `_drive_loop_gen`**（嵌套）。每层递归嵌套 Python 帧：
`_drive_loop_gen → vm_handle_IbCall(gen) → IbUserFunction.call → run_body → run → 调度器 → _drive_loop_gen（下一层）…`
→ **递归深度 = Python 栈深度**，违反 EXEC-1"主路径不使用 Python 递归栈"。阶段 1a 靠调度器 run 循环内联把每层帧数压回
基线以下（"帧数压制"），属妥协，需根治。

### 2.2 根治设计

1. **新建 `_vm_call_user_function(executor, func, receiver, args)` CPS 生成器**（与既有 `_vm_call_fn_callable` 平行）：
   - 帧准备移入生成器前奏：`enter_scope` / 实参绑定 / 闭包 cell 绑定 / 意图 fork / super 注入（从 `IbUserFunction.call`
     抽取为共享助手，同步后端与 CPS 路径复用）；
   - 逐语句 `yield body_stmt_uid` → `_drive_loop_gen` 把语句**压进同一 VMTask 栈**；
   - 每条语句结果回传后处理：one-shot 意图激活/清理（沿用 `run_body` 逻辑）、RETURN Signal → 返回 `e.signal.value`、
     BREAK/CONTINUE → 透传；`finally` 弹栈/恢复意图/模块上下文。
2. `vm_handle_IbCall` 对用户函数改走 `yield from _vm_call_user_function(...)`。
3. `IbUserFunction.call` 保留为**同步后端**（宿主直调/线程体/`_invoke_update_fn`），内部驱动同一 CPS 生成器经调度器跑完。
4. **线程体**用户函数分支（`coordinator._run_task_body`）改走同一 CPS 驱动（当前 `task_func.call` 同步嵌套，线程内深递归同样治根）。

### 2.3 为什么能达到"Python 深度恒定"

`_drive_loop_gen` 单生成器驱动整个 VMTask 栈：递归调用发生时把内层调用的语句**压栈**（list），外层调用生成器
**挂起**（不在 Python 栈上）。任一瞬间 Python 活跃链仅 `_drive_loop_gen → 栈顶 handler(gen) → _vm_call_user_function(gen)`
约 3-4 帧，与递归深度无关。→ EXEC-1 真正达成（trampoline）。

### 2.4 影响面与验证

- 影响：调用协议、闭包绑定、递归、意图上下文、llmexcept re-drive、线程体。
- 验证：`chain(100)` / 深递归 / 互递归 / 尾递归；`frame_stack_depth` 观察；全量 pytest 零回归。
- 独立分支 `exp/exec-rd`（最重，最后）。

---

## 三、深度分析：R2 调度器通知式唤醒（根治 poll+park 与"单待决阻塞"）

### 3.1 现状问题

阶段 1a 为绕开"HostAwaitable.result() 消耗性二次消费"放弃单待决阻塞，调度器全等待时 `time.sleep(~1ms)` 轮询。
低于主流（通知/回调唤醒），且"单待决阻塞即时唤醒"未恢复——两处同为**等待机制不高效**的根因。

### 3.2 根治设计

1. **`Waitable` 协议加完成通知钩子** `register_wake(event) -> None`（等待路径唯一新增成员；既有
   `try_result`（调度器非阻塞取）与 `result`（宿主阻塞取）不变量不变）。
2. **调度器**持 `_wake_event`：任务转等待时对 waitable `register_wake(self._wake_event)`；全等待时
   `self._wake_event.wait(安全超时)` 后清事件重 poll——**完成即唤醒，无轮询延迟**；安全超时仅作兜底。
3. **各 waitable 通知实现**：
   - `LLMFuture` → `future.add_done_callback(lambda _: event.set())`；
   - `SpawnedTask` → `future.add_done_callback`；
   - `IbStreamHandle` → 消费线程 `finally` 置事件；
   - `HostAwaitable` → 引擎 spawn 完成钩子（子线程完成时通知，engine spawn 追踪补回调）；
   - `ChannelRecvWaitable` → `CommBuffer` 增完成回调表（`send`/`close` 时触发，与既有 Condition 平行，热路径开销极小）。

### 3.3 意义

同时根治：poll+park 的 ~1ms 延迟、"单待决阻塞优化"缺失、等待机制偏离主流。通知式唤醒是异步模型的普适形态。

### 3.4 验证

- 单任务 LLM/宿主/通道等待时无 park 延迟（真并发基准）；
- 多任务协作不因单 waitable 阻塞；
- 全量 pytest 零回归。独立分支 `exp/exec-rc`。

---

## 四、深度分析：R3 D-04 意图修复（`IbThread` 本体满足 Waitable）

### 4.1 现状问题

语言方法 `is_done()`（装箱 bool）与 Waitable 协议属性 `is_done`（Python bool）重名冲突 → 阶段 1b 用
`_ThreadJoinWaitable` 包装绕开，偏离 D-04"`IbThread` 满足 Waitable、`await t` 直接可用"，并留
"is_done 概念两形态"（语言方法 vs 协议属性）碎片化苗头。

### 4.2 根治设计（unify is_done 为单一来源）

1. `IbThread.is_done` 改为 **property（Python bool）** → 直接满足 Waitable 协议。
2. **axiom auto-bind 机制改造**（`primitive_initializer`）：当公理声明的语言方法在 Python 侧是 property 时，
   包装成"读 property + 装箱"的可调用原生方法 → 语言 `t.is_done()` 继续可用（返回装箱 bool）。**通用机制**，
   非 is_done 特判（机制同构）。
3. `IbThread` 本体加 `try_result`/`result`（完成=thread_result 容器，逻辑复用 `_make_result`）；`join()` 返回自身。
4. 删除 `_ThreadJoinWaitable` 包装；`await t` 直接可用（与 `asyncio.Task` / Rust `JoinHandle` 同形态）。

### 4.3 影响面

auto-bind 机制、IbThread、join 契约（宿主 `t.join()` 返回自身 waitable）、测试迁移。

---

## 五、深度分析：R4 P3 公开协议

`coordinator._run_task_body` 直写 `_cell._shared_with_main = True`（跨模块摸私有槽）→ 改为
`IbCell.mark_shared_with_main()` 公开方法（语义：标记该 cell 已共享给线程任务）。琐碎，无设计分支。

---

## 六、R5 撤回（诚实更正）

- **原判断**（上一轮汇报）：`await` 对非 waitable 幂等返回（no-op）"偏松，容易掩盖 bug"，建议改报错。
- **深度分析更正**：幂等是 **auto-yield 组合的承载**——`vm_handle_IbCall` 对 native 返回 Waitable 自动挂起
  （leaf.py:291-294），故 `await ihost.collect(h)` 的 `collect(h)` 已自动解析为 dict，`await <dict>` 幂等返回。
  将 await 对非 waitable 改报错会**破坏该文档化组合**（docstring：对 collect 的自动等待幂等）；运行时无法区分
  "曾是 waitable 已自动解析"与"从未是 waitable"。
- **结论**：**R5 撤回**，保留幂等语义。既有测试 `test_await_non_waitable_idempotent` 继续有效。

---

## 七、深度分析：R6 嵌套函数捕获语义（对齐 lambda / Python）

### 7.1 现状

- lambda：`_analyze_lambda_capture` 自动分析外层引用 → free_vars → 闭包 cell（自动捕获，只读/写均可）。
- 函数：`_analyze_function_nonlocal` 仅当 `nonlocal` 声明时填充 free_vars → 嵌套函数**连只读捕获都要写 `nonlocal`**，
  比 Python 严格（Python 只读捕获自动，`nonlocal` 仅用于写）。

### 7.2 定案：函数自动捕获外层只读引用

- **编译期**：`binding_analysis_pass` 对函数体做与 lambda 相同的自由变量引用分析（复用 `_collect_name_nodes` +
  `prior_symbol_bindings`），把外层只读引用自动纳入 `free_vars`（排除 intrinsic / 全局）；`nonlocal` 仍标记可写。
- **运行期**：`vm_handle_IbFunctionDef` 为 free_vars 建立 cell（只读捕获也能读最新值）；`nonlocal` 写路径不变。
- **行为变更**：原"引用外层局部未声明 nonlocal → 运行时 not defined"现变为"自动捕获可用"（修复性、加法，非破坏）。

### 7.3 意义

- 函数与 lambda 捕获机制**同构**（消除双轨语义不一致）。
- P3 隔离检查触发面回到审计预期宽度（任务写共享 cell 可被自然构造并拦截）。
- 对齐 Python 心智模型（读捕获自动、写需 nonlocal）。

### 7.4 验证

- 只读捕获（返回外层局部）/ 写捕获（nonlocal）/ lambda 与函数捕获一致；
- P3 触发场景（任务写共享 cell）在无 nonlocal 只读路径下依然拦截写；
- 全量 pytest 零回归。独立分支 `exp/exec-rb`。

---

## 八、D-08 定案：保留透明 async（不再重议）

**决策：保留"无 async fn 关键字、任意函数可 await"（透明 async）。**

论证：
1. **CPS VM 天然可挂起**：所有函数体已是可挂起生成器，无"协程/普通"二分的运行时约束——主流 async 标记是栈式
   运行时的技术约束产物，IBCI 无此约束。
2. **auto-yield 组合**：native 调用返回 Waitable 自动挂起（leaf.py），`c.recv()` / `collect(h)` 已透明等待；
   `await` 是显式等待补充，非主通道。
3. **值契约**：函数返回声明类型（值），非 future——调用方契约是值，挂起是执行细节；类型系统不承载挂起（与
   IBCI 值语义一致）。
4. **函数"种类"可见性由 `yield` 自标记**：含 `yield` 即生成器（惰性序列），关键字本身就是标记；await 透明。
5. **可维护性**：IBCI 面向 LLM 编排，程序整体异步化，透明挂起是常态而非例外。

**后果**：后续 `yield` 生成器设计不再需要 async 标记；`yield` 与 await 正交可组合（可挂起生成器）。

---

## 九、工作安排（顺序 / 分支 / 验证）

| 序 | 项 | 分支 | 性质 | 验证要点 |
|----|----|------|------|---------|
| 1 | R4 + R3 | `exp/exec-ra` | 小 | auto-bind property 包装、`await t`、`t.is_done()` 保留 |
| 2 | R6 | `exp/exec-rb` | 中 | 函数只读捕获、与 lambda 同构、P3 触发面 |
| 3 | R2 | `exp/exec-rc` | 中 | 通知式唤醒、无 park 延迟、多任务协作 |
| 4 | R1 | `exp/exec-rd` | 大 | trampoline、深递归恒定 Python 深度、线程体接轨 |

- 每批：独立分支实验 → 全量 pytest 零回归 → 手动 cherry-pick 应用 unsafe-vibe-dev（禁合并）。
- **后续路线**：批次完成后 → **阶段 4 PT-FEAT-9 诊断机制**（设计已冻结 `DIAGNOSTIC_DESIGN.md`，依赖全局事件总线已落地）
  → **阶段 5 `yield` 惰性生成器**（设计 `EXEC_FOUNDATION_DESIGN.md` §5.2）→ 增量（streaming / host async 改进）。

---

## 十、决策记录

| 日期 | 决策 | 依据 |
|------|------|------|
| 2026-08-07 | R1 根治（CPS trampoline）；R2 通知式唤醒；R3 unify is_done；R4 公开协议；R6 函数自动捕获 | 用户裁定彻底修复；机制同构；主流普适设计 |
| 2026-08-07 | **R5 撤回**（保留 await 幂等） | 深度分析：幂等承载 auto-yield 组合（`await collect(h)`），改报错破坏组合；运行时无法区分 |
| 2026-08-07 | **D-08 定案保留**透明 async | CPS 天然可挂起 + auto-yield + 值契约 + yield 自标记；不再重议 |
| 2026-08-07 | 批次顺序 R4+R3 → R6 → R2 → R1（各独立分支，禁合并，手动应用） | 小先大后；每批全量零回归 |
