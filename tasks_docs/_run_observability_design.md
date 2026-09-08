# run 级可观测子系统设计（R3-⑤：R-1 journal + R-3 预算 + R-4 result-json）

> 状态：设计已定稿（2026-09-08，round3 整合批；单一设计文档一批批实施）。
> 实施批次：批 1 journal → 批 2 replay → 批 3 预算 → 批 4 result-json。
> 本文 = 设计阶段单点记录（落地后按 docs/ 治理纪律择机收敛写入技术手册）。

## 一、需求与现状

### 1.1 试用方请求（round3 需求单 R-1/R-3/R-4）

- **R-1**：LLM 调用日志 append-only 记录到 `llm_journal/`（prompt 全文、raw
  响应、模型、finish_reason、generation 参数、时间戳）；`main.py run` 加
  `--replay` 确定性重放（复测/审计零 LLM 成本）。
- **R-3**：run 级预算核算（tokens/calls/wall），api_config 阈值，超限时
  fail-fast 或告警。
- **R-4**：机器可读 run 摘要 `--result-json`（exit_status +
  exception{code,message,source}）——验收机告别 grep stdout 文本面。

### 1.2 现状勘察（2026-09-08 实码核验）

| 面 | 现状 | 复用性 |
|----|------|--------|
| LLM 调用汇点 | `LLMExecutorCore._call_llm(request)`（`core/runtime/interpreter/llm_executor/_core.py`）——**单一汇点**：全部 LLM 调用（behavior/llm 可调用/batch 同步面）经此委托 provider；持有 request（user_prompt）+ result（content/raw_response/finish_reason/provider_meta[sys_prompt/generation/reasoning]）+ 错误面 + 事件面（llm_dispatched/llm_resolved） | journal 挂接点（唯一） |
| 调用追踪 | `_call_trace`（有界 deque 64，内存）/ `_current_call_info`（单写槽）/ idbg 内省 / `get_current_call_info` ibci 面 | 内存调试面（保留）；journal = 持久审计面（新增 sink，同汇点同源数据） |
| 事件总线 | `core/runtime/observability/events.py`（EventBus = ChannelCore pubsub，引擎级单实例；事件轻负载：node_uid/response/error） | 不承载 journal（重负载 append-only 与轻负载内存 pubsub 职责分离——见 §3.5） |
| 配置契约 | `core/base/llm_protocol/config.py`（ModelSpec：generation 参数/timeout/extra_body）；api_config.json 书写格式 = 推荐适配器（`recommended.py`） | budget = api_config 顶层新增可选节（run 级，非模型级）；推荐适配器透传（批 3 详设） |
| provider 响应 | `provider_meta` 已含 sys_prompt/finish_reason/reasoning/generation；**缺 usage**（tokens 未从 API 响应提取） | 批 3 小增项：provider 提取 `usage` 入 provider_meta（契约不变——provider_meta 即指定的瞬态观测通道） |
| 诊断渲染 | CLI run 已有编译错误/运行期错误渲染路径（`_render_runtime_error`；诊断对象自带 code+message+source 定位） | result-json 复用诊断对象提取（无新渲染管线） |
| C7（原批 3 P2） | 性能内省（单调时钟/调用级埋点）——批 3 目标 | **消重**：调用级埋点面 = journal 行（每调用一行含 ts_mono）+ 预算核算（wall/calls/tokens 累计）；C7 独立批取消，需求由本子系统承载（本设计 = 其实现载体） |

## 二、总体架构

```
main.py run [--replay <journal>] [--result-json] [--no-journal]
   │
   ├─ 启动期（engine 构造后、run 前）：
   │    - journal 初始化（--replay 时：replay provider 注册为 CAP_LLM_PROVIDER，
   │      真实 provider 不加载；否则：真实 provider + journal sink 挂 _call_llm）
   │    - 预算核算器初始化（api_config budget 节；无节 = 无预算）
   │    - run 起始时间戳（monotonic + wall）
   │
   ├─ run 期：
   │    _call_llm（单一汇点）：
   │       1. 预算检查（fail 模式超限 → ThrownException RUN_BUDGET_EXCEEDED，
   │          provider 调用前——确定性拦截）
   │       2. provider.call(request)（真实 / replay / mock 三形态同槽）
   │       3. journal append（seq/ts/ts_mono/node_uid/model/prompts/
   │          content/raw/finish_reason/usage/error）
   │       4. 预算累计（calls+1 / tokens+=usage.total / wall 刷新）
   │
   └─ 收尾期（run 完成/失败后、exit 前）：
        - result-json trailer（stdout 末行 JSON：exit_status/exception/
          journal 路径/budget 快照）
        - journal 文件头行（run 元数据：run-id/入口文件/时间/replay 源）
```

