# LLM 并行化与状态重设计规划书

> **状态**：主线规划。Phase A 统一重构基本完成（U1-U7），剩余文档收尾与命名审查。
> **性质**：临时任务文档，全部 Phase 完成后删除，决策性内容并入 `docs/architecture/`。
> **关联**：`tasks_docs/NEXT_STEPS.md`、`tasks_docs/PENDING_TASKS.md` PT-4.7、`docs/KNOWN_LIMITS.md` §十五/§十七.6、`docs/architecture/05_vm_specification.md` §1.1/§3/§5。

---

## 一、背景与决策溯源

LLM 并行化工作此前搁置，根因是 async 层级边界（全栈 vs LLM 层面）与 llmexcept 机制统一性问题。

### 本轮决断

1. **async 层级**：优先 LLM 层面 async（FastAPI server），暂不推进全体系语言级 async（Phase D 暂搁置）。
2. **状态模型重设计**：摒弃"上一次/最近一次"全局共享语义，状态绑定到执行单元。
3. **llmexcept 机制统一**（本轮新增决断）：彻查发现当前存在**两种 llmexcept 绑定机制**（正则包装 `IbLLMExceptionalStmt` vs 条件驱动 for 内联 `llmexcept_handler`），是历史演进产物而非设计意图。两种机制导致 frame 创建时机不一致、certainty 传递无法统一、产生者依赖消费者 frame 状态等架构裂缝。**决断：彻底统一为单一机制**，消除 `IbLLMExceptionalStmt` 包装，禁止语法糖兼容展开，不留历史包袱。

### 已确认的缺陷清单（彻查取证）

- Bug-1：两条 llmexcept 路径对 `retry "hint"` 行为不一致（路径 A restore 清除 hint，路径 B 不清除）。**根因：两种绑定机制的 frame 生命周期不一致。**
- Bug-2：`_call_llm` 的 `set_retry_hint` 是死代码（已清除）。
- Bug-3：`ai.set_retry_hint()` 对 behavior 生效、对 llm 函数不生效（已清除）。
- Bug-8：`if/while @~cond~: ... llmexcept:` 编译期接受但运行期不工作（IbIf/IbWhile 无条件 raise，不检查 llmexcept）。**根因：正则包装机制下 IbIf 作为 target 被 IbLLMExceptionalStmt 驱动，但 IbIf 内部无条件 raise，绕过 llmexcept。**
- Bug-9：IbSwitch 条件 uncertain 时 silent return None，与其它 handler 不一致。**同 Bug-8 根因。**
- Bug-10（本轮新识别）：两种 llmexcept 绑定机制本身就是架构缺陷--本质统一的异常处理机制不应有两种实现。
- 缺陷-4：`provider._retry_hint` 持久不清零污染（已清除）。
- 缺陷-5：`last_call_info` 双存储回退链死路径。
- 缺陷-6：retry_hint 子系统语义碎片化（已清除）。
- 违规-7：MOCK 哨兵字符串比对（已清除）。
- 语义缺陷：`_last_llm_result` 的"last/最近"语义在 LLM 并行化下天然歧义。

---

## 二、核心设计原则

1. **llmexcept 机制统一**：消除两种绑定，统一为 `llmexcept_handler` 挂载 + 被保护语句内联处理 uncertain。禁止 `IbLLMExceptionalStmt` 包装，禁止语法糖兼容展开。
2. **状态绑定到执行单元**：retry_hint 绑定到 LLMExceptFrame；certainty 经 `IbLLMCallResult` 返回值传递（产生者不依赖 frame）；call_info 绑定到 LLMResult。
3. **摒弃"上一次/最近一次"全局语义**：无全局"最近 LLM 调用"槽位。
4. **产生者不依赖消费者状态**：产生者只产生结果（`IbLLMCallResult`），不访问消费者的 frame。架构解耦。
5. **质量优先于速度**：遵守 `NEXT_STEPS.md` "⛔ 工作模式定论"，禁止 compat shim / 胶水 / tricky 实现。已确认的历史遗留问题彻底处理，不留包袱。

---

## 三、async 层级边界声明

