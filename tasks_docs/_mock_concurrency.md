# LLM 并行化与状态重设计规划书

> **状态**：主线规划（取代旧 Phase 0-4 草案）。Phase A 启动前需完成"前置确认"项。
> **性质**：临时任务文档，全部 Phase 完成后删除，决策性内容并入 `docs/architecture/`。
> **关联**：`tasks_docs/NEXT_STEPS.md`（主线指针）、`tasks_docs/PENDING_TASKS.md` PT-4.7、`docs/KNOWN_LIMITS.md` §十五/§十七.6、`docs/architecture/05_vm_specification.md` §3。

---

## 一、背景与决策溯源

LLM 并行化工作此前搁置，根因是 **async 层级边界**无法定论：是否全栈转向（VM/解释器/语言级 async 关键字/原语/公理），还是仅 LLM 层面 async。

本次决断：
- **优先启动 LLM 层面 async 支持，暂不推进全体系完整 async 支持**（语言级 async 关键字/原语/公理列入 Phase D，暂搁置）。
- **状态模型重设计先行**：摒弃"上一次/最近一次"全局共享语义，状态绑定到执行单元。这是并行安全的根本，与 sync/async 无关，且是 async 的前置条件（共享状态下 async 只是换成协程竞争）。
- **分阶段推进**，每阶段独立可验证，避免"修竞争"与"换并发模型"耦合在大爆破里。

彻查确认的重设计触发缺陷：
- Bug-1：两条 llmexcept 路径对 `retry "hint"` 行为不一致（路径 A restore 清除 hint，路径 B 不清除）。
- Bug-2：`_call_llm` 的 `set_retry_hint` 是死代码。
- Bug-3：`ai.set_retry_hint()` 对 behavior 生效、对 llm 函数不生效。
- Bug-8：`if/while @~cond~: ... llmexcept:` 编译期接受但运行期不工作（IbIf/IbWhile 无条件 raise，不检查 llmexcept 帧）；文档 `10_robustness.md:20-27` 明确支持此语法。
- Bug-9：IbSwitch 条件 uncertain 时 silent return None（`control_flow.py:139-140`），与其它 handler 不一致。
- 缺陷-4：`provider._retry_hint` 持久不清零污染。
- 缺陷-5：`last_call_info` 双存储回退链死路径。
- 缺陷-6：retry_hint 子系统语义碎片化。
- 违规-7：MOCK 哨兵字符串比对（违反工作模式定论）。
- 语义缺陷：`_last_llm_result` 的"last/最近"语义在 LLM 并行化下天然歧义（调用序 vs 返回序 vs 定时器），是设计缺陷。

---

## 二、核心设计原则

1. **状态绑定到执行单元**：retry_hint 绑定到 LLMExceptFrame（per 重试循环），last_call_info 绑定到调用实例（LLMResult 携带），`_last_llm_result` 经返回值传递（不共享信号通道）。
2. **摒弃"上一次/最近一次"全局语义**：无全局"最近 LLM 调用"槽位。并发下"最近"无良定义。
3. **统一两条 llmexcept 路径**：frame 生命周期统一为"一个重试循环一个 frame，跨所有 retry 轮次存活"。
4. **worker 不触达共享可变状态**：dispatch 经 immutable snapshot 传参，worker 仅 HTTP+解析。
5. **质量优先于速度**：遵守 `NEXT_STEPS.md` "⛔ 工作模式定论"，禁止 compat shim / 胶水 / tricky 实现。

---

## 三、async 层级边界声明

| 层级 | 范围 | 本次决策 |
|---|---|---|
| 全体系 async（Phase D） | VM 43 handler + `_drive_loop`（`gen.send`->`asend`）+ 入口 + 语言级 async 关键字/原语/公理 | **暂搁置** |
| LLM 层面 async（Phase C） | FastAPI async MOCK server（独立线程事件循环）+ sync `OpenAI` client（含 sync stream iterator） | **本次推进** |
| client 侧 async（`AsyncOpenAI` + `async for`） | LLM client 异步流式 | **属 Phase D，暂搁置**（需 VM 桥接，不引入） |

