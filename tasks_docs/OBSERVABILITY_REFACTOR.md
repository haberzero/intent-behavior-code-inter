# OBSERVABILITY_REFACTOR — 可观测性统一与测试体系重构（任务控制文档）

> **最后更新**：2026-08-06
> **性质**：正式任务控制文档（非临时）。本周期主线任务控制文件。
> **主线**：本任务为当前唯一 P0 主线。原 PT-TEST-1 测试体系重构（`TEST_REFACTOR.md`）**并入本任务**（测试侧=观测骨架的消费方）。

---

## 一、背景与目标

用户裁定（2026-08-06）：测试体系重构不只是测试脚本层面的治理，而是**从内核出发、全局且系统级的机制完善**——让内核更积极、统一一致、高效地配合测试/调试/内省体系，使 IBCI 内核更好地适应**测试驱动开发演进**。

四项机制（测试体系 / CORE_DEBUG / idbg / 内省机制）**宏观统一，不可割裂考虑**，本质是同一件事的四个碎片——**内核可观测性（Kernel Observability）**：内核如何被观察、被诊断、被测试。

**核心事实**：内核已存在设计语言最现代的观测骨架——`core/runtime/observability/`（`snapshot.py` 结构化快照聚合 + `events.py` 协议驱动事件总线 + `config.py` 作用域化配置），经 `iruntime` 插件暴露。而 CORE_DEBUG（print 推送）、idbg（自拼 dict + 直扫 node_pool）、测试（70+ 处私有穿透）**都在该骨架之外另搞一套**。

**本任务方向**：以观测骨架为**单一权威源**，四机制收敛其上；历史包袱经分析确认无意义即**大胆抛弃并彻底清理**；禁止兼容层。

---

## 二、工作模式与授权（用户 2026-08-06 补充裁定，凌驾于本文档一切安排之上）

1. **允许代码破坏**；不以已存在代码为重。
2. **大规模破坏必须先在独立分支实验**；实验成功后**禁止直接合并**回 `unsafe-vibe-dev`，只能**根据已检验的设计思路手动**做出成熟、可靠的改动回 `unsafe-vibe-dev`。
3. 破坏性改造若同时满足：**实验通过 + 符合工程实践 + 一般普适性设计思路 + 符合 IBCI 整体设计原则 + 长期收益** → 用户已授予**全权自主决定并实施**。
4. 总体指导思路：**长期收益优先、系统级统一、宏观机制设计与思路一致性**，始终为主要基准。
5. **禁止兼容层设计**（工作模式定论 §1）。
6. **历史包袱**：经慎重分析确信无意义应演进 → 大胆抛弃并彻底清理（"不删也不修"两档）。
7. 工作模式定论（`NEXT_STEPS.md` §⛔）其余条款继续有效。

---

## 三、目标架构（统一可观测性骨架）

> 单一权威源 + 统一设计语言 + 机制同构 + 配合模式统一（对照 `design-philosophy`）。

```
                        ┌──── 内核观测骨架（observability，已存在，扩展） ────┐
  用户侧 idbg（渲染层）   │  状态面 State：RuntimeSnapshot（snapshot 聚合）       │  测试侧 PT-TEST-1
  iruntime（通用内省）    │    ├─ 统一 vars 查询（get_vars/get_vars_snapshot 收敛）│  conftest 收敛
  type()/__return_type__│    ├─ 最近 LLM 调用记录模型（单一权威源）             │  正式 API（test_snapshot
  （值层自持内省范式保留） │    └─ EngineTestSnapshot（替代 engine 生命周期穿透）   │  / test_hooks）
                        │  事件面 Events：EventBus 扩展                        │  私有穿透清零
  CORE_DEBUG（删除）     │    ├─ llm/retry/诊断事件类型                         │  meta 自检扩展
  15 处诊断点→warnings   │    ├─ ServiceContext.test_hooks（测试侧 sink）        │
                        │    └─ LastLLMCallRecord 由事件面更新                  │
                        │  控制面 Control：ConfigStore 扩展                    │
                        │    ├─ test_mode / IsolationPolicy.test_mode/mock_provider
                        │    └─ Engine.reset_test_state / Interpreter.reset_test_state
                        │  诊断面 Diagnostics：CoreDebugger 删除，无平行机制
                        └───────────────────────────────────────────────────────┘
```

