# P4 R-C 确定性执行模式 设计单点真理

> 状态：设计定稿（2026-09-10，P4 批次开工）。主线设计 = `_world_model_db_design.md`
> §3.3/§6-P4；试用方验收 = R-C（结构化代码路径零 LLM 调用、多次运行逐字节
> 可复现、"LLM 调用次数=0" 审计凭证可机读）+ M1（load_kb 后确定性模式
> quote/eval 一条事实全程零 LLM 可复现——P2/P3 已落，P4 = M1 余项）。
> 本文 = P4 机制裁定（self-grill 全分支消解记录）。P4 收束后删除。

## 1. 面定位（机制同构裁定）

**面 = CLI `run --deterministic` + 引擎级 `deterministic_guard` 参数**
（同 `budget_guard` 装配路径）+ result-json 审计凭证字段。

```
python main.py run script.ibci --deterministic --result-json
# → stdout: 数据面（print 输出）+ 末行 result-json trailer：
#   {"v":1, "exit_status":"ok", ..., "deterministic":{"enforced":true,"llm_calls":0}}
```

**为何是 CLI flag + 引擎参数（非新 IBCI 模块）**（消解）：试用方请求字面 =
"如 `run --deterministic` 或等价"——run 级执行模式是宿主装配语义（同
journal/budget/replay 三兄弟——全部 = CLI 创建、引擎挂载、汇点消费），非
语言内语义（脚本内容不因模式改变——模式作用于 run）。语言内无新面
（M1 脚本 = 纯 IBCI 代码 + CLI flag；后续如试用方需要语言内断言面再扩，
不预置）。

## 2. 机制 = LLM 调用汇点 guard（journal/budget 同点同边界）

- **guard 类**：`DeterministicGuard`（`core/runtime/observability/deterministic.py`
  新模块，observability 包三兄弟：journal/budget/deterministic）：
  - `check_pre_call(node_uid)` = **无条件 fail-fast**
    （`InterpreterError` + 新码 `RUN_DETERMINISTIC_LLM_CALL`）——provider 调用
    **前**拦截（结构性零 LLM：被拦调用不发出、无部分 LLM 态、无 API key 消耗）；
  - `snapshot()` = `{"enforced": true, "llm_calls": 0}`（凭证——机读"LLM
    调用次数=0"；guard 拦截在前，post-call 永不达 → 计数恒 0 = 结构事实）。
- **装配**（同 budget 逐点同构）：ServiceContext `set_deterministic_guard`/
  `deterministic_guard` 属性 → `_call_llm` 汇点 budget 检查**之前**检查
  （强不变量优先——deterministic = 零容忍，先于 budget 阈值面）→ 引擎
  `run/run_string/execute(..., deterministic_guard=None)` 参数（同
  `budget_guard` 行位）→ CLI `--deterministic` 创建挂载。
- **汇点覆盖面**：`_call_llm` = 单一核算点（journal/budget 同源）——覆盖
  `@~...~` 行为表达式（结构化代码路径 = 试用方验收面）。**边界（诚实记录，
  子系统既有边界同族）**：流式 `ai.stream_call`/`ai.stream_channel` 不经汇点
  （journal/budget 同边界，observability 包 docstring 已载）；`meta.eval`
  子进程 = 新引擎（guard 不跨 spawn 继承——quoted 表达式含 `@~...~` 时其
  LLM 调用属子进程面，P1 eval 环境参数边界同族；M1 事实表达式 = 纯代码，
  子进程自然零 LLM）。
- **CLI 互斥**：`--deterministic` × `--replay` = 矛盾组合（replay 供给 LLM
  响应 = 预期有 LLM 调用；deterministic = 零容忍）→ CLI 校验期 fail-fast
  （明确报错，不装入注定失败的组合）。

## 3. 新诊断码（+1，RUN_ 域）

| 码 | 语义 |
|----|------|
| `RUN_DETERMINISTIC_LLM_CALL` | 确定性执行模式（`--deterministic`）下尝试 LLM 调用——结构性拦截（零 LLM 保证的 fail-fast 面；可被 IBCI try/except 捕获） |

（与 `RUN_BUDGET_EXCEEDED` 分码：budget = 用户配置阈值（warn/fail 两面、
可超限继续）；deterministic = run 级零容忍不变量（无阈值、无 warn 面）——
不同概念不同码，单名纪律。）

## 4. 逐字节可复现（R-C 验收面 2）

零 LLM 的结构化执行 = 输出确定性（LLM 是语言内唯一非确定源；mock/真实
provider 面在 deterministic 下均被拦）。**验收实证 = M1 e2e**：同脚本经
`--deterministic --result-json` 两次独立 run（独立引擎实例）→ stdout
数据面逐字节一致 + 两次凭证均 `llm_calls: 0`。（差分 harness 语料纪律
同 P3 裁定：harness 进程内 run_string 面不挂 guard——确定性面 e2e 覆盖。）

## 5. 测试面

- **runtime**（`tests/runtime/test_deterministic_guard.py`）：guard 单元
  （check_pre_call 恒 fail-fast + 码 + snapshot 形态）；引擎面（带 guard
  run 纯代码 OK / `@~...~` fail-fast；try/except 可捕获）；
  budget×deterministic 组合（deterministic 先行拦截）。
- **e2e CLI**（M1 验收形态）：临时项目（api_config + KB artifact + 脚本：
  `load_kb` → `lookup` → `meta.quote/eval` 一条事实[数据形态 + 成立性验证]
  → print 数据面）→ 两次 `main.py run --deterministic --result-json`
  → 数据面逐字节一致 + 凭证 `deterministic.llm_calls == 0` +
  exit_status ok；`@~...~` 脚本 → RUN_DETERMINISTIC_LLM_CALL 面；
  `--deterministic --replay` 组合 → CLI 互斥 fail-fast。
- **文档**（D2）：15_diagnostics +1 码；CLI 面文档（--replay/--result-json
  所在处——定位后同步）+ KNOWN_LIMITS（流式/eval 子进程边界，若既有
  observability 边界节存在则并入）。

## 6. 批次

- **D1**：DeterministicGuard + ServiceContext + _call_llm 汇点 + 引擎参数 +
  RUN_DETERMINISTIC_LLM_CALL 码 + catalog + 15_diagnostics + runtime 测试
  + 受影响子集+smoke + commit。
- **D2**：CLI --deterministic（互斥 + result-json 凭证字段）+ M1 e2e +
  CLI/边界文档同步 + 全量放行门（语义错误集变更——新 RUN_ 码）+
  WORKLOG/NEXT_STEPS/HANDOFF + commit。