**关键边界**：Phase C 不涉及 client 侧 async。sync client 的 `stream=True` 是阻塞 iterator，可满足 Phase 1 流式需求。client 侧 async 流式是 Phase D 范畴，需 VM async 化桥接，本次不做。

---

## 四、Phase A：状态模型重设计（sync，修复 Bug + 奠基并行安全）

### A1. 统一两条 llmexcept 路径的 frame 生命周期 + 重试机制

**改造**：
- `vm_handle_IbFor` 条件驱动路径改为复用同一 `LLMExceptFrame` 跨循环迭代（而非每次 uncertain 新建，`control_flow.py:226`）。统一为路径 A 模型：一个重试循环一个 frame。
- **IbFor 条件驱动升级为完整多轮重试**（当前是单次内联重试，无 restore_snapshot/integrity check，能力弱于 IbLLMExceptionalStmt）。提取共用重试循环骨架，两路径复用。
- frame 创建时机：条件驱动 for 的 frame 在首次条件求值前创建（当前是 uncertain 之后创建，首次条件不在帧保护内）。

**影响文件**：`core/runtime/vm/handlers/control_flow.py`、`core/runtime/vm/handlers/llm_behavior.py`、`core/runtime/interpreter/llm_except_frame.py`（共用骨架）。

### A2. retry_hint 绑定到 LLMExceptFrame

**改造**：
- 新增 `LLMExceptFrame.retry_hint: Optional[str] = None`（**持续覆盖**状态，不参与 save/restore，类似 `loop_resume`；`retry "hint"` 覆盖式，跨 retry 轮次存活直到被新 `retry "hint"` 覆盖或块结束）。
- `vm_handle_IbRetry`（`llm_behavior.py:394`）改为写 `frame.retry_hint`（而非 `context.retry_hint`）。
- `execute_behavior_expression` / `execute_llm_function`（`_behavior.py:104-111`、`_llm_function.py:55-75`）读取 retry_hint 改为查当前 llmexcept 帧的 `frame.retry_hint`（经 `runtime_context.get_current_llm_except_frame()`），废弃读 `context.retry_hint` 与回退 `provider._retry_hint`。
- llm 函数的 `__llmretry__` 回退（`_llm_function.py:64-65`）保留为 frame.retry_hint 为空时的静态回退。

**废弃**：
- `RuntimeContextImpl._retry_hint`（`runtime_context.py:309,494-500`）。
- `AIPlugin._retry_hint`（`ibci_ai/core.py:16`）。
- `LLMExceptFrame.saved_retry_hint`（`llm_except_frame.py:100,168-169,256-257`，save/restore 不再管 retry_hint）。
- `_call_llm` 的 retry_hint 处理（`_core.py:169-175`，Bug-2 死代码，删除）。

**消除**：Bug-1、Bug-2、Bug-3、缺陷-4、缺陷-6。

### A3. 废弃 `ai.set_retry_hint()`

**改造**：
- 移除 vtable 声明（`ibci_ai/_spec.py:34`）。
- 移除实现（`ibci_ai/core.py:313-314`）。
- 移除接口声明（`core/base/interfaces.py:69`）。
- 更新注释（`core/kernel/spec/member.py:70`）。

**影响面确认**：无测试直接调用（grep tests/ 无命中），无生产代码调用（`_core.py:175` 是 Bug-2 死代码，A2 已删除）。

### A4. last_call_info 去共享 + `ai.get_last_call_info()` 重定义

**改造**：
- `LLMResult` 扩展携带 call_info 字段（sys_prompt/user_prompt/response/intents）。
- `execute_behavior_expression` / `execute_llm_function` 不再写全局 `LLMExecutorCore.last_call_info`（`_behavior.py:154`、`_llm_function.py:127`），call_info 附在 LLMResult 上。
- 废弃 `LLMExecutorCore.last_call_info`（`_core.py:72`）与 `get_last_call_info` 回退链（`_core.py:120-130`，缺陷-5 死路径）。
- 废弃 `AIPlugin._last_call_info`（`ibci_ai/core.py:17`）与 `AIPlugin.get_last_call_info`（`:316-317`）。
- `ai.get_last_call_info()` 重定义：主线程在 resolve 时刻把 call_info 写入"最近 resolve"槽（单线程写，无竞争）。用户看到"最近一次完成解析的调用"，并发下由 resolve 顺序（程序语义序）决定，遵从公理 LLM-3。

