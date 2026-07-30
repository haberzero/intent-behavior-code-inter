# MOCK 服务化与 LLM 并发调度（临时任务文档）

> **状态**：规划阶段（Phase 0）。**当前最优先任务**（见 `NEXT_STEPS.md`）。
> **性质**：临时文档，工作完成后删除。
> **关联**：激活 `PENDING_TASKS.md` PT-4.7（DDG 并行调度接入 VM）；解锁 4 项 dispatch 专属 skip 测试。

---

## 一、目标

1. 在**无真实 LLM API** 的前提下，让 LLMFuture / dispatch 调度排布 / LLM 并发调用 / 并发下的 retry 可被测试。
2. 修复 `dispatch_eager` 的数据竞争（PT-4.7），重新启用并发调度，解锁 4 项 skip 测试。
3. MOCK 机制升级为可编程的真实服务，能模拟延迟/并发/失败/流式，贴近真实使用场景。

## 二、核心架构决策

**采用独立进程 MOCK HTTP 服务（架构 B）作为并发/延迟/失败测试仪器。**

- 独立进程（或独立线程）HTTP 服务，模拟 OpenAI `/v1/chat/completions` 端点。
- `ai` 模块 `base_url` 指向本地服务 -> 走**真实 openai client + 真实 HTTP**（loopback socket、真线程池、真超时），即生产代码路径。
- 可编程场景引擎：测试前注入剧本（按请求延迟/返回 500/慢流式/并发顺序）。
- 提供真实异步窗口（dispatch 提交后 future 不立即决），使 LLMFuture lazy resolve、`_pending_futures` 生命周期、并发时序可观测。

**与现有进程内 MOCK DSL 的关系**（Phase 0 决策点）：
- 方案 a（共存，推荐）：简单确定性测试（MOCK:TRUE/INT 等）保留进程内 DSL（快）；并发/延迟/失败测试用 HTTP 服务。两者共享统一场景词汇。
- 方案 b（统一）：所有测试走 HTTP 服务，进程内 DSL 退役或降级为服务客户端。一致性强，但简单测试增加 HTTP 开销。

## 三、工作路径（Phase 0-4）

> 铁律：Phase 0 设计冻结前不启动代码改动。

### Phase 0：设计冻结

**0.1 MOCK HTTP 服务设计**
- 端点：`POST /v1/chat/completions`（OpenAI 兼容），可选 `/v1/embeddings` 等。
- 场景引擎 API：测试侧用 Python 配置剧本，如 `server.scenario([resp(delay=0.5, body=X), resp(status=500), resp(stream=chunks)])`；支持按请求序号/内容匹配、并发处理。
- 生命周期：pytest fixture 启停服务、端口分配（或 unix socket）、并发模型（async 还是线程）。
- 与 `ai.set_config` 的对接：新增正式 mock 注册口（取代散落 TESTONLY 判定，报告 C 提议 5），`base_url` 指向服务。
- 哨兵字符串常量化（报告 C 提议 6）：`MOCK_REPAIR_SENTINEL` 等跨模块共享。

**0.2 dispatch_eager 修复设计（PT-4.7）**
- 拆分 `execute_behavior_expression`：主线程预求值 prompt 段（同步，访问 VMExecutor）；worker 线程仅 `_call_llm(prompt)` + 解析（异步，不重入 VMExecutor）。
- `last_call_info`/`retry_hint` 线程安全：线程局部、加锁、或经 future 传递（去共享）。
- `BehaviorDependencyPass` 实现 `05_vm_specification.md §3.1` 规则（插值依赖/Cell/llmexcept 强制 `dispatch_eligible=False`）。
- 重新启用路径：先经 test flag 启用，验证后默认开启。

**0.3 DSL 共存 vs 统一**（决策点 0.1 方案 a/b）

**0.4 B 测试解锁标准**：4 项 skip 测试改为可执行 + 新增并发合规测试（时序/竞态/懒决/_pending_futures）。

### Phase 1：MOCK HTTP 服务（测试仪器，additive）

