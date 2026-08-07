# DIAGNOSTIC_DESIGN — 内核结构化诊断机制设计（PT-FEAT-9，设计冻结）

> **性质**：设计阶段任务控制文档（先于实现，落地后按 docs/ 治理纪律择机收敛写入技术手册）。
> **关联**：`PENDING_TASKS.md` §12 交接要点｜`OBSERVABILITY_REFACTOR.md`（2A 决策记录）｜
> `core/runtime/observability/events.py`（观测骨架）。
> **最后更新**：2026-08-07

---

## 〇、结论摘要（TL;DR）

- **为什么需要**：内核 12 处运行时降级/异常/策略点目前只留下裸 `warnings` 字符串——不可查询、不可计数、不可过滤、不可程序化消费；这是内核对自身异常行为**没有结构化观测面**的真实缺口。
- **做什么**：新增一个**事件类型 `kernel_diagnostic`**（统一形态）+ **诊断码注册表 `KDIAG_*`**（统一词汇），经既有观测骨架（EventBus + `emit_runtime_event`）发射，同时保留 `warnings` 投影保证开发者可见性与零回归。
- **不做什么**：不重建旧 CORE_DEBUG（print/级别门控/全局单例）；不重建流式流程追踪；编译期诊断维持 warnings（离线面无观测骨架）。
- **核心决策**：单一记录、双投影（warnings 不门控 + 事件受 `observability` 门控）；代码即数据非发射门控；rc 解析 best-effort；诊断码并入 `codes.py` 单一注册表。

---

## 一、技术定位：为什么"一定需要"

### 1.1 现状缺口（事实）

- OBSERVABILITY 2A 已整体删除旧 CoreDebugger（88 trace）。处置分类：~73 处流程/DATA 日志**删除**（合理，不重建）；
  "真实异常回退"点改 `warnings.warn`。**实跑清点（2026-08-07）**：运行时降级/策略/异常点共 **12 处 warnings** + 编译期 1 处：
  - 协议回退 8 处（`__to_prompt__`×2、`__from_prompt__`×2、`__payload_prompt__`、`__validate_prompt__`、`__snapshot__`、`__restore__`）
  - 策略/环境 2 处（register_module 覆盖、插件无导出）
  - 运行时降级 2 处（engine.collect 跳过、STAGE 6 令牌缺失跳过）
  - 编译期 1 处（scheduler 预定义符号非 Symbol）
- 缺口本质：内核对自身"异常/降级/异常决策"**没有结构化、可查询、可计数、可过滤的记录面**——只有散落的裸字符串。

### 1.2 为什么需要独立机制（四个消费诉求）

| 诉求 | 现状 | 缺口 |
|------|------|------|
| 根因调查 | 字符串不可过滤/计数 | 无法回答"某类型 `__from_prompt__` 本轮失败几次 / 哪些站点触发" |
| 统一测试 | 仅个别站点可 `pytest.warns` 断言 | 无法统一断言"该异常以该签名发生 N 次" |
| 程序化监控 | 只能解析 stderr | 嵌入式使用方需要稳定结构化接口 |
| 设计语言统一 | 12 个站点各写各的裸字符串 | 同物多形 = 碎片化；需要一个统一形态 + 统一词汇表 |

### 1.3 反方观点（为何不另建即可满足）

| 反方 | 反驳 |
|------|------|
| "warnings 就够" | warnings 不可编程、不可计数、不可过滤；实验引擎的立身之本就是定位内核行为 |
| "加几个域事件类型就行" | 诊断不是域对象生命周期；13+ 种 kind 塞进 `type` 词汇表污染域事件；且缺统一 schema/代码表 |
| "snapshot 覆盖" | snapshot 是同步拉取（"现在是什么"）；诊断是异常/因果信号（"为何降级"），时间轴与问题不同 |

**结论**：需要一个**独立语义面**——诊断面——与状态面/事件面/测试合作面/渲染层正交，职责单一。