**注意**：`get_last_call_info` 是 vtable 唯一用户面诊断 API（`_spec.py:35`），`get_last_llm_result` 非用户面（vtable 无）。重定义需保持该 API 可用。

**消除**：缺陷-5。

### A5. 重新设计 uncertain 信号传递 + 统一控制流 handler llmexcept 支持

**问题本质**（重新定位）：`_last_llm_result` 的"last/最近"语义在 LLM 并行化语境下天然歧义（调用序 vs 返回序 vs 定时器场景），是**设计缺陷**而非仅并行竞争。同时彻查发现 IbIf/IbWhile/IbSwitch/IbFor 对条件 uncertain 行为不一致（Bug-8/9），llmexcept 对条件语句支持不统一。

**改造方向**：
- 消除 `_last_llm_result` 全局"last"槽：certainty 绑定到特定 target 调用 / frame，非全局"最近"。
- 统一所有控制流 handler（if/while/for/switch）的 uncertain 处理：都应支持 llmexcept 重试（像 IbFor 那样检查 handler），消除 Bug-8（if/while 无条件 raise）/ Bug-9（switch silent）。
- certainty 经明确的、绑定的通道传递（frame 字段 / VMTask side-channel 等），**非破坏 VM 调度协议的信封**（评估确认信封解包会扩散到几乎所有表达式 handler）。

**方案设计（前置，frame 绑定）**：
certainty 经 `LLMExceptFrame.last_result` 传递（frame 绑定），消除全局 `_last_llm_result`。与 A2（retry_hint 绑 frame）同一范式--状态绑定到执行单元（frame）。
- **产生者**（LLM 调用 / is_truthy / IbCast）：uncertain 时，若有 llmexcept 帧则写 `frame.last_result`（经 `get_current_llm_except_frame()`，is_truthy/IbCast 已用此检查帧）；无帧则直接 raise LLMParseError（不需传递）。
- **消费者**（IbIf/While/For/Switch/Assign/llmexcept handler）：条件/RHS 求值后，检查当前帧的 `frame.last_result` 判断 uncertain（而非读全局 `_last_llm_result`）。
- **消除**：`RuntimeContext._last_llm_result` 全局槽（`runtime_context.py:340`）+ `set/get_last_llm_result` 接口。
- **不破坏 VM 调度协议**：certainty 经 frame 传递，不经 handler 返回值（无需信封）。
- **统一 llmexcept 支持**：if/while/for/switch 都检查帧，条件 uncertain 时有帧则交 llmexcept 处理、无帧则 raise（消除 Bug-8/9）。编译期绑定方式不改（正则情形 target=IbIf/While 即可，llmexcept 包装整个控制流语句作 target，执行时若条件 uncertain 写 frame.last_result，llmexcept handler 读）。
- **待验证细节**：frame.last_result 已存在（`llm_behavior.py:92`），当前是 llmexcept handler 读全局槽后存；改为产生者直接写 frame。**frame.last_result 存 LLMResult dataclass**（轻量内部类型，非 IbLLMCallResult；IbLLMCallResult 不再作 _last_llm_result 存储，idbg 适配读 LLMResult 字段）。**三条产生者路径必须同改**：IbBehaviorExpr（`llm_behavior.py:237`）、IbBehaviorInstance（`:286`）、`_finalize_invoke_result`（`_core.py:141`）。**引入 Uncertain 哨兵贯穿 leaf->consumer**：解决 is_truthy 在深层 leaf handler（IbBoolOp/IbCompare/IbIfExp）的 uncertain 传递链断裂（嵌套场景 `if a or b:` 中 a uncertain 时 frame.last_result 多次写入时序问题）。非 llmexcept 路径 IbBehaviorExpr uncertain 改为直接 raise（改变当前"返回 get_none 由父决定"行为），现有测试若体现该缺陷行为则更正。

**三类 uncertain 信号源**：
1. LLM 调用返回 uncertain（`_behavior.py` / `_llm_function.py`）。
2. `is_truthy` 模糊布尔判定（`interpreter.py:805-823`）。
3. 类型转换失败（`leaf.py:306-316`，`vm_handle_IbCast`）。