- 实现独立进程 HTTP 服务 + 场景引擎。
- pytest fixture（启停/端口/ai 指向）。
- 用简单延迟/失败场景验证仪器可用（不依赖 dispatch 修复）。
- 哨兵常量化 + mock 注册口收敛。

### Phase 2：dispatch_eager 修复（PT-4.7）

- 拆分 `execute_behavior_expression`（主线程预求值 + worker 仅 HTTP+解析）。
- 共享状态线程安全化。
- `BehaviorDependencyPass` 补 §3.1 规则。
- 经 test flag 临时启用 `dispatch_eligible`。

### Phase 3：MOCK 验证 + 解锁 B 测试

- 用 MOCK HTTP 服务的延迟制造并发窗口，复现并修复残留竞态。
- 新增并发合规测试（时序正确、lazy resolve、_pending_futures 生命周期、retry 并发）。
- 重新启用 4 项 skip 测试：
  - `test_e2e_llm_pipeline.py::test_two_independent_assignments_both_pending_after_run`
  - `test_e2e_llm_basic.py::TestE2EStaleResultIsolation` × 3
- `dispatch_eligible` 默认开启。

### Phase 4：收尾

- 移除 test flag，清理临时探针。
- 更新 `KNOWN_LIMITS §十五`（dispatch 不再禁用）、`PENDING_TASKS` PT-4.7（关闭）、`05_vm_specification.md §3`（并发调度启用状态）。
- 本临时文档删除。

---

## 四、依赖与协同关系（关键）

- **MOCK 与 dispatch 修复协同依赖**：MOCK 提供异步 LLM 行为（必要），dispatch 修复让并发路径安全（必要）。两者缺一不可。
- **MOCK-first 是正确入口**：没有异步 LLM 模拟，dispatch 修复无法开发/验证。MOCK 是开发 dispatch 修复的仪器，不是替代品。
- **不破坏现有同步测试**：dispatch 修复后，同步路径（`dispatch_eligible=False` 的情形，如插值依赖/Cell/llmexcept）仍走同步，现有 MOCK DSL 测试不受影响。

## 五、覆盖保活

- Phase 1/2 每步后全量 `pytest` 不退化。
- Phase 3 新增并发测试 + 解锁 4 项 skip；skip 数应从 8 降至 4（仅剩 C 类 3 项结构债 + D 类 1 项平台）。
- 不取消设计限制类 skip（已删除）与平台类 skip（保留）。

## 六、决策记录

1. **MOCK 服务进程模型**：✅ 已决定--**现阶段独立线程**；实现时留下未来改造成独立进程的余地（抽象服务边界，不把线程假设写死）。
2. **DSL 共存 vs 统一**：✅ 已决定--**保留共存**。简单 MOCK 指令（MOCK:TRUE/INT 等）用简单模式（进程内 DSL），确保速度；并发/延迟/失败/流式用 HTTP 服务。两者共享统一场景词汇。
3. **`last_call_info`/`retry_hint` 线程安全方案**：⏳ 暂未决定--需后续智能体做更全面的技术调研与分析探讨（线程局部 / 加锁 / 经 future 去共享的取舍），现阶段无法定论。Phase 2 启动前必须闭合。
4. **MOCK 服务实现选型**：⏳ 暂未决定--`pytest-httpserver` / 自建 aiohttp / `http.server` 等，留待 MOCK 服务实际开发时（Phase 1 启动前）再作选型探讨。

## 七、进度追踪

| Phase | 状态 | 备注 |
|---|---|---|
| 0 设计冻结 | ⏳ 待启动 | 规划阶段，不动代码 |
| 1 MOCK HTTP 服务 | ⬜ | |
| 2 dispatch_eager 修复 | ⬜ | PT-4.7 |
| 3 验证 + 解锁 B 测试 | ⬜ | |
| 4 收尾 | ⬜ | |

## 八、关联

- PT-4.7：`PENDING_TASKS.md` §三
- dispatch 禁用现状：`KNOWN_LIMITS.md` §十五
- 工作模式定论：`NEXT_STEPS.md` "⛔ 工作模式定论"
- 测试体系重构（独立、较低优先级）：`TEST_REFACTOR.md`