**三形态 provider 同槽**（机制同构）：真实 provider（api_config）/ replay
provider（本设计新增，CLI 级）/ mock provider（既有 `ai.set_mock_mode()`，
ibci 内）——全部经 `CAP_LLM_PROVIDER` 能力槽或 ibci 内 mock 分派；journal/
预算对三形态**统一生效**（mock 调用同样记账——审计完整性：mock run 的
journal 可重放 mock run）。优先级：--replay（CLI 级，最高）> mock（ibci 级）。

## 三、journal（批 1）

### 3.1 契约（schema v1，版本化）

文件：`<root_dir>/llm_journal/<run-id>.jsonl`（root_dir = --root 或自动检测
的项目根；run-id = `<UTC 时间戳>-<4 hex>`，如 `20260908T120000Z-a1b2`）。

- **首行** = run 元数据：
  `{"v":1,"type":"run","run_id":"...","entry":"...","started_at":"ISO8601",
  "replay_of":null|"llm_journal/<src>.jsonl"}`
- **每调用一行**（append-only，一行一次 LLM 调用，seq 单调递增）：
  `{"v":1,"type":"call","seq":0,"ts":1788888274.837,"ts_mono":123.45,
   "node_uid":"...","target_model":"...",
   "sys_prompt":"<全文>","user_prompt":"<全文>",
   "content":"<全文>","raw_response":"<全文>",
   "finish_reason":"stop"|null,
   "generation":{...},          // provider_meta.generation（有效值）
   "usage":{"input_tokens":n,"output_tokens":n,"total_tokens":n}|null,
   "error":null|"..."}`
- **字段缺失语义**：usage=null = provider 未上报（预算面按 0 计，见 §4）；
  error 非 null = provider 层失败（该次调用以 LLMCallError 告终——重放时
  同形态 raise，审计完整性）。
- **prompt 全文**（非哈希）：replay 需精确提示词；审计语料需原文。体积
  约束 = 用户可 `--no-journal`（默认开——试用方请求形态；审计基底定位）。

### 3.2 挂接与写入

- 汇点 `_call_llm` 内新增 journal sink 调用（成功/失败两面均记录）；
  journal writer = `core/runtime/observability/llm_journal.py`
  （`LLMJournalWriter`：open/append/close；同步 append + flush 每行——
  append-only 语义 = 每次写入后文件立即可读（崩溃不丢已 flush 行））。
- **写入失败语义**：journal 是观测侧信道（与事件总线尽力而为同定位）——
  写失败 = kernel_diagnostic 事件 + stderr 告警，**不阻断 run**（run 是
  主目的；审计缺失以告警显形，不静默也不崩溃）。
- 引擎级单实例（与 EventBus 同级：引擎生命周期）；CLI run 创建/收尾；
  Python API（engine.run 无 journal 参数）默认**不**创建——journal 是
  CLI 审计面（批 1 裁定：API 面挂接后续批次评估，不扩散）。

### 3.3 覆盖边界（诚实记录）

- 同步 LLM 调用面（behavior 表达式同步面 / llm 可调用 `q(args)` /
  run_batch 逐项）= 全部经 `_call_llm` ✓ 覆盖。
- **流式**（stream_call/stream_channel）不经 `_call_llm`（既有边界，
  KNOWN_LIMITS §十五 call_info 同边界）→ journal 不覆盖流式（文档明示，
  与 call_info 边界一致）。
- 并行 dispatch（CPS future）：resolve 点经同一 `_call_llm`（worker 线程
  调用）→ 覆盖；行序 = 实际发生序（seq 由 writer 原子分配，多线程安全）。

### 3.4 CLI 面

- 默认开：`main.py run` 自动创建 journal（root_dir 下）；run 启动时
  **stderr** 输出一行 `journal: llm_journal/<run-id>.jsonl`（stdout 是
  数据面——审计提示不入 stdout）。
- `--no-journal` 关闭（无 journal 目录创建、无 stderr 行）。
- `--replay <path>`（批 2 面，此处声明交互）：replay 模式仍写新 journal
  （记录"重放 run"——审计链完整：新 run 的 journal 首行 replay_of 指向源）。

### 3.5 与既有内存面的分离（单点真理表）

| 面 | 载体 | 生命周期 | 用途 |
|----|------|----------|------|
| journal（新） | 磁盘 JSONL，append-only | run 级持久 | 审计/重放/预算核算语料 |
| _call_trace | 内存 deque(64) | 引擎级 | idbg/调试内省（最近 64 次） |
| _current_call_info | 内存单写槽 | 引擎级 | ibci `get_current_call_info` 面 |
| 事件总线 | 内存 pubsub | 引擎级 | 生命周期事件（轻负载） |