| 层级 | 范围 | 决策 |
|---|---|---|
| 全体系 async（Phase D） | VM 43 handler + `_drive_loop` + 语言级 async 关键字/原语/公理 | **暂搁置** |
| LLM 层面 async（Phase C） | FastAPI async MOCK server（独立线程事件循环）+ sync `OpenAI` client | **本次推进** |
| client 侧 async（`AsyncOpenAI`） | LLM client 异步流式 | **属 Phase D** |

---

## 四、Phase A：状态模型重设计 + llmexcept 机制统一

### 已完成项（5 commit，全程 1186 passed, 8 skipped 不退化）

| 项 | 内容 | 消除 |
|---|---|---|
| A7 ✅ | 死代码清除（`set_error`/`error_history`/`last_error`/`last_llm_response` 等 6 项无调用方） | 技术债 |
| A1 ✅ | IbFor 条件驱动升级完整多轮重试 + frame 复用（统一重试能力的 IbFor 部分） | 重试能力不对等 |
| A2 ✅ | retry_hint 绑 LLMExceptFrame（持续覆盖，不参与 save/restore） | Bug-1/2/3 + 缺陷-4/6 |
| A3 ✅ | 废弃 `ai.set_retry_hint()` + 清理 `_retry_hint`（vtable/Protocol/实现/接口） | API 废弃 |
| A6 ✅ | MOCK 哨兵字符串常量化（`MOCK_REPAIR_SENTINEL`/`MOCK_AMBIGUOUS_SENTINEL`，含 enum.py 边界处理） | 违规-7 |

### 待完成：统一 llmexcept 机制（U1-U7，取代旧 A4+A5）

> **核心**：消除两种 llmexcept 绑定机制，统一为 `llmexcept_handler` 挂载 + 内联重试。certainty 经 `IbLLMCallResult` 返回值传递，产生者不依赖 frame。

#### U1. 统一编译期绑定（消除 IbLLMExceptionalStmt 包装）

**改造** `core/compiler/semantic/passes/binding_analysis_pass.py`：
- 消除正则情形的 `stmt.target = prev_stmt` + `new_body.pop()/append` 包装逻辑（当前 `:183-205`）。
- **所有 llmexcept 统一为 `prev_stmt.llmexcept_handler = stmt` 挂载**，无论被保护语句是赋值/if/while/for/switch/表达式语句。
- `IbLLMExceptionalStmt` 节点类型不再生成（llmexcept 语句本身挂载到被保护语句，不从 body 中移除）。
- `llmretry` 语法糖（`@~...~ llmretry "hint"`）在统一框架下设计：编译期展开为被保护语句 + llmexcept_handler（含 `retry "hint"` body），**不做兼容展开**，直接融入统一机制。

**影响文件**：`binding_analysis_pass.py`、`core/compiler/parser/components/statement.py`（llmretry 解析）、`core/kernel/ast.py`（IbLLMExceptionalStmt 节点定义评估）。

**消除**：Bug-10（两种绑定机制）、IbLLMExceptionalStmt 包装节点。

#### U2. 统一运行期内联重试（各语句 handler 处理 uncertain）

**改造**：各被保护语句 handler（IbAssign/IbIf/IbWhile/IbFor/IbSwitch/IbExprStmt）内联处理 uncertain：
- 求值条件/RHS 后，检查返回值是否 `IbLLMCallResult(is_certain=False)`。
- 有 `llmexcept_handler`：创建 `LLMExceptFrame` + 执行 handler body + 完整多轮重试（restore_snapshot + verify + increment，与 A1 的 IbFor 模式对齐）。
- 无 `llmexcept_handler`：raise `LLMParseError`（从 `IbLLMCallResult` 读 retry_hint/raw_response）。
- 提取共用辅助函数 `_handle_llm_uncertain(executor, value, handler_uid, max_retry, ...)` 避免重复。
- IbFor 条件驱动保留 A1 的完整多轮重试（已实现），适配为从 `IbLLMCallResult` 检查（而非 `get_last_llm_result`）。

**废弃** `vm_handle_IbLLMExceptionalStmt`（`core/runtime/vm/handlers/llm_behavior.py:20-130`）。

**影响文件**：`llm_behavior.py`、`control_flow.py`、`assignment.py`、`_shared.py`、`leaf.py`（IbExprStmt）。

**消除**：Bug-8（if/while llmexcept 不工作）、Bug-9（switch silent）。

#### U3. certainty 经 IbLLMCallResult 返回值传递