### 1.4 与既有机制的边界（谁做什么）

| 面 | 机制 | 形态 | 职责（一句话） |
|----|------|------|---------------|
| 状态面 | `snapshot` 聚合 | 同步拉取 | "现在是什么状态" |
| 事件面 | EventBus 域事件（llm/chan/slot） | 推送（正常流程） | "正常域对象发生了什么" |
| **诊断面（本任务，新）** | `kernel_diagnostic` 事件 + warnings 投影 | 推送（异常/降级/策略） | "**内核为何降级 / 做了什么异常决策**" |
| 测试合作面 | `ServiceContext.test_hooks` | 回调 | 测试精确回调 |
| 用户渲染层 | idbg | 渲染 | 观测数据的人类可读呈现 |

> 边界判定法：**正常流程 → 事件面；状态查询 → 状态面；异常/降级/策略 → 诊断面**。诊断面与事件面共用总线与发射入口（机制同构），仅语义域不同。

---

## 二、核心设计决策

### D1 单一事件类型 + 代码注册表（不造 13 个事件类型）

- 事件 `type` 固定为 **`kernel_diagnostic`**；具体种类由 `data.code`（`KDIAG_*`）区分。
- 依据：
  - events.py 头注释既定原则——"事件类型是数据，不是分发条件"；域事件词汇表保持小而稳定。
  - **可扩展性**：新增诊断 = 加一个 code + 调一次 helper，**无消费者变更、无 schema 变更**。
  - 诊断的 schema 统一（code/detail/message），不适合散成 13 个独立事件类型（各自 schema 漂移）。

### D2 单一记录、双投影（非双通道）

一次构造**一份结构化记录**，两路交付：

```
站点 ── kernel_diagnostic(code, detail, message)
        │
        ├─► 投影A：warnings.warn(message)   —— 开发者可见，不门控，文案逐字保留（零回归）
        └─► 投影B：emit_runtime_event(rc, "kernel_diagnostic", data)
                                            —— 程序化观测，受 observability 门控
```

- 依据：warnings=开发者可见通道；事件面=可编程观测通道。**语义不同，并存不冲突**（`PENDING_TASKS` §12 已预判）。
- 不是"双通道"：design-philosophy 的"同一语义两种实现"是指两套**实现**；此处是**一份记录的两路投影**（structured-logging 标准形态），消息由与 detail 同源的调用点局部变量构造，单一实现。

### D3 代码即数据，非发射门控（与旧 DebugLevel 本质不同）

- `KDIAG_*` 是**事件数据**（消费端过滤用），**不是**发射开关。
- 发射统一：总是构造记录；`observability` 开且 rc 可达 → 事件；否则仅警告。
- 与旧 CoreDebugger 的"每模块每级别门控"差异：**过滤在消费端，不在发射端**——这是"不重建旧机制"的关键分界。

### D4 rc 解析 best-effort（显式 > 当前 EC > 无）

- rc 来源优先级：显式参数 `rc=` > `get_current_execution_context().runtime_context` > None。
- rc 不可达（无活跃 EC）→ **仅警告面**（fail-open，开发者可见性不丢），事件面跳过。
- 依据：与 `callables.py` 既有 current-EC 回退范式同构（`get_current_execution_context() or self._execution_context`）；
  低层站点（IbObject 方法）**无需穿线 rc**，避免侵入式改造。
- 实现要点：`kernel_diagnostic` 内先 `warnings.warn`（不依赖 rc），再做 rc 解析 + 门控 + 发射。

### D5 范围边界（三个明确）

1. **迁移**：12 处运行时 warnings 站点 → `kernel_diagnostic`（**文案逐字保留**）。
2. **保持 warnings**：编译期 1 处（scheduler.py）——编译器离线、无事件总线/运行时上下文，编译面无观测骨架；
   不为此引入 compiler→runtime 跨层依赖（§十一 layering 纪律）。