### 目标架构要点

| 面 | 机制 | 收敛动作 |
|---|---|---|
| 状态面 | snapshot 聚合 + 统一查询 | 收敛 `get_vars`/`get_vars_snapshot`；新增 **LastLLMCallRecord**（sys_prompt/user_prompt/response/raw_response/active_intents/global_intents/merged_intents/result）作为 ai/idbg/snapshot/测试的单一事实来源；新增 **EngineTestSnapshot**（explicit_root/cwd/path_ctx/plugin_search_paths/install_path/spawned_handles/root_initialized）替代 engine 生命周期私有穿透 |
| 事件面 | EventBus 扩展 | 新增 llm 调用/重试/诊断事件类型；`ServiceContext.test_hooks`（on_llm_call/on_dispatch/on_llmexcept_enter/exit）作为测试侧 sink；LastLLMCallRecord 由事件更新 |
| 控制面 | ConfigStore 扩展 | `test_mode` 内核级概念；`IsolationPolicy.test_mode`/`mock_provider`；`Engine.reset_test_state()`；MOCK 判定收敛为内核级（不留在插件私有） |
| 诊断面 | CoreDebugger 删除 | 机制整体删除（类/配置流/engine 接线/dead import/88 trace）；15 处异常回退诊断点 → `warnings.warn`（与 PT-DEBT-6 先例一致、可测试）；流程日志直接删；silent 收敛为单职责 |
| 用户侧 | idbg 重定位 | idbg = 观测骨架的**用户侧渲染层**，API 按统一设计语言重设计（清幽灵 API/死 API/悬挂契约，数据源收敛）；iruntime 为通用内省入口；type()/`__return_type__` 值层自持范式保留 |
| 测试侧 | PT-TEST-1 并入 | conftest 收敛；私有穿透清零；meta 自检扩展（命名/矩阵三段式/helper 自动派生）；覆盖矩阵机器校验 |

### 设计原则（设计哲学对照）

- **单一权威源**：状态/事件/配置/最近调用记录各一个模型，禁止双写真相 / 多入口形态各异。
- **统一设计语言**：所有观测输出同形态（结构化 dict / 事件类型枚举）。
- **机制同构**：idbg=渲染层、测试 hooks=事件 sink、诊断=warnings，不造平行机制。
- **配合模式统一**：插件走 KernelRegistry 钩子；测试走 ServiceContext/Engine 正式口；禁私有穿透。
- **无兼容层**：旧机制要么真删除要么真收敛，不留中间态 / shim / 别名。
- **一致性先于便利**：白盒 helper 下沉、layering 白名单归零、无 skip 掩盖违规。

---

## 四、阶段规划与验收标准

### Phase 0：设计冻结（`unsafe-vibe-dev`，不动代码）

- [x] **0.1 覆盖基准固化**：`pytest --collect-only` per-file 快照 → 存档 `tasks_docs/test_baseline_20260806.txt`（103 文件 / 1632 用例；实跑 1626 passed / 6 skipped）。
- [x] **0.2 本文档冻结**（目标架构 + 阶段验收 + 分支政策）。
- [ ] **0.3 文档同步**：`NEXT_STEPS.md` 列本任务为主线；`TEST_REFACTOR.md` 标注并入；`HANDOFF.md` 动态状态更新。
- **验收**：设计冻结 + 基准存档 + 文档同步；零代码改动。

### Phase 1：契约修复 + 死码清理 + 零成本穿透替换（`unsafe-vibe-dev`，小改动直做）

> **重新定界（2026-08-06 实施中）**：与 CoreDebugger 机制强绑定的清理项（rt_scheduler `CoreModule.RUNTIME`
> bug、5 处 dead import、`core_enter`/`core_exit`、`dependencies.debugger` 死字段、silent 语义收敛）归入 **2A**
> 一并处理（2A 整体删除该机制，避免重复劳动）；idbg 死 API（fields/intents/_llm_provider/debugger_provider）
> 归入 **2C** idbg 重构一并决策。每项全量 pytest 零回归 + 描述性 commit。

