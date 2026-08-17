# 观测体系

## 定位

本文档描述 IBCI 的观测体系（observability）：内核如何被内省（snapshot）、如何推送正常流程事件（EventBus）、如何记录异常/降级/策略决策（诊断面），以及这些面的开关控制（configure）。

面向需要扩展观测能力、消费观测数据或实现嵌入式集成的开发者。阅读前需了解运行时上下文（`RuntimeContextImpl`）与值对象家族（`docs/architecture/03_type_system.md`）。

## 核心概念：四个正交语义面

观测需求可归为四类语义，每类对应一个独立机制。四者正交：职责不同、互不替代、共享同一引擎级事件总线。

| 面 | 机制 | 形态 | 职责 |
|----|------|------|------|
| 状态面 | `snapshot()` 聚合 | 同步拉取 | "现在是什么状态" |
| 事件面 | EventBus 域事件 | 推送（正常流程） | "正常域对象发生了什么" |
| 诊断面 | `kernel_diagnostic` 事件 + 警告投影 | 推送（异常/降级/策略） | "内核为何降级 / 做了什么异常决策" |
| 配置面 | `configure()` 控制 | 链式覆盖 | 观测能力的启停 |
| 测试合作面 | `TestHooks` 协议 | 精确回调 | 测试断言精确的 LLM 调用回调 |

**边界判定法**：正常流程 → 事件面；状态查询 → 状态面；异常/降级/策略 → 诊断面；测试精确回调 → 测试合作面。

**为什么需要诊断面**：内核的异常行为（协议回退、策略忽略、运行时降级）若只散落为裸警告字符串，则不可查询、不可计数、不可过滤、不可程序化消费。诊断面为这些行为提供结构化、可消费的记录面，同时保留警告投影保证开发者可见性。

---

## 一、状态面：snapshot

**职责**：同步拉取运行时当前状态。

经 `runtime.snapshot()`（用户级 `iruntime` 模块）聚合各可观测源的快照：任务（tasks）、通道（channels）、槽（slots）、虚拟机（vms）、变量（vars）、LLM 调用（llm）。实现位于 `core/runtime/observability/snapshot.py`。

**关键性质**：
- 快照是"现在是什么"的查询，与诊断的"为何降级"时间轴不同。
- 状态聚合是尽力而为：单源失败不阻断整体快照。

> 名称消歧：观测 snapshot 与 llmexcept 的快照恢复（`syntax/10`）、`snapshot` 值捕获关键字（`syntax/07`）是三个独立概念，仅共享词形。

---

## 二、事件面：EventBus 与域事件

**职责**：推送正常流程的域对象生命周期事件。

**机制**：事件总线（`core/runtime/observability/events.py`）复用 `ChannelCore` 的 pubsub 模式——`emit` = 扇出到全部订阅者缓冲，`subscribe()` 返回订阅者端点（`close` = 干净退订），与用户通道 `c.subscribe()` 同一惯用法。事件类型是数据，不是分发条件。

**发射入口**：`emit_runtime_event(rc, event_type, data)` 是统一发射入口——受 `observability` 开关门控、无订阅者零成本、失败不阻断执行。所有内核事件源经此发射，消除各点内联逻辑。

**事件类型（如实清单）**：

| 类型 | 来源 | 时机 |
|------|------|------|
| `llm_dispatched` / `llm_resolved` | LLM 执行器 | LLM 调用开始 / 结束（含失败） |
| `chan_created` / `slot_updated` | VM handler | 通道 / 槽值对象构造 |
| `configured` | `iruntime` 模块 | 配置变更生效（经 iruntime 直接广播，手动门控） |
| `kernel_diagnostic` | 诊断面 | 内核异常/降级/策略（见下一节） |

**事件形态**：`{"type": <str>, "data": {<自由 dict>}}`。域事件 data 为各域自有载荷。

---

## 三、诊断面：kernel_diagnostic

**职责**：发射"内核为何降级 / 做了什么异常决策"的结构化诊断。

**为什么独立**：诊断不是域对象生命周期事件；把异常/降级/策略塞进域事件词汇表会污染域事件语义，且缺少统一 schema 与代码表。

### 3.1 单一记录、双投影

一次异常构造**一份结构化记录**，两路交付：