**设计**（`sentinels.py:110` 已预见"llmexcept 接收 IbLLMCallResult"）：
- **产生者**（`vm_handle_IbBehaviorExpr`/`_finalize_invoke_result`/`vm_handle_IbBehaviorInstance`）uncertain 时返回 `IbLLMCallResult(is_certain=False, raw_response=..., retry_hint=...)`。不写 frame，不 `set_last_llm_result`，不 raise。
- **is_truthy** uncertain 时返回 `IbLLMCallResult(is_certain=False, ...)`（而非 False + 写 `_last_llm_result`）。
- **IbCast** 失败时返回 `IbLLMCallResult(is_certain=False, ...)`。
- **消费者**从返回值检查 uncertain（`_is_llm_uncertain_value` 检查 `IbLLMCallResult` 且 `is_certain=False`），创建 frame 时写 `frame.target_result = IbLLMCallResult`。
- `IbLLMUncertain` 保留为变量赋值标记（IbAssign 在 llmexcept 帧内赋 `IbLLMUncertain` 给变量），与 `IbLLMCallResult`（内部传递容器）角色分离。

**消除**：`_last_llm_result` 全局槽语义歧义 + 产生者对 frame 的依赖（架构解耦）。

#### U4. 消除 `_last_llm_result` + `last_call_info` 去共享

**消除 `_last_llm_result`**：
- 废弃 `RuntimeContextImpl._last_llm_result`（`runtime_context.py:340`）+ `set/get/clear_last_llm_result` 接口。
- 废弃 `RuntimeContextImpl.set_last_llm_result` 中 LLMResult->IbLLMCallResult 转换逻辑（IbLLMCallResult 现由产生者直接构造返回）。
- 废弃所有 `set_last_llm_result`/`get_last_llm_result` 调用点（U2/U3 改造中一并清除）。

**last_call_info 去共享**：
- `LLMResult.call_info` 字段已添加（步骤1已提交）。
- 产生者构造 LLMResult 时附 call_info（sys_prompt/user_prompt/response/intents），不再写全局 `LLMExecutorCore.last_call_info`。
- 废弃 `LLMExecutorCore.last_call_info`（`_core.py:72`）+ `get_last_call_info` 回退链（`:120-130`）。
- 废弃 `AIPlugin._last_call_info`（`ibci_ai/core.py:17`）+ `get_last_call_info`（`:316`）。
- `ai.get_last_call_info()` 重定义：返回"最近 resolve 的调用"的 call_info（主线程单写槽，无并行竞争）。

**消除**：缺陷-5（last_call_info 死路径）+ `_last_llm_result` 语义缺陷。

#### U5. 命名变更（"last" -> 并行化友好命名）

- `frame.last_result` -> `frame.target_result`（certainty 信号载体）。
- `last_target_value` -> `target_value`。
- 局部变量 `last`/`last_result` -> `uncertain_result`/`target_result`。
- `_shared.py` 的 `last_result` -> `seq_result`。
- idbg 用户面方法名同步改名：`last_llm`->`current_llm`、`last_result`->`current_result`、`show_last_prompt`->`show_target_prompt`、`show_last_result`->`show_target_result`（`ibci_idbg/_spec.py` + `core.py`）。
- `ai.get_last_call_info` -> `ai.get_current_call_info`（`ibci_ai/_spec.py` vtable）。
- 全局"last"状态（`_last_llm_result`/`last_call_info`/`_last_call_info`）随 U4 消除，无需改名（直接删除）。

#### U6. idbg 适配 + 接口清理

- `ibci_idbg/core.py` 适配：读 `frame.target_result` / `_recent_call_info`（U4 重定义），方法名改名（U5）。
- `IStateReader.get_last_llm_result`（`base/interfaces.py:54`）/ `IExecutionFrame.get_last_llm_result`（`:169`）废弃或重定义。
- `ILLMProvider.set_retry_hint`（已删 A3）/ `ILLMExecutor.get_last_call_info`（保留，语义变）。
- `runtime/interfaces.py` 的 `retry_hint` property 接口（已删 A3）。
- `tests/runtime/test_idbg.py` mock 适配。

#### U7. 公理 EXEC-3 更新 + 文档同步

