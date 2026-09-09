# P7 进程级隔离 + 反射能力 —— Phase 0 只读实证设计文档

> 本文件是 P7 Phase 0（只读实证，代码零改动）的设计产出。
> 分支 = `p7-process-isolation`（自 `free-explore` 拉出）。
> 设计阶段文档规则：先 tasks_docs，落地后收敛 docs/。

---

## 一、Phase 0 ① 现状隔离边界面实证

### 1.1 当前 spawn 机制（进程内子线程）

**核心入口**：`IBCIEngine.request_spawn_isolated(entry_path|code, policy, ...)`
（`core/engine.py:626`）

**执行模型**：
```
父引擎（线程 A）
  │ request_spawn_isolated()
  │   ├─ 创建子 IBCIEngine 实例（新 scheduler + registry + module system）
  │   ├─ LLM 快照：_llm_provider.save_plugin_state() → dict
  │   └─ 启动 daemon Thread（_run_child）
  │         └─ sub_engine.run(abs_path) / sub_engine.run_string(code)
  │              └─ 子引擎独立编译 + 执行（经 TaskScheduler 驱动）
  │
  │ request_collect(handle)
  │   └─ thread.join(collect_timeout) → 提取子环境全局变量 → dict
```

**隔离面（已实现的）**：
| 面 | 机制 | 强度 |
|----|------|------|
| IBCI 变量 | 子引擎独立 scope（变量不跨边界继承） | 完全隔离 |
| IBCI 注册表 | 子引擎独立 SpecRegistry / KernelRegistry / InterOp | 完全隔离 |
| IBCI 模块系统 | 子引擎独立 ModuleManager | 完全隔离 |
| LLM provider 状态 | per-engine 实例 + snapshot 继承 | 完全隔离（继承为显式快照） |
| 文件访问 | path 校验（子 entry 须在父 project_root 内） | 软件约束（无 OS 强制） |
| 防卡死 | collect_timeout（thread.join 墙钟上限） | 软超时（daemon 孤儿继续运行） |

**共享面（进程级，IBC-Inter 无强制力）**：
| 面 | 根因 | 影响 |
|----|------|------|
| `sys.modules` | CPython 全局单例；`importlib.import_module()` 缓存 | 宿主绑定 Python 模块的模块级全局状态被所有引擎共享 |
| Python 模块级全局 | 同 `sys.modules` | 有状态 Python 包（如 DB 连接池）跨引擎泄漏 |
| OS 资源 | 同进程 | 子代码可打开父进程文件描述符、修改环境变量 |
| GIL | CPython 线程模型 | 所有引擎线程串行化（性能面，非正确性面） |
| 进程级单例 | 如 `atexit` 注册表、线程池 | 子代码可影响父进程生命周期 |

### 1.2 LLM 通道跨引擎继承

**机制**：`save_plugin_state()` → dict → `restore_plugin_state()`

**state 内容**（`ibci_modules/ibci_ai/provider_impl.py:954`）：
```python
{
    "config": dict(self._config),           # base_url, api_key, model, timeout 等
    "return_type_prompts": dict(...),       # 类型→prompt 映射
    "model_registry": {k: dict(v) for ...}, # @NAME~ 命名路由注册表
}
```

**关键属性**：**完全可序列化**（纯 dict + str/number/bool）。子引擎收到快照后
独立调用 `_init_client()` 创建自己的 OpenAI client——**不共享 HTTP client 实例**。

**进程级隔离含义**：LLM 通道天然支持跨进程——child process 独立创建 provider +
client，只需接收 config dict 即可。无需跨进程 HTTP 共享。

### 1.3 通信协议（父 ↔ 子）

**父 → 子**（输入）：
- `entry_path`（str）或 `code`（str）
- `policy`（IsolationPolicy → dict：`{collect_timeout: float|None}`）
- `llm_snapshot`（dict：config + prompts + registry）
- `project_root`（str：子引擎的根目录锚点）
- `silent`（bool）/ `output_callback`（callable，跨进程不可直接传递→需改为文件/stdout）