3. **不重建流式流程追踪**：v1 只覆盖"异常/降级/策略"站点；流程级因果诊断（如 llmexcept 重试循环）未来可经
   新 code 扩展（机制已支持），**不在本任务范围**——尊重"禁重建旧 print 机制"与范围克制。

### D6 诊断码注册表并入 `codes.py`（单一权威源）

- `core/base/diagnostics/codes.py` 是既定"诊断码注册表"（常量名=值=单点真理，按域分组注释）。
- 新增 `=== 内核诊断 (KDIAG_) ===` 节。
- 依据：与 `SEM_`/`RUN_`/`LEX_` 等**同一命名约定**（设计语言统一）；单一注册表防双维护。
- codes.py 在 `core/base/` 基层，无依赖，编译器/运行时均可引用（常量零成本）。

### D7 v1 不引入 severity/category 字段

- 现状 12 站点全部等价（warning 级）；域前缀已编码在 code 名（`KDIAG_PROTOCOL_*`/`KDIAG_POLICY_*`/`KDIAG_RUNTIME_*`）。
- 事件 data 为自由 dict，未来加字段非破坏（可扩展性，不提前设字段）。

---

## 三、事件形态与 schema（设计冻结）

```python
{
  "type": "kernel_diagnostic",
  "data": {
    "code":    "KDIAG_PROTOCOL_FROM_PROMPT_FALLBACK",  # 稳定机器标识（codes.py 常量）
    "detail":  {"type_name": "Point", "error": "ValueError(...)", ...},  # JSON-safe 站点载荷
    "message": "__from_prompt__ parse failed for Point: ValueError(...)",  # 人类可读投影
  },
}
```

发射 helper（`core/runtime/observability/diagnostics.py`）：

```python
def kernel_diagnostic(code, detail=None, message=None, *, rc=None):
    """记录一条内核诊断（异常/降级/策略）。

    投影A（开发者可见，不门控）：warnings.warn(message, stacklevel=3)
        —— stacklevel=3 使归属行与现状一致（站点内直接 warnings.warn(stacklevel=2)）。
         message 缺省时生成 f"{code}: {detail!r}"。
    投影B（程序化观测，受 observability 门控）：
        rc = rc or (get_current_execution_context() 的 runtime_context)
        rc 不可达 → 仅投影A。
        observability 关 → 事件跳过，警告保留。
    经 emit_runtime_event 统一发射入口（机制同构，零订阅者零成本）。
    """
```

**消息与 detail 的关系**：两者由调用点**同一批局部变量**构造（同源），消息是 detail 的人类可读投影，漂移风险低；
新站点若只关心结构化消费，可省略 message（用缺省生成式）。

---

## 四、诊断码集（设计冻结）

> 10 码覆盖 12 处运行时站点。前缀 = 域（PROTOCOL/POLICY/RUNTIME）；站点定位信息进 `detail`（如 `context`）。

