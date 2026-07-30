# Phase 0 决策分析暂存（临时文档）

> **状态**：临时暂存，Phase 0 设计冻结的输入材料。决策闭合后内容并入 `_mock_concurrency.md` 决策记录，本文件删除。
> **来源**：两个并行 subagent 调研报告（2026-07-30）+ 主 agent 综合分析 + 用户决断输入。
> **关联**：`tasks_docs/_mock_concurrency.md`（主线临时文档）、`tasks_docs/PENDING_TASKS.md` PT-4.7、`docs/KNOWN_LIMITS.md` §十五/§十七.6。

---

## 〇、用户决断输入（2026-07-30）

1. **retry_hint 双存储 / 路径行为不一致**：用户判定为**潜在且未知的设计 bug 与架构缺陷**，要求**深入彻查**（彻查完毕后再讨论选型）。
2. **PT-4.7 拆分边界**（止于 `execute_behavior_expression` vs 延伸到 `AIPlugin.__call__`）：**暂存**，待彻查后再议。
3. **`ai.set_retry_hint()` 是否对 dispatched 调用生效**：**暂存**。
4. **Phase 1 流式 SSE**：**必须支持**。
5. **MOCK 服务选型**：用户倾向 **FastAPI** 构建标准 OpenAI 兼容响应服务，要求**尽可能完整兼容所有 OpenAI 定义的兼容接口形式**（即便 IBCI 内尚未涉及，mock 服务侧也要覆盖）。需调研 FastAPI 与其他成熟方案的配合。
6. **执行顺序**：先彻查 retry_hint / last_call_info 潜在 bug，彻查完毕后再讨论技术选型与后续工作方案。

---

## 一、决策点 1：`last_call_info` / `retry_hint` 线程安全

### 1.1 关键事实：双存储架构

#### `last_call_info` 双存储

| | 存储 1：executor 侧 | 存储 2：provider 侧（用户面） |
|---|---|---|
| 位置 | `LLMExecutorCore.last_call_info` (`core/runtime/interpreter/llm_executor/_core.py:72`) | `AIPlugin._last_call_info` (`ibci_modules/ibci_ai/core.py:17`) |
| 写入点 | `_behavior.py:123,139,154` 等（`_call_llm` 返回后）；CPS 版同构 | `AIPlugin.__call__` 内 `ibci_ai/core.py:370`(MOCK)/`:491`(真实API)/`:239`(probe) |
| 字段 | 富信息（sys/user_prompt、response、raw_response、active/global/merged intents） | 精简（sys/user_prompt、response、raw_response、scene，无 intent 信息） |
| 暴露面 | 仅调试（`ibci_idbg` 插件 `executor.get_last_call_info()`） | **用户面 API** `ai.get_last_call_info()`（vtable `ibci_ai/_spec.py:35`，方法调用非属性） |
| 回退链 | `get_last_call_info()`（`_core.py:120-130`）若本字段空则回退到存储 2 | 无回退 |

**结论**：用户 `ai.get_last_call_info()` 看到的是 provider 侧（HTTP 层写入）；executor 侧是调试用富信息。两者并发下都是"最后写者胜"非确定语义。

#### `retry_hint` 双存储（差异更大，疑存既有不一致）

| | 存储 1：context 侧（一次性令牌） | 存储 2：provider 侧（持久） |
|---|---|---|
| 位置 | `RuntimeContextImpl._retry_hint` (`core/runtime/interpreter/runtime_context.py:309`)；property `:495-500` | `AIPlugin._retry_hint` (`ibci_modules/ibci_ai/core.py:16`) |
| 写入 | `vm_handle_IbRetry`（`llm_behavior.py:394`）-- `retry "hint"` 语句；读后立即清零 | 用户 `ai.set_retry_hint()`（`core.py:313-314`）；`_call_llm` 经 `set_retry_hint`（`_core.py:175`） |
| 读取消费 | `execute_behavior_expression[_cps]`（`_behavior.py:105-106,272-273`）读后清零；`execute_llm_function[_cps]`（`_llm_function.py:60,75,193,205`）；`_call_llm`（`_core.py:169`） | `execute_behavior_expression[_cps]` 作**回退**（`_behavior.py:107-108,274-275`）当 context 侧为空时读取，**不清零** |
| 参与 llmexcept 快照？ | ✅ 是（`LLMExceptFrame.save_context` `llm_except_frame.py:168-169`；`restore_context` `:256-257`） | ❌ 否--跨 retry 回跳存活 |