**子 → 父**（输出）：
- 结果变量（dict：IBCI 全局变量 → Python 基元值）
- `exit_status`（str："ok" / "error"）
- `stdout`（str：子引擎 print 捕获）
- `exception`（dict：结构化异常记录）

**关键属性**：通信面**已近全序列化**——除 `output_callback`（callable）外，所有
数据为 str/dict/bool/float。`output_callback` 可替换为"子引擎 stdout 写入 temp file"。

### 1.4 现有 `--result-json` CLI 输出

`main.py --result-json` 已输出单行 JSON trailer：
```json
{"v":1, "exit_status":"ok", "exception":null, "journal":[...], "budget":{...}, "replay":null}
```

**可扩展性**：增加 `variables` 字段即覆盖 run_isolated 的变量交换面。
子进程 = `python main.py run <file> --result-json --root <root>` 已有完整
执行能力，**零新"child runner"代码**。

### 1.5 文件沙箱现状

**当前**：软件级 path 校验（`_validate_and_derive_isolated`：子 entry 须在父
project_root 内）。子代码执行期间对文件系统的访问无 OS 级限制。

**进程级隔离后的增强机会**：
- Linux：`seccomp` / `landlock` / `namespaces`（未来可选增强，非 P7 必须）
- 基础增强：子进程 `cwd` 设为 project_root + `os.umask` 收紧

---

## 二、Phase 0 ② 进程隔离实现形态对比（对照 9 项 VM 不变量）

### 2.1 候选形态

| 形态 | 机制 | 序列化 | 进程管理 | 优势 | 劣势 |
|------|------|--------|---------|------|------|
| **A. subprocess + JSON 协议** | `subprocess.Popen([python, main.py, "run", ...])` | JSON（stdin 文件 + stdout 解析） | OS 进程（wait/kill） | 最干净边界；复用现有 CLI；无 pickle 安全面 | 启动慢（~200ms）；IPC 仅 stdio |
| **B. multiprocessing (fork)** | `multiprocessing.Process(target=_run_in_child)` | Python pickle（Queue/Pipe） | `process.join()` | Python 原生；启动快（fork COW） | pickle 安全面（需白名单）；fork 语义微妙 |
| **C. multiprocessing (spawn)** | `multiprocessing.Process` + spawn context | Python pickle | `process.join()` | 无 fork 语义问题 | 同 B + 启动慢（新解释器） |

### 2.2 对照 9 项 VM 不变量

| # | 不变量 | subprocess+JSON | multiprocessing(fork) | 判定 |
|---|--------|----------------|----------------------|------|
| 1 | 统一执行入口 | ✅ 子进程内部仍经 TaskScheduler 驱动 | ✅ 同左 | 两者均满足 |
| 2 | 控制流数据化 | ✅ 子进程独立 Signal 体系 | ✅ 同左 | 两者均满足 |
| 3 | 执行帧抽象 | ✅ 子进程独立 frame stack | ✅ 同左 | 两者均满足 |
| 4 | LLM 通道唯一 | ✅ 子进程独立 provider 实例（经 config 创建） | ✅ 同左 | 两者均满足 |
| 5 | 公理层无运行时依赖 | ✅ 不变 | ✅ 不变 | 两者均满足 |
| 6 | isinstance 禁用 | ✅ 不变 | ✅ 不变 | 两者均满足 |
| 7 | 快照隔离不变量 | ✅ 不变 | ✅ 不变 | 两者均满足 |
| 8 | 阻塞即挂起 | ✅ 子进程内部 LLM 调用仍经 Waitable + 调度器 | ✅ 同左 | 两者均满足 |
| 9 | 调度器永不阻塞 | ✅ 父引擎 `subprocess.wait()` 非 VM 调度器路径（ihost collect 是 host 服务调用） | ✅ 同左 | 两者均满足 |

**结论**：两种形态均不违反 9 项不变量。不变量是语言执行模型约束，与宿主进程管理无关。

### 2.3 裁定：推荐 **形态 A（subprocess + JSON 协议）**