| code | 站点 | 现状消息（逐字保留） |
|------|------|---------------------|
| `KDIAG_PROTOCOL_TO_PROMPT_FALLBACK` | `intent.py:74`（意图内容解析，context=`intent_resolution`） | `__to_prompt__ failed in intent resolution, falling back to to_native(): {e!r}` |
| `KDIAG_PROTOCOL_TO_PROMPT_FALLBACK` | `kernel/base.py:103`（cast 经 `__to_prompt__`，context=`cast`） | `cast via __to_prompt__ failed for {cls}->{target}: {e!r}` |
| `KDIAG_PROTOCOL_FROM_PROMPT_FALLBACK` | `kernel/base.py:138`（`__from_prompt__` 解析，context=`parse`） | `__from_prompt__ parse failed for {cls}: {e!r}` |
| `KDIAG_PROTOCOL_FROM_PROMPT_FALLBACK` | `llm_parsing_strategy.py:245`（vtable `__from_prompt__`，context=`vtable`） | `vtable __from_prompt__ failed for '{type}': {e}` |
| `KDIAG_PROTOCOL_PAYLOAD_PROMPT_FALLBACK` | `_prompt.py:91`（`__payload_prompt__`） | `__payload_prompt__ dispatch failed, falling back to text: {e!r}` |
| `KDIAG_PROTOCOL_VALIDATE_FALLBACK` | `llm_parsing_strategy.py:204`（`__validate_prompt__`） | `__validate_prompt__ failed for '{type}': {e}` |
| `KDIAG_PROTOCOL_SNAPSHOT_FALLBACK` | `llm_except_frame.py:183`（`__snapshot__`） | `__snapshot__ protocol call failed for '{name}', falling back to deep clone: {e!r}` |
| `KDIAG_PROTOCOL_RESTORE_FALLBACK` | `llm_except_frame.py:267`（`__restore__`） | `__restore__ protocol call failed for '{name}', keeping current state (best-effort): {e!r}` |
| `KDIAG_POLICY_MODULE_OVERRIDE` | `host_interface.py:67`（插件覆盖 kernel-native） | `Ignoring user plugin '{name}' (discovery_name=...): name ... is reserved for kernel-native module and cannot be overridden.` |
| `KDIAG_POLICY_MODULE_NO_EXPORT` | `loader.py:330`（插件无导出） | `Module '{module}' skipped: no create_implementation() or implementation export found` |
| `KDIAG_RUNTIME_COLLECT_SKIP` | `engine.py:840`（collect 跳过） | `collect({handle!r}) skipped non-convertible variable '{name}': {e!r}` |
| `KDIAG_RUNTIME_STAGE_SKIP` | `interpreter.py:273`（STAGE 6 令牌缺失） | `Warning: Kernel token missing in Interpreter. STAGE 6 transition skipped.` |

**边界**：scheduler.py:364（`Scheduler: predefined symbol '{name}' is not a Symbol object, skipping.`）→ **保持 warnings**（编译期，见 D5）。

---

## 五、使用模式（易用性契约）

### 发射（新增一处诊断 = 2 步，无消费者变更）

```python
# 1) codes.py 加常量
KDIAG_PROTOCOL_RESTORE_FALLBACK = "KDIAG_PROTOCOL_RESTORE_FALLBACK"

# 2) 站点调用
kernel_diagnostic(
    code=KDIAG_PROTOCOL_RESTORE_FALLBACK,
    detail={"name": name, "error": repr(e)},
    message=f"__restore__ protocol call failed for '{name}', keeping current state (best-effort): {e!r}",
)
```

### 消费（IBC 语言，与域事件同一入口）

```python
import runtime
ch = runtime.subscribe()
loop:
    e = ch.recv()
    if e["type"] == "kernel_diagnostic":
        code = e["data"]["code"]          # 过滤：code.startswith("KDIAG_PROTOCOL_")
        detail = e["data"]["detail"]
```

### 消费（Python 测试）

- 警告投影：`pytest.warns(UserWarning, match=...)`（现状不变，零回归）。
- 事件投影：经 `engine.runtime_context.get_comm_event_bus().attach(sink)` 或 `runtime.subscribe()` 收事件，
  断言 `type == "kernel_diagnostic"` 且 `data.code` 符合预期。

### 门控

- `runtime.configure(observability=False)` → **事件停止，警告保留**（开发可见性不受记录开关控制）。

---

## 六、易用性 / 可维护性 / 可扩展性论证

| 维度 | 论证 |
|------|------|
| **易用性** | 发射方 = 一个 helper + 一个 code（message 可省略）；消费方 = 既有 `subscribe()` + 按 code 过滤；门控沿用既有 `observability` 开关，无新配置面 |
| **可维护性** | 单一代码注册表（codes.py）防双维护；事件 data 为自由 dict，无 schema 迁移；消息与 detail 调用点同源构造，漂移风险低；12 站点文案逐字保留 → 用户/测试无感知变化 |
| **可扩展性** | 新增诊断 = 加 code + 调 helper（零消费者变更）；新域（流程诊断、编译期诊断、severity 字段）均可非破坏扩展；诊断码命名约定与 SEM_/RUN_ 同构，跨域统一 |