### 1.2 疑似既有 bug（彻查目标）

- `vm_handle_IbLLMExceptionalStmt`（`llm_behavior.py:64-128`）retry 循环**每次迭代顶部**调 `frame.restore_snapshot`（`:70`），把 `context.retry_hint` 恢复为建帧时 `saved_retry_hint`（通常 None）。
- 故 `retry "hint"` 在 body 中写入的 `context.retry_hint`，**会在下一轮 target 执行前被 restore 清除**。
- 对照 `vm_handle_IbFor` 条件驱动路径（`control_flow.py:220-257`）：retry 时**不调 restore**，`context.retry_hint` 能存活到下一轮条件求值。
- **两条 llmexcept 路径对 `retry "hint"` 行为不一致**。因 MOCK 无法验证提示词内容（`KNOWN_LIMITS §十七.6`），可能被测试盲区掩盖。
- **用户已定性为潜在 bug，要求彻查**（见 §〇.1）。

### 1.3 `execute_behavior_expression` 当前结构与拆分边界

同步版（`_behavior.py:27-173`）10 步骤，`dispatch_eager` 当前把完整 10 步提交到 worker（`_scheduler.py:50-53`），worker 重入 VMExecutor--PT-4.7 数据竞争根源。

拆分后归属（已定方向）：
- 主线程：步骤 1-6（段求值 `vm.run` 重入 + sys_prompt 构造 + retry_hint 注入）+ 步骤 8-10（MOCK 处理 + 写 last_call_info + parse）
- worker：步骤 7（`_call_llm` HTTP）--理想仅此步

**worker 当前触达的全部共享可变状态**（拆分前）：
1. `runtime_context.retry_hint`（读+清）
2. `runtime_context` 的 global/active intents（读 live context）
3. `LLMExecutorCore.last_call_info`（写）
4. `LLMExecutorCore._result_parser`（读+惰性写，`_prompt.py:313-315`）
5. `AIPlugin._last_call_info`（`__call__` 内写）
6. `AIPlugin._retry_hint`（`_call_llm` 经 `set_retry_hint` 写）
7. `AIPlugin._mock_state/_mock_retry_counts/_mock_seq_counters`（MOCK 计数器，`__call__`->`_handle_mock_response` 写）-- **与决策点 2 交叉**
8. `AIPlugin._client/_named_clients/_model_capabilities`（惰性写）

**dispatch 与 llmexcept 互斥**：`vm_handle_IbAssign`（`assignment.py:48-58`）要求 `get_current_llm_except_frame() is None` 才 dispatch。故被 dispatch 的 behavior 自身不参与 llmexcept retry（其不确定结果经 `LLMFuture.get` 返回 `llm_uncertain` 哨兵，`llm_result.py:119-120`）。但 **dispatch worker 与主线程上其它同步 llmexcept retry 循环可并发**--竞争真实可达。

### 1.4 worker 线程模型

- 线程池 `ThreadPoolExecutor`，惰性创建（`_scheduler.py:24-28`），默认 `max_workers=8`（`_core.py:62,76`）。
- 提交点 `dispatch_eager`（`_scheduler.py:55`）。
- `_pending_futures` 由 `_pending_futures_lock` 保护（`_core.py:79`，`_scheduler.py:57,69`）--已线程安全。
- resolve 在主线程（`_scheduler.py:61-77`，由 `vm_handle_IbName` 触发）。

### 1.5 `BehaviorDependencyPass` 现状

`behavior_dependency_pass.py:124` -- `dispatch_eligible` **一律置 `False`**。`llm_deps` 仍计算（`:121`）。`_detect_cycles` 仅检测环（`:153-161`），**未实现 spec §3.1 三条强制 False 规则**（插值依赖/Cell/llmexcept）--PT-4.7 接通前置条件之一。

### 1.6 三方案分析

#### 方案 1：线程局部（thread-local）
- 实现：`last_call_info`/`retry_hint` 改 `threading.local()`/`ContextVar`。
- 正确性：retry 全程主线程同步（dispatch 与 llmexcept 互斥），thread-local 对 retry 自身语义零冲击；天然消除跨线程竞争。
- 致命代价：`ai.get_last_call_info()` 只看主线程副本，**丢失 dispatched 调用诊断信息**；`ai.set_retry_hint()` 只设主线程副本，**对 dispatched 调用失效**。
- 风险：`runtime_context` 是 per-Interpreter 共享实例（公理 ISO-1），内部字段改 thread-local 破坏"状态一致性"心智；provider 跨 Interpreter 共享（`KNOWN_LIMITS §二十一`），thread-local 化成隐式陷阱。
- 定位：最简单，用户面语义退化需文档化。