- 更新 `docs/architecture/05_vm_specification.md` §1.1 公理 EXEC-3：从"两种绑定"改为"统一 llmexcept_handler 挂载 + 内联驱动"。
- 更新 `docs/syntax/10_robustness.md`：llmexcept 机制描述（统一语义）。
- 更新 `docs/KNOWN_LIMITS.md` §十五/§十七.6（如涉及）。
- 更新 `docs/architecture/04_vm_interpreter.md`（如涉及 llmexcept 描述）。

### Phase A 验收
- 全量 `python -m pytest tests/`（现有测试若体现缺陷/不适应未来设计则更正，非退化）。
- Bug-1/2/3/8/9/10 + 缺陷-4/5/6 + 违规-7 + `_last_llm_result` 语义缺陷全部消除。
- llmexcept 统一为单一机制（无 `IbLLMExceptionalStmt` 包装，无两种绑定）。
- retry_hint / call_info / certainty 不再是全局共享可变字段。
- 新增针对性测试：if/while/for/switch + llmexcept 统一回归、retry "hint" 一致注入、is_truthy 嵌套 uncertain 传递。
- 修正 `test_e2e_llmexcept.py:545-571` 误导性 docstring + 固化 Bug-8 行为的测试。
- 公理 EXEC-3 更新。

### 测试策略
- 现有测试允许破坏：体现缺陷/不适应未来设计则更正。
- `test_e2e_llmexcept.py:538-597`（TestE2EConditionUncertainBugA）固化 Bug-8 当前行为，U2 修复后需更正 + 新增 if+llmexcept 正则绑定测试（当前缺）。
- `test_concurrent_llm.py` 9 项合规测试不直接依赖 `_last_llm_result`/`last_call_info`，U4 后应仍通过，须实跑验证。
- idbg 方法名改名（U5）需同步更新 idbg 测试。

---

## 五、Phase B：dispatch 修复（PT-4.7 闭合）

**前置**：Phase A 完成（状态去共享 + llmexcept 统一）。

### 调研微调（真实代码复核，2026-07-31）

接通前置经真实代码复核，规划需以下微调：

1. **spec §3.1 新增第 4 条强制规则：可重复执行上下文**。循环体 / 可重入函数内的同一 `node_uid` 多次 dispatch 会覆写 `_pending_futures[node_uid]`，旧 Future 泄漏且读点解析到错误 Future。当前 pass 未实现任何 §3.1 规则（只检测环），须一并补上。
2. **dispatch 路径 uncertain 容器与统一机制对齐**：`resolve`/`LLMFuture.get` 应返回 `IbLLMCallResult(is_certain=False)`（而非旧 `IbLLMUncertain` 哨兵），`vm_handle_IbName` 读点统一走 `_is_llm_uncertain_value` + `_raise_uncertain_parse_error`（保留 retry_hint/raw_response，当前 raise 时 raw_response 为空）。
3. **`_finalize_call` 分解**：拆为"绑定 call_info 到 result"（worker 可做）+ "记录主线程槽 `_current_call_info`"（仅 sync 尾部 / resolve 点）。worker 线程禁止写主线程槽。
4. **dispatch 主线程预求值复用 sync `_evaluate_segments`**：同线程 `vm.run` 嵌套 drive_loop 安全（`_drive_loop` 保存/恢复 `_current_stack`），不 CPS 化。
5. **call_info 元数据主线程烘焙**：`context.get_global_intents()` 在 prepare 阶段读取并烘焙进元数据，worker 不再读 live context。
6. **`fork_intent_snapshot` 失败 fail-fast**：当前静默回退 `intent_ctx=None` 会让 worker 走 lambda 模式读 live context（含 `consume_smear` 消费副作用），违背工作模式定论。
7. **未 resolve Future 泄漏观测性**：`_pending_futures` 条目程序结束残留，补结束断言/显式清理。
8. **`_result_parser` 惰性初始化竞争**：worker 并发首解析双初始化，改水化时预建。