数据同源（_call_llm 汇点的同一 request/result），四个视图服务四种用途；
**无第二条调用管线**（journal 不改变调用路径，只追加 sink）。

## 四、预算核算（批 3）

### 4.1 配置（api_config.json 顶层新增可选节）

```json
{
  "budget": {
    "max_tokens": 100000,
    "max_calls": 500,
    "max_wall_s": 600,
    "on_exceed": "warn"
  }
}
```

- 全节可选；缺省 = 无预算核算（行为与现状完全一致——零侵入）。
- `on_exceed`: `"warn"`（默认：stderr 告警 + result-json budget.exceeded
  标记，run 继续）| `"fail"`（下次 LLM 调用前拦截：ThrownException
  `RUN_BUDGET_EXCEEDED`，消息含超限维度与当前/阈值——确定性拦截点 =
  provider 调用前，不浪费一次真实调用）。
- 配置形态错误（类型错/负值/未知 on_exceed）→ `CFG_CONFIG_INVALID_BUDGET`
  （CFG_ 域，加载期 fail-fast）。

### 4.2 核算

- 核算点 = journal 汇点（单一核算点，每调用一行账）：
  calls = seq+1；tokens += usage.total_tokens（usage 缺失 = 0——预算是
  上限保护不是精确会计；provider 未上报 usage 的场景以 calls/wall 兜底）；
  wall = monotonic（run 起始 → 当前）。
- provider 增项（批 3）：API 响应 `usage` 提取入 `provider_meta["usage"]`
  （OpenAI 兼容字段 prompt_tokens/completion_tokens/total_tokens；
  契约不变——provider_meta 即瞬态观测通道，既有 finish_reason/generation
  同机制）。
- wall 核算时机：每次 LLM 调用点检查（非轮询——无后台线程，机制简单；
  两次调用间的长非 LLM 段不检查 = 已知边界，文档记录：预算面 = LLM 面
  预算，非全进程墙钟预算）。

### 4.3 C7 消重记录

原批 3 P2 C7（性能内省：单调时钟/调用级埋点）由本子系统承载：调用级
埋点 = journal 行（每调用 ts/ts_mono）+ 预算累计（wall/calls/tokens）。
C7 独立批**取消**（`_next_phase_targets.md` 批 3 清单中 C7 标记"由 R3-⑤
run 级可观测子系统承载，消重"）；未来若需 ibci 内"调用级性能查询"面，
为 journal/observability 面的扩展（同一汇点，不开第二条埋点管线）。

## 五、确定性重放（批 2）

### 5.1 语义

`main.py run <file> --replay llm_journal/<src>.jsonl`：

- replay provider 按 journal 中 type=call 行的 **seq 序**依次返回记录的
  LLMCallResult（content/raw_response/finish_reason/provider_meta 原样
  重建）；记录的 error 行 → 同形态 raise（LLMCallError 语义）。
- **确定性**：同一入口代码 + 同一 journal = 同一执行轨迹（控制流由代码
  决定；LLM 输出全部来自记录）。真实 provider 不加载（无需 API key）。
- **耗尽 = fail-fast**：代码请求次数 > journal 记录次数 → 新诊断
  `RUN_REPLAY_EXHAUSTED`（"replay journal exhausted at call #N — code
  diverges from the recorded run"）——代码相对记录 run 变更了，诚实失败
  （不静默回落真实 provider——重放的确定性承诺不容破坏）。
- **提前结束 = 正常**：run 在 journal 耗尽前结束（控制流分支少走了调用）
  = 合法（剩余行未消费，result-json 记录 consumed/total）。

### 5.2 机制

- `ReplayLLMProvider`（实现 `LLMProvider` 协议，`ibci_modules/ibci_ai/`
  或 `core/runtime/`？——**裁定：`core/runtime/replay/` 独立小模块**：
  重放是引擎级机制（CLI 驱动），不属 ai 插件（插件 = 供应商调用服务；
  重放器是 provider 的一种实现形态，经 CAP_LLM_PROVIDER 槽注册——机制
  同构：provider 就是 provider））。
- CLI 启动期注册（engine 构造后、run 前）：`capability_registry.expose(
  CAP_LLM_PROVIDER, replay_provider)`（替换真实 provider 的槽位——ibci_ai
  插件加载时序在 run 前：CLI replay 模式**跳过** ibci_ai 的真实 provider
  注册或后置覆盖——批 2 实施时按插件加载时序定案，设计意图 = 槽内唯一
  生效 provider 为 replay）。
- journal 读取校验：首行 v/type=run 校验（格式错 → CLI 启动期
  `CFG_` 域诊断 fail-fast）；call 行逐行解析（损坏行 → fail-fast，不
  跳过——审计文件的完整性不容部分消费）。