**Bug-8 修复**：IbIf/IbWhile 改为检查 llmexcept 帧（像 IbAssign `assignment.py:107-120`：帧内赋 Uncertain 哨兵由 llmexcept 处理，帧外 raise LLMParseError），而非无条件 raise。文档 `docs/syntax/10_robustness.md:20-27` 明确支持 `if @~cond~: ... llmexcept:` 语法。
**Bug-9 修复**：IbSwitch 统一为相同语义（消除 `control_flow.py:139-140` 的 silent return None）。

**影响面**：7 handler（IbIf/While/Switch/For/Assign/LLMExceptionalStmt/BehaviorExpr）+ is_truthy + IbCast + idbg。

**风险标注**：此项是 Phase A 中**设计难度最高**的一项--需设计新的 certainty 传递机制（替代全局槽）且不破坏 VM 调度协议。**启动前需专门的方案设计**（评估 frame 绑定 / VMTask side-channel / 其它方案的取舍）。可能需拆子阶段。

**消除**：`_last_llm_result` "last"语义歧义 + Bug-8 + Bug-9 + uncertain 处理不一致。

### A6. MOCK 哨兵字符串常量化

**改造**：
- `"__MOCK_REPAIR__"` / `"MAYBE_YES_MAYBE_NO_this_is_ambiguous"` 提取为常量（`ibci_ai/core.py` 与 `llm_executor/_behavior.py`/`_llm_function.py` 共享引用）。
- 收敛 TESTONLY 散落判定（`ibci_ai/core.py:83,159,197,355`）为单一 mock 注册口（报告 C 提议 5）。

**消除**：违规-7。

### A7. 死代码清除（工作模式定论"禁止半修复/技术债先清"）

**改造**：清除 `LLMExceptFrame` 的全部死代码（grep 确认无调用方）：
- `set_error`（`llm_except_frame.py:366`）、`reset_for_retry`（`:383`）、`get_retry_info`（`:394`）--无调用方。
- `error_history`（`:135`）、`last_error`（`:124`）、`last_llm_response`（`:125`）--仅在上述死方法中赋值/读取。

Phase A 改 frame 字段时必须同清，否则新旧并存。

### A8. "last" 命名变更（并行化友好命名）

**改造**：消除"last"命名的"最近"语义误导，改为绑定执行单元的命名：
- `frame.last_result` -> `frame.target_result`（target 调用的结果）。
- `last_target_value`（`llm_behavior.py:63`）-> `target_value`。
- `control_flow.py` 局部 `last`/`last_result` -> `uncertain_result` / `llm_signal`。
- `_shared.py` 的 `last_result` -> `seq_result`。
- **idbg 用户面方法名同步改名**（用户决策：接受破坏）：`last_llm` -> `current_llm`、`last_result` -> `current_result`、`show_last_prompt` -> `show_target_prompt`、`show_last_result` -> `show_target_result`（`ibci_idbg/_spec.py:21-25,46-62`、`core.py:75,114,182,227`）。idbg 文档同步更新。
- 全局共享"last"状态（`_last_llm_result`/`last_call_info`/`_last_call_info`）随 A4/A5 消除，无需改名（直接删除）。

### Phase A 验收
- 全量 `python -m pytest tests/`（基线以实跑为准；现有测试若体现缺陷/不适应未来设计则更正，非退化）。
- Bug-1/2/3/8/9 + 缺陷-4/5/6 + 违规-7 + `_last_llm_result` 语义缺陷消除。
- retry_hint / last_call_info / _last_llm_result 不再是 RuntimeContext/LLMExecutorCore 的共享可变字段（或"last"语义被显式绑定机制取代）。
- 死代码清除（A7）+ "last"命名变更（A8）。
- 新增针对性测试：retry "hint" 在两条路径下一致注入、if/while/for/switch 条件 uncertain 时统一支持 llmexcept（正则绑定回归，当前缺测试）、is_truthy 嵌套 uncertain 传递。
- 修正 `test_e2e_llmexcept.py:545-571` 误导性 docstring + 固化 Bug-8 行为的测试。