### 改造
1. 拆分 `execute_behavior_expression`：主线程 `_prepare`（预求值 prompt + 意图 + output hint + retry_hint + call_info 元数据）；worker 仅 `_call_llm` + 解析（不重入 VMExecutor，不写主线程槽）。
2. retry_hint 在 dispatch 时刻主线程从 frame 读（dispatched 不在 llmexcept 帧内，故为 None），烘焙进 sys_prompt。
3. call_info 经 LLMResult 回传，主线程 resolve 时写 `_current_call_info` 并处理 uncertain 容器。
4. 修 `BehaviorDependencyPass` 实现 spec §3.1 规则（插值依赖/Cell/llmexcept/可重复执行上下文），删除"一律 False"硬编码。
5. `dispatch_eligible` 按规则判定开启（`ast.py` 默认值 `False` 保留为安全默认）。
6. MOCK 并发确定性：seq/retry 计数加锁；**已被 B0-Mock 服务化吸收**（`MockScenarioEngine` RLock + 服务按请求隔离状态）。

### 验收
- 解锁 4 项 dispatch 专属 skip（`test_e2e_llm_pipeline.py` ×1 + `test_e2e_llm_basic.py::TestE2EStaleResultIsolation` ×3）。
- skip 数 8->4。
- 更新 `KNOWN_LIMITS §十五`、`PENDING_TASKS` PT-4.7、`05_vm_specification.md §3`。

### §五.1 MOCK 服务化与 Phase B 的次序（决策点）

> 调研发现规划内部不一致：PT-4.7 声明"MOCK 服务化（独立进程 HTTP 服务，模拟延迟/并发/失败）作为开发仪器，协同修复 dispatch 数据竞争"，但阶段依赖图把 C 排在 B 之后。Phase B 验收要求"补'插值 + 真实并发'合规测试（不验真实并发时序）"，而现有内联 MOCK（纯函数、零延迟控制、零失败注入、共享插件状态非线程安全、TESTONLY 判定散落 4 处、`_scene_prompts` 死字段、服务化依赖 openai/fastapi/uvicorn/httpx 全部未安装）无法提供该验证能力。

**决策选项**：
- **选项 A（MOCK 服务化提前，作为 Phase B0 开发仪器）**：先建服务主体（场景引擎 + 延迟 + 失败注入 + 请求级状态隔离 + OpenAI 兼容协议），再实施 §五 改造项 1-5，验收以服务为后端。符合 PT-4.7 原声明；一次性清 mock 子系统技术债；并发时序可观测。代价：引入服务依赖（openai + fastapi/uvicorn），改变项目零第三方依赖现状（需决策依赖策略：强制 vs 可选 skip）。
- **选项 B（保持 B→C 次序）**：内联 MOCK 加锁 + 值正确性验证先行，真实并发时序验证延后到 Phase C。风险：B 的"并发"属性无法在验收中实测，dispatch 可能静默串行化而不被发现。
- **选项 C（内联 MOCK 最小硬化 + 服务化并行推进）**：两轨并存，值场景留内联（258 处 MOCK 用法不迁移），机制/时序/失败场景用服务。工作量大但破坏面最小。

**已决策（B0 执行）**：采用选项 A+C 融合——**MOCK 服务化提前为 Phase B0 开发仪器**，值场景保留内联 MOCK（不迁移既有用法）。服务实现要点：
- **线程内 `ThreadingHTTPServer`**（非独立进程）：wire 行为与子进程一致，测试编排免端口协调/生命周期管理；服务器类可被子进程方式复用。
- **stdlib `http.server`**（无 fastapi/uvicorn）：依赖面保持仅 `openai`，配合环境正规化（pyproject 分组 + conda env）。
- **含 SSE 流式端点**（Phase C 原承诺一并落地）。
- **TESTONLY 判定收敛**：`_is_test_config` 统一 4 处散落比对。
- **指令语言单点真理**：`MockScenarioEngine`（`ibci_modules/ibci_ai/mock_scenario.py`）从 `_handle_mock_response` 提取，内联/服务共用；扩展控制指令 `SLEEP:<ms>`/`ERROR:<status>`。
- 环境正规化（B0-Env）：`pyproject.toml` 依赖分组 + `environment.yml` conda 环境 + `docs/guide/00_environment.md` + CI 统一安装。

---

## 六、Phase C：MOCK 服务（FastAPI + 流式）