## 六、result-json（批 4）

### 6.1 契约（stdout 末行 trailer，版本化）

`main.py run <file> --result-json`：run 全部输出完成后，stdout **末行**
输出一行 JSON（机器可解析：`tail -n1`）：

```json
{"v":1,
 "exit_status":"ok"|"error",
 "exception":null|{
   "code":"RUN_TYPE_MISMATCH",
   "message":"...",
   "source":{"file":"main.ibci","line":12,"column":3,"snippet":"..."}
 },
 "journal":"llm_journal/20260908T120000Z-a1b2.jsonl"|null,
 "budget":{"calls":42,"tokens":10240,"wall_s":12.3,"exceeded":false}|null,
 "replay":{"source":"llm_journal/....jsonl","consumed":42,"total":42}|null}
```

- **exit_status**：`ok` = 正常结束；`error` = 编译错误或运行期异常
  （非零退出码不变——exit_status 是机读补充，不替代退出码语义）。
- **exception**：复用既有诊断对象提取（编译错误 = 首个诊断；运行期 =
  抛出异常的诊断码/消息/源定位）——无新渲染管线；source.snippet = 源行
  （既有 caret 渲染同源数据）。
- **journal/budget/replay**：无对应面 = null（--no-journal / 无 budget 节
  / 非 replay 模式）。
- trailer 与数据面分离：trailer 总在末行；数据面（print 输出）不受影响
  （验收机：数据 = 前 N-1 行，结果 = 末行解析）。

## 七、新增诊断码（纯增面，不改动既有码）

| 码 | 域 | 触发 |
|----|----|------|
| `RUN_REPLAY_EXHAUSTED` | RUN_ | replay journal 耗尽（调用次数超记录） |
| `RUN_BUDGET_EXCEEDED` | RUN_ | budget on_exceed=fail 且超限（provider 调用前拦截） |
| `CFG_CONFIG_INVALID_BUDGET` | CFG_ | budget 节形态错误（加载期 fail-fast） |
| `CFG_JOURNAL_INVALID` | CFG_ | --replay 源 journal 格式损坏/不合法（启动期 fail-fast） |

（语义错误集变更 → 每批实施后全量 pytest 破坏面评估；15_diagnostics 同步。）

## 八、质量红线自查（对照工作模式定论）

- **单一权威源**：调用记录 = _call_llm 汇点单点（journal/预算/事件/call_info
  同源）；预算核算 = 汇点单点；provider 槽 = 能力注册单槽。
- **机制同构**：replay provider = LLMProvider 实现形态（同 mock/真实）；
  journal writer = 引擎级单例服务（同 EventBus 定位）；诊断码 = 既有域
  扩展（RUN_/CFG_）。
- **无兼容层**：既有内存面（_call_trace 等）保留为调试面（用途分离非兼容）；
  无 journal 旧路径分支（journal 新面，无旧行为需兼容）。
- **无兜底**：replay 耗尽/预算超限/配置损坏均 fail-fast（诚实错误，不静默
  降级）；journal 写失败 = 告警不阻断（观测侧信道定位，与事件总线一致，
  非"兜底"——审计缺失显形）。
- **fail-fast 纪律**：budget fail 模式在 provider 调用前拦截（确定性、
  零浪费）。

## 九、实施批次与验证面

| 批 | 内容 | 判别测试面 |
|----|------|-----------|
| 1 | journal writer + 汇点挂接 + CLI 默认开/--no-journal + stderr 行 | 文件生成/首行元数据/seq 单调/字段完备（mock run）/写失败告警不阻断/--no-journal 无目录/流式边界文档 |
| 2 | replay provider + 槽注册 + 耗尽/提前结束 + CFG_JOURNAL_INVALID | mock 录制 → replay 确定性（同轨迹）/耗尽 fail-fast/提前结束合法/损坏行 fail-fast/真实 provider 未加载（无 key 可跑） |
| 3 | budget 配置 + 核算 + warn/fail + provider usage 提取 + CFG_CONFIG_INVALID_BUDGET | warn 不阻断+标记/fail 拦截点（provider 前）/tokens 累计（含 usage 缺失=0）/calls/wall 维度/配置错 fail-fast/C7 消重记录 |
| 4 | result-json trailer + 三 exit 面 | ok/error（运行期）/error（编译期）/journal/budget/replay 字段联动/末行可解析（tail -n1） |

每批：全量 pytest 零回归 + commit + 落账（WORKLOG/NEXT_STEPS/HANDOFF/
intake 状态行/15_diagnostics 新码/00 或 17 文档面按批收敛）。