**理由**：
1. **最干净边界**：子进程是完全独立的 Python 解释器——零共享状态（连 `sys.modules`
   都不共享），无 fork COW 微妙语义
2. **复用现有 CLI**：子进程 = `python main.py run <file> --result-json --root <root>`
   ——零新"child runner"代码，CLI 已有完整执行能力
3. **无 pickle 安全面**：JSON 序列化天然安全（无 `__reduce__` 执行面）——
   避免 P5 缓存已踩过的 pickle 白名单坑
4. **资源限制**：OS 级 `resource.setrlimit` / cgroups 可直接施加于子进程
5. **可调试性**：子进程可独立运行/调试/strace
6. **可移植性**：subprocess 在 Linux/macOS/Windows 一致（multiprocessing fork 在
   macOS 3.8+ 已改 spawn）

**性能代价**：子进程启动 ~200ms（Python 解释器初始化）。对比当前子线程 ~1ms。
**缓解**：候选验证场景（非热循环）完全可接受（与 KNOWN_LIMITS §二十六 性能边界一致）。
热循环高频 spawn = P5 artifact 缓存 + P4 JIT 已解决的域。

### 2.4 协议设计（subprocess + JSON）

**输入协议**（父 → 子）：
```
命令行：python main.py run <entry_file> --root <project_root>
        --result-json --no-journal --isolated
        --llm-config <temp_json_path>    [LLM 快照]
        --collect-timeout <seconds>     [防卡死]
        --export-variables              [启用变量导出]
```

其中 `--llm-config` 指向一个 temp JSON 文件（内容 = `save_plugin_state()` 输出），
子进程启动时经既有 `load_project_config` 等价路径加载。

**输出协议**（子 → 父，stdout 末行 JSON）：
```json
{
  "v": 2,
  "exit_status": "ok" | "error",
  "exception": null | {"code": "...", "message": "...", "source": {...}},
  "variables": {...},          [仅 --export-variables 时]
  "stdout": "...",             [子引擎 print 捕获]
  "journal": [...],
  "budget": {...}
}
```

**进程管理**：
- 父：`subprocess.Popen(...)` → `proc.wait(timeout=collect_timeout)`
- 超时：`proc.kill()` + 读 stderr（子进程可被 OS 强杀——与线程 daemon 孤儿不同）
- 取消：`proc.kill()`（SIGTERM → SIGKILL 升级）

### 2.5 对现有 API 的影响

**用户面不变**（IBCI 脚本视角）：
- `ihost.run_file(path, policy) -> run_result` — 不变
- `ihost.run_code(code, policy) -> run_result` — 不变
- `ihost.run_isolated(path, policy) -> awaitable` — 不变
- `ihost.spawn_isolated(path, policy) -> handle` — 不变
- `ihost.collect(handle) -> awaitable` — 不变

**实现面变化**（内核视角）：
- `request_spawn_isolated` 内部从 `threading.Thread` 改为 `subprocess.Popen`
- `request_collect` 内部从 `thread.join()` 改为 `proc.wait()` + JSON 解析
- LLM 继承从 in-memory dict 传递改为 temp file（JSON）传递
- `output_callback` 从 callable 改为 stdout 捕获（subprocess `stdout=PIPE`）
- 新增：子进程资源限制（可选 `IsolationPolicy.resource_limits` 字段）

---

## 三、Phase 0 ③ 反射能力消费方重估

### 3.1 原始登记（F5 评估 2026-08-18）

> 档 B 真 JIT / 隔离改造 / 反射能力：无当前可验证收益/消费方 → pending 规划

### 3.2 新消费方识别（Round4 需求单）

**Round4 需求单（VISION-8）本身即反射能力的新消费方集**：