> **状态：主体已被 B0-Mock 吸收落地**（作为 Phase B 开发仪器提前启动）。原设计的技术选型（FastAPI 独立进程）调整为 stdlib `ThreadingHTTPServer` 线程内服务，五项改造逐一对应：① OpenAI 兼容 `/v1/chat/completions` + SSE 流式 → `MockServer`；② 可编程场景引擎 → `MockScenarioEngine`（延迟 `SLEEP`/失败 `ERROR`/并发统计）；③ 正式 mock 注册口 → `AIPlugin._is_test_config` 收敛；④ sync `OpenAI` client 指向本地服务 → 服务接入模式；⑤ requirements → `pyproject.toml` 依赖分组 + `environment.yml`。

### 边界
- 不涉及 client 侧 async（`AsyncOpenAI`）。VM 保持 sync。SSE 端点已就绪，其 `AsyncOpenAI` 消费方属 Phase D。

---

## 七、Phase D（暂搁置）：全栈 VM async + 语言级 async

当 client 侧 async 流式或语言级 async 关键字成为需求时启动。`frame.py` 的 ContextVar 已为此预留。

---

## 八、依赖与协同

```
Phase A（状态去共享 + llmexcept 统一）──奠基──> Phase B（dispatch 修复）
   │                                             ▲
   └──> B0（环境正规化 + MOCK 服务化）──开发仪器──┘
                                                      
Phase C（MOCK 服务）主体已被 B0-Mock 吸收
Phase D（全栈 async）暂搁置
```

- U1（编译期统一）是 U2（运行期统一）的前置。
- U3（certainty 经返回值）是 U2（消费者检查返回值）的前置。
- U4（消除全局槽）依赖 U2/U3（消费者不再读全局槽）。
- U5/U6 可与 U2-U4 并行或之后。
- U7 在 U1-U6 完成后。

---

## 九、风险与待跟踪项

### 启动 U1-U7 前已确认
- frame.target_result 存 IbLLMCallResult（已决策）。
- IbFor 升级完整多轮重试（已决策，A1 完成）。
- retry_hint 覆盖式（已决策，A2 完成）。
- idbg 方法名同步改名（已决策，接受破坏）。
- llmretry 语法糖在统一框架下设计，不做兼容展开（已决策）。

### 待跟踪
- `get_retry_prompt`/`_retry_prompts`（按 node_type 分类的通用重试提示词）与 retry_hint 不同机制，不在废弃范围。
- `_expected_type_stack`（`_core.py:73`）：LLMExecutor 实例级全局，并行化下潜在竞争，Phase A 外后续技术债。
- `__llmretry__`（llm 函数定义的 retry_hint）：首次调用也注入，既有设计问题，需文档注明。
- MOCK 哨兵 `enum.py` 局部镜像常量（A6 处理）。
- `IbLLMUncertain` 保留为变量赋值标记，与 `IbLLMCallResult`（内部传递容器）角色分离。

---

## 十、进度追踪

| Phase | 状态 | 备注 |
|---|---|---|
| A 已完成项 | ✅ | A7/A1/A2/A3/A6（5 commit） |
| A U1 统一编译期 | ✅ | ast.py 5 节点加 llmexcept_handler + binding_analysis_pass.py 统一挂载 |
| A U2 统一运行期内联重试 | ✅ | 各语句 handler 内联，废弃 vm_handle_IbLLMExceptionalStmt |
| A U3 certainty 经 IbLLMCallResult | ✅ | 产生者返回容器，不依赖 frame |
| A U4 消除 _last_llm_result + last_call_info | ✅ | _last_llm_result 全局槽消除；last_call_info 去共享（call_info 绑 LLMResult + 主线程单写槽） |
| A U5 命名变更 | 🔶 部分 | frame.last_result→target_result、executor/ai/idbg 方法改名已做；帧内局部变量名待审 |
| A U6 idbg 适配 + 接口清理 | ✅ | 读 frame.target_result；IStateReader/IExecutionFrame 接口重定义 |
| A U7 公理 EXEC-3 更新 + 文档 | 🔶 部分 | EXEC-3/IC-3 + 04_vm_interpreter + KNOWN_LIMITS 已更新；语法/子系统文档同步 |
| B0-Env 环境与依赖正规化 | ✅ | pyproject.toml 分组 + environment.yml + 00_environment.md + CI 统一安装 + ibci_modules 根 __init__.py |
| B0-Mock MOCK 服务化 | ✅ | MockScenarioEngine + MockServer（stdlib HTTP + SSE + SLEEP/ERROR）+ TESTONLY 收敛 + 16 项服务测试 |
| B dispatch 修复 | ⬜ | PT-4.7，依赖 B0（服务作为验收仪器） |
| C MOCK 服务 | ✅ 吸收 | 主体已由 B0-Mock 落地（非 fastapi，stdlib 线程内服务） |
| D 全栈 async | ⏸ 暂搁置 | 语言级 async |