- [x] **1.1a 悬挂契约修复（已完成，commit d2d828a）**：删 `IStateReader`/`IExecutionFrame.get_last_llm_result`
  协议方法（声明无实现、idbg 空帧回退必 AttributeError）+ idbg 改只依赖活跃帧 + 修 docs/subsystems/01_intent_system.md 不实引用。
- [x] **1.1b examples 幽灵 API（已完成，commit d2d828a）**：`last_llm`→`current_llm`、`last_result`→`current_result`、
  `show_last_prompt`→`show_target_prompt`（02/04/05/06 四示例）；顺带删除 06 示例引用不存在的 `call_info["scene"]` 打印行。
- [x] **1.1d 悬空键（已完成，commit d2d828a）**：`show_retry_stack` 删读已移除的 `is_fallback` 键。
- [ ] **1.2b idbg 死 API → 归入 2C**：fields/intents/_llm_provider/debugger_provider 在 idbg 重构中一并决策。
- [x] **1.3 零成本穿透替换（已完成，commit d2d828a）**：`engine.interpreter._execution_context`→`execution_context`
  （22 处 + conftest make_vm）、`len(executor._pending_futures)`→`pending_futures_count()`（6 处）、
  `getattr(rc,"_runtime_coordinator")`→`peek_runtime_coordinator()`（2 处）。
- [ ] **1.1c/1.4 → 归入 2A**：rt_scheduler RUNTIME bug、silent 语义收敛随 CoreDebugger 删除一并处理。
- **验收**：Phase 1 全绿；穿透替换后 tests/ 无上述三类私有访问残留（test_idbg 的 `_DummyExecutionContext` 自持字段除外）。

### Phase 2：大规模破坏实验（独立分支，禁止合并）

> 每实验：分支全绿 + 设计自检（design-philosophy / self-grill / code-odor / 残留扫描）+ 结论记录于本文件"六、决策记录"。

- [ ] **2A：CORE_DEBUG 移除实验**（分支 `exp/obs-2a-core-debug-removal`）
  - 删除 CoreDebugger 机制（类/单例/env `IBC_CORE_DEBUG`/CLI `--core-debug`/engine 接线/`ServiceContext.debugger` 契约/27 import 点/88 trace 点）。
  - 15 处异常回退诊断点 → `warnings.warn`；~73 处流程/DATA 日志直接删除。
  - 拆除 `debugger=` 构造参数链（Scheduler/Lexer/Parser/Analyzer/Interpreter/ServiceContext/llm_executor/ParsingStrategy）。
  - 影响面最大（~31 文件），先行实验。
- [ ] **2B：观测骨架扩展实验**（分支 `exp/obs-2b-skeleton`）
  - LastLLMCallRecord 权威模型 + `_current_call_info` 单写槽收敛；ai/idbg/snapshot 三入口统一数据源。
  - EventBus 新增事件类型；`ServiceContext.test_hooks`；test_mode 内核化。
  - `IsolationPolicy.test_mode`/`mock_provider`；`Engine.reset_test_state`/`Interpreter.reset_test_state`。
  - EngineTestSnapshot 正式 API（替代 engine 生命周期私有穿透）。
- [ ] **2C：idbg 重构实验**（分支 `exp/obs-2c-idbg`）
  - 数据源收敛到 LastLLMCallRecord/观测骨架；API 按统一设计语言重设计；渲染层化（消除手写拼 dict/打印分支、直扫 node_pool）。
  - vtable 与 docs/syntax/11_modules.md §11.5 同步。
- [ ] **2D：PT-TEST-1 新测试体系实验**（分支 `exp/obs-2d-test-refactor`）
  - 沿用 `TEST_REFACTOR.md` Phase 0-5 强制策略与覆盖保活铁律；测试侧消费 2B 新接口。
  - 结构重构（去代号/归类/拆白名单/plugins 层）+ 逐域移植 + 覆盖矩阵三段式 + meta 扩展。
- **验收**：各分支全绿；实验结论记录；不合并。

### Phase 3：手动应用到 `unsafe-vibe-dev`

- [ ] 每实验验证通过后，按已检验设计**手动**实施回 `unsafe-vibe-dev`；每步全量 pytest 零回归 + commit + 记录变化前后（实现+测试+文档）。
- **验收**：`unsafe-vibe-dev` 全绿；实验分支保留不合并；无兼容层残留。

### Phase 4：收敛收尾

