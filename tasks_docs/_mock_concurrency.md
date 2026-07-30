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

彻查确认的重设计触发缺陷（详见 git 历史的 `_retry_hint_audit.md`）：
- Bug-1：两条 llmexcept 路径对 `retry "hint"` 行为不一致（路径 A restore 清除 hint，路径 B 不清除）。
- Bug-2：`_call_llm` 的 `set_retry_hint` 是死代码。
- Bug-3：`ai.set_retry_hint()` 对 behavior 生效、对 llm 函数不生效。
- 缺陷-4：`provider._retry_hint` 持久不清零污染。
- 缺陷-5：`last_call_info` 双存储回退链死路径。
- 缺陷-6：retry_hint 子系统语义碎片化。
- 违规-7：MOCK 哨兵字符串比对（违反工作模式定论）。

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

### A1. 统一两条 llmexcept 路径的 frame 生命周期

**改造**：`vm_handle_IbFor` 条件驱动路径（`control_flow.py:198-283`）改为复用同一 `LLMExceptFrame` 跨循环迭代（而非每次 uncertain 新建，`:226`）。统一为路径 A（`vm_handle_IbLLMExceptionalStmt`）模型：一个重试循环一个 frame。

**影响文件**：`core/runtime/vm/handlers/control_flow.py`、`core/runtime/vm/handlers/llm_behavior.py`（确认两路径语义对齐）。

### A2. retry_hint 绑定到 LLMExceptFrame

**改造**：
- 新增 `LLMExceptFrame.retry_hint: Optional[str] = None`（累积状态，不参与 save/restore，类似 `loop_resume`）。
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

### A5. `_last_llm_result` 去共享（经返回值传递）

**改造**：target handler 返回值携带 LLMResult（或 certainty 标志），控制流 handler 从 `yield` 返回值读 certainty，不经共享 `_last_llm_result` 通道。

**三类 uncertain 信号源需全覆盖**：
1. LLM 调用返回 uncertain（`_behavior.py` / `_llm_function.py`）。
2. `is_truthy` 模糊布尔判定（`interpreter.py:805-823`）。
3. 类型转换失败（`leaf.py:306-316`，`vm_handle_IbCast`）。

**影响面**（7 handler + is_truthy + IbCast + idbg）：
- 写入点：`llm_behavior.py:74,85,237,282,286`、`assignment.py:38`、`control_flow.py:53,71,136,213`、`leaf.py:310`、`interpreter.py:817`、`_core.py:141`。
- 读取点：`llm_behavior.py:84`、`assignment.py:107`、`control_flow.py:55,73,138,217`、`ibci_idbg/core.py:102,237`。

**风险标注**：此项涉及 VM 调度协议的 handler 返回值约定，影响面大。Phase A 启动前需单独评估破坏面，可能需拆为子阶段 A5.1/A5.2。`ibci_idbg` 调试器读取路径需单独适配。

**消除**：`_last_llm_result` 共享竞争（并行安全奠基）。

### A6. MOCK 哨兵字符串常量化

**改造**：
- `"__MOCK_REPAIR__"` / `"MAYBE_YES_MAYBE_NO_this_is_ambiguous"` 提取为常量（`ibci_ai/core.py` 与 `llm_executor/_behavior.py`/`_llm_function.py` 共享引用）。
- 收敛 TESTONLY 散落判定（`ibci_ai/core.py:83,159,197,355`）为单一 mock 注册口（报告 C 提议 5）。

**消除**：违规-7。

### Phase A 验收
- 全量 `python -m pytest tests/` 不退化（基线以实跑为准）。
- Bug-1/2/3 + 缺陷-4/5/6 + 违规-7 消除（新增针对性测试验证 retry "hint" 在两条路径下一致注入）。
- retry_hint / last_call_info / _last_llm_result 不再是 RuntimeContext/LLMExecutorCore 的共享可变字段。

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

### 启动 Phase A 前需确认
1. **A5（`_last_llm_result` 去共享）破坏面评估**：handler 返回值协议改造影响 7 handler + is_truthy + IbCast + idbg。需单独评估是否拆子阶段，或是否有更局部的替代方案（如保留 `_last_llm_result` 但限定主线程访问，Phase B worker 不触达）。
2. **`ai.get_last_call_info()` 重定义的用户面语义**：确认"最近 resolve 的调用"语义可接受（并发下非严格"最近 HTTP"）。

### 待跟踪项
- `get_retry_prompt` / `_retry_prompts`（按 node_type 分类的通用重试提示词，`ibci_ai/core.py:39`）与 retry_hint 是不同机制，不在本次废弃范围，但 Phase A 需确认两者不冲突。
- `IbLLMCallResult`（`sentinels.py:89-140`）与 last_call_info 的关系：IbLLMCallResult 是 llmexcept 结果容器（is_certain/value/retry_hint），last_call_info 是诊断 dict（sys_prompt 等）。两者独立，A4/A5 改造需保持 IbLLMCallResult 语义不变。

---

## 十、进度追踪

| Phase | 状态 | 备注 |
|---|---|---|
| A 状态模型重设计 | ⬜ 待启动 | 前置确认 A5 破坏面后启动 |
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