```
站点 ── kernel_diagnostic(code, detail, message)
        │
        ├─► 投影A：warnings.warn(message)   —— 开发者可见，不门控
        └─► 投影B：emit_runtime_event("kernel_diagnostic", data)
                                            —— 程序化观测，受 observability 门控
```

- **投影A（警告）**：开发者可见通道，不受观测开关控制，文案与 detail 同源构造。
- **投影B（事件）**：可编程观测通道，受 `observability` 开关门控，无订阅者零成本。
- 二者是一份记录的两路投影，不是两套实现。

### 3.2 发射 helper

```python
kernel_diagnostic(code, detail=None, message=None, *, rc=None)
```

- `code`：`KDIAG_*` 诊断码（`core/base/diagnostics/codes.py`），稳定机器标识。
- `detail`：JSON-safe 站点载荷（如 `{"type_name": "Point", "error": repr(e)}`）。
- `message`：人类可读投影；缺省生成 `f"{code}: {detail!r}"`。
- `rc`：运行时上下文。缺省时按 best-effort 解析：显式 `rc=` > 当前执行上下文 > 无。
  rc 不可达（如 engine 加载期无活跃执行上下文）→ 仅警告投影，事件面跳过（fail-open）。

**事件形态**：

```json
{"type": "kernel_diagnostic",
 "data": {"code": "KDIAG_PROTOCOL_FROM_PROMPT_FALLBACK",
          "detail": {"type_name": "Point", "error": "ValueError(...)"},
          "message": "__from_prompt__ parse failed for Point: ValueError(...)"}}
```

### 3.3 代码即数据，非发射门控

`KDIAG_*` 码是**事件数据**（消费端过滤用），不是发射开关。发射总是构造记录；过滤在消费端，不在发射端。新增诊断 = 加一个码 + 调一次 helper，无消费者变更。

### 3.4 诊断码集

| 码 | 站点 | 触发动机 |
|----|------|---------|
| `KDIAG_PROTOCOL_TO_PROMPT_FALLBACK` | 意图解析 / cast 经 `__to_prompt__` | `__to_prompt__` 调用失败，回退 `to_native()` |
| `KDIAG_PROTOCOL_FROM_PROMPT_FALLBACK` | `__from_prompt__` 解析 / vtable | `__from_prompt__` 调用失败 |
| `KDIAG_PROTOCOL_PAYLOAD_PROMPT_FALLBACK` | `__payload_prompt__` | 载荷协议失败，回退纯文本 |
| `KDIAG_PROTOCOL_VALIDATE_FALLBACK` | `__validate_prompt__` | 校验协议失败（非致命） |
| `KDIAG_PROTOCOL_SNAPSHOT_FALLBACK` | `__snapshot__` | 快照协议失败，回退深克隆 |
| `KDIAG_PROTOCOL_RESTORE_FALLBACK` | `__restore__` | 恢复协议失败，保持现状（best-effort） |
| `KDIAG_POLICY_MODULE_OVERRIDE` | kernel-native 模块保护 | 非 kernel-native 注册尝试覆盖 kernel-native 保留名被忽略 |
| `KDIAG_RUNTIME_COLLECT_SKIP` | 隔离收集 | 变量无法转为原生值，跳过 |
| `KDIAG_RUNTIME_STAGE_SKIP` | Interpreter STAGE 6 预评估 | kernel 令牌缺失，STAGE 6 跳转跳过 |
| `KDIAG_RUNTIME_ENV_LIMIT` | 环境限制异常 | `RecursionError`/`MemoryError`/`SystemError` 判定为环境限制，保留根因发射诊断 |
| `KDIAG_RUNTIME_PRE_EVAL_FALLBACK` | 字段默认值预评估 | 类字段默认值预评估失败（尽力而为优化），留待实例化时求值（实例化路径完整重试 + fail-fast） |

> **码集权威**：完整码集与稳定定义以 `core/base/diagnostics/codes.py` 为机器权威源；人类可读的触发条件与修复指引见 `docs/syntax/15_diagnostics.md`（码集合一致由契约测试强制）。

**编译期诊断**：编译器离线、无事件总线与运行时上下文，编译面诊断维持 `warnings`（不引入 compiler → runtime 跨层依赖）。诊断码命名约定与 `SEM_`/`RUN_`/`LEX_` 同构。

---

## 四、配置面：configure

**职责**：统一控制观测及相关能力的启停。