### 测试策略
- 现有测试一定程度上允许破坏：若体现错误/缺陷/不适应未来设计，及时更正（非退化）。
- `test_e2e_llmexcept.py:538-597`（TestE2EConditionUncertainBugA）固化 Bug-8 当前行为（if/while uncertain 无条件 raise），A5 修复后 if/while 在 llmexcept 帧内不再 raise；这些测试用 try/except 无帧，A5 后仍通过（无帧仍 raise），但需新增"if+llmexcept"正则绑定测试。
- `test_concurrent_llm.py` 9 项合规测试不直接依赖 _last_llm_result/last_call_info（grep 确认），A5 后应仍通过，须实跑验证。
- idbg 方法名改名（A8）需同步更新 idbg 测试。

---

## 五、Phase B：dispatch 修复（PT-4.7 闭合）

**前置**：Phase A 完成（状态已去共享，worker 拆分简单）。

### 改造
1. 拆分 `execute_behavior_expression`：主线程预求值 prompt 段（访问 VMExecutor）；worker 仅 `_call_llm(prompt)` + 解析（不重入 VMExecutor）。
2. retry_hint 在 dispatch 时刻主线程从 frame 读（dispatched 不在 llmexcept 帧内，故为 None），烘焙进 sys_prompt；worker 不触达 retry_hint。
3. call_info 经 LLMResult/future 回传，主线程 resolve 时处理。
4. 补 `BehaviorDependencyPass` 的 spec §3.1 规则（插值依赖/Cell/llmexcept 强制 `dispatch_eligible=False`，`behavior_dependency_pass.py:124`）。
5. `dispatch_eligible` 默认开启。

### Phase B 验收
- 全量 pytest 不退化。
- 解锁 4 项 dispatch 专属 skip：
  - `test_e2e_llm_pipeline.py::test_two_independent_assignments_both_pending_after_run`
  - `test_e2e_llm_basic.py::TestE2EStaleResultIsolation` ×3
- skip 数 8->4（仅剩 C 类 3 项结构债 + D 类 1 项平台）。
- 更新 `KNOWN_LIMITS §十五`（dispatch 不再禁用）、`PENDING_TASKS` PT-4.7（关闭）、`05_vm_specification.md §3`（并发调度启用）。

---

## 六、Phase C：MOCK 服务（FastAPI + 流式）

**前置**：Phase B 完成（dispatch 可用，需 MOCK 仪器验证并发）。

### 改造
1. FastAPI 构建 OpenAI 兼容 `/v1/chat/completions`（含流式 SSE），独立线程事件循环。
2. 可编程场景引擎（延迟/并发/失败/流式），统一场景词汇与进程内 MOCK DSL 共存（简单确定性测试保留进程内 DSL）。
3. 正式 mock 注册口（A6 已收敛 TESTONLY），`base_url` 指向本地服务。
4. sync `OpenAI` client 指向本地服务，走真实 HTTP（loopback socket、真超时）。
5. sync client `stream=True` 支持流式（阻塞 iterator）。
6. 补 `requirements` 文件（openai + fastapi + uvicorn 等测试依赖）。
7. pytest fixture（启停服务/端口分配/ai 指向）。

### Phase C 验收
- Phase 1 流式 SSE 支持。
- MOCK 仪器可模拟延迟/并发/失败/流式。
- 用 MOCK 服务验证 dispatch 并发时序、lazy resolve、`_pending_futures` 生命周期、retry 并发。

### 边界
- **不涉及 client 侧 async**（`AsyncOpenAI`）。client 保持 sync。
- FastAPI server 侧 async + sync client 跨线程 loopback HTTP，不污染 VM（VM 保持同步生成器）。

---

## 七、Phase D（暂搁置）：全栈 VM async + 语言级 async

**状态**：暂不推进。当 client 侧 async 流式（`AsyncOpenAI` + `async for` 并发）或语言级 async 关键字成为明确需求时启动。

**预估范围**：43 handler 改 `async def`、`_drive_loop` 改 `asend`/`athrow`、入口 `asyncio.run`、测试 `pytest-asyncio`、语言级 async 原语/公理。`frame.py` 的 ContextVar 已为此预留。