| Round4 需求域 | 反射能力消费场景 |
|--------------|----------------|
| MEM 记忆基底 | 查询当前引擎的记忆层状态（`mem.tiers()` / `mem.size(tier)`）——需引擎暴露运行时注册表信息 |
| REC 召回策略 | 查询召回决策（所用 instruction / 维度 / 成本 / relevance）——需引擎暴露 LLM 调用元数据 |
| SELF 自修改 | 查询当前行为模式/策略/不变量——需引擎暴露策略层状态 |
| OBS 可观测 | 持续活体快照（`observe.snapshot()`）——需引擎暴露 scheduler 状态 / 帧栈 / 注册表 |
| COST 成本调度 | 查询当前 run 的 token/call/wall 统计——需引擎暴露预算/遥测数据 |
| TYPE 类型基底 | 类型内省（`type(x).name` / `type(x).members`）——需引擎暴露类型系统查询面 |

**裁定**：**反射能力不延期**。Round4 的 OBS 域（持续活体快照 / 召回审计 / 自修改
审计）直接需要"从 IBCI 代码内部检视自身运行时状态"——这是反射能力的核心场景。

### 3.3 反射能力范围界定

**P7 范围内（本次实施）**：
- 反射 = 为 Round4 的 OBS 域提供**内核查询面**（API 骨架），非完整反射系统
- 具体 = 引擎级 `idbg` 模块扩展（既有诊断模块）或新 `inspect` 模块面：
  - `inspect.engine_info() -> dict`（引擎标识 / 注册表规模 / 模块表）
  - `inspect.type_info(value) -> dict`（类型名 / 协议满足 / 成员面）
  - `inspect.run_summary() -> dict`（tokens / calls / wall / budget）
- **不含**：类型系统完整内省（VISION-4 域）/ 代码生成（meta 层已有）/ 运行时热修改

**与 P7 进程隔离的关系**：
- 反射能力是**纯新增面**（新模块/新 API），不改变执行模型
- 可与进程隔离并行/独立实施
- 进程隔离后，子进程中的反射查询仍正常工作（子进程有完整的引擎实例）

### 3.4 反射实施排布

反射能力**不阻塞 P7 进程隔离**——它是 Round4 OBS 域的前置件，排在 Phase B（MEM+REC）
之后实施（OBS-1 持续活体快照是第一个具体消费方）。P7 范围内仅登记方向 + 设计输入，
不实施。

---

## 四、Phase 0 ④ VISION-4 类型层交点联合重估

### 4.1 交点识别

VISION-4 类型层承诺清单（5 项）：
1. `compile(code: str) -> CompilationArtifact`（编译工件作类型值）
2. `run_file(path, policy) -> RunResult`（执行结果作类型值）
3. 行为表达式值类型（`BehaviorExpr`）
4. `fn[...]` 高阶签名支持
5. `判定结果类型`（`Verdict`）

**与 P7 进程隔离的交点**：

| 类型层项 | 交点 | 影响 |
|---------|------|------|
| ① CompilationArtifact 作类型值 | 子进程编译产物如何传回父进程？ | **强交点**：artifact 是编译产物（AST + 符号表 + 类型信息），跨进程需序列化 |
| ② RunResult 作类型值 | `ihost.run_file/run_code` 返回值 | **弱交点**：RunResult 已是结构化 dict（exit_status/stdout/exception），跨进程 JSON 序列化直接工作 |
| ③ BehaviorExpr 值类型 | 无直接交点 | 无 |
| ④ fn[...] 高阶签名 | 无直接交点 | 无 |
| ⑤ Verdict 判定结果 | 调用方在父进程判定子结果 | **弱交点**：Verdict 是父进程值，不涉及跨进程 |

### 4.2 裁定

- **RunResult（②）已就绪**：MVP 已落地 `run_result` 值类型（三字段结构化），JSON 序列化
  直接工作。P7 进程隔离不阻塞此项。
- **CompilationArtifact（①）是远期项**：artifact 序列化跨进程是 VISION-4 类型层深化
  的问题（序列化保真 + 类型身份保持），非 P7 必须。P7 范围内子进程执行完代码返回
  `RunResult`（变量 + 状态），不返回原始 artifact。
- **P7 不阻塞 VISION-4，VISION-4 不阻塞 P7**：两者正交，按独立主线推进。