#### 方案 2：加锁（mutex）
- 实现：各状态加锁。
- 正确性：保证数据完整性（不读半写 dict），**但不保证语义正确**--`last_call_info` 仍"最后写者胜"非确定；`retry_hint` 是一次性令牌（读即清），加锁后 worker 可能**抢先消费并清零**主线程的 retry hint（**窃取问题**），锁不解决"谁该消费"。
- 风险：①锁序/死锁（`_call_llm` 先读 `context.retry_hint` 再调 `provider.set_retry_hint`，两锁需固定序）；②给公理层 `runtime_context` 加锁改变并发模型假设，可能与 spec §4 多 Interpreter 隔离冲突；③8 项共享状态逐一加锁易遗漏（尤其 MOCK 计数器）。
- 定位：**隐藏陷阱最多，不推荐作首选**。锁保证安全不保证正确。

#### 方案 3：经 future 去共享（pass via future）
- 实现：worker 不读写任何共享可变状态。主线程预求值 prompt 段并把 `(sys_prompt, content, target_model, type_hint, node_uid)` 打包为不可变入参；retry_hint 在 dispatch 时刻**烘焙进 sys_prompt 字符串**；worker 仅 `provider.__call__` 取 raw response 回传；主线程 resolve 时写 `last_call_info`（单线程写无竞争）、parse。
- 正确性：**唯一能根治"retry_hint 令牌窃取"与"last_call_info 并发写"**。`LLMResult.retry_hint` 已天然经 future 回传（`llm_result.py:63-71`），路径自洽。
- 与 retry 兼容性：最佳。worker 根本不读 `context.retry_hint`，无从窃取。
- **关键依赖（决定彻底性）**：`AIPlugin.__call__`（`ibci_ai/core.py:354-496`）内部含 MOCK 处理（读写 `_mock_state` 等计数器）、`_client` 惰性初始化、`_last_call_info` 写入。若不剥离这些副作用，方案 3 仍有 provider 侧残留竞争--退化为混合方案。
- 定位：正确性最优，工作量取决于 `provider.__call__` 副作用剥离范围。符合"质量优先、不写 tricky 实现"。

### 1.7 核心矛盾（三方案共通）

1. retry 的"回跳重执行"与"最近一次调用"语义在并发下冲突：`retry "hint"` 是面向下一次 target 的定向令牌；`last_call_info` 的"最近一次"在并发 dispatch 下无良定义。
2. `provider._retry_hint` 不参与 llmexcept 快照：单线程下已存微妙不一致（持久 hint 跨回跳存活，一次性 hint 被 restore 清除），并发下两个存储需分别处理，易遗漏。
3. `ai.get_last_call_info()` 的并发语义重定义不可避免：thread-local->"本线程最近"；锁->"任意最后写"；future->"最近 resolve"。

### 1.8 倾向（非决策）

- 正确性最优：方案 3。
- 最简单：方案 1（用户面语义退化）。
- 最不推荐：方案 2（锁保证安全不保证正确）。
- 方案 3 成败关键：`provider.__call__` 副作用剥离范围（待 PT-4.7 边界决断 + 决策点 2 MOCK 计数器去向）。

### 1.9 信息缺口（待彻查/待用户输入）

1. **`retry "hint"` 在 `IbLLMExceptionalStmt` 路径下是否真被 restore 清除**（潜在既有缺陷）-- **用户已要求彻查，见本文件 §二**。
2. `ai.set_retry_hint()` 是否预期对 dispatched 调用生效--暂存待议。
3. PT-4.7 拆分边界是否延伸到 `provider.__call__`--暂存待议。
4. `LLMResultParser`（`_prompt.py:313-317`）是否无状态可并发调用--待深读 `llm_parsing_strategy.py`。
5. `LLMFuture` 扩展携带 call_info 是否破坏公理 LLM-2 合规测试（`tests/compliance/test_concurrent_llm.py` 9 测试）--待确认。

---

## 二、决策点 2：MOCK 服务实现选型

### 2.1 现有 MOCK 拦截与待清理债