---

## 八、依赖与协同关系

```
Phase A（状态去共享）──奠基──> Phase B（dispatch 修复，PT-4.7）
                                      │
                                      └──需仪器──> Phase C（MOCK 服务）
                                                       │
                                                       └──（Phase D 暂搁置）
```

- **A 是 B 的前置**：状态未去共享则 worker 拆分后仍竞争。
- **B 是 C 的前置**：dispatch 可用才需 MOCK 仪器验证并发。
- **A 不依赖 C**：A 在进程内 MOCK DSL 下即可验证（虽 MOCK 无法验证提示词内容，`KNOWN_LIMITS §十七.6`）。
- **D 独立**：不阻塞 A/B/C。

---

## 九、风险与前置确认

### 启动 Phase A 前需确认（已确认 2026-07-31）
1. **A5 certainty 传递机制**：frame 绑定方案，frame.last_result 存 **LLMResult dataclass**（已决策）。三条产生者路径同改 + Uncertain 哨兵贯穿 leaf->consumer。
2. **A1 重试机制统一**：IbFor 条件驱动**升级完整多轮重试**（已决策），提取共用骨架。
3. **A2 retry_hint 语义**：**覆盖式**（已决策，改"累积"措辞为"持续覆盖"）。
4. **A3 set_retry_hint 同步删**：vtable（`_spec.py:34`）+ Protocol（`interfaces.py:69`）+ 实现 + 死代码调用。
5. **A7 死代码清除**：set_error/reset_for_retry/get_retry_info/error_history/last_error/last_llm_response（已决策，新增 A7）。
6. **A8 命名变更**：含 idbg 用户面方法名同步改名（已决策，接受破坏）。
7. **`ai.get_last_call_info()` 重定义**：确认"最近 resolve 的调用"语义可接受。

### 待跟踪项
- `get_retry_prompt` / `_retry_prompts`（按 node_type 分类的通用重试提示词，`ibci_ai/core.py:39`）与 retry_hint 是不同机制，不在本次废弃范围，但 Phase A 需确认两者不冲突。
- `IbLLMCallResult`（`sentinels.py:89-140`）：A5 后不再作 _last_llm_result 存储，frame.last_result 存 LLMResult。IbLLMCallResult 是否仍需存在（未来 llmexcept 接收结果容器的预留）待评估，当前保留。
- `_expected_type_stack`（`_core.py:73`）：LLMExecutor 实例级全局共享，当前安全（dispatch 路径不 push），并行化下潜在竞争。Phase A 外的后续技术债，建议后续绑 frame。
- `__llmretry__`（`_llm_function.py:64-65`）：首次调用（非 retry）也注入，文案"上一次执行失败"误导。既有设计问题，A2 不引入新问题，需文档注明实际是"持续提示"。
- MOCK 哨兵 `MAYBE_YES_MAYBE_NO_THIS_IS_AMBIGUOUS`（大写）在 `enum.py:88` 也有耦合（枚举解析 pass-through），A6 常量化须同步。
- `LLMFuture` 不确定路径（`leaf.py:77-84`）：A5 须覆盖 dispatch-before-use 的 lazy resolve 不确定信号走帧。

---

## 十、进度追踪

| Phase | 状态 | 备注 |
|---|---|---|
| A 状态模型重设计 | ⬜ 待启动 | 前置已确认，含 A1-A8 |
| B dispatch 修复 | ⬜ | PT-4.7，依赖 A |
| C MOCK 服务 | ⬜ | FastAPI + 流式，依赖 B |
| D 全栈 async | ⏸ 暂搁置 | 语言级 async，未来需求驱动 |

---

## 十一、关联

- PT-4.7：`tasks_docs/PENDING_TASKS.md` §三
- dispatch 禁用现状：`docs/KNOWN_LIMITS.md` §十五
- MOCK 提示词验证限制：`docs/KNOWN_LIMITS.md` §十七.6
- 工作模式定论：`tasks_docs/NEXT_STEPS.md` "⛔ 工作模式定论"
- VM 规范 §3（并发调度）：`docs/architecture/05_vm_specification.md`
- 代码注释卫生：`docs/README.md` §三.6