---

## 五、P7 实施批次规划（Phase 0 产出 → Phase 1+ 输入）

### 5.1 批次划分

| 批次 | 内容 | 依赖 | 风险 |
|------|------|------|------|
| **B1** | 进程隔离核心：`request_spawn_isolated` 从 threading → subprocess（含 `request_collect` / 超时 / kill） | Phase 0 设计 | 中（执行模型边界改变） |
| **B2** | LLM 继承跨进程：`save_plugin_state` → temp JSON file → 子进程 `load_project_config` 等价路径 | B1 | 低（序列化已验证） |
| **B3** | 变量导出协议：子进程 `--export-variables` + stdout 末行 JSON 扩展 + 父进程解析 | B1 | 低（JSON 协议） |
| **B4** | 资源限制：`IsolationPolicy` 扩展 `resource_limits` 字段 + `subprocess` preexec_fn（RLIMIT_AS/RLIMIT_CPU） | B1 | 低（OS 原语） |
| **B5** | 文档收敛 + KNOWN_LIMITS §二十六 更新 + 判别测试套件 | B1-B4 | 低 |

### 5.2 每批放行门

- 全量 pytest 零回归
- 判别测试（进程隔离特性：子进程崩溃不杀父 / 变量不泄漏 / 超时 kill / LLM 继承正确）
- 残留扫描（无 `threading.Thread` 残留于 spawn 路径）

### 5.3 硬约束

- 9 项 VM 不变量（§11）
- 工作模式定论九条
- 禁 push
- 详尽落账（WORKLOG）
- 性能锚：`scripts/perf_bench.py`（数据平面不受影响——spawn 非热路径）

---

## 六、风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| 子进程启动延迟（~200ms） | 高频 spawn 场景性能退化 | 候选验证场景可接受；热循环 = P5 缓存域；性能锚验证 |
| 子进程 OOM 杀死父进程 | 稳定性 | `resource.setrlimit(RLIMIT_AS)` 限制子进程内存 |
| 子进程 hang（LLM 超时） | 父进程阻塞 | `collect_timeout` → `proc.wait(timeout)` + `proc.kill()` |
| temp file 竞争（多子进程） | 正确性 | 每子进程独立 temp file（uuid 命名）+ 原子写入 |
| 子进程 Python 版本不一致 | 兼容性 | 使用同一解释器（`sys.executable`）——同 venv |

---

## 七、开放问题（Phase 1 设计确认）

1. **子进程入口**：复用 `main.py run` CLI 还是新增 `core/process_runner.py` 独立入口？
   推荐 = 复用 CLI（零新代码 + 已有 `--result-json` 基础）；Phase 1 确认。
2. **stdout 分离**：子引擎 print 输出 vs result JSON trailer 如何分离？
   方案 = result JSON 走 stderr（或 stdout 末行约定）；print 走 stdout。Phase 1 确认。
3. **取消语义**：父进程取消子进程（`proc.kill()`）后，`HostAwaitable` 的
   `result()` 返回什么？方案 = `RunResult(exit_status="cancelled", exception={...})`。
   Phase 1 确认。
4. **Windows 兼容性**：`subprocess` + `resource.setrlimit` 在 Windows 不可用。
   当前开发环境 = Linux；Windows 支持 = 远期（`IsolationPolicy.resource_limits`
   在 Windows 下 fail-fast 或 no-op）。

---

## 八、性能基线（改前锚）

`scripts/perf_bench.py` 当前值（post-P6，free-explore 实跑）：
- arith ~352 / branch ~494 / recurse ~2292 / string ~30 / container ~2100 / class ~1061 ms

**P7 预期影响**：数据平面**零影响**（spawn 非热路径；JIT/缓存不触碰）。
构造期影响：子进程启动 ~200ms vs 子线程 ~1ms——但仅影响 `ihost.run_file/run_code`
调用（候选验证场景），不影响主引擎执行性能。

**A/B 方法论**：`git worktree` 双树对照（改前 vs 改后），5 轮取中位。