- **单一拦截入口**：`AIPlugin.__call__`（`ibci_ai/core.py:354-371`）`is_test_mode` 为真时跳过 openai，走 `_handle_mock_response`（`:543-751`）。
- **TESTONLY 判定散落 4 处**：`_init_client:83`/`_get_named_client:159`/`probe_model:197`/`__call__:355`，且 `probe_model` 多孤儿 `MOCK_KEY`（全仓库无人设置，疑似残留）。
- **跨模块魔法哨兵字符串**（报告 C 提议 6 待常量化）：
  - `"__MOCK_REPAIR__"`：生产者 `ibci_ai/core.py:674,743`；消费者 `_behavior.py:122,126,132,134,286,290,296,298` + `_llm_function.py:107,111,117`。
  - `"MAYBE_YES_MAYBE_NO_this_is_ambiguous"`：同上模式。
  - executor 层用 `if response == "__MOCK_REPAIR__"` 字符串比对识别 MOCK 语义--**违反工作模式定论"禁止靠凑巧相等/魔法哨兵"**。
- `AI_MOCK_PREFIX` 常量在 9 处重复定义（报告 C §3.3）。

### 2.2 openai client 形态

- 仅同步 `OpenAI`，`AsyncOpenAI` 全仓库 0 使用。
- **0 处用 `stream=True`**--流式当前未落地（但用户要求 Phase 1 必须支持）。
- 当前环境未装 openai，1186 passed 全绿--因 TESTONLY 拦截在 `from openai import OpenAI` 之前（`:87-89`）。**MOCK HTTP 服务接入后 openai 成测试硬依赖**（CI 已装 `ci.yml:33`，本地需补装；项目无 requirements 文件，建议借此次新增）。
- `base_url` 含 `127.0.0.1`/`localhost` 且无 `/v1` 时自动补 `/v1`（`:96-97`）。
- 超时 30s（probe 15s），MOCK 延迟须小于此。

### 2.3 测试基础设施与依赖

- 无 requirements.txt/pyproject.toml/setup.py。CI 仅 `pip install pytest`+`openai`。
- `ibci_net/core.py:17-21` 用 `try: import requests` 可选依赖模式--项目处理可选依赖的唯一先例。
- `tests/conftest.py` 强制 basetemp=`.tmp_pytest/`，无任何 HTTP/端口/socket fixture。
- Python 3.10+，CI 矩阵 ubuntu+windows × 3.10+3.12。Windows `SO_REUSEADDR` 语义激进；unix socket Windows 不可用。

### 2.4 4 项 dispatch 专属 skip 根因

- `test_e2e_llm_basic.py:159`（`TestE2EStaleResultIsolation` ×3）+ `test_e2e_llm_pipeline.py:43`（×1）。
- 根因：`dispatch_eligible` 强制 `False`（`behavior_dependency_pass.py:124`），`dispatch_eager` 永不触发，`_pending_futures` 永远为空，`MOCK:FAIL` 走同步路径立即抛错而非陷阱化。
- 解锁需 Phase 2（dispatch 修复）+ Phase 3（MOCK 验证）。skip 数目标 8->4。

### 2.5 三候选分析

| 维度 | pytest-httpserver | aiohttp | http.server+ThreadingHTTPServer |
|---|---|---|---|
| 独立线程 | ✅ fixture 后台线程 | ✅ 线程内事件循环 | ✅ ThreadingHTTPServer |
| 延迟注入 | ⚠️ 手写 handler+sleep | ✅ `asyncio.sleep` | ✅ `time.sleep` |
| 并发顺序控制 | ⚠️ 无法原生控制完成顺序 | ✅ **最强** `asyncio.Event`/`Task` | ⚠️ 手写 `threading.Event` |
| 失败 500 | ✅ | ✅ | ✅ |
| 流式 SSE | ⚠️ 自定义 handler 手写 | ✅ `StreamResponse` 最自然 | ⚠️ 手写 `wfile.write`+`flush` |
| OpenAI 端点匹配 | ✅ | ✅ | ✅ |
| pytest 集成 | ✅ 最自然 | ⚠️ 自写 ~40-60 行 | ⚠️ 自写 ~30-50 行 |
| 演进独立进程余地 | ❌ **最差**（pytest 进程内假设写死，违反决策） | ✅ 较干净 | ✅ **最干净** |
| 依赖成本 | +Werkzeug(~2MB) | +aiohttp(~3MB) | ✅ 零（标准库） |
| 与轻依赖定位 | 有张力 | 张力较大 | ✅ 完全契合 |