- [ ] 覆盖矩阵三段式同步（PT-TEST-3 并入）+ meta 机器校验（命名/矩阵/helper 自动派生）。
- [ ] 旧 `tests/` 删除（新体系覆盖 ≥ 基准论证后，遵循 TEST_REFACTOR §五）。
- [ ] docs 治理：docs/syntax/11_modules.md idbg 段、docs/guide/07_testing、docs/howto/debug_llm_calls、docs/architecture 01/07、docs/subsystems 01 等同步；清除 `IBC_CORE_DEBUG`/`--core-debug` 相关（当前零提及，确认不新增）。
- [ ] `NEXT_STEPS.md`/`WORKLOG.md`/`HANDOFF.md` 同步；本任务收尾。

---

## 五、分支政策

- 实验分支：`exp/obs-2a-core-debug-removal`、`exp/obs-2b-skeleton`、`exp/obs-2c-idbg`、`exp/obs-2d-test-refactor`。
- **禁止合并**实验分支到 `unsafe-vibe-dev` / `main`；验证后**手动**应用回 `unsafe-vibe-dev`。
- 永远不触碰 `main`。
- 全程本地 commit；**禁止 push**（除非用户显式授权）。
- 每个实验分支基于 `unsafe-vibe-dev` 的当前 HEAD 新建；实验完成后分支保留（不删除）供追溯。

---

## 六、决策记录

> 实施中按阶段追加：方案、依据（对照 §二 授权条件与 design-philosophy）、变化前后。

| 日期 | 阶段 | 决策 | 依据 |
|---|---|---|---|
| 2026-08-06 | 规划 | CORE_DEBUG 处置 = 机制整体删除，15 处异常回退诊断点改 `warnings.warn`（不保留平行诊断机制） | 历史包袱彻底清理；warnings 与 PT-DEBT-6 先例一致、可测试；无兼容层 |
| 2026-08-06 | 规划 | idbg 重定位为观测骨架渲染层，API 按统一设计语言重设计（不以 API 契约史为约束） | 对外契约破坏已获授权；长期收益与系统统一优先 |
| 2026-08-06 | 规划 | test_snapshot/test_hooks/test_mode 直接长在观测骨架上（不造第三套） | 单一权威源 / 机制同构 |
| 2026-08-06 | 规划 | PT-TEST-1 并入本任务；覆盖矩阵三段式 + meta 机器校验 | 用户裁定合并推进；矩阵"测试位置"列大面积虚构（TEST_MATRIX_FINDINGS） |
| 2026-08-06 | Phase1 | 删 `get_last_llm_result` 悬挂协议 + idbg 只依赖活跃帧（不实现该方法） | 设计意图（certainty 经 IbLLMCallResult 传递，无全局槽）自证无实现需求；无兼容层 |
| 2026-08-06 | Phase1 | 与 CoreDebugger 强绑定的清理项（rt_scheduler RUNTIME/dead import/core_enter/dependencies 字段/silent）归入 2A；idbg 死 API 归入 2C | 避免 2A/2C 重复劳动；机制整体删除时一并处理 |
| 2026-08-06 | 2A | **CORE_DEBUG 移除实验完成并应用**：`exp/obs-2a-core-debug-removal` 分支全量绿（1626/6、零 warning）→ cherry-pick 手动应用回 unsafe-vibe-dev（commit 6878986）。处置细化：15 处诊断点中仅"真实异常回退"转 warnings（8 处）；AttributeError 协议缺失回退=设计路径静默（receive 对无协议对象抛 AttributeError 是正常路径，实测 11 warning 触发后拆分）；设计内重试/已上报错误/会重抛的 trace 直接删 | 实验验证 + 全量零回归 + 实测噪音分类；警告语义与 _prompt.py 既有 AttributeError-fallback 范式一致 |
| 2026-08-06 | 2B | **观测骨架测试合作面实验完成并应用**：`exp/obs-2b-skeleton` 分支全量绿（1633/4）→ cherry-pick 应用回 unsafe-vibe-dev。交付：`EngineTestSnapshot`+`reset_test_state`+`resolve_plugin_search_paths` 公开（消除 engine 生命周期私有穿透、layering 豁免归零）、`ServiceContext.test_hooks`（TestHooks 协议，显式协议调用非 getattr 分派，契约强制全方法） | 实验验证 + 设计自检（code-odor 去除能力探测） |
| 2026-08-06 | 2B | **推迟 `IsolationPolicy.test_mode`/`mock_provider` 至 2D**：无消费方的预留字段=死字段（R2 教训）；MOCK/TESTONLY 判定内核化是行为变更，随测试重构一并设计 | 禁死代码；预留字段违背"禁兼容层/禁预留"哲学 |
| 2026-08-06 | 2B | **跳过 call_info 形式化**：ai/idbg/snapshot 三入口已收敛于 `get_current_call_info()`（`_current_call_info` 单写槽）单一权威源，dict 形态 JSON 友好无需 dataclass 化 | 单一权威源已达成；形式化收益边际 |
| 2026-08-06 | 2C | **idbg 适配实验完成并应用**：`exp/obs-2c-idbg` 分支全量绿（1633/4）→ cherry-pick 应用回 unsafe-vibe-dev（commit 8a0065c）。删真死代码 `_llm_provider`/`debugger_provider`；`show_intents` 收敛为 `intents()` 单一权威源（去 C9 双源回退 + except-pass）；`fields()` 改 `isinstance(IbObject)` 协议直访（去 A1 hasattr 探测）；保留 16-API vtable 契约（fields/intents 保留并修复，非删除） | 实验验证 + 审计记录（C9/A1）同步为已解决 |