### 当前状态（供下个 session 续接）

**已完成**：A7/A1/A2/A3/A6 + U1-U4 + U5（帧字段/方法改名）+ U6 + U7 核心文档 + PT-4.8 + **B0-Env（环境正规化）+ B0-Mock（MOCK 服务化）**。
**测试基线**：`1215 passed, 8 skipped`（llmexcept 统一回归 + PT-4.8 恒真陷阱修复 + 16 项 MOCK 服务测试）。

**B0 交付**：
- `pyproject.toml`（ibci-inter 0.1.0，运行时依赖 openai，`test`/`dev` 分组）；`environment.yml`（conda env `ibci`）；`docs/guide/00_environment.md`；CI 改 `pip install -e ".[test]"`。
- `MockScenarioEngine`（`ibci_modules/ibci_ai/mock_scenario.py`）：指令语言单点实现（RLock 线程安全），内联/服务共用。
- `MockServer`（`ibci_modules/ibci_ai/mock_service.py`）：stdlib `ThreadingHTTPServer` + OpenAI 兼容 `/v1/chat/completions` + SSE + `SLEEP`/`ERROR` 控制 + 并发统计。
- `AIPlugin._is_test_config` 收敛 4 处 TESTONLY 判定；`_handle_mock_response` 变薄委托。
- `tests/conftest.py` 新增 `mock_server` fixture；`tests/runtime/test_mock_service.py` 16 项。

**下一步：Phase B dispatch 修复**（§五 改造项 1-5 + 调研微调 1-8），以 `mock_server` 为验收仪器。剩余低优先级项：U5 命名审查、`_scene_prompts` 死方法清理（`set_general_prompt` 等 4 方法引用未初始化字段）。

**U2+U3 关键设计落地**：
- 产生者（`_finalize_invoke_result` / `vm_handle_IbBehaviorExpr` / `vm_handle_IbBehaviorInstance` / `is_truthy` / `IbCastExpr`）不确定时返回 `IbLLMCallResult(is_certain=False)`，不写 frame / 全局槽。
- 消费者（IbAssign/IbIf/IbWhile/IbFor/IbSwitch/IbExprStmt）从返回值检查 `_is_llm_uncertain_value`，经 `_retry_llm_uncertain` 单帧内收敛重试；`_resolve_condition` 用 `_condition_is_acceptable` 谓词统一"直接容器 + is_truthy 模糊"两种不确定来源（修复"重入新建帧导致重试永不止步"死循环缺陷）。
- 表达式层（BinOp/BoolOp/IfExp/Compare/Call/Attribute/Subscript/Tuple/List/Dict/Slice/CastExpr/FilteredExpr/AugAssign）透传不确定容器到语句消费者。
- `vm_handle_IbLLMExceptionalStmt` 已删除，dispatch 表条目移除。

**剩余**：
- U5 命名审查：`_shared.py`/`leaf.py`/`control_flow.py` 局部变量 `last_result`/`last_val` 等可审慎清理（低优先级，不影响功能）。
- U7 文档收尾：`docs/syntax/10_robustness.md` 已确认用户面语义无需改动；`_code_llmexcept_unify.md` 临时任务文档待清理。
- **独立调研项（本轮主线后启动）**：布尔上下文行为表达式定型 `str` 恒真陷阱（PT-4.8），见 `docs/KNOWN_LIMITS.md` §二十三。

---

## 十一、关联

- PT-4.7：`tasks_docs/PENDING_TASKS.md` §三
- dispatch 禁用现状：`docs/KNOWN_LIMITS.md` §十五
- MOCK 提示词验证限制：`docs/KNOWN_LIMITS.md` §十七.6
- 工作模式定论：`tasks_docs/NEXT_STEPS.md` "⛔ 工作模式定论"
- VM 规范：`docs/architecture/05_vm_specification.md` §1.1（EXEC-3）/§3（LLM 数据流）/§5（意图上下文）
- 代码注释卫生：`docs/README.md` §三.6