**第四选项评估**：
- `httpx`+ASGI transport / `respx`：**排除**--in-process transport，违背决策硬约束"走真实 HTTP loopback socket/真超时"。
- `uvicorn`+裸 ASGI：可行但依赖比 http.server 重、fixture 比 aiohttp 复杂，无相对优势。

### 2.6 用户倾向（待调研）

用户倾向 **FastAPI** 构建标准 OpenAI 兼容服务，要求尽可能完整兼容所有 OpenAI 兼容接口形式。需调研：
- FastAPI 构建 OpenAI 兼容 `/v1/chat/completions`（含流式 SSE）的成熟方案。
- FastAPI 与其他成熟方案（如 `openai` SDK 的 mock、`litellm` proxy、`fastapi-openai-mock` 等）的配合。
- FastAPI 的依赖成本（pydantic、starlette、uvicorn）与项目"轻依赖"定位的张力评估。
- FastAPI 服务的独立线程/独立进程演进余地。
- FastAPI 与可编程场景引擎（延迟/并发/失败/流式）的集成方式。

### 2.7 核心矛盾

1. `pytest-httpserver` 无法精细控制乱序完成（其强项是按序匹配），且演进余地最差。
2. `http.server` 误用基类会串行化（必须 `ThreadingHTTPServer`）。
3. aiohttp 的 asyncio 与 VM 线程模型：当前不冲突，若将来引入 `AsyncOpenAI` 有潜伏竞争风险。
4. 共性：openai 将成测试硬依赖，需先补 requirements 文件。

### 2.8 倾向（非决策，待 FastAPI 调研后修正）

1. `http.server`+`ThreadingHTTPServer`--轻依赖与演进干净度最优。
2. aiohttp--并发时序控制最强、SSE 最自然。
3. pytest-httpserver--不推荐。
- **FastAPI 待调研**：用户倾向，可能成为新首选（若依赖成本与演进余地可接受）。

### 2.9 信息缺口

1. Phase 1 是否必须支持流式 SSE--**用户已答：必须**。
2. `ai` 模块是否有未文档化的 base_url 分支（`_init_client:96-97` 自动补 `/v1`）--MOCK 端点须对齐。
3. `IBC_TEST_MODE` 环境变量使用面--全仓库无测试/文档设置它，是否可废弃。
4. `MOCK_KEY` 孤儿--`probe_model:197` 检测但无人设置，疑似残留。
5. 命名模型 `@NAME~` 是否需 MOCK 服务支持（`register_model`+`_get_named_client` 独立路由）。
6. Windows CI 上 openai client 连 loopback 服务的兼容性（IPv4/IPv6）。

---

## 三、两决策点交叉依赖（不可孤立决断）

决策点 1 方案 3 的"残留竞争点"清单第 7 项（MOCK 计数器）取决于决策点 2：

- 决策记录已定"DSL 共存"：简单 MOCK 指令保留进程内 DSL，MOCK 计数器**不会完全消失**。
- 但 Phase 1 用 HTTP 服务承担并发/延迟/失败/流式--这些是触发并发竞争的场景。若 dispatched 调用走简单 DSL，worker 仍写 MOCK 计数器（竞争仍在）；若 dispatched 调用必走 HTTP 服务，MOCK 计数器竞争在并发路径消失。

**推论**：方案 3 彻底性部分由"dispatched 调用走 DSL 还是 HTTP"决定，而这取决于 Phase 1 的 MOCK 注册口设计（报告 C 提议 5）。两决策点应联合决断，Phase 0 设计冻结须同时覆盖：(a) MOCK 服务选型与注册口；(b) dispatched 调用 MOCK 路径归属；(c) 线程安全方案与 `provider.__call__` 副作用剥离范围。

---

## 四、待决问题清单（彻查后讨论）

1. retry_hint / last_call_info 双存储与路径不一致彻查结论（见 §一.2，进行中）。
2. PT-4.7 拆分边界（止于 `execute_behavior_expression` vs 延伸 `AIPlugin.__call__`）。
3. `ai.set_retry_hint()` 对 dispatched 调用是否生效。
4. MOCK 服务选型（FastAPI 调研后定）。
5. dispatched 调用 MOCK 路径归属（DSL vs HTTP）。
6. 线程安全方案最终选择（依赖 1-5）。
7. Phase 1 流式 SSE 实现细节（用户已定必须支持）。