---

## 七、进度追踪

| Phase | 状态 | 备注 |
|---|---|---|
| 0 设计冻结 | ✅ 完成 | 基线存档 + 规划冻结 + 文档同步（commit 3dfba92） |
| 1 契约修复+死码清理 | ✅ 完成 | 1.1a/1.1b/1.1d/1.3 完成（commit d2d828a）；1.2b→2C、1.1c/1.4→2A |
| 2A CORE_DEBUG 移除实验 | ✅ 完成并应用 | 分支验证全绿 → cherry-pick 应用回 unsafe-vibe-dev（commit 6878986），全量 1626/6 零 warning |
| 2B 观测骨架扩展实验 | ✅ 完成并应用 | EngineTestSnapshot/test_hooks/resolve_plugin_search_paths 公开；test_mode/mock_provider→2D、call_info 形式化跳过 |
| 2C idbg 重构实验 | ✅ 完成并应用 | 删死代码 + show_intents 单一权威源 + fields() 协议化（commit 8a0065c） |
| 2D 测试体系重建实验 | ⬜ | 独立分支 |
| 3 手动应用回 unsafe-vibe-dev | ⬜ | |
| 4 收敛收尾 | ⬜ | |

---

## 八、风险与边界

- **破坏面最大**：2A CORE_DEBUG 移除（~31 文件）。已评估：测试零行为依赖（唯一使用 core_debugger 处为构造参数）、docs 零提及、输出无消费者。残留风险集中在"移除后 15 处回退诊断的可见性"——以 warnings.warn 承接。
- **idbg 为对外契约**：重设计需同步 vtable、docs、示例、测试；列为 2C 实验，验证后手动应用。
- **覆盖保活**：2D/3 遵循 `TEST_REFACTOR.md` §五 铁律（删除前先承接、collect 前后对照、INV-* 逐条核对、分批小步全绿）。
- **语义取舍**：test_mode/IsolationPolicy 字段为新增 additive，不破坏现有行为。
- **禁止范围**：不触碰 `main`；不做 media/跨进程/异步/泛型类/HM 求解等非目标。

---

## 九、关联文档

- 测试体系专项规划：`tasks_docs/TEST_REFACTOR.md`（并入本任务，策略/铁律沿用）
- 矩阵核对发现：`tasks_docs/TEST_MATRIX_FINDINGS.md`（PT-TEST-1 输入）
- 调研原始报告：`tasks_docs/TEST_REFACTOR_REPORTS.md`
- 基准快照：`tasks_docs/test_baseline_20260806.txt`
- 工作模式定论：`tasks_docs/NEXT_STEPS.md` §⛔
- 长期规划：`tasks_docs/PENDING_TASKS.md`
- 工作日志：`tasks_docs/WORKLOG.md`
- 设计哲学：`.opencode/skills/design-philosophy/SKILL.md`