---

## 七、实施步骤（落地后执行）

| 阶段 | 内容 | 验收 |
|------|------|------|
| **A 设计冻结** | 本文档；`NEXT_STEPS`/`PENDING_TASKS §12`/`WORKLOG` 挂指针 | 零代码改动 |
| **B 机制落地** | ① `codes.py` 增 KDIAG 节；② 新建 `core/runtime/observability/diagnostics.py`（helper）；③ **修复 events.py docstring 漂移**（documented-vs-actual 事件类型对账：`task_started`/`chan_closed`/`vm_*` 声明未发射，改为如实清单）；④ helper 单测（警告触发/事件门控/rc 缺省/stacklevel 归属） | 全量 pytest 零回归 |
| **C 站点迁移** | 12 处 runtime warnings → `kernel_diagnostic`（逐批、文案逐字、每批全绿）；每站点核验 rc 可达性（host_interface/loader 等无活跃 EC 站点 → 仅警告面，记录） | 全量 pytest 零回归；warning 归属行不变 |
| **D 事件投影测试** | 代表性站点事件测试（协议回退 / 策略忽略 / 运行时跳过）+ 门控测试（observability 关 → 事件不发射、警告保留）+ 覆盖矩阵补记 | 全量 pytest 零回归 |
| **E docs 治理** | 按 WRITING_GUIDE 写入 `docs/architecture/`（诊断面职责、事件形态、代码表）；`WORKLOG` 记录 | 文档一致 |

---

## 八、遗留 / 风险

| 项 | 说明 | 处置 |
|----|------|------|
| rc 可达性 | host_interface/loader 站点可能在无活跃 EC 时调用 → 事件面不触发 | 实现时逐站点核验；确需事件则在调用链显式传 rc |
| stacklevel 归属 | helper 引入一层间接帧 | 内部用 `stacklevel=3` 保持与现状一致的归属；测试断言归属行 |
| 消息文案 | 迁移须逐字保留 | 比对现状消息；`test_kernel_native_modules.py:98`（match="reserved for kernel-native module"）为回归锚点 |
| events.py 契约漂移 | 文档声明的事件类型与实际发射不符（task_*/vm_*/chan_closed 未发射） | 随 B 阶段修复为如实清单；不借机扩功能 |

---

## 九、决策记录

| 日期 | 决策 | 依据 |
|------|------|------|
| 2026-08-07 | 单一事件类型 `kernel_diagnostic` + `KDIAG_*` 代码注册表，不造 13 个事件类型 | D1：类型词汇表稳定、新增诊断零消费者变更 |
| 2026-08-07 | 单一记录双投影：warnings 不门控 + 事件受 observability 门控 | D2：开发者通道 vs 可编程通道语义不同，非双通道；零回归 |
| 2026-08-07 | 代码即数据，非发射门控；过滤在消费端 | D3：与旧 DebugLevel 门控本质划界 |
| 2026-08-07 | rc 解析 best-effort（显式 > current-EC > 无→仅警告） | D4：与 callables.py 范式同构，低层站点免穿线 |
| 2026-08-07 | 迁移 12 处运行时站点；编译期 scheduler 维持 warnings；不重建流式追踪 | D5：离线面无观测骨架、禁跨层依赖、范围克制 |
| 2026-08-07 | KDIAG 码并入 codes.py 单一注册表 | D6：单一权威源、命名约定与 SEM_/RUN_ 同构 |
| 2026-08-07 | v1 不设 severity/category 字段 | D7：现状全 warning 级；域前缀已编码于 code；未来非破坏可加 |