**机制**：`ConfigStore`（`core/runtime/observability/config.py`）是单点真理——只有一份配置存储承载全部配置。查询按 单实例 → 单调用 → 全局 → 默认 顺序读时解析，不缓存陈旧值。

**配置键**：

| 键 | 默认 | 控制 |
|----|------|------|
| `parallel` | 开 | 并发 dispatch |
| `stream` | 开 | 流式 LLM 增量 |
| `observability` | 开 | 事件面与诊断面的事件投影 |
| `debug` | 关 | 调试细节（call_info 保留） |

**门控语义**：`observability` 只控制**事件投影**。警告投影（诊断面投影A）不受其控制——开发者可见性不因观测开关关闭而丢失。

经 `runtime.configure(...)`（用户级 `iruntime` 模块）链式覆盖：全局 → 单调用 → 单实例（后者优先）。

---

## 五、测试合作面：TestHooks

**职责**：为测试提供精确的 LLM 调用回调，替代在事件流中过滤匹配。

`TestHooks` 协议（`core/runtime/interfaces.py`）三个回调：

| 回调 | 签名 | 调用时机 |
|------|------|---------|
| `on_llm_call` | `(node_uid, sys_prompt, user_prompt, target_model, response)` | LLM 调用成功返回 |
| `on_llm_call_error` | `(node_uid, error)` | LLM provider 失败 |
| `on_dispatch` | `(node_uid)` | LLM 调用提交调度器（dispatch） |

**契约**：回调由 LLM 执行器消费；测试断言应基于回调精确匹配，而非在事件流中过滤。未注入时回调不触发（生产路径零开销）。

**注入**：`engine.test_hooks = hooks`（setter）→ 解释器就绪时注入 `ServiceContext.test_hooks` → LLM 执行器消费。

**与诊断面的区别**：测试合作面是**精确回调**（测试断言用）；诊断面是**结构化记录**（可计数/过滤）。二者互补，不重叠。

---

## 六、消费方式

### 6.1 事件流（IBCI 语言面）

```ibci
import iruntime
subscriber ev = iruntime.subscribe()
chan c = chan(str, "stream")        # 触发 chan_created 域事件
loop:
    dict e = ev.recv()
    if e["type"] == "kernel_diagnostic":
        str code = (str)e["data"]["code"]   # 按 KDIAG_* 过滤
```

### 6.2 警告投影（Python 测试面）

```python
import pytest
with pytest.warns(UserWarning, match="__from_prompt__ parse failed"):
    ...
```

### 6.3 事件投影（Python 测试面）

```python
from core.engine import IBCIEngine
eng = IBCIEngine(root_dir=..., auto_sniff=False)
sub = eng.registry.get_event_bus().subscribe()
# 触发诊断站点...
ok, ev = sub.recv_nowait()
assert ev["type"] == "kernel_diagnostic"
assert ev["data"]["code"] == "KDIAG_..."
```

---

## 约束与边界

- **观测机制不采用 print 推送、级别门控、进程全局单例**：诊断统一经结构化事件与警告双投影。
- **不重建流式流程追踪**：流程级因果诊断（如 llmexcept 重试循环）不在诊断面 v1 范围；新增诊断码可非破坏扩展。
- **诊断面与事件面共用总线与发射入口**（机制同构），仅语义域不同。
- **kernel 层零 runtime 依赖**：事件总线与诊断发射器均由 engine（runtime 组装层）创建并注入
  （`registry.set_event_bus` / `HostInterface.set_diagnostic_emitter`）；kernel 层仅声明抽象槽，
  不 import runtime 具体类型（依赖注入模式，见架构原则 §4.2）。未注入时：事件总线
  `peek` 返回 None（发射 fail-open）、`get` fail-fast（主动使用观测属装配错误）；诊断发射器
  回退 `warnings.warn`（开发者可见性不丢）。
- **诊断事件 data 为自由 dict**：未来新增字段（如 severity）为非破坏扩展，不提前设字段。

## 深入指引

- 运行时上下文与公开访问器：`core/runtime/interpreter/runtime_context.py`
- 诊断码注册表：`core/base/diagnostics/codes.py`
- 观测实现：`core/runtime/observability/`（`snapshot.py` / `events.py` / `diagnostics.py` / `config.py`）
- 用户级 `iruntime` 模块：`ibci_modules/ibci_iruntime/core.py`
